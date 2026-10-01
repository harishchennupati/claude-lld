// The fixed window: a count per window of the clock (a calendar day for the daily quota, UTC),
// reset to 0 when a new window starts. Right when the calendar is the rule; across a window's
// edge it can let twice the limit through, which is why the per-second rules do not use it.
class FixedWindowCounter implements Counter {
    private final int limit;
    private final long periodMillis;
    private long windowStart;                // where the current window began
    private int count;                       // requests allowed in it so far

    FixedWindowCounter(Limit limit, long nowMillis) {
        this.limit = limit.requests();
        this.periodMillis = limit.periodMillis();
        this.windowStart = nowMillis - nowMillis % periodMillis;   // windows follow the clock
    }

    @Override
    public synchronized Decision tryAcquire(long nowMillis) {
        long start = nowMillis - nowMillis % periodMillis;
        if (start > windowStart) {           // a new window has begun: the count starts again
            windowStart = start;
            count = 0;
        }
        if (count < limit) {
            count++;
            return Decision.allow();
        }
        return Decision.deny(windowStart + periodMillis - nowMillis);   // until the window ends
    }

    @Override
    public synchronized void refund(long nowMillis) {
        boolean sameWindow = nowMillis - nowMillis % periodMillis == windowStart;
        if (sameWindow && count > 0) {
            count--;                         // a new window already starts from 0: nothing to do
        }
    }
}
