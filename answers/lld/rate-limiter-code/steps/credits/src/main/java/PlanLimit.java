// "limit: { from_plan: rate }": whatever the customer's plan carries. Which of the plan's limits
// a rule uses (its rate, or its daily allowance) is the field.
class PlanLimit implements LimitPolicy {
    enum Field { RATE, DAILY }

    private final Customers customers;
    private final Field field;

    PlanLimit(Customers customers, Field field) {
        this.customers = customers;
        this.field = field;
    }

    @Override
    public Limit limitFor(Request request) {
        Plan plan = customers.planOf(request.customerId());     // looked up on every request,
        return switch (field) {                                  // so an upgrade applies at once
            case RATE -> plan.rate;
            case DAILY -> plan.daily;
        };
    }
}
