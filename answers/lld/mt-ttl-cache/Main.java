import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Why an entry left the map. The listener is told the reason, so a metric can tell "it timed out"
 * from "the sweeper reclaimed it" from "somebody overwrote it" from "somebody deleted it".
 */
enum RemovalCause { EXPIRED, SWEPT, REPLACED, EXPLICIT }

/** Where time comes from. One method, handed in, so a test can jump an hour instead of sleeping an hour. */
interface Clock { long nowMs(); }

/** The real clock. nanoTime, not currentTimeMillis: a clock correction must never make a TTL run backwards. */
final class SystemClock implements Clock {
    /** Milliseconds on a monotonic timeline. Only differences mean anything; the origin is arbitrary. */
    public long nowMs() { return System.nanoTime() / 1_000_000L; }
}

/** A clock a test drives by hand. Thread-safe, because race tests read it from many threads while advancing it. */
final class ManualClock implements Clock {
    private final AtomicLong nowMs = new AtomicLong(1_000_000L);
    /** The time this clock is standing at. */
    public long nowMs() { return nowMs.get(); }
    /** Jump forward. Nothing expires as a side effect: expiry is decided by whoever reads the entry next. */
    public void advance(long ms) { nowMs.addAndGet(ms); }
}

/** How long a key is allowed to live, in milliseconds. This is the rule an interviewer changes mid-round. */
interface TtlPolicy<K> { long ttlMsFor(K key); }

/** One TTL for every key. Zero or less means "do not cache this at all": every call goes to the loader. */
final class FixedTtl<K> implements TtlPolicy<K> {
    private final long ttlMs;
    FixedTtl(long ttlMs) { this.ttlMs = ttlMs; }
    /** The same number for every key. */
    public long ttlMsFor(K key) { return ttlMs; }
}

/**
 * Decorator over any TTL rule: shortens each TTL by a random slice, up to percent of it.
 * A million keys written in the same minute would otherwise all die in the same millisecond and
 * send a million loads at the database at once. Jitter spreads those deadlines over a window.
 */
final class JitteredTtl<K> implements TtlPolicy<K> {
    private final TtlPolicy<K> base;
    private final int percent;
    JitteredTtl(TtlPolicy<K> base, int percent) {
        this.base = Objects.requireNonNull(base);
        if (percent < 0 || percent > 90) throw new IllegalArgumentException("jitter must be 0..90%");
        this.percent = percent;
    }
    /** The wrapped rule's answer, minus up to percent of it. Never lengthens a TTL, so it cannot serve stale. */
    public long ttlMsFor(K key) {
        long ttl = base.ttlMsFor(key);
        if (ttl <= 0) return ttl;
        long span = ttl * percent / 100;
        return span <= 0 ? ttl : ttl - ThreadLocalRandom.current().nextLong(span + 1);
    }
}

/** Told after an entry has left the map, outside every lock. A listener that throws cannot break the cache. */
interface RemovalListener<K, V> { void onRemoval(K key, V value, RemovalCause cause); }

/** What a miss calls: a database read, an HTTP call. Slow, allowed to throw, never called with a lock held. */
interface Loader<K, V> { V load(K key); }

/**
 * A value and the instant it stops being servable. Every field is final, so the memory model freezes them
 * when the constructor returns: a thread that finds this entry in the map can never see a half-built one.
 * That is safe publication, and it is why reading an entry needs no lock of any kind.
 * equals() is deliberately left as identity: map.remove(key, entry) must mean THIS object and no other,
 * which is what stops a sweeper from deleting a value that was refreshed while the sweeper was looking.
 */
final class CacheEntry<V> {
    final V value;
    final long loadedAtMs;
    final long expiresAtMs;
    CacheEntry(V value, long loadedAtMs, long expiresAtMs) {
        this.value = value; this.loadedAtMs = loadedAtMs; this.expiresAtMs = expiresAtMs;
    }
    /** Live means the clock has not reached the deadline yet. Strictly before, so a TTL of zero is born dead. */
    boolean isLive(long nowMs) { return nowMs < expiresAtMs; }
}

/** What a caller binds to, so a test can hand in a fake and the implementation can be swapped underneath. */
interface Cache<K, V> {
    /** Store a value with the TTL the policy gives this key. */
    void put(K key, V value);
    /** The value, or null if it is absent or its deadline has passed. An expired value is never returned. */
    V get(K key);
    /**
     * The value; on a miss exactly one thread per key runs the loader and the rest ride its result.
     * This form waits as long as the loader takes and ignores an interrupt while it waits. That is the
     * convenience, and the three-argument form below is the one to use when either matters.
     */
    V getOrLoad(K key, Loader<K, V> loader);
    /**
     * The same, with a ceiling on how long THIS caller will wait for somebody else's load, and an interrupt
     * that is honoured. Both exceptions are checked on purpose: a caller that asked for a deadline has to
     * decide what to do when it passes. The deadline bounds the wait only; a thread that ends up running the
     * loader itself is bounded by wrapping the loader (BoundedLoader in Extensions.java).
     */
    V getOrLoad(K key, Loader<K, V> loader, long timeoutMs) throws TimeoutException, InterruptedException;
    /** Remove a key. True if something was there. */
    boolean invalidate(K key);
    /** How many entries the map holds, including ones that expired but have not been reclaimed yet. */
    int size();
}

/**
 * The thread-safe cache. Two invariants, and everything in the file exists to hold one of them:
 *   1. a value whose deadline has passed is never handed to a caller, and is never deleted if it was refreshed;
 *   2. when many threads miss the same key at once, the loader runs once and the others share its result.
 * There is no lock of our own anywhere in this class. The map's own per-bin locks are the only ones,
 * they are held for about a hundred nanoseconds by put and remove, and the slow loader runs outside all of them.
 */
final class TtlCache<K, V> implements Cache<K, V> {
    /** The store. A read takes no lock at all; a write takes the lock of one bin out of thousands. */
    private final ConcurrentHashMap<K, CacheEntry<V>> map = new ConcurrentHashMap<>();
    /** One claim per key that is being loaded right now. Winning a claim is a compare-and-set, not a lock. */
    private final ConcurrentHashMap<K, CompletableFuture<CacheEntry<V>>> loading = new ConcurrentHashMap<>();
    /** Copy-on-write, so firing a removal never blocks a thread that is adding a listener. */
    private final List<RemovalListener<K, V>> listeners = new CopyOnWriteArrayList<>();

    private volatile TtlPolicy<K> ttl;
    private volatile Clock clock = new SystemClock();
    private ScheduledExecutorService sweeper;      // guarded by this; null until startSweeper is called

    /** LongAdder, not AtomicInteger: fifty thousand reads a second on one counter is itself a contention point. */
    final LongAdder hits = new LongAdder(), misses = new LongAdder(), loadCalls = new LongAdder();
    final LongAdder joins = new LongAdder(), expiredOnRead = new LongAdder(), sweptCount = new LongAdder();
    /** How often a waiter was handed a value that had already died while it waited: the retry loop, counted. */
    final LongAdder staleJoins = new LongAdder();

    /** A cache with one TTL for every key and the real clock. Collaborators are replaced with configure(). */
    TtlCache(long defaultTtlMs) { this.ttl = new FixedTtl<>(defaultTtlMs); }

    /** Hand in the rules. The cache never builds them, which is what lets a test hand in a clock it controls. */
    void configure(TtlPolicy<K> ttl, Clock clock) {
        this.ttl = Objects.requireNonNull(ttl);
        this.clock = Objects.requireNonNull(clock);
    }

    /** Add someone who wants to hear about removals: metrics, a log line, closing a socket. */
    void addListener(RemovalListener<K, V> listener) { listeners.add(Objects.requireNonNull(listener)); }

    /** The clock the cache is reading. Handy in a test that needs the same instant the cache sees. */
    Clock clock() { return clock; }

    /** Absolute deadline for a key stored now. A TTL that overflows a long is treated as "never expires". */
    private long deadline(long nowMs, long ttlMs) {
        long d = nowMs + ttlMs;
        return d < nowMs ? Long.MAX_VALUE : d;
    }

    /**
     * Store a value. A TTL of zero or less means "do not cache", so put removes whatever was there
     * rather than storing something born dead. Any replaced entry is announced after the map write.
     */
    public void put(K key, V value) {
        Objects.requireNonNull(key, "key"); Objects.requireNonNull(value, "value");
        long ttlMs = ttl.ttlMsFor(key);
        if (ttlMs <= 0) { invalidateAs(key, RemovalCause.REPLACED); return; }
        long now = clock.nowMs();
        CacheEntry<V> prev = map.put(key, new CacheEntry<>(value, now, deadline(now, ttlMs)));
        if (prev != null) fire(key, prev.value, RemovalCause.REPLACED);
    }

    /**
     * The value, or null. The order matters: read the entry first, then read the clock, then decide.
     * If the deadline has passed the entry is reclaimed with a compare-and-remove on the entry itself,
     * so a value that another thread installed in the meantime survives. An expired value is never returned.
     */
    public V get(K key) {
        CacheEntry<V> e = map.get(key);                       // no lock: a volatile read of one array slot
        if (e == null) { misses.increment(); return null; }
        long now = clock.nowMs();
        if (e.isLive(now)) { hits.increment(); return e.value; }
        if (map.remove(key, e)) {                             // identity, not key: never delete a fresher entry
            expiredOnRead.increment();
            fire(key, e.value, RemovalCause.EXPIRED);
        }
        misses.increment();
        return null;
    }

    /**
     * The value, loading it on a miss. Exactly one thread per key runs the loader; the others wait on its
     * result holding no lock. This form waits as long as the load takes and cannot be interrupted.
     */
    public V getOrLoad(K key, Loader<K, V> loader) {
        try {
            return valueOrLoad(key, loader, -1L);             // -1 means join(): no deadline, no interrupt
        } catch (TimeoutException | InterruptedException neither) {
            throw new AssertionError("join() throws neither", neither);
        }
    }

    /** The value, giving up after timeoutMs of waiting for another thread's load, and honouring an interrupt. */
    public V getOrLoad(K key, Loader<K, V> loader, long timeoutMs) throws TimeoutException, InterruptedException {
        if (timeoutMs < 0) throw new IllegalArgumentException("timeoutMs must not be negative");
        return valueOrLoad(key, loader, timeoutMs);
    }

    /**
     * One loop for both forms. The loop goes round a second time only when the winner's value had already
     * died by the time the waiter was woken, which needs a TTL shorter than a load; each extra round either
     * hands back a live value or makes this thread the next loader, so nobody spins without doing work.
     */
    private V valueOrLoad(K key, Loader<K, V> loader, long timeoutMs) throws TimeoutException, InterruptedException {
        Objects.requireNonNull(key, "key"); Objects.requireNonNull(loader, "loader");
        if (ttl.ttlMsFor(key) <= 0) { loadCalls.increment(); return require(key, loader.load(key)); }
        long deadlineNs = timeoutMs < 0 ? 0L : System.nanoTime() + timeoutMs * 1_000_000L;
        while (true) {
            V hit = get(key);
            if (hit != null) return hit;
            CompletableFuture<CacheEntry<V>> mine = new CompletableFuture<>();
            CompletableFuture<CacheEntry<V>> running = loading.putIfAbsent(key, mine);
            if (running == null) return loadAndPublish(key, loader, mine);   // this thread won the claim
            joins.increment();
            CacheEntry<V> e = timeoutMs < 0 ? await(running)  // a loser: no lock held, just a handle on a result
                                            : awaitUntil(running, deadlineNs);
            if (e.isLive(clock.nowMs())) return e.value;
            staleJoins.increment();          // the value died while we waited: go round, and one of us reloads
        }
    }

    /**
     * The winner's path, and the order is the whole design: call the loader with nothing held, store the
     * entry, and only then release the waiters, so a waiter can never see a value the map does not have.
     * If the loader throws, nothing was written, every waiter is told, and the claim is released in the
     * finally block, so the very next caller starts a clean load.
     */
    private V loadAndPublish(K key, Loader<K, V> loader, CompletableFuture<CacheEntry<V>> mine) {
        try {
            loadCalls.increment();
            V value = require(key, loader.load(key));         // the slow call: outside every lock in the process
            long now = clock.nowMs();
            CacheEntry<V> fresh = new CacheEntry<>(value, now, deadline(now, ttl.ttlMsFor(key)));
            map.put(key, fresh);                              // publish to the map first ...
            mine.complete(fresh);                             // ... then wake everyone who is waiting
            return value;
        } catch (RuntimeException | Error ex) {
            mine.completeExceptionally(ex);                   // nothing stored; every waiter sees this failure
            throw ex;
        } finally {
            loading.remove(key, mine);                        // identity again: never drop somebody else's claim
        }
    }

    /** Waiting on the winner. Unwraps the wrapper CompletableFuture puts around a failure. */
    private static <T> T await(CompletableFuture<T> f) {
        try {
            return f.join();
        } catch (CompletionException ce) {
            Throwable cause = ce.getCause();
            if (cause instanceof RuntimeException re) throw re;
            if (cause instanceof Error err) throw err;
            throw ce;
        }
    }

    /**
     * The same wait with a deadline, which is also the only form that answers an interrupt. InterruptedException
     * is rethrown rather than swallowed: the thread that asked for a bounded wait is the thread that must decide.
     */
    private static <T> T awaitUntil(CompletableFuture<T> f, long deadlineNs)
            throws TimeoutException, InterruptedException {
        long leftNs = deadlineNs - System.nanoTime();
        if (leftNs <= 0) throw new TimeoutException("gave up waiting for another thread's load");
        try {
            return f.get(leftNs, TimeUnit.NANOSECONDS);
        } catch (ExecutionException ee) {
            Throwable cause = ee.getCause();
            if (cause instanceof RuntimeException re) throw re;
            if (cause instanceof Error err) throw err;
            throw new CompletionException(cause);
        }
    }

    /** A loader that returns null is a bug, not a miss; negative caching is an explicit feature, not a default. */
    private V require(K key, V value) {
        if (value == null) throw new IllegalStateException("loader returned null for key " + key);
        return value;
    }

    /** Remove a key because a caller said so. True if something was actually removed. */
    public boolean invalidate(K key) { return invalidateAs(key, RemovalCause.EXPLICIT); }

    private boolean invalidateAs(K key, RemovalCause cause) {
        CacheEntry<V> gone = map.remove(key);
        if (gone == null) return false;
        fire(key, gone.value, cause);
        return true;
    }

    /** Entries held, including ones past their deadline that nobody has read or swept yet. An estimate. */
    public int size() { return map.size(); }

    /** The exact number of entries that would still be served. O(n): for tests and metrics, not the hot path. */
    int liveSize() {
        long now = clock.nowMs();
        int n = 0;
        for (CacheEntry<V> e : map.values()) if (e.isLive(now)) n++;
        return n;
    }

    /**
     * One sweep: reclaim every entry whose deadline has passed, and nothing else. The iterator is weakly
     * consistent, so it never throws and may miss a key added mid-pass, which is fine: the next pass gets it.
     * The compare-and-remove is the point of the method. A plain map.remove(key) here would delete the value
     * a refresh installed in the microsecond between reading the entry and removing it.
     */
    int sweepOnce() {
        int removed = 0;
        for (Map.Entry<K, CacheEntry<V>> en : map.entrySet()) {
            CacheEntry<V> e = en.getValue();
            if (e.isLive(clock.nowMs())) continue;
            if (map.remove(en.getKey(), e)) {
                removed++;
                sweptCount.increment();
                fire(en.getKey(), e.value, RemovalCause.SWEPT);
            }
        }
        return removed;
    }

    /**
     * Start the background sweeper: one daemon thread for the whole cache, not one timer per entry.
     * Fixed delay, not fixed rate, so a slow pass can never queue passes up behind itself. Idempotent.
     */
    synchronized void startSweeper(long everyMs) {
        if (sweeper != null) return;
        sweeper = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "ttl-sweeper");
            t.setDaemon(true);                                // the JVM must not be held open by a cache
            return t;
        });
        sweeper.scheduleWithFixedDelay(() -> {
            try { sweepOnce(); } catch (RuntimeException ignored) { /* one bad pass must not kill the thread */ }
        }, everyMs, everyMs, TimeUnit.MILLISECONDS);
    }

    /** Stop the sweeper. The cache still works afterwards: expiry on read never needed the thread. */
    synchronized void close() {
        if (sweeper != null) { sweeper.shutdownNow(); sweeper = null; }
    }

    /**
     * Announce a removal. Always after the map has been changed and never with a lock held, each listener
     * in its own try/catch, so a metrics client that is down cannot break a put or stall the sweeper.
     */
    private void fire(K key, V value, RemovalCause cause) {
        for (RemovalListener<K, V> l : listeners) {
            try { l.onRemoval(key, value, cause); }
            catch (RuntimeException ignored) { /* a broken listener is not the cache's problem */ }
        }
    }

    /** The counters an interviewer asks for: hit rate first, then how many loads the claim saved. */
    String stats() {
        long h = hits.sum(), m = misses.sum();
        long rate = (h + m) == 0 ? 0 : (h * 100) / (h + m);
        return "hits=" + h + " misses=" + m + " hitRate=" + rate + "%"
             + " loads=" + loadCalls.sum() + " joinedALoad=" + joins.sum()
             + " staleJoins=" + staleJoins.sum()
             + " expiredOnRead=" + expiredOnRead.sum() + " swept=" + sweptCount.sum();
    }
}

/**
 * A demo of the three things that make this cache different from a map, and then the race that
 * proves the second invariant: fifty threads, one cold key, and exactly one call to the loader.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        // ---------- 1. an expired value is never handed back, proved with a clock we drive by hand
        ManualClock clock = new ManualClock();
        TtlCache<String, String> cache = new TtlCache<>(60_000);
        cache.configure(new FixedTtl<>(60_000), clock);
        cache.addListener((k, v, cause) -> System.out.println("  removed[" + cause + "] " + k + "=" + v));

        cache.put("price:AAPL", "232.50");
        System.out.println("TTL: read at t+0s      = " + cache.get("price:AAPL"));
        clock.advance(59_000);
        System.out.println("TTL: read at t+59s     = " + cache.get("price:AAPL"));
        clock.advance(2_000);
        System.out.println("TTL: read at t+61s     = " + cache.get("price:AAPL") + "   (deadline passed)");
        System.out.println("TTL: entries held      = " + cache.size() + "   (the read reclaimed it)");

        // ---------- 2. the sweeper reclaims the dead and leaves a refreshed key alone
        cache.put("short", "a"); cache.put("long", "b");
        clock.advance(30_000);
        cache.put("long", "b2");                            // refreshed: its deadline is now 30s later than short's
        clock.advance(31_000);                              // short is dead, long is not
        System.out.println("SWEEP: reclaimed       = " + cache.sweepOnce() + " entry");
        System.out.println("SWEEP: short           = " + cache.get("short") + "   long = " + cache.get("long"));

        // ---------- 3. fifty threads miss one cold key at the same instant: the loader must run ONCE
        TtlCache<String, String> hot = new TtlCache<>(60_000);
        hot.configure(new FixedTtl<>(60_000), new SystemClock());
        AtomicInteger databaseCalls = new AtomicInteger();
        Loader<String, String> slowDatabase = key -> {
            databaseCalls.incrementAndGet();
            try { Thread.sleep(40); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            return "row-for-" + key;
        };

        int threads = 50;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<String>> answers = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            answers.add(pool.submit(() -> {
                go.await();                                  // everybody misses at the same instant
                return hot.getOrLoad("user:42", slowDatabase);
            }));
        }
        go.countDown();
        Set<String> distinct = new HashSet<>();
        for (Future<String> f : answers) distinct.add(f.get(30, TimeUnit.SECONDS));
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);

        System.out.println("RACE: threads          = " + threads);
        System.out.println("RACE: loader calls     = " + databaseCalls.get() + "   (the other " + (threads - 1)
            + " either rode it or read what it stored)");
        System.out.println("RACE: distinct answers = " + distinct + "   size " + distinct.size());
        System.out.println("RACE: " + hot.stats());

        // ---------- 4. the same race over ten cold keys: the claim is per key, not one global gate
        TtlCache<String, String> many = new TtlCache<>(60_000);
        many.configure(new FixedTtl<>(60_000), new SystemClock());
        AtomicInteger calls = new AtomicInteger();
        Loader<String, String> counted = key -> {
            calls.incrementAndGet();
            try { Thread.sleep(20); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            return "v-" + key;
        };
        ExecutorService pool2 = Executors.newFixedThreadPool(16);
        CountDownLatch go2 = new CountDownLatch(1);
        List<Future<String>> got = new ArrayList<>();
        for (int i = 0; i < threads; i++) {
            final String key = "k" + (i % 10);
            got.add(pool2.submit(() -> { go2.await(); return many.getOrLoad(key, counted); }));
        }
        go2.countDown();
        for (Future<String> f : got) f.get(20, TimeUnit.SECONDS);
        pool2.shutdown();
        pool2.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("KEYS: 50 threads over 10 cold keys -> loader calls = " + calls.get() + ", entries = " + many.size());

        // ---------- 5. a waiter that will not wait: one thread holds the loader, another gives up after 50 ms
        TtlCache<String, String> stuckCache = new TtlCache<>(60_000);
        stuckCache.configure(new FixedTtl<>(60_000), new SystemClock());
        CountDownLatch release = new CountDownLatch(1), loaderRunning = new CountDownLatch(1);
        Thread winner = new Thread(() -> stuckCache.getOrLoad("wedged", key -> {
            loaderRunning.countDown();
            try { release.await(20, TimeUnit.SECONDS); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            return "arrived-late";
        }), "the-winner");
        winner.start();
        loaderRunning.await(10, TimeUnit.SECONDS);
        try {
            stuckCache.getOrLoad("wedged", key -> "never called", 50);
            System.out.println("WAIT: the bounded caller did not time out   (unexpected)");
        } catch (TimeoutException te) {
            System.out.println("WAIT: bounded caller gave up after 50 ms while the loader was still running");
        }
        release.countDown(); winner.join(20_000);
        System.out.println("WAIT: and the value the winner loaded is there = " + stuckCache.get("wedged"));

        cache.close(); hot.close(); many.close(); stuckCache.close();
    }
}
