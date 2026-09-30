import java.util.ArrayList;
import java.util.List;

// A batch job sends 8 requests as score-widget (5 a second) and would rather wait than fail.
// Here "sleeping" moves the manual clock, so the demo runs instantly and prints real times.
public class WaitingDemo {
    public static void main(String[] args) throws InterruptedException {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(new Plans()),
                new InMemoryBucketStore(), clock);
        Waiting waiting = new Waiting(limiter, clock::advance, 10);   // production: Thread::sleep
        RequestContext job = RequestContext.of("score-widget", "203.0.113.7", "/scores");
        List<String> times = new ArrayList<>();
        for (int i = 1; i <= 8; i++) {
            Check.that(waiting.acquire(job, 1_000), "request " + i + " passes");
            times.add(String.valueOf(clock.nowMillis()));
        }
        System.out.println("8 requests passed at: " + String.join(", ", times) + " ms");
        boolean quick = waiting.acquire(job, 100);                    // the token is 200 ms away
        System.out.println("will wait 100 ms, the token is 200 ms away -> " + quick + ", at once");
        Check.that(!quick && clock.nowMillis() == 600, "refused at once, no sleeping");
    }
}
