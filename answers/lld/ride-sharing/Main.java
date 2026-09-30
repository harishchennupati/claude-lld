import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** The tiers a rider can ask for. The tier is the filter in matching and the key into the fare table. */
enum VehicleType { AUTO, GO, PREMIER, XL }

/**
 * A driver's availability. OFFLINE is not working; AVAILABLE can be claimed by anybody; RESERVED means exactly one
 * rider won him; ON_TRIP means the ride is running. Only AVAILABLE -> RESERVED is ever contended.
 */
enum DriverStatus { OFFLINE, AVAILABLE, RESERVED, ON_TRIP }

/**
 * A trip's life. COMPLETED_UNPAID is the honest state between "the car stopped" and "the card said yes": the ride
 * happened whatever the gateway thinks, so the money is a separate step that can be retried.
 */
enum TripStatus { REQUESTED, ASSIGNED, ARRIVED, IN_PROGRESS, COMPLETED_UNPAID, COMPLETED, CANCELLED }

/**
 * Money is whole paise in a long. The one double near a fare is the distance, rounded to whole paise once in
 * NormalPricing; every step after that is exact, and an overflow throws instead of wrapping to a negative fare.
 */
final class Money {
    /** Parse "172.00" into 17200 paise, exactly. Used at the edge (a form, a rate card), never in the maths. */
    static long rupees(String amount) { return new java.math.BigDecimal(amount).movePointRight(2).longValueExact(); }
    /** Print 17200 paise as "172.00". Presentation only. */
    static String fmt(long paise) {
        String sign = paise < 0 ? "-" : ""; long a = Math.abs(paise);
        return sign + (a / 100) + "." + String.format("%02d", a % 100);
    }
}

/** Where time comes from. Injected, so a test can decide that a ride took exactly twenty-four minutes. */
interface Clock { long nowMs(); }

/** A point on the map. Immutable, and it carries the one piece of geometry everybody needs. */
record Location(double lat, double lng) {
    /**
     * Great-circle (haversine) distance in kilometres. This is the "who is near me" number. It is deliberately NOT
     * the number a fare is built from: the fare uses the distance the car actually drove.
     */
    double distanceKm(Location o) {
        double R = 6371.0;
        double dLat = Math.toRadians(o.lat - lat), dLng = Math.toRadians(o.lng - lng);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                 + Math.cos(Math.toRadians(lat)) * Math.cos(Math.toRadians(o.lat))
                 * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return 2 * R * Math.asin(Math.min(1.0, Math.sqrt(a)));
    }
    @Override public String toString() { return String.format("(%.4f, %.4f)", lat, lng); }
}

/** A passenger. Only the id ever reaches a trip or a payment, so a rename can never move money. */
record Rider(String id, String name) {}

/** A car. The tier is what a rider asks for, so it lives here and not on the driver. */
record Vehicle(String plate, VehicleType type) {}

/**
 * One driver and his car. Two fields move on their own. `location` is written thousands of times a second by the
 * ping path and read by matching, so it is volatile and takes no lock. `status` is the one cell in this whole
 * system that two threads fight over, so it is an AtomicReference and every change to it is a compare-and-set.
 */
class Driver {
    private final String id, name;
    private final Vehicle vehicle;
    private volatile Location location;
    private final AtomicReference<DriverStatus> status = new AtomicReference<>(DriverStatus.OFFLINE);

    Driver(String id, String name, Vehicle vehicle, Location at) {
        this.id = id; this.name = name; this.vehicle = vehicle; this.location = at;
    }
    String id()              { return id; }
    String name()            { return name; }
    Vehicle vehicle()        { return vehicle; }
    /** The last ping. May be a few seconds stale, which is fine for choosing a car. */
    Location location()      { return location; }
    DriverStatus status()    { return status.get(); }
    /** The ping path: one volatile write, no lock, no allocation. */
    void moveTo(Location where) { this.location = where; }
    /** Start a shift: OFFLINE -> AVAILABLE. False if he was already online. */
    boolean goOnline()  { return status.compareAndSet(DriverStatus.OFFLINE, DriverStatus.AVAILABLE); }
    /** End a shift. Only from AVAILABLE, so a driver can never vanish in the middle of a ride. */
    boolean goOffline() { return status.compareAndSet(DriverStatus.AVAILABLE, DriverStatus.OFFLINE); }
    /**
     * THE critical step of this system. Two riders can reach the same car in the same microsecond; this single
     * hardware instruction decides. Exactly one caller gets true, and from that moment the car is his alone.
     */
    boolean reserve()   { return status.compareAndSet(DriverStatus.AVAILABLE, DriverStatus.RESERVED); }
    /** The rider is in the car: RESERVED -> ON_TRIP. */
    boolean board()     { return status.compareAndSet(DriverStatus.RESERVED, DriverStatus.ON_TRIP); }
    /** Back into the pool, from RESERVED (the ride was cancelled) or ON_TRIP (it finished). */
    boolean release()   { return status.compareAndSet(DriverStatus.RESERVED, DriverStatus.AVAILABLE)
                              || status.compareAndSet(DriverStatus.ON_TRIP,  DriverStatus.AVAILABLE); }
    @Override public String toString() { return id + " " + name + " " + vehicle.type() + " " + status.get(); }
}

// "who is near this pickup?" asked 400 times a second against 60,000 cars -> never a scan -> a spatial index
/**
 * The shape that answers "who is near here". An interface because the answer changes with the city: a flat grid
 * is right for one town, a quadtree or geohash for a country. Swapping it is one line at the composition root.
 */
interface DriverIndex {
    /** Record a driver at a place. Called on every ping, so it must be O(1) and must not allocate in the common case. */
    void update(Driver d, Location where);
    /** Forget a driver: he went offline. */
    void remove(Driver d);
    /** Every driver in the neighbourhood of this pickup, of any status. Matching does the filtering. */
    List<Driver> nearby(Location pickup);
}

/**
 * A uniform grid: round the latitude and longitude to a cell about 1.1 km across and keep a set per cell. A ping
 * only touches the grid when the car crosses a cell boundary, which at city speed is about once every two and a half
 * minutes, so the write-heavy path is a volatile field write and nothing else. A read is the pickup's cell plus its
 * eight neighbours: nine bucket lookups, never a scan of the fleet.
 */
class GridIndex implements DriverIndex {
    /** About 1.1 km of latitude. Bigger cells mean fewer rewrites and longer scans; this is the knob. */
    private static final double CELL_DEG = 0.01;
    private final Map<Long, Set<Driver>> cells = new ConcurrentHashMap<>();
    private final Map<String, Long> cellOfDriver = new ConcurrentHashMap<>();
    private final AtomicLong pings = new AtomicLong(), rewrites = new AtomicLong(), scanned = new AtomicLong();

    /**
     * A cell crossing is "leave the old set, join the new one, remember the new cell", and it runs inside compute()
     * on this driver's own entry, so two of his pings handled on two threads at once cannot both move him: without
     * that, each would add him to a different cell and the loser's cell would keep him forever, a ghost.
     */
    public void update(Driver d, Location where) {
        pings.incrementAndGet();
        d.moveTo(where);                                       // the cheap part: one volatile write
        long cell = cellOf(where);
        Long seen = cellOfDriver.get(d.id());
        if (seen != null && seen.longValue() == cell) return;  // the common case: same cell, nothing to rewrite
        cellOfDriver.compute(d.id(), (id, old) -> {            // one crossing at a time for THIS driver only
            if (d.status() == DriverStatus.OFFLINE) {          // a late ping after sign-off must not re-add him
                if (old != null) { Set<Driver> from = cells.get(old); if (from != null) from.remove(d); }
                return null;
            }
            if (old != null && old.longValue() == cell) return old;
            rewrites.incrementAndGet();
            if (old != null) { Set<Driver> from = cells.get(old); if (from != null) from.remove(d); }
            cells.computeIfAbsent(cell, k -> ConcurrentHashMap.newKeySet()).add(d);
            return cell;
        });
    }
    /** Forget a driver, in the same per-driver step as update, so a ping in flight cannot undo it. */
    public void remove(Driver d) {
        cellOfDriver.computeIfPresent(d.id(), (id, cell) -> {
            Set<Driver> from = cells.get(cell);
            if (from != null) from.remove(d);
            return null;                                       // null deletes his entry
        });
    }
    public List<Driver> nearby(Location pickup) {
        long latCell = (long) Math.floor(pickup.lat() / CELL_DEG), lngCell = (long) Math.floor(pickup.lng() / CELL_DEG);
        List<Driver> out = new ArrayList<>();
        for (long dLat = -1; dLat <= 1; dLat++)
            for (long dLng = -1; dLng <= 1; dLng++) {
                Set<Driver> bucket = cells.get(key(latCell + dLat, lngCell + dLng));
                if (bucket != null) out.addAll(bucket);        // a concurrent set: a mildly stale view is fine
            }
        scanned.addAndGet(out.size());
        return out;
    }
    /** How many pings arrived, how many of them actually rewrote the grid, and how many drivers reads have seen. */
    String stats() { return "pings=" + pings + " grid rewrites=" + rewrites + " drivers scanned=" + scanned; }
    /** How many location pings this index absorbed. */
    long pings() { return pings.get(); }
    /** How many of those pings actually moved a driver between cells. The rest were one volatile write and nothing else. */
    long rewrites() { return rewrites.get(); }
    /** How many drivers this index knows about. */
    int size() { return cellOfDriver.size(); }
    private static long cellOf(Location l) {
        return key((long) Math.floor(l.lat() / CELL_DEG), (long) Math.floor(l.lng() / CELL_DEG));
    }
    private static long key(long latCell, long lngCell) { return (latCell << 32) ^ (lngCell & 0xffff_ffffL); }
}

// "which driver?" is a business rule that changes every quarter -> hide it behind an interface -> Strategy
/** The rule that picks one car out of the neighbourhood. It only proposes; it never claims and never mutates. */
interface MatchingStrategy {
    /** The car this rule would send, or empty if none of the candidates will do. */
    Optional<Driver> select(Location pickup, VehicleType type, List<Driver> candidates);
}

/** Today's rule: the closest AVAILABLE car of the right tier. A min-scan over the candidates, nothing more. */
class NearestDriver implements MatchingStrategy {
    public Optional<Driver> select(Location pickup, VehicleType type, List<Driver> candidates) {
        Driver best = null; double bestKm = Double.MAX_VALUE;
        for (Driver d : candidates) {
            if (d.status() != DriverStatus.AVAILABLE) continue;       // a hint only: it can change a nanosecond later
            if (d.vehicle().type() != type) continue;
            double km = d.location().distanceKm(pickup);
            if (km < bestKm) { bestKm = km; best = d; }
        }
        return Optional.ofNullable(best);
    }
}

/** Everything a fare rule is allowed to look at. A value object, so a new rule needs no new method signature. */
record FareBasis(VehicleType type, double distanceKm, long minutes, Location pickup, long atMs) {}

// "what do we charge?" is the rule that changes weekly -> the same move -> Strategy again
/** The rule that turns a finished ride into paise. One method, because the whole of pricing is one decision. */
interface PricingStrategy {
    /** The fare for this ride, in paise. Must be deterministic: the same basis always gives the same number. */
    long price(FareBasis basis);
}

/**
 * Base fare plus per-kilometre plus per-minute, from a table keyed by tier. The kilometres are the one double, rounded
 * to paise once; the sum is exact long arithmetic, and addExact throws rather than wrap if a number is absurd.
 */
class NormalPricing implements PricingStrategy {
    private static final Map<VehicleType, long[]> RATE = rates();      // {base, perKm, perMin} in paise
    private static Map<VehicleType, long[]> rates() {
        Map<VehicleType, long[]> m = new EnumMap<>(VehicleType.class);
        m.put(VehicleType.AUTO,    new long[]{2000,  800, 100});
        m.put(VehicleType.GO,      new long[]{4000, 1200, 150});
        m.put(VehicleType.PREMIER, new long[]{6000, 1600, 200});
        m.put(VehicleType.XL,      new long[]{8000, 2000, 250});
        return Collections.unmodifiableMap(m);
    }
    public long price(FareBasis b) {
        long[] r = RATE.get(b.type());
        long perKm = Math.round(r[1] * b.distanceKm());                     // the only rounding in a fare
        return Math.addExact(Math.addExact(r[0], perKm), Math.multiplyExact(r[2], b.minutes()));
    }
}

/** Where a surge multiplier comes from, in basis points: 10000 is 1.0x, 15000 is 1.5x. Integer, so it is exact. */
interface SurgeSource {
    /** The multiplier for this ride, in basis points. Read at the moment of pricing, never cached on the trip. */
    int basisPoints(FareBasis basis);
}

// "add surge, then a coupon, then a toll" must not become four flags in one method -> wrap the rule -> Decorator
/**
 * Surge as a wrapper, not a flag: it takes whatever the base rule charged and multiplies it. Because it IS a
 * PricingStrategy and HOLDS a PricingStrategy, coupons and tolls stack the same way without anybody editing the
 * base formula. 10000 basis points is 1.0x, so a wrapper with no surge is exactly the base fare.
 */
class SurgePricing implements PricingStrategy {
    private final PricingStrategy base;
    private final SurgeSource surge;
    SurgePricing(PricingStrategy base, SurgeSource surge) { this.base = base; this.surge = surge; }
    public long price(FareBasis b) {
        int bp = surge.basisPoints(b);
        if (bp < 10_000) throw new IllegalArgumentException("surge cannot be a discount: " + bp + " bp");
        return Math.multiplyExact(base.price(b), (long) bp) / 10_000;       // truncates: the rider keeps the half paisa
    }
}

// "do we charge for a cancellation?" is a third rule the interviewer will change -> Strategy, again
/** The rule that decides what a cancellation costs. Reads the state it was cancelled in and how long the rider waited. */
interface CancellationPolicy {
    /** The fee in paise, zero when the cancellation is free. */
    long feePaise(TripStatus cancelledIn, long waitedMs);
}

/** Free while nobody has been sent and for two minutes after that; thirty rupees once the driver is really coming. */
class StandardCancellation implements CancellationPolicy {
    private static final long GRACE_MS = 2 * 60 * 1000L;
    private static final long FEE = Money.rupees("30.00");
    public long feePaise(TripStatus cancelledIn, long waitedMs) {
        if (cancelledIn == TripStatus.REQUESTED) return 0;                       // no driver was ever claimed
        if (cancelledIn == TripStatus.ASSIGNED && waitedMs < GRACE_MS) return 0; // he had only just set off
        return FEE;                                                             // en route, or already waiting at the kerb
    }
}

/**
 * Thrown when the gateway says no, or does not answer in time. After a timeout nobody knows whether the money
 * moved; that is safe here because the retry sends the same key, so it either charges now or returns the first
 * charge's reference. The ride still happened; only the money is unfinished.
 */
class PaymentDeclined extends RuntimeException {
    PaymentDeclined(String message) { super(message); }
}

/** The money gateway. Slow, external, and the one call in this system that cannot be undone by us. */
interface PaymentProcessor {
    /** Charge the rider. Returns a reference on success; throws PaymentDeclined otherwise. Must be idempotent on the key. */
    String charge(String riderId, long paise, String idempotencyKey);
}

/** A card gateway that remembers its keys, so the same trip charged twice takes the money once. */
class CardPayment implements PaymentProcessor {
    private final Map<String, String> byKey = new ConcurrentHashMap<>();
    private final AtomicLong charges = new AtomicLong();
    public String charge(String riderId, long paise, String key) {
        return byKey.computeIfAbsent(key, k -> {                 // the second call with the same key returns the first reference
            charges.incrementAndGet();
            return "pay-" + k + "-" + Money.fmt(paise);
        });
    }
    /** How many times money actually moved. A retry must not increase this. */
    long charges() { return charges.get(); }
}

// "the rider's phone and the driver's phone must be told" must not sit inside the money path -> Observer
/** Anyone who wants to hear that a trip moved: the rider's phone, the driver's app, analytics, a rating prompt. */
interface TripObserver {
    /** Called after the state has already changed, outside every lock. Must not throw; if it does, it is ignored. */
    void onTrip(Trip trip, TripStatus from, TripStatus to);
}

/** A push notification. Prints here; a real one calls a gateway, which is exactly why it runs after the transition. */
class PushNotifier implements TripObserver {
    public void onTrip(Trip t, TripStatus from, TripStatus to) {
        System.out.println("[push] " + t.id() + " " + from + " -> " + to
            + "  rider " + t.rider().name() + ", driver " + t.driver().name()
            + (to == TripStatus.COMPLETED ? ", fare " + Money.fmt(t.farePaise()) : ""));
    }
}

/**
 * One ride, and the only place a ride's rules live. Every legal move is in one table, so an out-of-order call
 * throws instead of quietly producing a nonsense fare. transitionTo is the only writer of status and it validates
 * BEFORE it writes, so a rejected call leaves the trip exactly as it was. status is volatile because other threads
 * read it without taking this monitor.
 */
class Trip {
    private static final Map<TripStatus, Set<TripStatus>> LEGAL = legalEdges();
    private static Map<TripStatus, Set<TripStatus>> legalEdges() {
        Map<TripStatus, Set<TripStatus>> m = new EnumMap<>(TripStatus.class);
        m.put(TripStatus.REQUESTED,        EnumSet.of(TripStatus.ASSIGNED, TripStatus.CANCELLED));
        m.put(TripStatus.ASSIGNED,         EnumSet.of(TripStatus.ARRIVED, TripStatus.CANCELLED));
        m.put(TripStatus.ARRIVED,          EnumSet.of(TripStatus.IN_PROGRESS, TripStatus.CANCELLED));
        m.put(TripStatus.IN_PROGRESS,      EnumSet.of(TripStatus.COMPLETED_UNPAID));   // no cancelling a moving car
        m.put(TripStatus.COMPLETED_UNPAID, EnumSet.of(TripStatus.COMPLETED));          // the money, later
        m.put(TripStatus.COMPLETED,        EnumSet.noneOf(TripStatus.class));
        m.put(TripStatus.CANCELLED,        EnumSet.noneOf(TripStatus.class));
        return Collections.unmodifiableMap(m);
    }

    private final String id;
    private final Rider rider;
    private final Driver driver;
    private final Location pickup, drop;
    private final VehicleType type;
    private final long requestedAtMs;
    private volatile TripStatus status = TripStatus.REQUESTED;
    private volatile long assignedAtMs, arrivedAtMs, startedAtMs, endedAtMs;
    private volatile double distanceKm;
    private volatile long minutes, farePaise, feePaise;
    private volatile String paymentRef = "";

    Trip(String id, Rider rider, Driver driver, Location pickup, Location drop, VehicleType type, long atMs) {
        this.id = id; this.rider = rider; this.driver = driver; this.pickup = pickup; this.drop = drop;
        this.type = type; this.requestedAtMs = atMs;
    }
    String id()            { return id; }
    Rider rider()          { return rider; }
    Driver driver()        { return driver; }
    Location pickup()      { return pickup; }
    Location drop()        { return drop; }
    VehicleType type()     { return type; }
    TripStatus status()    { return status; }
    long requestedAtMs()   { return requestedAtMs; }
    long startedAtMs()     { return startedAtMs; }
    long endedAtMs()       { return endedAtMs; }
    double distanceKm()    { return distanceKm; }
    long minutes()         { return minutes; }
    /** What the ride cost, in paise. Zero until the ride ends. */
    long farePaise()       { return farePaise; }
    /** What the cancellation cost, in paise. Zero unless it was cancelled late. */
    long feePaise()        { return feePaise; }
    /** The gateway's reference, empty while the trip is COMPLETED_UNPAID. */
    String paymentRef()    { return paymentRef; }

    /**
     * The only writer of status. Looks the move up in the table and throws if it is not there, before touching a
     * single field. Synchronized, so a rider cancelling and a driver starting at the same instant cannot both win.
     */
    synchronized void transitionTo(TripStatus to) {
        if (!LEGAL.get(status).contains(to))
            throw new IllegalStateException(id + ": " + status + " -> " + to + " is not a legal move");
        status = to;
    }
    /** A car has been claimed for this ride and is on his way. */
    synchronized void assigned(long atMs)  { transitionTo(TripStatus.ASSIGNED); assignedAtMs = atMs; }
    /** The car is at the kerb. */
    synchronized void arrived(long atMs)   { transitionTo(TripStatus.ARRIVED); arrivedAtMs = atMs; }
    /** The rider is in and the meter is running. */
    synchronized void started(long atMs)   { transitionTo(TripStatus.IN_PROGRESS); startedAtMs = atMs; }
    /** The car stopped. The ride is now a fact; the money has not been touched yet. */
    synchronized void ended(double km, long mins, long fare, long atMs) {
        transitionTo(TripStatus.COMPLETED_UNPAID);
        distanceKm = km; minutes = mins; farePaise = fare; endedAtMs = atMs;
    }
    /**
     * The gateway said yes. The last move of a happy trip. False if a second settle racing this one already recorded
     * it: both sent the same key, so the gateway moved the money once and handed both the same reference.
     */
    synchronized boolean paid(String ref) {
        if (status == TripStatus.COMPLETED) return false;
        transitionTo(TripStatus.COMPLETED); paymentRef = ref; return true;
    }
    /** Called off before the meter started, with whatever the policy decided it costs. */
    synchronized void cancelled(long fee)  { transitionTo(TripStatus.CANCELLED); feePaise = fee; }

    @Override public String toString() {
        return id + " " + status + " " + rider.name() + "/" + driver.name() + " " + type
            + (farePaise > 0 ? " fare " + Money.fmt(farePaise) : "") + (feePaise > 0 ? " fee " + Money.fmt(feePaise) : "");
    }
}

/**
 * The aggregate root. It owns the riders, the drivers, the index and every trip, and it is the only class that
 * knows the order of operations. Notice what it does NOT own: a global lock. Dispatch runs fully in parallel,
 * because the contended state is never a big structure: it is one driver's status, settled by a compare-and-set,
 * and one rider's live-ride slot, settled by a putIfAbsent. Two claims, two single steps, no lock between riders.
 */
class RideService {
    private final DriverIndex index;
    private final Map<String, Rider> riders = new ConcurrentHashMap<>();
    private final Map<String, Driver> drivers = new ConcurrentHashMap<>();
    private final Map<String, Trip> trips = new ConcurrentHashMap<>();
    /** riderId -> the id of the ride he is on right now. The rider-side claim: it is what stops a double tap. */
    private final Map<String, String> activeTrip = new ConcurrentHashMap<>();
    /** The value parked in activeTrip while a request is still looking for a car, so a second tap sees a claim. */
    private static final String MATCHING = "(matching)";
    private final List<TripObserver> observers = new CopyOnWriteArrayList<>();
    private final AtomicLong seq = new AtomicLong(), lostRaces = new AtomicLong();
    private MatchingStrategy matching = new NearestDriver();
    private PricingStrategy pricing = new NormalPricing();
    private CancellationPolicy cancellation = new StandardCancellation();
    private PaymentProcessor payments = new CardPayment();
    private Clock clock = System::currentTimeMillis;

    RideService(DriverIndex index) { this.index = index; }

    /** Hand in the four rules. The service never builds one, which is why a test can hand in a card that always declines. */
    void configure(MatchingStrategy m, PricingStrategy p, CancellationPolicy c, PaymentProcessor pay) {
        this.matching = m; this.pricing = p; this.cancellation = c; this.payments = pay;
    }
    /** Tests hand in a fixed clock, so a ride can take exactly twenty-four minutes. */
    void setClock(Clock c) { clock = c; }
    /** Subscribe a listener. Setup only; listeners are called after the state has already moved. */
    void addObserver(TripObserver o) { observers.add(o); }
    /** Register a passenger. */
    void addRider(Rider r) { riders.put(r.id(), r); }

    /**
     * A driver starts his shift: he becomes claimable and enters the index. One object per id: a second, different
     * object under an id already known is refused, because the first would stay in the index, claimable, as a ghost.
     */
    void goOnline(Driver d, Location at) {
        Driver known = drivers.putIfAbsent(d.id(), d);
        if (known != null && known != d) throw new IllegalArgumentException(d.id() + " is already registered");
        if (!d.goOnline()) throw new IllegalStateException(d.id() + " is already " + d.status());
        index.update(d, at);
    }
    /** A driver ends his shift. Refused mid-ride, because goOffline only moves from AVAILABLE. */
    void goOffline(String driverId) {
        Driver d = driver(driverId);
        if (!d.goOffline()) throw new IllegalStateException(d.id() + " cannot go offline while " + d.status());
        index.remove(d);
    }
    /**
     * The write-heavy path: every car, every few seconds. One volatile write, and a grid rewrite only when the car
     * actually crosses a cell boundary. Nothing here takes a lock and nothing here can block a rider.
     */
    void ping(String driverId, Location where) { index.update(driver(driverId), where); }

    /**
     * The critical step, and it makes TWO claims. First the rider: putIfAbsent on his live-ride slot, so a double
     * tap or a retried request cannot become two rides. Then the car: ask the index who is near, let the rule pick
     * one, and CLAIM him with a compare-and-set. If the car claim fails another rider got there first, so drop that
     * car and try the next-best one: the loser is never made to wait and never fails. Every way out that did not
     * make a trip -- no car, or a rule that threw -- hands back the slot and any car it held (the finally block),
     * so the system is left exactly as it was.
     */
    Optional<Trip> requestRide(String riderId, Location pickup, Location drop, VehicleType type) {
        Rider rider = rider(riderId);
        if (activeTrip.putIfAbsent(rider.id(), MATCHING) != null)           // the rider-side claim, one atomic step
            throw new IllegalStateException(rider.id() + " already has a ride: " + activeTrip.get(rider.id()));
        Driver held = null;                                                 // a car claimed but not yet in a trip
        boolean booked = false;
        try {
            List<Driver> candidates = new ArrayList<>(index.nearby(pickup)); // a snapshot; a few entries may be stale
            while (true) {
                Optional<Driver> pick = matching.select(pickup, type, candidates);   // may throw: a routing call
                if (pick.isEmpty()) return Optional.empty();                // no car: the finally hands the slot back
                Driver d = pick.get();
                if (!d.reserve()) {                                         // somebody beat us to this car by a nanosecond
                    lostRaces.incrementAndGet();
                    candidates.remove(d);
                    continue;                                               // straight on to the next-nearest
                }
                held = d;
                Trip t = new Trip("T" + seq.incrementAndGet(), rider, d, pickup, drop, type, clock.nowMs());
                t.assigned(clock.nowMs());
                trips.put(t.id(), t);
                activeTrip.put(rider.id(), t.id());                         // the slot now names the real ride
                booked = true;
                publish(t, TripStatus.REQUESTED, TripStatus.ASSIGNED);
                return Optional.of(t);
            }
        } finally {
            if (!booked) {                                                  // whatever this call took, it gives back
                if (held != null) held.release();
                activeTrip.remove(rider.id(), MATCHING);
            }
        }
    }

    /**
     * What the rider's map shows before he books: the k nearest FREE cars of his tier, nearest first. The same nine
     * cells as matching, then a heap that keeps only the k nearest, so it costs O(c log k) for c cars nearby. Each
     * distance is read once, so a ping landing mid-sort cannot upset the order. Changes nothing.
     */
    List<Driver> nearestFree(Location pickup, VehicleType type, int k) {
        if (k <= 0) return List.of();
        Comparator<Map.Entry<Driver, Double>> byKm = Map.Entry.comparingByValue();
        PriorityQueue<Map.Entry<Driver, Double>> keep = new PriorityQueue<>(byKm.reversed());   // farthest on top
        for (Driver d : index.nearby(pickup)) {
            if (d.status() != DriverStatus.AVAILABLE || d.vehicle().type() != type) continue;
            keep.add(Map.entry(d, d.location().distanceKm(pickup)));
            if (keep.size() > k) keep.poll();                               // drop the farthest: k stay
        }
        List<Map.Entry<Driver, Double>> out = new ArrayList<>(keep);
        out.sort(byKm);
        return out.stream().map(Map.Entry::getKey).toList();
    }

    /** The car is at the kerb. */
    Trip driverArrived(String tripId) {
        Trip t = trip(tripId);
        t.arrived(clock.nowMs());
        publish(t, TripStatus.ASSIGNED, TripStatus.ARRIVED);
        return t;
    }

    /**
     * The rider is in. The trip goes IN_PROGRESS and the driver RESERVED -> ON_TRIP in one step under the trip's
     * monitor, the same lock endTrip and cancelTrip hold, so nobody ever sees one of the two moves without the other.
     */
    Trip startTrip(String tripId) {
        Trip t = trip(tripId);
        synchronized (t) {
            t.started(clock.nowMs());                                        // validated first: an early start throws here
            t.driver().board();                                              // he can only be RESERVED for this trip here
        }
        publish(t, TripStatus.ARRIVED, TripStatus.IN_PROGRESS);
        return t;
    }

    /**
     * The other critical step, and it has the opposite shape to the first one. Claiming a driver had to happen
     * BEFORE anything was written; a ride cannot be un-driven, so here the ride is committed first and the money
     * follows. The order is: check the distance, price it (writes nothing, and it may throw), then under the trip's
     * monitor record that the ride ended AND put the car back in the pool, and only then call the gateway, outside
     * every lock, with the trip id as the idempotency key. A declined card leaves the trip COMPLETED_UNPAID, the
     * driver free and the rider free to book again; retryPayment finishes the money later, and charges once. Money
     * trouble must never hold a car, or a rider, hostage.
     */
    Trip endTrip(String tripId, double distanceKm) {
        if (!(distanceKm >= 0) || Double.isInfinite(distanceKm))                    // NaN fails the >= test too
            throw new IllegalArgumentException("a driven distance must be a number >= 0, got " + distanceKm);
        Trip t = trip(tripId);
        long now = clock.nowMs();
        long mins = Math.max(1, Math.round((now - t.startedAtMs()) / 60_000.0));      // every ride bills at least a minute
        long fare = pricing.price(new FareBasis(t.type(), distanceKm, mins, t.pickup(), now));
        synchronized (t) {
            t.ended(distanceKm, mins, fare, now);                                    // guarded: a second endTrip throws
            t.driver().release();                                                    // the car is free before the money
        }
        activeTrip.remove(t.rider().id(), t.id());                                   // and so is the rider's one-ride slot
        publish(t, TripStatus.IN_PROGRESS, TripStatus.COMPLETED_UNPAID);
        settle(t);
        return t;
    }

    /**
     * Try the money again on a trip the gateway refused. Refused BEFORE the gateway is called unless the trip is
     * COMPLETED_UNPAID, so a retry can never send the trip's key with a fare that is not final yet.
     */
    Trip retryPayment(String tripId) {
        Trip t = trip(tripId);
        if (t.status() != TripStatus.COMPLETED_UNPAID)
            throw new IllegalStateException(t.id() + " has nothing to charge: it is " + t.status());
        settle(t);
        return t;
    }

    /** Charge a finished, unpaid trip once. Status and fare are read together, under the lock ended() wrote them in. */
    private void settle(Trip t) {
        long fare;
        synchronized (t) {
            if (t.status() != TripStatus.COMPLETED_UNPAID) return;            // a racing settle already finished it
            fare = t.farePaise();
        }
        String ref;
        try {
            ref = payments.charge(t.rider().id(), fare, "trip:" + t.id());          // outside every lock
        } catch (PaymentDeclined e) {
            System.out.println("[unpaid] " + t.id() + " " + Money.fmt(fare) + ": " + e.getMessage());
            return;
        }
        if (t.paid(ref)) publish(t, TripStatus.COMPLETED_UNPAID, TripStatus.COMPLETED);
    }

    /**
     * Call the ride off. The fee depends on the state the trip is being cancelled IN, so reading that state and
     * cancelling must be ONE step: they run inside the trip's own monitor, the same one transitionTo holds. Split
     * them and a cancel racing the driver's arrival reads ASSIGNED, prices the cancellation free, and then cancels
     * a trip that has meanwhile reached ARRIVED -- a kerbside cancellation given away. The car goes back in the same
     * locked step and the rider's slot right after, because every path that takes a driver out must put him back or
     * the fleet drains. A declined fee is only logged here; nothing retries it.
     */
    Trip cancelTrip(String tripId) {
        Trip t = trip(tripId);
        TripStatus from;
        long fee;
        synchronized (t) {                                                   // re-entrant: transitionTo takes this same lock
            from = t.status();
            fee = cancellation.feePaise(from, clock.nowMs() - t.requestedAtMs());
            t.cancelled(fee);                                                // validated before anything else moves
            t.driver().release();
        }
        activeTrip.remove(t.rider().id(), t.id());
        if (fee > 0) {
            try { payments.charge(t.rider().id(), fee, "cancel:" + t.id()); }
            catch (PaymentDeclined e) { System.out.println("[unpaid fee] " + t.id() + ": " + e.getMessage()); }
        }
        publish(t, from, TripStatus.CANCELLED);
        return t;
    }

    /** One trip by id. O(1). */
    Trip trip(String id) {
        Trip t = trips.get(id);
        if (t == null) throw new NoSuchElementException("no such trip: " + id);
        return t;
    }
    /** One driver by id. O(1). */
    Driver driver(String id) {
        Driver d = drivers.get(id);
        if (d == null) throw new NoSuchElementException("no such driver: " + id);
        return d;
    }
    /** One rider by id. O(1). */
    Rider rider(String id) {
        Rider r = riders.get(id);
        if (r == null) throw new NoSuchElementException("no such rider: " + id);
        return r;
    }
    /** The ride this rider is on right now, if any. What the app shows instead of booking a second car. */
    Optional<Trip> activeTripOf(String riderId) {
        String id = activeTrip.get(riderId);
        return id == null || id.equals(MATCHING) ? Optional.empty() : Optional.of(trip(id));
    }
    /** Every trip, for a screen or a test. */
    Collection<Trip> trips() { return Collections.unmodifiableCollection(trips.values()); }
    /** How many times a request reached for a car and found it already taken. The cost of the race, measured. */
    long lostRaces() { return lostRaces.get(); }

    /** Tell every listener, after the state has already moved, and survive one that throws. */
    private void publish(Trip t, TripStatus from, TripStatus to) {
        for (TripObserver o : observers) {
            try { o.onTrip(t, from, to); }
            catch (RuntimeException e) { System.err.println("[observer failed] " + e.getMessage()); }
        }
    }
}

/**
 * Proof it works: one ride from tap to receipt with a 1.5x surge, a second tap that is refused, a declined card
 * that leaves the trip unpaid and is retried, a late cancellation with a fee, an out-of-order call that is
 * refused, and then fifty riders reaching for one car at once, and two hundred riders reaching for forty cars.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        GridIndex index = new GridIndex();
        RideService uber = new RideService(index);
        long[] now = { 1_700_000_000_000L };                                  // a clock the demo drives by hand
        uber.setClock(() -> now[0]);
        CardPayment card = new CardPayment();
        uber.configure(new NearestDriver(),
                       new SurgePricing(new NormalPricing(), b -> 15_000),    // 1.5x, everywhere, for the demo
                       new StandardCancellation(), card);
        uber.addObserver(new PushNotifier());

        uber.addRider(new Rider("R1", "Meera"));
        uber.addRider(new Rider("R2", "Ravi"));
        Location kormangala = new Location(12.9352, 77.6245);

        Driver asha  = new Driver("D1", "Asha",  new Vehicle("KA01AB1234", VehicleType.GO),      new Location(12.9380, 77.6260));
        Driver bilal = new Driver("D2", "Bilal", new Vehicle("KA02CD5678", VehicleType.GO),      new Location(12.9358, 77.6250));
        Driver chen  = new Driver("D3", "Chen",  new Vehicle("KA03EF9012", VehicleType.PREMIER), new Location(12.9355, 77.6247));
        Driver dev   = new Driver("D4", "Dev",   new Vehicle("KA04GH3456", VehicleType.GO),      new Location(12.9600, 77.6400));
        for (Driver d : List.of(asha, bilal, chen, dev)) uber.goOnline(d, d.location());
        Driver evan  = new Driver("D5", "Evan",  new Vehicle("KA05IJ7890", VehicleType.GO),      new Location(12.9353, 77.6246));
        System.out.println("online: " + index.size() + " drivers; Evan is offline and sitting on the pickup point");
        System.out.println("the map shows the nearest free GO cars: "
            + uber.nearestFree(kormangala, VehicleType.GO, 5).stream().map(Driver::name).toList()
            + "  (Chen is a PREMIER, Dev is 3 km out, Evan is offline)");

        // 1. a ride, end to end. Bilal is nearer than Asha; Chen is a PREMIER; Dev is 3 km away; Evan is offline
        Trip t = uber.requestRide("R1", kormangala, new Location(12.9720, 77.5940), VehicleType.GO).orElseThrow();
        System.out.println("matched " + t + "  (nearest GO of " + index.nearby(kormangala).size() + " scanned)");
        try { uber.requestRide("R1", kormangala, new Location(12.9720, 77.5940), VehicleType.GO); }
        catch (IllegalStateException e) { System.out.println("second tap refused: " + e.getMessage()); }
        uber.driverArrived(t.id());
        now[0] += 3 * 60_000L;
        uber.startTrip(t.id());
        now[0] += 24 * 60_000L;                                                // a 24-minute, 8 km ride
        uber.endTrip(t.id(), 8.0);
        System.out.println("fare = (4000 base + 1200x8.0 km + 150x24 min) x 1.5 surge = " + Money.fmt(t.farePaise())
            + "; ref " + t.paymentRef() + "; Bilal is " + bilal.status() + " again");

        // 2. an out-of-order call is refused, and changes nothing
        Trip t2 = uber.requestRide("R2", kormangala, new Location(12.9720, 77.5940), VehicleType.GO).orElseThrow();
        try { uber.endTrip(t2.id(), 5.0); }
        catch (IllegalStateException e) { System.out.println("expected: " + e.getMessage()); }
        System.out.println("after the refused call the trip is still " + t2.status()
            + " and the fare is " + Money.fmt(t2.farePaise()));

        // 3. a late cancellation: the driver was already at the kerb, so it costs thirty rupees, and he is freed
        uber.driverArrived(t2.id());
        now[0] += 5 * 60_000L;
        uber.cancelTrip(t2.id());
        System.out.println("cancelled after arrival: fee " + Money.fmt(t2.feePaise())
            + ", " + t2.driver().name() + " is " + t2.driver().status() + " again");

        // 4. the card declines: the ride still happened, the driver is still freed, and the retry charges once
        RideService flaky = new RideService(new GridIndex());
        boolean[] declining = { true };
        CardPayment realCard = new CardPayment();
        flaky.configure(new NearestDriver(), new NormalPricing(), new StandardCancellation(),
            (riderId, paise, key) -> {
                if (declining[0]) throw new PaymentDeclined("insufficient funds");
                return realCard.charge(riderId, paise, key);
            });
        flaky.setClock(() -> now[0]);
        flaky.addRider(new Rider("R9", "Nita"));
        Driver frank = new Driver("D9", "Frank", new Vehicle("KA09KL1234", VehicleType.AUTO), kormangala);
        flaky.goOnline(frank, kormangala);
        Trip t3 = flaky.requestRide("R9", kormangala, new Location(12.94, 77.63), VehicleType.AUTO).orElseThrow();
        flaky.driverArrived(t3.id()); flaky.startTrip(t3.id());
        now[0] += 10 * 60_000L;
        flaky.endTrip(t3.id(), 4.0);
        System.out.println("declined: trip is " + t3.status() + ", " + frank.name() + " is " + frank.status()
            + " and can take the next rider");
        declining[0] = false;
        flaky.retryPayment(t3.id());
        System.out.println("after the retry: " + t3.status() + ", ref " + t3.paymentRef()
            + ", money moved " + realCard.charges() + " time(s)");

        // 5. fifty riders reach for ONE car at the same instant: exactly one of them may get a trip
        System.out.println(race(1, 50));
        // and two hundred riders for forty cars: every car is used, and no car twice
        System.out.println(race(40, 200));
        System.out.println("index: " + index.stats());
    }

    /**
     * Put `cars` drivers on one spot, fire `riders` simultaneous requests at it, and check the invariant: the
     * number of trips equals the number of cars, and no driver appears in two trips.
     */
    private static String race(int cars, int riders) throws Exception {
        GridIndex index = new GridIndex();
        RideService svc = new RideService(index);
        Location spot = new Location(12.9352, 77.6245);
        for (int i = 0; i < cars; i++) {
            Driver d = new Driver("d" + i, "driver" + i, new Vehicle("P" + i, VehicleType.GO), spot);
            svc.goOnline(d, spot);
        }
        for (int i = 0; i < riders; i++) svc.addRider(new Rider("r" + i, "rider" + i));
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Optional<Trip>>> futures = new ArrayList<>();
        for (int i = 0; i < riders; i++) {
            final String rid = "r" + i;
            futures.add(pool.submit(() -> { go.await(); return svc.requestRide(rid, spot, new Location(12.97, 77.59), VehicleType.GO); }));
        }
        go.countDown();
        Set<String> claimed = new HashSet<>();
        int matched = 0;
        for (Future<Optional<Trip>> f : futures) {
            Optional<Trip> trip = f.get();
            if (trip.isPresent()) { matched++; claimed.add(trip.get().driver().id()); }
        }
        pool.shutdown();
        if (matched != cars || claimed.size() != cars) throw new AssertionError("a car was double-booked");
        return riders + " riders, " + cars + " car(s): matched=" + matched + " distinct drivers=" + claimed.size()
            + " lost races=" + svc.lostRaces() + " (must be " + cars + "/" + cars + ")";
    }
}
