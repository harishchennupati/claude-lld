// The numbers behind the questions in Check yourself.
public class QuizDemo {
    public static void main(String[] args) {
        Counter widget = new TokenBucket(Limit.perSecond(5), 0);
        for (int i = 0; i < 5; i++) {
            widget.tryAcquire(0);
        }
        StringBuilder a = new StringBuilder("450 ms:");
        for (int i = 0; i < 3; i++) {
            a.append("  ").append(Check.show(widget.tryAcquire(450)));
        }
        System.out.println(a);
        Counter fantasy = new TokenBucket(Limit.perSecond(50), 0);
        fantasy.tryAcquire(0);
        int passed = 0;
        for (int i = 0; i < 60; i++) {
            if (fantasy.tryAcquire(10_000).allowed()) {
                passed++;
            }
        }
        System.out.println("quiet 10 s, then 60 at once: " + passed + " pass");
        Check.that(passed == 50, "capped at 50");
    }
}
