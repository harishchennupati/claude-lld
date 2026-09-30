// One client's budget. Each way of counting (token bucket, sliding window, ...) is a class
// that implements this, so the code that uses a bucket never needs to know which one it has.
interface Bucket {
    // Take one token now, or say how long until there will be one.
    Decision tryConsume(long nowMillis);
}
