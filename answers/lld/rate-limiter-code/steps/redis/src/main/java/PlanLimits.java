import java.util.Map;

// A limit per plan: FREE 5 a second, PRO 50. Configuration, not if-statements: a new plan is a
// new entry, and nothing that reads limits changes.
class PlanLimits implements LimitPolicy {
    private final Plans plans;
    // Set once and only read after that (Map.of is immutable): every thread can read it with
    // no lock, because a final field is visible to all threads once the constructor ends.
    private final Map<Plan, Limit> limitOf;

    PlanLimits(Plans plans, Map<Plan, Limit> limitOf) {
        this.plans = plans;
        this.limitOf = limitOf;
    }

    @Override
    public Limit limitFor(RequestContext request) {
        return limitOf.get(plans.planOf(request.clientId()));
    }
}
