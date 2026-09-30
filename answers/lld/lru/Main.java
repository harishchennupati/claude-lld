import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * Why a value left the cache. The callback fires for every exit, not only the capacity one, because a
 * write-back store has to be told about all four: CAPACITY (the cache was full), EXPIRED (its time ran out),
 * REPLACED (a new value overwrote it) and REMOVED (a caller asked).
 */
enum EvictionCause { CAPACITY, EXPIRED, REPLACED, REMOVED }

/** Where time comes from. Injected, so a TTL test can jump an hour forward without sleeping for an hour. */
interface Clock { long nowMs(); }

/**
 * Where a miss goes: a database read, an HTTP call, a computation. It is slow and it is allowed to throw,
 * which is exactly why the cache calls it with no lock held and writes nothing until it comes back.
 */
interface CacheLoader<K, V> {
    /** The value for this key, or null if the source does not have one. May throw; the cache is unchanged if it does. */
    V load(K key);
}

/**
 * Told after a value has left the cache. Called after the lock is released and inside a try/catch, so a slow
 * or broken listener can neither stall a cache operation nor leave the two indexes disagreeing. The price:
 * notices from two threads can arrive in either order, so a listener must not depend on arrival order.
 */
interface EvictionListener<K, V> {
    /** One value left, and why. Runs on the thread that caused it, with no cache lock held. */
    void onEvict(K key, V value, EvictionCause cause);
}

/**
 * The contract every cache in this file honours. This is the seam that makes "now evict the least-FREQUENTLY
 * used instead" a new class and one constructor line: a caller holds a Cache, never an LruCache.
 */
interface Cache<K, V> {
    /** The value, or null on a miss. A read counts as a use: it changes the eviction order. */
    V get(K key);
    /** Insert or overwrite; returns the value that was there, or null. May evict exactly one entry. */
    V put(K key, V value);
    /** Drop this key now; returns the value that was there, or null. */
    V remove(K key);
    /** How many entries are resident. Never more than capacity(). */
    int size();
    /** The fixed budget, in entries. */
    int capacity();
    /** The keys in the order this cache would evict them, next victim first. O(n); for tests and debugging. */
    List<K> evictionOrder();
}

/**
 * One entry, and one node of an order list, in the same object. The key rides INSIDE the node because
 * eviction starts from the order list and then has to delete that entry from the map: without the key in
 * hand that delete would be a scan of the whole map.
 */
final class Node<K, V> {
    final K key;                       // final: the identity of an entry never changes
    V value;
    Node<K, V> prev, next;             // the links of whichever list this node is currently in
    int freq = 1;                      // LFU only: how many times this entry has been used
    long expireAtMs;                   // 0 = never expires

    Node(K key, V value, long expireAtMs) { this.key = key; this.value = value; this.expireAtMs = expireAtMs; }
}

/**
 * A doubly linked list of nodes with two sentinels, so every splice is straight-line pointer writes with no
 * empty-list or single-element special case. Doubly linked because eviction must unlink a node found through
 * the map, from the middle, without walking to its predecessor. Front = newest, back = the next victim.
 */
final class RecencyList<K, V> {
    private final Node<K, V> head = new Node<>(null, null, 0);   // sentinel: nothing before the newest
    private final Node<K, V> tail = new Node<>(null, null, 0);   // sentinel: nothing after the oldest
    private int size;

    RecencyList() { head.next = tail; tail.prev = head; }

    /** Splice n in as the newest. O(1). */
    void addFirst(Node<K, V> n) {
        n.prev = head; n.next = head.next;
        head.next.prev = n; head.next = n;
        size++;
    }
    /** Splice n out from wherever it is. O(1), and it is the reason the list is doubly linked. */
    void unlink(Node<K, V> n) {
        n.prev.next = n.next; n.next.prev = n.prev;
        n.prev = null; n.next = null;
        size--;
    }
    /** "This entry was just used." Two splices, still O(1). */
    void moveToFirst(Node<K, V> n) { unlink(n); addFirst(n); }
    /** The oldest node: the one this list would give up next, or null if the list is empty. */
    Node<K, V> last() { return size == 0 ? null : tail.prev; }
    boolean isEmpty() { return size == 0; }
    int size() { return size; }

    /** The keys from newest to oldest. Walks the links, so it is the honest view of the order. */
    List<K> keysNewestFirst() {
        List<K> out = new ArrayList<>(size);
        for (Node<K, V> n = head.next; n != tail; n = n.next) out.add(n.key);
        return out;
    }
    /** The keys from oldest to newest: the order in which this list would give them up. */
    List<K> keysOldestFirst() {
        List<K> out = new ArrayList<>(size);
        for (Node<K, V> n = tail.prev; n != head; n = n.prev) out.add(n.key);
        return out;
    }
}

/**
 * Everything both caches share: the one lock, the three rules they are handed, and the discipline that the
 * slow things happen outside the lock. It holds state and helpers; it does not own the algorithm, so get and
 * put are written out in full in each cache and either one can be read on its own.
 */
abstract class LockedCache<K, V> implements Cache<K, V> {
    /** One lock per cache. Every operation mutates (a get reorders), so there are no pure readers to separate. */
    final ReentrantLock lock = new ReentrantLock();
    // volatile: a rule handed in by one thread is seen by the very next read on any other thread, even one
    // that reads it without taking the lock (load and fire run outside the lock)
    private volatile CacheLoader<K, V> loader = key -> null;               // default: a miss is just a miss
    private volatile EvictionListener<K, V> listener = (k, v, c) -> { };   // default: nobody is listening
    private volatile Clock clock = System::currentTimeMillis;
    private volatile long ttlMs = 0;                                       // 0 = entries never expire
    private volatile boolean restartOnRead = false;                        // true = expire after the last USE
    /** Keys being loaded right now, each with the ticket its load was given. Only touched with the lock held. */
    private final Map<K, Object> loading = new HashMap<>();

    /** Hand in the rules. The cache never builds them, which is why a test can hand in a loader that throws. */
    void configure(CacheLoader<K, V> loader, EvictionListener<K, V> listener) {
        this.loader = Objects.requireNonNull(loader);
        this.listener = Objects.requireNonNull(listener);
    }
    /** Tests hand in a fixed instant so a TTL can be crossed without waiting for it. */
    void setClock(Clock c) { this.clock = Objects.requireNonNull(c); }
    /** Expire-after-write, in milliseconds: the time runs from the last put. 0 turns expiry off. */
    void setTtlMs(long ttlMs) { setTtlMs(ttlMs, false); }
    /** restartOnRead = expire-after-ACCESS: every hit pushes the deadline out again, not only every put. */
    void setTtlMs(long ttlMs, boolean restartOnRead) { this.ttlMs = ttlMs; this.restartOnRead = restartOnRead; }

    /** The expiry stamp to put on an entry written now, or 0 when there is no TTL. */
    long stamp() { return ttlMs <= 0 ? 0 : clock.nowMs() + ttlMs; }
    /** Is this entry past its time? Checked lazily, on the read that finds it. */
    boolean expired(Node<K, V> n) { return n.expireAtMs > 0 && clock.nowMs() >= n.expireAtMs; }
    /** A hit. With expire-after-access its deadline moves; with expire-after-write it stays where the put left it. */
    void touched(Node<K, V> n) { if (restartOnRead) n.expireAtMs = stamp(); }
    /** The read-through loader. ALWAYS called with no lock held: it is milliseconds, the lock is nanoseconds. */
    V load(K key) { return loader.load(key); }
    /** Tell the listener. Only ever called after the lock has been released, and it swallows a broken listener. */
    void fire(K key, V value, EvictionCause cause) {
        try { listener.onEvict(key, value, cause); }
        catch (RuntimeException e) { /* a listener is a bystander: it cannot be allowed to break the cache */ }
    }

    // Tickets. A miss takes a ticket before it loads; a put or remove of that key tears the ticket up; the load
    // may write its value only if its ticket is still there when it comes back. Without this, a slow load could
    // overwrite a newer put, or bring back a key that was removed while it was loading.
    /** A miss is about to load this key. Call with the lock held. */
    Object startLoad(K key) { Object ticket = new Object(); loading.put(key, ticket); return ticket; }
    /** A put or remove of this key: any load already running for it is now out of date. Call with the lock held. */
    void cancelLoad(K key) { loading.remove(key); }
    /** The load came back: may it write? Only if nobody put or removed the key meanwhile. Call with the lock held. */
    boolean finishLoad(K key, Object ticket) { return loading.remove(key, ticket); }
    /** The load threw or found nothing: hand the ticket back, so the map of loads cannot grow for ever. */
    void abandonLoad(K key, Object ticket) { lock.lock(); try { loading.remove(key, ticket); } finally { lock.unlock(); } }
}

/**
 * The cache itself: a hash map from key to node, and one recency list over the very same nodes. The map
 * answers "the value for this key" in O(1) but has no order; the list has order but no lookup; pointing both
 * at one node object is the whole trick, and everything else on this page is bookkeeping.
 *
 * The invariant, in one line: the map and the list always name exactly the same keys, and there is never one
 * more entry than the capacity -- not even for an instant.
 */
final class LruCache<K, V> extends LockedCache<K, V> {
    private final int capacity;
    private final Map<K, Node<K, V>> index;                       // key -> the node that holds its value
    private final RecencyList<K, V> order = new RecencyList<>();  // the same nodes, newest at the front

    LruCache(int capacity) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity must be positive, not " + capacity);
        this.capacity = capacity;
        this.index = new HashMap<>(capacity * 2);                 // sized so a full cache never rehashes
    }

    /**
     * A hit moves the entry to the front, because a read is a use. A miss, or an entry whose time has run out,
     * takes a ticket and calls the loader with NO lock held. Only a value that came back is written, and only
     * if its ticket survived: a loader that throws or returns null leaves the cache exactly as it was, and a
     * put or remove that landed during the load is never undone by it.
     */
    public V get(K key) {
        Objects.requireNonNull(key, "null keys are not cached");
        K deadKey = null; V deadValue = null; Object ticket;
        lock.lock();
        try {
            Node<K, V> n = index.get(key);
            if (n != null && !expired(n)) { touched(n); order.moveToFirst(n); return n.value; }  // hot path: ~80 ns
            if (n != null) { drop(n); deadKey = n.key; deadValue = n.value; }                    // stale: it leaves now
            ticket = startLoad(key);             // a put or remove of this key while we load cancels it
        } finally { lock.unlock(); }

        if (deadKey != null) fire(deadKey, deadValue, EvictionCause.EXPIRED);
        V loaded = null;
        try { loaded = load(key); }              // outside the lock: milliseconds, and allowed to throw
        finally { if (loaded == null) abandonLoad(key, ticket); }
        if (loaded == null) return null;         // a miss stays a miss; nothing has been written
        write(key, loaded, ticket);              // written only if nobody put or removed this key meanwhile
        return loaded;
    }

    /**
     * Insert or overwrite. The order is the design: an existing key is ONE node overwritten in place, never a
     * second node; a new key into a full cache evicts the oldest FIRST and only then links the newcomer, so
     * size is never capacity + 1; and the listener hears about it after the lock, never inside it.
     */
    public V put(K key, V value) { return write(key, value, null); }

    /**
     * The one write path. A put (no ticket) cancels any load running for this key, because the put's value is
     * newer. A load coming back (with its ticket) writes only if the ticket is still there.
     */
    private V write(K key, V value, Object ticket) {
        Objects.requireNonNull(key, "null keys are not cached");
        Objects.requireNonNull(value, "null values are not cached: null is how a miss is reported");
        K evictedKey = null; V evictedValue = null, previous = null;
        lock.lock();
        try {
            if (ticket == null) cancelLoad(key);                  // this value is newer than any load in flight
            else if (!finishLoad(key, ticket)) return null;       // a put or remove got here first: it wins
            Node<K, V> n = index.get(key);
            if (n != null) {                                  // overwrite: one node, moved to the front
                previous = n.value;
                n.value = value; n.expireAtMs = stamp();
                order.moveToFirst(n);
            } else {
                if (index.size() >= capacity) {               // evict FIRST, so the cache is never over capacity
                    Node<K, V> victim = order.last();
                    drop(victim);
                    evictedKey = victim.key; evictedValue = victim.value;
                }
                Node<K, V> fresh = new Node<>(key, value, stamp());
                order.addFirst(fresh);                        // list and map are written in the same section:
                index.put(key, fresh);                        // nobody can observe one without the other
            }
        } finally { lock.unlock(); }

        if (evictedKey != null) fire(evictedKey, evictedValue, EvictionCause.CAPACITY);
        if (previous != null) fire(key, previous, EvictionCause.REPLACED);
        return previous;
    }

    /** Drop a key on request, e.g. because the row behind it changed. The listener hears REMOVED, after the lock. */
    public V remove(K key) {
        Objects.requireNonNull(key, "null keys are not cached");
        V gone = null;
        lock.lock();
        try {
            cancelLoad(key);                     // a load already running must not bring the old row back
            Node<K, V> n = index.get(key); if (n != null) { drop(n); gone = n.value; }
        } finally { lock.unlock(); }
        if (gone != null) fire(key, gone, EvictionCause.REMOVED);
        return gone;
    }

    public int size() { lock.lock(); try { return index.size(); } finally { lock.unlock(); } }
    public int capacity() { return capacity; }

    /**
     * Free expired entries now instead of on the next read. With expire-after-ACCESS every use restarts the
     * clock, so the least recently used entry is always the first to expire: pop from the tail until the tail
     * is fresh, O(1) per entry freed. With expire-after-write a read can move an old entry away from the tail,
     * so this frees only what sits at the tail, and ExpirySweeper (Extensions.java) is the tool for that case.
     */
    int sweepExpired() {
        List<Node<K, V>> dead = new ArrayList<>();
        lock.lock();
        try { for (Node<K, V> n = order.last(); n != null && expired(n); n = order.last()) { drop(n); dead.add(n); } }
        finally { lock.unlock(); }
        for (Node<K, V> n : dead) fire(n.key, n.value, EvictionCause.EXPIRED);
        return dead.size();
    }

    /** Drop this key only if its OWN deadline has passed. A sweeper's note is a hint; the node's stamp is the truth. */
    boolean expireIfDue(K key) {
        V gone = null;
        lock.lock();
        try { Node<K, V> n = index.get(key); if (n != null && expired(n)) { drop(n); gone = n.value; } }
        finally { lock.unlock(); }
        if (gone != null) fire(key, gone, EvictionCause.EXPIRED);
        return gone != null;
    }

    /** The keys the cache would give up, next victim first: the list read from the tail. */
    public List<K> evictionOrder() { lock.lock(); try { return order.keysOldestFirst(); } finally { lock.unlock(); } }
    /** Newest first: the same walk the other way round, which is how the demo prints the order. */
    List<K> keysNewestFirst() { lock.lock(); try { return order.keysNewestFirst(); } finally { lock.unlock(); } }

    /** Test hook: the two indexes must name exactly the same keys. If this is ever false, a splice went wrong. */
    boolean consistent() {
        lock.lock();
        try { return order.size() == index.size() && index.keySet().equals(new HashSet<>(order.keysNewestFirst())); }
        finally { lock.unlock(); }
    }

    /** Out of both indexes in one step. Only ever called with the lock held. */
    private void drop(Node<K, V> n) { index.remove(n.key); order.unlink(n); }
}

/**
 * The same cache with the other policy: evict the least-FREQUENTLY used. The recency list becomes one list
 * PER use-count, plus the smallest count currently in use, which keeps every operation O(1). Because each
 * bucket is itself a recency list, a tie between two entries used the same number of times is broken by
 * recency: of the entries used once, the one used longest ago leaves.
 */
final class LfuCache<K, V> extends LockedCache<K, V> {
    private final int capacity;
    private final Map<K, Node<K, V>> index;
    private final Map<Integer, RecencyList<K, V>> buckets = new HashMap<>();   // use-count -> its entries, newest first
    private int minFreq = 1;                              // the smallest use-count present; exact whenever the cache is full

    LfuCache(int capacity) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity must be positive, not " + capacity);
        this.capacity = capacity;
        this.index = new HashMap<>(capacity * 2);
    }

    /** A hit counts one more use and moves the entry up a bucket. Same read-through and ticket rule as LruCache. */
    public V get(K key) {
        Objects.requireNonNull(key, "null keys are not cached");
        K deadKey = null; V deadValue = null; Object ticket;
        lock.lock();
        try {
            Node<K, V> n = index.get(key);
            if (n != null && !expired(n)) { touched(n); bump(n); return n.value; }
            if (n != null) { drop(n); deadKey = n.key; deadValue = n.value; }
            ticket = startLoad(key);
        } finally { lock.unlock(); }

        if (deadKey != null) fire(deadKey, deadValue, EvictionCause.EXPIRED);
        V loaded = null;
        try { loaded = load(key); }
        finally { if (loaded == null) abandonLoad(key, ticket); }
        if (loaded == null) return null;
        write(key, loaded, ticket);
        return loaded;
    }

    /** Same order as the LRU cache: overwrite in place, or evict the least-used-then-oldest first and insert after. */
    public V put(K key, V value) { return write(key, value, null); }

    /** The one write path, with the same ticket rule as LruCache.write. */
    private V write(K key, V value, Object ticket) {
        Objects.requireNonNull(key, "null keys are not cached");
        Objects.requireNonNull(value, "null values are not cached: null is how a miss is reported");
        K evictedKey = null; V evictedValue = null, previous = null;
        lock.lock();
        try {
            if (ticket == null) cancelLoad(key);
            else if (!finishLoad(key, ticket)) return null;
            Node<K, V> n = index.get(key);
            if (n != null) {
                previous = n.value;
                n.value = value; n.expireAtMs = stamp();
                bump(n);
            } else {
                if (index.size() >= capacity) {
                    Node<K, V> victim = buckets.get(minFreq).last();   // least used, and of those, least recent
                    drop(victim);
                    evictedKey = victim.key; evictedValue = victim.value;
                }
                Node<K, V> fresh = new Node<>(key, value, stamp());
                index.put(key, fresh);
                buckets.computeIfAbsent(1, f -> new RecencyList<>()).addFirst(fresh);
                minFreq = 1;                                           // a newcomer has been used once
            }
        } finally { lock.unlock(); }

        if (evictedKey != null) fire(evictedKey, evictedValue, EvictionCause.CAPACITY);
        if (previous != null) fire(key, previous, EvictionCause.REPLACED);
        return previous;
    }

    public V remove(K key) {
        Objects.requireNonNull(key, "null keys are not cached");
        V gone = null;
        lock.lock();
        try { cancelLoad(key); Node<K, V> n = index.get(key); if (n != null) { drop(n); gone = n.value; } }
        finally { lock.unlock(); }
        if (gone != null) fire(key, gone, EvictionCause.REMOVED);
        return gone;
    }

    public int size() { lock.lock(); try { return index.size(); } finally { lock.unlock(); } }
    public int capacity() { return capacity; }

    /** Next victim first: the least-used bucket oldest-first, then each higher use-count in turn. */
    public List<K> evictionOrder() {
        lock.lock();
        try {
            List<Integer> freqs = new ArrayList<>(buckets.keySet());
            Collections.sort(freqs);
            List<K> out = new ArrayList<>(index.size());
            for (int f : freqs) out.addAll(buckets.get(f).keysOldestFirst());
            return out;
        } finally { lock.unlock(); }
    }

    /** How often this key has been used. Test and demo only. */
    int frequencyOf(K key) { lock.lock(); try { Node<K, V> n = index.get(key); return n == null ? 0 : n.freq; } finally { lock.unlock(); } }
    /**
     * Test hook: every node is in exactly one bucket, the buckets hold exactly the map's keys, and whenever the
     * cache is full (the only time minFreq is read) minFreq is the smallest use-count present.
     */
    boolean consistent() {
        lock.lock();
        try {
            Set<K> inBuckets = new HashSet<>();
            int count = 0;
            for (Map.Entry<Integer, RecencyList<K, V>> e : buckets.entrySet()) {
                if (e.getValue().isEmpty()) return false;              // an empty bucket must have been removed
                inBuckets.addAll(e.getValue().keysNewestFirst());
                count += e.getValue().size();
            }
            return count == index.size() && inBuckets.equals(index.keySet())
                && (index.size() < capacity || minFreq == Collections.min(buckets.keySet()));
        } finally { lock.unlock(); }
    }

    /** One more use: out of its bucket, into the next one up, and mind the smallest count. O(1). */
    private void bump(Node<K, V> n) {
        RecencyList<K, V> from = buckets.get(n.freq);
        from.unlink(n);
        if (from.isEmpty()) {
            buckets.remove(n.freq);
            if (minFreq == n.freq) minFreq = n.freq + 1;               // the only entry at the bottom just moved up
        }
        n.freq++;
        buckets.computeIfAbsent(n.freq, f -> new RecencyList<>()).addFirst(n);
    }

    /**
     * Out of the map and out of its bucket in one step. It never repairs minFreq, even when it empties the
     * smallest bucket, and that is what keeps remove and expiry O(1) too: minFreq is only read when the cache
     * is full, and a cache that has just lost an entry can only fill up again through an insert, which sets
     * minFreq back to 1.
     */
    private void drop(Node<K, V> n) {
        index.remove(n.key);
        RecencyList<K, V> b = buckets.get(n.freq);
        b.unlink(n);
        if (b.isEmpty()) buckets.remove(n.freq);
    }
}

/**
 * A listener that writes a value back to a store as it leaves the cache for good. Realistic in that it is
 * SLOW, which is the whole reason the cache calls it after releasing the lock.
 */
class WriteBackListener<K, V> implements EvictionListener<K, V> {
    private final Map<K, V> store;
    private final List<String> log = Collections.synchronizedList(new ArrayList<>());

    WriteBackListener(Map<K, V> store) { this.store = store; }

    /**
     * Only CAPACITY and EXPIRED are written back: that value is leaving for good. A REPLACED value is already
     * out of date (its newer value is still cached and is written when it leaves), and REMOVED was on purpose.
     */
    public void onEvict(K key, V value, EvictionCause cause) {
        if (cause == EvictionCause.CAPACITY || cause == EvictionCause.EXPIRED) store.put(key, value);
        log.add(cause + " " + key);
    }
    /** What this listener saw, in order. Demo and test only. */
    List<String> log() { return log; }
}

/** A demo of the whole thing: the order after a read, an eviction, read-through, TTL, LFU, and a race. */
public class Main {
    public static void main(String[] args) throws Exception {
        // ---------- 1. the order after a read, and who leaves when the cache is full
        Map<String, String> store = new HashMap<>();
        WriteBackListener<String, String> writeBack = new WriteBackListener<>(store);
        LruCache<String, String> cache = new LruCache<>(3);
        cache.configure(key -> null, writeBack);                // no loader yet: a miss is just a miss

        cache.put("A", "alpha"); cache.put("B", "bravo"); cache.put("C", "charlie");
        System.out.println("newest first after A B C: " + cache.keysNewestFirst());
        cache.get("A");                                          // a read is a use: A is no longer the oldest
        System.out.println("newest first after get(A): " + cache.keysNewestFirst());
        cache.put("D", "delta");                                 // full, so the oldest -- B -- leaves
        System.out.println("after put(D): " + cache.keysNewestFirst() + "  size=" + cache.size()
            + "  B is gone: " + (cache.get("B") == null) + "  written back: " + writeBack.log());

        // ---------- 2. an overwrite is ONE node, not a second
        cache.put("C", "charlie-2");
        System.out.println("after overwriting C: size=" + cache.size() + " value=" + cache.get("C")
            + " the key appears once: " + Collections.frequency(cache.keysNewestFirst(), "C"));

        // ---------- 3. read-through: a miss loads from the store, outside the lock, and only then writes
        Map<String, String> database = new HashMap<>(Map.of("x", "from-db-x", "y", "from-db-y"));
        int[] reads = { 0 };
        LruCache<String, String> readThrough = new LruCache<>(2);
        readThrough.configure(key -> { reads[0]++; return database.get(key); }, (k, v, c) -> { });
        System.out.println("read-through get(x) -> " + readThrough.get("x") + "  database reads=" + reads[0]);
        System.out.println("read-through get(x) -> " + readThrough.get("x") + "  database reads=" + reads[0] + " (a hit costs nothing)");
        System.out.println("get(zzz), which no store has -> " + readThrough.get("zzz") + "  size=" + readThrough.size());

        // ---------- 4. the loader's database is down: nothing is written, and a retry works
        LruCache<String, String> flaky = new LruCache<>(2);
        boolean[] down = { true };
        flaky.configure(key -> { if (down[0]) throw new IllegalStateException("database unreachable"); return "late-" + key; }, (k, v, c) -> { });
        try { flaky.get("k"); } catch (IllegalStateException e) { System.out.println("expected: " + e.getMessage() + "; size is still " + flaky.size()); }
        down[0] = false;
        System.out.println("after the database comes back, get(k) -> " + flaky.get("k") + "  size=" + flaky.size());

        // ---------- 5. TTL, on an injected clock: no sleeping
        long[] now = { 1_700_000_000_000L };
        List<String> expiries = new ArrayList<>();
        LruCache<String, String> ttl = new LruCache<>(10);
        ttl.setClock(() -> now[0]);
        ttl.setTtlMs(60_000);                                    // one minute after it was written
        ttl.configure(key -> null, (k, v, c) -> expiries.add(c + " " + k));
        ttl.put("session", "abc123");
        now[0] += 59_000;
        System.out.println("59s later: " + ttl.get("session"));
        now[0] += 2_000;
        System.out.println("61s later: " + ttl.get("session") + "  size=" + ttl.size() + "  listener saw " + expiries);

        // ---------- 6. the other policy: least-frequently used, ties broken by recency
        LfuCache<String, String> lfu = new LfuCache<>(3);
        lfu.put("hot", "1"); lfu.put("warm", "2"); lfu.put("cold", "3");
        lfu.get("hot"); lfu.get("hot"); lfu.get("warm");          // hot used 3x, warm 2x, cold 1x
        lfu.put("new", "4");                                     // cold is the least used: it leaves
        System.out.println("LFU after put(new): " + lfu.evictionOrder() + " (victim first)  cold gone: " + (lfu.get("cold") == null));
        LfuCache<String, String> tie = new LfuCache<>(2);
        tie.put("first", "1"); tie.put("second", "2");            // both used once
        tie.put("third", "3");                                   // the tie is broken by recency: first leaves
        System.out.println("LFU tie at frequency 1 -> " + tie.evictionOrder() + "  'first' gone: " + (tie.get("first") == null));

        // ---------- 7. the race: fifty threads, twenty thousand distinct keys, one capacity-100 cache
        final int threads = 50, perThread = 400, cap = 100;
        LruCache<String, String> hot = new LruCache<>(cap);
        AtomicInteger evicted = new AtomicInteger();
        hot.configure(key -> null, (k, v, c) -> { if (c == EvictionCause.CAPACITY) evicted.incrementAndGet(); });
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> running = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            final int id = t;
            running.add(pool.submit(() -> {
                go.await();
                for (int i = 0; i < perThread; i++) hot.put("t" + id + "-" + i, "v");
                return null;
            }));
        }
        go.countDown();
        for (Future<?> f : running) f.get();
        pool.shutdown();
        int inserted = threads * perThread, gone = evicted.get();
        System.out.println("race: inserted=" + inserted + " evicted=" + gone + " resident=" + hot.size()
            + "  evicted+resident=" + (gone + hot.size()) + " (must equal " + inserted + ")"
            + "  map and list agree: " + hot.consistent());
        if (gone + hot.size() != inserted || hot.size() != cap || !hot.consistent())
            throw new AssertionError("the cache lost or duplicated an entry under contention");
    }
}
