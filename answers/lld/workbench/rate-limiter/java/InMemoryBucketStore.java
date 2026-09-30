//@ from idle
import java.util.Map;
//@ end
import java.util.concurrent.ConcurrentHashMap;
//@ from idle
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
//@ end

// This server's buckets, in one map shared by every request thread.
class InMemoryBucketStore implements BucketStore {
    private final ConcurrentHashMap<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    public Bucket bucketFor(String key, BucketFactory factory, Limit limit, long nowMillis) {
        // Find-or-create as ONE atomic step, so two threads that meet a new key at the same
        // moment still get the same bucket. The factory runs only for a new key.
        return buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));
    }

    //@ from idle

    // Forgets every bucket that a new one would replace exactly. A timer runs this, never a
    // request. Walking a ConcurrentHashMap while other threads change it is safe.
    int evictIdle(long nowMillis) {
        int removed = 0;
        for (Map.Entry<String, Bucket> e : buckets.entrySet()) {
            Bucket bucket = e.getValue();
            // remove(key, value) removes the entry only if the map still holds this same bucket.
            if (bucket.isIdle(nowMillis) && buckets.remove(e.getKey(), bucket)) {
                removed++;
            }
        }
        return removed;
    }

    // Runs the sweep every `periodMillis` on the timer's own thread. A task that throws would
    // silently stop a scheduled timer, so nothing escapes it.
    ScheduledFuture<?> sweepEvery(long periodMillis, Clock clock, ScheduledExecutorService timer) {
        return timer.scheduleAtFixedRate(() -> {
            try {
                evictIdle(clock.nowMillis());
            } catch (RuntimeException e) {
                // In production: log it. The next sweep runs anyway.
            }
        }, periodMillis, periodMillis, TimeUnit.MILLISECONDS);
    }

    int size() {                               // for the demo: how many buckets are kept
        return buckets.size();
    }
    //@ end
}
