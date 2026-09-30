import java.util.function.Predicate;

// One limit, on one kind of request, counted by one kind of key, in one way.
//   name       shown when this rule refuses; part of every bucket key the rule makes
//   appliesTo  which requests it covers: all of them, or only "/search"
//   scope      whose budget a request spends: the client's, the IP's, everyone's
//   limits     how much: fixed, or by the client's plan
//   algorithm  how to count
record RateLimitRule(String name, Predicate<RequestContext> appliesTo, KeyScope scope,
                     LimitPolicy limits, Algorithm algorithm) {
    static Predicate<RequestContext> everyRequest() {
        return request -> true;
    }

    static Predicate<RequestContext> withKey() {
        return RequestContext::hasKey;
    }

    static Predicate<RequestContext> endpoint(String path) {
        return request -> request.endpoint().equals(path);
    }
}
