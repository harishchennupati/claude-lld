// The follow-up demos check their own numbers, so a wrong result stops the build.
final class Check {
    static void that(boolean ok, String what) {
        if (!ok) {
            throw new AssertionError("demo check failed: " + what);
        }
    }
}
