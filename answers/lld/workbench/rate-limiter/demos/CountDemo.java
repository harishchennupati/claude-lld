// Two more ways to count, and choosing one by name. Sign-ins, 5 a minute: a token bucket earns
// one back every 12 s; the log waits until the first attempt is a minute old. Then a daily
// quota of 3, just before midnight.
public class CountDemo {
    public static void main(String[] args) {
        Bucket bucket = Algorithm.valueOf("TOKEN_BUCKET").create(Limit.perMinute(5), 0);
        Bucket log = Algorithm.valueOf("SLIDING_WINDOW_LOG").create(Limit.perMinute(5), 0);
        for (int i = 0; i < 5; i++) {
            bucket.tryConsume(1, 0);
            log.tryConsume(1, 0);
        }
        System.out.println("5 sign-ins at 0 s, a 6th at 12 s:");
        System.out.println("  " + bucket.getClass().getSimpleName() + "        "
                + Check.show(bucket.tryConsume(1, 12_000)));
        System.out.println("  " + log.getClass().getSimpleName() + "   "
                + Check.show(log.tryConsume(1, 12_000)));

        long lateEvening = 86_400_000L * 20_000 + 86_000_000;          // 23:53:20 UTC
        Bucket quota = Algorithm.FIXED_WINDOW.create(Limit.perDay(3), lateEvening);
        StringBuilder today = new StringBuilder();
        for (int i = 0; i < 4; i++) {
            today.append(quota.tryConsume(1, lateEvening).allowed() ? " yes" : " no");
        }
        System.out.println("a quota of 3 a day, 4 requests at 23:53:20:" + today);
        System.out.println("  the 4th again     " + Check.show(quota.tryConsume(1, lateEvening)));
        System.out.println("  at 00:00:00       "
                + Check.show(quota.tryConsume(1, lateEvening + 400_000)));
    }
}
