// A million customers who call once a day: forget the counters a new one would equal.
public class IdleDemo {
    public static void main(String[] args) {
        InMemoryCounterStore store = new InMemoryCounterStore();
        Limit limit = Limit.perSecond(5);
        for (int i = 0; i < 1_000; i++) {
            store.counterFor("rate:customer-" + i, limit, Algorithm.TOKEN_BUCKET, 0)
                    .tryAcquire(0);                                       // one call each
        }
        for (int i = 0; i < 6; i++) {
            store.counterFor("rate:busy-app", limit, Algorithm.TOKEN_BUCKET, 900)
                    .tryAcquire(900);                                     // still busy at 900 ms
        }
        System.out.println("counters before the sweep: " + store.size());
        store.evictIdle(1_000);
        System.out.println("after the sweep at 1000 ms: " + store.size()
                + " (busy-app is not full yet)");
        Check.that(store.size() == 1, "only busy-app stays");
    }
}
