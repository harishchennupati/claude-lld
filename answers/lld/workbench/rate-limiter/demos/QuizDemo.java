// The answers to the "predict the output" questions, printed by the real code.
public class QuizDemo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        plans.assign("fantasy-app", Plan.PRO);
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, clock);

        // 1. score-widget: 5 requests at 0 ms, then 3 at 450 ms.
        for (int i = 0; i < 5; i++) {
            limiter.tryAcquire("score-widget");
        }
        clock.advance(450);
        for (int i = 1; i <= 3; i++) {
            System.out.println("1.  450 ms  #" + i + "  " + limiter.tryAcquire("score-widget"));
        }

        // 2. fantasy-app (50 a second): one request, 10 quiet seconds, then 60 at once.
        limiter.tryAcquire("fantasy-app");
        clock.advance(10_000);
        int allowed = 0;
        for (int i = 0; i < 60; i++) {
            allowed += limiter.tryAcquire("fantasy-app").allowed() ? 1 : 0;
        }
        System.out.println("2.  60 at once after 10 quiet seconds: " + allowed + " allowed");
        Check.that(allowed == 50, "the bucket keeps only 50");
    }
}
