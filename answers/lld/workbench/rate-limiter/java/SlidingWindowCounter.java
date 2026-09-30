//@ file from more
// Nearly exact with two numbers: this window's count, and the last window's count weighted by
// how much of it is still inside the last `periodMillis`. 300 ms into a second, 70% of the last
// second still counts: estimate = previous x 0.7 + current. It assumes the previous window's
// requests were spread evenly; if they were bunched at its end, it lets a few too many through.
class SlidingWindowCounter implements Bucket {
    private final int limit;
    private final long periodMillis;
    private long windowStart;
    private int previous;              // requests in the window before the current one
    private int current;               // requests in the current window

    SlidingWindowCounter(Limit limit, long nowMillis) {
        this.limit = limit.capacity();
        this.periodMillis = limit.periodMillis();
        this.windowStart = nowMillis - Math.floorMod(nowMillis, periodMillis);
    }

    @Override
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        roll(nowMillis);
        double estimate = estimate(nowMillis);
        if (estimate + cost <= limit) {
            current += cost;
            return Decision.allow((long) (limit - estimate - cost));
        }
        return Decision.deny((long) Math.max(0, limit - estimate), waitFor(cost, nowMillis));
    }

    // When will `cost` more fit? In this window, once enough of the previous one has slid out;
    // otherwise in the next window, where this window's count becomes the "previous" one.
    private long waitFor(int cost, long nowMillis) {
        long end = windowStart + periodMillis;
        double room = limit - current - cost;          // what the previous window may still hold
        if (previous > 0 && room >= 0) {
            double at = windowStart + periodMillis * (1 - room / previous);
            if (at < end) {
                return (long) Math.ceil(at - nowMillis);
            }
        }
        double nextRoom = limit - cost;
        double at = current <= nextRoom ? end : end + periodMillis * (1 - nextRoom / current);
        return (long) Math.ceil(at - nowMillis);
    }

    @Override
    public synchronized void refund(int cost, long nowMillis) {
        roll(nowMillis);
        current = Math.max(0, current - cost);
    }

    //@ from idle
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        return nowMillis - windowStart >= 2 * periodMillis || previous + current == 0;
    }
    //@ end

    private double estimate(long nowMillis) {
        double stillInside = 1.0 - (double) (nowMillis - windowStart) / periodMillis;
        return previous * stillInside + current;
    }

    private void roll(long nowMillis) {
        long start = nowMillis - Math.floorMod(nowMillis, periodMillis);
        if (start <= windowStart) {
            return;
        }
        previous = start - windowStart == periodMillis ? current : 0;   // older than one window
        current = 0;
        windowStart = start;
    }
}
