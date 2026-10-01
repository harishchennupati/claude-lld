// The token bucket: it holds at most `capacity` tokens (the biggest burst) and earns one back every
// millisPerToken. Each request takes one token; with none left, it is refused and told when the
// next one arrives. No timer adds tokens: each call works out what the time since the last call
// has earned ("lazy refill"), so a million idle customers cost no threads.
class TokenBucket implements Counter {
    private final int capacity;              // 5 a second: at most 5 at once
    private final double millisPerToken;     // 5 a second: one token every 200 ms
    private double tokens;                   // a double: 120 ms earns 0.6 of a token, kept
    private long lastRefillMillis;           // when the tokens were last worked out

    TokenBucket(Limit limit, long nowMillis) {
        this.capacity = limit.requests();
        this.millisPerToken = (double) limit.periodMillis() / limit.requests();
        this.tokens = capacity;              // a new customer starts with a full bucket
        this.lastRefillMillis = nowMillis;
    }

    // synchronized: refill, check and take read the numbers, then write them back. Without one
    // lock around all three, two threads can both see the last token and both take it. The lock
    // is this bucket's, so requests for other keys never wait on it.
    @Override
    public synchronized Decision tryAcquire(long nowMillis) {
        refill(nowMillis);
        if (tokens >= 1) {
            tokens -= 1;
            return Decision.allow();
        }
        // Not enough: the missing part of a token, in ms. 0.6 left → 0.4 × 200 = 80 ms.
        long waitMillis = (long) Math.ceil((1 - tokens) * millisPerToken);
        return Decision.deny(waitMillis);
    }

    @Override
    public synchronized void refund(long nowMillis) {
        tokens = Math.min(capacity, tokens + 1);     // never above the cap
    }

    // Add what the time since the last refill has earned, capped at the capacity: quiet time
    // fills the bucket, never overfills it.
    private void refill(long nowMillis) {
        long elapsed = nowMillis - lastRefillMillis;
        if (elapsed <= 0) {
            return;                          // a clock that went back earns nothing
        }
        tokens = Math.min(capacity, tokens + elapsed / millisPerToken);
        lastRefillMillis = nowMillis;
    }
    //@ from idle

    // Full again: exactly what a new bucket would be, so it can be forgotten.
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        refill(nowMillis);
        return tokens >= capacity;
    }
    //@ end
}
