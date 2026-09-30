import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

// One test per promise the design makes. Plain Java, no library: run `java RateLimiterTest`.
// Every test builds a fresh limiter on a manual clock, so it runs instantly and gives the same
// answer every time. (With JUnit: each method gets @Test, and check(...) becomes assertTrue.)
public class RateLimiterTest {
    public static void main(String[] args) throws Exception {
        test("a new client bursts its whole limit, then is refused", RateLimiterTest::burst);
        test("a refusal says exactly when to retry", RateLimiterTest::retryTime);
        test("a refused request spends nothing", RateLimiterTest::refusalIsFree);
        test("quiet time never fills a bucket past its capacity", RateLimiterTest::capacity);
        test("each client has its own budget, from its own plan", RateLimiterTest::separate);
        test("many threads on one client get exactly its limit", RateLimiterTest::raceOneClient);
        test("threads that meet a new client share one bucket", RateLimiterTest::raceNewClients);
        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures > 0) {
            System.exit(1);
        }
    }

    // FREE: 5 a second, PRO: 50 a second. fantasy-app is on PRO, everyone else on FREE.
    static RateLimiter limiter(Clock clock) {
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        plans.assign("fantasy-app", Plan.PRO);
        return new ClientRateLimiter(plans, TokenBucket::new, clock);
    }

    static void burst() {
        RateLimiter limiter = limiter(new ManualClock(0));
        for (int i = 1; i <= 5; i++) {
            check(limiter.tryAcquire("score-widget").allowed(), "burst request " + i + " allowed");
        }
        check(!limiter.tryAcquire("score-widget").allowed(), "the 6th, same millisecond, refused");
    }

    static void retryTime() {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = limiter(clock);
        spend(limiter, "score-widget", 5);
        check(retryAfter(limiter, "score-widget") == 200, "an empty bucket: retry in 200 ms");
        clock.advance(120);
        check(retryAfter(limiter, "score-widget") == 80, "0.6 of a token: retry in 80 ms");
        clock.advance(80);
        check(limiter.tryAcquire("score-widget").allowed(), "80 ms later the token is there");
    }

    static void refusalIsFree() {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = limiter(clock);
        spend(limiter, "score-widget", 5);
        spend(limiter, "score-widget", 10);                 // 10 refusals: they must cost nothing,
        clock.advance(200);
        check(limiter.tryAcquire("score-widget").allowed(), "so 200 ms later a token is there");
    }

    static void capacity() {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = limiter(clock);
        spend(limiter, "score-widget", 5);
        clock.advance(10_000);                              // 10 quiet seconds earn 50 tokens...
        check(spend(limiter, "score-widget", 20) == 5, "...but the bucket keeps only 5");
    }

    static void separate() {
        RateLimiter limiter = limiter(new ManualClock(0));
        spend(limiter, "score-widget", 5);
        check(!limiter.tryAcquire("score-widget").allowed(), "score-widget has used its 5");
        check(limiter.tryAcquire("fantasy-app").remaining() == 49, "fantasy-app: 49 of 50 left");
        check(spend(limiter, "brand-new-app", 10) == 5, "a client nobody set up gets FREE: 5");
    }

    // A frozen clock and far more requests than tokens: more than the limit can pass only if two
    // threads spend the same token. Without `synchronized` on the bucket this fails almost every
    // run; with it, the count is exact every time. (PRO is 10,000 here, just for this test.)
    static void raceOneClient() throws InterruptedException {
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(10_000));
        plans.assign("fantasy-app", Plan.PRO);
        RateLimiter limiter = new ClientRateLimiter(plans, TokenBucket::new, new ManualClock(0));
        AtomicInteger allowed = new AtomicInteger();
        together(16, () -> {                                // 16 threads x 2,000 = 32,000 requests
            for (int i = 0; i < 2_000; i++) {
                if (limiter.tryAcquire("fantasy-app").allowed()) {
                    allowed.incrementAndGet();
                }
            }
        });
        check(allowed.get() == 10_000, "exactly 10,000 of 32,000 allowed, got " + allowed.get());
    }

    // 16 threads walk the same 2,000 brand-new clients at the same moment, one request each.
    // Each client may pass 5 (FREE). If every thread could create its own bucket for a new client,
    // all 16 of its requests could pass. Exactly 2,000 x 5 = 10,000 must pass.
    static void raceNewClients() throws InterruptedException {
        RateLimiter limiter = limiter(new ManualClock(0));
        AtomicInteger allowed = new AtomicInteger();
        together(16, () -> {
            for (int c = 0; c < 2_000; c++) {
                if (limiter.tryAcquire("client-" + c).allowed()) {
                    allowed.incrementAndGet();
                }
            }
        });
        check(allowed.get() == 10_000, "exactly 10,000 allowed, got " + allowed.get());
    }

    // ---- helpers

    // Sends `count` requests at once for one client; returns how many were allowed.
    static int spend(RateLimiter limiter, String clientId, int count) {
        int allowed = 0;
        for (int i = 0; i < count; i++) {
            if (limiter.tryAcquire(clientId).allowed()) {
                allowed++;
            }
        }
        return allowed;
    }

    static long retryAfter(RateLimiter limiter, String clientId) {
        return limiter.tryAcquire(clientId).retryAfterMillis();
    }

    // Runs `work` on `threads` threads that all start at the same instant, and waits for them.
    static void together(int threads, Runnable work) throws InterruptedException {
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        for (int t = 0; t < threads; t++) {
            pool.submit(() -> {
                start.await();
                work.run();
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        if (!pool.awaitTermination(60, TimeUnit.SECONDS)) {
            throw new IllegalStateException("the threads did not finish");
        }
    }

    private static int failures = 0;

    static void check(boolean ok, String what) {
        if (!ok) {
            throw new AssertionError(what);
        }
    }

    interface Test {
        void run() throws Exception;
    }

    static void test(String name, Test test) {
        try {
            test.run();
            System.out.println("PASS  " + name);
        } catch (Throwable e) {
            failures++;
            System.out.println("FAIL  " + name + "\n      " + e.getMessage());
        }
    }
}
