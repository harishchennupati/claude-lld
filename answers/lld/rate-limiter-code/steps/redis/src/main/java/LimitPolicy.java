// "Which limit applies to this request?" A rule with one limit for everyone uses fixed(...); a
// rule whose limit depends on the client's plan uses PlanLimits.
@FunctionalInterface
interface LimitPolicy {
    Limit limitFor(RequestContext request);

    static LimitPolicy fixed(Limit limit) {
        return request -> limit;
    }
}
