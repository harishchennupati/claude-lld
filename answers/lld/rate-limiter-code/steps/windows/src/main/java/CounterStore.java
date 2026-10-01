// Where counters live. In memory on one server; on Redis when many servers share one budget.
interface CounterStore {
    // The counter for this key, made on the key's first request.
    Counter counterFor(String key, Limit limit, long nowMillis);
}
