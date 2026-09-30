// Buckets whose numbers live in Redis, so every server spends from the same budget. The limiter
// does not change: it still asks a BucketStore for "the bucket for this key".
class RedisBucketStore implements BucketStore {
    private final FakeRedis redis;    // in production: a Redis client with a timeout of a few ms
    private final boolean failOpen;   // Redis unreachable: allow everything, or refuse everything?

    RedisBucketStore(FakeRedis redis, boolean failOpen) {
        this.redis = redis;
        this.failOpen = failOpen;
    }

    // Only the token bucket has a script here. The log would be a sorted set (ZADD,
    // ZREMRANGEBYSCORE, ZCARD) and the fixed window INCR with PEXPIRE, each one script too.
    @Override
    public Bucket bucketFor(String key, BucketFactory factory, Limit limit, long nowMillis) {
        if (factory != Algorithm.TOKEN_BUCKET) {
            throw new UnsupportedOperationException(factory + ": no Redis script here");
        }
        return new RedisTokenBucket(redis, "rl:" + key, limit, failOpen);   // no state: cheap
    }
}
