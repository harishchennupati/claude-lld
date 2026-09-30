import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

// Counts refusals per rule and client, for a dashboard: "search refused fantasy-app 3 times".
class RefusalMetrics implements RateLimitListener {
    // LongAdder: a counter built for many writers; each thread adds to its own cell.
    private final ConcurrentHashMap<String, LongAdder> refusals = new ConcurrentHashMap<>();

    @Override
    public void onDecision(RequestContext request, RateLimitResult result) {
        if (!result.allowed()) {
            String key = result.refusedBy() + " refused " + request.clientId();
            refusals.computeIfAbsent(key, k -> new LongAdder()).increment();
        }
    }

    // A sorted copy, safe to read while requests keep counting.
    Map<String, Long> snapshot() {
        Map<String, Long> copy = new TreeMap<>();
        refusals.forEach((key, count) -> copy.put(key, count.sum()));
        return copy;
    }
}
