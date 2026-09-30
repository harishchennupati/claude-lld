// The answer to "may this client make a request now?"
//   allowed           yes or no
//   remaining         whole tokens left after this request: the X-RateLimit-Remaining header
//   retryAfterMillis  if refused, how long until a retry can succeed: the Retry-After header
record Decision(boolean allowed, long remaining, long retryAfterMillis) {
    //@ from f3

    // The retry time of a request that costs more than the whole bucket: no wait will ever help.
    static final long NEVER = -1;
    //@ end

    static Decision allow(long remaining) {
        return new Decision(true, remaining, 0);
    }

    static Decision deny(long retryAfterMillis) {
        return new Decision(false, 0, retryAfterMillis);
    }
    //@ from f3

    // A costly request can be refused while some tokens remain: 3 left, the history needs 5.
    static Decision deny(long remaining, long retryAfterMillis) {
        return new Decision(false, remaining, retryAfterMillis);
    }

    static Decision never(long remaining) {
        return new Decision(false, remaining, NEVER);
    }
    //@ end

    // What the demos print: "allowed, 4 left" or "refused, retry in 200 ms".
    @Override
    public String toString() {
        if (allowed) {
            return "allowed, " + remaining + " left";
        }
        //@ from f3
        if (retryAfterMillis == NEVER) {
            return "refused for good: it costs more than the whole bucket";
        }
        //@ end
        //@ until f3
        return "refused, retry in " + retryAfterMillis + " ms";
        //@ end
        //@ from f3
        String left = remaining > 0 ? " (" + remaining + " left)" : "";
        return "refused" + left + ", retry in " + retryAfterMillis + " ms";
        //@ end
    }
}
