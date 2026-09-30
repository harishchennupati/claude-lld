//@ until f5
import java.util.EnumMap;
//@ end
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// Which plan each client is on, and each plan's limit: configuration, not if-statements.
//@ until f4
class Plans {
//@ end
//@ from f4
class Plans implements LimitLookup {
//@ end
    //@ until f5
    private final Map<Plan, Limit> limitOf = new EnumMap<>(Plan.class);   // filled once below, then only read
    //@ end
    //@ from f5
    // Was an EnumMap, filled once and then only read. Now ops can change a limit while
    // requests read it, and an EnumMap is not safe for that: a ConcurrentHashMap is.
    private final Map<Plan, Limit> limitOf = new ConcurrentHashMap<>();
    //@ end
    private final Map<String, Plan> planOf = new ConcurrentHashMap<>();   // clients sign up while requests run

    Plans(Limit free, Limit pro) {
        limitOf.put(Plan.FREE, free);
        limitOf.put(Plan.PRO, pro);
    }

    void assign(String clientId, Plan plan) {
        planOf.put(clientId, plan);
    }
    //@ from f5

    // A new limit for a whole plan, while the service runs. Each client's bucket notices
    // on the client's next request.
    void setLimit(Plan plan, Limit limit) {
        limitOf.put(plan, limit);
    }
    //@ end

    // A client nobody has set up is on FREE, so no caller ever has to handle a missing plan.
    //@ until f4
    Limit limitFor(String clientId) {
    //@ end
    //@ from f4
    @Override
    public Limit limitFor(String clientId) {
    //@ end
        return limitOf.get(planOf.getOrDefault(clientId, Plan.FREE));
    }
}
