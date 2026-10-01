import java.util.ArrayDeque;
import java.util.Deque;

// The time of every allowed request in the last period: exact, never more than the limit in ANY
// period. One timestamp per request, so it is for small limits such as sign-ins.
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
        while (!times.isEmpty() && times.peekFirst() <= nowMillis - periodMillis) {
            times.pollFirst();               // out of the last period: forget it
        }
        if (times.size() < limit) {
            times.addLast(nowMillis);
            return Decision.allow();
        }
        return Decision.deny(times.peekFirst() + periodMillis - nowMillis);   // oldest leaves
    }

    @Override
    public synchronized void refund(long nowMillis) {
        times.pollLast();                    // forget the newest entry: the count is right
    }
    //@ from idle

    @Override
    public synchronized boolean isIdle(long nowMillis) {
        return times.isEmpty() || times.peekLast() <= nowMillis - periodMillis;
    }
    //@ end
}
