//@ file from door
// What the door knows about a request. customerId is null before sign-in.
record Request(String customerId, String ip, String endpoint) {
}
