import java.util.*;
import java.util.concurrent.*;

// Targeted failure tests: each block proves one claim the design makes on page 02, move 9.
// javac Main.java Extensions.java FailureTests.java && java FailureTests   ->   ALL PASS
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /** Count the leaves of the legal-move tree to `depth`. The standard chess correctness benchmark. */
    static long perft(Game g, int depth) {
        if (depth == 0) return 1;
        long n = 0;
        for (Move m : g.legalMoves()) { g.play(m); n += perft(g, depth - 1); g.undo(); }
        return n;
    }
    /** Every legal move from this square. */
    static List<Move> from(Game g, String square) {
        Position p = Position.of(square);
        return g.legalMoves().stream().filter(m -> m.from().equals(p)).toList();
    }
    /** The legal move from one square to another, or null. */
    static Move move(Game g, String coords) {
        Position f = Position.of(coords.substring(0, 2)), t = Position.of(coords.substring(2, 4));
        return g.legalMoves().stream().filter(m -> m.from().equals(f) && m.to().equals(t)).findFirst().orElse(null);
    }
    static void line(Game g, String... coords) { for (String c : coords) g.play(move(g, c)); }

    public static void main(String[] args) throws Exception {

        // 1. the geometry a junior gets wrong: a knight in the corner, the pawn's double step, Black's direction
        Game corner = Game.fromFen("corner", "N6k/8/8/8/8/8/8/K7 w - - 0 1");
        check(from(corner, "a8").size() == 2, "a knight in the corner has exactly 2 moves, not 8");
        Game open = Game.newGame("open");
        check(open.legalMoves().size() == 20, "the opening position has exactly 20 legal moves");
        check(move(open, "e2e4") != null && move(open, "e2e3") != null, "a pawn on its own rank may step one or two");
        line(open, "e2e3", "e7e6");
        check(move(open, "e3e5") == null && move(open, "e3e4") != null,
              "a pawn that has already moved may not take two steps");
        check(open.legalMoves().size() == 30, "White has 30 legal moves after 1.e3 e6");
        Game black = Game.newGame("black");
        line(black, "e2e4");
        check(move(black, "e7e5") != null && move(black, "e7e8") == null,
              "Black's pawns march DOWN the board, not up (nobody hardcoded +1)");

        // 2. the move generator is provably correct: perft, the standard chess benchmark, on four hard positions
        check(perft(Game.newGame("p"), 1) == 20 && perft(Game.newGame("p"), 2) == 400,
              "perft from the start: 20 moves, 400 replies");
        check(perft(Game.newGame("p"), 3) == 8902, "perft depth 3 from the start is exactly 8902");
        Game kiwi = Game.fromFen("kiwi", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1");
        check(perft(kiwi, 1) == 48 && perft(kiwi, 2) == 2039,
              "perft on the standard castling/pin position: 48 and 2039");
        Game ep3 = Game.fromFen("ep3", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1");
        check(perft(ep3, 1) == 14 && perft(ep3, 2) == 191 && perft(ep3, 3) == 2812,
              "perft on the standard en-passant/discovered-check position: 14, 191, 2812");
        Game pr4 = Game.fromFen("pr4", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1");
        check(perft(pr4, 1) == 6 && perft(pr4, 2) == 264, "perft on the standard promotion position: 6 and 264");

        // 3. you may not leave your own king in check: a pinned piece is frozen, and a king cannot walk into fire
        Game pin = Game.fromFen("pin", "4r2k/8/8/8/8/8/4B3/4K3 w - - 0 1");
        check(pin.status() == GameStatus.ACTIVE, "the bishop blocks the rook, so White is not in check");
        check(from(pin, "e2").isEmpty(), "a pinned bishop has ZERO legal moves, however good they look");
        Game walk = Game.fromFen("walk", "7k/8/8/8/8/8/r7/4K3 w - - 0 1");
        check(walk.legalMoves().size() == 2, "the king has only the 2 squares off the attacked rank (Kd1, Kf1)");
        check(walk.legalMoves().stream().noneMatch(m -> m.to().equals(Position.of("e2"))),
              "the king may not step onto an attacked square");

        // 4. simulate on the REAL board and put it back exactly: the position must be byte-identical afterwards
        String[] positions = {
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            "rnbqkbnr/p1pppppp/8/1pP5/8/8/PP1PPPPP/RNBQKBNR w KQkq b6 0 3",
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
            "4r2k/8/8/8/8/8/4B3/4K3 w - - 0 1" };
        boolean intact = true;
        for (String fen : positions) {
            Game g = Game.fromFen("sim", fen);
            String before = g.fen();
            List<Move> legal = g.legalMoves();                            // generation makes and unmakes every move
            if (!before.equals(g.fen())) intact = false;
            for (Move m : legal) { g.play(m); g.undo(); if (!before.equals(g.fen())) intact = false; }
        }
        check(intact, "generating and taking back every legal move in 6 positions left every FEN identical");
        Game take = Game.fromFen("take", "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2");
        String beforeCapture = take.fen();
        take.play(move(take, "e4d5"));
        check(take.board().at(Position.of("d5")).color == Color.WHITE, "exd5 took the black pawn");
        take.undo();
        check(take.fen().equals(beforeCapture), "the takeback put the captured pawn back and restored the en passant square");

        // 5. castling: the five conditions, and what actually moves
        Game cast = Game.fromFen("cast", "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
        check(move(cast, "e1g1") != null && move(cast, "e1c1") != null, "both castles are offered when nothing is in the way");
        cast.play(move(cast, "e1g1"));
        check(cast.board().at(Position.of("g1")).isKing() && cast.board().at(Position.of("f1")) != null
              && cast.board().at(Position.of("h1")) == null, "O-O moved the ROOK too: h1 is empty, f1 holds it");
        Game through = Game.fromFen("through", "r4rk1/8/8/8/8/8/8/R3K2R w KQ - 0 1");
        check(move(through, "e1g1") == null, "castling is refused THROUGH an attacked square (f1)");
        check(move(through, "e1c1") != null, "but the other side, which is not attacked, is still offered");
        Game out = Game.fromFen("out", "4r2k/8/8/8/8/8/8/R3K2R w KQ - 0 1");
        check(move(out, "e1g1") == null && move(out, "e1c1") == null, "castling is refused OUT of check");
        Game moved = Game.fromFen("moved", "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
        line(moved, "h1g1", "a8b8", "g1h1", "b8a8");
        check(move(moved, "e1g1") == null, "the right is gone once the rook has moved, even though it came back");
        Game grab = Game.fromFen("grab", "r3k2r/8/8/8/8/8/6B1/R3K2R w KQkq - 0 1");
        grab.play(move(grab, "g2a8"));
        check(grab.fen().contains(" KQk "), "capturing a rook ON ITS CORNER kills that side's right (q is gone)");

        // 6. en passant: the window is exactly one ply, and the victim is not on the destination square
        Game ep = Game.fromFen("ep", "rnbqkbnr/p1pppppp/8/1pP5/8/8/PP1PPPPP/RNBQKBNR w KQkq b6 0 3");
        Move grabPassing = move(ep, "c5b6");
        check(grabPassing != null && grabPassing.kind() == MoveKind.EN_PASSANT, "the en passant capture is generated");
        check(grabPassing.capturedAt().equals(Position.of("b5")) && !grabPassing.capturedAt().equals(grabPassing.to()),
              "the victim stands on b5, which is NOT the square the pawn lands on");
        ep.play(grabPassing);
        check(ep.board().at(Position.of("b5")) == null && ep.board().at(Position.of("b6")) != null,
              "after it, b5 is empty and b6 holds the white pawn");
        Game late = Game.fromFen("late", "rnbqkbnr/p1pppppp/8/1pP5/8/8/PP1PPPPP/RNBQKBNR w KQkq b6 0 3");
        line(late, "a2a3", "a7a6");
        check(move(late, "c5b6") == null, "one ply later the chance is gone: the en passant square lives exactly one ply");

        // 7. promotion: four choices, a king is not one of them, and a takeback turns the queen back into a pawn
        Game promo = Game.fromFen("promo", "8/P6k/8/8/8/8/7K/8 w - - 0 1");
        List<Move> choices = from(promo, "a7");
        check(choices.size() == 4, "a promotion fans out into exactly 4 moves, one per piece");
        check(choices.stream().anyMatch(m -> m.promoteTo() == Pieces.knight(Color.WHITE)),
              "under-promotion to a knight is among them: it is legal and occasionally winning");
        check(choices.stream().noneMatch(m -> m.promoteTo().isKing()), "promoting to a king is not on the list");
        try {
            promo.play(Move.promotion(Position.of("a7"), Position.of("a8"), Pieces.pawn(Color.WHITE), null, Pieces.king(Color.WHITE)));
            check(false, "a hand-made promotion to a king must be refused");
        } catch (IllegalMoveException e) { check(true, "a hand-made promotion to a king is refused: " + e.getMessage()); }
        String beforePromo = promo.fen();
        promo.play(choices.stream().filter(m -> m.promoteTo() == Pieces.knight(Color.WHITE)).findFirst().orElseThrow());
        check(promo.board().at(Position.of("a8")).hopsKnight(), "the pawn really became a knight");
        promo.undo();
        check(promo.fen().equals(beforePromo) && promo.board().at(Position.of("a7")).isPawn(),
              "the takeback turned the knight back into a pawn on a7");

        // 8. one primitive, three endings -- and the pawn attack/move split that check detection depends on
        Game mate = Game.newGame("mate");
        line(mate, "f2f3", "e7e5", "g2g4", "d8h4");
        check(mate.status() == GameStatus.CHECKMATE && mate.winner() == Color.BLACK, "fool's mate is detected as CHECKMATE");
        check(mate.legalMoves().isEmpty(), "and it is detected because the side to move has no legal move at all");
        try { mate.play(Move.quiet(Position.of("h2"), Position.of("h3"), Pieces.pawn(Color.WHITE))); check(false, "a finished game must refuse moves"); }
        catch (IllegalMoveException e) { check(true, "a finished game refuses every further move: " + e.getMessage()); }
        Game stale = Game.fromFen("stale", "7k/8/6Q1/8/8/8/8/K7 b - - 0 1");
        check(stale.status() == GameStatus.STALEMATE, "the same 'no legal move' with no check is STALEMATE, not a win");
        check(stale.winner() == null, "and a stalemate has no winner");
        check(!Board.fromFen("8/8/8/8/4k3/4P3/8/4K3 b - - 0 1").inCheck(Color.BLACK),
              "a pawn directly in FRONT of the king does not give check: a pawn's move is not its attack");
        check(Board.fromFen("8/8/8/8/4k3/3P4/8/4K3 b - - 0 1").inCheck(Color.BLACK),
              "the same pawn one file over DOES give check, because it attacks diagonally");
        check(Board.fromFen("8/8/8/4p3/3K4/8/8/4k3 w - - 0 1").inCheck(Color.WHITE),
              "and a BLACK pawn checks downward, because the direction comes from the colour");

        // 9. two requests for one game at the same instant: exactly one may land; a broken spectator changes nothing
        Game contested = Game.newGame("race");
        List<Move> opening = contested.legalMoves();
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Boolean>> sent = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final Move mine = opening.get(i % opening.size());
            sent.add(pool.submit(() -> { go.await(); try { contested.play(mine); return true; } catch (IllegalMoveException e) { return false; } }));
        }
        go.countDown();
        int accepted = 0;
        for (Future<Boolean> f : sent) if (f.get()) accepted++;
        check(accepted == 1, "50 clients fired at one game: exactly 1 move was accepted");
        check(contested.ply() == 1, "the history has exactly one ply, not two");
        check(contested.toMove() == Color.BLACK, "and the turn flipped exactly once");
        // eight whole games at once: per-game locks mean they never touch each other
        List<Future<Integer>> games = new ArrayList<>();
        for (int i = 0; i < 8; i++) {
            final int seed = i;
            games.add(pool.submit(() -> {
                Game g = Game.newGame("par" + seed);
                Random r = new Random(seed);
                int plies = 0;
                while (!g.status().over() && plies < 60) { List<Move> l = g.legalMoves(); g.play(l.get(r.nextInt(l.size()))); plies++; }
                return g.ply();
            }));
        }
        boolean allFine = true;
        for (Future<Integer> f : games) if (f.get() < 1) allFine = false;
        pool.shutdown();
        check(allFine, "eight whole games played in parallel: the lock is per game, so they never wait for each other");
        Game noisy = Game.newGame("noisy");
        noisy.addObserver((g, m, after) -> { throw new RuntimeException("the spectator's websocket died"); });
        noisy.play(move(noisy, "e2e4"));
        check(noisy.ply() == 1 && noisy.board().at(Position.of("e4")) != null,
              "a spectator that throws does not break the move: it is called after the lock, in a try/catch");

        // 10. the draw rules are a wrapper: the same game is a draw with them and ongoing without them
        Game rep = Game.newGame("rep");
        rep.configure(new DrawRules(new StandardRules()));
        line(rep, "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8");
        check(rep.status() == GameStatus.DRAW, "the third time the same position appears is a DRAW");
        Game noRep = Game.newGame("norep");
        line(noRep, "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8");
        check(noRep.status() == GameStatus.ACTIVE,
              "the identical game WITHOUT the wrapper is still ACTIVE: the rule is in the decorator, not the engine");
        Game fifty = Game.newGame("fifty");
        fifty.configure(new DrawRules(new StandardRules(), 6, 99));        // a 6-ply limit, so the test is not 100 moves long
        line(fifty, "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6");
        check(fifty.status() == GameStatus.DRAW, "six plies with no pawn move and no capture hit the (shortened) fifty-move rule");
        check(fifty.halfmoveClock() == 6, "and the clock that measures it counted exactly six");
        Game reset = Game.newGame("reset");
        line(reset, "e2e4");
        check(reset.halfmoveClock() == 0, "a pawn move resets that clock to zero");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
