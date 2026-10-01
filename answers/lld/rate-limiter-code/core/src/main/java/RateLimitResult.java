// The limiter's answer for a whole request: go ahead, or which rule refused and when to retry.
record RateLimitResult(boolean allowed, long retryAfterMillis, String refusedBy) {
    static final RateLimitResult ALLOWED = new RateLimitResult(true, 0, null);

    static RateLimitResult refused(String rule, long retryAfterMillis) {
        return new RateLimitResult(false, retryAfterMillis, rule);
    }
}
