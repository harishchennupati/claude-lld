import java.util.Map;
import java.util.TreeMap;

// The front door: what the client sees. The endpoint is a function from request to response;
// headers are printed sorted so every run looks the same.
public class DoorDemo {
    public static void main(String[] args) {
        Plans plans = new Plans();
        plans.assign("fantasy-app", Plan.PRO);
        RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(plans),
                new InMemoryBucketStore(), new ManualClock(0));
        RateLimitFilter api = new RateLimitFilter(limiter);
        show("GET /scores   ", api.handle(
                RequestContext.of("fantasy-app", "203.0.113.7", "/scores"),
                request -> new RateLimitFilter.Response(200, Map.of())));
        for (int i = 1; i <= 3; i++) {
            show("GET /search #" + i, api.handle(
                    RequestContext.of("fantasy-app", "203.0.113.7", "/search"),
                    request -> new RateLimitFilter.Response(200, Map.of())));
        }
        System.out.println("rateLimit(\"score-widget\") -> " + limiter.rateLimit("score-widget"));
    }

    static void show(String what, RateLimitFilter.Response r) {
        System.out.println(what + "  " + r.status() + " " + new TreeMap<>(r.headers()));
    }
}
