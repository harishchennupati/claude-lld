//@ file from credits
// A fixed window whose unused requests are saved as credits, up to maxCredits, and spent once a
// window's own allowance is used up.
class CreditWindow implements Counter {
    private final int limit;
    private final int maxCredits;
    private final long periodMillis;
    private long windowStart;
    private int used;
    private int credits;

    CreditWindow(Limit limit, int maxCredits, long nowMillis) {
        this.limit = limit.requests();
        this.maxCredits = maxCredits;
        this.periodMillis = limit.periodMillis();
        this.windowStart = nowMillis - nowMillis % periodMillis;
    }

    @Override
    public synchronized Decision tryAcquire(long nowMillis) {
        long start = nowMillis - nowMillis % periodMillis;
        if (start > windowStart) {
            long quietWindows = (start - windowStart) / periodMillis - 1;   // none used at all
            long unused = (limit - used) + quietWindows * limit;
            credits = (int) Math.min(maxCredits, credits + unused);
            windowStart = start;
            used = 0;
        }
        if (used < limit) {
            used++;
            return Decision.allow();
        }
        if (credits > 0) {
            credits--;                       // the window is spent: use savings
            return Decision.allow();
        }
        return Decision.deny(windowStart + periodMillis - nowMillis);
    }
}
