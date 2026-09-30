import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

// Targeted failure tests: 36 checks, each proving a claim the design makes on page 02, move 9. Every wait in
// this file has a timeout, so a broken lock fails the test instead of hanging the run, and the whole file
// finishes in about a second.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }

    public static void main(String[] args) throws Exception {
        // a test that can hang is not a test: if anything below blocks, say so and stop
        Thread watchdog = new Thread(() -> {
            try { Thread.sleep(45_000); } catch (InterruptedException e) { return; }
            System.out.println("FAIL something blocked for 45 seconds");
            Runtime.getRuntime().halt(1);
        }, "watchdog");
        watchdog.setDaemon(true);
        watchdog.start();

        // 1. many readers really are inside at the same time -- otherwise this is an expensive mutex.
        //    Six readers take the read lock and none of them leaves until all six are in.
        {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
            int n = 6;
            CountDownLatch allIn = new CountDownLatch(n), release = new CountDownLatch(1);
            AtomicInteger peak = new AtomicInteger();
            for (int i = 0; i < n; i++) {
                Main.start("reader-" + i, () -> {
                    rw.readLock().lock();
                    try {
                        peak.accumulateAndGet(rw.stats().readers(), Math::max);
                        allIn.countDown();
                        release.await(5, TimeUnit.SECONDS);
                    } finally { rw.readLock().unlock(); }
                });
            }
            boolean together = allIn.await(5, TimeUnit.SECONDS);
            check(together, "six readers are inside the read lock at the same time");
            check(peak.get() == n, "the lock itself counted all six (peak readers = " + peak.get() + ")");
            check(rw.stats().writerActive() == false, "and no writer is inside while they read");
            release.countDown();
        }

        // 2. a writer is alone: while it holds the lock no reader may enter, and they all enter after it leaves
        {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
            CountDownLatch writing = new CountDownLatch(1), letGo = new CountDownLatch(1);
            Thread writer = Main.start("writer", () -> {
                rw.writeLock().lock();
                try { writing.countDown(); letGo.await(5, TimeUnit.SECONDS); } finally { rw.writeLock().unlock(); }
            });
            writing.await(2, TimeUnit.SECONDS);
            check(!rw.readLock().tryLock(), "a reader cannot enter while a writer holds the lock");
            check(!rw.writeLock().tryLock(), "and a second writer cannot either");
            check(!rw.readLock().tryLock(200), "a reader that waits 200ms still gives up, and does not hang");
            letGo.countDown();
            writer.join(3000);
            check(rw.readLock().tryLock(1000), "the moment the writer leaves, a reader gets in");
            rw.readLock().unlock();
        }

        // 3. the stress: eight readers and four writers on one document. A reader must never see a half-written
        //    document, and every write must land exactly once.
        {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
            SharedDocument doc = new SharedDocument(16);
            int readers = 8, writers = 4, readsEach = 3000, writesEach = 200;
            CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(readers + writers);
            for (int i = 0; i < readers; i++) {
                Main.start("r" + i, () -> {
                    go.await();
                    for (int k = 0; k < readsEach; k++) {
                        rw.readLock().lock();
                        try { doc.readAll(); } finally { rw.readLock().unlock(); }
                    }
                    done.countDown();
                });
            }
            for (int i = 0; i < writers; i++) {
                Main.start("w" + i, () -> {
                    go.await();
                    for (int k = 0; k < writesEach; k++) {
                        rw.writeLock().lock();
                        try { doc.bumpAll(); } finally { rw.writeLock().unlock(); }
                    }
                    done.countDown();
                });
            }
            go.countDown();
            check(done.await(20, TimeUnit.SECONDS), "24000 reads and 800 writes finish with nobody stuck");
            check(doc.tornReads.get() == 0, "no reader ever saw a half-written document (torn reads = " + doc.tornReads.get() + ")");
            check(doc.overlaps.get() == 0, "no reader was ever inside beside a writer, and no two writers met");
            check(doc.value() == writers * writesEach, "every write landed exactly once: " + doc.value() + " of " + (writers * writesEach));
        }

        // 4. writer preference: a writer that is already queued is not overtaken by readers that arrive later,
        //    which is the whole point of the rule -- a writer cannot be starved by a stream of readers.
        {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
            List<String> order = Collections.synchronizedList(new ArrayList<>());
            CountDownLatch holding = new CountDownLatch(1), letGo = new CountDownLatch(1);
            Thread holder = Main.start("first-reader", () -> {
                rw.readLock().lock();
                try { holding.countDown(); letGo.await(5, TimeUnit.SECONDS); } finally { rw.readLock().unlock(); }
            });
            holding.await(2, TimeUnit.SECONDS);
            Thread writer = Main.start("writer", () -> {
                rw.writeLock().lock();
                try { order.add("writer"); } finally { rw.writeLock().unlock(); }
            });
            Main.awaitState(rw, s -> s.waitingWriters() == 1, 2000);
            check(!rw.readLock().tryLock(), "a reader arriving after a queued writer is made to wait");
            Thread late = Main.start("late-reader", () -> {
                rw.readLock().lock();
                try { order.add("late-reader"); } finally { rw.readLock().unlock(); }
            });
            Main.awaitState(rw, s -> s.waitingReaders() == 1, 2000);
            letGo.countDown();
            holder.join(3000); writer.join(3000); late.join(3000);
            check(order.equals(List.of("writer", "late-reader")), "the queued writer went in first, then the late reader: " + order);
        }

        // 5. the rule is a real knob, not a comment: the same scenario under the other two rules behaves
        //    differently, and that difference is one line of configuration.
        {
            RwLock loose = new RwLock();
            loose.configure(Policies.of(Policy.READER_PREFERENCE));
            CountDownLatch holding = new CountDownLatch(1), letGo = new CountDownLatch(1);
            Thread holder = Main.start("first-reader", () -> {
                loose.readLock().lock();
                try { holding.countDown(); letGo.await(5, TimeUnit.SECONDS); } finally { loose.readLock().unlock(); }
            });
            holding.await(2, TimeUnit.SECONDS);
            Thread writer = Main.start("writer", () -> {
                loose.writeLock().lock();
                try { /* nothing */ } finally { loose.writeLock().unlock(); }
            });
            Main.awaitState(loose, s -> s.waitingWriters() == 1, 2000);
            boolean overtook = loose.readLock().tryLock();
            check(overtook, "READER_PREFERENCE lets a new reader overtake the queued writer -- that is the starvation it buys");
            if (overtook) loose.readLock().unlock();
            letGo.countDown();
            holder.join(3000); writer.join(3000);

            RwLock fair = new RwLock();
            fair.configure(Policies.of(Policy.FAIR));
            List<String> order = Collections.synchronizedList(new ArrayList<>());
            CountDownLatch holding2 = new CountDownLatch(1), letGo2 = new CountDownLatch(1);
            Thread holder2 = Main.start("first-reader", () -> {
                fair.readLock().lock();
                try { holding2.countDown(); letGo2.await(5, TimeUnit.SECONDS); } finally { fair.readLock().unlock(); }
            });
            holding2.await(2, TimeUnit.SECONDS);
            Thread w2 = Main.start("writer", () -> {
                fair.writeLock().lock();
                try { order.add("writer"); } finally { fair.writeLock().unlock(); }
            });
            Main.awaitState(fair, s -> s.waitingWriters() == 1, 2000);
            Thread r2 = Main.start("late-reader", () -> {
                fair.readLock().lock();
                try { order.add("late-reader"); } finally { fair.readLock().unlock(); }
            });
            Main.awaitState(fair, s -> s.waitingReaders() == 1, 2000);
            letGo2.countDown();
            holder2.join(3000); w2.join(3000); r2.join(3000);
            check(order.equals(List.of("writer", "late-reader")), "FAIR grants in arrival order: " + order);
        }

        // 6. downgrade is allowed, upgrade is refused instead of deadlocking, and both sides are reentrant
        {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
            rw.writeLock().lock();
            rw.writeLock().lock();                                   // reentrant write: counts, does not block
            rw.writeLock().unlock();
            rw.readLock().lock();                                    // downgrade: still the writer, admitted at once
            rw.writeLock().unlock();
            check(rw.stats().readers() == 1 && !rw.stats().writerActive(), "write -> read downgrade leaves exactly one read hold");
            AtomicBoolean otherGotIn = new AtomicBoolean();
            Thread other = Main.start("other-writer", () -> {
                if (rw.writeLock().tryLock()) { otherGotIn.set(true); rw.writeLock().unlock(); }
            });
            other.join(2000);
            check(!otherGotIn.get(), "and another thread's writer is kept out while that read hold is alive");
            rw.readLock().lock();                                    // reentrant read
            rw.readLock().unlock();
            rw.readLock().unlock();
            check(rw.stats().readers() == 0, "both read holds released, the lock is free");

            rw.readLock().lock();
            boolean refused = false;
            long t0 = System.currentTimeMillis();
            try { rw.writeLock().lock(); } catch (IllegalStateException e) { refused = true; }
            long took = System.currentTimeMillis() - t0;
            rw.readLock().unlock();
            check(refused && took < 1000, "a read-to-write upgrade is refused at once (" + took + "ms), never a silent deadlock");
        }

        // 7. a waiter that gives up must leave no ghost behind, and a deadline must be testable without waiting
        {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
            CountDownLatch holding = new CountDownLatch(1), letGo = new CountDownLatch(1);
            Thread holder = Main.start("reader", () -> {
                rw.readLock().lock();
                try { holding.countDown(); letGo.await(5, TimeUnit.SECONDS); } finally { rw.readLock().unlock(); }
            });
            holding.await(2, TimeUnit.SECONDS);
            AtomicBoolean threw = new AtomicBoolean();
            Thread writer = new Thread(() -> {
                try { rw.writeLock().lock(); rw.writeLock().unlock(); }
                catch (InterruptedException e) { threw.set(true); }
            }, "doomed-writer");
            writer.start();
            Main.awaitState(rw, s -> s.waitingWriters() == 1, 2000);
            writer.interrupt();
            writer.join(3000);
            check(threw.get(), "interrupting a parked writer throws InterruptedException instead of ignoring it");
            check(rw.stats().waitingWriters() == 0, "and its ticket is gone from the queue, not left behind as a ghost");
            boolean got = rw.readLock().tryLock();
            check(got, "so readers are admitted again -- a ghost writer would have blocked them forever");
            if (got) rw.readLock().unlock();
            letGo.countDown();
            holder.join(3000);

            // the injected clock: a thirty-second deadline can pass in a millisecond of real time
            RwLock timed = new RwLock();
            timed.configure(Policies.of(Policy.WRITER_PREFERENCE));
            long[] fake = { 1_000_000L };
            timed.setClock(() -> { long now = fake[0]; fake[0] += 30_000; return now; });   // every look is 30s later
            CountDownLatch writing = new CountDownLatch(1), release = new CountDownLatch(1);
            Thread w = Main.start("writer", () -> {
                timed.writeLock().lock();
                try { writing.countDown(); release.await(5, TimeUnit.SECONDS); } finally { timed.writeLock().unlock(); }
            });
            writing.await(2, TimeUnit.SECONDS);
            long t0 = System.currentTimeMillis();
            boolean acquired = timed.readLock().tryLock(30_000);
            long realMs = System.currentTimeMillis() - t0;
            check(!acquired && realMs < 1000, "a 30s deadline expires on the injected clock in " + realMs + "ms of real time");
            release.countDown();
            w.join(3000);
        }

        // 8. the safety wrapper, a broken listener, and an unpaired unlock
        {
            // a fairness rule written by somebody in a hurry: "nobody ever waits"
            AdmissionPolicy reckless = new AdmissionPolicy() {
                public boolean readerMustWait(LockState s, long ticket) { return false; }
                public boolean writerMustWait(LockState s, long ticket) { return false; }
            };
            RwLock rw = new RwLock();
            rw.configure(reckless);
            SharedDocument doc = new SharedDocument(16);
            CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(6);
            for (int i = 0; i < 4; i++) {
                Main.start("r" + i, () -> {
                    go.await();
                    for (int k = 0; k < 2000; k++) { rw.readLock().lock(); try { doc.readAll(); } finally { rw.readLock().unlock(); } }
                    done.countDown();
                });
            }
            for (int i = 0; i < 2; i++) {
                Main.start("w" + i, () -> {
                    go.await();
                    for (int k = 0; k < 300; k++) { rw.writeLock().lock(); try { doc.bumpAll(); } finally { rw.writeLock().unlock(); } }
                    done.countDown();
                });
            }
            go.countDown();
            check(done.await(20, TimeUnit.SECONDS), "the reckless rule runs to completion");
            check(doc.overlaps.get() == 0 && doc.tornReads.get() == 0,
                  "a rule that says nobody waits still cannot put a reader beside a writer: SafePolicy wraps every rule");
            check(doc.value() == 600, "and every write still landed exactly once");

            // a listener that throws on every event
            RwLock noisy = new RwLock();
            noisy.configure(Policies.of(Policy.FAIR), e -> { throw new RuntimeException("the metrics box is down"); });
            noisy.writeLock().lock();
            noisy.writeLock().unlock();
            noisy.readLock().lock();
            noisy.readLock().unlock();
            check(noisy.stats().readers() == 0, "a listener that throws on every event cannot break lock or unlock");

            // unlocking something this thread does not hold
            boolean caught = false;
            try { noisy.readLock().unlock(); } catch (IllegalMonitorStateException e) { caught = true; }
            check(caught, "unlocking a read lock this thread does not hold is refused, not silently accepted");
            caught = false;
            try { noisy.writeLock().unlock(); } catch (IllegalMonitorStateException e) { caught = true; }
            check(caught, "and the same for the write lock");
        }

        // 9. the wait protocol itself: a wake means "look again", never "it is your turn". Waking every parked
        //    thread without changing one counter is exactly what a spurious wakeup looks like from inside await().
        {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
            CountDownLatch holding = new CountDownLatch(1), letGo = new CountDownLatch(1);
            Thread reader = Main.start("reader", () -> {
                rw.readLock().lock();
                try { holding.countDown(); letGo.await(5, TimeUnit.SECONDS); } finally { rw.readLock().unlock(); }
            });
            holding.await(2, TimeUnit.SECONDS);
            AtomicBoolean writerIn = new AtomicBoolean();
            Thread writer = Main.start("patient-writer", () -> {
                rw.writeLock().lock();
                try { writerIn.set(true); } finally { rw.writeLock().unlock(); }
            });
            Main.awaitState(rw, s -> s.waitingWriters() == 1, 2000);
            for (int i = 0; i < 200; i++) rw.wakeWaitersForTest();      // 200 spurious wakeups, no state change
            Thread.sleep(50);
            check(!writerIn.get(), "200 spurious wakeups let nobody in while a reader is still inside");
            check(rw.stats().waitingWriters() == 1, "the woken writer re-tested, parked again and kept its ticket");
            letGo.countDown();
            reader.join(3000); writer.join(3000);
            check(writerIn.get(), "the real change -- the last reader leaving -- is what admits it");
            rw.wakeWaitersForTest();                                    // a signal with nobody parked
            boolean got = rw.writeLock().tryLock();
            check(got, "a wake with nobody parked is dropped, and costs the next acquire nothing");
            if (got) rw.writeLock().unlock();
        }

        // 10. the same lock built from synchronized / wait / notifyAll holds the same invariant, with one wait
        //     set and a herd on every wake. If this passes, the design is the design and not the API.
        {
            MonitorRwLock mon = new MonitorRwLock();
            SharedDocument doc = new SharedDocument(16);
            int readers = 4, writers = 2, readsEach = 1500, writesEach = 200;
            CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(readers + writers);
            for (int i = 0; i < readers; i++) {
                Main.start("mr" + i, () -> {
                    go.await();
                    for (int k = 0; k < readsEach; k++) {
                        mon.lockRead();
                        try { doc.readAll(); } finally { mon.unlockRead(); }
                    }
                    done.countDown();
                });
            }
            for (int i = 0; i < writers; i++) {
                Main.start("mw" + i, () -> {
                    go.await();
                    for (int k = 0; k < writesEach; k++) {
                        mon.lockWrite();
                        try { doc.bumpAll(); } finally { mon.unlockWrite(); }
                    }
                    done.countDown();
                });
            }
            go.countDown();
            check(done.await(20, TimeUnit.SECONDS), "the synchronized build finishes 6000 reads and 400 writes with nobody stuck");
            check(doc.overlaps.get() == 0 && doc.tornReads.get() == 0,
                  "one monitor and notifyAll still never put a reader beside a writer");
            check(doc.value() == writers * writesEach, "and every write landed exactly once: " + doc.value());
        }

        System.out.println();
        if (failures == 0) System.out.println("ALL PASS");
        else System.out.println(failures + " CHECK(S) FAILED");
        System.out.flush();
        System.exit(failures == 0 ? 0 : 1);
    }
}
