import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

/**
 * Where a finished token also goes, besides the ordered record kept by the Series. Handed in, so the same printer
 * can build a string for a test, write to System.out, or queue bytes for a socket without the turn loop changing.
 */
interface Sink {
    /** Called with one token at a time, in order, while the printer's lock is held: it must be fast and must not block. */
    void emit(String token);
    /** The default sink: the ordered record is enough, nothing else needs the token. */
    Sink NONE = token -> { };
}

/** Where "now" comes from, so a test can decide what the clock says instead of waiting for a deadline to pass. */
interface Clock {
    /** Milliseconds since some fixed point; only differences are used. */
    long nowMs();
}

/** Told after every finished turn, outside the lock, so a slow or broken listener can never stall the series. */
interface StepObserver {
    /** role = who acted, token = what it emitted, at = the value of the counter after the turn. */
    void onStep(String role, String token, int at);
}

/**
 * The blackboard every thread waits on: the counter, the phase flag, how many participants there are, and the
 * ordered record of what has been emitted. Nothing here is synchronized itself. Every field is touched only by a
 * thread that holds the printer's lock (or, in the semaphore build, only by the thread holding the baton), which
 * is the whole safety argument of this design.
 */
final class Series {
    /** The last number in the series; the run ends once i has passed it. */
    final int n;
    /** The next number to be emitted, 1..n. Most guards are written against this. */
    int i = 1;
    /** Whose turn it is among roles that alternate rather than read the number: FooBar and ZeroEvenOdd use it, FizzBuzz does not. */
    int phase = 0;
    /** How many participants are in the round robin right now; the elastic roster in Extensions.java changes it mid-run. */
    int k;
    private final StringBuilder text = new StringBuilder();
    private final Sink sink;

    Series(int n, int k, Sink sink) { this.n = n; this.k = k; this.sink = sink; }

    /** True once every number has been emitted. Every guard loop tests it too, so nobody waits past the end. */
    boolean done() { return i > n; }

    /** Appends one token to the ordered record and forwards it to the sink. Called under the lock: the ORDER is the product. */
    void emit(String token) { text.append(token); sink.emit(token); }

    /** The whole sequence, read only after every participating thread has finished. */
    String text() { return text.toString(); }
}

/**
 * One participating thread's rule: when it may act, and what it emits when it does. This is the only thing that
 * differs between FooBar, ZeroEvenOdd and FizzBuzz; the turn loop never changes.
 */
interface Role {
    /** The name used in the thread name and in the observer. */
    String name();
    /** The guard: may this role act right now? Read under the lock, and re-read after every single wake. */
    boolean ready(Series s);
    /** Advances the counter or the phase and returns the token the printer will emit. Runs under the lock and must not block. */
    String act(Series s);
}

/** A Role assembled from two lambdas, so a new participant is one object rather than one file. */
final class Rule implements Role {
    private final String name;
    private final Predicate<Series> guard;
    private final Function<Series, String> body;

    Rule(String name, Predicate<Series> guard, Function<Series, String> body) {
        this.name = name; this.guard = guard; this.body = body;
    }

    public String name() { return name; }
    public boolean ready(Series s) { return guard.test(s); }
    public String act(Series s) { return body.apply(s); }
}

/**
 * The three classic series, and a round robin of any size, written as guards over the blackboard. Nothing in here
 * mentions a thread, a lock or a wait: that is the point of the split.
 */
final class Roles {
    private Roles() { }

    /** Two threads alternating on the phase flag: foo prints, bar prints and closes the round. */
    static List<Role> fooBar() {
        return List.of(
            new Rule("foo", s -> s.phase == 0, s -> { s.phase = 1; return "foo"; }),
            new Rule("bar", s -> s.phase == 1, s -> { s.phase = 0; s.i++; return "bar"; }));
    }

    /** Three threads: zero fires before every number, then even or odd prints it, whichever matches the parity. */
    static List<Role> zeroEvenOdd() {
        return List.of(
            new Rule("zero", s -> s.phase == 0, s -> { s.phase = 1; return "0"; }),
            new Rule("even", s -> s.phase == 1 && s.i % 2 == 0, s -> { s.phase = 0; return Integer.toString(s.i++); }),
            new Rule("odd",  s -> s.phase == 1 && s.i % 2 == 1, s -> { s.phase = 0; return Integer.toString(s.i++); }));
    }

    /** Four threads and no phase flag at all: the number itself says whose turn it is, and the four guards partition every i. */
    static List<Role> fizzBuzz() {
        return List.of(
            new Rule("number",   s -> s.i % 3 != 0 && s.i % 5 != 0, s -> Integer.toString(s.i++)),
            new Rule("fizz",     s -> s.i % 3 == 0 && s.i % 5 != 0, s -> { s.i++; return "fizz"; }),
            new Rule("buzz",     s -> s.i % 5 == 0 && s.i % 3 != 0, s -> { s.i++; return "buzz"; }),
            new Rule("fizzbuzz", s -> s.i % 15 == 0,                s -> { s.i++; return "fizzbuzz"; }));
    }

    /** k threads taking strict turns: thread j prints exactly the numbers where (i - 1) % k == j. */
    static List<Role> roundRobin(int k) {
        List<Role> out = new ArrayList<>();
        for (int j = 0; j < k; j++) {
            final int me = j;
            out.add(new Rule("t" + me,
                             s -> me < s.k && (s.i - 1) % s.k == me,
                             s -> Integer.toString(s.i++) + " "));
        }
        return out;
    }
}

/** The listener list, owned by every build. Every call happens with no lock held and inside a try/catch. */
final class Observers {
    private final List<StepObserver> list = new CopyOnWriteArrayList<>();

    /** Adds a listener. Safe to call while a series is running. */
    void add(StepObserver o) { list.add(o); }

    /** Called after the unlock: a slow listener only slows its own thread, and one that throws is ignored. */
    void publish(String role, String token, int at) {
        for (StepObserver o : list) {
            try { o.onStep(role, token, at); } catch (RuntimeException ignored) { }
        }
    }
}

/**
 * Spins one thread per role, releases them all on one latch, and joins them against a deadline. A run that would
 * hang (a guard that is never true, a wake-up that never came) becomes a finished call that reports the stall, so
 * no test in this project can ever hang a build.
 */
final class Crew {
    /** The body of one participating thread, identified by its index in the role list. */
    interface Body { void serve(int index) throws InterruptedException; }

    /** What happened: did every thread finish inside the deadline, and did any of them throw? */
    static final class Result {
        final boolean finished;
        final Throwable error;
        Result(boolean finished, Throwable error) { this.finished = finished; this.error = error; }
    }

    /**
     * Starts size threads, releases them together, and waits until the deadline. If any is still alive it calls
     * stopper (which must wake every waiter), then interrupts, then gives up and reports finished = false.
     */
    static Result race(int size, IntFunction<String> names, Body body, Clock clock, long deadlineMs, Runnable stopper)
            throws InterruptedException {
        AtomicReference<Throwable> boom = new AtomicReference<>();
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> ts = new ArrayList<>();
        for (int k = 0; k < size; k++) {
            final int me = k;
            Thread t = new Thread(() -> {
                try { go.await(); body.serve(me); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                catch (Throwable e) { boom.compareAndSet(null, e); }
            }, "role-" + names.apply(k));
            ts.add(t);
            t.start();
        }
        go.countDown();                                   // every thread starts on the same instant
        long end = clock.nowMs() + deadlineMs;
        for (Thread t : ts) t.join(Math.max(1L, end - clock.nowMs()));
        boolean finished = true;
        for (Thread t : ts) if (t.isAlive()) finished = false;
        if (!finished) {
            stopper.run();                                // the polite way out: set the flag and wake everybody
            for (Thread t : ts) t.join(300);
            for (Thread t : ts) t.interrupt();            // the rude way out, so the JVM can still exit
            for (Thread t : ts) t.join(300);
        }
        return new Result(finished, boom.get());
    }
}

/**
 * The contract the three builds share: run a series to n with one thread per role and hand back the sequence.
 * Swapping the build must not change a single character of the output, which is exactly what the tests check.
 */
interface SeriesPrinter {
    /** Runs the series and returns the emitted sequence. Throws IllegalStateException if the threads stall instead of finishing. */
    String run(int n, List<Role> roles) throws InterruptedException;
    /** The name of this build, used when reporting the arithmetic. */
    String name();
    /** How many times a thread came back from a wait during the last run. */
    long wakeups();
    /** How many of those wakes found the guard still false: the thundering herd, counted. */
    long wastedWakeups();
    /** Ends a run early: every waiting thread wakes, sees the flag, and leaves. */
    void stop();
}

/**
 * Build 1, the default: one ReentrantLock and ONE shared Condition. Every turn ends with signalAll, every waiter
 * re-checks its own guard, and exactly one of them finds it true. Correct for any guard set, including one whose
 * next actor depends on the data (FizzBuzz); the price is that t-1 threads wake for nothing on every token.
 */
final class MonitorPrinter implements SeriesPrinter {
    private final ReentrantLock lock;
    private final Condition turn;
    private final Observers observers = new Observers();
    private final AtomicLong wakeups = new AtomicLong(), wasted = new AtomicLong();
    private Sink sink = Sink.NONE;
    private Clock clock = System::currentTimeMillis;
    private long deadlineMs = 10_000;
    private volatile boolean stopped;

    MonitorPrinter() { this(false); }

    /** fair = hand the lock out in arrival order. Slower, and only bought when one role is genuinely being starved. */
    MonitorPrinter(boolean fair) { lock = new ReentrantLock(fair); turn = lock.newCondition(); }

    /** Hands in the three things the printer must never build for itself: where tokens go, where time comes from, how long to wait. */
    void configure(Sink sink, Clock clock, long deadlineMs) {
        this.sink = sink; this.clock = clock; this.deadlineMs = deadlineMs;
    }

    /** Registers a listener. It is called after the unlock, never inside it. */
    void addObserver(StepObserver o) { observers.add(o); }

    public String name() { return "monitor: one condition, signalAll"; }
    public long wakeups() { return wakeups.get(); }
    public long wastedWakeups() { return wasted.get(); }

    /** Sets the stop flag under the lock and wakes every waiter, so a signal can never be lost against it. */
    public void stop() {
        lock.lock();
        try { stopped = true; turn.signalAll(); } finally { lock.unlock(); }
    }

    /** A pure spurious wakeup: takes the lock, changes nothing, and wakes everybody. Used by the tests to hammer the guard loop. */
    void nudge() {
        lock.lock();
        try { turn.signalAll(); } finally { lock.unlock(); }
    }

    public String run(int n, List<Role> roles) throws InterruptedException {
        stopped = false;
        wakeups.set(0);
        wasted.set(0);
        Series s = new Series(n, roles.size(), sink);
        Crew.Result r = Crew.race(roles.size(), k -> roles.get(k).name(),
                                  me -> serve(s, roles.get(me)), clock, deadlineMs, this::stop);
        if (r.error != null)
            throw new IllegalStateException(name() + ": a role threw; the counter never moved and nobody was stranded", r.error);
        if (!r.finished)
            throw new IllegalStateException(name() + ": the series did not finish in " + deadlineMs + " ms -- a thread is still waiting");
        if (!stopped && !s.done())
            throw new IllegalStateException(name() + ": the series stalled at i = " + s.i + " -- no guard was true, so nobody could act");
        return s.text();
    }

    /**
     * One participant's whole life. Wait while it is not this role's turn, act, wake everybody, then tell the
     * listeners with the lock released. The wait is a while loop because a wake only means "look again".
     */
    private void serve(Series s, Role role) throws InterruptedException {
        while (true) {
            String token;
            int at;
            lock.lockInterruptibly();                       // interruptibly, so a parked role can still be cancelled
            try {
                int waits = 0;
                while (!stopped && !s.done() && !role.ready(s)) {
                    turn.await();                           // the lock is RELEASED while this thread sleeps
                    waits++;
                }
                if (waits > 0) { wakeups.addAndGet(waits); wasted.addAndGet(waits - 1L); }
                if (stopped || s.done()) { turn.signalAll(); return; }   // wake the rest on the way out
                try {
                    token = role.act(s);                    // decide the token and advance the counter: one step
                    s.emit(token);                          // the ordered record, INSIDE the lock: the order is the product
                    at = s.i;
                } catch (RuntimeException e) {
                    turn.signalAll();                       // a broken role must not strand the others
                    throw e;
                }
                turn.signalAll();                           // one crowd; exactly one guard is now true
            } finally {
                lock.unlock();                              // in a finally, always: an exception must never leave the lock held
            }
            observers.publish(role.name(), token, at);      // only now, outside the lock
        }
    }
}

/**
 * Build 2, ladder rung two: the same lock, but one Condition per role. A turn ends by finding the single role whose
 * guard the turn just made true and signalling only that one, so no thread ever wakes for nothing. The cost is a
 * scan of the guards under the lock and one Condition object per participant.
 */
final class ConditionPrinter implements SeriesPrinter {
    private final ReentrantLock lock = new ReentrantLock();
    private final Observers observers = new Observers();
    private final AtomicLong wakeups = new AtomicLong(), wasted = new AtomicLong();
    private Sink sink = Sink.NONE;
    private Clock clock = System::currentTimeMillis;
    private long deadlineMs = 10_000;
    private volatile boolean stopped;
    private volatile Condition[] waits = new Condition[0];

    /** Same seams as the monitor build: the sink, the clock and the deadline are handed in. */
    void configure(Sink sink, Clock clock, long deadlineMs) {
        this.sink = sink; this.clock = clock; this.deadlineMs = deadlineMs;
    }

    /** Registers a listener, called after the unlock. */
    void addObserver(StepObserver o) { observers.add(o); }

    public String name() { return "one condition per role, signal"; }
    public long wakeups() { return wakeups.get(); }
    public long wastedWakeups() { return wasted.get(); }

    /** Sets the flag under the lock and wakes every per-role condition, because a shutdown concerns all of them at once. */
    public void stop() {
        lock.lock();
        try { stopped = true; wakeAll(); } finally { lock.unlock(); }
    }

    public String run(int n, List<Role> roles) throws InterruptedException {
        stopped = false;
        wakeups.set(0);
        wasted.set(0);
        Series s = new Series(n, roles.size(), sink);
        Condition[] w = new Condition[roles.size()];
        for (int k = 0; k < w.length; k++) w[k] = lock.newCondition();
        waits = w;
        Crew.Result r = Crew.race(roles.size(), k -> roles.get(k).name(),
                                  me -> serve(s, roles, w, me), clock, deadlineMs, this::stop);
        if (r.error != null)
            throw new IllegalStateException(name() + ": a role threw; the counter never moved", r.error);
        if (!r.finished)
            throw new IllegalStateException(name() + ": the series did not finish in " + deadlineMs + " ms");
        if (!stopped && !s.done())
            throw new IllegalStateException(name() + ": the series stalled at i = " + s.i);
        return s.text();
    }

    /** Same loop as the monitor build; only the wake at the end is aimed instead of broadcast. */
    private void serve(Series s, List<Role> roles, Condition[] w, int me) throws InterruptedException {
        Role role = roles.get(me);
        while (true) {
            String token;
            int at;
            lock.lockInterruptibly();
            try {
                int n = 0;
                while (!stopped && !s.done() && !role.ready(s)) { w[me].await(); n++; }
                if (n > 0) { wakeups.addAndGet(n); wasted.addAndGet(n - 1L); }
                if (stopped || s.done()) { wakeAll(); return; }
                try {
                    token = role.act(s);
                    s.emit(token);
                    at = s.i;
                } catch (RuntimeException e) { wakeAll(); throw e; }
                handOff(s, roles, w);
            } finally {
                lock.unlock();
            }
            observers.publish(role.name(), token, at);
        }
    }

    /**
     * Wakes exactly the one role the last turn made ready. A signal sent to a role that is not asleep yet is simply
     * dropped, and that is safe: it will re-check its guard under this same lock before it decides to wait.
     */
    private void handOff(Series s, List<Role> roles, Condition[] w) {
        if (!s.done())
            for (int k = 0; k < roles.size(); k++)
                if (roles.get(k).ready(s)) { w[k].signal(); return; }
        wakeAll();                                          // the run is over: everybody has to be let go
    }

    /** Signals every per-role condition. Called only when the change concerns all of them: the end of the run, or stop(). */
    private void wakeAll() {
        for (Condition c : waits) c.signal();
    }
}

/**
 * Build 3, ladder rung three: no lock at all. One Semaphore per role, all empty except the one whose guard holds at
 * the start. A thread touches the blackboard only while it holds its own permit, and hands the baton on by releasing
 * the permit of whichever role the new state made ready. release/acquire is a happens-before edge, so the counter
 * written by one thread is visible to the next without a single synchronized block.
 */
final class SemaphorePrinter implements SeriesPrinter {
    private final Observers observers = new Observers();
    private final AtomicLong wakeups = new AtomicLong();
    private Sink sink = Sink.NONE;
    private Clock clock = System::currentTimeMillis;
    private long deadlineMs = 10_000;
    private volatile boolean stopped;
    private volatile Semaphore[] batons = new Semaphore[0];

    /** Same seams again: sink, clock, deadline. */
    void configure(Sink sink, Clock clock, long deadlineMs) {
        this.sink = sink; this.clock = clock; this.deadlineMs = deadlineMs;
    }

    /** Registers a listener; here there is no lock to be outside of, but it is still called after the hand-off. */
    void addObserver(StepObserver o) { observers.add(o); }

    public String name() { return "semaphore baton, no lock"; }
    public long wakeups() { return wakeups.get(); }
    /** Always zero: a thread is handed the baton only when its own guard is already true. */
    public long wastedWakeups() { return 0; }

    /** Sets the flag, then gives every role a permit so that nobody is left parked on an acquire. */
    public void stop() {
        stopped = true;
        for (Semaphore b : batons) b.release();
    }

    public String run(int n, List<Role> roles) throws InterruptedException {
        stopped = false;
        wakeups.set(0);
        Series s = new Series(n, roles.size(), sink);
        Semaphore[] b = new Semaphore[roles.size()];
        for (int k = 0; k < b.length; k++) b[k] = new Semaphore(0);
        batons = b;
        for (int k = 0; k < b.length; k++)                  // the first baton goes to whoever is ready on an untouched series
            if (roles.get(k).ready(s)) { b[k].release(); break; }
        Crew.Result r = Crew.race(roles.size(), k -> roles.get(k).name(),
                                  me -> serve(s, roles, b, me), clock, deadlineMs, this::stop);
        if (r.error != null)
            throw new IllegalStateException(name() + ": a role threw", r.error);
        if (!r.finished)
            throw new IllegalStateException(name() + ": the series did not finish in " + deadlineMs + " ms");
        if (!stopped && !s.done())
            throw new IllegalStateException(name() + ": the series stalled at i = " + s.i + " -- no role was ready to take the baton");
        return s.text();
    }

    /** Hold the baton, act, pass it on. There is no while loop here because there is nothing to re-check: the permit IS the turn. */
    private void serve(Series s, List<Role> roles, Semaphore[] b, int me) throws InterruptedException {
        Role role = roles.get(me);
        while (true) {
            if (!b[me].tryAcquire(deadlineMs, TimeUnit.MILLISECONDS)) return;    // a timed acquire, so a lost baton fails instead of hanging
            wakeups.incrementAndGet();
            if (stopped || s.done()) { releaseAll(b); return; }
            String token = role.act(s);
            s.emit(token);
            int at = s.i;
            int next = -1;
            if (!s.done())
                for (int k = 0; k < roles.size(); k++)
                    if (roles.get(k).ready(s)) { next = k; break; }
            if (next >= 0) b[next].release(); else releaseAll(b);
            observers.publish(role.name(), token, at);
        }
    }

    /** Ends the run for everybody: one permit each, so every thread wakes, sees the state, and leaves. */
    private void releaseAll(Semaphore[] b) {
        for (Semaphore x : b) x.release();
    }
}

/** Counts every token by the role that emitted it, from outside the lock: the proof that each thread printed only its own. */
final class RoleTally implements StepObserver {
    private final Map<String, Integer> counts = new ConcurrentHashMap<>();

    public void onStep(String role, String token, int at) { counts.merge(role, 1, Integer::sum); }

    /** How many tokens this role emitted during the run. */
    int of(String role) { return counts.getOrDefault(role, 0); }

    /** Every role and its count, for printing. */
    Map<String, Integer> all() { return new TreeMap<>(counts); }
}

/** The demo: the three series, the many-thread race, and the arithmetic behind the ladder on page 02. */
public class Main {
    /** Runs each series once, then a race that proves the order holds, then measures the three builds against each other. */
    public static void main(String[] args) throws Exception {
        MonitorPrinter p = new MonitorPrinter();
        RoleTally tally = new RoleTally();
        p.addObserver(tally);

        System.out.println("== the three classic series, one engine ==");
        System.out.println("FooBar(3)        -> " + p.run(3, Roles.fooBar()) + "        (want foobarfoobarfoobar)");
        System.out.println("ZeroEvenOdd(5)   -> " + p.run(5, Roles.zeroEvenOdd()) + "         (want 0102030405)");
        System.out.println("FizzBuzz(15)     -> " + p.run(15, Roles.fizzBuzz()));
        System.out.println("RoundRobin(4,12) -> " + p.run(12, Roles.roundRobin(4)));
        System.out.println("tokens by role   -> " + tally.all());

        System.out.println();
        System.out.println("== the race: ten threads, one latch inside run(), 2000 numbers ==");
        MonitorPrinter race = new MonitorPrinter();
        RoleTally who = new RoleTally();
        race.addObserver(who);
        String got = race.run(2000, Roles.roundRobin(10));
        StringBuilder want = new StringBuilder();
        for (int i = 1; i <= 2000; i++) want.append(i).append(' ');
        System.out.println("2000 numbers, 10 threads, strict order? " + got.equals(want.toString()));
        System.out.println("each thread printed exactly its own 200:  " + allEqual(who, 10, 200));
        System.out.println("wakes " + race.wakeups() + ", of which wasted " + race.wastedWakeups()
                           + " (" + String.format("%.1f", race.wastedWakeups() / 2000.0) + " per token with 10 threads)");

        System.out.println();
        System.out.println("== 300 runs of FooBar(120): byte-identical every time ==");
        String base = p.run(120, Roles.fooBar());
        boolean stable = true;
        for (int r = 0; r < 300; r++) if (!p.run(120, Roles.fooBar()).equals(base)) stable = false;
        System.out.println("all 300 runs identical? " + stable + "   (" + base.length() + " characters each)");

        System.out.println();
        System.out.println("== the arithmetic: what one turn costs as the crowd grows (monitor build) ==");
        System.out.printf("%-10s %16s %14s %22s%n", "threads", "ns per token", "wakes/token", "wasted wakes/token");
        for (int k : new int[] { 1, 2, 3, 4, 10 }) {
            MonitorPrinter m = new MonitorPrinter();
            List<Role> rr = Roles.roundRobin(k);
            m.run(2_000, rr);                                   // warm the JIT before the reading
            long t0 = System.nanoTime();
            m.run(50_000, rr);
            long ns = System.nanoTime() - t0;
            System.out.printf("%-10d %16.0f %14.2f %22.2f%n", k, ns / 50_000.0,
                              m.wakeups() / 50_000.0, m.wastedWakeups() / 50_000.0);
        }
        System.out.println("one thread never waits: that row is the cost of the lock, the guard and the append alone.");

        System.out.println();
        System.out.println("== the ladder, measured: FizzBuzz(20000) with four threads ==");
        List<SeriesPrinter> builds = List.of(new MonitorPrinter(), new ConditionPrinter(), new SemaphorePrinter());
        String reference = null;
        for (SeriesPrinter b : builds) {
            long t0 = System.nanoTime();
            String out = b.run(20_000, Roles.fizzBuzz());
            long ns = System.nanoTime() - t0;
            if (reference == null) reference = out;
            System.out.printf("%-34s %7.0f ns/token   wakes %7d   wasted %7d   same output: %s%n",
                              b.name(), ns / 20_000.0, b.wakeups(), b.wastedWakeups(), out.equals(reference));
        }
        System.out.println();
        System.out.println("One token is one turn: a lock, a guard test, an append and a signal.");
        System.out.println("Unsynchronised, the four threads would read a counter another thread is writing,");
        System.out.println("so a number would be printed twice and another skipped. One lock makes the");
        System.out.println("check and the act a single step, and the while loop absorbs every wrong wake-up.");
    }

    /** True when every one of the k round-robin roles emitted exactly the expected number of tokens. */
    static boolean allEqual(RoleTally tally, int k, int each) {
        for (int j = 0; j < k; j++) if (tally.of("t" + j) != each) return false;
        return true;
    }
}
