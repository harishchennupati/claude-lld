// Which limit applies to a key. One method, so how limits are chosen (one for everyone, per
// customer, by plan) can change without the limiter knowing.
interface LimitPolicy {
    Limit limitFor(String key);
}
