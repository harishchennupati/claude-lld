import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

// The lock-free bucket gives the same answers as the locked one, and the same exact count when
// 16 threads race on one client.
public class LockFreeDemo {
    public static void main(String[] args) throws Exception {
        Bucket locked = new TokenBucket(Limit.perSecond(5), 0);
        Bucket lockFree = new AtomicTokenBucket(Limit.perSecond(5), 0);
        long[] times = {0, 0, 0, 0, 0, 0, 120, 200};
        int same = 0;
        for (long t : times) {
            Decision a = locked.tryConsume(1, t);
            Decision b = lockFree.tryConsume(1, t);
            same += a.equals(b) ? 1 : 0;                  // records compare field by field
        }
        System.out.println("the 8-request trace: " + same + " of 8 answers the same");

        RuleBook rules = new RuleBook(List.of(new RateLimitRule("plan",
                RateLimitRule.everyRequest(), KeyScope.CLIENT,
                LimitPolicy.fixed(Limit.perSecond(10_000)), Algorithm.LOCK_FREE_TOKEN_BUCKET)));
        RateLimiter limiter = new RuleBasedRateLimiter(rules, new InMemoryBucketStore(),
                new ManualClock(0));
        AtomicInteger allowed = new AtomicInteger();
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        RequestContext r = RequestContext.of("fantasy-app", "203.0.113.7", "/scores");
        for (int t = 0; t < 16; t++) {
            pool.submit(() -> {
                start.await();
                for (int i = 0; i < 2_000; i++) {
                    if (limiter.check(r).allowed()) {
                        allowed.incrementAndGet();
                    }
                }
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        pool.awaitTermination(60, TimeUnit.SECONDS);
        System.out.println("16 threads x 2,000 requests, limit 10,000: " + allowed.get()
                + " allowed");
        Check.that(same == 8 && allowed.get() == 10_000, "same answers, exact count");

        // Time per tryConsume on ONE bucket (a hot client): 1 thread, then 8 threads at once.
        // Measured, not asserted: the numbers depend on the machine, so both are printed and
        // neither is declared the winner.
        System.out.println("\nnanoseconds per tryConsume, " + Runtime.getRuntime()
                .availableProcessors() + " cores:");
        for (int threads : new int[] {1, 8}) {
            long lock = time(Algorithm.TOKEN_BUCKET, threads);
            long cas = time(Algorithm.LOCK_FREE_TOKEN_BUCKET, threads);
            System.out.printf("%d thread%s on one bucket:  synchronized %4d ns   CAS %4d ns%n",
                    threads, threads == 1 ? " " : "s", lock, cas);
        }
    }

    // Average nanoseconds per tryConsume, the best of 3 runs of 1,000,000 calls per thread.
    static long time(Algorithm algorithm, int threads) throws Exception {
        long best = Long.MAX_VALUE;
        for (int round = 0; round < 3; round++) {
            Bucket bucket = algorithm.create(Limit.perSecond(1_000_000), 0);
            CountDownLatch go = new CountDownLatch(1);
            ExecutorService pool = Executors.newFixedThreadPool(threads);
            for (int t = 0; t < threads; t++) {
                pool.submit(() -> {
                    go.await();
                    for (int i = 0; i < 1_000_000; i++) {
                        bucket.tryConsume(1, i);
                    }
                    return null;
                });
            }
            long t0 = System.nanoTime();
            go.countDown();
            pool.shutdown();
            pool.awaitTermination(60, TimeUnit.SECONDS);
            best = Math.min(best, (System.nanoTime() - t0) / (1_000_000L * threads));
        }
        return best;
    }
}
