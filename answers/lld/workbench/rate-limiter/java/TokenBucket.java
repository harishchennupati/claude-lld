// Holds up to `capacity` tokens and earns them back at a steady rate.
// score-widget, 5 per second: capacity 5, one token back every 200 ms.
class TokenBucket implements Bucket {
    private final int capacity;             // the most it can hold: the biggest burst
    private final double millisPerToken;    // time to earn one token back: 200 ms
    private double tokens;                  // tokens now; a double, because 120 ms earns 0.6 of a token
    private long lastRefillMillis;          // when `tokens` was last brought up to date

    TokenBucket(Limit limit, long nowMillis) {
        this.capacity = limit.capacity();
        this.millisPerToken = limit.millisPerToken();
        this.tokens = capacity;             // a new client starts full, so it can burst straight away
        this.lastRefillMillis = nowMillis;
    }

    // synchronized: refill, check and take happen as ONE step for this bucket.
    // Two requests from the same client take turns. Other clients have their own
    // bucket and their own lock, so they never wait for this one.
    @Override
    //@ until f3
    public synchronized Decision tryConsume(long nowMillis) {
        refill(nowMillis);
        if (tokens >= 1) {
            tokens -= 1;
            return Decision.allow((long) tokens);      // whole tokens left: 2.6 -> 2
        }
        // Wait for the missing part of a token: 0.6 left -> 0.4 x 200 ms = 80 ms.
        // Rounded up, so a client that waits exactly this long finds the token there.
        long waitMillis = (long) Math.ceil((1 - tokens) * millisPerToken);
        return Decision.deny(waitMillis);
    }
    //@ end
    //@ from f3
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        refill(nowMillis);
        if (cost > capacity) {
            return Decision.never((long) tokens);      // 6 tokens can never fit in a bucket of 5
        }
        if (tokens >= cost) {
            tokens -= cost;
            return Decision.allow((long) tokens);      // whole tokens left: 2.6 -> 2
        }
        // Wait for the missing tokens: 3 left, cost 5 -> 2 x 200 ms = 400 ms.
        // Rounded up, so a client that waits exactly this long finds the tokens there.
        long waitMillis = (long) Math.ceil((cost - tokens) * millisPerToken);
        return Decision.deny((long) tokens, waitMillis);
    }
    //@ end
    //@ from f4

    // Give tokens back, but never above capacity: if time refilled the bucket meanwhile,
    // a refund must not push it past full.
    @Override
    public synchronized void refund(int cost, long nowMillis) {
        refill(nowMillis);
        tokens = Math.min(capacity, tokens + cost);
    }
    //@ end
    //@ from f6

    // Unused for as long as a full refill takes (one period), the bucket is full again:
    // exactly like a new one, so forgetting it loses nothing.
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        return nowMillis - lastRefillMillis >= capacity * millisPerToken;
    }
    //@ end

    // Add the tokens earned since the last refill, but never more than capacity:
    // 2 quiet seconds earn 10 tokens, and a bucket of 5 keeps 5.
    private void refill(long nowMillis) {
        long elapsed = nowMillis - lastRefillMillis;
        if (elapsed <= 0) {
            return;   // same instant, or an older time from a thread that got the lock late: earn nothing
        }
        tokens = Math.min(capacity, tokens + elapsed / millisPerToken);
        lastRefillMillis = nowMillis;
    }
}
