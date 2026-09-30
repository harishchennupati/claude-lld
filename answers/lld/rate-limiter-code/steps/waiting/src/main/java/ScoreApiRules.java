import java.util.List;
import java.util.Map;

// The score API's rules: configuration, written once at startup (in production, read from a
// file). Reading the table top to bottom is reading the product's limits.
final class ScoreApiRules {
    private ScoreApiRules() {
    }

    static RuleBook build(Plans plans) {
        return build(plans, Limit.perSecond(5));
    }

    // The same rules with a different FREE rate: what ops change without a restart.
    static RuleBook build(Plans plans, Limit freeRate) {
        return new RuleBook(List.of(
                // Every client with a key: its plan's rate, with bursts.
                new RateLimitRule("plan", RateLimitRule.withKey(), KeyScope.CLIENT,
                        new PlanLimits(plans, Map.of(Plan.FREE, freeRate,
                                Plan.PRO, Limit.perSecond(50))),
                        Algorithm.TOKEN_BUCKET),
                // ...and its plan's daily quota, which starts again at midnight.
                new RateLimitRule("quota", RateLimitRule.withKey(), KeyScope.CLIENT,
                        new PlanLimits(plans, Map.of(Plan.FREE, Limit.perDay(10_000),
                                Plan.PRO, Limit.perDay(1_000_000))),
                        Algorithm.FIXED_WINDOW),
                // Search is expensive: 2 a second per client, whatever the plan.
                new RateLimitRule("search",
                        RateLimitRule.withKey().and(RateLimitRule.endpoint("/search")),
                        KeyScope.CLIENT_AND_ENDPOINT, LimitPolicy.fixed(Limit.perSecond(2)),
                        Algorithm.TOKEN_BUCKET),
                // Sign-ins carry no key yet: 5 attempts a minute per IP, exactly.
                new RateLimitRule("login", RateLimitRule.endpoint("/login"), KeyScope.IP,
                        LimitPolicy.fixed(Limit.perMinute(5)), Algorithm.SLIDING_WINDOW_LOG),
                // The whole API: what the servers can take. Last on purpose: its one bucket is
                // the busiest lock, and only requests every other rule allowed reach it.
                new RateLimitRule("global", RateLimitRule.everyRequest(), KeyScope.EVERYONE,
                        LimitPolicy.fixed(Limit.perSecond(1_000)), Algorithm.TOKEN_BUCKET)));
    }
}
