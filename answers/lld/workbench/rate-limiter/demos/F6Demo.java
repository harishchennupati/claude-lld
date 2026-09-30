import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

// 10,000 clients call once and never again; one client keeps calling. A sweep forgets the idle ones.
public class F6Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        ClientRateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, clock);

        for (int i = 0; i < 10_000; i++) {
            limiter.tryAcquire("one-time-" + i);
        }
        clock.advance(900);
        limiter.tryAcquire("score-widget");                  // still busy
        clock.advance(100);
        System.out.println("buckets before the sweep: " + limiter.size());
        int removed = limiter.evictIdle(clock.nowMillis());
        System.out.println("the sweep at 1000 ms removed " + removed + "; buckets left: " + limiter.size());
        Check.that(removed == 10_000 && limiter.size() == 1, "only score-widget's bucket is left");
    }

    // In production a timer runs the sweep once a minute, on its own thread, never on a request.
    static ScheduledExecutorService startSweeper(ClientRateLimiter limiter, Clock clock) {
        ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor();
        timer.scheduleAtFixedRate(() -> limiter.evictIdle(clock.nowMillis()), 1, 1, TimeUnit.MINUTES);
        return timer;
    }
}
