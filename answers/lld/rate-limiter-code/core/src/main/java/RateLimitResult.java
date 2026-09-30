// The limiter's answer for a whole request, after every rule that covers it has been asked.
//   remaining   the tightest rule's remaining tokens: the X-RateLimit-Remaining header
//   refusedBy   the rule that said no ("search"), or null when the request is allowed
record RateLimitResult(boolean allowed, long remaining, long retryAfterMillis, String refusedBy) {
    static RateLimitResult allowed(long remaining) {
        return new RateLimitResult(true, remaining, 0, null);
    }

    static RateLimitResult refused(Decision decision, String rule) {
        return new RateLimitResult(false, decision.remaining(), decision.retryAfterMillis(), rule);
    }
}
