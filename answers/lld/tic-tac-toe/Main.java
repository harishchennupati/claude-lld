import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;

/**
 * A game's life. Every entry point asks one question -- is this state terminal -- instead of two loose
 * booleans that drift apart. ABANDONED makes a disconnect or an expired move clock a real ending rather
 * than a game that hangs forever.
 */
enum GameState {
    NOT_STARTED, IN_PROGRESS, WON, DRAW, ABANDONED;
    /** True once no further move is legal. undo() can take back a WON or a DRAW; ABANDONED is final. */
    boolean isTerminal() { return this == WON || this == DRAW || this == ABANDONED; }
}

/**
 * One player's mark. index is a dense slot (0, 1, 2 ... with no gaps) so the win bookkeeping can be plain int
 * arrays instead of a hash lookup on the code every move runs; it is also what makes a third player cost nothing.
 */
record Symbol(char mark, int index) {
    @Override public String toString() { return String.valueOf(mark); }
}

/** One square, by row and column. A record, so it compares by value and can safely be a map key. */
record Cell(int row, int col) {
    @Override public String toString() { return "(" + row + "," + col + ")"; }
}

/**
 * One accepted move, in order. The list of these is the source of truth for this system: undo reads the
 * last one, replay reads them all, and an audit or a bug report is the same list.
 */
record Move(Player player, Cell cell, long seq, long atMs) {
    /** The mark this move stamped. Read from the player, so it can never disagree with the seat. */
    Symbol symbol() { return player.symbol(); }
    @Override public String toString() { return "#" + seq + " " + player.name() + "[" + symbol() + "] -> " + cell; }
}

/**
 * A refused move, carrying a machine-readable reason. The caller must be able to tell "not your turn"
 * (retry in a moment) from "cell taken" (choose another) from "game over" (stop); a bare false cannot.
 */
class InvalidMoveException extends RuntimeException {
    /** Why the move was refused. A bot's retry loop switches on this. */
    enum Reason { OUT_OF_BOUNDS, CELL_TAKEN, NOT_YOUR_TURN, GAME_OVER, NO_FREE_CELL }
    final Reason reason;
    /** Builds a typed rejection. The message is for humans, the reason is for code. */
    InvalidMoveException(Reason reason, String message) { super(reason + ": " + message); this.reason = reason; }
}

/** Where time comes from. Injected, so a test decides what a move was stamped with and when a clock ran out. */
interface Clock { long nowMs(); }

/**
 * The grid, and nothing else: what is where, stamp, lift, bounds, a copy, a picture. Deliberately no win
 * logic -- if storage knew how you win, "four in a row instead of a full line" would reopen this class.
 * Not thread-safe on purpose: the Game owns it and every touch happens inside the Game's lock.
 */
class Board {
    private final int size;
    private final Symbol[][] grid;
    private int filled;                                  // running count, so "is it a draw" is a comparison, not a scan

    /** A square empty board. Below 3x3 no line can be completed, so it is refused here rather than later. */
    Board(int size) {
        if (size < 3) throw new IllegalArgumentException("a board is at least 3x3, got " + size);
        this.size = size;
        this.grid = new Symbol[size][size];
    }
    /** The side length: the board is size x size. */
    int size() { return size; }
    /** How many squares are stamped. O(1), because place and lift keep it. */
    int filled() { return filled; }
    /** True when no square is left. The draw test, in one comparison. */
    boolean isFull() { return filled == size * size; }
    /** Is that square on the board at all? */
    boolean inBounds(Cell c) { return c.row() >= 0 && c.row() < size && c.col() >= 0 && c.col() < size; }
    /** On the board and not yet stamped. */
    boolean isFree(Cell c) { return inBounds(c) && grid[c.row()][c.col()] == null; }
    /** The mark at those coordinates, or null for empty or off the board. Used by rules that walk outward. */
    Symbol at(int row, int col) {
        return (row >= 0 && row < size && col >= 0 && col < size) ? grid[row][col] : null;
    }
    /** The mark on that square, or null if it is empty. The caller has already checked bounds. */
    Symbol at(Cell c) { return grid[c.row()][c.col()]; }
    /** Stamp a mark. The caller has already checked the square is free; this method does not re-check. */
    void place(Cell c, Symbol s) { grid[c.row()][c.col()] = s; filled++; }
    /** Take a mark back off, for undo and for the rollback when a rule throws. Lifting an empty square does nothing. */
    void lift(Cell c) { if (grid[c.row()][c.col()] != null) { grid[c.row()][c.col()] = null; filled--; } }
    /** Every empty square, in reading order. O(n^2): only bots and screens call it, never the win check. */
    List<Cell> freeCells() {
        List<Cell> out = new ArrayList<>();
        for (int r = 0; r < size; r++)
            for (int c = 0; c < size; c++) if (grid[r][c] == null) out.add(new Cell(r, c));
        return out;
    }
    /** A detached copy. A bot thinks on one of these outside the lock, so the real board cannot move under it. */
    Board copy() {
        Board b = new Board(size);
        for (int r = 0; r < size; r++)
            for (int c = 0; c < size; c++) if (grid[r][c] != null) b.place(new Cell(r, c), grid[r][c]);
        return b;
    }
    /** The board as text, for a console or a log. Presentation only. */
    String render() {
        StringBuilder sb = new StringBuilder();
        for (Symbol[] row : grid) {
            sb.append("     ");
            for (Symbol s : row) sb.append(s == null ? "." : s).append(' ');
            sb.append('\n');
        }
        return sb.toString();
    }
}

// "on a 5x5, four in a row wins" -> the win condition is the first thing an interviewer changes -> Strategy
/**
 * The rule that judges the move that just landed: did it win? One method, because the win condition is the
 * part that changes. A rule that keeps bookkeeping must rewind it in undo(); a stateless rule inherits the
 * no-op. isWinning must be all-or-nothing: if it throws, its own bookkeeping must be untouched, because the
 * referee will only lift the mark from the board.
 */
interface WinStrategy {
    /** Did this move complete a winning line? Called with the mark already stamped on the board. */
    boolean isWinning(Board board, Move move);
    /** Rewind whatever isWinning counted for this move. A stateless rule needs nothing. */
    default void undo(Board board, Move move) { }
}

/**
 * The classic rule -- a full row, column or diagonal -- in four increments instead of a scan. A move touches
 * at most four lines, so one counter per (line, symbol) answers "is this whole line mine" in O(1) on a 3x3
 * and on a 1000x1000 alike. The price is state, which is exactly why undo() is in the contract.
 */
class FullLineWinStrategy implements WinStrategy {
    private final int size;
    private final int[][] rowCount, colCount;            // [line][symbol index]
    private final int[] diagCount, antiCount;

    /** Sized once: symbols is the number of seats, which is why a third player needs no change here. */
    FullLineWinStrategy(int size, int symbols) {
        this.size = size;
        rowCount = new int[size][symbols]; colCount = new int[size][symbols];
        diagCount = new int[symbols];      antiCount = new int[symbols];
    }
    /** Four increments and four comparisons, whatever the board size. */
    @Override public boolean isWinning(Board board, Move m) {
        int r = m.cell().row(), c = m.cell().col(), s = m.symbol().index();
        boolean win = (++rowCount[r][s] == size);
        win |= (++colCount[c][s] == size);               // |= never short-circuits: every counter stays honest
        if (r == c)            win |= (++diagCount[s] == size);
        if (r + c == size - 1) win |= (++antiCount[s] == size);
        return win;
    }
    /** The same four lines, decremented. Without this, undo would leave a phantom win behind. */
    @Override public void undo(Board board, Move m) {
        int r = m.cell().row(), c = m.cell().col(), s = m.symbol().index();
        rowCount[r][s]--; colCount[c][s]--;
        if (r == c)            diagCount[s]--;
        if (r + c == size - 1) antiCount[s]--;
    }
}

// "human, random bot, unbeatable bot" -> how a seat picks a square is a second rule that changes -> Strategy
/**
 * How a seat chooses its square. One method, so a human UI, a test script, a random bot and a minimax bot
 * are the same code path to the Game. Returns null when there is nothing to play.
 */
interface MoveStrategy {
    /** The square this seat wants, judged from a board snapshot it may read at its leisure. */
    Cell chooseMove(Board board, Symbol symbol);
}

/**
 * A human UI, or a test, handing cells in one at a time. When the script runs out it plays the first free
 * square, so a demo can never wedge.
 */
class ScriptedStrategy implements MoveStrategy {
    private final Deque<Cell> script = new ArrayDeque<>();
    /** The cells this seat will play, in order. */
    ScriptedStrategy(Cell... cells) { script.addAll(Arrays.asList(cells)); }
    /** The next scripted cell, else the first free square. */
    @Override public Cell chooseMove(Board board, Symbol symbol) {
        Cell c = script.poll();
        if (c != null) return c;
        List<Cell> free = board.freeCells();
        return free.isEmpty() ? null : free.get(0);
    }
}

/** A bot that plays anywhere free. Seeded, so a demo and a test replay exactly. */
class RandomBotStrategy implements MoveStrategy {
    private final Random rng;
    /** Same seed, same game, every run. */
    RandomBotStrategy(long seed) { rng = new Random(seed); }
    /** A uniformly chosen free square. */
    @Override public Cell chooseMove(Board board, Symbol symbol) {
        List<Cell> free = board.freeCells();
        return free.isEmpty() ? null : free.get(rng.nextInt(free.size()));
    }
}

/**
 * A seat at the table: a name, a mark, and a brain. Identity is the object, so two seats can share a name
 * and never share a turn. The brain is held, not inherited, so human and bot are one class.
 */
final class Player {
    private final String name;
    private final Symbol symbol;
    private final MoveStrategy strategy;

    /** A seat. The strategy is handed in; Player never builds one. */
    Player(String name, Symbol symbol, MoveStrategy strategy) {
        this.name = name; this.symbol = symbol; this.strategy = strategy;
    }
    /** The display name. Not an identity: the object is. */
    String name() { return name; }
    /** This seat's mark, and its dense index into the win counters. */
    Symbol symbol() { return symbol; }
    /** Ask the brain, on a board snapshot. Called outside the game's lock. */
    Cell decide(Board board) { return strategy.chooseMove(board, symbol); }
    @Override public String toString() { return name + "[" + symbol + "]"; }
}

// "a scoreboard, a live log, a websocket feed" -> people who want to know, and must not be in the way -> Observer
/**
 * Anyone who wants to know what happened: a log, a scoreboard, a socket. Every callback is a default, so an
 * observer implements only the event it cares about. Called after the lock is released, never inside it.
 */
interface GameObserver {
    /** A move was accepted. */
    default void onMove(Game game, Move move) { }
    /** A move was taken back. Without this, a spectator would keep showing a mark that is gone. */
    default void onUndo(Game game, Move undone) { }
    /** The game changed state -- started, won, drawn, abandoned, or rewound by an undo. */
    default void onStateChange(Game game, GameState from, GameState to) { }
    /** A move was refused, and why. A dashboard counts these; a client shows the reason. */
    default void onRejected(Game game, Player player, Cell cell, InvalidMoveException e) { }
}

/** Narrates a game to stdout. The engine itself prints nothing; that is the whole point of the interface. */
class MoveLogger implements GameObserver {
    @Override public void onMove(Game g, Move m) { System.out.println("     move   " + m); }
    @Override public void onUndo(Game g, Move m) { System.out.println("     undo   " + m); }
    @Override public void onStateChange(Game g, GameState from, GameState to) {
        System.out.println("     state  " + from + " -> " + to + (to == GameState.WON ? "  winner=" + g.winner() : ""));
    }
    @Override public void onRejected(Game g, Player p, Cell c, InvalidMoveException e) {
        System.out.println("     reject " + p + " at " + c + "  " + e.reason);
    }
}

/**
 * Cross-game state the Game must never own: who won which game. Keyed by game id rather than counted, so an
 * undo that takes a win back also takes the point back -- a tally of increments could not do that.
 */
class ScoreBoard implements GameObserver {
    private final Map<String, String> decided = new ConcurrentHashMap<>();   // game id -> winner's name
    @Override public void onStateChange(Game g, GameState from, GameState to) {
        if (to == GameState.WON && g.winner() != null) decided.put(g.id(), g.winner().name());
        else if (from == GameState.WON) decided.remove(g.id());              // an undo rewound a finished game
    }
    /** Games won by that name, 0 if never. */
    int wins(String name) { int n = 0; for (String w : decided.values()) if (w.equals(name)) n++; return n; }
    @Override public String toString() {
        Map<String, Integer> tally = new TreeMap<>();
        for (String w : decided.values()) tally.merge(w, 1, Integer::sum);
        return "wins=" + tally;
    }
}

/**
 * A spectator that cannot get in the way. It wraps any other observer and delivers on its own background
 * (daemon) thread from a fixed-size queue, so a slow websocket or a blocking log never slows a move down.
 * Decorator: the same kind in, the same kind out, one behaviour added, and the wrapped observer never knows
 * it was wrapped. It must forward EVERY callback: one left out would fall to the interface's empty default.
 */
class AsyncObserver implements GameObserver, AutoCloseable {
    private final GameObserver base;
    private final ThreadPoolExecutor pump;

    /** queueSize events may be in flight; beyond that the OLDEST is dropped -- a spectator loses frames, never the game. */
    AsyncObserver(GameObserver base, int queueSize) {
        this.base = base;
        this.pump = new ThreadPoolExecutor(1, 1, 0L, TimeUnit.MILLISECONDS, new ArrayBlockingQueue<>(queueSize),
                r -> { Thread t = new Thread(r, "observer-pump"); t.setDaemon(true); return t; },
                new ThreadPoolExecutor.DiscardOldestPolicy());
    }
    private void post(Runnable r) { try { pump.execute(r); } catch (RuntimeException ignored) { } }
    @Override public void onMove(Game g, Move m) { post(() -> base.onMove(g, m)); }
    @Override public void onUndo(Game g, Move m) { post(() -> base.onUndo(g, m)); }
    @Override public void onStateChange(Game g, GameState from, GameState to) { post(() -> base.onStateChange(g, from, to)); }
    @Override public void onRejected(Game g, Player p, Cell c, InvalidMoveException e) { post(() -> base.onRejected(g, p, c, e)); }
    /** Stops the pump. Events still queued are dropped. */
    @Override public void close() { pump.shutdownNow(); }
}

/**
 * The referee, and the only class allowed to change anything. "The game is live", "it is your turn", "that
 * square is empty", "stamp it", "did that win", "next player" are one indivisible fact, so all of them happen
 * inside one lock held by this game. The lock is per GAME, so a server runs thousands in parallel.
 */
class Game {
    private final String id;
    private final Board board;
    private final List<Player> players;
    private final Deque<Player> turnOrder;               // rotation, not an index: undo is a rotate-back
    private final List<Move> history = new ArrayList<>();
    private final List<GameObserver> observers = new CopyOnWriteArrayList<>();
    // fair: waiting threads get the lock in arrival order, so a client that spams moves cannot starve (lock out) the other seat
    private final ReentrantLock lock = new ReentrantLock(true);
    private WinStrategy winRule;                         // handed in through configure(); never built here
    private Clock clock;
    private long seq;
    private long turnStartedMs;                          // when the seat on turn began: what the move clock measures
    private volatile GameState state = GameState.NOT_STARTED;     // volatile: a spectator polls without queueing
    private volatile Player winner;

    /**
     * A game with its seats. Fewer than two seats has no opponent; more seats than the board is wide is refused,
     * because most seats could then never fill a line. Symbol indexes must be a dense 0..n-1 (no gaps), because
     * they index the win counters.
     */
    Game(String id, int size, List<Player> players) {
        if (players.size() < 2 || players.size() > size)
            throw new IllegalArgumentException("need 2.." + size + " seats on a " + size + "x" + size + " board, got " + players.size());
        TreeSet<Integer> slots = new TreeSet<>();
        for (Player p : players) slots.add(p.symbol().index());
        if (slots.size() != players.size() || slots.first() != 0 || slots.last() != players.size() - 1)
            throw new IllegalArgumentException("symbol indexes must be a dense 0.." + (players.size() - 1) + ", got " + slots);
        this.id = id;
        this.board = new Board(size);
        this.players = List.copyOf(players);
        this.turnOrder = new ArrayDeque<>(this.players);
    }

    /** The two things this game is given and never builds: the win rule and the clock. Called before the first move. */
    void configure(WinStrategy rule, Clock clock) {
        this.winRule = Objects.requireNonNull(rule, "a game needs a win rule");
        this.clock = Objects.requireNonNull(clock, "a game needs a clock");
        this.turnStartedMs = clock.nowMs();              // the first seat's turn starts now
    }
    /** Register a listener. The list is copy-on-write (each add makes a new array), so a publish already looping is not disturbed. */
    void addObserver(GameObserver o) { observers.add(o); }

    /** This game's id. */
    String id() { return id; }
    /** The side length of the board. */
    int size() { return board.size(); }
    /** The seats, in turn order as they were at the start. */
    List<Player> players() { return players; }
    /** Where the game is. Read from a volatile field, so a spectator never waits on the lock. */
    GameState state() { return state; }
    /** The winner, or null while the game is live, drawn or abandoned. */
    Player winner() { return winner; }
    /** Whose turn it is, or null once the game is over. */
    Player currentPlayer() { lock.lock(); try { return state.isTerminal() ? null : turnOrder.peekFirst(); } finally { lock.unlock(); } }
    /** Every accepted move, in order, as a copy: the caller cannot edit this game's truth. */
    List<Move> history() { lock.lock(); try { return List.copyOf(history); } finally { lock.unlock(); } }
    /** The mark on that square, or null. Bounds-checked, so a test can ask about anywhere. */
    Symbol at(Cell c) { lock.lock(); try { return board.at(c.row(), c.col()); } finally { lock.unlock(); } }
    /** How many squares are stamped. */
    int filled() { lock.lock(); try { return board.filled(); } finally { lock.unlock(); } }
    /** The board as text. Only the copy is taken under the lock; the text is built after it is released. */
    String render() { return snapshot().render(); }
    /** A detached copy of the board, for a bot or a screen that wants to read at its leisure. */
    Board snapshot() { lock.lock(); try { return board.copy(); } finally { lock.unlock(); } }

    /**
     * The critical step. Order matters: every check runs before anything at all is written, so a refused move
     * leaves the board, the turn and the history exactly as they were and the caller can simply try again.
     * The mark, the win bookkeeping, the outcome and the turn all move inside one lock, so no reader can see
     * a stamped square whose game has not yet decided whether it was a win. Listeners are told after unlock.
     *
     * @throws InvalidMoveException with a typed reason, if the move is refused
     */
    Move play(Player player, Cell cell) {
        Move made = null; GameState from = null, to = null; InvalidMoveException bad = null;
        lock.lock();
        try {
            if (winRule == null) throw new IllegalStateException("configure(rule, clock) before the first move");
            if (state.isTerminal())                    bad = new InvalidMoveException(InvalidMoveException.Reason.GAME_OVER, id + " is " + state);
            else if (!board.inBounds(cell))            bad = new InvalidMoveException(InvalidMoveException.Reason.OUT_OF_BOUNDS, cell + " is off a " + board.size() + "x" + board.size() + " board");
            else if (turnOrder.peekFirst() != player)  bad = new InvalidMoveException(InvalidMoveException.Reason.NOT_YOUR_TURN, player + ", it is " + turnOrder.peekFirst() + "'s turn");
            else if (!board.isFree(cell))              bad = new InvalidMoveException(InvalidMoveException.Reason.CELL_TAKEN, cell + " already holds " + board.at(cell));
            if (bad == null) {
                // nothing above wrote anything. From here on, nothing can fail except the rule, which is rolled back.
                Move m = new Move(player, cell, seq + 1, clock.nowMs());
                board.place(cell, player.symbol());
                boolean won;
                try { won = winRule.isWinning(board, m); }
                catch (RuntimeException e) { board.lift(cell); throw e; }   // the move never happened
                seq++;
                history.add(m);
                turnStartedMs = m.atMs();                // the next seat's turn starts the moment this move landed
                from = state;
                if (won)                 { winner = player; state = GameState.WON; }   // winner first: whoever sees WON sees the winner
                else if (board.isFull())   state = GameState.DRAW;           // checked AFTER the win: a line on the last square wins
                else { state = GameState.IN_PROGRESS; turnOrder.addLast(turnOrder.removeFirst()); }
                to = state; made = m;
            }
        } finally { lock.unlock(); }
        if (bad != null) { publishRejected(player, cell, bad); throw bad; }
        publishMove(made);
        if (from != to) publishState(from, to);
        return made;
    }

    /**
     * Ask the seat whose turn it is for a square, then play it. The brain thinks OUTSIDE the lock on a
     * snapshot, and is arbitrated inside it: losing a race is a normal, retriable outcome, not a bug.
     */
    Move playAuto() {
        Player p; Board snap;
        lock.lock();
        try {
            if (state.isTerminal()) throw new InvalidMoveException(InvalidMoveException.Reason.GAME_OVER, id + " is " + state);
            p = turnOrder.peekFirst();
            snap = board.copy();
        } finally { lock.unlock(); }
        Cell c = p.decide(snap);                                   // seconds, if it likes: no lock is held
        if (c == null) throw new InvalidMoveException(InvalidMoveException.Reason.NO_FREE_CELL, "no square left for " + p);
        return play(p, c);
    }

    /**
     * Take the last move back, rewinding all five things that moved together: the board, the win rule's
     * counters, the sequence, the turn and the outcome. Forgetting any one of them is the classic bug --
     * a board that looks empty and a rule that still believes somebody has three in a row. A win or a draw
     * can be taken back; an abandoned game cannot, because the last move is not why it ended.
     */
    Move undo() {
        Move gone; GameState from, to;
        lock.lock();
        try {
            if (history.isEmpty()) throw new IllegalStateException("nothing to undo in " + id);
            if (state == GameState.ABANDONED) throw new IllegalStateException(id + " was abandoned; undo cannot revive it");
            gone = history.remove(history.size() - 1);
            winRule.undo(board, gone);
            board.lift(gone.cell());
            seq--;
            from = state;
            winner = null;
            state = history.isEmpty() ? GameState.NOT_STARTED : GameState.IN_PROGRESS;
            while (turnOrder.peekFirst() != gone.player()) turnOrder.addLast(turnOrder.removeFirst());
            turnStartedMs = clock.nowMs();               // the seat back on turn gets a fresh move clock
            to = state;
        } finally { lock.unlock(); }
        publishUndo(gone);                               // every undo is announced, even one that leaves the state alone
        if (from != to) publishState(from, to);
        return gone;
    }

    /**
     * End the game without a winner: a disconnect, a table closed. A no-op if the game has already ended, so
     * a late call cannot overwrite a win.
     */
    void abandon(String why) {
        GameState from, to; boolean changed = false;
        lock.lock();
        try {
            from = state; to = state;
            if (!state.isTerminal()) { state = GameState.ABANDONED; to = state; changed = true; }
        } finally { lock.unlock(); }
        if (changed) publishState(from, to);
    }

    /**
     * The move clock's check: end the game if the seat on turn has had more than limitMs. Reading the time
     * and abandoning are one step inside the lock, so a move that lands first always beats a late tick.
     * True if this call ended the game.
     */
    boolean abandonIfIdle(long limitMs) {
        GameState from; boolean changed = false;
        lock.lock();
        try {
            from = state;
            if (!state.isTerminal() && clock.nowMs() - turnStartedMs > limitMs) { state = GameState.ABANDONED; changed = true; }
        } finally { lock.unlock(); }
        if (changed) publishState(from, GameState.ABANDONED);
        return changed;
    }

    // Listeners run after the unlock, each in its own try/catch: a broken spectator cannot break a game.
    private void publishMove(Move m) { for (GameObserver o : observers) try { o.onMove(this, m); } catch (RuntimeException ignored) { } }
    private void publishUndo(Move m) { for (GameObserver o : observers) try { o.onUndo(this, m); } catch (RuntimeException ignored) { } }
    private void publishState(GameState from, GameState to) { for (GameObserver o : observers) try { o.onStateChange(this, from, to); } catch (RuntimeException ignored) { } }
    private void publishRejected(Player p, Cell c, InvalidMoveException e) { for (GameObserver o : observers) try { o.onRejected(this, p, c, e); } catch (RuntimeException ignored) { } }
}

/**
 * The thin caller: what a web layer holds. It keeps the live games by id and hands each new one its rule,
 * its clock and the standing observers. It owns no lock of its own -- the lock lives in each Game -- so ten
 * thousand games proceed in parallel and never wait for one another.
 */
class GameService {
    private final Map<String, Game> games = new ConcurrentHashMap<>();
    private final List<GameObserver> standing = new CopyOnWriteArrayList<>();
    private Clock clock = System::currentTimeMillis;

    /** Hand in the clock every new game will be built with. */
    void setClock(Clock c) { clock = c; }
    /** An observer attached to every game created from now on. */
    void addObserver(GameObserver o) { standing.add(o); }
    /**
     * Create a game. Pass null for the rule to get the classic full-line rule sized for this board and these
     * seats; the Game itself never builds a rule.
     */
    Game newGame(String id, int size, List<Player> players, WinStrategy rule) {
        Game g = new Game(id, size, players);
        g.configure(rule != null ? rule : new FullLineWinStrategy(size, players.size()), clock);
        for (GameObserver o : standing) g.addObserver(o);
        if (games.putIfAbsent(id, g) != null) throw new IllegalStateException("a game already has the id " + id);
        return g;
    }
    /** The game with that id, or null. */
    Game game(String id) { return games.get(id); }
    /** Every game still in the map. */
    Collection<Game> live() { return games.values(); }
    /** Forget a finished game, so memory does not grow forever. */
    void end(String id) { games.remove(id); }
}

/** Runs the system: a scripted win, an undo, a win on the last free square, and a fifty-thread race. */
public class Main {
    public static void main(String[] args) throws Exception {
        GameService service = new GameService();
        ScoreBoard scores = new ScoreBoard();
        service.addObserver(new MoveLogger());
        service.addObserver(scores);

        System.out.println("=== 1. scripted 4x4: Ann takes column 0 ===");
        Player ann = new Player("Ann", new Symbol('X', 0), new ScriptedStrategy(new Cell(0, 0), new Cell(1, 0), new Cell(2, 0), new Cell(3, 0)));
        Player bob = new Player("Bob", new Symbol('O', 1), new ScriptedStrategy(new Cell(0, 1), new Cell(1, 1), new Cell(2, 1)));
        Game g1 = service.newGame("g1", 4, List.of(ann, bob), null);
        while (!g1.state().isTerminal()) g1.playAuto();
        System.out.print(g1.render());
        System.out.println("     result " + g1.state() + " winner=" + g1.winner() + "  " + scores);

        System.out.println("=== 2. undo rewinds board, counters, turn and state together ===");
        Move gone = g1.undo();
        System.out.println("     took back " + gone);
        System.out.println("     state=" + g1.state() + " winner=" + g1.winner() + " turn=" + g1.currentPlayer() + " moves=" + g1.history().size());
        g1.play(ann, new Cell(3, 0));                              // the same square again: the counters were rewound, so it wins again
        System.out.println("     replayed the same square -> " + g1.state() + " winner=" + g1.winner());

        System.out.println("=== 3. a line completed on the LAST free square is a win, not a draw ===");
        Cell[] xs = { new Cell(0, 0), new Cell(0, 2), new Cell(2, 0), new Cell(2, 2), new Cell(1, 1) };
        Cell[] os = { new Cell(0, 1), new Cell(1, 0), new Cell(1, 2), new Cell(2, 1) };
        Player cat = new Player("Cat", new Symbol('X', 0), new ScriptedStrategy(xs));
        Player dan = new Player("Dan", new Symbol('O', 1), new ScriptedStrategy(os));
        Game g2 = service.newGame("g2", 3, List.of(cat, dan), null);
        while (!g2.state().isTerminal()) g2.playAuto();
        System.out.print(g2.render());
        System.out.println("     board full=" + (g2.filled() == 9) + "  result " + g2.state() + " winner=" + g2.winner() + "  " + scores);

        System.out.println("=== 4. race: fifty threads stamp the SAME square at the same instant ===");
        Player eve = new Player("Eve", new Symbol('X', 0), new ScriptedStrategy());
        Player fin = new Player("Fin", new Symbol('O', 1), new ScriptedStrategy());
        Game g3 = new Game("g3", 3, List.of(eve, fin));          // built directly, no logger: fifty threads would drown the output
        g3.configure(new FullLineWinStrategy(3, 2), System::currentTimeMillis);
        Cell centre = new Cell(1, 1);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        Map<String, Integer> outcome = new ConcurrentHashMap<>();
        List<Future<?>> shots = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final Player who = (i % 2 == 0) ? eve : fin;
            shots.add(pool.submit(() -> {
                go.await();
                try { g3.play(who, centre); outcome.merge("accepted", 1, Integer::sum); }
                catch (InvalidMoveException e) { outcome.merge(e.reason.name(), 1, Integer::sum); }
                return null;
            }));
        }
        go.countDown();
        for (Future<?> f : shots) f.get();
        pool.shutdown();
        System.out.println("     outcomes " + new TreeMap<>(outcome));
        System.out.println("     accepted=" + outcome.getOrDefault("accepted", 0) + "  marks on the board=" + g3.filled()
                + "  moves in history=" + g3.history().size() + "  turn=" + g3.currentPlayer());
        System.out.print(g3.render());
        System.out.println("done.");
    }
}
