// "limit: plan.rate" or "plan.daily": whatever the customer's plan carries.
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
        Plan plan = customers.planOf(request.customerId());
        return switch (field) {
            case RATE -> plan.rate;
            case DAILY -> plan.daily;
        };
    }
}
