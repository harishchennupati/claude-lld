import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// Which plan each client is on. Clients sign up and upgrade while requests are running, so many
// threads use this map at once: a ConcurrentHashMap.
class Plans {
    private final Map<String, Plan> planOf = new ConcurrentHashMap<>();

    void assign(String clientId, Plan plan) {
        planOf.put(clientId, plan);
    }

    // A client nobody has set up is on FREE, so no caller ever handles a missing plan.
    Plan planOf(String clientId) {
        return planOf.getOrDefault(clientId, Plan.FREE);
    }
}
