// The one question the API asks before it does any work for a request. The API depends on this
// interface, never on a class behind it: a Redis-backed or a shadow limiter drops in unseen.
interface RateLimiter {
    RateLimitResult check(RequestContext request);

    // The interviewer's `boolean rateLimit(customerId)`, true meaning "go ahead": one line on
    // top, for callers that have only a client id. Implementations get it for free.
    default boolean rateLimit(String customerId) {
        // No IP or endpoint is known: the endpoint rules (search, login) never match it.
        return check(RequestContext.of(customerId, "-", "/")).allowed();
    }
}
