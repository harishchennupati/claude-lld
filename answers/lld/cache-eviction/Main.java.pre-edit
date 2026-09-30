import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.ReentrantLock;

// A bounded in-memory cache whose eviction rule is a separate object. One cache class stores the entries,
// bounds the size and enforces expiry; an EvictionPolicy answers exactly one question -- who leaves next --
// and LRU, LFU, FIFO and shortest-fuse-first are four answers to it. "May I still return this?" is a
// different question, decided by the clock alone, and it lives in the cache where it always applies.

/**
 * Why an entry left the cache. Four causes are four different bugs when somebody asks "where did my session
 * go?", which is the whole reason the listener is told the cause and not just the key.
 */
enum RemovalCause {
    /** A caller called remove(key). */
    EXPLICIT,
    /** A caller put a new value over the same key; the old value is gone. */
    REPLACED,
    /** The clock passed the entry's deadline. Can happen in a cache that is 2% full. */
    EXPIRED,
    /** The cache was full and the policy named this key. Can happen to a perfectly fresh entry. */
    CAPACITY
}

/** Where time comes from. Injected, so a test can prove a 24-hour TTL in zero milliseconds. */
interface Clock {
    /** The current time in milliseconds. */
    long nowMs();
}

/** The real clock: the only place in this design that reads the wall. */
final class SystemClock implements Clock {
    /** Reads the wall clock. */
    public long nowMs() { return System.currentTimeMillis(); }
}

/** A clock a test drives by hand: no sleeping, no flakiness, and a 24-hour TTL takes a microsecond. */
final class ManualClock implements Clock {
    private long now;
    /** Starts the clock at a chosen instant. */
    ManualClock(long startMs) { this.now = startMs; }
    /** The instant this clock was last set or advanced to. */
    public long nowMs() { return now; }
    /** Moves time forward by the given number of milliseconds. */
    void advance(long ms) { now += ms; }
    /** Jumps to an absolute instant, so the same trace can be replayed from t = 0. */
    void setTo(long ms) { now = ms; }
}

/** Somebody who wants to be told when an entry leaves, and why. Always called after the lock is released. */
interface RemovalListener<K, V> {
    /** Told once per departed entry, with the value it held and the reason it went. */
    void onRemoval(K key, V value, RemovalCause cause);
}

/** One departure, recorded inside the lock and delivered after it. */
record Removal<K, V>(K key, V value, RemovalCause cause) { }

/** Counters for the four things anybody ever asks a cache. Approximate under load, deliberately. */
record CacheStats(long hits, long misses, long evictions, long expirations) {
    /** Hits as a fraction of all lookups; zero when nothing has been asked for yet. */
    double hitRate() { long n = hits + misses; return n == 0 ? 0.0 : (double) hits / n; }
    /** A one-line summary for a log or a demo. */
    public String toString() {
        return String.format("hits=%d misses=%d evictions=%d expirations=%d hitRate=%.2f",
                             hits, misses, evictions, expirations, hitRate());
    }
}

/** One stored value with its deadline. The cache owns these; they are never handed to a caller. */
final class CacheEntry<V> {
    final V value;
    final long writtenAtMs;
    /** The instant from which this entry may not be returned; Long.MAX_VALUE means "never dies". */
    final long expiresAtMs;
    long lastAccessMs;
    /** Built by the cache on every write. */
    CacheEntry(V value, long writtenAtMs, long expiresAtMs) {
        this.value = value; this.writtenAtMs = writtenAtMs;
        this.expiresAtMs = expiresAtMs; this.lastAccessMs = writtenAtMs;
    }
    /** True once the clock has reached the deadline. Checked on every read and by cleanUp(). */
    boolean expired(long nowMs) { return nowMs >= expiresAtMs; }
}

/** What a cache can do. A striped cache, a byte-bounded cache and a read-through cache are all this. */
interface Cache<K, V> {
    /** The value for this key, or null if it is absent or past its deadline. */
    V getIfPresent(K key);
    /** Stores a value with the cache's default time-to-live. */
    void put(K key, V value);
    /** Stores a value that dies ttlMs from now; a ttlMs of zero or less means it never dies. */
    void put(K key, V value, long ttlMs);
    /** Removes a key and returns the value it held, or null. */
    V remove(K key);
    /** How many entries are resident right now, dead-but-unread ones included. */
    int size();
    /** The hard bound on size(). */
    int capacity();
    /** Drops every entry whose deadline has passed. O(n), so it is on demand, never on the hot path. */
    void cleanUp();
    /** Hits, misses, evictions and expirations since the cache was built. */
    CacheStats stats();
}

/**
 * The rule for who leaves next. The cache tells the policy what happened; the policy names a victim. The
 * policy never touches the table -- it advises, the cache executes, so exactly one object mutates state.
 *
 * <p>Four methods rather than one, which is the honest cost of this seam: a rule that ranks keys has to see
 * every event that changes the ranking. Every method is called with the cache's lock already held, so no
 * implementation needs any synchronisation of its own.
 */
interface EvictionPolicy<K> {
    /** This key was just written (a fresh insert or a rewrite). expiresAtMs is for deadline-ordered rules. */
    void onPut(K key, long nowMs, long expiresAtMs);
    /** This key was just read and found. LRU moves it; FIFO ignores it -- that is the whole difference. */
    void onGet(K key, long nowMs);
    /** This key has left the table, for any reason. Miss this call and the policy leaks keys forever. */
    void onRemove(K key);
    /** The key to give up if room is needed now, or null when the policy is holding nothing. */
    K selectVictim(long nowMs);
    /** How many keys this policy is tracking; the cache's consistency check compares it with the table. */
    int trackedKeys();
    /** A readable name, for demos and logs. */
    default String name() { return getClass().getSimpleName(); }
}

/**
 * A doubly-linked list of keys with a map from key to node, so "move this key to the front" and "who is at
 * the back" are both a fixed number of pointer writes. Two sentinels remove every null check. LRU and FIFO
 * are the same list; they differ only in whether a read moves a key.
 */
final class KeyList<K> {
    private final class Node { K key; Node prev, next; }
    private final Node head = new Node(), tail = new Node();
    private final Map<K, Node> index = new HashMap<>();

    /** Builds an empty list: head and tail are sentinels that hold no key. */
    KeyList() { head.next = tail; tail.prev = head; }

    /** Puts the key at the front, moving it if it is already in the list. O(1). */
    void touchFirst(K key) {
        Node n = index.get(key);
        if (n == null) { n = new Node(); n.key = key; index.put(key, n); }
        else unlink(n);
        n.next = head.next; n.prev = head; head.next.prev = n; head.next = n;
    }
    /** Drops the key from the list if it is there. O(1). */
    void remove(K key) { Node n = index.remove(key); if (n != null) unlink(n); }
    /** True if this list is tracking the key. */
    boolean contains(K key) { return index.containsKey(key); }
    /** The key at the back -- the oldest by whatever "old" means here -- or null if the list is empty. */
    K last() { return tail.prev == head ? null : tail.prev.key; }
    /** How many keys are in the list. */
    int size() { return index.size(); }
    /** Back to front: the order in which these keys would be given up. */
    List<K> oldestFirst() {
        List<K> out = new ArrayList<>(index.size());
        for (Node n = tail.prev; n != head; n = n.prev) out.add(n.key);
        return out;
    }
    private void unlink(Node n) {
        if (n.prev != null) n.prev.next = n.next;
        if (n.next != null) n.next.prev = n.prev;
        n.prev = null; n.next = null;
    }
}

/** One key's deadline, with a sequence number so two keys that die in the same millisecond still order. */
record Fuse<K>(long deadlineMs, long seq, K key) { }

/**
 * Keys ordered by when they die. One index, two questions: "who dies soonest?" (an eviction order) and "is
 * anybody already dead?" (an expiry check). A TreeSet, so every operation is O(log n) -- the one structure
 * here that is not O(1), and worth saying out loud.
 */
final class DeadlineIndex<K> {
    private final TreeSet<Fuse<K>> fuses = new TreeSet<>(
            Comparator.<Fuse<K>>comparingLong(Fuse::deadlineMs).thenComparingLong(Fuse::seq));
    private final Map<K, Fuse<K>> byKey = new HashMap<>();
    private final boolean trackImmortal;
    private long seq;

    /** trackImmortal = true also indexes entries with no deadline, so this index can rank every key. */
    DeadlineIndex(boolean trackImmortal) { this.trackImmortal = trackImmortal; }

    /** Records (or re-records) this key's deadline. O(log n). */
    void put(K key, long deadlineMs) {
        remove(key);
        if (!trackImmortal && deadlineMs == Long.MAX_VALUE) return;    // no fuse, nothing to watch
        Fuse<K> f = new Fuse<>(deadlineMs, ++seq, key);
        fuses.add(f); byKey.put(key, f);
    }
    /** Forgets this key. O(log n). */
    void remove(K key) { Fuse<K> f = byKey.remove(key); if (f != null) fuses.remove(f); }
    /** The key with the soonest deadline, or null. Ties break by insertion order. */
    K earliest() { return fuses.isEmpty() ? null : fuses.first().key(); }
    /** That same key, but only if its deadline has already passed. */
    K earliestIfDue(long nowMs) {
        if (fuses.isEmpty()) return null;
        Fuse<K> f = fuses.first();
        return nowMs >= f.deadlineMs() ? f.key() : null;
    }
    /** How many keys are indexed. */
    int size() { return byKey.size(); }
}

/**
 * Least recently used: a read moves the key to the front, and the victim is whatever is at the back.
 * O(1) everywhere -- a hash lookup and six pointer writes.
 */
final class LruPolicy<K> implements EvictionPolicy<K> {
    private final KeyList<K> order = new KeyList<>();
    /** A write counts as a use, so the key goes to the front. */
    public void onPut(K key, long nowMs, long expiresAtMs) { order.touchFirst(key); }
    /** A read counts as a use: this one line is what makes it LRU and not FIFO. */
    public void onGet(K key, long nowMs) { order.touchFirst(key); }
    /** Drops the key from the order. */
    public void onRemove(K key) { order.remove(key); }
    /** The key at the back: nobody has touched it for longer. */
    public K selectVictim(long nowMs) { return order.last(); }
    /** Keys currently in the order. */
    public int trackedKeys() { return order.size(); }
    /** Coldest first: the order in which keys would be given up. */
    List<K> victimOrder() { return order.oldestFirst(); }
    public String name() { return "LRU"; }
}

/**
 * First in, first out: arrival order only. The same list as LRU with one method emptied out, which is the
 * clearest possible demonstration that the policy, not the cache, is what changes between rules.
 */
final class FifoPolicy<K> implements EvictionPolicy<K> {
    private final KeyList<K> arrival = new KeyList<>();
    /** A brand-new key joins the queue; rewriting a value does not move it back. */
    public void onPut(K key, long nowMs, long expiresAtMs) { if (!arrival.contains(key)) arrival.touchFirst(key); }
    /** A read is not a use here. One empty method is the entire difference from LRU. */
    public void onGet(K key, long nowMs) { }
    /** Drops the key from the queue. */
    public void onRemove(K key) { arrival.remove(key); }
    /** The key that arrived first. */
    public K selectVictim(long nowMs) { return arrival.last(); }
    /** Keys currently queued. */
    public int trackedKeys() { return arrival.size(); }
    public String name() { return "FIFO"; }
}

/**
 * Least frequently used, in O(1): keys are bucketed by use count and the coldest non-empty bucket is
 * remembered, so nothing is ever sorted or scanned. Inside a bucket a LinkedHashSet keeps equally cold keys
 * in arrival order, so the oldest of the coldest goes first.
 */
final class LfuPolicy<K> implements EvictionPolicy<K> {
    private final Map<K, Integer> useCount = new HashMap<>();
    private final Map<Integer, LinkedHashSet<K>> buckets = new HashMap<>();
    private int minCount = 1;

    /** A new key starts at one use; a rewrite counts as another use. */
    public void onPut(K key, long nowMs, long expiresAtMs) {
        if (useCount.containsKey(key)) { bump(key); return; }
        useCount.put(key, 1);
        buckets.computeIfAbsent(1, c -> new LinkedHashSet<>()).add(key);
        minCount = 1;                                          // a newcomer is always in the coldest bucket
    }
    /** A read moves the key one bucket up: two set operations, never a sort. */
    public void onGet(K key, long nowMs) { bump(key); }
    /** Drops the key and, if that emptied the coldest bucket, finds the new coldest. */
    public void onRemove(K key) {
        Integer c = useCount.remove(key);
        if (c == null) return;
        LinkedHashSet<K> b = buckets.get(c);
        if (b == null) return;
        b.remove(key);
        if (b.isEmpty()) { buckets.remove(c); if (c == minCount) recomputeMin(); }
    }
    /** The first key of the coldest bucket: fewest uses, and among those, the one that arrived first. */
    public K selectVictim(long nowMs) {
        LinkedHashSet<K> b = buckets.get(minCount);
        if (b == null || b.isEmpty()) { recomputeMin(); b = buckets.get(minCount); }
        return (b == null || b.isEmpty()) ? null : b.iterator().next();
    }
    /** Keys currently counted. */
    public int trackedKeys() { return useCount.size(); }
    /** How many times this key has been used; -1 if the policy has never seen it. */
    int useCountOf(K key) { return useCount.getOrDefault(key, -1); }
    public String name() { return "LFU"; }

    private void bump(K key) {
        Integer c = useCount.get(key);
        if (c == null) return;
        LinkedHashSet<K> from = buckets.get(c);
        if (from != null) {
            from.remove(key);
            if (from.isEmpty()) { buckets.remove(c); if (c == minCount) minCount = c + 1; }
        }
        useCount.put(key, c + 1);
        buckets.computeIfAbsent(c + 1, x -> new LinkedHashSet<>()).add(key);
    }
    // Only reached when an explicit remove emptied the coldest bucket. Bounded by the number of DISTINCT use
    // counts present, not by the number of keys, and never touched on the eviction path.
    private void recomputeMin() { minCount = buckets.isEmpty() ? 1 : Collections.min(buckets.keySet()); }
}

/**
 * Shortest fuse first: when the cache is full, give up whatever dies soonest. This is an eviction ORDER, not
 * expiry -- expiry always applies and lives in the cache. O(log n) per operation, the one policy here that is
 * not O(1); keys with no deadline sort last, so an immortal key goes only when nothing else is left.
 */
final class TtlPolicy<K> implements EvictionPolicy<K> {
    private final DeadlineIndex<K> deadlines = new DeadlineIndex<>(true);
    /** Records this key's deadline. */
    public void onPut(K key, long nowMs, long expiresAtMs) { deadlines.put(key, expiresAtMs); }
    /** A read does not extend a time-to-live, so there is nothing to do. */
    public void onGet(K key, long nowMs) { }
    /** Forgets the key's deadline. */
    public void onRemove(K key) { deadlines.remove(key); }
    /** The key whose deadline is soonest. */
    public K selectVictim(long nowMs) { return deadlines.earliest(); }
    /** Keys currently indexed. */
    public int trackedKeys() { return deadlines.size(); }
    public String name() { return "TTL"; }
}

/**
 * TTL as a wrapper over any other rule: if something in the cache is already dead, that goes first;
 * otherwise the wrapped rule decides. Decorator, and the reason TTL is not a fifth policy you must choose
 * instead of LRU -- ExpiryFirst(LRU), ExpiryFirst(LFU) and ExpiryFirst(FIFO) all exist. Entries with no
 * deadline are not indexed at all, so wrapping a cache that uses no TTLs costs nothing.
 */
final class ExpiryFirst<K> implements EvictionPolicy<K> {
    private final EvictionPolicy<K> inner;
    private final DeadlineIndex<K> deadlines = new DeadlineIndex<>(false);
    /** Wraps any policy; the wrapped object is handed in, never built here. */
    ExpiryFirst(EvictionPolicy<K> inner) { this.inner = Objects.requireNonNull(inner); }
    /** Records the deadline, then lets the wrapped rule do its own bookkeeping. */
    public void onPut(K key, long nowMs, long expiresAtMs) { deadlines.put(key, expiresAtMs); inner.onPut(key, nowMs, expiresAtMs); }
    /** A read does not extend a deadline, but it may still matter to the wrapped rule. */
    public void onGet(K key, long nowMs) { inner.onGet(key, nowMs); }
    /** Both indexes must drop the key, or one of them leaks. */
    public void onRemove(K key) { deadlines.remove(key); inner.onRemove(key); }
    /** A corpse if there is one, otherwise whoever the wrapped rule names. */
    public K selectVictim(long nowMs) {
        K dead = deadlines.earliestIfDue(nowMs);
        return dead != null ? dead : inner.selectVictim(nowMs);
    }
    /** The wrapped rule is the one holding every key. */
    public int trackedKeys() { return inner.trackedKeys(); }
    public String name() { return "ExpiryFirst(" + inner.name() + ")"; }
}

/**
 * The cache. It owns the table, the lock, the clock and the listeners, and it is handed an eviction policy.
 * The invariant it defends: the table and the policy always name exactly the same set of keys, and the number
 * of entries never exceeds the capacity -- not even for an instant in the middle of a put.
 */
final class PolicyCache<K, V> implements Cache<K, V> {
    private final int capacity;
    /** Insertion-ordered only so that re-indexing on a policy swap is deterministic and testable. */
    private final Map<K, CacheEntry<V>> table = new LinkedHashMap<>();
    private final ReentrantLock lock = new ReentrantLock();
    private final List<RemovalListener<K, V>> listeners = new CopyOnWriteArrayList<>();
    private final AtomicLong hits = new AtomicLong(), misses = new AtomicLong();
    private final AtomicLong evictions = new AtomicLong(), expirations = new AtomicLong();
    private EvictionPolicy<K> policy;
    private Clock clock;
    private final long defaultTtlMs;

    /** Built by CacheBuilder, which is the only place the pieces are assembled. */
    PolicyCache(int capacity, EvictionPolicy<K> policy, Clock clock, long defaultTtlMs) {
        if (capacity < 1) throw new IllegalArgumentException("capacity must be at least 1");
        this.capacity = capacity;
        this.policy = Objects.requireNonNull(policy, "policy");
        this.clock = Objects.requireNonNull(clock, "clock");
        this.defaultTtlMs = defaultTtlMs;
    }

    /** Adds somebody who wants to hear about departures. Listeners are called after the lock is released. */
    void addListener(RemovalListener<K, V> l) { listeners.add(Objects.requireNonNull(l)); }

    /**
     * The value for this key, or null. A read past the deadline is a miss: the dead entry is dropped here and
     * reported as EXPIRED, so a stale value can never be handed back.
     */
    public V getIfPresent(K key) {
        Objects.requireNonNull(key, "key");
        long now = clock.nowMs();
        List<Removal<K, V>> pending = new ArrayList<>(1);
        V out = null;
        boolean hit = false, dead = false;
        lock.lock();
        try {
            CacheEntry<V> e = table.get(key);
            if (e != null && e.expired(now)) {
                table.remove(key);
                policy.onRemove(key);
                pending.add(new Removal<>(key, e.value, RemovalCause.EXPIRED));
                dead = true;
            } else if (e != null) {
                e.lastAccessMs = now;
                policy.onGet(key, now);                        // a read is a write to the ranking
                out = e.value;
                hit = true;
            }
        } finally {
            lock.unlock();
        }
        if (hit) hits.incrementAndGet(); else misses.incrementAndGet();
        if (dead) expirations.incrementAndGet();
        fire(pending);
        return out;
    }

    /** Stores a value with the cache's default time-to-live. */
    public void put(K key, V value) { put(key, value, defaultTtlMs); }

    /**
     * Stores a value that dies ttlMs from now (a ttlMs of zero or less means never). The order IS the design: work
     * the deadline outside the lock; take the lock; evict BEFORE admitting, because under LFU a newcomer
     * arrives at one use, is instantly the coldest key, and would otherwise evict itself; write the entry;
     * unlock; only then tell the listeners.
     */
    public void put(K key, V value, long ttlMs) {
        Objects.requireNonNull(key, "key");
        Objects.requireNonNull(value, "null value: null is how this cache reports a miss");
        long now = clock.nowMs();
        long expiresAt = ttlMs <= 0 ? Long.MAX_VALUE : now + ttlMs;
        List<Removal<K, V>> pending = new ArrayList<>(2);
        int evicted = 0, expired = 0;
        lock.lock();
        try {
            CacheEntry<V> old = table.get(key);
            if (old != null) {                                  // a rewrite: the count does not grow
                table.put(key, new CacheEntry<>(value, now, expiresAt));
                policy.onPut(key, now, expiresAt);
                pending.add(new Removal<>(key, old.value, RemovalCause.REPLACED));
            } else {
                while (table.size() >= capacity) {              // evict first, admit second
                    K victim = policy.selectVictim(now);
                    if (victim == null) break;                  // a policy holding nothing has nothing to give
                    CacheEntry<V> gone = table.remove(victim);
                    policy.onRemove(victim);                    // both indexes drop it, or the policy leaks
                    if (gone == null) continue;                 // the policy named a key the table never had
                    boolean wasDead = gone.expired(now);
                    pending.add(new Removal<>(victim, gone.value,
                            wasDead ? RemovalCause.EXPIRED : RemovalCause.CAPACITY));
                    if (wasDead) expired++; else evicted++;
                }
                table.put(key, new CacheEntry<>(value, now, expiresAt));
                policy.onPut(key, now, expiresAt);
            }
        } finally {
            lock.unlock();
        }
        if (evicted > 0) evictions.addAndGet(evicted);
        if (expired > 0) expirations.addAndGet(expired);
        fire(pending);
    }

    /** Removes a key and returns what it held. The cause is EXPLICIT: the caller asked, whatever the clock says. */
    public V remove(K key) {
        Objects.requireNonNull(key, "key");
        List<Removal<K, V>> pending = new ArrayList<>(1);
        V out = null;
        lock.lock();
        try {
            CacheEntry<V> e = table.remove(key);
            if (e != null) {
                policy.onRemove(key);
                pending.add(new Removal<>(key, e.value, RemovalCause.EXPLICIT));
                out = e.value;
            }
        } finally {
            lock.unlock();
        }
        fire(pending);
        return out;
    }

    /** Entries resident right now, including ones past their deadline that nobody has read yet. */
    public int size() { lock.lock(); try { return table.size(); } finally { lock.unlock(); } }

    /** The hard bound. */
    public int capacity() { return capacity; }

    /** Drops every dead entry in one pass. O(n), which is why it is on demand and not on the read path. */
    public void cleanUp() {
        long now = clock.nowMs();
        List<Removal<K, V>> pending = new ArrayList<>();
        lock.lock();
        try {
            for (Iterator<Map.Entry<K, CacheEntry<V>>> it = table.entrySet().iterator(); it.hasNext(); ) {
                Map.Entry<K, CacheEntry<V>> en = it.next();
                if (en.getValue().expired(now)) {
                    it.remove();
                    policy.onRemove(en.getKey());
                    pending.add(new Removal<>(en.getKey(), en.getValue().value, RemovalCause.EXPIRED));
                }
            }
        } finally {
            lock.unlock();
        }
        if (!pending.isEmpty()) expirations.addAndGet(pending.size());
        fire(pending);
    }

    /** Hits, misses, evictions and expirations. Counted outside the lock, so they are approximate under load. */
    public CacheStats stats() {
        return new CacheStats(hits.get(), misses.get(), evictions.get(), expirations.get());
    }

    /**
     * Swaps the rule at runtime and returns the old one. Every live key is handed to the new policy as a
     * fresh insert under the same lock, so no entry is lost and no reader ever sees a cache without a rule.
     * What does not survive is the ranking: the new policy starts with no history. That is the honest trade,
     * and it is better said out loud than papered over by pretending recency counts carry across.
     */
    EvictionPolicy<K> setPolicy(EvictionPolicy<K> next) {
        Objects.requireNonNull(next, "policy");
        long now = clock.nowMs();
        lock.lock();
        try {
            EvictionPolicy<K> old = policy;
            for (Map.Entry<K, CacheEntry<V>> en : table.entrySet())
                next.onPut(en.getKey(), now, en.getValue().expiresAtMs);
            policy = next;
            return old;
        } finally {
            lock.unlock();
        }
    }

    /** The rule in force right now. */
    EvictionPolicy<K> policy() { lock.lock(); try { return policy; } finally { lock.unlock(); } }

    /** Replaces the clock. Tests use this; production hands one in through the builder. */
    void setClock(Clock c) { lock.lock(); try { this.clock = Objects.requireNonNull(c); } finally { lock.unlock(); } }

    /** The invariant, checkable: the policy tracks exactly as many keys as the table holds. */
    boolean consistent() {
        lock.lock();
        try { return policy.trackedKeys() == table.size(); } finally { lock.unlock(); }
    }

    /** A snapshot of the resident keys in insertion order, for demos and tests. */
    Set<K> keys() { lock.lock(); try { return new LinkedHashSet<>(table.keySet()); } finally { lock.unlock(); } }

    // A listener is caller code: it may do I/O, throw, or call straight back into this cache. All three are
    // safe out here and none of them are safe inside the lock, so departures are collected under the lock and
    // delivered once it is gone.
    private void fire(List<Removal<K, V>> pending) {
        if (pending.isEmpty() || listeners.isEmpty()) return;
        for (Removal<K, V> r : pending)
            for (RemovalListener<K, V> l : listeners)
                try { l.onRemoval(r.key(), r.value(), r.cause()); }
                catch (RuntimeException ignored) { /* a broken listener is the listener's problem */ }
    }
}

/**
 * The one place the pieces are assembled: capacity, policy, clock, default TTL, listeners. Six optional knobs
 * is exactly when a builder earns its place -- which is why Guava ships CacheBuilder and Caffeine ships
 * Caffeine.newBuilder().
 */
final class CacheBuilder<K, V> {
    private int capacity = 128;
    private EvictionPolicy<K> policy;
    private Clock clock = new SystemClock();
    private long ttlMs = 0;
    private final List<RemovalListener<K, V>> listeners = new ArrayList<>();

    /** Starts a builder; the type arguments are given at the call site. */
    static <K, V> CacheBuilder<K, V> newBuilder() { return new CacheBuilder<>(); }
    /** The hard bound on the number of entries. */
    CacheBuilder<K, V> capacity(int n) { this.capacity = n; return this; }
    /** The eviction rule. Defaults to LRU when nothing is said. */
    CacheBuilder<K, V> policy(EvictionPolicy<K> p) { this.policy = p; return this; }
    /** Where time comes from. Defaults to the wall clock. */
    CacheBuilder<K, V> clock(Clock c) { this.clock = c; return this; }
    /** A default time-to-live for entries written without one. */
    CacheBuilder<K, V> ttlMs(long ms) { this.ttlMs = ms; return this; }
    /** Somebody to tell when an entry leaves. */
    CacheBuilder<K, V> listener(RemovalListener<K, V> l) { this.listeners.add(l); return this; }
    /** Assembles the cache. The cache itself never names a policy class. */
    PolicyCache<K, V> build() {
        EvictionPolicy<K> p = policy != null ? policy : new LruPolicy<>();
        PolicyCache<K, V> c = new PolicyCache<>(capacity, p, clock, ttlMs);
        for (RemovalListener<K, V> l : listeners) c.addListener(l);
        return c;
    }
}

/** The demo: one access trace through four rules, expiry, a runtime policy swap, and a fifty-thread race. */
public class Main {

    /**
     * One fixed access trace, replayed through whichever policy is handed in, with a listener that records
     * what left. Identical calls, identical timing; the only difference is the rule.
     *
     * <p>t=0 put A(ttl 60s), t=1s put B(ttl 50s), t=2s get B, t=3s put C(ttl 40s), t=4s put D(ttl 5s),
     * t=5s get A, then (after extraWaitMs) put E into a cache of four.
     */
    static String replay(EvictionPolicy<String> policy, ManualClock clock, long extraWaitMs) {
        List<String> gone = new ArrayList<>();
        PolicyCache<String, String> c = CacheBuilder.<String, String>newBuilder()
                .capacity(4).policy(policy).clock(clock)
                .listener((k, v, cause) -> gone.add(k + " (" + cause + ")"))
                .build();
        clock.setTo(0);
        c.put("A", "alpha", 60_000);
        clock.advance(1_000); c.put("B", "bravo", 50_000);
        clock.advance(1_000); c.getIfPresent("B");
        clock.advance(1_000); c.put("C", "charlie", 40_000);
        clock.advance(1_000); c.put("D", "delta", 5_000);
        clock.advance(1_000); c.getIfPresent("A");
        clock.advance(1_000 + extraWaitMs);
        c.put("E", "echo");                                    // the cache is full: the policy decides
        return gone.isEmpty() ? "nobody" : gone.get(0);
    }

    /** Runs the demo and then a many-thread race that proves the size bound and the table/policy agreement. */
    public static void main(String[] args) throws Exception {
        ManualClock clock = new ManualClock(0);

        System.out.println("== the same access trace, four rules, four victims ==");
        System.out.println("   put A,B; get B; put C,D; get A; then put E into a cache of four");
        System.out.printf("   %-20s evicts %s%n", "FIFO", replay(new FifoPolicy<>(), clock, 0));
        System.out.printf("   %-20s evicts %s%n", "LRU", replay(new LruPolicy<>(), clock, 0));
        System.out.printf("   %-20s evicts %s%n", "LFU", replay(new LfuPolicy<>(), clock, 0));
        System.out.printf("   %-20s evicts %s%n", "TTL (shortest fuse)", replay(new TtlPolicy<>(), clock, 0));

        System.out.println();
        System.out.println("== TTL as a decorator: the same trace, but put E four seconds later, when D is dead ==");
        System.out.printf("   %-22s evicts %s%n", "LRU", replay(new LruPolicy<>(), clock, 4_000));
        System.out.printf("   %-22s evicts %s%n", "ExpiryFirst(LRU)",
                          replay(new ExpiryFirst<>(new LruPolicy<>()), clock, 4_000));
        System.out.printf("   %-22s evicts %s%n", "ExpiryFirst(LFU)",
                          replay(new ExpiryFirst<>(new LfuPolicy<>()), clock, 4_000));

        System.out.println();
        System.out.println("== expiry is not eviction: a dead entry is a miss in a cache that is 25% full ==");
        clock.setTo(0);
        PolicyCache<String, String> ttl = CacheBuilder.<String, String>newBuilder()
                .capacity(4).policy(new LruPolicy<>()).clock(clock)
                .listener((k, v, cause) -> System.out.println("   listener: " + k + " left because " + cause))
                .build();
        ttl.put("session", "harish", 30 * 60_000L);            // a thirty-minute session
        System.out.println("   at  0 min    get session -> " + ttl.getIfPresent("session"));
        clock.advance(29 * 60_000L);
        System.out.println("   at 29 min    get session -> " + ttl.getIfPresent("session"));
        clock.advance(2 * 60_000L);
        System.out.println("   at 31 min    get session -> " + ttl.getIfPresent("session")
                           + "   (size now " + ttl.size() + ")");

        System.out.println();
        System.out.println("== swapping the rule at runtime keeps every entry ==");
        clock.setTo(0);
        PolicyCache<String, String> live = CacheBuilder.<String, String>newBuilder()
                .capacity(3).policy(new LruPolicy<>()).clock(clock).build();
        live.put("x", "1"); live.put("y", "2"); live.put("z", "3");
        live.getIfPresent("x"); live.getIfPresent("x"); live.getIfPresent("y");
        System.out.println("   before swap: " + live.policy().name() + ", keys " + live.keys());
        EvictionPolicy<String> was = live.setPolicy(new LfuPolicy<>());
        System.out.println("   after swap:  " + live.policy().name() + ", keys " + live.keys()
                           + "  (was " + was.name() + "; x still reads " + live.getIfPresent("x") + ")");

        System.out.println();
        System.out.println("== the race: 50 threads, capacity 100, 500 distinct keys ==");
        PolicyCache<Integer, Integer> hot = CacheBuilder.<Integer, Integer>newBuilder()
                .capacity(100).policy(new LruPolicy<>()).build();
        AtomicLong overflow = new AtomicLong();
        int threads = 50, opsEach = 400;
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> all = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            final int seed = t;
            all.add(pool.submit(() -> {
                go.await();
                Random rnd = new Random(seed);
                for (int i = 0; i < opsEach; i++) {
                    int k = rnd.nextInt(500);
                    if ((i & 3) == 0) hot.put(k, k * 7); else hot.getIfPresent(k);
                    if (hot.size() > hot.capacity()) overflow.incrementAndGet();
                }
                return null;
            }));
        }
        go.countDown();
        for (Future<?> f : all) f.get();
        pool.shutdown();
        System.out.println("   " + (threads * opsEach) + " operations, size " + hot.size() + "/" + hot.capacity()
                           + ", times seen over capacity: " + overflow.get());
        System.out.println("   table and policy agree: " + hot.consistent());
        System.out.println("   " + hot.stats());
    }
}
