// The limiter on its own (no HTTP yet): four rules on one search, all or nothing, and a
// listener that counts refusals.
public class LimiterDemo {
    public static void main(String[] args) {
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);
        RuleBasedRateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(plans),
                new InMemoryBucketStore(), new ManualClock(0));
        RefusalMetrics metrics = new RefusalMetrics();
        limiter.addListener(metrics);
        RequestContext search = RequestContext.of("fantasy-app", "203.0.113.7", "/search");
        RequestContext scores = RequestContext.of("fantasy-app", "203.0.113.7", "/scores");
        for (int i = 1; i <= 3; i++) {
            System.out.println("/search #" + i + "  " + Check.show(limiter.check(search)));
        }
        RateLimitResult next = limiter.check(scores);
        System.out.println("/scores     " + Check.show(next)
                + "   (47, not 46: the 3rd search spent nothing)");
        System.out.println("metrics     " + metrics.snapshot());
        Check.that(next.remaining() == 47, "the refused search gave its plan token back");
    }
}
