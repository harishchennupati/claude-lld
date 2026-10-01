// Holds at most `capacity` tokens (the biggest burst) and earns one back every millisPerToken.
// No timer adds them: each call works out what the time since the last call has earned.
class TokenBucket implements Counter {
    private final int capacity;
    private final double millisPerToken;     // 5 a second: one token every 200 ms
    private double tokens;                   // a double: 120 ms earns 0.6 of a token, kept
    private long lastRefillMillis;

    TokenBucket(Limit limit, long nowMillis) {
        this.capacity = limit.requests();
        this.millisPerToken = (double) limit.periodMillis() / limit.requests();
        this.tokens = capacity;              // a new customer starts with a full bucket
        this.lastRefillMillis = nowMillis;
    }

    // synchronized: refill, check and take are one step. Without it two threads can both see the
    // last token and both take it. The lock is this bucket's, so other customers never wait.
    @Override
    public synchronized Decision tryAcquire(long nowMillis) {
        refill(nowMillis);
        if (tokens >= 1) {
            tokens -= 1;
            return Decision.allow();
        }
        long waitMillis = (long) Math.ceil((1 - tokens) * millisPerToken);   // the missing part
        return Decision.deny(waitMillis);
    }

    private void refill(long nowMillis) {
        long elapsed = nowMillis - lastRefillMillis;
        if (elapsed <= 0) {
            return;                          // a clock that went back earns nothing
        }
        tokens = Math.min(capacity, tokens + elapsed / millisPerToken);
        lastRefillMillis = nowMillis;
    }
    //@ from idle

    // Full again: exactly what a new bucket would be.
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        refill(nowMillis);
        return tokens >= capacity;
    }
    //@ end
}
