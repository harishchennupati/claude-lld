import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

// The whole API's limits at the door, each an ordinary limiter with its own key.
public class LimitsDemo {
    public static void main(String[] args) {
        AtomicLong now = new AtomicLong(0);
        Clock clock = now::get;
        TierLimits tiers = new TierLimits();
        tiers.setTier("fantasy-app", Tier.PRO);
        ApiLimits api = new ApiLimits(
                limiter(tiers, Algorithm.TOKEN_BUCKET, clock),
                limiter(key -> Limit.perDay(10_000), Algorithm.FIXED_WINDOW, clock),
                limiter(key -> Limit.perSecond(2), Algorithm.TOKEN_BUCKET, clock),
                limiter(key -> Limit.perMinute(5), Algorithm.SLIDING_WINDOW_LOG, clock),
                limiter(key -> Limit.perSecond(1_000), Algorithm.TOKEN_BUCKET, clock));

        for (int i = 1; i <= 3; i++) {
            show(api, new Request("fantasy-app", "198.51.100.4", "/search"), i);
        }
        show(api, new Request("fantasy-app", "198.51.100.4", "/scores"), 4);
        for (int i = 1; i <= 6; i++) {
            show(api, new Request(null, "203.0.113.7", "/login"), i);
        }
    }

    static RateLimiter limiter(LimitPolicy limits, Algorithm a, Clock clock) {
        return new PerKeyRateLimiter(limits, new InMemoryCounterStore(a), clock);
    }

    static void show(ApiLimits api, Request r, int n) {
        String who = r.customerId() == null ? "ip " + r.ip() : r.customerId();
        System.out.printf("%-17s %-8s #%d  %s%n", who, r.endpoint(), n, Check.show(api.check(r)));
    }
}
