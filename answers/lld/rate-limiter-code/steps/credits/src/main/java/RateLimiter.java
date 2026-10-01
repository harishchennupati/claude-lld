// The one question the front door asks before any work: may this request go ahead now?
// Why an interface: the door depends on this promise, never on the class behind it, so that class
// can change (another limiter, a dry-run wrapper) without the door knowing.
interface RateLimiter {
    RateLimitResult check(Request request);

    // The interviewer's own signature, kept as a one-line convenience. Endpoint "/" and no IP:
    // only the customer-wide rules and the global cap can match it.
    default boolean rateLimit(String customerId) {
        return check(new Request(customerId, null, "/")).allowed();
    }
}
