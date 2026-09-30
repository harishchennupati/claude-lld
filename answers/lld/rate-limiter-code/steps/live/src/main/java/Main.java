import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

// Wires the limiter the way the server does at startup (only the clock is manual, so every run
// prints the same), sends requests through the filter, then races 100 threads on one client.
public class Main {
    public static void main(String[] args) throws Exception {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);                          // everyone else: FREE
        RuleBasedRateLimiter limiter = new RuleBasedRateLimiter(
                ScoreApiRules.build(plans), new InMemoryBucketStore(), clock);
        RefusalMetrics metrics = new RefusalMetrics();
        limiter.addListener(metrics);
        RateLimitFilter api = new RateLimitFilter(limiter);

        send(api, clock, "score-widget", "/scores", 7);      // FREE: 5 a second
        send(api, clock, "fantasy-app", "/search", 3);       // PRO, but search allows 2 a second
        send(api, clock, "fantasy-app", "/scores", 1);       // the refused search spent nothing
        send(api, clock, RequestContext.ANONYMOUS, "/login", 6);   // 5 sign-ins a minute per IP
        clock.advance(300);                                  // 300 ms earn score-widget 1.5 tokens
        send(api, clock, "score-widget", "/scores", 2);
        System.out.println("\nrefusals: " + metrics.snapshot());

        race(plans);
    }

    // Sends `count` requests at the current instant and prints each response.
    static void send(RateLimitFilter api, ManualClock clock, String client, String endpoint,
                     int count) {
        for (int i = 1; i <= count; i++) {
            RequestContext request = RequestContext.of(client, "203.0.113.7", endpoint);
            RateLimitFilter.Response r =
                    api.handle(request, req -> new RateLimitFilter.Response(200, Map.of()));
            System.out.printf("%4d ms  %-12s %-8s #%d  %d %s%n", clock.nowMillis(), client,
                    endpoint, i, r.status(), new TreeMap<>(r.headers()));   // sorted
        }
    }

    // 100 threads send one request each for fantasy-app (PRO: 50 a second) at the same instant.
    // The clock is frozen, so no token comes back during the race: exactly 50 must pass.
    static void race(Plans plans) throws InterruptedException {
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(plans),
                new InMemoryBucketStore(), new ManualClock(0));
        CountDownLatch start = new CountDownLatch(1);   // a starting gun: threads wait at await()
        AtomicInteger allowed = new AtomicInteger();     // a counter many threads can add to safely
        ExecutorService pool = Executors.newFixedThreadPool(100);
        for (int i = 0; i < 100; i++) {
            pool.submit(() -> {
                start.await();                           // wait for the gun
                RequestContext r = RequestContext.of("fantasy-app", "198.51.100.4", "/scores");
                if (limiter.check(r).allowed()) {
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
