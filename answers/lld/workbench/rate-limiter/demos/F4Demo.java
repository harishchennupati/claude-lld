import java.util.List;

// Three rules on every request: the client's plan, 2 searches a second per client, and 100
// requests a second for the whole API. A request passes only if all of them allow it.
public class F4Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        plans.assign("fantasy-app", Plan.PRO);
        ClientRateLimiter perPlan = new ClientRateLimiter(plans, TokenBucket::new, clock);
        ClientRateLimiter searches = new ClientRateLimiter(key -> Limit.perSecond(2), TokenBucket::new, clock);
        ClientRateLimiter everyone = new ClientRateLimiter(key -> Limit.perSecond(100), TokenBucket::new, clock);
        AllRulesLimiter rules = new AllRulesLimiter(List.of(
                new Rule("plan", r -> true, Request::clientId, perPlan),
                new Rule("search", r -> r.endpoint().equals("/search"), r -> r.clientId() + " /search", searches),
                new Rule("global", r -> true, r -> "*", everyone)), clock);

        for (int i = 1; i <= 3; i++) {
            show("fantasy-app /search #" + i, rules.check(Request.of("fantasy-app", "/search")));
        }
        AllRulesLimiter.Result next = rules.check(Request.of("fantasy-app", "/scores"));
        show("fantasy-app /scores", next);
        System.out.println("   (the 3rd search's plan token was given back: 47 left, not 46)");
        Check.that(next.decision().remaining() == 47, "47 left after the refund");

        clock.advance(1_000);                            // a new second: the global bucket is full again
        for (int site = 1; site <= 20; site++) {         // 20 news sites, 5 requests each: 100 in all
            for (int i = 0; i < 5; i++) {
                rules.check(Request.of("news-site-" + site, "/scores"));
            }
        }
        AllRulesLimiter.Result blog = rules.check(Request.of("cricket-blog", "/scores"));
        show("cricket-blog /scores", blog);
        System.out.println("   (its own FREE budget was untouched: the plan token it took was given back)");
        Check.that("global".equals(blog.refusedBy()), "the global rule refuses the 101st request");
    }

    static void show(String what, AllRulesLimiter.Result r) {
        String by = r.refusedBy() == null ? "" : "   refused by: " + r.refusedBy();
        System.out.printf("%-22s  %s%s%n", what, r.decision(), by);
    }
}
