// One rule from the config: what it covers, whose budget it spends, how much, how it counts.
// Built once at startup and never changed, so every thread reads it without a lock.
record RateLimitRule(String name,
                     String endpoint,           // null: every endpoint
                     boolean needsApiKey,       // only requests from signed-in customers
                     CountPer countPer,         // whose budget
                     LimitPolicy limits,        // how much
                     Algorithm algorithm) {     // how it counts

    boolean covers(Request request) {
        if (needsApiKey && !request.hasApiKey()) {
            return false;
        }
        return endpoint == null || endpoint.equals(request.endpoint());
    }

    // The counter's key: this rule, and whose budget. "rate:fantasy-app", "login:203.0.113.7".
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
