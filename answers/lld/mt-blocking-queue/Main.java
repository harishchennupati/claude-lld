import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * Where time comes from. Injected, never read from the wall clock inside a method, so a test can push a
 * deadline into the past and watch a timed call give up without actually waiting for it.
 */
interface Clock { long nanoTime(); }

/**
 * The promise a producer and a consumer depend on: hand an item in, pull an item out, and two timed
 * versions for callers that cannot wait forever. put and take can block, so both declare InterruptedException.
 */
interface BlockingBuffer<T> {
    /** Hand an item in. Blocks (or drops, or throws) when the buffer is full: that is the overflow policy's call. */
    void put(T item) throws InterruptedException;
    /** Pull the oldest item out. Blocks while the buffer is empty. Returns null only when the queue is closed and drained. */
    T take() throws InterruptedException;
    /** Hand an item in, waiting at most this long for room. Returns false if the budget ran out; nothing is written then. */
    boolean offer(T item, long timeout, TimeUnit unit) throws InterruptedException;
    /** Pull an item out, waiting at most this long for one. Returns null if the budget ran out (or the queue is closed and drained). */
    T poll(long timeout, TimeUnit unit) throws InterruptedException;
    /** How many items are in the buffer right now, read as one consistent snapshot. */
    int size();
    /** The bound this buffer was built with. It never changes. */
    int capacity();
}

/**
 * Storage, and nothing else: no locks, no waiting, no opinions about what "full" means. One job, so it can be
 * tested on one thread. Swapping this is how FIFO becomes priority or count-bounded becomes byte-bounded.
 */
interface Store<T> {
    /** Put an item at the tail. The caller must have checked isFull() first; a full store throws rather than overwrite. */
    void add(T item);
    /** Remove and return the head item. The caller must have checked isEmpty() first. */
    T poll();
    /** True when there is no room for another item, in whatever unit this store counts in. */
    boolean isFull();
    /** True when there is nothing to hand out. */
    boolean isEmpty();
    /** How many items are held right now. */
    int size();
    /** The declared bound: items for the ring buffer, bytes for a byte-bounded store. */
    int capacity();
}

/**
 * A fixed array with two cursors. head is the next item to hand out, tail the next free slot; both advance
 * modulo the array length, so the queue rides a moving window over the array with no shifting and no allocation
 * per item. count is what tells full (count == capacity) from empty (count == 0), which head and tail alone cannot.
 */
final class RingBuffer<T> implements Store<T> {
    private final Object[] slots;
    private int head, tail, count;

    /** A ring of exactly this many slots. Capacity is fixed here and never changes: that is the bound. */
    RingBuffer(int capacity) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity must be > 0, got " + capacity);
        slots = new Object[capacity];
    }
    /** Append at the tail and wrap. Throws if full, so a policy that lies about having made room is caught here. */
    public void add(T item) {
        if (count == slots.length) throw new IllegalStateException("ring is full: " + count);
        slots[tail] = item;
        tail = (tail + 1) % slots.length;
        count++;
    }
    /** Remove the head, wrap, and null the slot so the array does not pin a dead object. */
    @SuppressWarnings("unchecked")
    public T poll() {
        if (count == 0) throw new IllegalStateException("ring is empty");
        T item = (T) slots[head];
        slots[head] = null;
        head = (head + 1) % slots.length;
        count--;
        return item;
    }
    public boolean isFull() { return count == slots.length; }
    public boolean isEmpty() { return count == 0; }
    public int size() { return count; }
    public int capacity() { return slots.length; }
}

/**
 * What "full" means, as one method. Called by put with the lock already held and the store already full.
 * Return true if the caller should now enqueue (room exists), false if this policy consumed or dropped the item.
 * A policy may wait, but only on the queue's own not-full condition, which releases the lock while it waits.
 */
interface OverflowPolicy<T> {
    /** Decide what happens to this item when there is no room. Return true to enqueue it after all. */
    boolean onFull(BoundedBlockingQueue<T> queue, T item) throws InterruptedException;
}

/** The default: make the producer wait until a consumer frees a slot. This is what "blocking queue" means. */
final class BlockUntilRoom<T> implements OverflowPolicy<T> {
    /** Park on not-full until there is room (or the queue closes), then tell put to enqueue. */
    public boolean onFull(BoundedBlockingQueue<T> queue, T item) throws InterruptedException {
        queue.awaitRoom();
        return true;
    }
}

/** Never stall the producer: throw the stalest item away and keep the freshest N. A live metrics panel wants this. */
final class DropOldest<T> implements OverflowPolicy<T> {
    /** Evict the head to make room, then tell put to enqueue. Never waits, so a producer is never blocked. */
    public boolean onFull(BoundedBlockingQueue<T> queue, T item) {
        queue.evictOldest();
        return true;
    }
}

/** Never stall and never lose silently: refuse the item loudly and let the caller decide. */
final class RejectWhenFull<T> implements OverflowPolicy<T> {
    /** Always throws. The caller sees the back-pressure as an exception instead of as a pause. */
    public boolean onFull(BoundedBlockingQueue<T> queue, T item) {
        throw new IllegalStateException("queue is full (" + queue.capacity() + ")");
    }
}

/** Somebody who wants to know what the queue did, without the queue knowing what a dashboard is. */
interface QueueObserver {
    /** Called after the lock is released, with what happened and the size right after it happened. */
    void onEvent(String what, int size);
}

/**
 * The proof that the bound holds: it remembers the largest size it ever saw. If this ever exceeds capacity,
 * an item was enqueued into a full queue. Used by the demo and by FailureTests.
 */
final class PeakMeter implements QueueObserver {
    private final AtomicInteger peak = new AtomicInteger();
    private final AtomicLong events = new AtomicLong();
    /** Record the size, keeping the maximum. Cheap, lock-free, and called outside the queue's lock. */
    public void onEvent(String what, int size) {
        events.incrementAndGet();
        peak.accumulateAndGet(size, Math::max);
    }
    /** The largest size ever observed. */
    public int peak() { return peak.get(); }
    /** How many events were seen. */
    public long events() { return events.get(); }
}

/**
 * The whole point of the exercise: a queue with a fixed capacity where a producer waits when it is full and a
 * consumer waits when it is empty, with no spinning. One lock guards the store and both cursors; two conditions
 * keep the two waiting crowds apart, so a put wakes a consumer and a take wakes a producer, never the wrong one.
 * The invariant, always true outside the lock: the size is never negative and never past the capacity, the order is
 * FIFO, and every item is delivered exactly once.
 */
final class BoundedBlockingQueue<T> implements BlockingBuffer<T> {
    private final Store<T> store;
    private final ReentrantLock lock;
    private final Condition notFull;   // producers park here; a take signals it
    private final Condition notEmpty;  // consumers park here; a put signals it
    private OverflowPolicy<T> onFull = new BlockUntilRoom<>();
    private Clock clock = System::nanoTime;
    private final List<QueueObserver> observers = new CopyOnWriteArrayList<>();
    private final AtomicLong parks = new AtomicLong();
    private boolean closed;            // written and read under the lock only

    /** A queue of this many items, with a non-fair lock (throughput first) and the blocking policy. */
    BoundedBlockingQueue(int capacity) { this(new RingBuffer<>(capacity), false); }

    /**
     * The full constructor: any store, and fair = true to hand the lock out in arrival order. Fairness costs
     * throughput and is only worth it when one starved waiter is a real problem.
     */
    BoundedBlockingQueue(Store<T> store, boolean fair) {
        this.store = Objects.requireNonNull(store);
        this.lock = new ReentrantLock(fair);
        this.notFull = lock.newCondition();
        this.notEmpty = lock.newCondition();
    }

    /** Hand in the rules. The queue never builds them, so a test can hand in a broken one on purpose. */
    void configure(OverflowPolicy<T> policy, Clock clock) {
        this.onFull = Objects.requireNonNull(policy);
        this.clock = Objects.requireNonNull(clock);
    }
    /** Add a listener. It is called after the lock is released, never inside it. */
    void addObserver(QueueObserver observer) { observers.add(observer); }

    /**
     * Hand an item in. Full means the policy decides: block (default), drop the oldest, or throw.
     * The order is the design: change the store first, signal second, unlock third, tell the world fourth.
     */
    public void put(T item) throws InterruptedException {
        Objects.requireNonNull(item, "null is not an item: poll returns null to mean empty");
        int sizeAfter;
        lock.lockInterruptibly();
        try {
            if (closed) throw new IllegalStateException("queue is closed");
            if (store.isFull() && !onFull.onFull(this, item)) return;  // the policy dropped or rejected it
            if (closed) throw new IllegalStateException("queue was closed while waiting for room");
            store.add(item);            // 1. the state changes
            sizeAfter = store.size();
            notEmpty.signal();          // 2. exactly one consumer is woken: one item arrived, one waiter can use it
        } finally {
            lock.unlock();              // 3. in a finally, so a throw cannot leave the lock held
        }
        publish("put", sizeAfter);      // 4. listeners, outside the lock, where they cannot slow anybody down
    }

    /**
     * Pull the oldest item out, waiting while the queue is empty. Returns null only when the queue was closed
     * and has been drained, which is the end-of-stream signal for a consumer loop.
     */
    public T take() throws InterruptedException {
        T item;
        int sizeAfter;
        lock.lockInterruptibly();
        try {
            try {
                while (store.isEmpty() && !closed) { parks.incrementAndGet(); notEmpty.await(); }
            } catch (InterruptedException e) {
                notEmpty.signal();      // we may have eaten a signal meant for another consumer: pass it on
                throw e;
            }
            if (store.isEmpty()) return null;   // closed and drained
            item = store.poll();
            sizeAfter = store.size();
            notFull.signal();           // one slot freed, so exactly one producer can proceed
        } finally {
            lock.unlock();
        }
        publish("take", sizeAfter);
        return item;
    }

    /**
     * Hand an item in, waiting at most this long for room, then giving up and returning false.
     * The deadline is computed once from the injected clock and the remaining budget is recomputed on every
     * wake, so a spurious wakeup shortens the wait instead of restarting it.
     */
    public boolean offer(T item, long timeout, TimeUnit unit) throws InterruptedException {
        Objects.requireNonNull(item, "null is not an item");
        long deadline = clock.nanoTime() + unit.toNanos(timeout);
        int sizeAfter;
        lock.lockInterruptibly();
        try {
            if (closed) throw new IllegalStateException("queue is closed");
            while (store.isFull()) {                       // offer answers "what if full" itself: it waits, then gives up
                long left = deadline - clock.nanoTime();
                if (left <= 0) return false;               // budget spent; nothing was written
                try { parks.incrementAndGet(); notFull.awaitNanos(left); }
                catch (InterruptedException e) { notFull.signal(); throw e; }
                if (closed) throw new IllegalStateException("queue was closed while waiting for room");
            }
            store.add(item);
            sizeAfter = store.size();
            notEmpty.signal();
        } finally {
            lock.unlock();
        }
        publish("offer", sizeAfter);
        return true;
    }

    /** Pull an item out, waiting at most this long. Returns null when the budget ran out, or when closed and drained. */
    public T poll(long timeout, TimeUnit unit) throws InterruptedException {
        long deadline = clock.nanoTime() + unit.toNanos(timeout);
        T item;
        int sizeAfter;
        lock.lockInterruptibly();
        try {
            while (store.isEmpty()) {
                if (closed) return null;
                long left = deadline - clock.nanoTime();
                if (left <= 0) return null;
                try { parks.incrementAndGet(); notEmpty.awaitNanos(left); }
                catch (InterruptedException e) { notEmpty.signal(); throw e; }
            }
            item = store.poll();
            sizeAfter = store.size();
            notFull.signal();
        } finally {
            lock.unlock();
        }
        publish("poll", sizeAfter);
        return item;
    }

    /**
     * Move up to max items into a sink under ONE lock acquire instead of max of them. The first rung of the
     * scaling ladder: it does not make the lock shorter, it makes it happen far less often.
     */
    public int drainTo(Collection<? super T> sink, int max) {
        int moved = 0, sizeAfter;
        lock.lock();
        try {
            while (moved < max && !store.isEmpty()) { sink.add(store.poll()); moved++; }
            for (int i = 0; i < moved; i++) notFull.signal();  // one wake per slot freed: one signal would leave the rest asleep
            sizeAfter = store.size();
        } finally {
            lock.unlock();
        }
        if (moved > 0) publish("drain", sizeAfter);
        return moved;
    }

    /**
     * Stop the queue: no new work in, and every parked thread wakes up to find out. signalAll, not signal,
     * because this is the one change that concerns every waiter on both sides at once.
     */
    public void close() {
        int sizeAfter;
        lock.lock();
        try {
            if (closed) return;
            closed = true;
            sizeAfter = store.size();
            notFull.signalAll();
            notEmpty.signalAll();
        } finally {
            lock.unlock();
        }
        publish("close", sizeAfter);
    }

    /** Called by the blocking policy, with the lock held: wait until there is room or the queue closes. */
    void awaitRoom() throws InterruptedException {
        requireLocked();
        try {
            while (store.isFull() && !closed) { parks.incrementAndGet(); notFull.await(); }
        } catch (InterruptedException e) {
            notFull.signal();   // a signal may have been meant for us and spent on us: hand it to another producer
            throw e;
        }
    }

    /** Called by the drop-oldest policy, with the lock held: throw away the stalest item to make room. */
    void evictOldest() {
        requireLocked();
        if (!store.isEmpty()) store.poll();
    }

    /** Guard for the two package-private hooks above: a policy that forgets the lock corrupts the store. */
    private void requireLocked() {
        if (!lock.isHeldByCurrentThread()) throw new IllegalStateException("the queue's lock must be held here");
    }

    /** A consistent snapshot of the size: read under the lock, so it is never seen half-updated. */
    public int size() { lock.lock(); try { return store.size(); } finally { lock.unlock(); } }
    /** The bound. Fixed at construction. */
    public int capacity() { lock.lock(); try { return store.capacity(); } finally { lock.unlock(); } }
    /** How much room is left right now. */
    public int remainingCapacity() { lock.lock(); try { return store.capacity() - store.size(); } finally { lock.unlock(); } }
    /** True once close() has run. */
    public boolean isClosed() { lock.lock(); try { return closed; } finally { lock.unlock(); } }
    /** How many times a caller actually went to sleep. Zero here means nothing ever blocked; it is never a spin count. */
    public long parkCount() { return parks.get(); }

    /** Tell the listeners, outside the lock, and never let a broken one break the queue. */
    private void publish(String what, int size) {
        for (QueueObserver o : observers) {
            try { o.onEvent(what, size); } catch (RuntimeException ignored) { /* a broken meter is not the queue's problem */ }
        }
    }
}

/** A demo that proves the two claims: a full queue really parks a producer, and nothing is lost under load. */
public class Main {
    /** Runs the four demos in order; the last one is the race that the whole design exists for. */
    public static void main(String[] args) throws Exception {
        blockingIsReal();
        timedCallsGiveUp();
        fullIsAPolicy();
        theRace();
    }

    /** Claim 1: a producer meeting a full queue sleeps, and a take is what wakes it. The measured delay is the proof. */
    static void blockingIsReal() throws Exception {
        BoundedBlockingQueue<String> q = new BoundedBlockingQueue<>(2);
        q.put("a");
        q.put("b");                                   // the queue is now full
        long start = System.nanoTime();
        Thread producer = new Thread(() -> {
            try { q.put("c"); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }, "producer");
        producer.start();
        Thread.sleep(150);                            // the producer is parked on not-full for all of this
        System.out.println("while the queue is full, the third put is still waiting: " + (producer.isAlive()));
        String first = q.take();                      // this frees a slot and signals not-full
        producer.join(2000);
        long waitedMs = (System.nanoTime() - start) / 1_000_000;
        System.out.println("took " + first + ", the parked producer woke and finished after " + waitedMs
            + " ms, size=" + q.size() + ", it parked " + q.parkCount() + " time(s) and never spun");
    }

    /** Claim 2: the timed calls give up on time and write nothing when they do. */
    static void timedCallsGiveUp() throws Exception {
        BoundedBlockingQueue<String> q = new BoundedBlockingQueue<>(1);
        long t0 = System.nanoTime();
        String nothing = q.poll(100, TimeUnit.MILLISECONDS);
        long ms = (System.nanoTime() - t0) / 1_000_000;
        System.out.println("poll on an empty queue returned " + nothing + " after " + ms + " ms");
        q.put("only");
        boolean accepted = q.offer("overflow", 80, TimeUnit.MILLISECONDS);
        System.out.println("offer into a full queue returned " + accepted + " and the size is still " + q.size());
    }

    /** Claim 3: what "full" means is a handed-in rule, so the same queue can drop instead of block. */
    static void fullIsAPolicy() throws Exception {
        BoundedBlockingQueue<Integer> q = new BoundedBlockingQueue<>(3);
        q.configure(new DropOldest<>(), System::nanoTime);
        for (int i = 1; i <= 7; i++) q.put(i);        // never blocks: the stalest reading is thrown away
        List<Integer> kept = new ArrayList<>();
        q.drainTo(kept, 10);
        System.out.println("drop-oldest kept the freshest " + kept.size() + ": " + kept + " (no producer ever waited: parks=" + q.parkCount() + ")");
    }

    /** Claim 4: four producers and four consumers, 100000 items, every one delivered exactly once and in bounds. */
    static void theRace() throws Exception {
        final int CAPACITY = 64, PRODUCERS = 4, CONSUMERS = 4, PER_PRODUCER = 25_000;
        final int TOTAL = PRODUCERS * PER_PRODUCER;
        BoundedBlockingQueue<Integer> q = new BoundedBlockingQueue<>(CAPACITY);
        PeakMeter meter = new PeakMeter();
        q.addObserver(meter);

        CountDownLatch go = new CountDownLatch(1);
        List<Thread> threads = new ArrayList<>();
        AtomicInteger produced = new AtomicInteger();
        List<List<Integer>> received = new ArrayList<>();

        for (int p = 0; p < PRODUCERS; p++) {
            final int id = p;
            Thread t = new Thread(() -> {
                try {
                    go.await();
                    for (int i = 0; i < PER_PRODUCER; i++) { q.put(id * PER_PRODUCER + i); produced.incrementAndGet(); }
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }, "producer-" + p);
            threads.add(t);
        }
        for (int c = 0; c < CONSUMERS; c++) {
            List<Integer> mine = new ArrayList<>();
            received.add(mine);
            Thread t = new Thread(() -> {
                try {
                    go.await();
                    Integer item;
                    while ((item = q.take()) != null) mine.add(item);   // null = closed and drained
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }, "consumer-" + c);
            threads.add(t);
        }
        threads.forEach(Thread::start);
        long t0 = System.nanoTime();
        go.countDown();
        for (int i = 0; i < PRODUCERS; i++) threads.get(i).join(30_000);
        q.close();                                   // wakes every parked consumer; they drain, then see null
        for (int i = PRODUCERS; i < threads.size(); i++) threads.get(i).join(30_000);
        long ms = (System.nanoTime() - t0) / 1_000_000;

        boolean[] seen = new boolean[TOTAL];
        int delivered = 0, duplicates = 0;
        for (List<Integer> list : received) for (int v : list) { delivered++; if (seen[v]) duplicates++; seen[v] = true; }
        int lost = 0;
        for (boolean b : seen) if (!b) lost++;
        System.out.println("race: produced=" + produced.get() + " delivered=" + delivered + " duplicates=" + duplicates
            + " lost=" + lost + " in " + ms + " ms");
        System.out.println("the bound held: peak size=" + meter.peak() + " of capacity " + CAPACITY
            + ", final size=" + q.size() + ", threads parked " + q.parkCount() + " times");
        if (delivered != TOTAL || duplicates != 0 || lost != 0 || meter.peak() > CAPACITY)
            throw new AssertionError("the queue lost, duplicated or overfilled an item");
    }
}
