import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

// Targeted failure tests: each block proves a claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    public static void main(String[] args) throws Exception {
        ManualClock clock = new ManualClock(0);

        // 1. the seam is real: ONE access trace, four rules, four different victims. If a policy were
        //    hard-coded, or if the cache quietly ignored it, these four answers would not differ.
        String fifo = Main.replay(new FifoPolicy<>(), clock, 0);
        String lru = Main.replay(new LruPolicy<>(), clock, 0);
        String lfu = Main.replay(new LfuPolicy<>(), clock, 0);
        String ttl = Main.replay(new TtlPolicy<>(), clock, 0);
        check(fifo.startsWith("A"), "FIFO gives up the key that arrived first (A), however hot it is");
        check(lru.startsWith("B"), "LRU gives up the key nobody has touched for longest (B)");
        check(lfu.startsWith("C"), "LFU gives up the key with the fewest uses (C)");
        check(ttl.startsWith("D"), "shortest-fuse-first gives up the key that dies soonest (D)");
        check(new HashSet<>(List.of(fifo, lru, lfu, ttl)).size() == 4, "four rules, four different victims");

        // 2. evict BEFORE admitting. Under LRU both orders look identical; under LFU a newcomer arrives at one
        //    use, is instantly the coldest key, and an insert-then-evict cache would have it evict itself.
        PolicyCache<String, String> lfuCache = CacheBuilder.<String, String>newBuilder()
                .capacity(3).policy(new LfuPolicy<>()).clock(clock).build();
        lfuCache.put("a", "1"); lfuCache.put("b", "2"); lfuCache.put("c", "3");
        lfuCache.getIfPresent("a"); lfuCache.getIfPresent("b");        // a and b are at two uses, c at one
        lfuCache.put("d", "4");
        check(lfuCache.keys().contains("d"), "the newcomer is in the cache: it did not evict itself");
        check(!lfuCache.keys().contains("c"), "the coldest existing key (c) is the one that went");
        check(lfuCache.size() == 3, "size is still exactly the capacity");

        // 3. fifty threads on one cache: the size bound must hold at every instant, and the table and the
        //    policy must still name the same keys afterwards. Drift here means evicting a key that is not
        //    there (so nothing goes and the cache grows forever) or one that is (so the policy leaks).
        PolicyCache<Integer, Integer> hot = CacheBuilder.<Integer, Integer>newBuilder()
                .capacity(100).policy(new LruPolicy<>()).build();
        AtomicLong overflow = new AtomicLong();
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> all = new ArrayList<>();
        for (int t = 0; t < 50; t++) {
            final int seed = t;
            all.add(pool.submit(() -> {
                go.await();
                Random rnd = new Random(seed);
                for (int i = 0; i < 400; i++) {
                    int k = rnd.nextInt(500);
                    if ((i & 3) == 0) hot.put(k, k); else hot.getIfPresent(k);
                    if (hot.size() > hot.capacity()) overflow.incrementAndGet();
                }
                return null;
            }));
        }
        go.countDown();
        for (Future<?> f : all) f.get();
        pool.shutdown();
        check(overflow.get() == 0, "20000 concurrent operations: the cache was never over capacity");
        check(hot.size() == 100, "the cache is exactly full afterwards, not 99 and not 101");
        check(hot.consistent(), "the table and the policy track exactly the same number of keys");

        // 4. a twenty-four-hour TTL, tested in zero milliseconds. The clock is injected, so nothing sleeps
        //    and nothing is flaky; a wall-clock test of this would take a day.
        clock.setTo(1_700_000_000_000L);
        List<RemovalCause> causes = new ArrayList<>();
        PolicyCache<String, String> sessions = CacheBuilder.<String, String>newBuilder()
                .capacity(10).policy(new LruPolicy<>()).clock(clock)
                .listener((k, v, cause) -> causes.add(cause)).build();
        sessions.put("sid", "harish", 24 * 3600_000L);
        clock.advance(23 * 3600_000L);
        check("harish".equals(sessions.getIfPresent("sid")), "after 23 hours the entry is still served");
        clock.advance(2 * 3600_000L);
        check(sessions.getIfPresent("sid") == null, "after 25 hours the read is a miss, not a stale value");
        check(sessions.size() == 0, "the dead entry was dropped by the read that found it");
        check(causes.equals(List.of(RemovalCause.EXPIRED)), "and it was reported as EXPIRED");

        // 5. "why did my session disappear?" -- four ways out, four causes. A listener that is only told the
        //    key cannot tell a capacity bug from an expiry bug, and those are different bugs.
        Map<String, RemovalCause> why = new LinkedHashMap<>();
        clock.setTo(0);
        PolicyCache<String, String> causeCache = CacheBuilder.<String, String>newBuilder()
                .capacity(2).policy(new FifoPolicy<>()).clock(clock)
                .listener((k, v, cause) -> why.put(k + "=" + v, cause)).build();
        causeCache.put("explicit", "v1");
        causeCache.remove("explicit");
        causeCache.put("replaced", "old");
        causeCache.put("replaced", "new");
        causeCache.put("dies", "v2", 1_000);
        clock.advance(2_000);
        causeCache.getIfPresent("dies");
        causeCache.put("x", "v3"); causeCache.put("y", "v4"); causeCache.put("z", "v5");   // pushes one out
        check(why.get("explicit=v1") == RemovalCause.EXPLICIT, "remove(key) reports EXPLICIT");
        check(why.get("replaced=old") == RemovalCause.REPLACED, "a rewrite reports REPLACED, with the OLD value");
        check(why.get("dies=v2") == RemovalCause.EXPIRED, "a read past the deadline reports EXPIRED");
        check(why.containsValue(RemovalCause.CAPACITY), "the policy's victim reports CAPACITY");

        // 6. TTL as a DECORATOR over any policy: when something is already dead, that goes first; when
        //    nothing is dead, the wrapped rule decides and the wrapper is invisible.
        String plain = Main.replay(new LruPolicy<>(), clock, 4_000);
        String wrapped = Main.replay(new ExpiryFirst<>(new LruPolicy<>()), clock, 4_000);
        String wrappedLfu = Main.replay(new ExpiryFirst<>(new LfuPolicy<>()), clock, 4_000);
        String noneDead = Main.replay(new ExpiryFirst<>(new LruPolicy<>()), clock, 0);
        check(plain.startsWith("B") && plain.contains("CAPACITY"), "plain LRU gives up a live key while a dead one sits there");
        check(wrapped.startsWith("D") && wrapped.contains("EXPIRED"), "ExpiryFirst(LRU) takes the corpse instead, and says EXPIRED");
        check(wrappedLfu.startsWith("D"), "the same wrapper works over LFU: it is a decorator, not a fifth policy");
        check(noneDead.startsWith("B"), "with nobody dead the wrapper delegates and behaves exactly like LRU");

        // 7. swapping the rule at runtime. Every entry must survive; what does not survive is the ranking,
        //    because the new policy starts with no history -- and the test says so rather than hiding it.
        clock.setTo(0);
        List<String> lost = new ArrayList<>();
        PolicyCache<String, String> live = CacheBuilder.<String, String>newBuilder()
                .capacity(3).policy(new LruPolicy<>()).clock(clock)
                .listener((k, v, cause) -> lost.add(k)).build();
        live.put("x", "1"); live.put("y", "2"); live.put("z", "3");
        live.getIfPresent("x"); live.getIfPresent("x"); live.getIfPresent("y");     // LRU would now give up z
        EvictionPolicy<String> was = live.setPolicy(new LfuPolicy<>());
        check(was.name().equals("LRU") && live.policy().name().equals("LFU"), "the rule really changed, and the old one is returned");
        check(live.size() == 3 && live.keys().containsAll(List.of("x", "y", "z")), "every entry survived the swap");
        check(lost.isEmpty(), "nothing was evicted to make the swap happen");
        live.put("w", "4");
        check(lost.equals(List.of("x")), "the fresh LFU has no history, so x goes, not the z the old LRU had lined up");

        // 8. a listener is caller code. One that throws must not break a put; one that calls straight back
        //    into the cache must not deadlock. Both are safe only because listeners run after the unlock.
        clock.setTo(0);
        AtomicBoolean reentered = new AtomicBoolean(false);
        PolicyCache<String, String> guarded = CacheBuilder.<String, String>newBuilder()
                .capacity(2).policy(new LruPolicy<>()).clock(clock).build();
        guarded.addListener((k, v, cause) -> { throw new IllegalStateException("this listener is broken"); });
        guarded.addListener((k, v, cause) -> {
            if (cause == RemovalCause.CAPACITY) { reentered.set(true); guarded.remove("canary"); }
        });
        guarded.put("canary", "alive");
        guarded.put("p", "1");
        guarded.put("q", "2");                                     // full: something is evicted, both listeners run
        check(true, "a listener that throws did not stop the put from completing");
        check(reentered.get(), "the second listener still ran after the first one threw");
        check(guarded.size() <= guarded.capacity() && guarded.consistent(),
              "a listener that called back into the cache neither deadlocked nor left it inconsistent");

        // 9. the counters. A dead read is a miss and an expiration, never a hit; an eviction is counted once.
        clock.setTo(0);
        PolicyCache<String, String> counted = CacheBuilder.<String, String>newBuilder()
                .capacity(2).policy(new LruPolicy<>()).clock(clock).build();
        counted.getIfPresent("a");                                 // miss 1
        counted.put("a", "1");
        counted.getIfPresent("a");                                 // hit 1
        counted.put("b", "2");
        counted.put("c", "3");                                     // full: a is evicted
        counted.getIfPresent("a");                                 // miss 2
        CacheStats s = counted.stats();
        check(s.hits() == 1 && s.misses() == 2, "one hit and two misses, counted outside the lock");
        check(s.evictions() == 1, "exactly one eviction, not one per key touched");
        check(Math.abs(s.hitRate() - 1.0 / 3) < 1e-9, "the hit rate is hits / (hits + misses)");

        // 10. writes. Write-through must not cache a value the store refused; write-back is a listener whose
        //     whole logic is the CAUSE -- CAPACITY and EXPIRED carry the newest value out of memory and must be
        //     flushed, while REPLACED and EXPLICIT must not be.
        clock.setTo(0);
        PolicyCache<String, String> wtInner = CacheBuilder.<String, String>newBuilder()
                .capacity(4).policy(new LruPolicy<>()).clock(clock).build();
        WriteThroughCache<String, String> wt = new WriteThroughCache<>(
                wtInner, (k, v) -> { throw new IllegalStateException("the database is down"); });
        try { wt.put("x", "1"); check(false, "a store that throws must reach the caller, not be swallowed"); }
        catch (IllegalStateException expected) { check(true, "a store that throws reaches the caller"); }
        check(wtInner.getIfPresent("x") == null, "a value the store refused was never cached: no lie to read back");

        Map<String, String> store = new LinkedHashMap<>();
        WriteBackListener<String, String> back = new WriteBackListener<>(store::put);
        PolicyCache<String, String> behind = CacheBuilder.<String, String>newBuilder()
                .capacity(2).policy(new LruPolicy<>()).clock(clock).listener(back).build();
        behind.put("a", "old");
        behind.put("a", "new");                                    // REPLACED: superseded, so not news
        check(store.isEmpty(), "an overwritten value is not written back: the newer one is still in the cache");
        behind.put("b", "1");
        behind.put("c", "1");                                      // full: a leaves by CAPACITY
        check("new".equals(store.get("a")) && back.flushes() == 1,
              "the value the policy carried out of memory reached the store, exactly once");
        behind.remove("c");
        check(back.flushes() == 1, "an explicit remove is the caller forgetting, not a flush");

        PolicyCache<String, String> dirty = CacheBuilder.<String, String>newBuilder()
                .capacity(4).policy(new LruPolicy<>()).clock(clock).listener(back).build();
        dirty.put("d", "unsaved", 1_000);
        clock.advance(2_000);
        check(dirty.getIfPresent("d") == null, "past its deadline the entry is gone from the cache");
        check("unsaved".equals(store.get("d")), "a value the clock carried out of memory still reached the store");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILURES");
        if (failures > 0) System.exit(1);
    }
}
