// The answer to "may this client make a request now?"
//   allowed           yes or no
//   remaining         whole tokens left after this request: the X-RateLimit-Remaining header
//   retryAfterMillis  if refused, how long until a retry can succeed: the Retry-After header
record Decision(boolean allowed, long remaining, long retryAfterMillis) {
    static Decision allow(long remaining) {
        return new Decision(true, remaining, 0);
    }

    static Decision deny(long retryAfterMillis) {
        return new Decision(false, 0, retryAfterMillis);
    }

    // What the demos print: "allowed, 4 left" or "refused, retry in 200 ms".
    @Override
    public String toString() {
        if (allowed) {
            return "allowed, " + remaining + " left";
        }
        return "refused, retry in " + retryAfterMillis + " ms";
    }
}
