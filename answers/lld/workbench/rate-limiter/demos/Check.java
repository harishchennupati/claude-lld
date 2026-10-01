// Helpers for the demos only (not part of the design): a check that stops the build when a
// number is wrong, and the words the demos print for a decision.
final class Check {
    static void that(boolean ok, String what) {
        if (!ok) {
            throw new AssertionError("demo check failed: " + what);
        }
    }

    static String show(Decision d) {
        return d.allowed() ? "allowed" : "refused, retry in " + d.retryAfterMillis() + " ms";
    }
}
