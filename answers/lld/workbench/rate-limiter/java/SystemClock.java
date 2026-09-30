// Production time. nanoTime only moves forward. The wall clock (currentTimeMillis) can jump
// back when the machine corrects its time, and a bucket must never see time go backwards.
class SystemClock implements Clock {
    @Override
    public long nowMillis() {
        // nanoTime's zero means nothing, which is fine: we only ever subtract two readings.
        return System.nanoTime() / 1_000_000;
    }
}
