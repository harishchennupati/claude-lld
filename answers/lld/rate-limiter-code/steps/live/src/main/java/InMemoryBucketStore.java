import java.util.concurrent.ConcurrentHashMap;

// This server's buckets, in one map shared by every request thread.
class InMemoryBucketStore implements BucketStore {
    private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    public Bucket bucketFor(String key, BucketFactory factory, Limit limit, long nowMillis) {
        // Find-or-create as ONE atomic step, so two threads that meet a new key at the same
        // moment still get the same bucket. The factory runs only for a new key.
        return buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));
    }
}
