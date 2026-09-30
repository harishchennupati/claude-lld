import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;

/** Which way a jump goes. It is derived from the two cells, never stored: a snake goes down, a ladder goes up. */
enum JumpKind { SNAKE, LADDER }

/**
 * The game's life. WAITING = built and valid but nobody may roll yet; IN_PROGRESS = rolls are accepted;
 * FINISHED = the places are decided (the first to rest on the last cell, or everyone but one when the table plays
 * on to the last) and every further roll is refused.
 */
enum GameStatus { WAITING, IN_PROGRESS, FINISHED }

/**
 * How a turn went. PLAYED = a throw and a move; CANCELLED = the throw that broke the extra-turn rule (a third six):
 * the token goes back to where the streak began; HELD = sat out on a mine, no die thrown; TIMED_OUT = the clock ran
 * out, no die thrown. Every kind is a row in the log, so undo and replay treat them all the same way.
 */
enum TurnKind { PLAYED, CANCELLED, HELD, TIMED_OUT }

/**
 * A one-way teleport from one cell to another. A snake and a ladder are the SAME object: only the sign of
 * end - start differs, and a sign is data, not a reason for two classes. Immutable, and it validates the one
 * thing that is always true of a jump.
 */
record Jump(int start, int end) {
    Jump {
        if (start == end) throw new IllegalArgumentException("a jump cannot start and end on the same cell: " + start);
    }
    /** SNAKE if it drags you back, LADDER if it lifts you. Computed, so the two can never disagree. */
    JumpKind kind() { return end < start ? JumpKind.SNAKE : JumpKind.LADDER; }
    @Override public String toString() { return (kind() == JumpKind.SNAKE ? "snake " : "ladder ") + start + "->" + end; }
}

/**
 * A person at the table. Deliberately immutable: the one thing that moves during a game is the token's
 * position, and the GAME owns that, so no two callers can ever write it at once -- and the same player can sit
 * at several tables at the same time.
 */
record Player(String id, String name) {}

/** Where time comes from. Injected, so a test can stamp a turn with any instant it likes. */
interface Clock { long nowMs(); }

// "how would you test a game of random rolls?" -> hide the randomness behind an interface -> Strategy
/** The source of a roll. One method, because "how many dice, with what faces" is the thing that changes. */
interface Dice {
    /** The total of this throw. Must be at least 1. */
    int roll();
}

/** n fair dice of f faces each, driven by a Random that is handed in so a game can be seeded and replayed. */
final class StandardDice implements Dice {
    private final int count, faces;
    private final Random rng;
    /** @param count how many dice, @param faces faces per die, @param rng injected: seed it to reproduce a game. */
    StandardDice(int count, int faces, Random rng) {
        if (count < 1) throw new IllegalArgumentException("at least one die: " + count);
        if (faces < 2) throw new IllegalArgumentException("at least two faces: " + faces);
        this.count = count; this.faces = faces; this.rng = rng;
    }
    @Override public int roll() {
        int sum = 0;
        for (int i = 0; i < count; i++) sum += rng.nextInt(faces) + 1;
        return sum;
    }
}

/**
 * Loaded dice: a scripted sequence, so a test can say "now roll a 6, then a 3" and assert an exact board.
 * It also counts how many rolls were taken, which is how the race test proves a refused request rolls nothing.
 */
final class ScriptedDice implements Dice {
    private final int[] script;
    private final boolean cycle;
    private int used = 0;
    /** A fixed script that runs out: the test that asks for one roll too many gets an error, not a surprise. */
    ScriptedDice(int... script) { this(false, script); }
    /** @param cycle true = start the script again from the top when it runs out. */
    ScriptedDice(boolean cycle, int... script) {
        if (script.length == 0) throw new IllegalArgumentException("an empty script");
        this.script = script.clone(); this.cycle = cycle;
    }
    /** How many rolls have actually been taken out of this dice. */
    int used() { return used; }
    @Override public int roll() {
        if (used >= script.length && !cycle) throw new IllegalStateException("the dice script ran out after " + used + " rolls");
        return script[used++ % script.length];
    }
}

// "what happens when a roll overshoots the last cell?" has more than one right answer -> Strategy
/** The rule that turns a roll into the cell the token lands on, BEFORE any snake or ladder is applied. */
interface MoveStrategy {
    /** The landing cell. Must be between 0 and boardSize; the game refuses anything else rather than trusting it. */
    int landingCell(int from, int roll, int boardSize);
}

/** The classic rule: a roll that would go past the last cell is wasted and the token stays where it is. */
final class OvershootStays implements MoveStrategy {
    @Override public int landingCell(int from, int roll, int boardSize) {
        int target = from + roll;
        return target > boardSize ? from : target;
    }
}

/** The other common rule: you must land exactly, and the extra steps bounce back off the last cell. */
final class BounceBack implements MoveStrategy {
    @Override public int landingCell(int from, int roll, int boardSize) {
        int target = from + roll;
        if (target <= boardSize) return target;
        int bounced = boardSize - (target - boardSize);
        return bounced < 0 ? from : bounced;                      // a roll bigger than the whole board: stay
    }
}

/**
 * What a throw means for the thrower: the turn passes, they throw again, or the whole streak (the throws they
 * have made in a row this go) is cancelled and the token goes back to where the streak began.
 */
enum Next { PASS, AGAIN, CANCEL_STREAK }

// "a six rolls again -- and three sixes in a row cancel all three" -> a rule that wraps a rule -> Decorator
/** Whether the same player throws again. Pure: the game hands in the throw and how many extras this player has had. */
interface ExtraTurnRule {
    /** @param roll what they just threw, @param extrasSoFar how many extra throws in a row they have already had. */
    Next after(int roll, int extrasSoFar);
}

/** The plain rule: one throw, one turn. */
final class NoExtraTurn implements ExtraTurnRule {
    @Override public Next after(int roll, int extrasSoFar) { return Next.PASS; }
}

/** Throw the maximum (a six on one die) and go again. */
final class ExtraTurnOnMax implements ExtraTurnRule {
    private final int max;
    /** @param max the highest total the dice can throw, usually 6. */
    ExtraTurnOnMax(int max) { this.max = max; }
    @Override public Next after(int roll, int extrasSoFar) { return roll == max ? Next.AGAIN : Next.PASS; }
}

/**
 * The house rule, as a wrapper rather than a copy: whatever the inner rule says, the throw that would be the
 * cap-th "again" in a row cancels the whole streak instead -- three sixes and all three are void. It adds that
 * limit to any extra-turn rule, including ones written next year.
 */
final class CappedExtraTurn implements ExtraTurnRule {
    private final ExtraTurnRule base;
    private final int cap;
    /** @param cap the throw that would make `cap` in a row cancels them all: 3 = three sixes cancel. */
    CappedExtraTurn(ExtraTurnRule base, int cap) { this.base = base; this.cap = cap; }
    @Override public Next after(int roll, int extrasSoFar) {
        Next n = base.after(roll, extrasSoFar);
        return n == Next.AGAIN && extrasSoFar + 1 >= cap ? Next.CANCEL_STREAK : n;
    }
}

/**
 * One completed turn: everything that happened, as data. It is the audit log, it is what the observers are
 * handed, it is what a replay reads, and because it records `from` and `to` it is its own undo.
 * `jumps` lists every snake and ladder taken, in order (a ladder can land on a snake); `sentHome` is the token
 * this move knocked back to the start, or null; `won` means the token rested on the last cell.
 */
record Turn(int number, String playerId, TurnKind kind, int roll, int from, int landedOn, int to,
            List<Jump> jumps, String sentHome, boolean extraTurn, boolean won, long atMs) {
    /** One line of commentary, the way a person would say it. */
    String describe() {
        String who = "#" + number + " " + playerId;
        if (kind == TurnKind.HELD) return who + " sits out a turn on the mine at " + from;
        if (kind == TurnKind.TIMED_OUT) return who + " ran out of time at " + from;
        if (kind == TurnKind.CANCELLED) return who + " rolled " + roll + ": one too many in a row, the streak is cancelled, back to " + to;
        StringBuilder s = new StringBuilder(who + " rolled " + roll + ": " + from + " -> " + landedOn);
        for (Jump j : jumps) s.append(j.kind() == JumpKind.SNAKE ? " then a snake down to " : " then a ladder up to ").append(j.end());
        if (sentHome != null) s.append(", and ").append(sentHome).append(" goes back to the start");
        if (extraTurn) s.append(" (rolls again)");
        if (won) s.append("  *** reaches ").append(to).append(" ***");
        return s.toString();
    }
}

/**
 * The board: a number line from 1 to size, plus the handful of cells that do something. The jumps are kept in
 * a map keyed by their start cell because they are sparse -- about twenty interesting cells on a hundred -- so
 * a landing is one hash lookup instead of a scan. Every board rule is enforced here, while the board is built,
 * and build() then freezes it, so the turn loop never has to check a layout it was given.
 */
class Board {
    private final int size;
    private final Map<Integer, Jump> jumps = new HashMap<>();
    private final Map<Integer, Integer> mines = new HashMap<>();      // cell -> how many turns it holds you
    private boolean frozen;                                            // set once by build(); published with the game
    /** @param size the last cell, and the cell you must rest on to win. */
    Board(int size) {
        if (size < 2) throw new IllegalArgumentException("a board needs at least two cells: " + size);
        this.size = size;
    }
    /** The last cell. */
    int size() { return size; }
    /**
     * Add a snake or a ladder, refusing a layout that would make the game wrong: endpoints must be on the
     * board, one cell does at most one thing (so a snake head cannot also be a ladder foot), nothing may start
     * on the winning cell, and no chain of jumps may come back to where it started -- jumps chain (a ladder
     * may end on a snake's head), so a loop would move a token for ever.
     */
    void addJump(Jump j) {
        requireOpen();
        if (j.start() < 1 || j.start() > size) throw new IllegalArgumentException("jump starts off the board: " + j);
        if (j.end() < 1 || j.end() > size) throw new IllegalArgumentException("jump ends off the board: " + j);
        if (j.start() == size) throw new IllegalArgumentException("nothing may start on the winning cell: " + j);
        Jump other = jumps.get(j.start());
        if (other != null) throw new IllegalArgumentException("cell " + j.start() + " already has " + other + ", cannot also have " + j);
        if (mines.containsKey(j.start())) throw new IllegalArgumentException("cell " + j.start() + " already has a mine");
        for (int c = j.end(); jumps.containsKey(c); ) {              // walk the chain this jump would land on
            c = jumps.get(c).end();
            if (c == j.start()) throw new IllegalArgumentException(j + " would close a loop: its chain comes back to " + c);
        }
        jumps.put(j.start(), j);
    }
    /** Add a mine: a token that rests here sits out its next `turns` turns. Same rules: one thing per cell. */
    void addMine(int cell, int turns) {
        requireOpen();
        if (cell < 1 || cell >= size) throw new IllegalArgumentException("a mine must be on the board, not on the last cell: " + cell);
        if (turns < 1) throw new IllegalArgumentException("a mine holds you for at least one turn: " + turns);
        if (jumps.containsKey(cell) || mines.containsKey(cell)) throw new IllegalArgumentException("cell " + cell + " already does something");
        mines.put(cell, turns);
    }
    /** The jump that starts on this cell, or null for a plain cell. O(1). */
    Jump jumpAt(int cell) { return jumps.get(cell); }
    /** How many turns a token resting here must sit out: 0 on every cell but a mine. O(1). */
    int holdAt(int cell) { return mines.getOrDefault(cell, 0); }
    /** How many snakes and ladders there are, for a display. */
    int jumpCount() { return jumps.size(); }
    /** Called by build(): from now on the layout cannot change, so what build() checked stays true. */
    void freeze() { frozen = true; }
    private void requireOpen() {
        if (frozen) throw new IllegalStateException("the board is fixed once a game is built on it");
    }
}

/** Raised when somebody rolls out of turn. Its own type so a caller can tell it apart from a real failure. */
class OutOfTurnException extends IllegalStateException {
    OutOfTurnException(String message) { super(message); }
}

// "the phones both pressed roll" -> whoever hears about a turn must not be inside the lock -> Observer
/** Anybody who wants to know that a turn happened: a screen, a commentator, an analytics sink. One method. */
interface GameObserver {
    /** Called AFTER the game's lock is released, so a slow or broken listener cannot stall the table. */
    void onTurn(String gameId, Turn t);
}

/** The commentary line under the board. An observer that only prints: it holds no game state at all. */
final class Commentary implements GameObserver {
    @Override public void onTurn(String gameId, Turn t) { System.out.println("  " + t.describe()); }
}

/** A quieter screen: it shows only the turns that changed something interesting -- a jump, or the win. */
final class Highlights implements GameObserver {
    @Override public void onTurn(String gameId, Turn t) {
        if (!t.jumps().isEmpty() || t.won()) System.out.println("  " + t.describe());
    }
}

/**
 * The game: the single owner of everything that moves -- every token's position, whose turn it is, the log,
 * the status -- behind one lock. Every rule it obeys was handed to it by the builder, so this class never
 * changes when a rule does. The critical method is roll(): all the checks happen before a die is touched,
 * the whole move is computed into local variables, and only then is anything written.
 */
class Game {
    private final String id;
    private final Board board;
    private final Dice dice;
    private final MoveStrategy moveRule;
    private final ExtraTurnRule extraRule;
    private final Clock clock;
    private final boolean playToLast, capture;
    private final List<Player> roster;
    private final Map<String, Integer> starts;                        // where each token starts; 0 = off the board
    private final Map<String, Integer> positions = new LinkedHashMap<>();
    private final ArrayDeque<String> turns = new ArrayDeque<>();      // FIFO: the head is whose turn it is
    private final List<Turn> log = new ArrayList<>();
    private final List<String> finishOrder = new ArrayList<>();       // first place first
    private final Map<String, Integer> sittingOut = new HashMap<>();  // player -> turns still to sit out on a mine
    private final EnumMap<JumpKind, Integer> jumpsTaken = new EnumMap<>(JumpKind.class);
    private final List<GameObserver> observers = new CopyOnWriteArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();
    private GameStatus status = GameStatus.WAITING;
    private int turnNo = 0;
    private int extrasInARow = 0;

    /** Package-private on purpose: the only way to get a Game is GameBuilder.build(), which validates. */
    Game(String id, Board board, Dice dice, MoveStrategy moveRule, ExtraTurnRule extraRule, Clock clock,
         boolean playToLast, boolean capture, List<Player> roster, Map<String, Integer> starts) {
        this.id = id; this.board = board; this.dice = dice; this.moveRule = moveRule; this.extraRule = extraRule;
        this.clock = clock; this.playToLast = playToLast; this.capture = capture; this.roster = List.copyOf(roster);
        this.starts = Map.copyOf(starts);
        for (Player p : this.roster) { positions.put(p.id(), startOf(p.id())); turns.addLast(p.id()); }
        for (JumpKind k : JumpKind.values()) jumpsTaken.put(k, 0);
    }

    /** The game's id. One lock per game, so this id also decides which server holds the game when there are millions. */
    String id() { return id; }
    /** The board, for a display or for a bot that wants to see what is ahead of it. */
    Board board() { return board; }
    /** Register a listener. It is called after the unlock, and a listener that throws is logged and ignored. */
    void addObserver(GameObserver o) { observers.add(o); }

    /** Open the table. Refused unless there are at least two players and the game has not started already. */
    void start() {
        lock.lock();
        try {
            if (status != GameStatus.WAITING) throw new IllegalStateException("the game is already " + status);
            if (roster.size() < 2) throw new IllegalStateException("a game needs at least two players");
            status = GameStatus.IN_PROGRESS;
        } finally { lock.unlock(); }
    }

    /**
     * One turn, and the method that holds the design. The order is the design:
     *   1 the game must be in progress and it must be this player's turn -- checked BEFORE a die is touched,
     *     so a phone that presses roll out of turn costs the game nothing, not even a random number;
     *   2 read the clock, roll, ask the extra-turn rule, ask the move rule for the landing cell, follow the
     *     jumps to a plain cell, decide the win, a mine, a capture and the extra turn -- all into local variables;
     *   3 only now write: the positions, the counters, the log, the places, and the rotation LAST.
     * Anything that throws in step 2 leaves the game exactly as it was and the same player still to move.
     *
     * @throws OutOfTurnException if it is not this player's turn
     * @throws IllegalStateException if the game has not started or is already finished
     */
    Turn roll(String playerId) {
        Turn t;
        lock.lock();
        try {
            if (status != GameStatus.IN_PROGRESS) throw new IllegalStateException("the game is " + status);
            String due = turns.peek();
            if (!playerId.equals(due)) throw new OutOfTurnException(playerId + " rolled, but it is " + due + "'s turn");
            long now = clock.nowMs();                                 // an injected call can fail: before any write
            if (sittingOut.containsKey(playerId)) {
                t = passWithoutMoving(playerId, TurnKind.HELD, now);  // a mine holds them: no die, the turn passes
            } else {
                int roll = dice.roll();                               // every check passed: now the die is spent
                int from = positions.get(playerId);
                Next next = extraRule.after(roll, extrasInARow);
                boolean played = next != Next.CANCEL_STREAK;
                int landedOn = from, to;
                List<Jump> path = new ArrayList<>(2);
                if (!played) {                                        // e.g. a third six: back to where the streak began
                    to = extrasInARow == 0 ? from : log.get(log.size() - extrasInARow).from();
                } else {
                    landedOn = moveRule.landingCell(from, roll, board.size());
                    if (landedOn < 0 || landedOn > board.size())
                        throw new IllegalStateException("the move rule returned an off-board cell: " + landedOn);
                    to = landedOn;
                    for (Jump j = board.jumpAt(to); j != null; j = board.jumpAt(to)) {   // jumps chain to a plain cell
                        path.add(j);
                        to = j.end();
                        if (to < 0 || to > board.size() || path.size() > board.size())
                            throw new IllegalStateException("the jumps left the board or looped at " + to);
                    }
                }
                boolean won = played && to == board.size();           // the win is checked on the RESTING cell
                int hold = played && !won ? board.holdAt(to) : 0;     // a mine: sit out the next `hold` turns
                String sentHome = capture && played && !won ? tokenOn(to, playerId) : null;
                boolean again = played && !won && hold == 0 && next == Next.AGAIN;

                positions.put(playerId, to);                          // the first write of the whole method
                if (sentHome != null) positions.put(sentHome, startOf(sentHome));
                if (hold > 0) sittingOut.put(playerId, hold);
                for (Jump j : path) jumpsTaken.merge(j.kind(), 1, Integer::sum);
                t = new Turn(++turnNo, playerId, played ? TurnKind.PLAYED : TurnKind.CANCELLED, roll, from, landedOn, to,
                             List.copyOf(path), sentHome, again, won, now);
                log.add(t);
                if (won) finish(playerId);
                else if (again) extrasInARow++;
                else passTurn();                                      // rotate last, so a reader is never half-updated
            }
        } finally { lock.unlock(); }
        publish(t);                                                   // the screens hear outside the lock
        return t;
    }

    /**
     * Give up the turn without moving: the clock ran out. Same lock, same log, no die thrown. A player held by a
     * mine loses that held turn the same way, so the timer and the mine can never disagree about who is due.
     */
    Turn forfeitTurn(String playerId) {
        Turn t;
        lock.lock();
        try {
            if (status != GameStatus.IN_PROGRESS) throw new IllegalStateException("the game is " + status);
            String due = turns.peek();
            if (!playerId.equals(due)) throw new OutOfTurnException(playerId + " cannot forfeit " + due + "'s turn");
            long now = clock.nowMs();
            t = passWithoutMoving(playerId, sittingOut.containsKey(playerId) ? TurnKind.HELD : TurnKind.TIMED_OUT, now);
        } finally { lock.unlock(); }
        publish(t);
        return t;
    }

    /** A turn that passes with no throw (HELD or TIMED_OUT): logged like any other, then the turn moves on. */
    private Turn passWithoutMoving(String playerId, TurnKind kind, long now) {
        int at = positions.get(playerId);
        if (kind == TurnKind.HELD) sittingOut.computeIfPresent(playerId, (k, v) -> v == 1 ? null : v - 1);
        Turn t = new Turn(++turnNo, playerId, kind, 0, at, at, at, List.of(), null, false, false, now);
        log.add(t);
        passTurn();
        return t;
    }

    /** The head of the queue goes to the back, and the next player starts a fresh streak. */
    private void passTurn() { extrasInARow = 0; turns.addLast(turns.poll()); }

    /**
     * The player on turn rested on the last cell: they take the next place and leave the rotation. The game ends
     * at the first finisher, or -- when the table plays on to the last -- once only one player is still playing.
     */
    private void finish(String playerId) {
        finishOrder.add(playerId);
        turns.poll();                                                 // the finisher was the head of the queue
        extrasInARow = 0;
        if (!playToLast || turns.size() < 2) status = GameStatus.FINISHED;
    }

    /** Where this player's token starts, and goes back to when it is captured: 0 (off the board) unless set. */
    private int startOf(String playerId) { return starts.getOrDefault(playerId, 0); }

    /** Another token still in play on this cell, or null. O(players) -- a table has fewer than ten. */
    private String tokenOn(int cell, String mover) {
        if (cell == 0) return null;                                   // everyone may wait off the board
        for (String p : turns) if (!p.equals(mover) && positions.get(p) == cell) return p;
        return null;
    }

    /**
     * Take the last turn back: a misclick, a phone that fired twice, a referee at a tournament. It is a walk
     * backwards through the writes roll() made, under the same lock: the position goes back to `from`, a token
     * it knocked home comes back, the jump counters come down, a mine's hold is taken off (or a held turn is
     * owed again), the log row is dropped, a finish is unmade, and the queue is rotated backwards if that turn
     * rotated it. Because the Turn record kept `from`, there is no separate undo stack.
     * The observers are NOT told: onTurn means "a turn happened". Telling them would need a second method on
     * GameObserver, and a two-method interface is a real cost -- name it rather than pretend it is free.
     *
     * @return the turn that was undone
     * @throws IllegalStateException if no turn has been played, or the game was ended by players leaving
     */
    Turn undoLastTurn() {
        lock.lock();
        try {
            if (log.isEmpty()) throw new IllegalStateException("there is no turn to undo");
            Turn t = log.get(log.size() - 1);
            if (status == GameStatus.FINISHED && !t.won())
                throw new IllegalStateException("the game ended because players left; there is no move to take back");
            log.remove(log.size() - 1);
            turnNo--;
            positions.put(t.playerId(), t.from());
            if (t.sentHome() != null) positions.put(t.sentHome(), t.to());   // the knocked-home token comes back
            for (Jump j : t.jumps()) jumpsTaken.merge(j.kind(), -1, Integer::sum);
            if (t.kind() == TurnKind.HELD) sittingOut.merge(t.playerId(), 1, Integer::sum);   // that held turn is owed again
            else if (t.kind() == TurnKind.PLAYED && !t.won() && board.holdAt(t.to()) > 0) sittingOut.remove(t.playerId());
            if (t.won()) {                                           // un-finish: back to the head of the queue
                finishOrder.remove(finishOrder.size() - 1);
                turns.addFirst(t.playerId());
                status = GameStatus.IN_PROGRESS;
            } else if (!t.extraTurn() && t.playerId().equals(turns.peekLast())) {
                turns.addFirst(turns.pollLast());                    // un-rotate, unless somebody has left since
            }
            extrasInARow = extrasBehind(turns.peek());               // read the counter back off the log
            return t;
        } finally { lock.unlock(); }
    }

    /** How many extra throws in a row this player had already had, counted backwards off the log. */
    private int extrasBehind(String playerId) {
        int n = 0;
        for (int i = log.size() - 1; i >= 0; i--) {
            Turn x = log.get(i);
            if (!x.playerId().equals(playerId) || !x.extraTurn()) break;
            n++;
        }
        return n;
    }

    /**
     * A player quits or drops off the network. They come out of the turn queue, so the turn passes on at once
     * if it was theirs; their token and their rows in the log stay, because history must keep telling the
     * truth. When one player is left standing, the game is FINISHED -- and if nobody has finished yet, that
     * player wins by default. Removing from the middle of the deque is O(n) in the number of PLAYERS, under ten.
     *
     * @throws NoSuchElementException if that player is not at this table
     */
    void leave(String playerId) {
        lock.lock();
        try {
            if (status == GameStatus.FINISHED) throw new IllegalStateException("the game is " + status);
            boolean wasDue = playerId.equals(turns.peek());
            if (!turns.remove(playerId)) throw new NoSuchElementException("not at this table: " + playerId);
            if (wasDue) extrasInARow = 0;                            // only the player on turn has a streak going
            sittingOut.remove(playerId);
            if (turns.size() == 1) {
                if (finishOrder.isEmpty()) finishOrder.add(turns.peek());
                status = GameStatus.FINISHED;
            }
        } finally { lock.unlock(); }
    }

    /** Play the whole game by itself, for a demo or a simulation. Stops at the win or at maxTurns. */
    Player playOut(int maxTurns) {
        for (int i = 0; i < maxTurns; i++) {
            String due = whoseTurn();
            if (due == null) break;
            roll(due);
        }
        return winner();
    }

    /** Where this token is: 0 means it has not entered the board yet. O(1). */
    int positionOf(String playerId) {
        lock.lock();
        try {
            Integer p = positions.get(playerId);
            if (p == null) throw new NoSuchElementException("no such player: " + playerId);
            return p;
        } finally { lock.unlock(); }
    }
    /** Whose turn it is, or null once the game is finished. O(1): the head of the queue. */
    String whoseTurn() { lock.lock(); try { return status == GameStatus.FINISHED ? null : turns.peek(); } finally { lock.unlock(); } }
    /** WAITING, IN_PROGRESS or FINISHED. */
    GameStatus status() { lock.lock(); try { return status; } finally { lock.unlock(); } }
    /** First place, or null while nobody has finished. */
    Player winner() {
        lock.lock();
        try {
            if (finishOrder.isEmpty()) return null;
            for (Player p : roster) if (p.id().equals(finishOrder.get(0))) return p;
            return null;
        } finally { lock.unlock(); }
    }
    /** The places so far, first place first. When a table plays on, whoever is still playing at the end comes last. */
    List<String> finishOrder() { lock.lock(); try { return List.copyOf(finishOrder); } finally { lock.unlock(); } }
    /** Every token's cell, in join order, from one instant. */
    Map<String, Integer> positions() { lock.lock(); try { return new LinkedHashMap<>(positions); } finally { lock.unlock(); } }
    /** The turn order as it stands now, the next player first. */
    List<String> turnOrder() { lock.lock(); try { return new ArrayList<>(turns); } finally { lock.unlock(); } }
    /** Everyone at the table. */
    List<Player> roster() { return roster; }
    /** Every turn that has been played, oldest first: the audit log, and the input to a replay. */
    List<Turn> history() { lock.lock(); try { return List.copyOf(log); } finally { lock.unlock(); } }
    /** How many turns have been played. */
    int turnNumber() { lock.lock(); try { return turnNo; } finally { lock.unlock(); } }
    /** How many snakes were bitten and how many ladders climbed, for the scoreboard. */
    Map<JumpKind, Integer> jumpsTaken() { lock.lock(); try { return new EnumMap<>(jumpsTaken); } finally { lock.unlock(); } }

    /** Tell every observer, outside the lock, and survive one that throws. */
    private void publish(Turn t) {
        for (GameObserver o : observers) {
            try { o.onTurn(id, t); } catch (RuntimeException ex) { System.err.println("[observer failed] " + ex.getMessage()); }
        }
    }
}

/**
 * The only way to build a Game. There are a dozen knobs and four rules that must always hold (two or more
 * players, unique ids, a legal layout, no loop), so a constructor with a dozen parameters would be unreadable
 * and would check nothing: build() is the single choke point that constructs the board, replays every jump
 * and mine through the board's checks (which fail fast on a bad layout), freezes it, and hands Game a world
 * that is already valid. Game's constructor is package-private, so an invalid Game cannot be made at all.
 */
final class GameBuilder {
    private String id = "g1";
    private int boardSize = 100, diceCount = 1, faces = 6;
    private Random rng = new Random();
    private Dice dice;                                            // set this to override the fair dice
    private Board board;                                          // set this to override the plain board
    private MoveStrategy moveRule = new OvershootStays();
    private ExtraTurnRule extraRule = new NoExtraTurn();
    private Clock clock = System::currentTimeMillis;
    private boolean playToLast = false, capture = false;
    private final List<Jump> jumps = new ArrayList<>();
    private final Map<Integer, Integer> mines = new LinkedHashMap<>();
    private final Map<String, Integer> starts = new HashMap<>();
    private final List<Player> players = new ArrayList<>();

    /** The game id: the key it is stored under, and what decides which server holds it when there are millions. */
    GameBuilder id(String v) { id = v; return this; }
    /** How many cells; the last one is the one you must rest on to win. */
    GameBuilder boardSize(int v) { boardSize = v; return this; }
    /** How many fair dice, and how many faces each. Ignored if dice(...) is handed in. */
    GameBuilder dice(int count, int facesPerDie) { diceCount = count; faces = facesPerDie; return this; }
    /** Seed the randomness so the same game plays out every run. */
    GameBuilder seed(long seed) { rng = new Random(seed); return this; }
    /** Hand in the dice yourself: scripted for a test, weighted for a house rule. */
    GameBuilder dice(Dice d) { dice = d; return this; }
    /** Hand in a board yourself: a subclass with special cells, for instance. */
    GameBuilder board(Board b) { board = b; return this; }
    /** The overshoot rule: stay put (default) or bounce back. */
    GameBuilder moveRule(MoveStrategy m) { moveRule = m; return this; }
    /** The extra-turn rule: none (default), on a six, or a capped version of either. */
    GameBuilder extraTurn(ExtraTurnRule r) { extraRule = r; return this; }
    /** Where time comes from. A test hands in a fixed instant. */
    GameBuilder clock(Clock c) { clock = c; return this; }
    /** One snake or ladder. Validated in build(), not here, so the error names the whole layout. */
    GameBuilder jump(int from, int to) { jumps.add(new Jump(from, to)); return this; }
    /** A crocodile takes you exactly five cells back: it is a snake of length five, so it IS a jump. */
    GameBuilder crocodile(int cell) { return jump(cell, cell - 5); }
    /** A mine: a token that rests here sits out its next `turns` turns. */
    GameBuilder mine(int cell, int turns) { mines.put(cell, turns); return this; }
    /** Landing on a cell another token is on sends that token back to its start (off: tokens may share a cell). */
    GameBuilder capture() { capture = true; return this; }
    /** Where one player's token starts (default 0, off the board): PhonePe's input gives each player a start cell. */
    GameBuilder startAt(String playerId, int cell) { starts.put(playerId, cell); return this; }
    /** Play on after the first finisher, for second and third place, until one player is left. */
    GameBuilder playToLast() { playToLast = true; return this; }
    /** One player, in turn order. */
    GameBuilder player(String playerId, String name) { players.add(new Player(playerId, name)); return this; }

    /**
     * Build a valid game or throw. Checks: at least two players, no duplicate ids, every start cell on the board,
     * and every jump and mine legal on this board (on the board, one thing per cell, nothing starting on the
     * winning cell, no loop).
     */
    Game build() {
        if (players.size() < 2) throw new IllegalArgumentException("a game needs at least two players: " + players.size());
        Set<String> ids = new HashSet<>();
        for (Player p : players) if (!ids.add(p.id())) throw new IllegalArgumentException("duplicate player id: " + p.id());
        Board b = board != null ? board : new Board(boardSize);
        for (Map.Entry<String, Integer> st : starts.entrySet())
            if (!ids.contains(st.getKey()) || st.getValue() < 0 || st.getValue() >= b.size())
                throw new IllegalArgumentException("a start must be a player's, on the board, before the last cell: " + st);
        for (Jump j : jumps) b.addJump(j);                        // fails fast, before a Game exists
        for (Map.Entry<Integer, Integer> m : mines.entrySet()) b.addMine(m.getKey(), m.getValue());
        b.freeze();                                               // from here on the layout cannot change
        Dice d = dice != null ? dice : new StandardDice(diceCount, faces, rng);
        return new Game(id, b, d, moveRule, extraRule, clock, playToLast, capture, players, starts);
    }
}

/**
 * The thin caller: it finds the game and calls it. It owns no game state and takes no lock of its own, which
 * is exactly why a million tables can play at the same time -- each game's own lock is the only place anyone waits.
 */
final class GameServer {
    private final Map<String, Game> games = new ConcurrentHashMap<>();
    /** Put a built game on the server. Refused if the id is taken: a second table must never replace the first. */
    Game host(Game g) {
        if (games.putIfAbsent(g.id(), g) != null) throw new IllegalArgumentException("a game with id " + g.id() + " is already hosted");
        return g;
    }
    /** The game, or an error. O(1). */
    Game game(String gameId) {
        Game g = games.get(gameId);
        if (g == null) throw new NoSuchElementException("no such game: " + gameId);
        return g;
    }
    /** One roll from one phone. The server does nothing but route: the game decides whether it is allowed. */
    Turn roll(String gameId, String playerId) { return game(gameId).roll(playerId); }
    /** How many tables are live. */
    int size() { return games.size(); }
}

/**
 * Proof it works: the two tricky rules checked by hand, a seeded game played to a win, a ladder that lands on a
 * snake head (the jumps chain), three sixes that cancel, and four phones hammering roll at the same instant with
 * the log coming out exactly consistent.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        // the two rules that are always asked about are pure functions: check them without a game at all
        MoveStrategy stay = new OvershootStays(), bounce = new BounceBack();
        System.out.println("at 98, roll 5, board 100 -> stays at " + stay.landingCell(98, 5, 100)
            + " (the roll is wasted); bounce-back goes to " + bounce.landingCell(98, 5, 100));
        System.out.println("at 98, roll 2, board 100 -> lands exactly on " + stay.landingCell(98, 2, 100) + " and wins");

        // a seeded game: the same run every time, which is what makes a bug reproducible
        Game g = new GameBuilder().id("table-1").boardSize(100).dice(1, 6).seed(7)
            .jump(2, 38).jump(7, 14).jump(8, 31).jump(15, 26).jump(21, 42).jump(28, 84).jump(36, 44)
            .jump(51, 67).jump(71, 91).jump(78, 98).jump(87, 94)                       // ladders
            .jump(16, 6).jump(46, 25).jump(49, 11).jump(62, 19).jump(64, 60).jump(74, 53)
            .jump(89, 68).jump(92, 88).jump(95, 75).jump(99, 80)                        // snakes
            .player("alice", "Alice").player("bob", "Bob").player("carol", "Carol")
            .build();
        g.addObserver(new Highlights());
        g.start();
        System.out.println("turn order: " + g.turnOrder() + ", board of " + g.board().size()
            + " cells with " + g.board().jumpCount() + " jumps");
        Player w = g.playOut(2000);
        System.out.println("winner: " + (w == null ? "nobody yet" : w.name()) + " in " + g.turnNumber()
            + " turns; positions " + g.positions());
        System.out.println("snakes and ladders taken: " + g.jumpsTaken());
        try { g.roll("alice"); } catch (IllegalStateException e) { System.out.println("after the win: " + e.getMessage()); }

        // the jumps chain: a ladder whose top is a snake head takes the snake too -- and a loop is refused at build()
        Game chain = new GameBuilder().id("chain").boardSize(50).dice(new ScriptedDice(4))
            .jump(4, 20).jump(20, 3).player("p1", "P1").player("p2", "P2").build();
        chain.start();
        Turn t = chain.roll("p1");
        System.out.println("ladder 4->20 whose top is snake 20->3: token rests on " + t.to() + " after " + t.jumps().size() + " jumps");
        try { new GameBuilder().jump(10, 30).jump(30, 10).player("p1", "P1").player("p2", "P2").build(); }
        catch (IllegalArgumentException e) { System.out.println("a layout whose jumps loop is refused: " + e.getMessage()); }

        // a six rolls again, but three in a row cancel all three and the turn passes: a rule wrapped in a rule
        Game sixes = new GameBuilder().id("sixes").boardSize(60).dice(new ScriptedDice(6, 6, 6, 2))
            .extraTurn(new CappedExtraTurn(new ExtraTurnOnMax(6), 3))
            .player("p1", "P1").player("p2", "P2").build();
        sixes.addObserver(new Commentary());
        sixes.start();
        sixes.roll("p1"); sixes.roll("p1"); sixes.roll("p1");
        System.out.println("three sixes: p1 is back on " + sixes.positionOf("p1")
            + " and the turn has passed to " + sixes.whoseTurn());

        // four phones press roll at the same instant, over and over: only the player on turn may move
        Game race = new GameBuilder().id("race").boardSize(400).dice(new ScriptedDice(true, 3, 5, 2, 6, 1, 4))
            .jump(12, 40).jump(60, 22).jump(120, 180).jump(200, 90)
            .player("p0", "P0").player("p1", "P1").player("p2", "P2").player("p3", "P3").build();
        race.start();
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<int[]>> fs = new ArrayList<>();
        for (int i = 0; i < 8; i++) {
            final int seed = i;
            fs.add(pool.submit(() -> {
                go.await();
                int ok = 0, refused = 0;
                Random r = new Random(seed);
                for (int k = 0; k < 50; k++) {
                    try { race.roll("p" + r.nextInt(4)); ok++; }
                    catch (OutOfTurnException e) { refused++; }
                    catch (IllegalStateException e) { refused++; }
                }
                return new int[] { ok, refused };
            }));
        }
        go.countDown();
        int ok = 0, refused = 0;
        for (Future<int[]> f : fs) { int[] r = f.get(); ok += r[0]; refused += r[1]; }
        pool.shutdown();
        List<Turn> log = race.history();
        Map<String, Integer> replay = new LinkedHashMap<>();
        for (Player p : race.roster()) replay.put(p.id(), 0);
        boolean sane = log.size() == ok;
        for (int i = 0; i < log.size(); i++) {
            Turn x = log.get(i);
            if (x.number() != i + 1) sane = false;                                  // turn numbers with no gaps
            if (replay.get(x.playerId()) != x.from()) sane = false;                 // each token continues where it was
            replay.put(x.playerId(), x.to());
        }
        System.out.println("400 roll attempts from 8 threads: accepted=" + ok + " refused=" + refused
            + ", log rows=" + log.size() + ", replay matches live positions: " + replay.equals(race.positions())
            + ", log consistent: " + sane);
        if (!sane || !replay.equals(race.positions())) throw new AssertionError("the game lost or doubled a turn");
    }
}
