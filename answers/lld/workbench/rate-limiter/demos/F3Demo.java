// Costs: a live score costs 1 token, a whole match's ball-by-ball history costs 5.
public class F3Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, clock);

        Decision history = limiter.tryAcquire("score-widget", 5);
        Decision score = limiter.tryAcquire("score-widget");      // old call: still costs 1
        clock.advance(600);                                       // 600 ms earn 3 tokens
        Decision early = limiter.tryAcquire("score-widget", 5);
        clock.advance(400);
        Decision onTime = limiter.tryAcquire("score-widget", 5);
        Decision tooBig = limiter.tryAcquire("score-widget", 6);
        System.out.println("   0 ms  history (5)     " + history);
        System.out.println("   0 ms  live score (1)  " + score);
        System.out.println(" 600 ms  history (5)     " + early);
        System.out.println("1000 ms  history (5)     " + onTime);
        System.out.println("1000 ms  export (6)      " + tooBig);
        Check.that(early.remaining() == 3 && early.retryAfterMillis() == 400, "3 left, 400 ms");
        Check.that(onTime.allowed() && tooBig.retryAfterMillis() == Decision.NEVER, "never");
    }
}
