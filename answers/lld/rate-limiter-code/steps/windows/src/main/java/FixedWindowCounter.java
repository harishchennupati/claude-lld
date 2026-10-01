// A count per clock window, reset when a new window starts. Simple, and exact for calendar
// quotas, but 5 at 995 ms and 5 at 1001 ms both pass: twice the limit across the edge.
class FixedWindowCounter implements Counter {
    private final int limit;
    private final long periodMillis;
    private long windowStart;
    private int count;

    FixedWindowCounter(Limit limit, long nowMillis) {
        this.limit = limit.requests();
        this.periodMillis = limit.periodMillis();
        this.windowStart = nowMillis - nowMillis % periodMillis;    // follow the clock (UTC days)
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
}
