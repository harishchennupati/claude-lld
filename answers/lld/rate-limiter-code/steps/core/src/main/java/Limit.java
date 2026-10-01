// "X requests every Y": the whole of a limit.
record Limit(int requests, long periodMillis) {
    static Limit perSecond(int requests) {
        return new Limit(requests, 1_000);
    }

    static Limit perMinute(int requests) {
        return new Limit(requests, 60_000);
    }
}
