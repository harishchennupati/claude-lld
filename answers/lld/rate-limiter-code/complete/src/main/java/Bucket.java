// One client's budget. Each way of counting (token bucket, sliding window, ...) is a class
// that implements this, so the code that uses a bucket never needs to know which one it has.
interface Bucket {
    // Take `cost` tokens now, or say how long until there will be enough.
    Decision tryConsume(int cost, long nowMillis);

    // Every caller written before costs existed keeps working: an ordinary request costs 1.
    default Decision tryConsume(long nowMillis) {
        return tryConsume(1, nowMillis);
    }

    // Give back what tryConsume took, when a later rule refuses the same request.
    void refund(int cost, long nowMillis);

    // True when forgetting this bucket loses nothing, because a new one would behave the same.
    // The safe default is "never": a bucket that cannot tell is simply kept.
    default boolean isIdle(long nowMillis) {
        return false;
    }
}
