// The answers to the "predict the output" questions, printed by the real code.
public class QuizDemo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(plans),
                new InMemoryBucketStore(), clock);
        RequestContext widget = RequestContext.of("score-widget", "203.0.113.7", "/scores");

        // 1. score-widget (FREE): 5 requests at 0 ms, then 3 at 450 ms.
        for (int i = 0; i < 5; i++) {
            limiter.check(widget);
        }
        clock.advance(450);
        for (int i = 1; i <= 3; i++) {
            System.out.println("1.  450 ms  #" + i + "  " + Check.show(limiter.check(widget)));
        }

        // 2. fantasy-app (PRO, 50 a second): one request, 10 quiet seconds, then 60 at once.
        RequestContext fantasy = RequestContext.of("fantasy-app", "203.0.113.7", "/scores");
        limiter.check(fantasy);
        clock.advance(10_000);
        int allowed = 0;
        for (int i = 0; i < 60; i++) {
            allowed += limiter.check(fantasy).allowed() ? 1 : 0;
        }
        System.out.println("2.  60 at once after 10 quiet seconds: " + allowed + " allowed");
        Check.that(allowed == 50, "the bucket keeps only 50");

        // 3. cricket-blog (FREE) asks for a match history (cost 5) at once, and again 700 ms later.
        RequestContext history = new RequestContext("cricket-blog", "203.0.113.7", "/history", 5);
        limiter.check(history);
        clock.advance(700);
        System.out.println("3.  700 ms  history (5)  "
                + Check.show(limiter.check(history)));
    }
}
