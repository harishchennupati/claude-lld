import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

// Wires the limiter the way production would (only the clock is manual, so every run prints
// the same), sends requests from three clients, then fires 100 requests for one client from
// 100 threads at the same instant.
public class Main {
    public static void main(String[] args) throws Exception {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));   // FREE, PRO
        plans.assign("fantasy-app", Plan.PRO);                              // everyone else: FREE
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, clock);

        burst(clock, limiter, "score-widget", 7);    // FREE: 5 pass, then refusals
        burst(clock, limiter, "fantasy-app", 7);     // PRO: a bucket of its own, 50 tokens
        burst(clock, limiter, "cricket-blog", 1);    // nobody set it up, so FREE

        clock.advance(300);                          // 300 ms earn score-widget 1.5 tokens
        burst(clock, limiter, "score-widget", 2);    // one whole token: 1 passes, 0.5 is left

        race();
    }

    // Sends `count` requests for one client at the current instant and prints each answer.
    static void burst(ManualClock clock, RateLimiter limiter, String clientId, int count) {
        for (int i = 1; i <= count; i++) {
            Decision d = limiter.tryAcquire(clientId);
            System.out.printf("%4d ms  %-12s  #%d  %s%n", clock.nowMillis(), clientId, i, d);
        }
    }

    // 100 threads send one request each for fantasy-app (limit 50) at the same instant.
    // The clock is frozen, so no token comes back during the race: exactly 50 must pass.
    static void race() throws InterruptedException {
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        plans.assign("fantasy-app", Plan.PRO);
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, new ManualClock(0));

        CountDownLatch start = new CountDownLatch(1);   // a starting gun: threads wait at await()
        AtomicInteger allowed = new AtomicInteger();     // a counter many threads can add to safely
        ExecutorService pool = Executors.newFixedThreadPool(100);
        for (int i = 0; i < 100; i++) {
            pool.submit(() -> {
                start.await();                           // wait for the gun
                if (limiter.tryAcquire("fantasy-app").allowed()) {
                    allowed.incrementAndGet();
                }
                return null;                             // a Callable, so await() may throw
            });
        }
        start.countDown();                               // fire: all 100 threads go at once
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);
        System.out.printf("%nrace: 100 threads, one request each for fantasy-app (limit 50)%n");
        System.out.printf("      %d allowed, %d refused%n", allowed.get(), 100 - allowed.get());
    }
}
