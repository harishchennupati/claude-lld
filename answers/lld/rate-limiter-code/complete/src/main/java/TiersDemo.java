import java.util.concurrent.atomic.AtomicLong;

// FREE gets 5 a second, PRO 50; an upgrade applies at the next request.
public class TiersDemo {
    public static void main(String[] args) {
        AtomicLong now = new AtomicLong(0);
        TierLimits tiers = new TierLimits();
        tiers.setTier("fantasy-app", Tier.PRO);
        RateLimiter limiter = new PerKeyRateLimiter(tiers,
                new InMemoryCounterStore(Algorithm.TOKEN_BUCKET), now::get);
        int widget = count(limiter, "score-widget", 60);
        int fantasy = count(limiter, "fantasy-app", 60);
        System.out.printf("score-widget (FREE): 60 asked, %d allowed%n", widget);
        System.out.printf("fantasy-app  (PRO):  60 asked, %d allowed%n", fantasy);
        tiers.setTier("score-widget", Tier.PRO);
        int upgraded = count(limiter, "score-widget", 60);
        System.out.printf("score-widget upgraded, same instant: 60 asked, %d allowed%n", upgraded);
        Check.that(widget == 5 && fantasy == 50 && upgraded == 50, "tiers");
    }

    static int count(RateLimiter limiter, String customer, int n) {
        int ok = 0;
        for (int i = 0; i < n; i++) {
            if (limiter.rateLimit(customer)) {
                ok++;
            }
        }
        return ok;
    }
}
