// The one question the front door asks before any work. The door depends on this interface,
// never on the class behind it.
interface RateLimiter {
    RateLimitResult check(Request request);

    // The interviewer's own signature: a customer, yes or no. Endpoint "/" and no IP, so only
    // the customer-wide rules and the global cap apply.
    default boolean rateLimit(String customerId) {
        return check(new Request(customerId, null, "/")).allowed();
    }
}
