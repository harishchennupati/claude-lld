import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Targeted failure tests: each one proves a claim the design makes on page 02, move 9. Every wait in this file
 * has a deadline and every thread is a daemon, so a bug shows up as a FAIL, never as a hung build; the
 * watchdog ends the run at 45 seconds. A barrier test that hangs has told you nothing.
 */
public class FailureTests {
    static int failures = 0;

    /** Print one line per claim and remember whether it held. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }

    /** A barrier test suite that hangs is a failed test suite: this daemon ends the run if one does. */
    static void watchdog(long seconds) {
        Thread t = new Thread(() -> {
            try { Thread.sleep(seconds * 1000); } catch (InterruptedException e) { return; }
            System.out.println("FAIL watchdog: the tests did not finish in " + seconds + " s (a deadlock or a lost wakeup)");
            Runtime.getRuntime().halt(2);
        });
        t.setDaemon(true);
        t.start();
    }

    /** One daemon thread offering one atom and appending its symbol to the shared buffer when released. */
    static Thread atom(MoleculeBarrier barrier, Element e, StringBuffer out, AtomicInteger released) {
        Thread t = new Thread(() -> {
            try {
                Runnable emit = () -> { out.append(e.symbol()); released.incrementAndGet(); };
                if (e == Element.HYDROGEN) barrier.hydrogen(emit); else barrier.oxygen(emit);
            } catch (InterruptedException ex) { Thread.currentThread().interrupt(); }
        }, e.symbol() + "-atom");
        t.setDaemon(true);
        t.start();
        return t;
    }

    /**
     * Drive any barrier with twenty hydrogen threads and ten oxygen threads pulling from a shared pool of
     * atoms, and return the per-thread counts. A shared pool and not a per-thread quota, because a thread
     * supplies one seat at a time: a quota that strands the last two hydrogen atoms on one thread deadlocks.
     */
    static int[] race(MoleculeBarrier barrier, StringBuffer out, int molecules, int hThreads, int oThreads)
            throws Exception {
        AtomicInteger hLeft = new AtomicInteger(2 * molecules), oLeft = new AtomicInteger(molecules);
        CountDownLatch go = new CountDownLatch(1);
        int[] done = new int[hThreads + oThreads];
        List<Thread> threads = new ArrayList<>();
        for (int i = 0; i < hThreads + oThreads; i++) {
            final int me = i;
            final boolean isHydrogen = i < hThreads;
            Thread t = new Thread(() -> {
                try {
                    go.await();
                    AtomicInteger pool = isHydrogen ? hLeft : oLeft;
                    while (pool.getAndDecrement() > 0) {
                        if (isHydrogen) barrier.hydrogen(() -> out.append("H"));
                        else barrier.oxygen(() -> out.append("O"));
                        done[me]++;
                    }
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            });
            t.setDaemon(true);
            threads.add(t);
        }
        threads.forEach(Thread::start);
        go.countDown();
        for (Thread t : threads) t.join(30_000);
        return done;
    }

    /** The quietest and the busiest thread of a run: how evenly the seats were handed out. */
    static int[] spread(int[] perThread) {
        int min = Integer.MAX_VALUE, max = 0;
        for (int n : perThread) { min = Math.min(min, n); max = Math.max(max, n); }
        return new int[] { min, max };
    }

    public static void main(String[] args) throws Exception {
        watchdog(45);

        // 1. the race: a thousand molecules through thirty threads. Every window of three released atoms
        //    must hold exactly two hydrogen and one oxygen -- never HHH, never HOO, and never a mixed window.
        H2OBarrier barrier = new H2OBarrier();
        MoleculeCounter counter = new MoleculeCounter();
        barrier.addObserver(counter);
        StringBuffer out = new StringBuffer();
        race(barrier, out, 1000, 20, 10);
        String released = out.toString();
        check(released.length() == 3000, "all 3000 atoms were released (" + released.length() + ")");
        check(Main.wellFormed(released, 2, 1), "every window of three is exactly two H and one O");
        check(barrier.moleculesFormed() == 1000 && counter.seen() == 1000,
              "1000 molecules formed and the listener was told exactly 1000 times");
        // and the parks are the proof there was no thundering herd: closeMyEmit signals exactly the two
        // hydrogen and one oxygen whose seats just opened, so a molecule costs about five parks, not thirty.
        check(barrier.waitCount() < 8 * 1000,
              "about five parks per molecule, not one per waiting thread (" + barrier.waitCount() + " parks)");

        // 2. nobody leaves early: two hydrogen with no oxygen must both still be asleep, and the arrival of
        //    the oxygen is what releases all three.
        H2OBarrier waiting = new H2OBarrier();
        StringBuffer w = new StringBuffer();
        AtomicInteger released2 = new AtomicInteger();
        Thread h1 = atom(waiting, Element.HYDROGEN, w, released2);
        Thread h2 = atom(waiting, Element.HYDROGEN, w, released2);
        Thread.sleep(250);
        check(released2.get() == 0 && h1.isAlive() && h2.isAlive(),
              "two hydrogen and no oxygen: nothing was released and both threads are still parked");
        Thread o1 = atom(waiting, Element.OXYGEN, w, released2);
        h1.join(5_000); h2.join(5_000); o1.join(5_000);
        check(released2.get() == 3 && Main.wellFormed(w.toString(), 2, 1),
              "the oxygen arrived and exactly three atoms left together as one molecule: " + w);

        // 3. a surplus atom waits for a partner instead of forming a bad molecule.
        H2OBarrier surplus = new H2OBarrier();
        StringBuffer s = new StringBuffer();
        AtomicInteger released3 = new AtomicInteger();
        List<Thread> spare = new ArrayList<>();
        for (int i = 0; i < 3; i++) spare.add(atom(surplus, Element.HYDROGEN, s, released3));
        atom(surplus, Element.OXYGEN, s, released3);
        Thread.sleep(250);
        long stillWaiting = spare.stream().filter(Thread::isAlive).count();
        check(released3.get() == 3 && stillWaiting == 1,
              "three hydrogen and one oxygen: exactly one molecule left and the spare hydrogen is still waiting");
        atom(surplus, Element.HYDROGEN, s, released3);
        atom(surplus, Element.OXYGEN, s, released3);
        for (Thread t : spare) t.join(5_000);
        Thread.sleep(100);
        check(released3.get() == 6 && Main.wellFormed(s.toString(), 2, 1),
              "its partners arrived and the second molecule formed: " + s);

        // 4. an interrupted atom hands its seat back. If it did not, the seat would be held by a thread that
        //    no longer exists and the next molecule could never complete -- this test would then time out.
        H2OBarrier cancel = new H2OBarrier();
        StringBuffer c = new StringBuffer();
        AtomicInteger released4 = new AtomicInteger();
        AtomicBoolean interrupted = new AtomicBoolean();
        Thread lonely = new Thread(() -> {
            try { cancel.hydrogen(() -> { c.append("H"); released4.incrementAndGet(); }); }
            catch (InterruptedException e) { interrupted.set(true); }
        });
        lonely.setDaemon(true);
        lonely.start();
        Thread.sleep(200);
        lonely.interrupt();
        lonely.join(5_000);
        check(interrupted.get() && released4.get() == 0 && cancel.seatedCount(Element.HYDROGEN) == 0,
              "a cancelled hydrogen threw InterruptedException, released nothing and gave its seat back");
        Thread a1 = atom(cancel, Element.HYDROGEN, c, released4);
        Thread a2 = atom(cancel, Element.HYDROGEN, c, released4);
        Thread a3 = atom(cancel, Element.OXYGEN, c, released4);
        a1.join(5_000); a2.join(5_000); a3.join(5_000);
        check(released4.get() == 3 && cancel.moleculesFormed() == 1,
              "and the barrier still forms molecules afterwards, which is the proof the seat came back");

        // 5. a release callback that throws must not wedge the barrier: the emit is still counted in a finally,
        //    so the molecule closes and the next one can form.
        H2OBarrier boom = new H2OBarrier();
        StringBuffer b = new StringBuffer();
        AtomicInteger released5 = new AtomicInteger();
        AtomicBoolean threw = new AtomicBoolean();
        Thread bad = new Thread(() -> {
            try { boom.hydrogen(() -> { throw new RuntimeException("the caller's callback blew up"); }); }
            catch (RuntimeException e) { threw.set(true); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        bad.setDaemon(true);
        bad.start();
        Thread t2 = atom(boom, Element.HYDROGEN, b, released5);
        Thread t3 = atom(boom, Element.OXYGEN, b, released5);
        bad.join(5_000); t2.join(5_000); t3.join(5_000);
        check(threw.get() && boom.moleculesFormed() == 1,
              "a release callback that threw reached its caller and still closed its molecule");
        StringBuffer b2 = new StringBuffer();
        race(boom, b2, 20, 4, 2);
        check(boom.moleculesFormed() == 21 && Main.wellFormed(b2.toString(), 2, 1),
              "and twenty more molecules formed on the same barrier afterwards");

        // 6. the semaphore + CyclicBarrier build satisfies exactly the same contract.
        SemaphoreBarrier sem = new SemaphoreBarrier();
        StringBuffer so = new StringBuffer();
        race(sem, so, 500, 20, 10);
        check(so.length() == 1500 && Main.wellFormed(so.toString(), 2, 1) && sem.moleculesFormed() == 500,
              "the semaphore + CyclicBarrier version passes the same window check over 500 molecules");

        // 7. nobody is left behind: over a long run every one of the thirty threads is served and every atom
        //    in the pool is consumed exactly once. The spread between them is the honest cost of a non-fair
        //    lock, which is why the same run is repeated with fair permits.
        H2OBarrier unfair = new H2OBarrier();
        int[] per = race(unfair, new StringBuffer(), 1500, 20, 10);
        int min = Integer.MAX_VALUE, max = 0, total = 0;
        for (int n : per) { min = Math.min(min, n); max = Math.max(max, n); total += n; }
        check(total == 4500 && min > 0 && unfair.moleculesFormed() == 1500,
              "1500 molecules: all 4500 atoms consumed once and every thread served (quietest " + min
              + ", busiest " + max + " -- a non-fair lock lets a hot thread barge)");
        // fairness is one constructor flag on the build you already have -- here is what it buys, measured
        // on the same run: the seat goes to the longest waiter instead of to whichever thread is running.
        int[] barging = race(new SemaphoreBarrier(Recipe.WATER, false), new StringBuffer(), 1500, 20, 10);
        SemaphoreBarrier evenly = new SemaphoreBarrier(Recipe.WATER, true);
        int[] served = race(evenly, new StringBuffer(), 1500, 20, 10);
        int[] sb = spread(barging), sf = spread(served);
        check(evenly.moleculesFormed() == 1500 && sf[0] > 0 && sf[1] - sf[0] <= (sb[1] - sb[0]) / 4,
              "fair = true is still correct and far more even: " + sf[0] + "-" + sf[1]
              + " atoms per thread, against " + sb[0] + "-" + sb[1] + " without the flag");

        // 8. the 2:1 rule is data, not code: the same class with a peroxide recipe releases groups of 2 H + 2 O.
        H2OBarrier peroxide = new H2OBarrier(Recipe.PEROXIDE);
        StringBuffer p = new StringBuffer();
        AtomicInteger released8 = new AtomicInteger();
        List<Thread> quad = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            quad.add(atom(peroxide, Element.HYDROGEN, p, released8));
            quad.add(atom(peroxide, Element.HYDROGEN, p, released8));
            quad.add(atom(peroxide, Element.OXYGEN, p, released8));
            quad.add(atom(peroxide, Element.OXYGEN, p, released8));
        }
        for (Thread t : quad) t.join(10_000);
        check(released8.get() == 12 && Main.wellFormed(p.toString(), 2, 2) && peroxide.moleculesFormed() == 3,
              "a peroxide recipe releases groups of two H and two O with no change to the barrier: " + p);

        // 9. a broken listener cannot break a molecule, and the timestamp comes from the injected clock.
        H2OBarrier told = new H2OBarrier();
        MoleculeCounter good = new MoleculeCounter();
        told.addObserver((index, atMs) -> { throw new RuntimeException("this dashboard is down"); });
        told.addObserver(good);
        told.configure(() -> 1_700_000_000_000L);
        StringBuffer tb = new StringBuffer();
        race(told, tb, 50, 4, 2);
        check(told.moleculesFormed() == 50 && good.seen() == 50,
              "a listener that throws did not stop a molecule, and the listener behind it still heard all 50");
        check(good.lastAtMs() == 1_700_000_000_000L,
              "the molecule was stamped with the injected clock, not the wall clock");

        // 10. the deadlock that is NOT in the barrier: a caller that owns a per-thread quota. One thread
        //     holding both hydrogen atoms of a molecule blocks on the first and can never supply the second,
        //     so the molecule never completes. The barrier is correct; the way it was driven is not.
        H2OBarrier stranded = new H2OBarrier();
        Thread quota = new Thread(() -> {
            try { stranded.hydrogen(() -> { }); stranded.hydrogen(() -> { }); }     // both H atoms, one thread
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        quota.setDaemon(true);
        quota.start();
        Thread onlyOxygen = atom(stranded, Element.OXYGEN, new StringBuffer(), new AtomicInteger());
        Thread.sleep(400);
        check(stranded.moleculesFormed() == 0 && quota.isAlive() && onlyOxygen.isAlive(),
              "a per-thread quota strands the molecule: one thread owning both H waits for itself forever");
        atom(stranded, Element.HYDROGEN, new StringBuffer(), new AtomicInteger());   // a partner from outside
        onlyOxygen.join(5_000);
        for (int i = 0; i < 100 && stranded.moleculesFormed() == 0; i++) Thread.sleep(20);
        check(stranded.moleculesFormed() == 1,
              "one hydrogen from any other thread frees it: drive the barrier from a shared pool, never a quota");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
