//@ file from live
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

// Tries new rules without refusing anyone. The live limiter decides every request, exactly as
// before; the candidate is asked too, and whom it would have refused is counted per client. It
// is itself a RateLimiter, so the filter is handed this one and cannot tell: the Decorator
// pattern (implement the interface, hold one, add behaviour).
class ShadowRateLimiter implements RateLimiter {
    private final RateLimiter live;
    private final RateLimiter candidate;
    private final ConcurrentHashMap<String, LongAdder> wouldRefuse = new ConcurrentHashMap<>();

    ShadowRateLimiter(RateLimiter live, RateLimiter candidate) {
        this.live = live;
        this.candidate = candidate;
    }

    @Override
    public RateLimitResult check(RequestContext request) {
        RateLimitResult r = live.check(request);
        // Only requests the live rules allowed matter: those are the ones the new rules would hurt.
        if (r.allowed() && !candidate.check(request).allowed()) {
            wouldRefuse.computeIfAbsent(request.clientId(), k -> new LongAdder()).increment();
        }
        return r;                         // always the live answer: the experiment refuses nobody
    }

    // Whom the new rules would hurt, and how often: what ops read before switching them on.
    Map<String, Long> report() {
        Map<String, Long> out = new TreeMap<>();
        wouldRefuse.forEach((client, count) -> out.put(client, count.sum()));
        return out;
    }
}
