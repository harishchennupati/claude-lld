import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/** The classes a train sells. Each class is its own pool of berths, RAC places and waitlist; nothing crosses between classes. */
enum TravelClass { SLEEPER, AC3, AC2 }

/** Where a berth sits in its bay of eight. Only a berth chooser reads it, to honour preferences such as a lower berth. */
enum BerthType { LOWER, MIDDLE, UPPER, SIDE_LOWER, SIDE_UPPER }

/** A passenger's place right now: his own berth, half of a shared side-lower berth (RAC), a waitlist number, or nothing. */
enum PassengerStatus { CONFIRMED, RAC, WAITLISTED, CANCELLED }

/**
 * A PNR's life. PENDING_PAYMENT while its places are held for ten minutes; BOOKED once paid (this is the ticket);
 * EXPIRED if the hold ran out first; CANCELLED if it was given back.
 */
enum PnrStatus { PENDING_PAYMENT, BOOKED, EXPIRED, CANCELLED }

/**
 * One stop on a route: the station code, the time the train leaves it (minutes after midnight; at the last stop,
 * the time it arrives), how many days after the first stop that is, and the distance from the first stop.
 */
record Stop(String station, int timeMin, int dayOffset, int km) {}

/** One coach in the layout: its id (B1), its class, and how many bays of eight berths it has. */
record Coach(String id, TravelClass cls, int bays) {}

/** Who wants to travel: a name, an age, and a berth preference (null = anything). Input only; never changed. */
record Traveller(String name, int age, BerthType preference) {}

/** One search hit: the run to book on, and when it leaves the first station and reaches the second. */
record Journey(TrainRun run, String from, String to, LocalDateTime departs, LocalDateTime arrives, int km) {}

/** What one class has left for one journey: free berths, free RAC halves, and how full the two queues are. */
record Availability(int berths, int racPlaces, int racQueued, int waitlisted, int waitlistCap) {
    /**
     * The line a search page prints, as IRCTC does: AVAILABLE 3 (berths free), else RAC 2 or WL 4 (the number the next
     * passenger would get), else REGRET when even the waitlist is full.
     */
    String label() {
        if (berths > 0) return "AVAILABLE " + berths;
        if (racPlaces > 0) return "RAC " + (racQueued + 1);
        if (waitlisted < waitlistCap) return "WL " + (waitlisted + 1);
        return "REGRET";
    }
}

/** A change a passenger should hear about (booked, moved up, cancelled). Published after the run's lock is released. */
record PnrEvent(String pnr, String passenger, String what) {}

/**
 * The timetable: a numbered train with a fixed route and a fixed coach layout. Catalog only: nothing here changes
 * while anybody books, and it holds no availability. Availability lives on a TrainRun, one per date.
 */
final class Train {
    final String number;
    final String name;
    final List<Stop> stops;
    final List<Coach> coaches;
    private final Map<String, Integer> stopNo = new HashMap<>();      // station -> its position on the route, O(1)

    Train(String number, String name, List<Stop> stops, List<Coach> coaches) {
        if (stops.size() < 2) throw new IllegalArgumentException("a route needs at least two stops");
        this.number = number; this.name = name; this.stops = List.copyOf(stops); this.coaches = List.copyOf(coaches);
        for (int i = 0; i < stops.size(); i++) {
            if (stopNo.put(stops.get(i).station(), i) != null)
                throw new IllegalArgumentException("station " + stops.get(i).station() + " appears twice on train " + number);
            if (i > 0 && (stops.get(i).km() <= stops.get(i - 1).km() || stops.get(i).dayOffset() < stops.get(i - 1).dayOffset()))
                throw new IllegalArgumentException("kilometres and days must go forward along the route of train " + number);
        }
    }
    /** The position of a station on this route (0 = the first stop), or -1 when the train does not stop there. */
    int stopNo(String station) { return stopNo.getOrDefault(station, -1); }
    /** How many segments the route has: one fewer than its stops. Segment i is the track from stop i to stop i + 1. */
    int segments() { return stops.size() - 1; }
    /** Kilometres from stop a to stop b. */
    int km(int a, int b) { return stops.get(b).km() - stops.get(a).km(); }
}

/**
 * One berth on one run, or one half of a side-lower berth shared by two RAC passengers. It has no free-or-sold
 * status. It has a bitmap with one bit per segment of the route, set where that segment is sold. Every read and
 * write happens under its run's lock.
 */
final class Berth {
    final String coach;
    final int number;
    final BerthType type;
    final boolean shared;                          // true = an RAC half: two of these make one side-lower berth
    private final BitSet sold = new BitSet();      // bit i set = segment i is sold

    Berth(String coach, int number, BerthType type, boolean shared) {
        this.coach = coach; this.number = number; this.type = type; this.shared = shared;
    }
    /** True when no segment in [from, to) is sold: the first sold bit at or after from is at or after to. */
    boolean isFree(int from, int to) { int s = sold.nextSetBit(from); return s < 0 || s >= to; }
    /** Sell segments [from, to). It refuses to overwrite: selling a segment twice is a bug, never a quiet overwrite. */
    void take(int from, int to) {
        if (!isFree(from, to)) throw new IllegalStateException(label() + " is already sold on part of segments " + from + "-" + to);
        sold.set(from, to);
    }
    /** Give segments [from, to) back. Only the passenger who holds them calls this, so nobody else's bits are touched. */
    void release(int from, int to) { sold.clear(from, to); }
    /** The sold segments as one 64-bit number (bit i = segment i), for routes of up to 64 segments: the database column. */
    long mask() { long[] w = sold.toLongArray(); return w.length == 0 ? 0 : w[0]; }
    /** How a ticket prints it: B1/23, or "B1/7 shared" for an RAC half. */
    String label() { return coach + "/" + number + (shared ? " shared" : ""); }
}

/**
 * One traveller on one PNR, and where he is right now. The run creates it, never the caller, so no object is ever
 * shared by two bookings. The changing fields are written only under the run's lock; volatile, so a reader
 * outside the lock sees the latest value.
 */
final class Passenger {
    final Traveller who;
    final Pnr pnr;
    volatile PassengerStatus status = PassengerStatus.WAITLISTED;
    volatile Berth place;                          // his berth (CONFIRMED) or his shared half (RAC); null otherwise
    Passenger(Traveller who, Pnr pnr) { this.who = who; this.pnr = pnr; }
}

/**
 * A booking reference: who travels, between which stops, in which class, for how much, and where it is in its
 * life. The fare is frozen when the places are taken, so paying can never quietly reprice it.
 */
final class Pnr {
    final String id;
    final TrainRun run;
    final String userId;
    final TravelClass cls;
    final int from, to;                            // stop numbers: the journey covers segments [from, to)
    final List<Passenger> passengers;
    final long amountPaise;                        // integer paise for the whole group: money is never a double
    final long holdExpiresMs;
    volatile PnrStatus status = PnrStatus.PENDING_PAYMENT;
    volatile String paymentRef;                    // what the gateway gave back; needed to refund
    Pnr(String id, TrainRun run, String userId, TravelClass cls, int from, int to, List<Traveller> group,
        long amountPaise, long holdExpiresMs) {
        this.id = id; this.run = run; this.userId = userId; this.cls = cls; this.from = from; this.to = to;
        this.amountPaise = amountPaise; this.holdExpiresMs = holdExpiresMs;
        List<Passenger> ps = new ArrayList<>();
        for (Traveller t : group) ps.add(new Passenger(t, this));
        this.passengers = List.copyOf(ps);
    }
}

/** Not enough places for the whole group, or not enough berths when only berths were wanted. Nothing was held. */
class NoPlaces extends RuntimeException { NoPlaces(String m) { super(m); } }
/** The hold ran out before the payment came back. The caller refunds whatever was charged. */
class HoldLapsed extends RuntimeException { HoldLapsed(String m) { super(m); } }
/** The gateway said no. The places stay held until the hold runs out, so the user can try another card. */
class PaymentDeclined extends RuntimeException { PaymentDeclined(String m) { super(m); } }

/** Where time comes from. Handed in, so a test can make ten minutes pass without sleeping. */
interface Clock { long nowMs(); }

// "fares will change: a festival week, Tatkal, flexi-fare" -> hide the rule behind an interface -> Strategy
/** What ONE passenger pays for a journey, in paise. Called inside the run's lock, so it must stay arithmetic. */
interface FareRule { long farePaise(TrainRun run, int from, int to, TravelClass cls); }

/** The base rule: paise per kilometre by class (made-up rates). A table, not an if-chain, so a new class is one row. */
final class DistanceFare implements FareRule {
    private static final Map<TravelClass, Long> PER_KM = new EnumMap<>(Map.of(
        TravelClass.SLEEPER, 50L, TravelClass.AC3, 140L, TravelClass.AC2, 200L));
    /** Rate times kilometres: 3A from Pune to Bengaluru is 140 x 868 = 121,520 paise. */
    public long farePaise(TrainRun run, int from, int to, TravelClass cls) { return PER_KM.get(cls) * run.train.km(from, to); }
}

/**
 * Journeys on peak days (a festival week) cost more: a NEW rule that wraps the one it is given (Decorator). It
 * reads the run's date, never the clock, so a booking made in September for a Diwali train pays the Diwali fare.
 */
final class PeakDayFare implements FareRule {
    private final FareRule base;
    private final Set<LocalDate> peakDays;
    private final int percent;                     // 120 = one fifth more
    PeakDayFare(FareRule base, Set<LocalDate> peakDays, int percent) { this.base = base; this.peakDays = Set.copyOf(peakDays); this.percent = percent; }
    /** The wrapped fare, times percent / 100 on a peak day; integer paise, rounded down. */
    public long farePaise(TrainRun run, int from, int to, TravelClass cls) {
        long f = base.farePaise(run, from, to, cls);
        return peakDays.contains(run.date) ? f * percent / 100 : f;
    }
}

// "the family wants to sit together; grandma needs a lower berth" -> which berths is a rule -> Strategy
/**
 * Which free berths a group gets. Given the berths free for the whole journey (in coach order) and the group, it
 * returns one entry per traveller, in the group's order: a berth, or null for no berth. It only decides WHICH
 * berths; the run insists on HOW MANY: as many as there are travellers or free berths, whichever is smaller.
 */
interface BerthChooser { List<Berth> choose(List<Berth> free, List<Traveller> group); }

/** The default: the first free berths in coach and berth order, to the travellers in the order they were listed. */
final class FirstFreeBerths implements BerthChooser {
    /** Traveller i gets free berth i while they last; the rest get null (RAC or waitlist). */
    public List<Berth> choose(List<Berth> free, List<Traveller> group) {
        List<Berth> out = new ArrayList<>();
        for (int i = 0; i < group.size(); i++) out.add(i < free.size() ? free.get(i) : null);
        return out;
    }
}

/** How much of a cancelled, paid PNR goes back, in paise. Called inside the run's lock, before anybody moves up. */
interface RefundRule { long refundPaise(Pnr p, long nowMs); }

/** The default: everything back. The railway's time-based rule is follow-up 9, one new class. */
final class FullRefund implements RefundRule {
    /** The whole amount that was paid. */
    public long refundPaise(Pnr p, long nowMs) { return p.amountPaise; }
}

/**
 * How money moves. charge takes an idempotency key (a unique id for this payment, so a retry that arrives twice is
 * charged once): the PNR. It returns the payment reference, or null when declined. refund gives one reference
 * back, at most once.
 */
interface PaymentGateway {
    String charge(String idempotencyKey, long paise);
    void refund(String paymentRef, long paise);
}

/** A UPI gateway stand-in. A real call takes a second or two, which is why it is never made inside the lock. */
final class UpiGateway implements PaymentGateway {
    private final AtomicInteger seq = new AtomicInteger();
    private final Map<String, String> byKey = new ConcurrentHashMap<>();      // the gateway's memory of keys
    private final Set<String> refunded = ConcurrentHashMap.newKeySet();
    /** One reference per key: a second call with the same key returns the first charge, and moves no money. */
    public String charge(String key, long paise) { return byKey.computeIfAbsent(key, k -> "UPI-" + seq.incrementAndGet()); }
    /** Gives the money back once per reference. */
    public void refund(String ref, long paise) { if (refunded.add(ref)) System.out.println("[refund] " + Main.rupees(paise) + " against " + ref); }
}

// "text the passenger when his waitlisted ticket confirms" -> publish/subscribe -> Observer
/** Anyone who wants to hear that a PNR changed: an SMS sender, analytics. Called after the run's lock is released. */
interface PnrObserver { void onEvent(PnrEvent e); }

/** Prints the SMS a passenger would get. A real one talks to a gateway, which must never happen inside the lock. */
final class SmsNotifier implements PnrObserver {
    /** One line per event. */
    public void onEvent(PnrEvent e) { System.out.println("[sms] PNR " + e.pnr() + (e.passenger().isEmpty() ? "" : " " + e.passenger()) + ": " + e.what()); }
}

/**
 * One class on one run: its berths, its shared RAC halves, and two queues in arrival order. Owned and guarded by
 * the run; nothing here takes a lock of its own.
 */
final class ClassInventory {
    final TravelClass cls;
    final int waitlistCap;
    final List<Berth> berths = new ArrayList<>();                        // coach order, then berth number
    final List<Berth> racHalves = new ArrayList<>();                     // two per side-lower berth kept for RAC
    final LinkedHashSet<Passenger> rac = new LinkedHashSet<>();          // RAC passengers, earliest first; O(1) remove
    final LinkedHashSet<Passenger> waitlist = new LinkedHashSet<>();     // waitlisted passengers, earliest first

    ClassInventory(TravelClass cls, int waitlistCap) { this.cls = cls; this.waitlistCap = waitlistCap; }
    /** Every place in the list that is free for all of [from, to), in order. One pass: one word test per place. */
    static List<Berth> free(List<Berth> places, int from, int to) {
        List<Berth> out = new ArrayList<>();
        for (Berth b : places) if (b.isFree(from, to)) out.add(b);
        return out;
    }
    /** The first place in the list free for all of [from, to), or null. */
    static Berth firstFree(List<Berth> places, int from, int to) {
        for (Berth b : places) if (b.isFree(from, to)) return b;
        return null;
    }
    /** A passenger's 1-based position in a queue: RAC 2, WL 5. O(queue): for printing, never on the booking path. */
    static int position(Set<Passenger> queue, Passenger p) {
        int i = 1;
        for (Passenger q : queue) { if (q == p) return i; i++; }
        return -1;
    }
}

/**
 * The aggregate root (the one object every change to its berths and queues goes through): one train on one date.
 * It owns every class's berths, RAC halves and waitlist, its PNRs, the holds waiting for payment, and ONE lock.
 * Payment never happens inside it; listeners are called after the lock is released.
 */
final class TrainRun {
    static final int MAX_PASSENGERS = 6;                                  // per PNR, as on IRCTC
    static final ZoneId IST = ZoneId.of("Asia/Kolkata");
    private static final BerthType[] BAY = { BerthType.LOWER, BerthType.MIDDLE, BerthType.UPPER, BerthType.LOWER,
        BerthType.MIDDLE, BerthType.UPPER, BerthType.SIDE_LOWER, BerthType.SIDE_UPPER };
    private static final AtomicLong PNR_SEQ = new AtomicLong(4_210_000_000L);   // ten digits, unique in this process
    final Train train;
    final LocalDate date;                                                 // the day it leaves its FIRST stop
    final String id;                                                      // "12999/2026-10-02"
    private final Map<TravelClass, ClassInventory> classes = new EnumMap<>(TravelClass.class);
    private final Map<String, Pnr> pnrs = new HashMap<>();                // pnr -> booking, O(1)
    private final ArrayDeque<Pnr> holds = new ArrayDeque<>();             // unpaid PNRs, oldest first
    private final ReentrantLock lock = new ReentrantLock(true);           // fair: the longest waiter goes next
    private final Clock clock;
    private final long holdMs;
    private final List<PnrObserver> observers;

    TrainRun(Train train, LocalDate date, Clock clock, long holdMs, int racBerthsPerClass, int waitlistCap,
             List<PnrObserver> observers) {
        if (racBerthsPerClass < 0 || waitlistCap < 0) throw new IllegalArgumentException("RAC berths and the waitlist cap cannot be negative");
        this.train = train; this.date = date; this.id = train.number + "/" + date;
        this.clock = clock; this.holdMs = holdMs; this.observers = observers;
        for (Coach c : train.coaches) {                                   // every run gets its own berth objects
            ClassInventory inv = classes.computeIfAbsent(c.cls(), k -> new ClassInventory(k, waitlistCap));
            for (int bay = 0; bay < c.bays(); bay++)
                for (int k = 0; k < BAY.length; k++) inv.berths.add(new Berth(c.id(), bay * BAY.length + k + 1, BAY[k], false));
        }
        for (ClassInventory inv : classes.values()) {                     // the last side lowers of a class become RAC berths
            List<Berth> kept = new ArrayList<>();
            for (int i = inv.berths.size() - 1; i >= 0 && kept.size() < racBerthsPerClass; i--)
                if (inv.berths.get(i).type == BerthType.SIDE_LOWER) kept.add(0, inv.berths.remove(i));
            for (Berth b : kept) {                                        // two passengers share each one
                inv.racHalves.add(new Berth(b.coach, b.number, b.type, true));
                inv.racHalves.add(new Berth(b.coach, b.number, b.type, true));
            }
        }
    }

    /**
     * Book a group from one station to another in one class. Under the lock, in two passes: first decide a place
     * for every traveller (a berth, else an RAC half, else the waitlist) while writing nothing; then write them all.
     * If the group does not fit, it throws NoPlaces and nothing was held. The PNR comes back PENDING_PAYMENT.
     */
    Pnr book(String userId, String fromStation, String toStation, TravelClass cls, List<Traveller> group,
             boolean berthsOnly, FareRule fare, BerthChooser chooser) {
        int from = stop(fromStation), to = stop(toStation);
        if (from >= to) throw new IllegalArgumentException("a journey goes forward along the route: " + fromStation + " -> " + toStation);
        if (group.isEmpty() || group.size() > MAX_PASSENGERS)
            throw new IllegalArgumentException("one to " + MAX_PASSENGERS + " passengers per PNR, not " + group.size());
        List<PnrEvent> events = new ArrayList<>();
        lock.lock();                                                      // decide-then-take is ONE step: the race lives in the gap
        try {
            long now = clock.nowMs();                                     // read inside the lock, so callers agree about expiry
            sweepLocked(now, events);                                     // lapsed holds go back first, and to the waitlist first
            if (now >= departsMs(from)) throw new IllegalStateException("train " + train.number + " has already left " + fromStation);
            ClassInventory inv = inventory(cls);
            List<Berth> free = ClassInventory.free(inv.berths, from, to);            // pass one: look, do not touch
            List<Berth> pick = chooser.choose(free, group);
            int berths = checked(pick, free, group.size());                          // the rule chose which; the run checks how many
            int missing = group.size() - berths;
            if (berthsOnly && missing > 0)
                throw new NoPlaces("only " + berths + " berths free " + fromStation + "-" + toStation + " for " + group.size() + " passengers");
            List<Berth> halves = missing == 0 ? List.of() : ClassInventory.free(inv.racHalves, from, to);
            int toRac = Math.min(missing, halves.size()), toWait = missing - toRac;
            if (inv.waitlist.size() + toWait > inv.waitlistCap) throw new NoPlaces("REGRET: the " + cls + " waitlist is full");
            long amount = fare.farePaise(this, from, to, cls) * group.size();       // arithmetic on fields we already have
            // nothing above this line wrote anything; below it, every step is a field write that cannot fail
            Pnr p = new Pnr(String.valueOf(PNR_SEQ.incrementAndGet()), this, userId, cls, from, to, group, amount, now + holdMs);
            int h = 0;
            for (int i = 0; i < group.size(); i++) {                                 // pass two: take them all
                Passenger x = p.passengers.get(i);
                if (pick.get(i) != null) seat(x, pick.get(i), PassengerStatus.CONFIRMED);
                else if (h < toRac) { seat(x, halves.get(h++), PassengerStatus.RAC); inv.rac.add(x); }
                else { x.status = PassengerStatus.WAITLISTED; inv.waitlist.add(x); }
            }
            pnrs.put(p.id, p);
            holds.addLast(p);                                             // every hold is ten minutes: the oldest is at the head
            return p;
        } finally { lock.unlock(); publish(events); }
    }

    /**
     * The commit half of paying. It releases lapsed holds first, so a hold that ran out while the card was being
     * charged is already EXPIRED here; then it marks this PNR BOOKED. true = this call booked it; false = a racing
     * retry already had (the caller refunds only a second, different payment). Throws HoldLapsed when the hold is gone.
     */
    boolean commit(Pnr p, String paymentRef) {
        List<PnrEvent> events = new ArrayList<>();
        lock.lock();
        try {
            long now = clock.nowMs();
            sweepLocked(now, events);
            if (p.status == PnrStatus.BOOKED) return false;                         // a second commit books nothing twice
            if (p.status == PnrStatus.PENDING_PAYMENT && p.holdExpiresMs <= now)    // a clock that stepped back can leave
                expireLocked(p, events);                                            // a lapsed hold behind a younger one
            if (p.status != PnrStatus.PENDING_PAYMENT) throw new HoldLapsed("PNR " + p.id + " is " + p.status + ": its places are gone");
            p.paymentRef = paymentRef;
            p.status = PnrStatus.BOOKED;
            events.add(new PnrEvent(p.id, "", "BOOKED " + String.join(", ", statusLocked(p))));
            return true;
        } finally { lock.unlock(); publish(events); }
    }

    /**
     * Give a PNR back: a paid ticket, or a hold the user abandons. Its places go back and the people waiting move up
     * in the SAME locked step, so no new booking can take a freed berth first. Returns the paise to refund: the
     * rule's amount for a paid ticket, 0 for a hold that was never paid.
     */
    long cancel(Pnr p, RefundRule rule) {
        List<PnrEvent> events = new ArrayList<>();
        lock.lock();
        try {
            long now = clock.nowMs();
            sweepLocked(now, events);
            if (p.status == PnrStatus.CANCELLED || p.status == PnrStatus.EXPIRED)
                throw new IllegalStateException("PNR " + p.id + " is already " + p.status);
            long back = p.status == PnrStatus.BOOKED ? Math.max(0, Math.min(p.amountPaise, rule.refundPaise(p, now))) : 0;
            releaseLocked(p);                                             // decided above from the statuses as they were
            p.status = PnrStatus.CANCELLED;
            events.add(new PnrEvent(p.id, "", "CANCELLED, refund " + Main.rupees(back)));
            promoteLocked(inventory(p.cls), events);                      // the freed places go to the waiters, now
            return back;
        } finally { lock.unlock(); publish(events); }
    }

    /** What is left for one journey in one class. It releases lapsed holds first, so the numbers are never stale. */
    Availability availability(String fromStation, String toStation, TravelClass cls) {
        int from = stop(fromStation), to = stop(toStation);
        if (from >= to) throw new IllegalArgumentException("a journey goes forward along the route: " + fromStation + " -> " + toStation);
        List<PnrEvent> events = new ArrayList<>();
        lock.lock();
        try {
            sweepLocked(clock.nowMs(), events);
            ClassInventory inv = inventory(cls);
            int berths = 0, halves = 0;
            for (Berth b : inv.berths) if (b.isFree(from, to)) berths++;             // one word test per berth: no list built
            for (Berth b : inv.racHalves) if (b.isFree(from, to)) halves++;
            return new Availability(berths, halves, inv.rac.size(), inv.waitlist.size(), inv.waitlistCap);
        } finally { lock.unlock(); publish(events); }
    }

    /** Each passenger's line as a PNR enquiry prints it: CNF B1/23 LOWER, RAC 2 B1/7 shared, WL 4, or CANCELLED. */
    List<String> status(Pnr p) {
        List<PnrEvent> events = new ArrayList<>();
        lock.lock();
        try { sweepLocked(clock.nowMs(), events); return statusLocked(p); }
        finally { lock.unlock(); publish(events); }
    }

    /** Release every lapsed hold now instead of at the next call. A sweeper calls this so SMSes are not late. */
    int sweep() {
        List<PnrEvent> events = new ArrayList<>();
        lock.lock();
        try { return sweepLocked(clock.nowMs(), events); }
        finally { lock.unlock(); publish(events); }
    }

    /** A PNR of this run by id, or null. O(1). */
    Pnr pnr(String pnrId) { lock.lock(); try { return pnrs.get(pnrId); } finally { lock.unlock(); } }
    /** Every PNR of this run, copied under the lock: for reports, and for the tests that check the invariants. */
    List<Pnr> pnrs() { lock.lock(); try { return new ArrayList<>(pnrs.values()); } finally { lock.unlock(); } }

    /** A copy of every berth's sold mask in a class, taken under the lock: for a read path that must not take it again. */
    long[] soldMasks(TravelClass cls) {
        List<PnrEvent> events = new ArrayList<>();
        lock.lock();
        try {
            sweepLocked(clock.nowMs(), events);
            List<Berth> bs = inventory(cls).berths;
            long[] out = new long[bs.size()];
            for (int i = 0; i < out.length; i++) out[i] = bs.get(i).mask();
            return out;
        } finally { lock.unlock(); publish(events); }
    }

    /** Tenths of a class already sold for a journey, 0 to 10. For a fare rule; re-entrant, so book() may call it. */
    int soldTenths(TravelClass cls, int from, int to) {
        lock.lock();
        try {
            ClassInventory inv = inventory(cls);
            int taken = 0;
            for (Berth b : inv.berths) if (!b.isFree(from, to)) taken++;
            return inv.berths.isEmpty() ? 10 : taken * 10 / inv.berths.size();
        } finally { lock.unlock(); }
    }

    /** When the train leaves a stop, in epoch milliseconds (Indian time). The last stop's time is its arrival. */
    long departsMs(int stop) { return at(stop).atZone(IST).toInstant().toEpochMilli(); }
    /** The local date and time the train is at a stop on this run. */
    LocalDateTime at(int stop) {
        Stop s = train.stops.get(stop);
        return date.plusDays(s.dayOffset()).atStartOfDay().plusMinutes(s.timeMin());
    }
    /** A class's inventory. Package-private so tests can check invariants; callers outside the lock must not write. */
    ClassInventory inventory(TravelClass cls) {
        ClassInventory inv = classes.get(cls);
        if (inv == null) throw new NoSuchElementException("train " + train.number + " has no " + cls + " coaches");
        return inv;
    }

    // ---- everything below runs with the lock already held ----

    /** A station's stop number on this route, or an exception naming it. */
    private int stop(String station) {
        int i = train.stopNo(station);
        if (i < 0) throw new IllegalArgumentException("train " + train.number + " does not stop at " + station);
        return i;
    }

    /** The chooser's answer, checked: one entry per traveller, each berth from the free list and used once, and as many as can be given. */
    private static int checked(List<Berth> pick, List<Berth> free, int travellers) {
        if (pick.size() != travellers) throw new IllegalStateException("the berth rule answered for " + pick.size() + " of " + travellers + " travellers");
        Set<Berth> seen = new HashSet<>();
        for (Berth b : pick)
            if (b != null && (!free.contains(b) || !seen.add(b)))
                throw new IllegalStateException("the berth rule chose " + b.label() + ", which is not free or is chosen twice");
        if (seen.size() != Math.min(travellers, free.size()))
            throw new IllegalStateException("the berth rule left a free berth empty while a traveller would wait");
        return seen.size();
    }

    /** Put a passenger on a berth or an RAC half for his journey. Lock held. */
    private static void seat(Passenger x, Berth b, PassengerStatus status) {
        b.take(x.pnr.from, x.pnr.to);
        x.place = b;
        x.status = status;
    }

    /** Release every hold whose time is up, oldest first; each one's places go to the waiters. Returns how many. Lock held. */
    private int sweepLocked(long now, List<PnrEvent> events) {
        int n = 0;
        while (!holds.isEmpty() && holds.peekFirst().holdExpiresMs <= now) {
            Pnr p = holds.pollFirst();
            if (p.status != PnrStatus.PENDING_PAYMENT) continue;          // paid or cancelled in time: just drop it
            expireLocked(p, events);
            n++;
        }
        return n;
    }

    /** One unpaid hold dies: its places go back, the PNR is EXPIRED, and the waiters move up. Lock held. */
    private void expireLocked(Pnr p, List<PnrEvent> events) {
        releaseLocked(p);
        p.status = PnrStatus.EXPIRED;
        events.add(new PnrEvent(p.id, "", "EXPIRED: not paid within the hold"));
        promoteLocked(inventory(p.cls), events);
    }

    /** Take every passenger of this PNR off whatever he holds: his segments, his RAC half, his queue place. Lock held. */
    private void releaseLocked(Pnr p) {
        ClassInventory inv = inventory(p.cls);
        for (Passenger x : p.passengers) {
            if (x.place != null) { x.place.release(p.from, p.to); x.place = null; }
            inv.rac.remove(x);
            inv.waitlist.remove(x);
            x.status = PassengerStatus.CANCELLED;
        }
    }

    /**
     * Hand freed places to the people already waiting, earliest first, before anybody new can ask. RAC passengers
     * try for a berth; then waitlisted ones try for a berth, else an RAC half. A waiter whose journey does not fit
     * is skipped and keeps his place. One pass is enough: the RAC half gives back only RAC halves, and the
     * waitlist half runs after it and only takes places. Lock held.
     */
    private void promoteLocked(ClassInventory inv, List<PnrEvent> events) {
        int n = 0;
        for (Passenger x : new ArrayList<>(inv.rac)) {                    // RAC first, in RAC order
            n++;
            Berth b = ClassInventory.firstFree(inv.berths, x.pnr.from, x.pnr.to);
            if (b == null) continue;                                      // no berth fits his journey: he stays RAC
            x.place.release(x.pnr.from, x.pnr.to);                        // his shared half goes back
            inv.rac.remove(x);
            seat(x, b, PassengerStatus.CONFIRMED);
            events.add(new PnrEvent(x.pnr.id, x.who.name(), "RAC " + n + " -> CNF " + b.label()));
        }
        int w = 0;
        for (Passenger x : new ArrayList<>(inv.waitlist)) {               // then the waitlist, in order
            w++;
            Berth b = ClassInventory.firstFree(inv.berths, x.pnr.from, x.pnr.to);
            if (b != null) {
                inv.waitlist.remove(x);
                seat(x, b, PassengerStatus.CONFIRMED);
                events.add(new PnrEvent(x.pnr.id, x.who.name(), "WL " + w + " -> CNF " + b.label()));
                continue;
            }
            Berth half = ClassInventory.firstFree(inv.racHalves, x.pnr.from, x.pnr.to);
            if (half == null) continue;                                   // nothing fits: he keeps his place
            inv.waitlist.remove(x);
            seat(x, half, PassengerStatus.RAC);
            inv.rac.add(x);
            events.add(new PnrEvent(x.pnr.id, x.who.name(), "WL " + w + " -> RAC " + inv.rac.size() + " " + half.label()));
        }
    }

    /** The status lines of a PNR. Lock held. */
    private List<String> statusLocked(Pnr p) {
        ClassInventory inv = inventory(p.cls);
        List<String> out = new ArrayList<>();
        for (Passenger x : p.passengers) {
            String s = switch (x.status) {
                case CONFIRMED -> "CNF " + x.place.label() + " " + x.place.type;
                case RAC -> "RAC " + ClassInventory.position(inv.rac, x) + " " + x.place.label();
                case WAITLISTED -> "WL " + ClassInventory.position(inv.waitlist, x);
                case CANCELLED -> "CANCELLED";
            };
            out.add(x.who.name() + " " + s);
        }
        return out;
    }

    /** Tell every listener, after the lock is released, and survive a broken one. */
    private void publish(List<PnrEvent> events) {
        for (PnrEvent e : events)
            for (PnrObserver o : observers) {
                try { o.onEvent(e); } catch (RuntimeException ex) { System.err.println("[listener failed] " + ex.getMessage()); }
            }
    }
}

/**
 * The orchestrator. It owns the catalog, the runs, the station index for search, and the handed-in rules; it
 * sequences book, then payment OUTSIDE any lock, then commit. It holds no berth state of its own.
 */
final class BookingService {
    private final Map<String, Train> trains = new ConcurrentHashMap<>();
    private final Map<String, TrainRun> runs = new ConcurrentHashMap<>();                  // "12999/2026-10-02" -> run
    private final Map<String, Map<String, Integer>> atStation = new ConcurrentHashMap<>(); // station -> train -> stop number
    private final Map<String, TrainRun> byPnr = new ConcurrentHashMap<>();                 // pnr -> its run, O(1)
    private final List<PnrObserver> observers = new CopyOnWriteArrayList<>();
    private final Clock clock;
    private final long holdMs;
    private volatile FareRule fare = new DistanceFare();          // volatile: a swap is seen by every booking thread
    private volatile BerthChooser chooser = new FirstFreeBerths();
    private volatile RefundRule refund = new FullRefund();

    BookingService(Clock clock, long holdMs) { this.clock = clock; this.holdMs = holdMs; }

    /** Hand in the rules. The service never builds one, so a swap is one new rule and this line. */
    void configure(FareRule fare, BerthChooser chooser, RefundRule refund) { this.fare = fare; this.chooser = chooser; this.refund = refund; }
    /** Subscribe a listener; it hears every run's events, after the lock. */
    void addObserver(PnrObserver o) { observers.add(o); }

    /** Add a train to the timetable and index every stop, so search is a map lookup and not a scan of all trains. */
    void addTrain(Train t) {
        trains.put(t.number, t);
        for (int i = 0; i < t.stops.size(); i++)
            atStation.computeIfAbsent(t.stops.get(i).station(), k -> new ConcurrentHashMap<>()).put(t.number, i);
    }
    /** Open a run of a train for booking: the train leaving its first stop on this date. */
    TrainRun addRun(String trainNo, LocalDate date, int racBerthsPerClass, int waitlistCap) {
        TrainRun r = new TrainRun(train(trainNo), date, clock, holdMs, racBerthsPerClass, waitlistCap, observers);
        if (runs.putIfAbsent(r.id, r) != null) throw new IllegalStateException("run " + r.id + " already exists");
        return r;
    }
    /** A train by number: its route and times ("search by train number"). */
    Train train(String number) {
        Train t = trains.get(number);
        if (t == null) throw new NoSuchElementException("no train " + number);
        return t;
    }
    /** A run by id, "12999/2026-10-02". */
    TrainRun run(String runId) {
        TrainRun r = runs.get(runId);
        if (r == null) throw new NoSuchElementException("no run " + runId);
        return r;
    }

    /**
     * Trains from one station to another on a date, where the date is the day the passenger BOARDS. A train that
     * reaches the boarding station on its second day belongs to the run that started the day before. Walks only the
     * trains that stop at the boarding station; earliest departure first. Takes no run's lock.
     */
    List<Journey> search(String from, String to, LocalDate date) {
        List<Journey> out = new ArrayList<>();
        Map<String, Integer> atTo = atStation.getOrDefault(to, Map.of());
        for (Map.Entry<String, Integer> e : atStation.getOrDefault(from, Map.of()).entrySet()) {
            Integer j = atTo.get(e.getKey());
            int i = e.getValue();
            if (j == null || j <= i) continue;                              // does not stop there, or goes the other way
            Train t = trains.get(e.getKey());
            TrainRun r = runs.get(t.number + "/" + date.minusDays(t.stops.get(i).dayOffset()));
            if (r != null) out.add(new Journey(r, from, to, r.at(i), r.at(j), t.km(i, j)));
        }
        out.sort(Comparator.comparing(Journey::departs));
        return out;
    }

    /** What a class has left for a journey on a run: berths, RAC halves, waitlist. */
    Availability availability(String runId, String from, String to, TravelClass cls) { return run(runId).availability(from, to, cls); }

    /** Step one: hold places for a group for ten minutes. Returns a PENDING_PAYMENT PNR, or throws NoPlaces. */
    Pnr book(String runId, String userId, String from, String to, TravelClass cls, List<Traveller> group, boolean berthsOnly) {
        TrainRun r = run(runId);
        Pnr p = r.book(userId, from, to, cls, group, berthsOnly, fare, chooser);
        byPnr.put(p.id, r);
        return p;
    }

    /**
     * Steps two and three: charge with NO lock held, then commit under the run's lock. The PNR is the idempotency
     * key, so a retry or a double tap is charged once. A decline releases nothing; a lapsed hold refunds.
     */
    Pnr pay(String pnrId, PaymentGateway gateway) {
        Pnr p = find(pnrId);
        if (p.status != PnrStatus.PENDING_PAYMENT)                               // refused before any money moves
            throw new IllegalStateException("PNR " + pnrId + " is " + p.status);
        String ref = gateway.charge(p.id, p.amountPaise);                        // OUTSIDE the lock: a gateway takes seconds
        if (ref == null) throw new PaymentDeclined("declined " + Main.rupees(p.amountPaise) + "; the places stay held until the hold runs out");
        boolean mine;
        try { mine = p.run.commit(p, ref); }
        catch (HoldLapsed e) { gateway.refund(ref, p.amountPaise); throw e; }   // money moved, the places did not: give it back
        if (!mine && !ref.equals(p.paymentRef)) gateway.refund(ref, p.amountPaise);   // same key = same charge; refund only a second one
        return p;
    }

    /** Cancel a PNR: places back and waiters up under the lock, then the refund outside it. Returns the paise refunded. */
    long cancel(String pnrId, PaymentGateway gateway) {
        Pnr p = find(pnrId);
        long back = p.run.cancel(p, refund);
        if (back > 0) gateway.refund(p.paymentRef, back);                        // after the lock: a slow refund holds no berth
        return back;
    }

    /** A PNR enquiry: one line per passenger. */
    List<String> status(String pnrId) { Pnr p = find(pnrId); return p.run.status(p); }

    /** A PNR by id, across every run. O(1). */
    Pnr find(String pnrId) {
        TrainRun r = byPnr.get(pnrId);
        Pnr p = r == null ? null : r.pnr(pnrId);
        if (p == null) throw new NoSuchElementException("no PNR " + pnrId);
        return p;
    }
}

/**
 * Proof it works: a search that finds an overnight train, one berth sold twice on different segments, RAC and the
 * waitlist, a cancellation that moves both up, a declined card, a peak-day fare, and two races with exact counts.
 */
public class Main {
    /** Rs 1,215.20 from 121520 paise. */
    static String rupees(long paise) { return String.format("Rs %,d.%02d", paise / 100, paise % 100); }

    /** A made-up train on a real route: Mumbai CSMT to Bengaluru, one 3A coach and one sleeper coach of eight berths each. */
    static Train deccanArrow() {
        return new Train("12999", "Deccan Arrow", List.of(
            new Stop("CSMT", 20 * 60, 0, 0), new Stop("PUNE", 23 * 60 + 15, 0, 192), new Stop("SUR", 4 * 60 + 30, 1, 455),
            new Stop("GTL", 10 * 60 + 20, 1, 790), new Stop("SBC", 16 * 60 + 30, 1, 1060)),
            List.of(new Coach("B1", TravelClass.AC3, 1), new Coach("S1", TravelClass.SLEEPER, 1)));
    }
    /** A traveller with no berth preference. */
    static Traveller t(String name, int age) { return new Traveller(name, age, null); }

    /** The demo: search, one berth sold on two segments, RAC and the waitlist moving up, a decline, a fare, two races. */
    public static void main(String[] args) throws Exception {
        long[] now = { ZonedDateTime.of(2026, 10, 1, 9, 58, 0, 0, TrainRun.IST).toInstant().toEpochMilli() };
        Clock clock = () -> now[0];
        long tenMinutes = 10 * 60_000L;
        BookingService svc = new BookingService(clock, tenMinutes);
        svc.addObserver(new SmsNotifier());
        svc.addTrain(deccanArrow());
        TrainRun run = svc.addRun("12999", LocalDate.of(2026, 10, 2), 1, 3);    // 1 side lower kept for RAC; waitlist of 3
        PaymentGateway upi = new UpiGateway();

        // search by the date you board: from Solapur on the 3rd finds the train that left Mumbai on the 2nd
        for (Journey j : svc.search("SUR", "SBC", LocalDate.of(2026, 10, 3)))
            System.out.println("search SUR->SBC on 3 Oct: " + j.run().id + " leaves " + j.departs() + ", arrives " + j.arrives() + ", " + j.km() + " km");

        // one berth, two passengers: Asha rides CSMT->PUNE, Ravi PUNE->SBC, on the same berth
        Pnr asha = svc.book(run.id, "asha", "CSMT", "PUNE", TravelClass.AC3, List.of(t("Asha", 34)), false);
        svc.pay(asha.id, upi);
        Pnr ravi = svc.book(run.id, "ravi", "PUNE", "SBC", TravelClass.AC3, List.of(t("Ravi", 41)), false);
        svc.pay(ravi.id, upi);
        System.out.println("Asha " + svc.status(asha.id) + " | Ravi " + svc.status(ravi.id) + "  (one berth, two segments of the route)");

        // a family of six takes the rest of 3A for the whole route
        List<Traveller> six = List.of(t("Dev", 45), t("Mira", 43), t("Anu", 12), t("Om", 9), t("Nana", 72), t("Nani", 68));
        Pnr family = svc.book(run.id, "dev", "CSMT", "SBC", TravelClass.AC3, six, false);
        svc.pay(family.id, upi);
        System.out.println("3A from SUR to SBC now: " + svc.availability(run.id, "SUR", "SBC", TravelClass.AC3).label());

        // the class is full on that stretch: Meena and her son share the RAC berth, Kiran goes on the waitlist
        Pnr meena = svc.book(run.id, "meena", "SUR", "SBC", TravelClass.AC3, List.of(t("Meena", 38), t("Arjun", 15)), false);
        Pnr kiran = svc.book(run.id, "kiran", "SUR", "SBC", TravelClass.AC3, List.of(t("Kiran", 29)), false);
        svc.pay(meena.id, upi);
        svc.pay(kiran.id, upi);
        System.out.println("Meena " + svc.status(meena.id) + " | Kiran " + svc.status(kiran.id));

        // Ravi cancels: his PUNE->SBC segments come back and the waiters move up in the same locked step
        System.out.println("Ravi cancels, refund " + rupees(svc.cancel(ravi.id, upi)));
        System.out.println("Meena " + svc.status(meena.id) + " | Kiran " + svc.status(kiran.id));

        // a declined card keeps the hold; ten minutes later the hold is gone and nobody had to sweep it
        Pnr sara = svc.book(run.id, "sara", "CSMT", "PUNE", TravelClass.SLEEPER, List.of(t("Sara", 30)), false);
        try { svc.pay(sara.id, declining()); } catch (PaymentDeclined e) { System.out.println("expected: " + e.getMessage()); }
        System.out.println("after the decline: " + sara.status + " " + svc.status(sara.id));
        now[0] += tenMinutes;
        System.out.println("ten minutes later: " + svc.availability(run.id, "CSMT", "PUNE", TravelClass.SLEEPER).label() + " sleeper berths, PNR " + sara.status);

        // a peak-day surge is a new class and one line
        TrainRun diwali = svc.addRun("12999", LocalDate.of(2026, 11, 7), 1, 3);
        svc.configure(new PeakDayFare(new DistanceFare(), Set.of(LocalDate.of(2026, 11, 7)), 120), new FirstFreeBerths(), new FullRefund());
        Pnr d = svc.book(diwali.id, "zoya", "PUNE", "SBC", TravelClass.AC3, List.of(t("Zoya", 26)), false);
        System.out.println("3A PUNE->SBC on a peak day: " + rupees(d.amountPaise) + " (a normal day: " + rupees(140L * 868) + ")");
        svc.cancel(d.id, upi);

        // race 1: fifty phones, one berth left, berths only: exactly one wins
        TrainRun race = svc.addRun("12999", LocalDate.of(2026, 10, 4), 1, 3);
        svc.book(race.id, "grp", "CSMT", "SBC", TravelClass.AC3, six, true);      // 6 of the 7 bookable berths
        int wins = race(50, i -> svc.book(race.id, "fan" + i, "CSMT", "SBC", TravelClass.AC3, List.of(t("Fan" + i, 30)), true));
        System.out.println("fifty phones, one berth: winners = " + wins + " (must be 1)");
        if (wins != 1) throw new AssertionError("one berth was sold twice");

        // race 2: fifty phones on an empty class: 7 berths + 2 RAC halves + 3 waitlist = 12 places, 38 REGRET
        TrainRun race2 = svc.addRun("12999", LocalDate.of(2026, 10, 5), 1, 3);
        int placed = race(50, i -> svc.book(race2.id, "fan" + i, "PUNE", "GTL", TravelClass.AC3, List.of(t("Fan" + i, 30)), false));
        Availability left = race2.availability("PUNE", "GTL", TravelClass.AC3);
        System.out.println("fifty phones, empty 3A: placed = " + placed + " (must be 12), now " + left.label() + ", waitlist " + left.waitlisted() + "/" + left.waitlistCap());
        if (placed != 12) throw new AssertionError("the count of places is wrong");
    }

    /** Start n threads behind one latch so they really collide; count the calls that returned instead of throwing. */
    static int race(int n, java.util.function.IntFunction<Pnr> call) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(n);                      // one thread per phone
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Pnr>> tries = new ArrayList<>();
        for (int i = 0; i < n; i++) { int k = i; tries.add(pool.submit(() -> { go.await(); return call.apply(k); })); }
        go.countDown();
        int ok = 0;
        for (Future<Pnr> f : tries) { try { f.get(); ok++; } catch (ExecutionException e) { /* NoPlaces for the losers */ } }
        pool.shutdown();
        return ok;
    }

    /** A gateway that always says no, for the decline path. */
    static PaymentGateway declining() {
        return new PaymentGateway() {
            public String charge(String key, long paise) { return null; }
            public void refund(String ref, long paise) { }
        };
    }
}
