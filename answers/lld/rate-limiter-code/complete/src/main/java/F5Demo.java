// Ops want to cut FREE from 5 to 3 a second. First a shadow run shows whom it would hurt,
// then the new limit goes live without a restart.
public class F5Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans live = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        Plans candidate = new Plans(Limit.perSecond(3), Limit.perSecond(50));
        live.assign("fantasy-app", Plan.PRO);
        candidate.assign("fantasy-app", Plan.PRO);
        ShadowLimiter shadow = new ShadowLimiter(
                new ClientRateLimiter(live, TokenBucket::new, clock),
                new ClientRateLimiter(candidate, TokenBucket::new, clock));

        int widget = 0;
        for (int i = 0; i < 5; i++) {
            if (shadow.tryAcquire("score-widget").allowed()) {
                widget++;
            }
            shadow.tryAcquire("fantasy-app");
        }
        System.out.println("shadow run: score-widget " + widget + " of 5 allowed;"
                + " the candidate would have refused " + shadow.wouldRefuse());
        Check.that(widget == 5 && shadow.wouldRefuse() == 2, "5 allowed, 2 would be refused");

        RateLimiter limiter = new ClientRateLimiter(live, TokenBucket::new, clock);
        limiter.tryAcquire("score-widget");                 // its bucket is built for 5 a second
        live.setLimit(Plan.FREE, Limit.perSecond(3));       // ops change the limit: no restart
        clock.advance(1_000);
        int after = 0;
        Decision last = null;
        for (int i = 0; i < 5; i++) {
            last = limiter.tryAcquire("score-widget");
            if (last.allowed()) {
                after++;
            }
        }
        System.out.println("after the change: " + after + " of 5 allowed, then " + last);
        Check.that(after == 3, "the next request built a bucket for 3 a second");
    }
}
