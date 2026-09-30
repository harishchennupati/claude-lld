// The one question the API asks before it does any work for a request.
// The API depends on this interface, never on a class behind it.
interface RateLimiter {
    Decision tryAcquire(String clientId);
}
