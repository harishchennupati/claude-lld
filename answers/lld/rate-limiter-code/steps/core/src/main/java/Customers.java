import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// Who is on which plan.
// Why a class: its state changes (sign-ups, upgrades), so not a record. The map is private and
// reached only through planOf() and setPlan(). It is a ConcurrentHashMap because upgrades write
// while request threads read: readers never see it half-updated, and never wait for a lock.
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
