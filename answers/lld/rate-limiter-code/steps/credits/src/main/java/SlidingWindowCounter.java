// The log's answer, guessed from two counts: this window's, and the last window's, assumed to be
// spread evenly. Two numbers per key instead of one timestamp per request.
class SlidingWindowCounter implements Counter {
    private final int limit;
    private final long periodMillis;
    private long windowStart;
    private int previous;
    private int current;

    SlidingWindowCounter(Limit limit, long nowMillis) {
        this.limit = limit.requests();
        this.periodMillis = limit.periodMillis();
        this.windowStart = nowMillis - nowMillis % periodMillis;
    }

    @Override
    public synchronized Decision tryAcquire(long nowMillis) {
        long start = nowMillis - nowMillis % periodMillis;
        if (start > windowStart) {           // moved on: one window, or more if it was quiet
            previous = (start - windowStart == periodMillis) ? current : 0;
            current = 0;
            windowStart = start;
        }
        double shareOfPrevious = 1 - (double) (nowMillis - windowStart) / periodMillis;
        double guess = previous * shareOfPrevious + current;
        if (guess + 1 <= limit) {
            current++;
            return Decision.allow();
        }
        return Decision.deny(windowStart + periodMillis - nowMillis);   // at most this long
    }

    @Override
    public synchronized void refund(long nowMillis) {
        if (current > 0) {
            current--;
        }
    }
}
