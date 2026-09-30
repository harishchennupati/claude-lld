import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: a new answer to "what does full mean" -- drop the NEWEST instead of the oldest. One class, one line.
/**
 * Keep the oldest N and refuse the newcomer, which is what a "first N wins" sampler wants. The queue is not
 * touched at all: this is the whole edit, plus the line that hands it in.
 */
final class DropNewest<T> implements OverflowPolicy<T> {
    /** Silently swallow the item and tell put not to enqueue it. Never waits, so a producer never stalls. */
    public boolean onFull(BoundedBlockingQueue<T> queue, T item) { return false; }
}

// ---- ext: measure without touching the queue -- a decorator over the interface both sides already depend on
/**
 * Counts items and total blocked time around ANY BlockingBuffer, including one written next year. It wraps the
 * interface, not the class, so the queue keeps its single job and a test can stack a second wrapper on top.
 */
final class MeteredBuffer<T> implements BlockingBuffer<T> {
    private final BlockingBuffer<T> inner;
    private final LongAdder puts = new LongAdder(), takes = new LongAdder(), blockedNanos = new LongAdder();

    /** Wrap any buffer. The wrapped one does not know it is wrapped. */
    MeteredBuffer(BlockingBuffer<T> inner) { this.inner = inner; }

    /** Time the call, then delegate. The measurement is outside the queue's lock by construction. */
    public void put(T item) throws InterruptedException {
        long t0 = System.nanoTime();
        try { inner.put(item); } finally { blockedNanos.add(System.nanoTime() - t0); puts.increment(); }
    }
    /** Time the call, then delegate. */
    public T take() throws InterruptedException {
        long t0 = System.nanoTime();
        try { return inner.take(); } finally { blockedNanos.add(System.nanoTime() - t0); takes.increment(); }
    }
    public boolean offer(T item, long timeout, TimeUnit unit) throws InterruptedException { puts.increment(); return inner.offer(item, timeout, unit); }
    public T poll(long timeout, TimeUnit unit) throws InterruptedException { takes.increment(); return inner.poll(timeout, unit); }
    public int size() { return inner.size(); }
    public int capacity() { return inner.capacity(); }
    /** What the meter saw: puts, takes and the average time a caller spent inside the queue. */
    public String report() {
        long calls = puts.sum() + takes.sum();
        return "puts=" + puts.sum() + " takes=" + takes.sum()
             + " avg time in the queue=" + (calls == 0 ? 0 : blockedNanos.sum() / calls) + " ns";
    }
}

// ---- ext: priority instead of FIFO -- a new Store, and the lock, the conditions and the policies do not change
/**
 * The urgent item goes first. Storage was already a separate job, so priority is a new Store and nothing else;
 * add and poll become O(log n) instead of O(1), which is the price of the ordering.
 * One honest caveat: with this store, drop-oldest drops the HIGHEST-priority item, so pair it with drop-newest.
 */
final class HeapStore<T> implements Store<T> {
    private final PriorityQueue<T> heap;
    private final int capacity;

    /** A bounded heap: at most this many items, ordered by this comparator. */
    HeapStore(int capacity, Comparator<? super T> order) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity must be > 0");
        this.capacity = capacity;
        this.heap = new PriorityQueue<>(capacity, order);
    }
    public void add(T item) { if (isFull()) throw new IllegalStateException("heap is full"); heap.add(item); }
    public T poll() { if (heap.isEmpty()) throw new IllegalStateException("heap is empty"); return heap.poll(); }
    public boolean isFull() { return heap.size() == capacity; }
    public boolean isEmpty() { return heap.isEmpty(); }
    public int size() { return heap.size(); }
    public int capacity() { return capacity; }
}

// ---- ext: bound by bytes, not by count -- because a thousand 2 KB messages and a thousand 2 MB ones are not the same risk
/** How big one item is, in whatever unit the bound is written in. Handed in, so the queue does no guessing. */
interface Weigher<T> { int weightOf(T item); }

/**
 * Full means "the bytes budget is spent", not "the slot count is spent". The overshoot is at most one item,
 * because fullness is tested before the item is weighed; the exact fix is one extra method on Store,
 * boolean hasRoomFor(T item), which put would call instead of isFull().
 */
final class ByteBoundedStore<T> implements Store<T> {
    private final ArrayDeque<T> items = new ArrayDeque<>();
    private final Weigher<T> weigher;
    private final int maxBytes;
    private int bytes;

    /** A store bounded by total weight rather than by item count. */
    ByteBoundedStore(int maxBytes, Weigher<T> weigher) { this.maxBytes = maxBytes; this.weigher = weigher; }

    public void add(T item) {
        int w = weigher.weightOf(item);
        if (w > maxBytes) throw new IllegalArgumentException("item of " + w + " bytes can never fit in " + maxBytes);
        items.addLast(item);
        bytes += w;
    }
    public T poll() { T item = items.pollFirst(); bytes -= weigher.weightOf(item); return item; }
    public boolean isFull() { return bytes >= maxBytes; }
    public boolean isEmpty() { return items.isEmpty(); }
    public int size() { return items.size(); }
    /** The declared bound, in bytes: this store counts weight, not slots. */
    public int capacity() { return maxBytes; }
    /** The bytes held right now. */
    public int bytes() { return bytes; }
}

// ---- ext: bulk transfer -- wait for the first item, then take everything that is already there, under one lock
/**
 * The batching consumer. drainTo alone never waits, so a consumer that called it in a loop would spin on an
 * empty queue; this waits for one item with a deadline and then drains the rest in the same breath.
 */
final class Bulk {
    /**
     * Block up to the timeout for at least one item, then drain up to max in total. Returns how many were moved:
     * zero means the budget ran out or the queue is closed and empty.
     */
    static <T> int drainAtLeastOne(BoundedBlockingQueue<T> q, Collection<? super T> sink, int max,
                                   long timeout, TimeUnit unit) throws InterruptedException {
        T first = q.poll(timeout, unit);
        if (first == null) return 0;
        sink.add(first);
        return 1 + q.drainTo(sink, max - 1);
    }
}

// ---- ext: ladder rung 2 -- two locks, the LinkedBlockingQueue trick: producers and consumers stop meeting
/**
 * One lock means a producer and a consumer contend even though they touch opposite ends of the queue. A linked
 * node list has two ends, so it can have two locks: producers take putLock, consumers take takeLock, and the
 * only shared word is an atomic count. The subtlety is the "cascading signal": a put signals not-empty only when
 * the queue WAS empty, and it must do that outside its own lock, or the two locks would be taken in a fixed
 * order and the design would be back to one lock's worth of contention.
 */
final class TwoLockQueue<T> implements BlockingBuffer<T> {
    /** A one-way linked cell. The head node is a dummy: its item is always null. */
    private static final class Node<T> { T item; Node<T> next; Node(T item) { this.item = item; } }

    private final int capacity;
    private final AtomicInteger count = new AtomicInteger();
    private Node<T> head = new Node<>(null), last = head;
    private final ReentrantLock putLock = new ReentrantLock(), takeLock = new ReentrantLock();
    private final Condition notFull = putLock.newCondition(), notEmpty = takeLock.newCondition();

    /** A queue bounded to this many items, with one lock per end. */
    TwoLockQueue(int capacity) { this.capacity = capacity; }

    /** Append under putLock; wake a consumer only if the queue was empty before this item. */
    public void put(T item) throws InterruptedException {
        Objects.requireNonNull(item);
        int c;
        putLock.lockInterruptibly();
        try {
            while (count.get() == capacity) notFull.await();
            last = last.next = new Node<>(item);
            c = count.getAndIncrement();
            if (c + 1 < capacity) notFull.signal();   // still room: pass the baton to the next producer
        } finally { putLock.unlock(); }
        if (c == 0) signalNotEmpty();                 // it WAS empty: somebody may be parked on the other lock
    }
    /** Remove under takeLock; wake a producer only if the queue was full before this take. */
    public T take() throws InterruptedException {
        T item;
        int c;
        takeLock.lockInterruptibly();
        try {
            while (count.get() == 0) notEmpty.await();
            item = dequeue();
            c = count.getAndDecrement();
            if (c > 1) notEmpty.signal();             // more left: pass the baton to the next consumer
        } finally { takeLock.unlock(); }
        if (c == capacity) signalNotFull();           // it WAS full: a producer may be parked
        return item;
    }
    /** The timed put: the same loop with a shrinking budget. */
    public boolean offer(T item, long timeout, TimeUnit unit) throws InterruptedException {
        Objects.requireNonNull(item);
        long nanos = unit.toNanos(timeout);
        int c;
        putLock.lockInterruptibly();
        try {
            while (count.get() == capacity) {
                if (nanos <= 0) return false;
                nanos = notFull.awaitNanos(nanos);    // awaitNanos hands back what is LEFT of the budget
            }
            last = last.next = new Node<>(item);
            c = count.getAndIncrement();
            if (c + 1 < capacity) notFull.signal();
        } finally { putLock.unlock(); }
        if (c == 0) signalNotEmpty();
        return true;
    }
    /** The timed take. */
    public T poll(long timeout, TimeUnit unit) throws InterruptedException {
        long nanos = unit.toNanos(timeout);
        T item;
        int c;
        takeLock.lockInterruptibly();
        try {
            while (count.get() == 0) {
                if (nanos <= 0) return null;
                nanos = notEmpty.awaitNanos(nanos);
            }
            item = dequeue();
            c = count.getAndDecrement();
            if (c > 1) notEmpty.signal();
        } finally { takeLock.unlock(); }
        if (c == capacity) signalNotFull();
        return item;
    }
    public int size() { return count.get(); }
    public int capacity() { return capacity; }

    /** Unlink the first real node; only ever called with takeLock held. */
    private T dequeue() {
        Node<T> first = head.next;
        head.next = head;        // help the collector: the old dummy points at itself
        head = first;
        T item = first.item;
        first.item = null;       // the new dummy holds nothing
        return item;
    }
    /** Take the other lock just long enough to wake one waiter. */
    private void signalNotEmpty() { takeLock.lock(); try { notEmpty.signal(); } finally { takeLock.unlock(); } }
    private void signalNotFull()  { putLock.lock();  try { notFull.signal();  } finally { putLock.unlock(); } }
}

// ---- ext: ladder rung 3 -- no lock at all, one producer thread and one consumer thread
/**
 * A single-producer single-consumer ring. Each cursor is written by exactly one thread and read by both, so a
 * volatile write and a volatile read are all the ordering needed: no lock, no CAS, no parking. The price is the
 * contract (exactly one thread on each side) and the fact that offer returning false is back-pressure the CALLER
 * must now handle -- spin, yield, park -- which is precisely what the blocking queue was doing for you.
 * In production this is where you also pad the cursors onto their own cache lines to stop false sharing.
 */
final class SpscRing<T> {
    private final Object[] slots;
    private final int mask;
    private volatile long writeAt, readAt;

    /** Capacity must be a power of two so the wrap is a bit mask instead of a division. */
    SpscRing(int capacity) {
        if (Integer.bitCount(capacity) != 1) throw new IllegalArgumentException("capacity must be a power of two");
        slots = new Object[capacity];
        mask = capacity - 1;
    }
    /** Called by the one producer thread. False means full; the caller decides what to do about it. */
    boolean offer(T item) {
        long w = writeAt;
        if (w - readAt == slots.length) return false;
        slots[(int) (w & mask)] = item;
        writeAt = w + 1;                    // the volatile write publishes the slot as well
        return true;
    }
    /** Called by the one consumer thread. Null means empty. */
    @SuppressWarnings("unchecked")
    T poll() {
        long r = readAt;
        if (r == writeAt) return null;
        T item = (T) slots[(int) (r & mask)];
        slots[(int) (r & mask)] = null;
        readAt = r + 1;
        return item;
    }
    /** How many items are in flight. */
    int size() { return (int) (writeAt - readAt); }
}

// ---- ext: the synchronized / wait / notify version, and the lost wakeup that comes free with it
/**
 * The same queue with one monitor instead of a lock and two conditions. It is correct ONLY with notifyAll:
 * with a single monitor there is one waiting crowd, so notify() may hand the wakeup to a producer when the
 * thread that could make progress was a consumer. That thread goes straight back to sleep, the signal is spent,
 * and everybody hangs -- the classic lost wakeup. notifyAll is the fix and the thundering herd is its price,
 * which is the whole argument for a ReentrantLock with two conditions.
 */
final class SyncQueue<T> {
    private final ArrayDeque<T> items = new ArrayDeque<>();
    private final int capacity;

    /** A monitor-based bounded queue of this many items. */
    SyncQueue(int capacity) { this.capacity = capacity; }

    /** while, not if: a wakeup only means "look again", never "the slot is yours". */
    synchronized void put(T item) throws InterruptedException {
        while (items.size() == capacity) wait();
        items.addLast(item);
        notifyAll();        // NOT notify(): one monitor, two crowds, and no way to aim
    }
    /** Mirror of put. */
    synchronized T take() throws InterruptedException {
        while (items.isEmpty()) wait();
        T item = items.pollFirst();
        notifyAll();
        return item;
    }
    /** Size, read under the same monitor. */
    synchronized int size() { return items.size(); }
}

// ---- ext: shutdown without a flag -- N poison pills for N consumers
/**
 * close() is the better answer when you own the queue. When you do not -- a java.util.concurrent queue, say --
 * the portable trick is a sentinel: put one pill per consumer, and each consumer that sees one re-parks nothing,
 * exits its loop, and leaves. The pill travels in FIFO order behind the real work, so nothing is lost.
 */
final class Pills {
    /** The sentinel. Reference equality is the test, so a real item can never be mistaken for it. */
    static final Object PILL = new Object();

    /** Run a consumer loop until a pill arrives; returns how many real items it handled. */
    static int consumeUntilPill(BoundedBlockingQueue<Object> q) throws InterruptedException {
        int handled = 0;
        while (true) {
            Object item = q.take();
            if (item == PILL || item == null) return handled;
            handled++;
        }
    }
    /** One pill per consumer, after the last real item. */
    static void shutdown(BoundedBlockingQueue<Object> q, int consumers) throws InterruptedException {
        for (int i = 0; i < consumers; i++) q.put(PILL);
    }
}

// ---- ext: fairness and starvation -- one flag, and what it costs
/**
 * A non-fair lock lets a thread that is arriving right now barge past threads that have been queued for a
 * while. That is fast, because the thread that just released the lock is still running and can simply take it
 * again -- no park, no unpark, no context switch. It is also how one caller can be passed over again and again,
 * which is starvation. new ReentrantLock(true) hands the lock out in arrival order instead.
 * This measures the flag on its own: six threads doing put-then-take on a queue big enough that nobody ever
 * blocks, so the ONLY thing being shared is the lock. The result is worth quoting in the interview: fairness
 * costs two to three ORDERS OF MAGNITUDE of throughput here, because every hand-off becomes a park and an
 * unpark -- and on this symmetric workload the barging lock did not starve anyone anyway (both spreads come
 * out near 1.0x). Fairness buys a guarantee that no waiter is passed over indefinitely, not a better average.
 */
final class Fairness {
    /**
     * Six threads hammering one queue for a fixed window. Returns the total round-trips through the lock, and
     * the busiest-to-quietest ratio across the six -- which is what "one of my producers is starved" means.
     */
    static String run(boolean fair, long millis) throws Exception {
        BoundedBlockingQueue<Integer> q = new BoundedBlockingQueue<>(new RingBuffer<>(1024), fair);
        final int THREADS = 6;
        long[] ops = new long[THREADS];
        AtomicBoolean stop = new AtomicBoolean();
        List<Thread> threads = new ArrayList<>();
        for (int i = 0; i < THREADS; i++) {
            final int id = i;
            threads.add(new Thread(() -> {
                try { while (!stop.get()) { q.put(id); q.take(); ops[id]++; } }   // never full, never empty
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }));
        }
        threads.forEach(Thread::start);
        Thread.sleep(millis);
        stop.set(true);
        for (Thread t : threads) t.join(2000);
        long total = 0, busiest = 0, quietest = Long.MAX_VALUE;
        for (long o : ops) { total += o; busiest = Math.max(busiest, o); quietest = Math.min(quietest, o); }
        return String.format("%s lock: %,d trips through the lock in %d ms; busiest thread %,d, quietest %,d (%.1fx spread)",
                fair ? "fair  " : "unfair", total, millis, busiest, quietest, busiest / (double) quietest);
    }
}

// ---- ext: why bound at all -- the back-pressure arithmetic that decides the capacity
/**
 * An unbounded queue does not remove the mismatch between a fast producer and a slow consumer, it hides it in
 * the heap until the process dies. A bound turns that into the producer waiting, which is the system telling the
 * truth. This prints the arithmetic that picks a capacity.
 */
final class BackPressure {
    /** What an unbounded queue costs, and what capacity a latency budget implies. */
    static String arithmetic(int producedPerSecond, int consumedPerSecond, int bytesPerItem, int latencyBudgetMs) {
        int gap = producedPerSecond - consumedPerSecond;
        long perHour = (long) gap * 3600;
        long mbPerHour = perHour * bytesPerItem / (1024 * 1024);
        int capacityForBudget = Math.max(1, consumedPerSecond * latencyBudgetMs / 1000);
        return "in " + producedPerSecond + "/s, out " + consumedPerSecond + "/s -> " + gap + " items/s pile up: "
             + perHour + " items/hour, about " + mbPerHour + " MB/hour, and the process dies overnight.\n"
             + "  bounded instead: the producer waits, and the queue's depth is the delay. A " + latencyBudgetMs
             + " ms budget at " + consumedPerSecond + "/s means a capacity of about " + capacityForBudget + ".";
    }
}

// ---- ext: the lost wakeup proper -- a signal sent before the waiter waited, and the one-lock rule that stops it
/**
 * There are two different bugs people call a lost wakeup. One is a signal spent on a thread that cannot use it
 * (the SyncQueue block above: one monitor, two crowds, notify()). The other is this one, and it is the reason
 * the wait protocol says "check the predicate and wait under the SAME lock": if you check outside the lock and
 * then take the lock to wait, the state can change and the signal can be sent in the gap between the two, and
 * that signal is gone forever -- notify wakes whoever is waiting NOW, it is not remembered for later.
 * Gate(false) reproduces it exactly; Gate(true) is the same code with the check inside the monitor, and the
 * setter then cannot get in until wait() has released it. One class, both halves, so you can read the diff.
 */
final class LostWakeup {
    /** A one-shot gate: a waiter waits for ready, a setter sets it. safe = check and wait under one monitor. */
    static final class Gate {
        private final boolean safe;
        private boolean ready;
        private final CountDownLatch pastTheCheck = new CountDownLatch(1);
        private final CountDownLatch signalSent = new CountDownLatch(1);

        /** safe = the correct protocol; false = check first, take the lock second, which leaves a gap. */
        Gate(boolean safe) { this.safe = safe; }

        /** Wait for ready, at most this long. Returns the milliseconds actually spent waiting. */
        long awaitReady(long millis) throws InterruptedException {
            long t0 = System.nanoTime();
            if (safe) {
                synchronized (this) {
                    pastTheCheck.countDown();            // the setter is now free to TRY; it still needs the monitor
                    while (!ready) wait(millis);         // check and wait, both inside the monitor
                }
            } else {
                boolean seen;
                synchronized (this) { seen = ready; }    // the check...
                pastTheCheck.countDown();                // ...and here is the gap, holding nothing
                signalSent.await();                      // the setter runs and signals right here
                synchronized (this) { if (!seen) wait(millis); }   // ...and only now do we wait: too late
            }
            return (System.nanoTime() - t0) / 1_000_000;
        }
        /** Set ready and signal, timed to land exactly in the waiter's gap. */
        void makeReady() throws InterruptedException {
            pastTheCheck.await();
            synchronized (this) { ready = true; notifyAll(); }
            signalSent.countDown();
        }
    }

    /** Run one gate and return how long the waiter slept: the full timeout means the signal was lost. */
    static long run(boolean safe, long timeoutMillis) throws InterruptedException {
        Gate gate = new Gate(safe);
        Thread setter = new Thread(() -> {
            try { gate.makeReady(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        setter.start();
        long waited = gate.awaitReady(timeoutMillis);
        setter.join(2000);
        return waited;
    }
}

// ---- ext: two semaphores and a mutex -- the same queue with no condition and no while loop
/**
 * The other way interviewers ask for this. A counting semaphore IS a count of permits, so "wait until there is
 * room" becomes slots.acquire() and "wait until there is an item" becomes items.acquire(): the counting is the
 * predicate, so there is no condition to re-check and no while loop. The mutex only protects the deque itself.
 * What you give up: a consistent snapshot across both counters (size() is a permit count, not a locked read),
 * atomic bulk moves like drainTo, and any policy that wants to look at the queue while it is full. Which is why
 * the lock-plus-two-conditions version is the one to write when the interviewer says "and now drop the oldest".
 */
final class SemaphoreQueue<T> {
    private final Semaphore slots, items;
    private final ReentrantLock mutex = new ReentrantLock();
    private final ArrayDeque<T> q = new ArrayDeque<>();

    /** A queue of this many items: capacity permits on the slots side, zero on the items side. */
    SemaphoreQueue(int capacity) {
        slots = new Semaphore(capacity);
        items = new Semaphore(0);
    }
    /** Take a free slot (waiting if there is none), append, then publish one item. */
    void put(T item) throws InterruptedException {
        slots.acquire();
        mutex.lock();
        try { q.addLast(item); } finally { mutex.unlock(); }
        items.release();
    }
    /** Take an item (waiting if there is none), remove it, then hand the slot back. */
    T take() throws InterruptedException {
        items.acquire();
        T item;
        mutex.lock();
        try { item = q.pollFirst(); } finally { mutex.unlock(); }
        slots.release();
        return item;
    }
    /** The timed put: tryAcquire either takes the permit or takes nothing, so nothing leaks on a timeout. */
    boolean offer(T item, long timeout, TimeUnit unit) throws InterruptedException {
        if (!slots.tryAcquire(timeout, unit)) return false;
        mutex.lock();
        try { q.addLast(item); } finally { mutex.unlock(); }
        items.release();
        return true;
    }
    /** How many items are in it: a permit count, not a locked snapshot. */
    int size() { return items.availablePermits(); }
}

// ---- ext: what java.util.concurrent already gives you -- and which one to reach for
/**
 * Say this out loud in the interview: in production you use java.util.concurrent, and the exercise is to show
 * you know what is inside it. ArrayBlockingQueue IS this class -- one lock, two conditions, a ring, a fairness
 * flag in the constructor. The rest of the family is the same shape with one knob moved, and two of them have a
 * trap: LinkedBlockingQueue's no-argument constructor is unbounded, and PriorityBlockingQueue is ALWAYS
 * unbounded, so both put the back-pressure you were asked for straight back into the heap.
 */
final class Jdk {
    /** Run one tiny example of each and return the lines to print. */
    static List<String> tour() throws InterruptedException {
        List<String> out = new ArrayList<>();

        // ArrayBlockingQueue: the same design as Main.java -- one lock, two conditions, a fixed array
        BlockingQueue<String> abq = new ArrayBlockingQueue<>(2, /* fair = */ false);
        abq.put("a");
        boolean second = abq.offer("b");
        boolean third = abq.offer("c", 20, TimeUnit.MILLISECONDS);
        out.add("ArrayBlockingQueue(2): the second item was accepted (" + second + ") and the third gave up after 20 ms ("
              + third + ") -- this is our class, in the JDK, fairness flag and all");

        // LinkedBlockingQueue: ladder rung 2 (two locks). The no-argument constructor is UNBOUNDED: the trap
        BlockingQueue<String> lbq = new LinkedBlockingQueue<>(2);
        out.add("LinkedBlockingQueue(2): two locks, so producers and consumers stop meeting; remaining room "
              + lbq.remainingCapacity() + ". new LinkedBlockingQueue<>() with no argument is UNBOUNDED");

        // SynchronousQueue: capacity ZERO. Every put waits for a taker: a hand-off, not a buffer
        SynchronousQueue<String> sq = new SynchronousQueue<>();
        out.add("SynchronousQueue: capacity 0, so offer with no taker returns " + sq.offer("x")
              + " -- it is a hand-off, and it is what a cached thread pool uses");

        // PriorityBlockingQueue: our HeapStore, except it is unbounded, so put NEVER blocks
        BlockingQueue<Integer> pbq = new PriorityBlockingQueue<>();
        pbq.addAll(List.of(5, 1, 9));
        out.add("PriorityBlockingQueue: urgent first (" + pbq.take() + " came out first) but it is ALWAYS unbounded: put never blocks");

        // DelayQueue / LinkedTransferQueue: the two specialist ends of the family
        out.add("DelayQueue: an item only becomes takeable at its own time -- scheduled retries. "
              + "LinkedTransferQueue.transfer() waits until a consumer has actually taken the item");

        // ThreadPoolExecutor: the bounded queue plus a RejectedExecutionHandler IS OverflowPolicy
        ThreadPoolExecutor pool = new ThreadPoolExecutor(1, 1, 0, TimeUnit.SECONDS,
                new ArrayBlockingQueue<>(1), new ThreadPoolExecutor.CallerRunsPolicy());
        AtomicInteger ran = new AtomicInteger();
        for (int i = 0; i < 6; i++) pool.execute(ran::incrementAndGet);
        pool.shutdown();
        pool.awaitTermination(5, TimeUnit.SECONDS);
        out.add("ThreadPoolExecutor(bounded queue + CallerRunsPolicy): all " + ran.get()
              + " tasks ran, the submitter ran the overflow itself -- a RejectedExecutionHandler IS an OverflowPolicy");
        return out;
    }
}

// ---- ext: the capacity table from move 8, measured here rather than remembered
/**
 * The numbers on page 02 move 8 come from this. One producer, one consumer, the same item count at four
 * capacities, after a warm-up pass so the JIT is not being measured. The shape is the lesson: the lock costs
 * tens of nanoseconds and a park costs about two microseconds, so the cost of a small queue is parking, and
 * capacity is the first knob. Absolute numbers move with the machine; the ratios do not.
 */
final class CapacityScan {
    /** One producer, one consumer, n items through a queue of this capacity. Returns one table row. */
    static String row(int capacity, int n) throws InterruptedException {
        BoundedBlockingQueue<Integer> q = new BoundedBlockingQueue<>(capacity);
        Thread producer = new Thread(() -> {
            try { for (int i = 0; i < n; i++) q.put(i); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        AtomicLong sum = new AtomicLong();
        Thread consumer = new Thread(() -> {
            try { for (int i = 0; i < n; i++) sum.addAndGet(q.take()); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        long t0 = System.nanoTime();
        producer.start(); consumer.start();
        producer.join(60_000); consumer.join(60_000);
        long nsPerItem = (System.nanoTime() - t0) / n;
        double parksPerItem = q.parkCount() / (double) n;
        return String.format("  capacity %5d: %6d ns per item, %,10d parks (%.3f per item)%s",
                capacity, nsPerItem, q.parkCount(), parksPerItem,
                sum.get() == (long) n * (n - 1) / 2 ? "" : "  CHECKSUM FAILED");
    }
    /** put and take on ONE thread, so nothing ever blocks: this is what the lock alone costs. */
    static String uncontended(int n) throws InterruptedException {
        BoundedBlockingQueue<Integer> q = new BoundedBlockingQueue<>(64);
        long t0 = System.nanoTime();
        for (int i = 0; i < n; i++) { q.put(i); q.take(); }
        return String.format("  one thread, alone: %d ns for a put AND a take, %d parks", (System.nanoTime() - t0) / n, q.parkCount());
    }
    /** Warm up, then print the table. */
    static List<String> table(int n) throws InterruptedException {
        uncontended(n); row(8, n / 4);                       // warm-up: never measured
        List<String> out = new ArrayList<>();
        out.add(uncontended(n));
        for (int capacity : new int[]{1, 8, 64, 1024}) out.add(row(capacity, n));
        return out;
    }
}

// ---- ext: surviving a restart -- the queue becomes a log, and the head index becomes a committed offset
/**
 * An in-memory queue loses everything when the process dies. The durable version is the same two cursors with
 * the array replaced by an append-only file: put appends a line and returns only after the write is durable,
 * take reads at the committed offset, and the offset is committed only AFTER the consumer's work succeeded.
 * That order is the whole design: a crash between the two replays the last item, so delivery is at-least-once
 * and consumers must be idempotent. Exactly-once needs the work and the offset commit in one transaction.
 * This is a sketch, not a broker: no fsync per record, no segments, no compaction -- that is what Kafka is.
 */
final class DurableLog implements AutoCloseable {
    private final java.nio.file.Path data, offsetFile;
    private final java.io.BufferedWriter out;
    private long committed;

    /** Open (or create) a log and read back the offset the last run committed. */
    DurableLog(java.nio.file.Path data, java.nio.file.Path offsetFile) throws java.io.IOException {
        this.data = data;
        this.offsetFile = offsetFile;
        this.out = java.nio.file.Files.newBufferedWriter(data, java.nio.file.StandardOpenOption.CREATE,
                                                         java.nio.file.StandardOpenOption.APPEND);
        this.committed = java.nio.file.Files.exists(offsetFile)
            ? Long.parseLong(java.nio.file.Files.readString(offsetFile).trim()) : 0;
    }
    /** Append and flush. The item is in the queue only once this returns. */
    synchronized void append(String item) throws java.io.IOException {
        out.write(item.replace("\n", " "));
        out.newLine();
        out.flush();
    }
    /** The next item at the committed offset, or null when the log has been caught up with. */
    synchronized String peek() throws java.io.IOException {
        List<String> lines = java.nio.file.Files.readAllLines(data);
        return committed < lines.size() ? lines.get((int) committed) : null;
    }
    /** Move past the item -- called only after the consumer's work succeeded, never before. */
    synchronized void commit() throws java.io.IOException {
        committed++;
        java.nio.file.Files.writeString(offsetFile, Long.toString(committed));
    }
    /** How far the consumer has got. */
    synchronized long offset() { return committed; }
    public void close() throws java.io.IOException { out.close(); }
}

/** Runs every extension above, so the follow-up answers on page 05 are code that has actually executed. */
class ExtDemo {
    /** Each block prints one line or two: the twist, and the evidence that it works. */
    public static void main(String[] args) throws Exception {
        // a new overflow policy: one class, one line, zero queue edits
        BoundedBlockingQueue<Integer> newest = new BoundedBlockingQueue<>(3);
        newest.configure(new DropNewest<>(), System::nanoTime);
        for (int i = 1; i <= 6; i++) newest.put(i);
        List<Integer> kept = new ArrayList<>();
        newest.drainTo(kept, 10);
        System.out.println("drop-newest kept the first three: " + kept);

        // the decorator: measurement wrapped around the interface, not bolted into the queue
        MeteredBuffer<String> metered = new MeteredBuffer<>(new BoundedBlockingQueue<>(4));
        for (int i = 0; i < 4; i++) metered.put("m" + i);
        for (int i = 0; i < 4; i++) metered.take();
        System.out.println("metered: " + metered.report());

        // priority instead of FIFO: a new Store; the lock, the conditions and the policies are untouched
        BoundedBlockingQueue<Integer> urgent =
            new BoundedBlockingQueue<>(new HeapStore<>(8, Comparator.<Integer>naturalOrder()), false);
        for (int v : new int[]{5, 1, 9, 3}) urgent.put(v);
        System.out.println("priority order out: " + urgent.take() + ", " + urgent.take() + ", " + urgent.take() + ", " + urgent.take());

        // bounded by bytes: 300 bytes of budget, items of 100 bytes each
        ByteBoundedStore<String> byBytes = new ByteBoundedStore<>(300, s -> s.length());
        BoundedBlockingQueue<String> bytesQ = new BoundedBlockingQueue<>(byBytes, false);
        bytesQ.configure(new DropOldest<>(), System::nanoTime);
        for (int i = 0; i < 5; i++) bytesQ.put("x".repeat(100));
        System.out.println("byte-bounded: " + bytesQ.size() + " items holding " + byBytes.bytes() + " of 300 bytes");

        // bulk transfer: one lock acquire instead of one per item
        BoundedBlockingQueue<Integer> bulk = new BoundedBlockingQueue<>(128);
        for (int i = 0; i < 100; i++) bulk.put(i);
        List<Integer> batch = new ArrayList<>();
        int moved = Bulk.drainAtLeastOne(bulk, batch, 64, 50, TimeUnit.MILLISECONDS);
        System.out.println("bulk drain moved " + moved + " items in one lock acquire (first=" + batch.get(0) + ")");

        // ladder rung 2: two locks
        TwoLockQueue<Integer> two = new TwoLockQueue<>(64);
        int n = 50_000;
        Thread tp = new Thread(() -> { try { for (int i = 0; i < n; i++) two.put(i); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } });
        AtomicLong sum = new AtomicLong();
        Thread tc = new Thread(() -> { try { for (int i = 0; i < n; i++) sum.addAndGet(two.take()); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } });
        long t0 = System.nanoTime();
        tp.start(); tc.start(); tp.join(10_000); tc.join(10_000);
        System.out.println("two-lock queue moved " + n + " items in " + (System.nanoTime() - t0) / 1_000_000
            + " ms, checksum ok=" + (sum.get() == (long) n * (n - 1) / 2));

        // ladder rung 3: no lock, one producer and one consumer
        SpscRing<Integer> ring = new SpscRing<>(1024);
        AtomicLong got = new AtomicLong();
        Thread sp = new Thread(() -> { for (int i = 0; i < n; i++) while (!ring.offer(i)) Thread.onSpinWait(); });
        Thread sc = new Thread(() -> { for (int i = 0; i < n; i++) { Integer v; while ((v = ring.poll()) == null) Thread.onSpinWait(); got.addAndGet(v); } });
        t0 = System.nanoTime();
        sp.start(); sc.start(); sp.join(10_000); sc.join(10_000);
        System.out.println("lock-free spsc ring moved " + n + " items in " + (System.nanoTime() - t0) / 1_000_000
            + " ms, checksum ok=" + (got.get() == (long) n * (n - 1) / 2) + " (the producer SPINS when full)");

        // the monitor version
        SyncQueue<Integer> sync = new SyncQueue<>(2);
        Thread syncProducer = new Thread(() -> { try { for (int i = 0; i < 10; i++) sync.put(i); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } });
        syncProducer.start();
        int total = 0;
        for (int i = 0; i < 10; i++) total += sync.take();
        syncProducer.join(2000);
        System.out.println("synchronized/wait/notifyAll version delivered 10 items, sum=" + total);

        // poison pills
        BoundedBlockingQueue<Object> pilled = new BoundedBlockingQueue<>(8);
        ExecutorService pool = Executors.newFixedThreadPool(3);
        List<Future<Integer>> handled = new ArrayList<>();
        for (int i = 0; i < 3; i++) handled.add(pool.submit(() -> Pills.consumeUntilPill(pilled)));
        for (int i = 0; i < 30; i++) pilled.put(i);
        Pills.shutdown(pilled, 3);
        int done = 0;
        for (Future<Integer> f : handled) done += f.get(10, TimeUnit.SECONDS);
        pool.shutdown();
        System.out.println("poison pills: 3 consumers exited on their own after handling " + done + " real items");

        // fairness: the flag on its own, six threads and a queue big enough that nobody ever blocks
        Fairness.run(false, 100);                          // warm-up, not printed
        System.out.println(Fairness.run(false, 200));
        System.out.println(Fairness.run(true, 200));

        // the lost wakeup proper: the same waiter, once with the check outside the lock and once inside
        System.out.println("lost wakeup: checking OUTSIDE the lock then waiting slept the whole "
            + LostWakeup.run(false, 300) + " ms; checking and waiting under the SAME lock woke in "
            + LostWakeup.run(true, 300) + " ms");

        // the same queue built out of two semaphores instead of a lock and two conditions
        SemaphoreQueue<Integer> sem = new SemaphoreQueue<>(2);
        Thread semProducer = new Thread(() -> { try { for (int i = 1; i <= 5; i++) sem.put(i); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } });
        semProducer.start();
        StringBuilder semOut = new StringBuilder();
        for (int i = 0; i < 5; i++) semOut.append(sem.take()).append(' ');
        semProducer.join(2000);
        System.out.println("semaphore queue (capacity 2) delivered in order: " + semOut.toString().trim()
            + " -- no condition, no while loop: the permit count IS the predicate");

        // what java.util.concurrent already gives you
        for (String line : Jdk.tour()) System.out.println("jdk | " + line);

        // the capacity table behind move 8, measured rather than remembered
        System.out.println("capacity scan, one producer and one consumer, 200,000 items each time:");
        for (String line : CapacityScan.table(200_000)) System.out.println(line);

        // surviving a restart: append, hand over, commit the offset only after the work succeeded
        java.nio.file.Path dir = java.nio.file.Files.createTempDirectory("bbq");
        try (DurableLog log = new DurableLog(dir.resolve("data.log"), dir.resolve("offset"))) {
            log.append("job-1"); log.append("job-2");
            String job = log.peek();
            log.commit();                                  // only now: the work above succeeded
            System.out.println("durable log: handled " + job + ", next is " + log.peek() + ", committed offset " + log.offset());
        }

        // why bound at all
        System.out.println("back-pressure: " + BackPressure.arithmetic(1000, 800, 200, 50));
    }
}
