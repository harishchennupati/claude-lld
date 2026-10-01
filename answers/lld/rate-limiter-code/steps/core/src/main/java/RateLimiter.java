// The one question the front door asks before any work: may this request go ahead now?
// The filter calls only this interface, never a concrete class, so the class that does the work
// can change (another limiter, a dry-run wrapper) without the filter changing.
interface RateLimiter {
    RateLimitResult check(Request request);

    // The interviewer's own signature, kept as a one-line convenience. Endpoint "/" and no IP:
    // only the customer-wide rules and the global cap can match it.
    default boolean rateLimit(String customerId) {
        return check(new Request(customerId, null, "/")).allowed();
    }
}
