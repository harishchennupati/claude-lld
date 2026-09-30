import java.util.concurrent.Semaphore;

// For callers that would rather wait than be refused, such as a nightly batch job.
// Never use it for a web request: every waiting caller holds on to a server thread.
class Waiting {
    // Sleeping is handed in, like time, so a test can "sleep" by moving a manual clock.
    @FunctionalInterface
    interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    private final RateLimiter limiter;
    private final Clock clock;
    private final Sleeper sleeper;
    private final Semaphore seats;   // a waiting room: at most this many callers wait at once

    Waiting(RateLimiter limiter, Clock clock, Sleeper sleeper, int maxWaiting) {
        this.limiter = limiter;
        this.clock = clock;
        this.sleeper = sleeper;
        this.seats = new Semaphore(maxWaiting);
    }

    // True once the request is allowed. False at once if it can never fit, if the wait would
    // run past the deadline, or if the waiting room is full.
    boolean acquire(String clientId, int cost, long maxWaitMillis) throws InterruptedException {
        if (!seats.tryAcquire()) {
            return false;                          // too many already waiting: refuse now
        }
        try {
            long deadline = clock.nowMillis() + maxWaitMillis;
            while (true) {
                Decision d = limiter.tryAcquire(clientId, cost);
                if (d.allowed()) {
                    return true;
                }
                long wait = d.retryAfterMillis();
                if (wait == Decision.NEVER || clock.nowMillis() + wait > deadline) {
                    return false;                  // no point sleeping only to fail
                }
                sleeper.sleep(wait);               // exactly as long as the limiter said, then ask
            }
        } finally {
            seats.release();                       // always leave the waiting room
        }
    }
}
