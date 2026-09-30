import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * One unit of work moving through the pipeline. POISON is a reserved instance that is never real work: it is
 * the stop signal that travels in-band, compared by identity (==), so no payload can ever impersonate it.
 */
final class Task {
    /** The stop signal. Exactly one per consumer is put into the buffer at shutdown, behind every real task. */
    static final Task POISON = new Task(-1, "poison");
    final int id;
    final String payload;
    Task(int id, String payload) { this.id = id; this.payload = payload; }
    @Override public String toString() { return "task#" + id; }
}

/** Where time comes from. Injected, so a test can control a deadline. A wait itself is always on the real machine. */
interface Clock { long nowMs(); }

/**
 * What a consumer does with one task. Handed in, so a test can make the work slow, make it throw, or make it
 * count. The pipeline never knows what the work is; it only knows when it returned.
 */
interface Work {
    /** Process one task. Throwing a RuntimeException sends the task to the failure policy, never to nowhere. */
    void process(Task t) throws InterruptedException;
}

/** What happens to a task whose work threw. Handed in, so the pipeline never silently decides to lose an item. */
interface FailurePolicy {
    /** Called with the failed task. It must either park it somewhere or count it; it must not throw. */
    void onFailed(Task t, RuntimeException cause, Metrics m);
}

/** Told after the fact, never with a lock held. A listener that throws cannot break a producer or a consumer. */
interface PipelineListener {
    /** One event: STATE, BACKPRESSURED, DROPPED or DEAD_LETTER, with a human line of detail. */
    void onEvent(String event, String detail);
}

/**
 * The hand-off: the one place a producer thread and a consumer thread meet. Every method is safe to call from
 * any thread. Three builds implement it -- synchronized/wait/notify, ReentrantLock with two Conditions, and
 * java.util.concurrent's ArrayBlockingQueue -- and the rest of the pipeline cannot tell which it was given.
 */
interface Handoff {
    /** Hand the item over, waiting while the buffer is full. Returns only when the item IS in the buffer. */
    void put(Task t) throws InterruptedException;
    /** The same, but give up after timeoutMs. false means the item was never handed over. */
    boolean put(Task t, long timeoutMs) throws InterruptedException;
    /** Hand it over only if there is room this instant. Never waits. */
    boolean offer(Task t);
    /** Take the next item, waiting while the buffer is empty. */
    Task take() throws InterruptedException;
    /** Take the next item, or null if none arrives within timeoutMs. */
    Task poll(long timeoutMs) throws InterruptedException;
    /** Make room by dropping the oldest item, then add. Returns what was dropped, or null if there was room. */
    Task putEvictingOldest(Task t);
    /** How many items are in the buffer right now. A number that is already stale when you read it. */
    int size();
    /** The bound. Memory is O(capacity) whatever the arrival rate; that bound IS the safety property. */
    int capacity();
    /** Which build this is, for the demo line that runs all three. */
    String name();
}

/**
 * Counters every thread tallies. These are independent single increments, so they are lock-free AtomicLongs;
 * the buffer needs a multi-step invariant, so it takes a lock. That is the whole rule for choosing between them.
 */
final class Metrics {
    /** Items created by a producer, counted before the hand-off is attempted. */
    final AtomicLong produced = new AtomicLong();
    /** Items that made it into the buffer. Counted only AFTER the hand-off returned. */
    final AtomicLong admitted = new AtomicLong();
    /** Items the overflow policy shed on arrival, never handed over at all. */
    final AtomicLong dropped = new AtomicLong();
    /** Items that WERE handed over and were later evicted to make room. A different loss, counted separately. */
    final AtomicLong evicted = new AtomicLong();
    /** Items created but never handed over, because the producer was interrupted mid-put. */
    final AtomicLong abandoned = new AtomicLong();
    /** Items whose work returned normally. */
    final AtomicLong consumed = new AtomicLong();
    /** Items whose work threw. */
    final AtomicLong failed = new AtomicLong();
    /** Items parked by the failure policy, so a failure is never a disappearance. */
    final AtomicLong deadLettered = new AtomicLong();
    /** Items still in the buffer when shutdownNow() was called: handed back to the caller, never run. */
    final AtomicLong discarded = new AtomicLong();
    /** How many times a producer found the buffer full and had to wait. This number IS back-pressure. */
    final AtomicLong backpressured = new AtomicLong();
    /** How long producers spent parked in total. */
    final AtomicLong blockedNanos = new AtomicLong();
    /** Items taken but not yet finished. The ledger balances only when this is zero. */
    final AtomicInteger inFlight = new AtomicInteger();
    /** The deepest the buffer was ever seen. It must never exceed the capacity. */
    final AtomicInteger maxDepth = new AtomicInteger();
    /** Pills actually taken by consumers. Must equal the consumer count after a clean shutdown. */
    final AtomicInteger pillsTaken = new AtomicInteger();

    /** Remember the high-water mark of the buffer. Used by the test that proves the bound held. */
    void observeDepth(int depth) { maxDepth.accumulateAndGet(depth, Math::max); }

    /** An immutable copy a monitor or a dashboard can print without touching the hot path. */
    MetricsSnapshot snapshot(int depth) {
        return new MetricsSnapshot(produced.get(), admitted.get(), dropped.get(), evicted.get(), abandoned.get(),
            consumed.get(), deadLettered.get(), discarded.get(), backpressured.get(), blockedNanos.get() / 1_000_000L,
            maxDepth.get(), depth, inFlight.get(), pillsTaken.get());
    }
}

/**
 * One reading of the counters. The two identities below are the exactly-once promise of the whole design; they
 * are exact at rest (after shutdown) and approximate while threads run, because the fields are read one at a time.
 */
record MetricsSnapshot(long produced, long admitted, long dropped, long evicted, long abandoned, long consumed,
                       long deadLettered, long discarded, long backpressured, long blockedMs, int maxDepth,
                       int depth, int inFlight, int pillsTaken) {
    /**
     * The exactly-once ledger, in two lines. Every item made was handed over, shed on arrival, or abandoned by an
     * interrupted producer; and every item handed over was consumed, parked in the dead-letter queue, evicted to
     * make room, handed back by shutdownNow, still in the buffer, or still in a consumer's hand. Nothing else is
     * possible, so if these two lines hold, no item was lost and no item was done twice.
     */
    boolean balanced() {
        return produced == admitted + dropped + abandoned
            && admitted == consumed + deadLettered + evicted + discarded + depth + inFlight;
    }
    @Override public String toString() {
        return "produced=" + produced + " admitted=" + admitted + " dropped=" + dropped + " evicted=" + evicted
            + " abandoned=" + abandoned + " consumed=" + consumed + " deadLettered=" + deadLettered
            + " discarded=" + discarded
            + " depth=" + depth + " inFlight=" + inFlight + " maxDepth=" + maxDepth
            + " backpressured=" + backpressured + " blockedMs=" + blockedMs + " pills=" + pillsTaken
            + " balanced=" + balanced();
    }
}

/**
 * The hand-off itself: a ReentrantLock and TWO Conditions over a fixed array ring. A Condition is a queue of
 * sleeping threads attached to the lock. Producers sleep on notFull, consumers sleep on notEmpty, so a signal
 * always wakes a thread that can actually make progress. Everything inside the lock is array arithmetic; nothing
 * slow is allowed in. (The sibling page, Bounded Blocking Queue, builds this same object three other ways.)
 */
final class LockHandoff implements Handoff {
    private final Task[] ring;
    private final int cap;
    private int head, tail, count;
    private final ReentrantLock lock;
    private final Condition notFull, notEmpty;

    LockHandoff(int capacity) { this(capacity, false); }
    /**
     * fair = true hands the lock to the thread that has waited longest, so no producer can be starved by a
     * neighbour that keeps barging in. It costs throughput, because every hand-over becomes a context switch.
     */
    LockHandoff(int capacity, boolean fair) {
        if (capacity < 1) throw new IllegalArgumentException("capacity must be at least 1");
        cap = capacity; ring = new Task[capacity];
        lock = new ReentrantLock(fair);
        notFull = lock.newCondition();
        notEmpty = lock.newCondition();
    }
    /** Park on notFull while the buffer is full, then add and wake exactly one waiting consumer. */
    @Override public void put(Task t) throws InterruptedException {
        lock.lockInterruptibly();
        try {
            while (count == cap) notFull.await();
            enqueue(t);
            notEmpty.signal();
        } finally { lock.unlock(); }
    }
    /** The timed twin, on awaitNanos: it returns the time LEFT, so the deadline survives a spurious wake-up. */
    @Override public boolean put(Task t, long timeoutMs) throws InterruptedException {
        long nanos = TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        lock.lockInterruptibly();
        try {
            while (count == cap) {
                if (nanos <= 0L) return false;
                nanos = notFull.awaitNanos(nanos);
            }
            enqueue(t); notEmpty.signal(); return true;
        } finally { lock.unlock(); }
    }
    @Override public boolean offer(Task t) {
        lock.lock();
        try {
            if (count == cap) return false;
            enqueue(t); notEmpty.signal(); return true;
        } finally { lock.unlock(); }
    }
    @Override public Task take() throws InterruptedException {
        lock.lockInterruptibly();
        try {
            while (count == 0) notEmpty.await();
            Task t = dequeue();
            notFull.signal();
            return t;
        } finally { lock.unlock(); }
    }
    @Override public Task poll(long timeoutMs) throws InterruptedException {
        long nanos = TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        lock.lockInterruptibly();
        try {
            while (count == 0) {
                if (nanos <= 0L) return null;
                nanos = notEmpty.awaitNanos(nanos);
            }
            Task t = dequeue(); notFull.signal(); return t;
        } finally { lock.unlock(); }
    }
    /** Drop the oldest and add the new one as ONE step under the lock, so the bound can never be exceeded. */
    @Override public Task putEvictingOldest(Task t) {
        lock.lock();
        try {
            Task evicted = count == cap ? dequeue() : null;
            enqueue(t);
            notEmpty.signal();
            return evicted;
        } finally { lock.unlock(); }
    }
    @Override public int size() { lock.lock(); try { return count; } finally { lock.unlock(); } }
    @Override public int capacity() { return cap; }
    @Override public String name() { return "ReentrantLock(fair=" + lock.isFair() + ") + notFull/notEmpty"; }

    private void enqueue(Task t) { ring[tail] = t; tail = (tail + 1) % cap; count++; }
    private Task dequeue() { Task t = ring[head]; ring[head] = null; head = (head + 1) % cap; count--; return t; }
}

/**
 * What happens when the buffer is full. THIS is the decision the interviewer changes mid-round, so it is one
 * method behind an interface and is handed in: the buffer, the producer and the consumer never learn its name.
 */
interface OverflowPolicy {
    /** true = the item is in the buffer; false = it was shed and will never be consumed. Announce on out, lock-free. */
    boolean submit(Handoff h, Task t, Metrics m, PipelineListener out) throws InterruptedException;
}

/**
 * The default policy, and the honest one: when the buffer is full the producer waits. That wait IS back-pressure
 * -- the consumer's slowness travelling backwards up the pipeline -- and it is why memory stays bounded.
 */
final class BlockUntilRoom implements OverflowPolicy {
    @Override public boolean submit(Handoff h, Task t, Metrics m, PipelineListener out) throws InterruptedException {
        if (h.offer(t)) return true;                        // the common case: room, no waiting, no bookkeeping
        m.backpressured.incrementAndGet();
        out.onEvent("BACKPRESSURED", Thread.currentThread().getName() + " parked with " + t + ", buffer full at " + h.capacity());
        long t0 = System.nanoTime();
        h.put(t);                                           // park on notFull until a consumer frees a slot
        m.blockedNanos.addAndGet(System.nanoTime() - t0);
        return true;
    }
}

/**
 * The wrapper the pipeline puts around WHATEVER work it was handed, so the exactly-once count cannot be broken
 * by work written next year: an item counts as consumed only after the work RETURNS, and work that throws goes
 * to the failure policy instead of vanishing. Same shape as the split-checker in the money problems: a Decorator.
 */
final class AccountedWork implements Work {
    private final Work base;
    private final Metrics m;
    private final FailurePolicy onFailure;
    AccountedWork(Work base, Metrics m, FailurePolicy onFailure) { this.base = base; this.m = m; this.onFailure = onFailure; }
    @Override public void process(Task t) throws InterruptedException {
        try {
            base.process(t);
        } catch (RuntimeException e) {
            m.failed.incrementAndGet();
            onFailure.onFailed(t, e, m);                    // parked, not lost
            return;
        }
        m.consumed.incrementAndGet();                       // counted only after the work actually finished
    }
}

/** The default failure policy: park the task in a queue somebody can drain later. Nothing is ever dropped silently. */
final class DeadLetterSink implements FailurePolicy {
    private final Queue<Task> parked = new ConcurrentLinkedQueue<>();
    @Override public void onFailed(Task t, RuntimeException cause, Metrics m) {
        m.deadLettered.incrementAndGet();
        parked.add(t);
    }
    /** The parked tasks, oldest first. A real system would retry these or show them to an operator. */
    Queue<Task> parked() { return parked; }
    int size() { return parked.size(); }
}

/**
 * Makes tasks on its own thread and hands each to the overflow policy. It never touches the lock, never decides
 * what a full buffer means, and stops making items the moment the stop flag is set -- so nothing is added after stop.
 */
final class Producer implements Runnable {
    private final String name;
    private final int baseId, count;
    private final Handoff handoff;
    private final OverflowPolicy policy;
    private final Metrics m;
    private final PipelineListener out;
    private final AtomicBoolean stopped;
    private final CountDownLatch gate;
    Producer(String name, int baseId, int count, Handoff handoff, OverflowPolicy policy, Metrics m,
             PipelineListener out, AtomicBoolean stopped, CountDownLatch gate) {
        this.name = name; this.baseId = baseId; this.count = count; this.handoff = handoff;
        this.policy = policy; this.m = m; this.out = out; this.stopped = stopped; this.gate = gate;
    }
    @Override public void run() {
        try {
            gate.await();                                   // every thread starts at the same instant: a real race
            for (int i = 0; i < count; i++) {
                if (stopped.get()) return;                  // no item is even created after stop
                Task t = new Task(baseId + i, name + ":" + i);
                m.produced.incrementAndGet();
                if (policy.submit(handoff, t, m, out)) {
                    m.admitted.incrementAndGet();           // counted only once it is IN the buffer
                } else {
                    m.dropped.incrementAndGet();
                    out.onEvent("DROPPED", name + " shed " + t);
                }
                m.observeDepth(handoff.size());
            }
        } catch (InterruptedException e) {
            m.abandoned.incrementAndGet();                  // made but never handed over: the ledger says so
            Thread.currentThread().interrupt();             // restore the flag, then end the thread
        }
    }
}

/**
 * Takes tasks and does the work. It stops on the POISON pill it takes out of the buffer, never on a flag it
 * polls, so every real task queued ahead of that pill is processed first. An interrupt is not a shutdown: if one
 * arrives with a task in hand, that task goes to the failure policy rather than disappearing with the thread.
 */
final class Consumer implements Runnable {
    private final String name;
    private final Handoff handoff;
    private final Work work;
    private final Metrics m;
    private final FailurePolicy onFailure;
    private final CountDownLatch gate;
    Consumer(String name, Handoff handoff, Work work, Metrics m, FailurePolicy onFailure, CountDownLatch gate) {
        this.name = name; this.handoff = handoff; this.work = work; this.m = m; this.onFailure = onFailure; this.gate = gate;
    }
    @Override public void run() {
        Task inHand = null;
        try {
            gate.await();
            for (;;) {
                inHand = handoff.take();                    // parks on notEmpty while the buffer is empty
                if (inHand == Task.POISON) {                // identity, not equals: only the real pill stops us
                    m.pillsTaken.incrementAndGet();
                    inHand = null;
                    return;
                }
                m.inFlight.incrementAndGet();
                work.process(inHand);
                m.inFlight.decrementAndGet();
                inHand = null;
            }
        } catch (InterruptedException e) {
            if (inHand != null) {
                m.inFlight.decrementAndGet();
                m.failed.incrementAndGet();
                onFailure.onFailed(inHand, new IllegalStateException(name + " interrupted holding " + inHand), m);
            }
            Thread.currentThread().interrupt();
        }
    }
}

/** The pipeline's life. DRAINING is the interesting one: producers have stopped, the backlog has not. */
enum PipelineState { NEW, RUNNING, DRAINING, TERMINATED }

/**
 * The aggregate root: it owns the hand-off, the threads, the counters and the life cycle, and it is the only
 * class that knows the shutdown protocol. One lock, and it guards the life cycle only -- the hand-off has its
 * own. Every rule it uses is handed in through configure(); it builds none of them.
 */
final class Pipeline {
    private final Handoff handoff;
    private final Metrics metrics = new Metrics();
    private final ReentrantLock lock = new ReentrantLock();      // guards state + the two thread lists, nothing else
    private final List<PipelineListener> listeners = new CopyOnWriteArrayList<>();
    private final List<Thread> producerThreads = new ArrayList<>();
    private final List<Thread> consumerThreads = new ArrayList<>();
    private final AtomicBoolean stopped = new AtomicBoolean();
    private final CountDownLatch gate = new CountDownLatch(1);   // released once every thread exists
    private PipelineState state = PipelineState.NEW;
    private OverflowPolicy policy = new BlockUntilRoom();
    private Work work = t -> { };
    private FailurePolicy onFailure = new DeadLetterSink();
    private Clock clock = System::currentTimeMillis;

    Pipeline(Handoff handoff) { this.handoff = handoff; }

    /** The three rules, handed in. The pipeline never constructs a policy, a work function or a failure rule. */
    void configure(OverflowPolicy policy, Work work, FailurePolicy onFailure) {
        lock.lock();
        try {
            if (state != PipelineState.NEW) throw new IllegalStateException("configure before start; this pipeline is " + state);
            this.policy = policy; this.work = work; this.onFailure = onFailure;
        } finally { lock.unlock(); }
    }
    /** Add a listener. It is called after the fact and outside every lock. */
    void addListener(PipelineListener l) { listeners.add(l); }
    /** Hand in a clock, so a test can decide what a shutdown deadline means. */
    void setClock(Clock c) { clock = c; }

    /** The single listener everything else is given: it fans out, and a listener that throws is swallowed here. */
    private final PipelineListener fanout = (event, detail) -> {
        for (PipelineListener l : listeners) {
            try { l.onEvent(event, detail); } catch (RuntimeException ignored) { /* a broken listener is not an outage */ }
        }
    };

    /**
     * Create the threads under the lock, start them outside it, then open the gate so all of them begin at the
     * same instant. Consumers are created first so they are already parked on notEmpty when work starts arriving.
     */
    void start(int producers, int itemsEach, int consumers) {
        lock.lock();
        try {
            if (state != PipelineState.NEW) throw new IllegalStateException("start() once, from NEW; this pipeline is " + state);
            Work counted = new AccountedWork(work, metrics, onFailure);     // the wrapper that guards the count
            for (int c = 0; c < consumers; c++) {
                Runnable r = new Consumer("consumer-" + c, handoff, counted, metrics, onFailure, gate);
                consumerThreads.add(new Thread(r, "consumer-" + c));
            }
            for (int p = 0; p < producers; p++) {
                Runnable r = new Producer("producer-" + p, p * itemsEach, itemsEach, handoff, policy, metrics, fanout, stopped, gate);
                producerThreads.add(new Thread(r, "producer-" + p));
            }
            state = PipelineState.RUNNING;
        } finally { lock.unlock(); }
        for (Thread t : consumerThreads) t.start();
        for (Thread t : producerThreads) t.start();
        gate.countDown();
        fanout.onEvent("STATE", "RUNNING: " + producers + " producers x " + itemsEach + " items, " + consumers
            + " consumers, capacity " + handoff.capacity() + ", hand-off = " + handoff.name());
    }

    /**
     * Wait for the producers to finish the work they planned, without telling them to stop. This is the normal
     * end of a run: the source is exhausted, and only then does the drain begin. Bounded: false means the deadline passed.
     */
    boolean awaitProducers(long timeoutMs) throws InterruptedException {
        long deadline = clock.nowMs() + timeoutMs;
        for (Thread t : producerThreads) {
            long left = deadline - clock.nowMs();
            if (left <= 0L) return false;
            t.join(left);
            if (t.isAlive()) return false;
        }
        return true;
    }

    /**
     * The shutdown protocol, in the order that makes it safe:
     * 1. flip to DRAINING and set the stop flag, so no producer starts another item;
     * 2. join the producers -- after this line nobody can add anything, which is what makes step 3 sound;
     * 3. put exactly one POISON pill per consumer; FIFO puts every pill behind every real task;
     * 4. join the consumers: each drains the backlog, takes one pill and exits;
     * 5. flip to TERMINATED.
     * Returns false if the deadline passed. It never waits without a bound, so it can never hang a test.
     */
    boolean shutdown(long timeoutMs) throws InterruptedException {
        lock.lock();
        try {
            if (state == PipelineState.TERMINATED) return true;
            if (state == PipelineState.NEW) { state = PipelineState.TERMINATED; return true; }
            state = PipelineState.DRAINING;
        } finally { lock.unlock(); }
        stopped.set(true);
        fanout.onEvent("STATE", "DRAINING: producers told to stop, backlog " + handoff.size());
        long deadline = clock.nowMs() + timeoutMs;
        for (Thread t : producerThreads) {
            long left = deadline - clock.nowMs();
            if (left <= 0L) return false;
            t.join(left);
            if (t.isAlive()) return false;
        }
        for (int i = 0; i < consumerThreads.size(); i++) {
            long left = deadline - clock.nowMs();
            if (left <= 0L || !handoff.put(Task.POISON, left)) return false;
        }
        for (Thread t : consumerThreads) {
            long left = deadline - clock.nowMs();
            if (left <= 0L) return false;
            t.join(left);
            if (t.isAlive()) return false;
        }
        lock.lock();
        try { state = PipelineState.TERMINATED; } finally { lock.unlock(); }
        fanout.onEvent("STATE", "TERMINATED: " + stats());
        return true;
    }

    /**
     * The other shutdown: stop NOW and hand back the work that will never run. Same first step -- flip to
     * DRAINING and set the stop flag -- then interrupt every thread instead of queueing pills, join them with
     * the same deadline, and drain whatever is left in the buffer into a list the CALLER owns. Those items are
     * counted discarded, so the ledger still balances: nothing was lost, it was handed over. An item a consumer
     * was already holding is not in this list; the interrupt sends that one to the failure policy instead.
     * This is exactly what ExecutorService.shutdownNow() does, and why it returns a List.
     */
    List<Task> shutdownNow(long timeoutMs) throws InterruptedException {
        lock.lock();
        try {
            if (state == PipelineState.NEW || state == PipelineState.TERMINATED) {
                state = PipelineState.TERMINATED; return List.of();
            }
            state = PipelineState.DRAINING;
        } finally { lock.unlock(); }
        stopped.set(true);
        for (Thread t : producerThreads) t.interrupt();       // a parked producer wakes with InterruptedException
        for (Thread t : consumerThreads) t.interrupt();       // a parked consumer wakes and ends
        long deadline = clock.nowMs() + timeoutMs;
        for (Thread t : producerThreads) { long left = deadline - clock.nowMs(); if (left > 0L) t.join(left); }
        for (Thread t : consumerThreads) { long left = deadline - clock.nowMs(); if (left > 0L) t.join(left); }
        List<Task> undone = new ArrayList<>();
        for (Task t = handoff.poll(0); t != null; t = handoff.poll(0)) {
            if (t == Task.POISON) continue;                   // a pill is not work and is not handed back
            undone.add(t);
            metrics.discarded.incrementAndGet();
        }
        lock.lock();
        try { state = PipelineState.TERMINATED; } finally { lock.unlock(); }
        fanout.onEvent("STATE", "TERMINATED by shutdownNow: " + undone.size() + " unprocessed items handed back");
        return undone;
    }

    /** A reading of the counters, with the buffer's current depth folded in. */
    MetricsSnapshot stats() { return metrics.snapshot(handoff.size()); }
    /** The counters themselves, for a test that wants to watch one of them move. */
    Metrics metrics() { return metrics; }
    PipelineState state() { lock.lock(); try { return state; } finally { lock.unlock(); } }
    Handoff handoff() { return handoff; }
    /** True when no producer and no consumer thread is still alive. */
    boolean allThreadsDead() {
        for (Thread t : producerThreads) if (t.isAlive()) return false;
        for (Thread t : consumerThreads) if (t.isAlive()) return false;
        return true;
    }
}

/** The demo: back-pressure made visible, a ten-by-ten exactly-once race, and the stop-now shutdown. */
public class Main {
    public static void main(String[] args) throws Exception {
        // ---------------------------------------------------------------- 1. back-pressure, made visible
        // three fast producers, two deliberately slow consumers, a buffer of four: the producers must park.
        Pipeline demo = new Pipeline(new LockHandoff(4));
        DeadLetterSink demoDlq = new DeadLetterSink();
        AtomicInteger printed = new AtomicInteger();
        demo.addListener((event, detail) -> {
            if (event.equals("STATE") || printed.getAndIncrement() < 4) System.out.println("[" + event + "] " + detail);
        });
        demo.configure(new BlockUntilRoom(), t -> Thread.sleep(2), demoDlq);
        demo.start(3, 20, 2);
        demo.awaitProducers(10_000);                            // the source is exhausted; only now do we drain
        boolean clean = demo.shutdown(10_000);
        System.out.println("demo shutdown clean=" + clean + " state=" + demo.state());
        System.out.println("demo " + demo.stats());

        // ---------------------------------------------------------------- 2. the race: 10 x 10, every item once
        int producers = 10, consumers = 10, each = 2_000, total = producers * each;
        AtomicIntegerArray seen = new AtomicIntegerArray(total);
        Pipeline race = new Pipeline(new LockHandoff(16));
        race.configure(new BlockUntilRoom(), t -> seen.incrementAndGet(t.id), new DeadLetterSink());
        long t0 = System.nanoTime();
        race.start(producers, each, consumers);                 // the internal gate releases all 20 threads at once
        race.awaitProducers(30_000);
        boolean raceClean = race.shutdown(30_000);
        long ms = (System.nanoTime() - t0) / 1_000_000L;
        int once = 0, twice = 0, never = 0;
        for (int i = 0; i < total; i++) {
            int n = seen.get(i);
            if (n == 1) once++; else if (n > 1) twice++; else never++;
        }
        MetricsSnapshot s = race.stats();
        System.out.println("race: " + producers + " producers x " + consumers + " consumers, " + total + " items in " + ms + " ms");
        System.out.println("race: consumed exactly once=" + once + " duplicated=" + twice + " lost=" + never);
        System.out.println("race: " + s);
        System.out.println("race: depth never exceeded capacity: " + (s.maxDepth() <= race.handoff().capacity())
            + " (maxDepth=" + s.maxDepth() + ", capacity=" + race.handoff().capacity() + ")");
        System.out.println("race: pills taken=" + s.pillsTaken() + " (one per consumer), threads alive=" + !race.allThreadsDead());
        if (!raceClean || once != total || twice != 0 || never != 0 || !s.balanced()) throw new AssertionError("the pipeline lost an item");

        // ---------------------------------------------------------------- 3. the other shutdown: stop NOW
        // Same pipeline, but the caller cannot wait for the backlog: it wants the unprocessed work handed back.
        Pipeline urgent = new Pipeline(new LockHandoff(32));
        urgent.configure(new BlockUntilRoom(), t -> Thread.sleep(2), new DeadLetterSink());
        urgent.start(2, 10_000, 2);
        Thread.sleep(40);
        List<Task> undone = urgent.shutdownNow(10_000);
        MetricsSnapshot us = urgent.stats();
        System.out.println("stopNow: handed back " + undone.size() + " unprocessed items, buffer now "
            + urgent.handoff().size() + ", threads alive=" + !urgent.allThreadsDead());
        System.out.println("stopNow: " + us);
        if (!urgent.allThreadsDead() || !us.balanced() || us.depth() != 0)
            throw new AssertionError("stopNow left the pipeline in a state the ledger cannot explain");
    }
}
