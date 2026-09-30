import java.util.List;
import java.util.Map;

// Two servers, one budget. With a map in each server, each grants the whole limit; with the
// buckets in Redis, the servers share it. Then Redis goes down.
public class RedisDemo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);
        RuleBook rules = new RuleBook(List.of(new RateLimitRule("plan", RateLimitRule.withKey(),
                KeyScope.CLIENT, new PlanLimits(plans, Map.of(Plan.FREE, Limit.perSecond(5),
                        Plan.PRO, Limit.perSecond(50))), Algorithm.TOKEN_BUCKET)));

        int local = send(new RuleBasedRateLimiter(rules, new InMemoryBucketStore(), clock),
                new RuleBasedRateLimiter(rules, new InMemoryBucketStore(), clock));
        FakeRedis redis = new FakeRedis(clock);
        RedisBucketStore shared = new RedisBucketStore(redis, true);
        RateLimiter serverA = new RuleBasedRateLimiter(rules, shared, clock);
        int together = send(serverA, new RuleBasedRateLimiter(rules, shared, clock));
        System.out.println("fantasy-app (PRO, 50 a second), 60 requests, 30 to each of 2 servers:");
        System.out.println("  a map in each server:   " + local + " allowed  (each grants all 50)");
        System.out.println("  buckets in Redis:       " + together + " allowed");
        Check.that(local == 60 && together == 50, "60 without Redis, 50 with it");

        redis.setDown(true);
        clock.advance(1_000);
        RequestContext r = RequestContext.of("fantasy-app", "203.0.113.7", "/scores");
        RateLimitResult open = serverA.check(r);
        RateLimiter closed = new RuleBasedRateLimiter(rules, new RedisBucketStore(redis, false),
                clock);
        System.out.println("Redis down, fail open:    " + open);
        System.out.println("Redis down, fail closed:  " + closed.check(r));
        Check.that(open.allowed() && open.remaining() == 50, "fail open says the whole budget");
    }

    static int send(RateLimiter a, RateLimiter b) {
        int allowed = 0;
        RequestContext r = RequestContext.of("fantasy-app", "203.0.113.7", "/scores");
        for (int i = 0; i < 30; i++) {
            allowed += a.check(r).allowed() ? 1 : 0;
            allowed += b.check(r).allowed() ? 1 : 0;
        }
        return allowed;
    }
}
