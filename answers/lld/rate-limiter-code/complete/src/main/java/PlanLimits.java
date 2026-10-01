import java.util.Map;

// A limit per plan: FREE 5 a second, PRO 50. Configuration, not if-statements: a new plan is a
// new entry, and nothing that reads limits changes.
class PlanLimits implements LimitPolicy {
    private final Plans plans;
    // Set once, only read after that: a final field is safely seen by every thread, no lock.
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
