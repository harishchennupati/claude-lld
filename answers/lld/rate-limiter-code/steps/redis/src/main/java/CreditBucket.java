// Atlassian's version: `capacity` requests per window, and requests a client leaves unused
// become credits, up to `maxCredits`, spent once a window is full. With 5 a second and up to
// 5 credits, a client that made only 3 requests in one second may make 7 in the next. Credits
// are real savings, so this bucket must never be thrown away as idle (see Idle clients).
class CreditBucket implements Bucket {
    private final int capacity;        // requests per window: 5
    private final long periodMillis;   // the window: 1,000 ms
    private final int maxCredits;      // the most that can be saved: 5
    private long windowStart;          // when the current window began
    private int used;                  // requests taken from the current window
    private int credits;               // saved from earlier windows; a new client has none yet

    CreditBucket(Limit limit, int maxCredits, long nowMillis) {
        this.capacity = limit.capacity();
        this.periodMillis = limit.periodMillis();
        this.maxCredits = maxCredits;
        this.windowStart = windowOf(nowMillis);
    }

    @Override
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        roll(nowMillis);
        long left = (capacity - used) + credits;
        int fromWindow = Math.min(cost, capacity - used);   // this window's requests first...
        int fromCredits = cost - fromWindow;                // ...then the savings
        if (fromCredits > credits) {
            // The next window brings `capacity` more: the earliest this could succeed.
            return Decision.deny(left, windowStart + periodMillis - nowMillis);
        }
        used += fromWindow;
        credits -= fromCredits;
        return Decision.allow(left - cost);
    }

    // Back to this window first; if a new window began in between, nothing comes back.
    @Override
    public synchronized void refund(int cost, long nowMillis) {
        if (windowOf(nowMillis) != windowStart) {
            return;
        }
        int back = Math.min(cost, used);
        used -= back;
        credits = Math.min(maxCredits, credits + (cost - back));
    }

    // When a new window begins, what the ended windows left unused becomes credits: the last
    // window's leftover, plus a full window for every window with no requests at all.
    private void roll(long nowMillis) {
        long current = windowOf(nowMillis);
        if (current <= windowStart) {
            return;                                         // same window, or an older time
        }
        long quietWindows = (current - windowStart) / periodMillis - 1;  // windows nobody used
        long unused = (capacity - used) + quietWindows * capacity;       // + this one's leftover
        credits = (int) Math.min(maxCredits, credits + unused);
        windowStart = current;
        used = 0;
    }

    private long windowOf(long nowMillis) {
        return nowMillis - Math.floorMod(nowMillis, periodMillis);
    }
}
