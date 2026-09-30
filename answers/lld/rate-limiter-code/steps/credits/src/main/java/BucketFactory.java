// Makes a new bucket for a limit. TokenBucket::new fits, because its constructor takes
// (Limit, long); so does any lambda with those two parameters.
@FunctionalInterface
interface BucketFactory {
    Bucket create(Limit limit, long nowMillis);
}
