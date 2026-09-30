import java.util.concurrent.Semaphore;

// For callers that would rather wait than be refused, such as a nightly batch job. Never for a
// web request: every waiting caller holds on to a thread.
class Waiting {
    // Sleeping is handed in, like time, so a test can "sleep" by moving a manual clock.
    @FunctionalInterface
    interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    private final RateLimiter limiter;
    private final Sleeper sleeper;
    private final Semaphore seats;   // a waiting room: at most this many callers wait at once

    Waiting(RateLimiter limiter, Sleeper sleeper, int maxWaiting) {
        this.limiter = limiter;
        this.sleeper = sleeper;
        this.seats = new Semaphore(maxWaiting);
    }

    // True once the request is allowed. False at once if the waits would add up to more than
    // maxWaitMillis, or if the waiting room is full. A request that needs no wait needs no seat.
    boolean acquire(RequestContext request, long maxWaitMillis) throws InterruptedException {
        RateLimitResult r = limiter.check(request);
        if (r.allowed()) {
            return true;
        }
        if (!seats.tryAcquire()) {
            return false;                         // too many already waiting: refuse now
        }
        try {
            long waited = 0;                      // what we have slept so far: no clock needed
            while (!r.allowed()) {
                long wait = r.retryAfterMillis();
                if (waited + wait > maxWaitMillis) {
                    return false;                 // no point sleeping only to fail
                }
                sleeper.sleep(wait);              // exactly as long as the limiter said, then ask
                waited += wait;
                r = limiter.check(request);
            }
            return true;
        } finally {
            seats.release();                      // always leave the waiting room, even when
        }                                         // the sleep is interrupted at shutdown
    }
}
