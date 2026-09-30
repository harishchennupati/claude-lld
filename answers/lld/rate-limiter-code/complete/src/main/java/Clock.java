// Where "now" comes from. The limiter is handed one, so a test can control time.
interface Clock {
    long nowMillis();
}
