import java.util.List;

// The rule book: which rules cover which request.
public class RuleBookDemo {
    public static void main(String[] args) {
        RuleBook rules = ScoreApiRules.build(new Plans());
        List<RequestContext> requests = List.of(
                RequestContext.of("fantasy-app", "203.0.113.7", "/scores"),
                RequestContext.of("fantasy-app", "203.0.113.7", "/search"),
                RequestContext.of(RequestContext.ANONYMOUS, "192.0.2.1", "/login"),
                RequestContext.of(RequestContext.ANONYMOUS, "192.0.2.1", "/search"));
        for (RequestContext r : requests) {
            StringBuilder names = new StringBuilder();
            for (RateLimitRule rule : rules.matching(r)) {
                names.append(' ').append(rule.name());
            }
            System.out.printf("%-12s %-8s ->%s%n", r.clientId(), r.endpoint(), names);
        }
    }
}
