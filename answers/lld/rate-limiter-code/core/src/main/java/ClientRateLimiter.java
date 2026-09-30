import java.util.concurrent.ConcurrentHashMap;

// The class the API calls. It keeps one bucket per client and creates it on the client's first
// request. Counting is the bucket's job, limits are Plans' job and time is the Clock's: all three
// are handed in through the constructor, so none of them is hard-wired here.
class ClientRateLimiter implements RateLimiter {
    private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();
    private final Plans plans;
    private final BucketFactory factory;
    private final Clock clock;

    ClientRateLimiter(Plans plans, BucketFactory factory, Clock clock) {
        this.plans = plans;
        this.factory = factory;
        this.clock = clock;
    }

    @Override
    public Decision tryAcquire(String clientId) {
        long now = clock.nowMillis();          // read the time once, and hand it to the bucket
        // Find this client's bucket, or create it on the first request, in ONE atomic step:
        // two threads that meet a new client at the same moment still share one bucket.
        Bucket bucket = buckets.computeIfAbsent(clientId,
                id -> factory.create(plans.limitFor(id), now));
        return bucket.tryConsume(now);
    }
}
