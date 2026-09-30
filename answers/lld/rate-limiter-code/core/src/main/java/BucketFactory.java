// Makes the bucket for a client's first request. TokenBucket::new fits this shape, because
// TokenBucket's constructor takes (Limit, long). The limiter only ever calls create(), so a
// new way of counting is a new class, and the limiter does not change.
@FunctionalInterface
interface BucketFactory {
    Bucket create(Limit limit, long nowMillis);
}
