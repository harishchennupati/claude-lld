import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Targeted failure tests: each one proves a claim the design makes on page 02, move 9.
// Every wait in this file has a timeout, so a broken pipeline FAILS a check instead of hanging the run.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /** Wait, with a bound, for a thread to reach a waiting state. Used instead of sleeping and hoping. */
    static boolean waitUntilParked(Thread t, long ms) throws InterruptedException {
        long deadline = System.currentTimeMillis() + ms;
        while (System.currentTimeMillis() < deadline) {
            Thread.State s = t.getState();
            if (s == Thread.State.WAITING || s == Thread.State.TIMED_WAITING) return true;
            if (s == Thread.State.TERMINATED) return false;
            Thread.sleep(1);
        }
        return false;
    }

    public static void main(String[] args) throws Exception {
        long started = System.currentTimeMillis();

        // 1. ten producers and ten consumers, 20000 items: every item consumed EXACTLY once, and the ledger balances.
        //    This is the whole promise of the design in one test; if the wait protocol were wrong it would fail here.
        int producers = 10, consumers = 10, each = 2_000, total = producers * each;
        AtomicIntegerArray seen = new AtomicIntegerArray(total);
        Pipeline race = new Pipeline(new LockHandoff(16));
        race.configure(new BlockUntilRoom(), t -> seen.incrementAndGet(t.id), new DeadLetterSink());
        race.start(producers, each, consumers);
        check(race.awaitProducers(30_000), "10 producers finished inside 30 s");
        check(race.shutdown(30_000), "shutdown of a 10x10 pipeline finished inside its deadline");
        int once = 0, more = 0, never = 0;
        for (int i = 0; i < total; i++) { int n = seen.get(i); if (n == 1) once++; else if (n > 1) more++; else never++; }
        check(once == total, "all " + total + " items were consumed exactly once (once=" + once + ")");
        check(more == 0, "no item was consumed twice (duplicates=" + more + ")");
        check(never == 0, "no item was lost (lost=" + never + ")");
        MetricsSnapshot raceStats = race.stats();
        check(raceStats.balanced(), "the ledger balances: " + raceStats);
        check(raceStats.consumed() == total, "consumed == produced == " + total);

        // 2. the bound is the safety property: 4 producers and 4 consumers on a buffer of ONE.
        //    If a waiter used `if` instead of `while`, two threads would slip past the guard and depth would reach 2.
        Pipeline tight = new Pipeline(new LockHandoff(1));
        AtomicInteger tightDone = new AtomicInteger();
        tight.configure(new BlockUntilRoom(), t -> tightDone.incrementAndGet(), new DeadLetterSink());
        tight.start(4, 2_000, 4);
        check(tight.awaitProducers(30_000), "the capacity-1 run finished producing");
        check(tight.shutdown(30_000), "the capacity-1 run shut down cleanly");
        check(tight.stats().maxDepth() <= 1, "depth NEVER exceeded the capacity of 1 (maxDepth="
            + tight.stats().maxDepth() + ")");
        check(tightDone.get() == 8_000, "all 8000 items squeezed through a buffer of one, exactly once");
        check(tight.stats().backpressured() > 0, "and the producers really did park: "
            + tight.stats().backpressured() + " back-pressure events");

        // 3. shutdown DRAINS: a real backlog exists when the stop begins, and every item in it is still processed.
        Pipeline drain = new Pipeline(new LockHandoff(64));
        AtomicInteger drained = new AtomicInteger();
        drain.configure(new BlockUntilRoom(), t -> { Thread.sleep(1); drained.incrementAndGet(); }, new DeadLetterSink());
        drain.start(4, 100, 2);
        check(drain.awaitProducers(20_000), "producers finished, so nothing can be added after this line");
        int backlog = drain.handoff().size();
        check(backlog > 0, "there is a real backlog when the drain starts: " + backlog + " items");
        check(drain.shutdown(30_000), "shutdown finished inside its deadline");
        check(drained.get() == 400, "every one of the 400 items was processed, backlog included (done=" + drained.get() + ")");
        check(drain.handoff().size() == 0, "the buffer is empty afterwards");
        check(drain.allThreadsDead(), "no consumer thread is left alive");
        check(drain.state() == PipelineState.TERMINATED, "the life cycle ended at TERMINATED");

        // 4. exactly one poison pill per consumer, and a pill is never mistaken for work.
        check(drain.stats().pillsTaken() == 2, "exactly one pill per consumer was taken (pills="
            + drain.stats().pillsTaken() + ", consumers=2)");
        check(drain.stats().consumed() == 400, "no pill was counted as a consumed item (consumed="
            + drain.stats().consumed() + ", not 402)");

        // 5. back-pressure, measured: a full buffer parks the producer, and exactly one take releases it.
        Handoff full = new LockHandoff(2);
        full.put(new Task(1, "a"));
        full.put(new Task(2, "b"));
        CountDownLatch handedOver = new CountDownLatch(1);
        Thread blocked = new Thread(() -> {
            try { full.put(new Task(3, "c")); handedOver.countDown(); } catch (InterruptedException ignored) { }
        }, "blocked-producer");
        blocked.start();
        check(waitUntilParked(blocked, 2_000), "the third producer reached a waiting state");
        check(!handedOver.await(200, TimeUnit.MILLISECONDS), "its put has NOT returned after 200 ms: that wait is back-pressure");
        check(full.size() == 2, "and the buffer is still exactly at its capacity of 2");
        full.take();
        check(handedOver.await(3, TimeUnit.SECONDS), "one take releases the parked producer within 3 s");
        blocked.join(3_000);
        check(!blocked.isAlive() && full.size() == 2, "the producer finished and the buffer is full again");

        // 6. an interrupt is not a shutdown protocol -- but it must not lose an item either.
        //    (a) a consumer parked on an empty buffer just exits.
        Handoff idleBuf = new LockHandoff(4);
        Metrics im = new Metrics();
        DeadLetterSink idleSink = new DeadLetterSink();
        Thread idle = new Thread(new Consumer("idle", idleBuf, new AccountedWork(t -> { }, im, idleSink),
            im, idleSink, new CountDownLatch(0)), "idle-consumer");
        idle.start();
        check(waitUntilParked(idle, 2_000), "a consumer with no work parks on notEmpty");
        idle.interrupt();
        idle.join(3_000);
        check(!idle.isAlive(), "the interrupted consumer ended instead of spinning");
        check(idleSink.size() == 0, "it was holding nothing, so nothing was dead-lettered");
        //    (b) a consumer interrupted WITH a task in hand parks that task instead of taking it to the grave.
        Handoff busyBuf = new LockHandoff(4);
        Metrics bm = new Metrics();
        DeadLetterSink busySink = new DeadLetterSink();
        CountDownLatch pickedUp = new CountDownLatch(1), neverFinishes = new CountDownLatch(1);
        Work stuck = t -> { pickedUp.countDown(); neverFinishes.await(5, TimeUnit.SECONDS); };
        Thread busy = new Thread(new Consumer("busy", busyBuf, new AccountedWork(stuck, bm, busySink),
            bm, busySink, new CountDownLatch(0)), "busy-consumer");
        busy.start();
        bm.produced.incrementAndGet();
        busyBuf.put(new Task(77, "in hand"));
        bm.admitted.incrementAndGet();                       // the producer's bookkeeping, done by hand here
        check(pickedUp.await(3, TimeUnit.SECONDS), "the consumer picked the task up and started the work");
        busy.interrupt();
        busy.join(3_000);
        check(!busy.isAlive(), "the interrupted consumer ended");
        check(busySink.size() == 1 && busySink.parked().peek().id == 77,
            "the task in its hand went to the dead-letter queue, not to nowhere");
        check(bm.snapshot(busyBuf.size()).balanced(), "and the ledger still balances after the interrupt: "
            + bm.snapshot(busyBuf.size()));

        // 7. work that throws does not lose the item: it is parked and counted, and the totals still add up.
        Pipeline flaky = new Pipeline(new LockHandoff(8));
        DeadLetterSink parked = new DeadLetterSink();
        flaky.configure(new BlockUntilRoom(),
            t -> { if (t.id % 7 == 3) throw new IllegalStateException("bad row " + t.id); }, parked);
        flaky.start(2, 50, 3);
        check(flaky.awaitProducers(20_000), "the flaky run finished producing");
        check(flaky.shutdown(20_000), "the flaky run shut down cleanly even though the work kept throwing");
        int shouldFail = 0;
        for (int id = 0; id < 100; id++) if (id % 7 == 3) shouldFail++;
        MetricsSnapshot fs = flaky.stats();
        check(fs.deadLettered() == shouldFail, "every one of the " + shouldFail + " failures was parked (parked="
            + parked.size() + ")");
        check(fs.consumed() + fs.deadLettered() == fs.admitted(), "not one of the 100 items disappeared: "
            + fs.consumed() + " done + " + fs.deadLettered() + " parked == " + fs.admitted() + " admitted");
        check(fs.balanced(), "the ledger balances with failures in it: " + fs);

        // 8. both builds of the hand-off pass the same exactly-once check, so the choice is a trade-off, not a fix:
        //    the hand-written lock with two Conditions, and the JDK's own ArrayBlockingQueue underneath the same interface.
        for (Handoff h : List.of(new LockHandoff(8), new JucHandoff(8))) {
            int n = 4 * 1_000;
            AtomicIntegerArray hits = new AtomicIntegerArray(n);
            Pipeline p = new Pipeline(h);
            p.configure(new BlockUntilRoom(), t -> hits.incrementAndGet(t.id), new DeadLetterSink());
            p.start(4, 1_000, 4);
            boolean clean = p.awaitProducers(30_000) && p.shutdown(30_000);
            int bad = 0;
            for (int i = 0; i < n; i++) if (hits.get(i) != 1) bad++;
            check(clean && bad == 0 && p.stats().balanced(),
                "build \"" + h.name() + "\": " + n + " items, each consumed exactly once, ledger balanced");
        }

        // 9. the other shutdown: a stop flag WITH a drain loses nothing; the naive flag strands the whole backlog.
        int[] processed = new int[2], stranded = new int[2];
        for (int mode = 0; mode < 2; mode++) {
            Handoff h = new LockHandoff(64);
            for (int i = 0; i < 40; i++) h.put(new Task(i, "backlog"));
            AtomicInteger done = new AtomicInteger();
            AtomicBoolean producersJoined = new AtomicBoolean(true);
            Work w = t -> done.incrementAndGet();
            Thread c = new Thread(mode == 0 ? new DrainingConsumer(h, producersJoined, w, 20)
                                            : new NaiveStopConsumer(h, producersJoined, w), "stopper-" + mode);
            c.start();
            c.join(5_000);
            check(!c.isAlive(), (mode == 0 ? "the draining" : "the naive") + " stop-flag consumer ended inside 5 s");
            processed[mode] = done.get();
            stranded[mode] = h.size();
        }
        check(processed[0] == 40 && stranded[0] == 0, "stop flag WITH a drain: all 40 processed, 0 stranded");
        check(processed[1] == 0 && stranded[1] == 40, "the naive stop flag strands the whole backlog: "
            + stranded[1] + " items abandoned -- this is why the pill travels in-band");

        // 10. nothing is added after stop: shutdown while the producers still have 200000 items to make.
        Pipeline cut = new Pipeline(new LockHandoff(4));
        cut.configure(new BlockUntilRoom(), t -> Thread.sleep(1), new DeadLetterSink());
        cut.start(2, 100_000, 2);
        Thread.sleep(30);
        check(cut.shutdown(20_000), "a stop-now shutdown returned cleanly with 200000 items still unmade");
        MetricsSnapshot cs = cut.stats();
        long admittedAtStop = cs.admitted();
        Thread.sleep(50);
        check(cut.stats().admitted() == admittedAtStop, "nothing was admitted after shutdown returned (admitted="
            + admittedAtStop + ")");
        check(cs.produced() < 200_000, "the producers stopped early instead of finishing: produced=" + cs.produced());
        check(cs.consumed() == cs.admitted() && cs.depth() == 0,
            "everything that WAS admitted got drained: consumed=" + cs.consumed() + " depth=0");
        check(cut.allThreadsDead() && cut.state() == PipelineState.TERMINATED, "every thread dead, state TERMINATED");

        // 11. the lost wakeup: a signal that lands between the check and the wait is thrown away.
        //     The interleaving is forced with two latches, so the bug shows up on every run instead of at 3 a.m.
        LostWakeupHandoff broken = new LostWakeupHandoff();
        long[] slept = new long[1];
        Thread victim = new Thread(() -> {
            try {
                long t0 = System.currentTimeMillis();
                broken.takeLosingWakeups(400);
                slept[0] = System.currentTimeMillis() - t0;
            } catch (InterruptedException ignored) { }
        }, "lost-wakeup-victim");
        victim.start();
        check(broken.guardRead.await(2, TimeUnit.SECONDS), "the broken take read the guard and released the lock");
        broken.put(new Task(5, "arrives in the gap"));        // add + notify with nobody in the wait set yet
        broken.signalSent.countDown();                        // only now does the victim call wait()
        victim.join(3_000);
        check(!victim.isAlive() && slept[0] >= 300,
            "checking the guard OUTSIDE the lock loses the wakeup: the item was already there, and the take still "
            + "slept " + slept[0] + " ms (with a plain wait() it would sleep forever)");
        //     the same race against the real hand-off: await() releases the lock atomically, so no signal is lost.
        Handoff correct = new LockHandoff(4);
        CountDownLatch got = new CountDownLatch(1);
        Thread waiter = new Thread(() -> { try { correct.take(); got.countDown(); } catch (InterruptedException ignored) { } }, "correct-waiter");
        waiter.start();
        check(waitUntilParked(waiter, 2_000), "a consumer on the real hand-off parks inside the lock");
        long beforePut = System.currentTimeMillis();
        correct.put(new Task(6, "same race"));
        check(got.await(2, TimeUnit.SECONDS) && System.currentTimeMillis() - beforePut < 500,
            "and it is woken at once, because await() releases the lock and re-takes it as one step");

        // 12. the OTHER shutdown: stop now, and hand the caller the work that will never run.
        Pipeline urgent = new Pipeline(new LockHandoff(32));
        urgent.configure(new BlockUntilRoom(), t -> Thread.sleep(2), new DeadLetterSink());
        urgent.start(2, 10_000, 2);
        Thread.sleep(40);                                     // let a real backlog build up
        List<Task> undone = urgent.shutdownNow(10_000);
        MetricsSnapshot us = urgent.stats();
        check(undone.size() > 0, "stopNow handed back the unprocessed backlog: " + undone.size() + " items");
        check(us.discarded() == undone.size(), "and counted every one of them discarded, so they are not 'lost'");
        check(us.depth() == 0 && urgent.handoff().size() == 0, "the buffer is empty: the caller owns those items now");
        check(us.balanced(), "the ledger still balances after a stop-now: " + us);
        check(urgent.allThreadsDead() && urgent.state() == PipelineState.TERMINATED,
            "every thread is dead and the state is TERMINATED");
        check(us.consumed() + us.deadLettered() + us.discarded() == us.admitted(),
            "and every admitted item is accounted for exactly once: " + us.consumed() + " done + "
            + us.deadLettered() + " dead-lettered + " + us.discarded() + " handed back == " + us.admitted());

        // 13. fairness and starvation, measured: 4 producers through a buffer of ONE for 120 ms.
        //     The surprise is that the UNFAIR lock is the even one here -- because a producer that finds the buffer
        //     full parks on the notFull Condition, and a Condition's wait set is served first-in-first-out. So the
        //     two things worth asserting are the even spread and the price of the fair lock, not the fair spread.
        long[] unfair = FairnessProbe.run(false, 4, 120);
        long[] fair = FairnessProbe.run(true, 4, 120);
        long unfairTotal = 0, fairTotal = 0;
        for (long c : unfair) unfairTotal += c;
        for (long c : fair) fairTotal += c;
        double us2 = FairnessProbe.spread(unfair), fs2 = FairnessProbe.spread(fair);
        check(FairnessProbe.spread(unfair) < 3.0, "no producer is starved by the default lock: counts "
            + Arrays.toString(unfair) + ", spread " + String.format("%.2f", us2) + "x (the notFull queue is FIFO)");
        check(fairTotal < unfairTotal, "and new ReentrantLock(true) is paid for in context switches: " + unfairTotal
            + " items unfair vs " + fairTotal + " fair in the same 120 ms window");
        System.out.println("      the fair lock's own spread this run: " + Arrays.toString(fair) + " = "
            + String.format("%.2f", fs2) + "x -- printed, NOT asserted, because it scatters and moves run to run."
            + " That is the finding: lock fairness does not govern threads parked on a Condition.");

        System.out.println("elapsed " + (System.currentTimeMillis() - started) + " ms");
        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
