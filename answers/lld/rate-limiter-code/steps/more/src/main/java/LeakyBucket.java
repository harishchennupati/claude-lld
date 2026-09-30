// A leaky bucket used as a meter: each request pours `cost` into a bucket of size `capacity`,
// which drains at a steady rate. Full means refused. It is the token bucket upside down (its
// level is capacity minus tokens) and gives the same answers, up to floating-point rounding on
// the edge. As a QUEUE instead (requests wait in the bucket and leave at the drain rate) it
// smooths traffic, which suits sending, not answering yes or no.
class LeakyBucket implements Bucket {
    private final int capacity;
    private final double millisPerUnit;   // how long one unit takes to drain
    private double level;                 // how full it is: 0 when idle
    private long lastLeakMillis;

    LeakyBucket(Limit limit, long nowMillis) {
        this.capacity = limit.capacity();
        this.millisPerUnit = limit.millisPerToken();
        this.lastLeakMillis = nowMillis;
    }

    @Override
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        leak(nowMillis);
        if (level + cost <= capacity) {
            level += cost;
            return Decision.allow((long) (capacity - level));
        }
        long wait = (long) Math.ceil((level + cost - capacity) * millisPerUnit);
        return Decision.deny((long) (capacity - level), wait);
    }

    @Override
    public synchronized void refund(int cost, long nowMillis) {
        leak(nowMillis);
        level = Math.max(0, level - cost);
    }

    private void leak(long nowMillis) {
        long elapsed = nowMillis - lastLeakMillis;
        if (elapsed <= 0) {
            return;
        }
        level = Math.max(0, level - elapsed / millisPerUnit);
        lastLeakMillis = nowMillis;
    }
}
