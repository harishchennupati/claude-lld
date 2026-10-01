// Which requests a rule applies to: the kind of caller, and an endpoint (or every endpoint).
// Why a record: it is the config's "match:" line, two values, plus one method that compares them
// with a request.
record Match(Caller caller, String endpoint) {
    static final String ANY_ENDPOINT = "*";

    boolean matches(Request request) {
        if (caller == Caller.CUSTOMER && !request.isCustomer()) {
            return false;                    // a customer-only rule ignores anonymous requests
        }
        return endpoint.equals(ANY_ENDPOINT) || endpoint.equals(request.endpoint());
    }
}
