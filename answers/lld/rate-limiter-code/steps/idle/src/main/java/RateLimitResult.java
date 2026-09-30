// The limiter's answer for a whole request, after every rule that covers it has been asked.
//   remaining   the tightest rule's remaining tokens: the X-RateLimit-Remaining header
//   refusedBy   the rule that said no ("search"), or null when the request is allowed
record RateLimitResult(boolean allowed, long remaining, long retryAfterMillis, String refusedBy) {
    // No rule covered the request, so nothing limits it: the filter sends no Remaining header.
    static final long UNLIMITED = Long.MAX_VALUE;

    static RateLimitResult allowed(long remaining) {
        return new RateLimitResult(true, remaining, 0, null);
    }

    static RateLimitResult refused(Decision decision, String rule) {
        return new RateLimitResult(false, decision.remaining(), decision.retryAfterMillis(), rule);
    }

    @Override
    public String toString() {
        if (allowed) {
            return remaining == UNLIMITED ? "allowed" : "allowed, " + remaining + " left";
        }
        if (retryAfterMillis == Decision.NEVER) {
            return "refused for good by " + refusedBy;
        }
        return "refused by " + refusedBy + ", retry in " + retryAfterMillis + " ms";
    }
}
