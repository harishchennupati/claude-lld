import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

// ---- ext: an audit trail, and not one line of the engine changes

/**
 * Decorator over any Role: it records who emitted what and then delegates. The turn loop, the other roles and every
 * guard stay byte-for-byte the same; the call site changes by one line per role. Because act() runs with the
 * printer's lock held, a plain ArrayList is enough for the trail: only one thread is inside it at a time.
 */
final class AuditRole implements Role {
    private final Role inner;
    private final List<String> trail;

    AuditRole(Role inner, List<String> trail) { this.inner = inner; this.trail = trail; }

    public String name() { return inner.name(); }
    public boolean ready(Series s) { return inner.ready(s); }

    /** Notes the role and the token, then lets the wrapped rule do the real work. */
    public String act(Series s) {
        String token = inner.act(s);
        trail.add(inner.name() + ":" + token);
        return token;
    }

    /** Wraps every role in a list, so auditing a whole series is one call. */
    static List<Role> wrap(List<Role> roles, List<String> trail) {
        List<Role> out = new ArrayList<>();
        for (Role r : roles) out.add(new AuditRole(r, trail));
        return out;
    }
}

// ---- ext: two more series -- a third alternating thread, and the H2O cousin

/** Series the interviewer adds after the first three. Both are new guard sets and nothing else. */
final class ExtraRoles {
    private ExtraRoles() { }

    /** "Add a Baz thread": the boolean flag becomes a three-value phase, and baz closes the round instead of bar. */
    static List<Role> fooBarBaz() {
        return List.of(
            new Rule("foo", s -> s.phase == 0, s -> { s.phase = 1; return "foo"; }),
            new Rule("bar", s -> s.phase == 1, s -> { s.phase = 2; return "bar"; }),
            new Rule("baz", s -> s.phase == 2, s -> { s.phase = 0; s.i++; return "baz"; }));
    }

    /**
     * Building H2O with two threads: phase counts how many hydrogens this molecule already has, so H may act while
     * that count is below two and O only when it is exactly two. Honest caveat in the Javadoc where it belongs: the
     * real problem has many H threads and many O threads and asks only that each group of three contains two H and
     * one O in any order. That is a barrier, not a turn order, and is where a Semaphore(2) plus a CyclicBarrier(3)
     * earns its place instead of a turn flag.
     */
    static List<Role> water() {
        return List.of(
            new Rule("H", s -> s.phase < 2,  s -> { s.phase++; return "H"; }),
            new Rule("O", s -> s.phase == 2, s -> { s.phase = 0; s.i++; return "O"; }));
    }
}

// ---- ext: the classic synchronized / wait / notifyAll version

/**
 * The same design with the language's built-in monitor instead of a Lock: synchronized, wait and notifyAll. It is
 * the version most people write first and it is correct, with one rule that cannot be broken -- an object has only
 * ONE wait set, so notify() (singular) would hand the single wake-up to an arbitrary sleeper, very likely one whose
 * guard is still false, and the thread that could have acted stays asleep forever. That is a lost wakeup, and it is
 * why this version must say notifyAll. What it cannot do is aim a wake-up: for that you need one Condition per
 * role, which is exactly why ConditionPrinter exists.
 */
final class SynchronizedPrinter implements SeriesPrinter {
    private final Object monitor = new Object();
    private final Observers observers = new Observers();
    private final AtomicLong wakeups = new AtomicLong(), wasted = new AtomicLong();
    private volatile boolean stopped;
    private long deadlineMs = 10_000;

    public String name() { return "synchronized / wait / notifyAll"; }
    public long wakeups() { return wakeups.get(); }
    public long wastedWakeups() { return wasted.get(); }

    /** Registers a listener, called once the synchronized block has been left. */
    void addObserver(StepObserver o) { observers.add(o); }

    /** Sets the flag inside the monitor and wakes the whole wait set. */
    public void stop() {
        synchronized (monitor) { stopped = true; monitor.notifyAll(); }
    }

    public String run(int n, List<Role> roles) throws InterruptedException {
        stopped = false;
        wakeups.set(0);
        wasted.set(0);
        Series s = new Series(n, roles.size(), Sink.NONE);
        Crew.Result r = Crew.race(roles.size(), k -> roles.get(k).name(),
                                  me -> serve(s, roles.get(me)), System::currentTimeMillis, deadlineMs, this::stop);
        if (r.error != null) throw new IllegalStateException(name() + ": a role threw", r.error);
        if (!r.finished || (!stopped && !s.done())) throw new IllegalStateException(name() + ": the series stalled");
        return s.text();
    }

    /** The identical shape: wait in a while loop, act, wake the whole set, publish outside the monitor. */
    private void serve(Series s, Role role) throws InterruptedException {
        while (true) {
            String token;
            int at;
            synchronized (monitor) {
                int w = 0;
                while (!stopped && !s.done() && !role.ready(s)) { monitor.wait(); w++; }
                if (w > 0) { wakeups.addAndGet(w); wasted.addAndGet(w - 1L); }
                if (stopped || s.done()) { monitor.notifyAll(); return; }
                token = role.act(s);
                s.emit(token);
                at = s.i;
                monitor.notifyAll();        // notify() here would be a lost-wakeup bug: one wait set, t sleepers
            }
            observers.publish(role.name(), token, at);
        }
    }
}

// ---- ext: if instead of while -- the bug, shown under a storm of stray wake-ups

/**
 * The single most common mistake on this problem: an if where the while belongs. A wake-up is only a hint to look
 * again -- the JVM may return from await for no reason at all (a spurious wakeup), and another thread may have
 * taken the turn in between (a stolen signal). With an if, the woken thread acts on a guard that was true when it
 * went to sleep and is false now, so a token lands out of order. ExtDemo runs this under a thread that does nothing
 * but signalAll, which makes the bug show up in seconds instead of once a month in production.
 */
final class BrokenIfPrinter {
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition turn = lock.newCondition();
    private volatile boolean stopped;

    /** A pure stray wake-up: take the lock, change nothing, wake everybody. */
    void nudge() {
        lock.lock();
        try { turn.signalAll(); } finally { lock.unlock(); }
    }

    /** Stops a run that will not end on its own. */
    void stop() {
        lock.lock();
        try { stopped = true; turn.signalAll(); } finally { lock.unlock(); }
    }

    /** Runs the series with the broken wait and returns whatever came out, right or wrong. */
    String run(int n, List<Role> roles, long deadlineMs) throws InterruptedException {
        stopped = false;
        Series s = new Series(n, roles.size(), Sink.NONE);
        Crew.race(roles.size(), k -> roles.get(k).name(),
                  me -> serve(s, roles.get(me)), System::currentTimeMillis, deadlineMs, this::stop);
        return s.text();
    }

    private void serve(Series s, Role role) throws InterruptedException {
        while (true) {
            lock.lockInterruptibly();
            try {
                if (!stopped && !s.done() && !role.ready(s)) turn.await();   // IF, not WHILE: the whole bug
                if (stopped || s.done()) { turn.signalAll(); return; }
                s.emit(role.act(s));                                         // acts even when the guard went false again
                turn.signalAll();
            } finally { lock.unlock(); }
        }
    }
}

// ---- ext: busy-waiting, and what it really costs

/**
 * No waiting at all: take the lock, look, drop it, look again. It is correct -- the check and the act are still one
 * step under the lock -- and on an idle machine with fewer threads than cores it can even beat the blocking version,
 * because it never pays the two microseconds of a park and an unpark. It is still the wrong answer, and the reason
 * is the row ExtDemo prints for thirty-two threads: a spinner holds a core whether or not it has anything to do, so
 * as soon as there are more participants than cores every spinner is stealing time from the one thread that could
 * actually make progress. Thread.onSpinWait() tells the CPU what is going on but does not give the core back.
 */
final class SpinPrinter {
    private final ReentrantLock lock = new ReentrantLock();

    /** Runs the series by spinning; gives up at the deadline so a demo can never hang. */
    String run(int n, List<Role> roles, long deadlineMs) throws InterruptedException {
        Series s = new Series(n, roles.size(), Sink.NONE);
        long end = System.nanoTime() + deadlineMs * 1_000_000L;
        Crew.race(roles.size(), k -> roles.get(k).name(), me -> {
            Role role = roles.get(me);
            while (System.nanoTime() < end) {
                lock.lock();
                try {
                    if (s.done()) return;
                    if (role.ready(s)) { s.emit(role.act(s)); continue; }
                } finally { lock.unlock(); }
                Thread.onSpinWait();                 // burn the core until it is our turn
            }
        }, System::currentTimeMillis, deadlineMs + 500, () -> { });
        return s.text();
    }
}

// ---- ext: stream it live, and keep slow output out of the lock

/** The obvious sink: every token goes straight to standard output, in order, while the lock is held. */
final class SystemOutSink implements Sink {
    public void emit(String token) { System.out.print(token); }
}

/**
 * The sink for a destination that can block -- a socket, a file, a remote log. emit() only adds the token to a
 * queue, which is a few nanoseconds and is safe to do while the lock is held; one background thread does the slow
 * write afterwards. That split is the answer to "what if printing is slow": decide under the lock, do the I/O
 * outside it. The order survives because the queue is FIFO and the tokens enter it under the lock.
 */
final class DeferredSink implements Sink {
    private final BlockingQueue<String> pending = new LinkedBlockingQueue<>();
    private final Consumer<String> slow;
    private final Thread drainer;
    private volatile boolean open = true;

    DeferredSink(Consumer<String> slow) {
        this.slow = slow;
        drainer = new Thread(this::drain, "sink-drainer");
        drainer.setDaemon(true);
        drainer.start();
    }

    /** O(1) and never blocks: this is the only part that runs with the printer's lock held. */
    public void emit(String token) { pending.add(token); }

    private void drain() {
        try {
            while (true) {
                String token = pending.poll(50, TimeUnit.MILLISECONDS);
                if (token == null) { if (!open) return; continue; }
                slow.accept(token);
            }
        } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }

    /** Waits for every queued token to reach the slow destination, with a deadline of its own. */
    void close() throws InterruptedException { open = false; drainer.join(10_000); }
}

// ---- ext: a roster that grows while the series is running

/**
 * "Now let threads join and leave mid-run." The turn loop is the same; what changes is that the printer keeps its
 * thread list and lets a newcomer join under the lock. The guard set stays total because the round-robin guard is
 * (i - 1) % k == me with k read from the blackboard: bump k and exactly one guard is still true at every step.
 * The newcomer's thread is started inside the same lock that bumps k, so the step that first belongs to it cannot
 * be reached before its thread exists -- and even if the signal arrives before it waits, it re-checks its guard
 * before deciding to sleep, so nothing is lost.
 */
final class ElasticPrinter {
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition turn = lock.newCondition();
    private final List<Thread> threads = new ArrayList<>();
    private final Observers observers = new Observers();
    private Series series;
    private volatile boolean stopped;

    /** Registers a listener, called after the unlock like everywhere else. */
    void addObserver(StepObserver o) { observers.add(o); }

    /** Starts the series with the roles it has today and returns at once; the threads keep running. */
    void start(int n, List<Role> roles) {
        stopped = false;
        series = new Series(n, roles.size(), Sink.NONE);
        lock.lock();
        try { for (Role r : roles) spawn(r); } finally { lock.unlock(); }
    }

    /** Adds one more participant to a running series: bump k, start its thread, wake everybody -- all under the lock. */
    void join(Role r) {
        lock.lock();
        try { series.k++; spawn(r); turn.signalAll(); } finally { lock.unlock(); }
    }

    private void spawn(Role r) {
        Thread t = new Thread(() -> {
            try { serve(r); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        }, "role-" + r.name());
        threads.add(t);
        t.start();
    }

    /** Waits for the series to end and returns the sequence; a stall becomes an exception, never a hang. */
    String await(long ms) throws InterruptedException {
        long end = System.currentTimeMillis() + ms;
        List<Thread> snapshot;
        lock.lock();
        try { snapshot = new ArrayList<>(threads); } finally { lock.unlock(); }
        for (Thread t : snapshot) t.join(Math.max(1L, end - System.currentTimeMillis()));
        for (Thread t : snapshot)
            if (t.isAlive()) { stopped = true; nudge(); t.join(300); t.interrupt(); }
        return series.text();
    }

    private void nudge() {
        lock.lock();
        try { turn.signalAll(); } finally { lock.unlock(); }
    }

    private void serve(Role role) throws InterruptedException {
        Series s = series;
        while (true) {
            String token;
            int at;
            lock.lockInterruptibly();
            try {
                while (!stopped && !s.done() && !role.ready(s)) turn.await();
                if (stopped || s.done()) { turn.signalAll(); return; }
                token = role.act(s);
                s.emit(token);
                at = s.i;
                turn.signalAll();
            } finally { lock.unlock(); }
            observers.publish(role.name(), token, at);
        }
    }
}

// ---- ext: a Phaser instead of a lock

/**
 * A fourth build that uses no lock and no condition: a Phaser, which is a barrier that trips once every registered
 * party has arrived, and is the memory fence as well -- what one thread wrote before arriving is visible to all of
 * them on the other side. The catch is that a barrier alone is NOT a lock, so one token needs TWO trips of it: in
 * the first half of a round every thread only READS its guard, and in the second half only the single thread whose
 * guard was true WRITES. Fuse those halves into one phase and the readers are reading the counter while the writer
 * is incrementing it, which is a plain data race: the first version of this class did exactly that and printed
 * "1fizz24buzz" instead of "12fizz4buzz". It is also the most wasteful build here -- every thread wakes twice per
 * token whatever happens -- and it silently requires the guards to be a partition.
 */
final class PhaserPrinter implements SeriesPrinter {
    private final Observers observers = new Observers();
    private final AtomicLong wakeups = new AtomicLong();
    private volatile boolean stopped;
    private volatile Phaser phaser = new Phaser(0);

    public String name() { return "phaser barrier, no lock"; }
    public long wakeups() { return wakeups.get(); }
    /** Always zero in the sense the other builds mean it: nobody re-checks a guard after a wake, everybody just arrives. */
    public long wastedWakeups() { return 0; }

    /** Registers a listener. */
    void addObserver(StepObserver o) { observers.add(o); }

    /** Ends the run: a forced termination makes every parked arrival return immediately. */
    public void stop() { stopped = true; phaser.forceTermination(); }

    public String run(int n, List<Role> roles) throws InterruptedException {
        stopped = false;
        wakeups.set(0);
        Series s = new Series(n, roles.size(), Sink.NONE);
        Phaser p = new Phaser(roles.size());
        phaser = p;
        long budget = 4L * n + 64;                        // a round budget, so a guard set that is not total cannot spin forever
        Crew.Result r = Crew.race(roles.size(), k -> roles.get(k).name(), me -> {
            Role role = roles.get(me);
            for (long round = 0; round < budget && !stopped && !p.isTerminated(); round++) {
                boolean mine = !s.done() && role.ready(s);   // READ half: every thread looks, nobody writes
                p.arriveAndAwaitAdvance();                   // ... and nobody writes until everybody has looked
                String token = null;
                int at = 0;
                if (mine) { token = role.act(s); s.emit(token); at = s.i; }   // WRITE half: exactly one writer
                p.arriveAndAwaitAdvance();                   // everybody sees the new blackboard after this line
                wakeups.addAndGet(2);                        // two barrier trips per token, per thread
                if (token != null) observers.publish(role.name(), token, at);
                if (s.done()) break;                         // every thread tests this at the same point, so they all leave together
            }
            p.arriveAndDeregister();
        }, System::currentTimeMillis, 10_000, this::stop);
        if (r.error != null) throw new IllegalStateException(name() + ": a role threw", r.error);
        if (!r.finished || (!stopped && !s.done())) throw new IllegalStateException(name() + ": the series stalled");
        return s.text();
    }
}

// ---- ext: fairness and starvation -- the knob people reach for, and why it is the wrong one here

/**
 * A fair lock hands itself to the thread that has been queuing longest instead of to whoever happens to be running.
 * It is the usual cure for starvation, and on this problem it cures nothing, because nothing can starve: the guards
 * are a partition of the series, so every role's turn arrives on a fixed schedule whatever order the lock is handed
 * out in. Barging only decides who wins a race that every loser was going straight back to sleep from. What fairness
 * does cost is real: every hand-off becomes a park and an unpark instead of the winner simply keeping the lock.
 */
final class Fairness {
    private Fairness() { }

    /** Nanoseconds per token for a round robin of k threads, with the lock fair or not. Warms the JIT first. */
    static double nsPerToken(boolean fair, int k, int tokens) throws InterruptedException {
        MonitorPrinter m = new MonitorPrinter(fair);
        List<Role> rr = Roles.roundRobin(k);
        m.run(2_000, rr);
        long t0 = System.nanoTime();
        m.run(tokens, rr);
        return (System.nanoTime() - t0) / (double) tokens;
    }

    /** The starvation check: over a long run every one of the k roles emitted exactly the same number of tokens. */
    static boolean everyRoleGotItsShare(int k, int tokens) throws InterruptedException {
        MonitorPrinter m = new MonitorPrinter(false);           // the UNFAIR lock, on purpose
        RoleTally tally = new RoleTally();
        m.addObserver(tally);
        m.run(tokens, Roles.roundRobin(k));
        for (int j = 0; j < k; j++) if (tally.of("t" + j) != tokens / k) return false;
        return true;
    }
}

// ---- ext: an interrupt while a thread is waiting

/**
 * What happens when somebody cancels a thread that is parked on await(). The wait throws InterruptedException, and
 * because it throws out of a try whose finally unlocks, the lock is released on the way out -- that finally is the
 * only reason the rest of the system survives. The interrupted thread then leaves for good, so the series it was
 * part of can never finish: the remaining threads wait for a turn that will never come, the run hits its deadline,
 * and run() throws instead of hanging. The printer itself is undamaged, which is the claim check 16 makes: the very
 * same object runs a clean series immediately afterwards.
 */
final class Interrupts {
    private Interrupts() { }

    /** Interrupts the live participant thread, the one Crew named "role-" plus the role name. False if it has already gone. */
    static boolean interruptRole(String name) {
        for (Thread t : Thread.getAllStackTraces().keySet())
            if (t.isAlive() && ("role-" + name).equals(t.getName())) { t.interrupt(); return true; }
        return false;
    }
}

/** Runs every extension on this page once, so the reference code is known to work and not only to compile. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        MonitorPrinter p = new MonitorPrinter();

        System.out.println("== audit trail: a Decorator over Role, engine untouched ==");
        List<String> trail = new ArrayList<>();
        String fb = p.run(4, AuditRole.wrap(Roles.fooBar(), trail));
        System.out.println("output " + fb + "   trail " + trail);

        System.out.println();
        System.out.println("== two more series: the same engine, a new guard set ==");
        System.out.println("fooBarBaz(3) -> " + p.run(3, ExtraRoles.fooBarBaz()));
        System.out.println("water(3)     -> " + p.run(3, ExtraRoles.water()) + "   (two hydrogens, then one oxygen, per molecule)");

        System.out.println();
        System.out.println("== the same answer from five different builds ==");
        List<SeriesPrinter> builds = List.of(new MonitorPrinter(), new ConditionPrinter(), new SemaphorePrinter(),
                                             new SynchronizedPrinter(), new PhaserPrinter());
        for (SeriesPrinter b : builds)
            System.out.printf("%-34s %s%n", b.name(), b.run(15, Roles.fizzBuzz()));

        System.out.println();
        System.out.println("== if instead of while: the bug, under a storm of stray wake-ups ==");
        String want = p.run(60, Roles.fizzBuzz());
        int wrong = 0, rounds = 40;
        for (int r = 0; r < rounds; r++) {
            BrokenIfPrinter broken = new BrokenIfPrinter();
            Thread storm = new Thread(() -> { while (!Thread.currentThread().isInterrupted()) broken.nudge(); });
            storm.setDaemon(true);
            storm.start();
            String got = broken.run(60, Roles.fizzBuzz(), 1_000);
            storm.interrupt();
            storm.join(500);
            if (!got.equals(want)) wrong++;
        }
        System.out.println("the if version printed the wrong sequence in " + wrong + " of " + rounds + " rounds");
        System.out.println("the while version, under the same storm, is byte-perfect every time (FailureTests check 5)");

        System.out.println();
        System.out.println("== busy-waiting: fine until there are more spinners than cores ==");
        System.out.println("this machine reports " + Runtime.getRuntime().availableProcessors() + " processors");
        for (int k : new int[] { 2, 4, 32 }) {
            SpinPrinter spin = new SpinPrinter();
            List<Role> rr = Roles.roundRobin(k);
            long t0 = System.nanoTime();
            String out = spin.run(4_000, rr, 8_000);
            long ns = System.nanoTime() - t0;
            MonitorPrinter block = new MonitorPrinter();
            long t1 = System.nanoTime();
            block.run(4_000, rr);
            long ns2 = System.nanoTime() - t1;
            System.out.printf("%2d threads: spinning %7.0f ns/token, blocking %7.0f ns/token, spin output complete: %s%n",
                              k, ns / 4_000.0, ns2 / 4_000.0, out.equals(block.run(4_000, rr)));
        }

        System.out.println();
        System.out.println("== a slow destination: inside the lock, then outside it ==");
        MonitorPrinter slowInside = new MonitorPrinter();
        slowInside.configure(token -> sleepMs(1), System::currentTimeMillis, 20_000);
        long t0 = System.nanoTime();
        slowInside.run(20, Roles.fooBar());
        System.out.printf("sink called inside the lock:   the run took %5d ms%n", (System.nanoTime() - t0) / 1_000_000);
        List<String> written = Collections.synchronizedList(new ArrayList<>());
        DeferredSink deferred = new DeferredSink(token -> { sleepMs(1); written.add(token); });
        MonitorPrinter slowOutside = new MonitorPrinter();
        slowOutside.configure(deferred, System::currentTimeMillis, 20_000);
        long t1 = System.nanoTime();
        String seq = slowOutside.run(20, Roles.fooBar());
        long runMs = (System.nanoTime() - t1) / 1_000_000;
        deferred.close();
        System.out.printf("queued under it, flushed after: the run took %5d ms, the flush finished later%n", runMs);
        System.out.println("order survived the deferral? " + String.join("", written).equals(seq));

        System.out.println();
        System.out.println("== an unbounded stream, stopped by a signal ==");
        MonitorPrinter live = new MonitorPrinter();
        AtomicReference<String> streamed = new AtomicReference<>("");
        Thread runner = new Thread(() -> {
            try { streamed.set(live.run(Integer.MAX_VALUE, Roles.fizzBuzz())); }
            catch (Exception e) { streamed.set("FAILED " + e); }
        });
        runner.start();
        Thread.sleep(50);
        live.stop();
        runner.join(5_000);
        System.out.println("stopped after 50 ms with " + streamed.get().length() + " characters emitted, "
                           + "every thread finished: " + !runner.isAlive());

        System.out.println();
        System.out.println("== a roster that grows while the series runs ==");
        ElasticPrinter elastic = new ElasticPrinter();
        CountDownLatch grow = new CountDownLatch(1);
        elastic.addObserver((role, token, at) -> { if (at >= 100) grow.countDown(); });
        List<Role> two = Roles.roundRobin(4);
        elastic.start(20_000, two.subList(0, 2));
        grow.await(5, TimeUnit.SECONDS);
        elastic.join(two.get(2));
        elastic.join(two.get(3));
        String grown = elastic.await(10_000);
        StringBuilder expected = new StringBuilder();
        for (int i = 1; i <= 20_000; i++) expected.append(i).append(' ');
        System.out.println("started with 2 threads, grew to 4 mid-run, still in strict order: "
                           + grown.equals(expected.toString()));

        System.out.println();
        System.out.println("== fairness: the wrong knob on this problem ==");
        for (boolean fair : new boolean[] { false, true })
            System.out.printf("fair lock = %-5s  %6.0f ns/token%n", fair, Fairness.nsPerToken(fair, 4, 20_000));
        System.out.println("nothing can starve either way: every role got exactly its share of 20,000 tokens "
                           + "on the UNFAIR lock: " + Fairness.everyRoleGotItsShare(4, 20_000));

        System.out.println();
        System.out.println("== an interrupt while a thread is waiting ==");
        MonitorPrinter cancelled = new MonitorPrinter();
        cancelled.configure(Sink.NONE, System::currentTimeMillis, 700);
        Thread host = new Thread(() -> {
            try { cancelled.run(Integer.MAX_VALUE, Roles.roundRobin(3)); }
            catch (IllegalStateException e) { System.out.println("run() ended with: " + e.getMessage()); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        host.start();
        Thread.sleep(40);
        System.out.println("interrupted the t1 thread mid-run: " + Interrupts.interruptRole("t1"));
        host.join(5_000);
        System.out.println("the same printer still works afterwards, so the lock was released: "
                           + cancelled.run(15, Roles.fizzBuzz()).equals("12fizz4buzzfizz78fizzbuzz11fizz1314fizzbuzz"));
    }

    /** Sleeps without making every caller catch the interrupt; used only to fake a slow destination. */
    static void sleepMs(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    }
}
