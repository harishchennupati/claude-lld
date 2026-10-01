import java.util.List;

// The config, in code: one line per rule, in the order they are checked. Read it next to the
// YAML on the first step. A new rule is a new line here; nothing else changes.
final class ScoreApiRules {
    static List<RateLimitRule> build(Customers customers) {
        LimitPolicy planRate = new PlanLimit(customers, PlanLimit.Field.RATE);
        LimitPolicy planDaily = new PlanLimit(customers, PlanLimit.Field.DAILY);
        return List.of(
            new RateLimitRule("rate", null, true, CountPer.CUSTOMER, planRate,
                    Algorithm.TOKEN_BUCKET),
            new RateLimitRule("daily", null, true, CountPer.CUSTOMER, planDaily,
                    Algorithm.FIXED_WINDOW),
            new RateLimitRule("search", "/search", true, CountPer.CUSTOMER_AND_ENDPOINT,
                    new FixedLimit(Limit.perSecond(2)), Algorithm.TOKEN_BUCKET),
            new RateLimitRule("login", "/login", false, CountPer.IP,
                    new FixedLimit(Limit.perMinute(5)), Algorithm.SLIDING_WINDOW_LOG),
            new RateLimitRule("export", "/export", true, CountPer.CUSTOMER_AND_ENDPOINT,
                    new FixedLimit(Limit.perMinute(10)), Algorithm.TOKEN_BUCKET),
            new RateLimitRule("global", null, false, CountPer.EVERYONE,      // last: the busiest
                    new FixedLimit(Limit.perSecond(1_000)), Algorithm.TOKEN_BUCKET));
    }
}
