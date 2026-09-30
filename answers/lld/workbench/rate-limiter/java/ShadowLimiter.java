//@ file from f5
import java.util.concurrent.atomic.LongAdder;

// Tries a stricter limit without refusing anyone. The live limiter decides every request, exactly
// as before; the candidate is asked as well, and the requests it would have refused are counted.
// It is itself a RateLimiter, so the API is handed this one instead of the live one and cannot
// tell the difference: the Decorator pattern.
class ShadowLimiter implements RateLimiter {
    private final RateLimiter live;
    private final RateLimiter candidate;
    private final LongAdder wouldRefuse = new LongAdder();   // a counter many threads can add to without contention

    ShadowLimiter(RateLimiter live, RateLimiter candidate) {
        this.live = live;
        this.candidate = candidate;
    }

    @Override
    public Decision tryAcquire(String clientId, int cost) {
        Decision d = live.tryAcquire(clientId, cost);
        // Only requests the live limiter allowed matter: those are the ones the new limit would hurt.
        if (d.allowed() && !candidate.tryAcquire(clientId, cost).allowed()) {
            wouldRefuse.increment();
        }
        return d;                                           // always the live answer: the experiment refuses nobody
    }

    long wouldRefuse() {
        return wouldRefuse.sum();
    }
}
