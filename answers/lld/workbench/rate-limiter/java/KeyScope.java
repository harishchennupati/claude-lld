import java.util.function.Function;

// What a rule counts by: whose budget a request spends.
enum KeyScope {
    CLIENT(RequestContext::clientId),                               // "fantasy-app"
    IP(RequestContext::ip),                                         // "203.0.113.7": logins
    CLIENT_AND_ENDPOINT(r -> r.clientId() + " " + r.endpoint()),    // "fantasy-app /search"
    EVERYONE(r -> "*");                                             // one budget for the API

    private final Function<RequestContext, String> key;

    KeyScope(Function<RequestContext, String> key) {
        this.key = key;
    }

    String keyOf(RequestContext request) {
        return key.apply(request);
    }
}
