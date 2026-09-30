// The token bucket on its own: score-widget's bucket (5 a second), driven by times we pick by
// hand. It needs no clock and no limiter: a bucket is simply told the time.
public class BucketDemo {
    public static void main(String[] args) {
        Bucket widget = new TokenBucket(Limit.perSecond(5), 0);
        for (int i = 1; i <= 6; i++) {
            Decision d = widget.tryConsume(1, 0);
            System.out.println("   0 ms  request " + i + "  " + Check.show(d));
        }
        System.out.println(" 120 ms  request 7  " + Check.show(widget.tryConsume(1, 120)));
        System.out.println(" 200 ms  request 8  " + Check.show(widget.tryConsume(1, 200)));
        int allowed = 0;
        for (int i = 0; i < 7; i++) {
            if (widget.tryConsume(1, 2_200).allowed()) {
                allowed++;
            }
        }
        System.out.println("2200 ms  7 at once  " + allowed + " allowed, " + (7 - allowed)
                + " refused");
    }
}
