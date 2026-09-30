import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: shed load instead of stalling -- the rule changes mid-round, and only the rule changes
/**
 * "The source is a live market feed. It must never stall." Blocking is suddenly the wrong answer, so the full
 * buffer decision changes -- and because it was already one method behind an interface, the buffer, the producer,
 * the consumer and the shutdown protocol are untouched. Newest loss: the arriving item is thrown away.
 */
final class DropNewest implements OverflowPolicy {
    @Override public boolean submit(Handoff h, Task t, Metrics m, PipelineListener out) {
        if (h.offer(t)) return true;
        out.onEvent("DROPPED", "buffer full, discarded the arriving " + t);
        return false;                                        // false means "shed": the producer counts it as dropped
    }
}

/**
 * Oldest loss: keep the freshest window of work, which is what a dashboard or a live price feed wants. On the
 * hand-built buffers this is ONE step under the lock, so the bound can never be exceeded even for an instant.
 */
final class DropOldest implements OverflowPolicy {
    @Override public boolean submit(Handoff h, Task t, Metrics m, PipelineListener out) {
        Task evicted = h.putEvictingOldest(t);
        if (evicted != null) {
            // the evicted item is the loss, not the new one, and it is counted apart from a shed-on-arrival drop
            m.evicted.incrementAndGet();
            out.onEvent("DROPPED", "evicted the stale " + evicted + " to make room for " + t);
        }
        return true;
    }
}

// ---- ext: a producer that must not wait forever -- a deadline, and awaitNanos underneath
/**
 * Waiting is fine; waiting without a bound is not, because it turns one slow consumer into a stuck request
 * thread. The timed put re-arms its deadline from awaitNanos's return value, so a spurious wake-up cannot
 * silently extend the wait. false is returned on expiry, and the producer already treats false as a drop.
 */
final class TimedBlock implements OverflowPolicy {
    private final long deadlineMs;
    TimedBlock(long deadlineMs) { this.deadlineMs = deadlineMs; }
    @Override public boolean submit(Handoff h, Task t, Metrics m, PipelineListener out) throws InterruptedException {
        if (h.offer(t)) return true;
        m.backpressured.incrementAndGet();
        long t0 = System.nanoTime();
        boolean in = h.put(t, deadlineMs);
        m.blockedNanos.addAndGet(System.nanoTime() - t0);
        if (!in) out.onEvent("DROPPED", t + " gave up after " + deadlineMs + " ms of back-pressure");
        return in;
    }
}

// ---- ext: a task that keeps failing -- retry a few times, then park it, never lose it
/**
 * A Decorator on the work, not a change to the consumer: try the real work up to attempts times, and let the
 * last failure escape so the failure policy parks it. The consumer, the buffer and the policy never change.
 */
final class RetryingWork implements Work {
    private final Work base;
    private final int attempts;
    private final AtomicInteger retries = new AtomicInteger();
    RetryingWork(Work base, int attempts) { this.base = base; this.attempts = attempts; }
    @Override public void process(Task t) throws InterruptedException {
        RuntimeException last = null;
        for (int i = 0; i < attempts; i++) {
            try { base.process(t); return; }
            catch (RuntimeException e) { last = e; retries.incrementAndGet(); }
        }
        throw last;                                          // AccountedWork turns this into a dead-letter
    }
    int retries() { return retries.get(); }
}

/**
 * A dead-letter sink that is itself a bounded buffer, so a storm of failures cannot become an out-of-memory
 * crash either: the same reasoning that bounded the main hand-off bounds the failure path.
 */
final class BoundedDeadLetters implements FailurePolicy {
    private final Handoff parked;
    private final AtomicInteger overflowed = new AtomicInteger();
    BoundedDeadLetters(int capacity) { parked = new LockHandoff(capacity); }
    @Override public void onFailed(Task t, RuntimeException cause, Metrics m) {
        m.deadLettered.incrementAndGet();
        if (!parked.offer(t)) overflowed.incrementAndGet();   // never block a consumer on the failure path
    }
    int size() { return parked.size(); }
    int overflowed() { return overflowed.get(); }
}

// ---- ext: the other shutdown -- a stop flag with a drain, and the version that strands items
/**
 * The alternative to poison pills. The flag must mean "every producer has been JOINED", not "producers were
 * asked to stop": a consumer exits only when the flag is set AND a timed poll comes back empty, which is only
 * safe if nothing can add after the flag. Cost: up to one poll timeout of extra latency on the way out.
 * Benefit: no pills to count, and it works when consumers outnumber the pills you can afford to inject.
 */
final class DrainingConsumer implements Runnable {
    private final Handoff h;
    private final AtomicBoolean producersJoined;
    private final Work work;
    private final long pollMs;
    DrainingConsumer(Handoff h, AtomicBoolean producersJoined, Work work, long pollMs) {
        this.h = h; this.producersJoined = producersJoined; this.work = work; this.pollMs = pollMs;
    }
    @Override public void run() {
        try {
            for (;;) {
                Task t = h.poll(pollMs);
                if (t == null) { if (producersJoined.get()) return; continue; }   // empty AND nothing can arrive
                work.process(t);
            }
        } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}

/**
 * The junior version, kept here to be measured rather than argued about: it checks the flag FIRST and exits,
 * so whatever is still in the buffer is stranded. The test counts exactly how many items it abandons.
 */
final class NaiveStopConsumer implements Runnable {
    private final Handoff h;
    private final AtomicBoolean stop;
    private final Work work;
    NaiveStopConsumer(Handoff h, AtomicBoolean stop, Work work) { this.h = h; this.stop = stop; this.work = work; }
    @Override public void run() {
        try {
            while (!stop.get()) {
                Task t = h.poll(5);
                if (t != null) work.process(t);
            }
        } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}

// ---- ext: the lost wakeup -- the bug that only happens when you check the guard outside the lock
/**
 * The classic threading bug, written down so it can be measured instead of argued about. This buffer reads the
 * guard ("is it empty?") with NO lock held and only then takes the monitor to wait. A producer that adds an item
 * and calls notify() in that gap signals an empty wait set: nobody is waiting yet, so the signal is thrown away,
 * and the consumer then goes to sleep on top of an item that is already sitting in the buffer. That is a lost
 * wakeup. With a plain wait() it sleeps forever; with wait(ms) it wastes the whole timeout. The rule that kills
 * it is one line long: read the guard, decide, and wait while HOLDING the same lock the signaller holds.
 * The two latches exist only so a test can land the signal exactly in the gap and get the same answer every run.
 */
final class LostWakeupHandoff {
    private final ArrayDeque<Task> q = new ArrayDeque<>();
    /** Counted down after the guard is read and before the wait, so a test knows when the gap is open. */
    final CountDownLatch guardRead = new CountDownLatch(1);
    /** The test opens this once it has added an item and signalled, so the wait happens AFTER the signal. */
    final CountDownLatch signalSent = new CountDownLatch(1);

    /** A correct put: it holds the monitor and signals under it. It is the take that is broken. */
    void put(Task t) { synchronized (this) { q.addLast(t); notify(); } }

    /** The broken take. Step 1 reads the guard outside the lock, so the answer is stale by step 3. */
    Task takeLosingWakeups(long waitMs) throws InterruptedException {
        boolean empty;
        synchronized (this) { empty = q.isEmpty(); }      // 1. the guard is read, and the lock is RELEASED
        guardRead.countDown();
        signalSent.await(3, TimeUnit.SECONDS);            // 2. the put and the notify land in this gap
        synchronized (this) {
            if (empty) wait(waitMs);                      // 3. sleeps, although the item is already here
            return q.pollFirst();
        }
    }
    int size() { synchronized (this) { return q.size(); } }
}

// ---- ext: what java.util.concurrent already gives you -- the same design, already written
/**
 * Hand the buffer to the JDK. ArrayBlockingQueue is the main file's LockHandoff, written by the people
 * who maintain the runtime -- same array ring, same lock, same two Conditions. What you give up is a multi-step
 * operation of your own: eviction here is two calls with a lock of ours around them, and a concurrent take
 * between them can make it drop an item it did not have to. Own the lock, or accept that.
 */
final class JucHandoff implements Handoff {
    private final ArrayBlockingQueue<Task> q;
    private final ReentrantLock evictLock = new ReentrantLock();
    private final int cap;
    JucHandoff(int capacity) { cap = capacity; q = new ArrayBlockingQueue<>(capacity); }
    @Override public void put(Task t) throws InterruptedException { q.put(t); }
    @Override public boolean put(Task t, long timeoutMs) throws InterruptedException { return q.offer(t, timeoutMs, TimeUnit.MILLISECONDS); }
    @Override public boolean offer(Task t) { return q.offer(t); }
    @Override public Task take() throws InterruptedException { return q.take(); }
    @Override public Task poll(long timeoutMs) throws InterruptedException { return q.poll(timeoutMs, TimeUnit.MILLISECONDS); }
    @Override public Task putEvictingOldest(Task t) {
        evictLock.lock();
        try {
            if (q.offer(t)) return null;
            Task evicted = q.poll();
            q.offer(t);
            return evicted;
        } finally { evictLock.unlock(); }
    }
    @Override public int size() { return q.size(); }
    @Override public int capacity() { return cap; }
    @Override public String name() { return "java.util.concurrent.ArrayBlockingQueue"; }
}

/**
 * And the honest answer to "would you ship this?": no -- you would ship these fifteen lines. A ThreadPoolExecutor
 * with a BOUNDED queue is this whole page, assembled from the JDK. The mapping is one to one: the
 * ArrayBlockingQueue is the hand-off; the pool threads are the consumers; the RejectedExecutionHandler is the
 * OverflowPolicy (AbortPolicy throws, DiscardPolicy is DropNewest, DiscardOldestPolicy is DropOldest, and
 * CallerRunsPolicy is back-pressure -- the submitting thread runs the task itself and therefore stops producing
 * while it does); shutdown() plus awaitTermination() is the drained shutdown, and shutdownNow() is the stop-now
 * that hands back the work that never ran. What it does NOT give you is the ledger: no exactly-once counters, no
 * dead-letter queue, no depth metric. That is the part you still write, and it is the part this page is about.
 */
final class JdkPipeline {
    private final ThreadPoolExecutor pool;
    private final AtomicLong ran = new AtomicLong();
    JdkPipeline(int workers, int capacity) {
        pool = new ThreadPoolExecutor(workers, workers, 0L, TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(capacity), new ThreadPoolExecutor.CallerRunsPolicy());
    }
    /** Submitting IS the put: when the queue is full the caller runs the task, which is back-pressure. */
    void submit(Task t, Work work) {
        pool.execute(() -> {
            try { work.process(t); ran.incrementAndGet(); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
    }
    /** The drained stop: no new work is accepted, everything queued still runs. */
    boolean drainAndStop(long ms) throws InterruptedException { pool.shutdown(); return pool.awaitTermination(ms, TimeUnit.MILLISECONDS); }
    /** The stop-now: the tasks that never ran come back to the caller, exactly like Pipeline.shutdownNow(). */
    List<Runnable> stopNow() { return pool.shutdownNow(); }
    long ran() { return ran.get(); }
}

// ---- ext: what the lock actually costs -- the two numbers behind "one lock is not the bottleneck"
/**
 * Move 8 says the lock is not where the time goes. That is a claim, and a claim you have not run is an opinion,
 * so here are the two measurements behind it. First the floor: one thread alternating put and take on a buffer
 * of sixteen, warmed up so the JIT has compiled it. Nothing is contended, so what is left is the lock, the array
 * write, the index update and the signal -- and it comes out around nine nanoseconds for the pair. Second the
 * capacity ladder: one producer and one consumer pushing the same number of items through buffers of 1, 16 and
 * 1024. A buffer of one forces a park and a wake on nearly every item; a big buffer lets both sides run for long
 * stretches without meeting. The gap between the two is the real cost, and it is the park, not the lock. The
 * numbers move with the machine and the load; the ratio between them does not.
 */
final class HandoffCost {
    /** Nanoseconds for one put plus one take, single-threaded and uncontended: the floor the lock can reach. */
    static double uncontendedNanos(int iterations) throws InterruptedException {
        Handoff h = new LockHandoff(16);
        Task t = new Task(1, "x");
        for (int i = 0; i < 200_000; i++) { h.put(t); h.take(); }      // warm-up: let the JIT compile the loop
        long t0 = System.nanoTime();
        for (int i = 0; i < iterations; i++) { h.put(t); h.take(); }
        return (System.nanoTime() - t0) / (double) iterations;
    }

    /** Milliseconds to move `items` through a buffer of `capacity` with one producer and one consumer. */
    static long ladderMs(int capacity, int items) throws InterruptedException {
        Handoff h = new LockHandoff(capacity);
        Thread consumer = new Thread(() -> {
            try { for (;;) if (h.take() == Task.POISON) return; } catch (InterruptedException ignored) { }
        }, "ladder-consumer");
        consumer.start();
        Task t = new Task(1, "x");
        long t0 = System.nanoTime();
        for (int i = 0; i < items; i++) h.put(t);
        h.put(Task.POISON);                                            // the same stop signal, in band
        consumer.join();
        return (System.nanoTime() - t0) / 1_000_000L;
    }
}

// ---- ext: fairness and starvation -- measured, because "is it fair?" is a question about numbers
/**
 * Starvation is not a theory, it is a spread. N producers push through a buffer of ONE for a fixed window; the
 * probe returns how many items each of them got through. The answer surprises people, so measure before you
 * claim: the DEFAULT unfair lock comes out dead even here, a spread of 1.00. A producer that finds the buffer
 * full never fights for the lock at all -- it parks on the notFull Condition, and a Condition's wait set is
 * served first-in-first-out, so the order producers fell asleep in IS the order they are served in. Lock
 * fairness governs only threads arriving at lock() itself, which on this design is the instant after a
 * wake-up. So new ReentrantLock(true) does not buy the even counts -- it scatters them (spreads from 3x to
 * over 1000x, run to run) and pushes a fifth to a third fewer items through, because every hand-over becomes
 * a context switch. Correctness is identical either way. Fairness is a knob you turn on a measurement.
 */
final class FairnessProbe {
    /** Returns one count per producer: how many items each got through the buffer inside the window. */
    static long[] run(boolean fair, int producers, long windowMs) throws InterruptedException {
        Handoff h = new LockHandoff(1, fair);
        long[] counts = new long[producers];                  // index k is written only by producer k
        AtomicBoolean stop = new AtomicBoolean();
        CountDownLatch gate = new CountDownLatch(1);          // all producers start at the same instant
        Thread consumer = new Thread(() -> {
            try { for (;;) if (h.take() == Task.POISON) return; } catch (InterruptedException ignored) { }
        }, "probe-consumer");
        consumer.start();
        Thread[] ps = new Thread[producers];
        for (int i = 0; i < producers; i++) {
            final int k = i;
            ps[k] = new Thread(() -> {
                try { gate.await(); while (!stop.get()) { h.put(new Task(k, "probe")); counts[k]++; } }
                catch (InterruptedException ignored) { }
            }, "probe-producer-" + k);
        }
        for (Thread t : ps) t.start();
        gate.countDown();
        Thread.sleep(windowMs);
        stop.set(true);
        for (Thread t : ps) { t.join(2_000); t.interrupt(); }  // a producer parked on a full buffer is woken
        h.put(Task.POISON);
        consumer.join(2_000);
        return counts;
    }
    /** max / min: 1.0 is perfectly even, and a big number is the shape of starvation. */
    static double spread(long[] counts) {
        long min = Long.MAX_VALUE, max = 0;
        for (long c : counts) { min = Math.min(min, c); max = Math.max(max, c); }
        return min == 0 ? Double.POSITIVE_INFINITY : (double) max / min;
    }
}

// ---- ext: batching -- amortise the hand-off over many items
/**
 * One lock trip per item is the cost that actually shows up in a profile, not the lock itself. Take one item
 * with a wait, then sweep up whatever is already there without waiting: a burst becomes one batch. A real
 * implementation adds int drainTo(Collection, max) to the buffer and copies the whole ring under ONE lock --
 * that is what ArrayBlockingQueue.drainTo does, and it is why a batching consumer is worth writing.
 */
final class Batches {
    static List<Task> takeUpTo(Handoff h, int max, long waitMs) throws InterruptedException {
        List<Task> batch = new ArrayList<>(max);
        Task first = h.poll(waitMs);
        if (first == null) return batch;
        batch.add(first);
        while (batch.size() < max) {
            Task t = h.poll(0);
            if (t == null) break;
            batch.add(t);
        }
        return batch;
    }
}

// ---- ext: order per key -- one lane per key, so "same account, same order" survives many consumers
/**
 * One buffer with many consumers gives you no ordering at all: two tasks for the same account can be processed
 * in either order. Route by a hash of the key into N lanes, one consumer per lane, and order within a key is
 * restored without a global lock. The price is head-of-line blocking: one slow key stalls its whole lane.
 */
final class KeyedLanes {
    private final Handoff[] lanes;
    KeyedLanes(int laneCount, int capacityEach) {
        lanes = new Handoff[laneCount];
        for (int i = 0; i < laneCount; i++) lanes[i] = new LockHandoff(capacityEach);
    }
    /** The lane a key always lands in. Same key, same lane, same consumer, therefore same order. */
    Handoff laneFor(String key) { return lanes[Math.floorMod(key.hashCode(), lanes.length)]; }
    int laneCount() { return lanes.length; }
    Handoff lane(int i) { return lanes[i]; }
}

// ---- ext: many stages -- back-pressure composes backwards along the whole chain
/**
 * A consumer of one buffer is the producer of the next. The property that matters: if the LAST buffer fills,
 * its stage slows, which fills the buffer feeding it, which slows the stage before it, all the way back to the
 * source -- so the whole chain has bounded memory, with no coordination between stages. The pill travels too:
 * a stage that takes POISON passes one on before it exits, so one injection stops the entire chain in order.
 */
final class Stage implements Runnable {
    private final Handoff in, out;
    private final Work work;
    private final String name;
    Stage(String name, Handoff in, Handoff out, Work work) { this.name = name; this.in = in; this.out = out; this.work = work; }
    @Override public void run() {
        try {
            for (;;) {
                Task t = in.take();
                if (t == Task.POISON) { if (out != null) out.put(Task.POISON); return; }
                work.process(t);
                if (out != null) out.put(t);                 // this put is where back-pressure enters the chain
            }
        } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
    String stageName() { return name; }
}

// ---- ext: scale the consumers -- a pool instead of a thread each, and a monitor that watches depth
/**
 * Thread-per-consumer reads plainly and makes the race visible, which is why the main file uses it. In
 * production the consumers are a sized pool and the number is a decision made from a number: sustained high
 * depth says "add consumers", sustained zero depth says "you over-provisioned". Depth IS the lag signal --
 * the same one Kafka calls consumer lag.
 */
final class AutoScaler {
    private final Handoff h;
    private final int high, low;
    private final List<String> decisions = new ArrayList<>();
    AutoScaler(Handoff h, int highWaterPercent, int lowWaterPercent) {
        this.h = h; this.high = h.capacity() * highWaterPercent / 100; this.low = h.capacity() * lowWaterPercent / 100;
    }
    /** One sample. A real scaler needs several consecutive samples before it acts, or it oscillates. */
    String sample() {
        int d = h.size();
        String decision = d >= high ? "GROW" : d <= low ? "SHRINK" : "HOLD";
        decisions.add(decision + "@" + d);
        return decision;
    }
    List<String> decisions() { return decisions; }
}

/** Consumers as a pool: the same pill protocol works, one pill per worker, submitted after the producers are joined. */
final class PooledConsumers {
    private final ExecutorService pool;
    private final int workers;
    private final Handoff h;
    PooledConsumers(Handoff h, int workers, Work work, Metrics m, FailurePolicy onFailure) {
        this.h = h; this.workers = workers;
        pool = Executors.newFixedThreadPool(workers);
        CountDownLatch open = new CountDownLatch(0);
        for (int i = 0; i < workers; i++) pool.execute(new Consumer("pool-" + i, h, work, m, onFailure, open));
    }
    /** Drain and stop: one pill per worker, then a bounded wait. Never Thread.stop, never shutdownNow first. */
    boolean drainAndStop(long timeoutMs) throws InterruptedException {
        for (int i = 0; i < workers; i++) h.put(Task.POISON);
        pool.shutdown();
        return pool.awaitTermination(timeoutMs, TimeUnit.MILLISECONDS);
    }
}

// ---- ext: the monitoring surface -- back-pressure is invisible without numbers
/**
 * Read-only sampling of the counters so a dashboard can see depth, throughput and blocked time without touching
 * the hot path. Two derived numbers earn their place: items per second, and the share of producer time spent
 * parked -- the second one is the honest measure of whether the consumers are keeping up.
 */
final class Monitor {
    private final Pipeline p;
    private MetricsSnapshot previous;
    private long previousMs;
    Monitor(Pipeline p) { this.p = p; previous = p.stats(); previousMs = System.currentTimeMillis(); }
    /** One line an operator can read: depth, rate since the last sample, and how much back-pressure there was. */
    String line() {
        MetricsSnapshot now = p.stats();
        long ms = Math.max(1L, System.currentTimeMillis() - previousMs);
        long rate = (now.consumed() - previous.consumed()) * 1000L / ms;
        previous = now; previousMs = System.currentTimeMillis();
        return "depth=" + now.depth() + "/" + p.handoff().capacity() + " consumed/s=" + rate
            + " dropped=" + now.dropped() + " parkEvents=" + now.backpressured() + " blockedMs=" + now.blockedMs();
    }
}

// ---- ext: beyond one JVM -- what an in-memory buffer is not, and the smallest seam that fixes it
/**
 * A bounded buffer in one process is not a queue: a crash loses everything in it. The seam is an append-then-ack
 * log in front of the hand-off. put() records the item BEFORE handing it over; the consumer acks after the work
 * succeeds; whatever is unacked at restart is redelivered. That makes delivery at-least-once, not exactly-once,
 * so the consumer must be idempotent -- dedupe by task id is the same trick as an idempotency key on a payment.
 */
final class DurableHandoff implements Handoff {
    private final Handoff base;
    private final Map<Integer, Task> unacked = new ConcurrentHashMap<>();
    private final Set<Integer> alreadyDone = ConcurrentHashMap.newKeySet();
    DurableHandoff(Handoff base) { this.base = base; }
    @Override public void put(Task t) throws InterruptedException { unacked.put(t.id, t); base.put(t); }
    @Override public boolean put(Task t, long ms) throws InterruptedException {
        unacked.put(t.id, t);
        boolean in = base.put(t, ms);
        if (!in) unacked.remove(t.id);
        return in;
    }
    @Override public boolean offer(Task t) { unacked.put(t.id, t); boolean in = base.offer(t); if (!in) unacked.remove(t.id); return in; }
    @Override public Task take() throws InterruptedException { return base.take(); }
    @Override public Task poll(long ms) throws InterruptedException { return base.poll(ms); }
    @Override public Task putEvictingOldest(Task t) { unacked.put(t.id, t); return base.putEvictingOldest(t); }
    @Override public int size() { return base.size(); }
    @Override public int capacity() { return base.capacity(); }
    @Override public String name() { return "durable(" + base.name() + ")"; }
    /** The consumer records the id as done as part of its OWN work, before it acks. */
    void markDone(Task t) { alreadyDone.add(t.id); }
    /** Only after the ack may the item leave the log. A crash between markDone and ack causes a redelivery. */
    void ack(Task t) { unacked.remove(t.id); }
    /** True if this id was already processed. At-least-once delivery means the consumer must ask. */
    boolean isDuplicate(Task t) { return alreadyDone.contains(t.id); }
    /** After a restart: everything not acked goes back in. Some of it will be a second delivery. */
    int redeliver() throws InterruptedException {
        int n = 0;
        for (Task t : new ArrayList<>(unacked.values())) { base.put(t); n++; }
        return n;
    }
}

/** Runs every extension above, so each block on page 05 is code that has actually executed. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        PipelineListener quiet = (event, detail) -> { };

        // shed load instead of stalling: drop-newest and drop-oldest on a buffer of two
        Metrics m = new Metrics();
        Handoff small = new LockHandoff(2);
        new DropNewest().submit(small, new Task(1, "a"), m, quiet);
        new DropNewest().submit(small, new Task(2, "b"), m, quiet);
        boolean admitted = new DropNewest().submit(small, new Task(3, "c"), m, quiet);
        System.out.println("drop-newest: third item admitted=" + admitted + " depth=" + small.size());
        new DropOldest().submit(small, new Task(4, "d"), m, quiet);
        System.out.println("drop-oldest: depth=" + small.size() + " head is now " + small.take() + " (task#1 was evicted)");

        // a producer that must not wait forever
        Handoff full = new LockHandoff(1);
        full.offer(new Task(9, "sits there"));
        long t0 = System.currentTimeMillis();
        boolean in = new TimedBlock(80).submit(full, new Task(10, "late"), m, quiet);
        System.out.println("timed put gave up after " + (System.currentTimeMillis() - t0) + " ms, admitted=" + in);

        // retry then park: a task that fails twice and then succeeds, and one that never does
        AtomicInteger tries = new AtomicInteger();
        Work flaky = t -> { if (t.id == 7 && tries.incrementAndGet() < 3) throw new IllegalStateException("flaky"); };
        RetryingWork retry = new RetryingWork(flaky, 5);
        Metrics rm = new Metrics();
        BoundedDeadLetters dlq = new BoundedDeadLetters(16);
        Work accounted = new AccountedWork(retry, rm, dlq);
        accounted.process(new Task(7, "flaky"));
        accounted.process(new Task(8, "fine"));
        Work alwaysBad = new AccountedWork(t -> { throw new IllegalStateException("poisoned data"); }, rm, dlq);
        alwaysBad.process(new Task(99, "bad"));
        System.out.println("retry: attempts=" + retry.retries() + " consumed=" + rm.consumed.get()
            + " deadLettered=" + rm.deadLettered.get() + " parked=" + dlq.size());

        // the other shutdown: a stop flag WITH a drain, next to the naive one that strands work
        for (boolean drain : new boolean[] { true, false }) {
            Handoff h = new LockHandoff(64);
            for (int i = 0; i < 40; i++) h.put(new Task(i, "backlog"));
            AtomicInteger done = new AtomicInteger();
            AtomicBoolean flag = new AtomicBoolean(true);         // producers already joined
            Work w = t -> done.incrementAndGet();
            Thread c = new Thread(drain ? new DrainingConsumer(h, flag, w, 20) : new NaiveStopConsumer(h, flag, w));
            c.start(); c.join(3_000);
            System.out.println((drain ? "draining stop" : "naive stop  ") + ": processed=" + done.get() + " stranded=" + h.size());
        }

        // the lost wakeup: the signal lands between the check and the wait, so the consumer sleeps on a full buffer
        LostWakeupHandoff broken = new LostWakeupHandoff();
        long[] took = new long[1];
        Thread victim = new Thread(() -> {
            try { long t = System.currentTimeMillis(); broken.takeLosingWakeups(400); took[0] = System.currentTimeMillis() - t; }
            catch (InterruptedException ignored) { }
        });
        victim.start();
        broken.guardRead.await(2, TimeUnit.SECONDS);          // the gap is now open
        broken.put(new Task(5, "arrives in the gap"));        // add + notify: nobody is waiting yet
        broken.signalSent.countDown();                        // only now does the victim call wait()
        victim.join(3_000);
        System.out.println("lost wakeup: the item was there all along, yet the take slept " + took[0]
            + " ms (the whole timeout) before noticing");

        // what java.util.concurrent already gives you: the same run on the JDK's queue, then the JDK's own pipeline
        for (Handoff h : List.of(new LockHandoff(8), new JucHandoff(8))) {
            AtomicLong sum = new AtomicLong();
            Pipeline p = new Pipeline(h);
            p.configure(new BlockUntilRoom(), t -> sum.addAndGet(t.id), new DeadLetterSink());
            p.start(4, 500, 4);
            p.awaitProducers(30_000);
            boolean ok = p.shutdown(30_000);
            long expected = (long) 4 * 500 * (4 * 500 - 1) / 2;
            System.out.println("build \"" + h.name() + "\": clean=" + ok + " every id delivered once="
                + (sum.get() == expected) + " ledger=" + p.stats().balanced());
        }
        JdkPipeline jdk = new JdkPipeline(4, 8);
        AtomicInteger jdkDone = new AtomicInteger();
        for (int i = 0; i < 500; i++) jdk.submit(new Task(i, "row"), t -> { Thread.sleep(0, 200_000); jdkDone.incrementAndGet(); });
        boolean jdkClean = jdk.drainAndStop(10_000);
        System.out.println("ThreadPoolExecutor(4 workers, ArrayBlockingQueue(8), CallerRunsPolicy): ran=" + jdk.ran()
            + " done=" + jdkDone.get() + " stoppedCleanly=" + jdkClean + " (CallerRuns = back-pressure on the submitter)");

        // fairness: the same work through a buffer of one, unfair then fair
        long[] unfairCounts = FairnessProbe.run(false, 4, 120);
        long[] fairCounts = FairnessProbe.run(true, 4, 120);
        System.out.println("fairness: unfair " + Arrays.toString(unfairCounts) + " spread="
            + String.format("%.2f", FairnessProbe.spread(unfairCounts)));
        System.out.println("fairness: fair   " + Arrays.toString(fairCounts) + " spread="
            + String.format("%.2f", FairnessProbe.spread(fairCounts))
            + " (fairness scatters the counts here and costs throughput: the Condition was already FIFO)");

        // what the lock actually costs: the floor, then the capacity ladder
        System.out.printf("cost: one uncontended put+take = %.1f ns -- that is the whole critical section%n",
            HandoffCost.uncontendedNanos(2_000_000));
        System.out.println("cost: 200,000 items, 1 producer 1 consumer: capacity 1 = " + HandoffCost.ladderMs(1, 200_000)
            + " ms, capacity 16 = " + HandoffCost.ladderMs(16, 200_000) + " ms, capacity 1024 = "
            + HandoffCost.ladderMs(1024, 200_000) + " ms (the park is the cost, not the lock)");

        // batching
        Handoff burst = new LockHandoff(64);
        for (int i = 0; i < 25; i++) burst.put(new Task(i, "b"));
        System.out.println("batch of at most 10 from a burst of 25: " + Batches.takeUpTo(burst, 10, 50).size()
            + ", left behind " + burst.size());

        // order per key
        KeyedLanes lanes = new KeyedLanes(4, 16);
        for (String key : new String[] { "acct-1", "acct-2", "acct-1" }) lanes.laneFor(key).put(new Task(key.length(), key));
        System.out.println("keyed lanes: acct-1 always lands in the same lane = "
            + (lanes.laneFor("acct-1") == lanes.laneFor("acct-1")) + ", lane depths "
            + lanes.lane(0).size() + lanes.lane(1).size() + lanes.lane(2).size() + lanes.lane(3).size());

        // many stages: the pill travels down the chain and stops all of them
        Handoff s1 = new LockHandoff(4), s2 = new LockHandoff(4), sink = new LockHandoff(64);
        Thread a = new Thread(new Stage("parse", s1, s2, t -> { }));
        Thread b = new Thread(new Stage("enrich", s2, sink, t -> { }));
        a.start(); b.start();
        for (int i = 0; i < 20; i++) s1.put(new Task(i, "row"));
        s1.put(Task.POISON);
        a.join(3_000); b.join(3_000);
        System.out.println("two stages: sink holds " + sink.size() + " rows, both stages ended="
            + (!a.isAlive() && !b.isAlive()) + ", pill reached the sink=" + (sink.size() == 21));

        // a pool of consumers, and a scaler reading depth
        Handoff pooled = new LockHandoff(32);
        Metrics pm = new Metrics();
        AutoScaler scaler = new AutoScaler(pooled, 75, 10);
        PooledConsumers pc = new PooledConsumers(pooled, 4,
            new AccountedWork(t -> Thread.sleep(1), pm, new DeadLetterSink()), pm, new DeadLetterSink());
        for (int i = 0; i < 200; i++) { pooled.put(new Task(i, "job")); if (i == 150) scaler.sample(); }
        boolean stopped = pc.drainAndStop(10_000);
        scaler.sample();
        System.out.println("pool of 4 with 1 ms work: consumed=" + pm.consumed.get() + " stoppedCleanly=" + stopped
            + " scaler read the depth and said " + scaler.decisions());

        // the monitoring surface
        Pipeline watched = new Pipeline(new LockHandoff(8));
        watched.configure(new BlockUntilRoom(), t -> Thread.sleep(1), new DeadLetterSink());
        Monitor mon = new Monitor(watched);
        watched.start(2, 30, 2);
        Thread.sleep(20);
        System.out.println("monitor mid-run: " + mon.line());
        watched.awaitProducers(5_000);
        watched.shutdown(5_000);
        System.out.println("monitor at rest:  " + mon.line());

        // beyond one JVM: append, ack, redeliver, and the duplicate the consumer must expect
        DurableHandoff durable = new DurableHandoff(new LockHandoff(8));
        durable.put(new Task(41, "charge")); durable.put(new Task(42, "charge"));
        Task first = durable.take();
        durable.markDone(first); durable.ack(first);               // the clean path: work, record, ack
        Task second = durable.take();
        durable.markDone(second);                                  // work done and recorded -- then the process dies
        int back = durable.redeliver();                            // restart: whatever is unacked comes back
        Task again = durable.take();
        System.out.println("durable: redelivered=" + back + " item=" + again + " isDuplicate="
            + durable.isDuplicate(again) + " -> the consumer skips it (at-least-once, so dedupe by id)");
    }
}
