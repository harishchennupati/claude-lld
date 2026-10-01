// One counter's answer: go ahead, or not yet and how many milliseconds until it would.
// Why a record: plain data, never changed. allow() and deny(ms) are static factory methods that
// name the two kinds of answer.
record Decision(boolean allowed, long retryAfterMillis) {
    static Decision allow() {
        return new Decision(true, 0);
    }

    static Decision deny(long retryAfterMillis) {
        return new Decision(false, retryAfterMillis);
    }
}
