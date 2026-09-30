// How a rule counts, by name, so rules can come from a config file ("algorithm: TOKEN_BUCKET").
// Each constant IS a BucketFactory, holding its bucket's constructor: there is no switch
// anywhere, and a new way of counting is one new class and one new line here.
enum Algorithm implements BucketFactory {
    TOKEN_BUCKET(TokenBucket::new),               // bursts, then a steady rate
    SLIDING_WINDOW_LOG(SlidingWindowLog::new),    // exact, at one entry per request
    SLIDING_WINDOW_COUNTER(SlidingWindowCounter::new),   // nearly exact, two counters
    LEAKY_BUCKET(LeakyBucket::new),               // the token bucket, mirrored
    FIXED_WINDOW(FixedWindowCounter::new);        // one counter: quotas per day or month

    private final BucketFactory factory;

    Algorithm(BucketFactory factory) {
        this.factory = factory;
    }

    @Override
    public Bucket create(Limit limit, long nowMillis) {
        return factory.create(limit, nowMillis);
    }
}
