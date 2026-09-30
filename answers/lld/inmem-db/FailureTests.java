import java.util.*;
import java.util.concurrent.*;

// Targeted failure tests: each one proves a claim the design makes on page 02 (move 9) or in a follow-up on page 05.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }
    /** The value of one column of one row, for a short assertion. */
    static Object v(Database db, String table, Object pk, String col) {
        Row r = db.table(table).row(pk);
        return r == null ? null : r.get(db.table(table).schema(), col);
    }
    /** Every primary key the index on that column currently points at, over the whole index. */
    static Set<Object> indexed(Database db, String table, String col) {
        Set<Object> out = new LinkedHashSet<>();
        Index ix = db.table(table).index(col);
        for (Row r : db.table(table).allRows()) out.addAll(ix.eq(r.get(db.table(table).schema(), col)));
        return out;
    }

    public static void main(String[] args) throws Exception {

        // 1. fifty threads insert the SAME primary key at the same instant, and fifty more insert fifty distinct
        //    keys: exactly one winner on the contested key, exact counts everywhere, and every index in step.
        Database race = Main.sample();
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Boolean>> same = new ArrayList<>(), distinct = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final int n = i;
            same.add(pool.submit(() -> { go.await(); return Main.tryInsert(race, "users", 7L, "racer" + n, "Pune", 30L); }));
            distinct.add(pool.submit(() -> { go.await(); return Main.tryInsert(race, "orders", 1000L + n, 7L, 50L, 20260901L); }));
        }
        go.countDown();
        int wonSame = 0, wonDistinct = 0;
        for (Future<Boolean> f : same) if (f.get()) wonSame++;
        for (Future<Boolean> f : distinct) if (f.get()) wonDistinct++;
        pool.shutdown();
        check(wonSame == 1, "exactly one of 50 transactions was told it inserted the contested key (was " + wonSame + ")");
        check(race.table("users").rowCount() == 1, "and exactly one row carries that key");
        check(wonDistinct == 50 && race.table("orders").rowCount() == 50, "50 distinct keys: 50 accepted, 50 rows, nothing lost");
        check(race.table("orders").index("user_id").eq(7L).size() == 50, "the secondary index holds all 50 primary keys");
        check(indexed(race, "orders", "placed_at").size() == 50, "the second index holds them too: no index drifted from the rows");

        // 2. a duplicate primary key is refused, and the refusal changes nothing at all
        Database db = Main.sample();
        db.insert("users", 1, "Asha", "Pune", 31);
        db.insert("users", 2, "Bela", "Kochi", 42);
        int rowsBefore = db.table("users").rowCount();
        try {
            db.insert("users", 1, "Impostor", "Surat", 20);
            check(false, "a duplicate primary key must be refused");
        } catch (ConstraintViolation e) { check(true, "duplicate primary key refused: " + e.getMessage()); }
        check(db.table("users").rowCount() == rowsBefore, "the refused insert added no row");
        check("Asha".equals(v(db, "users", 1L, "name")), "and it did not overwrite the row that was already there");
        check(db.table("users").index("city").eq("Surat").isEmpty(), "and it left nothing behind in any index");

        // 3. a wrong type, a null in a NOT NULL column and a failed CHECK are all refused before the lock is taken
        try { db.insert("users", 3, "Chandra", "Kochi", "twenty-seven"); check(false, "a wrong type must be refused"); }
        catch (ConstraintViolation e) { check(true, "wrong type refused: " + e.getMessage()); }
        try { db.insert("users", 4, "Devi", null, 30); check(false, "a null in a NOT NULL column must be refused"); }
        catch (ConstraintViolation e) { check(true, "NOT NULL refused: " + e.getMessage()); }
        try { db.insert("users", 5, "Ekta", "Pune", 900); check(false, "a failed CHECK must be refused"); }
        catch (ConstraintViolation e) { check(true, "CHECK refused: " + e.getMessage()); }
        try { db.insert("users", 6, "Farid"); check(false, "the wrong number of values must be refused"); }
        catch (ConstraintViolation e) { check(true, "wrong arity refused: " + e.getMessage()); }
        check(db.table("users").rowCount() == 2, "four refused inserts, still two rows");
        check(!db.table("users").lock().isLocked(), "and the table is not left locked by any of them");

        // 4. an update that changes an indexed column moves the row in that index: old key gone, new key there
        db.insert("users", 3, "Chandra", "Kochi", 27);
        db.update("users", Where.eq("id", 1), Map.of("city", "Surat", "age", 32));
        check(db.select("users", Where.eq("city", "Pune")).isEmpty(), "the old index key no longer finds the row");
        check(db.select("users", Where.eq("city", "Surat")).size() == 1, "the new index key does");
        check(db.select("users", Where.between("age", 32, 32)).size() == 1, "the range index moved with it");
        check((Long) v(db, "users", 1L, "age") == 32L && "Asha".equals(v(db, "users", 1L, "name")),
              "the columns that were not in the SET are untouched");
        try { db.update("users", Where.eq("id", 1), Map.of("id", 99)); check(false, "editing a primary key must be refused"); }
        catch (ConstraintViolation e) { check(true, "editing a primary key refused: " + e.getMessage()); }

        // 5. a range query answered by the TreeMap index returns exactly what a full scan would, in key order
        Database ages = Main.sample();
        for (int i = 1; i <= 40; i++) ages.insert("users", i, "u" + i, "Pune", 20 + i);
        List<Row> byIndex = ages.select("users", Where.between("age", 30, 35));
        List<Long> scan = new ArrayList<>();
        for (Row r : ages.table("users").allRows()) {
            long a = (Long) r.get(ages.table("users").schema(), "age");
            if (a >= 30 && a <= 35) scan.add(a);
        }
        List<Long> got = new ArrayList<>();
        for (Row r : byIndex) got.add((Long) r.get(ages.table("users").schema(), "age"));
        Collections.sort(scan);
        check(got.equals(scan) && got.size() == 6, "the range index returns the same 6 rows a scan would, in key order: " + got);
        check(ages.explain("users", Where.between("age", 30, 35)).startsWith("index range"), "and it says so: " + ages.explain("users", Where.between("age", 30, 35)));
        check(ages.explain("users", Where.eq("id", 5)).startsWith("primary key lookup"), "a primary key query is one hash lookup, not a scan");
        check(ages.explain("users", Where.eq("name", "u5")).startsWith("full scan"), "an unindexed column is a scan, and the planner admits it");
        boolean backwardsIsEmpty;
        try { backwardsIsEmpty = ages.select("users", Where.between("age", 35, 30)).isEmpty(); }
        catch (RuntimeException e) { backwardsIsEmpty = false; }
        check(backwardsIsEmpty, "a range written backwards (35 to 30) finds nothing, as a scan would, instead of throwing");

        // 6. a delete removes the row from the primary key map AND from every secondary index
        ages.delete("users", Where.eq("id", 11));                       // age 31, inside the range above
        check(ages.table("users").row(11L) == null, "the deleted row is gone from the primary key map");
        check(ages.select("users", Where.between("age", 30, 35)).size() == 5, "and out of the range index");
        check(ages.table("users").index("city").eq("Pune").size() == 39, "and out of the equality index");
        check(indexed(ages, "users", "age").size() == 39, "no index still points at a row that is not there");

        // 7. ROLLBACK puts everything back, including deleted rows, and a savepoint rolls back only part of it
        Database tx = Main.sample();
        tx.insert("users", 1, "Asha", "Pune", 31);
        tx.insert("users", 2, "Bela", "Kochi", 42);
        Txn t = tx.begin();
        t.insert("users", 3, "Chandra", "Surat", 27);
        int sp = t.savepoint();
        t.delete("users", Where.eq("id", 1));
        t.update("users", Where.eq("id", 2), Map.of("city", "Surat"));
        check(t.select("users", Where.eq("city", "Surat")).size() == 2, "inside the transaction the writes are visible to it");
        t.rollbackTo(sp);
        check(t.select("users", Where.all()).size() == 3, "ROLLBACK TO SAVEPOINT put the deleted row back");
        check("Kochi".equals(v(tx, "users", 2L, "city")), "and undid the update, but kept the insert before the savepoint");
        t.rollback();
        check(tx.table("users").rowCount() == 2, "ROLLBACK undid the rest: the insert is gone");
        check("Asha".equals(v(tx, "users", 1L, "name")) && "Kochi".equals(v(tx, "users", 2L, "city")), "every row is exactly as it was");
        check(tx.select("users", Where.eq("city", "Surat")).isEmpty() && tx.select("users", Where.eq("city", "Pune")).size() == 1,
              "and every index is exactly as it was");
        check(t.state() == TxnState.ROLLED_BACK, "the transaction says so");
        try { t.insert("users", 9, "Late", "Pune", 20); check(false, "a finished transaction must not accept more work"); }
        catch (IllegalStateException e) { check(true, "a finished transaction refuses more work: " + e.getMessage()); }

        // 8. a trigger that throws cannot break the commit, cannot stop the other triggers, and never sees a rolled-back row
        Database trg = Main.sample();
        AuditTrigger audit = new AuditTrigger();
        SafeTrigger broken = trg.addTrigger(batch -> { throw new RuntimeException("the index rebuilder is down"); });
        trg.addTrigger(audit);
        trg.insert("users", 1, "Asha", "Pune", 31);
        Txn doomed = trg.begin();
        doomed.insert("users", 2, "Never", "Surat", 20);
        doomed.rollback();
        trg.insert("users", 3, "Chandra", "Kochi", 27);
        check(trg.table("users").rowCount() == 2, "the commits went through although a trigger threw every time");
        check(broken.failures() == 2, "the broken trigger's failures are counted, not swallowed: " + broken.failures());
        check(audit.lines().size() == 2, "the trigger AFTER the broken one still saw both batches");
        check(audit.lines().toString().contains("Asha") && !audit.lines().toString().contains("Never"),
              "and it never saw the row that was rolled back");
        Database busy = Main.sample();
        AuditTrigger heard = new AuditTrigger();
        busy.addTrigger(heard);
        ExecutorService eight = Executors.newFixedThreadPool(8);
        List<Future<?>> writers = new ArrayList<>();
        for (int w = 0; w < 8; w++) {
            final long base = w * 1000L;
            writers.add(eight.submit(() -> { for (long i = 0; i < 400; i++) busy.insert("orders", base + i, 1L, 10L, 20260901L); return null; }));
        }
        for (Future<?> f : writers) f.get();
        eight.shutdown();
        check(heard.lines().size() == 3200 && busy.triggerFailures() == 0,
              "8 threads, 3,200 commits: the trigger, called from all of them at once, kept every line (" + heard.lines().size() + ")");

        // 9. a deadlock: two transactions take two tables in opposite orders; one is aborted and leaves nothing behind
        Database dl = Main.sample();
        dl.configure(new StrictTableLocking(), 300);
        CyclicBarrier both = new CyclicBarrier(2);
        ExecutorService pair = Executors.newFixedThreadPool(2);
        Future<String> a = pair.submit(() -> Main.cross(dl, both, "users", 100L, "orders", 100L, 0));
        Future<String> b = pair.submit(() -> Main.cross(dl, both, "orders", 101L, "users", 101L, 100));
        String ra = a.get(5, TimeUnit.SECONDS), rb = b.get(5, TimeUnit.SECONDS);
        pair.shutdown();
        int committed = (ra.startsWith("committed") ? 1 : 0) + (rb.startsWith("committed") ? 1 : 0);
        int rows = dl.table("users").rowCount() + dl.table("orders").rowCount();
        check(ra.startsWith("gave up") || rb.startsWith("gave up"), "the deadlock was broken by a timeout, not by hanging");
        check(rows == committed * 2, "every row present belongs to a transaction that committed (" + rows + " rows, " + committed + " committed)");
        check(!dl.table("users").lock().isLocked() && !dl.table("orders").lock().isLocked(), "and both tables were released by the loser");

        // 10. the isolation the lock buys: inside one transaction, two identical reads see the same database --
        //     no value changes under it, no row appears in it. The same code with no locking shows all three anomalies.
        for (Isolation.Anomaly anomaly : Isolation.Anomaly.values())
            check(Isolation.run(new StrictTableLocking(), anomaly).stable(), "strict two-phase locking: no " + anomaly);
        check(Isolation.run(new NoLocking(), Isolation.Anomaly.DIRTY_READ).second() == 2,
              "with no locking the reader sees a row from a transaction that never committed (a dirty read)");
        check(Isolation.run(new NoLocking(), Isolation.Anomaly.NON_REPEATABLE_READ).second() == 0,
              "with no locking the row it just read moves out from under it (a non-repeatable read)");
        check(Isolation.run(new NoLocking(), Isolation.Anomaly.PHANTOM).second() == 2,
              "with no locking a new row appears inside its range (a phantom)");

        // 11. a statement is all or nothing, even inside a transaction: an UPDATE refused on its second row puts the
        //     first row back, and the transaction stays open, so a COMMIT after it saves nothing half done
        Database st = Main.sample();
        st.table("users").addRule(new CheckRule((s, r) -> !("Surat".equals(r.get(s, "city")) && (Long) r.get(s, "age") > 40),
                                                "nobody over 40 lives in Surat"));
        st.insert("users", 1, "Asha", "Pune", 31);
        st.insert("users", 2, "Bela", "Pune", 42);
        Txn move = st.begin();
        try { move.update("users", Where.eq("city", "Pune"), Map.of("city", "Surat")); check(false, "the second row must be refused"); }
        catch (ConstraintViolation e) { check(true, "the UPDATE was refused on its second row: " + e.getMessage()); }
        move.commit();
        check("Pune".equals(v(st, "users", 1L, "city")), "the first row, already changed, was put back before the COMMIT");
        check(st.select("users", Where.eq("city", "Pune")).size() == 2 && st.select("users", Where.eq("city", "Surat")).isEmpty(),
              "and the city index agrees: two in Pune, none in Surat");

        // 12. the commit log is written while the tables are held, so its order is the commit order even when the
        //     first committer's disk is slow, and replaying it rebuilds the live database. A failed append fails the COMMIT.
        Database live = Main.sample();
        live.configure(new StrictTableLocking(), 2000);
        WalLog wal = new WalLog();
        CountDownLatch secondDone = new CountDownLatch(1), firstHolds = new CountDownLatch(1);
        live.setLog(batch -> {
            if (batch.get(0).kind() == ChangeKind.INSERT)      // the first commit's disk is slow: it waits, up to 300 ms
                try { secondDone.await(300, TimeUnit.MILLISECONDS); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            wal.append(batch);
        });
        Thread first = new Thread(() -> { Txn t1 = live.begin(); t1.insert("users", 5, "Asha", "Pune", 31); firstHolds.countDown(); t1.commit(); });
        Thread second = new Thread(() -> {
            try { firstHolds.await(); } catch (InterruptedException e) { return; }
            live.update("users", Where.eq("id", 5), Map.of("city", "Kochi"));   // waits for the table, then commits
            secondDone.countDown();
        });
        first.start(); second.start(); first.join(5000); second.join(5000);
        Database rebuilt = WalLog.replay(wal.lines(), Main.sample());
        check("Kochi".equals(v(live, "users", 5L, "city")) && wal.lines().size() == 2 && wal.lines().get(0).startsWith("INSERT"),
              "the log holds the insert before the update, the order they committed in: " + wal.lines());
        check("Kochi".equals(v(rebuilt, "users", 5L, "city")), "and replaying it rebuilds the same row: " + rebuilt.table("users").allRows().get(0).show(rebuilt.table("users").schema()));
        Database full = Main.sample();
        full.setLog(batch -> { throw new IllegalStateException("disk full"); });
        try { full.insert("users", 1, "Asha", "Pune", 31); check(false, "a commit whose log append failed must not succeed"); }
        catch (IllegalStateException e) { check(true, "the log append failed, so the COMMIT failed: " + e.getMessage()); }
        check(full.table("users").rowCount() == 0 && !full.table("users").lock().isLocked(), "and the row was rolled back and the table released");

        // 13. two usable indexes: the cost-based planner takes the one that examines fewer rows
        Database cp = Main.sample();
        cp.table("users").createIndex("name");
        cp.insert("users", 1, "Asha", "Pune", 31);
        cp.insert("users", 2, "Bela", "Pune", 42);
        cp.insert("users", 3, "Chandra", "Kochi", 27);
        int[] examined = { 0 };
        Predicate counted = Where.and((s, r) -> { examined[0]++; return true; }, Where.eq("city", "Pune"), Where.eq("name", "Bela"));
        Txn q = cp.begin();
        List<Row> found = CostPlanner.select(q, "users", counted);
        q.commit();
        check(found.size() == 1 && examined[0] == 1,
              "city = Pune AND name = Bela examined " + examined[0] + " row through the name index, not 2 through the city index");

        // 14. ORDER BY two columns, one of them descending, then only the columns asked for
        Database ob = Main.sample();
        ob.insert("users", 1, "Asha", "Pune", 31);
        ob.insert("users", 2, "Bela", "Pune", 42);
        ob.insert("users", 3, "Chandra", "Kochi", 27);
        ob.insert("users", 4, "Devi", "Kochi", 55);
        Txn sorted = ob.begin();
        List<List<Object>> names = OrderBy.select(sorted, "users", List.of("name"), Where.all(), "city", "age DESC");
        List<List<Object>> byAge = OrderBy.select(sorted, "users", List.of("age"), Where.between("age", 30, 60), "age");
        sorted.commit();
        check(names.equals(List.of(List.of("Devi"), List.of("Chandra"), List.of("Bela"), List.of("Asha"))),
              "ORDER BY city, age DESC, name only: Kochi before Pune, the older first in each: " + names);
        check(byAge.equals(List.of(List.of(31L), List.of(42L), List.of(55L))), "a range read through the age index, ordered by age: " + byAge);

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
