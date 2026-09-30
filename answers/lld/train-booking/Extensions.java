import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

// ---- ext: fares that change -- Tatkal and flexi-fare, each a new rule that wraps the one before it
/**
 * Tatkal: the base fare plus a premium of 30% of it, never below a floor or above a cap for the class. The
 * amounts are illustrative; the shape (a percentage with a floor and a cap) is the real rule's shape.
 */
final class TatkalFare implements FareRule {
    private static final Map<TravelClass, long[]> FLOOR_CAP = new EnumMap<>(Map.of(
        TravelClass.SLEEPER, new long[] { 10_000, 20_000 }, TravelClass.AC3, new long[] { 30_000, 40_000 },
        TravelClass.AC2, new long[] { 40_000, 50_000 }));
    private final FareRule base;
    TatkalFare(FareRule base) { this.base = base; }
    /** base + clamp(30% of base, floor, cap), in integer paise. */
    public long farePaise(TrainRun run, int from, int to, TravelClass cls) {
        long f = base.farePaise(run, from, to, cls);
        long[] fc = FLOOR_CAP.get(cls);
        return f + Math.max(fc[0], Math.min(fc[1], f * 30 / 100));
    }
}

/**
 * Flexi-fare: the price climbs 10% for every tenth of the class already sold on that journey, up to 50% more.
 * It reads the run inside book(), where the lock is already held; the lock is re-entrant, so that is safe.
 */
final class FlexiFare implements FareRule {
    private final FareRule base;
    FlexiFare(FareRule base) { this.base = base; }
    /** base x (100 + 10 x tenths sold, at most 150) / 100. */
    public long farePaise(TrainRun run, int from, int to, TravelClass cls) {
        int tenths = Math.min(5, run.soldTenths(cls, from, to));
        return base.farePaise(run, from, to, cls) * (100 + 10 * tenths) / 100;
    }
}

// ---- ext: a family together -- one coach if it fits, lower berths for the seniors
/**
 * Same coach when one coach has room for the whole group; seniors (60 and over) get lower berths first; then
 * each traveller's own preference if it is free; then whatever is left, in order. When there are fewer berths
 * than travellers, seniors get them first. Pure: it reads the free list and writes nothing.
 */
final class FamilyChooser implements BerthChooser {
    /** One entry per traveller, in the group's order; exactly min(group, free) of them are berths. */
    public List<Berth> choose(List<Berth> free, List<Traveller> group) {
        Map<String, List<Berth>> byCoach = new LinkedHashMap<>();
        for (Berth b : free) byCoach.computeIfAbsent(b.coach, k -> new ArrayList<>()).add(b);
        List<Berth> pool = new ArrayList<>(free);                          // no coach fits everyone: use them all
        for (List<Berth> coach : byCoach.values()) if (coach.size() >= group.size()) { pool = new ArrayList<>(coach); break; }
        Integer[] order = new Integer[group.size()];
        for (int i = 0; i < order.length; i++) order[i] = i;
        Arrays.sort(order, Comparator.comparingInt(i -> rank(group.get(i))));   // stable: seniors, then preferences, then the rest
        Berth[] out = new Berth[group.size()];
        int give = Math.min(group.size(), free.size());
        for (int k = 0; k < give; k++) {
            Traveller t = group.get(order[k]);
            Berth b = takeFirst(pool, t.age() >= 60 ? BerthType.LOWER : t.preference());
            if (b == null && t.age() >= 60) b = takeFirst(pool, BerthType.SIDE_LOWER);   // a side lower is still a lower
            if (b == null) b = pool.remove(0);
            out[order[k]] = b;
        }
        return Arrays.asList(out);
    }
    /** 0 = senior, 1 = has a preference, 2 = anything will do. */
    private static int rank(Traveller t) { return t.age() >= 60 ? 0 : t.preference() != null ? 1 : 2; }
    /** Remove and return the first berth of a type, or null (a null type matches nothing). */
    private static Berth takeFirst(List<Berth> pool, BerthType type) {
        for (Iterator<Berth> it = pool.iterator(); it.hasNext(); ) { Berth b = it.next(); if (b.type == type) { it.remove(); return b; } }
        return null;
    }
}

// ---- ext: the railway's refund rule -- how much comes back depends on the hours left and the status
/**
 * The shape of the Indian Railways rule, with illustrative amounts. A confirmed passenger loses a flat charge for
 * his class until 48 hours before departure, a quarter of his fare (at least the flat charge) until 12 hours, half
 * until 4 hours, and everything after that. An RAC or waitlisted passenger loses only a small clerkage fee. It
 * runs inside the run's lock, before anybody moves up, so it sees each passenger's status exactly as it was.
 */
final class RailwayRefund implements RefundRule {
    private static final Map<TravelClass, Long> FLAT = new EnumMap<>(Map.of(
        TravelClass.SLEEPER, 12_000L, TravelClass.AC3, 18_000L, TravelClass.AC2, 20_000L));
    private static final long CLERKAGE = 6_000L;
    /** The sum over passengers, in integer paise, never below zero. */
    public long refundPaise(Pnr p, long nowMs) {
        long each = p.amountPaise / p.passengers.size();                  // the amount is fare x passengers exactly
        long hoursLeft = (p.run.departsMs(p.from) - nowMs) / 3_600_000L;
        long flat = FLAT.get(p.cls), back = 0;
        for (Passenger x : p.passengers) {
            long charge;
            if (x.status != PassengerStatus.CONFIRMED) charge = CLERKAGE;           // RAC or waitlisted
            else if (hoursLeft >= 48) charge = flat;
            else if (hoursLeft >= 12) charge = Math.max(flat, each / 4);
            else if (hoursLeft >= 4) charge = Math.max(flat, each / 2);
            else charge = each;                                                     // chart prepared: nothing back
            back += Math.max(0, each - charge);
        }
        return back;
    }
}

// ---- ext: availability without the walk -- the bitmaps turned sideways
/**
 * For each segment, one bit per berth, set where that berth is FREE on that segment. Free for [from, to) is the AND
 * of rows from .. to-1, then a count of the bits: (to - from) x berths / 64 word operations instead of one test per
 * berth. It is built from a copy of the masks taken under the run's lock, so a reader never touches the lock.
 */
final class SegmentIndex {
    private final BitSet[] freeOn;                                        // freeOn[s]: bit i = berth i is free on segment s
    SegmentIndex(long[] soldMasks, int segments) {
        freeOn = new BitSet[segments];
        for (int s = 0; s < segments; s++) {
            freeOn[s] = new BitSet(soldMasks.length);
            for (int i = 0; i < soldMasks.length; i++) if ((soldMasks[i] & (1L << s)) == 0) freeOn[s].set(i);
        }
    }
    /** How many berths are free on every segment of [from, to). */
    int freeFor(int from, int to) {
        BitSet acc = (BitSet) freeOn[from].clone();
        for (int s = from + 1; s < to; s++) acc.and(freeOn[s]);
        return acc.cardinality();
    }
}

// ---- ext: a sweeper -- so a waitlisted passenger hears about his berth in seconds, not at the next booking
/**
 * Correctness never needs it: every call on a run releases lapsed holds first. But if nobody touches a run for
 * an hour, a hold that lapsed at 10:10 moves nobody up until 11:10. A pass every few seconds fixes that. Each
 * pass takes each run's lock for a few microseconds and lets go.
 */
final class HoldSweeper {
    private final List<TrainRun> runs;
    private final ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor(
        r -> { Thread t = new Thread(r, "hold-sweeper"); t.setDaemon(true); return t; });
    HoldSweeper(List<TrainRun> runs) { this.runs = runs; }
    /** Sweep every run every so many milliseconds; one bad run cannot kill the timer. */
    void start(long everyMs) {
        timer.scheduleAtFixedRate(() -> {
            for (TrainRun r : runs) { try { r.sweep(); } catch (RuntimeException e) { /* keep sweeping the others */ } }
        }, everyMs, everyMs, TimeUnit.MILLISECONDS);
    }
    /** Stop the timer thread. */
    void stop() { timer.shutdownNow(); }
    /** One pass by hand, for tests: how many holds were released. */
    int sweepOnce() { int n = 0; for (TrainRun r : runs) n += r.sweep(); return n; }
}

// ---- ext: a queue in front of a run -- the Tatkal rush, and where Kafka would go
/**
 * One worker thread per run takes booking requests off a bounded queue and runs them one at a time, in arrival
 * order: the in-process picture of a Kafka topic partitioned by run id, one consumer per partition. The caller
 * waits on a future, not on a lock. A full queue refuses at once: back-pressure (telling the caller "try again"
 * instead of queueing without limit).
 */
final class RunQueue {
    private final BlockingQueue<Runnable> queue;
    private final Thread worker;
    RunQueue(String name, int capacity) {
        queue = new ArrayBlockingQueue<>(capacity);
        worker = new Thread(() -> {
            try { while (true) queue.take().run(); } catch (InterruptedException e) { /* stop() was called */ }
        }, name);
        worker.setDaemon(true);
        worker.start();
    }
    /** Queue one request. The future completes with its result or its exception; a full queue fails it at once. */
    <T> CompletableFuture<T> submit(Supplier<T> job) {
        CompletableFuture<T> f = new CompletableFuture<>();
        Runnable r = () -> { try { f.complete(job.get()); } catch (RuntimeException e) { f.completeExceptionally(e); } };
        if (!queue.offer(r)) f.completeExceptionally(new RejectedExecutionException("busy: try again in a moment"));
        return f;
    }
    /** Stop the worker; anything still queued is dropped. */
    void stop() { worker.interrupt(); }
}

// ---- ext: persistence -- the tables, and a booking as one conditional UPDATE per berth
/**
 * The tables are the classes, payments included (the table candidates forget):
 *   station(code PK, name)
 *   train(number PK, name)
 *   train_stop(train_no, seq, station_code, time_min, day_offset, km)    PK(train_no, seq), INDEX(station_code)
 *   coach(train_no, coach_id, class, bays)
 *   train_run(id PK, train_no, origin_date)                               UNIQUE(train_no, origin_date)
 *   run_berth(run_id, berth_id, class, type, shared, sold_mask BIGINT)    PK(run_id, berth_id): bit i = segment i sold
 *   pnr(id PK, run_id, user_id, class, from_seq, to_seq, status, amount_paise, hold_expires_at)
 *   passenger(pnr_id, seq, name, age, status, berth_id NULL, queue_no NULL)   queue_no orders RAC and the waitlist
 *   payment(id PK, pnr_id, idempotency_key UNIQUE, amount_paise, status, gateway_ref)
 * Optimistic: sell segments [2,4) of one berth with one conditional UPDATE; 1 row changed = yours, 0 = taken:
 *   UPDATE run_berth SET sold_mask = sold_mask | :m WHERE run_id = ? AND berth_id = ? AND (sold_mask & :m) = 0
 * A group is one transaction: every row changes, or ROLLBACK. Pessimistic, the same result with one lock per run,
 * exactly like the ReentrantLock:  SELECT id FROM train_run WHERE id = ? FOR UPDATE; read, decide, write; COMMIT.
 * A cancel and the promotion it causes are written in that same transaction.
 */
interface BerthStore {
    /** Sell segments [from, to) on every named berth of a run: all of them, or none. */
    boolean sellAll(String runId, List<String> berthIds, int from, int to);
    /** Give segments [from, to) of one berth back. */
    void release(String runId, String berthId, int from, int to);
    /** The sold mask of one berth: bit i = segment i sold. */
    long mask(String runId, String berthId);
}

/**
 * A stand-in for the run_berth table: one row per berth per run, a 64-bit mask each. Every write is a
 * compare-and-set on the row, which is what the conditional UPDATE does: the row changes only if none of our bits
 * are set. A group takes rows in id order and, at the first refusal, clears what it set: the ROLLBACK.
 */
final class MaskStore implements BerthStore {
    private final ConcurrentHashMap<String, AtomicLong> rows = new ConcurrentHashMap<>();
    /** Insert one empty row. */
    void add(String runId, String berthId) { rows.put(runId + "#" + berthId, new AtomicLong()); }
    /** The bits of segments [from, to), for routes of up to 64 segments. */
    static long bits(int from, int to) { return (to == 64 ? -1L : (1L << to) - 1) ^ ((1L << from) - 1); }
    /** The group claim: every row's bits set, or none (the rows it took are cleared again). */
    public boolean sellAll(String runId, List<String> berthIds, int from, int to) {
        long m = bits(from, to);
        List<AtomicLong> taken = new ArrayList<>();
        for (String id : new TreeSet<>(berthIds)) {                        // one fixed order for every caller
            AtomicLong row = rows.get(runId + "#" + id);
            boolean ok = false;
            while (row != null) {                                         // loops only when OTHER bits changed meanwhile
                long cur = row.get();
                if ((cur & m) != 0) break;                                // WHERE (sold_mask & :m) = 0 failed: 0 rows
                if (row.compareAndSet(cur, cur | m)) { ok = true; break; }
            }
            if (!ok) { for (AtomicLong r : taken) r.getAndUpdate(v -> v & ~m); return false; }   // ROLLBACK
            taken.add(row);
        }
        return true;                                                      // COMMIT
    }
    /** UPDATE run_berth SET sold_mask = sold_mask & ~:m: clears only this journey's bits. */
    public void release(String runId, String berthId, int from, int to) { long m = bits(from, to); rows.get(runId + "#" + berthId).getAndUpdate(v -> v & ~m); }
    /** The row's current mask. */
    public long mask(String runId, String berthId) { return rows.get(runId + "#" + berthId).get(); }
}

// ---- ext: the flight version -- Cleartrip's machine-coding round: sectors, fare types, a wallet
/** A traveller's account on the flight desk: a wallet in integer paise, guarded by this object's own monitor. */
final class FlyUser {
    final String id, name;
    private long fundsPaise;
    FlyUser(String id, String name, long fundsPaise) { this.id = id; this.name = name; this.fundsPaise = fundsPaise; }
    /** Take money out if there is enough; false, and nothing changed, if not. */
    synchronized boolean debit(long paise) { if (paise > fundsPaise) return false; fundsPaise -= paise; return true; }
    /** Put money back. */
    synchronized void credit(long paise) { fundsPaise += paise; }
    /** The balance now. */
    synchronized long funds() { return fundsPaise; }
}

/** One fare type on one flight (F1, SAVER): a price per seat and its own list of seats still for sale. */
final class FlightFare {
    final String type;
    final long pricePaise;
    final TreeSet<String> seats = new TreeSet<>();
    FlightFare(String type, long pricePaise, List<String> seats) { this.type = type; this.pricePaise = pricePaise; this.seats.addAll(seats); }
}

/**
 * One flight on one date: a single sector, so a seat is simply sold or not, with no segments. Each fare type sells
 * from its own seat list. One lock per flight: on this side, the flight is the aggregate root.
 */
final class Flight {
    final String number, airline, from, to;
    final int date, departMin;
    final Map<String, FlightFare> fares = new LinkedHashMap<>();
    final ReentrantLock lock = new ReentrantLock();
    Flight(String number, String airline, String from, String to, int date, int departMin) {
        this.number = number; this.airline = airline; this.from = from; this.to = to; this.date = date; this.departMin = departMin;
    }
    /** Add a fare type and the seats the airline gave it. Setup only. */
    Flight fare(String type, long pricePaise, String... seats) { fares.put(type, new FlightFare(type, pricePaise, List.of(seats))); return this; }
    /** Number and date, the key bookings use and the order locks are taken in: "111/2". */
    String key() { return number + "/" + date; }
}

/** One offer a search returns: a flight, a fare type with enough seats, and those seats as they were at that moment. */
record Offer(Flight flight, String fareType, long pricePaise, List<String> seats) {}

/** A flight booking. Its fields change only under its flight's lock (and, for a change, the new flight's too). */
final class FlightBooking {
    final String id, userId;
    volatile Flight flight;
    volatile String fareType;
    volatile List<String> seats;
    volatile long paidPaise;
    volatile boolean cancelled;
    FlightBooking(String id, String userId, Flight flight, String fareType, List<String> seats, long paidPaise) {
        this.id = id; this.userId = userId; this.flight = flight; this.fareType = fareType; this.seats = seats; this.paidPaise = paidPaise;
    }
}

/**
 * The desk: users, flights, bookings. A booking takes its flight's lock, then the user's wallet; a change takes
 * both flights' locks in key order first. One fixed order everywhere means two calls can never wait for each
 * other in a circle (a deadlock).
 */
final class FlightDesk {
    private final Map<String, FlyUser> users = new ConcurrentHashMap<>();
    private final Map<String, Flight> flights = new ConcurrentHashMap<>();                  // "111/2" -> flight
    private final Map<String, List<Flight>> bySector = new ConcurrentHashMap<>();           // "DEL-BLR-2" -> flights
    private final Map<String, FlightBooking> bookings = new ConcurrentHashMap<>();
    private final Map<String, List<FlightBooking>> byUser = new ConcurrentHashMap<>();
    private final AtomicInteger seq = new AtomicInteger();

    /** ADDUSER u1 Vinit 5000 -> "<u1, Vinit, Rs 5,000.00>". */
    String addUser(String id, String name, long fundsPaise) {
        FlyUser u = new FlyUser(id, name, fundsPaise);
        if (users.putIfAbsent(id, u) != null) throw new IllegalArgumentException("user " + id + " exists");
        return "<" + id + ", " + name + ", " + Main.rupees(fundsPaise) + ">";
    }
    /** The supplier's feed: a flight on a sector and date. Setup. */
    void addFlight(Flight f) {
        if (flights.putIfAbsent(f.key(), f) != null) throw new IllegalArgumentException("flight " + f.key() + " exists");
        bySector.computeIfAbsent(f.from + "-" + f.to + "-" + f.date, k -> new CopyOnWriteArrayList<>()).add(f);
    }

    /** SEARCHFLIGHT from to date pax: every flight and fare type with at least pax seats, earliest first, then cheapest. */
    List<Offer> search(String from, String to, int date, int pax) {
        List<Offer> out = new ArrayList<>();
        for (Flight f : bySector.getOrDefault(from + "-" + to + "-" + date, List.of())) {
            f.lock.lock();                                                // one flight at a time: never two locks here
            try {
                for (FlightFare fare : f.fares.values())
                    if (fare.seats.size() >= pax) out.add(new Offer(f, fare.type, fare.pricePaise, List.copyOf(fare.seats)));
            } finally { f.lock.unlock(); }
        }
        out.sort(Comparator.comparingInt((Offer o) -> o.flight().departMin).thenComparingLong(Offer::pricePaise));
        return out;
    }
    /** The bonus search: the preferred airline's offers first, then the others, each part in the order asked for. */
    List<Offer> searchPreferred(String from, String to, int date, int pax, String airline, Comparator<Offer> order) {
        List<Offer> out = search(from, to, date, pax);
        out.sort(Comparator.comparing((Offer o) -> !o.flight().airline.equals(airline)).thenComparing(order));
        return out;
    }

    /**
     * BOOK: every seat must be free in that one fare type and the wallet must cover them all, or nothing happens
     * and the message says why. Returns the booking id.
     */
    String book(String userId, String flightNo, int date, String fareType, List<String> seats) {
        FlyUser u = user(userId);
        Flight f = flight(flightNo, date);
        if (seats.isEmpty() || new HashSet<>(seats).size() != seats.size()) throw new IllegalArgumentException("name each seat once");
        f.lock.lock();
        try {
            FlightFare fare = fareOf(f, fareType);
            for (String s : seats) if (!fare.seats.contains(s)) throw new IllegalStateException("seat " + s + " is not available in " + fareType + " on " + f.key());
            long cost = fare.pricePaise * seats.size();
            if (!u.debit(cost)) throw new IllegalStateException("insufficient funds: " + Main.rupees(cost) + " needed, " + Main.rupees(u.funds()) + " in the wallet");
            fare.seats.removeAll(seats);                                  // money and seats move inside the same lock
            FlightBooking b = new FlightBooking("b" + seq.incrementAndGet(), userId, f, fareType, List.copyOf(seats), cost);
            bookings.put(b.id, b);
            byUser.computeIfAbsent(userId, k -> new CopyOnWriteArrayList<>()).add(b);
            return b.id;
        } finally { f.lock.unlock(); }
    }

    /** CANCEL: the seats go back to their fare type and the money to the wallet, once. */
    void cancel(String userId, String bookingId) {
        FlightBooking b = booking(userId, bookingId);
        while (true) {
            Flight f = b.flight;                                          // a change may move it: lock, then re-check
            f.lock.lock();
            try {
                if (b.flight != f) continue;                              // it moved while we waited: go again
                if (b.cancelled) throw new IllegalStateException("booking " + bookingId + " is already cancelled");
                fareOf(f, b.fareType).seats.addAll(b.seats);
                user(userId).credit(b.paidPaise);
                b.cancelled = true;
                return;
            } finally { f.lock.unlock(); }
        }
    }

    /**
     * UPDATE: move a booking to another flight, fare and seats, charging or refunding the difference. Both flights
     * are locked in key order, every check runs before anything moves, so a refusal leaves the old booking intact.
     */
    void change(String userId, String bookingId, String newFlightNo, int newDate, String fareType, List<String> seats) {
        FlightBooking b = booking(userId, bookingId);
        Flight to = flight(newFlightNo, newDate);
        if (seats.isEmpty() || new HashSet<>(seats).size() != seats.size()) throw new IllegalArgumentException("name each seat once");
        while (true) {
            Flight from = b.flight;
            Flight first = from.key().compareTo(to.key()) <= 0 ? from : to, second = first == from ? to : from;
            first.lock.lock();
            if (second != first) second.lock.lock();
            try {
                if (b.flight != from) continue;                           // it moved while we waited for the locks
                if (b.cancelled) throw new IllegalStateException("booking " + bookingId + " is cancelled");
                FlightFare oldFare = fareOf(from, b.fareType), newFare = fareOf(to, fareType);
                for (String s : seats)                                    // his own seats count as free on the same fare
                    if (!newFare.seats.contains(s) && !(newFare == oldFare && b.seats.contains(s)))
                        throw new IllegalStateException("seat " + s + " is not available in " + fareType + " on " + to.key());
                long cost = newFare.pricePaise * seats.size(), diff = cost - b.paidPaise;
                FlyUser u = user(userId);
                if (diff > 0 && !u.debit(diff)) throw new IllegalStateException("insufficient funds for the difference " + Main.rupees(diff));
                if (diff < 0) u.credit(-diff);
                oldFare.seats.addAll(b.seats);                            // nothing below can fail
                newFare.seats.removeAll(seats);
                b.flight = to; b.fareType = fareType; b.seats = List.copyOf(seats); b.paidPaise = cost;
                return;
            } finally {
                if (second != first) second.lock.unlock();
                first.lock.unlock();
            }
        }
    }

    /** GET_USER_BOOKING: every booking of the user, booked and cancelled, in the order made. */
    List<String> bookings(String userId) {
        List<String> out = new ArrayList<>();
        for (FlightBooking b : byUser.getOrDefault(userId, List.of()))
            out.add("<" + b.id + ", " + b.flight.number + ", " + b.flight.date + ", " + String.format("%02d:%02d", b.flight.departMin / 60, b.flight.departMin % 60)
                + ", " + Main.rupees(b.paidPaise) + ", " + b.fareType + ", " + b.seats + (b.cancelled ? ", CANCELLED" : "") + ">");
        return out;
    }
    /** A wallet balance, for the demo and the tests. */
    long funds(String userId) { return user(userId).funds(); }

    /** A user by id, or a clear error. */
    private FlyUser user(String id) { FlyUser u = users.get(id); if (u == null) throw new NoSuchElementException("no user " + id); return u; }
    /** A flight by number and date, or a clear error. */
    private Flight flight(String no, int date) { Flight f = flights.get(no + "/" + date); if (f == null) throw new NoSuchElementException("no flight " + no + " on day " + date); return f; }
    /** A fare type of a flight, or a clear error. */
    private static FlightFare fareOf(Flight f, String type) { FlightFare x = f.fares.get(type); if (x == null) throw new IllegalStateException("no fare " + type + " on " + f.key()); return x; }
    /** One of the user's bookings, or a clear error. */
    private FlightBooking booking(String userId, String id) {
        FlightBooking b = bookings.get(id);
        if (b == null || !b.userId.equals(userId)) throw new NoSuchElementException("no booking " + id + " for " + userId);
        return b;
    }
}

/** Runs every extension once, so the reference code on page 05 is code that actually executed. */
class ExtDemo {
    /** Each extension once, in the order of page 05, printing what it did. */
    public static void main(String[] args) throws Exception {
        long[] now = { ZonedDateTime.of(2026, 10, 1, 9, 58, 0, 0, TrainRun.IST).toInstant().toEpochMilli() };
        Clock clock = () -> now[0];
        BookingService svc = new BookingService(clock, 10 * 60_000L);
        svc.addTrain(Main.deccanArrow());
        TrainRun run = svc.addRun("12999", LocalDate.of(2026, 10, 2), 1, 3);
        PaymentGateway upi = new UpiGateway();

        // a family of four with grandparents: one coach, lower berths for the two over sixty
        svc.configure(new DistanceFare(), new FamilyChooser(), new RailwayRefund());
        Pnr fam = svc.book(run.id, "dev", "CSMT", "SBC", TravelClass.AC3,
            List.of(new Traveller("Dev", 45, BerthType.UPPER), new Traveller("Mira", 43, null), new Traveller("Nana", 72, null), new Traveller("Nani", 68, null)), false);
        svc.pay(fam.id, upi);
        System.out.println("family: " + svc.status(fam.id));

        // fares: Tatkal and flexi stack on the distance rule, and the order of wrapping changes the price
        FareRule base = new DistanceFare(), tatkal = new TatkalFare(base);
        FareRule flexiThenTatkal = new TatkalFare(new FlexiFare(base)), tatkalThenFlexi = new FlexiFare(new TatkalFare(base));
        System.out.println("3A PUNE->SBC with 4 of 7 berths sold: base " + Main.rupees(base.farePaise(run, 1, 4, TravelClass.AC3))
            + ", Tatkal " + Main.rupees(tatkal.farePaise(run, 1, 4, TravelClass.AC3))
            + ", flexi inside Tatkal " + Main.rupees(flexiThenTatkal.farePaise(run, 1, 4, TravelClass.AC3))
            + ", Tatkal inside flexi " + Main.rupees(tatkalThenFlexi.farePaise(run, 1, 4, TravelClass.AC3)));

        // the railway's refund rule: 30 hours before departure, a confirmed 3A ticket loses a quarter
        Pnr asha = svc.book(run.id, "asha", "PUNE", "SBC", TravelClass.AC3, List.of(new Traveller("Asha", 34, null)), false);
        svc.pay(asha.id, upi);
        now[0] = run.departsMs(1) - 30 * 3_600_000L;
        System.out.println("cancel 30 hours before a " + Main.rupees(asha.amountPaise) + " ticket: " + Main.rupees(svc.cancel(asha.id, upi)) + " back");

        // availability without the walk: the same count from the sideways index
        SegmentIndex idx = new SegmentIndex(run.soldMasks(TravelClass.AC3), run.train.segments());
        System.out.println("3A free PUNE->SUR: run says " + run.availability("PUNE", "SUR", TravelClass.AC3).berths() + ", sideways index says " + idx.freeFor(1, 2));

        // a sweeper releases a lapsed hold without anybody calling the run
        Pnr ghost = svc.book(run.id, "ghost", "CSMT", "PUNE", TravelClass.SLEEPER, List.of(new Traveller("Ghost", 30, null)), false);
        now[0] += 10 * 60_000L;
        HoldSweeper sweeper = new HoldSweeper(List.of(run));
        System.out.println("the sweeper released " + sweeper.sweepOnce() + " hold; PNR " + ghost.id + " is " + ghost.status);

        // a queue in front of the run: one worker, arrival order, a bounded queue that says "try again"
        TrainRun rush = svc.addRun("12999", LocalDate.of(2026, 10, 6), 1, 3);
        RunQueue q = new RunQueue("run-" + rush.id, 64);
        List<CompletableFuture<Pnr>> answers = new ArrayList<>();
        for (int i = 0; i < 10; i++) { String u = "tatkal" + i; answers.add(q.submit(() -> svc.book(rush.id, u, "CSMT", "SBC", TravelClass.AC3, List.of(new Traveller(u, 30, null)), true))); }
        int got = 0; for (CompletableFuture<Pnr> f : answers) { try { f.get(); got++; } catch (ExecutionException e) { /* NoPlaces */ } }
        System.out.println("ten Tatkal requests through the queue for 7 berths: " + got + " booked, in arrival order");
        q.stop();

        // persistence: fifty callers, one conditional UPDATE on one berth's mask: one row changes
        MaskStore db = new MaskStore();
        db.add("R1", "B1/1"); db.add("R1", "B1/2");
        ExecutorService pool = Executors.newFixedThreadPool(50);
        CountDownLatch go = new CountDownLatch(1);
        AtomicInteger wins = new AtomicInteger();
        for (int i = 0; i < 50; i++) pool.submit(() -> { go.await(); if (db.sellAll("R1", List.of("B1/1"), 1, 3)) wins.incrementAndGet(); return null; });
        go.countDown(); pool.shutdown(); pool.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("fifty conditional UPDATEs on B1/1 segments 1-3: " + wins.get() + " winner; the same berth for segments 3-4: "
            + db.sellAll("R1", List.of("B1/1"), 3, 4) + "; mask now " + Long.toBinaryString(db.mask("R1", "B1/1")));

        // the flight version: Cleartrip's commands
        FlightDesk desk = new FlightDesk();
        System.out.println(desk.addUser("u1", "Vinit", 500_000) + " " + desk.addUser("u2", "Neha", 150_000));
        desk.addFlight(new Flight("111", "6E", "DEL", "BLR", 2, 10 * 60 + 30).fare("F1", 100_000, "10a", "11c", "20b", "21a").fare("F2", 150_000, "1a", "1b"));
        desk.addFlight(new Flight("211", "6E", "DEL", "BLR", 2, 18 * 60 + 45).fare("F1", 120_000, "10a", "11c", "20b"));
        desk.addFlight(new Flight("141", "AI", "DEL", "BLR", 2, 7 * 60 + 10).fare("F4", 140_000, "32e", "33a"));
        for (Offer o : desk.search("DEL", "BLR", 2, 2)) System.out.println("  " + o.flight().number + " " + o.flight().airline + " " + o.fareType() + " " + Main.rupees(o.pricePaise()) + " " + o.seats());
        String b1 = desk.book("u1", "111", 2, "F1", List.of("10a", "11c", "20b"));
        try { desk.book("u1", "211", 2, "F2", List.of("10a")); } catch (IllegalStateException e) { System.out.println("  refused: " + e.getMessage()); }
        String b2 = desk.book("u2", "141", 2, "F4", List.of("32e"));
        desk.cancel("u1", b1);
        System.out.println("  after cancel u1 has " + Main.rupees(desk.funds("u1")) + "; u1 bookings " + desk.bookings("u1"));
        desk.change("u2", b2, "111", 2, "F1", List.of("21a"));
        System.out.println("  u2 moved to 111 F1: " + desk.bookings("u2") + ", wallet " + Main.rupees(desk.funds("u2")));
        System.out.println("  AI first, dearest first: " + desk.searchPreferred("DEL", "BLR", 2, 1, "AI", Comparator.comparingLong(Offer::pricePaise).reversed()).stream().map(o -> o.flight().number + "/" + o.fareType()).toList());
    }
}
