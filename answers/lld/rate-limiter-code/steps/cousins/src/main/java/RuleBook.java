import java.util.ArrayList;
import java.util.List;

// The rules, in the order they are checked. Built once and only read after that, so every
// request thread shares it without a lock.
class RuleBook {
    private final List<RateLimitRule> rules;

    // Rule names go into bucket keys, so each must be unique. Pass an unmodifiable List.of(...).
    RuleBook(List<RateLimitRule> rules) {
        this.rules = rules;
    }

    // The rules that cover this request, in order.
    List<RateLimitRule> matching(RequestContext request) {
        List<RateLimitRule> out = new ArrayList<>();
        for (RateLimitRule rule : rules) {
            if (rule.appliesTo().test(request)) {
                out.add(rule);
            }
        }
        return out;
    }
}
