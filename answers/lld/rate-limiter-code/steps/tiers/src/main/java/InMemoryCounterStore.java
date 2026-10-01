import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// One server's counters, one per key, shared by every request thread.
class InMemoryCounterStore implements CounterStore {
    private final Map<String, Counter> counters = new ConcurrentHashMap<>();
    private final Algorithm algorithm;

    InMemoryCounterStore(Algorithm algorithm) {
        this.algorithm = algorithm;
    }

    // computeIfAbsent finds, creates and stores as one step for this key. With get, then put,
    // two threads meeting a new customer would both make a counter, and it would get two budgets.
    // The limit is part of the map's key, so a customer whose limit changes starts a new counter.
    @Override
    public Counter counterFor(String key, Limit limit, long nowMillis) {
        String id = key + "|" + limit.requests() + "/" + limit.periodMillis();
        return counters.computeIfAbsent(id, k -> newCounter(limit, nowMillis));
    }

    // A simple factory: a plain switch on the enum.
    private Counter newCounter(Limit limit, long nowMillis) {
        return switch (algorithm) {
            case TOKEN_BUCKET -> new TokenBucket(limit, nowMillis);
            case FIXED_WINDOW -> new FixedWindowCounter(limit, nowMillis);
            case SLIDING_WINDOW_LOG -> new SlidingWindowLog(limit);
            case SLIDING_WINDOW_COUNTER -> new SlidingWindowCounter(limit, nowMillis);
        };
    }
}
