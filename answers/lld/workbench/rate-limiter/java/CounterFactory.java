// Makes a new counter for an algorithm (the Factory pattern): the one place that knows which class
// counts which way. A new algorithm is a new class and one new line here.
final class CounterFactory {
    static Counter create(Algorithm algorithm, Limit limit, long nowMillis) {
        return switch (algorithm) {
            case TOKEN_BUCKET -> new TokenBucket(limit, nowMillis);
            case FIXED_WINDOW -> new FixedWindowCounter(limit, nowMillis);
            case SLIDING_WINDOW_LOG -> new SlidingWindowLog(limit);
            //@ from windows
            case SLIDING_WINDOW_COUNTER -> new SlidingWindowCounter(limit, nowMillis);
            //@ end
            //@ from credits
            case CREDITS -> new CreditWindow(limit, limit.requests(), nowMillis);
            //@ end
        };
    }
}
