import java.util.Map;

// The front door: what the client sees. The endpoint is a function from request to response.
public class DoorDemo {
    public static void main(String[] args) {
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(plans),
                new InMemoryBucketStore(), new ManualClock(0));
        RateLimitFilter api = new RateLimitFilter(limiter);
        RateLimitFilter.Response ok = api.handle(
                RequestContext.of("fantasy-app", "203.0.113.7", "/scores"),
                request -> new RateLimitFilter.Response(200, Map.of()));
        System.out.println("GET /scores            " + ok.status() + " " + ok.headers());
        for (int i = 1; i <= 3; i++) {
            RateLimitFilter.Response r = api.handle(
                    RequestContext.of("fantasy-app", "203.0.113.7", "/search"),
                    request -> new RateLimitFilter.Response(200, Map.of()));
            System.out.println("GET /search #" + i + "         " + r.status() + " " + r.headers());
        }
        RateLimitFilter.Response big = api.handle(
                new RequestContext("score-widget", "203.0.113.7", "/export", 6),
                request -> new RateLimitFilter.Response(200, Map.of()));
        System.out.println("GET /export (cost 6)   " + big.status() + " " + big.headers());
        System.out.println("rateLimit(\"score-widget\") -> " + limiter.rateLimit("score-widget"));
    }
}
