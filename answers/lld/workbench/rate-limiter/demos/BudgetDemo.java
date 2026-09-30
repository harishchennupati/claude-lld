import java.util.Map;

// Whose budget, and how much: the key each scope makes from one request, and one limit per plan.
public class BudgetDemo {
    public static void main(String[] args) {
        RequestContext request = RequestContext.of("fantasy-app", "203.0.113.7", "/search");
        for (KeyScope scope : KeyScope.values()) {
            System.out.printf("%-20s -> %s%n", scope, scope.keyOf(request));
        }
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);
        LimitPolicy perSecond = new PlanLimits(plans,
                Map.of(Plan.FREE, Limit.perSecond(5), Plan.PRO, Limit.perSecond(50)));
        for (String client : new String[] {"fantasy-app", "score-widget", "brand-new-app"}) {
            RequestContext r = RequestContext.of(client, "203.0.113.7", "/scores");
            System.out.printf("%-20s -> %s%n", client, perSecond.limitFor(r));
        }
        LimitPolicy searches = LimitPolicy.fixed(Limit.perSecond(2));
        System.out.printf("%-20s -> %s%n", "any client, /search", searches.limitFor(request));
    }
}
