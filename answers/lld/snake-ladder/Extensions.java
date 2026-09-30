import java.util.*;
import java.util.concurrent.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: the two house rules they change mid-round -- both are one small MoveStrategy, and Game is untouched
/**
 * "You win by reaching OR passing the last cell." One line: clamp the landing to the last cell. The game's
 * win check is still `to == boardSize`, so nothing in the turn loop is edited -- that is the whole point of
 * having pulled the rule out in move 3.
 */
final class ReachOrPass implements MoveStrategy {
    @Override public int landingCell(int from, int roll, int boardSize) { return Math.min(from + roll, boardSize); }
}

/**
 * A common house rule: a token sits off the board on cell 0 and only a six brings it on. It is a WRAPPER, not a
 * copy -- it adds the entry gate to whatever rule you already had for the far end of the board, so "must throw a
 * six to start" and "bounce back off 100" compose for free. This is the Decorator of move 3 again, on a different
 * interface.
 */
final class MustRollSixToEnter implements MoveStrategy {
    private final MoveStrategy inner;
    private final int entryRoll;
    /** @param inner the rule for a token already on the board, @param entryRoll the throw that lets you on (6). */
    MustRollSixToEnter(MoveStrategy inner, int entryRoll) { this.inner = inner; this.entryRoll = entryRoll; }
    MustRollSixToEnter(MoveStrategy inner) { this(inner, 6); }
    @Override public int landingCell(int from, int roll, int boardSize) {
        if (from == 0 && roll != entryRoll) return 0;                  // still off the board: the throw is wasted
        return inner.landingCell(from, roll, boardSize);
    }
}

// ---- ext: several dice -- move by the sum, the highest face or the lowest
/** How several dice become one number of steps. */
enum Combine { SUM, MAX, MIN }

/**
 * n dice thrown together and turned into steps by a rule: the sum (two dice give 2 to 12), the highest face or
 * the lowest. Each die is thrown by the one-die Dice it was handed -- a seeded StandardDice in play, a
 * ScriptedDice in a test -- and the result is just another Dice, so the game does not change.
 */
final class CombinedDice implements Dice {
    private final int count;
    private final Dice oneDie;
    private final Combine how;
    /** @param count how many dice, @param oneDie throws a single die, @param how SUM, MAX or MIN of the faces. */
    CombinedDice(int count, Dice oneDie, Combine how) {
        if (count < 1) throw new IllegalArgumentException("at least one die: " + count);
        this.count = count; this.oneDie = oneDie; this.how = how;
    }
    @Override public int roll() {
        int sum = 0, max = Integer.MIN_VALUE, min = Integer.MAX_VALUE;
        for (int i = 0; i < count; i++) {
            int face = oneDie.roll();
            sum += face; max = Math.max(max, face); min = Math.min(min, face);
        }
        return how == Combine.SUM ? sum : how == Combine.MAX ? max : min;
    }
}

// ---- ext: the board from input -- the machine-coding format, and a random board that is valid and can be won
/**
 * Reads the classic machine-coding input: the number of snakes, then one "head tail" pair each; the number of
 * ladders, then one "start end" pair each; the number of players, then one name each. Every pair goes into the
 * same builder, so a bad board is refused by the same checks in build(), with the same messages.
 */
final class BoardInput {
    /** Parse the input into a builder; the caller still chooses the dice and the rules, then calls build(). */
    static GameBuilder read(Scanner in) {
        GameBuilder b = new GameBuilder();
        for (int s = in.nextInt(); s > 0; s--) {
            int head = in.nextInt(), tail = in.nextInt();
            if (tail >= head) throw new IllegalArgumentException("a snake must go down: " + head + " " + tail);
            b.jump(head, tail);
        }
        for (int l = in.nextInt(); l > 0; l--) {
            int start = in.nextInt(), end = in.nextInt();
            if (end <= start) throw new IllegalArgumentException("a ladder must go up: " + start + " " + end);
            b.jump(start, end);
        }
        for (int p = in.nextInt(); p > 0; p--) { String name = in.next(); b.player(name, name); }
        return b;
    }
}

/**
 * PhonePe's version reads a configuration (YAML or JSON there; a Java Properties file here, the same map of keys):
 * N players, a BS x BS board, S snakes, L ladders, D dice. It holds counts, not positions, so the board comes from
 * RandomBoard. The "manual override" the interviewer uses to test edge cases is the builder's own seams: a
 * ScriptedDice for the throws and startAt for each token's starting cell.
 */
final class GameConfig {
    /** keys: players=Gaurav,Sagar  boardSize=10 (a 10 x 10 board)  snakes=9  ladders=8  dice=2 */
    static GameBuilder from(Properties c, Random rng) {
        int cells = Integer.parseInt(c.getProperty("boardSize", "10"));
        cells *= cells;
        GameBuilder b = new GameBuilder().boardSize(cells)
            .board(RandomBoard.generate(cells, Integer.parseInt(c.getProperty("snakes", "0")),
                                        Integer.parseInt(c.getProperty("ladders", "0")), rng))
            .dice(Integer.parseInt(c.getProperty("dice", "1")), 6).seed(rng.nextLong());   // D dice, added up
        for (String name : c.getProperty("players").split(",")) b.player(name.trim(), name.trim());
        return b;
    }
}

/**
 * A random board, valid by construction: propose a random pair of cells and keep it only if the board accepts
 * it, so every placing rule (on the board, one thing per cell, nothing on the last cell, no loop) lives in ONE
 * place, Board.addJump. Then check the board can be won at all, with a breadth-first search over the cells:
 * start at 0, try every throw, follow the jumps, and see whether the last cell is ever reached.
 */
final class RandomBoard {
    /** A board of `size` cells with exactly this many snakes and ladders, from a seeded Random. */
    static Board generate(int size, int snakes, int ladders, Random rng) {
        for (int attempt = 0; attempt < 100; attempt++) {
            Board b = new Board(size);
            int s = snakes, l = ladders;
            for (int tries = 0; s + l > 0 && tries < 100 * size; tries++) {
                int a = 2 + rng.nextInt(size - 2), c = 2 + rng.nextInt(size - 2);   // cells 2..size-1
                if (a == c || (a > c ? s == 0 : l == 0)) continue;                 // a > c is a snake
                try { b.addJump(new Jump(a, c)); } catch (IllegalArgumentException refused) { continue; }
                if (a > c) s--; else l--;
            }
            if (s + l == 0 && winnable(b, 6)) return b;
        }
        throw new IllegalArgumentException("cannot place " + snakes + " snakes and " + ladders + " ladders on " + size + " cells");
    }

    /** Can a token starting on 0 ever rest on the last cell? Breadth-first over the cells: O(cells x faces). */
    static boolean winnable(Board b, int maxRoll) {
        boolean[] seen = new boolean[b.size() + 1];
        ArrayDeque<Integer> queue = new ArrayDeque<>(List.of(0));
        seen[0] = true;
        while (!queue.isEmpty()) {
            int cell = queue.poll();
            if (cell == b.size()) return true;
            for (int r = 1; r <= maxRoll && cell + r <= b.size(); r++) {         // an overshoot is wasted
                int to = cell + r;
                for (Jump j = b.jumpAt(to); j != null; j = b.jumpAt(to)) to = j.end();
                if (!seen[to]) { seen[to] = true; queue.add(to); }
            }
        }
        return false;
    }
}

// ---- ext: turn timers -- a player who does not roll in time forfeits, and the game is never blocked
/**
 * Thirty seconds to roll. It is wired in as an observer, so every turn tells it who is on the clock now,
 * and a sweeper thread (or the next request, which is cheaper) calls forfeitIfLate. It reads the injected
 * Clock and never the wall clock, so a test can make thirty seconds pass instantly. Who is on the clock and
 * since when are ONE value written in one step: a sweeper can never pair the new player with the old start time.
 */
final class TurnTimer {
    /** Who is on the clock, and since when. Immutable, so it is always a matching pair. */
    private record Deadline(String playerId, long sinceMs) {}
    private final Clock clock;
    private final long limitMs;
    private volatile Deadline current;                                 // one write swaps both halves at once
    TurnTimer(Clock clock, long limitMs) { this.clock = clock; this.limitMs = limitMs; }
    /** Start the clock for whoever is now due. Wire it as an observer: game.addObserver((id, t) -> timer.watch(game.whoseTurn())). */
    void watch(String playerId) { current = new Deadline(playerId, clock.nowMs()); }
    /** Forfeit the turn if the clock has run out. Returns true if it did. Safe to call from anywhere. */
    boolean forfeitIfLate(Game g) {
        Deadline d = current;                                          // read once: a pair that belongs together
        if (d == null || clock.nowMs() - d.sinceMs() < limitMs) return false;
        try { g.forfeitTurn(d.playerId()); return true; }
        catch (IllegalStateException e) { return false; }              // somebody already moved: nothing to do
    }
}

// ---- ext: many servers -- every roll for one game goes to the one server that holds it
/**
 * Scaling out without touching Game: the game id picks the server, so every request for one table lands in the
 * same process, and that game's own lock is still the whole concurrency answer. floorMod, because a hashCode can
 * be negative. Adding a server here moves most games; consistent hashing (servers placed on a ring, so a new one
 * takes games only from its neighbour) moves few -- name it if they ask about growing the fleet.
 */
final class GameRouter {
    private final List<GameServer> servers;
    GameRouter(List<GameServer> servers) { this.servers = List.copyOf(servers); }
    /** The one server that owns this game: the same id always gives the same server. */
    GameServer serverFor(String gameId) { return servers.get(Math.floorMod(gameId.hashCode(), servers.size())); }
}

// ---- ext: online play -- a retried request must move the token once
/**
 * The same phone pressing roll twice, or a network retry, must move the token once. The request id is the key:
 * the first call claims it with ONE atomic putIfAbsent, then plays the turn OUTSIDE the map's lock; every later
 * copy finds the claim and waits for the same Turn. Playing the turn inside computeIfAbsent would hold a lock
 * of the map while the game told its screens, so one slow screen could stall another table's roll.
 * A failed turn removes its claim, so the client can simply retry. The honest caveat: in one process a crash
 * loses the record; the real fix is the database version below, where the turn row and the request id are
 * written in one transaction.
 */
final class IdempotentRolls {
    private final ConcurrentHashMap<String, CompletableFuture<Turn>> byRequest = new ConcurrentHashMap<>();
    /** Play this turn once, however many times the request arrives; every copy gets the first one's Turn. */
    Turn roll(Game g, String playerId, String requestId) {
        CompletableFuture<Turn> mine = new CompletableFuture<>();
        CompletableFuture<Turn> first = byRequest.putIfAbsent(requestId, mine);   // the claim: one atomic step
        if (first != null) return first.join();                                 // a copy: wait for the first answer
        try {
            Turn t = g.roll(playerId);                                          // no lock of the map is held here
            mine.complete(t);
            return t;
        } catch (RuntimeException e) {
            byRequest.remove(requestId, mine);                                  // nothing happened: a retry may play
            mine.completeExceptionally(e);
            throw e;
        }
    }
}

// ---- ext: persistence -- the game becomes a row, and the lock becomes a conditional UPDATE
/**
 * Beyond one process the turn number is the version: a turn is accepted only if the stored game is still on
 * the turn the caller thinks it is on. Two servers applying the same turn means one of them updates zero
 * rows and retries with fresh state -- the database doing exactly what the ReentrantLock did in one process.
 *
 *   UPDATE game SET turn_no = turn_no + 1, current_player = ?, positions = ?
 *    WHERE game_id = ? AND turn_no = ?           -- 0 rows updated = somebody else moved first
 *   INSERT INTO turn (game_id, turn_no, request_id, player, roll, from_cell, to_cell) VALUES (...)
 *                                                -- UNIQUE (game_id, request_id) makes the retry safe
 */
interface GameRepository {
    /** Append a turn only if the game is still at expectedTurnNo. False means: re-read and try again. */
    boolean applyTurn(String gameId, int expectedTurnNo, Turn t);
    /** The stored turn number, which is the version a writer must match. */
    int turnNoOf(String gameId);
}

/** A map standing in for the table, with the same compare-and-set semantics so the seam can be tested. */
final class InMemoryGameRepository implements GameRepository {
    private final Map<String, List<Turn>> rows = new ConcurrentHashMap<>();
    @Override public synchronized boolean applyTurn(String gameId, int expectedTurnNo, Turn t) {
        List<Turn> ts = rows.computeIfAbsent(gameId, k -> new ArrayList<>());
        if (ts.size() != expectedTurnNo) return false;                 // the WHERE clause failed: 0 rows
        ts.add(t);
        return true;
    }
    @Override public synchronized int turnNoOf(String gameId) { return rows.getOrDefault(gameId, List.of()).size(); }
}

/** Runs every extension above, and the follow-ups that live in Main.java, so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        // reach-or-pass: 97 plus a 5 wins instead of being wasted
        Game rp = new GameBuilder().id("rp").boardSize(100).moveRule(new ReachOrPass())
            .dice(new ScriptedDice(true, 6))                       // a six, over and over
            .player("a", "A").player("b", "B").build();
        rp.start();
        for (int i = 0; i < 34 && rp.status() != GameStatus.FINISHED; i++) rp.roll(rp.whoseTurn());
        System.out.println("reach-or-pass: winner " + rp.winner().id() + " resting on " + rp.positionOf(rp.winner().id()));

        // "you must throw a six to get on the board", wrapped around the ordinary rule
        Game six = new GameBuilder().id("six").boardSize(50)
            .moveRule(new MustRollSixToEnter(new OvershootStays()))
            .dice(new ScriptedDice(3, 4, 6, 2))
            .player("a", "A").player("b", "B").build();
        six.start();
        System.out.println("a throws a 3 while off the board: still on " + six.roll("a").to()
            + "; b throws a 4: still on " + six.roll("b").to());
        System.out.println("a throws a six: on the board at " + six.roll("a").to()
            + "; next turn b's 2 still leaves b on " + six.roll("b").to());

        // several dice: the same three faces, combined three ways
        for (Combine how : Combine.values())
            System.out.println("three dice showing 3, 5, 2 with " + how + ": move " + new CombinedDice(3, new ScriptedDice(3, 5, 2), how).roll());

        // the board from the classic input, and a random board that is valid and can be won
        Game fromInput = BoardInput.read(new Scanner("2  62 5  33 6   2  2 37  27 46   2 Gaurav Sagar"))
            .dice(new ScriptedDice(true, 2)).build();
        fromInput.start();
        System.out.println("from input: " + fromInput.board().jumpCount() + " jumps, players " + fromInput.turnOrder()
            + "; Gaurav throws a 2 and rests on " + fromInput.roll("Gaurav").to());
        Board rb = RandomBoard.generate(100, 8, 8, new Random(42));
        System.out.println("random board: " + rb.jumpCount() + " jumps, winnable " + RandomBoard.winnable(rb, 6));
        Properties cfg = new Properties();
        cfg.load(new java.io.StringReader("players=Gaurav,Sagar\nboardSize=10\nsnakes=9\nladders=8\ndice=2\n"));
        Game fromConfig = GameConfig.from(cfg, new Random(3)).dice(new ScriptedDice(3)).startAt("Gaurav", 97).build();
        fromConfig.start();
        System.out.println("from config: " + fromConfig.board().size() + " cells, " + fromConfig.board().jumpCount()
            + " jumps; the override starts Gaurav on 97 and throws a 3: " + fromConfig.roll("Gaurav").describe());

        // PhonePe's board: a crocodile (five back), a mine (sit out two turns), and landing on a token sends it home
        ScriptedDice ppDice = new ScriptedDice(9, 3, 9, 3, 1);       // five throws for seven turns: held turns throw nothing
        Game pp = new GameBuilder().id("pp").boardSize(50).crocodile(12).mine(9, 2).capture()
            .dice(ppDice).player("a", "A").player("b", "B").build();
        pp.start();
        System.out.println("PhonePe's board: a crocodile on 12, a mine on 9 (two turns), capture on");
        for (int i = 0; i < 7; i++) System.out.println("  " + pp.roll(pp.whoseTurn()).describe());
        System.out.println("  seven turns took " + ppDice.used() + " throws; positions " + pp.positions());

        // play on for second place
        Game last = new GameBuilder().id("last").boardSize(10).playToLast().dice(new ScriptedDice(true, 5))
            .player("a", "A").player("b", "B").player("c", "C").build();
        last.start();
        last.playOut(20);
        System.out.println("play to the last: places " + last.finishOrder() + ", still playing at the end: "
            + last.turnOrder() + ", status " + last.status());

        // turn timers: thirty seconds on an injected clock, moved by hand
        long[] now = { 1_700_000_000_000L };
        Game tt = new GameBuilder().id("tt").boardSize(50).clock(() -> now[0]).dice(new ScriptedDice(true, 3))
            .player("slow", "Slow").player("quick", "Quick").build();
        TurnTimer timer = new TurnTimer(() -> now[0], 30_000);
        tt.addObserver((gid, turn) -> timer.watch(tt.whoseTurn()));      // re-arm after every turn
        tt.start();
        timer.watch(tt.whoseTurn());
        now[0] += 10_000;
        System.out.println("timer after 10s: forfeited=" + timer.forfeitIfLate(tt) + ", still " + tt.whoseTurn() + "'s turn");
        now[0] += 25_000;
        System.out.println("timer after 35s: forfeited=" + timer.forfeitIfLate(tt) + ", now " + tt.whoseTurn() + "'s turn");

        // many servers: the game id picks the server, the same one every time
        GameRouter router = new GameRouter(List.of(new GameServer(), new GameServer(), new GameServer()));
        GameServer home = router.serverFor("table-42");
        home.host(new GameBuilder().id("table-42").player("a", "A").player("b", "B").build());
        System.out.println("router: table-42 lives on the same server every time: " + (router.serverFor("table-42") == home)
            + ", and that server finds it: " + home.game("table-42").id());

        // online play: a retried request must move the token once
        Game idem = new GameBuilder().id("idem").boardSize(50).dice(new ScriptedDice(true, 4))
            .player("a", "A").player("b", "B").build();
        idem.start();
        IdempotentRolls once = new IdempotentRolls();
        Turn first = once.roll(idem, "a", "req-1");
        Turn again = once.roll(idem, "a", "req-1");
        System.out.println("the same request id twice: same turn=" + (first == again)
            + ", a is on " + idem.positionOf("a") + " and the log has " + idem.turnNumber() + " row");

        // persistence: the conditional update refuses the second writer
        GameRepository repo = new InMemoryGameRepository();
        Turn t1 = idem.history().get(0);
        System.out.println("repository: first write=" + repo.applyTurn("idem", 0, t1)
            + ", the same write again=" + repo.applyTurn("idem", 0, t1)
            + ", stored turns=" + repo.turnNoOf("idem"));

        // undo, and a player who quits: the last one standing wins by default
        Game q = new GameBuilder().id("quit").boardSize(30).dice(new ScriptedDice(true, 3))
            .player("a", "A").player("b", "B").player("c", "C").build();
        q.start();
        q.roll("a");
        String after = "a on " + q.positionOf("a") + ", " + q.whoseTurn() + " due";
        q.undoLastTurn();
        System.out.println("after a's turn: " + after + "   after undo: a on " + q.positionOf("a")
            + ", " + q.whoseTurn() + " due, log rows " + q.turnNumber());
        q.roll("a");
        q.leave("b");
        System.out.println("b quits while due: the turn goes straight to " + q.whoseTurn() + ", queue " + q.turnOrder());
        q.leave("a");
        System.out.println("a quits too: " + q.status() + ", winner by default " + q.winner().name());
    }
}
