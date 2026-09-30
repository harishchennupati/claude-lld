// Step 4 on its own: which limit each client gets, and a factory that makes its bucket.
public class B4Demo {
    public static void main(String[] args) {
        Plans plans = new Plans(Limit.perSecond(5), Limit.perSecond(50));
        plans.assign("fantasy-app", Plan.PRO);
        System.out.println("fantasy-app    " + plans.limitFor("fantasy-app"));
        System.out.println("score-widget   " + plans.limitFor("score-widget") + "  (not assigned)");

        BucketFactory factory = TokenBucket::new;         // a constructor, passed as a value
        Bucket bucket = factory.create(plans.limitFor("fantasy-app"), 0);
        System.out.println("fantasy-app's first request: " + bucket.tryConsume(0));
    }
}
