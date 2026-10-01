// One key's count under one algorithm. The limiter never knows which algorithm it holds: each is
// a class behind this interface (the Strategy pattern).
interface Counter {
    Decision tryAcquire(long nowMillis);

    // True when forgetting this counter loses nothing: a new one would be the same.
    default boolean isIdle(long nowMillis) {
        return false;
    }
}
