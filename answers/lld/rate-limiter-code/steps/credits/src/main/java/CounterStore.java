// Where counters live. In memory on one server today; on Redis when many servers must share one
// budget. The limiter only ever sees this interface, so that change never reaches it.
interface CounterStore {
    // The counter for this key, created on the key's first request.
    Counter counterFor(String key, Limit limit, Algorithm algorithm, long nowMillis);
}
