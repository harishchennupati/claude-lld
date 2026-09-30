import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Consumer;
import java.util.function.Supplier;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong. Nothing here opens PolicyCache.

// ---- ext: a new rule -- sampled LRU, which is what Redis actually does. ONE class, one builder line.
/**
 * Approximate LRU: instead of a linked list, keep a dense array of keys and a monotonic tick per key, then
 * sample a handful at random and evict the coldest one you saw. Cheaper than exact LRU and sometimes wrong --
 * Redis's deliberate trade. Removal swaps the last key into the hole, so it stays O(1).
 */
final class SampledLruPolicy<K> implements EvictionPolicy<K> {
    private final int sampleSize;
    private final Random rnd;
    private final Map<K, Long> lastUsedTick = new HashMap<>();
    private final List<K> keys = new ArrayList<>();
    private final Map<K, Integer> slotOf = new HashMap<>();
    private long tick;

    /** sampleSize is how many random keys are looked at per eviction; Redis defaults to five. */
    SampledLruPolicy(int sampleSize, long seed) { this.sampleSize = Math.max(1, sampleSize); this.rnd = new Random(seed); }

    /** Adds the key to the dense array if it is new, and stamps it with the current tick. */
    public void onPut(K key, long nowMs, long expiresAtMs) {
        if (!slotOf.containsKey(key)) { slotOf.put(key, keys.size()); keys.add(key); }
        lastUsedTick.put(key, ++tick);
    }
    /** A read is a use: one map write, no pointer surgery at all. */
    public void onGet(K key, long nowMs) { if (slotOf.containsKey(key)) lastUsedTick.put(key, ++tick); }
    /** Swap-with-last keeps removal O(1) and the array dense enough to sample by index. */
    public void onRemove(K key) {
        Integer i = slotOf.remove(key);
        lastUsedTick.remove(key);
        if (i == null) return;
        K moved = keys.remove(keys.size() - 1);
        if (!moved.equals(key)) { keys.set(i, moved); slotOf.put(moved, i); }
    }
    /** The coldest of a few random keys. O(sample), and occasionally not the coldest key in the cache. */
    public K selectVictim(long nowMs) {
        if (keys.isEmpty()) return null;
        K coldest = null;
        long coldestTick = Long.MAX_VALUE;
        for (int s = 0, n = Math.min(sampleSize, keys.size()); s < n; s++) {
            K cand = keys.get(rnd.nextInt(keys.size()));
            long t = lastUsedTick.getOrDefault(cand, Long.MAX_VALUE);
            if (t < coldestTick) { coldestTick = t; coldest = cand; }
        }
        return coldest;
    }
    /** Keys in the dense array. */
    public int trackedKeys() { return slotOf.size(); }
    public String name() { return "SampledLRU(" + sampleSize + ")"; }
}

// ---- ext: scan resistance -- a nightly report reads every row and destroys the hit rate. A NEW class.
/**
 * Segmented LRU: two lists. A key enters PROBATION; a second read promotes it to PROTECTED, which holds the
 * working set. Victims come from probation first, so a one-pass scan of a million cold keys walks in and
 * straight back out without touching what is protected. This is the shape TinyLFU and Caffeine build on.
 */
final class SegmentedLruPolicy<K> implements EvictionPolicy<K> {
    private final KeyList<K> probation = new KeyList<>();
    private final KeyList<K> protectedSeg = new KeyList<>();
    private final int protectedCapacity;

    /** protectedCapacity is usually about 80% of the cache: the part a scan must not be able to evict. */
    SegmentedLruPolicy(int protectedCapacity) { this.protectedCapacity = Math.max(1, protectedCapacity); }

    /** A new or rewritten key sits in probation until somebody reads it a second time. */
    public void onPut(K key, long nowMs, long expiresAtMs) {
        if (protectedSeg.contains(key)) protectedSeg.touchFirst(key);
        else probation.touchFirst(key);
    }
    /** The promotion: one read moves a key out of probation, and the coldest protected key is demoted. */
    public void onGet(K key, long nowMs) {
        if (probation.contains(key)) {
            probation.remove(key);
            protectedSeg.touchFirst(key);
            while (protectedSeg.size() > protectedCapacity) {
                K cold = protectedSeg.last();
                protectedSeg.remove(cold);
                probation.touchFirst(cold);                    // demoted, not evicted: it gets another chance
            }
        } else if (protectedSeg.contains(key)) {
            protectedSeg.touchFirst(key);
        }
    }
    /** Both lists must drop the key. */
    public void onRemove(K key) { probation.remove(key); protectedSeg.remove(key); }
    /** Probation goes first; only an empty probation reaches into the protected working set. */
    public K selectVictim(long nowMs) {
        K v = probation.last();
        return v != null ? v : protectedSeg.last();
    }
    /** Keys across both segments. */
    public int trackedKeys() { return probation.size() + protectedSeg.size(); }
    public String name() { return "SegmentedLRU"; }
}

// ---- ext: capacity in bytes -- a 2 MB value and a 2 KB value are not the same thing
/** How heavy an entry is. One method, handed in, so the cache never guesses at sizes. */
interface Weigher<K, V> {
    /** The cost of holding this entry, in whatever unit the budget is written in. */
    int weigh(K key, V value);
}

/**
 * The same cache bounded by total weight instead of entry count. Two changes, both small: the single "is it
 * full?" check becomes a LOOP, because one heavy value can push out several small ones, and an entry heavier
 * than the whole budget is refused outright -- otherwise it empties the cache and still does not fit.
 * The policies are untouched: weight is a bound, not a ranking.
 */
final class ByteBoundedCache<K, V> implements Cache<K, V> {
    private final long maxWeight;
    private final Weigher<K, V> weigher;
    private final Map<K, CacheEntry<V>> table = new LinkedHashMap<>();
    private final Map<K, Integer> weightOf = new HashMap<>();
    private final EvictionPolicy<K> policy;
    private final ReentrantLock lock = new ReentrantLock();
    private final Clock clock;
    private final AtomicLong hits = new AtomicLong(), misses = new AtomicLong(), evictions = new AtomicLong();
    private long totalWeight;

    /** maxWeight is the budget, in the weigher's unit; the policy still decides who goes. */
    ByteBoundedCache(long maxWeight, Weigher<K, V> weigher, EvictionPolicy<K> policy, Clock clock) {
        this.maxWeight = maxWeight; this.weigher = weigher; this.policy = policy; this.clock = clock;
    }

    /** The value, or null. Same read path as PolicyCache, minus the expiry branch for brevity. */
    public V getIfPresent(K key) {
        lock.lock();
        try {
            CacheEntry<V> e = table.get(key);
            if (e == null || e.expired(clock.nowMs())) { misses.incrementAndGet(); return null; }
            policy.onGet(key, clock.nowMs());
            hits.incrementAndGet();
            return e.value;
        } finally { lock.unlock(); }
    }
    /** Stores a value with no deadline. */
    public void put(K key, V value) { put(key, value, 0); }
    /** Stores a value, evicting as many entries as it takes to fit the new one inside the budget. */
    public void put(K key, V value, long ttlMs) {
        int w = weigher.weigh(key, value);
        if (w > maxWeight) return;                             // refuse: it would empty the cache and still not fit
        long now = clock.nowMs();
        lock.lock();
        try {
            if (table.containsKey(key)) { totalWeight -= weightOf.remove(key); table.remove(key); policy.onRemove(key); }
            while (totalWeight + w > maxWeight) {               // a LOOP, not an if
                K victim = policy.selectVictim(now);
                if (victim == null) break;
                table.remove(victim);
                policy.onRemove(victim);
                Integer vw = weightOf.remove(victim);
                if (vw != null) totalWeight -= vw;
                evictions.incrementAndGet();
            }
            table.put(key, new CacheEntry<>(value, now, ttlMs <= 0 ? Long.MAX_VALUE : now + ttlMs));
            weightOf.put(key, w);
            totalWeight += w;
            policy.onPut(key, now, ttlMs <= 0 ? Long.MAX_VALUE : now + ttlMs);
        } finally { lock.unlock(); }
    }
    /** Removes a key and gives back its weight. */
    public V remove(K key) {
        lock.lock();
        try {
            CacheEntry<V> e = table.remove(key);
            if (e == null) return null;
            policy.onRemove(key);
            Integer w = weightOf.remove(key);
            if (w != null) totalWeight -= w;
            return e.value;
        } finally { lock.unlock(); }
    }
    /** Entries resident. */
    public int size() { lock.lock(); try { return table.size(); } finally { lock.unlock(); } }
    /** This cache is bounded by weight, not by entry count, so there is no entry bound to report. */
    public int capacity() { return Integer.MAX_VALUE; }
    /** Bytes held right now: the number the bound is actually about. */
    long weight() { lock.lock(); try { return totalWeight; } finally { lock.unlock(); } }
    /** Drops dead entries. */
    public void cleanUp() {
        lock.lock();
        try {
            long now = clock.nowMs();
            for (Iterator<Map.Entry<K, CacheEntry<V>>> it = table.entrySet().iterator(); it.hasNext(); ) {
                Map.Entry<K, CacheEntry<V>> en = it.next();
                if (en.getValue().expired(now)) {
                    it.remove(); policy.onRemove(en.getKey());
                    Integer w = weightOf.remove(en.getKey());
                    if (w != null) totalWeight -= w;
                }
            }
        } finally { lock.unlock(); }
    }
    /** Hits, misses and evictions. */
    public CacheStats stats() { return new CacheStats(hits.get(), misses.get(), evictions.get(), 0); }
}

// ---- ext: read-through without a stampede -- six threads miss the same hot key at the same instant
/** Where a value comes from on a miss: a database, an API, a computation. One method, handed in. */
interface CacheLoader<K, V> {
    /** Fetches the value for this key. Called with NO cache lock held. */
    V load(K key) throws Exception;
}

/**
 * Read-through with single flight. The naive version of "load on a miss" is an incident: six threads miss
 * the same hot key, all six pass the "is it cached?" check before any of them finishes, and all six hit the
 * database at exactly the moment it can least take it. The fix is a per-key election -- putIfAbsent on a
 * future is one compare-and-set that names a winner, and the losers wait on the winner's future.
 * A wrapper, not an edit: it composes over any Cache, including a striped one.
 */
final class LoadingCache<K, V> implements Cache<K, V> {
    private final Cache<K, V> inner;
    private final CacheLoader<K, V> loader;
    private final ConcurrentHashMap<K, CompletableFuture<V>> inFlight = new ConcurrentHashMap<>();
    private final boolean singleFlight;

    /** singleFlight = false reproduces the stampede, which is what the demo contrasts against. */
    LoadingCache(Cache<K, V> inner, CacheLoader<K, V> loader, boolean singleFlight) {
        this.inner = inner; this.loader = loader; this.singleFlight = singleFlight;
    }

    /** The value, loading it on a miss. At most one loader call per key is in flight at a time. */
    V get(K key) throws Exception {
        V cached = inner.getIfPresent(key);
        if (cached != null) return cached;
        if (!singleFlight) {                                   // the version that takes down the database
            V loaded = loader.load(key);
            if (loaded != null) inner.put(key, loaded);
            return loaded;
        }
        CompletableFuture<V> mine = new CompletableFuture<>();
        CompletableFuture<V> winner = inFlight.putIfAbsent(key, mine);
        if (winner != null) return winner.get();               // a loser: wait for the winner's result
        try {
            V again = inner.getIfPresent(key);                 // double-check inside the flight
            V loaded = again != null ? again : loader.load(key);
            if (loaded != null) inner.put(key, loaded);
            mine.complete(loaded);
            return loaded;
        } catch (Exception e) {
            mine.completeExceptionally(e);                     // or every waiter parks forever
            throw e;
        } finally {
            inFlight.remove(key, mine);                        // in a finally, so a throw cannot poison the key
        }
    }

    /** Delegates: a read that does not load. */
    public V getIfPresent(K key) { return inner.getIfPresent(key); }
    /** Delegates. */
    public void put(K key, V value) { inner.put(key, value); }
    /** Delegates. */
    public void put(K key, V value, long ttlMs) { inner.put(key, value, ttlMs); }
    /** Delegates. */
    public V remove(K key) { return inner.remove(key); }
    /** Delegates. */
    public int size() { return inner.size(); }
    /** Delegates. */
    public int capacity() { return inner.capacity(); }
    /** Delegates. */
    public void cleanUp() { inner.cleanUp(); }
    /** Delegates. */
    public CacheStats stats() { return inner.stats(); }
}

// ---- ext: writes -- does a put reach the database, and when?
/** The durable side of a write: where a value lives once the cache lets go of it. One method, handed in. */
interface WriteStore<K, V> {
    /** Persists one key. Called with NO cache lock held, so it may take a millisecond of database. */
    void write(K key, V value);
}

/**
 * Write-through: the store is written BEFORE the cache, so a failed write never becomes a cached lie and the
 * store is never behind the cache. The price is that every put pays the store's latency on the caller's
 * thread, so a write-through cache speeds up reads only. This is the same ordering rule as move 6 -- commit
 * nothing until the irreversible thing has succeeded -- and it is a wrapper, so PolicyCache still has no idea
 * what a database is.
 */
final class WriteThroughCache<K, V> implements Cache<K, V> {
    private final Cache<K, V> inner;
    private final WriteStore<K, V> store;

    /** Wraps any cache, including a striped one. */
    WriteThroughCache(Cache<K, V> inner, WriteStore<K, V> store) { this.inner = inner; this.store = store; }

    /** Store first, cache second: if the store throws, nothing was cached and the caller can retry. */
    public void put(K key, V value) { store.write(key, value); inner.put(key, value); }
    /** Store first, cache second, with a deadline. */
    public void put(K key, V value, long ttlMs) { store.write(key, value); inner.put(key, value, ttlMs); }
    /** Delegates: reads never touch the store. */
    public V getIfPresent(K key) { return inner.getIfPresent(key); }
    /** Delegates. */
    public V remove(K key) { return inner.remove(key); }
    /** Delegates. */
    public int size() { return inner.size(); }
    /** Delegates. */
    public int capacity() { return inner.capacity(); }
    /** Delegates. */
    public void cleanUp() { inner.cleanUp(); }
    /** Delegates. */
    public CacheStats stats() { return inner.stats(); }
}

/**
 * Write-back (write-behind): a put touches only the cache, and the value reaches the store when the entry
 * leaves. That is a RemovalListener and nothing else -- no new field on the cache, no new lock. The CAUSE is
 * the whole logic, which is the clearest payoff of having four causes instead of a boolean:
 * CAPACITY and EXPIRED carry the newest value out of memory, so not writing it loses the write;
 * REPLACED hands back a value that a newer one has already superseded, and writing it is pure waste;
 * EXPLICIT is the caller saying forget this, which is not a request to persist it.
 * The honest cost: the flush happens after the unlock, so a crash in that window loses the write. Real
 * write-back caches pair this with a periodic flush of everything still dirty.
 */
final class WriteBackListener<K, V> implements RemovalListener<K, V> {
    private final WriteStore<K, V> store;
    private final AtomicLong flushes = new AtomicLong();

    /** Hand it the store; hand it to the cache with builder.listener(...). */
    WriteBackListener(WriteStore<K, V> store) { this.store = store; }

    /** Writes back only the two causes that carry a live value out of memory. */
    public void onRemoval(K key, V value, RemovalCause cause) {
        if (cause == RemovalCause.CAPACITY || cause == RemovalCause.EXPIRED) {
            store.write(key, value);
            flushes.incrementAndGet();
        }
    }

    /** How many entries have been written back so far. */
    long flushes() { return flushes.get(); }
}

// ---- ext: striping -- the profiler says threads are queueing on your one lock
/**
 * N independent caches behind one Cache, chosen by a spread hash of the key. Callers change nothing;
 * throughput goes up roughly N times because unrelated keys no longer share a lock. The price: eviction is
 * now per stripe, so the bound is per stripe too and the recency order is approximate across the whole cache.
 */
final class StripedCache<K, V> implements Cache<K, V> {
    private final List<PolicyCache<K, V>> segments = new ArrayList<>();

    /** Splits the capacity evenly; each stripe gets its OWN policy instance, never a shared one. */
    StripedCache(int stripes, int totalCapacity, Supplier<EvictionPolicy<K>> policyPerStripe, Clock clock) {
        int per = Math.max(1, totalCapacity / stripes);
        for (int i = 0; i < stripes; i++)
            segments.add(new PolicyCache<>(per, policyPerStripe.get(), clock, 0));
    }

    // The same bit-spreading HashMap uses: raw hashCodes clump, and a clumped hash means one hot stripe.
    private PolicyCache<K, V> segmentFor(K key) {
        int h = key.hashCode();
        h ^= (h >>> 16);
        return segments.get((h & 0x7fffffff) % segments.size());
    }

    /** Reads from the one stripe that could hold this key. */
    public V getIfPresent(K key) { return segmentFor(key).getIfPresent(key); }
    /** Writes into the one stripe that owns this key. */
    public void put(K key, V value) { segmentFor(key).put(key, value); }
    /** Writes into the one stripe that owns this key. */
    public void put(K key, V value, long ttlMs) { segmentFor(key).put(key, value, ttlMs); }
    /** Removes from the one stripe that owns this key. */
    public V remove(K key) { return segmentFor(key).remove(key); }
    /** The total across stripes; no lock spans them, so it is a sum of snapshots. */
    public int size() { int n = 0; for (PolicyCache<K, V> s : segments) n += s.size(); return n; }
    /** The sum of the per-stripe bounds. */
    public int capacity() { int n = 0; for (PolicyCache<K, V> s : segments) n += s.capacity(); return n; }
    /** Sweeps every stripe. */
    public void cleanUp() { for (PolicyCache<K, V> s : segments) s.cleanUp(); }
    /** Adds the stripes' counters together. */
    public CacheStats stats() {
        long h = 0, m = 0, e = 0, x = 0;
        for (PolicyCache<K, V> s : segments) {
            CacheStats t = s.stats();
            h += t.hits(); m += t.misses(); e += t.evictions(); x += t.expirations();
        }
        return new CacheStats(h, m, e, x);
    }
}

// ---- ext: two servers -- a write on one must not leave a stale copy on the other
/**
 * A stand-in for a message bus: in a real system this is Redis pub/sub, Kafka or a gossip channel, and which
 * node owns which key is decided by consistent hashing so that adding a node moves 1/N of the keys, not all
 * of them. The rule that matters is the same either way: publish INVALIDATIONS, not values, so two nodes can
 * never disagree about what the newest value is -- they simply both go and read it again.
 */
final class InvalidationBus {
    private final Map<String, Consumer<String>> nodes = new ConcurrentHashMap<>();
    /** A node subscribes with its own id and a handler that drops a key locally. */
    void join(String nodeId, Consumer<String> onInvalidate) { nodes.put(nodeId, onInvalidate); }
    /** Tells every OTHER node that this key changed. The writer keeps its own fresh copy. */
    void publish(String fromNodeId, String key) {
        nodes.forEach((id, handler) -> { if (!id.equals(fromNodeId)) handler.accept(key); });
    }
}

/**
 * One node's cache, wired to the bus. A local write publishes an invalidation; an invalidation from another
 * node drops the local copy so the next read reloads it. A fifth removal cause, INVALIDATED, would be worth
 * adding in production: today the drop is reported as EXPLICIT, which is close enough to be a lie.
 */
final class ReplicatedCache<V> implements Cache<String, V> {
    private final String nodeId;
    private final Cache<String, V> local;
    private final InvalidationBus bus;

    /** Joins the bus on construction, so the node starts hearing about other nodes' writes immediately. */
    ReplicatedCache(String nodeId, Cache<String, V> local, InvalidationBus bus) {
        this.nodeId = nodeId; this.local = local; this.bus = bus;
        bus.join(nodeId, local::remove);                       // never re-publishes: that would loop forever
    }

    /** Reads the local copy. */
    public V getIfPresent(String key) { return local.getIfPresent(key); }
    /**
     * Fills the local copy after a read from the database, and publishes NOTHING. The distinction matters:
     * a cache fill is not news -- nobody else's copy became wrong -- and a node that invalidates the cluster
     * every time it warms itself up turns a cache into a broadcast storm.
     */
    void fill(String key, V value) { local.put(key, value); }
    /** Writes locally, then tells the other nodes to forget what they have. */
    public void put(String key, V value) { local.put(key, value); bus.publish(nodeId, key); }
    /** Writes locally with a deadline, then invalidates elsewhere. */
    public void put(String key, V value, long ttlMs) { local.put(key, value, ttlMs); bus.publish(nodeId, key); }
    /** Removes locally, then invalidates elsewhere. */
    public V remove(String key) { V v = local.remove(key); bus.publish(nodeId, key); return v; }
    /** Delegates. */
    public int size() { return local.size(); }
    /** Delegates. */
    public int capacity() { return local.capacity(); }
    /** Delegates. */
    public void cleanUp() { local.cleanUp(); }
    /** Delegates. */
    public CacheStats stats() { return local.stats(); }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        ManualClock clock = new ManualClock(0);

        System.out.println("== sampled LRU: Redis's trade, one class and one builder line ==");
        PolicyCache<Integer, Integer> sampled = CacheBuilder.<Integer, Integer>newBuilder()
                .capacity(50).policy(new SampledLruPolicy<>(5, 42)).clock(clock).build();
        for (int i = 0; i < 500; i++) { sampled.put(i, i); if (i % 3 == 0) sampled.getIfPresent(i); }
        System.out.println("   500 keys into a cache of 50 -> size " + sampled.size()
                           + ", consistent " + sampled.consistent() + ", " + sampled.stats());

        System.out.println();
        System.out.println("== scan resistance: a report reads a million cold rows; the working set survives ==");
        for (EvictionPolicy<String> p : List.of(new LruPolicy<String>(), new SegmentedLruPolicy<String>(8))) {
            PolicyCache<String, String> seg = CacheBuilder.<String, String>newBuilder()
                    .capacity(10).policy(p).clock(clock).build();
            for (int i = 0; i < 8; i++) { seg.put("hot" + i, "v"); seg.getIfPresent("hot" + i); }  // the working set
            for (int i = 0; i < 200; i++) seg.put("scan" + i, "v");                                 // the report
            int survived = 0;
            for (int i = 0; i < 8; i++) if (seg.getIfPresent("hot" + i) != null) survived++;
            System.out.printf("   %-14s hot keys still resident after a 200-key scan: %d/8%n", p.name(), survived);
        }

        System.out.println();
        System.out.println("== capacity in bytes: one 750-byte value pushes out several small ones ==");
        ByteBoundedCache<String, byte[]> bytes = new ByteBoundedCache<>(
                1000, (k, v) -> v.length, new LruPolicy<>(), clock);
        for (int i = 0; i < 5; i++) bytes.put("small" + i, new byte[100]);
        System.out.println("   after 5 x 100 bytes: entries " + bytes.size() + ", weight " + bytes.weight());
        bytes.put("big", new byte[750]);
        System.out.println("   after one 750-byte value: entries " + bytes.size() + ", weight " + bytes.weight()
                           + "   (three small ones had to go, so the check is a loop)");
        bytes.put("enormous", new byte[2000]);
        System.out.println("   a 2000-byte value into a 1000-byte budget is refused: entries "
                           + bytes.size() + ", weight " + bytes.weight());

        System.out.println();
        System.out.println("== the stampede: six threads miss the same hot key at the same instant ==");
        for (boolean single : new boolean[]{false, true}) {
            AtomicLong dbCalls = new AtomicLong();
            PolicyCache<String, String> backing = CacheBuilder.<String, String>newBuilder()
                    .capacity(16).policy(new LruPolicy<>()).clock(clock).build();
            LoadingCache<String, String> through = new LoadingCache<>(backing, key -> {
                dbCalls.incrementAndGet();
                Thread.sleep(30);                              // the database, being slow
                return "row:" + key;
            }, single);
            ExecutorService pool = Executors.newFixedThreadPool(6);
            CountDownLatch go = new CountDownLatch(1);
            List<Future<String>> fs = new ArrayList<>();
            for (int i = 0; i < 6; i++) fs.add(pool.submit(() -> { go.await(); return through.get("user:42"); }));
            go.countDown();
            for (Future<String> f : fs) f.get();
            pool.shutdown();
            System.out.println("   singleFlight=" + single + " -> loader called " + dbCalls.get() + " time(s)");
        }

        System.out.println();
        System.out.println("== writes: through to the store now, or back when the entry leaves ==");
        Map<String, String> throughStore = new LinkedHashMap<>();
        WriteThroughCache<String, String> wt = new WriteThroughCache<>(
                CacheBuilder.<String, String>newBuilder().capacity(4).clock(clock).build(), throughStore::put);
        wt.put("order:1", "paid");
        System.out.println("   write-through: one put, and the store already holds " + throughStore);

        Map<String, String> backStore = new LinkedHashMap<>();
        WriteBackListener<String, String> back = new WriteBackListener<>(backStore::put);
        PolicyCache<String, String> behind = CacheBuilder.<String, String>newBuilder()
                .capacity(2).policy(new LruPolicy<>()).clock(clock).listener(back).build();
        behind.put("order:1", "pending");
        behind.put("order:1", "paid");                         // REPLACED: the old value is not news
        System.out.println("   write-back:    two puts to one key, store " + backStore + ", flushes " + back.flushes());
        behind.put("order:2", "paid"); behind.put("order:3", "paid");   // full: one entry leaves by CAPACITY
        System.out.println("   after the cache overflows: store " + backStore + ", flushes " + back.flushes()
                           + "   (the cause is the whole logic)");

        System.out.println();
        System.out.println("== striping: sixteen locks instead of one, callers unchanged ==");
        StripedCache<Integer, Integer> striped = new StripedCache<>(16, 1600, LruPolicy::new, clock);
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> all = new ArrayList<>();
        for (int t = 0; t < 8; t++) {
            final int seed = t;
            all.add(pool.submit(() -> {
                go.await();
                Random rnd = new Random(seed);
                for (int i = 0; i < 5000; i++) { int k = rnd.nextInt(4000); if (striped.getIfPresent(k) == null) striped.put(k, k); }
                return null;
            }));
        }
        go.countDown();
        for (Future<?> f : all) f.get();
        pool.shutdown();
        System.out.println("   40000 operations across 16 stripes -> size " + striped.size()
                           + "/" + striped.capacity() + ", " + striped.stats());

        System.out.println();
        System.out.println("== two servers: a write on node A invalidates node B ==");
        InvalidationBus bus = new InvalidationBus();
        ReplicatedCache<String> a = new ReplicatedCache<>("A",
                CacheBuilder.<String, String>newBuilder().capacity(8).clock(clock).build(), bus);
        ReplicatedCache<String> b = new ReplicatedCache<>("B",
                CacheBuilder.<String, String>newBuilder().capacity(8).clock(clock).build(), bus);
        a.fill("price:AAPL", "230"); b.fill("price:AAPL", "230");     // both warmed from the database
        System.out.println("   both nodes hold: A=" + a.getIfPresent("price:AAPL") + " B=" + b.getIfPresent("price:AAPL"));
        a.put("price:AAPL", "231");
        System.out.println("   after A writes 231: A=" + a.getIfPresent("price:AAPL")
                           + " B=" + b.getIfPresent("price:AAPL") + "  (B reloads instead of serving 230)");
    }
}
