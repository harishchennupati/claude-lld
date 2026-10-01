import java.util.List;

// The rules section of rate-limits.yaml, in code: one entry per rule, in the order they are
// checked. Read it next to the YAML. A new limit is a new entry here; no other class changes.
// Why a final class with a static method: it holds no state, it is just one function that builds
// the list, so nobody needs an object of it and nobody should extend it. (Loading the YAML file at
// startup would replace this class and nothing else.)
final class ScoreApiRules {
    static List<RateLimitRule> build(Customers customers) {
        Match anyCustomerRequest = new Match(Caller.CUSTOMER, Match.ANY_ENDPOINT);
        return List.of(
            // each customer's speed: a burst, then a steady rate, by plan
            new RateLimitRule("rate", anyCustomerRequest, CountPer.CUSTOMER,
                    new PlanLimit(customers, PlanLimit.Field.RATE), Algorithm.TOKEN_BUCKET),
            // each customer's allowance for the calendar day, by plan
            new RateLimitRule("daily", anyCustomerRequest, CountPer.CUSTOMER,
                    new PlanLimit(customers, PlanLimit.Field.DAILY), Algorithm.FIXED_WINDOW),
            // search is expensive: its own small budget per customer
            new RateLimitRule("search", new Match(Caller.CUSTOMER, "/search"),
                    CountPer.CUSTOMER_AND_ENDPOINT, new FixedLimit(Limit.perSecond(2)),
                    Algorithm.TOKEN_BUCKET),
            // sign-in has no API key yet: count by IP, and exactly (stops password guessing)
            new RateLimitRule("login", new Match(Caller.ANY, "/login"), CountPer.IP,
                    new FixedLimit(Limit.perMinute(5)), Algorithm.SLIDING_WINDOW_LOG),
            //@ from newrule
            // exports are heavy: 10 a minute per customer
            new RateLimitRule("export", new Match(Caller.CUSTOMER, "/export"),
                    CountPer.CUSTOMER_AND_ENDPOINT, new FixedLimit(Limit.perMinute(10)),
                    Algorithm.TOKEN_BUCKET),
            //@ end
            // protects the servers. Last on purpose: its one counter is shared by every request,
            // the busiest lock in the system, so only requests every other rule allowed reach it.
            new RateLimitRule("global", new Match(Caller.ANY, Match.ANY_ENDPOINT),
                    CountPer.EVERYONE, new FixedLimit(Limit.perSecond(1_000)),
                    Algorithm.TOKEN_BUCKET));
    }
}
