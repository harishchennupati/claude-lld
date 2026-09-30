import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: any molecule, any stoichiometry -- the same two ideas, keyed by symbol instead of by a two-value enum
/**
 * CO2, NH3, C6H12O6: the seat-then-rendezvous shape does not change, only the recipe it is built from.
 * The map is read once in the constructor and never again, so no lookup in it is ever on a hot path.
 */
final class MoleculeAssembler {
    private final ReentrantLock lock = new ReentrantLock();
    private final Map<String, Condition> seatFree = new HashMap<>();
    private final Map<String, Integer> needed = new HashMap<>();
    private final Map<String, Integer> seated = new HashMap<>();
    private final Condition full = lock.newCondition();
    private final int size;
    private int filled, emitted;
    private long molecules;

    /** One waiting room per symbol, and a molecule the size of the whole recipe. */
    MoleculeAssembler(Map<String, Integer> recipe) {
        int total = 0;
        for (Map.Entry<String, Integer> e : recipe.entrySet()) {
            needed.put(e.getKey(), e.getValue());
            seated.put(e.getKey(), 0);
            seatFree.put(e.getKey(), lock.newCondition());
            total += e.getValue();
        }
        if (total == 0) throw new IllegalArgumentException("a molecule with no atoms would never complete");
        size = total;
    }

    /** Offer one atom of this symbol. Identical protocol to H2OBarrier, with a map where the enum array was. */
    void atom(String symbol, Runnable release) throws InterruptedException {
        Integer want = needed.get(symbol);
        if (want == null) throw new IllegalArgumentException(symbol + " is not in this molecule");
        lock.lockInterruptibly();
        try {
            while (seated.get(symbol).equals(want)) seatFree.get(symbol).await();
            seated.merge(symbol, 1, Integer::sum);
            filled++;
            long mine = molecules;
            if (filled == size) full.signalAll();
            else while (molecules == mine && filled < size) full.await();
        } finally {
            lock.unlock();
        }
        try {
            release.run();
        } finally {
            lock.lock();
            try {
                if (++emitted == size) {
                    emitted = 0;
                    filled = 0;
                    molecules++;
                    for (String s : needed.keySet()) {
                        seated.put(s, 0);
                        for (int k = 0; k < needed.get(s); k++) seatFree.get(s).signal();
                    }
                }
            } finally { lock.unlock(); }
        }
    }

    /** How many complete molecules have been emitted. */
    long moleculesFormed() { lock.lock(); try { return molecules; } finally { lock.unlock(); } }
}

// ---- ext: ladder rung three -- a Phaser instead of a lock and three waiting rooms
/**
 * A Phaser is a CyclicBarrier that can change its party count while it runs and is not permanently broken
 * by one cancelled party. The per-element semaphores are unchanged: they are what makes H,H,H impossible.
 */
final class PhaserBarrier implements MoleculeBarrier {
    private final EnumMap<Element, Semaphore> seats = new EnumMap<>(Element.class);
    private final Phaser bond = new Phaser();

    /** Two hydrogen permits, one oxygen permit, and a phase that advances once all three have arrived. */
    PhaserBarrier() {
        int total = 0;
        for (Element e : Element.values()) { int n = Recipe.WATER.needed(e); seats.put(e, new Semaphore(n)); total += n; }
        bond.bulkRegister(total);
    }

    /** Offer one hydrogen atom. */
    public void hydrogen(Runnable releaseHydrogen) throws InterruptedException { atom(Element.HYDROGEN, releaseHydrogen); }

    /** Offer one oxygen atom. */
    public void oxygen(Runnable releaseOxygen) throws InterruptedException { atom(Element.OXYGEN, releaseOxygen); }

    /** Arrive at the phase, wait for it to advance, emit, and only then hand the permit back. */
    void atom(Element e, Runnable release) throws InterruptedException {
        Semaphore seat = seats.get(e);
        seat.acquire();
        try {
            bond.awaitAdvanceInterruptibly(bond.arrive());   // interruptible, and one cancelled atom does not break it
            release.run();
        } finally {
            seat.release();
        }
    }

    /** The phase number is the molecule count: it advances exactly once per complete molecule. */
    public long moleculesFormed() { return bond.getPhase(); }
}

// ---- ext: a deadline and a way to stop -- the two things a barrier grows in production
/**
 * The same protocol with two additions: every wait has a deadline, and a closed flag the wait loops already
 * read. An atom that gives up hands its seat back before it returns, so the molecule can still form without it.
 */
final class TimedBarrier {
    private final ReentrantLock lock = new ReentrantLock();
    private final EnumMap<Element, Condition> seatFree = new EnumMap<>(Element.class);
    private final Condition full = lock.newCondition();
    private final int[] needed = new int[Element.values().length];
    private final int[] seated = new int[Element.values().length];
    private final int size;
    private int filled, emitted;
    private long molecules;
    private boolean closed;

    /** A water barrier whose every wait can time out. */
    TimedBarrier() {
        int total = 0;
        for (Element e : Element.values()) {
            int n = Recipe.WATER.needed(e);
            needed[e.ordinal()] = n;
            seatFree.put(e, lock.newCondition());
            total += n;
        }
        size = total;
    }

    /**
     * Offer one atom, waiting at most this long in total. Returns false if the budget ran out; when it does,
     * nothing has changed -- the seat is given back and the atom's release never runs.
     */
    boolean atom(Element e, Runnable release, long timeoutMs) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        lock.lockInterruptibly();
        try {
            int want = needed[e.ordinal()];
            while (seated[e.ordinal()] == want) {
                if (closed) throw new IllegalStateException("this barrier is closed");
                if (!awaitUntil(seatFree.get(e), deadline)) return false;      // gave up before taking a seat
            }
            seated[e.ordinal()]++;
            filled++;
            long mine = molecules;
            if (filled == size) {
                full.signalAll();
            } else {
                try {
                    while (molecules == mine && filled < size) {
                        if (closed) { giveSeatBack(e); throw new IllegalStateException("this barrier is closed"); }
                        if (!awaitUntil(full, deadline)) { giveSeatBack(e); return false; }
                    }
                } catch (InterruptedException ie) {
                    if (molecules == mine && filled < size) { giveSeatBack(e); throw ie; }
                    Thread.currentThread().interrupt();
                }
            }
        } finally {
            lock.unlock();
        }
        try {
            release.run();
        } finally {
            closeMyEmit();
        }
        return true;
    }

    /** Wake everybody: parked atoms give their seats back and leave with an exception instead of sleeping forever. */
    void close() {
        lock.lock();
        try {
            closed = true;
            full.signalAll();
            for (Condition c : seatFree.values()) c.signalAll();
        } finally { lock.unlock(); }
    }

    /** Wait on this condition until the deadline. False means the budget ran out. Caller holds the lock. */
    private boolean awaitUntil(Condition c, long deadline) throws InterruptedException {
        long left = deadline - System.nanoTime();
        return left > 0 && c.awaitNanos(left) > 0;
    }

    /** Undo the seat this atom took, and wake one thread that was waiting for it. Caller holds the lock. */
    private void giveSeatBack(Element e) {
        seated[e.ordinal()]--;
        filled--;
        seatFree.get(e).signal();
    }

    /** Count one finished callback; the last one of a molecule opens the seats for the next. */
    private void closeMyEmit() {
        lock.lock();
        try {
            if (++emitted < size) return;
            emitted = 0;
            filled = 0;
            molecules++;
            for (Element e : Element.values()) {
                seated[e.ordinal()] = 0;
                for (int k = 0; k < needed[e.ordinal()]; k++) seatFree.get(e).signal();
            }
        } finally { lock.unlock(); }
    }

    /** How many complete molecules have been emitted. */
    long moleculesFormed() { lock.lock(); try { return molecules; } finally { lock.unlock(); } }
}

// ---- ext: why a CountDownLatch cannot do this job -- it builds exactly one molecule and is then dead
/**
 * The tempting wrong answer. A latch counts down to zero and stays there: the first molecule is correct and
 * every atom after it walks straight through alone, because a spent latch lets everybody past instantly.
 * A CyclicBarrier or a Phaser resets itself every generation, which is the whole difference.
 */
final class OneShotLatchBarrier {
    private final Semaphore hydrogenSeats = new Semaphore(2), oxygenSeats = new Semaphore(1);
    private final CountDownLatch gathered = new CountDownLatch(3);

    /** Offer one atom, waiting at most this long. True means it was released -- which after molecule one is a lie. */
    boolean atom(Element e, Runnable release, long timeoutMs) throws InterruptedException {
        Semaphore seat = e == Element.HYDROGEN ? hydrogenSeats : oxygenSeats;
        seat.acquire();
        try {
            gathered.countDown();
            if (!gathered.await(timeoutMs, TimeUnit.MILLISECONDS)) return false;
            release.run();                       // molecule 2 reaches this line with no partners at all
            return true;
        } finally {
            seat.release();
        }
    }
}

// ---- ext: the naive barrier of three, and the HHH it ships -- the bug, as code that actually runs
/**
 * A rendezvous with no per-element cap. Three hydrogen atoms are three parties, so the barrier trips and
 * emits H,H,H. This is the single most common wrong answer, and it is worth being able to demonstrate.
 */
final class NaiveBarrier {
    private final CyclicBarrier bond = new CyclicBarrier(3);

    /** Any three atoms at all form a "molecule" here, which is exactly the defect. */
    void atom(Runnable release) throws InterruptedException {
        try { bond.await(); } catch (BrokenBarrierException e) { throw new IllegalStateException(e); }
        release.run();
    }
}

// ---- ext: the synchronized / wait / notifyAll version, for when java.util.concurrent.locks is off the table
/**
 * One monitor instead of a lock with three waiting rooms. Everything still works, but every wake wakes
 * everybody: there is only one queue, so notify() could hand the wakeup to an atom that cannot use it.
 */
final class MonitorBarrier implements MoleculeBarrier {
    private int hydrogen, oxygen, filled, emitted;
    private long molecules;

    /** Offer one hydrogen atom. */
    public void hydrogen(Runnable releaseHydrogen) throws InterruptedException { atom(true, releaseHydrogen); }

    /** Offer one oxygen atom. */
    public void oxygen(Runnable releaseOxygen) throws InterruptedException { atom(false, releaseOxygen); }

    /** The same four steps, with wait() and notifyAll() in place of await() and signal(). */
    private void atom(boolean isHydrogen, Runnable release) throws InterruptedException {
        synchronized (this) {
            while (isHydrogen ? hydrogen == 2 : oxygen == 1) wait();
            if (isHydrogen) hydrogen++; else oxygen++;
            filled++;
            long mine = molecules;
            if (filled == 3) {
                notifyAll();                       // notify() here could wake an atom waiting for a SEAT instead
            } else {
                try {
                    while (molecules == mine && filled < 3) wait();
                } catch (InterruptedException ie) {
                    if (molecules == mine && filled < 3) {
                        if (isHydrogen) hydrogen--; else oxygen--;
                        filled--;
                        notifyAll();
                        throw ie;
                    }
                    Thread.currentThread().interrupt();
                }
            }
        }
        try {
            release.run();
        } finally {
            synchronized (this) {
                if (++emitted == 3) { emitted = 0; filled = 0; hydrogen = 0; oxygen = 0; molecules++; notifyAll(); }
            }
        }
    }

    /** How many complete molecules have been emitted. */
    public synchronized long moleculesFormed() { return molecules; }
}

// ---- ext: the unisex bathroom -- the same shape with the rule turned inside out
/**
 * The H2O barrier says "nobody LEAVES until the set is complete". Its sibling says "nobody ENTERS unless the
 * room already matches": at most capacity people inside, and never two kinds at once. One lock, one condition.
 */
final class UnisexRoom {
    private final ReentrantLock lock = new ReentrantLock();
    private final Condition changed = lock.newCondition();
    private final int capacity;
    private Element inside;                     // whose turn the room currently is; null when it is empty
    private int occupants;
    private long admitted;

    /** A room that holds this many people of one kind at a time. */
    UnisexRoom(int capacity) { this.capacity = capacity; }

    /** Wait until the room is empty or already holds your kind with room left, then walk in. */
    void enter(Element kind) throws InterruptedException {
        lock.lockInterruptibly();
        try {
            while (!(occupants == 0 || (inside == kind && occupants < capacity))) changed.await();
            inside = kind;
            occupants++;
            admitted++;
        } finally { lock.unlock(); }
    }

    /** Walk out. The last one out empties the room, which is the only moment the other kind can get in. */
    void leave() {
        lock.lock();
        try {
            if (--occupants == 0) inside = null;
            changed.signalAll();                // the room changed kind: everybody must look again
        } finally { lock.unlock(); }
    }

    /** Whose turn the room currently is, and how many are in it. A test reads this from inside the room. */
    Element currentKind() { lock.lock(); try { return inside; } finally { lock.unlock(); } }

    /** How many people have been let in so far. */
    long admitted() { lock.lock(); try { return admitted; } finally { lock.unlock(); } }
}

// ---- ext: measure without touching the barrier -- a decorator over the interface both sides already depend on
/**
 * Wraps any MoleculeBarrier and records how long an atom waited and how many molecules formed. The barrier
 * it wraps is not edited, not subclassed and never learns it is being measured; callers see the same interface.
 */
final class MeteredBarrier implements MoleculeBarrier {
    private final MoleculeBarrier inner;
    private final AtomicLong atoms = new AtomicLong(), totalWaitNs = new AtomicLong(), worstWaitNs = new AtomicLong();

    /** Wrap a barrier. The only thing that changes at the call site is the word new. */
    MeteredBarrier(MoleculeBarrier inner) { this.inner = Objects.requireNonNull(inner, "inner"); }

    /** Time one hydrogen atom from the call to its release, then delegate the count upward. */
    public void hydrogen(Runnable releaseHydrogen) throws InterruptedException {
        long t0 = System.nanoTime();
        try { inner.hydrogen(releaseHydrogen); } finally { record(System.nanoTime() - t0); }
    }

    /** Time one oxygen atom from the call to its release. */
    public void oxygen(Runnable releaseOxygen) throws InterruptedException {
        long t0 = System.nanoTime();
        try { inner.oxygen(releaseOxygen); } finally { record(System.nanoTime() - t0); }
    }

    /** Keep the running total and the worst case. Lock-free, and never on the barrier's critical path. */
    private void record(long ns) {
        atoms.incrementAndGet();
        totalWaitNs.addAndGet(ns);
        worstWaitNs.accumulateAndGet(ns, Math::max);
    }

    /** The average microseconds an atom spent between calling and being released. */
    public double averageWaitUs() { long n = atoms.get(); return n == 0 ? 0 : totalWaitNs.get() / 1000.0 / n; }

    /** The worst wait any single atom saw, in microseconds. */
    public double worstWaitUs() { return worstWaitNs.get() / 1000.0; }

    /** Delegated unchanged: a decorator adds, it does not replace. */
    public long moleculesFormed() { return inner.moleculesFormed(); }
}

/** Runs every extension above, so the follow-up answers on page 05 are code that has actually executed. */
class ExtDemo {

    /** Each block prints one line or two: the twist, and the evidence that it works. */
    public static void main(String[] args) throws Exception {
        anyMolecule();
        phaserRung();
        deadlinesAndShutdown();
        theLatchIsOneShot();
        theNaiveBarrierShipsHHH();
        theMonitorVersion();
        theUnisexRoom();
        measureWithoutTouching();
        fairnessCosts();
    }

    /** The same barrier, wrapped: it never learns it is being timed, and the caller's line barely changes. */
    static void measureWithoutTouching() throws Exception {
        MeteredBarrier metered = new MeteredBarrier(new H2OBarrier());
        race(metered, new StringBuffer(), 2000);
        System.out.println("metered decorator: " + metered.moleculesFormed() + " molecules, an atom waited "
            + String.format("%.1f", metered.averageWaitUs()) + " us on average and "
            + String.format("%.0f", metered.worstWaitUs()) + " us at worst");
    }

    /** CO2 and NH3 from the same machinery: only the recipe map changes. */
    static void anyMolecule() throws Exception {
        StringBuffer out = new StringBuffer();
        MoleculeAssembler co2 = new MoleculeAssembler(Map.of("C", 1, "O", 2));
        List<Thread> threads = new ArrayList<>();
        for (int i = 0; i < 3; i++) for (String s : List.of("C", "O", "O"))
            threads.add(atomOf(() -> co2.atom(s, () -> out.append(s))));
        join(threads);
        System.out.println("CO2 from the same machinery: " + group(out.toString(), 3)
            + "  molecules=" + co2.moleculesFormed());
    }

    /** The Phaser build satisfies the same contract, and its phase number IS the molecule count. */
    static void phaserRung() throws Exception {
        PhaserBarrier barrier = new PhaserBarrier();
        StringBuffer out = new StringBuffer();
        join(water(barrier, out, 4));
        System.out.println("phaser: " + group(out.toString(), 3) + "  wellFormed="
            + Main.wellFormed(out.toString(), 2, 1) + "  phase=" + barrier.moleculesFormed());
    }

    /** A lonely hydrogen gives up on time and hands its seat back, and close() never leaves anybody parked. */
    static void deadlinesAndShutdown() throws Exception {
        TimedBarrier timed = new TimedBarrier();
        long t0 = System.nanoTime();
        boolean bonded = timed.atom(Element.HYDROGEN, () -> { }, 120);
        System.out.println("one hydrogen, no partners: bonded=" + bonded + " after "
            + (System.nanoTime() - t0) / 1_000_000 + " ms, and its seat was handed back");
        StringBuffer out = new StringBuffer();
        List<Thread> threads = new ArrayList<>();
        for (Element e : List.of(Element.HYDROGEN, Element.HYDROGEN, Element.OXYGEN))
            threads.add(atomOf(() -> timed.atom(e, () -> out.append(e.symbol()), 5_000)));
        join(threads);
        System.out.println("after the timeout the barrier still works: " + out + ", molecules="
            + timed.moleculesFormed());
        TimedBarrier closing = new TimedBarrier();
        Thread parked = atomOf(() -> {
            try { closing.atom(Element.OXYGEN, () -> { }, 30_000); }
            catch (IllegalStateException e) { System.out.println("close() woke the parked atom: " + e.getMessage()); }
        });
        parked.start();
        Thread.sleep(80);
        closing.close();
        parked.join(3_000);
    }

    /** The latch builds exactly one molecule; after that it is at zero and lets every lone atom through. */
    static void theLatchIsOneShot() throws Exception {
        OneShotLatchBarrier latch = new OneShotLatchBarrier();
        StringBuffer out = new StringBuffer();
        List<Thread> first = new ArrayList<>();
        for (Element e : List.of(Element.HYDROGEN, Element.HYDROGEN, Element.OXYGEN))
            first.add(atomOf(() -> latch.atom(e, () -> out.append(e.symbol()), 2_000)));
        join(first);
        String afterOne = out.toString();
        latch.atom(Element.OXYGEN, () -> out.append("O"), 150);       // one lone oxygen, no hydrogen anywhere
        System.out.println("CountDownLatch: molecule 1 = " + afterOne + ", then one lone oxygen was released too: "
            + out + " -- a spent latch lets everybody past, so molecule 2 is a single atom");
    }

    /** Evidence for the interview: a barrier of three with no per-element cap really does emit HHH. */
    static void theNaiveBarrierShipsHHH() throws Exception {
        NaiveBarrier naive = new NaiveBarrier();
        StringBuffer out = new StringBuffer();
        List<Thread> threads = new ArrayList<>();
        for (int i = 0; i < 3; i++) threads.add(atomOf(() -> naive.atom(() -> out.append("H"))));
        join(threads);
        System.out.println("the naive barrier of three, fed three hydrogen atoms, shipped: " + out
            + "  (this is the molecule that does not exist)");
    }

    /** The wait/notifyAll build, for the interviewer who takes java.util.concurrent away. */
    static void theMonitorVersion() throws Exception {
        MonitorBarrier barrier = new MonitorBarrier();
        StringBuffer out = new StringBuffer();
        long ms = race(barrier, out, 500);
        System.out.println("synchronized/wait/notifyAll: " + barrier.moleculesFormed() + " molecules in " + ms
            + " ms, wellFormed=" + Main.wellFormed(out.toString(), 2, 1));
    }

    /** The sibling problem: at most three inside, never mixed -- checked from inside the room. */
    static void theUnisexRoom() throws Exception {
        UnisexRoom room = new UnisexRoom(3);
        AtomicInteger mixed = new AtomicInteger();
        List<Thread> threads = new ArrayList<>();
        for (int i = 0; i < 60; i++) {
            final Element kind = i % 2 == 0 ? Element.HYDROGEN : Element.OXYGEN;
            threads.add(atomOf(() -> {
                room.enter(kind);
                if (room.currentKind() != kind) mixed.incrementAndGet();       // somebody of the other kind is in
                Thread.sleep(1);
                room.leave();
            }));
        }
        join(threads);
        System.out.println("unisex room: " + room.admitted() + " people admitted, times the room was mixed = "
            + mixed.get());
    }

    /**
     * Fairness needs no new class at all: both builds already take the flag. Fair permits never starve a
     * thread and cost a context switch per handoff -- here is that price on both builds, measured.
     */
    static void fairnessCosts() throws Exception {
        long fast = race(new SemaphoreBarrier(Recipe.WATER, false), new StringBuffer(), 2000);
        long fair = race(new SemaphoreBarrier(Recipe.WATER, true), new StringBuffer(), 2000);
        long lockFast = race(new H2OBarrier(Recipe.WATER, false), new StringBuffer(), 2000);
        long lockFair = race(new H2OBarrier(Recipe.WATER, true), new StringBuffer(), 2000);
        System.out.println("2000 molecules, fairness is one constructor flag: semaphores " + fast + " ms -> "
            + fair + " ms fair, and the reference lock " + lockFast + " ms -> " + lockFair
            + " ms fair -- never starves, and it is not free");
    }

    /**
     * Drive any barrier with twenty hydrogen threads and ten oxygen threads pulling from a shared pool of
     * atoms, and return the milliseconds. A shared pool, not a per-thread quota: a thread supplies one seat
     * at a time, so a quota that strands the last two hydrogen atoms on one thread would wait forever.
     */
    static long race(MoleculeBarrier barrier, StringBuffer out, int molecules) throws Exception {
        AtomicInteger hLeft = new AtomicInteger(2 * molecules), oLeft = new AtomicInteger(molecules);
        CountDownLatch go = new CountDownLatch(1);
        List<Thread> threads = new ArrayList<>();
        for (int i = 0; i < 30; i++) {
            final boolean isHydrogen = i < 20;
            threads.add(atomOf(() -> {
                go.await();
                AtomicInteger pool = isHydrogen ? hLeft : oLeft;
                while (pool.getAndDecrement() > 0) {
                    if (isHydrogen) barrier.hydrogen(() -> out.append("H"));
                    else barrier.oxygen(() -> out.append("O"));
                }
            }));
        }
        threads.forEach(Thread::start);
        long t0 = System.nanoTime();
        go.countDown();
        for (Thread t : threads) t.join(60_000);
        return (System.nanoTime() - t0) / 1_000_000;
    }

    /** Start one thread per atom for a handful of molecules, in a shuffled arrival order. */
    static List<Thread> water(MoleculeBarrier barrier, StringBuffer out, int molecules) {
        List<Thread> threads = new ArrayList<>();
        for (int i = 0; i < molecules; i++) {
            threads.add(atomOf(() -> barrier.hydrogen(() -> out.append("H"))));
            threads.add(atomOf(() -> barrier.hydrogen(() -> out.append("H"))));
            threads.add(atomOf(() -> barrier.oxygen(() -> out.append("O"))));
        }
        Collections.shuffle(threads);
        threads.forEach(Thread::start);
        return threads;
    }

    /** A demo body that is allowed to be interrupted, so no demo below writes the same try/catch twice. */
    interface Body { void run() throws InterruptedException; }

    /** One unstarted thread running this body, with the interrupt handled once, here. */
    static Thread atomOf(Body body) {
        return new Thread(() -> {
            try { body.run(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
    }

    /** Start anything not started yet, then join every thread with a deadline: a demo may fail, never hang. */
    static void join(List<Thread> threads) throws InterruptedException {
        for (Thread t : threads) if (t.getState() == Thread.State.NEW) t.start();
        for (Thread t : threads) t.join(20_000);
    }

    /** Split a release string into readable groups for printing. */
    static String group(String released, int size) { return Main.group(released, size); }
}
