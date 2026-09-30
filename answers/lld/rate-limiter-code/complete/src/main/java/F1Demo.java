// Logins, 5 a minute. Someone tries 5 times at 0 s, then once every 12 s. The token bucket
// earns a token back every 12 s, so it lets 9 through in the first minute; the log, exactly 5.
public class F1Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans logins = new Plans(Limit.perMinute(5), Limit.perMinute(5));   // 5 a minute, any plan
        RateLimiter bucket = new ClientRateLimiter(logins, TokenBucket::new, clock);
        // The only difference between the two limiters: which factory makes the buckets.
        RateLimiter log = new ClientRateLimiter(logins, SlidingWindowLog::new, clock);

        int byBucket = 0;
        int byLog = 0;
        System.out.println("time   token bucket              sliding window log");
        for (int second = 0; second <= 60; second += 12) {
            clock.advance(second * 1_000L - clock.nowMillis());
            if (second == 0) {                            // 5 tries at once: both allow all 5
                for (int i = 0; i < 5; i++) {
                    byBucket += bucket.tryAcquire("priya@login").allowed() ? 1 : 0;
                    byLog += log.tryAcquire("priya@login").allowed() ? 1 : 0;
                }
                System.out.println(" 0 s   5 tries: 5 allowed        5 tries: 5 allowed");
                continue;
            }
            Decision b = bucket.tryAcquire("priya@login");
            Decision l = log.tryAcquire("priya@login");
            if (second < 60) {
                byBucket += b.allowed() ? 1 : 0;
                byLog += l.allowed() ? 1 : 0;
            }
            System.out.printf("%2d s   %-26s%s%n", second, b, l);
        }
        System.out.printf("%nin the first minute: token bucket %d, sliding window log %d%n",
                byBucket, byLog);
        Check.that(byBucket == 9 && byLog == 5, "9 by the bucket, 5 by the log");
    }
}
