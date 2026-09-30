import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Targeted failure tests: each one proves a claim the design makes on page 02, move 9. Every wait in this file
 * has a deadline, so a bug shows up as a FAIL, never as a hung build; the watchdog kills the run at 50 seconds.
 */
public class FailureTests {
    static int failures = 0;

    /** Print one line per claim and remember whether it held. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }

    /** A blocking-queue test suite that hangs is a failed test suite: this daemon ends the run if one does. */
    static void watchdog(long seconds) {
        Thread t = new Thread(() -> {
            try { Thread.sleep(seconds * 1000); } catch (InterruptedException e) { return; }
            System.out.println("FAIL watchdog: the tests did not finish in " + seconds + " s (a lost wakeup or a deadlock)");
            Runtime.getRuntime().halt(2);
        });
        t.setDaemon(true);
        t.start();
    }

    public static void main(String[] args) throws Exception {
        watchdog(50);

        // 1. FIFO: what one producer puts in, one consumer takes out in the same order, with the queue
        //    blocking in both directions along the way (capacity 8 against 2000 items).
        BoundedBlockingQueue<Integer> fifo = new BoundedBlockingQueue<>(8);
        List<Integer> out = new ArrayList<>();
        Thread producer = new Thread(() -> {
            try { for (int i = 0; i < 2000; i++) fifo.put(i); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        Thread consumer = new Thread(() -> {
            try { for (int i = 0; i < 2000; i++) out.add(fifo.take()); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        producer.start(); consumer.start();
        producer.join(10_000); consumer.join(10_000);
        boolean ordered = out.size() == 2000;
        for (int i = 0; ordered && i < 2000; i++) ordered = out.get(i) == i;
        check(ordered, "2000 items came out in exactly the order they went in (FIFO)");
        check(fifo.size() == 0 && fifo.parkCount() > 0, "the queue is empty at the end, and it really blocked on the way (" + fifo.parkCount() + " parks)");

        // 2. the race: 10 producers and 10 consumers, 100000 items. Nothing lost, nothing delivered twice,
        //    and the bound held at every instant.
        final int PRODUCERS = 10, CONSUMERS = 10, PER = 10_000, TOTAL = PRODUCERS * PER, CAP = 32;
        BoundedBlockingQueue<Integer> q = new BoundedBlockingQueue<>(CAP);
        PeakMeter meter = new PeakMeter();
        q.addObserver(meter);
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> threads = new ArrayList<>();
        List<List<Integer>> got = new ArrayList<>();
        for (int p = 0; p < PRODUCERS; p++) {
            final int id = p;
            threads.add(new Thread(() -> {
                try { go.await(); for (int i = 0; i < PER; i++) q.put(id * PER + i); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }));
        }
        for (int c = 0; c < CONSUMERS; c++) {
            List<Integer> mine = new ArrayList<>();
            got.add(mine);
            threads.add(new Thread(() -> {
                try { go.await(); Integer item; while ((item = q.take()) != null) mine.add(item); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }));
        }
        threads.forEach(Thread::start);
        go.countDown();
        for (int i = 0; i < PRODUCERS; i++) threads.get(i).join(30_000);
        q.close();
        for (int i = PRODUCERS; i < threads.size(); i++) threads.get(i).join(30_000);
        boolean[] seen = new boolean[TOTAL];
        int delivered = 0, duplicates = 0, lost = 0;
        for (List<Integer> list : got) for (int v : list) { delivered++; if (seen[v]) duplicates++; seen[v] = true; }
        for (boolean b : seen) if (!b) lost++;
        check(delivered == TOTAL && lost == 0, TOTAL + " items across 20 threads: every one delivered (" + delivered + ", lost " + lost + ")");
        check(duplicates == 0, "and not one of them twice");
        check(meter.peak() <= CAP && q.size() == 0, "0 <= size <= capacity held throughout: peak was " + meter.peak() + " of " + CAP);

        // 3. full means the producer SLEEPS, and a take is what wakes it. If put spun instead, the latch
        //    would fire immediately; if the signal were lost, it would never fire.
        BoundedBlockingQueue<String> small = new BoundedBlockingQueue<>(2);
        small.put("a"); small.put("b");
        CountDownLatch putDone = new CountDownLatch(1);
        Thread blocked = new Thread(() -> {
            try { small.put("c"); putDone.countDown(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        blocked.start();
        check(!putDone.await(200, TimeUnit.MILLISECONDS), "a put into a full queue is still waiting 200 ms later");
        check(small.parkCount() >= 1 && small.size() == 2, "it parked instead of spinning, and wrote nothing while it waited");
        small.take();
        check(putDone.await(3, TimeUnit.SECONDS), "the take woke it, and the put completed");
        blocked.join(3_000);

        // 4. empty means the consumer sleeps; an interrupt must wake it with InterruptedException, and the
        //    queue must still work afterwards -- which is what the unlock-in-a-finally buys.
        BoundedBlockingQueue<String> idle = new BoundedBlockingQueue<>(2);
        AtomicBoolean interrupted = new AtomicBoolean();
        Thread waiter = new Thread(() -> {
            try { idle.take(); } catch (InterruptedException e) { interrupted.set(true); }
        });
        waiter.start();
        Thread.sleep(100);
        waiter.interrupt();
        waiter.join(3_000);
        check(interrupted.get() && !waiter.isAlive(), "an interrupt woke the parked consumer with InterruptedException");
        idle.put("still works");
        check("still works".equals(idle.poll(2, TimeUnit.SECONDS)), "and the queue is untouched: the lock was released, nothing half-written");

        // 5. the timed calls give up on time, write nothing, and take their deadline from the injected clock.
        BoundedBlockingQueue<String> timed = new BoundedBlockingQueue<>(1);
        long t0 = System.nanoTime();
        String none = timed.poll(150, TimeUnit.MILLISECONDS);
        long waitedMs = (System.nanoTime() - t0) / 1_000_000;
        check(none == null && waitedMs >= 140, "poll on an empty queue returned null after waiting the full 150 ms (" + waitedMs + " ms)");
        timed.put("one");
        check(!timed.offer("two", 100, TimeUnit.MILLISECONDS) && timed.size() == 1, "offer into a full queue gave up and wrote nothing");
        AtomicLong fake = new AtomicLong();
        timed.configure(new BlockUntilRoom<>(), () -> fake.addAndGet(1_000_000_000L));  // every reading is a second later
        timed.take();
        t0 = System.nanoTime();
        String expired = timed.poll(200, TimeUnit.MILLISECONDS);
        long elapsedMs = (System.nanoTime() - t0) / 1_000_000;
        check(expired == null && elapsedMs < 50, "with an injected clock already past the deadline, poll gave up at once (" + elapsedMs + " ms)");

        // 6. capacity 1 and a stress loop: every round must finish, or a signal was lost. This is the test
        //    that catches `if` instead of `while`, and a signal on the wrong condition.
        ExecutorService pool = Executors.newFixedThreadPool(8);
        boolean allRounds = true;
        long roundsStart = System.nanoTime();
        for (int round = 0; round < 200 && allRounds; round++) {
            BoundedBlockingQueue<Integer> tiny = new BoundedBlockingQueue<>(1);
            List<Future<?>> tasks = new ArrayList<>();
            for (int p = 0; p < 2; p++) tasks.add(pool.submit(() -> { for (int i = 0; i < 25; i++) tiny.put(i); return null; }));
            AtomicInteger taken = new AtomicInteger();
            for (int c = 0; c < 2; c++) tasks.add(pool.submit(() -> { for (int i = 0; i < 25; i++) { tiny.take(); taken.incrementAndGet(); } return null; }));
            try { for (Future<?> f : tasks) f.get(5, TimeUnit.SECONDS); }
            catch (TimeoutException e) { allRounds = false; }
            if (taken.get() != 50) allRounds = false;
        }
        pool.shutdownNow();
        check(allRounds, "200 rounds of 4 threads over a capacity-1 queue all finished ("
            + (System.nanoTime() - roundsStart) / 1_000_000 + " ms): no wakeup was lost");

        // 7. a listener that throws must not break a put, and swapping what "full" means must not touch the queue.
        BoundedBlockingQueue<Integer> observed = new BoundedBlockingQueue<>(3);
        AtomicInteger heard = new AtomicInteger();
        observed.addObserver((what, size) -> { heard.incrementAndGet(); throw new RuntimeException("the dashboard is down"); });
        observed.configure(new DropOldest<>(), System::nanoTime);
        for (int i = 1; i <= 6; i++) observed.put(i);
        List<Integer> kept = new ArrayList<>();
        observed.drainTo(kept, 10);
        check(heard.get() >= 6, "a broken listener was called and threw, and every put still completed");
        check(kept.equals(List.of(4, 5, 6)) && observed.parkCount() == 0, "drop-oldest kept the freshest three " + kept + " and never blocked a producer");

        // 8. close() wakes everyone: no thread is left parked, put is refused, and what was already in the
        //    queue is still handed out before the end-of-stream null.
        BoundedBlockingQueue<String> closing = new BoundedBlockingQueue<>(4);
        CountDownLatch woke = new CountDownLatch(3);
        for (int i = 0; i < 3; i++) {
            new Thread(() -> {
                try { if (closing.take() == null) woke.countDown(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }).start();
        }
        Thread.sleep(100);
        closing.close();
        check(woke.await(3, TimeUnit.SECONDS), "close() woke all three parked consumers with end-of-stream");
        boolean refused = false;
        try { closing.put("late"); } catch (IllegalStateException e) { refused = true; }
        check(refused, "a put after close is refused instead of being silently dropped");
        BoundedBlockingQueue<String> draining = new BoundedBlockingQueue<>(4);
        draining.put("x"); draining.put("y");
        draining.close();
        check("x".equals(draining.take()) && "y".equals(draining.take()) && draining.take() == null,
              "a closed queue hands out what it already had, then returns null");

        // 9. the lost wakeup proper: a signal sent while nobody is waiting is gone, it is not remembered.
        //    Checking the flag OUTSIDE the lock and then taking the lock to wait leaves exactly that gap.
        long slept = LostWakeup.run(false, 300);
        check(slept >= 250, "checking outside the lock missed the signal and slept the whole 300 ms (" + slept + " ms)");
        long wokeAtOnce = LostWakeup.run(true, 300);
        check(wokeAtOnce < 100, "the same code with the check INSIDE the lock cannot miss it: woke in " + wokeAtOnce + " ms");

        // 10. the two alternatives agree with us: two semaphores, and the JDK's own ArrayBlockingQueue.
        //     If our queue were subtly wrong, this is where the orders would stop matching.
        SemaphoreQueue<Integer> sem = new SemaphoreQueue<>(2);
        Thread semFeeder = new Thread(() -> {
            try { for (int i = 0; i < 500; i++) sem.put(i); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        semFeeder.start();
        boolean semOrdered = true;
        for (int i = 0; i < 500; i++) semOrdered &= sem.take() == i;
        semFeeder.join(5_000);
        check(semOrdered, "the two-semaphore version delivers the same 500 items in the same FIFO order");
        BlockingQueue<Integer> jdk = new ArrayBlockingQueue<>(2);
        BoundedBlockingQueue<Integer> ours = new BoundedBlockingQueue<>(2);
        boolean same = true;
        for (int i = 0; i < 500; i++) {
            jdk.put(i); ours.put(i);
            same &= jdk.take().equals(ours.take());
            same &= jdk.offer(i, 5, TimeUnit.MILLISECONDS) == ours.offer(i, 5, TimeUnit.MILLISECONDS);
            same &= jdk.take().equals(ours.take());
        }
        check(same, "our queue and java.util.concurrent's ArrayBlockingQueue answer identically over 500 rounds");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
