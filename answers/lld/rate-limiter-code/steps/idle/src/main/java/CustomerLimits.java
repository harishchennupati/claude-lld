import java.util.Map;

// "Each customer may make X requests every Y seconds": a limit per customer, and a default for
// everyone not listed. Built once at startup and never changed, so threads share it freely.
class CustomerLimits implements LimitPolicy {
    private final Map<String, Limit> byCustomer;
    private final Limit defaultLimit;

    CustomerLimits(Map<String, Limit> byCustomer, Limit defaultLimit) {
        this.byCustomer = Map.copyOf(byCustomer);
        this.defaultLimit = defaultLimit;
    }

    @Override
    public Limit limitFor(String customerId) {
        return byCustomer.getOrDefault(customerId, defaultLimit);
    }
}
