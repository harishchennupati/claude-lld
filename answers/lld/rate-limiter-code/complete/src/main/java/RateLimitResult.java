// The limiter's answer for a whole request. When refused, it says which rule refused and
// how long to wait, so the front door can send 429 with a Retry-After header.
// Why a record, not a boolean: a boolean can only say yes or no; this carries three values, and
// like any answer it never changes once made.
record RateLimitResult(boolean allowed, long retryAfterMillis, String refusedBy) {
    static final RateLimitResult ALLOWED = new RateLimitResult(true, 0, null);

    static RateLimitResult refused(String rule, long retryAfterMillis) {
        return new RateLimitResult(false, retryAfterMillis, rule);
    }
}
