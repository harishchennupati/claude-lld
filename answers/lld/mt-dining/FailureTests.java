import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.locks.LockSupport;

// Targeted failure tests: each one proves a claim the design makes on page 02, move 9.
// Nothing in this file can hang. The naive protocol is demonstrated with a grace timeout and a
// detector, every philosopher thread is a daemon, and every wait has a deadline, so a broken
// design FAILS a check instead of wedging the run.
public class FailureTests {
    static int failures = 0;

    /** Print one claim and remember whether it held. */
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /**
     * Sample the table's wait-for graph until the SAME ring shows up twice in a row, or the budget
     * runs out. Twice, not once: the graph is built from fields that are moving while it is read, so
     * one sample can compose a ring out of stale values even on a perfectly healthy table. A real
     * deadlock is frozen, so it confirms on every sample; a false alarm almost never repeats itself.
     */
    static Cycle watchFor(DiningTable t, long ms) {
        long end = System.currentTimeMillis() + ms;
        while (System.currentTimeMillis() < end) {
            Cycle c = t.findCycle();
            if (c != null && c.equals(t.findCycle())) return c;
            LockSupport.parkNanos(5_000_000L);
        }
        return null;
    }

    public static void main(String[] args) throws Exception {
        long started = System.currentTimeMillis();

        // 1. the naive protocol really does form a circular wait -- shown with timeouts, never a hang.
        //    A latch holds every philosopher until all five have their LEFT fork; then every one of them
        //    reaches right, and the detector reads the ring off the table while they are all stuck in it.
        CountDownLatch wedge = new CountDownLatch(5);
        NaivePolicy naive = new NaivePolicy(400, wedge);
        DiningTable bad = new DiningTable(5, naive, 1).configure(Work.none(), Work.none());
        long t1 = System.currentTimeMillis();
        bad.start();
        Cycle ring = watchFor(bad, 1_000);
        boolean unwound = bad.awaitFinish(3_000);
        long naiveMs = System.currentTimeMillis() - t1;
        check(ring != null && ring.size() == 5, "the naive protocol forms a ring of 5: " + ring);
        check(naive.timeouts() >= 1, "at least one philosopher had to give up to break it: " + naive.timeouts() + " of 5 did");
        check(naiveMs >= 400, "nobody could eat during the whole 400 ms grace window (run took " + naiveMs + " ms)");
        check(unwound && bad.allForksFree(), "every philosopher returned and every fork went back on the table");
        long abandoned = 0;
        for (int i = 0; i < 5; i++) abandoned += bad.seat(i).abandoned();
        check(abandoned + bad.totalMeals() == 5, "all 5 rounds ended as a meal or a named give-up, none still holding a fork: "
            + bad.totalMeals() + " ate, " + abandoned + " gave up");

        // 2. resource ordering: the same five, released by one latch, ten thousand meals, no deadlock.
        DiningTable ordered = new DiningTable(5, new OrderedPolicy(), 2_000).configure(Work.none(), Work.none());
        long t2 = System.currentTimeMillis();
        ordered.start();
        boolean done2 = ordered.awaitFinish(20_000);
        check(done2, "ordered locking: 10000 meals finished in " + (System.currentTimeMillis() - t2) + " ms, no deadlock");
        boolean each2000 = true;
        for (int i = 0; i < 5; i++) each2000 &= ordered.seat(i).meals() == 2_000;
        check(each2000 && ordered.totalMeals() == 10_000, "every philosopher ate exactly 2000 times: total " + ordered.totalMeals());
        check(!ordered.anyForkViolated(), "no fork was ever in two hands at once (20000 pick-ups)");
        check(ordered.allForksFree() && ordered.findCycle() == null, "all forks back, and no ring left behind");

        // 3. the arbitrator: at most n-1 may reach, so a full cycle cannot form, and every seat comes back.
        ArbitratorPolicy waiter = new ArbitratorPolicy(5);
        DiningTable seated = new DiningTable(5, waiter, 1_000).configure(Work.none(), Work.none());
        seated.start();
        boolean done3 = seated.awaitFinish(20_000);
        check(done3 && seated.totalMeals() == 5_000, "the waiter (4 seats for 5 philosophers): 5000 meals, no deadlock");
        check(waiter.freeSeats() == 4, "every seat was handed back: free seats = " + waiter.freeSeats() + " of 4");
        check(seated.allForksFree() && !seated.anyForkViolated(), "all forks back, and never two hands on one");

        // 4. mutual exclusion under a bigger table: 7 philosophers, 21000 meals, 42000 pick-ups.
        DiningTable seven = new DiningTable(7, new OrderedPolicy(), 3_000).configure(Work.none(), Work.none());
        seven.start();
        boolean done4 = seven.awaitFinish(20_000);
        check(done4 && seven.totalMeals() == 21_000 && !seven.anyForkViolated(),
            "7 philosophers, 21000 meals, 42000 pick-ups: a fork was never held twice");

        // 5. the fix must keep the parallelism: ordering lets two eat at once, one big lock lets one.
        DiningTable par = new DiningTable(5, new OrderedPolicy(), 30).configure(Work.sleepMs(1), Work.sleepMs(3));
        long t5 = System.currentTimeMillis();
        par.start();
        par.awaitFinish(20_000);
        long parMs = System.currentTimeMillis() - t5;
        DiningTable serial = new DiningTable(5, new GlobalLockPolicy(), 30).configure(Work.sleepMs(1), Work.sleepMs(3));
        long t5b = System.currentTimeMillis();
        serial.start();
        serial.awaitFinish(20_000);
        long serialMs = System.currentTimeMillis() - t5b;
        check(par.peakEating() >= 2, "resource ordering still runs " + par.peakEating() + " philosophers at once (" + parMs + " ms)");
        check(serial.peakEating() == 1, "one big lock 'fixes' the deadlock by serialising everybody: peak 1 (" + serialMs + " ms)");
        check(serialMs > parMs, "and it costs real time: " + serialMs + " ms against " + parMs + " ms for the same 150 meals");

        // 6. a meal that throws must still return both forks -- that is what the finally is for.
        DiningTable choke = new DiningTable(5, new OrderedPolicy(), 200)
            .configure(Work.none(), id -> { if (id == 2) throw new IllegalStateException("choked on the soup"); });
        choke.start();
        boolean done6 = choke.awaitFinish(20_000);
        check(done6 && choke.allForksFree(), "eating threw on every round of p2: dinner still ended with every fork on the table");
        check(choke.seat(2).errors() == 200 && choke.seat(2).meals() == 0, "p2 counted 200 failures and zero meals");
        check(choke.seat(1).meals() == 200 && choke.seat(3).meals() == 200, "its neighbours were never blocked by it: 200 meals each");

        // 7. a supervisor can break a run: interruptible locks mean a wedged philosopher throws and lets go.
        DiningTable slow = new DiningTable(5, new OrderedPolicy(), 50).configure(Work.none(), Work.sleepMs(5_000));
        slow.start();
        Thread.sleep(50);                                   // two are eating a five-second meal, three are blocked on a fork
        long t7 = System.currentTimeMillis();
        slow.interruptAll();
        boolean rescued = slow.awaitFinish(3_000);
        check(rescued, "interrupt unwound a table stuck in 5-second meals in " + (System.currentTimeMillis() - t7) + " ms");
        check(slow.allForksFree(), "every interrupted philosopher dropped the fork it was holding");

        // 8. putting down a fork you do not hold is a no-op, not a way to free somebody else's fork.
        Fork f = new Fork(3, false);
        f.pickUp(1);
        Thread thief = new Thread(() -> f.putDown(1));
        thief.start();
        thief.join(1_000);
        check(!f.isFree() && f.owner() == 1, "a stray putDown from another thread did not free fork 3");
        f.putDown(1);
        check(f.isFree() && f.owner() == -1, "the philosopher that holds it can put it down");

        // 9. nobody starves in a bounded run: fair forks, four hundred meals each, everybody finishes.
        DiningTable fair = new DiningTable(5, new OrderedPolicy(), 400, true).configure(Work.none(), Work.none());
        long t9 = System.currentTimeMillis();
        fair.start();
        boolean done9 = fair.awaitFinish(20_000);
        long min = Long.MAX_VALUE, max = 0;
        for (int i = 0; i < 5; i++) { min = Math.min(min, fair.seat(i).meals()); max = Math.max(max, fair.seat(i).meals()); }
        check(done9 && min == 400 && max == 400, "fair forks: all five finished their 400 meals in "
            + (System.currentTimeMillis() - t9) + " ms, min=" + min + " max=" + max);

        // 10. drop-and-retry never deadlocks either -- it pays in retries instead of in a ring.
        TimeoutBackoffPolicy backoff = new TimeoutBackoffPolicy(5, 50);
        DiningTable retrying = new DiningTable(5, backoff, 1_000).configure(Work.none(), Work.none());
        long t10 = System.currentTimeMillis();
        retrying.start();
        boolean done10 = retrying.awaitFinish(20_000);
        check(done10 && retrying.totalMeals() == 5_000, "tryLock with random backoff: 5000 meals in "
            + (System.currentTimeMillis() - t10) + " ms, no deadlock");
        check(backoff.retries() > 0, "and it really did drop a fork and try again: " + backoff.retries() + " retries");

        // 11. no false alarms: while a healthy ordered table runs, neither detector reports a deadlock.
        //     Note what is measured. The JVM's detector reads real lock ownership and is never wrong.
        //     Ours reads two volatile ints that are moving while it reads them, so a SINGLE sample can
        //     compose a ring out of stale values on a table that is perfectly healthy -- and it does,
        //     about once in forty runs. That is not a bug to fix, it is the nature of sampling a live
        //     graph, and it is why the rule is "confirm before you cry wolf": the same ring, twice.
        DiningTable healthy = new DiningTable(5, new OrderedPolicy(), 4_000).configure(Work.none(), Work.none());
        ThreadMXBean jvm = ManagementFactory.getThreadMXBean();
        healthy.start();
        boolean jvmClean = true, graphClean = true;
        for (int i = 0; i < 40; i++) {
            if (jvm.findDeadlockedThreads() != null) jvmClean = false;
            Cycle once = healthy.findCycle();
            if (once != null && once.equals(healthy.findCycle())) graphClean = false;   // confirmed twice = believe it
            LockSupport.parkNanos(2_000_000L);
        }
        healthy.awaitFinish(20_000);
        check(jvmClean, "ThreadMXBean.findDeadlockedThreads() reported nothing during a healthy run (40 samples)");
        check(graphClean, "and the wait-for graph never confirmed a ring either: one sample is a suspicion, "
            + "the same ring twice is a deadlock, and a detector that cries wolf gets switched off");

        // 12. the wait protocol: one table lock, one condition per seat, both forks taken atomically.
        MonitorPolicy monitor = new MonitorPolicy(5);
        DiningTable waited = new DiningTable(5, monitor, 1_000).configure(Work.none(), Work.none());
        long t12 = System.currentTimeMillis();
        waited.start();
        boolean done12 = waited.awaitFinish(20_000);
        check(done12 && waited.totalMeals() == 5_000, "the monitor version (wait in a while loop, signal after the change): "
            + "5000 meals in " + (System.currentTimeMillis() - t12) + " ms, no deadlock");
        check(!waited.anyForkViolated(), "no fork was ever in two hands: the grant made under the table lock is atomic");
        check(waited.allForksFree() && monitor.quiescent(), "every fork back and the hungry/eating arrays ended clean");
        // and it keeps the parallelism: peak is measured with a real meal, because an instant meal
        // is over before anybody else can overlap it and would measure the clock, not the design.
        DiningTable mPar = new DiningTable(5, new MonitorPolicy(5), 40).configure(Work.sleepMs(1), Work.sleepMs(3));
        mPar.start();
        mPar.awaitFinish(20_000);
        check(mPar.peakEating() == 2, "waiting on a condition costs no parallelism either: peak "
            + mPar.peakEating() + ", which is the floor(5/2) ceiling of the problem");

        // 13. interrupting a philosopher that is waiting on a Condition, not on a fork. Run it ten times,
        //     because the interesting interleavings are rare: a philosopher can be signalled and
        //     interrupted in the same breath, or be interrupted in the gap between being granted a meal
        //     and actually picking the forks up -- and both have to end with the grant handed back.
        boolean rescued13 = true, clean13 = true, forksBack13 = true;
        for (int round = 0; round < 10; round++) {
            MonitorPolicy monitorSlow = new MonitorPolicy(5);
            DiningTable mSlow = new DiningTable(5, monitorSlow, 50).configure(Work.none(), Work.sleepMs(5_000));
            mSlow.start();
            Thread.sleep(20);                               // two are eating, three are parked in await()
            mSlow.interruptAll();
            rescued13 &= mSlow.awaitFinish(3_000);
            forksBack13 &= mSlow.allForksFree();
            clean13 &= monitorSlow.quiescent();
        }
        check(rescued13 && forksBack13, "an interrupt wakes a thread parked in await() and every fork went back (10 runs)");
        check(clean13, "a philosopher signalled and interrupted at once handed its grant on: the arrays "
            + "ended clean in all 10 runs, so no seat is left marked EATING by a thread that has gone home");

        // 14. the asymmetric fix: odd seats reach the other way, and that alone breaks the ring.
        DiningTable asym = new DiningTable(5, new AsymmetricPolicy(), 1_000).configure(Work.none(), Work.none());
        boolean done14 = false;
        asym.start();
        done14 = asym.awaitFinish(20_000);
        check(done14 && asym.totalMeals() == 5_000 && !asym.anyForkViolated(),
            "asymmetric seating: 5000 meals, no deadlock, no fork in two hands -- with no global order at all");

        // 15. the other half of the wait protocol: who gets told. One condition for several different
        //     conditions loses wakeups, which is the whole reason "notifyAll, not notify" is advice.
        check(!WakeupRules.woken(false), "one shared condition + signal(): the wakeup went to a thread whose own "
            + "test was still false, and the thread the change was for was never told");
        check(WakeupRules.woken(true), "signalAll(): everybody wakes, everybody re-tests in its while loop, "
            + "and the one the change was for gets through");

        System.out.println("elapsed " + (System.currentTimeMillis() - started) + " ms");
        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
