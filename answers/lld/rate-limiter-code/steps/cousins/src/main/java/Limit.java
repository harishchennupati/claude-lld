// A limit such as "5 requests per second": a bucket that holds `capacity` tokens and earns all
// of them back over `periodMillis`.
record Limit(int capacity, long periodMillis) {
    static Limit perSecond(int n) {
        return new Limit(n, 1_000);
    }

    static Limit perMinute(int n) {
        return new Limit(n, 60_000);
    }

    static Limit perDay(int n) {
        return new Limit(n, 86_400_000);
    }

    // How long one token takes to come back: 5 per second -> 200 ms.
    double millisPerToken() {
        return (double) periodMillis / capacity;
    }
}
