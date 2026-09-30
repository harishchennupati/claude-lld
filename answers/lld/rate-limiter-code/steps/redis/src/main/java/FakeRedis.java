import java.util.HashMap;
import java.util.Map;

// A stand-in for Redis, so the demo runs anywhere. Real Redis runs one command or script at a
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

    // The same steps as RedisTokenBucket.SCRIPT, in Java, as one indivisible call. Returns
    // {1 if allowed else 0, whole tokens left, milliseconds until enough}.
    synchronized long[] tokenBucket(String key, int capacity, double millisPerToken, int cost) {
        double[] b = refilled(key, capacity, millisPerToken);
        if (b[0] >= cost) {
            b[0] -= cost;
            return new long[] {1, (long) b[0], 0};
        }
        return new long[] {0, (long) b[0], (long) Math.ceil((cost - b[0]) * millisPerToken)};
    }

    // Another tiny script in real Redis: add back, never above capacity.
    synchronized void refund(String key, int capacity, int cost) {
        check();
        double[] b = buckets.get(key);
        if (b != null) {
            b[0] = Math.min(capacity, b[0] + cost);
        }
    }

    private double[] refilled(String key, int capacity, double millisPerToken) {
        check();
        long now = serverClock.nowMillis();
        double[] b = buckets.computeIfAbsent(key, k -> new double[] {capacity, now});
        if (now > b[1]) {
            b[0] = Math.min(capacity, b[0] + (now - b[1]) / millisPerToken);
            b[1] = now;
        }
        return b;
    }

    private void check() {
        if (down) {
            throw new IllegalStateException("Redis is unreachable");
        }
    }
}
