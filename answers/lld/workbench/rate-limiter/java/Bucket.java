// One key's budget under one rule. Each way of counting is a class that implements this, so the
// limiter never needs to know which one it has: the Strategy pattern.
interface Bucket {
    // Take `cost` tokens now, or say how long until there will be enough.
    Decision tryConsume(int cost, long nowMillis);

    // Give back what tryConsume took, when a later rule refuses the same request.
    void refund(int cost, long nowMillis);
    //@ from idle

    // True when forgetting this bucket loses nothing, because a new one would behave the same.
    // The safe default is "never": a bucket that cannot tell is simply kept.
    default boolean isIdle(long nowMillis) {
        return false;
    }
    //@ end
}
