import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// One server's counters, one per key, shared by every request thread.
class InMemoryCounterStore implements CounterStore {
    private final Map<String, Counter> counters = new ConcurrentHashMap<>();

    // computeIfAbsent finds, creates and stores as one step for this key. With get, then put,
    // two threads meeting a new customer would both make a counter: two budgets.
    // The limit is part of the key, so a customer who upgrades starts a new counter at once.
    @Override
    public Counter counterFor(String key, Limit limit, Algorithm algorithm, long nowMillis) {
        String id = key + "|" + limit.requests() + "/" + limit.periodMillis();
        return counters.computeIfAbsent(id, k -> newCounter(algorithm, limit, nowMillis));
    }

    // A simple factory: a plain switch on the enum.
    private Counter newCounter(Algorithm algorithm, Limit limit, long nowMillis) {
        return switch (algorithm) {
            case TOKEN_BUCKET -> new TokenBucket(limit, nowMillis);
            case FIXED_WINDOW -> new FixedWindowCounter(limit, nowMillis);
            case SLIDING_WINDOW_LOG -> new SlidingWindowLog(limit);
            case SLIDING_WINDOW_COUNTER -> new SlidingWindowCounter(limit, nowMillis);
            case CREDITS -> new CreditWindow(limit, limit.requests(), nowMillis);
        };
    }

    // Run by a timer, never by a request. A request that fetched a counter just before it is
    // removed spends from the old one; the next request starts a new, full one: harmless.
    void evictIdle(long nowMillis) {
        counters.values().removeIf(counter -> counter.isIdle(nowMillis));
    }

    int size() {
        return counters.size();
    }
}
