// 5 a second with credits: a quiet second saves 5, spent after the next second's own 5.
public class CreditsDemo {
    public static void main(String[] args) {
        Counter c = new InMemoryCounterStore(Algorithm.CREDITS)
                .counterFor("news-app", Limit.perSecond(5), 0);
        int first = count(c, 100, 2);             // second 0: uses 2 of 5, saves 3
        int second = count(c, 1_100, 12);         // second 1: 5 of its own + 3 credits
        int fourth = count(c, 3_100, 12);         // second 2 was quiet: it saves 5, the cap
        System.out.printf("second 0: 2 asked, %d allowed (3 unused, saved)%n", first);
        System.out.printf("second 1: 12 asked, %d allowed (5 + 3 credits)%n", second);
        System.out.printf("second 3, after a quiet one: 12 asked, %d allowed (5 + 5)%n", fourth);
        Check.that(first == 2 && second == 8 && fourth == 10, "credits");
    }

    static int count(Counter c, long now, int n) {
        int ok = 0;
        for (int i = 0; i < n; i++) {
            if (c.tryAcquire(now).allowed()) {
                ok++;
            }
        }
        return ok;
    }
}
