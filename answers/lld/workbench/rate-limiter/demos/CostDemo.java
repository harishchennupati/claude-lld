// What a check costs, measured on the machine that builds the page: time per check through the
// score API's rules (three buckets for a /scores request), and memory per client.
public class CostDemo {
    public static void main(String[] args) throws InterruptedException {
        Plans plans = new Plans();
        ManualClock clock = new ManualClock(0);
        InMemoryBucketStore store = new InMemoryBucketStore();
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(plans), store, clock);
        plans.assign("fantasy-app", Plan.PRO);
        RequestContext r = RequestContext.of("fantasy-app", "203.0.113.7", "/scores");
        long sink = 0;
        long best = Long.MAX_VALUE;
        for (int round = 0; round < 5; round++) {             // the first rounds warm the JIT up
            long t0 = System.nanoTime();
            for (int i = 0; i < 2_000_000; i++) {
                clock.advance(1);
                sink += limiter.check(r).remaining();
            }
            best = Math.min(best, (System.nanoTime() - t0) / 2_000_000);
        }
        System.out.println("one check, three rules, one thread: about " + best + " ns");

        Runtime rt = Runtime.getRuntime();
        String[] ids = new String[200_000];
        for (int i = 0; i < ids.length; i++) {
            ids[i] = "client-" + (1_000_000 + i);
        }
        long before = used(rt);
        for (String id : ids) {
            limiter.check(RequestContext.of(id, "203.0.113.7", "/scores"));
        }
        long after = used(rt);
        long perClient = (after - before) / ids.length;
        System.out.println("memory per new client (its buckets and their keys): about "
                + perClient + " bytes; a million clients: about " + perClient + " MB");
        // Keep the store reachable until here; otherwise the collector may free it as soon as the
        // last check returns, and we would measure 0.
        java.lang.ref.Reference.reachabilityFence(store);
        Check.that(sink > 0 && perClient > 0, "measured");
    }

    static long used(Runtime rt) throws InterruptedException {
        for (int i = 0; i < 3; i++) {
            System.gc();
            Thread.sleep(50);
        }
        return rt.totalMemory() - rt.freeMemory();
    }
}
