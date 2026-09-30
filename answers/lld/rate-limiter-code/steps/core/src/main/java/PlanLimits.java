import java.util.EnumMap;
import java.util.Map;

// A limit per plan: FREE 5 a second, PRO 50. Configuration, not if-statements: a new plan is a
// new entry, and nothing that reads limits changes.
class PlanLimits implements LimitPolicy {
    private final Plans plans;
    // Filled in the constructor and only read after that. A final field filled before the
    // constructor returns is safe for every thread to read, with no lock.
    private final Map<Plan, Limit> limitOf;

    PlanLimits(Plans plans, Map<Plan, Limit> limits) {
        this.plans = plans;
        this.limitOf = new EnumMap<>(limits);
        for (Plan plan : Plan.values()) {
            if (!limitOf.containsKey(plan)) {
                throw new IllegalArgumentException("no limit for plan " + plan);  // at startup
            }
        }
    }

    @Override
    public Limit limitFor(RequestContext request) {
        return limitOf.get(plans.planOf(request.clientId()));
    }
}
