import java.util.Collections;
import java.util.Map;
import java.util.TreeMap;
import java.util.function.Function;

// The API's front door. It asks the limiter first, so a refused request is answered at once and
// no real work is done for it. The limiter knows nothing about HTTP; this class knows nothing
// about buckets.
class RateLimitFilter {
    // Just enough of an HTTP response for this page: a status and headers.
    record Response(int status, Map<String, String> headers) {
        Response {
            headers = Collections.unmodifiableMap(new TreeMap<>(headers));   // sorted: stable
        }

        Response withHeader(String name, String value) {
            Map<String, String> more = new TreeMap<>(headers);
            more.put(name, value);
            return new Response(status, more);
        }
    }

    private final RateLimiter limiter;

    RateLimitFilter(RateLimiter limiter) {
        this.limiter = limiter;
    }

    Response handle(RequestContext request, Function<RequestContext, Response> endpoint) {
        RateLimitResult r = limiter.check(request);
        if (!r.allowed() && r.retryAfterMillis() == Decision.NEVER) {
            // No wait will ever help: it costs more than the rule allows at once. 413 says
            // "make it smaller"; a 429 would send the client into endless retries.
            return new Response(413, Map.of("X-RateLimit-Rule", r.refusedBy()));
        }
        if (!r.allowed()) {
            long seconds = (r.retryAfterMillis() + 999) / 1000;            // 200 ms -> 1 second
            return new Response(429, Map.of("Retry-After", String.valueOf(seconds),
                    "X-RateLimit-Rule", r.refusedBy()));
        }
        Response response = endpoint.apply(request);                      // the real work
        if (r.remaining() == RateLimitResult.UNLIMITED) {
            return response;
        }
        // X-RateLimit-* is the convention GitHub and others use; the IETF draft says RateLimit.
        return response.withHeader("X-RateLimit-Remaining", String.valueOf(r.remaining()));
    }
}
