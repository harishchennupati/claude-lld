import java.util.LinkedHashMap;
import java.util.Map;

// All five ways of counting on the same traffic: 5 a second, 5 requests at 995 ms and 5 more at
// 1,001 ms. Then the counter's estimate, and the leaky bucket against the token bucket.
public class MoreDemo {
    public static void main(String[] args) {
        Map<String, Algorithm> all = new LinkedHashMap<>();
        all.put("fixed window", Algorithm.FIXED_WINDOW);
        all.put("sliding window log", Algorithm.SLIDING_WINDOW_LOG);
        all.put("sliding window counter", Algorithm.SLIDING_WINDOW_COUNTER);
        all.put("token bucket", Algorithm.TOKEN_BUCKET);
        all.put("leaky bucket (meter)", Algorithm.LEAKY_BUCKET);
        System.out.println("                        995 ms   1,001 ms   the next request");
        int fixedTotal = 0;
        for (Map.Entry<String, Algorithm> e : all.entrySet()) {
            Bucket bucket = e.getValue().create(Limit.perSecond(5), 0);
            int early = 0;
            int late = 0;
            for (int i = 0; i < 5; i++) {
                early += bucket.tryConsume(1, 995).allowed() ? 1 : 0;
            }
            for (int i = 0; i < 5; i++) {
                late += bucket.tryConsume(1, 1_001).allowed() ? 1 : 0;
            }
            Decision next = bucket.tryConsume(1, 1_001);
            System.out.printf("%-24s %4d   %8d     %s%n", e.getKey(), early, late, next);
            if (e.getValue() == Algorithm.FIXED_WINDOW) {
                fixedTotal = early + late;
            }
        }
        Check.that(fixedTotal == 10, "the fixed window lets 10 through in 6 ms");

        // The counter: 5 hits at 999 ms; at 1,300 ms, 70% of the last second still counts, so
        // the estimate is 3.5: one more fits, the next does not.
        Bucket counter = Algorithm.SLIDING_WINDOW_COUNTER.create(Limit.perSecond(5), 0);
        for (int i = 0; i < 5; i++) {
            counter.tryConsume(1, 999);
        }
        Decision one = counter.tryConsume(1, 1_300);
        Decision two = counter.tryConsume(1, 1_300);
        System.out.println("\ncounter, 5 at 999 ms, then at 1,300 ms: " + one + "; then " + two);
        Check.that(one.allowed() && !two.allowed(), "estimate 3.5: one more, then no");

        // The leaky bucket as a meter is the token bucket in a mirror (level = 5 - tokens).
        // Storing 4.4 instead of 0.6 rounds differently: a retry can come out 1 ms longer.
        Bucket leaky = Algorithm.LEAKY_BUCKET.create(Limit.perSecond(5), 0);
        Bucket token = Algorithm.TOKEN_BUCKET.create(Limit.perSecond(5), 0);
        long[] times = {0, 0, 0, 0, 0, 0, 120, 200};
        int same = 0;
        for (long t : times) {
            Decision l = leaky.tryConsume(1, t);
            Decision k = token.tryConsume(1, t);
            long gap = l.retryAfterMillis() - k.retryAfterMillis();
            same += l.allowed() == k.allowed() && gap >= 0 && gap <= 1 ? 1 : 0;
        }
        System.out.println("leaky vs token bucket, the eight requests from the bucket step: "
                + same + " the same (retry times within 1 ms)");
        Check.that(same == 8, "the same eight answers");
    }
}
