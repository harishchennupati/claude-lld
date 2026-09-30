// One bucket's answer to "may this request spend `cost` tokens now?"
//   allowed           yes or no
//   remaining         whole tokens left after this request
//   retryAfterMillis  if refused, how long until enough tokens are there; NEVER if they never
//                     will be (the request costs more than the whole bucket)
record Decision(boolean allowed, long remaining, long retryAfterMillis) {
    static final long NEVER = -1;

    static Decision allow(long remaining) {
        return new Decision(true, remaining, 0);
    }

    static Decision deny(long remaining, long retryAfterMillis) {
        return new Decision(false, remaining, retryAfterMillis);
    }

    static Decision never(long remaining) {
        return new Decision(false, remaining, NEVER);
    }

    // What the demos print: "allowed, 4 left" or "refused, retry in 200 ms".
    @Override
    public String toString() {
        if (allowed) {
            return "allowed, " + remaining + " left";
        }
        if (retryAfterMillis == NEVER) {
            return "refused for good: costs more than the whole bucket";
        }
        return "refused, retry in " + retryAfterMillis + " ms";
    }
}
