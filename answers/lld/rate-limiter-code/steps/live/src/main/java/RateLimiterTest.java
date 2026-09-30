import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.LockSupport;

// One test per promise the design makes. Plain Java, no library: run `java RateLimiterTest`.
// Every test builds a fresh limiter on a manual clock, so it runs instantly and gives the same
// answer every time. (With JUnit: each method gets @Test, and check(...) becomes assertTrue.)
public class RateLimiterTest {
    public static void main(String[] args) {
        test("a new client bursts its whole limit, then is refused", RateLimiterTest::burst);
        test("a refusal says exactly when to retry", RateLimiterTest::retryTime);
        test("a refused request spends nothing, in any rule", RateLimiterTest::refusalIsFree);
        test("quiet time never fills a bucket past its capacity", RateLimiterTest::capacity);
        test("each client gets its plan's budget; an upgrade applies at once",
                RateLimiterTest::plans);
        test("each rule counts by its own key", RateLimiterTest::scopes);
        test("sign-ins are exact: never 6 in any minute", RateLimiterTest::exactSignIns);
        test("the daily quota starts again at midnight", RateLimiterTest::quota);
        test("the tightest rule's remaining is reported", RateLimiterTest::tightest);
        test("listeners hear every refusal", RateLimiterTest::listeners);
        test("a listener that throws does not break a request", RateLimiterTest::brokenListener);
        test("a clock that jumps back neither earns nor takes tokens", RateLimiterTest::clockBack);
        test("many threads on one client get exactly its limit", RateLimiterTest::raceOneClient);
        test("threads that meet a new client share one bucket", RateLimiterTest::raceNewClients);
        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures > 0) {
            System.exit(1);
        }
    }

    // ---- behaviour, on the score API's real rules

    static void burst() {
        RateLimiter limiter = limiter(new ManualClock(0));
        for (int i = 1; i <= 5; i++) {
            check(limiter.check(scores("score-widget")).allowed(), "burst request " + i);
        }
        RateLimitResult sixth = limiter.check(scores("score-widget"));
        check(!sixth.allowed() && "plan".equals(sixth.refusedBy()), "the 6th: refused by plan");
    }

    static void retryTime() {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = limiter(clock);
        spend(limiter, scores("score-widget"), 5);
        check(retryAfter(limiter, scores("score-widget")) == 200, "empty: retry in 200 ms");
        clock.advance(120);
        check(retryAfter(limiter, scores("score-widget")) == 80, "0.6 of a token: 80 ms");
        clock.advance(80);
        check(limiter.check(scores("score-widget")).allowed(), "80 ms later the token is there");
    }

    static void refusalIsFree() {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = limiter(clock);
        spend(limiter, request("fantasy-app", "/search"), 3);   // the 3rd is refused by search,
        check(limiter.check(scores("fantasy-app")).remaining() == 47, "plan gave its token back");
        spend(limiter, scores("score-widget"), 5);
        spend(limiter, scores("score-widget"), 10);             // 10 refusals must cost nothing,
        clock.advance(200);
        check(limiter.check(scores("score-widget")).allowed(), "so 200 ms later a token is there");
    }

    static void capacity() {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = limiter(clock);
        spend(limiter, scores("score-widget"), 5);
        clock.advance(10_000);                                  // 10 quiet seconds earn 50...
        check(spend(limiter, scores("score-widget"), 20) == 5, "...but the bucket keeps 5");
    }

    static void plans() {
        Plans plans = new Plans();
        RateLimiter limiter = limiter(new ManualClock(0), plans);
        spend(limiter, scores("score-widget"), 5);
        check(!limiter.check(scores("score-widget")).allowed(), "score-widget has used its 5");
        check(limiter.check(scores("fantasy-app")).remaining() == 49, "fantasy-app: 49 of 50");
        check(spend(limiter, scores("brand-new-app"), 10) == 5, "nobody set it up: FREE, 5");
        plans.assign("score-widget", Plan.PRO);                 // an upgrade, while requests run
        check(limiter.check(scores("score-widget")).remaining() == 49, "PRO at once: 49 left");
    }

    static void scopes() {
        RateLimiter limiter = limiter(new ManualClock(0));
        spend(limiter, request("fantasy-app", "/search"), 2);
        check(!limiter.check(request("fantasy-app", "/search")).allowed(), "no searches left");
        check(limiter.check(scores("fantasy-app")).allowed(), "...but /scores is another key");
        check(limiter.check(request("cricket-blog", "/search")).allowed(), "...so is cricket-blog");
        RequestContext fromA = signIn("192.0.2.1");
        spend(limiter, fromA, 5);
        check(!limiter.check(fromA).allowed(), "one IP has used its 5 sign-ins");
        check(limiter.check(signIn("192.0.2.2")).allowed(), "...another IP has its own 5");
    }

    static void exactSignIns() {
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = limiter(clock);
        spend(limiter, signIn("192.0.2.1"), 5);                 // 5 attempts at 0 s
        clock.advance(59_999);
        check(!limiter.check(signIn("192.0.2.1")).allowed(), "59.999 s: still 5 in the minute");
        clock.advance(1);
        check(limiter.check(signIn("192.0.2.1")).allowed(), "60 s: the first attempt has left");
    }

    static void quota() {
        ManualClock clock = new ManualClock(86_400_000L * 20_000 + 86_000_000);   // 23:53:20 UTC
        RateLimiter limiter = oneRule(clock, Algorithm.FIXED_WINDOW, Limit.perDay(3));
        check(spend(limiter, scores("score-widget"), 5) == 3, "3 a day");
        check(retryAfter(limiter, scores("score-widget")) == 400_000, "retry at midnight: 400 s");
        clock.advance(400_000);
        check(limiter.check(scores("score-widget")).allowed(), "a new day, a new quota");
    }

    static void tightest() {
        RateLimiter limiter = limiter(new ManualClock(0));
        RateLimitResult r = limiter.check(request("fantasy-app", "/search"));
        check(r.remaining() == 1, "search has 1 left, plan 49: the header says 1");
    }

    static void listeners() {
        RuleBasedRateLimiter limiter = limiter(new ManualClock(0));
        RefusalMetrics metrics = new RefusalMetrics();
        limiter.addListener(metrics);
        spend(limiter, request("fantasy-app", "/search"), 5);   // 2 allowed, 3 refused
        check(metrics.snapshot().equals(Map.of("search refused fantasy-app", 3L)),
                "3 refusals by search, got " + metrics.snapshot());
    }

    static void brokenListener() {
        RuleBasedRateLimiter limiter = limiter(new ManualClock(0));
        limiter.addListener((request, result) -> {
            throw new IllegalStateException("the dashboard is down");
        });
        check(limiter.check(scores("score-widget")).allowed(), "the request still gets its answer");
    }

    static void clockBack() {
        ManualClock clock = new ManualClock(10_000);
        RateLimiter limiter = limiter(clock);
        spend(limiter, scores("score-widget"), 3);              // 2 tokens left
        clock.advance(-1_000);                                  // the wall clock is set back 1 s
        check(limiter.check(scores("score-widget")).remaining() == 1, "the 2 tokens were there");
        clock.advance(1_000);                                   // back where it was
        check(spend(limiter, scores("score-widget"), 5) == 1, "and nothing was earned meanwhile");
    }

    // ---- threads. Frozen clocks and far more requests than tokens: more than the limit can
    // pass only if two threads spend the same token or build two buckets for one client.

    static void raceOneClient() throws Exception {
        RateLimiter limiter = oneRule(new ManualClock(0), Algorithm.TOKEN_BUCKET,
                Limit.perSecond(10_000));
        AtomicInteger allowed = new AtomicInteger();
        together(16, () -> {                                    // 16 threads x 2,000 requests
            for (int i = 0; i < 2_000; i++) {
                if (limiter.check(scores("fantasy-app")).allowed()) {
                    allowed.incrementAndGet();
                }
            }
        });
        check(allowed.get() == 10_000, "exactly 10,000 of 32,000 allowed, got " + allowed.get());
    }

    // 16 threads ask the store for the same new key at the same instant. The factory takes 50 ms
    // to build a bucket, on purpose: it holds the race window open, so if two threads COULD each
    // build a bucket, they always do. A race that shows up once in a thousand runs now shows up
    // on every run.
    static void raceNewClients() throws Exception {
        InMemoryBucketStore store = new InMemoryBucketStore();
        BucketFactory slow = (limit, now) -> {
            LockSupport.parkNanos(50_000_000);                  // 50 ms, no checked exception
            return new TokenBucket(limit, now);
        };
        Set<Bucket> seen = ConcurrentHashMap.newKeySet();       // a thread-safe set
        together(16, () -> seen.add(store.bucketFor("plan|news-app|5/1000", slow,
                Limit.perSecond(5), 0)));
        check(seen.size() == 1, "one bucket for one key, got " + seen.size());
    }

    // ---- helpers

    static final String IP = "203.0.113.7";

    // The score API's real rules. fantasy-app is on PRO; everyone else is on FREE.
    static RuleBasedRateLimiter limiter(Clock clock, Plans plans) {
        plans.assign("fantasy-app", Plan.PRO);
        return new RuleBasedRateLimiter(ScoreApiRules.build(plans), new InMemoryBucketStore(),
                clock);
    }

    static RuleBasedRateLimiter limiter(Clock clock) {
        return limiter(clock, new Plans());
    }

    // One rule, per client, for a test about one algorithm on its own.
    static RateLimiter oneRule(Clock clock, Algorithm algorithm, Limit limit) {
        RuleBook rules = new RuleBook(List.of(new RateLimitRule("only",
                RateLimitRule.everyRequest(), KeyScope.CLIENT, LimitPolicy.fixed(limit),
                algorithm)));
        return new RuleBasedRateLimiter(rules, new InMemoryBucketStore(), clock);
    }

    static RequestContext request(String clientId, String endpoint) {
        return RequestContext.of(clientId, IP, endpoint);
    }

    static RequestContext scores(String clientId) {
        return request(clientId, "/scores");
    }

    static RequestContext signIn(String ip) {
        return RequestContext.of(RequestContext.ANONYMOUS, ip, "/login");
    }

    // Sends the same request `count` times at once; returns how many were allowed.
    static int spend(RateLimiter limiter, RequestContext request, int count) {
        int allowed = 0;
        for (int i = 0; i < count; i++) {
            if (limiter.check(request).allowed()) {
                allowed++;
            }
        }
        return allowed;
    }

    static long retryAfter(RateLimiter limiter, RequestContext request) {
        return limiter.check(request).retryAfterMillis();
    }

    // Runs `work` on `threads` threads that all start at the same instant, and waits for them.
    // get() on each Future rethrows anything a thread threw, so no failure is swallowed.
    static void together(int threads, Runnable work) throws Exception {
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        List<Future<?>> running = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            running.add(pool.submit(() -> {
                start.await();
                work.run();
                return null;
            }));
        }
        start.countDown();
        for (Future<?> f : running) {
            f.get(60, TimeUnit.SECONDS);
        }
        pool.shutdown();
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
