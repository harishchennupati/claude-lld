// The answer to the costs question, printed by the real code (the snapshot with costs).
public class QuizCostDemo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, clock);

        // 3. score-widget spends all 5 at 0 ms; at 700 ms it asks for a history, which costs 5.
        limiter.tryAcquire("score-widget", 5);
        clock.advance(700);
        System.out.println("3.  700 ms  history (5)  " + limiter.tryAcquire("score-widget", 5));
    }
}
