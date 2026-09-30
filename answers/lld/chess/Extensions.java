import java.util.*;
import java.util.function.Function;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: a fairy piece -- "add a Chancellor: it moves like a rook AND a knight". One new class, one line.
/**
 * The Chancellor rides the four straight rays and also hops the knight's L. It touches nothing else: move
 * generation calls attacks(), and check detection asks the capability flags, so the board, the game, castling,
 * checkmate and stalemate all keep working with no edit at all. That is Open/Closed, paid out.
 */
class Chancellor extends Piece {
    private static final int[][] JUMPS = { {2, 1}, {2, -1}, {-2, 1}, {-2, -1}, {1, 2}, {1, -2}, {-1, 2}, {-1, -2} };
    Chancellor(Color color) { super(color, 'C'); }

    /** Rook rays until blocked, plus the eight knight squares. */
    @Override void attacks(Board board, Position from, List<Position> out) {
        for (int[] d : SlidingPiece.STRAIGHT)
            for (int step = 1; ; step++) {
                int r = from.row() + d[0] * step, c = from.col() + d[1] * step;
                if (!Position.onBoard(r, c)) break;
                out.add(Position.at(r, c));
                if (board.at(r, c) != null) break;
            }
        for (int[] j : JUMPS) {
            int r = from.row() + j[0], c = from.col() + j[1];
            if (Position.onBoard(r, c)) out.add(Position.at(r, c));
        }
    }
    @Override boolean ridesStraight() { return true; }
    @Override boolean hopsKnight() { return true; }
}
// the only change at the call site, once, at start-up:
//     Pieces.register('C', Chancellor::new);
// after that 'C' and 'c' work in FEN, in printing and in promotion, and isAttacked finds it because it asks
// "do you ride straight lines? do you hop like a knight?" instead of "are you a rook?".

// ---- ext: an AI opponent -- legalMoves() IS the move generator, so a search only has to consume it
/** What a position is worth to one side. The one thing an engine's strength actually comes from. */
interface Evaluator { int score(Board board, Color side); }

/** The crudest honest evaluator: material only, in centipawns. Good enough to stop hanging a queen. */
class MaterialEvaluator implements Evaluator {
    private static int value(char letter) {
        return switch (Character.toUpperCase(letter)) {
            case 'P' -> 100; case 'N' -> 320; case 'B' -> 330;
            case 'R' -> 500; case 'Q' -> 900; case 'C' -> 850; default -> 0;
        };
    }
    public int score(Board board, Color side) {
        int total = 0;
        for (int r = 0; r < 8; r++)
            for (int c = 0; c < 8; c++) {
                Piece p = board.at(r, c);
                if (p != null) total += (p.color == side ? 1 : -1) * value(p.symbol());
            }
        return total;
    }
}

/** Whoever decides a move: a human at a screen, a random mover, a search. Handed to the loop, never built by it. */
interface Player { Move choose(Game game); }

/** A legal move at random. Useful as the opponent in a test, and as the floor a real engine must beat. */
class RandomPlayer implements Player {
    private final Random random;
    RandomPlayer(long seed) { random = new Random(seed); }
    public Move choose(Game game) { List<Move> legal = game.legalMoves(); return legal.get(random.nextInt(legal.size())); }
}

/**
 * Alpha-beta minimax over the rules layer. It never touches the pieces or the board directly: it plays a move,
 * asks for the score, and takes it back -- exactly what the legality filter already does. It searches on a COPY
 * made from the FEN, so no spectator ever sees the moves the engine is only thinking about.
 */
class MinimaxPlayer implements Player {
    private final Evaluator evaluator;
    private final int depth;
    MinimaxPlayer(Evaluator evaluator, int depth) { this.evaluator = evaluator; this.depth = depth; }

    public Move choose(Game game) {
        Game work = Game.fromFen("search", game.fen());                  // a private copy: no observers, no shared lock
        Color me = work.toMove();
        Move best = null; int bestScore = Integer.MIN_VALUE;
        for (Move m : work.legalMoves()) {
            work.play(m);
            int score = search(work, depth - 1, Integer.MIN_VALUE + 1, Integer.MAX_VALUE - 1, me);
            work.undo();
            if (score > bestScore) { bestScore = score; best = m; }
        }
        return best;
    }

    private int search(Game g, int depth, int alpha, int beta, Color me) {
        if (g.status().over())
            return g.status() == GameStatus.CHECKMATE ? (g.toMove() == me ? -100_000 : 100_000) : 0;
        if (depth == 0) return evaluator.score(g.board(), me);
        boolean maximising = g.toMove() == me;
        int best = maximising ? Integer.MIN_VALUE : Integer.MAX_VALUE;
        for (Move m : g.legalMoves()) {
            g.play(m);
            int score = search(g, depth - 1, alpha, beta, me);
            g.undo();
            if (maximising) { best = Math.max(best, score); alpha = Math.max(alpha, best); }
            else            { best = Math.min(best, score); beta  = Math.min(beta, best); }
            if (beta <= alpha) break;                                     // this branch cannot change the answer
        }
        return best;
    }
}

// ---- ext: algebraic notation -- "accept Nf3 and O-O". The legal-move set is the disambiguation oracle.
/**
 * Standard algebraic notation, both directions. The trick is that neither direction needs new rules code:
 * to print a move you only have to know which OTHER legal moves would look the same, and to read one you print
 * every legal move and compare. A notation bug can therefore never become a rules bug.
 *
 * Both entry points work on a PRIVATE COPY of the game, because deciding whether a move gives check means
 * playing it -- and playing it on the live game would tell every spectator about a move nobody made.
 */
final class Notation {
    /** The move in standard notation, disambiguated against the other legal moves, with + or # if it gives one. */
    static String san(Game game, Move move) { return sanOn(Game.fromFen("san", game.fen()), move); }

    /** Read "Nf3", "exd5", "O-O", "e8=Q#": print every legal move and take the one that matches. */
    static Move parse(Game game, String text) {
        String wanted = text.replaceAll("[+#!?]", "").trim();
        Game probe = Game.fromFen("san", game.fen());                     // one copy, reused for every candidate
        for (Move m : probe.legalMoves()) if (sanOn(probe, m).replaceAll("[+#]", "").equals(wanted)) return m;
        throw new IllegalMoveException("no legal move reads as " + text);
    }

    /** The same, on a game the caller already knows is a throwaway copy. */
    static String sanOn(Game game, Move move) {
        if (move.kind() == MoveKind.CASTLE_KING) return "O-O" + suffix(game, move);
        if (move.kind() == MoveKind.CASTLE_QUEEN) return "O-O-O" + suffix(game, move);
        StringBuilder sb = new StringBuilder();
        if (move.moved().isPawn()) {
            if (move.isCapture()) sb.append((char) ('a' + move.from().col())).append('x');
        } else {
            sb.append(Character.toUpperCase(move.moved().symbol())).append(disambiguate(game, move));
            if (move.isCapture()) sb.append('x');
        }
        sb.append(move.to());
        if (move.promoteTo() != null) sb.append('=').append(Character.toUpperCase(move.promoteTo().symbol()));
        return sb.append(suffix(game, move)).toString();
    }

    /** The file, the rank, or both -- whichever is the least that tells this move apart from its twins. */
    private static String disambiguate(Game game, Move move) {
        List<Move> twins = game.legalMoves().stream()
            .filter(m -> m.moved() == move.moved() && m.to().equals(move.to()) && !m.from().equals(move.from())).toList();
        if (twins.isEmpty()) return "";
        boolean fileIsEnough = twins.stream().noneMatch(m -> m.from().col() == move.from().col());
        if (fileIsEnough) return String.valueOf((char) ('a' + move.from().col()));
        boolean rankIsEnough = twins.stream().noneMatch(m -> m.from().row() == move.from().row());
        if (rankIsEnough) return String.valueOf((char) ('1' + move.from().row()));
        return move.from().toString();
    }

    /** Play it, look, take it back: the only way to know whether a move gives check is to make it. */
    private static String suffix(Game game, Move move) {
        GameStatus after = game.play(move);
        game.undo();
        return after == GameStatus.CHECKMATE ? "#" : after == GameStatus.CHECK ? "+" : "";
    }
    private Notation() {}
}

// ---- ext: PGN -- an observer that keeps the move list, and renders it on demand by replaying it
/**
 * A spectator that writes the game down. It stores MOVES, not text, and renders the notation by replaying them
 * on a private copy -- because notation needs the position BEFORE each move, which an observer, called after
 * the move, no longer has. Storing the move list rather than the text is also what makes takeback and resume work.
 */
class PgnRecorder implements GameObserver {
    private final String startFen;
    private final List<Move> moves = new ArrayList<>();
    PgnRecorder(String startFen) { this.startFen = startFen; }
    public void onMove(Game game, Move move, GameStatus after) { moves.add(move); }

    /** "1. e4 e5 2. Nf3 Nc6 ... 1-0". Built by replaying the move list from the starting position. */
    String pgn() {
        Game replay = Game.fromFen("pgn", startFen);
        StringBuilder sb = new StringBuilder();
        int number = 1;
        for (int i = 0; i < moves.size(); i++) {
            if (replay.toMove() == Color.WHITE) sb.append(number++).append(". ");
            sb.append(Notation.sanOn(replay, moves.get(i))).append(' ');  // `replay` is already a private copy
            replay.play(moves.get(i));
        }
        return sb.append(result(replay)).toString();
    }
    private static String result(Game g) {
        if (g.status() == GameStatus.CHECKMATE) return g.winner() == Color.WHITE ? "1-0" : "0-1";
        if (g.status().over()) return "1/2-1/2";
        return "*";
    }
    List<Move> moves() { return List.copyOf(moves); }
}

// ---- ext: the chess clock -- a time control is an observer built on the injected Clock, not a rule of chess
/**
 * The clock debits whoever just moved and adds the increment. It is an observer because the rules engine has no
 * business knowing about time: a flag-fall is a result the SERVICE records, not a status the rules produce.
 * Because the time comes from an injected Clock, a test moves an hour in one line instead of waiting an hour.
 */
class ChessClock implements GameObserver {
    private final Clock clock;
    private final long incrementMs;
    private final long[] remaining = new long[2];
    private long lastMs;
    ChessClock(Clock clock, long perSideMs, long incrementMs) {
        this.clock = clock; this.incrementMs = incrementMs;
        remaining[0] = remaining[1] = perSideMs;
        lastMs = clock.nowMs();
    }
    public void onMove(Game game, Move move, GameStatus after) {
        Color mover = game.toMove().opponent();                          // the turn has already flipped
        long now = clock.nowMs();
        remaining[mover.ordinal()] -= (now - lastMs);
        if (remaining[mover.ordinal()] > 0) remaining[mover.ordinal()] += incrementMs;
        lastMs = now;
    }
    long remainingMs(Color c) { return remaining[c.ordinal()]; }
    /** Has this side already run out? */
    boolean flagged(Color c) { return remaining[c.ordinal()] <= 0; }
    /**
     * Would this side be out of time if its move arrived now? This is the question the SERVICE asks before it
     * accepts a move, because a player who has gone to lunch never sends the move that would stop their clock.
     */
    boolean wouldFlag(Color c) { return remaining[c.ordinal()] - (clock.nowMs() - lastMs) <= 0; }
}

// ---- ext: insufficient material -- one more draw rule, and therefore one more wrapper, not an edit
/**
 * King against king, and king and a single minor piece against king, cannot be mated by anyone, so the game is
 * drawn the moment the last relevant piece leaves the board. It wraps any rule set, and it can be stacked with
 * DrawRules: each wrapper adds one rule and none of them knows the others exist.
 */
class InsufficientMaterial implements RuleSet {
    private final RuleSet base;
    InsufficientMaterial(RuleSet base) { this.base = base; }
    public GameStatus adjudicate(Game game, boolean inCheck, boolean anyLegalMove) {
        GameStatus decided = base.adjudicate(game, inCheck, anyLegalMove);
        if (decided.over()) return decided;
        return dead(game.board()) ? GameStatus.DRAW : decided;
    }
    /** True when neither side has enough on the board to force mate. */
    private static boolean dead(Board board) {
        int minors = 0;
        for (int r = 0; r < 8; r++)
            for (int c = 0; c < 8; c++) {
                Piece p = board.at(r, c);
                if (p == null || p.isKing()) continue;
                char kind = Character.toUpperCase(p.symbol());
                if (kind == 'N' || kind == 'B') { minors++; if (minors > 1) return false; }
                else return false;                                        // a pawn, rook, queen: mate is possible
            }
        return true;
    }
}

// ---- ext: perft -- the standard proof that a chess move generator is correct, and the speed number
/**
 * Count the leaves of the legal-move tree. The published numbers for these positions are known to the last
 * unit, so a generator that reproduces them has castling, en passant, promotion, pins and check evasion right.
 * It is also the honest speed benchmark: everything it does is generate, apply and take back.
 */
final class Perft {
    static long count(Game game, int depth) {
        if (depth == 0) return 1;
        long leaves = 0;
        for (Move m : game.legalMoves()) { game.play(m); leaves += count(game, depth - 1); game.undo(); }
        return leaves;
    }
    /** Same count, split by first move: what you print when a number is wrong and you need to find out where. */
    static Map<String, Long> divide(Game game, int depth) {
        Map<String, Long> out = new LinkedHashMap<>();
        for (Move m : game.legalMoves()) { game.play(m); out.put(m.toString(), count(game, depth - 1)); game.undo(); }
        return out;
    }
    private Perft() {}
}

// ---- ext: persistence and resume -- the move list IS the save format; FEN is the snapshot
/** What is stored for one game: where it started, and every move since. Both are needed; neither is enough. */
record SavedGame(String startFen, List<String> moves) {}

/** Somewhere to keep games. A table, a file, a key-value store: the game does not care, which is the point. */
interface GameRepository {
    void save(String gameId, SavedGame saved);
    Optional<SavedGame> load(String gameId);
}

/** The in-memory one, so the tests and the demo have something to talk to. */
class InMemoryGameRepository implements GameRepository {
    private final Map<String, SavedGame> rows = new HashMap<>();
    public void save(String gameId, SavedGame saved) { rows.put(gameId, saved); }
    public Optional<SavedGame> load(String gameId) { return Optional.ofNullable(rows.get(gameId)); }
}

/**
 * Save after every move, and rebuild a game from what was saved. Rebuilding replays the moves through the same
 * play() every live game uses, so a resumed game cannot be in a state a played game could not reach -- and the
 * repetition counts and the fifty-move clock come back right, which a FEN snapshot alone would lose.
 */
class Persistence implements GameObserver {
    private final GameRepository repository;
    private final String gameId, startFen;
    private final List<String> moves = new ArrayList<>();
    Persistence(GameRepository repository, Game game) {
        this.repository = repository; this.gameId = game.id(); this.startFen = game.fen();
        repository.save(gameId, new SavedGame(startFen, List.of()));
    }
    public void onMove(Game game, Move move, GameStatus after) {
        moves.add(move.from().toString() + move.to()
            + (move.promoteTo() == null ? "" : String.valueOf(Character.toUpperCase(move.promoteTo().symbol()))));
        repository.save(gameId, new SavedGame(startFen, List.copyOf(moves)));
    }
    /** Rebuild a game from storage: the starting position, then every move replayed through the rules. */
    static Game resume(GameRepository repository, String gameId) {
        SavedGame saved = repository.load(gameId).orElseThrow(() -> new NoSuchElementException("no such game: " + gameId));
        Game game = Game.fromFen(gameId, saved.startFen());
        for (String coords : saved.moves()) {
            Position from = Position.of(coords.substring(0, 2)), to = Position.of(coords.substring(2, 4));
            char promote = coords.length() > 4 ? coords.charAt(4) : 0;
            game.play(game.legalMoves().stream()
                .filter(m -> m.from().equals(from) && m.to().equals(to))
                .filter(m -> promote == 0 ? m.promoteTo() == null : m.promoteTo() == Pieces.of(m.moved().color, promote))
                .findFirst().orElseThrow(() -> new IllegalMoveException("the saved move " + coords + " is not legal")));
        }
        return game;
    }
}

// ---- ext: online play -- two servers, a reconnecting client, and the compare-and-set that makes it safe
/**
 * The service in front of many live games. Its only addition to the in-process version is the ply the client
 * says it saw: a phone that went through a tunnel and came back sends a move computed on a stale board, and
 * play(expectedPly, move) refuses it instead of applying it. Reconnecting is then just "here is the move list
 * from ply n", which is why the move list is the thing that is stored.
 */
class MatchService {
    private final Map<String, Game> live = new HashMap<>();
    private final GameRepository repository;
    MatchService(GameRepository repository) { this.repository = repository; }

    /** Start a game, wire up persistence, and keep it in memory. */
    Game start(String gameId) {
        Game game = Game.newGame(gameId);
        game.addObserver(new Persistence(repository, game));
        live.put(gameId, game);
        return game;
    }
    /** A move from a client that tells us which position it was looking at. */
    GameStatus play(String gameId, int clientSawPly, Move move) { return game(gameId).play(clientSawPly, move); }
    /** What a reconnecting client needs: everything that happened while it was away. */
    List<Move> since(String gameId, int clientSawPly) {
        List<Move> all = game(gameId).history();
        return all.subList(Math.min(clientSawPly, all.size()), all.size());
    }
    /** A server that was restarted rebuilds the game from storage before serving it. */
    Game game(String gameId) {
        return live.computeIfAbsent(gameId, id -> Persistence.resume(repository, id));
    }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) {
        // a fairy piece: one register() call, and the whole engine accepts it
        Pieces.register('C', Chancellor::new);
        Game fairy = Game.fromFen("fairy", "7k/8/8/8/8/8/8/C3K3 w - - 0 1");
        System.out.println("chancellor on a1 has " + fairy.legalMoves().stream().filter(m -> m.from().equals(Position.of("a1"))).count()
            + " moves (rook rays + knight hops)");
        Game fairyCheck = Game.fromFen("fairycheck", "4k3/8/3C4/8/8/8/8/4K3 w - - 0 1");
        System.out.println("check detection needed no edit: a chancellor on d6 attacks the king on e8 -> "
            + fairyCheck.board().isAttacked(Position.of("e8"), Color.WHITE));

        // an AI opponent: alpha-beta over the same legalMoves() a user interface uses
        Game engineGame = Game.fromFen("ai", "rnbqkbnr/ppp2ppp/8/3pp3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 0 3");
        Player engine = new MinimaxPlayer(new MaterialEvaluator(), 3);
        long t0 = System.nanoTime();
        Move chosen = engine.choose(engineGame);
        System.out.println("depth-3 search picked " + chosen + " in " + (System.nanoTime() - t0) / 1_000_000 + " ms");

        // notation, both directions
        Game note = Game.newGame("note");
        for (String san : new String[] { "e4", "e5", "Nf3", "Nc6", "Bb5", "a6" }) note.play(Notation.parse(note, san));
        System.out.println("read six moves of the Ruy Lopez from text; the position is " + note.fen());
        Game twins = Game.fromFen("twins", "8/8/8/3N1N2/8/4k3/8/4K3 w - - 0 1");
        System.out.println("two knights can reach e7, so the notation disambiguates: "
            + twins.legalMoves().stream().filter(m -> m.to().equals(Position.of("e7"))).map(m -> Notation.san(twins, m)).toList());

        // PGN, written by a spectator, rendered by replaying the move list -- including the result
        Game recorded = Game.newGame("pgn");
        PgnRecorder recorder = new PgnRecorder(recorded.fen());
        recorded.addObserver(recorder);
        for (String san : new String[] { "f3", "e5", "g4", "Qh4" }) recorded.play(Notation.parse(recorded, san));
        System.out.println("pgn: " + recorder.pgn());
        Game random = Game.newGame("random");
        PgnRecorder log = new PgnRecorder(random.fen());
        random.addObserver(log);
        Player white = new RandomPlayer(4), black = new RandomPlayer(9);
        while (!random.status().over() && random.ply() < 10)
            random.play((random.toMove() == Color.WHITE ? white : black).choose(random));
        System.out.println("two random players: " + log.pgn());

        // the chess clock, on a clock the test controls
        long[] now = { 1_700_000_000_000L };
        Game timed = Game.newGame("timed");
        timed.setClock(() -> now[0]);
        ChessClock clock = new ChessClock(() -> now[0], 180_000, 2_000);   // 3 minutes each, 2 second increment
        timed.addObserver(clock);
        now[0] += 10_000; timed.play(Notation.parse(timed, "e4"));
        now[0] += 30_000; timed.play(Notation.parse(timed, "e5"));
        System.out.println("after 10s and 30s: white has " + clock.remainingMs(Color.WHITE) / 1000
            + "s, black has " + clock.remainingMs(Color.BLACK) / 1000 + "s (both got the 2s increment)");
        now[0] += 200_000;                                                 // White goes to lunch
        System.out.println("white sat for 200 more seconds -> the service asks before accepting: wouldFlag(WHITE)="
            + clock.wouldFlag(Color.WHITE) + ", so the SERVICE records a loss on time. The rules engine never knew"
            + " there was a clock, which is why a correspondence game and a bullet game share it.");

        // draw rules, stacked: repetition, fifty moves and now insufficient material
        Game bare = Game.fromFen("bare", "4k3/8/8/8/8/8/8/4K1N1 w - - 0 1");
        bare.configure(new InsufficientMaterial(new DrawRules(new StandardRules())));
        System.out.println("king and a knight against a bare king -> " + bare.status());

        // perft: the numbers are published to the last unit, so this is a proof, not a smoke test
        long t1 = System.nanoTime();
        long leaves = Perft.count(Game.newGame("perft"), 4);
        System.out.println("perft(4) from the start = " + leaves + " (must be 197281) in "
            + (System.nanoTime() - t1) / 1_000_000 + " ms");
        System.out.println("perft divide(2): " + Perft.divide(Game.newGame("perft"), 2).entrySet().stream().limit(4).toList() + " ...");

        // persistence, a restarted server, and a reconnecting client
        GameRepository repository = new InMemoryGameRepository();
        MatchService matches = new MatchService(repository);
        Game online = matches.start("m1");
        matches.play("m1", 0, Notation.parse(online, "e4"));
        matches.play("m1", 1, Notation.parse(online, "e5"));
        try {
            matches.play("m1", 1, Notation.parse(online, "Nf3"));           // a client that missed a move
            System.out.println("a stale client was accepted -- this should not print");
        } catch (IllegalMoveException e) { System.out.println("stale client refused: " + e.getMessage()); }
        System.out.println("what a reconnecting client missed since ply 0: " + matches.since("m1", 0));
        Game rebuilt = Persistence.resume(repository, "m1");
        System.out.println("rebuilt from storage on a fresh server: " + rebuilt.fen() + "  same=" + rebuilt.fen().equals(online.fen()));
    }
}
