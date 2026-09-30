// One incoming request, as the limiter sees it: who sent it, from where, to which endpoint, and
// what it costs. Built by the API filter from the HTTP request, before any real work.
//   clientId  the API key's owner: "fantasy-app"; ANONYMOUS when there is no key (a sign-in)
//   ip        where it came from: the only identity an anonymous request has
//   endpoint  "/scores", "/search", "/login"
//   cost      tokens it spends: 1 for most calls, more for heavy ones (a whole match's history)
record RequestContext(String clientId, String ip, String endpoint, int cost) {
    static final String ANONYMOUS = "anonymous";

    static RequestContext of(String clientId, String ip, String endpoint) {
        return new RequestContext(clientId, ip, endpoint, 1);
    }

    boolean hasKey() {
        return !ANONYMOUS.equals(clientId);
    }
}
