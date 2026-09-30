import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Semaphore;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.locks.LockSupport;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Where time comes from. Injected, so a test can stamp events with any instant it likes
 * and nothing in the system reads the wall clock by itself.
 */
interface Clock {
    /** The current instant in milliseconds. */
    long nowMs();
}

/**
 * The life of one philosopher. THINKING is the only state in which it holds nothing;
 * HUNGRY means it is reaching (and may be blocked); EATING means it holds BOTH forks.
 */
enum PhilosopherState { THINKING, HUNGRY, EATING, DONE }

/**
 * A bounded piece of work standing in for thinking or eating. Handed in, so a test can make
 * a meal instant, slow, or a meal that throws half way through.
 */
interface Work {
    /** Do the work for one philosopher; may be interrupted while it waits. */
    void perform(int philosopherId) throws InterruptedException;

    /** Work that sleeps for a fixed number of milliseconds. */
    static Work sleepMs(long ms) { return id -> { if (ms > 0) Thread.sleep(ms); }; }

    /** Work that returns immediately: used by the tests that want raw lock traffic. */
    static Work none() { return id -> { }; }
}

/**
 * Thrown by a policy that refuses to wait any longer for the second fork. It is how the naive
 * protocol is demonstrated without hanging a JVM: the philosopher gives the fork it holds back
 * and reports the circular wait instead of sitting in it forever.
 */
final class WouldDeadlock extends RuntimeException {
    private final int philosopherId, forkId;

    /** Records which philosopher gave up and which fork it was reaching for. */
    WouldDeadlock(int philosopherId, int forkId) {
        super("philosopher " + philosopherId + " gave up waiting for fork " + forkId);
        this.philosopherId = philosopherId;
        this.forkId = forkId;
    }

    /** The philosopher that gave up. */
    int philosopherId() { return philosopherId; }

    /** The fork it could not get. */
    int forkId() { return forkId; }
}

/**
 * A fork: one thing that exactly one philosopher may hold at a time, which is the definition of
 * a mutual-exclusion lock, so it IS a lock and not a boolean that would then need its own lock.
 * The lock is taken interruptibly so a supervisor can rescue a wedged run; the owner id is
 * published so a detector can see who holds what; and "hands" counts holders so the tests can
 * prove the invariant (never more than one) instead of trusting it.
 */
final class Fork {
    private final int id;
    private final ReentrantLock lock;
    private volatile int owner = -1;
    private final AtomicInteger hands = new AtomicInteger();
    private volatile boolean violated = false;

    /** A fork with an id; fair = the lock hands itself to the longest waiter (slower, starvation-free). */
    Fork(int id, boolean fair) { this.id = id; this.lock = new ReentrantLock(fair); }

    /** The fork's number, 0..n-1 around the table. This number is what resource ordering orders by. */
    int id() { return id; }

    /** Take the fork, waiting as long as it takes; throws if the thread is interrupted while waiting. */
    void pickUp(int by) throws InterruptedException { lock.lockInterruptibly(); claim(by); }

    /** Take the fork if it comes free within the timeout; false means somebody else still holds it. */
    boolean tryPickUp(int by, long ms) throws InterruptedException {
        if (!lock.tryLock(ms, TimeUnit.MILLISECONDS)) return false;
        claim(by);
        return true;
    }

    /** Record the new holder and count the hands on this fork: two hands would break the invariant. */
    private void claim(int by) {
        owner = by;
        if (hands.incrementAndGet() != 1) violated = true;
    }

    /**
     * Put the fork back. Two guards, and both matter: the lock may only be released by the thread
     * that took it, and the caller must be the recorded owner. A putDown from anybody else is a
     * harmless no-op rather than an IllegalMonitorStateException, so a clumsy caller -- or a
     * finally that runs after a failed acquire -- can never free somebody else's fork.
     */
    void putDown(int by) {
        if (owner != by || !lock.isHeldByCurrentThread()) return;
        hands.decrementAndGet();
        owner = -1;
        lock.unlock();
    }

    /** Who holds this fork right now, or -1 if it is on the table. Read by the deadlock detector. */
    int owner() { return owner; }

    /** True when nobody holds the fork. */
    boolean isFree() { return !lock.isLocked(); }

    /** True if two philosophers were ever counted holding this fork at once: the invariant broken. */
    boolean violated() { return violated; }
}

/**
 * The one rule that decides whether this program deadlocks: how a philosopher gets BOTH forks.
 * Everything else in the system is fixed, so every deadlock-avoidance idea is a new implementation
 * of this interface, handed to the table, with Philosopher and DiningTable untouched (Strategy).
 */
interface ForkPolicy {
    /** Acquire both of the philosopher's forks, or acquire neither. Throws if interrupted while waiting. */
    void acquireBoth(Philosopher p) throws InterruptedException;

    /** Return both forks (and anything else the policy took, such as a seat). Never throws. */
    void releaseBoth(Philosopher p);

    /** The policy's name, for printing. */
    default String name() { return getClass().getSimpleName(); }
}

/**
 * The obvious wrong protocol: left fork, then right fork. If every philosopher takes its left fork
 * in the same instant, every one of them holds one fork and waits for a neighbour's: a circular wait.
 * Two things make it safe to SHOW: an optional wedge latch that forces exactly that instant, and a
 * grace timeout on the second fork, after which the philosopher hands its first fork back and
 * reports the cycle instead of hanging. The timeouts are the evidence, not a fix.
 */
final class NaivePolicy implements ForkPolicy {
    private final long graceMs;
    private final CountDownLatch wedge;
    private final AtomicInteger timeouts = new AtomicInteger();

    /** graceMs = how long to wait for the second fork before calling it a circular wait. */
    NaivePolicy(long graceMs) { this(graceMs, null); }

    /** With a wedge latch sized to the table: every philosopher holds its left fork before any reaches right. */
    NaivePolicy(long graceMs, CountDownLatch wedge) { this.graceMs = graceMs; this.wedge = wedge; }

    /** Left, then right -- and the gap between those two lines is where the deadlock lives. */
    @Override public void acquireBoth(Philosopher p) throws InterruptedException {
        p.markWaiting(p.left().id());
        p.left().pickUp(p.id());
        if (wedge != null) { wedge.countDown(); wedge.await(1, TimeUnit.SECONDS); }
        p.markWaiting(p.right().id());
        if (!p.right().tryPickUp(p.id(), graceMs)) {
            p.left().putDown(p.id());
            p.markWaiting(-1);
            timeouts.incrementAndGet();
            throw new WouldDeadlock(p.id(), p.right().id());
        }
        p.markWaiting(-1);
    }

    /** Both forks go back; the order of release never matters, only the order of acquisition does. */
    @Override public void releaseBoth(Philosopher p) { p.right().putDown(p.id()); p.left().putDown(p.id()); }

    /** How many times a philosopher sat in a circular wait long enough to give up. */
    int timeouts() { return timeouts.get(); }
}

/**
 * The fix that costs one comparison: put a global order on the forks and always take the
 * lower-numbered one first. A cycle needs somebody holding a high fork and waiting for a low one
 * while somebody else does the reverse; if everybody takes low first, that pattern cannot form,
 * so the circular wait is structurally impossible. No waiter, no timeout, no retry.
 */
final class OrderedPolicy implements ForkPolicy {
    /** Lower id first, higher id second, always, for every philosopher at the table. */
    @Override public void acquireBoth(Philosopher p) throws InterruptedException {
        Fork first = p.left().id() < p.right().id() ? p.left() : p.right();
        Fork second = first == p.left() ? p.right() : p.left();
        p.markWaiting(first.id());
        first.pickUp(p.id());
        try {
            p.markWaiting(second.id());
            second.pickUp(p.id());
        } catch (InterruptedException e) {
            first.putDown(p.id());
            throw e;
        } finally {
            p.markWaiting(-1);
        }
    }

    /** Both forks go back. */
    @Override public void releaseBoth(Philosopher p) { p.right().putDown(p.id()); p.left().putDown(p.id()); }
}

/**
 * The fix for when you are not allowed to renumber the resources: a waiter seats at most n-1
 * philosophers at a time. A full cycle needs all n reaching at once, so with one seat missing at
 * least one philosopher always gets both forks. The semaphore is fair, so the queue for a seat
 * is first-come-first-served and nobody is skipped forever.
 */
final class ArbitratorPolicy implements ForkPolicy {
    private final Semaphore seats;
    private final int capacity;

    /** n = the number of philosophers; the waiter hands out n-1 seats. */
    ArbitratorPolicy(int n) { this.capacity = n - 1; this.seats = new Semaphore(capacity, true); }

    /** Take a seat first, then both forks; if anything fails, the seat goes back with the forks. */
    @Override public void acquireBoth(Philosopher p) throws InterruptedException {
        seats.acquire();
        boolean ok = false;
        try {
            p.markWaiting(p.left().id());
            p.left().pickUp(p.id());
            try {
                p.markWaiting(p.right().id());
                p.right().pickUp(p.id());
                ok = true;
            } catch (InterruptedException e) {
                p.left().putDown(p.id());
                throw e;
            }
        } finally {
            p.markWaiting(-1);
            if (!ok) seats.release();
        }
    }

    /** Both forks, then the seat -- in that order, so a freed seat always comes with free forks. */
    @Override public void releaseBoth(Philosopher p) {
        p.right().putDown(p.id());
        p.left().putDown(p.id());
        seats.release();
    }

    /** Seats currently free; must be back to n-1 when dinner is over. */
    int freeSeats() { return seats.availablePermits(); }

    /** How many may reach for forks at once. */
    int capacity() { return capacity; }
}

/**
 * The fix for when there is no order and no waiter: try for both forks, and if the second does not
 * come, put the first one back and retry after a RANDOM pause. It cannot deadlock, because nobody
 * ever holds a fork while waiting forever -- but without the randomness it can livelock, with
 * everybody dropping and grabbing in step, busy and making no progress.
 */
final class TimeoutBackoffPolicy implements ForkPolicy {
    private final long tryMs;
    private final int maxBackoffMicros;
    private final AtomicLong retries = new AtomicLong();

    /** tryMs = how long to wait for each fork; maxBackoffMicros = the upper end of the random pause. */
    TimeoutBackoffPolicy(long tryMs, int maxBackoffMicros) { this.tryMs = tryMs; this.maxBackoffMicros = maxBackoffMicros; }

    /** Drop and retry until both forks are in hand; an interrupt is the only way out. */
    @Override public void acquireBoth(Philosopher p) throws InterruptedException {
        while (true) {
            if (Thread.interrupted()) throw new InterruptedException();
            p.markWaiting(p.left().id());
            if (p.left().tryPickUp(p.id(), tryMs)) {
                p.markWaiting(p.right().id());
                if (p.right().tryPickUp(p.id(), tryMs)) { p.markWaiting(-1); return; }
                p.left().putDown(p.id());
            }
            p.markWaiting(-1);
            retries.incrementAndGet();
            LockSupport.parkNanos(1_000L * (1 + ThreadLocalRandom.current().nextInt(maxBackoffMicros)));
        }
    }

    /** Both forks go back. */
    @Override public void releaseBoth(Philosopher p) { p.right().putDown(p.id()); p.left().putDown(p.id()); }

    /** How many times somebody dropped a fork and tried again: the price of this policy. */
    long retries() { return retries.get(); }
}

/**
 * The junior "fix": one big lock around the whole meal. It cannot deadlock, because there is only
 * one lock -- and it cannot run two philosophers at once either, which is the point of the problem.
 * It is here so a test can measure the difference instead of arguing about it.
 */
final class GlobalLockPolicy implements ForkPolicy {
    private final ReentrantLock table = new ReentrantLock();

    /** One lock for the whole table: correct, and completely serial. */
    @Override public void acquireBoth(Philosopher p) throws InterruptedException {
        table.lockInterruptibly();
        p.left().pickUp(p.id());
        p.right().pickUp(p.id());
    }

    /** Forks back, then the table lock. */
    @Override public void releaseBoth(Philosopher p) {
        p.right().putDown(p.id());
        p.left().putDown(p.id());
        if (table.isHeldByCurrentThread()) table.unlock();
    }
}

/**
 * Somebody who wants to know what happened at the table without being part of it: a tracer, a
 * metrics collector, a UI. Called after the forks are back, never while they are held, and inside
 * a try/catch so a broken listener cannot break dinner.
 */
interface DiningObserver {
    /** One philosopher changed state at this instant. */
    void onState(int philosopherId, PhilosopherState state, long atMs);
}

/**
 * A circular wait, found and named: philosopher p[0] waits for a fork held by p[1], which waits for
 * a fork held by p[2], and so on back to p[0]. forks[i] is the fork p[i] is waiting for.
 */
record Cycle(List<Integer> philosophers, List<Integer> forks) {
    /** How many philosophers are in the ring. */
    int size() { return philosophers.size(); }

    /** "p0 -> fork1 -> p1 -> fork2 -> ... -> p0", the sentence you say to the interviewer. */
    @Override public String toString() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < philosophers.size(); i++)
            sb.append("p").append(philosophers.get(i)).append(" waits for fork ").append(forks.get(i))
              .append(i + 1 < philosophers.size() ? " -> " : " -> back to p" + philosophers.get(0));
        return sb.toString();
    }
}

/**
 * The detector: builds the who-holds-what / who-waits-for-what graph from a snapshot of the table
 * and looks for a ring. It is a watchdog, not a fix -- the fix is the acquisition policy -- and
 * because it reads a moving picture, a ring it finds once is a suspicion until it is still there
 * on the next sample.
 */
final class WaitGraph {
    private WaitGraph() { }

    /** Find one circular wait among these philosophers, or null when nobody is in a ring. */
    static Cycle find(Fork[] forks, Philosopher[] seats) {
        int n = seats.length;
        int[] next = new int[n], via = new int[n];
        Arrays.fill(next, -1);
        Arrays.fill(via, -1);
        for (int i = 0; i < n; i++) {                       // one edge per philosopher: i waits for the holder of the fork it wants
            int want = seats[i].waitingFor();
            if (want < 0) continue;
            int holder = forks[want].owner();
            if (holder >= 0 && holder != i) { next[i] = holder; via[i] = want; }
        }
        for (int start = 0; start < n; start++) {           // walk forward from each philosopher; coming back to the start is a ring
            boolean[] seen = new boolean[n];
            List<Integer> path = new ArrayList<>(), waited = new ArrayList<>();
            int at = start;
            while (at >= 0 && !seen[at]) { seen[at] = true; path.add(at); waited.add(via[at]); at = next[at]; }
            if (at == start && path.size() >= 2) return new Cycle(List.copyOf(path), List.copyOf(waited));
        }
        return null;
    }
}

/**
 * One philosopher: a thread that thinks, gets both forks, eats, puts both back, for a fixed number
 * of rounds. It knows nothing about ordering, waiters or timeouts -- it delegates "get both forks"
 * to the policy it was handed, which is why a new avoidance rule never touches this class.
 */
final class Philosopher implements Runnable {
    private final int id;
    private final Fork left, right;
    private final ForkPolicy policy;
    private final DiningTable table;
    private final int rounds;
    private volatile PhilosopherState state = PhilosopherState.THINKING;
    private volatile int waitingFor = -1;
    private volatile long meals, abandoned, errors, waitNanos;

    /** Seated by the table with its two neighbouring forks and the one shared policy. */
    Philosopher(int id, Fork left, Fork right, ForkPolicy policy, DiningTable table, int rounds) {
        this.id = id; this.left = left; this.right = right; this.policy = policy; this.table = table; this.rounds = rounds;
    }

    /** The philosopher's seat number. */
    int id() { return id; }

    /** The fork on its left (fork i for philosopher i). */
    Fork left() { return left; }

    /** The fork on its right (fork (i+1) mod n). */
    Fork right() { return right; }

    /** What it is doing right now. */
    PhilosopherState state() { return state; }

    /** The fork it is reaching for right now, or -1: the detector's only input from this thread. */
    int waitingFor() { return waitingFor; }

    /** Published by the policy before it blocks, so the detector can see the reach. */
    void markWaiting(int forkId) { waitingFor = forkId; }

    /** Meals finished. Written only by this thread; read after a join, which makes it visible. */
    long meals() { return meals; }

    /** Rounds abandoned because the policy refused to wait any longer (the naive demonstration). */
    long abandoned() { return abandoned; }

    /** Rounds where eating itself threw; the forks still went back. */
    long errors() { return errors; }

    /** Total time spent hungry, in milliseconds. */
    long waitMs() { return waitNanos / 1_000_000L; }

    /**
     * Think, get both forks, eat, put both back -- and the try/finally is the load-bearing part:
     * whatever happens while eating, both forks go back to the table in the same breath.
     */
    @Override public void run() {
        try { table.awaitStart(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
        for (int r = 0; r < rounds && !Thread.currentThread().isInterrupted(); r++) {
            try {
                table.think().perform(id);
                set(PhilosopherState.HUNGRY);
                long t0 = System.nanoTime();
                policy.acquireBoth(this);                     // nothing is "half held": either both, or none
                waitNanos += System.nanoTime() - t0;
                try {
                    set(PhilosopherState.EATING);
                    table.enterMeal();
                    table.eat().perform(id);
                    meals++;                                  // counted only after a whole meal, never before
                } finally {
                    table.exitMeal();
                    policy.releaseBoth(this);                 // the forks go back even if eating threw
                    set(PhilosopherState.THINKING);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();           // a supervisor is stopping us: leave, forks already returned
                break;
            } catch (WouldDeadlock e) {
                abandoned++;                                  // the naive policy gave up rather than sit in the ring
            } catch (RuntimeException e) {
                errors++;                                     // eating threw; the finally above already returned both forks
            }
        }
        set(PhilosopherState.DONE);
    }

    /** Change state and tell the observers -- always with no fork in hand. */
    private void set(PhilosopherState s) { state = s; table.publish(id, s); }
}

/**
 * A read-only picture of the table for a supervisor or a test: meals per philosopher, what each is
 * doing, the most that ever ate at once, and whether every fork is back on the table.
 */
record Snapshot(long[] meals, PhilosopherState[] states, long totalMeals, int peakEating, boolean allForksFree) {
    /** One line per philosopher plus the totals. */
    String format() {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < meals.length; i++)
            sb.append(String.format("   p%d %-8s meals=%d%n", i, states[i], meals[i]));
        sb.append(String.format("   total=%d  peak eating at once=%d  every fork back on the table=%b%n",
                totalMeals, peakEating, allForksFree));
        return sb.toString();
    }
}

/**
 * The table: it builds the ring of n forks and n philosophers, hands every philosopher the SAME
 * policy, starts them together on one latch and can stop them. It owns the forks and the
 * philosophers; it owns no lock of its own, because the forks are the locks.
 */
final class DiningTable {
    private final int n;
    private final Fork[] forks;
    private final Philosopher[] seats;
    private final Thread[] threads;
    private final ForkPolicy policy;
    private final CountDownLatch gate = new CountDownLatch(1);
    private final List<DiningObserver> observers = new CopyOnWriteArrayList<>();
    private final AtomicInteger eating = new AtomicInteger();
    private final AtomicInteger peakEating = new AtomicInteger();
    private Clock clock = System::currentTimeMillis;
    private Work think = Work.none(), eat = Work.none();
    private boolean started = false;

    /** n philosophers, one shared policy, a fixed number of meals each, plain (unfair) fork locks. */
    DiningTable(int n, ForkPolicy policy, int rounds) { this(n, policy, rounds, false); }

    /** fairForks = every fork hands itself to the longest waiter: slower, but nobody is skipped. */
    DiningTable(int n, ForkPolicy policy, int rounds, boolean fairForks) {
        if (n < 2) throw new IllegalArgumentException("a table needs at least two philosophers");
        this.n = n; this.policy = policy;
        this.forks = new Fork[n];
        this.seats = new Philosopher[n];
        this.threads = new Thread[n];
        for (int i = 0; i < n; i++) forks[i] = new Fork(i, fairForks);
        for (int i = 0; i < n; i++) seats[i] = new Philosopher(i, forks[i], forks[(i + 1) % n], policy, this, rounds);
    }

    /** Hand in what thinking and eating mean. The table never decides that itself. */
    DiningTable configure(Work think, Work eat) { this.think = think; this.eat = eat; return this; }

    /** Hand in where time comes from. */
    DiningTable setClock(Clock c) { this.clock = c; return this; }

    /** Add somebody who wants to be told about state changes. */
    DiningTable addObserver(DiningObserver o) { observers.add(o); return this; }

    /** What thinking means for this run. */
    Work think() { return think; }

    /** What eating means for this run. */
    Work eat() { return eat; }

    /** How many philosophers are at this table. */
    int size() { return n; }

    /** The forks, in ring order. */
    Fork[] forks() { return forks; }

    /** One seat. */
    Philosopher seat(int i) { return seats[i]; }

    /** The policy every philosopher at this table was handed. */
    ForkPolicy policy() { return policy; }

    /** Start every philosopher and release them in the same instant: that latch IS the race. */
    void start() {
        if (started) throw new IllegalStateException("this table has already eaten");
        started = true;
        for (int i = 0; i < n; i++) {
            threads[i] = new Thread(seats[i], "philosopher-" + i);
            threads[i].setDaemon(true);                        // a stuck run can never keep the JVM alive
            threads[i].start();
        }
        gate.countDown();
    }

    /** Called by each philosopher thread: wait at the gate until every one of them is ready. */
    void awaitStart() throws InterruptedException { gate.await(); }

    /** Wait for dinner to end; false means somebody is still at the table when the budget ran out. */
    boolean awaitFinish(long ms) throws InterruptedException {
        long deadline = System.nanoTime() + ms * 1_000_000L;
        for (Thread t : threads) {
            long left = deadline - System.nanoTime();
            if (left <= 0) return false;
            t.join(Math.max(1, left / 1_000_000L));
            if (t.isAlive()) return false;
        }
        return true;
    }

    /** The rescue: interrupt everyone, so anybody blocked on a fork throws and unwinds. */
    void interruptAll() { for (Thread t : threads) if (t != null) t.interrupt(); }

    /** Counted when a philosopher starts eating; remembers the most that ever ate at once. */
    void enterMeal() { peakEating.accumulateAndGet(eating.incrementAndGet(), Math::max); }

    /** Counted when a philosopher stops eating. */
    void exitMeal() { eating.decrementAndGet(); }

    /** The most philosophers that ever ate at the same instant: the parallelism the design keeps. */
    int peakEating() { return peakEating.get(); }

    /** Tell the observers, outside every fork, and never let a broken one break dinner. */
    void publish(int philosopherId, PhilosopherState s) {
        if (observers.isEmpty()) return;
        long at = clock.nowMs();
        for (DiningObserver o : observers) {
            try { o.onState(philosopherId, s, at); } catch (RuntimeException ignored) { /* log it, do not rethrow */ }
        }
    }

    /** Look for a circular wait right now. Null means nobody is in a ring at this instant. */
    Cycle findCycle() { return WaitGraph.find(forks, seats); }

    /** True when every fork is back on the table. */
    boolean allForksFree() { for (Fork f : forks) if (!f.isFree()) return false; return true; }

    /** True if any fork was ever held by two philosophers at once: the invariant, measured. */
    boolean anyForkViolated() { for (Fork f : forks) if (f.violated()) return true; return false; }

    /** Meals eaten at this table. */
    long totalMeals() { long t = 0; for (Philosopher p : seats) t += p.meals(); return t; }

    /** A read-only picture for a supervisor or a test. */
    Snapshot snapshot() {
        long[] meals = new long[n];
        PhilosopherState[] states = new PhilosopherState[n];
        for (int i = 0; i < n; i++) { meals[i] = seats[i].meals(); states[i] = seats[i].state(); }
        return new Snapshot(meals, states, totalMeals(), peakEating(), allForksFree());
    }
}

/**
 * Runs the whole thing: one ordinary dinner, then the naive protocol demonstrated safely (a real
 * circular wait, named by the detector, and nobody hangs), then the race -- five threads released
 * by one latch, ten thousand meals, with the invariants checked and counted.
 */
public class Main {

    /** Prints the demo, the safe deadlock demonstration and the race. */
    public static void main(String[] args) throws Exception {
        System.out.println("== 1. dinner: 5 philosophers, resource ordering, 20 meals each, think 1ms / eat 1ms ==");
        DiningTable dinner = new DiningTable(5, new OrderedPolicy(), 20)
                .configure(Work.sleepMs(1), Work.sleepMs(1))
                .addObserver((id, state, at) -> { });
        long t0 = System.currentTimeMillis();
        dinner.start();
        boolean done = dinner.awaitFinish(20_000);
        System.out.printf("   finished=%b in %d ms%n", done, System.currentTimeMillis() - t0);
        System.out.print(dinner.snapshot().format());
        System.out.printf("   longest anyone stayed hungry: p%d, %d ms total%n%n", slowest(dinner), dinner.seat(slowest(dinner)).waitMs());

        System.out.println("== 2. the naive protocol (left then right), demonstrated safely ==");
        CountDownLatch wedge = new CountDownLatch(5);                 // nobody reaches right until all five hold a left fork
        NaivePolicy naive = new NaivePolicy(400, wedge);
        DiningTable bad = new DiningTable(5, naive, 1).configure(Work.none(), Work.sleepMs(1));
        Cycle[] seen = new Cycle[1];
        Thread detector = new Thread(() -> {                           // the watchdog: samples the wait-for graph
            long end = System.currentTimeMillis() + 1_000;
            while (System.currentTimeMillis() < end && seen[0] == null) {
                seen[0] = bad.findCycle();
                LockSupport.parkNanos(10_000_000L);
            }
        });
        detector.setDaemon(true);
        long naiveStart = System.currentTimeMillis();
        bad.start();
        detector.start();
        boolean unwound = bad.awaitFinish(5_000);
        long naiveMs = System.currentTimeMillis() - naiveStart;
        detector.join(1_500);
        System.out.printf("   everyone finished without hanging: %b, after %d ms%n", unwound, naiveMs);
        System.out.printf("   circular wait found by the detector: %s%n", seen[0] == null ? "none" : seen[0].size() + " philosophers");
        if (seen[0] != null) System.out.printf("   %s%n", seen[0]);
        System.out.printf("   nobody ate during the whole 400 ms grace: %b%n", naiveMs >= 400);
        System.out.printf("   gave up on the second fork: %d of 5; meals eaten only after a fork came back: %d%n%n",
                naive.timeouts(), bad.totalMeals());

        System.out.println("== 3. the race: 5 threads on one latch, 2000 rounds each, no sleeps ==");
        for (ForkPolicy p : new ForkPolicy[]{ new OrderedPolicy(), new ArbitratorPolicy(5), new TimeoutBackoffPolicy(5, 50) }) {
            DiningTable t = new DiningTable(5, p, 2_000).configure(Work.none(), Work.none());
            long start = System.currentTimeMillis();
            t.start();
            boolean ok = t.awaitFinish(30_000);
            long ms = System.currentTimeMillis() - start;
            String extra = p instanceof TimeoutBackoffPolicy b ? "  drops+retries=" + b.retries() : "";
            System.out.printf("   %-22s finished=%b in %4d ms  meals=%d  fork held twice=%b  all forks back=%b%s%n",
                    p.name(), ok, ms, t.totalMeals(), t.anyForkViolated(), t.allForksFree(), extra);
        }

        System.out.println("\n== 4. the same five, with a 2 ms meal: how many eat at once ==");
        for (ForkPolicy p : new ForkPolicy[]{ new OrderedPolicy(), new GlobalLockPolicy() }) {
            DiningTable t = new DiningTable(5, p, 20).configure(Work.sleepMs(1), Work.sleepMs(2));
            long start = System.currentTimeMillis();
            t.start();
            t.awaitFinish(30_000);
            System.out.printf("   %-18s peak eating at once=%d  meals=%d  wall clock=%d ms%n",
                    p.name(), t.peakEating(), t.totalMeals(), System.currentTimeMillis() - start);
        }
    }

    /** The philosopher that spent the longest hungry: the fairness number, in one line. */
    private static int slowest(DiningTable t) {
        int worst = 0;
        for (int i = 1; i < t.size(); i++) if (t.seat(i).waitMs() > t.seat(worst).waitMs()) worst = i;
        return worst;
    }
}
