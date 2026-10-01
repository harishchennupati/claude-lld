import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// Who is on which plan. Sign-ups and upgrades write while request threads read, so the map is a
// ConcurrentHashMap: readers never see it half-updated, and nobody waits for a lock to read.
class Customers {
    private final Map<String, Plan> planOf = new ConcurrentHashMap<>();

    void setPlan(String customerId, Plan plan) {
        planOf.put(customerId, plan);
    }

    Plan planOf(String customerId) {
        if (customerId == null) {
            return Plan.FREE;                // no API key: no plan of its own
        }
        return planOf.getOrDefault(customerId, Plan.FREE);   // not signed up for more: FREE
    }
}
