import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;
import java.util.concurrent.locks.StampedLock;
import java.util.function.Function;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: optimistic reads -- the fastest read is the one that never takes the lock
/**
 * A StampedLock hands out a stamp instead of a hold. You read the fields with no lock at all, then ask whether
 * a writer moved in the meantime; if one did, you read again, this time under a real read lock. It costs a
 * reader nothing when writes are rare, which is exactly when a read-write lock is worth having. The catch: the
 * optimistic body must be short, side-effect free and safe to run twice, because it can be thrown away.
 */
final class OptimisticPoint {
    private final StampedLock sl = new StampedLock();
    private double x, y;

    /** A write, exclusive, exactly like the write side of our lock. */
    void move(double dx, double dy) {
        long stamp = sl.writeLock();
        try { x += dx; y += dy; } finally { sl.unlockWrite(stamp); }
    }

    /** Read with no lock, then validate. Only a reader that lost the race pays for a real read lock. */
    double distanceFromOrigin() {
        long stamp = sl.tryOptimisticRead();
        double cx = x, cy = y;                                  // may be torn; validate() is what decides
        if (!sl.validate(stamp)) {
            stamp = sl.readLock();
            try { cx = x; cy = y; } finally { sl.unlockRead(stamp); }
        }
        return Math.sqrt(cx * cx + cy * cy);
    }
}

/**
 * The same trick by hand, so the mechanism is not magic: a version counter that is odd while a writer is
 * inside. A reader takes the version, reads the fields, and takes the version again; if it moved, it retries.
 * Writers must still be serialised by something (hold the write lock around set); only the readers go free.
 */
final class SeqLockPair {
    private final AtomicLong version = new AtomicLong();
    private volatile int a, b;

    /** One writer at a time -- hold the write lock around this. The odd version is the "do not trust me" flag. */
    void set(int na, int nb) {
        long v = version.get();
        version.set(v + 1);                                     // odd: a write is in progress
        a = na; b = nb;
        version.set(v + 2);                                     // even again: the pair is consistent
    }

    /** Never blocks. Repeats the read if a writer touched the pair while it was reading. */
    int[] get() {
        while (true) {
            long before = version.get();
            if ((before & 1) != 0) { Thread.onSpinWait(); continue; }   // a writer is inside; try again
            int ra = a, rb = b;
            if (version.get() == before) return new int[] { ra, rb };
        }
    }
}

// ---- ext: a condition variable on the write lock -- await() must drop the WHOLE hold and take it back
/**
 * "Wait until the document is not empty" needs a condition bound to the write lock. The hard part is not the
 * parking: it is that await() has to give the write hold up, or nobody can ever change the thing it is waiting
 * for, and then take it back before returning, or the caller comes back holding less than it had. The
 * re-acquire is done ignoring interruption and the flag is restored afterwards, which is what a real
 * Condition does: you may be cancelled, but you never come back without your lock.
 */
final class WriteCondition {
    private final RwLock rw;
    private final Deque<CountDownLatch> waiters = new ArrayDeque<>();
    private final ReentrantLock guard = new ReentrantLock();

    WriteCondition(RwLock rw) { this.rw = rw; }

    /**
     * Call while holding the write lock exactly once. Returns true if signalled, false if the timeout won.
     * A full implementation would record the hold count first and restore it; this one assumes a single hold.
     */
    boolean await(long timeoutMs) throws InterruptedException {
        CountDownLatch mine = new CountDownLatch(1);
        guard.lock();
        try { waiters.addLast(mine); } finally { guard.unlock(); }
        rw.writeLock().unlock();                                  // drop it, or nobody can signal us
        try {
            return mine.await(timeoutMs, TimeUnit.MILLISECONDS);
        } finally {
            boolean interrupted = Thread.interrupted();           // clear it so the re-acquire cannot fail
            while (true) {
                try { rw.writeLock().lock(); break; }
                catch (InterruptedException again) { interrupted = true; }
            }
            if (interrupted) Thread.currentThread().interrupt();  // hand the interrupt back to the caller
        }
    }

    /** Wake the longest waiter. Call while holding the write lock, exactly like Condition.signal(). */
    void signal() {
        guard.lock();
        try { CountDownLatch w = waiters.pollFirst(); if (w != null) w.countDown(); } finally { guard.unlock(); }
    }

    /** Wake everybody; each one re-tests its own predicate in a while loop, as always. */
    void signalAll() {
        guard.lock();
        try { CountDownLatch w; while ((w = waiters.pollFirst()) != null) w.countDown(); } finally { guard.unlock(); }
    }
}

// ---- ext: the same lock from a semaphore -- N permits, and a writer takes all N
/**
 * Ten lines, no conditions, obviously correct: a reader takes one permit, a writer takes all of them at once.
 * acquire(MAX) is the trick -- taking permits one at a time would let readers keep slipping in. What you give
 * up is the knob: at most MAX readers, and the only fairness available is the semaphore's own FIFO flag.
 */
final class SemaphoreRwLock {
    static final int MAX_READERS = 64;
    private final Semaphore permits = new Semaphore(MAX_READERS, true);

    /** One permit: many readers can hold one each. */
    void lockRead() throws InterruptedException { permits.acquire(); }
    void unlockRead() { permits.release(); }
    /** All the permits, atomically, so no reader can be inside. */
    void lockWrite() throws InterruptedException { permits.acquire(MAX_READERS); }
    void unlockWrite() { permits.release(MAX_READERS); }
    /** How many readers could still get in right now. */
    int free() { return permits.availablePermits(); }
}

// ---- ext: the same lock from synchronized / wait / notifyAll -- one monitor, one wait set
/**
 * The whole lock again with nothing from java.util.concurrent: the object's own monitor, wait() and
 * notifyAll(). It keeps writer preference and the while loop, and it shows what one monitor costs. A monitor
 * has ONE wait set, so readers and writers park in the same queue and every wake is a wake for everybody --
 * that is the thundering herd. notify() would be a bug here: it may pick a reader that still cannot move, and
 * the writer that could move stays asleep. That is a lost wakeup, and it is why notify() is only safe when
 * every waiter is waiting for the same thing and any one of them can use the wake.
 */
final class MonitorRwLock {
    private int readers;
    private boolean writer;
    private int waitingWriters;

    /** Get in as a reader. The predicate is tested under the monitor, in a while loop, as in Main.java. */
    synchronized void lockRead() throws InterruptedException {
        while (writer || waitingWriters > 0) wait();      // while, never if: wait() also returns on its own
        readers++;
    }

    /** The last reader out wakes everybody, because one monitor cannot wake only the writers. */
    synchronized void unlockRead() {
        if (--readers == 0) notifyAll();
    }

    /** Get in as a writer, alone. It registers before parking, so readers arriving later wait behind it. */
    synchronized void lockWrite() throws InterruptedException {
        waitingWriters++;
        try {
            while (writer || readers > 0) wait();
        } catch (InterruptedException e) {
            waitingWriters--; notifyAll(); throw e;        // our leaving can admit the readers behind us
        }
        waitingWriters--;
        writer = true;
    }

    /** Give the write side back and wake every waiter: both sides share the one wait set. */
    synchronized void unlockWrite() {
        writer = false;
        notifyAll();
    }

    /** A snapshot for a test, taken under the same monitor that guards the counters. */
    synchronized String state() { return readers + " readers, writer=" + writer + ", queued writers=" + waitingWriters; }
}

// ---- ext: a guarded map, and the day ConcurrentHashMap beats any lock you can write
/**
 * The everyday use: make a plain HashMap safe for many readers and the occasional writer. It works, and for a
 * map it is still the wrong answer -- ConcurrentHashMap locks one bin instead of the whole map, so two writers
 * to different keys never meet, and readers take no lock at all. Reach for a read-write lock when the thing
 * you guard is NOT a map: a config snapshot, a routing table, a rules object, a document.
 */
final class GuardedMap<K, V> {
    private final Map<K, V> data = new HashMap<>();
    private final RwLock rw = new RwLock();

    GuardedMap() { rw.configure(Policies.of(Policy.WRITER_PREFERENCE)); }

    /** Many of these run at once. */
    V get(K key) throws InterruptedException {
        rw.readLock().lock();
        try { return data.get(key); } finally { rw.readLock().unlock(); }
    }
    /** This one runs alone. */
    void put(K key, V value) throws InterruptedException {
        rw.writeLock().lock();
        try { data.put(key, value); } finally { rw.writeLock().unlock(); }
    }
    /** A copy, so an iteration cannot blow up half way through with a concurrent modification. */
    Map<K, V> snapshot() throws InterruptedException {
        rw.readLock().lock();
        try { return new LinkedHashMap<>(data); } finally { rw.readLock().unlock(); }
    }
    /** The map the JDK would have given you for free, for comparison in the demo. */
    static <K, V> Map<K, V> theBoringAnswer() { return new ConcurrentHashMap<>(); }
}

// ---- ext: upgrading safely -- drop the read hold, take the write hold, then RE-CHECK
/**
 * The lock refuses a read-to-write upgrade because two upgraders would wait for each other forever. The safe
 * shape is to let go first and then re-check, and the re-check is the whole point: two threads can both decide
 * "it is missing", both arrive at the write lock, and only the first one may insert. This is the same
 * double-check that makes a cache loader safe.
 */
final class UpgradeSafely {
    private UpgradeSafely() {}

    /** Read it under the read lock; if it is missing, let go, take the write lock, and look again. */
    static <K, V> V computeIfAbsent(RwLock rw, Map<K, V> data, K key, Function<K, V> maker) throws InterruptedException {
        rw.readLock().lock();
        try { V found = data.get(key); if (found != null) return found; }
        finally { rw.readLock().unlock(); }                       // let go BEFORE asking for the write side
        rw.writeLock().lock();
        try {
            V again = data.get(key);                              // the gap: somebody may have inserted it
            if (again != null) return again;
            V made = maker.apply(key);
            data.put(key, made);
            return made;
        } finally { rw.writeLock().unlock(); }
    }
}

// ---- ext: a starvation meter -- an observer that notices the writer nobody let in
/**
 * Answers the question the fairness rule raises: is anybody being starved? It records the longest wait on each
 * side and counts the waits over a threshold. It is told after the unlock, so measuring costs the lock nothing,
 * and it deliberately throws on demand in the tests to prove a broken listener cannot break the lock.
 */
final class StarvationMeter implements LockObserver {
    private final long slowMs;
    private final AtomicLong worstWriterMs = new AtomicLong();
    private final AtomicLong worstReaderMs = new AtomicLong();
    private final AtomicInteger slowWrites = new AtomicInteger();
    private final AtomicInteger slowReads = new AtomicInteger();

    StarvationMeter(long slowMs) { this.slowMs = slowMs; }

    public void onEvent(LockEvent e) {
        switch (e.kind()) {
            case WRITE_ACQUIRED -> {
                worstWriterMs.accumulateAndGet(e.waitedMs(), Math::max);
                if (e.waitedMs() >= slowMs) slowWrites.incrementAndGet();
            }
            case READ_ACQUIRED -> {
                worstReaderMs.accumulateAndGet(e.waitedMs(), Math::max);
                if (e.waitedMs() >= slowMs) slowReads.incrementAndGet();
            }
            default -> { }                                        // releases are not waits
        }
    }

    /** One line for a dashboard or a log. */
    String report() {
        return "worst writer wait " + worstWriterMs.get() + "ms (" + slowWrites.get() + " over " + slowMs
               + "ms), worst reader wait " + worstReaderMs.get() + "ms (" + slowReads.get() + " over " + slowMs + "ms)";
    }
    /** The longest any writer waited, for a test that wants to assert it. */
    long worstWriterMs() { return worstWriterMs.get(); }
}

// ---- ext: a distributed read-write lock -- the same three numbers, in a store, with a lease
/** The one operation a store must give you: replace a value only if it still equals what you last read. */
interface LockStore {
    /** Returns false if somebody else changed the row first. This is the whole distributed primitive. */
    boolean compareAndSet(String key, String expected, String next);
    /** The current row, or null. */
    String get(String key);
}

/** A CAS store in one process, so the demo runs. In production this row lives in Redis, etcd or a table. */
final class InMemoryLockStore implements LockStore {
    private final Map<String, String> rows = new ConcurrentHashMap<>();
    public boolean compareAndSet(String key, String expected, String next) {
        if (expected == null) return rows.putIfAbsent(key, next) == null;
        return rows.replace(key, expected, next);
    }
    public String get(String key) { return rows.get(key); }
}

/**
 * The same three numbers, moved out of the process: one row holding "readers:writer", changed with
 * compare-and-set. What you lose is the part this whole page is about -- there is no condition to park on, so
 * a waiter polls, and every acquire is a network round trip instead of forty nanoseconds. What you must add is
 * a lease (an expiry stamped on the row) so a holder that dies does not own the lock forever, and a fencing
 * token so a resurrected holder's late write is rejected by the storage it was writing to.
 */
final class DistributedRwLock {
    private final LockStore store;
    private final String key;
    private final Clock clock;

    DistributedRwLock(LockStore store, String key, Clock clock) {
        this.store = store; this.key = key; this.clock = clock;
        store.compareAndSet(key, null, "0:0");
    }

    /** Poll until the row says no writer, then bump the reader count with a CAS. Gives up at the deadline. */
    boolean acquireRead(long timeoutMs) throws InterruptedException {
        long deadline = clock.nowMs() + timeoutMs;
        while (clock.nowMs() < deadline) {
            String row = store.get(key);
            String[] parts = row.split(":");
            if (parts[1].equals("0") && store.compareAndSet(key, row, (Integer.parseInt(parts[0]) + 1) + ":0")) return true;
            Thread.sleep(2);                                      // no condition to wait on: this is the cost
        }
        return false;
    }

    /** Drop the reader count by one, retrying the CAS if another reader moved it in between. */
    void releaseRead() {
        while (true) {
            String row = store.get(key);
            String[] parts = row.split(":");
            if (store.compareAndSet(key, row, (Integer.parseInt(parts[0]) - 1) + ":" + parts[1])) return;
        }
    }

    /** Only from a completely free row: no readers and no writer. */
    boolean acquireWrite(long timeoutMs) throws InterruptedException {
        long deadline = clock.nowMs() + timeoutMs;
        while (clock.nowMs() < deadline) {
            if (store.compareAndSet(key, "0:0", "0:1")) return true;
            Thread.sleep(2);
        }
        return false;
    }

    void releaseWrite() { store.compareAndSet(key, "0:1", "0:0"); }
    /** The raw row, for a demo that wants to print it. */
    String row() { return store.get(key); }
}

// ---- ext: the JDK's answer -- ReentrantReadWriteLock, and what AQS does that this file does not
/**
 * What you would actually ship. ReentrantReadWriteLock is built on AbstractQueuedSynchronizer: one 32-bit int
 * holds the reader count in its top half and the write hold count in its bottom half, moved with a single
 * compare-and-set, and the waiters sit in an explicit linked queue so a release wakes exactly ONE node instead
 * of everybody. The three decisions it makes are the three this page made: reentrant on both sides, downgrade
 * allowed, upgrade forbidden -- and its fair mode is our FairOrder with a real queue behind it.
 */
final class JdkComparison {
    private JdkComparison() {}

    /** Shows that the JDK lock behaves exactly as ours on the three interesting cases. */
    static String run() throws InterruptedException {
        ReentrantReadWriteLock jdk = new ReentrantReadWriteLock(true);      // true = fair mode

        jdk.readLock().lock(); jdk.readLock().lock();                       // reentrant reads
        int holds = jdk.getReadHoldCount();
        jdk.readLock().unlock(); jdk.readLock().unlock();

        jdk.writeLock().lock();
        jdk.readLock().lock();                                              // downgrade: legal
        jdk.writeLock().unlock();
        boolean stillReading = jdk.getReadHoldCount() == 1;
        jdk.readLock().unlock();

        jdk.readLock().lock();
        boolean upgraded = jdk.writeLock().tryLock();                       // upgrade: refused, never hangs
        jdk.readLock().unlock();

        return "jdk fair lock: read holds " + holds + ", downgrade " + stillReading + ", upgrade allowed " + upgraded;
    }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        // optimistic reads: a reader that takes no lock, and the hand-rolled version of the same idea
        OptimisticPoint p = new OptimisticPoint();
        p.move(3, 4);
        System.out.println("optimistic read: distance = " + p.distanceFromOrigin());
        SeqLockPair pair = new SeqLockPair();
        pair.set(7, 9);
        System.out.println("seqlock pair: " + java.util.Arrays.toString(pair.get()));

        // a condition on the write lock: a waiter drops the whole hold and gets it back
        RwLock rw = new RwLock();
        rw.configure(Policies.of(Policy.WRITER_PREFERENCE));
        WriteCondition notEmpty = new WriteCondition(rw);
        boolean[] ready = { false };
        CountDownLatch waiting = new CountDownLatch(1);
        Thread waiter = Main.start("condition-waiter", () -> {
            rw.writeLock().lock();
            try {
                waiting.countDown();
                while (!ready[0]) notEmpty.await(2000);            // while, not if: the predicate is re-tested
                System.out.println("condition: woke with the write lock back in hand, ready=" + ready[0]);
            } finally { rw.writeLock().unlock(); }
        });
        waiting.await(2, TimeUnit.SECONDS);
        Thread.sleep(20);                                          // let it park and give the lock up
        rw.writeLock().lock();
        try { ready[0] = true; notEmpty.signal(); } finally { rw.writeLock().unlock(); }
        waiter.join(3000);

        // the semaphore build: one permit per reader, all permits for a writer
        SemaphoreRwLock sem = new SemaphoreRwLock();
        sem.lockRead(); sem.lockRead();
        System.out.println("semaphore lock: 2 readers inside, " + sem.free() + " permits left");
        sem.unlockRead(); sem.unlockRead();
        sem.lockWrite();
        System.out.println("semaphore lock: writer inside, " + sem.free() + " permits left");
        sem.unlockWrite();

        // the same lock with nothing but synchronized / wait / notifyAll
        MonitorRwLock mon = new MonitorRwLock();
        mon.lockRead(); mon.lockRead();
        System.out.println("monitor lock: " + mon.state());
        mon.unlockRead(); mon.unlockRead();
        mon.lockWrite();
        System.out.println("monitor lock: " + mon.state());
        mon.unlockWrite();

        // the everyday use, and the boring answer that beats it for maps
        GuardedMap<String, Integer> guarded = new GuardedMap<>();
        guarded.put("a", 1); guarded.put("b", 2);
        System.out.println("guarded map: " + guarded.snapshot() + "   ConcurrentHashMap would need no lock at all: "
                           + GuardedMap.theBoringAnswer().getClass().getSimpleName());

        // the upgrade, done safely, from two threads at once: the maker must run exactly once
        RwLock cacheLock = new RwLock();
        cacheLock.configure(Policies.of(Policy.WRITER_PREFERENCE));
        Map<String, String> cache = new HashMap<>();
        AtomicInteger made = new AtomicInteger();
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(4);
        for (int i = 0; i < 4; i++) {
            Main.start("loader-" + i, () -> {
                go.await();
                UpgradeSafely.computeIfAbsent(cacheLock, cache, "k", k -> { made.incrementAndGet(); return "loaded"; });
                done.countDown();
            });
        }
        go.countDown();
        done.await(3, TimeUnit.SECONDS);
        System.out.println("safe upgrade: 4 threads missed the same key, the loader ran " + made.get() + " time(s)");

        // the starvation meter, on a lock a read storm is holding down
        RwLock metered = new RwLock();
        StarvationMeter meter = new StarvationMeter(20);
        metered.configure(Policies.of(Policy.READER_PREFERENCE), meter);
        long stormEnds = System.currentTimeMillis() + 120;
        Thread[] storm = new Thread[4];
        for (int i = 0; i < storm.length; i++) {
            storm[i] = Main.start("storm-" + i, () -> {
                while (System.currentTimeMillis() < stormEnds) {
                    metered.readLock().lock();
                    try { Thread.sleep(1); } finally { metered.readLock().unlock(); }
                }
            });
        }
        Thread.sleep(10);
        Thread late = Main.start("late-writer", () -> {
            metered.writeLock().lock();
            try { Thread.sleep(1); } finally { metered.writeLock().unlock(); }
        });
        for (Thread t : storm) t.join(3000);
        late.join(3000);
        System.out.println("starvation meter (READER_PREFERENCE): " + meter.report());

        // the distributed version: the same three numbers, in a row, with compare-and-set
        DistributedRwLock dist = new DistributedRwLock(new InMemoryLockStore(), "doc:42", System::currentTimeMillis);
        System.out.println("distributed: read acquired " + dist.acquireRead(500) + ", row " + dist.row());
        System.out.println("distributed: a writer cannot get in while a reader holds it: " + !dist.acquireWrite(50));
        dist.releaseRead();
        System.out.println("distributed: write acquired " + dist.acquireWrite(500) + ", row " + dist.row());
        dist.releaseWrite();

        // and what you would actually ship
        System.out.println(JdkComparison.run());
    }
}
