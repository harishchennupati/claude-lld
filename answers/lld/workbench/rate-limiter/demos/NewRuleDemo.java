import java.util.concurrent.atomic.AtomicLong;

// The new rule: exports, 10 a minute per customer. One line in the config, nothing else.
public class NewRuleDemo {
    public static void main(String[] args) {
        AtomicLong now = new AtomicLong(0);
        Customers customers = new Customers();
        customers.setPlan("fantasy-app", Plan.PRO);
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(customers),
                new InMemoryCounterStore(), now::get);
        Request export = new Request("fantasy-app", "198.51.100.9", "/export");
        int allowed = 0;
        RateLimitResult last = null;
        for (int i = 0; i < 11; i++) {
            last = limiter.check(export);
            if (last.allowed()) {
                allowed++;
            }
        }
        System.out.println("fantasy-app, 11 exports at once: " + allowed + " allowed; the 11th "
                + Check.show(last));
        Check.that(allowed == 10 && "export".equals(last.refusedBy()), "10 exports a minute");
    }
}
