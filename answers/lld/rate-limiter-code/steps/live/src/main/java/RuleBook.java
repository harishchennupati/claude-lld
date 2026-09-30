import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

// The rules, in the order they are checked. Built once and only read after that, so every
// request thread shares it without a lock.
class RuleBook {
    private final List<RateLimitRule> rules;

    RuleBook(List<RateLimitRule> rules) {
        Set<String> names = new HashSet<>();
        for (RateLimitRule rule : rules) {
            if (!names.add(rule.name())) {      // names are part of bucket keys: they must differ
                throw new IllegalArgumentException("two rules named " + rule.name());
            }
        }
        this.rules = List.copyOf(rules);        // unmodifiable: nobody can change it later
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
