import java.util.HashMap;
import java.util.Map;

// A stand-in for Redis, so this runs anywhere. Real Redis runs one command or script at a
// time, on one thread, so two scripts never interleave: `synchronized` models exactly that.
class FakeRedis {
    private final Map<String, double[]> buckets = new HashMap<>();   // key -> {tokens, last}
    private final Clock serverClock;   // Redis's own clock: its TIME command
    private boolean down;              // to show what an outage does

    FakeRedis(Clock serverClock) {
        this.serverClock = serverClock;
    }

    synchronized void setDown(boolean down) {
        this.down = down;
    }

    // The same steps as RedisRateLimiter.SCRIPT, in Java, as one indivisible call.
    // Returns {1 if allowed else 0, whole tokens left, milliseconds until enough}.
    synchronized long[] tokenBucket(String key, int capacity, double millisPerToken, int cost) {
        if (down) {
            throw new IllegalStateException("Redis is unreachable");
        }
        long now = serverClock.nowMillis();
        double[] b = buckets.computeIfAbsent(key, k -> new double[] {capacity, now});
        if (now > b[1]) {
            b[0] = Math.min(capacity, b[0] + (now - b[1]) / millisPerToken);
            b[1] = now;
        }
        if (b[0] >= cost) {
            b[0] -= cost;
            return new long[] {1, (long) b[0], 0};
        }
        return new long[] {0, (long) b[0], (long) Math.ceil((cost - b[0]) * millisPerToken)};
    }
}
