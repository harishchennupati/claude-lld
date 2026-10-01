// A count per clock window, reset when a new window starts: right for "10,000 a day", where the
// calendar day (UTC here) is the rule. Across a window's edge it lets twice the limit through.
class FixedWindowCounter implements Counter {
    private final int limit;
    private final long periodMillis;
    private long windowStart;
    private int count;

    FixedWindowCounter(Limit limit, long nowMillis) {
        this.limit = limit.requests();
        this.periodMillis = limit.periodMillis();
        this.windowStart = nowMillis - nowMillis % periodMillis;
    }

    @Override
    public synchronized Decision tryAcquire(long nowMillis) {
        long start = nowMillis - nowMillis % periodMillis;
        if (start > windowStart) {           // a new window: the count starts again
            windowStart = start;
            count = 0;
        }
        if (count < limit) {
            count++;
            return Decision.allow();
        }
        return Decision.deny(windowStart + periodMillis - nowMillis);   // the window's end
    }

    @Override
    public synchronized void refund(long nowMillis) {
        if (nowMillis - nowMillis % periodMillis == windowStart && count > 0) {
            count--;
        }
    }
}
