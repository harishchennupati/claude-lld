//@ file from f1
import java.util.ArrayDeque;

// Exact: never more than `limit` requests in ANY window of `periodMillis`. It keeps the time
// of every allowed request, oldest first. Logins, 5 a minute: after 5 attempts at 0 s, the 6th
// must wait until 60 s, whatever happens in between.
class SlidingWindowLog implements Bucket {
    private final int limit;
    private final long periodMillis;
    private final ArrayDeque<Long> times = new ArrayDeque<>();   // oldest first; both ends O(1)

    SlidingWindowLog(Limit limit, long nowMillis) {              // an empty log needs no start time
        this.limit = limit.capacity();
        this.periodMillis = limit.periodMillis();
    }

    @Override
    //@ until f3
    public synchronized Decision tryConsume(long nowMillis) {
        dropExpired(nowMillis);
        if (times.size() < limit) {
            times.addLast(nowMillis);
            return Decision.allow(limit - times.size());
        }
        // Full. A place opens when the oldest request leaves the window.
        return Decision.deny(times.peekFirst() + periodMillis - nowMillis);
    }
    //@ end
    //@ from f3
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        dropExpired(nowMillis);
        if (cost > limit) {
            return Decision.never(limit - times.size());
        }
        if (times.size() + cost <= limit) {
            for (int i = 0; i < cost; i++) {
                times.addLast(nowMillis);                        // one entry per token spent
            }
            return Decision.allow(limit - times.size());
        }
        // Full. `cost` places open when enough of the oldest entries have left the window:
        // with 5 entries and a cost of 2, the 2nd-oldest must leave.
        long mustLeave = times.size() + cost - limit;
        long leavesAt = 0;
        int seen = 0;
        for (long t : times) {
            if (++seen == mustLeave) {
                leavesAt = t + periodMillis;
                break;
            }
        }
        return Decision.deny(limit - times.size(), leavesAt - nowMillis);
    }
    //@ end
    //@ from f4

    // Remove this request's entries: the newest ones, which it has just added.
    @Override
    public synchronized void refund(int cost, long nowMillis) {
        for (int i = 0; i < cost && !times.isEmpty(); i++) {
            times.pollLast();
        }
    }
    //@ end
    //@ from f6

    // Idle once even the newest entry has left the window: the log is as empty as a new one.
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        return times.isEmpty() || times.peekLast() <= nowMillis - periodMillis;
    }
    //@ end

    // Forget the entries that have left the window: at 60,000 ms, anything at 0 ms or earlier.
    private void dropExpired(long nowMillis) {
        while (!times.isEmpty() && times.peekFirst() <= nowMillis - periodMillis) {
            times.pollFirst();
        }
    }
}
