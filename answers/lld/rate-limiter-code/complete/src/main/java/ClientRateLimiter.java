import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// The class the API calls. It keeps one bucket per key and creates it on the key's first request.
// A key is usually a client, but it can be anything a rule counts by: "fantasy-app /search", "*".
// Counting is the bucket's job, limits are the lookup's job and time is the Clock's: all three
// are handed in through the constructor, so none of them is hard-wired here.
class ClientRateLimiter implements RateLimiter {
    private final ConcurrentHashMap<String, LimitedBucket> buckets = new ConcurrentHashMap<>();
    // Was `Plans plans`. The limiter only ever asks one question, "which limit for this key?",
    // so now it depends on just that question. Plans still answers it for clients, and a rule
    // with one limit for every key is a lambda: key -> Limit.perSecond(2).
    private final LimitLookup limits;
    private final BucketFactory factory;
    private final Clock clock;

    // A key's bucket, and the limit it was built for: that is how a stale bucket is spotted.
    private record LimitedBucket(Limit limit, Bucket bucket) { }

    ClientRateLimiter(LimitLookup limits, BucketFactory factory, Clock clock) {
        this.limits = limits;
        this.factory = factory;
        this.clock = clock;
    }

    @Override
    public Decision tryAcquire(String key, int cost) {
        return tryAcquire(key, cost, clock.nowMillis());
    }

    // For a caller that checks several rules for one request: every rule sees the same instant.
    Decision tryAcquire(String key, int cost, long nowMillis) {
        return current(key, nowMillis).tryConsume(cost, nowMillis);
    }

    // Give back what tryAcquire took for this key, when a later rule refused the same request.
    void refund(String key, int cost, long nowMillis) {
        LimitedBucket held = buckets.get(key);
        if (held != null) {
            held.bucket().refund(cost, nowMillis);
        }
    }

    // This key's bucket for its limit right now. The first request creates it, and the first
    // request after ops changed the limit replaces it. compute() does the check and the swap as
    // ONE atomic step, like computeIfAbsent, so two threads never build two buckets.
    private Bucket current(String key, long nowMillis) {
        Limit limit = limits.limitFor(key);
        LimitedBucket held = buckets.get(key);
        if (held == null || !held.limit().equals(limit)) {
            held = buckets.compute(key, (k, old) -> old != null && old.limit().equals(limit)
                    ? old
                    : new LimitedBucket(limit, factory.create(limit, nowMillis)));
        }
        return held.bucket();
    }

    // Forgets buckets that are idle, because a new one would behave exactly the same. A timer
    // calls this, never a request. A ConcurrentHashMap can be walked while threads change it.
    int evictIdle(long nowMillis) {
        int removed = 0;
        for (Map.Entry<String, LimitedBucket> e : buckets.entrySet()) {
            // remove(key, value) removes the entry only if the map still holds this same one,
            // so a bucket another thread has just replaced is left alone.
            LimitedBucket held = e.getValue();
            if (held.bucket().isIdle(nowMillis) && buckets.remove(e.getKey(), held)) {
                removed++;
            }
        }
        return removed;
    }

    // How many keys have a bucket right now: the number evictIdle keeps small.
    int size() {
        return buckets.size();
    }
}
