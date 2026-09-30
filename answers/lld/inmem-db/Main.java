import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * The types a column can hold. The enum is also the type checker: the check is one map lookup, never a chain of
 * ifs, so adding DECIMAL later is one constant and one line in the table below.
 */
enum ColType {
    INT, TEXT, BOOL;
    /** The Java class each column type stores. An EnumMap, so a type check is an array index. */
    private static final EnumMap<ColType, Class<?>> JAVA = new EnumMap<>(ColType.class);
    static { JAVA.put(INT, Long.class); JAVA.put(TEXT, String.class); JAVA.put(BOOL, Boolean.class); }
    /** Can a column of this type hold this value? null is the NOT NULL rule's business, not this one's. */
    boolean accepts(Object v) { return v == null || JAVA.get(this).isInstance(v); }
    /** The Java class behind this type, so a rejection message tells you what to hand it instead. */
    String javaType() { return JAVA.get(this).getSimpleName(); }
}

/** One column of a table: its name, its type, and whether it may hold null. Fixed when the table is created. */
record Column(String name, ColType type, boolean notNull) {
    /** A whole-number column, stored as a long. */
    static Column intCol(String name, boolean notNull) { return new Column(name, ColType.INT, notNull); }
    /** A string column. */
    static Column text(String name, boolean notNull) { return new Column(name, ColType.TEXT, notNull); }
    /** A true/false column. */
    static Column bool(String name, boolean notNull) { return new Column(name, ColType.BOOL, notNull); }
}

/** The one coercion in the system: an int literal becomes a long, so 1 and 1L mean the same column value. */
final class Values {
    private Values() {}
    /** Normalise a value handed in from outside. Everything else is stored exactly as given. */
    static Object norm(Object v) { return (v instanceof Integer i) ? Long.valueOf(i.longValue()) : v; }
}

/** A rule was broken: a type, a NOT NULL, a CHECK, a duplicate primary key, a foreign key. Nothing of the refused statement stays. */
class ConstraintViolation extends RuntimeException {
    /** @param message what was refused, in words a caller can act on. */
    ConstraintViolation(String message) { super(message); }
}

/** This transaction waited for a table longer than it was allowed to. It has been rolled back; retry it. */
class LockTimeout extends RuntimeException {
    /** @param message which table was wanted and for how long. */
    LockTimeout(String message) { super(message); }
}

/**
 * The shape of a table: its columns in order, a name-to-position map so a lookup by name is O(1), and which
 * column is the primary key. Immutable, so every row of the table can share one Schema.
 */
final class Schema {
    private final List<Column> cols;
    private final Map<String, Integer> pos;
    private final int pk;

    /** @param pkColumn the name of the primary key column; it must exist and must be NOT NULL. */
    Schema(String pkColumn, Column... columns) {
        cols = List.of(columns);
        Map<String, Integer> p = new LinkedHashMap<>();
        for (int i = 0; i < cols.size(); i++)
            if (p.put(cols.get(i).name(), i) != null) throw new IllegalArgumentException("duplicate column: " + cols.get(i).name());
        pos = Map.copyOf(p);
        Integer k = p.get(pkColumn);
        if (k == null) throw new IllegalArgumentException("primary key column is not in the table: " + pkColumn);
        if (!cols.get(k).notNull()) throw new IllegalArgumentException("a primary key column cannot be nullable: " + pkColumn);
        pk = k;
    }
    /** How many columns the table has. */
    int size() { return cols.size(); }
    /** The column at this position. */
    Column col(int i) { return cols.get(i); }
    /** The position of a column by name, O(1). Throws if there is no such column, which is a bug, not bad data. */
    int pos(String name) {
        Integer i = pos.get(name);
        if (i == null) throw new IllegalArgumentException("no such column: " + name);
        return i;
    }
    /** Does the table have this column? Used by the planner before it tries to read a predicate. */
    boolean has(String name) { return pos.containsKey(name); }
    /** The position of the primary key column. */
    int pkIndex() { return pk; }
    /** The name of the primary key column. */
    String pkName() { return cols.get(pk).name(); }
    /** The columns, in order. */
    List<Column> columns() { return cols; }
}

/**
 * One row, immutable. An update never edits a row: it builds a new one and swaps it in, which is exactly what
 * makes the undo log free -- the old object IS the before-image, so nothing has to be copied to be able to undo.
 */
final class Row {
    private final Object[] cells;
    private final long version;
    private final long atMs;

    /** @param cells one value per column, in column order; version and atMs come from the database. */
    Row(Object[] cells, long version, long atMs) { this.cells = cells; this.version = version; this.atMs = atMs; }
    /** The value in this column position. */
    Object get(int i) { return cells[i]; }
    /** The value in this column by name. */
    Object get(Schema s, String col) { return cells[s.pos(col)]; }
    /** A number no other write shares, from one database-wide counter: the stamp an optimistic-locking check compares. */
    long version() { return version; }
    /** When this version of the row was written, from the injected clock. */
    long atMs() { return atMs; }
    /** This row's primary key value. */
    Object pk(Schema s) { return cells[s.pkIndex()]; }
    /** A copy with some columns replaced. The original is untouched, so it can still be used as the undo image. */
    Row with(Schema s, Map<String, Object> set, long version, long atMs) {
        Object[] c = cells.clone();
        for (Map.Entry<String, Object> e : set.entrySet()) c[s.pos(e.getKey())] = Values.norm(e.getValue());
        return new Row(c, version, atMs);
    }
    /** The row as "id=1, name=Asha, city=Pune", for a demo print or a failing test's message. */
    String show(Schema s) {
        StringJoiner j = new StringJoiner(", ");
        for (int i = 0; i < cells.length; i++) j.add(s.col(i).name() + "=" + cells[i]);
        return j.toString();
    }
}

/** Where time comes from. Injected, so a test can stamp rows, and time out a lock, at instants it chooses. */
interface Clock { long nowMs(); }

/**
 * A where-clause: does this row match? One method, so a lambda is a valid predicate. The two shapes the planner
 * can READ -- Eq and Between -- are what let it reach for an index instead of scanning.
 */
interface Predicate {
    /** True if this row matches. The schema is handed in so a predicate can name columns rather than positions. */
    boolean test(Schema s, Row r);
}

/** column = value. On the primary key this is a hash lookup; on an indexed column, an index probe. */
record Eq(String col, Object val) implements Predicate {
    public boolean test(Schema s, Row r) { return Objects.equals(r.get(s.pos(col)), val); }
}

/** lo <= column <= hi, both ends included. On an indexed column the planner turns this into a TreeMap subMap. */
record Between(String col, Object lo, Object hi) implements Predicate {
    public boolean test(Schema s, Row r) {
        Object v = r.get(s.pos(col));
        return v != null && Index.cmp(v, lo) >= 0 && Index.cmp(v, hi) <= 0;
    }
}

/** Every part must match. The planner uses the first part it can turn into an index probe and filters with the rest. */
record And(List<Predicate> parts) implements Predicate {
    public boolean test(Schema s, Row r) {
        for (Predicate p : parts) if (!p.test(s, r)) return false;
        return true;
    }
}

/** Matches every row: a full scan, said out loud rather than implied. */
record All() implements Predicate {
    public boolean test(Schema s, Row r) { return true; }
}

/** Readable constructors for the where-clause: Where.eq("city", "Pune"), Where.between("age", 30, 40). */
final class Where {
    private Where() {}
    /** column = value. */
    static Predicate eq(String column, Object value) { return new Eq(column, Values.norm(value)); }
    /** lo <= column <= hi. */
    static Predicate between(String column, Object lo, Object hi) { return new Between(column, Values.norm(lo), Values.norm(hi)); }
    /** All of these must match. */
    static Predicate and(Predicate... parts) { return new And(List.of(parts)); }
    /** Every row. */
    static Predicate all() { return new All(); }
}

/**
 * A rule that can be judged by looking at the row alone: a type, a NOT NULL, a CHECK. It runs BEFORE any lock is
 * taken and before anything is written, so a bad row never reaches the table at all.
 */
interface RowRule {
    /** Throw ConstraintViolation if this row may not be stored. */
    void check(Schema s, Row row);
}

/** Every value must fit its column's type. Built in: a table always has this rule. */
final class TypeRule implements RowRule {
    public void check(Schema s, Row row) {
        for (int i = 0; i < s.size(); i++) {
            Column c = s.col(i);
            if (!c.type().accepts(row.get(i)))
                throw new ConstraintViolation("column " + c.name() + " is " + c.type() + " (" + c.type().javaType()
                    + "), got " + (row.get(i) == null ? "null" : row.get(i).getClass().getSimpleName()));
        }
    }
}

/** A NOT NULL column may not hold null. Built in: a table always has this rule. */
final class NotNullRule implements RowRule {
    public void check(Schema s, Row row) {
        for (int i = 0; i < s.size(); i++)
            if (s.col(i).notNull() && row.get(i) == null)
                throw new ConstraintViolation("column " + s.col(i).name() + " is NOT NULL");
    }
}

/** A CHECK: any predicate over the row itself, handed in when the table is created. */
final class CheckRule implements RowRule {
    private final Predicate p;
    private final String message;
    /** @param p the condition every row must satisfy; message is what the caller is told when it does not. */
    CheckRule(Predicate p, String message) { this.p = p; this.message = message; }
    public void check(Schema s, Row row) { if (!p.test(s, row)) throw new ConstraintViolation("CHECK failed: " + message); }
}

/**
 * A rule that cannot be judged from the row alone because it has to READ a table: primary key uniqueness, a
 * foreign key. That is the whole reason it runs INSIDE the table lock -- reading and writing must be one step.
 */
interface TableRule {
    /** Throw ConstraintViolation if this change may not happen. before is null for an insert, after for a delete.
     *  It is handed the transaction, not the database, so a rule that reads another table locks it like any read. */
    void check(Txn txn, Table t, Row before, Row after);
}

/** The primary key is unique. Built in, and the one check that must be inside the lock or two inserts both win. */
final class PrimaryKeyRule implements TableRule {
    public void check(Txn txn, Table t, Row before, Row after) {
        if (after == null) return;                                   // a delete cannot create a duplicate
        Object pk = after.pk(t.schema());
        Row existing = t.row(pk);
        if (existing != null && existing != before)                  // identity: an update may keep its own key
            throw new ConstraintViolation("duplicate primary key " + t.schema().pkName() + "=" + pk + " in " + t.name());
    }
}

/** What happened to one row. INSERT has no before, DELETE has no after, UPDATE has both. */
enum ChangeKind { INSERT, UPDATE, DELETE }

/** One row change from one committed transaction, handed to the triggers as part of a batch. */
record Change(String table, Schema schema, ChangeKind kind, Row before, Row after) {}

/**
 * Somebody who wants to know what changed: an audit log, a count kept up to date, a cache to refresh.
 * Called AFTER the transaction commits and AFTER every lock is released, with the whole batch in one call.
 * So two commits can call it at the same moment, in either order: a trigger must be thread-safe, and anything
 * that needs the commit order (a log for a restart) is a CommitLog instead, written before the unlock.
 */
interface Trigger {
    /** The changes of one committed transaction, in the order they happened. */
    void afterCommit(List<Change> batch);
}

/**
 * The wrapper the database puts around every trigger it is handed. A trigger that throws must not break a commit
 * that already happened, and must not stop the other triggers; the failure is counted instead of swallowed.
 */
final class SafeTrigger implements Trigger {
    private final Trigger inner;
    private final AtomicInteger failures = new AtomicInteger();
    /** @param inner the trigger that was handed in; it is never called directly by the database. */
    SafeTrigger(Trigger inner) { this.inner = inner; }
    public void afterCommit(List<Change> batch) {
        try { inner.afterCommit(batch); } catch (RuntimeException e) { failures.incrementAndGet(); }
    }
    /** How many times this trigger has thrown. A number worth putting on a dashboard. */
    int failures() { return failures.get(); }
    /** The trigger that was handed in, for a test that wants to read it. */
    Trigger inner() { return inner; }
}

/**
 * Where committed changes go so that they outlive the process: a file on disk, a feed to a replica. It is called
 * at COMMIT while the transaction still holds its tables, so the log's order is the commit order. It is NOT
 * wrapped like a trigger: a log that fails must fail the commit. The default keeps nothing (memory only).
 */
interface CommitLog {
    /** Append one transaction's changes and return only when they are safe; throw if they are not. */
    void append(List<Change> batch);
}

/**
 * A secondary index: one column's value -> the primary keys that hold it, kept in a TreeMap so "between" is a
 * subMap instead of a scan. Rows whose indexed value is null are not in the index; a query for them scans.
 */
final class Index {
    private final String column;
    private final int col;
    private final TreeMap<Object, LinkedHashSet<Object>> tree = new TreeMap<>(Index::cmp);

    /** @param s the table's schema, used once to turn the column name into a position. */
    Index(Schema s, String column) { this.column = column; this.col = s.pos(column); }
    /** The column this index is on. */
    String column() { return column; }
    /** Compare two values of the same column. They are Long, String or Boolean, so all of them are Comparable. */
    @SuppressWarnings("unchecked")
    static int cmp(Object a, Object b) { return ((Comparable<Object>) a).compareTo(b); }
    /** Record that this row, whose primary key is pk, holds its value in this column. */
    void add(Row r, Object pk) {
        Object k = r.get(col);
        if (k == null) return;
        tree.computeIfAbsent(k, x -> new LinkedHashSet<>()).add(pk);
    }
    /** Forget that row. An empty key is removed so a settled index costs no memory. */
    void remove(Row r, Object pk) {
        Object k = r.get(col);
        if (k == null) return;
        Set<Object> s = tree.get(k);
        if (s != null) { s.remove(pk); if (s.isEmpty()) tree.remove(k); }
    }
    /** The primary keys holding exactly this value: one tree lookup, O(log n). */
    Set<Object> eq(Object v) {
        Set<Object> s = tree.get(Values.norm(v));
        return s == null ? Set.of() : s;
    }
    /** The primary keys in this closed range, in key order: O(log n) to find the start, then one step per hit. */
    List<Object> range(Object lo, Object hi) {
        List<Object> out = new ArrayList<>();
        if (cmp(Values.norm(lo), Values.norm(hi)) > 0) return out;    // 35 to 30 is empty, as a scan says; subMap would throw
        for (Set<Object> s : tree.subMap(Values.norm(lo), true, Values.norm(hi), true).values()) out.addAll(s);
        return out;
    }
    /** How many distinct values the index holds. Used by the planner and by the tests. */
    int keyCount() { return tree.size(); }
}

/** How a query will be answered: the access path chosen, and the rows it has to look at. */
record Plan(String how, List<Row> candidates) {}

/**
 * One table: its shape, its rows by primary key, its secondary indexes, its rules and its one lock. Every row
 * change in the whole system goes through this class's apply(), which is the only place rows and indexes move.
 */
final class Table {
    private final String name;
    private final Schema schema;
    private final Map<Object, Row> byPk = new HashMap<>();
    private final Map<String, Index> indexes = new LinkedHashMap<>();
    private final List<RowRule> rowRules = new ArrayList<>();
    private final List<TableRule> tableRules = new ArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();

    /** A table starts with the three rules every table has: types, NOT NULL, and a unique primary key. */
    Table(String name, Schema schema) {
        this.name = name; this.schema = schema;
        rowRules.add(new TypeRule());
        rowRules.add(new NotNullRule());
        tableRules.add(new PrimaryKeyRule());
    }
    /** The table's name. */
    String name() { return name; }
    /** The table's shape. */
    Schema schema() { return schema; }
    /** The one lock for this table. Taken by the lock policy, never by the table itself. */
    ReentrantLock lock() { return lock; }
    /** Hand in a row-level rule (a CHECK). The table never builds one. */
    Table addRule(RowRule r) { rowRules.add(r); return this; }
    /** Hand in a table-level rule (a foreign key). It will run inside the lock, with the table already readable. */
    Table addRule(TableRule r) { tableRules.add(r); return this; }

    /**
     * Build a secondary index on a column, backfilling from the rows already there, so an index can be added at
     * any time. Call it while nothing else is running: creating an index is not part of the transaction story.
     */
    Index createIndex(String column) {
        Index ix = new Index(schema, column);
        for (Map.Entry<Object, Row> e : byPk.entrySet()) ix.add(e.getValue(), e.getKey());
        indexes.put(column, ix);
        return ix;
    }
    /** The index on this column, or null if there is none. */
    Index index(String column) { return indexes.get(column); }
    /** Every index on this table. */
    Collection<Index> indexes() { return indexes.values(); }

    /** Run every row-level rule. Called before the lock is taken, because none of them needs to read the table. */
    void checkRow(Row r) { for (RowRule x : rowRules) x.check(schema, r); }
    /** Run every table-level rule. Called inside the lock, because all of them read the table. */
    void checkTable(Txn txn, Row before, Row after) { for (TableRule x : tableRules) x.check(txn, this, before, after); }

    /**
     * THE ONE DOOR every row change passes through: an insert (before = null), an update, a delete (after = null),
     * and an undo, which is this same call with the two images swapped. Row and indexes move together or not at
     * all, so there is exactly one place an index could ever go out of step with the rows.
     */
    void apply(Row before, Row after) {
        Object pk = (after != null ? after : before).pk(schema);
        if (before != null) for (Index ix : indexes.values()) ix.remove(before, pk);
        if (after == null) byPk.remove(pk); else byPk.put(pk, after);
        if (after != null) for (Index ix : indexes.values()) ix.add(after, pk);
    }

    /** Build a row from positional values in column order. Arity is checked here; types are checked by the rules. */
    Row build(Database db, Object[] values) {
        if (values.length != schema.size())
            throw new ConstraintViolation(name + " has " + schema.size() + " columns, got " + values.length + " values");
        Object[] cells = new Object[values.length];
        for (int i = 0; i < values.length; i++) cells[i] = Values.norm(values[i]);
        return new Row(cells, db.nextVersion(), db.now());
    }

    /** The row with this primary key, or null. One hash lookup: O(1) at any table size. */
    Row row(Object pk) { return byPk.get(Values.norm(pk)); }
    /** How many rows the table holds. */
    int rowCount() { return byPk.size(); }
    /** Every row, in primary key order, so a print or a test is deterministic. */
    List<Row> allRows() { return sortedByPk(byPk.values()); }

    /**
     * Choose the access path. In order of cheapness: the primary key map, an index probe, an index range, and
     * only then a full scan. This is the whole query planner: three ifs, and it is why a where-clause is an
     * object rather than a lambda -- the planner has to be able to READ the predicate to improve on it.
     */
    Plan plan(Predicate p) {
        List<Predicate> parts = (p instanceof And a) ? a.parts() : List.of(p);
        for (Predicate q : parts)
            if (q instanceof Eq e && e.val() != null && e.col().equals(schema.pkName())) {
                Row r = byPk.get(e.val());
                return new Plan("primary key lookup on " + name, r == null ? List.of() : List.of(r));
            }
        for (Predicate q : parts)
            if (q instanceof Eq e && e.val() != null && indexes.containsKey(e.col()))
                return new Plan("index probe on " + name + "." + e.col(), rowsOf(indexes.get(e.col()).eq(e.val())));
        for (Predicate q : parts)
            if (q instanceof Between b && indexes.containsKey(b.col()))
                return new Plan("index range on " + name + "." + b.col(), rowsOf(indexes.get(b.col()).range(b.lo(), b.hi())));
        return new Plan("full scan of " + name + " (" + byPk.size() + " rows)", allRows());
    }

    /** The rows matching this predicate: the planner picks the candidates, then every candidate is tested. */
    List<Row> select(Predicate p) {
        List<Row> out = new ArrayList<>();
        for (Row r : plan(p).candidates()) if (p.test(schema, r)) out.add(r);
        return out;
    }

    /** Turn a list of primary keys from an index into rows, keeping the index's order. */
    private List<Row> rowsOf(Collection<Object> pks) {
        List<Row> out = new ArrayList<>(pks.size());
        for (Object pk : pks) { Row r = byPk.get(pk); if (r != null) out.add(r); }
        return out;
    }
    /** Sort by primary key, so a scan has a stable order (a real database promises none without ORDER BY). */
    private List<Row> sortedByPk(Collection<Row> rows) {
        List<Row> out = new ArrayList<>(rows);
        out.sort((a, b) -> Index.cmp(a.pk(schema), b.pk(schema)));
        return out;
    }
}

/**
 * Who may touch a table, and for how long. Handed in, so the same race in main() can be run twice -- once with
 * locking and once without -- and the difference printed rather than described.
 */
interface LockPolicy {
    /** Take the table for the calling transaction, waiting at most timeoutMs. false means "give up and abort". */
    boolean acquire(Table t, long timeoutMs);
    /** Give the table back. Called once per table, when the transaction ends. */
    void release(Table t);
}

/**
 * Strict two-phase locking: take a table's lock the first time the transaction touches it and hold it until the
 * transaction ends. That is what makes the undo log sound -- nobody else can write a row between the moment this
 * transaction saved its before-image and the moment it decides to put it back.
 */
final class StrictTableLocking implements LockPolicy {
    public boolean acquire(Table t, long timeoutMs) {
        try { return t.lock().tryLock(timeoutMs, TimeUnit.MILLISECONDS); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
    }
    public void release(Table t) { t.lock().unlock(); }
}

/** No locking at all. It exists so the demo can run the same race with it and show what breaks. Never ship it. */
final class NoLocking implements LockPolicy {
    public boolean acquire(Table t, long timeoutMs) { return true; }
    public void release(Table t) { }
}

/** A transaction's life. Every operation after it ends throws, rather than quietly doing nothing. */
enum TxnState { ACTIVE, COMMITTED, ROLLED_BACK }

/** One reversible change: undoing it is apply(after, before) -- the same door, with the two images swapped. */
record UndoEntry(Table table, Row before, Row after) {}

/**
 * One client's transaction: the undo log, the tables it holds, and the changes it will publish if it commits.
 * Used only by the thread that began it: a table lock is a ReentrantLock, which only the thread that took it can
 * release. One thread runs one transaction at a time; the concurrency is between transactions, never inside one.
 */
final class Txn {
    private final Database db;
    private final long id;
    private final List<UndoEntry> undo = new ArrayList<>();
    private final List<Change> pending = new ArrayList<>();
    private final LinkedHashSet<Table> held = new LinkedHashSet<>();
    private TxnState state = TxnState.ACTIVE;

    /** @param db the database this transaction runs against; id is for logs and messages. */
    Txn(Database db, long id) { this.db = db; this.id = id; }
    /** This transaction's number. */
    long id() { return id; }
    /** The database this transaction runs against, for a rule that needs to name another table. */
    Database db() { return db; }
    /** ACTIVE, COMMITTED or ROLLED_BACK. */
    TxnState state() { return state; }

    /** Refuse anything after the transaction has ended: a finished transaction is not a usable handle. */
    private void alive() {
        if (state != TxnState.ACTIVE) throw new IllegalStateException("transaction " + id + " is " + state + "; begin a new one");
    }

    /**
     * Take this table's lock unless we already hold it, and hold it until the transaction ends. If the wait runs
     * out this transaction is the deadlock loser: it rolls back (freeing every table it held) and throws.
     */
    private void use(Table t) {
        if (held.add(t) && !db.locks().acquire(t, db.lockTimeoutMs())) {
            held.remove(t);
            rollback();
            throw new LockTimeout("transaction " + id + " waited " + db.lockTimeoutMs() + " ms for " + t.name() + " and gave up");
        }
    }

    /**
     * Insert one row. The order is the whole design: build and validate the row with nothing locked and nothing
     * written; take the lock; check the rules that must read the table; only then write the row and its indexes.
     */
    Row insert(String table, Object... values) {
        alive();
        Table t = db.table(table);
        Row row = t.build(db, values);
        t.checkRow(row);                                  // types, NOT NULL, CHECK -- no lock held, nothing written
        use(t);                                           // now the lock, and we keep it until commit or rollback
        t.checkTable(this, null, row);                      // primary key uniqueness: must read the table, so it is in here
        write(t, null, row, ChangeKind.INSERT);
        return row;
    }

    /**
     * Update every row matching the where-clause. Each new row can only be built after reading the old one, so its
     * rules run inside the lock. If the third row is refused, the first two are undone: a statement is all or nothing.
     */
    int update(String table, Predicate where, Map<String, Object> set) {
        alive();
        Table t = db.table(table);
        if (set.containsKey(t.schema().pkName()))
            throw new ConstraintViolation("a primary key is not editable: delete the row and insert it again");
        use(t);
        int start = undo.size();                              // where this statement began, like a savepoint
        try {
            List<Row> hits = t.select(where);
            for (Row before : hits) {
                Row after = before.with(t.schema(), set, db.nextVersion(), db.now());
                t.checkRow(after);
                t.checkTable(this, before, after);
                write(t, before, after, ChangeKind.UPDATE);
            }
            return hits.size();
        } catch (RuntimeException e) { undoStatement(start); throw e; }
    }

    /** Delete every row matching the where-clause. A table rule (a foreign key) may refuse one; then none go. */
    int delete(String table, Predicate where) {
        alive();
        Table t = db.table(table);
        use(t);
        int start = undo.size();
        try {
            List<Row> hits = t.select(where);
            for (Row before : hits) {
                t.checkTable(this, before, null);
                write(t, before, null, ChangeKind.DELETE);
            }
            return hits.size();
        } catch (RuntimeException e) { undoStatement(start); throw e; }
    }

    /** A statement that failed half way is undone back to its start; the transaction stays open, as in SQL. */
    private void undoStatement(int start) {
        if (state == TxnState.ACTIVE) rollbackTo(start);      // a lock timeout has already rolled everything back
    }

    /** The table, locked for the rest of this transaction. Every read starts here, and so can code that reads the
     *  table's maps directly (a join, a cost-based planner). */
    Table table(String table) {
        alive();
        Table t = db.table(table);
        use(t);
        return t;
    }

    /** Read the rows matching the where-clause. Reads take the lock too, and keep it: that is what isolation costs. */
    List<Row> select(String table, Predicate where) { return table(table).select(where); }

    /** How this transaction would answer that query: the access path, for an EXPLAIN-style print. */
    String explain(String table, Predicate where) {
        Plan p = table(table).plan(where);
        return p.how() + ", " + p.candidates().size() + " row(s) examined";
    }

    /** One write: through the table's single door, then one undo entry and one pending change, always in step. */
    private void write(Table t, Row before, Row after, ChangeKind kind) {
        t.apply(before, after);
        undo.add(new UndoEntry(t, before, after));
        pending.add(new Change(t.name(), t.schema(), kind, before, after));
    }

    /** A SQL SAVEPOINT: how many changes this transaction has made so far. Locks are not released -- they are held to the end. */
    int savepoint() { alive(); return undo.size(); }

    /** Undo everything done since that savepoint and keep the transaction open. Nested BEGIN is this, with a name. */
    void rollbackTo(int savepoint) {
        alive();
        if (savepoint < 0 || savepoint > undo.size()) throw new IllegalArgumentException("no such savepoint: " + savepoint);
        for (int i = undo.size() - 1; i >= savepoint; i--) {
            UndoEntry e = undo.remove(i);
            e.table().apply(e.after(), e.before());
            pending.remove(pending.size() - 1);           // undo and pending grow in step, one entry per change
        }
    }

    /**
     * Commit, in three steps. The batch goes to the log while the tables are still held, so the log's order is the
     * commit order; if the log throws, the transaction is rolled back and the caller is told. Then the locks are
     * released. Only then are the triggers told, so a trigger never runs while a table is held.
     */
    void commit() {
        alive();
        List<Change> batch = List.copyOf(pending);
        if (!batch.isEmpty()) {
            try { db.log().append(batch); }                   // the commit point: a failed append is a failed commit
            catch (RuntimeException e) { rollback(); throw e; }
        }
        state = TxnState.COMMITTED;
        undo.clear(); pending.clear();
        releaseAll();
        if (!batch.isEmpty()) db.publish(batch);
    }

    /** Roll back: replay the undo log backwards through the same door, release every table, publish nothing. */
    void rollback() {
        if (state != TxnState.ACTIVE) return;             // rolling back a finished transaction is a no-op, not an error
        for (int i = undo.size() - 1; i >= 0; i--) {
            UndoEntry e = undo.get(i);
            e.table().apply(e.after(), e.before());
        }
        state = TxnState.ROLLED_BACK;
        undo.clear(); pending.clear();
        releaseAll();
    }

    /** Give back every table this transaction took, in the order it took them. */
    private void releaseAll() {
        for (Table t : held) db.locks().release(t);
        held.clear();
    }
}

/**
 * The database: the tables, the triggers, the log, the lock policy and the clock. It hands out transactions and
 * publishes their batches; it owns no row state itself, which is why a table can be locked without locking the database.
 */
final class Database {
    private final Map<String, Table> tables = new ConcurrentHashMap<>();
    private final List<SafeTrigger> triggers = new CopyOnWriteArrayList<>();
    private final AtomicLong txnIds = new AtomicLong();
    private final AtomicLong versions = new AtomicLong();
    private volatile LockPolicy locks = new StrictTableLocking();
    private volatile Clock clock = System::currentTimeMillis;
    private volatile CommitLog log = batch -> { };
    private volatile long lockTimeoutMs = 500;

    /** Create a table. DDL (a statement that creates or drops a table) is not transactional here: do it before the clients arrive. */
    Table createTable(String name, String pkColumn, Column... columns) {
        Table t = new Table(name, new Schema(pkColumn, columns));
        if (tables.putIfAbsent(name, t) != null) throw new IllegalArgumentException("table already exists: " + name);
        return t;
    }
    /** Drop a table and every row in it. DDL again: do it when no client is using the table. */
    void dropTable(String name) {
        if (tables.remove(name) == null) throw new IllegalArgumentException("no such table: " + name);
    }
    /** The table with this name. Throws if there is none, which is a bug in the query, not bad data. */
    Table table(String name) {
        Table t = tables.get(name);
        if (t == null) throw new IllegalArgumentException("no such table: " + name);
        return t;
    }
    /** Every table, in name order. */
    List<Table> tables() {
        List<Table> out = new ArrayList<>(tables.values());
        out.sort(Comparator.comparing(Table::name));
        return out;
    }
    /** Hand in the locking policy and the deadlock timeout. The database never builds them itself. */
    void configure(LockPolicy policy, long lockTimeoutMs) { this.locks = policy; this.lockTimeoutMs = lockTimeoutMs; }
    /** Hand in the clock. Tests use it to stamp rows at an instant they choose. */
    void setClock(Clock c) { this.clock = c; }
    /** Hand in the commit log. It is not wrapped: if it throws, the commit fails and is rolled back. */
    void setLog(CommitLog l) { this.log = l; }
    /** The commit log in force. By default it keeps nothing, because this database lives in memory only. */
    CommitLog log() { return log; }
    /** Add a trigger. It is wrapped, so one that throws cannot break a commit or stop the others. */
    SafeTrigger addTrigger(Trigger t) { SafeTrigger s = new SafeTrigger(t); triggers.add(s); return s; }
    /** How many times any trigger has thrown since startup. */
    int triggerFailures() { int n = 0; for (SafeTrigger t : triggers) n += t.failures(); return n; }
    /** Now, from the injected clock. */
    long now() { return clock.nowMs(); }
    /** The next row version. One counter for the whole database, so no two writes ever share a version. */
    long nextVersion() { return versions.incrementAndGet(); }
    /** The lock policy in force. */
    LockPolicy locks() { return locks; }
    /** How long a transaction waits for a table before it gives up and rolls back. */
    long lockTimeoutMs() { return lockTimeoutMs; }
    /** Tell every trigger about one committed batch. Called after the locks are gone, never inside them. */
    void publish(List<Change> batch) { for (SafeTrigger t : triggers) t.afterCommit(batch); }
    /** Begin a transaction. It belongs to the thread that begins it. */
    Txn begin() { return new Txn(this, txnIds.incrementAndGet()); }

    /** Autocommit: one insert in its own transaction. A failure rolls back and rethrows, so nothing is half done. */
    Row insert(String table, Object... values) {
        Txn t = begin();
        try { Row r = t.insert(table, values); t.commit(); return r; }
        catch (RuntimeException e) { t.rollback(); throw e; }
    }
    /** Autocommit: one update in its own transaction. */
    int update(String table, Predicate where, Map<String, Object> set) {
        Txn t = begin();
        try { int n = t.update(table, where, set); t.commit(); return n; }
        catch (RuntimeException e) { t.rollback(); throw e; }
    }
    /** Autocommit: one delete in its own transaction. */
    int delete(String table, Predicate where) {
        Txn t = begin();
        try { int n = t.delete(table, where); t.commit(); return n; }
        catch (RuntimeException e) { t.rollback(); throw e; }
    }
    /** Autocommit: one read in its own transaction. */
    List<Row> select(String table, Predicate where) {
        Txn t = begin();
        try { List<Row> rows = t.select(table, where); t.commit(); return rows; }
        catch (RuntimeException e) { t.rollback(); throw e; }
    }
    /** Autocommit: how that query would be answered. */
    String explain(String table, Predicate where) {
        Txn t = begin();
        try { String s = t.explain(table, where); t.commit(); return s; }
        catch (RuntimeException e) { t.rollback(); throw e; }
    }
}

/**
 * An audit trigger: keeps one line per committed row change. The simplest possible listener, and still it must be
 * thread-safe, because two commits can call it at the same moment.
 */
final class AuditTrigger implements Trigger {
    private final List<String> lines = Collections.synchronizedList(new ArrayList<>());
    public void afterCommit(List<Change> batch) {
        for (Change c : batch) {
            Row r = c.after() != null ? c.after() : c.before();
            lines.add(c.kind() + " " + c.table() + " [" + r.show(c.schema()) + "]");
        }
    }
    /** A copy of everything this trigger has seen. */
    List<String> lines() { return List.copyOf(lines); }
}

/**
 * A materialised count (a result kept up to date as rows change, so reading it needs no scan): "how many users in
 * each city", in O(1). It is the mid-round change that costs one class and one line, because the database already
 * announces what changed. Adding and subtracting give the same total in any order, so batches may arrive in any order.
 */
final class CityCount implements Trigger {
    private final String table, column;
    private final Map<String, Integer> counts = new ConcurrentHashMap<>();
    /** @param table the table to watch; column the text column to count by. */
    CityCount(String table, String column) { this.table = table; this.column = column; }
    public void afterCommit(List<Change> batch) {
        for (Change c : batch) {
            if (!c.table().equals(table)) continue;
            if (c.before() != null) add((String) c.before().get(c.schema(), column), -1);
            if (c.after() != null) add((String) c.after().get(c.schema(), column), +1);
        }
    }
    private void add(String key, int delta) { if (key != null) counts.merge(key, delta, (a, b) -> a + b == 0 ? null : a + b); }
    /** How many rows hold that value, without touching the table. */
    int count(String value) { return counts.getOrDefault(value, 0); }
    /** The whole tally, for a print. */
    Map<String, Integer> all() { return new TreeMap<>(counts); }
}

/** The demo and the race. Run it: java Main. */
public class Main {
    /** Build the two tables, their indexes and their rules. Used by the demo and by the tests. */
    static Database sample() {
        Database db = new Database();
        db.createTable("users", "id",
            Column.intCol("id", true), Column.text("name", true), Column.text("city", true), Column.intCol("age", false));
        db.createTable("orders", "id",
            Column.intCol("id", true), Column.intCol("user_id", true), Column.intCol("total", true), Column.intCol("placed_at", true));
        db.table("users").createIndex("city");
        db.table("users").createIndex("age");
        db.table("orders").createIndex("user_id");
        db.table("orders").createIndex("placed_at");
        db.table("users").addRule(new CheckRule(Where.between("age", 0, 150), "age between 0 and 150"));
        return db;
    }

    public static void main(String[] args) throws Exception {
        Database db = sample();
        AuditTrigger audit = new AuditTrigger();
        CityCount byCity = new CityCount("users", "city");
        db.addTrigger(audit);
        db.addTrigger(byCity);
        db.addTrigger(batch -> { throw new RuntimeException("this trigger is broken on purpose"); });
        Schema us = db.table("users").schema();

        System.out.println("-- inserts (autocommit) ------------------------------------------");
        db.insert("users", 1, "Asha", "Pune", 31);
        db.insert("users", 2, "Bela", "Pune", 42);
        db.insert("users", 3, "Chandra", "Kochi", 27);
        db.insert("users", 4, "Devi", "Kochi", 55);
        db.insert("users", 5, "Ekta", "Indore", 36);
        for (int i = 1; i <= 6; i++) db.insert("orders", i, (i % 5) + 1, 100L * i, 20260900L + i);
        System.out.println("users: " + db.table("users").rowCount() + " rows, orders: " + db.table("orders").rowCount() + " rows");
        System.out.println("a broken trigger threw on every commit; commits: fine, failures counted = " + db.triggerFailures());

        System.out.println("\n-- the three access paths ----------------------------------------");
        System.out.println("by primary key : " + db.explain("users", Where.eq("id", 3)));
        System.out.println("                 " + db.select("users", Where.eq("id", 3)).get(0).show(us));
        System.out.println("by index       : " + db.explain("users", Where.eq("city", "Pune")));
        for (Row r : db.select("users", Where.eq("city", "Pune"))) System.out.println("                 " + r.show(us));
        System.out.println("by range       : " + db.explain("users", Where.between("age", 30, 45)));
        for (Row r : db.select("users", Where.between("age", 30, 45))) System.out.println("                 " + r.show(us));
        System.out.println("no index       : " + db.explain("users", Where.eq("name", "Devi")));
        System.out.println("materialised   : users in Pune = " + byCity.count("Pune") + ", in Kochi = " + byCity.count("Kochi") + "  (no scan)");

        System.out.println("\n-- an update moves the row in the index --------------------------");
        db.update("users", Where.eq("id", 1), Map.of("city", "Kochi", "age", 32));
        System.out.println("Pune now : " + db.select("users", Where.eq("city", "Pune")).size() + " row(s)");
        System.out.println("Kochi now: " + db.select("users", Where.eq("city", "Kochi")).size() + " row(s)");
        System.out.println("counts   : " + byCity.all());

        System.out.println("\n-- what a rejected write leaves behind ---------------------------");
        int before = db.table("users").rowCount();
        for (Object[] bad : new Object[][] {
                { 2L, "Twin", "Pune", 30L },                      // duplicate primary key
                { 9L, "NoCity", null, 30L },                      // NOT NULL
                { 10L, "Wrong", "Pune", "thirty" },               // wrong type
                { 11L, "Old", "Pune", 900L } }) {                 // the CHECK
            try { db.insert("users", bad); System.out.println("ACCEPTED (bug!)"); }
            catch (ConstraintViolation e) { System.out.println("refused: " + e.getMessage()); }
        }
        System.out.println("rows before " + before + ", rows after " + db.table("users").rowCount() + " -- nothing was half written");

        System.out.println("\n-- a transaction, a savepoint and a rollback ---------------------");
        Txn t = db.begin();
        t.insert("users", 6, "Farid", "Surat", 45);
        int sp = t.savepoint();
        t.delete("users", Where.eq("id", 3));
        t.update("users", Where.eq("id", 4), Map.of("city", "Surat"));
        System.out.println("inside the transaction : " + t.select("users", Where.all()).size() + " rows, Kochi = "
            + t.select("users", Where.eq("city", "Kochi")).size());
        t.rollbackTo(sp);
        System.out.println("after ROLLBACK TO      : " + t.select("users", Where.all()).size() + " rows, Kochi = "
            + t.select("users", Where.eq("city", "Kochi")).size());
        t.rollback();
        System.out.println("after ROLLBACK         : " + db.table("users").rowCount() + " rows, Surat = "
            + db.select("users", Where.eq("city", "Surat")).size() + ", counts = " + byCity.all());
        System.out.println("the audit trigger never saw the rolled-back rows: " + audit.lines().size() + " lines for "
            + (db.table("users").rowCount() + db.table("orders").rowCount() + 1) + " committed changes");

        System.out.println("\n-- the race: 50 threads, one primary key -------------------------");
        race();

        System.out.println("\n-- the same 50 read-modify-writes, with the lock and without -----");
        lostUpdate(new StrictTableLocking(), "strict table locking");
        lostUpdate(new NoLocking(), "no locking at all");

        System.out.println("\n-- deadlock: two transactions, two tables, opposite order --------");
        deadlock();
    }

    /**
     * Fifty threads insert the SAME primary key at the same instant, and fifty more insert fifty distinct keys
     * into a second table. Exactly one winner on the contested key, exact counts everywhere, indexes in step.
     */
    static void race() throws Exception {
        Database db = sample();
        db.configure(new StrictTableLocking(), 2000);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Boolean>> contested = new ArrayList<>(), distinct = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final int n = i;
            contested.add(pool.submit(() -> { go.await(); return tryInsert(db, "users", 7L, "racer" + n, "Pune", 30L); }));
            distinct.add(pool.submit(() -> { go.await(); return tryInsert(db, "orders", 1000L + n, 1L, 50L, 20260901L); }));
        }
        go.countDown();
        int wonPk = 0, wonDistinct = 0;
        for (Future<Boolean> f : contested) if (f.get()) wonPk++;
        for (Future<Boolean> f : distinct) if (f.get()) wonDistinct++;
        pool.shutdown();
        int rows = db.table("users").select(Where.eq("id", 7L)).size();
        int indexed = db.table("orders").index("user_id").eq(1L).size();
        System.out.println("the same key  : told \"inserted\" " + wonPk + " / 50, rows with that key: " + rows);
        System.out.println("distinct keys : " + wonDistinct + " / 50 accepted, " + db.table("orders").rowCount()
            + " rows, " + indexed + " primary keys in the user_id index");
        System.out.println(wonPk == 1 && rows == 1 && wonDistinct == 50 && indexed == 50
            ? "invariant held: one winner, exact counts, every index in step with the rows"
            : "INVARIANT BROKEN");
    }

    /**
     * Fifty read-modify-writes of one row -- read the counter, add one, write it back -- run with the lock policy
     * handed in. Identical code both times: nothing here knows or asks which policy it got.
     */
    static void lostUpdate(LockPolicy policy, String label) throws Exception {
        Database db = new Database();
        db.configure(policy, 2000);
        db.createTable("counters", "id", Column.intCol("id", true), Column.intCol("hits", true));
        db.insert("counters", 1, 0);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> all = new ArrayList<>();
        for (int i = 0; i < 50; i++) all.add(pool.submit(() -> {
            go.await();
            Txn t = db.begin();
            try {
                long hits = (Long) t.select("counters", Where.eq("id", 1)).get(0).get(db.table("counters").schema(), "hits");
                t.update("counters", Where.eq("id", 1), Map.of("hits", hits + 1));
                t.commit();
            } catch (RuntimeException e) { t.rollback(); }
            return null;
        }));
        go.countDown();
        for (Future<?> f : all) f.get();
        pool.shutdown();
        long hits = (Long) db.select("counters", Where.eq("id", 1)).get(0).get(db.table("counters").schema(), "hits");
        System.out.println(String.format("%-22s : 50 increments, the counter says %d%s", label, hits,
            hits == 50 ? "" : "  <-- " + (50 - hits) + " committed updates vanished"));
    }

    /** Insert and say whether it was accepted. Any rule failure or lock timeout is a "no", not a crash. */
    static boolean tryInsert(Database db, String table, Object... values) {
        try { db.insert(table, values); return true; }
        catch (ConstraintViolation | LockTimeout e) { return false; }
        catch (RuntimeException e) { return false; }
    }

    /** T1 takes users then wants orders; T2 takes orders then wants users. One of them must give up and roll back. */
    static void deadlock() throws Exception {
        Database db = sample();
        db.configure(new StrictTableLocking(), 300);
        CyclicBarrier both = new CyclicBarrier(2);
        Callable<String> t1 = () -> cross(db, both, "users", 100L, "orders", 100L, 0);
        Callable<String> t2 = () -> cross(db, both, "orders", 101L, "users", 101L, 100);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        Future<String> f1 = pool.submit(t1), f2 = pool.submit(t2);
        String r1 = f1.get(5, TimeUnit.SECONDS), r2 = f2.get(5, TimeUnit.SECONDS);
        pool.shutdown();
        System.out.println("T1: " + r1);
        System.out.println("T2: " + r2);
        System.out.println("rows left behind: " + (db.table("users").rowCount() + db.table("orders").rowCount())
            + " (the winner's two rows; the loser's writes were undone by its own rollback)");
    }

    /** One half of the deadlock: write to one table, wait for the other thread, then reach for the other table. */
    static String cross(Database db, CyclicBarrier both, String first, long id1, String second, long id2, int staggerMs) {
        Txn t = db.begin();
        try {
            if (first.equals("users")) t.insert("users", id1, "dead", "Pune", 30L);
            else t.insert("orders", id1, 1L, 10L, 20260901L);
            both.await();
            Thread.sleep(staggerMs);
            if (second.equals("users")) t.insert("users", id2, "lock", "Pune", 30L);
            else t.insert("orders", id2, 1L, 10L, 20260901L);
            t.commit();
            return "committed both rows";
        } catch (LockTimeout e) {
            return "gave up and rolled back: " + e.getMessage();
        } catch (Exception e) {
            t.rollback();
            return "failed: " + e;
        }
    }
}
