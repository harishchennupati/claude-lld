// Where buckets live: one per key. In memory for one server; in Redis when many servers must
// share one budget. The limiter only ever asks for "the bucket for this key", and hands in how
// to make one if the key is new (a rule's Algorithm, which is a BucketFactory).
interface BucketStore {
    Bucket bucketFor(String key, BucketFactory factory, Limit limit, long nowMillis);
}
