import java.util.ArrayList;
import java.util.List;

// A request goes ahead only if every rule that covers it agrees. Rules are checked in order;
// on the first refusal, the tokens the earlier rules took are given back: all or nothing.
class RuleBasedRateLimiter implements RateLimiter {
    private final List<RateLimitRule> rules;      // from the config, in order
    private final CounterStore counters;          // where every rule's counts live
    private final Clock clock;

    RuleBasedRateLimiter(List<RateLimitRule> rules, CounterStore counters, Clock clock) {
        this.rules = List.copyOf(rules);          // read-only: threads share it with no lock
        this.counters = counters;
        this.clock = clock;
    }

    @Override
    public RateLimitResult check(Request request) {
        long now = clock.nowMillis();             // one instant for every rule
        List<Counter> charged = new ArrayList<>();
        for (RateLimitRule rule : rules) {
            if (!rule.covers(request)) {
                continue;
            }
            Limit limit = rule.limits().limitFor(request);
            Counter counter = counters.counterFor(rule.keyFor(request), limit, rule.algorithm(),
                    now);
            Decision d = counter.tryAcquire(now);
            if (!d.allowed()) {
                for (Counter spent : charged) {
                    spent.refund(now);            // a refused request spends nothing anywhere
                }
                return RateLimitResult.refused(rule.name(), d.retryAfterMillis());
            }
            charged.add(counter);
        }
        return RateLimitResult.ALLOWED;
    }
}
