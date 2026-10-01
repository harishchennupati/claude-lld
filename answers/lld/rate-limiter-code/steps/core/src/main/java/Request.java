// What the front door knows about a request. customerId is null before sign-in (no API key yet).
record Request(String customerId, String ip, String endpoint) {
    boolean hasApiKey() {
        return customerId != null;
    }
}
