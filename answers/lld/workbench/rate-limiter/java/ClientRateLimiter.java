//@ from f6
import java.util.Map;
//@ end
import java.util.concurrent.ConcurrentHashMap;

//@ until f4
// The class the API calls. It keeps one bucket per client and creates it on the client's first
// request. Counting is the bucket's job, limits are Plans' job and time is the Clock's: all three
// are handed in through the constructor, so none of them is hard-wired here.
//@ end
//@ from f4
// The class the API calls. It keeps one bucket per key and creates it on the key's first request.
// A key is usually a client, but it can be anything a rule counts by: "fantasy-app /search", "*".
// Counting is the bucket's job, limits are the lookup's job and time is the Clock's: all three
// are handed in through the constructor, so none of them is hard-wired here.
//@ end
class ClientRateLimiter implements RateLimiter {
    //@ until f5
    private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();
    //@ end
    //@ from f5
    private final ConcurrentHashMap<String, LimitedBucket> buckets = new ConcurrentHashMap<>();
    //@ end
    //@ until f4
    private final Plans plans;
    //@ end
    //@ from f4
    // Was `Plans plans`. The limiter only ever asks one question, "which limit for this key?",
    // so now it depends on just that question. Plans still answers it for clients, and a rule
    // with one limit for every key is a lambda: key -> Limit.perSecond(2).
    private final LimitLookup limits;
    //@ end
    private final BucketFactory factory;
    private final Clock clock;
    //@ from f5

    // A key's bucket, and the limit it was built for: that is how a stale bucket is spotted.
    private record LimitedBucket(Limit limit, Bucket bucket) { }
    //@ end

    //@ until f4
    ClientRateLimiter(Plans plans, BucketFactory factory, Clock clock) {
        this.plans = plans;
    //@ end
    //@ from f4
    ClientRateLimiter(LimitLookup limits, BucketFactory factory, Clock clock) {
        this.limits = limits;
    //@ end
        this.factory = factory;
        this.clock = clock;
    }

    //@ until f3
    @Override
    public Decision tryAcquire(String clientId) {
        long now = clock.nowMillis();          // read the time once, and hand it to the bucket
        // Find this client's bucket, or create it on the first request, in ONE atomic step:
        // two threads that meet a new client at the same moment still share one bucket.
        Bucket bucket = buckets.computeIfAbsent(clientId, id -> factory.create(plans.limitFor(id), now));
        return bucket.tryConsume(now);
    }
    //@ end
    //@ from f3 until f4
    @Override
    public Decision tryAcquire(String clientId, int cost) {
        long now = clock.nowMillis();          // read the time once, and hand it to the bucket
        // Find this client's bucket, or create it on the first request, in ONE atomic step:
        // two threads that meet a new client at the same moment still share one bucket.
        Bucket bucket = buckets.computeIfAbsent(clientId, id -> factory.create(plans.limitFor(id), now));
        return bucket.tryConsume(cost, now);
    }
    //@ end
    //@ from f4
    @Override
    public Decision tryAcquire(String key, int cost) {
        return tryAcquire(key, cost, clock.nowMillis());
    }

    // For a caller that checks several rules for one request, so that every rule sees the same instant.
    Decision tryAcquire(String key, int cost, long nowMillis) {
    //@ end
    //@ from f4 until f5
        // Find this key's bucket, or create it on the first request, in ONE atomic step:
        // two threads that meet a new key at the same moment still share one bucket.
        Bucket bucket = buckets.computeIfAbsent(key, k -> factory.create(limits.limitFor(k), nowMillis));
        return bucket.tryConsume(cost, nowMillis);
    }

    // Give back what tryAcquire took for this key, when a later rule refused the same request.
    void refund(String key, int cost, long nowMillis) {
        Bucket bucket = buckets.get(key);
        if (bucket != null) {
            bucket.refund(cost, nowMillis);
        }
    }
    //@ end
    //@ from f5
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
    //@ end
    //@ from f6

    // Forgets buckets that are idle, because a new one would behave exactly the same. A timer
    // calls this, never a request. A ConcurrentHashMap can be walked while other threads change it.
    int evictIdle(long nowMillis) {
        int removed = 0;
        for (Map.Entry<String, LimitedBucket> e : buckets.entrySet()) {
            // remove(key, value) removes the entry only if the map still holds this same one,
            // so a bucket another thread has just replaced is left alone.
            if (e.getValue().bucket().isIdle(nowMillis) && buckets.remove(e.getKey(), e.getValue())) {
                removed++;
            }
        }
        return removed;
    }

    // How many keys have a bucket right now: the number evictIdle keeps small.
    int size() {
        return buckets.size();
    }
    //@ end
}
