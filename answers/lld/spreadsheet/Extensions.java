import java.util.*;
import java.util.concurrent.*;

// The reference code for every follow-up on page 05. Each block is one twist an interviewer adds; none of them
// opens Main.java. ExtDemo at the bottom runs all of them, so none can rot.

// ---- ext: a new function -- MEDIAN is one class and one register() line. This is the axis the design exists for.
/** MEDIAN of the numeric arguments. Extends the base class, so it gets error propagation and blank-skipping free. */
final class MedianFunction extends NumericFunction {
    public String name() { return "MEDIAN"; }
    protected Value reduce(List<Double> n) {
        List<Double> s = new ArrayList<>(n);
        Collections.sort(s);
        int m = s.size();
        return new Num(m % 2 == 1 ? s.get(m / 2) : (s.get(m / 2 - 1) + s.get(m / 2)) / 2);
    }
}

/** VLOOKUP over a flattened range: the first column is keys, the rest are columns of answers. */
final class VlookupFunction implements SheetFunction {
    private final int width;
    /** width = how many columns the flattened table has, because a range arrives as a flat list of values. */
    VlookupFunction(int width) { this.width = width; }
    public String name() { return "VLOOKUP"; }
    public Value apply(List<Value> args) {
        if (args.size() < 3) return new Err("#VALUE!");
        Value key = args.get(0);
        Double col = Evaluator.num(args.get(args.size() - 1));
        if (col == null) return new Err("#VALUE!");
        List<Value> table = args.subList(1, args.size() - 1);
        for (int r = 0; r + width <= table.size(); r += width)
            if (table.get(r).display().equals(key.display())) return table.get(r + col.intValue() - 1);
        return new Err("#N/A");
    }
}

// ---- ext: IFERROR -- the one function that must SEE an error, so it declines the propagating base class
/** IFERROR(value, fallback): the only function allowed to swallow an error, which is why it is not a NumericFunction. */
final class IfErrorFunction implements SheetFunction {
    public String name() { return "IFERROR"; }
    public Value apply(List<Value> args) {
        if (args.size() != 2) return new Err("#VALUE!");
        return args.get(0) instanceof Err ? args.get(1) : args.get(0);
    }
}

// ---- ext: the cycle policy -- Excel refuses the edit, Sheets paints #CYCLE! on the loop. Same detection, two policies.
/** What the product does when an edit would make a loop. The detection never changes; only this does. */
interface CyclePolicy {
    /** Called with the loop the sheet found. Returns what the user should see in the cell they were typing in. */
    String onCycle(List<CellRef> loop);
}
/** Excel's behaviour, and the sheet's own: refuse the edit and leave the sheet exactly as it was. */
final class RefuseCycle implements CyclePolicy {
    public String onCycle(List<CellRef> loop) { throw new CircularReferenceException(loop); }
}
/** Google Sheets' behaviour: accept it and mark every cell on the loop, leaving unrelated cells alone. */
final class MarkCycle implements CyclePolicy {
    private final Set<CellRef> marked = new LinkedHashSet<>();
    public String onCycle(List<CellRef> loop) { marked.addAll(loop); return "#CYCLE!"; }
    /** The cells currently known to be on a loop; a display layer paints these #CYCLE!. */
    Set<CellRef> marked() { return marked; }
}
/** The editor the UI calls. The sheet keeps its one honest behaviour; the policy decides what the product shows. */
final class PolicyEditor {
    private final Sheet sheet;
    private final CyclePolicy policy;
    PolicyEditor(Sheet sheet, CyclePolicy policy) { this.sheet = sheet; this.policy = policy; }
    /** Type into a cell. Returns what the cell now displays, which for a refused loop is the policy's answer. */
    String type(String a1, String text) {
        try { sheet.set(a1, text); return sheet.get(a1).display(); }
        catch (CircularReferenceException e) { return policy.onCycle(e.path()); }
    }
}

// ---- ext: undo and redo -- the edit is already reversible, because the sheet keeps the raw text of every cell
/** One typed edit, and the text that was there before it. Its own undo: replay `before` through set(). */
record EditCommand(String a1, String before, String after) { }

/** An undo stack over the sheet. Nothing in Main.java changes: undo is a second set() with the old text. */
final class EditHistory {
    private final Sheet sheet;
    private final Deque<EditCommand> undo = new ArrayDeque<>(), redo = new ArrayDeque<>();
    EditHistory(Sheet sheet) { this.sheet = sheet; }
    /** Type, and remember what was there. A new edit clears the redo stack, as every editor does. */
    void type(String a1, String text) {
        String before = sheet.raw(a1);
        sheet.set(a1, text);
        undo.push(new EditCommand(a1, before, text));
        redo.clear();
    }
    /** Put the previous text back. Dependents recompute for free, because it is an ordinary edit. */
    boolean undo() {
        if (undo.isEmpty()) return false;
        EditCommand c = undo.pop();
        sheet.set(c.a1(), c.before());
        redo.push(c);
        return true;
    }
    /** Re-apply the edit that was just undone. */
    boolean redo() {
        if (redo.isEmpty()) return false;
        EditCommand c = redo.pop();
        sheet.set(c.a1(), c.after());
        undo.push(c);
        return true;
    }
    /** How deep the undo stack is. */
    int depth() { return undo.size(); }
}

// ---- ext: lazy evaluation -- dirty flags and compute-on-read, and the honest reason the eager sheet is the default
/**
 * The other evaluation strategy: an edit marks the affected cells dirty and computes nothing; a read computes
 * what it needs and memoises it. Cheap when you edit a lot and read a little, which is not what a grid does.
 */
final class LazySheet {
    private final Map<CellRef, Expr> formulas = new HashMap<>();
    private final Map<CellRef, Value> cache = new HashMap<>();
    private final DependencyGraph graph = new DependencyGraph();
    private final Evaluator evaluator;
    private int evaluations;
    LazySheet(FunctionRegistry functions) { this.evaluator = new Evaluator(functions); }

    /** Type into a cell: rewire the edges, drop the cached values of everything affected, and stop. */
    void set(String a1, String text) {
        CellRef r = CellRef.parse(a1);
        Expr e = Parser.parseInput(text);
        Set<CellRef> refs = new LinkedHashSet<>();
        e.collectRefs(refs);
        graph.setPrecedents(r, refs);
        formulas.put(r, e);
        for (CellRef d : graph.affectedBy(r)) cache.remove(d);        // dirty, not recomputed
    }
    /** Read a cell, computing it and everything under it that is dirty, once each. */
    Value get(String a1) { return value(CellRef.parse(a1)); }
    private Value value(CellRef r) {
        Value v = cache.get(r);
        if (v != null) return v;
        Expr e = formulas.get(r);
        if (e == null) return Blank.IT;
        evaluations++;
        Value out = evaluator.eval(e, this::value);                   // memoised recursion is the invalidate-plus-cache
        cache.put(r, out);
        return out;
    }
    /** How many cells have actually been evaluated. The number that makes the trade-off visible. */
    int evaluations() { return evaluations; }
}

// ---- ext: a workbook -- the graph never mentions a Cell, only keys, so widening the key is the whole change
/** An address in a workbook: which sheet, then the cell. Equal-comparable, which is all the graph ever needed. */
record Addr(String sheet, CellRef ref) {
    @Override public String toString() { return sheet + "!" + ref; }
}

/**
 * DependencyGraph from Main.java with the key made a type parameter. Nothing about cycles, dirty sets or
 * topological order mentioned a cell, which is the proof that a workbook is a wider key and a parser change.
 */
final class Deps<K> {
    private final Map<K, Set<K>> precedents = new HashMap<>();
    private final Map<K, Set<K>> dependents = new HashMap<>();
    /** Point a key at the keys it reads, removing its old edges first. */
    void setPrecedents(K k, Set<K> refs) {
        for (K old : precedents.getOrDefault(k, Set.of())) {
            Set<K> d = dependents.get(old);
            if (d != null) { d.remove(k); if (d.isEmpty()) dependents.remove(old); }
        }
        if (refs.isEmpty()) precedents.remove(k); else precedents.put(k, new LinkedHashSet<>(refs));
        for (K p : refs) dependents.computeIfAbsent(p, x -> new LinkedHashSet<>()).add(k);
    }
    /** Everything that would recompute if this key changed. Also the set a new precedent must not be in. */
    Set<K> affectedBy(K from) {
        Set<K> seen = new LinkedHashSet<>();
        Deque<K> q = new ArrayDeque<>();
        seen.add(from); q.add(from);
        while (!q.isEmpty()) { K c = q.poll(); for (K d : dependents.getOrDefault(c, Set.<K>of())) if (seen.add(d)) q.add(d); }
        return seen;
    }
    /** Would pointing this key at those precedents make a loop? The same one-walk test as the sheet's. */
    boolean wouldCycle(K k, Set<K> refs) {
        Set<K> affected = affectedBy(k);
        for (K p : refs) if (affected.contains(p)) return true;
        return false;
    }
}

// ---- ext: persistence -- a repository and a conditional UPDATE, so two servers cannot silently lose an edit
/**
 * Where cells live when they must outlive the process. save() is the whole design: it writes only if the
 * stored version is the one the caller read, which is the database doing what the sheet's lock does in memory.
 *
 * UPDATE cells SET raw = ?, version = version + 1 WHERE sheet = ? AND a1 = ? AND version = ?
 */
interface CellRepository {
    /** Write the text if nobody else has written since `expectedVersion`. False means you must re-read and retry. */
    boolean save(String sheetId, String a1, String raw, int expectedVersion);
    /** The stored text, or "" if nothing is stored. */
    String load(String sheetId, String a1);
    /** The stored version, 0 if nothing is stored. Read it, then pass it back to save(). */
    int version(String sheetId, String a1);
}

/** The in-memory stand-in, with exactly the semantics of the conditional UPDATE above. */
final class InMemoryCellRepository implements CellRepository {
    private final Map<String, String[]> rows = new ConcurrentHashMap<>();      // key -> { raw, version }
    private static String key(String s, String a1) { return s + "!" + a1; }
    public synchronized boolean save(String sheetId, String a1, String raw, int expectedVersion) {
        String[] row = rows.get(key(sheetId, a1));
        int v = row == null ? 0 : Integer.parseInt(row[1]);
        if (v != expectedVersion) return false;                               // somebody else got there first
        rows.put(key(sheetId, a1), new String[] { raw, String.valueOf(v + 1) });
        return true;
    }
    public String load(String sheetId, String a1) { String[] r = rows.get(key(sheetId, a1)); return r == null ? "" : r[0]; }
    public int version(String sheetId, String a1) { String[] r = rows.get(key(sheetId, a1)); return r == null ? 0 : Integer.parseInt(r[1]); }
}

// ---- ext: lock-free readers -- an immutable snapshot behind one volatile reference, rebuilt as edits land
/**
 * A read path that takes no lock at all: every edit publishes a new immutable map, and readers follow one
 * volatile reference. A million cells being repainted never wait for a typist.
 */
final class SnapshotView {
    private volatile Map<CellRef, Value> view = Map.of();
    /** Subscribe to a sheet. Each committed change is merged into a fresh immutable map and published. */
    SnapshotView(Sheet sheet) { sheet.addListener(this::merge); }
    private synchronized void merge(CellChange c) {
        Map<CellRef, Value> next = new HashMap<>(view);
        next.put(c.ref(), c.after());
        view = Map.copyOf(next);                                              // one volatile write publishes the whole map
    }
    /** Read with no lock. At most one edit behind, because listeners run after the write lock is released. */
    Value get(String a1) { return view.getOrDefault(CellRef.parse(a1), Blank.IT); }
    /** How many cells the current snapshot holds. */
    int size() { return view.size(); }
}

// ---- ext: volatile functions -- NOW() changes with no cell changing, so something must re-post it on a tick
/** The cells whose answer moves on its own. A timer re-types their own text, which recomputes their dependents. */
final class VolatileCells {
    private final Set<String> watched = new LinkedHashSet<>();
    /** Register a cell whose formula is volatile: NOW(), RAND(), TODAY(). */
    void watch(String a1) { watched.add(a1); }
    /** One recalculation tick: re-post each volatile cell's own text through the ordinary edit path. */
    void tick(Sheet sheet) { for (String a1 : watched) sheet.set(a1, sheet.raw(a1)); }
    /** How many volatile cells are being watched. A sheet with thousands of them is the reason Excel warns about NOW(). */
    int size() { return watched.size(); }
}

// ---- ext: copy a formula -- relative references move with it, $-anchored ones do not, and the tree makes that one line
/**
 * The formula as text again. Needed the moment anything rewrites a formula -- a copy, an inserted row --
 * because the sheet stores what the user typed and the formula bar has to show the new version.
 * A round trip preserves meaning, not keystrokes: "=-A1" comes back as "=0-A1", and only the brackets the
 * precedence actually needs are printed.
 */
final class Formula {
    /** The tree as a formula the parser would read back, leading "=" included. */
    static String text(Expr e) { return "=" + write(e); }

    /** One address, with its anchors put back: A1, $A1, A$1, $A$1. */
    static String a1(Ref r) {
        String s = r.ref().a1();
        int k = 0;
        while (k < s.length() && Character.isLetter(s.charAt(k))) k++;
        return (r.absCol() ? "$" : "") + s.substring(0, k) + (r.absRow() ? "$" : "") + s.substring(k);
    }

    /**
     * The same tree, as it would read pasted dRow down and dCol right: an unanchored part moves by the
     * distance the formula moved, an anchored one does not, and a reference pushed off the grid is #REF!.
     */
    static Expr copyShift(Expr e, int dRow, int dCol) {
        if (e instanceof Ref r) {
            int row = r.absRow() ? r.ref().row() : r.ref().row() + dRow;
            int col = r.absCol() ? r.ref().col() : r.ref().col() + dCol;
            if (row < 0 || col < 0) return new Lit(new Err("#REF!"));       // dragged off the top or the left edge
            return new Ref(new CellRef(row, col), r.absRow(), r.absCol());
        }
        if (e instanceof RangeRef rr) {
            Expr a = copyShift(rr.from(), dRow, dCol), b = copyShift(rr.to(), dRow, dCol);
            if (!(a instanceof Ref x) || !(b instanceof Ref y)) return new Lit(new Err("#REF!"));
            return new RangeRef(x, y);
        }
        if (e instanceof Bin b) return new Bin(b.op(), copyShift(b.left(), dRow, dCol), copyShift(b.right(), dRow, dCol));
        if (e instanceof Call c) {
            List<Expr> args = new ArrayList<>();
            for (Expr a : c.args()) args.add(copyShift(a, dRow, dCol));
            return new Call(c.name(), args);
        }
        return e;                                                           // a literal copies unchanged
    }

    private static String write(Expr e) {
        if (e instanceof Lit l) return l.value() instanceof Text t ? "\"" + t.s() + "\"" : l.value().display();
        if (e instanceof Ref r) return a1(r);
        if (e instanceof RangeRef rr) return a1(rr.from()) + ":" + a1(rr.to());
        if (e instanceof Bin b) return side(b.left(), prec(b.op()), false) + b.op() + side(b.right(), prec(b.op()), true);
        if (e instanceof Call c) {
            StringBuilder sb = new StringBuilder(c.name()).append("(");
            for (int k = 0; k < c.args().size(); k++) sb.append(k == 0 ? "" : ",").append(write(c.args().get(k)));
            return sb.append(")").toString();
        }
        return "";
    }
    private static int prec(String op) { return switch (op) { case "*", "/" -> 3; case "+", "-", "&" -> 2; default -> 1; }; }
    /** Brackets only where dropping them would change the meaning: a weaker operator under a stronger one. */
    private static String side(Expr e, int parent, boolean right) {
        String s = write(e);
        boolean needs = e instanceof Bin b && (prec(b.op()) < parent || (right && prec(b.op()) == parent));
        return needs ? "(" + s + ")" : s;
    }
}

// ---- ext: insert and delete a row -- the one edit that is not a cell edit: it moves cells AND rewrites formulas
/**
 * One structural edit: insert a blank row at `at`, or delete the row at `at`. It knows two things -- where a
 * cell ends up, and what a formula says afterwards -- and both are needed, because inserting a row above a
 * total and not rewriting the total's formula is how a spreadsheet quietly starts printing the wrong number.
 * Rows are 0-based here, the way CellRef counts them.
 */
record RowOp(int at, int delta) {
    /** Insert a blank row, pushing that row and everything below it down. */
    static RowOp insert(int row0) { return new RowOp(row0, +1); }
    /** Delete a row, pulling everything below it up. */
    static RowOp delete(int row0) { return new RowOp(row0, -1); }

    /** Where this cell ends up, or null if this operation deleted it. */
    CellRef move(CellRef c) {
        if (delta > 0) return c.row() >= at ? new CellRef(c.row() + 1, c.col()) : c;
        if (c.row() == at) return null;
        return c.row() > at ? new CellRef(c.row() - 1, c.col()) : c;
    }

    /**
     * The same formula, said about the moved grid. A single reference into a deleted row becomes the value
     * #REF!; a range that merely spanned the deleted row shrinks by one, which is what Excel does and what
     * the user expects: =SUM(A1:A10) with row 5 gone is =SUM(A1:A9), not an error.
     * The dollar anchors are deliberately ignored here: $A$5 still moves, because that box really did move.
     */
    Expr rewrite(Expr e) {
        if (e instanceof Ref r) {
            CellRef to = move(r.ref());
            return to == null ? new Lit(new Err("#REF!")) : new Ref(to, r.absRow(), r.absCol());
        }
        if (e instanceof RangeRef rr) {
            CellRef a = rr.from().ref(), b = rr.to().ref();
            int r1 = Math.min(a.row(), b.row()), r2 = Math.max(a.row(), b.row());
            if (delta < 0 && r1 == r2 && r1 == at) return new Lit(new Err("#REF!"));   // the range WAS that row
            return new RangeRef(new Ref(endpoint(a, r1), rr.from().absRow(), rr.from().absCol()),
                                new Ref(endpoint(b, r1), rr.to().absRow(), rr.to().absCol()));
        }
        if (e instanceof Bin b) return new Bin(b.op(), rewrite(b.left()), rewrite(b.right()));
        if (e instanceof Call c) {
            List<Expr> args = new ArrayList<>();
            for (Expr a : c.args()) args.add(rewrite(a));
            return new Call(c.name(), args);
        }
        return e;
    }
    private CellRef endpoint(CellRef c, int firstRow) {
        if (delta > 0) return c.row() >= at ? new CellRef(c.row() + 1, c.col()) : c;
        if (c.row() > at) return new CellRef(c.row() - 1, c.col());
        if (c.row() == at && c.row() != firstRow) return new CellRef(c.row() - 1, c.col());
        return c;                                                            // the top of the range stays put
    }
}

/**
 * The toolbar operations, over the sheet's public API and nothing else. Note what they are: many cells
 * changed at once, so in a product this is ONE method on the sheet holding the write lock for the whole
 * thing. Done from outside, as here, a reader could catch the grid halfway rewritten.
 */
final class GridEditor {
    /** Insert a blank row above the 1-based row number, the way the toolbar button does. */
    static void insertRow(Sheet s, int row1) { apply(s, RowOp.insert(row1 - 1)); }
    /** Delete the 1-based row. Its cells go, and anything that pointed INTO it reads #REF!. */
    static void deleteRow(Sheet s, int row1) { apply(s, RowOp.delete(row1 - 1)); }

    /** Copy one cell to another address, shifting its relative references by the distance it moved. */
    static void copy(Sheet s, String from, String to) {
        String raw = s.raw(from);
        if (!raw.startsWith("=")) { s.set(to, raw); return; }
        CellRef f = CellRef.parse(from), t = CellRef.parse(to);
        s.set(to, Formula.text(Formula.copyShift(Parser.parseInput(raw), t.row() - f.row(), t.col() - f.col())));
    }
    /** Drag the corner handle down n rows: the same copy, n times. */
    static void fillDown(Sheet s, String from, int n) {
        CellRef f = CellRef.parse(from);
        for (int k = 1; k <= n; k++) copy(s, from, new CellRef(f.row() + k, f.col()).a1());
    }

    private static void apply(Sheet s, RowOp op) {
        Map<CellRef, String> before = new LinkedHashMap<>();
        for (CellRef c : s.addresses()) before.put(c, s.raw(c.a1()));
        Map<CellRef, String> after = new LinkedHashMap<>();
        for (Map.Entry<CellRef, String> e : before.entrySet()) {
            CellRef to = op.move(e.getKey());
            if (to == null) continue;                                        // that cell was in the deleted row
            String raw = e.getValue();
            after.put(to, raw.startsWith("=") ? Formula.text(op.rewrite(Parser.parseInput(raw))) : raw);
        }
        for (CellRef c : before.keySet()) s.clear(c.a1());                   // no edges left, so no order to get wrong
        for (Map.Entry<CellRef, String> e : after.entrySet()) s.set(e.getKey().a1(), e.getValue());
    }
}

// ---- ext: a range is one edge, not a thousand -- blocks, so =SUM(A1:A1000) does not put a thousand edges in the graph
/** A rectangle of addresses, the way a formula writes a range. */
record Rect(int r1, int c1, int r2, int c2) {
    /** Is this address inside the rectangle? */
    boolean covers(CellRef c) { return c.row() >= r1 && c.row() <= r2 && c.col() >= c1 && c.col() <= c2; }
}

/**
 * The other way to hold a range's dependency. The graph in Main.java gives =SUM(A1:A1000) one edge per cell,
 * so a hundred such formulas are a hundred thousand edges to build and walk. Here a range is filed once per
 * 64x64 block it overlaps -- sixteen entries instead of a thousand -- and "who reads A500?" is one block
 * lookup plus a containment test on the few ranges filed in that block. An interval tree or an R-tree is the
 * same idea with a sharper lookup; blocks are what real grid engines use, because a block id is one shift.
 */
final class BlockRangeIndex {
    /** The side of one block, in cells. Bigger blocks mean fewer entries and longer scans. */
    static final int BLOCK = 64;
    /** One range, and the formula that reads it. */
    record RangeEdge(Rect area, CellRef formula) { }
    private final Map<Long, List<RangeEdge>> byBlock = new HashMap<>();
    private int entries;

    /** File that this formula reads every cell of that rectangle. */
    void add(CellRef formula, Rect r) {
        for (int br = r.r1() / BLOCK; br <= r.r2() / BLOCK; br++)
            for (int bc = r.c1() / BLOCK; bc <= r.c2() / BLOCK; bc++) {
                byBlock.computeIfAbsent(key(br, bc), k -> new ArrayList<>()).add(new RangeEdge(r, formula));
                entries++;
            }
    }
    /** Which formulas read this cell through a range: one map lookup, then a test per range in that block. */
    Set<CellRef> readersOf(CellRef c) {
        Set<CellRef> out = new LinkedHashSet<>();
        for (RangeEdge e : byBlock.getOrDefault(key(c.row() / BLOCK, c.col() / BLOCK), List.of()))
            if (e.area().covers(c)) out.add(e.formula());
        return out;
    }
    /** How many entries the index holds: the number to compare with one edge per cell. */
    int entries() { return entries; }
    private static long key(int br, int bc) { return ((long) br << 32) ^ (bc & 0xffffffffL); }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) {
        // a new function: one class, one register line, nothing else opened
        FunctionRegistry fns = FunctionRegistry.standard(System::currentTimeMillis)
                .register(new MedianFunction()).register(new IfErrorFunction()).register(new VlookupFunction(2));
        Sheet sheet = new Sheet();
        sheet.configure(fns, System::currentTimeMillis);
        sheet.set("A1", "1"); sheet.set("A2", "9"); sheet.set("A3", "4");
        sheet.set("B1", "=MEDIAN(A1:A3)");
        System.out.println("MEDIAN(1,9,4) = " + sheet.get("B1").display());

        // IFERROR: the function that looks at an error instead of propagating it
        sheet.set("C1", "=A1/0");
        sheet.set("C2", "=IFERROR(C1,0)");
        System.out.println("C1 = " + sheet.get("C1").display() + ", IFERROR(C1,0) = " + sheet.get("C2").display());

        // VLOOKUP over a two-column table
        sheet.set("E1", "pen"); sheet.set("F1", "30"); sheet.set("E2", "book"); sheet.set("F2", "250");
        sheet.set("G1", "=VLOOKUP(\"book\",E1:F2,2)");
        System.out.println("VLOOKUP(book) = " + sheet.get("G1").display());

        // the cycle policy: the sheet always refuses; the product decides what to show
        PolicyEditor refuses = new PolicyEditor(sheet, new RefuseCycle());
        MarkCycle mark = new MarkCycle();
        PolicyEditor marks = new PolicyEditor(sheet, mark);
        System.out.println("marking policy on A1 = =B1: " + marks.type("A1", "=B1") + " marked=" + mark.marked());
        try { refuses.type("A1", "=B1"); }
        catch (CircularReferenceException e) { System.out.println("refusing policy: " + e.getMessage()); }
        System.out.println("either way A1 is still " + sheet.raw("A1") + " = " + sheet.get("A1").display());

        // undo and redo, with no change to the sheet at all
        EditHistory hist = new EditHistory(sheet);
        hist.type("A1", "5"); hist.type("A1", "6");
        System.out.println("after two edits B1 = " + sheet.get("B1").display() + " (median of 6, 9, 4)");
        hist.undo(); hist.undo();
        System.out.println("after two undos A1 = " + sheet.raw("A1") + ", B1 = " + sheet.get("B1").display());
        hist.redo();
        System.out.println("after one redo  A1 = " + sheet.raw("A1") + ", depth = " + hist.depth());

        // lazy: an edit computes nothing, a read computes only what it needs
        LazySheet lazy = new LazySheet(FunctionRegistry.standard(System::currentTimeMillis));
        lazy.set("A1", "1");
        for (int i = 2; i <= 20; i++) lazy.set("A" + i, "=A" + (i - 1) + "+1");
        lazy.set("A1", "100");
        System.out.println("lazy: after editing A1, A5 = " + lazy.get("A5").display()
                + " and only " + lazy.evaluations() + " cells were ever evaluated (eager would have done 20)");

        // a workbook: the same graph code, with the key widened to (sheet, cell)
        Deps<Addr> book = new Deps<>();
        Addr salesA1 = new Addr("Sales", CellRef.parse("A1")), summaryB2 = new Addr("Summary", CellRef.parse("B2"));
        book.setPrecedents(summaryB2, Set.of(salesA1));
        System.out.println("workbook: editing " + salesA1 + " affects " + book.affectedBy(salesA1)
                + "; " + salesA1 + " = " + summaryB2 + " would cycle = " + book.wouldCycle(salesA1, Set.of(summaryB2)));

        // persistence: two servers read the same version; exactly one write wins
        CellRepository repo = new InMemoryCellRepository();
        repo.save("s1", "A1", "10", 0);
        int seen = repo.version("s1", "A1");
        boolean first = repo.save("s1", "A1", "20", seen);
        boolean second = repo.save("s1", "A1", "30", seen);
        System.out.println("repository: first writer " + first + ", second writer " + second
                + ", stored = " + repo.load("s1", "A1") + " v" + repo.version("s1", "A1"));

        // lock-free readers
        Sheet live = Sheet.standard();
        SnapshotView snap = new SnapshotView(live);
        live.set("A1", "3"); live.set("A2", "=A1*7");
        System.out.println("snapshot (no lock taken): A2 = " + snap.get("A2").display() + ", " + snap.size() + " cells published");

        // volatile functions: nothing changed, but NOW() must change
        long[] now = { 1_700_000_000_000L };
        Sheet timed = Sheet.standard(() -> now[0]);
        timed.set("A1", "=NOW()");
        timed.set("A2", "=A1+0");
        VolatileCells vol = new VolatileCells();
        vol.watch("A1");
        String before = timed.get("A2").display();
        now[0] += 60_000;
        vol.tick(timed);
        System.out.println("volatile: A2 was " + before + ", after a tick a minute later it is " + timed.get("A2").display());

        // copy a formula: the relative half moves, the $-anchored half does not
        Sheet grid = Sheet.standard();
        grid.set("A1", "2"); grid.set("B1", "3"); grid.set("A2", "20"); grid.set("B2", "30");
        grid.set("C1", "=A1+B1");
        GridEditor.copy(grid, "C1", "C2");
        System.out.println("copy C1 down: " + grid.raw("C2") + " = " + grid.get("C2").display());
        grid.set("D1", "=$A$1+B1");
        GridEditor.copy(grid, "D1", "D2");
        System.out.println("copy an anchored one: " + grid.raw("D2") + " = " + grid.get("D2").display());

        // insert a row: every formula below it is rewritten, so the totals still mean the same thing
        Sheet ledger = Sheet.standard();
        ledger.set("A1", "10"); ledger.set("A2", "20"); ledger.set("A3", "30"); ledger.set("B1", "=SUM(A1:A3)");
        GridEditor.insertRow(ledger, 2);
        System.out.println("after inserting a row at 2: B1 is " + ledger.raw("B1") + " = " + ledger.get("B1").display()
                + ", and A2 is now " + (ledger.raw("A2").isEmpty() ? "blank" : ledger.raw("A2")));
        GridEditor.deleteRow(ledger, 2);
        System.out.println("after deleting it again:    B1 is " + ledger.raw("B1") + " = " + ledger.get("B1").display());
        ledger.set("C1", "=A2*10");
        GridEditor.deleteRow(ledger, 2);
        System.out.println("deleting the row C1 pointed INTO: " + ledger.raw("C1") + " = " + ledger.get("C1").display());

        // a range as blocks instead of one edge per cell
        Sheet wide = Sheet.standard();
        wide.set("B1", "=SUM(A1:A1000)");
        BlockRangeIndex idx = new BlockRangeIndex();
        idx.add(CellRef.parse("B1"), new Rect(0, 0, 999, 0));
        System.out.println("a 1000-cell range: " + wide.edgeCount() + " edges in the plain graph, "
                + idx.entries() + " entries as blocks; readers of A500 = " + idx.readersOf(CellRef.parse("A500")));
    }
}
