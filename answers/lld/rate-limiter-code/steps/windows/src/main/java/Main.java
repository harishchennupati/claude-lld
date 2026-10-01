import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

// Wires everything as the server would at startup (with a clock moved by hand, so every run
// prints the same), sends requests through the front door, then races 100 threads.
public class Main {
    public static void main(String[] args) throws Exception {
        AtomicLong now = new AtomicLong(0);
        Customers customers = new Customers();
        customers.setPlan("fantasy-app", Plan.PRO);                     // everyone else: FREE
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(customers),
                new InMemoryCounterStore(), now::get);    // production: System::currentTimeMillis
        RateLimitFilter door = new RateLimitFilter(limiter);

        send(door, now, new Request("score-widget", "198.51.100.4", "/scores"), 7);
        send(door, now, new Request("fantasy-app", "198.51.100.9", "/search"), 3);
        send(door, now, new Request("fantasy-app", "198.51.100.9", "/scores"), 1);
        send(door, now, new Request(null, "203.0.113.7", "/login"), 6);
        now.addAndGet(200);                                            // 200 ms: one token back
        send(door, now, new Request("score-widget", "198.51.100.4", "/scores"), 2);

        race(customers);
    }

    static void send(RateLimitFilter door, AtomicLong now, Request request, int count) {
        String who = request.isCustomer() ? request.customerId() : "ip " + request.ip();
        for (int i = 1; i <= count; i++) {
            RateLimitFilter.Response r = door.handle(request,
                    () -> new RateLimitFilter.Response(200, Map.of()));
            System.out.printf("%4d ms  %-15s %-8s #%d  %d %s%n", now.get(), who,
                    request.endpoint(), i, r.status(), new TreeMap<>(r.headers()));
        }
    }

    // 100 threads, one request each for fantasy-app (PRO: 50 a second), at the same instant,
    // with the clock frozen so no token comes back: exactly 50 may pass.
    static void race(Customers customers) throws InterruptedException {
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(customers),
                new InMemoryCounterStore(), () -> 0L);
        CountDownLatch start = new CountDownLatch(1);                  // a starting gun
        AtomicInteger allowed = new AtomicInteger();
        ExecutorService pool = Executors.newFixedThreadPool(100);
        for (int i = 0; i < 100; i++) {
            pool.submit(() -> {
                start.await();
                if (limiter.rateLimit("fantasy-app")) {
                    allowed.incrementAndGet();
                }
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);
        System.out.printf("%nrace: 100 threads for fantasy-app (PRO, 50 a second): %d allowed%n",
                allowed.get());
    }
}
