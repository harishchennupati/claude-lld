// The one question the API asks before it does any work: may this caller go ahead now?
// The API depends on this interface, never on the class behind it.
interface RateLimiter {
    // key: who is counted. The customer id here; later an IP, or "customer + endpoint".
    Decision check(String key);

    // The interviewer's own signature: just yes or no.
    default boolean rateLimit(String customerId) {
        return check(customerId).allowed();
    }
}
