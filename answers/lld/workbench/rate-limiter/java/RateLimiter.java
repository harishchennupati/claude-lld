// The one question the API asks before it does any work for a request.
// The API depends on this interface, never on a class behind it.
interface RateLimiter {
    //@ until f3
    Decision tryAcquire(String clientId);
    //@ end
    //@ from f3
    // `cost` tokens for this request: 1 for a live score, 5 for a whole match's history.
    Decision tryAcquire(String clientId, int cost);

    // Every caller written before costs existed keeps working: an ordinary request costs 1.
    default Decision tryAcquire(String clientId) {
        return tryAcquire(clientId, 1);
    }
    //@ end
}
