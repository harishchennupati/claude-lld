import java.util.ArrayDeque;
import java.util.Deque;

// The sliding window log: the time of every allowed request in the last period. "The last
// minute" moves with now, so it is exact: never more than the limit in ANY minute. The price is
// one timestamp per request, so it is for small limits that must be exact, such as sign-ins.
class SlidingWindowLog implements Counter {
    private final int limit;
    private final long periodMillis;
    private final Deque<Long> times = new ArrayDeque<>();    // oldest first

    SlidingWindowLog(Limit limit) {
        this.limit = limit.requests();
        this.periodMillis = limit.periodMillis();
    }

    @Override
    public synchronized Decision tryAcquire(long nowMillis) {
        // Forget the requests that are no longer inside the last period.
        while (!times.isEmpty() && times.peekFirst() <= nowMillis - periodMillis) {
            times.pollFirst();
        }
        if (times.size() < limit) {
            times.addLast(nowMillis);
            return Decision.allow();
        }
        // Full: there is room again when the oldest request leaves the window.
        return Decision.deny(times.peekFirst() + periodMillis - nowMillis);
    }

    @Override
    public synchronized void refund(long nowMillis) {
        times.pollLast();                    // remove the newest entry: the count is right again
    }
}
