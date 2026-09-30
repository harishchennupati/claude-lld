import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

// ---- ext: the bug, reproduced. Read, check, write on a shared counter, and call it atomic.
/**
 * What everybody writes first: a counter per key, no lock. Two threads read "one left", both decide yes,
 * both write zero, and two requests go through a budget of one. The demo runs it so the number is real.
 */
class UnsafeLimiter implements Limiter {
    private final Map<String, long[]> spent = new ConcurrentHashMap<>();
    private final long permits;
    UnsafeLimiter(long permits) { this.permits = permits; }
    /** Deliberately wrong: the read, the check and the write are three steps with a gap between them. */
    public Decision allow(String key, long cost) {
        long[] c = spent.computeIfAbsent(key, k -> new long[1]);
        long seen = c[0];                    // read ...
        if (seen + cost <= permits) {        // ... check ...
            Thread.onSpinWait();             // ... the gap, widened here so the bug shows on every run
            c[0] = seen + cost;              // ... write, over whatever another thread wrote in between
            return Decision.allow(permits - c[0]);
        }
        return Decision.deny(0, 1, "window full");
    }
}

// ---- ext: rung one of the ladder: the same bucket with no lock at all, using compare-and-set
/**
 * The whole bucket as one immutable value in an AtomicReference. Refill-and-deduct becomes compare-and-set:
 * compute the new value from the one you read, and swap it in only if the reference still holds what you read.
 * A thread that loses recomputes against the winner's value and tries again. No lock and no thread put to
 * sleep, and it cannot livelock (spin forever with nobody getting through): somebody wins every round. One
 * trap: a thread may have read the clock before another thread's swap, so the measured-at instant only ever
 * moves forward - moving it back would let the next caller mint the same milliseconds twice.
 */
class CasBucket implements Limiter {
    /** The pair that must move together: permits, and the instant they were measured at. */
    record Snap(double tokens, long atMs) { }
    private final ConcurrentHashMap<String, AtomicReference<Snap>> keys = new ConcurrentHashMap<>();
    private final AtomicLong retries = new AtomicLong();
    private final Rule rule;
    private final Clock clock;
    CasBucket(Rule rule, Clock clock) { this.rule = rule; this.clock = clock; }
    public Decision allow(String key, long cost) {
        if (cost > rule.burst()) return Decision.never(0, "costs more than this key can ever hold");
        AtomicReference<Snap> ref = keys.computeIfAbsent(key,
                k -> new AtomicReference<>(new Snap(rule.burst(), clock.nowMs())));
        while (true) {
            long now = clock.nowMs();
            Snap cur = ref.get();
            long elapsed = Math.max(0, now - cur.atMs());
            double tokens = Math.min(rule.burst(), cur.tokens() + elapsed * rule.perMs());
            if (tokens < cost)
                return Decision.deny((long) Math.floor(tokens), (long) Math.ceil((cost - tokens) / rule.perMs()), "no permits");
            long measuredAt = Math.max(now, cur.atMs());                          // never backwards
            if (ref.compareAndSet(cur, new Snap(tokens - cost, measuredAt)))      // the whole decision, one swap
                return Decision.allow((long) Math.floor(tokens - cost));
            retries.incrementAndGet();                                            // somebody else won; redo the sums
        }
    }
    /** How often a thread lost the swap and recomputed: the measurable price of many threads on one key. */
    long retries() { return retries.get(); }
}

// ---- ext: shadow mode, so a new limit can be measured for a week before it blocks anyone
/**
 * Wraps any limiter, runs the real algorithm, charges the real permits - and then admits everything anyway,
 * counting what it would have blocked. The answer to "we ship to a live tenant tomorrow and I cannot reject
 * real traffic on day one": turn the count into a dashboard, and flip one wiring line when it looks right.
 */
class ShadowLimiter implements Limiter {
    private final Limiter delegate;
    private final AtomicLong observed = new AtomicLong(), wouldHaveBlocked = new AtomicLong();
    ShadowLimiter(Limiter delegate) { this.delegate = delegate; }
    public Decision allow(String key, long cost) {
        Decision d = delegate.allow(key, cost);
        observed.incrementAndGet();
        if (!d.allowed()) wouldHaveBlocked.incrementAndGet();
        return Decision.allow(d.remaining());                 // shadow mode: nobody is actually refused
    }
    /** How many calls went through the limiter. */
    long observed() { return observed.get(); }
    /** How many of them the real limit would have refused. The number that decides whether to switch it on. */
    long wouldHaveBlocked() { return wouldHaveBlocked.get(); }
}

// ---- ext: layered limits: per key AND a global budget, with a refund when a later layer refuses
/**
 * Two invariants at once: this tenant may spend 600 a minute, and the whole service may spend 10,000 a minute.
 * Every layer is charged in order, and if a later layer refuses, the earlier ones are refunded - otherwise a
 * tenant loses permits for a request that never happened. That refund is the compensating step of this design.
 * Per user AND per endpoint is the same class: two layers, keyed by user and by user plus route.
 */
class LayeredLimiter implements Limiter {
    /** One budget: its name for the error, the limiter that holds it, and how the key maps into it. */
    record Layer(String name, RateLimiter limiter, Function<String, String> keyOf) { }
    private final List<Layer> layers;
    LayeredLimiter(List<Layer> layers) { this.layers = List.copyOf(layers); }
    public Decision allow(String key, long cost) {
        List<Layer> charged = new ArrayList<>();
        for (Layer l : layers) {
            Decision d = l.limiter().allow(l.keyOf().apply(key), cost);
            if (!d.allowed()) {
                for (Layer c : charged) c.limiter().refund(c.keyOf().apply(key), cost);   // give back, in full, at once
                return new Decision(false, d.remaining(), d.retryAfterMs(), l.name() + " limit");   // that layer's wait
            }
            charged.add(l);
        }
        return Decision.allow(layers.get(0).limiter().remaining(layers.get(0).keyOf().apply(key)));
    }
}

// ---- ext: back-pressure: wait for a permit until a deadline instead of failing fast
/**
 * Back-pressure means slowing a caller down instead of failing it. Some callers - a batch job, a queue
 * consumer - would rather wait than fail. Retry-After already says how long the wait is, so waiting is a
 * loop around the same decision, bounded by a timeout the caller sets. Never offer this to a web request: a
 * held thread under load is how a service falls over.
 */
class WaitingLimiter {
    private final Limiter delegate;
    WaitingLimiter(Limiter delegate) { this.delegate = delegate; }
    /**
     * Try until the permit arrives or timeoutMs has passed; true if admitted. Sleeps exactly the retry-after the
     * limiter reported, never a fixed poll interval, and gives up at once on a call that can never fit. The
     * deadline is kept on System.nanoTime, which a correction to the wall clock cannot move.
     */
    boolean acquire(String key, long cost, long timeoutMs) throws InterruptedException {
        long deadline = System.nanoTime() + timeoutMs * 1_000_000L;
        while (true) {
            Decision d = delegate.allow(key, cost);
            if (d.allowed()) return true;
            if (d.retryAfterMs() == Decision.NEVER) return false;
            long leftMs = (deadline - System.nanoTime()) / 1_000_000L;
            if (leftMs <= 0) return false;
            Thread.sleep(Math.min(d.retryAfterMs(), leftMs));
        }
    }
}

// ---- ext: twelve pods, one budget: the distributed limiter
/**
 * A stand-in for Redis: a map plus one lock, because a single-threaded server IS a lock every client shares.
 * The method below is the Lua script, a small program Redis runs as one step with no other command in
 * between. Running it on the server makes refill-and-deduct atomic (one step nobody can see half-done) across
 * twelve pods, exactly as the per-key lock does across threads inside one pod. The script reads the time from
 * Redis itself, so twelve pods whose clocks disagree still share one clock, and its timestamp only moves forward.
 *
 * <pre>
 * -- KEYS[1] = the key   ARGV: burst, perMs, cost
 * local t      = redis.call('TIME')                     -- the server's clock, not the pod's
 * local now    = t[1] * 1000 + math.floor(t[2] / 1000)
 * local burst, perMs, cost = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
 * local b      = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
 * local tokens = tonumber(b[1]) or burst
 * local ts     = tonumber(b[2]) or now
 * if now &gt; ts then tokens = math.min(burst, tokens + (now - ts) * perMs); ts = now end
 * local ok = tokens &gt;= cost
 * if ok then tokens = tokens - cost end
 * redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', ts)
 * redis.call('PEXPIRE', KEYS[1], 120000)             -- TTL: Redis deletes an idle key by itself
 * if ok then return math.floor(tokens) end
 * return -math.ceil((cost - tokens) / perMs)          -- refused: minus the wait in ms
 * </pre>
 */
class RedisLike {
    private final Map<String, double[]> store = new HashMap<>();     // key -> { tokens, measuredAtMs }
    private final ReentrantLock singleThread = new ReentrantLock();  // Redis's one thread, modelled
    private final Clock serverClock;                                  // redis.call('TIME')
    RedisLike(Clock serverClock) { this.serverClock = serverClock; }
    /**
     * The script above, in Java: refill from the server's elapsed time and deduct, as one indivisible step.
     * Returns the permits left (zero or more) when admitted, or minus the wait in ms when refused.
     */
    long takeToken(String key, double burst, double perMs, long cost) {
        singleThread.lock();
        try {
            long now = serverClock.nowMs();
            double[] st = store.computeIfAbsent(key, k -> new double[] { burst, now });
            if (now > st[1]) { st[0] = Math.min(burst, st[0] + (now - st[1]) * perMs); st[1] = now; }
            if (st[0] >= cost) { st[0] -= cost; return (long) Math.floor(st[0]); }
            return -(long) Math.ceil((cost - st[0]) / perMs);
        } finally { singleThread.unlock(); }
    }
}

/**
 * The same interface, backed by the shared server, so twelve pods enforce one budget instead of twelve. The
 * price is a network hop on every request - so keep the local bucket in front of it as a cheap first filter,
 * and decide out loud what happens when Redis is down: fail open (let every call through) or fail closed
 * (refuse every call).
 */
class RedisTokenBucket implements Limiter {
    private final RedisLike redis;
    private final Rule rule;
    RedisTokenBucket(RedisLike redis, Rule rule) { this.redis = redis; this.rule = rule; }
    public Decision allow(String key, long cost) {
        if (cost > rule.burst()) return Decision.never(0, "costs more than this key can ever hold");
        long r = redis.takeToken(key, rule.burst(), rule.perMs(), cost);
        return r >= 0 ? Decision.allow(r) : Decision.deny(0, -r, "fleet limit");
    }
}

// ---- ext: a limit per endpoint, and a heavy endpoint that costs more than one permit
/**
 * Two questions that look big and are not. "Different limits per endpoint" is a different key - tenant plus
 * route - so the map grows by the number of routes and nothing else changes. "A search costs more than a
 * ping" is the cost argument that has been on allow() all along, read from a table.
 */
class Endpoints {
    private final Map<String, Long> cost = new ConcurrentHashMap<>();
    /** Say what one call to this route is worth in permits. */
    void price(String route, long permits) { cost.put(route, permits); }
    /** What this route costs; anything unpriced costs one. */
    long costOf(String route) { return cost.getOrDefault(route, 1L); }
    /** The key a decision is made against: one budget per tenant per route. */
    static String key(String tenant, String route) { return tenant + ":" + route; }
}

// ---- ext: warm-up, for the cold cache behind you
/**
 * Wraps any rule source and scales the permits up from a tenth to the full limit over the warm-up period,
 * measured from the first time each key was seen. Wraps rather than replaces: the tier rules underneath are
 * untouched, which is the same Decorator move as surge pricing on a parking lot.
 */
class WarmUpRules implements RuleResolver {
    private final RuleResolver base;
    private final long warmUpMs;
    private final Clock clock;
    private final Map<String, Long> firstSeen = new ConcurrentHashMap<>();
    WarmUpRules(RuleResolver base, long warmUpMs, Clock clock) { this.base = base; this.warmUpMs = warmUpMs; this.clock = clock; }
    public Rule ruleFor(String key) {
        Rule r = base.ruleFor(key);
        long now = clock.nowMs();
        long since = now - firstSeen.computeIfAbsent(key, k -> now);
        if (since >= warmUpMs) return r;
        double f = Math.max(0.1, (double) since / warmUpMs);            // a tenth, rising to the whole limit
        return new Rule(Math.max(1, (long) (r.permits() * f)), r.windowMs(), Math.max(1, (long) (r.burst() * f)));
    }
}

// ---- ext: the leaky bucket, properly: GCRA keeps one moment per key where the token bucket keeps two numbers
/**
 * A leaky bucket used as a meter is the token bucket turned upside down: water drains out at the steady rate,
 * each call pours its cost in, and a call that would overflow is refused. GCRA (the generic cell rate
 * algorithm, which the redis-cell module runs) keeps that bucket as one moment: when it will have drained
 * empty. A call pushes that moment one interval later per permit (an interval is windowMs / permits) and is
 * admitted if the moment stays within burst intervals of now. To keep every sum exact, time is counted in
 * units of 1/permits of a millisecond, so an interval is exactly windowMs units even at 3 a second (333 1/3
 * ms each). The moment is kept as whole milliseconds in lastRefillMs plus leftover units in currentCount,
 * which a new KeyState already holds as "now" and 0. The other reading of "leaky bucket", a queue that lets
 * calls out at a fixed pace, delays calls instead of refusing them; WaitingLimiter above is the nearest thing.
 */
class Gcra implements RateLimitAlgorithm {
    public Decision tryAcquire(KeyState s, Rule rule, long cost, long nowMs) {
        long interval = rule.windowMs(), now = nowMs * rule.permits();
        long empty = Math.max(emptyAt(s, rule), now);             // when the bucket will have drained
        long next = empty + cost * interval;                      // ... once this call has poured in its cost
        long limit = now + rule.burst() * interval;               // the most it may hold, as a moment
        if (next > limit)
            return Decision.deny(Math.max(0, (limit - empty) / interval),
                                 Math.ceilDiv(next - limit, rule.permits()), "no permits");
        s.lastRefillMs = Math.floorDiv(next, rule.permits());
        s.currentCount = Math.floorMod(next, rule.permits());
        return Decision.allow((limit - next) / interval);
    }
    public void refund(KeyState s, Rule rule, long cost, long nowMs) {
        long back = Math.max(nowMs * rule.permits(), emptyAt(s, rule) - cost * rule.windowMs());
        s.lastRefillMs = Math.floorDiv(back, rule.permits());
        s.currentCount = Math.floorMod(back, rule.permits());
    }
    public long remaining(KeyState s, Rule rule, long nowMs) {
        long now = nowMs * rule.permits();
        return Math.max(0, (now + rule.burst() * rule.windowMs() - Math.max(emptyAt(s, rule), now)) / rule.windowMs());
    }
    public long capacity(Rule rule) { return rule.burst(); }
    /** The drained-empty moment, in units of 1/permits of a millisecond. */
    private static long emptyAt(KeyState s, Rule rule) { return s.lastRefillMs * rule.permits() + s.currentCount; }
    public String name() { return "gcra"; }
}

// ---- ext: credits: a quiet window's unused permits carry over, up to a cap (Atlassian's follow-up)
/**
 * Atlassian's version of the prompt: each customer may make X calls per Y seconds, and whatever a window leaves
 * unused is saved as credits, up to a cap, for a later busy window. Here X is permits, Y is the window, and the
 * cap is burst - permits, so Rule(5, 1s, 8) means 5 a second plus up to 3 saved. The credits live in
 * KeyState.tokens (a saved permit is a token) and this window's count where FixedWindow keeps it. A new key
 * starts with a full bank, the way a new bucket starts full. It is the token bucket's burst, earned one whole
 * window at a time instead of continuously.
 */
class CreditWindow implements RateLimitAlgorithm {
    public Decision tryAcquire(KeyState s, Rule rule, long cost, long nowMs) {
        roll(s, rule, nowMs);
        long room = Math.max(0, rule.permits() - s.currentCount), credits = (long) s.tokens;
        if (cost <= room + credits) {
            long fromCredits = Math.max(0, cost - room);           // this window's room first, then the savings
            s.currentCount += cost - fromCredits;
            s.tokens -= fromCredits;
            return Decision.allow(room + credits - cost);
        }
        // wait for the next window, plus as many quiet windows as it takes to save what a big call still lacks
        long saved = Math.min(cap(rule), credits + room), lacking = Math.max(0, cost - rule.permits() - saved);
        long windows = 1 + (lacking + rule.permits() - 1) / rule.permits();
        return Decision.deny(room + credits, s.windowStartMs + windows * rule.windowMs() - nowMs, "window full, no credits");
    }
    public void refund(KeyState s, Rule rule, long cost, long nowMs) {
        roll(s, rule, nowMs);
        long back = Math.min(cost, s.currentCount);                 // undo this window's count first
        s.currentCount -= back;
        s.tokens = Math.min(cap(rule), s.tokens + (cost - back));
    }
    public long remaining(KeyState s, Rule rule, long nowMs) {
        roll(s, rule, nowMs);
        return Math.max(0, rule.permits() - s.currentCount) + (long) s.tokens;
    }
    public long capacity(Rule rule) { return rule.permits() + cap(rule); }
    /** The most credits a key may hold: whatever the burst allows beyond one window. */
    private static long cap(Rule rule) { return Math.max(0, rule.burst() - rule.permits()); }
    /** At a new window, save what the ended windows left unused, up to the cap. A quiet window saves all of it. */
    private static void roll(KeyState s, Rule rule, long nowMs) {
        long w = rule.windowMs(), aligned = Math.floorDiv(nowMs, w) * w;
        long ended = (aligned - s.windowStartMs) / w;
        if (ended > 0) {
            s.tokens += Math.max(0, rule.permits() - s.currentCount) + (double) (ended - 1) * rule.permits();
            s.currentCount = 0;
            s.windowStartMs = aligned;
        }
        s.tokens = Math.min(cap(rule), s.tokens);                   // also trims a new key's bank to the cap
    }
    public String name() { return "credit window"; }
}

// ---- ext: the hit counter (LeetCode 362): hits in the last 300 seconds, at any rate
/**
 * The same problem asked as an API: hit(second) records a hit, getHits(second) counts the last 300 seconds.
 * The first answer is the sliding window log, a queue of timestamps. The follow-up, "what if there are a
 * million hits a second?", is why this one keeps 300 slots instead: one per second, each holding which second
 * it counts and how many hits it saw. Memory stays 300 slots whatever the traffic, and a read is one pass over
 * them. One lock, held for a few field writes, makes it safe for many threads. LeetCode 359, the Logger Rate
 * Limiter, is the smallest case: a map from each message to the second it may next be printed.
 */
class HitCounter {
    private static final int SECONDS = 300;
    private final long[] second = new long[SECONDS], hits = new long[SECONDS];
    private final ReentrantLock lock = new ReentrantLock();
    /** One hit at this second. A slot still holding an older second is reused; a hit older than its slot is dropped. */
    void hit(long sec) {
        int i = Math.floorMod(sec, SECONDS);
        lock.lock();
        try {
            if (second[i] > sec) return;                               // too old: this slot has moved on
            if (second[i] < sec) { second[i] = sec; hits[i] = 0; }     // a new second takes over the slot
            hits[i]++;
        } finally { lock.unlock(); }
    }
    /** Hits in the 300 seconds ending at this one: from sec - 299 up to sec. */
    long getHits(long sec) {
        lock.lock();
        try {
            long total = 0;
            for (int i = 0; i < SECONDS; i++) if (second[i] <= sec && sec - second[i] < SECONDS) total += hits[i];
            return total;
        } finally { lock.unlock(); }
    }
}

/** Runs every extension above, so each block on page 05 is code that has actually executed. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        // the bug, reproduced: no lock, a budget of 50, 200 threads
        UnsafeLimiter buggy = new UnsafeLimiter(50);
        System.out.println("unsafe read-check-write, 200 threads -> admitted " + hammer(buggy, 200) + " on a budget of 50");

        // rung one: the same bucket with compare-and-set instead of a lock
        CasBucket cas = new CasBucket(new Rule(50, 1_000L, 50), new ManualClock(0));
        System.out.println("compare-and-set bucket, 200 threads -> admitted " + hammer(cas, 200)
                         + ", lost swaps and recomputed " + cas.retries() + " times");

        // shadow mode: the real algorithm, nothing refused
        ManualClock clock = new ManualClock(0);
        RateLimiter real = new RateLimiter();
        real.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), clock);
        ShadowLimiter shadow = new ShadowLimiter(real);
        int refused = 0;
        for (int i = 0; i < 20; i++) if (!shadow.allow("acme", 1).allowed()) refused++;
        System.out.println("shadow mode: saw " + shadow.observed() + ", would have blocked "
                         + shadow.wouldHaveBlocked() + ", actually refused " + refused);

        // layered: per tenant AND a global budget, with the refund when the global one refuses
        RateLimiter perTenant = new RateLimiter(), global = new RateLimiter();
        perTenant.configure(new TokenBucket(), new FlatRules(new Rule(10, 1_000L, 10)), clock);
        global.configure(new TokenBucket(), new FlatRules(new Rule(3, 1_000L, 3)), clock);
        LayeredLimiter layered = new LayeredLimiter(List.of(
                new LayeredLimiter.Layer("tenant", perTenant, k -> k),
                new LayeredLimiter.Layer("global", global, k -> "ALL")));
        int ok = 0;
        for (int i = 0; i < 6; i++) if (layered.allow("acme", 1).allowed()) ok++;
        System.out.println("layered (tenant 10, global 3)     -> admitted " + ok
                         + ", tenant permits left " + perTenant.remaining("acme") + " (7 only if the refunds happened)");

        // back-pressure: wait for the permit instead of failing
        RateLimiter slow = new RateLimiter();
        slow.configure(new TokenBucket(), new FlatRules(new Rule(20, 1_000L, 1)), new SystemClock());
        WaitingLimiter waiting = new WaitingLimiter(slow);
        slow.allow("batch");                                            // spend the only permit
        long t0 = System.nanoTime();
        boolean got = waiting.acquire("batch", 1, 500);
        System.out.println("back-pressure: waited " + (System.nanoTime() - t0) / 1_000_000 + "ms, admitted " + got);

        // twelve pods, one budget, one clock: the server's
        RedisLike redis = new RedisLike(new ManualClock(0));
        Rule fleetRule = new Rule(50, 1_000L, 50);
        Limiter pod1 = new RedisTokenBucket(redis, fleetRule), pod2 = new RedisTokenBucket(redis, fleetRule);
        int fleet = 0;
        for (int i = 0; i < 40; i++) { if (pod1.allow("acme", 1).allowed()) fleet++; if (pod2.allow("acme", 1).allowed()) fleet++; }
        System.out.println("two pods, one Redis budget of 50  -> admitted " + fleet + " (per-process would be 100)");

        // per-endpoint keys and weighted cost
        Endpoints ep = new Endpoints();
        ep.price("/search", 5);
        RateLimiter routed = new RateLimiter();
        routed.configure(new TokenBucket(), new FlatRules(new Rule(10, 1_000L, 10)), clock);
        routed.allow(Endpoints.key("acme", "/search"), ep.costOf("/search"));
        System.out.println("per route: /search costs " + ep.costOf("/search") + " -> key "
                         + Endpoints.key("acme", "/search") + " has " + routed.remaining(Endpoints.key("acme", "/search"))
                         + " left, /ping has " + routed.remaining(Endpoints.key("acme", "/ping")));

        // warm-up: a new key starts at a tenth of its limit
        ManualClock warmClock = new ManualClock(0);
        WarmUpRules warm = new WarmUpRules(new FlatRules(Rule.perMinute(600, 100)), 30_000L, warmClock);
        long atStart = warm.ruleFor("fresh").permits();
        warmClock.advance(30_000);
        System.out.println("warm-up over 30s: permits at t=0 " + atStart + ", at t=30s " + warm.ruleFor("fresh").permits());

        // the leaky bucket as a meter: GCRA must agree with the token bucket on the burst
        RateLimiter g = new RateLimiter();
        ManualClock gc = new ManualClock(0);
        g.configure(new Gcra(), new FlatRules(new Rule(10, 1_000L, 5)), gc);
        int burst = 0;
        while (g.allow("k").allowed()) burst++;
        gc.advance(100);
        System.out.println("gcra: burst admitted " + burst + ", one more after 100ms -> " + g.allow("k").allowed());

        // credits: 5 a second, and up to 3 unused permits saved for a busy second
        ManualClock cc = new ManualClock(0);
        RateLimiter credits = new RateLimiter();
        credits.configure(new CreditWindow(), new FlatRules(new Rule(5, 1_000L, 8)), cc);
        int first = passed(credits, 10);                                 // a new key: 5 + a full bank of 3
        cc.advance(1_000);
        int busyAfterBusy = passed(credits, 10);                         // the last second saved nothing
        cc.advance(2_000);
        int afterQuiet = passed(credits, 10);                            // a quiet second saved 3
        System.out.println("credits: first second " + first + ", busy after busy " + busyAfterBusy
                         + ", busy after a quiet second " + afterQuiet + " (of 10 tried each time)");

        // the hit counter: 4 threads, 100,000 hits in one second, counted in 300 slots
        HitCounter hc = new HitCounter();
        ExecutorService four = Executors.newFixedThreadPool(4);
        for (int t = 0; t < 4; t++) four.submit(() -> { for (int i = 0; i < 25_000; i++) hc.hit(100); });
        four.shutdown();
        four.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("hit counter: at second 100 -> " + hc.getHits(100) + ", at 399 -> " + hc.getHits(399)
                         + ", at 400 -> " + hc.getHits(400));
    }

    /** Try n calls on one key at the current instant and count the ones admitted. */
    static int passed(Limiter limiter, int n) {
        int ok = 0;
        for (int i = 0; i < n; i++) if (limiter.allow("acme", 1).allowed()) ok++;
        return ok;
    }

    /** Fire n threads at one key at the same instant and count how many were admitted. */
    static int hammer(Limiter limiter, int n) throws Exception {
        CountDownLatch start = new CountDownLatch(1), done = new CountDownLatch(n);
        AtomicInteger admitted = new AtomicInteger();
        ExecutorService pool = Executors.newFixedThreadPool(32);
        for (int i = 0; i < n; i++) pool.submit(() -> {
            try { start.await(); if (limiter.allow("hot", 1).allowed()) admitted.incrementAndGet(); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            finally { done.countDown(); }
        });
        start.countDown();
        done.await();
        pool.shutdown();
        return admitted.get();
    }
}
