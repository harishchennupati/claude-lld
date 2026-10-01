// One key's count under one rule. Each way of counting is a class behind this interface (the
// Strategy pattern), so the limiter never knows which one it holds.
interface Counter {
    Decision tryAcquire(long nowMillis);

    // Give back one request this counter allowed: a later rule refused it.
    void refund(long nowMillis);

    // True when forgetting this counter loses nothing: a new one would be the same.
    default boolean isIdle(long nowMillis) {
        return false;
    }
}
