// Everything the front door knows about one request: who the customer is, where the
// request comes from, and which endpoint it calls. A limit can depend on any of it.
// Why a record: it is plain data that never changes on its way through, so any thread can read
// it safely, and Java writes the constructor, getters and equals for us.
record Request(String customerId,   // from the API key; null before sign-in (no key yet)
               String ip,           // the caller's address: the only identity before sign-in
               String endpoint) {   // "/scores", "/search", "/login" ...

    boolean isCustomer() {
        return customerId != null;
    }
}
