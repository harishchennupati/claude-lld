import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;
import java.time.*;

/** The kinds of vehicle that can enter. Used only to look up which spot sizes fit. */
enum VehicleType { MOTORCYCLE, CAR, TRUCK }

/**
 * The thing that drives in: a plate and a type, nothing else. Subclasses exist so one kind can be special-
 * cased later.
 */
abstract class Vehicle {                       // the first noun: what drives in
    final String plate;
    final VehicleType type;
    Vehicle(String plate, VehicleType type) { this.plate = plate; this.type = type; }
}
class Car        extends Vehicle { Car(String p)        { super(p, VehicleType.CAR); } }
class Motorcycle extends Vehicle { Motorcycle(String p) { super(p, VehicleType.MOTORCYCLE); } }
class Truck      extends Vehicle { Truck(String p)      { super(p, VehicleType.TRUCK); } }

/** Spot sizes. A bigger spot can hold a smaller vehicle; the Fit table says which. */
enum SpotType { SMALL, COMPACT, LARGE }        // a bigger spot fits smaller vehicles

/**
 * One physical spot. Deliberately dumb: it knows its size and who is in it. Two questions, two answers:
 * "which free spot of this size is next?" is the head of the floor's queue; "is THIS spot free?" is
 * occupant() == null. The queue and the field are always changed together, under the lot's one lock.
 */
class ParkingSpot {                            // where the vehicle goes
    final String id;
    final SpotType type;
    private Vehicle vehicle;                    // who is in it, for the ticket and for display; null == nobody
    ParkingSpot(String id, SpotType type) { this.id = id; this.type = type; }
    /** Who is parked here, or null. For the ticket and the display only. */
    Vehicle occupant()        { return vehicle; }
    /**
     * Record the vehicle now in this spot. Called by the lot, inside its lock, after the floor handed the
     * spot out.
     */
    void    assign(Vehicle v) { this.vehicle = v; }
    /** Forget the vehicle. Called at exit, after payment succeeded. */
    void    release()         { this.vehicle = null; }
}

// hand out the SMALLEST fitting spot first, so large spots stay free for trucks.
// Rule: the FIRST floor that has any fitting spot wins, then the smallest size on that floor.
/**
 * The fit table: for each vehicle type, the spot sizes it may use, SMALLEST FIRST, so large spots stay
 * free for trucks. A table, not an if-chain, so adding a size is one row.
 */
final class Fit {
    static final Map<VehicleType, List<SpotType>> ORDER = Map.of(
        VehicleType.MOTORCYCLE, List.of(SpotType.SMALL, SpotType.COMPACT, SpotType.LARGE),
        VehicleType.CAR,        List.of(SpotType.COMPACT, SpotType.LARGE),
        VehicleType.TRUCK,      List.of(SpotType.LARGE));
}

/**
 * A ticket's life: ISSUED at entry; PAYING while its exit payment is in flight (a second checkout is
 * refused); PENDING when the gateway could not say whether the money moved (the retry re-sends the same key
 * and amount); PAID once money moved; LOST if reported lost (billed the cap); CLOSED when the spot is freed.
 */
enum TicketStatus { ISSUED, PAYING, PENDING, PAID, LOST, CLOSED }

/**
 * Issued at entry, priced at exit. Remembers its floor so exit never searches, and its entry time so the
 * fee is computable. Time is handed in, never read here.
 */
class Ticket {                                 // issued at entry, priced at exit
    private static final AtomicInteger SEQ = new AtomicInteger();
    final int id;
    final ParkingSpot spot;
    final ParkingFloor floor;                  // remembered -> unpark is O(1)
    final Vehicle vehicle;
    final long entryMs;
    long exitMs;
    long feePaise;                             // priced when a payment starts; a retry after a timeout re-sends this exact amount
    TicketStatus status = TicketStatus.ISSUED;
    int attempt;                               // bumped after a decline: a NEW try needs a NEW key
    PaymentProcessor pendingOn;                // the gateway holding an unconfirmed payment; a retry must go back there
    Ticket(ParkingSpot spot, ParkingFloor floor, Vehicle vehicle, long entryMs) {
        this.id = SEQ.incrementAndGet(); this.spot = spot; this.floor = floor; this.vehicle = vehicle;
        this.entryMs = entryMs;                // time is handed in, never read here (testable, replayable)
    }
    /**
     * The idempotency key: ticket id plus attempt number. A retry after a timeout reuses it, so the gateway
     * charges it at most once; a decline bumps the attempt, because a gateway keeps its first answer per key,
     * and the same key would answer "declined" to the driver's next card too.
     */
    String payKey() { return "ticket-" + id + "-" + attempt; }
}

// "they'll want to change pricing" -> hide it behind an interface -> Strategy
/**
 * The pricing rule, behind an interface because it WILL change mid-round (surge, caps). Reads only the
 * ticket. Returns paise (100 paise = one rupee) in a long: a double cannot even hold 0.1 exactly.
 */
interface PricingStrategy { long price(Ticket t); }

/** Hourly by spot size, any started hour billed. 60 minutes and 1 millisecond is two hours. */
class FlatHourlyPricing implements PricingStrategy {
    private static final Map<SpotType, Long> RATE =                    // paise an hour: Rs 10, Rs 20, Rs 40
        Map.of(SpotType.SMALL, 1_000L, SpotType.COMPACT, 2_000L, SpotType.LARGE, 4_000L);
    /** Fee for a finished ticket, in paise: started hours times the size's rate. */
    public long price(Ticket t) {
        long ms = t.exitMs - t.entryMs;
        long hours = Math.max(1, (long) Math.ceil(ms / 3600000.0));   // any started hour is billed: 60 min + 1 ms = 2 hours
        return hours * RATE.get(t.spot.type);
    }
}

// "smallest fit today, nearest-to-exit tomorrow" -> same shape -> Strategy again
/**
 * Which spot to hand out on a floor for this vehicle, or null if none fits. It is given the whole vehicle,
 * not just its type, so a rule may look at the plate (a monthly pass) or the subclass (an electric car).
 * Behind an interface because 'nearest to exit' is the follow-up that always comes.
 */
interface SpotAssignmentStrategy { ParkingSpot find(ParkingFloor floor, Vehicle v); }

/**
 * Walk the fit table smallest-first and return the first size that has a free spot. O(sizes), never a scan
 * of spots.
 */
class SmallestFitStrategy implements SpotAssignmentStrategy {
    /**
     * The head of the first non-empty fitting queue, or null. Peeks only; the lot decides whether to take
     * it.
     */
    public ParkingSpot find(ParkingFloor floor, Vehicle v) {
        for (SpotType st : Fit.ORDER.get(v.type)) {   // smallest fitting size first
            ParkingSpot s = floor.peekFree(st);
            if (s != null) return s;
        }
        return null;
    }
}

// "a board should update but not be wired into parking logic" -> publish/subscribe -> Observer
/**
 * Anyone who wants to hear 'free counts on floor X changed': a display board, a metrics exporter. The
 * floor does not know what they are.
 */
interface ParkingObserver { void onChange(String floorId, Map<SpotType, Integer> free); }

/** A screen at the floor entrance. Prints the counts; a real one would drive an LED panel. */
class DisplayBoard implements ParkingObserver {
    public void onChange(String floorId, Map<SpotType, Integer> free) {
        System.out.println("[board] " + floorId + " free=" + free);
    }
}

/**
 * One floor: its spots, and per size a queue of the FREE ones. The ORDER of that queue is the rule for
 * which free spot of a size is handed out next, so it is handed in: a plain ArrayDeque means "any of
 * them", O(1); a PriorityQueue ordered by metres from the exit means "the nearest", O(log n). Nothing
 * else in the design changes. All mutation happens under the lot's lock; observers are told after the
 * lock is released.
 */
class ParkingFloor {
    final String id;
    private final Map<SpotType, Queue<ParkingSpot>> free = new EnumMap<>(SpotType.class);   // the free spots of each size, in policy order
    private final Map<String, ParkingSpot> all = new HashMap<>();
    private final List<ParkingObserver> observers = new CopyOnWriteArrayList<>();

    /** A floor that hands out any free spot of the right size: ArrayDeque, O(1) at both ends. */
    ParkingFloor(String id) { this(id, ArrayDeque::new); }
    /**
     * A floor whose free spots of each size are kept in the order this queue imposes; the head is
     * whatever the order calls best. Hand in a PriorityQueue by distance and you have nearest-to-exit.
     */
    ParkingFloor(String id, Supplier<Queue<ParkingSpot>> order) {
        this.id = id;
        for (SpotType st : SpotType.values()) free.put(st, order.get());
    }
    /** Subscribe a listener; setup only. */
    void addObserver(ParkingObserver o) { observers.add(o); }
    /** Register a spot; it starts free. Setup only. */
    void addSpot(ParkingSpot s)         { all.put(s.id, s); free.get(s.type).offer(s); }
    /** One spot by its id, free or not; for rules that need a named spot (adjacency, a reservation). */
    ParkingSpot spot(String id)         { return all.get(id); }
    /** Every spot on this floor, free or not. Only rules that must look at pairs of spots use it. */
    Collection<ParkingSpot> spots()     { return all.values(); }
    /** The next free spot of a size without taking it, or null. O(1). */
    ParkingSpot peekFree(SpotType st)   { return free.get(st).peek(); }   // O(1)
    /** How many spots of a size are free. O(1): the queue's size. */
    int freeCount(SpotType st)          { return free.get(st).size(); }   // O(1)

    /**
     * Take a free spot out of its queue. The head costs O(1), which is what the default rule always asks
     * for; a rule that picks some other free spot pays one O(n) removal on that floor. Taking a spot that
     * is not free is a caller bug and throws.
     */
    void take(ParkingSpot s) {
        Queue<ParkingSpot> q = free.get(s.type);
        if (q.peek() == s) { q.poll(); return; }                       // the common case: O(1)
        if (!q.remove(s)) throw new IllegalStateException("not free: " + s.id);
    }
    /** Give a spot back; it re-enters its queue in policy order. O(1) for a deque, O(log n) for a heap. */
    void vacate(ParkingSpot s) { free.get(s.type).offer(s); }

    /** Copy of the free counts, taken INSIDE the lock so it is consistent. */
    Map<SpotType, Integer> snapshot() {
        Map<SpotType, Integer> counts = new EnumMap<>(SpotType.class);
        for (SpotType st : SpotType.values()) counts.put(st, free.get(st).size());
        return counts;
    }
    /**
     * Tell every observer, OUTSIDE the lock, from a snapshot. A slow or throwing observer can stall no
     * gate and corrupt nothing.
     */
    void publish(Map<SpotType, Integer> counts) {     // called after the lock is released; a broken listener cannot break parking
        for (ParkingObserver o : observers) {
            try { o.onChange(id, counts); } catch (RuntimeException e) { System.err.println("[observer failed] " + e.getMessage()); }
        }
    }
}

/** What the gateway answered: the money moved, it was refused, or nobody knows (a timeout). */
enum PaymentStatus { OK, DECLINED, UNKNOWN }

/**
 * How money is taken at exit; card, cash, UPI. The amount is in paise. The key is an idempotency key (the
 * ticket id: a unique id for this payment, so a retry that arrives twice is charged once): the gateway
 * charges one key at most once, and a retry with a key it already charged gets OK back, with no new charge.
 */
interface PaymentProcessor { PaymentStatus pay(String idempotencyKey, long paise); }   // Strategy #3
class CardPayment implements PaymentProcessor { public PaymentStatus pay(String key, long paise) { /* gateway, keyed */ return PaymentStatus.OK; } }
class CashPayment implements PaymentProcessor { public PaymentStatus pay(String key, long paise) { return PaymentStatus.OK; } }

/** Where time comes from. Injected so tests can pick 'Saturday 10:00' and billing is replayable. */
interface Clock { long nowMs(); }                                       // time is injected: tests and replays choose it

/**
 * The orchestrator and the only writer of shared state: the floors, the active tickets, and ONE lock.
 * park is one short critical section. unpark is two, with the card payment between them and no lock held;
 * nothing is committed before the payment succeeded.
 */
class ParkingLot {                                   // one source of truth (Singleton)
    private static ParkingLot instance;
    private final List<ParkingFloor> floors = new ArrayList<>();
    private final Map<String, ParkingFloor> byId = new HashMap<>();  // for "how many free on F2?"
    private final Map<String, Ticket> active = new HashMap<>();     // guarded by lock
    private final ReentrantLock lock = new ReentrantLock();
    private PricingStrategy pricing;
    private SpotAssignmentStrategy assignment;
    private Clock clock = System::currentTimeMillis;

    /** Package-private on purpose: application code goes through getInstance(), tests build their own. */
    ParkingLot() {}
    static synchronized ParkingLot getInstance() {
        if (instance == null) instance = new ParkingLot();
        return instance;
    }
    /**
     * Hand in the rules. The lot never builds a strategy itself, so swapping one is a new class and this
     * one line.
     */
    void configure(PricingStrategy p, SpotAssignmentStrategy a) { pricing = p; assignment = a; }
    /** Tests hand in a fixed clock. */
    void setClock(Clock c) { clock = c; }
    void addFloor(ParkingFloor f) { floors.add(f); byId.put(f.id, f); }

    /**
     * Entry. Under the lock: reject a duplicate plate, ask the strategy floor by floor for a spot, take it, record the vehicle, issue the ticket.
     * After the lock: tell the floor's observers. Throws if the lot is full for this vehicle.
     */
    Ticket park(Vehicle v) {
        Ticket t; ParkingFloor changed; Map<SpotType, Integer> counts;
        lock.lock();                                  // critical section: find + take + assign, nothing else
        try {
            if (active.containsKey(v.plate)) throw new IllegalStateException("Already parked: " + v.plate);
            ParkingSpot spot = null; changed = null;
            for (ParkingFloor floor : floors) {       // first floor with a fitting spot wins
                spot = assignment.find(floor, v);
                if (spot != null) { changed = floor; break; }
            }
            if (spot == null) throw new IllegalStateException("Lot full for " + v.type);
            changed.take(spot);
            spot.assign(v);
            t = new Ticket(spot, changed, v, clock.nowMs());
            active.put(v.plate, t);
            counts = changed.snapshot();
        } finally { lock.unlock(); }
        changed.publish(counts);                      // the board hears AFTER the lock; a slow or broken board stalls nobody
        return t;
    }

    /**
     * Exit, in three steps, so the slow card payment never runs inside the lock.
     * 1, locked: find the ticket, refuse it unless it is ISSUED (or PENDING: a retry), mark it PAYING, stamp
     *    the exit time and price it. A second checkout while it is PAYING is refused.
     * 2, no lock: take the payment, keyed by the ticket id, so this ticket is charged at most once.
     * 3, locked: settle() commits on OK, goes back to ISSUED on a decline, and waits as PENDING on a timeout.
     * Returns the fee in paise.
     */
    long unpark(String plate, PaymentProcessor payment) {
        Ticket t; PaymentProcessor via;
        lock.lock();                                  // step 1: short, nothing slow inside
        try {
            t = active.get(plate);                    // peek: commit nothing until the money has moved
            if (t == null) throw new NoSuchElementException("No active ticket: " + plate);
            if (t.status != TicketStatus.ISSUED && t.status != TicketStatus.PENDING)
                throw new IllegalStateException("Payment already in progress: " + plate);   // a second checkout while PAYING
            if (t.status == TicketStatus.ISSUED) { t.exitMs = clock.nowMs(); t.feePaise = pricing.price(t); }
            via = t.status == TicketStatus.PENDING ? t.pendingOn : payment;   // an unconfirmed payment is retried where it started, never in cash on top
            t.status = TicketStatus.PAYING;           // a PENDING retry keeps its amount: same key, same paise
        } finally { lock.unlock(); }
        PaymentStatus answer;
        try { answer = via.pay(t.payKey(), t.feePaise); }                // step 2: ~500 ms at a card gateway, NO lock held
        catch (RuntimeException e) { answer = PaymentStatus.UNKNOWN; }    // a gateway that throws: nobody knows if money moved
        return settle(t, answer, TicketStatus.PAID, via);  // step 3
    }

    /**
     * Step 3 of an exit, under the lock again, with the gateway's answer. OK: commit (PAID or LOST, remove,
     * free the spot, CLOSED) and tell the board after the lock. DECLINED: back to ISSUED, nothing else
     * changed; the driver retries. UNKNOWN (a timeout): PENDING, the spot still held; the retry sends the
     * same key and amount, and the gateway returns its first answer instead of charging again.
     */
    private long settle(Ticket t, PaymentStatus answer, TicketStatus paidAs, PaymentProcessor via) {
        Map<SpotType, Integer> counts;
        lock.lock();
        try {
            if (answer == PaymentStatus.DECLINED) { t.status = TicketStatus.ISSUED; t.attempt++; t.pendingOn = null; throw new IllegalStateException("Payment declined"); }   // next try: a new key
            if (answer == PaymentStatus.UNKNOWN) { t.status = TicketStatus.PENDING; t.pendingOn = via; throw new IllegalStateException("Payment not confirmed: retry; the same key cannot charge twice"); }
            t.pendingOn = null;
            t.status = paidAs;                        // money moved: now commit
            active.remove(t.vehicle.plate);
            t.spot.release();
            t.floor.vacate(t.spot);                   // O(1): ticket knew its floor
            t.status = TicketStatus.CLOSED;
            counts = t.floor.snapshot();
        } finally { lock.unlock(); }
        t.floor.publish(counts);                      // the board hears AFTER the lock, same as park()
        return t.feePaise;
    }

    /**
     * Free spots per size across the lot. O(floors x sizes), under the lock so a count is never torn by a
     * concurrent park.
     */
    Map<SpotType, Integer> availability() {
        lock.lock();
        try {
            Map<SpotType, Integer> total = new EnumMap<>(SpotType.class);
            for (SpotType st : SpotType.values()) total.put(st, 0);
            for (ParkingFloor f : floors)
                for (SpotType st : SpotType.values())
                    total.merge(st, f.freeCount(st), Integer::sum);
            return total;
        } finally { lock.unlock(); }
    }
    /**
     * Free spots of one size on ONE floor: what the display board and the app ask for. O(1), the size of
     * that queue, read under the lock so a count is never torn by a park happening at the same moment.
     */
    int freeCount(String floorId, SpotType st) {
        lock.lock();
        try {
            ParkingFloor f = byId.get(floorId);
            if (f == null) throw new NoSuchElementException("No floor: " + floorId);
            return f.freeCount(st);
        } finally { lock.unlock(); }
    }
    /** True when no floor has any spot this vehicle type may use. */
    boolean isFullFor(VehicleType v) {
        lock.lock();
        try {
            for (ParkingFloor f : floors)
                for (SpotType st : Fit.ORDER.get(v))
                    if (f.freeCount(st) > 0) return false;
            return true;
        } finally { lock.unlock(); }
    }
    /**
     * Lost ticket: duration is unknown, so bill the daily cap. The same three steps as unpark: PAYING under
     * the lock, pay with no lock held, then LOST, remove, free, CLOSED under the lock.
     */
    long reportLost(String plate, PaymentProcessor payment, long dailyCapPaise) {
        Ticket t; PaymentProcessor via;
        lock.lock();                                  // step 1
        try {
            t = active.get(plate);
            if (t == null) throw new NoSuchElementException("No active ticket: " + plate);
            if (t.status != TicketStatus.ISSUED && t.status != TicketStatus.PENDING)
                throw new IllegalStateException("Payment already in progress: " + plate);
            if (t.status == TicketStatus.ISSUED) { t.exitMs = clock.nowMs(); t.feePaise = dailyCapPaise; }
            via = t.status == TicketStatus.PENDING ? t.pendingOn : payment;   // same rule as unpark
            t.status = TicketStatus.PAYING;
        } finally { lock.unlock(); }
        PaymentStatus answer;
        try { answer = via.pay(t.payKey(), t.feePaise); }                // step 2: no lock held
        catch (RuntimeException e) { answer = PaymentStatus.UNKNOWN; }
        return settle(t, answer, TicketStatus.LOST, via);  // step 3, shared with unpark: LOST, remove, free, CLOSED
    }
}

// new rule live: 1.5x on weekends. A NEW class + one line — nothing else changes.
/**
 * 1.5x on weekends: a NEW class that wraps the existing rule (Decorator). The lot did not change; only the
 * configure() line did.
 */
class WeekendSurgePricing implements PricingStrategy {
    private final PricingStrategy base;                    // wrap the existing rule (Decorator)
    private final ZoneId zone;
    WeekendSurgePricing(PricingStrategy base, ZoneId zone) { this.base = base; this.zone = zone; }
    public long price(Ticket t) {
        long p = base.price(t);
        DayOfWeek d = Instant.ofEpochMilli(t.exitMs).atZone(zone).getDayOfWeek();   // the ticket's exit time, which the lot's clock stamped
        boolean weekend = (d == DayOfWeek.SATURDAY || d == DayOfWeek.SUNDAY);
        return weekend ? (p * 3 + 1) / 2 : p;               // x1.5 in whole paise; a half paisa rounds up
    }
}
// the only change at the call site — swap the injected strategy:
// lot.configure(new WeekendSurgePricing(new FlatHourlyPricing(), ZoneId.of("Asia/Kolkata")), new SmallestFitStrategy());

// entry / exit gates: thin actors. Real logic + the lock live in the lot,
// which is exactly why concurrent gates are safe.
/**
 * A thin actor at the barrier. No logic, no lock: it calls the lot, which is exactly why many gates at
 * once are safe.
 */
class EntryGate {
    private final ParkingLot lot;
    EntryGate(ParkingLot lot) { this.lot = lot; }
    Ticket admit(Vehicle v) { return lot.park(v); }        // print ticket, open barrier
}
/** The exit barrier: charges via the lot, then opens. */
class ExitGate {
    private final ParkingLot lot;
    ExitGate(ParkingLot lot) { this.lot = lot; }
    long checkout(String plate, PaymentProcessor pay) {    // charge, then open barrier
        return lot.unpark(plate, pay);
    }
    /** The driver lost the ticket: charge the daily cap through the lot, then open the barrier. */
    long lostTicket(String plate, PaymentProcessor pay, long dailyCapPaise) {
        return lot.reportLost(plate, pay, dailyCapPaise);
    }
}



/**
 * Proof it works: park, fill, reject, unpark, a fee, a lost ticket, and fifty gates racing for one spot
 * with exactly one winner.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        ParkingLot lot = ParkingLot.getInstance();
        lot.configure(new FlatHourlyPricing(), new SmallestFitStrategy());

        ParkingFloor f1 = new ParkingFloor("F1");
        f1.addObserver(new DisplayBoard());
        f1.addSpot(new ParkingSpot("F1-S1", SpotType.SMALL));
        f1.addSpot(new ParkingSpot("F1-C1", SpotType.COMPACT));
        f1.addSpot(new ParkingSpot("F1-L1", SpotType.LARGE));
        lot.addFloor(f1);

        Ticket t = lot.park(new Car("KA01AB1234"));       // -> COMPACT
        System.out.println("parked at " + t.spot.id);
        lot.park(new Truck("KA02CD9999"));                // -> LARGE
        try { lot.park(new Car("KA03EF0001")); }          // compact+large gone, small can't fit
        catch (Exception e) { System.out.println("expected: " + e.getMessage()); }
        System.out.println("availability " + lot.availability() + " fullForCar=" + lot.isFullFor(VehicleType.CAR));
        System.out.println("F1 small free = " + lot.freeCount("F1", SpotType.SMALL));   // what the board asks, O(1)
        long fee = lot.unpark("KA01AB1234", new CardPayment());
        System.out.println("fee for car: " + fee + " paise");   // 1 hour x Rs 20 = 2000 paise (100 paise = one rupee)

        // the race: fifty gates, one compact spot, released by one latch; exactly one must win
        EntryGate gate = new EntryGate(lot);
        ExecutorService pool = Executors.newFixedThreadPool(50);   // one thread per gate: all fifty really wait at the latch
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Ticket>> tries = new ArrayList<>();
        for (int i = 0; i < 50; i++) { String plate = "RACE-" + i; tries.add(pool.submit(() -> { go.await(); return gate.admit(new Car(plate)); })); }
        go.countDown();
        int wins = 0; String winner = null;
        for (Future<Ticket> f : tries) { try { winner = f.get().vehicle.plate; wins++; } catch (ExecutionException e) { /* "Lot full for CAR" for the 49 losers */ } }
        pool.shutdown();
        System.out.println("race winners = " + wins + " (must be 1)");
        if (wins != 1) throw new AssertionError("double-booking!");
        System.out.println("lost ticket fee: " + new ExitGate(lot).lostTicket(winner, new CashPayment(), 20_000) + " paise");   // the daily cap, Rs 200
    }
}
