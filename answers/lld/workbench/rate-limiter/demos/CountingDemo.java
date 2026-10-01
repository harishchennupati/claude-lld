// The two other ways the rules count: the daily quota's fixed window and the sign-ins' log.
public class CountingDemo {
    public static void main(String[] args) {
        Counter daily = new FixedWindowCounter(new Limit(3, 86_400_000), 0);   // 3 a day, short
        StringBuilder d = new StringBuilder("daily, 3 a day:      ");
        for (int i = 0; i < 4; i++) {
            d.append(daily.tryAcquire(1_000).allowed() ? " allowed" : " refused");
        }
        Decision tomorrow = daily.tryAcquire(86_400_000);
        d.append(" | next day: ").append(Check.show(tomorrow));
        System.out.println(d);

        Counter login = new SlidingWindowLog(Limit.perMinute(5));
        for (int t = 0; t < 5; t++) {
            login.tryAcquire(t * 10_000L);                                // 0 s, 10 s ... 40 s
        }
        Decision sixth = login.tryAcquire(59_000);
        Decision later = login.tryAcquire(60_000);
        System.out.println("login, 5 a minute:    5 tries by 40 s | 59 s: " + Check.show(sixth)
                + " | 60 s: " + Check.show(later));
        Check.that(tomorrow.allowed() && !sixth.allowed() && sixth.retryAfterMillis() == 1_000
                && later.allowed(), "fixed window resets; the log is exact");
    }
}
