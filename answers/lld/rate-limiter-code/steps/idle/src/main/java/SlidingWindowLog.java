import java.util.ArrayDeque;

// Exact: never more than `limit` requests in ANY window of `periodMillis`. It keeps the time of
// every allowed request, oldest first. Logins, 5 a minute per IP: after 5 attempts at 0 s, the
// 6th must wait until 60 s, whatever happens in between. The price is one entry per request.
class SlidingWindowLog implements Bucket {
    private final int limit;
    private final long periodMillis;
    private final ArrayDeque<Long> times = new ArrayDeque<>();   // oldest first; both ends O(1)

    SlidingWindowLog(Limit limit, long nowMillis) {              // an empty log needs no start time
        this.limit = limit.capacity();
        this.periodMillis = limit.periodMillis();
    }

    @Override
    public synchronized Decision tryConsume(int cost, long nowMillis) {
        dropExpired(nowMillis);
        if (times.size() + cost <= limit) {
            for (int i = 0; i < cost; i++) {
                times.addLast(nowMillis);                        // one entry per token spent
            }
            return Decision.allow(limit - times.size());
        }
        // Full. For a cost of 1 the wait is simply: times.peekFirst() + periodMillis - nowMillis
        // (enough in the room). For any cost: with 5 entries and a cost of 2, the 2nd-oldest
        // entry must leave the window first.
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

    // Remove this request's own entries (they carry its time), not whoever came last.
    @Override
    public synchronized void refund(int cost, long nowMillis) {
        for (int i = 0; i < cost; i++) {
            times.removeLastOccurrence(nowMillis);
        }
    }

    // Idle once even the newest entry has left the window: as empty as a new log.
    @Override
    public synchronized boolean isIdle(long nowMillis) {
        return times.isEmpty() || times.peekLast() <= nowMillis - periodMillis;
    }

    // Forget the entries that have left the window: at 60,000 ms, anything at 0 ms or earlier.
    private void dropExpired(long nowMillis) {
        while (!times.isEmpty() && times.peekFirst() <= nowMillis - periodMillis) {
            times.pollFirst();
        }
    }
}
