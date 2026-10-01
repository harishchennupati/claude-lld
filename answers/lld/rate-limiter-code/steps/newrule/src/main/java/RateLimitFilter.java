import java.util.Map;
import java.util.function.Supplier;

// The front door: every request passes through here before any endpoint runs, so no endpoint can
// forget the check. It knows HTTP and nothing about rules; the limiter knows rules and nothing
// about HTTP.
class RateLimitFilter {
    record Response(int status, Map<String, String> headers) {
    }

    private final RateLimiter limiter;

    RateLimitFilter(RateLimiter limiter) {
        this.limiter = limiter;
    }

    // `work` is the real endpoint. It runs only if the limiter allows the request.
    Response handle(Request request, Supplier<Response> work) {
        RateLimitResult result = limiter.check(request);
        if (result.allowed()) {
            return work.get();
        }
        // Retry-After is in whole seconds. Round up: a wait of 200 ms must say 1, not 0, or the
        // client comes straight back and is refused again.
        long seconds = (result.retryAfterMillis() + 999) / 1000;
        return new Response(429, Map.of("Retry-After", String.valueOf(seconds),
                "X-RateLimit-Rule", result.refusedBy()));
    }
}
