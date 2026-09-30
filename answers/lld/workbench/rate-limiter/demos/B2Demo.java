// Step 2 on its own: a manual clock moves only when told to.
public class B2Demo {
    public static void main(String[] args) {
        ManualClock clock = new ManualClock(0);
        System.out.println("start          " + clock.nowMillis() + " ms");
        clock.advance(120);
        System.out.println("advance(120)   " + clock.nowMillis() + " ms");
        clock.advance(80);
        System.out.println("advance(80)    " + clock.nowMillis() + " ms");
    }
}
