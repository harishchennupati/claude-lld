import java.util.ArrayList;
import java.util.List;

// Decides one request by asking every rule that matches it. The request goes ahead only if all of
// them allow it. Rules are asked in order, and each one takes its token as it goes; if a later
// rule refuses, the tokens the earlier ones took are given back, so a refused request spends
// nothing anywhere ("all or nothing").
class RuleBasedRateLimiter implements RateLimiter {
    private final List<RateLimitRule> rules;      // from the config, in the order they are checked
    private final CounterStore counters;          // where every rule's counts live
    private final Clock clock;                    // passed in, so a demo can move time by hand

    RuleBasedRateLimiter(List<RateLimitRule> rules, CounterStore counters, Clock clock) {
        this.rules = List.copyOf(rules);          // read-only: every thread shares it, no lock
        this.counters = counters;
        this.clock = clock;
    }

    @Override
    public RateLimitResult check(Request request) {
        long now = clock.nowMillis();             // one instant for every rule of this request
        List<Counter> charged = new ArrayList<>();   // counters that already took a token
        for (RateLimitRule rule : rules) {
            if (!rule.matches(request)) {
                continue;                         // this rule does not cover this request
            }
            // How much this rule allows for this caller (fixed, or from the customer's plan),
            // and the counter for this rule and this caller: "search:fantasy-app:/search".
            Limit limit = rule.limits().limitFor(request);
            Counter counter = counters.counterFor(rule.keyFor(request), limit, rule.algorithm(),
                    now);
            Decision d = counter.tryAcquire(now);
            if (!d.allowed()) {
                // Give back what the earlier rules took: this request will not run.
                for (Counter spent : charged) {
                    spent.refund(now);
                }
                return RateLimitResult.refused(rule.name(), d.retryAfterMillis());
            }
            charged.add(counter);
        }
        return RateLimitResult.ALLOWED;           // every matching rule allowed it (or none did)
    }
}
