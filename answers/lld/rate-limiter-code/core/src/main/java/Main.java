import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

// Wires the limiter as the server would at startup, with a clock moved by hand so every run
// prints the same, then races 100 threads on one customer.
public class Main {
    public static void main(String[] args) throws Exception {
        AtomicLong now = new AtomicLong(0);
        Clock clock = now::get;                         // production: System::currentTimeMillis
        LimitPolicy limits = new CustomerLimits(
                Map.of("fantasy-app", Limit.perSecond(50)),  // a paying customer
                Limit.perSecond(5));                         // everyone else
        RateLimiter limiter = new PerKeyRateLimiter(
                limits, new InMemoryCounterStore(Algorithm.TOKEN_BUCKET), clock);

        send(limiter, now, "score-widget", 7);   // 5 a second: a burst of 5, then refused
        now.addAndGet(120);                       // 120 ms earns 0.6 of a token
        send(limiter, now, "score-widget", 1);   // not enough yet
        now.addAndGet(80);                        // 200 ms in all: one whole token
        send(limiter, now, "score-widget", 1);
        send(limiter, now, "cricket-blog", 1);   // its own bucket: score-widget cost it nothing

        race(limits);
    }

    static void send(RateLimiter limiter, AtomicLong now, String customer, int count) {
        for (int i = 1; i <= count; i++) {
            Decision d = limiter.check(customer);
            System.out.printf("%4d ms  %-13s #%d  %s%n", now.get(), customer, i,
                    d.allowed() ? "allowed" : "429, retry in " + d.retryAfterMillis() + " ms");
        }
    }

    // 100 threads send one request each for fantasy-app (50 a second) at the same instant. The
    // clock is frozen, so no token comes back during the race: exactly 50 must pass.
    static void race(LimitPolicy limits) throws InterruptedException {
        RateLimiter limiter = new PerKeyRateLimiter(
                limits, new InMemoryCounterStore(Algorithm.TOKEN_BUCKET), () -> 0L);
        CountDownLatch start = new CountDownLatch(1);   // a starting gun
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
        start.countDown();                               // all 100 go at once
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);
        System.out.printf("%nrace: 100 threads for fantasy-app (50 a second): %d allowed%n",
                allowed.get());
    }
}
