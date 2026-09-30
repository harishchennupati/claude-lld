// Test time: it moves only when the test says so. advance(200) means "200 ms later", instantly,
// so no test ever sleeps and every run gives the same answer.
class ManualClock implements Clock {
    private volatile long now;   // volatile: other threads see every move the test makes

    ManualClock(long startMillis) {
        now = startMillis;
    }

    @Override
    public long nowMillis() {
        return now;
    }

    // Only the test's own thread calls this. `now += millis` is a read and then a write, not
    // one atomic step, so if several threads moved time at once this would need an AtomicLong.
    void advance(long millis) {
        now += millis;
    }
}
