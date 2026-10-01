// The count for one key under one rule.
// Why an interface: each way of counting is a class behind it (Strategy), so the limiter calls all
// of them the same way. Not an abstract class: that is for shared fields and code, and the
// counters share none (tokens, a count, a list of times).
interface Counter {
    // Take room for one request if there is any, or say how long until there will be.
    Decision tryAcquire(long nowMillis);

    // Give back one request this counter allowed: a later rule refused the request.
    void refund(long nowMillis);

    // True when forgetting this counter loses nothing: a new one would be the same.
    default boolean isIdle(long nowMillis) {
        return false;
    }
}
