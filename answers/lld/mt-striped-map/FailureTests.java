import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

/**
 * Targeted failure tests: each one proves a claim the design makes on page 02, move 9. Every wait in this file has
 * a deadline, so a bug shows up as a FAIL and never as a hung build; the watchdog ends the run at 45 seconds.
 */
public class FailureTests {
    static int failures = 0;

    /** Print one line per claim and remember whether it held. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }

    /** A concurrency test suite that hangs has told you nothing: this daemon ends the run if one does. */
    static void watchdog(long seconds) {
        Thread t = new Thread(() -> {
            try { Thread.sleep(seconds * 1000); } catch (InterruptedException e) { return; }
            System.out.println("FAIL watchdog: the tests did not finish in " + seconds + " s (a deadlock, or a lost lock)");
            Runtime.getRuntime().halt(2);
        });
        t.setDaemon(true);
        t.start();
    }

    /** Start N threads on one latch, run the job, and join with a deadline. Returns false if anybody was late. */
    static boolean runAll(int threads, IntConsumer job, long joinMs) throws Exception {
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> ts = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            final int id = i;
            ts.add(new Thread(() -> {
                try { go.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                job.accept(id);
            }, "t" + i));
        }
        ts.forEach(Thread::start);
        go.countDown();
        boolean allDone = true;
        for (Thread t : ts) { t.join(joinMs); allDone &= !t.isAlive(); }
        return allDone;
    }

    public static void main(String[] args) throws Exception {
        watchdog(45);

        // 1. fifty threads writing distinct keys: every key present, the exact count right, the weak count
        //    agreeing once the writers have stopped, and the stripes evenly loaded.
        final int THREADS = 50, PER = 2_000, TOTAL = THREADS * PER;
        StripedMap<String, Integer> map = new StripedMap<>(16);
        boolean done = runAll(THREADS, id -> { for (int i = 0; i < PER; i++) map.put(id + ":" + i, i); }, 20_000);
        int missing = 0;
        for (int t = 0; t < THREADS; t++)
            for (int i = 0; i < PER; i++) { Integer v = map.get(t + ":" + i); if (v == null || v != i) missing++; }
        int[] sizes = map.stripeSizes();
        int min = Integer.MAX_VALUE, max = 0;
        for (int s : sizes) { min = Math.min(min, s); max = Math.max(max, s); }
        check(done && missing == 0, "50 threads wrote " + TOTAL + " distinct keys and all of them came back (" + missing + " missing)");
        check(map.exactSize(2000) == TOTAL && map.size() == TOTAL,
              "exact size and weak size both read " + TOTAL + " once the writers stopped");
        check(max - min < TOTAL / 20, "the 16 stripes hold " + min + ".." + max + " entries: the spreader really spreads");

        // 2. the race. A read-modify-write inside ONE lock hold loses nothing; the same thing split across a get
        //    and a put loses most of it. Shown by running it, not by asserting it.
        final int RT = 8, RI = 25_000, EXPECT = RT * RI;
        StripedMap<String, Integer> safe = new StripedMap<>(16);
        runAll(RT, id -> { for (int i = 0; i < RI; i++) safe.merge("hits", 1, Integer::sum); }, 20_000);
        check(safe.get("hits") == EXPECT, "merge: " + RT + " threads x " + RI + " increments = exactly " + EXPECT);
        StripedMap<String, Integer> racy = new StripedMap<>(16);
        runAll(RT, id -> {
            for (int i = 0; i < RI; i++) { Integer c = racy.get("hits"); racy.put("hits", c == null ? 1 : c + 1); }
        }, 20_000);
        check(racy.get("hits") < EXPECT, "get-then-put: the same loop landed on " + racy.get("hits")
              + " instead of " + EXPECT + " -- the gap between two lock holds, demonstrated");

        // 3. computeIfAbsent: the loader runs at most once per key, however many threads miss it at once.
        StripedMap<String, String> loaded = new StripedMap<>(16);
        AtomicInteger calls = new AtomicInteger();
        boolean allGot = runAll(32, id -> {
            String v = loaded.computeIfAbsent("hot", k -> { calls.incrementAndGet(); return "value-" + k; });
            if (!"value-hot".equals(v)) throw new AssertionError("a caller got " + v);
        }, 10_000);
        check(allGot && calls.get() == 1, "32 threads missed the same key: the loader ran " + calls.get() + " time(s)");
        AtomicInteger perKey = new AtomicInteger();
        runAll(32, id -> { for (int i = 0; i < 100; i++) loaded.computeIfAbsent("k" + i, k -> { perKey.incrementAndGet(); return k; }); }, 10_000);
        check(perKey.get() == 100, "100 distinct keys missed by 32 threads each: the loader ran " + perKey.get() + " times, one per key");

        // 4. a stripe that resizes while readers are reading it. The worst hasher on purpose, so every one of
        //    20,000 keys lands in stripe 0 and that one stripe has to grow its buckets many times.
        StripedMap<Integer, Integer> crowded = new StripedMap<>(16);
        crowded.configure(new OneStripeHasher(), System::currentTimeMillis);
        AtomicInteger badReads = new AtomicInteger();
        boolean grew = runAll(8, id -> {
            if (id == 0) { for (int i = 0; i < 20_000; i++) crowded.put(i, i); }
            else for (int r = 0; r < 20_000; r++) {
                Integer v = crowded.get(r % 20_000);
                if (v != null && v != r % 20_000) badReads.incrementAndGet();   // a torn read would show here
            }
        }, 20_000);
        check(grew && badReads.get() == 0 && crowded.size() == 20_000,
              "20,000 keys forced into ONE stripe while 7 readers read: no torn read, size=" + crowded.size());
        check(crowded.bucketsIn(0) >= 16_384 && crowded.stripeSizes()[1] == 0,
              "that stripe grew itself to " + crowded.bucketsIn(0) + " buckets; the other 15 stayed empty");

        // 5. one key, many writers: last writer wins, the entry is never lost or duplicated. And a remap
        //    function that throws leaves the map exactly as it was, because nothing is written before it returns.
        StripedMap<String, Integer> one = new StripedMap<>(16);
        runAll(16, id -> { for (int i = 0; i < 5_000; i++) one.put("k", id); }, 10_000);
        Integer last = one.get("k");
        check(one.size() == 1 && last != null && last >= 0 && last < 16,
              "16 threads wrote the same key 5,000 times each: one entry, holding one of the written values (" + last + ")");
        boolean threw = false;
        try { one.merge("k", 1, (a, b) -> { throw new IllegalStateException("boom"); }); }
        catch (IllegalStateException e) { threw = true; }
        check(threw && one.get("k").equals(last) && one.size() == 1,
              "a remap function that throws left the value and the count exactly as they were");

        // 6. two stripes at once, in opposite directions, 20,000 times each. Ordered acquisition means this
        //    finishes; the unordered version is the classic deadlock and would sit here until the watchdog.
        StripedMap<String, String> moving = new StripedMap<>(16);
        String a = "coin-A", b = null;
        for (int i = 0; b == null; i++) { String cand = "coin-B" + i; if (moving.stripeOf(cand) != moving.stripeOf(a)) b = cand; }
        final String from = a, to = b;
        check(moving.stripeOf(from) != moving.stripeOf(to),
              "the two keys really are in different stripes (" + moving.stripeOf(from) + " and " + moving.stripeOf(to) + ")");
        moving.put(from, "the coin");
        boolean moved = runAll(2, id -> {
            for (int i = 0; i < 20_000; i++) { if (id == 0) moving.moveValue(from, to); else moving.moveValue(to, from); }
        }, 15_000);
        String at1 = moving.get(from), at2 = moving.get(to);
        check(moved, "two threads moved a value between two stripes in opposite directions 20,000 times, no deadlock");
        check(moving.size() == 1 && ("the coin".equals(at1) ^ "the coin".equals(at2)),
              "the value was never duplicated and never lost: exactly one key holds it at the end");

        // 7. the stripe count is rounded UP to a power of two, and an all-stripe operation is budgeted: with a
        //    clock whose reading is already past the deadline it gives up instead of fighting every writer.
        check(new StripedMap<>(17).stripeCount() == 32 && new StripedMap<>(1).stripeCount() == 1
              && new StripedMap<>(100).stripeCount() == 128,
              "17 stripes becomes 32, 100 becomes 128: a power of two, so the stripe choice is a mask not a modulo");
        StripedMap<String, Integer> budgeted = new StripedMap<>(16);
        for (int i = 0; i < 100; i++) budgeted.put("b" + i, i);
        check(budgeted.exactSize(1000) == 100, "with a real clock, exactSize takes all 16 locks in order and returns 100");
        long[] tick = { 0 };
        budgeted.configure(new SpreadHasher(), () -> tick[0] += 10_000);       // every reading is 10 s later
        long t0 = System.nanoTime();
        int refused = budgeted.exactSize(50);
        long ms = (System.nanoTime() - t0) / 1_000_000;
        check(refused == -1 && ms < 200, "with a clock already past the deadline it returned " + refused
              + " in " + ms + " ms instead of blocking the whole map");
        budgeted.configure(new SpreadHasher(), System::currentTimeMillis);

        // 8. listeners are called AFTER the lock is released, and a broken one cannot break a write. The proof
        //    that it is outside: the listener waits for ANOTHER thread to finish a write on the same key, which
        //    could never happen if the listener were running inside that stripe's lock.
        StripedMap<String, Integer> watched = new StripedMap<>(4);
        AtomicInteger heard = new AtomicInteger();
        AtomicBoolean outside = new AtomicBoolean();
        AtomicBoolean firstOnly = new AtomicBoolean();
        watched.addObserver((op, key, stripe, at) -> { throw new RuntimeException("a broken listener"); });
        watched.addObserver((op, key, stripe, at) -> heard.incrementAndGet());
        watched.addObserver((op, key, stripe, at) -> {
            if (!"a".equals(key) || !firstOnly.compareAndSet(false, true)) return;
            CountDownLatch otherDone = new CountDownLatch(1);
            new Thread(() -> { watched.put("a", 2); otherDone.countDown(); }, "other-writer").start();
            try { outside.set(otherDone.await(3, TimeUnit.SECONDS)); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        watched.put("a", 1);
        check(heard.get() >= 1 && watched.get("a") != null,
              "a listener threw and the write still completed, and the next listener was still called");
        check(outside.get(), "while a listener was running, another thread completed a write on the same key: "
              + "the listener is outside the lock");

        // 9. iteration while a writer runs: weakly consistent, and it can never throw.
        StripedMap<Integer, Integer> live = new StripedMap<>(16);
        for (int i = 0; i < 10_000; i++) live.put(i, i);
        Thread writer = new Thread(() -> { for (int i = 10_000; i < 40_000; i++) live.put(i, i); }, "writer");
        writer.start();
        int seen = 0;
        RuntimeException blew = null;
        try { for (Iterator<Map.Entry<Integer, Integer>> it = new StripeIterator<>(live); it.hasNext(); it.next()) seen++; }
        catch (RuntimeException e) { blew = e; }
        writer.join(10_000);
        check(blew == null && seen >= 10_000 && seen <= live.size(),
              "iterated " + seen + " entries while 30,000 more were being written: no ConcurrentModificationException");
        Map<Integer, Integer> frozen = live.snapshot(2000);
        check(frozen != null && frozen.size() == live.exactSize(2000),
              "and a snapshot taken under all 16 locks is exact: " + (frozen == null ? -1 : frozen.size()) + " entries");

        // 10. reads that take NO lock, while the stripe they are reading resizes underneath them. The resize
        //     copies into a fresh table instead of relinking the old one, so a reader mid-walk is never stranded.
        ReadOptimizedMap<Integer, Integer> free = new ReadOptimizedMap<>(16, 16, new OneStripeHasher());
        AtomicInteger wrong = new AtomicInteger();
        boolean ranFree = runAll(8, id -> {
            if (id == 0) { for (int i = 0; i < 20_000; i++) free.put(i, i); }
            else for (int r = 0; r < 40_000; r++) {
                int k = r % 20_000;
                Integer v = free.get(k);
                if (v != null && v != k) wrong.incrementAndGet();      // a stale read is fine; a WRONG one is not
            }
        }, 20_000);
        check(ranFree && wrong.get() == 0 && free.size() == 20_000,
              "20,000 keys into ONE lock-free stripe while 7 readers read it with no lock: 0 wrong reads, size=" + free.size());
        check(free.bucketsIn(0) >= 16_384,
              "that stripe copied itself up to " + free.bucketsIn(0) + " buckets; readers walking the old table were never relinked");

        // 11. the wait protocol. Eight threads ask for a key that does not exist, one thread supplies it, and a
        //     single signalAll wakes every one of them -- because each re-checks in a loop rather than assuming.
        WaitableMap<String, String> waitMap = new WaitableMap<>(16, new SpreadHasher());
        AtomicInteger woke = new AtomicInteger(), quit = new AtomicInteger();
        CountDownLatch asked = new CountDownLatch(8);
        List<Thread> waiters = new ArrayList<>();
        for (int i = 0; i < 8; i++) waiters.add(new Thread(() -> {
            asked.countDown();
            try { if (waitMap.awaitValue("late", 5_000) != null) woke.incrementAndGet(); else quit.incrementAndGet(); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }, "waiter"));
        waiters.forEach(Thread::start);
        asked.await(3, TimeUnit.SECONDS);
        Thread.sleep(100);
        int parked = waitMap.waitersOn("late");
        waitMap.put("late", "here");
        boolean allWoke = true;
        for (Thread t : waiters) { t.join(6_000); allWoke &= !t.isAlive(); }
        check(parked == 8 && allWoke && woke.get() == 8 && quit.get() == 0,
              "8 threads parked on one condition; one signalAll after the write woke all " + woke.get() + " of them");

        // 12. and the same wait with a budget, on a key that never arrives: it gives up, on time, instead of
        //     hanging -- because awaitNanos hands back what is LEFT and the loop cannot restart the clock.
        long waitT0 = System.nanoTime();
        String never = waitMap.awaitValue("never-arrives", 200);
        long waitMs = (System.nanoTime() - waitT0) / 1_000_000;
        check(never == null && waitMs >= 150 && waitMs < 1_500,
              "a wait for a key that never arrives returned null after " + waitMs + " ms, not never");

        // 13. cancelling a thread that is blocked on a lock somebody else holds. lock() cannot be interrupted;
        //     lockInterruptibly() can. Both finish here -- the point is WHEN, and that neither one is stuck.
        String canCancel = LockWaiting.cancelWhileBlocked(true);
        String cannot = LockWaiting.cancelWhileBlocked(false);
        check(canCancel.startsWith("cancelled"), "lockInterruptibly(): " + canCancel);
        check(cannot.startsWith("waited for the holder"), "plain lock() ignores the interrupt: " + cannot);

        // 14. fairness. The default lock lets an arriving thread barge past the queue, which is most of why it is
        //     fast; a fair lock hands turns out in arrival order and pays a context switch for each one.
        LockWaiting.Turns unfair = LockWaiting.hammer(false, 4, 200);
        LockWaiting.Turns fairTurns = LockWaiting.hammer(true, 4, 200);
        check(unfair.total > fairTurns.total * 5,
              "the default (barging) lock did " + unfair.total + " acquisitions where the fair one did "
              + fairTurns.total + ": fairness is not free");
        check(fairTurns.min > 0 && fairTurns.max <= fairTurns.min * 2 && unfair.min > 0,
              "under the fair lock every thread got a turn and the spread was " + fairTurns.min + ".." + fairTurns.max
              + "; under the barging lock it was " + unfair.min + ".." + unfair.max);

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
