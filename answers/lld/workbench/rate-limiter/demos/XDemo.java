// The same idea in two other interview questions.
public class XDemo {
    public static void main(String[] args) {
        HitCounter hits = new HitCounter();
        hits.hit(1);
        hits.hit(2);
        hits.hit(3);
        hits.hit(300);
        System.out.println("hit counter: getHits(300) = " + hits.getHits(300) + ", getHits(301) = " + hits.getHits(301));
        Check.that(hits.getHits(300) == 4 && hits.getHits(301) == 3, "the hit at 1 s leaves at 301 s");

        LoggerRateLimiter logger = new LoggerRateLimiter();
        boolean a = logger.shouldPrintMessage(1, "foo");
        boolean b = logger.shouldPrintMessage(3, "foo");
        boolean c = logger.shouldPrintMessage(11, "foo");
        System.out.println("logger: foo at 1 s -> " + a + ", at 3 s -> " + b + ", at 11 s -> " + c);
        Check.that(a && !b && c, "true, false, true");
    }
}
