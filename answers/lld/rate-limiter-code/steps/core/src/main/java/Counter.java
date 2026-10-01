// The count for one key under one rule. Each way of counting is a class behind this interface
// (the Strategy pattern), so the limiter never knows which one it holds.
interface Counter {
    // Take room for one request if there is any, or say how long until there will be.
    Decision tryAcquire(long nowMillis);

    // Give back one request this counter allowed: a later rule refused the request.
    void refund(long nowMillis);
}
