import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

// The limit comes from the customer's tier. Sign-ups and upgrades write while requests read,
// so a ConcurrentHashMap. The limiter is untouched: this is just another LimitPolicy.
class TierLimits implements LimitPolicy {
    private final Map<String, Tier> tierOf = new ConcurrentHashMap<>();

    void setTier(String customerId, Tier tier) {
        tierOf.put(customerId, tier);
    }

    @Override
    public Limit limitFor(String customerId) {
        return tierOf.getOrDefault(customerId, Tier.FREE).limit;
    }
}
