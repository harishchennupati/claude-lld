//@ file from f2
// Atlassian's version: `capacity` requests per window, and requests a client leaves unused become
// credits, up to `maxCredits`, spent when a window is full. With 5 a second and up to 5 credits,
// a client that made only 3 requests in one second may make 7 in the next.
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
    //@ until f3
    public synchronized Decision tryConsume(long nowMillis) {
        roll(nowMillis);
        if (used < capacity) {
            used++;                                            // this window's requests first...
        } else if (credits > 0) {
            credits--;                                         // ...then the savings
        } else {
            return Decision.deny(windowStart + periodMillis - nowMillis);   // the next window brings more
        }
        return Decision.allow((capacity - used) + credits);
    }
    //@ end
    //@ from f3
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        roll(nowMillis);
        if (cost > capacity + maxCredits) {
            return Decision.never((capacity - used) + credits);
        }
        int fromWindow = Math.min(cost, capacity - used);      // this window's requests first...
        int fromCredits = cost - fromWindow;                   // ...then the savings
        if (fromCredits > credits) {
            // The next window brings `capacity` more: the earliest this could succeed.
            return Decision.deny((capacity - used) + credits, windowStart + periodMillis - nowMillis);
        }
        used += fromWindow;
        credits -= fromCredits;
        return Decision.allow((capacity - used) + credits);
    }
    //@ end
    //@ from f4

    // Give back to this window first: that never hands the client more than it had. If a new
    // window began in between, give nothing back: the client loses one request's worth, never gains.
    @Override
    public synchronized void refund(int cost, long nowMillis) {
        if (windowOf(nowMillis) != windowStart) {
            return;
        }
        int back = Math.min(cost, used);
        used -= back;
        credits = Math.min(maxCredits, credits + (cost - back));
    }
    //@ end

    // When a new window begins, what the ended windows left unused becomes credits.
    private void roll(long nowMillis) {
        long current = windowOf(nowMillis);
        if (current <= windowStart) {
            return;                                            // same window, or an older time: nothing to do
        }
        long ended = (current - windowStart) / periodMillis;   // windows that have ended since
        long unused = (capacity - used) + (ended - 1) * capacity;   // the last one's leftover, plus whole quiet ones
        credits = (int) Math.min(maxCredits, credits + unused);
        windowStart = current;
        used = 0;
    }

    // The start of the window that `nowMillis` falls in: 2,350 ms -> 2,000.
    private long windowOf(long nowMillis) {
        return nowMillis - Math.floorMod(nowMillis, periodMillis);
    }
}
