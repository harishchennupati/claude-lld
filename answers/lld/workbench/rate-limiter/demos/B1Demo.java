// Step 1 on its own: two records and an interface, and nothing else yet.
public class B1Demo {
    public static void main(String[] args) {
        Limit free = Limit.perSecond(5);
        System.out.println(free);                                   // a record writes toString for you
        System.out.println(free.millisPerToken() + " ms per token");
        System.out.println(Decision.allow(4));
        System.out.println(Decision.deny(200));
        try {
            new Limit(0, 1_000);
        } catch (IllegalArgumentException e) {
            System.out.println("new Limit(0, 1_000) -> " + e.getMessage());
        }
    }
}
