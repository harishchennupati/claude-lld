// The answer: go ahead, or not yet and how long to wait (the API sends it as Retry-After).
record Decision(boolean allowed, long retryAfterMillis) {
    static Decision allow() {
        return new Decision(true, 0);
    }

    static Decision deny(long retryAfterMillis) {
        return new Decision(false, retryAfterMillis);
    }
}
