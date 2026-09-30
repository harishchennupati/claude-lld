import java.util.ArrayDeque;
import java.util.Deque;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Predicate;

/** Where time comes from. Injected everywhere, so a test can move the clock instead of waiting for it. */
interface Clock { long nowMs(); }

/**
 * Which fairness rule the lock runs. The constant is only a key into the registry of rules; the rule itself
 * is a class, so a fourth rule is a new class and one registry line.
 */
enum Policy { READER_PREFERENCE, WRITER_PREFERENCE, FAIR }

/** What just happened to the lock. Handed to observers after the mutex is released, never inside it. */
enum EventKind { READ_ACQUIRED, READ_RELEASED, WRITE_ACQUIRED, WRITE_RELEASED }

/**
 * One thing that happened, with the time the thread spent waiting for it, measured with the injected clock.
 * readersAfter is the reader count captured inside the critical section, so it is never a half-updated number.
 */
record LockEvent(EventKind kind, String threadName, long waitedMs, int readersAfter) {}

/** Anyone who wants to know: metrics, a log, a starvation alarm. A broken observer cannot break the lock. */
interface LockObserver { void onEvent(LockEvent e); }

/**
 * One side of the lock as a caller sees it. Pair every successful acquire with exactly one unlock, in a
 * finally block. lock() blocks until admitted and throws if the thread is interrupted while it waits.
 */
interface Lock {
    /** Wait until this side is admitted. Throws if the thread is interrupted while parked. */
    void lock() throws InterruptedException;
    /** Take it only if it is free right now. Never parks, never throws. */
    boolean tryLock();
    /** Take it, giving up at the deadline. The deadline is computed from the injected clock. */
    boolean tryLock(long timeoutMs) throws InterruptedException;
    /** Give this side back. Throws IllegalMonitorStateException if this thread does not hold it. */
    void unlock();
}

/**
 * The read-only view of the lock's counters. This, and only this, is what a fairness rule may see: it can
 * decide who waits, and it cannot touch the state that decides who is inside.
 */
interface LockState {
    /** How many threads are inside the read side right now. */
    int readers();
    /** Is a thread inside the write side right now. */
    boolean writerActive();
    /** How many readers are parked. */
    int waitingReaders();
    /** How many writers are parked. */
    int waitingWriters();
    /** The ticket of the longest-waiting writer, or Long.MAX_VALUE when no writer is parked. */
    long earliestWaitingWriterTicket();
    /** The ticket of the longest-waiting thread of either kind, or Long.MAX_VALUE when nobody is parked. */
    long earliestWaitingTicket();
}

/**
 * The fairness rule, and nothing else: given the counters and this waiter's arrival ticket, must it wait?
 * Two questions because the lock has two sides. It answers; the lock does the parking and the waking.
 */
interface AdmissionPolicy {
    /** Must a reader holding this ticket park instead of going in? */
    boolean readerMustWait(LockState s, long ticket);
    /** Must a writer holding this ticket park instead of going in? */
    boolean writerMustWait(LockState s, long ticket);
}

/**
 * Readers first: a reader goes in whenever no writer is inside, even if writers are queued. Highest read
 * throughput, and a writer can be starved forever by a steady stream of readers. That is the trade, said aloud.
 */
final class ReaderPreference implements AdmissionPolicy {
    public boolean readerMustWait(LockState s, long ticket) { return s.writerActive(); }
    public boolean writerMustWait(LockState s, long ticket) { return s.writerActive() || s.readers() > 0; }
}

/**
 * Writers first: a reader that arrives while a writer is queued waits behind it, so the readers already
 * inside drain and the writer gets in. Writers cannot starve; a long read storm pauses instead of continuing.
 */
final class WriterPreference implements AdmissionPolicy {
    public boolean readerMustWait(LockState s, long ticket) { return s.writerActive() || s.waitingWriters() > 0; }
    public boolean writerMustWait(LockState s, long ticket) { return s.writerActive() || s.readers() > 0; }
}

/**
 * Arrival order: nobody overtakes a thread that got here first. Readers that arrived with no writer ahead of
 * them still go in together, so this is FIFO between the two sides, not one thread at a time.
 */
final class FairOrder implements AdmissionPolicy {
    public boolean readerMustWait(LockState s, long ticket) {
        return s.writerActive() || s.earliestWaitingWriterTicket() < ticket;
    }
    public boolean writerMustWait(LockState s, long ticket) {
        return s.writerActive() || s.readers() > 0 || s.earliestWaitingTicket() < ticket;
    }
}

/**
 * Decorator. Wraps any fairness rule and adds the safety rule on top: never a reader beside a writer, never
 * two writers. A rule written next year can get fairness wrong and still cannot corrupt the guarded data,
 * because this wrapper is consulted first and the lock only ever wraps what it is handed.
 */
final class SafePolicy implements AdmissionPolicy {
    private final AdmissionPolicy base;
    SafePolicy(AdmissionPolicy base) { this.base = base; }
    public boolean readerMustWait(LockState s, long ticket) {
        if (s.writerActive()) return true;                       // safety: not negotiable
        return base.readerMustWait(s, ticket);                   // fairness: the base's business
    }
    public boolean writerMustWait(LockState s, long ticket) {
        if (s.writerActive() || s.readers() > 0) return true;    // safety: not negotiable
        return base.writerMustWait(s, ticket);
    }
    /** What was wrapped, for a page that wants to print the rule's name. */
    AdmissionPolicy base() { return base; }
}

/** The registry of built-in rules. Every rule is stateless, so one instance serves every lock in the process. */
final class Policies {
    private Policies() {}
    static final Map<Policy, AdmissionPolicy> REGISTRY = new EnumMap<>(Policy.class);
    static {
        REGISTRY.put(Policy.READER_PREFERENCE, new ReaderPreference());
        REGISTRY.put(Policy.WRITER_PREFERENCE, new WriterPreference());
        REGISTRY.put(Policy.FAIR, new FairOrder());
    }
    /** O(1) lookup, and the one line that changes when a fourth rule arrives. */
    static AdmissionPolicy of(Policy p) { return REGISTRY.get(p); }
}

/** A consistent copy of the counters, taken under the mutex. For tests, metrics and demos -- never for a decision. */
record LockStats(int readers, boolean writerActive, int waitingReaders, int waitingWriters) {}

/**
 * The whole lock: three numbers, one mutex and two conditions. Everything else in this file is a view of it.
 *
 * The invariant it exists to hold: while a writer is inside, every reader inside is that same thread (the
 * downgrade case), and no second writer is inside. Every wait() in here blocks a transition that would break it.
 */
final class Sync implements LockState {
    /** Park until admitted. */
    static final int BLOCK = 0;
    /** Do not park at all: take it or report failure. */
    static final int NO_WAIT = 1;
    /** Park, but give up at the deadline. */
    static final int TIMED = 2;

    private final ReentrantLock mutex = new ReentrantLock();
    private final Condition okToRead = mutex.newCondition();
    private final Condition okToWrite = mutex.newCondition();
    private final Deque<Long> readerQueue = new ArrayDeque<>();   // arrival order, so peekFirst is the oldest
    private final Deque<Long> writerQueue = new ArrayDeque<>();
    private final ThreadLocal<int[]> readHolds = ThreadLocal.withInitial(() -> new int[1]);
    private final List<LockObserver> observers = new CopyOnWriteArrayList<>();
    private int readers;
    private int writerHolds;
    private Thread writerOwner;
    private long nextTicket = 1;
    private AdmissionPolicy policy = new SafePolicy(new WriterPreference());
    private Clock clock = System::currentTimeMillis;

    /** Hand in the fairness rule and the listeners. Call it once, before the lock is handed to any thread. */
    void configure(AdmissionPolicy rule, LockObserver... listeners) {
        mutex.lock();
        try {
            if (readers > 0 || writerHolds > 0 || !readerQueue.isEmpty() || !writerQueue.isEmpty())
                throw new IllegalStateException("configure the lock before anyone uses it");
            this.policy = new SafePolicy(rule);                   // every rule is wrapped: safety is not optional
            for (LockObserver o : listeners) observers.add(o);
        } finally { mutex.unlock(); }
    }

    /** Hand in the clock. A test injects one so a deadline can pass without the test waiting for it. */
    void setClock(Clock c) { this.clock = c; }

    /** The rule in force, already wrapped in SafePolicy. */
    AdmissionPolicy policy() { return policy; }

    // ---------------- the read side

    /**
     * Get in as a reader. Returns false only when the caller said it would not wait (NO_WAIT) or its deadline
     * passed (TIMED). A thread that already holds either side is admitted at once: it cannot release what it
     * holds while it waits, so parking it would be a deadlock with itself.
     */
    boolean acquireRead(int mode, long timeoutMs) throws InterruptedException {
        long startedMs = clock.nowMs();
        boolean admitted = false;
        int readersAfter = 0;
        mutex.lock();
        try {
            int[] mine = readHolds.get();
            if (mine[0] > 0 || writerOwner == Thread.currentThread()) {
                mine[0]++; readers++; admitted = true;            // reentrant read, or a write-to-read downgrade
            } else {
                long ticket = nextTicket++;
                if (!policy.readerMustWait(this, ticket)) {
                    admitted = true;
                } else if (mode != NO_WAIT) {
                    readerQueue.addLast(ticket);
                    boolean gaveUp = false;
                    try {
                        long deadline = startedMs + timeoutMs;
                        while (policy.readerMustWait(this, ticket)) {   // while, never if: re-test after every wake
                            if (mode == TIMED) {
                                long remain = deadline - clock.nowMs();
                                if (remain <= 0) { gaveUp = true; break; }
                                okToRead.await(remain, TimeUnit.MILLISECONDS);
                            } else {
                                okToRead.await();                      // the mutex is released while parked here
                            }
                        }
                        admitted = !gaveUp;
                    } catch (InterruptedException e) {
                        gaveUp = true;
                        throw e;
                    } finally {
                        readerQueue.removeFirstOccurrence(ticket);     // never leave a ghost in the queue
                        if (gaveUp) wakeBoth();                        // our leaving can admit somebody behind us
                    }
                }
                if (admitted) { mine[0] = 1; readers++; }
            }
            readersAfter = readers;
        } finally { mutex.unlock(); }
        if (admitted) publish(EventKind.READ_ACQUIRED, startedMs, readersAfter);
        return admitted;
    }

    /**
     * Give the read side back. Only the last reader out wakes anybody, and it wakes writers only: a reader that
     * is parked is parked because of a writer, and no writer state changed here.
     */
    void releaseRead() {
        int readersAfter;
        mutex.lock();
        try {
            int[] mine = readHolds.get();
            if (mine[0] == 0) throw new IllegalMonitorStateException("this thread does not hold the read lock");
            mine[0]--;
            readers--;
            if (mine[0] == 0) readHolds.remove();
            readersAfter = readers;
            if (readers == 0) okToWrite.signalAll();               // only now can a writer make progress
        } finally { mutex.unlock(); }
        publish(EventKind.READ_RELEASED, 0, readersAfter);
    }

    // ---------------- the write side

    /**
     * Get in as a writer, alone. A thread that already holds the write side re-enters and only counts up. A
     * thread that holds the READ side is refused loudly: read-to-write upgrade is the classic deadlock, because
     * two upgraders would each wait for the other's read hold to go away.
     */
    boolean acquireWrite(int mode, long timeoutMs) throws InterruptedException {
        long startedMs = clock.nowMs();
        boolean admitted = false, reentered = false;
        int readersAfter = 0;
        mutex.lock();
        try {
            if (writerOwner == Thread.currentThread()) {
                writerHolds++; reentered = true;                   // reentrant write
            } else {
                if (readHolds.get()[0] > 0)
                    throw new IllegalStateException("read-to-write upgrade would deadlock: release the read hold first");
                long ticket = nextTicket++;
                if (!policy.writerMustWait(this, ticket)) {
                    admitted = true;
                } else if (mode != NO_WAIT) {
                    writerQueue.addLast(ticket);
                    boolean gaveUp = false;
                    try {
                        long deadline = startedMs + timeoutMs;
                        while (policy.writerMustWait(this, ticket)) {
                            if (mode == TIMED) {
                                long remain = deadline - clock.nowMs();
                                if (remain <= 0) { gaveUp = true; break; }
                                okToWrite.await(remain, TimeUnit.MILLISECONDS);
                            } else {
                                okToWrite.await();
                            }
                        }
                        admitted = !gaveUp;
                    } catch (InterruptedException e) {
                        gaveUp = true;
                        throw e;
                    } finally {
                        writerQueue.removeFirstOccurrence(ticket);
                        if (gaveUp) wakeBoth();                    // a cancelled writer must stop blocking readers
                    }
                }
                if (admitted) { writerOwner = Thread.currentThread(); writerHolds = 1; }
            }
            readersAfter = readers;
        } finally { mutex.unlock(); }
        if (admitted) publish(EventKind.WRITE_ACQUIRED, startedMs, readersAfter);
        return admitted || reentered;
    }

    /**
     * Give the write side back. The last release wakes both sides, because with a swappable rule the lock does
     * not know which side may now go in; each woken thread re-tests its own predicate and parks again if not.
     */
    void releaseWrite() {
        boolean fully = false;
        int readersAfter;
        mutex.lock();
        try {
            if (writerOwner != Thread.currentThread())
                throw new IllegalMonitorStateException("this thread does not hold the write lock");
            if (--writerHolds == 0) { writerOwner = null; fully = true; wakeBoth(); }
            readersAfter = readers;
        } finally { mutex.unlock(); }
        if (fully) publish(EventKind.WRITE_RELEASED, 0, readersAfter);
    }

    // ---------------- the counters, read only while the mutex is held

    public int readers() { return readers; }
    public boolean writerActive() { return writerHolds > 0; }
    public int waitingReaders() { return readerQueue.size(); }
    public int waitingWriters() { return writerQueue.size(); }
    public long earliestWaitingWriterTicket() { Long t = writerQueue.peekFirst(); return t == null ? Long.MAX_VALUE : t; }
    public long earliestWaitingTicket() {
        Long r = readerQueue.peekFirst();
        return Math.min(earliestWaitingWriterTicket(), r == null ? Long.MAX_VALUE : r);
    }

    /** A copy of the counters, taken under the mutex, so another thread can look without racing. */
    LockStats snapshot() {
        mutex.lock();
        try { return new LockStats(readers, writerHolds > 0, readerQueue.size(), writerQueue.size()); }
        finally { mutex.unlock(); }
    }

    /** How many read holds THIS thread has. Used to spot an upgrade, and by tests. */
    int myReadHolds() { return readHolds.get()[0]; }

    /**
     * For tests: wake every parked thread without changing one counter. That is exactly what a spurious wakeup
     * looks like from inside await(), so this is how the while loop gets proved instead of merely claimed.
     */
    void wakeWaitersForTest() {
        mutex.lock();
        try { wakeBoth(); } finally { mutex.unlock(); }
    }

    private void wakeBoth() { okToRead.signalAll(); okToWrite.signalAll(); }

    /** Told after the mutex is released. A listener that throws is logged and ignored; the lock is already safe. */
    private void publish(EventKind kind, long startedMs, int readersAfter) {
        if (observers.isEmpty()) return;
        long waited = startedMs == 0 ? 0 : clock.nowMs() - startedMs;
        LockEvent e = new LockEvent(kind, Thread.currentThread().getName(), waited, readersAfter);
        for (LockObserver o : observers) {
            try { o.onEvent(e); } catch (RuntimeException ignored) { /* a broken listener is not the lock's problem */ }
        }
    }
}

/** The read side. It owns nothing: it is a handle on the one Sync, which is why both sides see one set of counters. */
final class ReadLock implements Lock {
    private final Sync sync;
    ReadLock(Sync sync) { this.sync = sync; }
    public void lock() throws InterruptedException { sync.acquireRead(Sync.BLOCK, 0); }
    public boolean tryLock() {
        try { return sync.acquireRead(Sync.NO_WAIT, 0); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
    }
    public boolean tryLock(long timeoutMs) throws InterruptedException { return sync.acquireRead(Sync.TIMED, timeoutMs); }
    public void unlock() { sync.releaseRead(); }
}

/** The write side. Same handle-over-one-Sync shape as the read side, which is what makes them interchangeable. */
final class WriteLock implements Lock {
    private final Sync sync;
    WriteLock(Sync sync) { this.sync = sync; }
    public void lock() throws InterruptedException { sync.acquireWrite(Sync.BLOCK, 0); }
    public boolean tryLock() {
        try { return sync.acquireWrite(Sync.NO_WAIT, 0); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
    }
    public boolean tryLock(long timeoutMs) throws InterruptedException { return sync.acquireWrite(Sync.TIMED, timeoutMs); }
    public void unlock() { sync.releaseWrite(); }
}

/**
 * What a caller is given: two lock handles over one core. It builds the Sync and the two views and nothing
 * else, and it never builds a fairness rule -- that is handed in through configure().
 */
final class RwLock {
    private final Sync sync = new Sync();
    private final Lock read = new ReadLock(sync);
    private final Lock write = new WriteLock(sync);

    /** Hand in the fairness rule and any listeners. Do it once, before any thread touches the lock. */
    void configure(AdmissionPolicy rule, LockObserver... listeners) { sync.configure(rule, listeners); }
    /** Hand in the clock used for deadlines and for the waited-for time in events. */
    void setClock(Clock c) { sync.setClock(c); }
    /** The shared read side. Many threads may hold it at once. */
    Lock readLock() { return read; }
    /** The exclusive write side. One thread, and no readers. */
    Lock writeLock() { return write; }
    /** A consistent copy of the counters, for a test or a dashboard. */
    LockStats stats() { return sync.snapshot(); }
    /** How many read holds the calling thread has right now. */
    int myReadHolds() { return sync.myReadHolds(); }

    /** For tests: a wake with nothing changed, which is what a spurious wakeup is. */
    void wakeWaitersForTest() { sync.wakeWaitersForTest(); }
}

/**
 * The data the lock guards -- a row of cells that must always read the same number. A writer bumps them one at
 * a time, so a reader that sees two different numbers has caught a writer half way through: a torn read, which
 * is the exact bug the lock exists to prevent. The counters here are the proof, not part of the lock.
 */
final class SharedDocument {
    private final int[] cells;
    private final AtomicInteger activeReaders = new AtomicInteger();
    private final AtomicInteger activeWriters = new AtomicInteger();
    final AtomicInteger tornReads = new AtomicInteger();
    final AtomicInteger overlaps = new AtomicInteger();
    final AtomicInteger maxConcurrentReaders = new AtomicInteger();

    SharedDocument(int cellCount) { this.cells = new int[cellCount]; }

    /** Call ONLY while holding the write lock. Bumps every cell, slowly on purpose, so a torn read is visible. */
    void bumpAll() {
        activeWriters.incrementAndGet();
        if (activeReaders.get() != 0 || activeWriters.get() != 1) overlaps.incrementAndGet();
        for (int i = 0; i < cells.length; i++) { cells[i]++; Thread.onSpinWait(); }
        activeWriters.decrementAndGet();
    }

    /** Call ONLY while holding the read lock. Returns the number every cell must agree on. */
    int readAll() {
        int now = activeReaders.incrementAndGet();
        maxConcurrentReaders.accumulateAndGet(now, Math::max);
        if (activeWriters.get() != 0) overlaps.incrementAndGet();
        int first = cells[0];
        boolean torn = false;
        for (int c : cells) { if (c != first) torn = true; Thread.onSpinWait(); }
        if (torn) tornReads.incrementAndGet();
        activeReaders.decrementAndGet();
        return first;
    }

    /** The value with no locking at all, for a report printed when every thread has stopped. */
    int value() { return cells[0]; }
}

/** Counts what the lock did and the longest anybody waited. Pre-filled so no thread ever resizes the map. */
final class Metrics implements LockObserver {
    private final Map<EventKind, AtomicInteger> counts = new EnumMap<>(EventKind.class);
    private final AtomicLong longestWaitMs = new AtomicLong();
    Metrics() { for (EventKind k : EventKind.values()) counts.put(k, new AtomicInteger()); }
    public void onEvent(LockEvent e) {
        counts.get(e.kind()).incrementAndGet();
        longestWaitMs.accumulateAndGet(e.waitedMs(), Math::max);
    }
    /** How many events of this kind, O(1). */
    int count(EventKind k) { return counts.get(k).get(); }
    /** The longest any single thread waited to be let in, in milliseconds of the injected clock. */
    long longestWaitMs() { return longestWaitMs.get(); }
}

/** A body that may throw, so a demo thread can report the exception instead of swallowing it. */
interface ThrowingBody { void run() throws Exception; }

/** The demo and the many-thread race. Everything it prints is a claim FailureTests proves. */
public class Main {

    /** Start a named thread that prints and remembers any exception instead of dying quietly. */
    static Thread start(String name, ThrowingBody body) {
        Thread t = new Thread(() -> {
            try { body.run(); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            catch (Exception e) { System.out.println("  ! " + name + " threw " + e); }
        }, name);
        t.start();
        return t;
    }

    /**
     * Wait until the lock's counters satisfy a test, or give up. Used instead of sleeping a guessed number of
     * milliseconds, and used instead of waiting forever: a test that can hang is not a test.
     */
    static boolean awaitState(RwLock rw, Predicate<LockStats> test, long timeoutMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (test.test(rw.stats())) return true;
            Thread.sleep(1);
        }
        return test.test(rw.stats());
    }

    public static void main(String[] args) throws Exception {
        demo();
        policyComparison();
        race();
    }

    /** One writer and three readers on one document: the readers overlap, the writer is alone. */
    private static void demo() throws Exception {
        System.out.println("== one document, three readers and one writer ==");
        SharedDocument doc = new SharedDocument(8);
        Metrics metrics = new Metrics();
        RwLock rw = new RwLock();
        rw.configure(Policies.of(Policy.WRITER_PREFERENCE), metrics);

        CountDownLatch insideTogether = new CountDownLatch(3);
        CountDownLatch holdUntil = new CountDownLatch(1);
        for (int i = 1; i <= 3; i++) {
            start("reader-" + i, () -> {
                rw.readLock().lock();
                try {
                    insideTogether.countDown();
                    holdUntil.await(2, TimeUnit.SECONDS);          // hold, so the overlap is visible
                    doc.readAll();
                } finally { rw.readLock().unlock(); }
            });
        }
        System.out.println("three readers inside at once: " + insideTogether.await(2, TimeUnit.SECONDS)
                           + "  counters " + rw.stats());

        Thread writer = start("writer-1", () -> {
            rw.writeLock().lock();
            try { doc.bumpAll(); } finally { rw.writeLock().unlock(); }
        });
        awaitState(rw, s -> s.waitingWriters() == 1, 2000);
        System.out.println("the writer is queued, and with WRITER_PREFERENCE a new reader now waits behind it: "
                           + !rw.readLock().tryLock() + "  counters " + rw.stats());
        holdUntil.countDown();
        writer.join(2000);
        System.out.println("after the writer: value=" + doc.value() + " torn reads=" + doc.tornReads.get()
                           + " reader-beside-writer=" + doc.overlaps.get());

        // downgrade: hold the write lock, take the read lock, then drop the write lock. Legal, and useful:
        // you publish a change and keep reading it without anybody else writing in between.
        rw.writeLock().lock();
        doc.bumpAll();
        rw.readLock().lock();                                       // still the writer: admitted at once
        rw.writeLock().unlock();                                    // now only a reader
        System.out.println("downgraded write -> read, holding " + rw.myReadHolds() + " read hold, counters " + rw.stats());
        rw.readLock().unlock();

        // upgrade: refused loudly rather than deadlocking quietly
        rw.readLock().lock();
        try { rw.writeLock().lock(); System.out.println("  ! upgrade should not be allowed"); }
        catch (IllegalStateException e) { System.out.println("upgrade refused: " + e.getMessage()); }
        finally { rw.readLock().unlock(); }

        System.out.println("metrics: reads=" + metrics.count(EventKind.READ_ACQUIRED)
                           + " writes=" + metrics.count(EventKind.WRITE_ACQUIRED)
                           + " longest wait=" + metrics.longestWaitMs() + "ms");
    }

    /** The same lock, the same code, one line different: the rule decides who suffers. */
    private static void policyComparison() throws Exception {
        System.out.println();
        System.out.println("== the same read storm under two rules ==");
        for (Policy p : List.of(Policy.READER_PREFERENCE, Policy.WRITER_PREFERENCE)) {
            RwLock rw = new RwLock();
            rw.configure(Policies.of(p));
            SharedDocument doc = new SharedDocument(8);
            AtomicInteger reads = new AtomicInteger();
            AtomicLong writerWaitedMs = new AtomicLong(-1);
            long stormEnds = System.currentTimeMillis() + 300;

            Thread[] storm = new Thread[6];
            for (int i = 0; i < storm.length; i++) {
                storm[i] = start("storm-" + i, () -> {
                    while (System.currentTimeMillis() < stormEnds) {
                        rw.readLock().lock();
                        try { doc.readAll(); reads.incrementAndGet(); Thread.sleep(1); }   // a read that does real work
                        finally { rw.readLock().unlock(); }
                    }
                });
            }
            Thread.sleep(30);                                        // let the storm get going
            Thread writer = start("late-writer", () -> {
                long t0 = System.currentTimeMillis();
                rw.writeLock().lock();
                try { writerWaitedMs.set(System.currentTimeMillis() - t0); doc.bumpAll(); }
                finally { rw.writeLock().unlock(); }
            });
            for (Thread t : storm) t.join(3000);
            writer.join(3000);
            System.out.println(p + ": " + reads.get() + " reads during the storm, the writer waited "
                               + writerWaitedMs.get() + "ms, torn reads=" + doc.tornReads.get());
        }
    }

    /** Twelve threads at one instant on one document: many readers, four writers, and the invariant must hold. */
    private static void race() throws Exception {
        System.out.println();
        System.out.println("== 8 readers + 4 writers, all released at the same instant ==");
        SharedDocument doc = new SharedDocument(16);
        Metrics metrics = new Metrics();
        RwLock rw = new RwLock();
        rw.configure(Policies.of(Policy.FAIR), metrics);

        int readerCount = 8, writerCount = 4, readsEach = 4000, writesEach = 50;
        CountDownLatch go = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(readerCount + writerCount);
        AtomicInteger reads = new AtomicInteger();

        for (int i = 0; i < readerCount; i++) {
            start("reader-" + i, () -> {
                go.await();
                for (int k = 0; k < readsEach; k++) {
                    rw.readLock().lock();
                    try { doc.readAll(); reads.incrementAndGet(); } finally { rw.readLock().unlock(); }
                }
                done.countDown();
            });
        }
        for (int i = 0; i < writerCount; i++) {
            start("writer-" + i, () -> {
                go.await();
                for (int k = 0; k < writesEach; k++) {
                    rw.writeLock().lock();
                    try { doc.bumpAll(); } finally { rw.writeLock().unlock(); }
                    Thread.sleep(1);                                 // a real system writes now and then, not always
                }
                done.countDown();
            });
        }
        long t0 = System.currentTimeMillis();
        go.countDown();
        boolean finished = done.await(30, TimeUnit.SECONDS);
        long ms = System.currentTimeMillis() - t0;

        System.out.println("rule=FAIR  finished=" + finished + " in " + ms + "ms");
        System.out.println("writes applied: " + doc.value() + " (must be " + (writerCount * writesEach) + ")");
        System.out.println("reads: " + reads.get() + "   torn reads: " + doc.tornReads.get()
                           + "   reader-beside-writer: " + doc.overlaps.get());
        System.out.println("most readers inside at once: " + doc.maxConcurrentReaders.get() + " (1 would mean no sharing)");
        System.out.println("lock events: " + metrics.count(EventKind.READ_ACQUIRED) + " read, "
                           + metrics.count(EventKind.WRITE_ACQUIRED) + " write");
        if (!finished || doc.tornReads.get() != 0 || doc.overlaps.get() != 0 || doc.value() != writerCount * writesEach)
            throw new AssertionError("the lock let somebody in it should not have");
    }
}
