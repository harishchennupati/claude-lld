// Everything the front door knows about one request. A limit can depend on any of it: who the
// customer is, where the request comes from, and which endpoint it calls.
record Request(String customerId,   // from the API key; null before sign-in (no key yet)
               String ip,           // the caller's address: the only identity before sign-in
               String endpoint) {   // "/scores", "/search", "/login" ...

    boolean isCustomer() {
        return customerId != null;
    }
}
