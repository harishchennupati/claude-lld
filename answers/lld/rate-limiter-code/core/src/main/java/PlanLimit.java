// "limit: { from_plan: rate }": whatever the customer's plan carries. Which of the plan's
// limits a rule uses (its rate, or its daily allowance) is the field.
// Why a class, not a record: it holds the live Customers directory and looks the plan up on every
// call, so it is behaviour rather than a value. Field is an enum nested inside, because only
// PlanLimit uses it.
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
