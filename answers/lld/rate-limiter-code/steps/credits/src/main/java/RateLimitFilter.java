import java.util.Map;
import java.util.function.Supplier;

// The front door. Asks the limiter first: refused requests get 429 at once and nothing else runs.
// The limiter knows nothing about HTTP; this class knows nothing about rules or counting.
class RateLimitFilter {
    record Response(int status, Map<String, String> headers) {
    }

    private final RateLimiter limiter;

    RateLimitFilter(RateLimiter limiter) {
        this.limiter = limiter;
    }

    Response handle(Request request, Supplier<Response> work) {
        RateLimitResult result = limiter.check(request);
        if (result.allowed()) {
            return work.get();
        }
        long seconds = (result.retryAfterMillis() + 999) / 1000;   // whole seconds, rounded up
        return new Response(429, Map.of("Retry-After", String.valueOf(seconds),
                "X-RateLimit-Rule", result.refusedBy()));
    }
}
