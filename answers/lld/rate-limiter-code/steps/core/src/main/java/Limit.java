// "X requests every Y": the whole of a limit, as a value.
// Why a record: two numbers that never change. perSecond(5) and perDay(10_000) are static factory
// methods: named ways to make one that read better than new Limit(5, 1000).
record Limit(int requests, long periodMillis) {
    static Limit perSecond(int requests) {
        return new Limit(requests, 1_000);
    }

    static Limit perMinute(int requests) {
        return new Limit(requests, 60_000);
    }

    static Limit perDay(int requests) {
        return new Limit(requests, 86_400_000);
    }
}
