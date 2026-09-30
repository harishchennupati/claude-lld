import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;
import java.util.zip.CRC32;

// Reference code for every follow-up on page 05. Nothing here edits Main.java: each twist is a new class that
// either implements Cache, wraps a Cache, or is handed to a cache through configure().

// ---- ext: stats -- the hit rate, as a wrapper, without touching either cache
/**
 * "What is the hit ratio?" is not a change to the cache; it is another Cache that delegates and counts. It
 * composes with anything, because the seam it plugs into is the interface and not a class.
 *
 * One honest caveat: with a read-through loader a miss that the loader satisfies comes back non-null, so this
 * wrapper would call it a hit. Count the loader's calls (as ExtDemo does) when that distinction matters.
 */
final class StatsCache<K, V> implements Cache<K, V> {
    private final Cache<K, V> inner;
    private final AtomicLong hits = new AtomicLong(), misses = new AtomicLong(), writes = new AtomicLong();

    StatsCache(Cache<K, V> inner) { this.inner = inner; }

    public V get(K key) {
        V v = inner.get(key);
        if (v == null) misses.incrementAndGet(); else hits.incrementAndGet();
        return v;
    }
    public V put(K key, V value) { writes.incrementAndGet(); return inner.put(key, value); }
    public V remove(K key) { return inner.remove(key); }
    public int size() { return inner.size(); }
    public int capacity() { return inner.capacity(); }
    public List<K> evictionOrder() { return inner.evictionOrder(); }

    /** Hits over reads, 0 when nothing has been read yet. */
    double hitRate() { long h = hits.get(), m = misses.get(); return h + m == 0 ? 0 : (double) h / (h + m); }
    String summary() { return "hits=" + hits + " misses=" + misses + " writes=" + writes
        + " hitRate=" + String.format("%.2f", hitRate()); }
}

// ---- ext: the locking decorator -- what it buys, and the one thing it cannot do
/**
 * The textbook answer to "make it thread-safe": wrap it. It is correct, it is five lines, and it is what you
 * write when the class you were handed is not yours to change.
 *
 * What it costs, and why the caches in Main.java hold their own lock instead: everything the inner cache does
 * now happens inside this lock, including the read-through loader (milliseconds against a database) and the
 * eviction listener (a write-back to a store). Only the owner of the lock can release it and THEN call the
 * listener, so from outside you cannot keep the slow things out of the critical section.
 */
final class SynchronizedCache<K, V> implements Cache<K, V> {
    private final Cache<K, V> inner;
    SynchronizedCache(Cache<K, V> inner) { this.inner = inner; }

    public synchronized V get(K key) { return inner.get(key); }
    public synchronized V put(K key, V value) { return inner.put(key, value); }
    public synchronized V remove(K key) { return inner.remove(key); }
    public synchronized int size() { return inner.size(); }
    public int capacity() { return inner.capacity(); }
    public synchronized List<K> evictionOrder() { return inner.evictionOrder(); }
}

// ---- ext: bound by bytes -- a weight per entry, and a LOOP of evictions inside one lock
/**
 * "Bound it by memory, not by entry count." Capacity becomes a budget and each entry declares a weight, so a
 * single put can evict several entries -- or none, if what it replaced was bigger. The new invariant is "the
 * sum of the weights never exceeds the budget", and the whole loop runs inside ONE lock: either the budget
 * holds when the lock is released, or nothing was written at all.
 */
final class WeightedLruCache<K, V> extends LockedCache<K, V> {
    private final long maxWeight;
    private final ToLongFunction<V> weigher;
    private final Map<K, Node<K, V>> index = new HashMap<>();
    private final Map<K, Long> weights = new HashMap<>();
    private final RecencyList<K, V> order = new RecencyList<>();
    private long weight;

    WeightedLruCache(long maxWeight, ToLongFunction<V> weigher) { this.maxWeight = maxWeight; this.weigher = weigher; }

    public V get(K key) {
        lock.lock();
        try { Node<K, V> n = index.get(key); if (n == null) return null; order.moveToFirst(n); return n.value; }
        finally { lock.unlock(); }
    }

    public V put(K key, V value) {
        long w = weigher.applyAsLong(value);
        if (w < 0 || w > maxWeight) throw new IllegalArgumentException("weight " + w + " is outside 0.." + maxWeight);
        List<Node<K, V>> evicted = new ArrayList<>();
        V previous = null;
        lock.lock();
        try {
            Node<K, V> n = index.get(key);
            if (n != null) { previous = n.value; weight -= weights.get(key); n.value = value; order.moveToFirst(n); }
            else { n = new Node<>(key, value, stamp()); order.addFirst(n); index.put(key, n); }
            weights.put(key, w); weight += w;
            while (weight > maxWeight) {                      // a loop, not an if: one put can free several entries
                Node<K, V> victim = order.last();
                weight -= weights.remove(victim.key);
                index.remove(victim.key); order.unlink(victim);
                evicted.add(victim);
            }
        } finally { lock.unlock(); }
        for (Node<K, V> v : evicted) fire(v.key, v.value, EvictionCause.CAPACITY);
        return previous;
    }

    public V remove(K key) {
        V gone = null;
        lock.lock();
        try { Node<K, V> n = index.remove(key); if (n != null) { order.unlink(n); weight -= weights.remove(key); gone = n.value; } }
        finally { lock.unlock(); }
        if (gone != null) fire(key, gone, EvictionCause.REMOVED);
        return gone;
    }

    public int size() { lock.lock(); try { return index.size(); } finally { lock.unlock(); } }
    /** There is no entry cap here: the budget is the weight. Reported so the interface still means something. */
    public int capacity() { return (int) Math.min(maxWeight, Integer.MAX_VALUE); }
    public List<K> evictionOrder() { lock.lock(); try { return order.keysOldestFirst(); } finally { lock.unlock(); } }
    /** The bytes currently held. The whole point of this class. */
    long weight() { lock.lock(); try { return weight; } finally { lock.unlock(); } }
}

// ---- ext: striping -- N segments, N locks, approximate global LRU
/**
 * Rung two of the ladder. The keyspace is cut into independent segments by hash, each a whole little cache
 * with its own lock and its own order, so sixteen threads on sixteen different segments never meet.
 *
 * What you give up, and must say out loud: there is no longer one global recency order. A key can be evicted
 * from a crowded segment while an older key survives in a quiet one, so this is APPROXIMATE LRU -- exactly
 * the trade Guava's cache makes (its segments each limit their own size). Caffeine keeps one global order
 * instead and makes the READS approximate: it records them in small buffers and may drop some when busy.
 */
final class StripedCache<K, V> implements Cache<K, V> {
    private final LruCache<K, V>[] segments;

    @SuppressWarnings("unchecked")
    StripedCache(int capacity, int stripes) {
        this.segments = new LruCache[stripes];
        int each = Math.max(1, capacity / stripes);
        for (int i = 0; i < stripes; i++) segments[i] = new LruCache<>(each);
    }
    /** Every segment is handed the same rules. */
    void configure(CacheLoader<K, V> loader, EvictionListener<K, V> listener) {
        for (LruCache<K, V> s : segments) s.configure(loader, listener);
    }
    /** Spread the low bits, the way HashMap does, so keys that differ only in their high bits do not pile up. */
    private LruCache<K, V> segmentFor(K key) {
        int h = key.hashCode(); h ^= (h >>> 16);
        return segments[Math.floorMod(h, segments.length)];
    }
    public V get(K key) { return segmentFor(key).get(key); }
    public V put(K key, V value) { return segmentFor(key).put(key, value); }
    public V remove(K key) { return segmentFor(key).remove(key); }
    public int size() { int n = 0; for (LruCache<K, V> s : segments) n += s.size(); return n; }
    public int capacity() { int n = 0; for (LruCache<K, V> s : segments) n += s.capacity(); return n; }
    /** Segment by segment. There is deliberately no global order to report. */
    public List<K> evictionOrder() {
        List<K> out = new ArrayList<>();
        for (LruCache<K, V> s : segments) out.addAll(s.evictionOrder());
        return out;
    }
}

// ---- ext: the stampede -- a thousand threads miss the same cold key; collapse them into one database read
/**
 * A cold key that a thousand threads want at the same instant is a thousand database reads, because the
 * loader runs outside the lock on purpose. The fix is not to move it back inside: it is to make the LOADER
 * collapse duplicate work, so the first caller for a key does the read and everybody else waits on its result.
 * A CacheLoader wrapping a CacheLoader -- the same Decorator seam, one level down.
 */
final class SingleFlightLoader<K, V> implements CacheLoader<K, V> {
    private final CacheLoader<K, V> real;
    private final ConcurrentMap<K, FutureTask<V>> inFlight = new ConcurrentHashMap<>();
    private final AtomicInteger calls = new AtomicInteger();

    SingleFlightLoader(CacheLoader<K, V> real) { this.real = real; }

    public V load(K key) {
        FutureTask<V> mine = new FutureTask<>(() -> { calls.incrementAndGet(); return real.load(key); });
        FutureTask<V> running = inFlight.putIfAbsent(key, mine);
        if (running == null) { running = mine; mine.run(); }       // I am the one who does the work
        try { return running.get(); }                              // everybody else just waits for it
        catch (ExecutionException e) {
            Throwable cause = e.getCause();
            throw cause instanceof RuntimeException r ? r : new RuntimeException(cause);
        } catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new RuntimeException(e); }
        finally { inFlight.remove(key, mine); }                    // only the owner clears the slot
    }
    /** How many real loads happened. A thousand concurrent misses on one key should leave this at 1. */
    int realLoads() { return calls.get(); }
}

// ---- ext: the sweeper -- proactive expiry, and why lazy is usually enough
/**
 * Lazy expiry only frees an entry when somebody reads it, so a key that nobody ever asks for again holds its
 * memory until the capacity pushes it out. A sweeper is a second index ordered by expiry -- here a heap, in a
 * real system a timing wheel (a ring of time slots, each holding the keys due in it) -- that a background
 * tick drains. It is needed when entries can have DIFFERENT deadlines; with one fixed TTL a list in the right
 * order is enough (LruCache.sweepExpired for expire-after-access, the write-order list further down).
 *
 * The heap is only a hint about what to look at. A key written twice has two notes in it, and the older note
 * comes due while the newer value is still fresh, so the sweep asks the cache to drop the key only if the
 * node's own deadline has passed.
 */
final class ExpirySweeper<K, V> {
    /** One "look at this key at this time" note. */
    record Due<K>(long atMs, K key) { }

    private final LruCache<K, V> cache;
    private final PriorityQueue<Due<K>> heap = new PriorityQueue<>(Comparator.comparingLong(Due::atMs));

    ExpirySweeper(LruCache<K, V> cache) { this.cache = cache; }

    /** Called by whoever wrote the entry, with the same instant the cache stamped on it. */
    synchronized void track(K key, long expireAtMs) { heap.add(new Due<>(expireAtMs, key)); }
    /** One tick: look at every note due by now. O(k log n) for k notes due, not O(size). Returns how many left. */
    int sweep(long nowMs) {
        List<K> due = new ArrayList<>();
        synchronized (this) { while (!heap.isEmpty() && heap.peek().atMs() <= nowMs) due.add(heap.poll().key()); }
        int swept = 0;
        for (K key : due) if (cache.expireIfDue(key)) swept++;     // outside this lock: the listener may be slow
        return swept;                                               // a fresh rewrite stays; a real expiry fires EXPIRED
    }
}

// ---- ext: write-behind -- a bounded queue, one writer thread, and a named overflow policy
/**
 * A write-back listener that talks to the store on the caller's thread makes every eviction as slow as the
 * store. Write-behind hands the value to a bounded queue instead and one writer thread drains it.
 *
 * The two things to say out loud: the queue is BOUNDED, so there is an overflow policy (this one drops and
 * counts, which is honest; blocking and discard-oldest are the other two); and a process that dies with a
 * full queue loses those writes, which is the trade you are making in exchange for the latency.
 */
final class WriteBehindListener<K, V> implements EvictionListener<K, V>, AutoCloseable {
    /** One pending write. */
    record Pending<K, V>(K key, V value) { }

    private final BlockingQueue<Pending<K, V>> queue;
    private final Map<K, V> store;
    private final AtomicInteger dropped = new AtomicInteger();
    private final Thread writer;
    private volatile boolean running = true;

    WriteBehindListener(Map<K, V> store, int queueDepth) {
        this.store = store;
        this.queue = new ArrayBlockingQueue<>(queueDepth);
        this.writer = new Thread(() -> {
            while (running || !queue.isEmpty()) {
                try {
                    Pending<K, V> p = queue.poll(10, TimeUnit.MILLISECONDS);
                    if (p != null) store.put(p.key(), p.value());
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
            }
        }, "write-behind");
        writer.setDaemon(true);
        writer.start();
    }

    public void onEvict(K key, V value, EvictionCause cause) {
        // only a value leaving for good: REPLACED is out of date, REMOVED was asked for and must not come back
        if (cause != EvictionCause.CAPACITY && cause != EvictionCause.EXPIRED) return;
        if (!queue.offer(new Pending<>(key, value))) dropped.incrementAndGet();
    }
    /** How many writes the overflow policy threw away. A metric ops will ask for. */
    int dropped() { return dropped.get(); }
    /** Stop accepting, drain what is queued, join the writer. A crash instead of a close loses the queue. */
    public void close() throws InterruptedException { running = false; writer.join(2000); }
}

// ---- ext: two tiers -- memory, then a shared store, and the invalidation message
/** The far tier: a shared store (Redis, a table) that outlives this process. */
interface CacheStore<K, V> {
    /** The stored value, or null. */
    V read(K key);
    /** Write only if this version is newer than what is stored. Returns true if this write won. */
    boolean write(K key, V value, long version);
}

/**
 * A store whose write is a conditional update, which is the database's version of the cache's lock: two
 * servers writing the same key at once do not have to coordinate, because the older version simply loses.
 */
final class VersionedStore<K, V> implements CacheStore<K, V> {
    private final ConcurrentMap<K, Object[]> rows = new ConcurrentHashMap<>();   // key -> { version, value }

    @SuppressWarnings("unchecked")
    public V read(K key) { Object[] row = rows.get(key); return row == null ? null : (V) row[1]; }

    public boolean write(K key, V value, long version) {
        Object[] mine = { version, value };
        Object[] winner = rows.merge(key, mine,
            (old, fresh) -> (Long) fresh[0] > (Long) old[0] ? fresh : old);      // UPDATE ... WHERE version < ?
        return winner == mine;                                                  // did MY row end up stored?
    }
}

/**
 * Memory in front of the shared store. A local miss falls through to the store because the store IS the
 * loader. A write goes to the store FIRST, then this server DROPS its local copy instead of updating it, so
 * the next read loads whichever write won in the store. Updating the copy instead could leave this server
 * serving a value the store refused. The versions come from ONE source every server shares (a database
 * sequence, Redis INCR): with a counter per server, a quiet server's newer write would lose to a busy
 * server's older one.
 */
final class TwoTierCache<K, V> implements Cache<K, V> {
    private final LruCache<K, V> memory;
    private final CacheStore<K, V> far;
    private final LongSupplier versions;

    TwoTierCache(LruCache<K, V> memory, CacheStore<K, V> far, LongSupplier versions) {
        this.memory = memory; this.far = far; this.versions = versions;
        memory.configure(far::read, (k, v, c) -> { });               // read-through to the far tier
    }
    public V get(K key) { return memory.get(key); }
    public V put(K key, V value) {
        far.write(key, value, versions.getAsLong());                 // the irreversible step first
        return memory.remove(key);                                   // then drop the local copy (and any load of it)
    }
    public V remove(K key) { return memory.remove(key); }
    public int size() { return memory.size(); }
    public int capacity() { return memory.capacity(); }
    public List<K> evictionOrder() { return memory.evictionOrder(); }
    /** What another server publishes after it writes: this server's copy of that key is now wrong. */
    void onInvalidation(K key) { memory.remove(key); }
}

// ---- ext: the builder -- the one problem where a Builder genuinely earns its place
/**
 * On most LLD problems a Builder is ceremony. Here it is the real-world answer, and Guava's CacheBuilder and
 * Caffeine's Caffeine.newBuilder() are exactly this class: capacity, TTL, policy, loader, listener, clock and
 * stats are seven knobs of which six are optional, and a seven-argument constructor of mostly nulls is worse
 * than a chain of named calls. That is the rule -- a builder earns its place when the optional fields do.
 */
final class CacheBuilder<K, V> {
    private int capacity = 1_000;
    private long ttlMs = 0;
    private boolean lfu = false, stats = false, afterAccess = false;
    private CacheLoader<K, V> loader = key -> null;
    private EvictionListener<K, V> listener = (k, v, c) -> { };
    private Clock clock = System::currentTimeMillis;

    static <K, V> CacheBuilder<K, V> newBuilder() { return new CacheBuilder<>(); }

    CacheBuilder<K, V> maximumSize(int entries) { this.capacity = entries; return this; }
    CacheBuilder<K, V> expireAfterWrite(long ms) { this.ttlMs = ms; this.afterAccess = false; return this; }
    CacheBuilder<K, V> expireAfterAccess(long ms) { this.ttlMs = ms; this.afterAccess = true; return this; }
    CacheBuilder<K, V> leastFrequentlyUsed() { this.lfu = true; return this; }
    CacheBuilder<K, V> recordStats() { this.stats = true; return this; }
    CacheBuilder<K, V> loader(CacheLoader<K, V> l) { this.loader = l; return this; }
    CacheBuilder<K, V> evictionListener(EvictionListener<K, V> l) { this.listener = l; return this; }
    CacheBuilder<K, V> clock(Clock c) { this.clock = c; return this; }

    /** Assemble the core and its wrappers. This method is also the Factory: the policy name picks the class. */
    Cache<K, V> build() {
        LockedCache<K, V> core = lfu ? new LfuCache<>(capacity) : new LruCache<>(capacity);
        core.setClock(clock);
        core.setTtlMs(ttlMs, afterAccess);
        core.configure(loader, listener);
        return stats ? new StatsCache<>(core) : core;
    }
}

// ---- ext: the five-line version -- LinkedHashMap(accessOrder = true), and when it is enough
/**
 * The JDK has shipped an LRU cache since 1.4: a LinkedHashMap built in access order keeps exactly the same
 * map-plus-doubly-linked-list, and removeEldestEntry is the eviction hook.
 *
 * When it is enough: a single-threaded or coarsely synchronized cache with no TTL and no intention of
 * changing the policy. When it is not: there is no per-entry expiry; the only victim it can offer is the
 * eldest, so LFU is out; it is not thread-safe, and in access order even get() rearranges the list, so every
 * read needs the exclusive lock too; and the eviction hook runs inside put, so a listener called from it runs
 * inside that lock. The moment the interviewer says "now make it LFU" you are back to writing the nodes out.
 */
final class LinkedHashMapCache<K, V> implements Cache<K, V> {
    /** Access order plus the eviction hook: this is the whole LRU policy, in the JDK. */
    private static final class AccessOrdered<K, V> extends LinkedHashMap<K, V> {
        private final int cap;
        AccessOrdered(int cap) { super(cap * 2, 0.75f, true); this.cap = cap; }
        @Override protected boolean removeEldestEntry(Map.Entry<K, V> eldest) { return size() > cap; }
    }
    private final int capacity;
    private final AccessOrdered<K, V> map;

    LinkedHashMapCache(int capacity) { this.capacity = capacity; this.map = new AccessOrdered<>(capacity); }

    public synchronized V get(K key) { return map.get(key); }
    public synchronized V put(K key, V value) { return map.put(key, value); }
    public synchronized V remove(K key) { return map.remove(key); }
    public synchronized int size() { return map.size(); }
    public int capacity() { return capacity; }
    /** LinkedHashMap iterates oldest first in access order, which is already the eviction order. */
    public synchronized List<K> evictionOrder() { return new ArrayList<>(map.keySet()); }
}

// ---- ext: admission -- a scan must not be allowed to evict the working set (TinyLFU / Caffeine)
/**
 * How often has this key been ASKED FOR? Answered in a fixed amount of memory, whatever the key space.
 *
 * The structure is a Count-Min sketch with small saturating counters: every key hashes to four counters, an
 * increment bumps all four, and the estimate is the SMALLEST of the four, because collisions can only push a
 * count up. Counters stop at fifteen, so "very popular" and "popular" are the same answer and that is fine.
 * Every so often all the counters are halved, which is what makes the count a RECENT frequency rather than a
 * record of all time: yesterday's hot key decays instead of holding its place for ever.
 *
 * One byte per counter here, for readability; Caffeine packs sixteen four-bit counters into one long and
 * allocates one long per entry of capacity, so a cache of a hundred thousand entries spends about a megabyte
 * on it. Not thread-safe on its own: AdmissionLruCache only touches it with its lock held.
 */
final class FrequencySketch<K> {
    private static final int[] SEEDS = { 0x7f4a7c15, 0x9e3779b1, 0xc2b2ae35, 0x27d4eb2f };
    private final byte[] counters;      // one saturating 0..15 counter each; length is a power of two
    private final int mask;
    private final int sampleSize;       // halve everything after this many increments
    private int additions;

    /** Four counters per expected entry keeps the collision rate low enough for the comparison to be useful. */
    FrequencySketch(int expectedEntries) {
        int n = 16;
        while (n < Math.max(4, expectedEntries) * 4) n <<= 1;
        this.counters = new byte[n];
        this.mask = n - 1;
        this.sampleSize = 10 * Math.max(1, expectedEntries);
    }

    /** This key was asked for. O(1): four bumps, and a halving every sampleSize requests. */
    void increment(K key) {
        int h = spread(key.hashCode());
        for (int i = 0; i < SEEDS.length; i++) {
            int j = slot(h, i);
            if (counters[j] < 15) counters[j]++;
        }
        if (++additions >= sampleSize) halve();
    }

    /** The estimate: the smallest of this key's four counters, so a collision can never make a key look rarer. */
    int frequency(K key) {
        int h = spread(key.hashCode()), min = 15;
        for (int i = 0; i < SEEDS.length; i++) min = Math.min(min, counters[slot(h, i)]);
        return min;
    }

    /** Which counter this key uses for hash function i. Four different seeds give four independent-ish slots. */
    private int slot(int hash, int i) { int h = hash * SEEDS[i]; return (h ^ (h >>> 17)) & mask; }
    /** Mix the high bits down, the way HashMap does, so keys differing only up there do not collide. */
    private static int spread(int h) { return h ^ (h >>> 16); }
    /** Halve every counter. The whole history fades by half; nothing is ever hot for ever. */
    private void halve() {
        for (int i = 0; i < counters.length; i++) counters[i] = (byte) ((counters[i] & 0xFF) >>> 1);
        additions = 0;
    }
}

/**
 * The same LRU cache with a door on it. A nightly report that reads a million rows once is, to plain LRU, a
 * million most-recently-used entries: it pushes out the whole working set and the morning hit rate is zero.
 * Nothing about the EVICTION rule fixes that, because by the time a scan key is the victim it has already
 * thrown somebody out. The fix is an ADMISSION rule.
 *
 * On a full cache the newcomer is compared with the entry it would displace: it is let in only if the sketch
 * says it has been asked for MORE often than the victim. Ties go to the incumbent, which has already proved
 * itself, so a key seen once can never displace a key seen five times. A rejected newcomer is reported to the
 * listener immediately, because it did leave -- it just never got a place first.
 *
 * The known weakness, worth saying out loud: a genuinely new hot key is also seen once, so it is also refused.
 * Caffeine fixes that with the W in W-TinyLFU -- a small LRU window (1% of the cache to start with; Caffeine
 * tunes it as it runs) that every newcomer enters first, so only the window's own victim ever faces the door,
 * by which time a real hot key has built up a count. W-TinyLFU is the policy inside Caffeine, the successor
 * that Guava's own documentation points to.
 */
final class AdmissionLruCache<K, V> extends LockedCache<K, V> {
    private final int capacity;
    private final Map<K, Node<K, V>> index;
    private final RecencyList<K, V> order = new RecencyList<>();
    private final FrequencySketch<K> sketch;
    private long admitted, refused;

    AdmissionLruCache(int capacity) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity must be positive, not " + capacity);
        this.capacity = capacity;
        this.index = new HashMap<>(capacity * 2);
        this.sketch = new FrequencySketch<>(capacity);
    }

    /** Every request counts towards the frequency, hit or miss: that is how a scan key stays at one. */
    public V get(K key) {
        Objects.requireNonNull(key, "null keys are not cached");
        Object ticket;
        lock.lock();
        try {
            sketch.increment(key);                             // under the lock: the sketch is plain arrays
            Node<K, V> n = index.get(key);
            if (n != null && !expired(n)) { touched(n); order.moveToFirst(n); return n.value; }
            if (n != null) { index.remove(n.key); order.unlink(n); }
            ticket = startLoad(key);
        } finally { lock.unlock(); }
        V loaded = null;
        try { loaded = load(key); }
        finally { if (loaded == null) abandonLoad(key, ticket); }
        if (loaded == null) return null;
        write(key, loaded, ticket);
        return loaded;
    }

    /** The only difference from LruCache: on a full cache the newcomer must beat the victim to get in. */
    public V put(K key, V value) { return write(key, value, null); }

    /** LruCache's write path, ticket rule included, with the door added. */
    private V write(K key, V value, Object ticket) {
        Objects.requireNonNull(key, "null keys are not cached");
        Objects.requireNonNull(value, "null values are not cached");
        K goneKey = null; V goneValue = null, previous = null;
        lock.lock();
        try {
            if (ticket == null) { cancelLoad(key); sketch.increment(key); }   // a load was counted by its get
            else if (!finishLoad(key, ticket)) return null;
            Node<K, V> n = index.get(key);
            if (n != null) {                                   // an overwrite never faces the door
                previous = n.value; n.value = value; n.expireAtMs = stamp();
                order.moveToFirst(n);
            } else if (index.size() >= capacity) {
                Node<K, V> victim = order.last();
                if (sketch.frequency(key) > sketch.frequency(victim.key)) {
                    index.remove(victim.key); order.unlink(victim);   // the newcomer earned the place
                    goneKey = victim.key; goneValue = victim.value;
                    link(key, value); admitted++;
                } else {
                    goneKey = key; goneValue = value; refused++;      // the door stays shut; nothing moves
                }
            } else link(key, value);
        } finally { lock.unlock(); }

        if (goneKey != null) fire(goneKey, goneValue, EvictionCause.CAPACITY);
        if (previous != null) fire(key, previous, EvictionCause.REPLACED);
        return previous;
    }

    public V remove(K key) {
        Objects.requireNonNull(key, "null keys are not cached");
        V gone = null;
        lock.lock();
        try { cancelLoad(key); Node<K, V> n = index.get(key); if (n != null) { index.remove(key); order.unlink(n); gone = n.value; } }
        finally { lock.unlock(); }
        if (gone != null) fire(key, gone, EvictionCause.REMOVED);
        return gone;
    }

    public int size() { lock.lock(); try { return index.size(); } finally { lock.unlock(); } }
    public int capacity() { return capacity; }
    public List<K> evictionOrder() { lock.lock(); try { return order.keysOldestFirst(); } finally { lock.unlock(); } }
    /** How many newcomers were let in, and how many the door refused. Demo and test only. */
    String doorLog() { return "admitted=" + admitted + " refused=" + refused; }

    private void link(K key, V value) {
        Node<K, V> fresh = new Node<>(key, value, stamp());
        order.addFirst(fresh);
        index.put(key, fresh);
    }
}

// ---- ext: pluggable policy -- a store plus an eviction policy, both chosen when the cache is built
/**
 * The shape Flipkart-style machine-coding prompts ask for: "users pick the store and the eviction policy when
 * they create the cache". The policy is split off from the values: it only hears which keys were used and
 * answers which key should leave next. The price is a second index (the policy keeps its own key-to-node
 * map); the gain is one cache class that serves every policy.
 */
interface EvictionPolicy<K> {
    /** This key was just read or written. */
    void keyUsed(K key);
    /** This key has left the store: forget it. */
    void keyRemoved(K key);
    /** The key that should leave next, or null if there is none. It stays until keyRemoved is called. */
    K victim();
}

/** LRU and FIFO are the same list. The only difference: does a repeat use move the key to the front? */
final class ListPolicy<K> implements EvictionPolicy<K> {
    /** A repeat use moves the key to the front: least recently used leaves first. */
    static <K> ListPolicy<K> lru() { return new ListPolicy<>(true); }
    /** A repeat use moves nothing: the first key in is the first out. */
    static <K> ListPolicy<K> fifo() { return new ListPolicy<>(false); }

    private final boolean moveOnUse;
    private final Map<K, Node<K, Void>> nodes = new HashMap<>();
    private final RecencyList<K, Void> order = new RecencyList<>();

    private ListPolicy(boolean moveOnUse) { this.moveOnUse = moveOnUse; }

    public void keyUsed(K key) {
        Node<K, Void> n = nodes.get(key);
        if (n == null) { n = new Node<>(key, null, 0); nodes.put(key, n); order.addFirst(n); }
        else if (moveOnUse) order.moveToFirst(n);                // LRU moves it; FIFO leaves it where it arrived
    }
    public void keyRemoved(K key) { Node<K, Void> n = nodes.remove(key); if (n != null) order.unlink(n); }
    public K victim() { Node<K, Void> n = order.last(); return n == null ? null : n.key; }
}

/**
 * The cache that prompt describes: a store (any Map) and an EvictionPolicy handed in at construction, under
 * one lock. LFU plugs in the same way: its policy is LfuCache's buckets with the values taken out.
 */
final class PolicyCache<K, V> {
    private final int capacity;
    private final Map<K, V> store;
    private final EvictionPolicy<K> policy;
    private final ReentrantLock lock = new ReentrantLock();

    PolicyCache(int capacity, Map<K, V> store, EvictionPolicy<K> policy) {
        if (capacity <= 0) throw new IllegalArgumentException("capacity must be positive, not " + capacity);
        this.capacity = capacity; this.store = store; this.policy = policy;
    }
    /** The value or null. A hit is reported to the policy, which decides whether a read changes anything. */
    V get(K key) {
        lock.lock();
        try { V v = store.get(key); if (v != null) policy.keyUsed(key); return v; }
        finally { lock.unlock(); }
    }
    /** Insert or overwrite. A new key into a full cache first evicts the policy's victim. */
    V put(K key, V value) {
        lock.lock();
        try {
            if (!store.containsKey(key) && store.size() >= capacity) {
                K out = policy.victim();
                store.remove(out); policy.keyRemoved(out);
            }
            V previous = store.put(key, value);
            policy.keyUsed(key);
            return previous;
        } finally { lock.unlock(); }
    }
    /** Drop a key from the store and from the policy, in the same step. */
    V remove(K key) {
        lock.lock();
        try { V v = store.remove(key); if (v != null) policy.keyRemoved(key); return v; }
        finally { lock.unlock(); }
    }
    /** How many entries the store holds. */
    int size() { lock.lock(); try { return store.size(); } finally { lock.unlock(); } }
}

// ---- ext: multi-level -- L1..Ln, each with its own capacity, read time and write time
/**
 * N levels, fastest first, each a whole LruCache with a read cost and a write cost. A read walks down until
 * a level has the key, then copies the value into every faster level above it. A write goes down from L1 and
 * stops at the first level that already holds the same value (the prompt's rule). Each call returns the time
 * it would take: every read it tried plus every write it made. stats() prints each level's usage and the
 * average read and write time over the last few calls.
 */
final class MultiLevelCache<K, V> {
    /** One level: its cache, and what one read or one write at this level costs. */
    record Level<K, V>(String name, LruCache<K, V> cache, int readMs, int writeMs) { }
    /** What a read returns: the value (or null) and the time it took. */
    record Read<V>(V value, int ms) { }

    private final List<Level<K, V>> levels;
    private final int window;                                        // stats average over the last `window` calls
    private final Deque<Integer> reads = new ArrayDeque<>(), writes = new ArrayDeque<>();
    private final ReentrantLock lock = new ReentrantLock();          // one lock over all levels: a read also writes

    MultiLevelCache(List<Level<K, V>> levels, int window) { this.levels = List.copyOf(levels); this.window = window; }

    /** Walk down; on a hit at level i, copy the value into levels 0..i-1. */
    Read<V> read(K key) {
        lock.lock();
        try {
            int ms = 0, hit = -1; V value = null;
            for (int i = 0; i < levels.size() && value == null; i++) {
                ms += levels.get(i).readMs();
                value = levels.get(i).cache().get(key);
                if (value != null) hit = i;
            }
            for (int i = 0; i < hit; i++) { ms += levels.get(i).writeMs(); levels.get(i).cache().put(key, value); }
            remember(reads, ms);
            return new Read<>(value, ms);
        } finally { lock.unlock(); }
    }

    /** Write down from L1; stop at the first level that already has this exact value. */
    int write(K key, V value) {
        lock.lock();
        try {
            int ms = 0;
            for (Level<K, V> l : levels) {
                ms += l.readMs();
                if (value.equals(l.cache().get(key))) break;         // already here: the prompt says stop
                ms += l.writeMs();
                l.cache().put(key, value);
            }
            remember(writes, ms);
            return ms;
        } finally { lock.unlock(); }
    }

    /** Each level's filled/total, then the average read and write time over the last `window` calls. */
    String stats() {
        lock.lock();
        try {
            StringBuilder s = new StringBuilder();
            for (Level<K, V> l : levels) s.append(l.name()).append(' ').append(l.cache().size()).append('/').append(l.cache().capacity()).append("  ");
            return s + "avgRead=" + average(reads) + "ms  avgWrite=" + average(writes) + "ms";
        } finally { lock.unlock(); }
    }

    /** Keep the last `window` timings, oldest dropped first. */
    private void remember(Deque<Integer> last, int ms) { last.addLast(ms); if (last.size() > window) last.removeFirst(); }
    /** The mean of the kept timings, 0 before the first call. */
    private static double average(Deque<Integer> last) { return last.stream().mapToInt(Integer::intValue).average().orElse(0); }
}

// ---- ext: write-order expiry -- one fixed lifetime, and the average of the live values in O(1)
/**
 * Every value lives a fixed time after it was WRITTEN, and average() must be O(1). With one fixed lifetime,
 * entries expire in the order they were written, so keep them in a list in write order (a read moves
 * nothing) plus a running sum. Every call first pops expired entries off the old end and subtracts them.
 * Each entry is popped at most once, so that cleanup is O(1) amortized (averaged over all the calls).
 */
final class ExpiringAverageCache<K> {
    private final Map<K, Node<K, Long>> index = new HashMap<>();
    private final RecencyList<K, Long> byWriteTime = new RecencyList<>();   // newest write at the front
    private final long lifeMs;
    private final Clock clock;
    private final ReentrantLock lock = new ReentrantLock();
    private long sum;                                                       // of the live values: a long, so exact

    ExpiringAverageCache(long lifeMs, Clock clock) { this.lifeMs = lifeMs; this.clock = clock; }

    /** Insert or overwrite. An overwrite takes the old value out of the sum and restarts the lifetime. */
    void put(K key, long value) {
        lock.lock();
        try {
            expire();
            Node<K, Long> old = index.remove(key);
            if (old != null) { byWriteTime.unlink(old); sum -= old.value; }
            Node<K, Long> n = new Node<>(key, value, clock.nowMs() + lifeMs);
            byWriteTime.addFirst(n); index.put(key, n); sum += value;
        } finally { lock.unlock(); }
    }
    /** The live value, or null. A read moves nothing: the lifetime runs from the write. */
    Long get(K key) {
        lock.lock();
        try { expire(); Node<K, Long> n = index.get(key); return n == null ? null : n.value; }
        finally { lock.unlock(); }
    }
    /** The mean of the live values, 0 when there are none. */
    double average() {
        lock.lock();
        try { expire(); return index.isEmpty() ? 0 : (double) sum / index.size(); }
        finally { lock.unlock(); }
    }
    /** Pop from the old end while the oldest write has expired. */
    private void expire() {
        long now = clock.nowMs();
        for (Node<K, Long> n = byWriteTime.last(); n != null && now >= n.expireAtMs; n = byWriteTime.last()) {
            byWriteTime.unlink(n); index.remove(n.key); sum -= n.value;
        }
    }
}

// ---- ext: memo + log -- an LRU memo in front of a function, a key that is really equal, then a crash-proof log
/**
 * The key a memo cache files a call under. Equal calls must give equal keys. Positional arguments compare by
 * CONTENT through Arrays.deepEquals: an array's own equals only asks "same object?", so f(new int[]{1}) called
 * twice would miss every time. Named arguments sit in a TreeMap, sorted by name, so f(a=1, b=2) and
 * f(b=2, a=1) are one key. The argument array is copied; an argument that is itself mutable must not change
 * while it is a key, because a HashMap cannot find a key whose hash has changed.
 */
record CallKey(String fn, Object[] args, SortedMap<String, Object> named) {
    CallKey { args = args.clone(); named = new TreeMap<>(named); }
    @Override public boolean equals(Object o) {
        return o instanceof CallKey k && fn.equals(k.fn) && Arrays.deepEquals(args, k.args) && named.equals(k.named);
    }
    @Override public int hashCode() { return Objects.hash(fn, Arrays.deepHashCode(args), named); }
}

/** An LRU memo in front of one function: the function is the loader, so tickets and eviction come for free. */
final class MemoCache<V> {
    private final LruCache<CallKey, V> cache;

    MemoCache(int capacity, CacheLoader<CallKey, V> function) {
        cache = new LruCache<>(capacity);
        cache.configure(function, (k, v, c) -> { });
    }

    /** The answer for this call: computed once, then served from the cache until it is evicted. */
    V call(String fn, Object[] args, Map<String, Object> named) { return cache.get(new CallKey(fn, args, new TreeMap<>(named))); }
}

/**
 * An LRU cache that survives a crash. Every change is appended to a log file BEFORE the cache changes (a
 * write-ahead log): die after the append and the restart replays it; die before and it never happened. A
 * restart replays the log through the same LRU rules, which rebuilds the entries AND their recency order.
 * A put is forced to disk (fsync: milliseconds). A hit is logged without the force, because losing the last
 * few hits in a crash only makes the order slightly stale. Each line ends in a CRC32 checksum, so a line
 * torn by a crash mid-write is found and cut off. compact() rewrites the log as the live entries, oldest
 * first, through a temp file and one atomic rename. Keys and values: text without tabs or newlines.
 */
final class LoggedLruCache implements AutoCloseable {
    private final LinkedHashMap<String, String> map;     // the five-line LRU from the LinkedHashMap question
    private final Path file;
    private FileChannel log;

    LoggedLruCache(int capacity, Path file) throws IOException {
        this.map = new LinkedHashMap<>(16, 0.75f, true) {
            @Override protected boolean removeEldestEntry(Map.Entry<String, String> eldest) { return size() > capacity; }
        };
        this.file = file;
        this.log = FileChannel.open(file, StandardOpenOption.CREATE, StandardOpenOption.READ, StandardOpenOption.WRITE);
        log.truncate(replay());                          // cut a torn last line, so new records start clean
        log.position(log.size());
    }

    /** A hit is logged as a use, not forced: it only moves the order. */
    synchronized String get(String key) throws IOException {
        String v = map.get(key);
        if (v != null) append("U\t" + key, false);
        return v;
    }
    /** The log first, forced to disk; only then the cache. */
    synchronized void put(String key, String value) throws IOException {
        append("P\t" + key + "\t" + value, true);
        map.put(key, value);
    }
    /** The keys, next victim first. */
    synchronized List<String> evictionOrder() { return new ArrayList<>(map.keySet()); }

    /** Rewrite the log as the live entries, oldest first, so replaying it rebuilds the same cache and order. */
    synchronized void compact() throws IOException {
        Path tmp = file.resolveSibling(file.getFileName() + ".tmp");
        try (FileChannel out = FileChannel.open(tmp, StandardOpenOption.CREATE, StandardOpenOption.WRITE,
                                                StandardOpenOption.TRUNCATE_EXISTING)) {
            for (Map.Entry<String, String> e : map.entrySet()) out.write(line("P\t" + e.getKey() + "\t" + e.getValue()));
            out.force(true);
        }
        log.close();
        Files.move(tmp, file, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);   // all or nothing
        log = FileChannel.open(file, StandardOpenOption.WRITE, StandardOpenOption.APPEND);
    }
    public synchronized void close() throws IOException { log.close(); }

    /** Replay every intact line in order; stop at the first torn one. Returns where the intact part ends. */
    private long replay() throws IOException {
        byte[] all = Files.readAllBytes(file);
        int start = 0;
        for (int i = 0; i < all.length; i++) {
            if (all[i] != '\n') continue;
            String text = new String(all, start, i - start, StandardCharsets.UTF_8);
            int cut = text.lastIndexOf('\t');
            if (cut < 0 || !Long.toString(crc(text.substring(0, cut))).equals(text.substring(cut + 1))) break;
            String[] f = text.substring(0, cut).split("\t");
            if (f[0].equals("P")) map.put(f[1], f[2]); else map.get(f[1]);    // a put, or a use
            start = i + 1;
        }
        return start;
    }
    /** Append one record; force it to the disk when it must survive a crash. */
    private void append(String record, boolean force) throws IOException {
        log.write(line(record));
        if (force) log.force(false);
    }
    /** One log line: the record, a tab, its checksum, a newline. */
    private static ByteBuffer line(String record) {
        return ByteBuffer.wrap((record + "\t" + crc(record) + "\n").getBytes(StandardCharsets.UTF_8));
    }
    /** CRC32 of the record: a torn or damaged line will not match. */
    private static long crc(String s) { CRC32 c = new CRC32(); c.update(s.getBytes(StandardCharsets.UTF_8)); return c.getValue(); }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        // stats: the hit rate, from outside
        StatsCache<String, String> counted = new StatsCache<>(new LruCache<>(2));
        counted.put("a", "1"); counted.get("a"); counted.get("a"); counted.get("nope");
        System.out.println("stats: " + counted.summary());

        // the locking decorator: correct, and it drags the slow things inside the lock
        Cache<String, String> wrapped = new SynchronizedCache<>(new LruCache<>(2));
        wrapped.put("a", "1");
        System.out.println("synchronized wrapper: get(a)=" + wrapped.get("a") + " size=" + wrapped.size());

        // bound by bytes: one put can evict several entries
        WeightedLruCache<String, byte[]> weighted = new WeightedLruCache<>(1_000, v -> v.length);
        weighted.configure(k -> null, (k, v, c) -> System.out.println("  weighted evicted " + k + " (" + v.length + " bytes)"));
        weighted.put("small1", new byte[300]); weighted.put("small2", new byte[300]); weighted.put("small3", new byte[300]);
        System.out.println("weighted before the big one: " + weighted.evictionOrder() + " weight=" + weighted.weight());
        weighted.put("big", new byte[900]);                       // needs 900 of 1000: it clears the rest out
        System.out.println("weighted after the big one:  " + weighted.evictionOrder() + " weight=" + weighted.weight());

        // striping: sixteen locks instead of one, and no global order
        StripedCache<Integer, String> striped = new StripedCache<>(160, 16);
        for (int i = 0; i < 500; i++) striped.put(i, "v" + i);
        System.out.println("striped: capacity=" + striped.capacity() + " resident=" + striped.size()
            + " (approximate LRU: each segment evicted on its own)");

        // the stampede: a thousand threads, one cold key, one database read
        AtomicInteger rawLoads = new AtomicInteger();
        SingleFlightLoader<String, String> single = new SingleFlightLoader<>(key -> {
            rawLoads.incrementAndGet();
            try { Thread.sleep(20); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            return "loaded-" + key;
        });
        LruCache<String, String> stampede = new LruCache<>(10);
        stampede.configure(single, (k, v, c) -> { });
        ExecutorService pool = Executors.newFixedThreadPool(32);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<String>> asked = new ArrayList<>();
        for (int i = 0; i < 1_000; i++) asked.add(pool.submit(() -> { go.await(); return stampede.get("cold"); }));
        go.countDown();
        for (Future<String> f : asked) f.get();
        pool.shutdown();
        System.out.println("stampede: 1000 concurrent misses on one key -> " + single.realLoads() + " real load(s), "
            + rawLoads.get() + " database read(s)");

        // the sweeper: proactive expiry off a heap, on an injected clock
        long[] now = { 1_000_000L };
        LruCache<String, String> swept = new LruCache<>(100);
        swept.setClock(() -> now[0]);
        swept.setTtlMs(60_000);
        ExpirySweeper<String, String> sweeper = new ExpirySweeper<>(swept);
        for (int i = 0; i < 5; i++) { swept.put("s" + i, "v"); sweeper.track("s" + i, now[0] + 60_000); }
        now[0] += 61_000;
        System.out.println("sweeper: removed " + sweeper.sweep(now[0]) + " expired entries, size is now " + swept.size());

        // write-behind: the store is written by one background thread, not by the evicting caller
        Map<String, String> store = new ConcurrentHashMap<>();
        try (WriteBehindListener<String, String> behind = new WriteBehindListener<>(store, 1_000)) {
            LruCache<String, String> dirty = new LruCache<>(10);
            dirty.configure(k -> null, behind);
            for (int i = 0; i < 100; i++) dirty.put("w" + i, "v" + i);
            behind.close();
            System.out.println("write-behind: 100 puts into a cache of 10 -> " + store.size()
                + " evicted values reached the store on the writer thread, " + behind.dropped()
                + " dropped by the overflow policy (10 are still resident)");
        }

        // two tiers: memory in front of a versioned store, plus the invalidation message
        VersionedStore<String, String> far = new VersionedStore<>();
        AtomicLong sequence = new AtomicLong();                    // ONE version source that every server shares
        TwoTierCache<String, String> tiered = new TwoTierCache<>(new LruCache<>(2), far, sequence::incrementAndGet);
        tiered.put("k", "v1");
        System.out.println("two tiers: store has " + far.read("k") + ", memory has " + tiered.get("k"));
        far.write("k", "v2-from-another-server", sequence.incrementAndGet());   // somebody else wrote it
        System.out.println("  before the invalidation message this server still serves " + tiered.get("k"));
        tiered.onInvalidation("k");
        System.out.println("  after the invalidation message it re-reads and serves " + tiered.get("k"));
        System.out.println("  a stale write with an older version loses: " + !far.write("k", "old", 1)
            + ", stored value is still " + far.read("k"));

        // the builder: seven knobs, six optional
        Cache<String, String> built = CacheBuilder.<String, String>newBuilder()
            .maximumSize(3).expireAfterWrite(30_000).leastFrequentlyUsed().recordStats()
            .loader(key -> "lazy-" + key)
            .evictionListener((k, v, c) -> { })
            .build();
        built.put("a", "1"); built.get("a"); built.get("b");
        System.out.println("builder: LFU + TTL + stats -> " + ((StatsCache<String, String>) built).summary()
            + " size=" + built.size() + "  (get(b) missed, but the loader answered it, so the wrapper counted a hit:"
            + " that is the caveat in StatsCache's comment)");

        // admission: the same scan through two caches, one with a door on it
        AdmissionLruCache<Integer, String> guarded = new AdmissionLruCache<>(100);
        LruCache<Integer, String> plain = new LruCache<>(100);
        for (int round = 0; round < 20; round++)                   // 20 real users, asked for again and again
            for (int k = 0; k < 50; k++) { guarded.put(k, "hot" + k); plain.put(k, "hot" + k); guarded.get(k); plain.get(k); }
        for (int row = 10_000; row < 11_000; row++) { guarded.put(row, "scan"); plain.put(row, "scan"); }
        int guardedKept = 0, plainKept = 0;
        for (int k = 0; k < 50; k++) { if (guarded.get(k) != null) guardedKept++; if (plain.get(k) != null) plainKept++; }
        System.out.println("admission: after a 1000-row scan, the working set surviving is " + guardedKept
            + "/50 with a door, " + plainKept + "/50 without it (" + guarded.doorLog() + ")");

        // the five-line version
        LinkedHashMapCache<String, String> jdk = new LinkedHashMapCache<>(3);
        jdk.put("A", "1"); jdk.put("B", "2"); jdk.put("C", "3");
        jdk.get("A");                                              // access order: A is no longer the eldest
        jdk.put("D", "4");
        System.out.println("LinkedHashMap(accessOrder=true): " + jdk.evictionOrder() + " (oldest first), B evicted: "
            + (jdk.get("B") == null));

        // expire-after-access: every use restarts the clock, so the tail is always the first to expire
        long[] t = { 0 };
        LruCache<String, String> idle = new LruCache<>(10);
        idle.setClock(() -> t[0]);
        idle.setTtlMs(5_000, true);
        idle.put("a", "1"); idle.put("b", "2"); idle.put("c", "3");
        t[0] = 4_000; idle.get("a");                               // a's five seconds start again
        t[0] = 6_000;
        System.out.println("expire-after-access: sweepExpired freed " + idle.sweepExpired() + " from the tail, left "
            + idle.evictionOrder() + " (a was read at 4s, so it lives to 9s)");

        // the pluggable policy: the same calls, two policies, two different victims
        for (String name : List.of("lru", "fifo")) {
            PolicyCache<String, String> pc = new PolicyCache<>(2, new HashMap<>(),
                name.equals("lru") ? ListPolicy.lru() : ListPolicy.fifo());
            pc.put("A", "1"); pc.put("B", "2"); pc.get("A"); pc.put("C", "3");
            System.out.println("policy " + name + ": after put A, put B, get A, put C -> A kept: " + (pc.get("A") != null)
                + ", B kept: " + (pc.get("B") != null));
        }

        // multi-level: L1 fast and small, L3 slow and big
        MultiLevelCache<String, String> levels = new MultiLevelCache<>(List.of(
            new MultiLevelCache.Level<>("L1", new LruCache<>(2), 1, 2),
            new MultiLevelCache.Level<>("L2", new LruCache<>(4), 5, 10),
            new MultiLevelCache.Level<>("L3", new LruCache<>(8), 20, 40)), 5);
        System.out.println("multi-level: write(x) took " + levels.write("x", "1") + " ms (1+2 + 5+10 + 20+40)");
        levels.write("y", "2"); levels.write("z", "3");            // L1 holds two: x is pushed out of it
        MultiLevelCache.Read<String> r = levels.read("x");
        System.out.println("  read(x) -> " + r.value() + " in " + r.ms() + " ms (L1 miss 1, L2 hit 5, copy to L1 2); "
            + levels.stats());

        // write-order expiry with an O(1) average of the live values
        long[] c = { 0 };
        ExpiringAverageCache<String> avg = new ExpiringAverageCache<>(10_000, () -> c[0]);
        avg.put("a", 10); c[0] = 1_000; avg.put("b", 20); c[0] = 2_000; avg.put("c", 30);
        double at2s = avg.average();
        c[0] = 10_500;
        System.out.println("average of the live values: " + at2s + " at 2s, " + avg.average() + " at 10.5s (a expired at 10s)");

        // memo + log: equal calls share one key; the cache survives a crash with its recency order
        int[] runs = { 0 };
        MemoCache<Integer> memo = new MemoCache<>(100, key -> ++runs[0]);
        memo.call("sum", new Object[] { new int[] { 1, 2 } }, Map.of("a", 1, "b", 2));
        memo.call("sum", new Object[] { new int[] { 1, 2 } }, Map.of("b", 2, "a", 1));   // new array, other order
        System.out.println("memo: two equal calls computed " + runs[0] + " time(s)");
        Path wal = Files.createTempFile("lru-demo", ".log");
        try (LoggedLruCache before = new LoggedLruCache(2, wal)) {
            before.put("a", "1"); before.put("b", "2"); before.get("a"); before.put("c", "3");
        }
        try (LoggedLruCache after = new LoggedLruCache(2, wal)) {
            System.out.println("  after a restart the log rebuilt " + after.evictionOrder() + " (oldest first; b had been evicted)");
        }
        Files.deleteIfExists(wal);
    }
}
