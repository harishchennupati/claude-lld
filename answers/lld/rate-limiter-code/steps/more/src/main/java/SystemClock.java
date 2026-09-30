// Production time: the wall clock, because the daily quota starts again at midnight. It can
// jump when the machine corrects its time; the buckets tolerate that (see TokenBucket.refill).
class SystemClock implements Clock {
    @Override
    public long nowMillis() {
        return System.currentTimeMillis();
    }
}
