// Production time: the wall clock, because the daily quota must start again at midnight, and a
// monotonic clock (nanoTime) knows nothing about midnight. The wall clock can jump when the
// machine corrects its time. A jump back freezes refills until the clock catches up (stricter).
// A jump forward refills early, at most one burst per key. Both bounded; neither breaks a count.
class SystemClock implements Clock {
    @Override
    public long nowMillis() {
        return System.currentTimeMillis();
    }
}
