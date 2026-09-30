// The first build step on its own: the values, and a bad request refused at the door.
public class AnswerDemo {
    public static void main(String[] args) {
        Limit free = Limit.perSecond(5);
        System.out.println(free + " -> " + free.millisPerToken() + " ms per token");
        System.out.println(RequestContext.of("fantasy-app", "203.0.113.7", "/scores"));
        System.out.println(Decision.allow(4) + "  |  " + Decision.deny(0, 200));
        System.out.println(RateLimitResult.refused(Decision.deny(0, 200), "plan"));
        try {
            new RequestContext("fantasy-app", "203.0.113.7", "/scores", 0);
        } catch (IllegalArgumentException e) {
            System.out.println("cost 0 -> " + e.getMessage());
        }
    }
}
