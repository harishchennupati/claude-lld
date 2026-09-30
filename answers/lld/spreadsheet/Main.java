import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

/** Where time comes from. Injected, so NOW() and the edit stamps are whatever a test says they are. */
interface Clock { long nowMs(); }

/**
 * One cell's address. "A1" to a human, (row 0, col 0) to the code. A record, so two addresses for the same
 * box are equal and hash the same, which is what lets the whole dependency graph be keyed by address.
 */
record CellRef(int row, int col) implements Comparable<CellRef> {
    /** Parse "A1", "bc12". Throws IllegalArgumentException on anything else, so a typo never becomes an address. */
    static CellRef parse(String s) {
        String t = s.trim();
        int i = 0, c = 0;
        while (i < t.length() && Character.isLetter(t.charAt(i))) { c = c * 26 + (Character.toUpperCase(t.charAt(i)) - 'A' + 1); i++; }
        if (i == 0 || i == t.length()) throw new IllegalArgumentException("bad cell reference: " + s);
        int r;
        try { r = Integer.parseInt(t.substring(i)); } catch (NumberFormatException e) { throw new IllegalArgumentException("bad row: " + s); }
        if (r <= 0) throw new IllegalArgumentException("bad row: " + s);
        return new CellRef(r - 1, c - 1);
    }
    /** Back to "A1" for printing, the formula bar, and error messages. */
    String a1() {
        StringBuilder sb = new StringBuilder();
        int c = col + 1;
        while (c > 0) { sb.append((char) ('A' + (c - 1) % 26)); c = (c - 1) / 26; }
        return sb.reverse().append(row + 1).toString();
    }
    @Override public int compareTo(CellRef o) { return row != o.row ? Integer.compare(row, o.row) : Integer.compare(col, o.col); }
    @Override public String toString() { return a1(); }
}

// "a cell can hold #DIV/0!" -> an error is a VALUE, not an exception -> one bad cell cannot abort a recalc pass
/**
 * What a cell holds. Sealed, so the four possibilities are a closed set the compiler can check: a number,
 * text, an error code, or blank. An error being a value is the decision the whole design rests on.
 */
sealed interface Value permits Num, Text, Err, Blank {
    /** What the grid would paint in the box. */
    String display();
}
/** A number. Every arithmetic result is one of these; booleans are 1 and 0. */
record Num(double v) implements Value {
    public String display() { return v == Math.rint(v) && !Double.isInfinite(v) ? String.valueOf((long) v) : String.valueOf(v); }
}
/** Text. Also what a formula returns when the join operator glues two things together. */
record Text(String s) implements Value { public String display() { return s; } }
/** An error, carrying the code the user sees: #DIV/0!, #VALUE!, #NAME?, #REF!, #PARSE!. It caches and propagates like any other value. */
record Err(String code) implements Value { public String display() { return code; } }
/** An empty box. A cell nobody has typed into is not in the map at all; reading it gives this. */
enum Blank implements Value { IT; public String display() { return ""; } }

// "=SUM(A1:A3)*2 must be obeyed again whenever A1 moves" -> parse once, keep the tree -> Composite
/**
 * A parsed formula: a tree of nodes, each of which can hold nodes. Sealed, so the evaluator's five cases are
 * the whole grammar. The tree knows which cells it reads, which is where the dependency edges come from.
 */
sealed interface Expr permits Lit, Ref, RangeRef, Bin, Call {
    /** Add every cell this node (and everything under it) reads into out. This IS the precedent set. */
    void collectRefs(Set<CellRef> out);
}
/** A constant: a typed number, a quoted string, or a stored error. Reads nothing. */
record Lit(Value value) implements Expr { public void collectRefs(Set<CellRef> out) { } }
/**
 * One cell reference, "A1". Reads exactly one cell. The two flags are the dollar signs in $A$1: an anchored
 * part does not move when the formula is COPIED to another box. They change nothing else -- an anchored
 * reference still moves when a row is inserted above it, because the box it points at really did move.
 */
record Ref(CellRef ref, boolean absRow, boolean absCol) implements Expr {
    /** A plain, unanchored reference: what "A1" means. */
    Ref(CellRef ref) { this(ref, false, false); }
    public void collectRefs(Set<CellRef> out) { out.add(ref); }
}
/** A rectangle, "A1:B3" or "$A$1:$A$10". Expanded to its cells here, which is why functions never learn that ranges exist. */
record RangeRef(Ref from, Ref to) implements Expr {
    /** The cap that stops =SUM(A1:A100000) materialising a hundred thousand addresses on a keystroke. */
    static final int MAX_CELLS = 20_000;
    /** Every address in the rectangle, row by row. Throws if the rectangle is bigger than the cap. */
    List<CellRef> cells() {
        int r1 = Math.min(from.ref().row(), to.ref().row()), r2 = Math.max(from.ref().row(), to.ref().row());
        int c1 = Math.min(from.ref().col(), to.ref().col()), c2 = Math.max(from.ref().col(), to.ref().col());
        long n = (long) (r2 - r1 + 1) * (c2 - c1 + 1);
        if (n > MAX_CELLS) throw new IllegalArgumentException("range too large: " + n + " cells");
        List<CellRef> out = new ArrayList<>();
        for (int r = r1; r <= r2; r++) for (int c = c1; c <= c2; c++) out.add(new CellRef(r, c));
        return out;
    }
    public void collectRefs(Set<CellRef> out) { out.addAll(cells()); }
}
/** A binary operator: plus, minus, times, divide, join, and the comparisons. Reads whatever its two sides read. */
record Bin(String op, Expr left, Expr right) implements Expr {
    public void collectRefs(Set<CellRef> out) { left.collectRefs(out); right.collectRefs(out); }
}
/** A function call, "SUM(A1:A3, 2)". Holds its argument nodes, so it is a node holding nodes: Composite. */
record Call(String name, List<Expr> args) implements Expr {
    public void collectRefs(Set<CellRef> out) { for (Expr a : args) a.collectRefs(out); }
}

/**
 * The only class in the file that touches characters. Recursive descent: precedence is just the order the
 * methods call each other. A syntax error throws here and the sheet turns it into a #PARSE! value.
 */
final class Parser {
    private final String src;
    private int i;
    private Parser(String src) { this.src = src; }

    /** What the user typed, as a tree. No leading "=" means a literal: a number if it parses, otherwise text. */
    static Expr parseInput(String raw) {
        if (raw == null || raw.isBlank()) return new Lit(Blank.IT);
        if (raw.startsWith("=")) {
            Parser p = new Parser(raw.substring(1));
            Expr e = p.expr();
            p.ws();
            if (p.i < p.src.length()) throw new IllegalArgumentException("trailing input at " + p.i);
            return e;
        }
        try { return new Lit(new Num(Double.parseDouble(raw.trim()))); }
        catch (NumberFormatException nfe) { return new Lit(new Text(raw)); }
    }

    private static final String[] CMP = { "<=", ">=", "<>", "<", ">", "=" };

    /** Lowest precedence: one optional comparison over an additive expression. */
    private Expr expr() {
        Expr l = additive();
        ws();
        for (String op : CMP) if (src.startsWith(op, i)) { i += op.length(); return new Bin(op, l, additive()); }
        return l;
    }
    private Expr additive() {
        Expr l = multiplicative();
        while (true) {
            ws();
            char c = at(i);
            if (c == '+' || c == '-' || c == '&') { i++; l = new Bin(String.valueOf(c), l, multiplicative()); } else return l;
        }
    }
    private Expr multiplicative() {
        Expr l = unary();
        while (true) {
            ws();
            char c = at(i);
            if (c == '*' || c == '/') { i++; l = new Bin(String.valueOf(c), l, unary()); } else return l;
        }
    }
    private Expr unary() {
        ws();
        if (at(i) == '-') { i++; return new Bin("-", new Lit(new Num(0)), unary()); }
        if (at(i) == '+') { i++; return unary(); }
        return primary();
    }
    private Expr primary() {
        ws();
        char c = at(i);
        if (c == '(') { i++; Expr e = expr(); ws(); expect(')'); return e; }
        if (c == '"') {
            i++;
            StringBuilder sb = new StringBuilder();
            while (i < src.length() && src.charAt(i) != '"') sb.append(src.charAt(i++));
            expect('"');
            return new Lit(new Text(sb.toString()));
        }
        if (Character.isDigit(c) || c == '.') return new Lit(new Num(number()));
        if (c == '#') {                                            // an error typed as a literal: #REF!, #DIV/0!
            int s = i++;
            while (i < src.length() && (Character.isLetterOrDigit(src.charAt(i)) || src.charAt(i) == '/' || src.charAt(i) == '?')) i++;
            if (at(i) == '!') i++;
            return new Lit(new Err(src.substring(s, i)));          // an error is a value, so it is also a literal
        }
        if (c == '$') return range(address());                     // an anchored address can only be an address
        if (Character.isLetter(c)) {
            int save = i, s = i;
            while (i < src.length() && (Character.isLetterOrDigit(src.charAt(i)) || src.charAt(i) == '_')) i++;
            String word = src.substring(s, i);
            ws();
            if (at(i) == '(') {                                    // a function call
                i++;
                List<Expr> args = new ArrayList<>();
                ws();
                if (at(i) != ')') { args.add(expr()); ws(); while (at(i) == ',') { i++; args.add(expr()); ws(); } }
                expect(')');
                return new Call(word.toUpperCase(), args);
            }
            i = save;                                              // not a call, so read it again as an address
            return range(address());
        }
        throw new IllegalArgumentException("unexpected '" + c + "' at " + i);
    }
    /** One address, with the optional dollar anchors: A1, $A1, A$1, $A$1. */
    private Ref address() {
        boolean absCol = false, absRow = false;
        if (at(i) == '$') { absCol = true; i++; }
        int s = i;
        while (i < src.length() && Character.isLetter(src.charAt(i))) i++;
        String col = src.substring(s, i);
        if (at(i) == '$') { absRow = true; i++; }
        int s2 = i;
        while (i < src.length() && Character.isDigit(src.charAt(i))) i++;
        return new Ref(CellRef.parse(col + src.substring(s2, i)), absRow, absCol);
    }
    /** An address, or the rectangle it starts if a colon follows. */
    private Expr range(Ref first) {
        if (at(i) != ':') return first;
        i++;
        return new RangeRef(first, address());
    }
    private double number() {
        int s = i;
        while (i < src.length() && (Character.isDigit(src.charAt(i)) || src.charAt(i) == '.')) i++;
        return Double.parseDouble(src.substring(s, i));
    }
    private void ws() { while (i < src.length() && Character.isWhitespace(src.charAt(i))) i++; }
    private char at(int k) { return k < src.length() ? src.charAt(k) : '\0'; }
    private void expect(char c) { if (at(i) != c) throw new IllegalArgumentException("expected '" + c + "' at " + i); i++; }
}

// "now add MEDIAN" is the follow-up everyone gets -> one object per function in a registry -> Strategy
/**
 * One spreadsheet function. Two methods: what it is called, and what it does to already-evaluated arguments.
 * The contract is that it returns a Value and never throws; a bad argument comes back as an Err.
 */
interface SheetFunction {
    /** The name as it appears in a formula, upper case. */
    String name();
    /** Apply to the evaluated arguments. Ranges have already been flattened into individual values. */
    Value apply(List<Value> args);
}

/**
 * The plumbing most functions share: an error argument poisons the result, blanks are skipped, numeric text
 * is coerced, and text that is not a number is skipped like a blank -- so a header row does not break the
 * column total under it. A function that needs to SEE errors or blanks (IF, COUNT) declines this base class.
 */
abstract class NumericFunction implements SheetFunction {
    public Value apply(List<Value> args) {
        List<Double> nums = new ArrayList<>();
        for (Value v : args) {
            if (v instanceof Err e) return e;                      // one bad argument, one error out: propagation
            if (v instanceof Blank) continue;
            if (v instanceof Num n) { nums.add(n.v()); continue; }
            if (v instanceof Text t) {
                try { nums.add(Double.parseDouble(t.s().trim())); }
                catch (NumberFormatException nfe) { /* a label in the range, not a number: skip it */ }
            }
        }
        if (nums.isEmpty() && needsAtLeastOne()) return new Err("#VALUE!");
        return reduce(nums);
    }
    /** Whether an empty argument list is an error. SUM says no (an empty sum is 0); AVERAGE says yes. */
    protected boolean needsAtLeastOne() { return true; }
    /** The actual arithmetic, once the arguments are clean numbers. */
    protected abstract Value reduce(List<Double> nums);
}

/** SUM: adds the numbers, treats blanks as nothing, returns 0 over an empty range. */
final class SumFunction extends NumericFunction {
    public String name() { return "SUM"; }
    @Override protected boolean needsAtLeastOne() { return false; }
    protected Value reduce(List<Double> n) { double s = 0; for (double d : n) s += d; return new Num(s); }
}
/** AVERAGE: the mean of the numeric arguments. #VALUE! over nothing, because there is no mean of nothing. */
final class AverageFunction extends NumericFunction {
    public String name() { return "AVERAGE"; }
    protected Value reduce(List<Double> n) { double s = 0; for (double d : n) s += d; return new Num(s / n.size()); }
}
/** MIN of the numeric arguments. */
final class MinFunction extends NumericFunction {
    public String name() { return "MIN"; }
    protected Value reduce(List<Double> n) { double m = n.get(0); for (double d : n) m = Math.min(m, d); return new Num(m); }
}
/** MAX of the numeric arguments. */
final class MaxFunction extends NumericFunction {
    public String name() { return "MAX"; }
    protected Value reduce(List<Double> n) { double m = n.get(0); for (double d : n) m = Math.max(m, d); return new Num(m); }
}
/** COUNT declines the numeric base class on purpose: it must see blanks and errors to not count them. */
final class CountFunction implements SheetFunction {
    public String name() { return "COUNT"; }
    public Value apply(List<Value> args) {
        long n = 0;
        for (Value v : args) if (v instanceof Num) n++;
        return new Num(n);
    }
}
/** IF also declines the base class: it must see an error argument to choose a branch rather than propagate it. */
final class IfFunction implements SheetFunction {
    public String name() { return "IF"; }
    public Value apply(List<Value> args) {
        if (args.size() != 3) return new Err("#VALUE!");
        Value c = args.get(0);
        if (c instanceof Err e) return e;
        Double d = Evaluator.num(c);
        if (d == null) return new Err("#VALUE!");
        return d != 0 ? args.get(1) : args.get(2);
    }
}
/** NOW(): the one function whose answer changes without any cell changing. It reads the injected clock, never the wall clock. */
final class NowFunction implements SheetFunction {
    private final Clock clock;
    NowFunction(Clock clock) { this.clock = clock; }
    public String name() { return "NOW"; }
    public Value apply(List<Value> args) { return new Num(clock.nowMs()); }
}

/**
 * Name to function. The one place a new function is added, which is why "add MEDIAN" is a new class plus one
 * line here and no engine file is opened.
 */
final class FunctionRegistry {
    private final Map<String, SheetFunction> byName = new HashMap<>();
    /** Add or replace a function. Returns this, so a registry can be built in one expression. */
    FunctionRegistry register(SheetFunction f) { byName.put(f.name().toUpperCase(), f); return this; }
    /** The function with this name, or null, which the evaluator turns into #NAME?. */
    SheetFunction lookup(String name) { return byName.get(name.toUpperCase()); }
    /** Every registered name, sorted. For a help panel, and for the demo. */
    Set<String> names() { return new TreeSet<>(byName.keySet()); }
    /** The seven built-ins. NOW needs the clock, which is why the registry is built with one. */
    static FunctionRegistry standard(Clock clock) {
        return new FunctionRegistry().register(new SumFunction()).register(new AverageFunction())
                .register(new MinFunction()).register(new MaxFunction()).register(new CountFunction())
                .register(new IfFunction()).register(new NowFunction(clock));
    }
}

/**
 * Where a value comes from when the evaluator meets a reference. One method, so the evaluator never sees the
 * sheet's map, its graph or its lock, and a test can hand it a lambda over a HashMap.
 */
@FunctionalInterface
interface ValueSource {
    /** The current value of that address. Blank if nobody typed there. */
    Value valueOf(CellRef ref);
}

// "walk the tree and produce a value" -> one method per node kind -> Interpreter
/**
 * Turns a tree into a value. Holds a registry and nothing else; everything it reads arrives through the
 * ValueSource it is handed, which is what makes it unit-testable without a sheet.
 */
final class Evaluator {
    private final FunctionRegistry functions;
    Evaluator(FunctionRegistry functions) { this.functions = functions; }

    /** Evaluate one node. Never throws: every failure becomes an Err value. */
    Value eval(Expr e, ValueSource src) {
        if (e instanceof Lit l) return l.value();
        if (e instanceof Ref r) return src.valueOf(r.ref());
        if (e instanceof RangeRef rr) {                            // a range on its own is not a value
            List<CellRef> cs = rr.cells();
            return cs.size() == 1 ? src.valueOf(cs.get(0)) : new Err("#VALUE!");
        }
        if (e instanceof Bin b) return binary(b, src);
        if (e instanceof Call c) {
            SheetFunction f = functions.lookup(c.name());
            if (f == null) return new Err("#NAME?");
            List<Value> args = new ArrayList<>();
            for (Expr a : c.args()) {
                if (a instanceof RangeRef rr) for (CellRef cr : rr.cells()) args.add(src.valueOf(cr));
                else args.add(eval(a, src));
            }
            try { return f.apply(args); }
            catch (RuntimeException ex) { return new Err("#VALUE!"); }   // a function written next year cannot take the sheet down
        }
        return new Err("#VALUE!");
    }

    private Value binary(Bin b, ValueSource src) {
        Value l = eval(b.left(), src), r = eval(b.right(), src);
        if (l instanceof Err e) return e;
        if (r instanceof Err e) return e;
        String op = b.op();
        if (op.equals("&")) return new Text(l.display() + r.display());
        if (op.equals("=")) return bool(same(l, r));
        if (op.equals("<>")) return bool(!same(l, r));
        Double x = num(l), y = num(r);
        if (x == null || y == null) return new Err("#VALUE!");
        return switch (op) {
            case "+" -> new Num(x + y);
            case "-" -> new Num(x - y);
            case "*" -> new Num(x * y);
            case "/" -> y == 0 ? new Err("#DIV/0!") : new Num(x / y);
            case "<" -> bool(x < y);
            case ">" -> bool(x > y);
            case "<=" -> bool(x <= y);
            case ">=" -> bool(x >= y);
            default -> new Err("#VALUE!");
        };
    }
    private static boolean same(Value a, Value b) {
        Double x = num(a), y = num(b);
        return x != null && y != null ? x.doubleValue() == y.doubleValue() : a.display().equals(b.display());
    }
    /** A value as a number, or null if it is not one. Blank is 0; numeric text is coerced; an error is not a number. */
    static Double num(Value v) {
        if (v instanceof Num n) return n.v();
        if (v instanceof Blank) return 0.0;
        if (v instanceof Text t) { try { return Double.parseDouble(t.s().trim()); } catch (NumberFormatException e) { return null; } }
        return null;
    }
    private static Value bool(boolean b) { return new Num(b ? 1 : 0); }
}

/**
 * One box. Three fields: what the user typed (the formula bar, and what an undo replays), the parsed tree,
 * and the cached value. The cache is why a read is one hash lookup and never evaluates anything.
 */
final class Cell {
    private final CellRef ref;
    private String raw = "";
    private Expr expr = new Lit(Blank.IT);
    private Value value = Blank.IT;
    Cell(CellRef ref) { this.ref = ref; }
    /** The address of this cell. */
    CellRef ref() { return ref; }
    /** What the user typed, verbatim. */
    String raw() { return raw; }
    /** The parsed tree of what the user typed. */
    Expr expr() { return expr; }
    /** The last computed value. Reads return this; nothing evaluates on a read. */
    Value value() { return value; }
    /** Store new text and its tree together, so the two can never disagree. */
    void bind(String raw, Expr expr) { this.raw = raw; this.expr = expr; }
    /** Store a freshly computed value. Only the sheet's recalculation pass calls this. */
    void setValue(Value v) { this.value = v; }
}

/**
 * Who reads whom, in both directions. Precedents (what this cell reads) answer "would this edit make a
 * loop?"; dependents (who reads this cell) answer "who has to be recomputed?". It stores addresses only,
 * never Cell objects, so an edge to a cell nobody has typed into yet is perfectly legal.
 */
final class DependencyGraph {
    private final Map<CellRef, Set<CellRef>> precedents = new HashMap<>();
    private final Map<CellRef, Set<CellRef>> dependents = new HashMap<>();

    /** What this cell reads. */
    Set<CellRef> precedentsOf(CellRef c) { return precedents.getOrDefault(c, Set.of()); }
    /** Who reads this cell. */
    Set<CellRef> dependentsOf(CellRef c) { return dependents.getOrDefault(c, Set.of()); }

    /**
     * Everything that would have to be recomputed if this cell changed: itself, then forward over dependents.
     * One walk, two jobs -- it is also the set a new precedent must not be in, or the edit makes a loop.
     */
    Set<CellRef> affectedBy(CellRef from) {
        Set<CellRef> seen = new LinkedHashSet<>();
        Deque<CellRef> q = new ArrayDeque<>();
        seen.add(from); q.add(from);
        while (!q.isEmpty()) { CellRef c = q.poll(); for (CellRef d : dependentsOf(c)) if (seen.add(d)) q.add(d); }
        return seen;
    }

    /**
     * Point this cell at a new set of precedents. Old edges are removed first: the classic leak is a stale
     * edge, where a cell keeps being recomputed by a cell it no longer reads.
     */
    void setPrecedents(CellRef cell, Set<CellRef> refs) {
        for (CellRef old : precedentsOf(cell)) {
            Set<CellRef> d = dependents.get(old);
            if (d != null) { d.remove(cell); if (d.isEmpty()) dependents.remove(old); }
        }
        if (refs.isEmpty()) precedents.remove(cell); else precedents.put(cell, new LinkedHashSet<>(refs));
        for (CellRef p : refs) dependents.computeIfAbsent(p, k -> new LinkedHashSet<>()).add(cell);
    }

    /**
     * Kahn's algorithm restricted to the dirty set: each cell comes out exactly once, after every precedent
     * of it that is also dirty. That is a correctness property, not a speed-up -- out of order, a cell reads
     * a stale input. Throws if the set is not acyclic, which the cycle check has already made impossible.
     */
    List<CellRef> topoOrder(Set<CellRef> dirty) {
        Map<CellRef, Integer> indeg = new HashMap<>();
        for (CellRef c : dirty) { int n = 0; for (CellRef p : precedentsOf(c)) if (dirty.contains(p)) n++; indeg.put(c, n); }
        Deque<CellRef> q = new ArrayDeque<>();
        for (CellRef c : dirty) if (indeg.get(c) == 0) q.add(c);
        List<CellRef> out = new ArrayList<>(dirty.size());
        while (!q.isEmpty()) {
            CellRef c = q.poll();
            out.add(c);
            for (CellRef d : dependentsOf(c)) if (dirty.contains(d) && indeg.merge(d, -1, Integer::sum) == 0) q.add(d);
        }
        if (out.size() != dirty.size()) throw new IllegalStateException("the graph is not a DAG");
        return out;
    }

    /** The chain of reads from `from` to `to` over dependents, for a readable cycle message. */
    List<CellRef> path(CellRef from, CellRef to) {
        Map<CellRef, CellRef> parent = new HashMap<>();
        Deque<CellRef> q = new ArrayDeque<>();
        q.add(from); parent.put(from, null);
        while (!q.isEmpty()) {
            CellRef c = q.poll();
            if (c.equals(to)) break;
            for (CellRef d : dependentsOf(c)) if (!parent.containsKey(d)) { parent.put(d, c); q.add(d); }
        }
        LinkedList<CellRef> out = new LinkedList<>();
        for (CellRef c = to; c != null; c = parent.get(c)) out.addFirst(c);
        return out;
    }

    /** How many edges the graph holds. A test uses it to prove a rejected edit left no trace. */
    int edgeCount() { int n = 0; for (Set<CellRef> s : precedents.values()) n += s.size(); return n; }
}

/** Thrown when an edit would make a cell depend on itself. Carries the loop, so the message names the cells. */
final class CircularReferenceException extends RuntimeException {
    private final List<CellRef> path;
    CircularReferenceException(List<CellRef> path) { super("circular reference: " + join(path)); this.path = List.copyOf(path); }
    /** The cells in the loop, in reading order. */
    List<CellRef> path() { return path; }
    private static String join(List<CellRef> p) {
        StringBuilder sb = new StringBuilder();
        for (CellRef c : p) { if (sb.length() > 0) sb.append(" -> "); sb.append(c); }
        return sb.toString();
    }
}

/** One cell moved: where, from what, to what. What a listener is told, after the lock is released. */
record CellChange(CellRef ref, Value before, Value after) { }

// "the screen must repaint when a total changes" -> announce, without knowing what a screen is -> Observer
/** Anybody who wants to know that a value moved: a repaint, an autosave, a chart. One method, so a lambda works. */
@FunctionalInterface
interface ChangeListener {
    /** Called once per changed cell, after the edit has been committed and the lock released. */
    void onChange(CellChange change);
}

/**
 * The sheet: the one object that owns the cells, the graph and the lock. Every edit is a transaction --
 * parse, cycle-check, commit the edges, recompute the affected subgraph -- and nothing is written until
 * every check has passed, so a rejected edit leaves the sheet exactly as it was.
 */
final class Sheet {
    private final Map<CellRef, Cell> cells = new HashMap<>();
    private final Set<CellRef> removed = new HashSet<>();          // addresses deleted out of the grid: reads give #REF!
    private final DependencyGraph graph = new DependencyGraph();
    private final List<ChangeListener> listeners = new CopyOnWriteArrayList<>();
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private Evaluator evaluator;
    private Clock clock;
    private long edits, lastEditMs;

    /** A bare sheet with no functions. Use standard(), or configure() with your own registry. */
    Sheet() { configure(new FunctionRegistry(), System::currentTimeMillis); }
    /** A sheet with the seven built-in functions and the wall clock. */
    static Sheet standard() { return standard(System::currentTimeMillis); }
    /** A sheet with the built-ins and the clock you hand in, which is how a test pins NOW(). */
    static Sheet standard(Clock clock) {
        Sheet s = new Sheet();
        s.configure(FunctionRegistry.standard(clock), clock);
        return s;
    }
    /** Hand in the rules: which functions exist, and where time comes from. The sheet never builds either. */
    void configure(FunctionRegistry functions, Clock clock) {
        this.evaluator = new Evaluator(functions);
        this.clock = clock;
    }
    /** Add a listener. Copy-on-write, so a repaint can subscribe while an edit is running. */
    void addListener(ChangeListener l) { listeners.add(l); }

    // ---------------- reads: one hash lookup, never an evaluation ----------------
    /** The value in that box. O(1): the cached value, computed when something it reads last changed. */
    Value get(String a1) { return get(CellRef.parse(a1)); }
    /** The value at that address. */
    Value get(CellRef ref) { lock.readLock().lock(); try { return read(ref); } finally { lock.readLock().unlock(); } }
    /** What the user typed there: the formula bar, not the value. */
    String raw(String a1) {
        lock.readLock().lock();
        try { Cell c = cells.get(CellRef.parse(a1)); return c == null ? "" : c.raw(); }
        finally { lock.readLock().unlock(); }
    }
    /** How many boxes have ever been typed into. The grid is sparse: blanks cost nothing. */
    int cellCount() { lock.readLock().lock(); try { return cells.size(); } finally { lock.readLock().unlock(); } }
    /**
     * Every address that has been typed into, in reading order. What a save, a repaint of the whole grid, or
     * a structural edit (insert a row) walks; the grid is sparse, so this is the typed cells, not the plane.
     */
    List<CellRef> addresses() {
        lock.readLock().lock();
        try { List<CellRef> out = new ArrayList<>(cells.keySet()); Collections.sort(out); return out; }
        finally { lock.readLock().unlock(); }
    }
    /** How many read-edges the graph holds. Used by a test to prove a refused edit changed nothing. */
    int edgeCount() { lock.readLock().lock(); try { return graph.edgeCount(); } finally { lock.readLock().unlock(); } }
    /** When the last committed edit happened, by the injected clock. */
    long lastEditMs() { lock.readLock().lock(); try { return lastEditMs; } finally { lock.readLock().unlock(); } }
    /** How many edits have been committed. */
    long edits() { lock.readLock().lock(); try { return edits; } finally { lock.readLock().unlock(); } }

    // ---------------- the one write path ----------------
    /**
     * Type text into a cell. Returns the cells that were recomputed, in the order they were recomputed, which
     * is the proof that only the affected subgraph ran and that it ran in dependency order.
     * Throws CircularReferenceException if the edit would make a loop, having written nothing.
     */
    List<String> set(String a1, String text) {
        CellRef ref = CellRef.parse(a1);
        Prepared p = prepare(text);                                 // 1. parse OUTSIDE the lock: it can throw
        List<CellChange> changes = new ArrayList<>();
        List<String> order;
        lock.writeLock().lock();
        try { order = commit(ref, p, changes); }
        finally { lock.writeLock().unlock(); }
        publish(changes);                                           // 5. the listeners hear AFTER the unlock
        return order;
    }

    /**
     * Read a number out of a cell, change it, and write it back -- as ONE step under ONE lock. get() then
     * set() is two steps, and two typists in that gap lose an increment. This is the whole concurrency fix.
     */
    List<String> update(String a1, DoubleUnaryOperator f) {
        CellRef ref = CellRef.parse(a1);
        List<CellChange> changes = new ArrayList<>();
        List<String> order;
        lock.writeLock().lock();
        try {
            Double cur = Evaluator.num(read(ref));
            if (cur == null) throw new IllegalStateException(a1 + " is not a number: " + read(ref).display());
            order = commit(ref, prepare(new Num(f.applyAsDouble(cur)).display()), changes);
        } finally { lock.writeLock().unlock(); }
        publish(changes);
        return order;
    }

    /** Empty the box: it becomes blank, and everything that reads it recomputes with a blank. */
    List<String> clear(String a1) { return set(a1, ""); }

    /**
     * Take the address out of the grid altogether, as deleting a column does. Anything still pointing at it
     * reads #REF!, until somebody types into that address again, which heals every dependent.
     */
    List<String> deleteCell(String a1) {
        CellRef ref = CellRef.parse(a1);
        List<CellChange> changes = new ArrayList<>();
        List<String> order = new ArrayList<>();
        lock.writeLock().lock();
        try {
            Set<CellRef> affected = graph.affectedBy(ref);
            graph.setPrecedents(ref, Set.of());
            cells.remove(ref);
            removed.add(ref);
            edits++; lastEditMs = clock.nowMs();
            recompute(graph.topoOrder(affected), order, changes);
        } finally { lock.writeLock().unlock(); }
        publish(changes);
        return order;
    }

    // ---------------- the transaction, step by step ----------------
    /** Text, its tree, and the cells that tree reads. Computed before the lock is taken: this part can throw. */
    private record Prepared(String text, Expr expr, Set<CellRef> refs) { }

    private Prepared prepare(String text) {
        Expr parsed;
        try { parsed = Parser.parseInput(text); }
        catch (RuntimeException syntax) { parsed = new Lit(new Err("#PARSE!")); }   // a typo is a value, not a crash
        Set<CellRef> refs = new LinkedHashSet<>();
        parsed.collectRefs(refs);                                   // a range over the cap throws here: the sheet is untouched
        return new Prepared(text, parsed, refs);
    }

    /** Steps 2 to 4, with the write lock held. Returns the recalculation order; fills `changes` for the listeners. */
    private List<String> commit(CellRef ref, Prepared p, List<CellChange> changes) {
        Set<CellRef> affected = graph.affectedBy(ref);              // 2. one walk: the dirty set AND the cycle test
        for (CellRef pre : p.refs())
            if (affected.contains(pre))                             //    a new precedent that already reads me is a loop
                throw new CircularReferenceException(closed(graph.path(ref, pre), ref));
        graph.setPrecedents(ref, p.refs());                         // 3. only now commit: edges, then text and tree
        removed.remove(ref);
        cells.computeIfAbsent(ref, Cell::new).bind(p.text(), p.expr());
        edits++; lastEditMs = clock.nowMs();
        List<String> order = new ArrayList<>(affected.size());
        recompute(graph.topoOrder(affected), order, changes);       // 4. each affected cell once, after its inputs
        return order;
    }

    private void recompute(List<CellRef> order, List<String> names, List<CellChange> changes) {
        for (CellRef c : order) {
            Cell cell = cells.get(c);
            if (cell == null) continue;                             // an address somebody points at but nobody typed into
            names.add(c.a1());
            Value before = cell.value();
            Value after = evaluator.eval(cell.expr(), this::read);
            if (!after.equals(before)) { cell.setValue(after); changes.add(new CellChange(c, before, after)); }
        }
    }

    /** The value at an address, with the lock already held. Deleted addresses are #REF!, untyped ones are blank. */
    private Value read(CellRef ref) {
        if (removed.contains(ref)) return new Err("#REF!");
        Cell c = cells.get(ref);
        return c == null ? Blank.IT : c.value();
    }

    /** Tell the listeners, each in its own try/catch, so a broken repaint cannot break an edit that already happened. */
    private void publish(List<CellChange> changes) {
        for (CellChange c : changes)
            for (ChangeListener l : listeners) {
                try { l.onChange(c); } catch (RuntimeException ignored) { /* a listener is never allowed to fail an edit */ }
            }
    }

    private static List<CellRef> closed(List<CellRef> path, CellRef start) {
        List<CellRef> out = new ArrayList<>(path);
        out.add(start);
        return out;
    }
}

/** The demo: the model, an edit rippling in order, a refused cycle, errors as values, and the race made visible. */
public class Main {
    public static void main(String[] args) throws Exception {
        Sheet sheet = Sheet.standard();

        System.out.println("1. MODEL -- literals, formulas, a range, a branch, an error");
        sheet.set("A1", "10"); sheet.set("A2", "20"); sheet.set("A3", "=A1+A2");
        sheet.set("B1", "=SUM(A1:A3)"); sheet.set("B2", "=IF(B1>50,\"BIG\",\"SMALL\")");
        sheet.set("C1", "=A1/0"); sheet.set("C2", "=SUM(C1,1)");
        for (String r : new String[] { "A3", "B1", "B2", "C1", "C2" })
            System.out.println("   " + r + "  " + pad(sheet.raw(r)) + " -> " + sheet.get(r).display());
        System.out.println("   cells stored = " + sheet.cellCount() + ", read-edges = " + sheet.edgeCount() + " (the grid is sparse)");

        System.out.println("2. EDIT A1 -> 25: only the affected cells recompute, and in dependency order");
        System.out.println("   recalc order = " + sheet.set("A1", "25"));
        System.out.println("   A3=" + sheet.get("A3").display() + "  B1=" + sheet.get("B1").display()
                + "  B2=" + sheet.get("B2").display() + "   (A2 never appeared, and is still " + sheet.get("A2").display() + ")");

        System.out.println("3. CYCLE: A1 = =A3 is refused, and the sheet is untouched");
        String rawBefore = sheet.raw("A1"); int edgesBefore = sheet.edgeCount();
        try { sheet.set("A1", "=A3"); }
        catch (CircularReferenceException e) { System.out.println("   " + e.getMessage()); }
        System.out.println("   A1 raw=" + sheet.raw("A1") + " value=" + sheet.get("A1").display()
                + "  unchanged=" + rawBefore.equals(sheet.raw("A1")) + "  edges=" + sheet.edgeCount() + " (was " + edgesBefore + ")");

        System.out.println("4. BAD INPUT is a value, not a crash -- and it heals");
        sheet.set("D1", "=1+"); sheet.set("D2", "=NOPE(1)");
        sheet.set("E1", "hello"); sheet.set("E2", "=E1*2");
        System.out.println("   D1=" + sheet.get("D1").display() + "  D2=" + sheet.get("D2").display()
                + "  E2=" + sheet.get("E2").display());
        sheet.set("E1", "7");
        System.out.println("   after E1 = 7, E2 = " + sheet.get("E2").display() + " (the error was a cached value, and it went away)");

        System.out.println("5. DELETE a referenced cell -> #REF!, and typing into it again heals the dependents");
        sheet.deleteCell("A2");
        System.out.println("   A3=" + sheet.get("A3").display() + "  B1=" + sheet.get("B1").display());
        sheet.set("A2", "20");
        System.out.println("   A2 back -> A3=" + sheet.get("A3").display() + "  B1=" + sheet.get("B1").display());

        System.out.println("6. LISTENERS hear after the unlock, and a broken one is harmless");
        List<String> heard = Collections.synchronizedList(new ArrayList<>());
        sheet.addListener(c -> { throw new RuntimeException("a broken chart"); });
        sheet.addListener(c -> heard.add(c.ref() + ":" + c.before().display() + "->" + c.after().display()));
        sheet.set("A1", "30");
        System.out.println("   " + heard);

        System.out.println("7. COST of one edit, measured: these are the numbers page 02 quotes");
        Sheet small = Sheet.standard();
        small.set("A1", "10"); small.set("A2", "20"); small.set("A3", "=A1+A2"); small.set("B1", "=A3*2");
        System.out.println("   three cells recomputed:  " + perEdit(small, 50_000) + " us inside the write lock");
        Sheet column = Sheet.standard();
        column.set("A1", "1");
        for (int i = 1; i <= 100; i++) column.set("B" + i, "=A1+" + i);
        System.out.println("   a hundred-cell column:   " + perEdit(column, 20_000) + " us inside the write lock");
        Sheet one = Sheet.standard();
        one.set("A1", "5");
        for (int i = 0; i < 200_000; i++) one.get("A1");
        long t0 = System.nanoTime();
        for (int i = 0; i < 1_000_000; i++) one.get("A1");
        System.out.println("   and one read:            " + (System.nanoTime() - t0) / 1_000_000 + " ns (a hash lookup under the read lock)");

        System.out.println("8. THE RACE: eight typists, 250 increments each, on one cell");
        System.out.println("   get() then set()  -> D1 = " + increments(false) + "   (should be 2000)");
        System.out.println("   update(), one lock -> D1 = " + increments(true) + "   (should be 2000)");

        System.out.println("9. THE RACE, the other shape: fifty threads, fifty different cells, one total");
        Sheet big = Sheet.standard();
        for (int i = 1; i <= 50; i++) big.set("A" + i, "0");
        big.set("B1", "=SUM(A1:A50)");
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> fs = new ArrayList<>();
        for (int i = 1; i <= 50; i++) {
            final int n = i;
            fs.add(pool.submit(() -> { go.await(); return big.set("A" + n, String.valueOf(n)); }));
        }
        go.countDown();
        for (Future<?> f : fs) f.get();
        pool.shutdown();
        double total = ((Num) big.get("B1")).v();
        System.out.println("   B1 = " + big.get("B1").display() + " (must be 1275); every formula consistent = " + (total == 1275));
        if (total != 1275) throw new AssertionError("the sheet lost an update");
    }

    /** Microseconds for one edit of A1, after a warm-up long enough that the JIT has compiled the write path. */
    private static double perEdit(Sheet s, int n) {
        for (int i = 0; i < n; i++) s.set("A1", String.valueOf(i));
        long t0 = System.nanoTime();
        for (int i = 0; i < n; i++) s.set("A1", String.valueOf(i));
        return Math.round((System.nanoTime() - t0) / (double) n) / 1000.0;
    }

    /** Eight threads adding 1 to D1, 250 times each. Compound is get-then-set; otherwise one locked update(). */
    private static String increments(boolean atomic) throws Exception {
        Sheet s = Sheet.standard();
        s.set("D1", "0");
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> fs = new ArrayList<>();
        for (int t = 0; t < 8; t++) fs.add(pool.submit(() -> {
            go.await();
            for (int k = 0; k < 250; k++) {
                if (atomic) s.update("D1", v -> v + 1);
                else s.set("D1", new Num(Evaluator.num(s.get("D1")) + 1).display());   // two steps, and a gap between them
            }
            return null;
        }));
        go.countDown();
        for (Future<?> f : fs) f.get();
        pool.shutdown();
        return s.get("D1").display();
    }

    private static String pad(String s) { return (s + "                ").substring(0, 16); }
}
