// Credits: 5 a second, and up to 5 unused requests saved. A lambda is a BucketFactory too.
public class F2Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        BucketFactory withCredits = (limit, now) -> new CreditBucket(limit, 5, now);
        RateLimiter limiter = new ClientRateLimiter(plans, withCredits, clock);

        int s0 = send(limiter, 3);          // second 0: uses 3 of 5, so 2 become credits
        clock.advance(1_000);
        int s1 = send(limiter, 8);          // second 1: 5 + 2 credits
        clock.advance(2_000);               // second 2 is quiet: 5 more saved, but the cap is 5
        int s3 = send(limiter, 12);         // second 3: 5 + 5 credits
        System.out.println("second 0:  3 requests ->  " + s0 + " allowed  (2 unused: credits)");
        System.out.println("second 1:  8 requests ->  " + s1 + " allowed  (5 + 2 credits)");
        System.out.println("second 2:  quiet              (5 more saved, capped at 5)");
        System.out.println("second 3: 12 requests -> " + s3 + " allowed  (5 + 5 credits)");
        Check.that(s0 == 3 && s1 == 7 && s3 == 10, "3, then 7, then 10");
    }

    static int send(RateLimiter limiter, int count) {
        int allowed = 0;
        for (int i = 0; i < count; i++) {
            if (limiter.tryAcquire("score-widget").allowed()) {
                allowed++;
            }
        }
        return allowed;
    }
}
