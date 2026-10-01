// Where counters live: in memory on one server today, on Redis when many servers must share
// one budget.
// Why an interface: the limiter only ever sees this promise, so that change never reaches it.
interface CounterStore {
    // The counter for this key, created on the key's first request.
    Counter counterFor(String key, Limit limit, Algorithm algorithm, long nowMillis);
}
