import java.util.Map;

// Ops want to cut FREE from 5 to 3 a second. A shadow run first shows whom it would hurt; then
// the new rules go live without a restart.
public class LiveDemo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);
        RuleBasedRateLimiter live = new RuleBasedRateLimiter(ScoreApiRules.build(plans),
                new InMemoryBucketStore(), clock);
        RuleBook cut = ScoreApiRules.build(plans, Limit.perSecond(3));
        ShadowRateLimiter shadow = new ShadowRateLimiter(live,
                new RuleBasedRateLimiter(cut, new InMemoryBucketStore(), clock));
        for (int i = 0; i < 5; i++) {
            shadow.check(RequestContext.of("score-widget", "203.0.113.7", "/scores"));
            shadow.check(RequestContext.of("fantasy-app", "203.0.113.7", "/scores"));
        }
        System.out.println("shadow run, 5 requests each: the new rules would have refused "
                + shadow.report());
        Check.that(shadow.report().equals(Map.of("score-widget", 2L)), "only score-widget, twice");

        live.replaceRules(cut);                             // ops flip the switch: no restart
        clock.advance(1_000);
        int allowed = 0;
        RateLimitResult last = null;
        for (int i = 0; i < 5; i++) {
            last = live.check(RequestContext.of("score-widget", "203.0.113.7", "/scores"));
            allowed += last.allowed() ? 1 : 0;
        }
        System.out.println("after the switch: " + allowed + " of 5 allowed, then " + last);
        Check.that(allowed == 3, "3 a second now");
    }
}
