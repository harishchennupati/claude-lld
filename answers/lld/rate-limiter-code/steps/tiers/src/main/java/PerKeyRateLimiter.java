// One counter per key. Answers the question by asking three others: how much may this key do,
// what has it done so far, and what time is it. It keeps no state of its own, so it needs no lock.
class PerKeyRateLimiter implements RateLimiter {
    private final LimitPolicy limits;      // how much
    private final CounterStore counters;   // what has been done
    private final Clock clock;             // when

    // Handed in, not created here: tests pass a clock they move by hand, and many servers
    // pass a store on Redis. This class never changes for either.
    PerKeyRateLimiter(LimitPolicy limits, CounterStore counters, Clock clock) {
        this.limits = limits;
        this.counters = counters;
        this.clock = clock;
    }

    @Override
    public Decision check(String key) {
        long now = clock.nowMillis();
        Limit limit = limits.limitFor(key);
        Counter counter = counters.counterFor(key, limit, now);
        return counter.tryAcquire(now);
    }
}
