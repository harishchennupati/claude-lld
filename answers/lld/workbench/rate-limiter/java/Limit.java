// A limit such as "5 requests per second": a bucket that holds `capacity` tokens
// and earns all of them back over `periodMillis`.
record Limit(int capacity, long periodMillis) {

    // A compact constructor runs on every `new Limit(...)`. A bad limit fails here,
    // at startup, not as a division by zero deep inside a bucket later.
    Limit {
        if (capacity <= 0 || periodMillis <= 0) {
            throw new IllegalArgumentException("capacity and period must be > 0");
        }
    }

    static Limit perSecond(int n) {
        return new Limit(n, 1_000);
    }

    static Limit perMinute(int n) {
        return new Limit(n, 60_000);
    }

    // How long one token takes to come back: 5 per second -> 200 ms.
    double millisPerToken() {
        return (double) periodMillis / capacity;
    }
}
