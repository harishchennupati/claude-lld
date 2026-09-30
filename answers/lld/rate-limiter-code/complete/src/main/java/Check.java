// Helpers for the demos only (not part of the design): a check that stops the build when a
// number is wrong, and the words the demos print for a decision.
final class Check {
    static void that(boolean ok, String what) {
        if (!ok) {
            throw new AssertionError("demo check failed: " + what);
        }
    }

    // "allowed, 4 left" or "refused, retry in 200 ms"
    static String show(Decision d) {
        if (d.allowed()) {
            return "allowed, " + d.remaining() + " left";
        }
        return "refused, retry in " + d.retryAfterMillis() + " ms";
    }

    // "allowed, 47 left" or "refused by search, retry in 500 ms"
    static String show(RateLimitResult r) {
        if (r.allowed()) {
            return "allowed, " + r.remaining() + " left";
        }
        return "refused by " + r.refusedBy() + ", retry in " + r.retryAfterMillis() + " ms";
    }
}
