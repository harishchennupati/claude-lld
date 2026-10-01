// The token bucket on its own: 5 a second, told the time by hand.
public class BucketDemo {
    public static void main(String[] args) {
        Counter bucket = new TokenBucket(Limit.perSecond(5), 0);
        StringBuilder log = new StringBuilder();
        for (int i = 1; i <= 6; i++) {
            log.append(String.format("   0 ms  #%d  %s%n", i, Check.show(bucket.tryAcquire(0))));
        }
        Decision at120 = bucket.tryAcquire(120);
        log.append(String.format(" 120 ms  #7  %s%n", Check.show(at120)));
        Decision at200 = bucket.tryAcquire(200);
        log.append(String.format(" 200 ms  #8  %s%n", Check.show(at200)));
        int later = 0;
        for (int i = 0; i < 7; i++) {
            if (bucket.tryAcquire(3_400).allowed()) {
                later++;
            }
        }
        log.append(String.format("3400 ms  7 at once: %d allowed (filled to 5, never more)%n",
                later));
        System.out.print(log);
        Check.that(!at120.allowed() && at120.retryAfterMillis() == 80, "120 ms: retry in 80");
        Check.that(at200.allowed() && later == 5, "200 ms allowed; capped at 5");
    }
}
