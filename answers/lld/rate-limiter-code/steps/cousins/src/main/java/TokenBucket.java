// Holds up to `capacity` tokens and earns them back at a steady rate: bursts up to the capacity,
// then a steady pace. score-widget, 5 a second: capacity 5, one token back every 200 ms.
class TokenBucket implements Bucket {
    private final int capacity;           // the most it can hold: the biggest burst
    private final double millisPerToken;  // time to earn one token back: 200 ms
    private double tokens;                // a double, because 120 ms earns 0.6 of a token
    private long lastRefillMillis;        // when `tokens` was last brought up to date

    TokenBucket(Limit limit, long nowMillis) {
        this.capacity = limit.capacity();
        this.millisPerToken = limit.millisPerToken();
        this.tokens = capacity;           // a new key starts full: it may burst straight away
        this.lastRefillMillis = nowMillis;
    }

    // synchronized: refill, check and take happen as ONE step for this bucket. Requests for the
    // same key take turns; other keys have their own bucket and their own lock.
    @Override
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        refill(nowMillis);
        if (tokens >= cost) {
            tokens -= cost;
            return Decision.allow((long) tokens);        // whole tokens left: 2.6 -> 2
        }
        // Wait for the missing part: 0.6 left, cost 1 -> 0.4 x 200 ms = 80 ms. Rounded up, so a
        // client that waits this long finds the tokens there (floating point may add 1 ms).
        long waitMillis = (long) Math.ceil((cost - tokens) * millisPerToken);
        return Decision.deny((long) tokens, waitMillis);
    }

    // Never above capacity: if time refilled the bucket meanwhile, a refund must not overfill it.
    @Override
    public synchronized void refund(int cost, long nowMillis) {
        refill(nowMillis);
        tokens = Math.min(capacity, tokens + cost);
    }

    // Left alone for as long as a full refill takes, it is full again: exactly like a new one.
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        return nowMillis - lastRefillMillis >= capacity * millisPerToken;
    }

    // Add the tokens earned since the last refill, never more than capacity: 2 quiet seconds
    // earn 10 tokens, and a bucket of 5 keeps 5.
    private void refill(long nowMillis) {
        long elapsed = nowMillis - lastRefillMillis;
        // Times can arrive out of order: the limiter reads the clock before it takes this lock,
        // so a thread with an older reading can get here after one with a newer reading, and the
        // wall clock can jump back. Treat that as no time passing: earn nothing, take nothing.
        if (elapsed <= 0) {
            return;
        }
        tokens = Math.min(capacity, tokens + elapsed / millisPerToken);
        lastRefillMillis = nowMillis;
    }
}
