import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// Which plan each client is on, and each plan's limit: configuration, not if-statements.
class Plans implements LimitLookup {
    // Each plan's limit. It was an EnumMap, filled once and then only read. Now ops can change
    // a limit while requests read it, and an EnumMap is not safe for that: a ConcurrentHashMap is.
    private final Map<Plan, Limit> limitOf = new ConcurrentHashMap<>();

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

    // A new limit for a whole plan, while the service runs. Each client's bucket is rebuilt
    // on that client's next request.
    void setLimit(Plan plan, Limit limit) {
        limitOf.put(plan, limit);
    }

    // A client nobody has set up is on FREE, so no caller ever has to handle a missing plan.
    @Override
    public Limit limitFor(String clientId) {
        return limitOf.get(planOf.getOrDefault(clientId, Plan.FREE));
    }
}
