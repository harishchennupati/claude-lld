// A batch job sends 8 requests as score-widget (5 a second) and would rather wait than fail.
// The "sleep" moves the manual clock, so the demo runs instantly and prints the real times.
public class F7Demo {
    public static void main(String[] args) throws InterruptedException {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, clock);
        Waiting waiting = new Waiting(limiter, clock, clock::advance, 10);   // in production: Thread::sleep

        StringBuilder times = new StringBuilder();
        for (int i = 0; i < 8; i++) {
            Check.that(waiting.acquire("score-widget", 1, 1_000), "request " + (i + 1) + " passes within a second");
            times.append(clock.nowMillis()).append(" ms  ");
        }
        System.out.println("8 requests passed at: " + times);
        boolean quick = waiting.acquire("score-widget", 1, 100);         // the next token is 200 ms away
        boolean huge = waiting.acquire("score-widget", 6, 60_000);       // 6 can never fit in 5
        System.out.println("willing to wait 100 ms, but the token is 200 ms away -> " + quick + ", at once");
        System.out.println("a request that costs 6 -> " + huge + ", at once");
        Check.that(!quick && !huge && clock.nowMillis() == 600, "both refused without sleeping");
    }
}
