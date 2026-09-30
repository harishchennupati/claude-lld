//@ file from f4
import java.util.ArrayList;
import java.util.List;

// Checks every rule that covers a request. The request passes only if ALL of them allow it,
// and a refused request spends nothing from any of them.
class AllRulesLimiter {
    // Checked in this order. Any order gives the same answers, because a refusal gives back
    // what the earlier rules took. The global rule goes last: its one bucket is shared by every
    // client, so it is the busiest lock, and a request another rule refuses never touches it.
    private final List<Rule> rules;
    private final Clock clock;

    AllRulesLimiter(List<Rule> rules, Clock clock) {
        this.rules = List.copyOf(rules);
        this.clock = clock;
    }

    // The decision, and the name of the rule that refused (null when the request is allowed).
    record Result(Decision decision, String refusedBy) {
    }

    Result check(Request request) {
        long now = clock.nowMillis();                     // one instant for every rule
        List<Rule> charged = new ArrayList<>();
        long remaining = Long.MAX_VALUE;
        for (Rule rule : rules) {
            if (!rule.appliesTo().test(request)) {
                continue;
            }
            String key = rule.key().apply(request);
            Decision d = rule.limiter().tryAcquire(key, request.cost(), now);
            if (!d.allowed()) {
                // All or nothing: give back what the earlier rules took for this request.
                for (Rule done : charged) {
                    done.limiter().refund(done.key().apply(request), request.cost(), now);
                }
                return new Result(d, rule.name());
            }
            charged.add(rule);
            remaining = Math.min(remaining, d.remaining());   // the tightest rule decides
        }
        return new Result(Decision.allow(remaining), null);
    }
}
