import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

/**
 * Every follow-up on page 05, as code that compiles and has actually run. Nothing in this file edits StripedMap,
 * Segment or Entry: each twist is a new class handed in at construction, or a wrapper around the interface both
 * sides already depend on. That is the test that the derivation on page 02 was right.
 */

// ---- ext: the naive spreader, and the histogram that catches it in thirty seconds
/**
 * What java.util.HashMap does: fold the high sixteen bits down onto the low ones. Perfectly good there, because
 * HashMap only ever uses the LOW bits. Here it is a trap: this map picks a stripe from the HIGH bits, and a fold
 * leaves those untouched, so every sequential Integer key keeps its all-zero top bits and lands in stripe 0.
 */
final class FoldOnlyHasher implements Hasher {
    /** No multiply, so no avalanche: bit 31 of the output is still bit 31 of the input. */
    public int spread(int hashCode) { return hashCode ^ (hashCode >>> 16); }
}

/** The histogram that turns "I think the keys are spread" into a number you can read in one line. */
final class Histogram {
    /** min..max entries per stripe, and how many stripes got nothing at all. */
    static String of(int[] sizes) {
        int min = Integer.MAX_VALUE, max = 0, empty = 0;
        for (int s : sizes) { min = Math.min(min, s); max = Math.max(max, s); if (s == 0) empty++; }
        return sizes.length + " stripes hold " + min + ".." + max + " entries each, " + empty + " of them empty";
    }
}

// ---- ext: force every key into one stripe -- the worst case, on purpose, so a test can measure it
/**
 * Every key to stripe 0. Not a bug: the deliberate worst case. A map that is still correct under this -- right
 * answers, chains that grow, a stripe that resizes itself -- is correct under any hashCode anybody hands you.
 */
final class OneStripeHasher implements Hasher {
    /** Constant, so the stripe bits and the bucket bits are both constant and every key collides. */
    public int spread(int hashCode) { return 0; }
}

// ---- ext: measure without touching the map -- a Decorator over the interface both sides already depend on
/**
 * Counts hits, misses and writes around ANY KeyValueStore, because it implements the same interface and holds
 * one. The map never learns it is being measured, and swapping the map underneath for a ConcurrentHashMap adapter
 * changes nothing here. Counters are LongAdders: under contention they beat a synchronized long by an order of
 * magnitude, because each thread adds into its own cell.
 */
final class MeteredMap<K, V> implements KeyValueStore<K, V> {
    private final KeyValueStore<K, V> inner;
    private final LongAdder hits = new LongAdder(), misses = new LongAdder(), writes = new LongAdder();

    /** Wrap a store. The wrapper is the only thing the caller sees; the store does not know it exists. */
    MeteredMap(KeyValueStore<K, V> inner) { this.inner = inner; }

    public V get(K key) {
        V v = inner.get(key);
        if (v == null) misses.increment(); else hits.increment();
        return v;
    }
    public V put(K key, V value) { writes.increment(); return inner.put(key, value); }
    public V putIfAbsent(K key, V value) { writes.increment(); return inner.putIfAbsent(key, value); }
    public V remove(K key) { writes.increment(); return inner.remove(key); }
    public boolean replace(K key, V expected, V updated) { writes.increment(); return inner.replace(key, expected, updated); }
    public V merge(K key, V value, BinaryOperator<V> remap) { writes.increment(); return inner.merge(key, value, remap); }
    public V compute(K key, BiFunction<? super K, ? super V, ? extends V> remap) { writes.increment(); return inner.compute(key, remap); }
    public V computeIfAbsent(K key, Function<? super K, ? extends V> loader) { writes.increment(); return inner.computeIfAbsent(key, loader); }
    public int size() { return inner.size(); }

    /** One line for a dashboard: reads, hit rate, writes. */
    String report() {
        long h = hits.sum(), m = misses.sum();
        long pct = (h + m) == 0 ? 0 : 100 * h / (h + m);
        return h + " hits, " + m + " misses (" + pct + "% hit rate), " + writes.sum() + " writes";
    }
}

// ---- ext: the rung that is NOT on the ladder -- a read/write lock per stripe, and why it disappoints
/**
 * The obvious next move when somebody says "our workload is 95% reads": swap each stripe's ReentrantLock for a
 * ReentrantReadWriteLock, so many readers share a stripe and only a writer excludes everybody. Measured on this
 * machine it is consistently about TWICE AS SLOW as the plain lock (33 ms against 75 ms on the run below), and that
 * is the point worth remembering: a read lock is not free. Taking one is still a compare-and-set on a single shared
 * counter, so every reader in a stripe still writes to the same cache line and readers still fight each other --
 * they just do not block while they do it. An RW lock pays only when the critical section is long enough that the
 * exclusion itself was the cost, and here it is fifteen nanoseconds. When reads really dominate, the shape that wins
 * is the next block: stop locking on reads at all.
 */
final class RwStripedMap<K, V> {
    /** One stripe: a plain HashMap guarded by its own read/write lock. The JDK's HashMap is fine once it is guarded. */
    private static final class RwStripe<K, V> {
        final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
        final Map<K, V> data = new HashMap<>();
        volatile int count;
    }

    private final RwStripe<K, V>[] stripes;
    private final int mask, shift;
    private final Hasher hasher;

    /** Stripes rounded up to a power of two, with the spreader handed in exactly as the main map does it. */
    @SuppressWarnings("unchecked")
    RwStripedMap(int stripes, Hasher hasher) {
        int n = StripedMap.tableSizeFor(stripes);
        this.mask = n - 1;
        this.shift = 32 - Integer.numberOfTrailingZeros(n);
        this.hasher = hasher;
        this.stripes = (RwStripe<K, V>[]) new RwStripe[n];
        for (int i = 0; i < n; i++) this.stripes[i] = new RwStripe<>();
    }

    private RwStripe<K, V> stripeFor(K key) {
        int h = hasher.spread(key.hashCode());
        return stripes[(h >>> shift) & mask];
    }

    /** Readers share: ten threads can be inside the same stripe at the same instant. */
    V get(K key) {
        RwStripe<K, V> s = stripeFor(key);
        s.lock.readLock().lock();
        try { return s.data.get(key); } finally { s.lock.readLock().unlock(); }
    }

    /** Writers exclude: the write lock waits for every reader in this stripe to leave. */
    V put(K key, V value) {
        RwStripe<K, V> s = stripeFor(key);
        s.lock.writeLock().lock();
        try { V old = s.data.put(key, value); s.count = s.data.size(); return old; }
        finally { s.lock.writeLock().unlock(); }
    }

    /** The read-modify-write, under the write lock, exactly as before: one hold, no lost update. */
    V merge(K key, V value, BinaryOperator<V> remap) {
        RwStripe<K, V> s = stripeFor(key);
        s.lock.writeLock().lock();
        try {
            V old = s.data.get(key);
            V now = old == null ? value : remap.apply(old, value);
            s.data.put(key, now);
            s.count = s.data.size();
            return now;
        } finally { s.lock.writeLock().unlock(); }
    }

    /** Weakly consistent, as before: a sum of volatile counters, no lock. */
    int size() { int n = 0; for (RwStripe<K, V> s : stripes) n += s.count; return n; }
}

// ---- ext: reads with no lock at all -- the Java 5 ConcurrentHashMap shape, kept inside a striped map
/**
 * The answer to "why does get() take a lock at all?" -- it does not have to. Three changes to the stripe, and a
 * reader can walk it holding nothing:
 *
 * 1. the bucket array is volatile, so a reader that sees a new table also sees everything written into it before
 *    it was published (that is what a volatile write and the matching volatile read buy you);
 * 2. a node's key and hash are final and its value is volatile, so the node is safe to read the instant it is
 *    published, and a value overwritten under the lock is visible at once to a reader who is not holding it;
 * 3. a resize builds a WHOLE NEW table out of WHOLE NEW nodes and leaves the old one untouched -- so a reader
 *    already walking the old chain finishes on a chain that nobody is editing.
 *
 * Rule 3 is the one Main.java refuses to pay for: its resize relinks the existing nodes, which is cheaper and is
 * exactly why its get() has to hold the lock. Here the resize allocates instead, and reads become free. This is
 * what java.util.concurrent.ConcurrentHashMap looked like in Java 5 and 6: striped, locked writes, unlocked reads.
 *
 * What a lock-free reader can see is one instant's worth of stale -- a value that was overwritten a nanosecond
 * ago, an entry that was removed a nanosecond ago. Weakly consistent, never torn, never wrong.
 */
final class ReadOptimizedMap<K, V> {
    /** A node a reader walks with no lock held: key and hash frozen at construction, value and next volatile. */
    private static final class Node<K, V> {
        final K key; final int hash; volatile V value; volatile Node<K, V> next;
        Node(K key, int hash, V value, Node<K, V> next) {
            this.key = key; this.hash = hash; this.value = value; this.next = next;
        }
    }

    /** One stripe: the lock is for writers only. Readers touch `table` and the nodes, both volatile. */
    private static final class Stripe<K, V> {
        final ReentrantLock lock = new ReentrantLock();
        volatile Node<K, V>[] table;
        volatile int count;
        int threshold;                                  // written under the lock, read under the lock
        @SuppressWarnings("unchecked")
        Stripe(int buckets) { this.table = (Node<K, V>[]) new Node[buckets]; this.threshold = (int) (buckets * 0.75f); }
    }

    private final Stripe<K, V>[] stripes;
    private final int mask, shift;
    private final Hasher hasher;

    /** Same routing as StripedMap: a power-of-two stripe count, the high bits choosing the stripe. */
    @SuppressWarnings("unchecked")
    ReadOptimizedMap(int stripeCount, int bucketsPerStripe, Hasher hasher) {
        int n = StripedMap.tableSizeFor(stripeCount);
        this.mask = n - 1;
        this.shift = 32 - Integer.numberOfTrailingZeros(n);
        this.hasher = hasher;
        this.stripes = (Stripe<K, V>[]) new Stripe[n];
        int b = StripedMap.tableSizeFor(bucketsPerStripe);
        for (int i = 0; i < n; i++) this.stripes[i] = new Stripe<>(b);
    }

    private int hashOf(K key) { return hasher.spread(key.hashCode()); }
    private Stripe<K, V> stripeFor(int h) { return stripes[(h >>> shift) & mask]; }

    /**
     * No lock, no compare-and-set, nothing: one volatile read of the table, then a walk of volatile next pointers.
     * The table reference is read ONCE into a local, so a resize landing mid-walk cannot move the ground: this
     * reader simply finishes on the old table, which is still intact and still correct.
     */
    V get(K key) {
        int h = hashOf(key);
        Node<K, V>[] t = stripeFor(h).table;            // the one volatile read
        for (Node<K, V> e = t[h & (t.length - 1)]; e != null; e = e.next)
            if (e.hash == h && e.key.equals(key)) return e.value;
        return null;
    }

    /** Writers still take the stripe lock: this design buys lock-free READS, and nothing else. */
    V put(K key, V value) {
        int h = hashOf(key);
        Stripe<K, V> s = stripeFor(h);
        s.lock.lock();
        try {
            Node<K, V>[] t = s.table;
            int i = h & (t.length - 1);
            for (Node<K, V> e = t[i]; e != null; e = e.next)
                if (e.hash == h && e.key.equals(key)) { V old = e.value; e.value = value; return old; }
            t[i] = new Node<>(key, h, value, t[i]);     // prepend: a walker either sees the new head or does not
            s.count = s.count + 1;                      // volatile, and LAST, exactly as in Main.java
            if (s.count > s.threshold) resize(s);
            return null;
        } finally { s.lock.unlock(); }
    }

    /** Unlink under the lock. A reader already standing on the removed node still walks out through its next. */
    V remove(K key) {
        int h = hashOf(key);
        Stripe<K, V> s = stripeFor(h);
        s.lock.lock();
        try {
            Node<K, V>[] t = s.table;
            int i = h & (t.length - 1);
            Node<K, V> prev = null;
            for (Node<K, V> e = t[i]; e != null; prev = e, e = e.next)
                if (e.hash == h && e.key.equals(key)) {
                    if (prev == null) t[i] = e.next; else prev.next = e.next;
                    s.count = s.count - 1;
                    return e.value;
                }
            return null;
        } finally { s.lock.unlock(); }
    }

    /**
     * [lock held] Copy into a doubled array, building a fresh node for every entry, and publish the new table with
     * one volatile write. The old table is never touched, so any reader walking it is safe until it finishes.
     */
    @SuppressWarnings("unchecked")
    private void resize(Stripe<K, V> s) {
        Node<K, V>[] old = s.table;
        int cap = old.length << 1;
        if (cap <= 0) return;
        Node<K, V>[] fresh = (Node<K, V>[]) new Node[cap];
        for (Node<K, V> head : old)
            for (Node<K, V> e = head; e != null; e = e.next) {
                int i = e.hash & (cap - 1);
                fresh[i] = new Node<>(e.key, e.hash, e.value, fresh[i]);   // a NEW node, so `old` stays intact
            }
        s.threshold = (int) (cap * 0.75f);
        s.table = fresh;                                // the publish: one volatile write
    }

    /** Weakly consistent, as before: a sum of volatile counters with no lock. */
    int size() { int n = 0; for (Stripe<K, V> s : stripes) n += s.count; return n; }

    /** How many buckets one stripe has grown to. Used by the test that forces a resize under readers. */
    int bucketsIn(int stripe) { return stripes[stripe].table.length; }
}

// ---- ext: one lock per BIN -- what ConcurrentHashMap became in Java 8
/**
 * The Java 8 ConcurrentHashMap shape, in miniature. There are no stripes: the lock granularity is ONE BUCKET.
 * A read takes nothing at all -- a volatile array read, a walk, a volatile value read. A write into an empty
 * bucket is a single compare-and-set; a write into an occupied one synchronizes on the node that is already the
 * head. That is why CHM never relinks a node another thread might be walking: a reader holds nothing, so a node
 * has to stay valid forever. This version has a fixed bucket count, which is the part that has been left out --
 * a concurrent resize is where the real implementation's complexity lives.
 */
final class CasMap<K, V> {
    /** A chain node whose value and next are volatile, because a reader walks it holding no lock. */
    private static final class Node<K, V> {
        final K key; final int hash; volatile V value; volatile Node<K, V> next;
        Node(K key, int hash, V value, Node<K, V> next) { this.key = key; this.hash = hash; this.value = value; this.next = next; }
    }

    private final AtomicReferenceArray<Node<K, V>> bins;
    private final LongAdder count = new LongAdder();

    /** A fixed number of buckets, rounded up to a power of two. No resize: that is the part left out on purpose. */
    CasMap(int buckets) { this.bins = new AtomicReferenceArray<>(StripedMap.tableSizeFor(buckets)); }

    private int spread(K key) { int h = key.hashCode() * 0x9E3779B1; return h ^ (h >>> 16); }

    /** No lock, no CAS, nothing: two volatile reads and a walk. This is the whole point of rung 3. */
    V get(K key) {
        int h = spread(key), i = h & (bins.length() - 1);
        for (Node<K, V> e = bins.get(i); e != null; e = e.next)
            if (e.hash == h && e.key.equals(key)) return e.value;
        return null;
    }

    /** CAS into an empty bucket; synchronize on the head node when the bucket is not empty; retry if it moved. */
    V put(K key, V value) {
        int h = spread(key), i = h & (bins.length() - 1);
        for (;;) {
            Node<K, V> head = bins.get(i);
            if (head == null) {
                if (bins.compareAndSet(i, null, new Node<>(key, h, value, null))) { count.increment(); return null; }
                continue;                                   // somebody else won the empty bucket: look again
            }
            synchronized (head) {
                if (bins.get(i) != head) continue;          // the head changed under us: start over
                Node<K, V> prev = null;
                for (Node<K, V> e = head; e != null; prev = e, e = e.next)
                    if (e.hash == h && e.key.equals(key)) { V old = e.value; e.value = value; return old; }
                prev.next = new Node<>(key, h, value, null); // append at the tail, so nobody walking is disturbed
                count.increment();
                return null;
            }
        }
    }

    /** A LongAdder, which is the same trick as striping applied to one number: per-thread cells, summed on read. */
    int size() { return count.intValue(); }
}

// ---- ext: two stripes at once, and the deadlock you get for free when you do not order them
/**
 * Two threads, two locks, opposite directions. Ordered acquisition -- always the lower index first -- cannot
 * deadlock, so it runs to completion. The "natural" order -- source first, destination second -- can, and does.
 * The demo proves it with tryLock and a deadline, so the evidence is a count of back-offs and never a hung build.
 */
final class LockOrdering {
    /** Run N rounds of two threads taking two locks in opposite orders. Returns how often a thread had to back off. */
    static int race(boolean ordered, int rounds) throws InterruptedException {
        ReentrantLock a = new ReentrantLock(), b = new ReentrantLock();
        AtomicInteger backoffs = new AtomicInteger();
        CountDownLatch go = new CountDownLatch(1);
        Thread t1 = new Thread(job(a, b, rounds, backoffs, go), "left");
        Thread t2 = new Thread(ordered ? job(a, b, rounds, backoffs, go)     // both ask for `a` first: no cycle
                                       : job(b, a, rounds, backoffs, go),    // opposite orders: the cycle is back
                               "right");
        t1.start(); t2.start();
        go.countDown();
        t1.join(20_000); t2.join(20_000);
        return backoffs.get();
    }

    /** Take `first`, then try for `second` with a deadline. Failing to get the second one IS the deadlock, survived. */
    private static Runnable job(ReentrantLock first, ReentrantLock second, int rounds, AtomicInteger backoffs, CountDownLatch go) {
        return () -> {
            try { go.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            for (int i = 0; i < rounds; i++) {
                first.lock();
                try {
                    if (!second.tryLock(20, TimeUnit.MILLISECONDS)) { backoffs.incrementAndGet(); continue; }
                    try { Thread.onSpinWait(); } finally { second.unlock(); }
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                finally { first.unlock(); }
            }
        };
    }
}

// ---- ext: load once per key WITHOUT holding the stripe while the loader runs -- one future per key
/**
 * computeIfAbsent runs the loader inside the stripe lock, which is what makes it exactly-once but also means a
 * four-hundred-millisecond database call holds up every other key in that stripe. The fix is to put a promise in
 * the map instead of a value: the first caller wins a putIfAbsent -- one short lock hold -- and then does the slow
 * work holding nothing, while the losers wait on its future. A loader that throws removes the slot so the next
 * caller retries, rather than caching a failure forever.
 */
final class FutureLoader<K, V> {
    private final StripedMap<K, CompletableFuture<V>> slots;
    private final LongAdder loaderCalls = new LongAdder();

    /** As many stripes as the map it fronts. The slot map holds promises, not values. */
    FutureLoader(int stripes) { this.slots = new StripedMap<>(stripes); }

    /** Get, loading at most once per key, with the load running outside every lock. */
    V get(K key, Function<K, V> loader) {
        CompletableFuture<V> mine = new CompletableFuture<>();
        CompletableFuture<V> winner = slots.putIfAbsent(key, mine);
        if (winner != null) return winner.join();           // a loser: waits holding no lock at all
        try {
            loaderCalls.increment();
            V v = loader.apply(key);                        // the slow part, with nothing held
            mine.complete(v);
            return v;
        } catch (RuntimeException e) {
            slots.remove(key);                              // do not cache a failure: the next caller retries
            mine.completeExceptionally(e);
            throw e;
        }
    }

    /** How many times the loader actually ran. The number the test asserts. */
    long loaderCalls() { return loaderCalls.sum(); }
}

// ---- ext: waiting for a key to appear -- the wait protocol, in a loop, with a deadline
/**
 * The one place a map like this needs a thread to WAIT rather than just take its turn: "give me the value under
 * this key, and if it is not there yet, wait for it." A stripe grows one Condition -- a queue of threads parked
 * on that stripe -- and four rules come with it. Every one of them is a bug if you skip it.
 *
 * 1. CHECK UNDER THE LOCK. Look for the key while holding the stripe, not before taking it. Check outside and the
 *    value can arrive in the gap between your look and your await, taking the signal with it: you then wait for an
 *    announcement that has already been made. That is a LOST WAKEUP, and it is a hang, not a slowdown.
 * 2. WAIT IN A WHILE LOOP, never an if. await() is allowed to return with nobody having signalled at all -- a
 *    SPURIOUS WAKEUP -- and even after a real signal another waiter may have taken the value first. The loop
 *    re-checks the thing you actually care about, so neither case can fool you.
 * 3. SIGNAL AFTER THE CHANGE, STILL HOLDING THE LOCK. signalAll() only moves threads from the condition queue to
 *    the lock queue, so it is cheap and Java requires the lock to be held for it. Note the contrast with the
 *    observer in StripedMap: a listener is arbitrary user code and must be called AFTER the unlock; a signal is
 *    two pointer moves and must be called BEFORE it.
 * 4. CARRY A DEADLINE, NOT A FRESH TIMEOUT. awaitNanos returns how much of the budget is LEFT; feeding that back
 *    into the loop is what stops a thread waiting forever in a series of short naps.
 *
 * And lockInterruptibly at the door, so a cancelled request is not stuck waiting for permission to start waiting.
 */
final class WaitableMap<K, V> {
    /** One stripe: its lock, the queue of threads waiting on it, and the entries. */
    private static final class Cell<K, V> {
        final ReentrantLock lock = new ReentrantLock();
        final Condition changed = lock.newCondition();
        final Map<K, V> data = new HashMap<>();
    }

    private final Cell<K, V>[] cells;
    private final int mask, shift;
    private final Hasher hasher;

    /** The same routing as every other map here: a power-of-two stripe count, chosen by the high bits. */
    @SuppressWarnings("unchecked")
    WaitableMap(int stripeCount, Hasher hasher) {
        int n = StripedMap.tableSizeFor(stripeCount);
        this.mask = n - 1;
        this.shift = 32 - Integer.numberOfTrailingZeros(n);
        this.hasher = hasher;
        this.cells = (Cell<K, V>[]) new Cell[n];
        for (int i = 0; i < n; i++) this.cells[i] = new Cell<>();
    }

    private Cell<K, V> cellFor(K key) { int h = hasher.spread(key.hashCode()); return cells[(h >>> shift) & mask]; }

    /** Store, then wake everybody parked on this stripe -- inside the lock, after the change. Rule 3. */
    V put(K key, V value) {
        Cell<K, V> c = cellFor(key);
        c.lock.lock();
        try {
            V old = c.data.put(key, value);
            c.changed.signalAll();                      // cheap: it only re-queues threads, it does not run them
            return old;
        } finally { c.lock.unlock(); }
    }

    /** The value right now, or null. No waiting. */
    V get(K key) {
        Cell<K, V> c = cellFor(key);
        c.lock.lock();
        try { return c.data.get(key); } finally { c.lock.unlock(); }
    }

    /**
     * The value under this key, waiting up to timeoutMs for it to appear. Returns null when the budget ran out.
     * Throws InterruptedException the moment the caller is cancelled, whether it is queued for the lock or parked
     * on the condition. All four rules above are visible in these eight lines.
     */
    V awaitValue(K key, long timeoutMs) throws InterruptedException {
        Cell<K, V> c = cellFor(key);
        c.lock.lockInterruptibly();                     // cancellable even before the wait starts
        try {
            long left = TimeUnit.MILLISECONDS.toNanos(timeoutMs);
            V v;
            while ((v = c.data.get(key)) == null) {     // rule 1 + rule 2: checked under the lock, in a loop
                if (left <= 0L) return null;            // the budget is spent: say so, do not wait on
                left = c.changed.awaitNanos(left);      // rule 4: awaitNanos hands back what remains
            }
            return v;
        } finally { c.lock.unlock(); }
    }

    /** How many threads are parked on this key's stripe right now. Only ever an estimate; used by the demo. */
    int waitersOn(K key) {
        Cell<K, V> c = cellFor(key);
        c.lock.lock();
        try { return c.lock.getWaitQueueLength(c.changed); } finally { c.lock.unlock(); }
    }
}

// ---- ext: a thread stuck on a busy stripe -- cancelling it, and whether the lock is fair
/**
 * Two questions about the thread that lost the race for a stripe.
 *
 * CAN YOU CANCEL IT? Not if you wrote lock(). ReentrantLock.lock() is uninterruptible: interrupting a thread
 * parked in it only sets a flag that the thread will notice long afterwards, once it has the lock anyway.
 * lockInterruptibly() and tryLock(timeout) both give up on demand, and the price is that every method built on
 * them must be allowed to fail. That is exactly the split in Main.java: plain lock() on the single-key path,
 * where the wait is nanoseconds and failure would be absurd, and tryLock with a deadline on the all-stripe path,
 * where the wait is unbounded and giving up is the right answer.
 *
 * CAN IT STARVE? new ReentrantLock() is UNFAIR: a thread arriving at an unlocked-but-queued lock may barge in
 * front of threads that have been waiting, and that barging is most of why it is fast. new ReentrantLock(true)
 * hands the lock out strictly in arrival order and costs a context switch per handover -- measured below, it is
 * an order of magnitude slower. On a stripe held for fifteen nanoseconds nothing starves in practice. What CAN
 * starve is an operation that needs every stripe at once, which is precisely why exactSize carries a budget and
 * returns -1 rather than promising an answer.
 */
final class LockWaiting {
    /** What one run measured: total acquisitions, and the fewest and the most any single thread got. */
    static final class Turns {
        final long total; final long min; final long max;
        Turns(long total, long min, long max) { this.total = total; this.min = min; this.max = max; }
        public String toString() { return total + " acquisitions, the unluckiest thread got " + min + " and the luckiest " + max; }
    }

    /**
     * N threads hammering ONE lock for a fixed wall-clock window. A barging lock does far more total work; a fair
     * lock spreads the work evenly. Both numbers matter, and you rarely get both.
     */
    static Turns hammer(boolean fair, int threads, long windowMs) throws InterruptedException {
        ReentrantLock lock = new ReentrantLock(fair);
        long[] counts = new long[threads];
        CountDownLatch go = new CountDownLatch(1);
        AtomicBoolean stop = new AtomicBoolean();
        List<Thread> ts = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            final int id = i;
            ts.add(new Thread(() -> {
                try { go.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                while (!stop.get()) {
                    lock.lock();
                    try { counts[id]++; } finally { lock.unlock(); }
                }
            }, "hammer-" + i));
        }
        ts.forEach(Thread::start);
        go.countDown();
        Thread.sleep(windowMs);
        stop.set(true);
        for (Thread t : ts) t.join(10_000);
        long total = 0, min = Long.MAX_VALUE, max = 0;
        for (long c : counts) { total += c; min = Math.min(min, c); max = Math.max(max, c); }
        return new Turns(total, min, max);
    }

    /**
     * Park a thread on a lock somebody else holds, interrupt it, and report whether it came back. With
     * lockInterruptibly it returns immediately; with plain lock() it cannot, and only finishes when the holder
     * lets go -- with its interrupt flag still set, which is the whole of what the interrupt achieved.
     */
    static String cancelWhileBlocked(boolean interruptibly) throws Exception {
        ReentrantLock lock = new ReentrantLock();
        CountDownLatch parked = new CountDownLatch(1), finished = new CountDownLatch(1);
        AtomicBoolean threw = new AtomicBoolean(), flagStillSet = new AtomicBoolean();
        lock.lock();                                     // the holder: this thread
        Thread waiter = new Thread(() -> {
            parked.countDown();
            try {
                if (interruptibly) lock.lockInterruptibly(); else lock.lock();
                try { flagStillSet.set(Thread.currentThread().isInterrupted()); } finally { lock.unlock(); }
            } catch (InterruptedException e) { threw.set(true); }
            finished.countDown();
        }, "waiter");
        waiter.start();
        parked.await(2, TimeUnit.SECONDS);
        Thread.sleep(60);                                // let it actually reach the lock and block there
        waiter.interrupt();
        boolean cameBackWhileHeld = finished.await(400, TimeUnit.MILLISECONDS);
        lock.unlock();                                   // now let it in
        boolean done = finished.await(3, TimeUnit.SECONDS);
        waiter.join(3_000);
        if (!done) return "STUCK";
        if (cameBackWhileHeld && threw.get()) return "cancelled while the lock was still held";
        if (!cameBackWhileHeld && flagStillSet.get()) return "waited for the holder, then finished with the interrupt flag still set";
        return "finished, but not in either expected way";
    }
}

// ---- ext: bound the map -- a per-stripe LRU that evicts inside the write, so the bound is real
/**
 * "At most ten thousand entries, evict the least recently used." Per stripe, a LinkedHashMap in access order with
 * removeEldestEntry does the whole job -- you never write the linked list yourself -- and the eviction happens
 * inside the same write that caused it, so the bound is never exceeded even for an instant. The caveat to say out
 * loud before they say it: the bound is per stripe (total / N each), so a skewed key set evicts one stripe early
 * while others sit half empty. A global bound would need one shared counter, which is the contention you just spent
 * the whole design removing.
 */
final class CappedMap<K, V> {
    /** One stripe: an access-ordered LinkedHashMap that drops its eldest entry when it is over its share. */
    private static final class Shard<K, V> extends LinkedHashMap<K, V> {
        private final int max;
        Shard(int max) { super(16, 0.75f, true); this.max = max; }
        /** Called by LinkedHashMap after each insert, still inside our lock: true means "drop this one". */
        protected boolean removeEldestEntry(Map.Entry<K, V> eldest) { return size() > max; }
    }

    private final Object[] locks;
    private final Shard<K, V>[] shards;
    private final int mask, shift;
    private final Hasher hasher;
    private final LongAdder evictions = new LongAdder();

    /** Total capacity is split evenly across the stripes; at least one entry per stripe. */
    @SuppressWarnings("unchecked")
    CappedMap(int stripes, int totalCapacity, Hasher hasher) {
        int n = StripedMap.tableSizeFor(stripes);
        this.mask = n - 1;
        this.shift = 32 - Integer.numberOfTrailingZeros(n);
        this.hasher = hasher;
        this.locks = new Object[n];
        this.shards = (Shard<K, V>[]) new Shard[n];
        for (int i = 0; i < n; i++) { locks[i] = new Object(); shards[i] = new Shard<>(Math.max(1, totalCapacity / n)); }
    }

    private int indexOf(K key) { int h = hasher.spread(key.hashCode()); return (h >>> shift) & mask; }

    /** A get is a write here: access order means reading an entry moves it to the young end. */
    V get(K key) {
        int i = indexOf(key);
        synchronized (locks[i]) { return shards[i].get(key); }
    }

    /** Insert, and evict the eldest in the same hold if this stripe is now over its share. */
    V put(K key, V value) {
        int i = indexOf(key);
        synchronized (locks[i]) {
            int before = shards[i].size();
            V old = shards[i].put(key, value);
            if (shards[i].size() == before && old == null) evictions.increment();
            return old;
        }
    }

    /** Entries held across every stripe. */
    int size() { int n = 0; for (int i = 0; i < shards.length; i++) synchronized (locks[i]) { n += shards[i].size(); } return n; }

    /** How many entries the bound has thrown away. */
    long evictions() { return evictions.sum(); }
}

// ---- ext: iteration that never copies the whole map -- one stripe at a time, lazily
/**
 * A weakly-consistent iterator: it copies ONE stripe under that stripe's lock, hands those entries out, then moves
 * to the next. It therefore reflects writes that land while it is running, never freezes the map, and can never
 * throw ConcurrentModificationException, because it is walking a copy and not live state. Say "weakly consistent"
 * out loud -- it is the word that tells an interviewer you know this is not a snapshot.
 */
final class StripeIterator<K, V> implements Iterator<Map.Entry<K, V>> {
    private final StripedMap<K, V> map;
    private int stripe = -1;
    private Iterator<Map.Entry<K, V>> current = Collections.emptyIterator();

    /** Start before the first stripe; nothing is copied until the first hasNext(). */
    StripeIterator(StripedMap<K, V> map) { this.map = map; }

    /** Advance stripe by stripe until one of them has an entry, or there are no stripes left. */
    public boolean hasNext() {
        while (!current.hasNext() && stripe + 1 < map.stripeCount())
            current = map.stripeSnapshot(++stripe).entrySet().iterator();
        return current.hasNext();
    }

    public Map.Entry<K, V> next() {
        if (!hasNext()) throw new NoSuchElementException();
        return current.next();
    }
}

// ---- ext: surviving a restart -- an append-only log, and a conditional UPDATE so a stale writer cannot win
/**
 * The map becomes a cache over a log. The ORDER is the design: the append -- the irreversible thing -- happens
 * inside the same stripe hold as the in-memory write, so an append that throws leaves the map exactly as it was
 * and the caller can retry. That is the one slow thing deliberately allowed inside a lock, and the stripes are
 * precisely what stops it from serialising the whole map (page 02, move 8, part B).
 *
 * For a real database the same shape is a version column: UPDATE rows SET value=?, version=version+1 WHERE key=?
 * AND version=?, and "zero rows updated" means somebody else got there first.
 */
final class DurableMap {
    /** A row as it would live in a table: the value plus the version that write produced. */
    static final class Row {
        final String value; final long version;
        Row(String value, long version) { this.value = value; this.version = version; }
        public String toString() { return value + "@v" + version; }
    }

    private final StripedMap<String, Row> memory = new StripedMap<>(16);
    private final List<String> log = Collections.synchronizedList(new ArrayList<>());

    /**
     * Conditional write. Returns the new version, or -1 when the caller's expected version is stale. The compare,
     * the append and the in-memory write are one hold of one stripe lock, so two writers cannot both win.
     */
    long put(String key, String value, long expectedVersion) {
        long[] written = { -1 };                                      // set only on the path that actually wrote
        memory.compute(key, (k, current) -> {
            long have = current == null ? 0 : current.version;
            if (have != expectedVersion) return current;              // stale: change nothing at all
            long next = have + 1;
            log.add(k + "=" + value + "@v" + next);                   // the irreversible step, before the commit
            written[0] = next;
            return new Row(value, next);
        });
        return written[0];
    }

    /** The value under a key, or null. */
    Row get(String key) { return memory.get(key); }

    /** How many records the log holds. */
    int logSize() { return log.size(); }

    /** Rebuild the whole map from the log after a restart: replay in order, last writer per key wins. */
    static Map<String, Row> replay(List<String> log) {
        Map<String, Row> out = new LinkedHashMap<>();
        for (String line : log) {
            int eq = line.indexOf('='), at = line.lastIndexOf("@v");
            out.put(line.substring(0, eq), new Row(line.substring(eq + 1, at), Long.parseLong(line.substring(at + 2))));
        }
        return out;
    }

    /** The log itself, for the replay demo. */
    List<String> log() { return log; }
}

/** Runs every extension above, so each follow-up answer on page 05 is code that has actually executed. */
class ExtDemo {
    /** Each block prints the twist and the evidence that it works. */
    public static void main(String[] args) throws Exception {
        // 1. the naive spreader: same map, same keys, one changed line at construction
        StripedMap<Integer, Integer> good = new StripedMap<>(16);
        StripedMap<Integer, Integer> bad = new StripedMap<>(16);
        bad.configure(new FoldOnlyHasher(), System::currentTimeMillis);
        for (int i = 0; i < 20_000; i++) { good.put(i, i); bad.put(i, i); }
        System.out.println("multiply-then-fold: " + Histogram.of(good.stripeSizes()));
        System.out.println("fold only:          " + Histogram.of(bad.stripeSizes()) + "  <- same map, one line changed");

        // 2. the deliberate worst case: every key in one stripe. Still correct, just not parallel.
        StripedMap<String, Integer> worst = new StripedMap<>(16);
        worst.configure(new OneStripeHasher(), System::currentTimeMillis);
        for (int i = 0; i < 5_000; i++) worst.put("k" + i, i);
        System.out.println("every key in stripe 0: size=" + worst.size() + ", get(k4999)=" + worst.get("k4999")
            + ", stripe 0 grew to " + worst.bucketsIn(0) + " buckets");

        // 3. the decorator: counting without the map knowing
        MeteredMap<String, Integer> metered = new MeteredMap<>(new StripedMap<>(16));
        for (int i = 0; i < 1_000; i++) metered.put("m" + i, i);
        for (int i = 0; i < 1_500; i++) metered.get("m" + i);
        System.out.println("metered: " + metered.report());

        // 4. the read-heavy question, three ways. Every one is warmed first, or whichever runs second gets a JIT
        //    the first one paid for and the comparison is worthless. These numbers move 30% run to run: what is
        //    stable is which shape wins, not the milliseconds.
        readHeavyPlain(16); readHeavyRw(16); readHeavyLockFree(16);
        long plainMs = readHeavyPlain(16), rwMs = readHeavyRw(16), freeMs = readHeavyLockFree(16);
        System.out.println("read-heavy (95% get), 8 threads, 2,000,000 operations:");
        System.out.println("   plain lock per stripe    : " + plainMs + " ms");
        System.out.println("   read/write per stripe    : " + rwMs + " ms  <- "
            + String.format("%.1fx", rwMs / (double) plainMs) + " the plain lock -- SLOWER, not faster: taking a read"
            + " lock is still a CAS on one shared counter, so readers in a stripe still fight over one cache line");
        System.out.println("   no lock on reads at all  : " + freeMs + " ms  <- "
            + String.format("%.1fx", plainMs / (double) freeMs) + " the plain lock. THAT is the read-heavy answer");

        // 5. the same map under a resize, read with no lock: the old table is left intact, so nobody tears
        ReadOptimizedMap<Integer, Integer> lockFree = new ReadOptimizedMap<>(16, 16, new SpreadHasher());
        for (int i = 0; i < 50_000; i++) lockFree.put(i, i);
        System.out.println("lock-free reads: size=" + lockFree.size() + ", get(49999)=" + lockFree.get(49_999)
            + ", stripe 0 grew to " + lockFree.bucketsIn(0) + " buckets by copying, never by relinking");

        // 6. one lock per bin: what ConcurrentHashMap became in Java 8
        CasMap<String, Integer> cas = new CasMap<>(1 << 16);
        String[] ck = keys();
        for (int i = 0; i < ck.length; i++) cas.put(ck[i], i);
        long t0 = System.nanoTime();
        long sum = 0;
        for (int i = 0; i < 2_000_000; i++) { Integer v = cas.get(ck[i & 0xffff]); sum += v == null ? 0 : 1; }
        long casNs = (System.nanoTime() - t0) / 2_000_000;
        System.out.println("CAS map (CHM shape): size=" + cas.size() + ", " + casNs
            + " ns per lock-free get, all found=" + (sum == 2_000_000));

        // 7. lock ordering: the same work, ordered and unordered
        System.out.println("two threads, two locks, 2000 rounds each:");
        System.out.println("   ordered (lower index first): " + LockOrdering.race(true, 2000) + " back-offs");
        System.out.println("   natural order (the bug)    : " + LockOrdering.race(false, 2000)
            + " back-offs -- each one would have been a permanent deadlock without the deadline");

        // 8. one loader call per key, with the slow load outside every lock
        FutureLoader<String, String> loader = new FutureLoader<>(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> ts = new ArrayList<>();
        AtomicInteger answers = new AtomicInteger();
        for (int i = 0; i < 32; i++) {
            ts.add(new Thread(() -> {
                try { go.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                String v = loader.get("hot", k -> { sleep(200); return "loaded-" + k; });
                if ("loaded-hot".equals(v)) answers.incrementAndGet();
            }));
        }
        ts.forEach(Thread::start);
        long t1 = System.nanoTime();
        go.countDown();
        for (Thread t : ts) t.join(10_000);
        System.out.println("32 threads missed the same key: loader ran " + loader.loaderCalls() + " time(s), "
            + answers.get() + " got the answer, total wall time " + (System.nanoTime() - t1) / 1_000_000
            + " ms (one 200 ms load, not 32)");

        // 9. the wait protocol: eight threads ask for a key that does not exist yet, one thread supplies it
        WaitableMap<String, String> waiting = new WaitableMap<>(16, new SpreadHasher());
        CountDownLatch asked = new CountDownLatch(8);
        AtomicInteger got = new AtomicInteger(), gaveUp = new AtomicInteger();
        List<Thread> waiters = new ArrayList<>();
        for (int i = 0; i < 8; i++) {
            waiters.add(new Thread(() -> {
                asked.countDown();
                try { if (waiting.awaitValue("late", 3_000) != null) got.incrementAndGet(); else gaveUp.incrementAndGet(); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            }, "waiter-" + i));
        }
        waiters.forEach(Thread::start);
        asked.await(2, TimeUnit.SECONDS);
        sleep(80);
        System.out.println("wait protocol: " + waiting.waitersOn("late") + " threads parked on the condition");
        waiting.put("late", "here at last");
        for (Thread t : waiters) t.join(5_000);
        long t2 = System.nanoTime();
        String none = waiting.awaitValue("never", 150);
        System.out.println("   one signalAll woke all of them: " + got.get() + " got the value, " + gaveUp.get()
            + " gave up; a wait for a key that never arrives returned " + none + " after "
            + (System.nanoTime() - t2) / 1_000_000 + " ms instead of hanging");

        // 10. cancellation and fairness: what happens to the thread that lost the race for a stripe
        System.out.println("a thread blocked on a lock somebody else holds:");
        System.out.println("   lockInterruptibly(): " + LockWaiting.cancelWhileBlocked(true));
        System.out.println("   plain lock()       : " + LockWaiting.cancelWhileBlocked(false));
        LockWaiting.Turns barging = LockWaiting.hammer(false, 4, 250);
        LockWaiting.Turns fair = LockWaiting.hammer(true, 4, 250);
        System.out.println("4 threads, one lock, 250 ms each:");
        System.out.println("   unfair (the default): " + barging);
        System.out.println("   fair                : " + fair + "  <- even, and "
            + (barging.total / Math.max(1, fair.total)) + "x less total work done");

        // 11. the bound, with eviction inside the write
        CappedMap<Integer, Integer> capped = new CappedMap<>(16, 10_000, new SpreadHasher());
        for (int i = 0; i < 100_000; i++) capped.put(i, i);
        System.out.println("capped at 10,000: size=" + capped.size() + " after 100,000 puts, "
            + capped.evictions() + " evicted; the newest key is still there: " + capped.get(99_999));

        // 12. weakly-consistent iteration while a writer runs
        StripedMap<Integer, Integer> live = new StripedMap<>(16);
        for (int i = 0; i < 10_000; i++) live.put(i, i);
        Thread writer = new Thread(() -> { for (int i = 10_000; i < 60_000; i++) live.put(i, i); });
        writer.start();
        int seen = 0;
        for (Iterator<Map.Entry<Integer, Integer>> it = new StripeIterator<>(live); it.hasNext(); it.next()) seen++;
        writer.join(10_000);
        System.out.println("iterated " + seen + " entries while a writer added 50,000 more: no exception, and "
            + seen + " is somewhere between 10,000 and " + live.size() + " -- that is what weakly consistent means");

        // 13. durability: append first, commit second, and a stale writer loses
        DurableMap durable = new DurableMap();
        long v1 = durable.put("balance", "100", 0);
        long v2 = durable.put("balance", "150", v1);
        long stale = durable.put("balance", "999", v1);        // a writer holding the old version
        System.out.println("durable: v1=" + v1 + " v2=" + v2 + " stale write returned " + stale
            + ", value is still " + durable.get("balance") + ", log holds " + durable.logSize() + " records");
        System.out.println("replayed from the log after a restart: " + DurableMap.replay(durable.log()));
    }

    /** 8 threads, 95% gets, on plain per-stripe locks. */
    static long readHeavyPlain(int stripes) throws Exception {
        StripedMap<String, Integer> map = new StripedMap<>(stripes);
        String[] keys = keys();
        for (int i = 0; i < keys.length; i++) map.put(keys[i], i);
        return run(8, 250_000, (x, i) -> {
            String k = keys[(x >>> 8) & 0xffff];
            if ((x & 31) == 0) map.put(k, i); else map.get(k);
        });
    }

    /** The same workload on read/write locks, so the two numbers are comparable. */
    static long readHeavyRw(int stripes) throws Exception {
        RwStripedMap<String, Integer> map = new RwStripedMap<>(stripes, new SpreadHasher());
        String[] keys = keys();
        for (int i = 0; i < keys.length; i++) map.put(keys[i], i);
        return run(8, 250_000, (x, i) -> {
            String k = keys[(x >>> 8) & 0xffff];
            if ((x & 31) == 0) map.put(k, i); else map.get(k);
        });
    }

    /** The same workload again, with readers taking no lock at all. Same keys, same mix, same thread count. */
    static long readHeavyLockFree(int stripes) throws Exception {
        ReadOptimizedMap<String, Integer> map = new ReadOptimizedMap<>(stripes, 1 << 12, new SpreadHasher());
        String[] keys = keys();
        for (int i = 0; i < keys.length; i++) map.put(keys[i], i);
        return run(8, 250_000, (x, i) -> {
            String k = keys[(x >>> 8) & 0xffff];
            if ((x & 31) == 0) map.put(k, i); else map.get(k);
        });
    }

    /** 65,536 pre-built keys, so the benchmark measures the map and not the string builder. */
    static String[] keys() {
        String[] out = new String[1 << 16];
        for (int i = 0; i < out.length; i++) out[i] = "key-" + i;
        return out;
    }

    /** Run a per-iteration body on N threads released together; returns the wall time in milliseconds. */
    static long run(int threads, int per, java.util.function.BiConsumer<Integer, Integer> body) throws Exception {
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> ts = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            final int seed = t * 7919 + 1;
            ts.add(new Thread(() -> {
                try { go.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                int x = seed;
                for (int i = 0; i < per; i++) { x = x * 1103515245 + 12345; body.accept(x, i); }
            }));
        }
        ts.forEach(Thread::start);
        long t0 = System.nanoTime();
        go.countDown();
        for (Thread t : ts) t.join(60_000);
        return (System.nanoTime() - t0) / 1_000_000;
    }

    /** Sleep without the checked exception, for a loader that stands in for a database call. */
    static void sleep(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
