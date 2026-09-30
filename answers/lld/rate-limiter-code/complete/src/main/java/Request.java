// One request as the rules see it: who sent it, which endpoint it is for, and what it costs.
record Request(String clientId, String endpoint, int cost) {
    static Request of(String clientId, String endpoint) {
        return new Request(clientId, endpoint, 1);
    }
}
