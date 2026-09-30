import java.util.HashMap;
import java.util.Map;
import java.util.function.Function;

// The API's front door. It asks the limiter first, so a refused request is answered at once and
// no real work is done for it. The limiter knows nothing about HTTP; this class knows nothing
// about buckets.
class RateLimitFilter {
    // Just enough of an HTTP response for this page: a status and headers.
    record Response(int status, Map<String, String> headers) { }

    private final RateLimiter limiter;

    RateLimitFilter(RateLimiter limiter) {
        this.limiter = limiter;
    }

    Response handle(RequestContext request, Function<RequestContext, Response> endpoint) {
        RateLimitResult r = limiter.check(request);
        if (!r.allowed()) {
            long seconds = (r.retryAfterMillis() + 999) / 1000;            // 200 ms -> 1 second
            return new Response(429, Map.of("Retry-After", String.valueOf(seconds),
                    "X-RateLimit-Rule", r.refusedBy()));
        }
        Response response = endpoint.apply(request);                      // the real work
        Map<String, String> headers = new HashMap<>(response.headers());
        headers.put("X-RateLimit-Remaining", String.valueOf(r.remaining()));
        return new Response(response.status(), headers);
    }
}
