// Two servers, one budget. With a map in each server, each grants the whole limit; with the
// bucket in Redis, the servers share it.
public class F8Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        plans.assign("fantasy-app", Plan.PRO);

        RateLimiter localA = new ClientRateLimiter(plans, TokenBucket::new, clock);
        RateLimiter localB = new ClientRateLimiter(plans, TokenBucket::new, clock);
        int local = send(localA, localB);

        FakeRedis redis = new FakeRedis(clock);
        RateLimiter serverA = new RedisRateLimiter(plans, redis, true);
        RateLimiter serverB = new RedisRateLimiter(plans, redis, true);
        int shared = send(serverA, serverB);

        System.out.println("fantasy-app (limit 50), 60 requests, 30 to each of 2 servers:");
        System.out.println("  a map in each server: " + local + " allowed   (each server grants the whole 50)");
        System.out.println("  one bucket in Redis:  " + shared + " allowed");
        Check.that(local == 60 && shared == 50, "60 without Redis, 50 with it");

        redis.setDown(true);
        RateLimiter logins = new RedisRateLimiter(plans, redis, false);
        System.out.println("Redis down, scores (fail open):  " + serverA.tryAcquire("fantasy-app"));
        System.out.println("Redis down, logins (fail closed): " + logins.tryAcquire("priya@login"));
    }

    static int send(RateLimiter a, RateLimiter b) {
        int allowed = 0;
        for (int i = 0; i < 30; i++) {
            if (a.tryAcquire("fantasy-app").allowed()) {
                allowed++;
            }
            if (b.tryAcquire("fantasy-app").allowed()) {
                allowed++;
            }
        }
        return allowed;
    }
}
