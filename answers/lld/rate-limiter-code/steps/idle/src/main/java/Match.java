// Which requests a rule applies to: the kind of caller, and an endpoint (or every endpoint).
// The "match:" line of the config, as a value.
record Match(Caller caller, String endpoint) {
    static final String ANY_ENDPOINT = "*";

    boolean matches(Request request) {
        if (caller == Caller.CUSTOMER && !request.isCustomer()) {
            return false;                    // a customer-only rule ignores anonymous requests
        }
        return endpoint.equals(ANY_ENDPOINT) || endpoint.equals(request.endpoint());
    }
}
