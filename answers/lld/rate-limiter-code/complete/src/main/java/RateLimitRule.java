// One rule from the config: which requests it matches, whose budget they spend, how much is
// allowed, and how the requests are counted. Built once at startup and never changed, so every
// request thread reads it without a lock.
record RateLimitRule(String name,
                     Match match,              // which requests
                     CountPer countPer,        // whose budget
                     LimitPolicy limits,       // how much
                     Algorithm algorithm) {    // how they are counted

    boolean matches(Request request) {
        return match.matches(request);
    }

    // The key of this rule's counter for this request: the rule's name, then whose budget it is.
    // "rate:fantasy-app", "login:203.0.113.7", "search:fantasy-app:/search", "global:*".
    String keyFor(Request request) {
        String who = switch (countPer) {
            case CUSTOMER -> request.customerId();
            case IP -> request.ip();
            case CUSTOMER_AND_ENDPOINT -> request.customerId() + ":" + request.endpoint();
            case EVERYONE -> "*";
        };
        return name + ":" + who;
    }
}
