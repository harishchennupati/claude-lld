import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

/**
 * Thirteen claims from page 02, move 9, each proved here. Time is injected everywhere except the tests
 * whose whole point is that real threads really run, and every wait has a deadline, so a broken design
 * fails a test instead of hanging it. The whole file finishes in under a second.
 */
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }

    /** Wait for a condition instead of sleeping a guessed number of milliseconds. Never waits forever. */
    static boolean waitUntil(BooleanSupplier condition, long timeoutMs) {
        long end = System.nanoTime() + timeoutMs * 1_000_000L;
        while (!condition.getAsBoolean()) {
            if (System.nanoTime() > end) return false;
            try { Thread.sleep(1); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); return false; }
        }
        return true;
    }

    public static void main(String[] args) throws Exception {

        // 1. an expired value is never handed back, and the read that finds it dead reclaims it
        ManualClock clock = new ManualClock();
        TtlCache<String, String> c = new TtlCache<>(100);
        c.configure(new FixedTtl<>(100), clock);
        List<RemovalCause> seen = Collections.synchronizedList(new ArrayList<>());
        c.addListener((k, v, cause) -> seen.add(cause));

        c.put("k", "v1");
        check("v1".equals(c.get("k")), "a fresh value reads back");
        clock.advance(99);
        check("v1".equals(c.get("k")), "one millisecond before the deadline it is still served");
        clock.advance(1);
        check(c.get("k") == null, "at the deadline the value is gone: an expired value is never returned");
        check(c.size() == 0, "the read that found it dead reclaimed the entry, so nothing leaks");
        check(seen.equals(List.of(RemovalCause.EXPIRED)), "and the listener heard EXPIRED exactly once");

        // a TTL of zero means do not cache: the caller still gets a value, the cache stores nothing
        TtlCache<String, String> nocache = new TtlCache<>(0);
        nocache.configure(new FixedTtl<>(0), clock);
        AtomicInteger zeroLoads = new AtomicInteger();
        for (int i = 0; i < 5; i++)
            nocache.getOrLoad("k", key -> { zeroLoads.incrementAndGet(); return "fresh"; });
        check(zeroLoads.get() == 5 && nocache.size() == 0, "TTL 0 means do not cache: 5 calls, 5 loads, 0 entries");
        nocache.put("k", "v");
        check(nocache.size() == 0, "and put with TTL 0 stores nothing rather than storing something born dead");

        // 2. the sweeper reclaims what died and leaves every live entry exactly where it was
        ManualClock clock2 = new ManualClock();
        TtlCache<String, String> c2 = new TtlCache<>(1_000);
        c2.configure(key -> key.startsWith("short") ? 50 : 5_000, clock2);
        c2.put("short1", "a"); c2.put("short2", "b"); c2.put("long1", "c"); c2.put("long2", "d");
        clock2.advance(100);
        check(c2.sweepOnce() == 2, "one pass reclaimed exactly the two entries that died");
        check(c2.size() == 2 && c2.liveSize() == 2, "the two live entries are untouched");
        check("c".equals(c2.get("long1")) && "d".equals(c2.get("long2")), "and they still read back correctly");
        check(c2.sweepOnce() == 0, "a second pass over the same map removes nothing");

        // 3. the identity check: a value refreshed while the sweeper was looking at the old one survives.
        //    The injected clock is the seam: the sweeper reads the clock between picking the entry up and
        //    removing it, so a clock that writes at that instant reproduces the race exactly, every run.
        ManualClock clock3 = new ManualClock();
        TtlCache<String, String> c3 = new TtlCache<>(100);
        AtomicBoolean armed = new AtomicBoolean(false);
        c3.configure(new FixedTtl<>(100), () -> {
            long now = clock3.nowMs();
            if (armed.compareAndSet(true, false)) c3.put("k", "refreshed");   // the concurrent write
            return now;
        });
        c3.put("k", "stale");
        clock3.advance(200);                     // "stale" is now past its deadline
        armed.set(true);                         // the refresh lands inside the sweeper's own clock read
        check(c3.sweepOnce() == 0, "the sweeper removed nothing: the entry it held was not the entry in the map");
        check("refreshed".equals(c3.get("k")), "the refreshed value survived a sweep already looking at that key");
        check(c3.sweptCount.sum() == 0, "and nothing was reported as swept");

        // the same race on the read path: get() must compare-and-remove, not remove by key
        ManualClock clock4 = new ManualClock();
        TtlCache<String, String> c4 = new TtlCache<>(100);
        AtomicBoolean armed2 = new AtomicBoolean(false);
        c4.configure(new FixedTtl<>(100), () -> {
            long now = clock4.nowMs();
            if (armed2.compareAndSet(true, false)) c4.put("k", "refreshed");
            return now;
        });
        c4.put("k", "stale");
        clock4.advance(200);
        armed2.set(true);
        check(c4.get("k") == null, "the reader that found a dead entry reports a miss, as it should");
        check("refreshed".equals(c4.get("k")), "but it did not delete the value another thread had just written");

        // 4. fifty threads miss one cold key at the same instant: the loader runs exactly once.
        //    The loader does not return until all forty-nine losers are provably waiting on it, so the
        //    count is the same on a fast laptop and a loaded build box.
        ExecutorService pool = Executors.newFixedThreadPool(50);
        TtlCache<String, String> hot = new TtlCache<>(60_000);
        hot.configure(new FixedTtl<>(60_000), new SystemClock());
        AtomicInteger calls = new AtomicInteger();
        Loader<String, String> slow = key -> {
            calls.incrementAndGet();
            waitUntil(() -> hot.joins.sum() >= 49, 15_000);      // every other thread is now inside the wait
            return "row-" + key;
        };
        CountDownLatch go = new CountDownLatch(1);
        List<Future<String>> answers = new ArrayList<>();
        for (int i = 0; i < 50; i++)
            answers.add(pool.submit(() -> { go.await(); return hot.getOrLoad("user:42", slow); }));
        go.countDown();
        Set<String> distinct = new HashSet<>();
        for (Future<String> f : answers) distinct.add(f.get(30, TimeUnit.SECONDS));
        check(calls.get() == 1, "50 threads, one cold key, exactly 1 call to the loader (was " + calls.get() + ")");
        check(distinct.equals(Set.of("row-user:42")), "and all 50 threads got the same value");
        check(hot.joins.sum() == 49, "the other 49 rode the winner's result instead of loading");
        check(hot.size() == 1, "and exactly one entry was stored");

        // 5. the claim is per key, not one global gate: ten cold keys mean ten loads, and they overlap.
        //    All ten loaders are inside the loader at the same moment here -- that is what lets the
        //    barrier below be reached at all -- so this also proves nothing serialises across keys.
        TtlCache<String, String> many = new TtlCache<>(60_000);
        many.configure(new FixedTtl<>(60_000), new SystemClock());
        AtomicInteger keyCalls = new AtomicInteger();
        Loader<String, String> counted = key -> {
            keyCalls.incrementAndGet();
            waitUntil(() -> many.joins.sum() >= 40, 15_000);
            return "v-" + key;
        };
        CountDownLatch go2 = new CountDownLatch(1);
        List<Future<String>> got = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final String key = "k" + (i % 10);
            got.add(pool.submit(() -> { go2.await(); return many.getOrLoad(key, counted); }));
        }
        go2.countDown();
        for (Future<String> f : got) f.get(30, TimeUnit.SECONDS);
        check(keyCalls.get() == 10, "50 threads over 10 cold keys, exactly 10 loads (was " + keyCalls.get() + ")");
        check(many.joins.sum() == 40, "the other 40 rode one of those ten loads");
        check(many.size() == 10, "and ten entries were stored");

        // the counterfactual: the same race with no claim runs the loader once per thread that misses
        NaiveCache<String, String> naive = new NaiveCache<>(new SystemClock());
        AtomicInteger naiveCalls = new AtomicInteger();
        CountDownLatch go3 = new CountDownLatch(1);
        List<Future<String>> naiveGot = new ArrayList<>();
        for (int i = 0; i < 40; i++)
            naiveGot.add(pool.submit(() -> { go3.await(); return naive.getOrLoad("cold", k -> {
                naiveCalls.incrementAndGet();
                try { Thread.sleep(60); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
                return "v";
            }, 60_000); }));
        go3.countDown();
        for (Future<String> f : naiveGot) f.get(30, TimeUnit.SECONDS);
        check(naiveCalls.get() >= 10, "the same race without a claim hammered the loader " + naiveCalls.get() + " times");

        // 6. a loader that throws: nothing is stored, every waiter is told, and the next caller can retry
        TtlCache<String, String> broken = new TtlCache<>(60_000);
        broken.configure(new FixedTtl<>(60_000), new SystemClock());
        AtomicInteger brokenCalls = new AtomicInteger();
        Loader<String, String> throwing = key -> {
            brokenCalls.incrementAndGet();
            waitUntil(() -> broken.joins.sum() >= 19, 15_000);
            throw new IllegalStateException("the database is down");
        };
        CountDownLatch go4 = new CountDownLatch(1);
        List<Future<String>> attempts = new ArrayList<>();
        for (int i = 0; i < 20; i++)
            attempts.add(pool.submit(() -> { go4.await(); return broken.getOrLoad("down", throwing); }));
        go4.countDown();
        int failed = 0;
        for (Future<String> f : attempts) {
            try { f.get(30, TimeUnit.SECONDS); }
            catch (ExecutionException ee) { if (ee.getCause() instanceof IllegalStateException) failed++; }
        }
        check(failed == 20, "all 20 callers were told the load failed (" + failed + ")");
        check(brokenCalls.get() == 1, "and only one of them actually called the broken loader");
        check(broken.size() == 0, "a failed load stored nothing: the key is not poisoned with a bad value");
        check("recovered".equals(broken.getOrLoad("down", key -> "recovered")), "the very next caller loads cleanly");

        // 7. a slow load of one key blocks nothing else: there is no lock of our own anywhere
        TtlCache<String, String> free = new TtlCache<>(60_000);
        free.configure(new FixedTtl<>(60_000), new SystemClock());
        CountDownLatch holdTheLoader = new CountDownLatch(1);
        CountDownLatch loaderStarted = new CountDownLatch(1);
        Future<String> stuck = pool.submit(() -> free.getOrLoad("slow", key -> {
            loaderStarted.countDown();
            try { holdTheLoader.await(20, TimeUnit.SECONDS); }
            catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            return "slow-value";
        }));
        check(loaderStarted.await(10, TimeUnit.SECONDS), "the slow loader is running and has not returned");
        Future<String> other = pool.submit(() -> {
            free.put("other", "written while the slow load is in flight");
            return free.getOrLoad("fast", key -> "fast-value");
        });
        check("fast-value".equals(other.get(10, TimeUnit.SECONDS)),
              "another key was written and loaded while the slow load was still in flight");
        check("written while the slow load is in flight".equals(free.get("other")), "and that write is visible");
        holdTheLoader.countDown();
        check("slow-value".equals(stuck.get(20, TimeUnit.SECONDS)), "the slow load then finished normally");

        // 8. a listener that throws cannot break anything, and every removal reports the right reason
        ManualClock clock8 = new ManualClock();
        TtlCache<String, String> noisy = new TtlCache<>(100);
        noisy.configure(new FixedTtl<>(100), clock8);
        List<RemovalCause> causes = Collections.synchronizedList(new ArrayList<>());
        noisy.addListener((k, v, cause) -> { throw new RuntimeException("the metrics client is down"); });
        noisy.addListener((k, v, cause) -> causes.add(cause));
        noisy.put("a", "1");
        noisy.put("a", "2");                                               // REPLACED
        check("2".equals(noisy.get("a")), "the put landed although the first listener threw");
        clock8.advance(200);
        check(noisy.get("a") == null, "the expired read still worked");     // EXPIRED
        noisy.put("b", "1");
        clock8.advance(200);
        check(noisy.sweepOnce() == 1, "the sweep still worked");            // SWEPT
        noisy.put("c", "1");
        check(noisy.invalidate("c"), "the explicit removal still worked");  // EXPLICIT
        check(causes.equals(List.of(RemovalCause.REPLACED, RemovalCause.EXPIRED, RemovalCause.SWEPT, RemovalCause.EXPLICIT)),
              "every removal reported its reason, in order: " + causes);

        // 9. the background sweeper really runs: a real thread, a real clock, and a bounded wait
        TtlCache<String, String> swept = new TtlCache<>(30);
        swept.configure(new FixedTtl<>(30), new SystemClock());
        CountDownLatch reclaimed = new CountDownLatch(1);
        swept.addListener((k, v, cause) -> { if (cause == RemovalCause.SWEPT) reclaimed.countDown(); });
        swept.put("ghost", "nobody will ever read me again");
        swept.startSweeper(20);
        check(reclaimed.await(15, TimeUnit.SECONDS), "the background sweeper reclaimed a key nobody ever read again");
        check(swept.size() == 0, "and the map is empty afterwards");
        swept.close();
        swept.put("after", "stored with the sweeper stopped");
        check("stored with the sweeper stopped".equals(swept.get("after")),
              "the cache still works with the sweeper shut down: expiry on read never needed it");

        // 10. a waiter does not have to wait forever. The deadline belongs to the WAIT, never to the load:
        //     the thread that is running the loader is not cut off by somebody else's impatience.
        TtlCache<String, String> wedged = new TtlCache<>(60_000);
        wedged.configure(new FixedTtl<>(60_000), new SystemClock());
        CountDownLatch releaseLoader = new CountDownLatch(1), loaderIn = new CountDownLatch(1);
        Future<String> holder = pool.submit(() -> wedged.getOrLoad("k", key -> {
            loaderIn.countDown();
            try { releaseLoader.await(20, TimeUnit.SECONDS); }
            catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            return "eventually";
        }));
        check(loaderIn.await(10, TimeUnit.SECONDS), "the winner is inside the loader and has not returned");
        long waitStart = System.nanoTime();
        boolean gaveUp = false;
        try { wedged.getOrLoad("k", key -> "never called", 120); }
        catch (TimeoutException te) { gaveUp = true; }
        long waitedMs = (System.nanoTime() - waitStart) / 1_000_000L;
        check(gaveUp, "a waiter with a 120ms deadline gave up instead of waiting out the load");
        check(waitedMs < 5_000, "it gave up on its own deadline, not when the load finished (" + waitedMs + "ms)");
        check(wedged.loadCalls.sum() == 1, "and giving up did not start a second load");
        releaseLoader.countDown();
        check("eventually".equals(holder.get(20, TimeUnit.SECONDS)), "the winner's own load was never cut off");
        check("eventually".equals(wedged.get("k")), "and the value it loaded is in the cache");

        // 11. a waiter that is cancelled. The bounded form answers an interrupt instead of swallowing it,
        //     and the thread that was loading is not disturbed by it.
        TtlCache<String, String> cancelled = new TtlCache<>(60_000);
        cancelled.configure(new FixedTtl<>(60_000), new SystemClock());
        CountDownLatch releaseSlow = new CountDownLatch(1), slowIn = new CountDownLatch(1);
        Future<String> slowWinner = pool.submit(() -> cancelled.getOrLoad("c", key -> {
            slowIn.countDown();
            try { releaseSlow.await(20, TimeUnit.SECONDS); }
            catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            return "done";
        }));
        check(slowIn.await(10, TimeUnit.SECONDS), "the slow loader is running and is holding the claim");
        AtomicBoolean sawInterrupt = new AtomicBoolean(false);
        Thread waiter = new Thread(() -> {
            try { cancelled.getOrLoad("c", key -> "never called", 20_000); }
            catch (InterruptedException ie) { sawInterrupt.set(true); }
            catch (TimeoutException te) { /* a different failure; the check below catches it */ }
        }, "waiter");
        waiter.start();
        check(waitUntil(() -> cancelled.joins.sum() >= 1, 10_000), "a second thread is waiting on that claim");
        waiter.interrupt();
        waiter.join(10_000);
        check(sawInterrupt.get(), "the interrupted waiter threw InterruptedException instead of waiting on");
        check(!waiter.isAlive(), "and its thread finished rather than hanging behind a wedged load");
        releaseSlow.countDown();
        check("done".equals(slowWinner.get(20, TimeUnit.SECONDS)), "the loading thread was untouched by that interrupt");

        // 12. the retry loop terminates. With a TTL shorter than a load, a waiter is woken with a value that
        //     has already died, so it goes round again -- and every round either serves or loads, never spins.
        //     The clock is the seam again: this one is five milliseconds later every time it is read, which
        //     makes "the value died before the waiters woke" happen on every run instead of once in a while.
        AtomicLong fastForward = new AtomicLong(1_000_000L);
        TtlCache<String, String> tiny = new TtlCache<>(1);
        tiny.configure(new FixedTtl<>(1), () -> fastForward.addAndGet(5));
        AtomicInteger tinyLoads = new AtomicInteger();
        Loader<String, String> slowish = key -> {
            tinyLoads.incrementAndGet();
            try { Thread.sleep(10); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            return "v";
        };
        CountDownLatch go5 = new CountDownLatch(1);
        List<Future<String>> tinyGot = new ArrayList<>();
        for (int i = 0; i < 10; i++)
            tinyGot.add(pool.submit(() -> { go5.await(); return tiny.getOrLoad("hot", slowish); }));
        go5.countDown();
        int served = 0;
        for (Future<String> f : tinyGot) if ("v".equals(f.get(30, TimeUnit.SECONDS))) served++;
        check(served == 10, "all 10 callers returned a value although every value died before they woke");
        check(tinyLoads.get() >= 2 && tinyLoads.get() <= 10,
              "the loads stayed bounded by the thread count: " + tinyLoads.get() + " loads for 10 callers");
        check(tiny.staleJoins.sum() > 0, "the retry loop really ran: " + tiny.staleJoins.sum() + " waiters woke to a dead value");

        // 13. the same wait protocol written with a monitor, and the lost wakeup the done flag prevents
        MonitorSingleFlight<String, String> monitor = new MonitorSingleFlight<>();
        AtomicInteger monitorLoads = new AtomicInteger();
        CountDownLatch go6 = new CountDownLatch(1);
        List<Future<String>> mon = new ArrayList<>();
        for (int i = 0; i < 30; i++)
            mon.add(pool.submit(() -> { go6.await(); return monitor.get("cold", k -> {
                monitorLoads.incrementAndGet();
                try { Thread.sleep(30); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
                return "m"; }); }));
        go6.countDown();
        Set<String> monAnswers = new HashSet<>();
        for (Future<String> f : mon) monAnswers.add(f.get(30, TimeUnit.SECONDS));
        check(monitorLoads.get() == 1, "wait/notify gives the same answer: 30 threads, 1 load (was " + monitorLoads.get() + ")");
        check(monAnswers.equals(Set.of("m")), "and all 30 threads got the winner's value");
        check(MonitorSingleFlight.lostWakeup().startsWith("the signal was missed"),
              "a notify sent before the wait began is gone for good: that is the lost wakeup the done flag prevents");

        pool.shutdownNow();
        pool.awaitTermination(15, TimeUnit.SECONDS);
        c.close(); c2.close(); c3.close(); c4.close(); hot.close(); many.close();
        broken.close(); free.close(); noisy.close(); nocache.close();
        wedged.close(); cancelled.close(); tiny.close();

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
