// One counter per window: 10,000 requests a day, starting again at midnight (UTC). Here the
// window IS the rule, a quota per calendar day, so the fixed window's flaw (twice the limit
// across a window edge) does not matter: the per-second rules still stop any burst.
class FixedWindowCounter implements Bucket {
    private final int limit;
    private final long periodMillis;
    private long windowStart;         // where the current window began: a multiple of the period
    private int used;

    FixedWindowCounter(Limit limit, long nowMillis) {
        this.limit = limit.capacity();
        this.periodMillis = limit.periodMillis();
        this.windowStart = windowOf(nowMillis);
    }

    @Override
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        roll(nowMillis);
        if (cost > limit) {
            return Decision.never(limit - used);
        }
        if (used + cost <= limit) {
            used += cost;
            return Decision.allow(limit - used);
        }
        return Decision.deny(limit - used, windowStart + periodMillis - nowMillis);  // next window
    }

    // Only within the same window: after midnight the count started again anyway.
    @Override
    public synchronized void refund(int cost, long nowMillis) {
        if (windowOf(nowMillis) == windowStart) {
            used = Math.max(0, used - cost);
        }
    }

    //@ from idle
    // A quota bucket holds today's count, so it is idle only when that count is zero or the day
    // is over: a sweep at noon keeps it, a sweep after midnight removes it.
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        return used == 0 || windowOf(nowMillis) > windowStart;
    }

    //@ end
    // A later window starts from zero. An older time (an earlier clock reading, or the wall
    // clock jumping back) stays in the current window.
    private void roll(long nowMillis) {
        long current = windowOf(nowMillis);
        if (current > windowStart) {
            windowStart = current;
            used = 0;
        }
    }

    // The start of the window that `nowMillis` falls in. With days and epoch time: midnight UTC.
    private long windowOf(long nowMillis) {
        return nowMillis - Math.floorMod(nowMillis, periodMillis);
    }
}
