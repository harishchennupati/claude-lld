import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is one twist; ExtDemo at the bottom runs all of them,
// so none of this can rot. Nothing here changes Main.java: every block is a new class handed to the database.

// ---- ext: a foreign key -- a new rule handed in, and the reason a rule is given the TRANSACTION and not the map
/**
 * A foreign key: this column must name a row that exists in the parent table. It is a TableRule because it has to
 * READ another table, and it reads through the transaction, so the parent table is locked for as long as this
 * transaction lives -- which is exactly why two transactions touching two tables in opposite orders can deadlock.
 */
final class ForeignKeyRule implements TableRule {
    private final String column, parentTable;
    /** @param column the child column; parentTable the table whose primary key it must match. */
    ForeignKeyRule(String column, String parentTable) { this.column = column; this.parentTable = parentTable; }
    public void check(Txn txn, Table t, Row before, Row after) {
        if (after == null) return;                                    // a delete in the child cannot break this
        Object v = after.get(t.schema(), column);
        if (v == null) return;                                        // null means "no parent", which is allowed
        if (txn.select(parentTable, Where.eq(txn.db().table(parentTable).schema().pkName(), v)).isEmpty())
            throw new ConstraintViolation(t.name() + "." + column + " = " + v + " has no row in " + parentTable);
    }
}

/**
 * The other direction: do not delete a row that somebody still points at. Installed on the PARENT table, and it
 * scans the child through the transaction, so a child insert cannot slip in behind it.
 */
final class RestrictDeleteRule implements TableRule {
    private final String childTable, childColumn;
    /** @param childTable the table that points here; childColumn the column that holds this table's key. */
    RestrictDeleteRule(String childTable, String childColumn) { this.childTable = childTable; this.childColumn = childColumn; }
    public void check(Txn txn, Table t, Row before, Row after) {
        if (after != null || before == null) return;                  // only a delete is our business
        Object pk = before.pk(t.schema());
        int kids = txn.select(childTable, Where.eq(childColumn, pk)).size();
        if (kids > 0) throw new ConstraintViolation("cannot delete " + t.name() + " " + pk + ": " + kids + " row(s) in " + childTable);
    }
}

// ---- ext: an index added at run time -- backfilled from the rows already there, then maintained by the same door
/**
 * Adding an index to a table that already has rows. createIndex backfills, so the new index is complete the
 * moment it exists, and from then on the table's single apply() keeps it in step like any other index.
 */
final class LateIndex {
    private LateIndex() {}
    /** Add the index and immediately prove the planner uses it. Do it while nothing else is running: DDL is not transactional. */
    static String add(Database db, String table, String column) {
        Table t = db.table(table);
        Index ix = t.createIndex(column);
        return "index on " + table + "." + column + " built over " + t.rowCount() + " existing rows, "
             + ix.keyCount() + " distinct values; the planner now says: " + t.plan(Where.eq(column, t.allRows().get(0).get(t.schema(), column))).how();
    }
}

// ---- ext: EXPLAIN -- when two indexes are usable, pick the one that examines fewer rows
/**
 * A cost-based planner. Main's planner takes the first usable index; this one prices every usable path by the rows
 * it would examine and takes the cheapest. Probing an index to price it is cheap at this size; a real planner keeps
 * histograms (counts of rows per range of values) because probing millions of rows would cost more than the query.
 */
final class CostPlanner {
    private CostPlanner() {}
    /** The cheapest usable path. Each index path is priced by probing it; the scan is priced at the row count. */
    static Plan cheapest(Table t, Predicate p) {
        Plan best = null;
        for (Predicate q : (p instanceof And a) ? a.parts() : List.of(p)) {
            Plan c = probe(t, q);
            if (c != null && (best == null || c.candidates().size() < best.candidates().size())) best = c;
        }
        return best != null ? best : new Plan("full scan (" + t.rowCount() + " rows)", t.allRows());
    }
    /** One part of the where-clause as an index path, or null when no index can answer it. */
    private static Plan probe(Table t, Predicate q) {
        if (q instanceof Eq e && e.val() != null && e.col().equals(t.schema().pkName()))
            return new Plan("primary key lookup on " + e.col(), t.row(e.val()) == null ? List.of() : List.of(t.row(e.val())));
        if (q instanceof Eq e && e.val() != null && t.index(e.col()) != null)
            return new Plan("index probe on " + e.col(), rows(t, t.index(e.col()).eq(e.val())));
        if (q instanceof Between b && t.index(b.col()) != null)
            return new Plan("index range on " + b.col(), rows(t, t.index(b.col()).range(b.lo(), b.hi())));
        return null;
    }
    private static List<Row> rows(Table t, Collection<Object> pks) {
        List<Row> out = new ArrayList<>();
        for (Object pk : pks) out.add(t.row(pk));
        return out;
    }
    /** The rows, found through the cheapest path: the same rows as Main's select, with the fewest examined. */
    static List<Row> select(Txn tx, String table, Predicate p) {
        Table t = tx.table(table);                            // locked for the rest of the transaction, like any read
        List<Row> out = new ArrayList<>();
        for (Row r : cheapest(t, p).candidates()) if (p.test(t.schema(), r)) out.add(r);
        return out;
    }
}

// ---- ext: ORDER BY and a column list -- select(columns, where, orderBy), the API-driven version of this prompt
/**
 * ORDER BY over several columns, each ascending or descending, then only the columns asked for (a projection).
 * Only the k matched rows are sorted, O(k log k), never the table. A range read through a TreeMap index already
 * returns rows in that column's order, and Java's sort notices an already-sorted list and makes one pass.
 */
final class OrderBy {
    private OrderBy() {}
    /** One sort key, written "age" or "age DESC". A null sorts last in either direction. */
    static Comparator<Row> key(Schema s, String spec) {
        String[] p = spec.trim().split("\\s+");
        int col = s.pos(p[0]);
        boolean desc = p.length > 1 && p[1].equalsIgnoreCase("DESC");
        return (a, b) -> {
            Object x = a.get(col), y = b.get(col);
            if (x == null || y == null) return x == y ? 0 : (x == null ? 1 : -1);
            int c = Index.cmp(x, y);
            return desc ? -c : c;
        };
    }
    /** SELECT columns FROM table WHERE where ORDER BY keys, read inside the caller's transaction like any read. */
    static List<List<Object>> select(Txn tx, String table, List<String> columns, Predicate where, String... orderBy) {
        Table t = tx.table(table);
        Schema s = t.schema();
        List<Row> rows = t.select(where);                     // the planner picks the rows: key, index or scan
        Comparator<Row> order = null;
        for (String k : orderBy) order = (order == null) ? key(s, k) : order.thenComparing(key(s, k));
        if (order != null) rows.sort(order);                  // k log k for the k matches only
        List<List<Object>> out = new ArrayList<>();
        for (Row r : rows) {
            List<Object> cells = new ArrayList<>();
            for (String c : columns) cells.add(r.get(s, c));
            out.add(cells);
        }
        return out;
    }
}

// ---- ext: joins -- nested loop with an index, and a hash join, and when each one wins
/**
 * Two ways to join users to orders. Nested loop walks the left side and probes the right side's index: cheap when
 * the left side is small and the right side is indexed. Hash join builds a map from the smaller side and streams
 * the other: one pass over each, no index needed, but the map has to fit in memory. Both read the two tables
 * inside the caller's transaction, so the join sees one consistent database while other clients write.
 */
final class Joins {
    private Joins() {}
    /** For each user, probe the orders index on user_id: n left rows x one index probe each. */
    static List<String> nestedLoop(Txn tx) {
        Table users = tx.table("users"), orders = tx.table("orders");
        List<String> out = new ArrayList<>();
        for (Row u : users.allRows())
            for (Row o : orders.select(Where.eq("user_id", u.pk(users.schema()))))
                out.add(u.get(users.schema(), "name") + " -> " + o.get(orders.schema(), "total"));
        Collections.sort(out);
        return out;
    }
    /** Build a map from users (the smaller side), then stream orders once: O(n + m), and no index is needed. */
    static List<String> hashJoin(Txn tx) {
        Table users = tx.table("users"), orders = tx.table("orders");
        Map<Object, String> build = new HashMap<>();
        for (Row u : users.allRows()) build.put(u.pk(users.schema()), (String) u.get(users.schema(), "name"));
        List<String> out = new ArrayList<>();
        for (Row o : orders.allRows()) {
            String name = build.get(o.get(orders.schema(), "user_id"));
            if (name != null) out.add(name + " -> " + o.get(orders.schema(), "total"));
        }
        Collections.sort(out);
        return out;
    }
}

// ---- ext: persistence -- a write-ahead log, and the conditional UPDATE the same design becomes in SQL
/**
 * Durability: the database's CommitLog. COMMIT appends the batch here while the transaction still holds its tables,
 * so the lines are in commit order, and only then releases the locks. On a real disk the append ends with an fsync
 * (the call that forces the bytes onto the disk); if it throws, the commit fails and is rolled back. A rolled-back
 * transaction never reaches here, which is why replaying the log rebuilds exactly the committed state.
 */
final class WalLog implements CommitLog {
    private final List<String> log = Collections.synchronizedList(new ArrayList<>());
    public void append(List<Change> batch) {
        List<String> lines = new ArrayList<>();
        for (Change c : batch) {
            Row r = c.after() != null ? c.after() : c.before();
            StringJoiner j = new StringJoiner("~");
            j.add(c.kind().name()).add(c.table());
            for (int i = 0; i < c.schema().size(); i++) j.add(enc(r.get(i)));
            lines.add(j.toString());                                  // a real log writes lengths and a checksum
        }
        log.addAll(lines);                                            // one transaction's lines stay together
    }
    /** The log lines, oldest first. */
    List<String> lines() { return List.copyOf(log); }
    /** One value as text, with its type, so replay can put back a long rather than a string that looks like one. */
    static String enc(Object v) {
        if (v == null) return "N";
        if (v instanceof Long l) return "L" + l;
        if (v instanceof Boolean b) return "B" + (b ? 1 : 0);
        return "S" + v;
    }
    /** One value back from text. */
    static Object dec(String s) {
        return switch (s.charAt(0)) {
            case 'N' -> null;
            case 'L' -> Long.parseLong(s.substring(1));
            case 'B' -> s.charAt(1) == '1';
            default -> s.substring(1);
        };
    }
    /**
     * Rebuild a database from the log. The log is a list of statements, so replay is just running them again;
     * this is also why the log, not the map, is the thing you ship to a replica.
     */
    static Database replay(List<String> lines, Database fresh) {
        for (String line : lines) {
            String[] f = line.split("~");
            Table t = fresh.table(f[1]);
            Schema s = t.schema();
            Object[] cells = new Object[s.size()];
            for (int i = 0; i < s.size(); i++) cells[i] = dec(f[i + 2]);
            Object pk = cells[s.pkIndex()];
            switch (ChangeKind.valueOf(f[0])) {
                case INSERT -> fresh.insert(f[1], cells);
                case DELETE -> fresh.delete(f[1], Where.eq(s.pkName(), pk));
                case UPDATE -> {
                    Map<String, Object> set = new LinkedHashMap<>();
                    for (int i = 0; i < s.size(); i++) if (i != s.pkIndex()) set.put(s.col(i).name(), cells[i]);
                    fresh.update(f[1], Where.eq(s.pkName(), pk), set);
                }
            }
        }
        return fresh;
    }
    /**
     * The same design on a real database, where the lock is the row and the transaction is the server's. The
     * version column makes the write conditional: two servers cannot both apply an update to the row they read.
     *
     * <pre>
     * UPDATE users SET city = ?, version = version + 1
     *  WHERE id = ? AND version = ?;         -- 0 rows updated means somebody else got there first: re-read and retry
     * INSERT INTO users (...) VALUES (...) ON CONFLICT (id) DO NOTHING;   -- a retried request inserts once
     * </pre>
     */
    static final String SQL = "see the Javadoc above";
}

// ---- ext: MVCC -- versions per row, so a reader never waits behind a writer
/**
 * Multi-version concurrency control, small enough to read. Every key keeps a chain of versions stamped with the
 * commit number that created them. A reader takes a snapshot -- the commit number at its start -- and always
 * reads the newest version older than that, so it never blocks and never sees a half-finished transaction.
 * What it costs: old versions are garbage that something has to collect, and two transactions can both commit
 * against the same snapshot (write skew), which is why snapshot isolation is not serialisable.
 */
final class MvccStore {
    /** One committed value of one key, stamped with the commit that wrote it. */
    private record Version(long at, String value, boolean deleted) {}
    private final Map<String, List<Version>> chains = new ConcurrentHashMap<>();
    private final AtomicLong commits = new AtomicLong();
    /** A reader's snapshot: everything committed up to now is visible, everything later is not. */
    long snapshot() { return commits.get(); }
    /** The value this snapshot sees: the newest version at or before it. A reader never waits for a writer's
     *  transaction; the only wait is this key's monitor, held for the length of one list append. */
    String read(String key, long snapshot) {
        List<Version> chain = chains.get(key);
        if (chain == null) return null;
        String seen = null;
        synchronized (chain) {
            for (Version v : chain) if (v.at() <= snapshot) seen = v.deleted() ? null : v.value();
        }
        return seen;
    }
    /** Commit a new version. Readers already running keep reading the old one. */
    void write(String key, String value) { append(key, value, false); }
    /** Commit a deletion as a version, so a reader with an older snapshot still sees the row. */
    void delete(String key) { append(key, null, true); }
    private void append(String key, String value, boolean deleted) {
        List<Version> chain = chains.computeIfAbsent(key, k -> new ArrayList<>());
        synchronized (chain) { chain.add(new Version(commits.incrementAndGet(), value, deleted)); }
    }
    /** Drop versions no live snapshot can still need. This is the garbage collector MVCC buys you. */
    int vacuum(long oldestLiveSnapshot) {
        int dropped = 0;
        for (List<Version> chain : chains.values())
            synchronized (chain) {
                int keep = 0;
                for (int i = 0; i < chain.size(); i++) if (chain.get(i).at() <= oldestLiveSnapshot) keep = i;
                while (keep-- > 0) { chain.remove(0); dropped++; }
            }
        return dropped;
    }
}

// ---- ext: row-level locks -- the next rung, and the phantom it lets back in
/**
 * A lock per row instead of a lock per table: two transactions writing different rows of one table never wait.
 * The interface has to widen -- a key is now part of the request -- and one guarantee is lost: a table lock also
 * stopped rows from APPEARING, so with row locks a repeated range query can return a new row (a phantom) unless
 * the range itself is locked. Multi-key requests are taken in sorted order, which is how you avoid deadlock.
 */
final class KeyLocks {
    private final ConcurrentHashMap<String, ReentrantLock> locks = new ConcurrentHashMap<>();
    /** Take one row's lock, waiting at most timeoutMs. */
    boolean acquire(String table, Object pk, long timeoutMs) {
        ReentrantLock l = locks.computeIfAbsent(table + "#" + pk, k -> new ReentrantLock());
        try { return l.tryLock(timeoutMs, TimeUnit.MILLISECONDS); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
    }
    /** Give one row's lock back. */
    void release(String table, Object pk) { locks.get(table + "#" + pk).unlock(); }
    /** Take several rows in one agreed order, so two transactions wanting the same pair cannot deadlock. */
    boolean acquireAll(String table, List<Object> pks, long timeoutMs) {
        List<Object> sorted = new ArrayList<>(pks);
        sorted.sort((a, b) -> Index.cmp(a, b));
        List<Object> taken = new ArrayList<>();
        for (Object pk : sorted) {
            if (!acquire(table, pk, timeoutMs)) { for (Object done : taken) release(table, done); return false; }
            taken.add(pk);
        }
        return true;
    }
}

// ---- ext: sharding by primary key -- more locks by having more databases
/**
 * Split one table across n databases by the hash of its primary key. Each shard has its own lock, so throughput
 * multiplies by n for key lookups and writes. What it costs: a query that is not on the key has to ask every
 * shard and merge, and a transaction touching two shards needs two-phase commit -- so COMMIT can now fail.
 */
final class ShardedUsers {
    private final List<Database> shards = new ArrayList<>();
    /** @param n how many shards; each is a whole little database with its own tables and locks. */
    ShardedUsers(int n) {
        for (int i = 0; i < n; i++) {
            Database db = new Database();
            db.createTable("users", "id", Column.intCol("id", true), Column.text("name", true),
                Column.text("city", true), Column.intCol("age", false));
            db.table("users").createIndex("city");
            shards.add(db);
        }
    }
    /** Which shard owns this key. The whole routing rule, and it must never change without a migration. */
    Database shardFor(Object pk) { return shards.get(Math.floorMod(pk.hashCode(), shards.size())); }
    /** Insert: one shard, one lock. */
    void insert(long id, String name, String city, long age) { shardFor(id).insert("users", id, name, city, age); }
    /** Read by key: one shard, O(1), no fan-out. */
    Row get(long id) {
        List<Row> rows = shardFor(id).select("users", Where.eq("id", id));
        return rows.isEmpty() ? null : rows.get(0);
    }
    /** Anything not keyed by the primary key: ask every shard and merge. This is what sharding costs. */
    List<Row> byCity(String city) {
        List<Row> out = new ArrayList<>();
        for (Database db : shards) out.addAll(db.select("users", Where.eq("city", city)));
        return out;
    }
    /** Rows per shard, to show the spread. */
    List<Integer> sizes() {
        List<Integer> out = new ArrayList<>();
        for (Database db : shards) out.add(db.table("users").rowCount());
        return out;
    }
}

// ---- ext: isolation levels -- what strict two-phase locking gives you, and what each weaker level lets back in
/**
 * The three anomalies an interviewer names, each as a scenario you can run twice: once with the lock policy this
 * design ships with, once with no locking at all. A reader begins a transaction, counts the rows in Pune, lets a
 * writer loose, and counts again. Under StrictTableLocking the writer cannot have the table until the reader
 * commits, so both counts agree. Under NoLocking the writer lands in the middle of the reader and they differ.
 *
 * <p>The four SQL isolation levels, said in terms of this code. Every level keeps a table it WROTE locked to the
 * end; only the reads differ. READ UNCOMMITTED: reads take no lock, so you can see a write that is rolled back a
 * moment later (a dirty read). NoLocking is worse than any level: it drops the write locks too, so updates are lost.
 * READ COMMITTED: a table that was only READ is released at the end of the statement, which lets non-repeatable
 * reads back in. REPEATABLE READ keeps read locks to the end but on rows, not the table, so rows can still APPEAR
 * between two reads (a phantom). SERIALIZABLE is what Main already does: a table lock also stops inserts.
 */
final class Isolation {
    private Isolation() {}
    /** Which anomaly the scenario tries to produce. */
    enum Anomaly { DIRTY_READ, NON_REPEATABLE_READ, PHANTOM }
    /** One reader's two counts of the same query. Equal counts mean the anomaly did not happen. */
    record Reads(int first, int second) {
        /** True if the transaction saw the same database twice, which is the whole promise of isolation. */
        boolean stable() { return first == second; }
    }
    /**
     * Run one scenario under one lock policy and report what the reader counted before and after the writer ran.
     * Nothing here waits forever: the writer is given 300 ms to get in, which is all it needs when it can.
     */
    static Reads run(LockPolicy policy, Anomaly anomaly) throws Exception {
        Database db = Main.sample();
        db.configure(policy, 2000);
        db.insert("users", 1, "Asha", "Pune", 31);
        CountDownLatch started = new CountDownLatch(1), wrote = new CountDownLatch(1), readerDone = new CountDownLatch(1);
        Thread writer = new Thread(() -> {
            started.countDown();
            Txn w = db.begin();
            try {
                switch (anomaly) {
                    case DIRTY_READ           -> w.insert("users", 2, "Never", "Pune", 20);   // never committed
                    case NON_REPEATABLE_READ  -> w.update("users", Where.eq("id", 1), Map.of("city", "Kochi"));
                    case PHANTOM              -> w.insert("users", 2, "Bela", "Pune", 42);
                }
                if (anomaly != Anomaly.DIRTY_READ) w.commit();
            } catch (RuntimeException e) { /* it waited for the table and gave up: that is the lock doing its job */ }
            wrote.countDown();
            if (anomaly == Anomaly.DIRTY_READ) {
                try { readerDone.await(3, TimeUnit.SECONDS); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                w.rollback();                                         // so the row the reader may have seen never existed
            }
        });
        Txn reader = db.begin();
        int first = reader.select("users", Where.eq("city", "Pune")).size();
        writer.start();
        started.await();
        wrote.await(300, TimeUnit.MILLISECONDS);                      // under strict locking it cannot get in, and that is the point
        int second = reader.select("users", Where.eq("city", "Pune")).size();
        reader.commit();
        readerDone.countDown();
        writer.join(5000);
        return new Reads(first, second);
    }
    /** The same scenario as one line for a demo print. */
    static String describe(LockPolicy policy, String label, Anomaly anomaly) throws Exception {
        Reads r = run(policy, anomaly);
        return String.format("%-12s %-20s reader counted %d then %d  %s", label, anomaly, r.first(), r.second(),
            r.stable() ? "-- the same database twice" : "<-- " + anomaly + ": one transaction, two different databases");
    }
}

// ---- ext: TTL rows -- the injected clock, and why the sweeper is an ordinary transaction
/**
 * Rows that expire. Every row is stamped with the injected clock when it is written, so a sweeper can delete
 * everything older than a TTL -- and it does it with ordinary transactions, so the triggers, the indexes and the
 * undo log all behave exactly as they do for a hand-typed DELETE. A test moves the clock instead of sleeping.
 */
final class TtlSweeper {
    private final Database db;
    private final String table;
    private final long ttlMs;
    private final Clock clock;
    /** @param ttlMs how old a row may get; clock the same clock the database was handed. */
    TtlSweeper(Database db, String table, long ttlMs, Clock clock) { this.db = db; this.table = table; this.ttlMs = ttlMs; this.clock = clock; }
    /** Delete every row written longer ago than the TTL. Returns how many went. */
    int sweep() {
        long cutoff = clock.nowMs() - ttlMs;
        return db.delete(table, (s, r) -> r.atMs() < cutoff);          // a lambda predicate: the planner cannot read it, so it is a scan
    }
}

/** Runs every extension above so none of them can rot. Run it: java ExtDemo. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        Database db = Main.sample();
        db.table("orders").addRule(new ForeignKeyRule("user_id", "users"));
        db.table("users").addRule(new RestrictDeleteRule("orders", "user_id"));
        db.insert("users", 1, "Asha", "Pune", 31);
        db.insert("users", 2, "Bela", "Pune", 42);
        db.insert("users", 3, "Chandra", "Kochi", 27);
        db.insert("orders", 10, 1, 300, 20260901);
        db.insert("orders", 11, 2, 450, 20260902);
        db.insert("orders", 12, 1, 120, 20260903);

        System.out.println("-- foreign keys --------------------------------------------------");
        try { db.insert("orders", 13, 99, 10, 20260904); } catch (ConstraintViolation e) { System.out.println("refused: " + e.getMessage()); }
        try { db.delete("users", Where.eq("id", 1)); } catch (ConstraintViolation e) { System.out.println("refused: " + e.getMessage()); }
        System.out.println("orders: " + db.table("orders").rowCount() + " rows, users: " + db.table("users").rowCount() + " rows -- both refusals wrote nothing");

        System.out.println("\n-- an index added after the rows ---------------------------------");
        System.out.println(LateIndex.add(db, "users", "name"));

        System.out.println("\n-- EXPLAIN: two usable indexes, one of them cheaper --------------");
        Predicate both = Where.and(Where.eq("city", "Pune"), Where.eq("name", "Bela"));
        System.out.println("first usable : " + db.explain("users", both));
        Txn planning = db.begin();
        Plan best = CostPlanner.cheapest(planning.table("users"), both);
        System.out.println("cheapest     : " + best.how() + ", " + best.candidates().size() + " row(s) examined; rows found: "
            + CostPlanner.select(planning, "users", both).size());
        planning.commit();

        System.out.println("\n-- ORDER BY city, age DESC, and only two columns ------------------");
        Txn sorting = db.begin();
        System.out.println(OrderBy.select(sorting, "users", List.of("name", "age"), Where.all(), "city", "age DESC"));
        sorting.commit();

        System.out.println("\n-- joins ---------------------------------------------------------");
        Txn reading = db.begin();
        System.out.println("nested loop: " + Joins.nestedLoop(reading));
        System.out.println("hash join  : " + Joins.hashJoin(reading));
        System.out.println("same answer: " + Joins.nestedLoop(reading).equals(Joins.hashJoin(reading)));
        reading.commit();

        System.out.println("\n-- a write-ahead log, and replay ---------------------------------");
        Database live = Main.sample();
        WalLog wal = new WalLog();
        live.setLog(wal);
        live.insert("users", 1, "Asha", "Pune", 31);
        live.insert("users", 2, "Bela", "Pune", 42);
        live.update("users", Where.eq("id", 1), Map.of("city", "Kochi"));
        Txn doomed = live.begin();
        doomed.insert("users", 3, "Never", "Surat", 20);
        doomed.rollback();
        live.delete("users", Where.eq("id", 2));
        Database rebuilt = WalLog.replay(wal.lines(), Main.sample());
        System.out.println("log lines: " + wal.lines());
        System.out.println("rebuilt: " + rebuilt.table("users").rowCount() + " row(s), " + rebuilt.table("users").allRows().get(0).show(rebuilt.table("users").schema()));
        System.out.println("the rolled-back row is not in the log: " + wal.lines().stream().noneMatch(l -> l.contains("Never")));

        System.out.println("\n-- MVCC: a reader that does not wait ------------------------------");
        MvccStore mv = new MvccStore();
        mv.write("balance", "100");
        long reader = mv.snapshot();
        mv.write("balance", "999");
        System.out.println("the old reader still sees " + mv.read("balance", reader) + "; a new reader sees " + mv.read("balance", mv.snapshot()));
        mv.delete("balance");
        System.out.println("after a delete: old reader " + mv.read("balance", reader) + ", new reader " + mv.read("balance", mv.snapshot()));
        System.out.println("vacuum dropped " + mv.vacuum(mv.snapshot()) + " dead version(s)");

        System.out.println("\n-- row-level locks -----------------------------------------------");
        KeyLocks keys = new KeyLocks();
        CountDownLatch held = new CountDownLatch(1), done = new CountDownLatch(1);
        Thread other = new Thread(() -> { keys.acquire("users", 1L, 1000); held.countDown(); try { done.await(); } catch (InterruptedException e) { } keys.release("users", 1L); });
        other.start();
        held.await();
        System.out.println("row 1 is held by another transaction; row 2 free? " + keys.acquire("users", 2L, 200));
        System.out.println("row 1 free? " + keys.acquire("users", 1L, 200) + "  (with a table lock, both answers would be no)");
        keys.release("users", 2L);
        done.countDown(); other.join();

        System.out.println("\n-- sharding by primary key ---------------------------------------");
        ShardedUsers sharded = new ShardedUsers(4);
        for (long i = 1; i <= 100; i++) sharded.insert(i, "u" + i, i % 3 == 0 ? "Pune" : "Kochi", 20 + i % 40);
        System.out.println("rows per shard: " + sharded.sizes());
        System.out.println("by key, one shard: " + sharded.get(42).show(sharded.shardFor(42L).table("users").schema()));
        System.out.println("by city, all four shards: " + sharded.byCity("Pune").size() + " rows");

        System.out.println("\n-- isolation: the same three scenarios, with the lock and without -");
        for (Isolation.Anomaly a : Isolation.Anomaly.values()) System.out.println(Isolation.describe(new StrictTableLocking(), "strict 2PL", a));
        for (Isolation.Anomaly a : Isolation.Anomaly.values()) System.out.println(Isolation.describe(new NoLocking(), "no locking", a));

        System.out.println("\n-- TTL rows, with the clock moved by hand -------------------------");
        Database ttlDb = Main.sample();
        long[] now = { 1_700_000_000_000L };
        ttlDb.setClock(() -> now[0]);
        ttlDb.insert("users", 1, "Old", "Pune", 30);
        now[0] += 60_000;
        ttlDb.insert("users", 2, "New", "Pune", 30);
        TtlSweeper sweeper = new TtlSweeper(ttlDb, "users", 30_000, () -> now[0]);
        System.out.println("swept " + sweeper.sweep() + " row(s); left: " + ttlDb.table("users").allRows().get(0).show(ttlDb.table("users").schema()));
    }
}
