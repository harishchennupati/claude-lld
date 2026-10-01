import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// One server's counters: one per key, shared by every request thread.
// Why a class: it owns changing state, a ConcurrentHashMap. Swapping it for a Redis class changes
// no other file.
class InMemoryCounterStore implements CounterStore {
    private final Map<String, Counter> counters = new ConcurrentHashMap<>();

    @Override
    public Counter counterFor(String key, Limit limit, Algorithm algorithm, long nowMillis) {
        // The limit is part of the map's key: a customer who upgrades from FREE to PRO gets a new
        // 50-a-second counter on the next request (the old one waits for the idle sweep).
        String id = key + "|" + limit.requests() + "/" + limit.periodMillis();
        // computeIfAbsent finds, creates and stores as ONE step for this key. With get, then put,
        // two threads meeting a new customer would both create a counter: two budgets.
        return counters.computeIfAbsent(id,
                k -> CounterFactory.create(algorithm, limit, nowMillis));
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
