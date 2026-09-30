// 1,000 clients call once and never again; score-widget keeps calling. Sweeps forget what a new
// bucket would replace exactly: token buckets once they are full again, quota buckets only
// once their day is over.
public class IdleDemo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        InMemoryBucketStore store = new InMemoryBucketStore();
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(new Plans()), store,
                clock);
        for (int i = 0; i < 1_000; i++) {
            limiter.check(RequestContext.of("one-time-" + i, "203.0.113.7", "/scores"));
        }
        clock.advance(900);
        limiter.check(RequestContext.of("score-widget", "203.0.113.7", "/scores"));
        clock.advance(100);
        System.out.println("buckets at 1,000 ms:   " + store.size()
                + "  (a plan and a quota bucket per client, one global)");
        int first = store.evictIdle(clock.nowMillis());
        System.out.println("sweep at 1,000 ms:     removed " + first + ", left " + store.size()
                + "  (quota buckets hold today's counts)");
        clock.advance(86_400_000);                            // the next day
        int second = store.evictIdle(clock.nowMillis());
        System.out.println("sweep the next day:    removed " + second + ", left " + store.size());
        Check.that(first == 1_000 && second == 1_003 && store.size() == 0, "1,000 then 1,003");
    }
}
