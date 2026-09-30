import java.io.File;
import java.io.IOException;
import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is one twist; nothing here edits Main.java.

// ---- ext: cron, holidays and spreading ------------------------------------------------------------------
/**
 * A crontab line: "minute hour day-of-month month day-of-week", each field "*", a number, "a-b", "a,b,c" or
 * "x/n" (every n-th). next() walks forward from the last planned start, skipping a whole month, day or hour
 * at a time when that field does not match, so even "29 February" is found in a few thousand steps. The
 * walk happens in the job's time zone, so "30 9 * * 1-5" in Asia/Kolkata means 09:30 IST on weekdays.
 * As in classic cron, when both day fields are restricted, a day matching EITHER one counts.
 */
record Cron(BitSet minutes, BitSet hours, BitSet days, BitSet months, BitSet weekdays,
            boolean anyDay, boolean anyWeekday, ZoneId zone) implements Trigger {
    /** Parse a five-field line for a time zone; a bad field throws IllegalArgumentException. */
    static Cron parse(String line, ZoneId zone) {
        String[] f = line.trim().split("\\s+");
        if (f.length != 5) throw new IllegalArgumentException("cron needs 5 fields: " + line);
        return new Cron(field(f[0], 0, 59), field(f[1], 0, 23), field(f[2], 1, 31), field(f[3], 1, 12),
                        field(f[4], 0, 6), f[2].equals("*"), f[4].equals("*"), zone);
    }
    /** One field as the set of values it allows. */
    private static BitSet field(String s, int lo, int hi) {
        BitSet b = new BitSet();
        for (String part : s.split(",")) {
            int step = 1, slash = part.indexOf('/');
            if (slash >= 0) { step = Integer.parseInt(part.substring(slash + 1)); part = part.substring(0, slash); }
            int a, z;
            if (part.equals("*")) { a = lo; z = hi; }
            else if (part.contains("-")) { a = Integer.parseInt(part.split("-")[0]); z = Integer.parseInt(part.split("-")[1]); }
            else { a = Integer.parseInt(part); z = slash >= 0 ? hi : a; }      // "5/10" = 5, 15, 25 ...
            if (a < lo || z > hi || a > z || step < 1) throw new IllegalArgumentException("bad cron field " + s);
            for (int v = a; v <= z; v += step) b.set(v);
        }
        return b;
    }
    /** Does this calendar day match both day fields (or either, when both are restricted)? */
    private boolean dayMatches(ZonedDateTime t) {
        boolean d = days.get(t.getDayOfMonth()), w = weekdays.get(t.getDayOfWeek().getValue() % 7);
        return (anyDay || anyWeekday) ? d && w : d || w;
    }
    /** The first matching minute strictly after plannedAt, in the job's zone; NONE if none in about 5 years. */
    public long next(long plannedAt, long finishedAt) {
        ZonedDateTime t = Instant.ofEpochMilli(plannedAt).atZone(zone).truncatedTo(ChronoUnit.MINUTES).plusMinutes(1);
        for (int steps = 0; steps < 100_000; steps++) {
            if (!months.get(t.getMonthValue())) t = t.plusMonths(1).withDayOfMonth(1).truncatedTo(ChronoUnit.DAYS);
            else if (!dayMatches(t)) t = t.plusDays(1).truncatedTo(ChronoUnit.DAYS);
            else if (!hours.get(t.getHour())) t = t.plusHours(1).truncatedTo(ChronoUnit.HOURS);
            else if (!minutes.get(t.getMinute())) t = t.plusMinutes(1);
            else return t.toInstant().toEpochMilli();
        }
        return NONE;
    }
}

/**
 * Decorator: the same trigger, minus the holidays. A run that would fall on a holiday moves to the wrapped
 * trigger's next run instead. A cron line cannot say "not on Diwali"; this wraps any trigger and edits none.
 */
record SkipHolidays(Trigger inner, ZoneId zone, Set<LocalDate> holidays) implements Trigger {
    /** The wrapped trigger's next run that is not on a holiday (at most a year of tries, then NONE). */
    public long next(long plannedAt, long finishedAt) {
        long t = inner.next(plannedAt, finishedAt);
        for (int i = 0; i < 366 && t != NONE; i++) {
            if (!holidays.contains(Instant.ofEpochMilli(t).atZone(zone).toLocalDate())) return t;
            t = inner.next(t, t);
        }
        return NONE;
    }
}

/**
 * Decorator: shift every run of the wrapped trigger by a fixed offset taken from the job's id (what Jenkins
 * calls "H"). 5,000 jobs written as "09:30" then start spread over a window instead of in one second, and
 * because the offset is the same every time, the schedule never drifts. Build it with Spread.of(id, ...).
 */
record Spread(Trigger inner, long offsetMs) implements Trigger {
    /** A spread whose offset in [0, windowMs) comes from the id's hash: the same id, the same offset, always. */
    static Spread of(String jobId, Trigger inner, long windowMs) {
        return new Spread(inner, Math.floorMod(jobId.hashCode() * 0x9E3779B1L, windowMs));
    }
    /** The wrapped trigger's next run after the unshifted plannedAt, shifted again. */
    public long next(long plannedAt, long finishedAt) {
        long t = inner.next(plannedAt - offsetMs, finishedAt);
        return t == NONE ? NONE : t + offsetMs;
    }
}

/**
 * Swiggy's cron: the job is a unix command. It runs as its own process, so a time limit can really stop it
 * (destroyForcibly), which a Java thread never can. A non-zero exit code or a timeout is a failed attempt,
 * so the job's RetryPolicy applies. Output goes to a log file, never into the scheduler's memory.
 */
record CommandTask(List<String> command, long timeoutMs, File log) implements Task {
    /** Start the process, wait up to timeoutMs, kill it if it overruns; throw on a timeout or a non-zero exit. */
    public void run() throws Exception {
        ProcessBuilder pb = new ProcessBuilder(command).redirectErrorStream(true);
        pb.redirectOutput(log == null ? ProcessBuilder.Redirect.DISCARD : ProcessBuilder.Redirect.appendTo(log));
        Process p = pb.start();
        try {
            if (!p.waitFor(timeoutMs, TimeUnit.MILLISECONDS)) {
                p.destroyForcibly();
                throw new TimeoutException(command + " ran longer than " + timeoutMs + " ms");
            }
            if (p.exitValue() != 0) throw new IOException(command + " exited with " + p.exitValue());
        } catch (InterruptedException e) {
            p.destroyForcibly();                               // shutdownNow: the process goes down with the job
            throw e;
        }
    }
}

// ---- ext: schedules from text ----------------------------------------------------------------------------
/**
 * Factory: once schedules arrive as text (a config file, an API field), one place turns text into a Trigger.
 * A new kind is one more case here, and no caller changes. Accepts "every 10s", "after-each 30s" (fixed
 * delay), "cron 30 9 * * 1-5 Asia/Kolkata".
 */
final class Triggers {
    /** Static helpers only. */
    private Triggers() {}
    /** Parse one schedule, or throw IllegalArgumentException naming what was wrong. */
    static Trigger parse(String text) {
        String[] w = text.trim().split("\\s+");
        return switch (w[0]) {
            case "every" -> new FixedRate(millis(w[1]));
            case "after-each" -> new FixedDelay(millis(w[1]));
            case "cron" -> {
                if (w.length != 7) throw new IllegalArgumentException("cron needs 5 fields and a zone: " + text);
                yield Cron.parse(String.join(" ", Arrays.copyOfRange(w, 1, 6)), ZoneId.of(w[6]));
            }
            default -> throw new IllegalArgumentException("unknown schedule: " + text);
        };
    }
    /** "500ms", "10s", "5m", "2h" as milliseconds. */
    static long millis(String s) {
        if (s.endsWith("ms")) return Long.parseLong(s.substring(0, s.length() - 2));
        long n = Long.parseLong(s.substring(0, s.length() - 1));
        return switch (s.charAt(s.length() - 1)) {
            case 's' -> n * 1_000; case 'm' -> n * 60_000; case 'h' -> n * 3_600_000;
            default -> throw new IllegalArgumentException("bad duration " + s);
        };
    }
}

// ---- ext: aging -----------------------------------------------------------------------------------------
/**
 * Priority with aging, handed to Scheduler.configure(...): every stepMs a job has been due counts as one level
 * of priority. Two waiting jobs age at the same speed, so their order never changes while they wait, which
 * keeps the heap valid. With stepMs = 10 s, a priority-1 job due 30 s ago beats a priority-3 job due now: a
 * later job overtakes it only if it became due less than (its priority - 1) x 10 s later. No starvation.
 */
final class Aging {
    /** Static helpers only. */
    private Aging() {}
    /** Smallest key first: dueAt minus priority x stepMs; then submission order. */
    static Comparator<ScheduledJob> comparator(long stepMs) {
        return Comparator.comparingLong((ScheduledJob j) -> j.dueAt - j.priority * stepMs).thenComparingLong(j -> j.seq);
    }
}

// ---- ext: completion plan -------------------------------------------------------------------------------
/**
 * Brex's third milestone: "what must finish, in what order, before X can run?" Walk X's prerequisites
 * depth first and write a job down only after everything it waits for, so the list is a valid order that
 * ends with X. DONE jobs are left out. An explicit stack instead of recursion, so a 20,000-job chain is fine.
 */
final class CompletionPlan {
    /** Static helpers only. */
    private CompletionPlan() {}
    /** A valid order of every unfinished job X needs, ending with X. */
    static List<String> of(Scheduler s, String id) {
        List<String> plan = new ArrayList<>();
        Set<String> seen = new HashSet<>(List.of(id));
        Deque<String> path = new ArrayDeque<>(List.of(id));
        Deque<Iterator<String>> todo = new ArrayDeque<>(List.of(s.prerequisitesOf(id).iterator()));
        while (!path.isEmpty()) {
            Iterator<String> it = todo.peek();
            if (it.hasNext()) {
                String p = it.next();
                if (seen.add(p) && s.status(p) != JobState.DONE) { path.push(p); todo.push(s.prerequisitesOf(p).iterator()); }
            } else {
                todo.pop();
                plan.add(path.pop());                          // everything it waits for is already written down
            }
        }
        return plan;
    }
}

// ---- ext: timeouts --------------------------------------------------------------------------------------
/**
 * A time limit per job. Java cannot kill a thread, so a timeout is a polite interrupt: a watchdog (our own
 * Scheduler) interrupts the worker when time is up; the job sees InterruptedException in its sleep, wait
 * or blocking read, and the attempt fails with a TimeoutException, so the RetryPolicy applies. The guard
 * makes "time is up" and "the run ended" exclusive, so a late watchdog never interrupts the NEXT job on that
 * worker. A job that never blocks and never checks for interrupts cannot be stopped: run it as a process.
 */
final class TimeoutTask implements Task {
    private final Task inner;
    private final long limitMs;
    private final Scheduler watchdog;

    TimeoutTask(Task inner, long limitMs, Scheduler watchdog) { this.inner = inner; this.limitMs = limitMs; this.watchdog = watchdog; }
    /** Run the inner task with a watchdog armed; turn the watchdog's interrupt into a TimeoutException. */
    public void run() throws Exception {
        Thread me = Thread.currentThread();
        Object guard = new Object();
        boolean[] endedOrFired = {false, false};                  // {the run ended, the watchdog fired}
        String dog = watchdog.schedule(() -> {
            synchronized (guard) { if (!endedOrFired[0]) { endedOrFired[1] = true; me.interrupt(); } }
        }, limitMs);
        try {
            inner.run();
        } catch (Exception e) {
            synchronized (guard) {
                if (endedOrFired[1]) {
                    TimeoutException t = new TimeoutException("ran longer than " + limitMs + " ms");
                    t.initCause(e);
                    throw t;
                }
            }
            throw e;                                              // a real failure, or shutdownNow's interrupt
        } finally {
            synchronized (guard) { endedOrFired[0] = true; }
            watchdog.cancel(dog);
        }
    }
}

// ---- ext: machines with capabilities --------------------------------------------------------------------
/** A machine jobs run on: the capabilities it has ("gpu", "ssd") and its size. */
record Machine(String name, Set<String> tags, int cpus, int ramGb) {}
/** What one job needs from a machine. */
record Needs(Set<String> tags, int cpus, int ramGb) {}
/** A job waiting for a machine: highest priority first, then first come. */
record PendingJob(String id, Needs needs, int priority, long seq) {}

/**
 * Microsoft's and Arcesium's version: a job may run only on a machine with every capability it needs and
 * enough free CPU and RAM. Placement runs under one lock, like dispatch: waiting jobs in priority order, each
 * on the fitting machine that wastes least (fewest capabilities it does not need, then least CPU and RAM left
 * over), so the GPU machine stays free for GPU work. A job that fits nowhere yet waits, and smaller jobs
 * behind it may go first (backfilling). A job that fits no machine at all is refused at submit.
 */
final class Placement {
    private final List<Machine> machines;
    private final Map<String, int[]> free = new HashMap<>();              // machine -> {cpus, ram} free now
    private final Map<String, String> placedOn = new HashMap<>();         // job -> machine
    private final Map<String, Needs> needsOf = new HashMap<>();
    private final PriorityQueue<PendingJob> waiting = new PriorityQueue<>(
            Comparator.comparingInt((PendingJob p) -> -p.priority()).thenComparingLong(PendingJob::seq));
    private final ReentrantLock lock = new ReentrantLock();
    private long seq;

    Placement(List<Machine> machines) {
        this.machines = List.copyOf(machines);
        for (Machine m : machines) free.put(m.name(), new int[] {m.cpus(), m.ramGb()});
    }
    /** Queue a job and place whatever fits now. Returns the new placements, job -> machine. */
    Map<String, String> submit(String id, Needs needs, int priority) {
        lock.lock();
        try {
            if (machines.stream().noneMatch(m -> fits(m, needs, m.cpus(), m.ramGb())))
                throw new IllegalArgumentException(id + " fits no machine: " + needs);
            needsOf.put(id, needs);
            waiting.add(new PendingJob(id, needs, priority, seq++));
            return placeLocked();
        } finally { lock.unlock(); }
    }
    /** A job ended: give its CPU and RAM back, then place whatever now fits. */
    Map<String, String> release(String id) {
        lock.lock();
        try {
            String m = placedOn.remove(id);
            if (m == null) return Map.of();
            Needs n = needsOf.remove(id);
            free.get(m)[0] += n.cpus();
            free.get(m)[1] += n.ramGb();
            return placeLocked();
        } finally { lock.unlock(); }
    }
    /** Does this machine have the capabilities, and this much CPU and RAM free? */
    private static boolean fits(Machine m, Needs n, int freeCpu, int freeRam) {
        return m.tags().containsAll(n.tags()) && freeCpu >= n.cpus() && freeRam >= n.ramGb();
    }
    /** Every waiting job, best first, onto the fitting machine that wastes least; the rest keep waiting. */
    private Map<String, String> placeLocked() {
        Map<String, String> placed = new LinkedHashMap<>();
        List<PendingJob> notYet = new ArrayList<>();
        while (!waiting.isEmpty()) {
            PendingJob p = waiting.poll();
            Machine best = null;
            for (Machine m : machines) {
                int[] f = free.get(m.name());
                if (!fits(m, p.needs(), f[0], f[1])) continue;
                if (best == null || waste(m, p.needs()) < waste(best, p.needs())) best = m;
            }
            if (best == null) { notYet.add(p); continue; }
            free.get(best.name())[0] -= p.needs().cpus();
            free.get(best.name())[1] -= p.needs().ramGb();
            placedOn.put(p.id(), best.name());
            placed.put(p.id(), best.name());
        }
        waiting.addAll(notYet);
        return placed;
    }
    /** How much a placement wastes: unneeded capabilities count most, then CPU left over, then RAM left over. */
    private long waste(Machine m, Needs n) {
        int[] f = free.get(m.name());
        long extraTags = m.tags().stream().filter(t -> !n.tags().contains(t)).count();
        return extraTags * 1_000_000_000L + (f[0] - n.cpus()) * 100_000L + (f[1] - n.ramGb());
    }
}

/**
 * Per-type limits ("at most 2 report jobs at once, whatever else runs"): a bulkhead, one small Scheduler per
 * type with that many workers, so a flood of reports can never take the workers the payment jobs need.
 * Scheduler does not change at all. The price: prerequisites cannot cross types.
 */
final class Bulkheads {
    private final Map<String, Scheduler> byType = new HashMap<>();

    Bulkheads(Map<String, Integer> limits, Clock clock) {
        limits.forEach((type, n) -> { Scheduler s = new Scheduler(n, clock); s.start(); byType.put(type, s); });
    }
    /** Submit a job to its type's own scheduler. */
    String schedule(String type, JobSpec spec) {
        Scheduler s = byType.get(type);
        if (s == null) throw new IllegalArgumentException("no bulkhead for type " + type);
        return s.schedule(spec);
    }
    /** Graceful shutdown of every type, then wait for all of them. */
    void shutdownAndWait(long timeoutMs) throws InterruptedException {
        for (Scheduler s : byType.values()) s.shutdown();
        for (Scheduler s : byType.values()) s.awaitTermination(timeoutMs);
    }
}

// ---- ext: persistence and many instances ----------------------------------------------------------------
/**
 * The jobs table behind an interface (a repository), so memory and a database are interchangeable. The
 * claim is the database's compare-and-set: one conditional UPDATE decides which instance gets a job, the way
 * the lock did inside one process. A lease (a claim that expires) means a dead instance's job comes back.
 */
interface JobStore {
    /** INSERT INTO jobs(id, due_at, state) VALUES (?, ?, 'SCHEDULED') */
    void add(String id, long dueAt);
    /** SELECT id FROM jobs WHERE state = 'SCHEDULED' AND due_at &lt;= :now AND lease_until &lt; :now ORDER BY due_at LIMIT :n */
    List<String> due(long now, int limit);
    /** UPDATE jobs SET owner = ?, lease_until = :now + lease WHERE id = ? AND state = 'SCHEDULED' AND lease_until &lt; :now -- 1 row = won */
    boolean claim(String id, String owner, long now, long leaseMs);
    /** UPDATE jobs SET state = 'DONE' WHERE id = ? AND owner = ? AND lease_until &gt;= :now -- 0 rows = the lease was lost */
    boolean complete(String id, String owner, long now);
}

/** One row of the table. */
record JobRow(String id, long dueAt, String state, String owner, long leaseUntil) {}

/** The table in memory: ConcurrentHashMap.compute makes each conditional update atomic, like a row lock. */
final class InMemoryJobStore implements JobStore {
    private final ConcurrentHashMap<String, JobRow> rows = new ConcurrentHashMap<>();

    /** A new row, never leased. */
    public void add(String id, long dueAt) { rows.put(id, new JobRow(id, dueAt, "SCHEDULED", null, Long.MIN_VALUE)); }
    /** The due, unleased rows, earliest first (a scan here; an index on (state, due_at) in a database). */
    public List<String> due(long now, int limit) {
        return rows.values().stream().filter(r -> r.state().equals("SCHEDULED") && r.dueAt() <= now && r.leaseUntil() < now)
                .sorted(Comparator.comparingLong(JobRow::dueAt)).limit(limit).map(JobRow::id).toList();
    }
    /** The conditional update: only one instance can move a row from free to leased. */
    public boolean claim(String id, String owner, long now, long leaseMs) {
        boolean[] won = {false};
        rows.computeIfPresent(id, (k, r) -> {
            if (!r.state().equals("SCHEDULED") || r.leaseUntil() >= now) return r;
            won[0] = true;
            return new JobRow(k, r.dueAt(), "SCHEDULED", owner, now + leaseMs);
        });
        return won[0];
    }
    /** DONE only for the instance that still holds the lease. */
    public boolean complete(String id, String owner, long now) {
        boolean[] ok = {false};
        rows.computeIfPresent(id, (k, r) -> {
            if (!owner.equals(r.owner()) || r.leaseUntil() < now) return r;
            ok[0] = true;
            return new JobRow(k, r.dueAt(), "DONE", owner, r.leaseUntil());
        });
        return ok[0];
    }
}

/**
 * One scheduler instance of many (three machines, one jobs table). Each poll claims due rows and runs them.
 * An instance that dies mid-run just lets its lease expire, and another instance claims the job again:
 * at-least-once, never lost. So a job must be idempotent (running it twice has the effect of running it
 * once): key its side effect by the job's id.
 */
final class Instance {
    private final String name;
    private final JobStore store;
    private final Map<String, Task> tasks;
    private final long leaseMs;

    Instance(String name, JobStore store, Map<String, Task> tasks, long leaseMs) {
        this.name = name; this.store = store; this.tasks = tasks; this.leaseMs = leaseMs;
    }
    /** Claim and run whatever is due now. dieBeforeDone simulates a crash after the work, before DONE is written. */
    int pollOnce(long now, boolean dieBeforeDone) {
        int ran = 0;
        for (String id : store.due(now, 50)) {
            if (!store.claim(id, name, now, leaseMs)) continue;    // another instance won this one
            try { tasks.get(id).run(); } catch (Exception e) { continue; }   // a failed run: the lease expires, it is retried
            if (dieBeforeDone) return ran;                        // the email went out, DONE was never written
            store.complete(id, name, now);
            ran++;
        }
        return ran;
    }
}

// ---- ext: history ---------------------------------------------------------------------------------------
/**
 * Media.net's "history": the last N run records, and the latest record per job ("what happened to job X?").
 * A listener, so the scheduler does not change. It is called from many worker threads after the lock, so it
 * has its own small lock. Bounded: the oldest record and the least recently seen job fall off.
 */
final class RunHistory implements RunListener {
    private final int capacity;
    private final ArrayDeque<RunRecord> recent = new ArrayDeque<>();
    private final LinkedHashMap<String, RunRecord> latest;

    RunHistory(int capacity) {
        this.capacity = capacity;
        this.latest = new LinkedHashMap<>(16, 0.75f, true) {
            @Override protected boolean removeEldestEntry(Map.Entry<String, RunRecord> e) { return size() > RunHistory.this.capacity; }
        };
    }
    /** Keep the record; O(1). */
    public synchronized void onRun(RunRecord r) {
        if (recent.size() == capacity) recent.removeFirst();
        recent.addLast(r);
        latest.put(r.jobId(), r);
    }
    /** The last n records, oldest first. */
    synchronized List<RunRecord> last(int n) {
        List<RunRecord> all = new ArrayList<>(recent);
        return all.subList(Math.max(0, all.size() - n), all.size());
    }
    /** The latest record for one job, or null. O(1). */
    synchronized RunRecord latest(String jobId) { return latest.get(jobId); }
}

// ---- ext: what the JDK already gives you ----------------------------------------------------------------
/**
 * The same core on the JDK's own parts, about 25 lines: DelayQueue is a heap whose take() blocks until the
 * head's time has come (it does the wait-and-signal inside, and wakes early for an earlier item), and N
 * workers take from it. What it leaves you to write is the interview: cancel, retries, prerequisites, what
 * happens to missed runs, shutdown policies, and a job that throws.
 */
final class DelayQueueScheduler {
    /** One queued job: its task and when it may run; Delayed tells DelayQueue how long is left. */
    private record Item(Runnable task, long dueNanos) implements Delayed {
        /** How long until due. */
        public long getDelay(TimeUnit unit) { return unit.convert(dueNanos - System.nanoTime(), TimeUnit.NANOSECONDS); }
        /** Earlier due first. */
        public int compareTo(Delayed o) { return Long.compare(dueNanos, ((Item) o).dueNanos); }
    }
    private final DelayQueue<Item> queue = new DelayQueue<>();
    private final List<Thread> workers = new ArrayList<>();

    DelayQueueScheduler(int n) {
        for (int i = 0; i < n; i++) {
            Thread t = new Thread(() -> {
                try {
                    while (true) {
                        Item it = queue.take();                   // blocks until the head is due
                        try { it.task().run(); } catch (RuntimeException e) { /* keep the worker alive */ }
                    }
                } catch (InterruptedException e) { /* shutdown */ }
            });
            workers.add(t);
            t.start();
        }
    }
    /** Run task once, delayMs from now. */
    void schedule(Runnable task, long delayMs) { queue.add(new Item(task, System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(delayMs))); }
    /** Stop the workers; jobs still queued are dropped. */
    void shutdownNow() { workers.forEach(Thread::interrupt); }
}

// ---- ext: sharding --------------------------------------------------------------------------------------
/**
 * Rung 1 of the ladder: K independent schedulers; a job goes to shard hash(key) mod K. K locks, K heaps, K
 * dispatchers, so submitting threads rarely meet. The price: priority holds only inside a shard, and a
 * batch with prerequisites must go to one shard, so it is routed by one key.
 */
final class ShardedScheduler {
    private final Scheduler[] shards;
    private final ConcurrentHashMap<String, Scheduler> home = new ConcurrentHashMap<>();   // job id -> its shard, for cancel

    ShardedScheduler(int k, int workersEach, Clock clock) {
        shards = new Scheduler[k];
        for (int i = 0; i < k; i++) { shards[i] = new Scheduler(workersEach, clock); shards[i].start(); }
    }
    /** The shard for a routing key. */
    private Scheduler shardFor(String key) { return shards[Math.floorMod(key.hashCode(), shards.length)]; }
    /** One job, routed by its own id. */
    String schedule(JobSpec spec) { return scheduleAll(spec.id, List.of(spec)).get(0); }
    /** A batch that may have prerequisites, all to the shard of one routing key. */
    List<String> scheduleAll(String routingKey, List<JobSpec> batch) {
        Scheduler s = shardFor(routingKey);
        List<String> ids = s.scheduleAll(batch);
        for (String id : ids) home.put(id, s);
        return ids;
    }
    /** Cancel on the job's own shard. */
    boolean cancel(String id) { Scheduler s = home.get(id); return s != null && s.cancel(id); }
    /** Graceful shutdown of every shard, then wait. */
    void shutdownAndWait(long timeoutMs) throws InterruptedException {
        for (Scheduler s : shards) s.shutdown();
        for (Scheduler s : shards) s.awaitTermination(timeoutMs);
    }
}

/** Runs every extension once, so the page's follow-up code is code that has actually executed. */
class ExtDemo {
    /** Each block prints what its follow-up on page 05 claims. */
    public static void main(String[] args) throws Exception {
        ZoneId ist = ZoneId.of("Asia/Kolkata");
        long friday = LocalDateTime.of(2026, 10, 30, 10, 0).atZone(ist).toInstant().toEpochMilli();

        System.out.println("-- cron, holidays, spreading");
        Trigger weekdays930 = Cron.parse("30 9 * * 1-5", ist);
        long n1 = weekdays930.next(friday, friday);
        System.out.println("   after Fri 30 Oct 10:00, \"30 9 * * 1-5\" runs " + Instant.ofEpochMilli(n1).atZone(ist));
        Trigger noHoliday = new SkipHolidays(weekdays930, ist, Set.of(LocalDate.of(2026, 11, 2)));
        System.out.println("   with Mon 2 Nov a holiday: " + Instant.ofEpochMilli(noHoliday.next(friday, friday)).atZone(ist));
        Trigger spread = Spread.of("nightly-report", noHoliday, 600_000);
        System.out.println("   spread by the job's id over 10 minutes: " + Instant.ofEpochMilli(spread.next(friday, friday)).atZone(ist));
        long feb29 = Cron.parse("0 0 29 2 *", ist).next(friday, friday);
        System.out.println("   \"0 0 29 2 *\" next: " + Instant.ofEpochMilli(feb29).atZone(ist).toLocalDate());
        System.out.println("   Triggers.parse(\"every 10s\") = " + Triggers.parse("every 10s"));

        ManualClock c = new ManualClock(friday);
        Scheduler cron = new Scheduler(2, c);
        List<String> ran = new ArrayList<>();
        Trigger t = Triggers.parse("cron 30 9 * * 1-5 Asia/Kolkata");
        cron.schedule(JobSpec.of("standup-mail", () -> ran.add(Instant.ofEpochMilli(c.nowMs()).atZone(ist).toString()))
                .at(t.next(c.nowMs(), c.nowMs())).every(t));
        for (int day = 0; day < 5; day++) {                          // five days, driven by hand, one minute at a time
            for (int m = 0; m < 24 * 60; m++) { for (ScheduledJob j : cron.pollDue(c.nowMs())) cron.runJob(j); c.advance(60_000); }
        }
        System.out.println("   five days of \"weekdays 09:30\" ran on: " + ran.stream().map(s -> s.substring(0, 16)).toList());
        cron.shutdownNow();

        File log = File.createTempFile("cron", ".log");
        new CommandTask(List.of("sh", "-c", "echo hello from cron"), 2_000, log).run();
        String exit3 = "", slow = "";
        try { new CommandTask(List.of("sh", "-c", "exit 3"), 2_000, null).run(); } catch (IOException e) { exit3 = e.getMessage(); }
        try { new CommandTask(List.of("sleep", "5"), 100, null).run(); } catch (TimeoutException e) { slow = e.getMessage(); }
        System.out.println("   a command: wrote \"" + new String(java.nio.file.Files.readAllBytes(log.toPath())).trim()
                + "\"; " + exit3 + "; " + slow);
        log.delete();

        System.out.println("-- aging: a low-priority job is not starved");
        ManualClock ca = new ManualClock(0);
        Scheduler aged = new Scheduler(1, ca);
        aged.configure(Aging.comparator(10_000));
        List<String> order = new ArrayList<>();
        aged.schedule(JobSpec.of("old-low", () -> order.add("old-low (p1, due at 0 s)")).priority(1));
        ca.set(25_000);
        aged.schedule(JobSpec.of("young-low", () -> order.add("young-low (p1, due at 25 s)")).priority(1));
        ca.set(30_000);
        aged.schedule(JobSpec.of("high", () -> order.add("high (p3, due at 30 s)")).priority(3));
        for (ScheduledJob j : aged.pollDue(ca.nowMs())) aged.runJob(j);
        for (ScheduledJob j : aged.pollDue(ca.nowMs())) aged.runJob(j);
        for (ScheduledJob j : aged.pollDue(ca.nowMs())) aged.runJob(j);
        System.out.println("   one worker, step 10 s: " + order);

        System.out.println("-- completion plan (Brex)");
        ManualClock cp = new ManualClock(0);
        Scheduler plan = new Scheduler(1, cp);
        plan.scheduleAll(List.of(JobSpec.of("yoga", () -> {}), JobSpec.of("coffee", () -> {}).after("yoga"),
                JobSpec.of("toast", () -> {}).after("yoga"), JobSpec.of("brainstorm", () -> {}).after("coffee", "toast")));
        System.out.println("   before brainstorm: " + CompletionPlan.of(plan, "brainstorm"));

        System.out.println("-- timeouts");
        Scheduler watchdog = new Scheduler(1, Clock.system());
        watchdog.start();
        Scheduler work = new Scheduler(1, Clock.system());
        work.start();
        CountDownLatch settled = new CountDownLatch(2);
        work.addListener(r -> { System.out.println("   " + r.jobId() + ": " + (r.error() == null ? "ok" : r.error()) + " -> " + r.then()); settled.countDown(); });
        work.schedule(JobSpec.of("hangs", new TimeoutTask(() -> Thread.sleep(10_000), 100, watchdog)));
        work.schedule(JobSpec.of("quick", new TimeoutTask(() -> Thread.sleep(10), 1_000, watchdog)));
        settled.await(5, TimeUnit.SECONDS);
        work.shutdown();
        work.awaitTermination(2_000);
        watchdog.shutdownNow();
        watchdog.awaitTermination(2_000);

        System.out.println("-- machines with capabilities (Microsoft, Arcesium)");
        Placement pl = new Placement(List.of(new Machine("gpu-1", Set.of("gpu"), 16, 128),
                                             new Machine("cpu-1", Set.of(), 8, 32), new Machine("cpu-2", Set.of(), 32, 256)));
        System.out.println("   train (gpu, 8 cpu) -> " + pl.submit("train", new Needs(Set.of("gpu"), 8, 64), 5));
        System.out.println("   etl (4 cpu, 16 GB) -> " + pl.submit("etl", new Needs(Set.of(), 4, 16), 1));
        System.out.println("   big (24 cpu, 200 GB) -> " + pl.submit("big", new Needs(Set.of(), 24, 200), 3));
        System.out.println("   big2 (24 cpu, 200 GB) waits -> " + pl.submit("big2", new Needs(Set.of(), 24, 200), 3));
        System.out.println("   big finishes -> " + pl.release("big"));
        String refusedMsg = "";
        try { pl.submit("tpu-job", new Needs(Set.of("tpu"), 1, 1), 1); } catch (IllegalArgumentException e) { refusedMsg = e.getMessage(); }
        System.out.println("   " + refusedMsg);
        Bulkheads bh = new Bulkheads(Map.of("report", 2, "payment", 4), Clock.system());
        AtomicInteger inReports = new AtomicInteger(), mostReports = new AtomicInteger();
        for (int i = 0; i < 10; i++)
            bh.schedule("report", JobSpec.of("report-" + i, () -> {
                mostReports.accumulateAndGet(inReports.incrementAndGet(), Math::max);
                Thread.sleep(10);
                inReports.decrementAndGet();
            }));
        bh.shutdownAndWait(5_000);
        System.out.println("   10 reports through a bulkhead of 2: the most at once was " + mostReports.get());

        System.out.println("-- persistence: 3 instances, one jobs table");
        InMemoryJobStore store = new InMemoryJobStore();
        Map<String, Task> tasks = new ConcurrentHashMap<>();
        ConcurrentHashMap<String, Boolean> effects = new ConcurrentHashMap<>();   // the idempotent side effect
        AtomicInteger executions = new AtomicInteger();
        for (int i = 0; i < 300; i++) {
            String id = "email-" + i;
            store.add(id, 0);
            tasks.put(id, () -> { executions.incrementAndGet(); effects.putIfAbsent(id, true); });
        }
        Instance a = new Instance("A", store, tasks, 30_000), b = new Instance("B", store, tasks, 30_000),
                 cI = new Instance("C", store, tasks, 30_000);
        b.pollOnce(1_000, true);                                       // B sends one email, then dies before DONE
        List<Thread> three = new ArrayList<>();
        for (Instance in : List.of(a, cI, b))
            three.add(new Thread(() -> { while (!store.due(2_000, 1).isEmpty()) in.pollOnce(2_000, false); }));
        three.forEach(Thread::start);
        for (Thread th : three) th.join();
        System.out.println("   3 instances racing: " + executions.get() + " runs for 300 jobs; the one B held is still leased");
        a.pollOnce(40_000, false);                                     // 39 s later B's lease has expired
        System.out.println("   after the lease expires: " + executions.get() + " runs in all (one twice), "
                + effects.size() + " emails in the effect table: at-least-once runs, one effect each");
        long lastPlanned = 0, now = 3_605_000;                         // back after an hour and 5 s down
        FixedRate every10s = new FixedRate(10_000);
        for (Misfire m : Misfire.values())
            System.out.println("   restart after 1 h, " + m + ": next slot " + m.place(every10s, every10s.next(lastPlanned, lastPlanned), lastPlanned, now));

        System.out.println("-- history (Media.net)");
        RunHistory history = new RunHistory(100);
        ManualClock ch = new ManualClock(0);
        Scheduler hs = new Scheduler(1, ch);
        hs.addListener(history);
        hs.schedule(JobSpec.of("sync", () -> { throw new IOException("timeout"); }).retry(new ExponentialBackoff(10, 100, 2, null)));
        for (int k = 0; k < 30; k++) { for (ScheduledJob j : hs.pollDue(ch.nowMs())) hs.runJob(j); ch.advance(1); }
        System.out.println("   latest for sync: " + history.latest("sync") + "; " + history.last(10).size() + " records kept");

        System.out.println("-- the JDK: a fixed-rate task that throws is silently cancelled");
        ScheduledThreadPoolExecutor stpe = new ScheduledThreadPoolExecutor(2);
        AtomicInteger jdkRuns = new AtomicInteger(), ourRuns = new AtomicInteger();
        ScheduledFuture<?> f = stpe.scheduleAtFixedRate(() -> { if (jdkRuns.incrementAndGet() == 2) throw new IllegalStateException("oops"); },
                                                          0, 10, TimeUnit.MILLISECONDS);
        Scheduler ours = new Scheduler(2, Clock.system());
        ours.start();
        ours.scheduleAtFixedRate(() -> { if (ourRuns.incrementAndGet() == 2) throw new IllegalStateException("oops"); }, 0, 10);
        Thread.sleep(120);
        stpe.shutdownNow();
        ours.shutdownNow();
        ours.awaitTermination(2_000);
        System.out.println("   JDK: " + jdkRuns.get() + " runs, then nothing (isDone=" + f.isDone() + "); ours: " + ourRuns.get()
                + " runs, the failure recorded and the schedule kept");
        DelayQueueScheduler dq = new DelayQueueScheduler(2);
        CountDownLatch dqDone = new CountDownLatch(2);
        List<String> dqOrder = Collections.synchronizedList(new ArrayList<>());
        dq.schedule(() -> { dqOrder.add("200ms"); dqDone.countDown(); }, 200);
        dq.schedule(() -> { dqOrder.add("50ms"); dqDone.countDown(); }, 50);
        dqDone.await(2, TimeUnit.SECONDS);
        dq.shutdownNow();
        System.out.println("   the DelayQueue version ran " + dqOrder + ": the earlier one first, though added second");

        System.out.println("-- sharding");
        ShardedScheduler sh = new ShardedScheduler(4, 2, Clock.system());
        AtomicInteger shardRuns = new AtomicInteger();
        List<Thread> submitters = new ArrayList<>();
        for (int k = 0; k < 8; k++) {
            int base = k * 250;
            submitters.add(new Thread(() -> { for (int i = 0; i < 250; i++) sh.schedule(JobSpec.of("s" + (base + i), shardRuns::incrementAndGet)); }));
        }
        submitters.forEach(Thread::start);
        for (Thread th : submitters) th.join();
        sh.scheduleAll("release-42", List.of(JobSpec.of("build", shardRuns::incrementAndGet),
                                             JobSpec.of("ship", shardRuns::incrementAndGet).after("build")));
        sh.shutdownAndWait(5_000);
        System.out.println("   8 threads x 250 jobs over 4 shards, plus a 2-job batch on one shard: " + shardRuns.get() + " runs");
    }
}
