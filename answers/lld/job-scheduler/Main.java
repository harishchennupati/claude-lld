import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// ================================================================ the job's code, and where time comes from

/** The code a job runs. A throw of any kind is one failed attempt; the job's RetryPolicy decides what follows. */
@FunctionalInterface
interface Task {
    /** Do the work once. */
    void run() throws Exception;
}

/**
 * Where time comes from, in milliseconds. The scheduler never reads a clock of its own, so a test can hand
 * in a ManualClock and make "one hour later" happen instantly.
 */
@FunctionalInterface
interface Clock {
    /** Now, in milliseconds. */
    long nowMs();

    /**
     * The production clock: System.nanoTime, which never jumps (the wall clock does, when NTP or a person
     * corrects it), anchored once to the wall clock so its values read as epoch milliseconds.
     */
    static Clock system() {
        long anchor = System.currentTimeMillis() - System.nanoTime() / 1_000_000;
        return () -> anchor + System.nanoTime() / 1_000_000;
    }
}

/** A clock that tests move by hand: nothing sleeps, and "one hour later" costs nothing. */
final class ManualClock implements Clock {
    private final AtomicLong now;

    ManualClock(long startMs) { now = new AtomicLong(startMs); }
    /** The time the test last set. */
    public long nowMs() { return now.get(); }
    /** Jump to a moment. */
    void set(long ms) { now.set(ms); }
    /** Move forward by ms. */
    void advance(long ms) { now.addAndGet(ms); }
}

// ================================================================ the rules that change: when next, what if late, how to retry

/**
 * When a job runs next. A pure function of two times: it runs inside the scheduler's lock, so it must be fast
 * and must never call back into the scheduler. ONCE means the job does not recur.
 */
@FunctionalInterface
interface Trigger {
    /** Returned by next() when there is no next run. */
    long NONE = -1;
    /** A one-shot job: no next run. */
    Trigger ONCE = (plannedAt, finishedAt) -> NONE;

    /** The next planned start, later than plannedAt, after a run planned for plannedAt that ended at finishedAt; or NONE. */
    long next(long plannedAt, long finishedAt);
}

/**
 * Fixed rate: every periodMs, counted from the PLANNED start of the last run (10:00:00, 10:00:10, 10:00:20),
 * so the rhythm never drifts, however long a run takes.
 */
record FixedRate(long periodMs) implements Trigger {
    /** Refuses a period of zero or less. */
    FixedRate { if (periodMs <= 0) throw new IllegalArgumentException("period must be positive: " + periodMs); }
    /** The planned start plus one period. */
    public long next(long plannedAt, long finishedAt) { return plannedAt + periodMs; }
}

/** Fixed delay: delayMs after the last run ENDED, so a slow run pushes every later run back. */
record FixedDelay(long delayMs) implements Trigger {
    /** Refuses a delay of zero or less. */
    FixedDelay { if (delayMs <= 0) throw new IllegalArgumentException("delay must be positive: " + delayMs); }
    /** The end of the last run plus the delay. */
    public long next(long plannedAt, long finishedAt) { return finishedAt + delayMs; }
}

/**
 * What happens to planned runs of a recurring job that were missed: the job was still running at its next
 * planned time, every worker was busy, or the process was down. A closed list of three answers, so an enum.
 */
enum Misfire {
    /** Run every missed one, back to back, until caught up (what the JDK's fixed rate does). */
    RUN_ALL,
    /** Run once, now, for all the missed ones; then continue from the next planned time in the future. */
    RUN_ONCE,
    /** Run none of the missed ones; wait for the next planned time in the future. */
    SKIP;

    /**
     * The planned slot to run next, given the trigger's next slot (maybe already in the past) and now; NONE
     * means no more runs. The job starts at max(slot, now), so a slot in the past starts at once.
     * Cost: one step per missed slot.
     */
    long place(Trigger t, long next, long finishedAt, long now) {
        if (next == Trigger.NONE || next >= now || this == RUN_ALL) return next;
        long after = t.next(next, finishedAt);
        while (after != Trigger.NONE && after > next && after < now) { next = after; after = t.next(after, finishedAt); }
        if (this == RUN_ONCE) return next;                                   // the latest missed slot, once, now
        return (after == Trigger.NONE || after <= next) ? Trigger.NONE : after;  // SKIP: the first slot not yet past
    }
}

/** How long to wait before the next attempt of a failed run, or GIVE_UP. Pure, like Trigger: it runs inside the lock. */
@FunctionalInterface
interface RetryPolicy {
    /** Returned by delayMs() to stop retrying. */
    long GIVE_UP = -1;
    /** Never retry: one attempt per run. */
    RetryPolicy NONE = (attempts, error) -> GIVE_UP;

    /** The wait before attempt number attempts + 1, now that `attempts` attempts have failed; or GIVE_UP. */
    long delayMs(int attempts, Exception error);
}

/**
 * Exponential backoff with jitter: wait base, then 2 x base, 4 x base ..., never more than cap, and at most
 * maxAttempts attempts in all. Jitter (a random part of each wait) spreads out jobs that failed together, so
 * a thousand of them do not all retry in the same millisecond: here half of each wait is fixed, half random.
 */
final class ExponentialBackoff implements RetryPolicy {
    private final long baseMs, capMs;
    private final int maxAttempts;
    private final Random random;                          // null = no jitter: exact waits, for tests

    ExponentialBackoff(long baseMs, long capMs, int maxAttempts, Random random) {
        if (baseMs <= 0 || capMs < baseMs || maxAttempts < 1) throw new IllegalArgumentException("bad backoff");
        this.baseMs = baseMs; this.capMs = capMs; this.maxAttempts = maxAttempts; this.random = random;
    }
    /** base, 2 x base, 4 x base ... up to the cap; half of it random when jitter is on; GIVE_UP after maxAttempts. */
    public long delayMs(int attempts, Exception error) {
        if (attempts >= maxAttempts) return GIVE_UP;
        long wait = baseMs;
        for (int i = 1; i < attempts && wait < capMs; i++) wait *= 2;       // doubling stops at the cap: no overflow
        wait = Math.min(wait, capMs);
        return random == null ? wait : wait / 2 + random.nextLong(wait / 2 + 1);
    }
}

// ================================================================ a job's life, and what a caller asks for

/** The life of a job. The ALLOWED table is the whole state machine: any other move is a bug, and it throws. */
enum JobState {
    /** Waiting for its prerequisites to finish. */
    BLOCKED,
    /** Waiting for its time, or for a free worker. */
    SCHEDULED,
    /** Handed to a worker. */
    RUNNING,
    /** Finished: a one-shot that succeeded, or a recurring job whose trigger ran out. */
    DONE,
    /** Finished: the last attempt threw and the retry policy gave up. */
    FAILED,
    /** Finished: cancelled before it started, or stopped by a cancel or a shutdown while it ran. */
    CANCELLED,
    /** Finished without running: a prerequisite failed, was cancelled, or was itself skipped. */
    SKIPPED;

    /** The legal moves. BLOCKED and SCHEDULED can be cancelled; RUNNING goes back to SCHEDULED for a retry or the next run. */
    static final Map<JobState, Set<JobState>> ALLOWED = new EnumMap<>(Map.of(
            BLOCKED,   EnumSet.of(SCHEDULED, CANCELLED, SKIPPED),
            SCHEDULED, EnumSet.of(RUNNING, CANCELLED),
            RUNNING,   EnumSet.of(SCHEDULED, DONE, FAILED, CANCELLED),
            DONE,      EnumSet.noneOf(JobState.class),
            FAILED,    EnumSet.noneOf(JobState.class),
            CANCELLED, EnumSet.noneOf(JobState.class),
            SKIPPED,   EnumSet.noneOf(JobState.class)));

    /** True for the four states a job never leaves. */
    boolean isFinal() { return compareTo(DONE) >= 0; }
}

/**
 * What a caller asks for, filled in with chained calls: JobSpec.of("backup", task).in(300_000).priority(5).
 * An id and a task are required and six settings are optional, which is why this is a builder and not a
 * constructor with eight arguments.
 */
final class JobSpec {
    final String id;
    final Task task;
    long delayMs;                                          // start this long after it is submitted...
    long atMs = -1;                                        // ...or at this clock time, when set
    Trigger trigger = Trigger.ONCE;
    RetryPolicy retry = RetryPolicy.NONE;
    Misfire misfire = Misfire.RUN_ONCE;
    int priority;
    final List<String> after = new ArrayList<>();

    /** Use JobSpec.of(id, task). */
    private JobSpec(String id, Task task) {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("a job needs an id");
        this.id = id; this.task = Objects.requireNonNull(task, "task");
    }
    /** A job with this id (unique in the scheduler) that runs this task once, now, unless told otherwise. */
    static JobSpec of(String id, Task task) { return new JobSpec(id, task); }
    /** Start delayMs after submission; a negative delay means now. */
    JobSpec in(long delayMs) { this.delayMs = Math.max(0, delayMs); this.atMs = -1; return this; }
    /** Start at this clock time, in epoch milliseconds ("run this command at epoch T"); a time already past means now. */
    JobSpec at(long epochMs) { this.atMs = epochMs; return this; }
    /** Recur by this trigger: FixedRate, FixedDelay, a daily time... */
    JobSpec every(Trigger t) { this.trigger = Objects.requireNonNull(t); return this; }
    /** Retry failed attempts by this policy. */
    JobSpec retry(RetryPolicy r) { this.retry = Objects.requireNonNull(r); return this; }
    /** What to do with the missed runs of a recurring job. */
    JobSpec misfire(Misfire m) { this.misfire = Objects.requireNonNull(m); return this; }
    /** Higher goes first when several jobs are due and the workers are all busy. */
    JobSpec priority(int p) { this.priority = p; return this; }
    /** Run only after these jobs have finished successfully: its prerequisites. */
    JobSpec after(String... ids) { after.addAll(List.of(ids)); return this; }
}

/**
 * One job inside the scheduler: its settings, where it is in its life, and the links to the jobs that wait
 * for it. Every field that changes is read and written only under the scheduler's lock.
 */
final class ScheduledJob {
    final String id;
    final Task task;
    final Trigger trigger;
    final RetryPolicy retry;
    final Misfire misfire;
    final int priority;
    final long seq;                                        // submission order: the last tie-break, first come first served
    final List<String> after;                              // the ids this job waits for (its prerequisites)
    final List<ScheduledJob> dependents = new ArrayList<>();  // the jobs that wait for this one
    JobState state;
    long plannedAt;                                        // the planned slot this run belongs to; a retry keeps it
    long dueAt;                                            // when it may start: the time heap's key
    int attempts;                                          // attempts made for the current planned run
    int waitingFor;                                        // prerequisites not yet DONE; 0 = free to be scheduled
    boolean cancelRequested;                               // cancel() arrived while it ran: no retry and no next run
    String lastError;

    /** Copies the settings out of the spec, so a caller who changes the spec later changes nothing here. */
    ScheduledJob(JobSpec s, long seq, long plannedAt) {
        id = s.id; task = s.task; trigger = s.trigger; retry = s.retry; misfire = s.misfire;
        priority = s.priority; this.seq = seq; after = List.copyOf(new LinkedHashSet<>(s.after));
        this.plannedAt = plannedAt; this.dueAt = plannedAt;
    }
    /** True when the job repeats. */
    boolean recurring() { return trigger != Trigger.ONCE; }
}

/** What one attempt did, or why a job ended without running: one line of history. error is null on success. */
record RunRecord(String jobId, int attempt, long startedAt, long finishedAt, String error, JobState then) {}

/**
 * Hears about every finished attempt and every job that ends without running, AFTER the scheduler's lock is
 * released, so a slow or broken listener delays no job: history, metrics, a pager on FAILED.
 */
@FunctionalInterface
interface RunListener {
    /** Called from worker threads and callers: an implementation must be thread-safe. */
    void onRun(RunRecord r);
}

// ================================================================ the aggregate root

/**
 * The scheduler. It owns every job, two heaps (one ordered by time, one by who goes first), the counts, one
 * lock and one condition. One dispatcher thread sleeps until the earliest job is due and hands it to one of
 * N worker threads. Jobs never run on the dispatcher and never inside the lock.
 */
final class Scheduler {
    /** Order of the time heap: earliest due first, then submission order. */
    static final Comparator<ScheduledJob> BY_DUE =
            Comparator.comparingLong((ScheduledJob j) -> j.dueAt).thenComparingLong(j -> j.seq);
    /** The default "which due job first": higher priority, then earlier due, then submission order. */
    static final Comparator<ScheduledJob> HIGHEST_PRIORITY_FIRST =
            ((Comparator<ScheduledJob>) (a, b) -> Integer.compare(b.priority, a.priority))
                    .thenComparingLong(j -> j.dueAt).thenComparingLong(j -> j.seq);
    /** The stop sign a worker takes off the hand-off queue when the scheduler ends. */
    private static final ScheduledJob POISON = new ScheduledJob(JobSpec.of("poison", () -> {}), -1, 0);

    private final ReentrantLock lock = new ReentrantLock();
    private final Condition wake = lock.newCondition();    // the dispatcher sleeps here; signalled when its plan may be stale
    private final PriorityQueue<ScheduledJob> byTime = new PriorityQueue<>(BY_DUE);      // not due yet
    private PriorityQueue<ScheduledJob> ready = new PriorityQueue<>(HIGHEST_PRIORITY_FIRST); // due, waiting for a worker
    private final Map<String, ScheduledJob> jobs = new HashMap<>();
    private final Map<JobState, Integer> counts = new EnumMap<>(JobState.class);
    private final BlockingQueue<ScheduledJob> handoff = new LinkedBlockingQueue<>();     // dispatcher -> workers
    private final List<Thread> workerThreads = new ArrayList<>();
    private final List<RunListener> listeners = new CopyOnWriteArrayList<>();
    private final AtomicLong autoIds = new AtomicLong();
    private final int workers;
    private final Clock clock;
    private Thread dispatcher;
    private int running;                                   // handed to a worker and not finished; never above workers
    private int live;                                      // jobs not in a final state
    private long seq;
    private int maxPending = Integer.MAX_VALUE;           // back-pressure: the most unfinished jobs accepted at once
    private boolean accepting = true, stopNow;

    /** A scheduler with this many worker threads, reading time from this clock. start() launches the threads. */
    Scheduler(int workers, Clock clock) {
        if (workers < 1) throw new IllegalArgumentException("need at least one worker");
        this.workers = workers;
        this.clock = Objects.requireNonNull(clock);
        for (JobState s : JobState.values()) counts.put(s, 0);
    }

    /** Hand in the rule for which due job goes first when the workers are all busy (Strategy). Safe at any time. */
    void configure(Comparator<ScheduledJob> whichFirst) {
        lock.lock();
        try {
            PriorityQueue<ScheduledJob> q = new PriorityQueue<>(Objects.requireNonNull(whichFirst));
            q.addAll(ready);
            ready = q;
        } finally { lock.unlock(); }
    }
    /** Subscribe a listener: history, metrics, alerts. */
    void addListener(RunListener l) { listeners.add(Objects.requireNonNull(l)); }
    /**
     * Back-pressure at the door: refuse new jobs while `max` are unfinished (blocked, waiting or running), so a
     * flood of submissions becomes an error the caller sees, not a heap that grows until memory runs out.
     */
    void limitPending(int max) {
        if (max < 1) throw new IllegalArgumentException("limit must be positive");
        lock.lock();
        try { maxPending = max; } finally { lock.unlock(); }
    }

    /** Launch the dispatcher and the N workers. Without start(), a test drives pollDue and runJob by hand. */
    void start() {
        lock.lock();
        try {
            if (dispatcher != null) throw new IllegalStateException("already started");
            dispatcher = new Thread(this::dispatchLoop, "dispatcher");
            for (int i = 0; i < workers; i++) workerThreads.add(new Thread(this::workLoop, "worker-" + i));
        } finally { lock.unlock(); }
        dispatcher.start();
        for (Thread t : workerThreads) t.start();
    }

    // ---------------------------------------------------------------- submitting jobs

    /** Run task once, delayMs from now. Returns the job's id. */
    String schedule(Task task, long delayMs) {
        return schedule(JobSpec.of(nextId(), task).in(delayMs));
    }
    /** Run task every periodMs, counted from each planned start; the first run after initialDelayMs. */
    String scheduleAtFixedRate(Task task, long initialDelayMs, long periodMs) {
        return schedule(JobSpec.of(nextId(), task).in(initialDelayMs).every(new FixedRate(periodMs)));
    }
    /** Run task delayMs after each run ends; the first run after initialDelayMs. */
    String scheduleWithFixedDelay(Task task, long initialDelayMs, long delayMs) {
        return schedule(JobSpec.of(nextId(), task).in(initialDelayMs).every(new FixedDelay(delayMs)));
    }
    /** Submit one job with every setting. Refused, with nothing changed, if scheduleAll would refuse it. */
    String schedule(JobSpec spec) { return scheduleAll(List.of(spec)).get(0); }

    /**
     * Submit a batch whose jobs may wait for each other and for jobs already here. All or nothing: every check
     * (duplicate id, unknown or recurring prerequisite, a cycle) runs BEFORE anything is created, so a refused
     * batch leaves no trace.
     */
    List<String> scheduleAll(List<JobSpec> specs) {
        List<RunRecord> events = new ArrayList<>();
        List<String> ids = new ArrayList<>();
        lock.lock();
        try {
            if (!accepting) throw new RejectedExecutionException("the scheduler is shut down");
            if (specs.size() > maxPending - live)
                throw new RejectedExecutionException("full: " + live + " unfinished jobs, the limit is " + maxPending);
            Map<String, JobSpec> batch = new LinkedHashMap<>();
            for (JobSpec s : specs)
                if (jobs.containsKey(s.id) || batch.put(s.id, s) != null)
                    throw new IllegalArgumentException("duplicate job id " + s.id);
            for (JobSpec s : specs)
                for (String p : s.after) {
                    JobSpec inBatch = batch.get(p);
                    ScheduledJob old = jobs.get(p);
                    if (inBatch == null && old == null) throw new IllegalArgumentException(s.id + " waits for unknown job " + p);
                    if ((inBatch != null ? inBatch.trigger : old.trigger) != Trigger.ONCE)
                        throw new IllegalArgumentException(s.id + " cannot wait for a recurring job: " + p);
                }
            List<String> cycle = findCycle(batch);
            if (cycle != null)
                throw new IllegalArgumentException("cycle, each waits for the next: " + String.join(" -> ", cycle));

            // every check passed: only now does anything change
            long now = clock.nowMs();
            List<ScheduledJob> made = new ArrayList<>();
            for (JobSpec s : batch.values()) {
                long planned = s.atMs >= 0 ? s.atMs
                             : s.delayMs > Long.MAX_VALUE - now ? Long.MAX_VALUE : now + s.delayMs;   // no overflow into the past
                ScheduledJob j = new ScheduledJob(s, seq++, planned);
                j.dueAt = Math.max(j.plannedAt, now);
                j.state = JobState.BLOCKED;
                counts.merge(JobState.BLOCKED, 1, Integer::sum);
                live++;
                jobs.put(j.id, j);
                made.add(j);
                ids.add(j.id);
            }
            Map<ScheduledJob, String> doomed = new HashMap<>();
            for (ScheduledJob j : made)
                for (String p : j.after) {
                    ScheduledJob pre = jobs.get(p);
                    if (pre.state == JobState.DONE) continue;                // already finished: nothing to wait for
                    if (pre.state.isFinal()) { doomed.put(j, p); continue; } // failed, cancelled or skipped: j never runs
                    pre.dependents.add(j);
                    j.waitingFor++;
                }
            for (ScheduledJob j : made) {
                if (j.state != JobState.BLOCKED) continue;                   // skipped already, through an earlier one
                if (doomed.containsKey(j)) {
                    events.add(new RunRecord(j.id, 0, -1, now, "prerequisite " + doomed.get(j) + " did not succeed", JobState.SKIPPED));
                    endLocked(j, JobState.SKIPPED, events);
                } else if (j.waitingFor == 0) enqueueLocked(j);
            }
        } finally { lock.unlock(); }
        publish(events);
        return ids;
    }

    /** A fresh id for the short forms of schedule. */
    private String nextId() { return "job-" + autoIds.incrementAndGet(); }

    /**
     * Kahn's algorithm over the batch: keep removing jobs that wait for nothing still in the batch. Whatever
     * cannot be removed sits on or behind a cycle; walk "waits for" links from one of them until a job repeats.
     * Jobs already in the scheduler cannot close a cycle: they never wait for new ones. O(jobs + links).
     */
    private static List<String> findCycle(Map<String, JobSpec> batch) {
        Map<String, Integer> waits = new HashMap<>();              // prerequisites inside the batch not yet removed
        Map<String, List<String>> waiters = new HashMap<>();       // p -> the batch jobs waiting for p
        for (JobSpec s : batch.values()) {
            int n = 0;
            for (String p : new LinkedHashSet<>(s.after))
                if (batch.containsKey(p)) { n++; waiters.computeIfAbsent(p, k -> new ArrayList<>()).add(s.id); }
            waits.put(s.id, n);
        }
        Deque<String> free = new ArrayDeque<>();
        for (String id : batch.keySet()) if (waits.get(id) == 0) free.add(id);
        int removed = 0;
        while (!free.isEmpty()) {
            String id = free.poll();
            removed++;
            for (String w : waiters.getOrDefault(id, List.of()))
                if (waits.merge(w, -1, Integer::sum) == 0) free.add(w);
        }
        if (removed == batch.size()) return null;
        String at = null;                                          // every job left waits for another job left
        for (String id : batch.keySet()) if (waits.get(id) > 0) { at = id; break; }
        List<String> walk = new ArrayList<>();
        Map<String, Integer> seenAt = new HashMap<>();
        while (!seenAt.containsKey(at)) {
            seenAt.put(at, walk.size());
            walk.add(at);
            for (String p : batch.get(at).after)
                if (batch.containsKey(p) && waits.get(p) > 0) { at = p; break; }
        }
        List<String> cycle = new ArrayList<>(walk.subList(seenAt.get(at), walk.size()));
        cycle.add(at);
        return cycle;
    }

    // ---------------------------------------------------------------- cancel, and questions

    /**
     * Cancel a job. True if it had not started, so it never will, and the jobs waiting for it are skipped.
     * False if it is running (this run finishes, with no retry and no next run after it) or already finished.
     * Decided under the lock, so between cancel and the dispatcher exactly one wins.
     */
    boolean cancel(String id) {
        List<RunRecord> events = new ArrayList<>();
        boolean won = false;
        lock.lock();
        try {
            ScheduledJob j = jobs.get(id);
            if (j == null) return false;
            if (j.state == JobState.BLOCKED || j.state == JobState.SCHEDULED) {
                events.add(new RunRecord(j.id, j.attempts, -1, clock.nowMs(), "cancelled", JobState.CANCELLED));
                endLocked(j, JobState.CANCELLED, events);           // it stays in its heap until it reaches the top: lazy removal
                won = true;
            } else if (j.state == JobState.RUNNING) {
                j.cancelRequested = true;
            }
        } finally { lock.unlock(); }
        publish(events);
        return won;
    }

    /** A job's state, or null for an unknown id. O(1). */
    JobState status(String id) {
        lock.lock();
        try { ScheduledJob j = jobs.get(id); return j == null ? null : j.state; } finally { lock.unlock(); }
    }
    /** How many jobs are in each state, as one consistent snapshot. O(number of states). */
    Map<JobState, Integer> counts() {
        lock.lock();
        try { return new EnumMap<>(counts); } finally { lock.unlock(); }
    }
    /** The ids a job waits for, or an empty list for an unknown id. */
    List<String> prerequisitesOf(String id) {
        lock.lock();
        try { ScheduledJob j = jobs.get(id); return j == null ? List.of() : j.after; } finally { lock.unlock(); }
    }

    // ---------------------------------------------------------------- the dispatcher and the workers

    /**
     * The dispatcher's one step, pure and testable: every job whose time has come moves from the time heap
     * to the ready heap; then as many as there are free workers leave the ready heap, best first, as RUNNING.
     */
    private List<ScheduledJob> pollDueLocked(long now) {
        while (!byTime.isEmpty() && byTime.peek().dueAt <= now) {
            ScheduledJob j = byTime.poll();
            if (j.state == JobState.SCHEDULED) ready.add(j);        // a cancelled job is dropped here: lazy removal
        }
        List<ScheduledJob> out = new ArrayList<>();
        while (running < workers && !ready.isEmpty()) {
            ScheduledJob j = ready.poll();
            if (j.state != JobState.SCHEDULED) continue;           // cancelled while it waited for a worker
            move(j, JobState.RUNNING);                              // from this line on, cancel() loses
            j.attempts++;
            running++;
            out.add(j);
        }
        return out;
    }
    /** pollDueLocked under the lock: what the dispatcher does each time it wakes. Tests call it with a ManualClock. */
    List<ScheduledJob> pollDue(long now) {
        lock.lock();
        try { return pollDueLocked(now); } finally { lock.unlock(); }
    }

    /** How long the dispatcher may sleep: -1 = until signalled; otherwise ms until the earliest job is due. */
    private long sleepMsLocked(long now) {
        if (running >= workers) return -1;                          // no free worker: a finishing job will signal
        while (!byTime.isEmpty() && byTime.peek().state != JobState.SCHEDULED) byTime.poll();   // drop cancelled heads
        if (byTime.isEmpty()) return -1;                            // nothing waiting: schedule() will signal
        return byTime.peek().dueAt - now;                           // positive: pollDueLocked took everything due
    }

    /**
     * The dispatcher thread. Under the lock: take what is due, else decide how long to sleep and sleep in
     * the SAME locked step (await releases the lock while it waits and takes it back on waking). A new
     * earlier job signals it; a spurious wakeup just goes round the loop once more.
     */
    private void dispatchLoop() {
        lock.lock();
        try {
            while (!stopNow) {
                long now = clock.nowMs();
                List<ScheduledJob> due = pollDueLocked(now);
                if (!due.isEmpty()) { handoff.addAll(due); continue; }     // the hand-off queue never blocks
                if (!accepting && live == 0) break;                        // graceful shutdown: nothing is left
                long sleepMs = sleepMsLocked(now);
                if (sleepMs < 0) wake.await();
                else wake.awaitNanos(TimeUnit.MILLISECONDS.toNanos(sleepMs));
            }
        } catch (InterruptedException e) {
            // nobody interrupts the dispatcher on purpose; if someone does, stop cleanly like shutdownNow
        } finally {
            lock.unlock();
            for (int i = 0; i < workers; i++) handoff.add(POISON);        // one stop sign per worker
        }
    }

    /** A worker thread: take a job, run it, report; a stop sign ends it. A job's throw never ends it. */
    private void workLoop() {
        while (true) {
            ScheduledJob j;
            try { j = handoff.take(); } catch (InterruptedException e) { return; }   // shutdownNow while idle
            if (j == POISON) return;
            runJob(j);
            Thread.interrupted();          // an interrupt meant for that job must not stop this worker
        }
    }

    /** Run one handed-out job on the calling thread, outside the lock, then settle it under the lock. */
    void runJob(ScheduledJob j) {
        long startedAt = clock.nowMs();
        Exception error = null;
        try {
            j.task.run();
        } catch (Exception e) {
            error = e;
        } catch (Throwable t) {                                    // even an Error is one failed attempt:
            error = new ExecutionException(t);                     // the worker lives on and its slot comes back
        }
        List<RunRecord> events = new ArrayList<>();
        lock.lock();
        try {
            finishLocked(j, startedAt, clock.nowMs(), error, events);
        } finally { lock.unlock(); }
        publish(events);                                           // after the unlock, never inside it
    }

    /**
     * The order after every attempt, all under the lock: free the worker slot; then retry, next run, or end;
     * then settle the jobs that wait for it; then signal the dispatcher. A job goes back into a heap only
     * AFTER its run has ended, which is why two runs of one job can never overlap.
     */
    private void finishLocked(ScheduledJob j, long startedAt, long finishedAt, Exception error, List<RunRecord> events) {
        running--;
        int attempt = j.attempts;
        String err = error == null ? null : String.valueOf(error);
        boolean stop = stopNow || j.cancelRequested || (j.recurring() && !accepting);
        JobState next;
        try {
            long retryIn = (error != null && !stop) ? j.retry.delayMs(attempt, error) : RetryPolicy.GIVE_UP;
            if (retryIn >= 0) {                                    // the same planned run, one more attempt
                j.dueAt = finishedAt + retryIn;
                next = JobState.SCHEDULED;
            } else if (stop) {
                next = (error == null && !j.recurring()) ? JobState.DONE : JobState.CANCELLED;
            } else if (!j.recurring()) {
                next = error == null ? JobState.DONE : JobState.FAILED;
            } else {                                               // a failed run is recorded; the job goes on
                j.attempts = 0;
                long slot = j.misfire.place(j.trigger, j.trigger.next(j.plannedAt, finishedAt), finishedAt, finishedAt);
                if (slot == Trigger.NONE) next = JobState.DONE;
                else { j.plannedAt = slot; j.dueAt = Math.max(slot, finishedAt); next = JobState.SCHEDULED; }
            }
        } catch (RuntimeException brokenRule) {                    // a Trigger or RetryPolicy that throws ends the job
            err = (err == null ? "" : err + "; ") + "rule threw " + brokenRule;   // instead of stranding it RUNNING
            next = JobState.FAILED;                                // or killing this worker
        }
        j.lastError = err;
        events.add(new RunRecord(j.id, attempt, startedAt, finishedAt, err, next));
        if (next == JobState.SCHEDULED) enqueueLocked(j);
        else endLocked(j, next, events);
        wake.signal();                                             // a worker is free, and the heaps changed
    }

    /** Into the time heap as SCHEDULED; wake the dispatcher only if this job is now the earliest. */
    private void enqueueLocked(ScheduledJob j) {
        move(j, JobState.SCHEDULED);
        byTime.add(j);
        if (byTime.peek() == j) wake.signal();                     // the dispatcher may be asleep planning for a later job
    }

    /**
     * Move a job to a final state, then settle the jobs that wait for it: DONE counts each one down (the one
     * that reaches zero is scheduled, exactly once, because this runs under the lock); any other end skips
     * all of them, and everything behind them, breadth first.
     */
    private void endLocked(ScheduledJob j, JobState how, List<RunRecord> events) {
        move(j, how);
        live--;
        if (how == JobState.DONE) {
            for (ScheduledJob d : j.dependents)
                if (d.state == JobState.BLOCKED && --d.waitingFor == 0) enqueueLocked(d);
        } else {
            Deque<ScheduledJob> todo = new ArrayDeque<>(j.dependents);
            while (!todo.isEmpty()) {
                ScheduledJob d = todo.poll();
                if (d.state != JobState.BLOCKED) continue;         // already skipped or cancelled
                move(d, JobState.SKIPPED);
                live--;
                events.add(new RunRecord(d.id, 0, -1, clock.nowMs(),
                        "prerequisite " + j.id + " " + how.name().toLowerCase(), JobState.SKIPPED));
                todo.addAll(d.dependents);
            }
        }
        j.dependents.clear();
    }

    /** The one place a state changes: it checks the ALLOWED table and keeps the counts right. */
    private void move(ScheduledJob j, JobState to) {
        if (!JobState.ALLOWED.get(j.state).contains(to))
            throw new IllegalStateException(j.id + ": " + j.state + " -> " + to + " is not allowed");
        counts.merge(j.state, -1, Integer::sum);
        counts.merge(to, 1, Integer::sum);
        j.state = to;
    }

    /** Tell the listeners, after the lock is released. A listener that throws is ignored: it cannot break a job. */
    private void publish(List<RunRecord> events) {
        for (RunRecord r : events)
            for (RunListener l : listeners)
                try { l.onRun(r); } catch (RuntimeException e) { /* a broken listener must not break scheduling */ }
    }

    // ---------------------------------------------------------------- shutting down

    /**
     * Graceful: refuse new jobs. One-shot jobs already accepted still run at their time, with their retries
     * and prerequisites; recurring jobs stop after the run in progress. The threads end when nothing is left.
     */
    void shutdown() {
        List<RunRecord> events = new ArrayList<>();
        lock.lock();
        try {
            accepting = false;
            for (ScheduledJob j : jobs.values())
                if (j.recurring() && j.state == JobState.SCHEDULED) {
                    events.add(new RunRecord(j.id, j.attempts, -1, clock.nowMs(), "shutdown", JobState.CANCELLED));
                    endLocked(j, JobState.CANCELLED, events);
                }
            wake.signal();
        } finally { lock.unlock(); }
        publish(events);
    }

    /**
     * Now: refuse new jobs, cancel every job that has not started and return their ids, and interrupt the
     * workers so a running job that waits or sleeps stops early. Java cannot force a thread to stop: a job
     * that ignores interrupts runs to its end, and nothing follows it.
     */
    List<String> shutdownNow() {
        List<RunRecord> events = new ArrayList<>();
        List<String> neverStarted = new ArrayList<>();
        List<Thread> toInterrupt;
        lock.lock();
        try {
            accepting = false;
            stopNow = true;
            long now = clock.nowMs();
            List<ScheduledJob> notStarted = new ArrayList<>();
            handoff.drainTo(notStarted);                           // handed out, but no worker has picked them up
            for (ScheduledJob j : jobs.values())
                if (j.state == JobState.BLOCKED || j.state == JobState.SCHEDULED) notStarted.add(j);
            for (ScheduledJob j : notStarted) {
                if (j == POISON) { handoff.add(POISON); continue; } // a stop sign stays: a worker still needs it
                if (j.state == JobState.RUNNING) running--;        // it was handed out but never ran
                neverStarted.add(j.id);
                events.add(new RunRecord(j.id, j.attempts, -1, now, "shutdownNow", JobState.CANCELLED));
                move(j, JobState.CANCELLED);                       // directly, not through endLocked: every waiting job
                live--;                                            // is being cancelled here, so none is left to skip
            }
            wake.signal();
            toInterrupt = new ArrayList<>(workerThreads);
        } finally { lock.unlock(); }
        for (Thread t : toInterrupt) t.interrupt();
        publish(events);
        return neverStarted;
    }

    /** Wait up to timeoutMs (real time) for the dispatcher and every worker to end. True if they all did. */
    boolean awaitTermination(long timeoutMs) throws InterruptedException {
        List<Thread> all = new ArrayList<>();
        lock.lock();
        try { if (dispatcher != null) all.add(dispatcher); all.addAll(workerThreads); } finally { lock.unlock(); }
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        for (Thread t : all)
            if (!t.join(Duration.ofNanos(deadline - System.nanoTime()))) return false;
        return true;
    }
}

// ================================================================ a demo, then the race

/** Runs the scheduler twice: by hand with a ManualClock (timing, retries, prerequisites), then on real threads (the race). */
public class Main {
    /** Drive a scheduler with no threads: move the clock in steps and run whatever is due, on this thread. */
    static void drive(Scheduler s, ManualClock c, long untilMs, long stepMs) {
        while (c.nowMs() <= untilMs) {
            for (ScheduledJob j : s.pollDue(c.nowMs())) s.runJob(j);
            c.advance(stepMs);
        }
    }

    /** The timing rules by hand with a ManualClock, the early wake-up on real threads, then the 16-thread race. */
    public static void main(String[] args) throws Exception {
        System.out.println("-- by hand, with a ManualClock: nothing sleeps");
        ManualClock c = new ManualClock(0);
        Scheduler s = new Scheduler(4, c);
        List<String> starts = new ArrayList<>();
        s.schedule(JobSpec.of("rate", () -> { starts.add("" + c.nowMs()); c.advance(300); }).every(new FixedRate(1000)));
        drive(s, c, 2_900, 50);
        s.cancel("rate");
        System.out.println("   every run takes 300 ms. fixed rate 1000 starts at " + starts + ": no drift");
        starts.clear();
        c.set(10_000);
        s.schedule(JobSpec.of("delay", () -> { starts.add("" + c.nowMs()); c.advance(300); }).every(new FixedDelay(1000)));
        drive(s, c, 12_900, 50);
        s.cancel("delay");
        System.out.println("   fixed delay 1000 starts at " + starts + ": each 1000 after the last run ENDED");

        int[] tries = {0};
        s.schedule(JobSpec.of("charge", () -> { if (++tries[0] < 3) throw new IllegalStateException("gateway timeout"); })
                .in(0).retry(new ExponentialBackoff(1_000, 30_000, 5, null)));
        s.schedule(JobSpec.of("receipt", () -> starts.add("receipt@" + c.nowMs())).after("charge"));
        s.addListener(r -> { if (r.jobId().equals("charge")) System.out.println("   charge attempt " + r.attempt()
                + " at " + r.startedAt() + ": " + (r.error() == null ? "ok" : r.error()) + " -> " + r.then()); });
        long t = c.nowMs();
        drive(s, c, t + 4_000, 50);
        System.out.println("   receipt waited for charge: " + s.status("receipt") + ", " + starts.get(starts.size() - 1));

        List<String> built = new ArrayList<>();
        s.scheduleAll(List.of(
                JobSpec.of("build-a", () -> built.add("build-a")),
                JobSpec.of("build-b", () -> built.add("build-b")),
                JobSpec.of("test", () -> { throw new AssertionError("3 tests failed"); }).after("build-a", "build-b"),
                JobSpec.of("release", () -> built.add("release")).after("test"),
                JobSpec.of("docs", () -> built.add("docs")).after("build-a")));
        drive(s, c, c.nowMs() + 100, 10);
        System.out.println("   ran " + built + "; test " + s.status("test") + ", release " + s.status("release"));
        try {
            s.scheduleAll(List.of(JobSpec.of("x", () -> {}).after("z"), JobSpec.of("y", () -> {}).after("x"),
                                  JobSpec.of("z", () -> {}).after("y")));
        } catch (IllegalArgumentException e) {
            System.out.println("   refused: " + e.getMessage() + "; x exists? " + (s.status("x") != null));
        }

        System.out.println("-- on threads: an earlier job wakes the sleeping dispatcher");
        Clock real = Clock.system();
        Scheduler live = new Scheduler(2, real);
        live.start();
        CountDownLatch early = new CountDownLatch(1);
        live.schedule(() -> {}, 10_000);                           // the dispatcher sleeps towards this one
        Thread.sleep(50);
        long asked = real.nowMs();
        live.schedule(early::countDown, 100);                      // earlier than the head: it must signal
        early.await();
        System.out.println("   the 100 ms job ran after " + (real.nowMs() - asked) + " ms, not 10,000");
        live.shutdownNow();
        live.awaitTermination(2_000);

        // the race: 16 threads submit 500 jobs each at the same instant; 8 workers run them
        int submitters = 16, each = 500, total = submitters * each, pool = 8;
        Scheduler race = new Scheduler(pool, real);
        race.start();
        AtomicIntegerArray ran = new AtomicIntegerArray(total);
        AtomicInteger inFlight = new AtomicInteger(), mostAtOnce = new AtomicInteger();
        CountDownLatch go = new CountDownLatch(1), finished = new CountDownLatch(total);
        Random rnd = new Random(7);
        for (int t2 = 0; t2 < submitters; t2++) {
            int base = t2 * each;
            new Thread(() -> {
                try { go.await(); } catch (InterruptedException e) { return; }
                for (int k = 0; k < each; k++) {
                    int n = base + k;
                    race.schedule(JobSpec.of("r" + n, () -> {
                        mostAtOnce.accumulateAndGet(inFlight.incrementAndGet(), Math::max);
                        ran.incrementAndGet(n);
                        long until = System.nanoTime() + 50_000;           // 50 microseconds of real work
                        while (System.nanoTime() < until) Thread.onSpinWait();
                        inFlight.decrementAndGet();
                        finished.countDown();
                    }).in(rnd.nextInt(20)));
                }
            }).start();
        }
        go.countDown();
        boolean all = finished.await(30, TimeUnit.SECONDS);
        boolean exactlyOnce = all;
        for (int n = 0; n < total; n++) exactlyOnce &= ran.get(n) == 1;
        race.shutdown();
        race.awaitTermination(5_000);
        System.out.println("-- " + submitters + " threads submitted " + total + " jobs at once to " + pool + " workers");
        System.out.println("   every job ran exactly once: " + exactlyOnce + "; most running at one moment: "
                + mostAtOnce.get() + " (never above " + pool + "); DONE count " + race.counts().get(JobState.DONE));
    }
}
