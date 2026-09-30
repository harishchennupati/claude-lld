import java.util.ArrayList;
import java.util.List;

// A batch job sends 8 requests as score-widget (5 a second) and would rather wait than fail.
// Here "sleeping" moves the manual clock, so the demo runs instantly and prints real times.
public class F7Demo {
    public static void main(String[] args) throws InterruptedException {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, clock);
        // In production the sleeper is Thread::sleep.
        Waiting waiting = new Waiting(limiter, clock, clock::advance, 10);

        List<String> times = new ArrayList<>();
        for (int i = 1; i <= 8; i++) {
            Check.that(waiting.acquire("score-widget", 1, 1_000), "request " + i + " passes");
            times.add(String.valueOf(clock.nowMillis()));
        }
        System.out.println("8 requests passed at: " + String.join(", ", times) + " ms");
        boolean quick = waiting.acquire("score-widget", 1, 100);    // the token is 200 ms away
        boolean huge = waiting.acquire("score-widget", 6, 60_000);  // 6 never fit in 5
        System.out.println("will wait 100 ms, the token is 200 ms away -> " + quick + ", at once");
        System.out.println("a request that costs 6 -> " + huge + ", at once");
        Check.that(!quick && !huge && clock.nowMillis() == 600, "both refused, no sleeping");
    }
}
