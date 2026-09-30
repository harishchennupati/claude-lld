import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

/**
 * Where time comes from. Injected, never read off the wall clock inside a method, so a test can hand in a clock
 * whose reading is already past a deadline and watch a budgeted operation give up without actually waiting.
 */
interface Clock {
    /** Milliseconds since some fixed origin. Only differences are ever used, so the origin does not matter. */
    long nowMs();
}

/**
 * The promise the callers depend on: read a key, write a key, and -- because callers will want counters --
 * read-modify-write a key as ONE atomic step. Nothing in here mentions stripes or locks, so the implementation
 * underneath can be swapped for a global lock or for java.util.concurrent.ConcurrentHashMap without touching a
 * single call site.
 */
interface KeyValueStore<K, V> {
    /** The value stored under this key, or null when there is none. Null keys and values are refused, so null is unambiguous. */
    V get(K key);
    /** Store the value; returns what was there before, or null when the key is new. Last writer wins. */
    V put(K key, V value);
    /** Store only when the key is absent. Returns the value that won: the existing one, or null when this call stored. */
    V putIfAbsent(K key, V value);
    /** Remove the key; returns the value it held, or null when it held none. */
    V remove(K key);
    /** Compare-and-set on one key: replaces only when the current value equals expected. One lock hold, so it cannot race. */
    boolean replace(K key, V expected, V updated);
    /** Read-modify-write in ONE lock hold: remap(old, value) when the key exists, value when it does not. Never loses an update. */
    V merge(K key, V value, BinaryOperator<V> remap);
    /** The general read-modify-write: remap(key, current-or-null) runs inside one lock hold; returning null removes the key. */
    V compute(K key, BiFunction<? super K, ? super V, ? extends V> remap);
    /** Load on miss, with the loader running at most once per key: a second caller waits and takes the first one's answer. */
    V computeIfAbsent(K key, Function<? super K, ? extends V> loader);
    /** How many entries are held. Weakly consistent: a sum of per-stripe counters, taken with no lock at all. */
    int size();
}

/**
 * The one rule most likely to change per workload: how a key's hashCode becomes the bits that pick a stripe and a
 * bucket. Handed in, so "our keys are sequential Longs and they all pile into four stripes" is a new class and one
 * changed line at construction, never an edit to anything that holds a lock.
 */
interface Hasher {
    /** Spread a raw hashCode. Must be a pure function of its argument: the same key has to reach the same stripe every time. */
    int spread(int hashCode);
}

/**
 * The default spreader: multiply by the 32-bit golden ratio so every input bit reaches every output bit, then fold
 * the top sixteen down with an xor. The multiply is the part that matters here. java.util.HashMap gets away with
 * the fold alone because it only ever uses the LOW bits; this map picks a stripe from the HIGH bits, and a fold
 * leaves those exactly as they were -- so with a fold-only spreader every sequential Integer key lands in stripe 0.
 */
final class SpreadHasher implements Hasher {
    /** Fibonacci mix, then fold: consecutive keys come out far apart in both the high bits and the low ones. */
    public int spread(int hashCode) {
        int h = hashCode * 0x9E3779B1;
        return h ^ (h >>> 16);
    }
}

/**
 * Whoever wants to know that a write happened: a metrics counter, an audit line, a cache invalidator. Called AFTER
 * the stripe lock is released, inside a try/catch, so a slow or broken listener can never hold a stripe shut.
 */
interface MapObserver {
    /** One completed write. op is "put" / "remove" / "merge" / "compute"; stripe is the index the key landed in. */
    void onWrite(String op, Object key, int stripe, long atMs);
}

/**
 * One node in a bucket's collision chain: the key, its spread hash cached so a lookup compares two ints before it
 * ever calls equals, the value, and the next node. Only value and next ever change, and only under the owning
 * stripe's lock; key and hash are final, which is what makes a node safe to read once it is published.
 */
final class Entry<K, V> {
    final K key;
    final int hash;
    V value;
    Entry<K, V> next;

    /** Build a node that already points at the current head of its bucket, so publishing it is one reference write. */
    Entry(K key, int hash, V value, Entry<K, V> next) {
        this.key = key; this.hash = hash; this.value = value; this.next = next;
    }
}

/**
 * One stripe: a bucket array, a count, and its own lock. This is the monitor object of the design -- every field
 * is private, and every path that touches one goes through a method that takes the lock, so "who guards this
 * state" has exactly one answer. Stripes know nothing about each other, which is the whole point: two threads
 * working on two stripes never meet.
 */
final class Segment<K, V> {
    /** The one lock guarding everything below. Package-private because the map takes it for two-stripe operations. */
    final ReentrantLock lock = new ReentrantLock();
    private Entry<K, V>[] table;
    /** Entries held. Volatile so size() can read it with no lock; written only under the lock, and written LAST. */
    private volatile int count;
    private int threshold;
    private final float loadFactor;
    /** How often a thread found this stripe already held. The only contention number worth quoting. */
    private final LongAdder waits = new LongAdder();

    /** A stripe with its own bucket array. Capacity is rounded to a power of two by the caller. */
    Segment(int capacity, float loadFactor) {
        this.table = newTable(capacity);
        this.loadFactor = loadFactor;
        this.threshold = (int) (capacity * loadFactor);
    }

    /** Allocate a bucket array. The one unavoidable unchecked cast: Java cannot make an array of a generic type. */
    @SuppressWarnings("unchecked")
    private Entry<K, V>[] newTable(int capacity) { return (Entry<K, V>[]) new Entry[capacity]; }

    /** Take the lock, counting the times somebody else already had it. An uncontended tryLock is the same CAS as lock(). */
    private void acquire() {
        if (!lock.tryLock()) { waits.increment(); lock.lock(); }
    }

    /** The bucket a hash belongs to. The low bits, masked -- a power-of-two length turns a modulo into an AND. */
    private int indexFor(int hash) { return hash & (table.length - 1); }

    // ---- the public surface: each one takes the lock, does its work, and releases it in a finally

    /** Look the key up. Reads take the lock too in this version; rung 2 of the ladder is where readers stop excluding readers. */
    V get(K key, int hash) { acquire(); try { return getLocked(key, hash); } finally { lock.unlock(); } }

    /** Insert or overwrite in one hold. Returns the previous value, or null when the key is new. */
    V put(K key, int hash, V value) { acquire(); try { return putLocked(key, hash, value); } finally { lock.unlock(); } }

    /** Insert only when absent. The check and the write are one hold, so two threads cannot both think they are first. */
    V putIfAbsent(K key, int hash, V value) {
        acquire();
        try {
            Entry<K, V> e = findLocked(key, hash);
            if (e != null) return e.value;
            putLocked(key, hash, value);
            return null;
        } finally { lock.unlock(); }
    }

    /** Remove in one hold. Returns the value that was there, or null. */
    V remove(K key, int hash) { acquire(); try { return removeLocked(key, hash); } finally { lock.unlock(); } }

    /** Compare-and-set on a value. The compare and the set are one hold: this is what makes it a CAS and not a race. */
    boolean replace(K key, int hash, V expected, V updated) {
        acquire();
        try {
            Entry<K, V> e = findLocked(key, hash);
            if (e == null || !e.value.equals(expected)) return false;
            e.value = updated;
            return true;
        } finally { lock.unlock(); }
    }

    /**
     * The read-modify-write that the whole design exists for. The caller's remap function runs INSIDE the one lock
     * hold, between the read and the write, so no other thread can slip an update in between and have it overwritten.
     * If remap throws, nothing has been written yet and the map is exactly as it was.
     */
    V merge(K key, int hash, V value, BinaryOperator<V> remap) {
        acquire();
        try {
            Entry<K, V> e = findLocked(key, hash);
            if (e == null) { putLocked(key, hash, value); return value; }
            V merged = remap.apply(e.value, value);
            if (merged == null) { removeLocked(key, hash); return null; }
            e.value = merged;
            return merged;
        } finally { lock.unlock(); }
    }

    /**
     * The general form of merge: the caller's function sees the key and whatever is there (null when absent), and
     * whatever it returns is stored -- or the key is removed when it returns null. One hold, so a durable store can
     * append to its log inside this same hold and know the map and the log can never disagree.
     */
    V compute(K key, int hash, BiFunction<? super K, ? super V, ? extends V> remap) {
        acquire();
        try {
            Entry<K, V> e = findLocked(key, hash);
            V made = remap.apply(key, e == null ? null : e.value);
            if (made == null) { if (e != null) removeLocked(key, hash); return null; }
            if (e != null) { e.value = made; return made; }
            putLocked(key, hash, made);
            return made;
        } finally { lock.unlock(); }
    }

    /**
     * Load on miss with the loader inside the lock, which is what buys "called exactly once per key": the second
     * caller blocks on the stripe, and by the time it gets in the entry is there. The price is honest and worth
     * saying out loud -- a slow loader holds up every other key in this stripe.
     */
    V computeIfAbsent(K key, int hash, Function<? super K, ? extends V> loader) {
        acquire();
        try {
            Entry<K, V> e = findLocked(key, hash);
            if (e != null) return e.value;
            V made = loader.apply(key);
            if (made == null) return null;
            putLocked(key, hash, made);
            return made;
        } finally { lock.unlock(); }
    }

    /** Entries held right now. A plain volatile read: no lock, so size() cannot be the thing that stops the map. */
    int size() { return count; }

    /** Buckets in this stripe's array right now. Grows on resize; useful only for the demo and the tests. */
    int capacity() { lock.lock(); try { return table.length; } finally { lock.unlock(); } }

    /** How many times a thread arrived to find this stripe busy. */
    long waitCount() { return waits.sum(); }

    // ---- [lock held] the same work, without taking the lock: for the map's two-stripe and all-stripe operations

    /** [lock held] Walk the chain. The cached int hash is compared first, so equals runs at most once per bucket. */
    Entry<K, V> findLocked(K key, int hash) {
        for (Entry<K, V> e = table[indexFor(hash)]; e != null; e = e.next)
            if (e.hash == hash && e.key.equals(key)) return e;
        return null;
    }

    /** [lock held] The value under this key, or null. */
    V getLocked(K key, int hash) {
        Entry<K, V> e = findLocked(key, hash);
        return e == null ? null : e.value;
    }

    /**
     * [lock held] Insert or overwrite. The ORDER is the design: the node is built pointing at the current head and
     * published with one reference write, and only THEN is the volatile count raised. A size() running without any
     * lock therefore never counts an entry it could not have found.
     */
    V putLocked(K key, int hash, V value) {
        int i = indexFor(hash);
        for (Entry<K, V> e = table[i]; e != null; e = e.next)
            if (e.hash == hash && e.key.equals(key)) { V old = e.value; e.value = value; return old; }
        table[i] = new Entry<>(key, hash, value, table[i]);
        count = count + 1;
        if (count > threshold) resize();
        return null;
    }

    /** [lock held] Unlink the node from its chain and lower the count. Returns the value it held, or null. */
    V removeLocked(K key, int hash) {
        int i = indexFor(hash);
        Entry<K, V> prev = null;
        for (Entry<K, V> e = table[i]; e != null; prev = e, e = e.next)
            if (e.hash == hash && e.key.equals(key)) {
                if (prev == null) table[i] = e.next; else prev.next = e.next;
                count = count - 1;
                return e.value;
            }
        return null;
    }

    /** [lock held] Copy every entry of this stripe into the sink. Used by the map's snapshot. */
    void copyInto(Map<K, V> sink) {
        for (Entry<K, V> head : table)
            for (Entry<K, V> e = head; e != null; e = e.next) sink.put(e.key, e.value);
    }

    /** [lock held] Drop everything in this stripe. */
    void clearLocked() {
        table = newTable(16);
        threshold = (int) (16 * loadFactor);
        count = 0;
    }

    /**
     * [lock held] Double the bucket array and rehash every chain into it, then swap the table in ONE reference
     * write. The whole rehash happens under this stripe's lock, so no thread can be walking a chain while its nodes
     * are being relinked -- that is precisely why get() takes the lock in this version, and precisely what a
     * lock-free read would have to pay for (see rung 3 of the ladder).
     */
    private void resize() {
        Entry<K, V>[] old = table;
        int cap = old.length << 1;
        if (cap <= 0) return;                       // 2^30 buckets is the ceiling; refuse to overflow the int
        Entry<K, V>[] fresh = newTable(cap);
        for (Entry<K, V> head : old)
            for (Entry<K, V> e = head; e != null; ) {
                Entry<K, V> next = e.next;
                int i = e.hash & (cap - 1);
                e.next = fresh[i];
                fresh[i] = e;
                e = next;
            }
        table = fresh;
        threshold = (int) (cap * loadFactor);
    }
}

/**
 * The aggregate root, and mostly a router: it owns a power-of-two array of stripes, spreads a key's hash once,
 * picks the stripe with the HIGH bits and hands the whole hash to that stripe, which picks a bucket with the LOW
 * bits. Two bit ranges, so the stripe choice and the bucket choice never correlate.
 *
 * The invariant: a key lives in exactly one stripe, and every read-modify-write on that key happens inside one
 * hold of that stripe's lock. No update is ever lost, and no reader ever sees a half-built chain.
 */
final class StripedMap<K, V> implements KeyValueStore<K, V> {
    private final Segment<K, V>[] segments;
    private final int segMask;
    private final int segShift;
    /** Handed in, never built here after construction. Volatile so a late configure() is at least visible. */
    private volatile Hasher hasher = new SpreadHasher();
    private volatile Clock clock = System::currentTimeMillis;
    private final List<MapObserver> observers = new CopyOnWriteArrayList<>();

    /** A map with at least this many stripes, rounded UP to a power of two so the stripe choice is a mask, not a modulo. */
    StripedMap(int stripes) { this(stripes, 16, 0.75f); }

    /** The full form: stripe count, the bucket array each stripe starts with, and the load factor that triggers its resize. */
    @SuppressWarnings("unchecked")
    StripedMap(int stripes, int bucketsPerStripe, float loadFactor) {
        int n = tableSizeFor(stripes);
        this.segMask = n - 1;
        this.segShift = 32 - Integer.numberOfTrailingZeros(n);
        this.segments = (Segment<K, V>[]) new Segment[n];
        int buckets = tableSizeFor(bucketsPerStripe);
        for (int i = 0; i < n; i++) this.segments[i] = new Segment<>(buckets, loadFactor);
    }

    /** Hand in the two rules the map must not build for itself: how to spread a hash, and where time comes from. */
    void configure(Hasher hasher, Clock clock) {
        this.hasher = Objects.requireNonNull(hasher);
        this.clock = Objects.requireNonNull(clock);
    }

    /** Register a listener. It is called after the lock is released, so it can be as slow as it likes. */
    void addObserver(MapObserver o) { observers.add(o); }

    /** Round up to the next power of two, so a mask can replace a modulo everywhere. 17 stripes becomes 32. */
    static int tableSizeFor(int c) {
        int n = -1 >>> Integer.numberOfLeadingZeros(Math.max(1, c) - 1);
        return (n < 0) ? 1 : (n >= 1 << 30) ? 1 << 30 : n + 1;
    }

    /** The spread hash of a key. Null keys are refused here, once, so no stripe has to think about them. */
    private int hashOf(K key) {
        Objects.requireNonNull(key, "null keys are not allowed: get() could not tell absent from null");
        return hasher.spread(key.hashCode());
    }

    /** The stripe index for a spread hash: the top bits, masked. Decorrelated from the bucket, which uses the low bits. */
    int stripeIndex(int hash) { return (hash >>> segShift) & segMask; }

    /** Which stripe a key lands in. Public for the demo, the tests and the pictures on page 02. */
    int stripeOf(K key) { return stripeIndex(hashOf(key)); }

    /** How many stripes this map has: the rounded-up power of two, not necessarily what was asked for. */
    int stripeCount() { return segments.length; }

    /** How many times any thread arrived at a stripe that was already held. Summed across stripes. */
    long waitCount() { long n = 0; for (Segment<K, V> s : segments) n += s.waitCount(); return n; }

    /** Entries per stripe right now: the histogram that tells you whether the hasher is doing its job. */
    int[] stripeSizes() {
        int[] out = new int[segments.length];
        for (int i = 0; i < segments.length; i++) out[i] = segments[i].size();
        return out;
    }

    /** How many buckets one stripe has grown to. Each stripe resizes on its own, so these can differ. */
    int bucketsIn(int stripe) { return segments[stripe].capacity(); }

    // ---- the single-key operations: spread once, route once, one stripe lock, then tell the listeners

    public V get(K key) { int h = hashOf(key); return segments[stripeIndex(h)].get(key, h); }

    public V put(K key, V value) {
        Objects.requireNonNull(value, "null values are not allowed: get() could not tell absent from null");
        int h = hashOf(key), i = stripeIndex(h);
        V old = segments[i].put(key, h, value);
        publish("put", key, i);
        return old;
    }

    public V putIfAbsent(K key, V value) {
        Objects.requireNonNull(value);
        int h = hashOf(key), i = stripeIndex(h);
        V won = segments[i].putIfAbsent(key, h, value);
        if (won == null) publish("put", key, i);
        return won;
    }

    public V remove(K key) {
        int h = hashOf(key), i = stripeIndex(h);
        V gone = segments[i].remove(key, h);
        if (gone != null) publish("remove", key, i);
        return gone;
    }

    public boolean replace(K key, V expected, V updated) {
        Objects.requireNonNull(updated);
        int h = hashOf(key), i = stripeIndex(h);
        boolean done = segments[i].replace(key, h, expected, updated);
        if (done) publish("replace", key, i);
        return done;
    }

    public V merge(K key, V value, BinaryOperator<V> remap) {
        Objects.requireNonNull(value);
        int h = hashOf(key), i = stripeIndex(h);
        V now = segments[i].merge(key, h, value, remap);
        publish("merge", key, i);
        return now;
    }

    public V compute(K key, BiFunction<? super K, ? super V, ? extends V> remap) {
        int h = hashOf(key), i = stripeIndex(h);
        V now = segments[i].compute(key, h, remap);
        publish("compute", key, i);
        return now;
    }

    public V computeIfAbsent(K key, Function<? super K, ? extends V> loader) {
        int h = hashOf(key), i = stripeIndex(h);
        V v = segments[i].computeIfAbsent(key, h, loader);
        publish("compute", key, i);
        return v;
    }

    /** Weakly consistent: a sum of volatile counters taken with no lock, so it can miss a write that lands mid-sum. */
    public int size() {
        long n = 0;
        for (Segment<K, V> s : segments) n += s.size();
        return (int) Math.min(n, Integer.MAX_VALUE);
    }

    // ---- the all-stripe operations: every lock, in index order, with a budget

    /**
     * The exact count, taken with every stripe lock held so no write can slip between two of the counters. Returns
     * -1 when the budget ran out: an exact size fights the whole map, and a monitoring call must never be the thing
     * that stops it. The order is stripe 0, 1, 2 ... always, which is what makes a deadlock impossible.
     */
    int exactSize(long budgetMs) {
        if (!lockAll(budgetMs)) return -1;
        try {
            int n = 0;
            for (Segment<K, V> s : segments) n += s.size();
            return n;
        } finally { unlockAll(segments.length); }
    }

    /** A frozen copy of the whole map, taken with every lock held. Null when the budget ran out. O(n): say so out loud. */
    Map<K, V> snapshot(long budgetMs) {
        if (!lockAll(budgetMs)) return null;
        try {
            Map<K, V> out = new LinkedHashMap<>();
            for (Segment<K, V> s : segments) s.copyInto(out);
            return out;
        } finally { unlockAll(segments.length); }
    }

    /** A copy of ONE stripe, under just that stripe's lock: the unit a weakly-consistent iterator walks. */
    Map<K, V> stripeSnapshot(int stripe) {
        Segment<K, V> s = segments[stripe];
        s.lock.lock();
        try { Map<K, V> out = new LinkedHashMap<>(); s.copyInto(out); return out; }
        finally { s.lock.unlock(); }
    }

    /**
     * A copy taken one stripe at a time. It reflects writes that land while it runs, so it is NOT a frozen moment
     * -- but it holds one lock at a time, never blocks the whole map, and cannot throw
     * ConcurrentModificationException, because it copies instead of iterating live state.
     */
    Map<K, V> weakSnapshot() {
        Map<K, V> out = new LinkedHashMap<>();
        for (Segment<K, V> s : segments) {
            s.lock.lock();
            try { s.copyInto(out); } finally { s.lock.unlock(); }
        }
        return out;
    }

    /** Empty every stripe, with all locks held so nobody sees the map half-empty. False when the budget ran out. */
    boolean clear(long budgetMs) {
        if (!lockAll(budgetMs)) return false;
        try { for (Segment<K, V> s : segments) s.clearLocked(); return true; }
        finally { unlockAll(segments.length); }
    }

    /**
     * Move a value from one key to another as ONE atomic step, even when the two keys live in different stripes.
     * The ORDER is the whole answer: always take the lower stripe index first. Two threads moving in opposite
     * directions then ask for the same lock first, so one of them waits instead of both holding half of what the
     * other needs. Taking them "naturally" -- source first, destination second -- deadlocks within seconds.
     */
    boolean moveValue(K from, K to) {
        int hf = hashOf(from), ht = hashOf(to);
        int i = stripeIndex(hf), j = stripeIndex(ht);
        int first = Math.min(i, j), second = Math.max(i, j);
        segments[first].lock.lock();
        if (second != first) segments[second].lock.lock();
        try {
            V v = segments[i].getLocked(from, hf);
            if (v == null) return false;
            segments[i].removeLocked(from, hf);
            segments[j].putLocked(to, ht, v);
            return true;
        } finally {
            if (second != first) segments[second].lock.unlock();
            segments[first].lock.unlock();
        }
    }

    /** Every stripe lock, in index order, inside a deadline taken from the injected clock. All or nothing. */
    private boolean lockAll(long budgetMs) {
        long deadline = clock.nowMs() + budgetMs;
        int held = 0;
        try {
            for (int i = 0; i < segments.length; i++) {
                long left = deadline - clock.nowMs();
                if (left <= 0 || !segments[i].lock.tryLock(left, TimeUnit.MILLISECONDS)) { unlockAll(held); return false; }
                held++;
            }
        } catch (InterruptedException e) {
            unlockAll(held);
            Thread.currentThread().interrupt();
            return false;
        }
        return true;
    }

    /** Release the first `held` stripe locks in reverse order. */
    private void unlockAll(int held) { for (int i = held - 1; i >= 0; i--) segments[i].lock.unlock(); }

    /** Tell the listeners, AFTER the lock is gone and inside a try/catch: a broken listener cannot break a write. */
    private void publish(String op, K key, int stripe) {
        if (observers.isEmpty()) return;
        long at = clock.nowMs();
        for (MapObserver o : observers) {
            try { o.onWrite(op, key, stripe, at); } catch (RuntimeException ignored) { }
        }
    }
}

/**
 * A demo and a race. The demo shows one thread's view: routing, chaining, growth. The race shows the two claims
 * that matter -- a read-modify-write inside one lock hold never loses an increment, and writers on different
 * stripes really do run at the same time -- and the arithmetic behind the ladder on page 02, move 8.
 */
public class Main {
    /** Everything this page claims, run once and printed. */
    public static void main(String[] args) throws Exception {
        oneThread();
        theLostUpdate();
        theRace();
        theArithmetic();
    }

    /** Claim 1: a key routes to exactly one stripe, collisions chain, and a stripe that fills up grows by itself. */
    static void oneThread() {
        StripedMap<String, Integer> map = new StripedMap<>(16);
        map.put("alice", 1);
        map.put("bob", 2);
        map.put("carol", 3);
        System.out.println("get(bob)=" + map.get("bob") + "  stripes: alice->" + map.stripeOf("alice")
            + " bob->" + map.stripeOf("bob") + " carol->" + map.stripeOf("carol") + " of " + map.stripeCount());
        System.out.println("removed bob=" + map.remove("bob") + ", get(bob) is now " + map.get("bob")
            + ", size=" + map.size());
        map.merge("hits", 1, Integer::sum);
        map.merge("hits", 1, Integer::sum);
        System.out.println("merge twice on a fresh key -> " + map.get("hits")
            + "; putIfAbsent on a taken key returns the winner: " + map.putIfAbsent("hits", 99));

        StripedMap<Integer, Integer> grow = new StripedMap<>(4, 16, 0.75f);
        for (int i = 0; i < 20_000; i++) grow.put(i, i);
        int[] sizes = grow.stripeSizes();
        System.out.println("20,000 keys over " + grow.stripeCount() + " stripes: per-stripe counts "
            + Arrays.toString(sizes) + "; stripe 0 grew from 16 buckets to " + grow.bucketsIn(0)
            + " on its own; exact size=" + grow.exactSize(1000));
    }

    /** Claim 2: get-then-put loses increments; merge, which does both inside one lock hold, does not. */
    static void theLostUpdate() throws Exception {
        int threads = 8, iters = 50_000, expected = threads * iters;

        StripedMap<String, Integer> safe = new StripedMap<>(16);
        runAll(threads, () -> { for (int i = 0; i < iters; i++) safe.merge("hits", 1, Integer::sum); });
        System.out.println("merge (one lock hold)   -> " + safe.get("hits") + "   expected " + expected);

        StripedMap<String, Integer> racy = new StripedMap<>(16);
        runAll(threads, () -> {
            for (int i = 0; i < iters; i++) {
                Integer c = racy.get("hits");                  // hold one
                racy.put("hits", c == null ? 1 : c + 1);       // hold two: the gap between them is the bug
            }
        });
        int got = racy.get("hits");
        System.out.println("get-then-put (two holds)-> " + got + "   expected " + expected
            + "   LOST " + (expected - got) + " increments (" + (100 * (expected - got) / expected) + "%)");
    }

    /** Claim 3: fifty threads writing distinct keys land on different stripes, so almost nobody ever waits. */
    static void theRace() throws Exception {
        final int THREADS = 50, PER = 2_000, TOTAL = THREADS * PER;
        StripedMap<String, Integer> map = new StripedMap<>(16);
        AtomicInteger writes = new AtomicInteger();
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> ts = new ArrayList<>();
        for (int t = 0; t < THREADS; t++) {
            final int id = t;
            ts.add(new Thread(() -> {
                try { go.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                for (int i = 0; i < PER; i++) { map.put(id + ":" + i, i); writes.incrementAndGet(); }
            }, "writer-" + t));
        }
        ts.forEach(Thread::start);
        long t0 = System.nanoTime();
        go.countDown();
        for (Thread t : ts) t.join(30_000);
        long ms = (System.nanoTime() - t0) / 1_000_000;

        int missing = 0;
        for (int t = 0; t < THREADS; t++)
            for (int i = 0; i < PER; i++) if (map.get(t + ":" + i) == null) missing++;
        int[] sizes = map.stripeSizes();
        int min = Integer.MAX_VALUE, max = 0;
        for (int s : sizes) { min = Math.min(min, s); max = Math.max(max, s); }
        System.out.println("race: " + writes.get() + " writes by " + THREADS + " threads in " + ms + " ms; "
            + "exact size=" + map.exactSize(1000) + " weak size=" + map.size() + " missing=" + missing);
        System.out.println("      stripes held " + min + ".." + max + " entries each; a thread found a stripe busy "
            + map.waitCount() + " times out of " + TOTAL + " writes");
        if (missing != 0 || map.exactSize(1000) != TOTAL) throw new AssertionError("a key was lost");
    }

    /** Claim 4: the arithmetic behind the ladder -- what one lock costs, and what each doubling of the stripes buys. */
    static void theArithmetic() throws Exception {
        final int THREADS = 8, PER = 200_000;
        String[] keys = new String[1 << 16];
        Integer[] vals = new Integer[256];
        for (int i = 0; i < keys.length; i++) keys[i] = "key-" + i;
        for (int i = 0; i < vals.length; i++) vals[i] = i;             // pre-boxed: the loop allocates nothing

        timed(THREADS, 50_000, keys, vals, new StripedMap<>(16), 0);   // warm up the JIT before any measurement
        System.out.println("A. 8 threads, " + (THREADS * PER) + " writes over 65,536 keys, a tiny critical section:");
        for (int stripes : new int[] { 1, 2, 4, 16, 64 }) {
            StripedMap<String, Integer> map = new StripedMap<>(stripes);
            long ms = timed(THREADS, PER, keys, vals, map, 0);
            System.out.printf("   %3d stripe(s): %5d ms   %4d ns per write%n",
                map.stripeCount(), ms, ms * 1_000_000 / (THREADS * PER));
        }

        final int SLOW_PER = 20_000, SLOW_TOTAL = THREADS * SLOW_PER;
        System.out.println("B. the same, with real work INSIDE the lock (a loader, a big value, a listener):");
        long oneStripeMs = 0;
        for (int stripes : new int[] { 1, 4, 16, 64 }) {
            StripedMap<String, Integer> map = new StripedMap<>(stripes);
            long ms = timed(THREADS, SLOW_PER, keys, vals, map, 2200);
            if (stripes == 1) oneStripeMs = ms;
            System.out.printf("   %3d stripe(s): %5d ms   %,d writes/second   %.1fx the one-lock version%n",
                map.stripeCount(), ms, ms == 0 ? 0 : (long) SLOW_TOTAL * 1000 / ms, oneStripeMs / (double) ms);
        }
        System.out.println("   one lock serialises everything, so its time / writes IS the critical section: "
            + (oneStripeMs * 1_000_000 / SLOW_TOTAL) + " ns of work held the whole map");

        StripedMap<String, Integer> solo = new StripedMap<>(16);
        long t0 = System.nanoTime();
        for (int i = 0; i < 2_000_000; i++) solo.put(keys[i & 0xffff], vals[i & 0xff]);
        long put = (System.nanoTime() - t0) / 2_000_000;
        t0 = System.nanoTime();
        for (int i = 0; i < 2_000_000; i++) solo.get(keys[i & 0xffff]);
        long get = (System.nanoTime() - t0) / 2_000_000;
        System.out.println("C. one thread, nobody to contend with: " + put + " ns per put, " + get
            + " ns per get -- that is all that is inside the lock in part A");
    }

    /** Run one write loop on N threads released together, and return the wall time in milliseconds. */
    static long timed(int threads, int per, String[] keys, Integer[] vals,
                      StripedMap<String, Integer> map, int burn) throws Exception {
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> ts = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            final int seed = t * 7919 + 1;
            ts.add(new Thread(() -> {
                try { go.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
                int x = seed;
                for (int i = 0; i < per; i++) {
                    x = x * 1103515245 + 12345;
                    String k = keys[(x >>> 8) & 0xffff];
                    if (burn == 0) map.put(k, vals[i & 0xff]);
                    else map.merge(k, vals[i & 0xff], (a, b) -> vals[(int) (burn(burn) & 0xff)]);
                }
            }));
        }
        ts.forEach(Thread::start);
        long t0 = System.nanoTime();
        go.countDown();
        for (Thread t : ts) t.join(120_000);
        return (System.nanoTime() - t0) / 1_000_000;
    }

    /** Busy work whose result is used, so the compiler cannot delete it. Stands in for a loader inside the lock. */
    static long burn(int rounds) {
        long x = 1;
        for (int i = 1; i <= rounds; i++) x = x * 31 + i;
        return x;
    }

    /** Start N threads on the same job and wait for all of them. */
    static void runAll(int n, Runnable job) throws InterruptedException {
        Thread[] ts = new Thread[n];
        for (int i = 0; i < n; i++) ts[i] = new Thread(job);
        for (Thread t : ts) t.start();
        for (Thread t : ts) t.join(60_000);
    }
}
