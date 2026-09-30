import java.util.concurrent.atomic.AtomicReference;

// The token bucket without a lock. Both numbers live in one immutable State, and a request
// swaps in the next State with compareAndSet: if another thread swapped first, the request
// reads the new State and does its sums again. No thread ever waits for another, but a thread
// may redo its sums many times. Whether that beats the lock depends on the machine and the
// contention: measure it (LockFreeDemo prints both).
class AtomicTokenBucket implements Bucket {
    private record State(double tokens, long lastRefillMillis) { }

    private final int capacity;
    private final double millisPerToken;
    private final AtomicReference<State> state;

    AtomicTokenBucket(Limit limit, long nowMillis) {
        this.capacity = limit.capacity();
        this.millisPerToken = limit.millisPerToken();
        this.state = new AtomicReference<>(new State(capacity, nowMillis));
    }

    @Override
    public Decision tryConsume(int cost, long nowMillis) {
        while (true) {
            State seen = state.get();                    // what this thread read
            State now = refilled(seen, nowMillis);       // plus what time has earned since
            if (cost > capacity) {
                return Decision.never((long) now.tokens());
            }
            if (now.tokens() < cost) {                   // refused: nothing to write
                long wait = (long) Math.ceil((cost - now.tokens()) * millisPerToken);
                return Decision.deny((long) now.tokens(), wait);
            }
            State next = new State(now.tokens() - cost, now.lastRefillMillis());
            // Write only if the state is still the one we read. If another thread got there
            // first, loop: read its state and do the sums again.
            if (state.compareAndSet(seen, next)) {
                return Decision.allow((long) next.tokens());
            }
        }
    }

    // updateAndGet runs the same compare-and-set loop for us. The function may run more than
    // once, so it must only compute, never change anything else.
    @Override
    public void refund(int cost, long nowMillis) {
        state.updateAndGet(s -> {
            State r = refilled(s, nowMillis);
            return new State(Math.min(capacity, r.tokens() + cost), r.lastRefillMillis());
        });
    }

    @Override
    public boolean isIdle(long nowMillis) {
        return nowMillis - state.get().lastRefillMillis() >= capacity * millisPerToken;
    }

    private State refilled(State s, long nowMillis) {
        long elapsed = nowMillis - s.lastRefillMillis();
        if (elapsed <= 0) {
            return s;
        }
        return new State(Math.min(capacity, s.tokens() + elapsed / millisPerToken), nowMillis);
    }
}
