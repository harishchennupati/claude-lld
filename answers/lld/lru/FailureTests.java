import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Targeted failure tests: each one proves a claim the page makes (move 9 on page 02, and the follow-ups on
// page 05). Every claim that cannot be turned into a few lines here is not a claim, it is a hope.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }
    /** Wait for a latch inside a lambda, where a checked exception is not allowed. */
    static void await(CountDownLatch latch) {
        try { latch.await(); } catch (InterruptedException e) { throw new IllegalStateException(e); }
    }

    public static void main(String[] args) throws Exception {

        // 1. a read is a USE: the entry a caller just read must not be the one that leaves next.
        //    This is the bug that makes a cache evict exactly the keys it is busiest with.
        List<String> evicted = new ArrayList<>();
        LruCache<String, String> lru = new LruCache<>(3);
        lru.configure(k -> null, (k, v, c) -> evicted.add(c + ":" + k));
        lru.put("A", "1"); lru.put("B", "2"); lru.put("C", "3");
        check(lru.evictionOrder().equals(List.of("A", "B", "C")), "before any read, A is the next victim");
        lru.get("A");
        check(lru.evictionOrder().equals(List.of("B", "C", "A")), "after get(A), A is the LAST to go and B is next");
        lru.put("D", "4");
        check(lru.get("B") == null && lru.get("A") != null, "put(D) evicted B, not the key that had just been read");
        check(evicted.equals(List.of("CAPACITY:B")), "the listener was told exactly once, with the cause: " + evicted);
        check(lru.size() == 3 && lru.consistent(), "size is still 3 and the map and the list name the same keys");

        // 2. an overwrite is ONE node, not a second one: the classic bug that lets size drift past capacity.
        LruCache<String, String> once = new LruCache<>(2);
        once.put("k", "first"); once.put("k", "second"); once.put("k", "third");
        check(once.size() == 1, "three puts of one key leave one entry, not three");
        check("third".equals(once.get("k")), "and the value is the newest one");
        check(Collections.frequency(once.keysNewestFirst(), "k") == 1, "the key appears exactly once in the order list");
        check(once.consistent(), "the two indexes still agree after the overwrites");

        // 3. the edges: capacity 1 works, and a capacity of zero is refused at construction rather than
        //    producing a cache that silently keeps nothing.
        LruCache<String, String> one = new LruCache<>(1);
        one.put("A", "1"); one.put("B", "2");
        check(one.size() == 1 && one.get("A") == null && "2".equals(one.get("B")), "capacity 1: A left as B arrived");
        boolean refused = false;
        try { new LruCache<String, String>(0); } catch (IllegalArgumentException e) { refused = true; }
        check(refused, "capacity 0 is refused at construction");

        // 4. a loader that fails writes NOTHING, and the caller can retry. The load happens outside the lock and
        //    before any state change, which is why a database outage cannot leave a half-populated cache.
        boolean[] databaseDown = { true };
        int[] loads = { 0 };
        LruCache<String, String> readThrough = new LruCache<>(2);
        readThrough.configure(key -> {
            loads[0]++;
            if (databaseDown[0]) throw new IllegalStateException("database unreachable");
            return "row-" + key;
        }, (k, v, c) -> { });
        readThrough.put("keep", "me");
        boolean threw = false;
        try { readThrough.get("missing"); } catch (IllegalStateException e) { threw = true; }
        check(threw, "a loader that throws propagates instead of inventing a value");
        check(readThrough.size() == 1 && "me".equals(readThrough.get("keep")), "and the cache is exactly as it was");
        databaseDown[0] = false;
        check("row-missing".equals(readThrough.get("missing")), "the retry succeeds once the database is back");
        check(readThrough.size() == 2 && readThrough.consistent(), "and only then is the value resident");
        int before = loads[0];
        readThrough.get("missing");
        check(loads[0] == before, "the second read is a hit: the loader is not called again");

        // 5. fifty threads, twenty thousand distinct keys, one cache of a hundred. The proof is arithmetic:
        //    every key that went in either sits in the cache or was reported as evicted, exactly once. A lost
        //    update would leave the two numbers short; a double count would leave them over.
        final int threads = 50, perThread = 400, cap = 100;
        LruCache<String, String> hot = new LruCache<>(cap);
        AtomicInteger gone = new AtomicInteger();
        AtomicInteger overCapacity = new AtomicInteger();
        hot.configure(k -> null, (k, v, c) -> { if (c == EvictionCause.CAPACITY) gone.incrementAndGet(); });
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> running = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            final int id = t;
            running.add(pool.submit(() -> {
                go.await();
                for (int i = 0; i < perThread; i++) {
                    hot.put("t" + id + "-" + i, "v");
                    if (hot.size() > cap) overCapacity.incrementAndGet();   // sampled while the storm is running
                }
                return null;
            }));
        }
        go.countDown();
        for (Future<?> f : running) f.get();
        pool.shutdown();
        int inserted = threads * perThread;
        check(gone.get() + hot.size() == inserted, "evicted (" + gone.get() + ") + resident (" + hot.size()
            + ") = " + inserted + ": no entry was lost and none was counted twice");
        check(hot.size() == cap, "the cache is exactly full, not full-ish");
        check(overCapacity.get() == 0, "size was never observed above the capacity, not once in " + inserted + " puts");
        check(hot.consistent(), "after the race the map and the list still name exactly the same keys");

        // 6. an eviction listener that throws is a bystander, not a participant: it runs after the unlock, in a
        //    try/catch, so a broken write-back cannot leave the two indexes disagreeing.
        LruCache<String, String> withBadListener = new LruCache<>(2);
        withBadListener.configure(k -> null, (k, v, c) -> { throw new RuntimeException("the store is on fire"); });
        withBadListener.put("A", "1"); withBadListener.put("B", "2"); withBadListener.put("C", "3");
        check(withBadListener.size() == 2 && "3".equals(withBadListener.get("C")), "the put stood despite the throwing listener");
        check(withBadListener.consistent(), "and the cache is still consistent");

        // 7. TTL, on an injected clock: no test sleeps for a minute. A stale entry is a miss, it is unlinked on
        //    the read that found it, and the listener hears EXPIRED rather than CAPACITY.
        long[] now = { 1_700_000_000_000L };
        List<String> causes = new ArrayList<>();
        LruCache<String, String> ttl = new LruCache<>(10);
        ttl.setClock(() -> now[0]);
        ttl.setTtlMs(60_000);
        ttl.configure(k -> null, (k, v, c) -> causes.add(c.toString()));
        ttl.put("session", "abc");
        now[0] += 59_999;
        check("abc".equals(ttl.get("session")), "one millisecond before the minute is up, it is still a hit");
        now[0] += 2;
        check(ttl.get("session") == null, "one millisecond after, it is a miss");
        check(ttl.size() == 0, "and the entry was unlinked, not left to rot until the capacity pushed it out");
        check(causes.equals(List.of("EXPIRED")), "the listener was told the cause was EXPIRED: " + causes);

        // 8. LFU evicts the least-USED, and a tie between two equally-used entries is broken by RECENCY,
        //    because each frequency bucket is itself a recency list.
        LfuCache<String, String> lfu = new LfuCache<>(3);
        lfu.put("hot", "1"); lfu.put("warm", "2"); lfu.put("cold", "3");
        lfu.get("hot"); lfu.get("hot"); lfu.get("warm");
        check(lfu.frequencyOf("hot") == 3 && lfu.frequencyOf("warm") == 2 && lfu.frequencyOf("cold") == 1,
              "use counts are 3 / 2 / 1");
        lfu.put("new", "4");
        check(lfu.get("cold") == null && lfu.get("hot") != null, "the least-used entry left, not the oldest one");
        LfuCache<String, String> tie = new LfuCache<>(2);
        tie.put("first", "1"); tie.put("second", "2");
        tie.put("third", "3");
        check(tie.get("first") == null && tie.get("second") != null,
              "with both at one use, the LEAST RECENTLY used of them left");
        check(tie.consistent(), "every LFU node is in exactly one bucket and no bucket is left empty");

        // 9. an explicit remove must not leave the LFU cache pointing at a bucket that no longer exists --
        //    the one place where the smallest-use-count bookkeeping can go wrong.
        LfuCache<String, String> removed = new LfuCache<>(3);
        removed.put("a", "1"); removed.get("a"); removed.get("a");   // a is at use-count 3
        removed.put("b", "2");                                       // b is at 1, so the smallest count is 1
        removed.remove("b");                                         // ...and now nothing is at 1
        check(removed.consistent(), "after removing the only least-used entry the buckets are still coherent");
        removed.put("c", "3"); removed.put("d", "4");
        removed.put("e", "5");                                       // full: the least-used of c and d must go
        check(removed.get("c") == null && removed.get("a") != null,
              "the next eviction still picks the least-used entry, not a stale bucket");

        //    remove and expiry never repair the smallest count (that is what keeps them O(1)), so check the
        //    whole LFU against a brute-force one that finds every victim by a scan: 20,000 random operations.
        Random rnd = new Random(9);
        LfuCache<Integer, Integer> fast = new LfuCache<>(5);
        Map<Integer, long[]> slow = new HashMap<>();                 // key -> { uses, time of last use }
        long tick = 0; boolean same = true;
        for (int step = 0; step < 20_000 && same; step++) {
            int k = rnd.nextInt(12), op = rnd.nextInt(3); tick++;
            if (op == 0) { fast.get(k); long[] e = slow.get(k); if (e != null) { e[0]++; e[1] = tick; } }
            else if (op == 1) { fast.remove(k); slow.remove(k); }
            else {
                if (!slow.containsKey(k) && slow.size() == 5)        // least uses, then least recent: the scan
                    slow.remove(Collections.min(slow.keySet(), Comparator.comparingLong((Integer x) -> slow.get(x)[0])
                                                                      .thenComparingLong(x -> slow.get(x)[1])));
                long[] e = slow.get(k);
                if (e == null) slow.put(k, new long[] { 1, tick }); else { e[0]++; e[1] = tick; }
                fast.put(k, step);
            }
            same = new HashSet<>(fast.evictionOrder()).equals(slow.keySet()) && fast.consistent();
        }
        check(same, "20,000 random get/put/remove: the O(1) LFU always holds the same keys as the brute-force one");

        // 10. a scan must not be allowed to evict the working set. Plain LRU has no defence: every row of a
        //     one-off report is the most recently used entry the instant it arrives. Admission is the fix --
        //     the newcomer only gets in if it has been asked for more often than the entry it would displace.
        AdmissionLruCache<Integer, String> guarded = new AdmissionLruCache<>(50);
        LruCache<Integer, String> unguarded = new LruCache<>(50);
        for (int round = 0; round < 5; round++)                      // 40 real keys, asked for again and again
            for (int k = 0; k < 40; k++) {
                guarded.put(k, "hot"); guarded.get(k);
                unguarded.put(k, "hot"); unguarded.get(k);
            }
        for (int row = 10_000; row < 10_500; row++) { guarded.put(row, "scan"); unguarded.put(row, "scan"); }
        int keptGuarded = 0, keptPlain = 0;
        for (int k = 0; k < 40; k++) {
            if (guarded.get(k) != null) keptGuarded++;
            if (unguarded.get(k) != null) keptPlain++;
        }
        check(keptPlain == 0, "plain LRU: a 500-row scan evicted the entire 40-key working set");
        check(keptGuarded == 40, "with admission: all 40 stayed, because a row seen once cannot beat a key seen ten times");
        check(guarded.doorLog().startsWith("admitted=0 "), "not one scan row displaced a resident key: " + guarded.doorLog());
        check(guarded.size() == 50 && guarded.evictionOrder().size() == 50, "and the cache is still exactly full");

        // 11. a slow load must not undo a put that landed while it ran. The loader waits until the test has put
        //     a newer value, then comes back with the old row: the old row must not be written.
        ExecutorService side = Executors.newSingleThreadExecutor();
        CountDownLatch inLoader = new CountDownLatch(1), letGo = new CountDownLatch(1);
        LruCache<String, String> racing = new LruCache<>(4);
        racing.configure(k -> { inLoader.countDown(); await(letGo); return "old-row"; }, (k, v, c) -> { });
        Future<String> slowGet = side.submit(() -> racing.get("k"));
        inLoader.await();                                            // the get is in the loader, lock released
        racing.put("k", "newer");
        letGo.countDown();
        slowGet.get();
        check("newer".equals(racing.get("k")), "a put during a load wins: the load's older row was not written over it");

        // 12. ...and a load must not bring back a key removed while it ran (the row changed, the cache was told).
        String[] row = { "v1" };
        boolean[] blockFirstLoad = { true };
        CountDownLatch inLoad2 = new CountDownLatch(1), letGo2 = new CountDownLatch(1);
        LruCache<String, String> invalidated = new LruCache<>(4);
        invalidated.configure(k -> {
            String seen = row[0];
            if (blockFirstLoad[0]) { blockFirstLoad[0] = false; inLoad2.countDown(); await(letGo2); }
            return seen;
        }, (k, v, c) -> { });
        Future<String> firstGet = side.submit(() -> invalidated.get("k"));
        inLoad2.await();
        row[0] = "v2"; invalidated.remove("k");                      // the row changes and the cache is told
        letGo2.countDown();
        firstGet.get();                                              // it returns v1: it started before the change
        check("v2".equals(invalidated.get("k")), "a remove during a load is not undone: the next read loads v2");
        side.shutdown();

        // 13. the sweeper's heap is only a hint. A key rewritten after its first note survives that note, and a
        //     key that really expired is reported as EXPIRED, not REMOVED (write-back skips REMOVED).
        long[] now2 = { 0 };
        List<String> heard = new ArrayList<>();
        LruCache<String, String> swept = new LruCache<>(10);
        swept.setClock(() -> now2[0]); swept.setTtlMs(60_000);
        swept.configure(k -> null, (k, v, c) -> heard.add(c + " " + k));
        ExpirySweeper<String, String> sweeper = new ExpirySweeper<>(swept);
        swept.put("k", "v1"); sweeper.track("k", 60_000);             // due at 60s
        now2[0] = 50_000; swept.put("k", "v2"); sweeper.track("k", 110_000);   // rewritten: now due at 110s
        now2[0] = 61_000; sweeper.sweep(now2[0]);
        check("v2".equals(swept.get("k")), "the 60s note did not remove the value rewritten at 50s");
        now2[0] = 111_000; sweeper.sweep(now2[0]);
        check(swept.size() == 0 && heard.contains("EXPIRED k"), "at 111s it is gone and the listener heard EXPIRED: " + heard);

        // 14. write-back writes only what leaves for good. An overwritten value is out of date: writing it would
        //     put an old row in the store while the cache holds the new one.
        Map<String, String> store = new HashMap<>();
        LruCache<String, String> writeBack = new LruCache<>(1);
        writeBack.configure(k -> null, new WriteBackListener<>(store));
        writeBack.put("k", "old"); writeBack.put("k", "new");
        check(!store.containsKey("k"), "an overwrite wrote nothing: the store never saw the out-of-date value");
        writeBack.put("other", "x");                                 // capacity 1: k leaves for good now
        check("new".equals(store.get("k")), "the eviction wrote the newest value");

        // 15. two servers, one shared store. The versions come from ONE sequence, so the latest write wins
        //     whichever server made it, and a server that loses in the store never serves its own refused value.
        VersionedStore<String, String> shared = new VersionedStore<>();
        AtomicLong sequence = new AtomicLong();
        TwoTierCache<String, String> serverA = new TwoTierCache<>(new LruCache<>(4), shared, sequence::incrementAndGet);
        TwoTierCache<String, String> serverB = new TwoTierCache<>(new LruCache<>(4), shared, sequence::incrementAndGet);
        serverA.put("k", "a1"); serverA.put("k", "a2"); serverB.put("k", "b1");   // b1 is the latest write
        check("b1".equals(shared.read("k")) && "b1".equals(serverA.get("k")) && "b1".equals(serverB.get("k")),
              "the latest write won in the store, and both servers read it");
        TwoTierCache<String, String> delayed = new TwoTierCache<>(new LruCache<>(4), shared, () -> 1L);  // an old version, arriving late
        delayed.put("k", "stale");
        check("b1".equals(shared.read("k")) && "b1".equals(delayed.get("k")), "a late write with an old version loses, and its server serves the winner");
        check(!shared.write("k", "dup", sequence.get()), "a write carrying the version already stored does not claim to have won");

        // 16. expire-after-ACCESS: every use restarts the lifetime, so the least recently used entry is always
        //     the first to expire and a sweep only ever needs the tail.
        long[] now3 = { 0 };
        LruCache<String, String> idle = new LruCache<>(10);
        idle.setClock(() -> now3[0]); idle.setTtlMs(5_000, true);
        idle.put("a", "1"); idle.put("b", "2"); idle.put("c", "3");
        now3[0] = 4_000; idle.get("a");                              // a's five seconds start again
        now3[0] = 6_000;
        check(idle.sweepExpired() == 2 && idle.evictionOrder().equals(List.of("a")), "at 6s the sweep freed b and c from the tail; a was read at 4s");

        // 17. a store plus a pluggable policy: the same calls through LRU and through FIFO lose different keys.
        PolicyCache<String, String> lruPolicy = new PolicyCache<>(2, new HashMap<>(), ListPolicy.lru());
        PolicyCache<String, String> fifoPolicy = new PolicyCache<>(2, new HashMap<>(), ListPolicy.fifo());
        for (PolicyCache<String, String> pc : List.of(lruPolicy, fifoPolicy)) { pc.put("A", "1"); pc.put("B", "2"); pc.get("A"); pc.put("C", "3"); }
        check(lruPolicy.get("B") == null && lruPolicy.get("A") != null, "LRU: the read saved A, so B left");
        check(fifoPolicy.get("A") == null && fifoPolicy.get("B") != null, "FIFO: the read changed nothing, so A, first in, left");

        // 18. multi-level: a hit low down is copied into every faster level, and the time charged is every read
        //     tried plus every write made.
        MultiLevelCache<String, String> levels = new MultiLevelCache<>(List.of(
            new MultiLevelCache.Level<>("L1", new LruCache<>(1), 1, 2),
            new MultiLevelCache.Level<>("L2", new LruCache<>(2), 5, 10),
            new MultiLevelCache.Level<>("L3", new LruCache<>(4), 20, 40)), 5);
        check(levels.write("x", "1") == 78, "write x: 1+2 + 5+10 + 20+40 = 78 ms");
        levels.write("y", "2"); levels.write("z", "3");              // now x is only in L3
        MultiLevelCache.Read<String> found = levels.read("x");
        check("1".equals(found.value()) && found.ms() == 1 + 5 + 20 + 2 + 10, "read x: three reads, then copies into L1 and L2 = 38 ms");
        check(levels.write("x", "1") == 1, "writing the same value again stops at L1, which already has it: 1 ms");

        // 19. one fixed lifetime from the WRITE, and an O(1) average of the live values.
        long[] now4 = { 0 };
        ExpiringAverageCache<String> avg = new ExpiringAverageCache<>(10_000, () -> now4[0]);
        avg.put("a", 10); now4[0] = 1_000; avg.put("b", 20); now4[0] = 2_000; avg.put("c", 30);
        check(avg.average() == 20.0, "three live values average 20");
        now4[0] = 10_000;
        check(avg.average() == 25.0 && avg.get("a") == null, "at 10s a has expired: it left the map and the sum");
        avg.put("b", 40);                                            // an overwrite at 10s: b now lives to 20s
        now4[0] = 12_000;
        check(avg.average() == 40.0 && avg.get("c") == null, "at 12s c has expired; b's overwrite restarted its clock");

        // 20. a memo key must be equal for equal calls. The naive key compares arrays by identity and misses;
        //     CallKey compares them by content and sorts the named arguments.
        check(!Arrays.asList(new int[] { 1 }).equals(Arrays.asList(new int[] { 1 })), "the naive key: two equal arrays are not equal");
        int[] runs = { 0 };
        MemoCache<Integer> memo = new MemoCache<>(10, key -> ++runs[0]);
        Map<String, Object> ab = new LinkedHashMap<>(), ba = new LinkedHashMap<>();
        ab.put("a", 1); ab.put("b", 2); ba.put("b", 2); ba.put("a", 1);
        memo.call("f", new Object[] { new int[] { 1, 2 } }, ab);
        memo.call("f", new Object[] { new int[] { 1, 2 } }, ba);         // a new array, named args in another order
        check(runs[0] == 1, "equal arrays and reordered named arguments are one key: computed once");

        // 21. a write-ahead log: a restart rebuilds the entries AND the recency order, a line torn by a crash is
        //     cut off, and compaction keeps the same cache in fewer lines.
        Path wal = Files.createTempFile("lru-wal", ".log");
        try (LoggedLruCache first = new LoggedLruCache(2, wal)) {
            first.put("a", "1"); first.put("b", "2"); first.get("a"); first.put("c", "3");   // b leaves; a was used
        }
        Files.writeString(wal, "P\tz\thalf-writ", StandardOpenOption.APPEND);           // a crash mid-write
        try (LoggedLruCache second = new LoggedLruCache(2, wal)) {
            check(second.evictionOrder().equals(List.of("a", "c")), "after the restart: the same two entries in the same order");
            second.put("d", "4");                                                        // a is the oldest: it leaves
            check(second.evictionOrder().equals(List.of("c", "d")) && second.get("z") == null,
                  "the torn line was cut off and new records append cleanly");
            second.compact();
        }
        List<String> lines = Files.readAllLines(wal);
        try (LoggedLruCache third = new LoggedLruCache(2, wal)) {
            check(lines.size() == 2 && third.evictionOrder().equals(List.of("c", "d")), "compaction: two lines, same cache");
        }
        Files.deleteIfExists(wal);

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILURES");
        if (failures > 0) System.exit(1);
    }
}
