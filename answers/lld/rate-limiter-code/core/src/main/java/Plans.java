import java.util.EnumMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// Which plan each client is on, and each plan's limit: configuration, not if-statements.
class Plans {
    // Each plan's limit. Filled once in the constructor and only read after that,
    // so threads can share it without a lock.
    private final Map<Plan, Limit> limitOf = new EnumMap<>(Plan.class);

    // Which plan each client is on. Clients can sign up while requests are running,
    // so many threads use this map at once: a ConcurrentHashMap.
    private final Map<String, Plan> planOf = new ConcurrentHashMap<>();

    Plans(Limit free, Limit pro) {
        limitOf.put(Plan.FREE, free);
        limitOf.put(Plan.PRO, pro);
    }

    void assign(String clientId, Plan plan) {
        planOf.put(clientId, plan);
    }

    // A client nobody has set up is on FREE, so no caller ever has to handle a missing plan.
    Limit limitFor(String clientId) {
        return limitOf.get(planOf.getOrDefault(clientId, Plan.FREE));
    }
}
