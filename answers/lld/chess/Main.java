import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.function.Function;

/** Which side is moving. The three facts everyone asks a colour for live here, so nobody hardcodes White's direction. */
enum Color {
    WHITE, BLACK;
    /** The other side. Written once, because "the opponent" appears in every check test in the file. */
    Color opponent() { return this == WHITE ? BLACK : WHITE; }
    /** +1 for White, -1 for Black: the direction this side's pawns march in. The junior bug is hardcoding +1. */
    int forward() { return this == WHITE ? 1 : -1; }
    /** The row this side's pawns start on, which is the only row a double step is allowed from. */
    int pawnRow() { return this == WHITE ? 1 : 6; }
    /** The row this side's pawns promote on. */
    int lastRow() { return this == WHITE ? 7 : 0; }
}

/** What kind of move this is. The three special moves each need an extra edit when applied, and this flag drives them. */
enum MoveKind { NORMAL, DOUBLE_PAWN, EN_PASSANT, CASTLE_KING, CASTLE_QUEEN, PROMOTION }

/**
 * A game's life. ACTIVE and CHECK still accept moves; CHECKMATE, STALEMATE and DRAW are terminal and every
 * further move is refused. Checkmate and stalemate are the SAME condition -- no legal move -- split by check.
 */
enum GameStatus {
    ACTIVE, CHECK, CHECKMATE, STALEMATE, DRAW;
    /** True once the game has ended: the three terminal states refuse every further move. */
    boolean over() { return this == CHECKMATE || this == STALEMATE || this == DRAW; }
}

/** Thrown when a caller offers a move that is not in the legal set. The board is untouched when this is thrown. */
class IllegalMoveException extends RuntimeException {
    IllegalMoveException(String why) { super(why); }
}

/**
 * A square, as a value. row 0 is rank 1 (White's back rank) and col 0 is file a, so "e4" is row 3, col 4.
 * Immutable and pre-built: the 64 squares are shared, so equals and hashCode are free and sets of squares are cheap.
 */
record Position(int row, int col) {
    private static final Position[] ALL = new Position[64];
    static { for (int r = 0; r < 8; r++) for (int c = 0; c < 8; c++) ALL[r * 8 + c] = new Position(r, c); }

    /** The shared square object for these coordinates. Callers must have checked onBoard first. */
    static Position at(int row, int col) { return ALL[row * 8 + col]; }
    /** Is this pair of coordinates on the board at all? Every generator's first question. */
    static boolean onBoard(int row, int col) { return row >= 0 && row < 8 && col >= 0 && col < 8; }
    /** Parse "e4". Used by tests, by FEN and by a user interface; never inside the rules. */
    static Position of(String square) { return at(square.charAt(1) - '1', square.charAt(0) - 'a'); }
    /** Index into the board's flat 64-slot array. */
    int index() { return row * 8 + col; }
    @Override public String toString() { return "" + (char) ('a' + col) + (char) ('1' + row); }
}

/**
 * A piece: geometry and nothing else. A piece holds NO mutable state -- no "has moved" flag, no square -- so
 * twelve objects serve every game on the server, and undoing a move can never leave a piece half-restored.
 * Every other class talks to this abstraction and never to Rook or Pawn, which is why a new piece is a new file.
 */
abstract class Piece {
    final Color color;
    private final char letter;                       // uppercase; the colour decides the case in symbol()

    Piece(Color color, char letter) { this.color = color; this.letter = letter; }

    /**
     * Every square this piece attacks from `from`, including squares holding a friend (that friend is defended,
     * which matters for the enemy king). For every piece except the pawn this is also where it may move.
     */
    abstract void attacks(Board board, Position from, List<Position> out);

    /**
     * Pseudo-legal moves: attacked squares that do not hold a friend. "Pseudo-legal" means the geometry is right
     * but nobody has asked whether it leaves this side's own king in check -- that is the rules layer's job.
     * Only the Pawn overrides this, because the pawn is the one piece whose moves are not its attacks.
     */
    void pseudoMoves(Board board, Position from, List<Move> out) {
        List<Position> targets = new ArrayList<>(28);
        attacks(board, from, targets);
        for (Position to : targets) {
            Piece there = board.at(to);
            if (there != null && there.color == color) continue;          // cannot capture your own
            out.add(there == null ? Move.quiet(from, to, this) : Move.capture(from, to, this, there));
        }
    }

    // ---- capability flags: what this piece CAN DO, asked by Board.isAttacked. A new piece answers these and
    // ---- check detection keeps working without a single edit to Board or Game.
    /** Does it slide along ranks and files (rook, queen)? */
    boolean ridesStraight() { return false; }
    /** Does it slide along diagonals (bishop, queen)? */
    boolean ridesDiagonal() { return false; }
    /** Does it jump the knight's L (knight)? */
    boolean hopsKnight() { return false; }
    /** Does it attack the eight squares around it (king)? */
    boolean stepsOne() { return false; }
    /** Does it attack the two squares diagonally FORWARD only (pawn)? */
    boolean attacksPawnwise() { return false; }
    /** A pawn is the only piece that resets the fifty-move clock by moving and that can promote. */
    boolean isPawn() { return false; }
    /** The king is the piece whose square the board caches and whose safety is the whole invariant. */
    boolean isKing() { return false; }

    /** FEN letter: uppercase for White, lowercase for Black. Used for printing, FEN and the piece registry. */
    char symbol() { return color == Color.WHITE ? letter : Character.toLowerCase(letter); }
    @Override public String toString() { return String.valueOf(symbol()); }
}

/**
 * The template method for the three pieces that ride: they differ only in their direction vectors, so the
 * ray walk -- go until the edge or the first piece, and include that piece's square -- is written exactly once.
 */
abstract class SlidingPiece extends Piece {
    static final int[][] STRAIGHT = { {1, 0}, {-1, 0}, {0, 1}, {0, -1} };
    static final int[][] DIAGONAL = { {1, 1}, {1, -1}, {-1, 1}, {-1, -1} };
    private final int[][] dirs;

    SlidingPiece(Color color, char letter, int[][] dirs) { super(color, letter); this.dirs = dirs; }

    /** Walk every direction until the board edge or the first occupied square, which is included. */
    @Override void attacks(Board board, Position from, List<Position> out) {
        for (int[] d : dirs) {
            for (int step = 1; ; step++) {
                int r = from.row() + d[0] * step, c = from.col() + d[1] * step;
                if (!Position.onBoard(r, c)) break;
                out.add(Position.at(r, c));
                if (board.at(r, c) != null) break;                        // blocked: this square, and no further
            }
        }
    }
}

/** Rook: the four straight rays, and the piece whose corner square carries a castling right. */
class Rook extends SlidingPiece {
    Rook(Color color) { super(color, 'R', STRAIGHT); }
    @Override boolean ridesStraight() { return true; }
}

/** Bishop: the four diagonal rays. */
class Bishop extends SlidingPiece {
    Bishop(Color color) { super(color, 'B', DIAGONAL); }
    @Override boolean ridesDiagonal() { return true; }
}

/** Queen: both sets of rays, and nothing else new -- which is the point of the template method. */
class Queen extends SlidingPiece {
    private static final int[][] ALL8 = { {1, 0}, {-1, 0}, {0, 1}, {0, -1}, {1, 1}, {1, -1}, {-1, 1}, {-1, -1} };
    Queen(Color color) { super(color, 'Q', ALL8); }
    @Override boolean ridesStraight() { return true; }
    @Override boolean ridesDiagonal() { return true; }
}

/** Knight: eight fixed offsets, and the only piece that ignores what is in the way. */
class Knight extends Piece {
    private static final int[][] JUMPS = { {2, 1}, {2, -1}, {-2, 1}, {-2, -1}, {1, 2}, {1, -2}, {-1, 2}, {-1, -2} };
    Knight(Color color) { super(color, 'N'); }
    @Override void attacks(Board board, Position from, List<Position> out) {
        for (int[] j : JUMPS) {
            int r = from.row() + j[0], c = from.col() + j[1];
            if (Position.onBoard(r, c)) out.add(Position.at(r, c));
        }
    }
    @Override boolean hopsKnight() { return true; }
}

/**
 * King: the eight neighbours. Castling is NOT generated here, because it is the one move that depends on
 * whether squares are attacked, and no piece can see whole-board safety. The rules layer adds it.
 */
class King extends Piece {
    King(Color color) { super(color, 'K'); }
    @Override void attacks(Board board, Position from, List<Position> out) {
        for (int dr = -1; dr <= 1; dr++)
            for (int dc = -1; dc <= 1; dc++) {
                if (dr == 0 && dc == 0) continue;
                int r = from.row() + dr, c = from.col() + dc;
                if (Position.onBoard(r, c)) out.add(Position.at(r, c));
            }
    }
    @Override boolean stepsOne() { return true; }
    @Override boolean isKing() { return true; }
}

/**
 * Pawn: the piece that breaks every rule, and therefore the only one that overrides pseudoMoves. It attacks
 * two diagonals but moves straight ahead, so reusing one for the other is the classic silently-wrong bug:
 * check detection would then think a pawn in front of a king gives check.
 */
class Pawn extends Piece {
    Pawn(Color color) { super(color, 'P'); }

    /** The two forward diagonals. This is what check detection uses, and it is NOT where the pawn can move. */
    @Override void attacks(Board board, Position from, List<Position> out) {
        int r = from.row() + color.forward();
        for (int dc = -1; dc <= 1; dc += 2)
            if (Position.onBoard(r, from.col() + dc)) out.add(Position.at(r, from.col() + dc));
    }

    /**
     * One forward if empty, two from the starting rank if both are empty, a diagonal only to take something,
     * en passant onto an empty square whose victim stands beside the pawn, and a promotion fanned out into the
     * four legal choices. Each of those five clauses exists because a rule said so.
     */
    @Override void pseudoMoves(Board board, Position from, List<Move> out) {
        int fw = color.forward(), r1 = from.row() + fw, col = from.col();
        if (Position.onBoard(r1, col) && board.at(r1, col) == null) {
            addForward(from, Position.at(r1, col), null, out);
            int r2 = from.row() + 2 * fw;
            if (from.row() == color.pawnRow() && board.at(r2, col) == null)
                out.add(Move.doublePawn(from, Position.at(r2, col), this));
        }
        for (int dc = -1; dc <= 1; dc += 2) {
            int c = col + dc;
            if (!Position.onBoard(r1, c)) continue;
            Position to = Position.at(r1, c);
            Piece there = board.at(to);
            if (there != null && there.color != color) addForward(from, to, there, out);
            else if (there == null && to.equals(board.enPassantTarget())) {
                Position victimAt = Position.at(from.row(), c);            // the victim is NOT on the destination
                Piece victim = board.at(victimAt);
                if (victim != null && victim.isPawn() && victim.color != color)
                    out.add(Move.enPassant(from, to, this, victim, victimAt));
            }
        }
    }

    /** One move, or four if this lands on the last rank: under-promotion to a knight is legal and sometimes wins. */
    private void addForward(Position from, Position to, Piece victim, List<Move> out) {
        if (to.row() != color.lastRow()) {
            out.add(victim == null ? Move.quiet(from, to, this) : Move.capture(from, to, this, victim));
            return;
        }
        for (Piece choice : Pieces.promotionChoices(color)) out.add(Move.promotion(from, to, this, victim, choice));
    }

    @Override boolean attacksPawnwise() { return true; }
    @Override boolean isPawn() { return true; }
}

/**
 * The piece registry. Pieces hold no state, so ONE object per colour per kind serves every game in the process
 * (the Flyweight pattern, earned rather than chosen). A new piece kind is one register() call: FEN, promotion,
 * printing and check detection all keep working.
 */
final class Pieces {
    private static final Map<Character, Piece[]> BY_LETTER = new ConcurrentHashMap<>();
    static {
        register('P', Pawn::new); register('N', Knight::new); register('B', Bishop::new);
        register('R', Rook::new); register('Q', Queen::new);  register('K', King::new);
    }
    /** Add a kind of piece: one line, and every part of the engine accepts it. */
    static void register(char letter, Function<Color, Piece> maker) {
        BY_LETTER.put(Character.toUpperCase(letter), new Piece[] { maker.apply(Color.WHITE), maker.apply(Color.BLACK) });
    }
    /** The shared piece for this letter, the case deciding the colour: 'R' white rook, 'r' black rook. */
    static Piece bySymbol(char fenLetter) {
        Piece[] pair = BY_LETTER.get(Character.toUpperCase(fenLetter));
        if (pair == null) throw new IllegalArgumentException("no piece registered for '" + fenLetter + "'");
        return pair[Character.isUpperCase(fenLetter) ? 0 : 1];
    }
    static Piece of(Color c, char letter) { return bySymbol(c == Color.WHITE ? Character.toUpperCase(letter) : Character.toLowerCase(letter)); }
    static Piece pawn(Color c)   { return of(c, 'P'); }
    static Piece knight(Color c) { return of(c, 'N'); }
    static Piece bishop(Color c) { return of(c, 'B'); }
    static Piece rook(Color c)   { return of(c, 'R'); }
    static Piece queen(Color c)  { return of(c, 'Q'); }
    static Piece king(Color c)   { return of(c, 'K'); }
    /** The four pieces a pawn may become. A king is not on this list, which is why promoting to one is refused. */
    static List<Piece> promotionChoices(Color c) { return List.of(queen(c), rook(c), bishop(c), knight(c)); }
    private Pieces() {}
}

/**
 * One move, as a value. It carries everything the board edit needs AND everything the undo needs: what was
 * captured and from which square (en passant takes from a square that is not the destination), and what the
 * pawn became. Because pieces are shared objects, two Moves with the same fields are equal, which is what lets
 * play() check the caller's move against the generated set with one contains().
 */
record Move(Position from, Position to, Piece moved, MoveKind kind, Piece captured, Position capturedAt, Piece promoteTo) {
    static Move quiet(Position f, Position t, Piece moved) { return new Move(f, t, moved, MoveKind.NORMAL, null, null, null); }
    static Move capture(Position f, Position t, Piece moved, Piece victim) { return new Move(f, t, moved, MoveKind.NORMAL, victim, t, null); }
    static Move doublePawn(Position f, Position t, Piece moved) { return new Move(f, t, moved, MoveKind.DOUBLE_PAWN, null, null, null); }
    static Move enPassant(Position f, Position t, Piece moved, Piece victim, Position victimAt) { return new Move(f, t, moved, MoveKind.EN_PASSANT, victim, victimAt, null); }
    static Move promotion(Position f, Position t, Piece moved, Piece victim, Piece becomes) { return new Move(f, t, moved, MoveKind.PROMOTION, victim, victim == null ? null : t, becomes); }
    static Move castle(Position f, Position t, Piece king, boolean kingSide) { return new Move(f, t, king, kingSide ? MoveKind.CASTLE_KING : MoveKind.CASTLE_QUEEN, null, null, null); }

    /** Did this move take something? The fifty-move clock and the draw rules ask. */
    boolean isCapture() { return captured != null; }
    @Override public String toString() {
        if (kind == MoveKind.CASTLE_KING) return "O-O";
        if (kind == MoveKind.CASTLE_QUEEN) return "O-O-O";
        String piece = moved.isPawn() ? "" : String.valueOf(Character.toUpperCase(moved.symbol()));
        String promo = promoteTo == null ? "" : "=" + Character.toUpperCase(promoteTo.symbol());
        return piece + from + (captured == null ? "-" : "x") + to + promo;
    }
}

/**
 * Everything a move must put back, captured at the instant before the move is applied. The rights, the en
 * passant square and the fifty-move clock are board state a move quietly destroys, so the undo carries them.
 * This record IS the undo half of the Command pattern; the history is a stack of them.
 */
record Undo(Move move, Position enPassantBefore, boolean[] rightsBefore, int halfmoveBefore) {}

/**
 * The board: the 64 squares plus the three pieces of state that move generation must see and that a naive
 * design forgets -- which squares may still castle, which square is capturable en passant for exactly one ply,
 * and how many plies since the last pawn move or capture. It also answers the one question the whole engine
 * leans on: is this square attacked?
 */
class Board {
    private final Piece[] squares = new Piece[64];
    private final Position[] kings = new Position[2];      // cached: finding a king is O(1), never a 64-square scan
    private Position enPassantTarget;                      // set by a double pawn push, cleared by the next move
    private final boolean[] rights = new boolean[4];       // 0 = White O-O, 1 = White O-O-O, 2 = Black O-O, 3 = Black O-O-O
    private int halfmove;                                  // plies since the last capture or pawn move

    /** What is on this square, or null. O(1). */
    Piece at(Position p) { return squares[p.index()]; }
    /** What is on these coordinates, or null. The caller has already checked they are on the board. */
    Piece at(int row, int col) { return squares[row * 8 + col]; }
    /** Put a piece down, keeping the king cache in step. */
    void place(Position p, Piece piece) {
        squares[p.index()] = piece;
        if (piece != null && piece.isKing()) kings[piece.color.ordinal()] = p;
    }
    /** Lift a piece off and return it. Kings are never removed without being placed again in the same breath. */
    Piece remove(Position p) { Piece was = squares[p.index()]; squares[p.index()] = null; return was; }
    /** Where this side's king stands. O(1), because place() maintains it. */
    Position kingOf(Color c) { return kings[c.ordinal()]; }

    Position enPassantTarget() { return enPassantTarget; }
    void setEnPassantTarget(Position p) { enPassantTarget = p; }
    int halfmoveClock() { return halfmove; }
    void setHalfmoveClock(int n) { halfmove = n; }
    /** A copy of the four castling rights, for an Undo to hold. */
    boolean[] rights() { return rights.clone(); }
    void setRights(boolean[] four) { System.arraycopy(four, 0, rights, 0, 4); }
    /** May this side still castle on this side of the board? */
    boolean mayCastle(Color c, boolean kingSide) { return rights[c.ordinal() * 2 + (kingSide ? 0 : 1)]; }
    void revoke(Color c, boolean kingSide) { rights[c.ordinal() * 2 + (kingSide ? 0 : 1)] = false; }
    /** A rook leaving a corner, or being captured on it, kills exactly one right. Both cases are this one call. */
    void revokeIfCorner(Position p) {
        if (p.equals(Position.of("h1"))) revoke(Color.WHITE, true);
        else if (p.equals(Position.of("a1"))) revoke(Color.WHITE, false);
        else if (p.equals(Position.of("h8"))) revoke(Color.BLACK, true);
        else if (p.equals(Position.of("a8"))) revoke(Color.BLACK, false);
    }

    /**
     * Is `target` attacked by any piece of colour `by`? Asked from the king's square, so it walks OUTWARD:
     * eight rays until the first piece, plus the eight knight offsets. At most 64 array reads whatever is on
     * the board, and usually about thirty, because a ray stops at the first piece it meets.
     *
     * It asks each piece it finds what it CAN DO, never what it is, so a new kind of piece that rides straight
     * lines or hops like a knight is detected here with no edit at all.
     */
    boolean isAttacked(Position target, Color by) {
        for (int[] d : RAYS) {
            boolean straight = d[0] == 0 || d[1] == 0;
            for (int step = 1; ; step++) {
                int r = target.row() + d[0] * step, c = target.col() + d[1] * step;
                if (!Position.onBoard(r, c)) break;
                Piece p = squares[r * 8 + c];
                if (p == null) continue;
                if (p.color == by) {
                    if (straight ? p.ridesStraight() : p.ridesDiagonal()) return true;
                    if (step == 1 && p.stepsOne()) return true;                       // an enemy king next door
                    // a pawn attacks FORWARD only, so it must be standing one row behind the target
                    if (step == 1 && !straight && p.attacksPawnwise() && d[0] == -by.forward()) return true;
                }
                break;                                                                // the ray is blocked either way
            }
        }
        for (int[] j : KNIGHT_OFFSETS) {
            int r = target.row() + j[0], c = target.col() + j[1];
            if (!Position.onBoard(r, c)) continue;
            Piece p = squares[r * 8 + c];
            if (p != null && p.color == by && p.hopsKnight()) return true;
        }
        return false;
    }
    /** Is this side's king attacked right now? The whole invariant, in one line. */
    boolean inCheck(Color c) { return isAttacked(kingOf(c), c.opponent()); }

    private static final int[][] RAYS = { {1, 0}, {-1, 0}, {0, 1}, {0, -1}, {1, 1}, {1, -1}, {-1, 1}, {-1, -1} };
    private static final int[][] KNIGHT_OFFSETS = { {2, 1}, {2, -1}, {-2, 1}, {-2, -1}, {1, 2}, {1, -2}, {-1, 2}, {-1, -2} };

    /** The standard opening position. */
    static Board start() { return fromFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"); }

    /**
     * Read a position from FEN, the one-line standard notation. This is how every test in this file sets up a
     * position in one line, and it is also the save format a persistence follow-up would use.
     */
    static Board fromFen(String fen) {
        String[] f = fen.trim().split("\\s+");
        Board b = new Board();
        String[] ranks = f[0].split("/");                                  // ranks[0] is rank 8, which is row 7
        for (int i = 0; i < 8; i++) {
            int row = 7 - i, col = 0;
            for (char ch : ranks[i].toCharArray()) {
                if (Character.isDigit(ch)) col += ch - '0';
                else b.place(Position.at(row, col++), Pieces.bySymbol(ch));
            }
        }
        String r = f.length > 2 ? f[2] : "-";
        b.setRights(new boolean[] { r.indexOf('K') >= 0, r.indexOf('Q') >= 0, r.indexOf('k') >= 0, r.indexOf('q') >= 0 });
        b.setEnPassantTarget(f.length > 3 && !f[3].equals("-") ? Position.of(f[3]) : null);
        b.setHalfmoveClock(f.length > 4 ? Integer.parseInt(f[4]) : 0);
        return b;
    }

    /** Write the position back out as FEN. Two FENs being equal is the cheapest possible "the board is unchanged". */
    String toFen(Color toMove, int fullmove) {
        StringBuilder sb = new StringBuilder();
        for (int row = 7; row >= 0; row--) {
            int empty = 0;
            for (int col = 0; col < 8; col++) {
                Piece p = at(row, col);
                if (p == null) { empty++; continue; }
                if (empty > 0) { sb.append(empty); empty = 0; }
                sb.append(p.symbol());
            }
            if (empty > 0) sb.append(empty);
            if (row > 0) sb.append('/');
        }
        String r = (rights[0] ? "K" : "") + (rights[1] ? "Q" : "") + (rights[2] ? "k" : "") + (rights[3] ? "q" : "");
        return sb.append(' ').append(toMove == Color.WHITE ? 'w' : 'b')
                 .append(' ').append(r.isEmpty() ? "-" : r)
                 .append(' ').append(enPassantTarget == null ? "-" : enPassantTarget.toString())
                 .append(' ').append(halfmove).append(' ').append(fullmove).toString();
    }

    /**
     * The identity of a position for the repetition rule: the pieces, the side to move, the castling rights and
     * the en passant square -- but not the clocks. Two positions with this key are the same position in FIDE's
     * sense. A real engine keeps a rolling Zobrist hash instead of building a string once per ply.
     */
    String positionKey(Color toMove) {
        String fen = toFen(toMove, 1);
        return fen.substring(0, fen.lastIndexOf(' ', fen.lastIndexOf(' ') - 1));
    }

    /** The position as eight lines, for a human. */
    String render() {
        StringBuilder sb = new StringBuilder();
        for (int row = 7; row >= 0; row--) {
            sb.append(row + 1).append("  ");
            for (int col = 0; col < 8; col++) { Piece p = at(row, col); sb.append(p == null ? '.' : p.symbol()).append(' '); }
            sb.append('\n');
        }
        return sb.append("   a b c d e f g h\n").toString();
    }
}

/**
 * The rule that decides how a game ends. One method, because "when is it over" is exactly what a variant or a
 * house rule changes, and the Game is handed the rule rather than building one.
 */
interface RuleSet {
    /** Given whether the side to move is in check and whether it has any legal move, what is the status? */
    GameStatus adjudicate(Game game, boolean inCheck, boolean anyLegalMove);
}

/**
 * Ordinary chess. Notice that checkmate and stalemate are not two detectors: they are one condition -- the side
 * to move has no legal move -- split by whether that side is in check. Two detectors drift apart; this cannot.
 */
class StandardRules implements RuleSet {
    public GameStatus adjudicate(Game game, boolean inCheck, boolean anyLegalMove) {
        if (!anyLegalMove) return inCheck ? GameStatus.CHECKMATE : GameStatus.STALEMATE;
        return inCheck ? GameStatus.CHECK : GameStatus.ACTIVE;
    }
}

/**
 * The draws that are facts about the HISTORY rather than the position: the fifty-move rule and threefold
 * repetition. It wraps any other rule set instead of editing it, so the same class works over ordinary chess
 * and over a variant, and the two thresholds are parameters so a test does not have to play a hundred plies.
 */
class DrawRules implements RuleSet {
    private final RuleSet base;
    private final int halfmoveLimit, repetitionLimit;

    /** Standard chess: a draw at 100 plies without a pawn move or capture, and at the third repetition. */
    DrawRules(RuleSet base) { this(base, 100, 3); }
    DrawRules(RuleSet base, int halfmoveLimit, int repetitionLimit) {
        this.base = base; this.halfmoveLimit = halfmoveLimit; this.repetitionLimit = repetitionLimit;
    }
    public GameStatus adjudicate(Game game, boolean inCheck, boolean anyLegalMove) {
        GameStatus decided = base.adjudicate(game, inCheck, anyLegalMove);
        if (decided.over()) return decided;                                // checkmate beats every draw rule
        if (game.halfmoveClock() >= halfmoveLimit) return GameStatus.DRAW;
        if (game.timesRepeated() >= repetitionLimit) return GameStatus.DRAW;
        return decided;
    }
}

/** Where time comes from. Injected, so a chess clock can be tested without waiting for real seconds to pass. */
interface Clock { long nowMs(); }

/**
 * Anyone who wants to know a move happened: a spectator, a move list, a clock, an analytics feed. The game
 * announces without knowing what any of them is, and they are called AFTER the lock is released.
 */
interface GameObserver {
    /** Called once per committed move, after the game's lock is released. Must not throw; if it does, it is ignored. */
    void onMove(Game game, Move move, GameStatus after);
}

/** A spectator that prints. The simplest possible proof that the game announces without knowing its audience. */
class MoveLogger implements GameObserver {
    public void onMove(Game game, Move move, GameStatus after) {
        System.out.println("  " + game.id() + ": " + move + "  -> " + after);
    }
}

/**
 * The aggregate root: one game owns its board, whose turn it is, the history, the status and ONE lock. Every
 * write goes through play(), which re-derives legality itself rather than trusting the caller, edits the board
 * only after the move is known legal, and tells the spectators only after the lock is released.
 *
 * Chess is turn-based, so the lock is not there for two players racing each other: it is there for two REQUESTS
 * for the same game -- a double click, a retry, a second browser tab -- which would otherwise both validate
 * against the same board and both apply.
 */
class Game {
    private final String id;
    private final Board board;
    private Color toMove;
    private int fullmove;
    private GameStatus status;
    private final Deque<Undo> history = new ArrayDeque<>();
    private final Map<String, Integer> seen = new HashMap<>();          // position key -> how many times reached
    private final ReentrantLock lock = new ReentrantLock();
    private final List<GameObserver> observers = new CopyOnWriteArrayList<>();
    private RuleSet rules = new StandardRules();
    private Clock clock = System::currentTimeMillis;
    private List<Move> cachedLegal;                                     // one generation per ply, not one per question

    Game(String id, Board board, Color toMove, int fullmove) {
        this.id = id; this.board = board; this.toMove = toMove; this.fullmove = fullmove;
        this.seen.merge(board.positionKey(toMove), 1, Integer::sum);
        this.status = judge();
    }
    /** A new game in the opening position. */
    static Game newGame(String id) { return new Game(id, Board.start(), Color.WHITE, 1); }
    /** A game from a FEN string: the one-line way a test, a puzzle screen or a resumed game states a position. */
    static Game fromFen(String id, String fen) {
        String[] f = fen.trim().split("\\s+");
        Color side = f.length > 1 && f[1].equals("b") ? Color.BLACK : Color.WHITE;
        int full = f.length > 5 ? Integer.parseInt(f[5]) : 1;
        return new Game(id, Board.fromFen(fen), side, full);
    }

    /**
     * Hand in the rules. The game never builds a rule set, which is why the fifty-move rule, a variant and a
     * house rule are all "one class, one line here" and touch nothing else.
     */
    void configure(RuleSet rules) {
        lock.lock();
        try { this.rules = rules; this.status = judge(); } finally { lock.unlock(); }
    }
    /** Tests hand in a fixed clock, so a chess clock's arithmetic is checked without waiting for real seconds. */
    void setClock(Clock c) { clock = c; }
    /** Subscribe a spectator. Setup only; spectators are called after the lock, never inside it. */
    void addObserver(GameObserver o) { observers.add(o); }

    String id() { return id; }
    /** The board, for rendering and for questions like "what is on e4". Do not edit it; play() owns every write. */
    Board board() { return board; }
    Color toMove() { lock.lock(); try { return toMove; } finally { lock.unlock(); } }
    GameStatus status() { lock.lock(); try { return status; } finally { lock.unlock(); } }
    /** The winner of a finished game, or null if it is not a checkmate. */
    Color winner() { lock.lock(); try { return status == GameStatus.CHECKMATE ? toMove.opponent() : null; } finally { lock.unlock(); } }
    /** How many plies have been played. Also the version number an online game compares against. */
    int ply() { lock.lock(); try { return history.size(); } finally { lock.unlock(); } }
    int halfmoveClock() { return board.halfmoveClock(); }
    /** How many times the CURRENT position has been reached. The threefold rule reads this. */
    int timesRepeated() { return seen.getOrDefault(board.positionKey(toMove), 0); }
    /** Every move played, oldest first. The move list is the save format and the takeback stack. */
    List<Move> history() {
        lock.lock();
        try { List<Move> out = new ArrayList<>(history.size()); for (Undo u : history) out.add(0, u.move()); return out; }
        finally { lock.unlock(); }
    }
    /** The position as FEN: the whole game state in one line. */
    String fen() { lock.lock(); try { return board.toFen(toMove, fullmove); } finally { lock.unlock(); } }

    /**
     * Every legal move for the side to move. Generated once per ply and remembered, because a user interface
     * asks this on every click and the status check asks it again straight after every move.
     */
    List<Move> legalMoves() { lock.lock(); try { return legalMovesLocked(); } finally { lock.unlock(); } }

    /**
     * Play a move. The order is the design:
     *   1. refuse outright if the game is already over;
     *   2. re-derive the legal set here -- a user interface that offers only legal moves is a convenience, never
     *      a guarantee, and play() is the only thing standing between a hostile client and a broken board;
     *   3. only now edit the board, then push the undo record, flip the turn and re-judge the status;
     *   4. release the lock, and only then tell the spectators.
     * A refused move throws before step 3, so the board, the turn and the history are exactly as they were and
     * the caller can simply try again.
     */
    GameStatus play(Move move) {
        Objects.requireNonNull(move, "move");
        GameStatus after;
        lock.lock();
        try { after = commit(move); } finally { lock.unlock(); }
        publish(move, after);                                            // outside the lock: a slow spectator stalls nobody
        return after;
    }

    /**
     * Play a move only if the game is still at the ply the client saw. This is the same critical section with an
     * optimistic check in front of it: a client that has been away, or a retried request, comes back with a move
     * computed on a stale board and is refused rather than silently applied. It is the in-memory twin of
     * <code>UPDATE games SET ... WHERE ply = ?</code>, which is how the same guarantee is written once the game
     * lives in a database and two servers can both hold a request for it.
     */
    GameStatus play(int expectedPly, Move move) {
        Objects.requireNonNull(move, "move");
        GameStatus after;
        lock.lock();
        try {
            if (history.size() != expectedPly)
                throw new IllegalMoveException("stale board: you saw ply " + expectedPly + ", the game is at ply " + history.size());
            after = commit(move);
        } finally { lock.unlock(); }
        publish(move, after);
        return after;
    }

    /** The critical section itself. The caller holds the lock; nothing slow and nothing external happens in here. */
    private GameStatus commit(Move move) {
        if (status.over()) throw new IllegalMoveException("the game is over: " + status);
        if (!legalMovesLocked().contains(move)) throw new IllegalMoveException("not a legal move: " + move);
        history.push(applyMove(move));                                   // the board edit, and its exact undo
        toMove = toMove.opponent();
        if (toMove == Color.WHITE) fullmove++;
        cachedLegal = null;
        seen.merge(board.positionKey(toMove), 1, Integer::sum);
        return status = judge();
    }

    /**
     * Take back the last move. The undo record holds the captured piece, the castling rights, the en passant
     * square and the fifty-move clock, so this restores the position exactly -- the same mechanism the legality
     * filter uses thousands of times a second, which is why it is the best-tested code in the file.
     */
    Move undo() {
        lock.lock();
        try {
            if (history.isEmpty()) throw new IllegalStateException("no move to take back");
            seen.merge(board.positionKey(toMove), -1, Integer::sum);
            Undo u = history.pop();
            undoMove(u);
            toMove = toMove.opponent();
            if (toMove == Color.BLACK) fullmove--;
            cachedLegal = null;
            status = judge();
            return u.move();
        } finally { lock.unlock(); }
    }

    // ---------------------------------------------------------------- the rules layer, all under the lock

    private List<Move> legalMovesLocked() {
        if (cachedLegal != null) return cachedLegal;
        List<Move> pseudo = new ArrayList<>(48);
        for (int i = 0; i < 64; i++) {
            Position from = Position.at(i / 8, i % 8);
            Piece p = board.at(from);
            if (p != null && p.color == toMove) p.pseudoMoves(board, from, pseudo);
        }
        addCastles(pseudo);
        List<Move> legal = new ArrayList<>(pseudo.size());
        for (Move m : pseudo) {
            Undo u = applyMove(m);                                       // play it for real...
            boolean safe = !board.inCheck(toMove);                       // ...ask the only question that matters...
            undoMove(u);                                                 // ...and put everything back, exactly.
            if (safe) legal.add(m);
        }
        return cachedLegal = List.copyOf(legal);
    }

    /**
     * Castling is generated here and not in King, because it is the one move whose legality depends on squares
     * being attacked, and no piece can see the whole board. Five conditions: the right is still held, the rook
     * is still there, the squares between are empty, and the king is not in check, does not pass through an
     * attacked square, and does not land on one (the last is left to the ordinary filter).
     */
    private void addCastles(List<Move> out) {
        int row = toMove == Color.WHITE ? 0 : 7;
        Position kingSquare = Position.at(row, 4);
        Piece king = board.at(kingSquare);
        if (king == null || !king.isKing() || king.color != toMove) return;
        if (board.isAttacked(kingSquare, toMove.opponent())) return;     // you may not castle out of check
        if (board.mayCastle(toMove, true) && rookAt(row, 7)
                && board.at(row, 5) == null && board.at(row, 6) == null
                && !board.isAttacked(Position.at(row, 5), toMove.opponent()))
            out.add(Move.castle(kingSquare, Position.at(row, 6), king, true));
        if (board.mayCastle(toMove, false) && rookAt(row, 0)
                && board.at(row, 1) == null && board.at(row, 2) == null && board.at(row, 3) == null
                && !board.isAttacked(Position.at(row, 3), toMove.opponent()))
            out.add(Move.castle(kingSquare, Position.at(row, 2), king, false));
    }
    private boolean rookAt(int row, int col) {
        Piece p = board.at(row, col);
        return p != null && p.color == toMove && p.ridesStraight() && !p.ridesDiagonal();
    }

    /**
     * Edit the board, and return everything needed to put it back. This touches the squares, the king cache,
     * the castling rights, the en passant square and the fifty-move clock -- and nothing else, so the legality
     * filter can call it thousands of times without disturbing the turn, the history or the status.
     */
    private Undo applyMove(Move m) {
        Undo undo = new Undo(m, board.enPassantTarget(), board.rights(), board.halfmoveClock());
        Piece mover = board.remove(m.from());
        if (m.capturedAt() != null) board.remove(m.capturedAt());        // en passant clears a DIFFERENT square
        switch (m.kind()) {
            case PROMOTION -> board.place(m.to(), m.promoteTo());
            case CASTLE_KING -> { board.place(m.to(), mover); board.place(Position.at(m.from().row(), 5), board.remove(Position.at(m.from().row(), 7))); }
            case CASTLE_QUEEN -> { board.place(m.to(), mover); board.place(Position.at(m.from().row(), 3), board.remove(Position.at(m.from().row(), 0))); }
            default -> board.place(m.to(), mover);
        }
        // the en passant square is created by a double push and destroyed by literally anything else: one ply
        board.setEnPassantTarget(m.kind() == MoveKind.DOUBLE_PAWN
                ? Position.at((m.from().row() + m.to().row()) / 2, m.from().col()) : null);
        if (mover.isKing()) { board.revoke(mover.color, true); board.revoke(mover.color, false); }
        board.revokeIfCorner(m.from());                                  // a rook left its corner
        board.revokeIfCorner(m.to());                                    // or a rook was captured on its corner
        board.setHalfmoveClock(m.moved().isPawn() || m.isCapture() ? 0 : undo.halfmoveBefore() + 1);
        return undo;
    }

    /** The exact mirror of applyMove. Every line here undoes one line there, in the opposite order. */
    private void undoMove(Undo u) {
        Move m = u.move();
        Piece mover = board.remove(m.to());
        if (m.kind() == MoveKind.PROMOTION) mover = Pieces.pawn(mover.color);
        board.place(m.from(), mover);
        if (m.kind() == MoveKind.CASTLE_KING) board.place(Position.at(m.from().row(), 7), board.remove(Position.at(m.from().row(), 5)));
        if (m.kind() == MoveKind.CASTLE_QUEEN) board.place(Position.at(m.from().row(), 0), board.remove(Position.at(m.from().row(), 3)));
        if (m.captured() != null) board.place(m.capturedAt(), m.captured());
        board.setEnPassantTarget(u.enPassantBefore());
        board.setRights(u.rightsBefore());
        board.setHalfmoveClock(u.halfmoveBefore());
    }

    /** Ask the rule set what the position means. Two facts go in: is the side to move in check, and has it a move. */
    private GameStatus judge() {
        boolean inCheck = board.inCheck(toMove);
        return rules.adjudicate(this, inCheck, !legalMovesLocked().isEmpty());
    }

    /** Tell the spectators. Outside the lock, and inside a try/catch, so a broken spectator cannot break chess. */
    private void publish(Move move, GameStatus after) {
        for (GameObserver o : observers) {
            try { o.onMove(this, move, after); }
            catch (RuntimeException ignored) { /* a spectator's problem is never the game's problem */ }
        }
    }
}

/**
 * The thin caller: many games at once, each with its own lock. Two games never wait for each other, which is
 * the whole reason the lock lives on the game and not on the service.
 */
class ChessService {
    private final Map<String, Game> games = new ConcurrentHashMap<>();
    /** Start a game in the opening position. */
    Game newGame(String id) { Game g = Game.newGame(id); games.put(id, g); return g; }
    /** Start a game from a position. */
    Game newGame(String id, String fen) { Game g = Game.fromFen(id, fen); games.put(id, g); return g; }
    /** The game, or an error. O(1). */
    Game game(String id) {
        Game g = games.get(id);
        if (g == null) throw new NoSuchElementException("no such game: " + id);
        return g;
    }
}

/**
 * Proof it works: an opening, a castle, an en passant, an under-promotion, fool's mate, a stalemate, a
 * takeback, and fifty clients firing moves at ONE game at the same instant with exactly one landing.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        ChessService service = new ChessService();
        Game game = service.newGame("g1");
        game.addObserver(new MoveLogger());
        game.configure(new DrawRules(new StandardRules()));               // the draw rules wrap the ordinary ones

        System.out.println(game.board().render());
        System.out.println("legal moves in the opening position: " + game.legalMoves().size() + " (must be 20)");

        // the Italian: four moves each, ending in a kingside castle
        for (String m : new String[] { "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1" }) play(game, m);
        System.out.println("after O-O, f1 holds " + game.board().at(Position.of("f1")) + " and g1 holds " + game.board().at(Position.of("g1")));
        System.out.println("status " + game.status() + ", ply " + game.ply() + ", fen " + game.fen());

        // en passant: Black has just pushed b7-b5, and the window is exactly this ply
        Game ep = service.newGame("ep", "rnbqkbnr/p1pppppp/8/1pP5/8/8/PP1PPPPP/RNBQKBNR w KQkq b6 0 3");
        Move take = find(ep, "c5b6");
        System.out.println("en passant " + take + ": the victim stands on " + take.capturedAt() + ", not on " + take.to());
        ep.play(take);
        System.out.println("after it, b5 holds " + ep.board().at(Position.of("b5")) + " and b6 holds " + ep.board().at(Position.of("b6")));

        // promotion fans out into four choices, and a king is not one of them
        Game promo = service.newGame("promo", "8/P6k/8/8/8/8/7K/8 w - - 0 1");
        List<Move> pawnMoves = promo.legalMoves().stream().filter(m -> m.from().equals(Position.of("a7"))).toList();
        System.out.println("promotion choices: " + pawnMoves + " (four, including the knight)");
        promo.play(pawnMoves.stream().filter(m -> m.promoteTo() == Pieces.knight(Color.WHITE)).findFirst().orElseThrow());
        System.out.println("under-promoted: a8 now holds " + promo.board().at(Position.of("a8")));

        // fool's mate: checkmate and stalemate come out of the same primitive
        Game mate = service.newGame("mate");
        for (String m : new String[] { "f2f3", "e7e5", "g2g4", "d8h4" }) play(mate, m);
        System.out.println("fool's mate -> " + mate.status() + ", winner " + mate.winner()
            + ", legal moves left " + mate.legalMoves().size());
        try { mate.play(Move.quiet(Position.of("h2"), Position.of("h3"), Pieces.pawn(Color.WHITE))); }
        catch (IllegalMoveException e) { System.out.println("expected: " + e.getMessage()); }

        Game stale = service.newGame("stale", "7k/8/6Q1/8/8/8/8/K7 b - - 0 1");
        System.out.println("black to move, no legal move, not in check -> " + stale.status()
            + " (legal moves: " + stale.legalMoves().size() + ")");

        // takeback: the captured piece comes back, exactly
        Game back = service.newGame("back", "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2");
        String before = back.fen();
        back.play(find(back, "e4d5"));
        System.out.println("after exd5, d5 holds " + back.board().at(Position.of("d5")));
        back.undo();
        System.out.println("after the takeback the position is identical: " + before.equals(back.fen()));

        // fifty clients fire a move at ONE game at the same instant: exactly one may land
        Game contested = service.newGame("race");
        List<Move> opening = contested.legalMoves();
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Boolean>> sent = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final Move mine = opening.get(i % opening.size());
            sent.add(pool.submit(() -> { go.await(); try { contested.play(mine); return true; } catch (IllegalMoveException e) { return false; } }));
        }
        go.countDown();
        int accepted = 0, refused = 0;
        for (Future<Boolean> f : sent) { if (f.get()) accepted++; else refused++; }
        pool.shutdown();
        System.out.println("50 clients, one game: accepted=" + accepted + " refused=" + refused
            + " ply=" + contested.ply() + " toMove=" + contested.toMove() + " (must be 1, 49, 1, BLACK)");
        if (accepted != 1 || contested.ply() != 1) throw new AssertionError("two moves landed on the same turn");

        // what the lock actually costs: whole random games, timed, after a warm-up
        for (int i = 0; i < 5; i++) randomGame(service, "warm" + i, new Random(i));
        long t0 = System.nanoTime(); int plies = 0;
        for (int i = 0; i < 10; i++) plies += randomGame(service, "timed" + i, new Random(100 + i));
        long perMove = (System.nanoTime() - t0) / Math.max(plies, 1) / 1000;
        System.out.println(plies + " plies of random games, " + perMove
            + " microseconds per move inside the lock (generate every legal move, filter it, commit, re-judge)");
    }

    /** Play a whole game at random, up to 160 plies. The generator does all the work, so this times the lock. */
    private static int randomGame(ChessService service, String id, Random random) {
        Game g = service.newGame(id);
        int plies = 0;
        while (!g.status().over() && plies < 160) {
            List<Move> legal = g.legalMoves();
            g.play(legal.get(random.nextInt(legal.size())));
            plies++;
        }
        return plies;
    }

    /** Play a move written as "e2e4", the way a coordinate-based user interface sends it. */
    private static void play(Game game, String coords) { game.play(find(game, coords)); }

    /** Find the legal move that goes from one square to another; a promotion defaults to a queen. */
    private static Move find(Game game, String coords) {
        Position from = Position.of(coords.substring(0, 2)), to = Position.of(coords.substring(2, 4));
        return game.legalMoves().stream()
            .filter(m -> m.from().equals(from) && m.to().equals(to))
            .filter(m -> m.promoteTo() == null || m.promoteTo() == Pieces.queen(m.moved().color))
            .findFirst().orElseThrow(() -> new IllegalMoveException("no legal move " + coords));
    }
}
