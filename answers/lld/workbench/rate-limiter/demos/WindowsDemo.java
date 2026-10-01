import java.util.List;

// Four ways of counting, 5 a second, on the same two tests.
public class WindowsDemo {
    static final List<Algorithm> ALL = List.of(Algorithm.FIXED_WINDOW,
            Algorithm.SLIDING_WINDOW_LOG, Algorithm.SLIDING_WINDOW_COUNTER, Algorithm.TOKEN_BUCKET);

    public static void main(String[] args) {
        System.out.println("test 1, the window edge: 5 at 995 ms, then 5 at 1001 ms");
        for (Algorithm a : ALL) {
            Counter c = counter(a, 995);
            String marks = burst(c, 995, 5) + "  " + burst(c, 1001, 5);
            long passed = marks.chars().filter(ch -> ch == 'Y').count();
            System.out.printf("  %-23s %s  %2d passed%n", a, marks, passed);
            Check.that(passed == (a == Algorithm.FIXED_WINDOW ? 10 : 5), a + " at the edge");
        }
        System.out.println("test 2, a trickle: 5 at 0 ms, then one every 200 ms");
        for (Algorithm a : List.of(Algorithm.SLIDING_WINDOW_LOG, Algorithm.TOKEN_BUCKET)) {
            Counter c = counter(a, 0);
            StringBuilder marks = new StringBuilder(burst(c, 0, 5));
            for (long t = 200; t <= 1000; t += 200) {
                marks.append(' ').append(burst(c, t, 1));
            }
            System.out.printf("  %-23s %s%n", a, marks);
        }
    }

    static Counter counter(Algorithm a, long now) {
        return new InMemoryCounterStore(a).counterFor("demo", Limit.perSecond(5), now);
    }

    static String burst(Counter c, long now, int n) {
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < n; i++) {
            s.append(c.tryAcquire(now).allowed() ? 'Y' : '.');
        }
        return s.toString();
    }
}
