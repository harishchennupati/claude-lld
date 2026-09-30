// Holds up to `capacity` tokens and earns them back at a steady rate.
// score-widget, 5 per second: capacity 5, one token back every 200 ms.
class TokenBucket implements Bucket {
    private final int capacity;           // the most it can hold: the biggest burst
    private final double millisPerToken;  // time to earn one token back: 200 ms
    private double tokens;                // a double, because 120 ms earns 0.6 of a token
    private long lastRefillMillis;        // when `tokens` was last brought up to date

    TokenBucket(Limit limit, long nowMillis) {
        this.capacity = limit.capacity();
        this.millisPerToken = limit.millisPerToken();
        this.tokens = capacity;           // a new client starts full: it may burst straight away
        this.lastRefillMillis = nowMillis;
    }

    // synchronized: refill, check and take happen as ONE step for this bucket.
    // Two requests from the same client take turns. Other clients have their own
    // bucket and their own lock, so they never wait for this one.
    @Override
    public synchronized Decision tryConsume(long nowMillis) {
        refill(nowMillis);
        if (tokens >= 1) {
            tokens -= 1;
            return Decision.allow((long) tokens);        // whole tokens left: 2.6 -> 2
        }
        // Wait for the missing part of a token: 0.6 left -> 0.4 x 200 ms = 80 ms.
        // Rounded up, so a client that waits exactly this long finds the token there.
        long waitMillis = (long) Math.ceil((1 - tokens) * millisPerToken);
        return Decision.deny(waitMillis);
    }

    // Add the tokens earned since the last refill, but never more than capacity:
    // 2 quiet seconds earn 10 tokens, and a bucket of 5 keeps 5.
    private void refill(long nowMillis) {
        long elapsed = nowMillis - lastRefillMillis;
        // Same instant, or an older time: a thread that read the clock earlier can get the lock
        // later. Earn nothing then, and never move lastRefillMillis backwards.
        if (elapsed <= 0) {
            return;
        }
        tokens = Math.min(capacity, tokens + elapsed / millisPerToken);
        lastRefillMillis = nowMillis;
    }
}
