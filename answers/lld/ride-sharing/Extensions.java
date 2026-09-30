import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose: a twist
// that needs a big block means the derivation on page 02 went wrong. Nothing in Main.java changes for any of them.

// ---- ext: the driver declines, or never taps accept -- the claim becomes an offer with a deadline
/**
 * One ride shown on one driver's phone until a deadline. What happens to it is decided exactly once, by a
 * compare-and-set away from PENDING, so "he tapped accept" and "the timer ran out" can arrive in the same
 * millisecond and only one of them wins. The offer object is also the ticket: a late tap on an OLD offer finds it
 * already decided, so it can never attach him to a newer ride, even though his status reads RESERVED again.
 */
final class Offer {
    enum Outcome { PENDING, ACCEPTED, DECLINED, EXPIRED }
    private final String id, riderId;
    private final Driver driver;
    private final long deadlineMs;
    private final AtomicReference<Outcome> outcome = new AtomicReference<>(Outcome.PENDING);

    Offer(String id, String riderId, Driver driver, long deadlineMs) {
        this.id = id; this.riderId = riderId; this.driver = driver; this.deadlineMs = deadlineMs;
    }
    String id()          { return id; }
    String riderId()     { return riderId; }
    Driver driver()      { return driver; }
    long deadlineMs()    { return deadlineMs; }
    Outcome outcome()    { return outcome.get(); }
    /** Decide the offer, once. False if a tap or the timer already decided it. */
    boolean decide(Outcome to) { return outcome.compareAndSet(Outcome.PENDING, to); }
    @Override public String toString() { return id + " " + outcome.get(); }
}

/**
 * Dispatch with consent. offer() takes the nearest free car out of the pool with the same reserve() that
 * requestRide uses, so a driver can never be offered two rides at once: making the offer IS the compare-and-set.
 * accept() keeps the car; decline() and expireDue() put it back, and the rider's next offer skips every driver who
 * already saw his request. Every offer stays in the driver's history: that is his "accepted and declined" screen.
 */
class OfferDesk {
    private final DriverIndex index;
    private final MatchingStrategy matching;
    private final Clock clock;
    private final long windowMs;
    private final AtomicLong seq = new AtomicLong();
    private final Map<String, Offer> ringing = new ConcurrentHashMap<>();           // offer id -> an undecided offer
    private final Map<String, Set<String>> askedFor = new ConcurrentHashMap<>();    // rider -> drivers who saw his request
    private final Map<String, List<Offer>> history = new ConcurrentHashMap<>();     // driver -> every offer he got

    OfferDesk(DriverIndex index, MatchingStrategy matching, Clock clock, long windowMs) {
        this.index = index; this.matching = matching; this.clock = clock; this.windowMs = windowMs;
    }
    /** Ring the nearest free car that has not seen this rider's request yet. Empty when nobody is left to ask. */
    Optional<Offer> offer(String riderId, Location pickup, VehicleType type) {
        Set<String> asked = askedFor.computeIfAbsent(riderId, k -> ConcurrentHashMap.newKeySet());
        List<Driver> candidates = new ArrayList<>(index.nearby(pickup));
        candidates.removeIf(d -> asked.contains(d.id()));
        while (true) {
            Optional<Driver> pick = matching.select(pickup, type, candidates);
            if (pick.isEmpty()) { askedFor.remove(riderId); return Optional.empty(); }   // a later request starts afresh
            Driver d = pick.get();
            if (!d.reserve()) { candidates.remove(d); continue; }    // his phone is already ringing for someone else
            asked.add(d.id());
            Offer o = new Offer("O" + seq.incrementAndGet(), riderId, d, clock.nowMs() + windowMs);
            ringing.put(o.id(), o);
            history.computeIfAbsent(d.id(), k -> new CopyOnWriteArrayList<>()).add(o);
            return Optional.of(o);
        }
    }
    /** He tapped accept. Wins only while the offer is undecided and the tap is inside the window. */
    boolean accept(String offerId) {
        Offer o = ringing.get(offerId);
        if (o == null) return false;                                 // already decided: a late or a repeated tap
        if (clock.nowMs() > o.deadlineMs()) { close(o, Offer.Outcome.EXPIRED); return false; }
        if (!o.decide(Offer.Outcome.ACCEPTED)) return false;         // the timer decided it a moment earlier
        ringing.remove(offerId);
        askedFor.remove(o.riderId());
        return true;                                                 // the car stays RESERVED: the trip starts now
    }
    /** He tapped decline: the car goes straight back into the pool. */
    boolean decline(String offerId) {
        Offer o = ringing.get(offerId);
        return o != null && close(o, Offer.Outcome.DECLINED);
    }
    /** The timer, run every second: each offer past its deadline expires and its car goes back. Returns how many. */
    int expireDue() {
        int n = 0;
        for (Offer o : ringing.values()) if (clock.nowMs() > o.deadlineMs() && close(o, Offer.Outcome.EXPIRED)) n++;
        return n;
    }
    /** Every offer this driver got and what became of it, oldest first. */
    List<Offer> historyOf(String driverId) { return List.copyOf(history.getOrDefault(driverId, List.of())); }

    private boolean close(Offer o, Offer.Outcome how) {
        if (!o.decide(how)) return false;                            // somebody else decided it first: touch nothing
        ringing.remove(o.id());
        o.driver().release();                                        // RESERVED -> AVAILABLE, back in the pool
        return true;
    }
}

// ---- ext: fairness -- nearest-first starves the car parked at the edge of the hotspot
/**
 * Ops says the same few cars keep winning while a driver two streets out waits an hour. This is a NEW matching
 * rule and one line where the service is built: among the cars that are close enough, send the one who has been
 * idle longest. Distance is still the first filter, because fairness inside a five-kilometre radius is fair;
 * fairness across a city is a rider waiting twenty minutes.
 */
class LongestIdleMatching implements MatchingStrategy {
    private static final double MAX_PICKUP_KM = 5.0;
    private final Map<String, Long> idleSince = new ConcurrentHashMap<>();
    private final Clock clock;
    LongestIdleMatching(Clock clock) { this.clock = clock; }
    /** Called when a driver comes back into the pool; stamps the start of his wait. */
    void onAvailable(String driverId) { idleSince.put(driverId, clock.nowMs()); }
    public Optional<Driver> select(Location pickup, VehicleType type, List<Driver> candidates) {
        Driver best = null; long bestStamp = Long.MAX_VALUE;
        for (Driver d : candidates) {
            if (d.status() != DriverStatus.AVAILABLE || d.vehicle().type() != type) continue;
            if (d.location().distanceKm(pickup) > MAX_PICKUP_KM) continue;        // still bounded by distance
            long stamp = idleSince.getOrDefault(d.id(), 0L);                      // the oldest stamp waited longest
            if (stamp < bestStamp) { bestStamp = stamp; best = d; }
        }
        return Optional.ofNullable(best);
    }
}

// ---- ext: minutes, not kilometres -- the straight line is a lie when there is a river in the way
/** The seam where a real routing service plugs in. One method, so a test can hand in a fixed map. */
interface RouteProvider {
    /** How long a car at `from` would take to reach `to`, in seconds. */
    long etaSeconds(Location from, Location to);
}

/** Send the car that will ARRIVE first, which is not always the closest one. A new class, nothing else moves. */
class EtaMatching implements MatchingStrategy {
    private final RouteProvider routes;
    EtaMatching(RouteProvider routes) { this.routes = routes; }
    public Optional<Driver> select(Location pickup, VehicleType type, List<Driver> candidates) {
        Driver best = null; long bestEta = Long.MAX_VALUE;
        for (Driver d : candidates) {
            if (d.status() != DriverStatus.AVAILABLE || d.vehicle().type() != type) continue;
            long eta = routes.etaSeconds(d.location(), pickup);
            if (eta < bestEta) { bestEta = eta; best = d; }
        }
        return Optional.ofNullable(best);
    }
}

/**
 * "Three minutes away" is not a field anybody keeps up to date; it is a question, answered when the screen asks
 * it. The inputs are already there: the driver's last ping and the trip's own status. Before the rider is in the
 * car the answer is the time to the kerb; once the meter is running it is the time to the destination. Nothing is
 * stored, so nothing can go stale, and no ping has to be copied out to every open app.
 */
class RiderEta {
    /** Seconds until the car reaches whatever the rider is waiting for right now. */
    static long secondsAway(RouteProvider routes, Trip t) {
        Location target = t.status() == TripStatus.IN_PROGRESS ? t.drop() : t.pickup();
        return routes.etaSeconds(t.driver().location(), target);
    }
}

/**
 * Paytm's version of the question: the ETA depends on the vehicle. One RouteProvider per tier, looked up by the
 * car's own type, so an auto and an XL on the same spot get different answers and a new tier is one more entry.
 */
class EtaByVehicle {
    private final Map<VehicleType, RouteProvider> byType = new EnumMap<>(VehicleType.class);
    EtaByVehicle(Map<VehicleType, RouteProvider> rules) { byType.putAll(rules); }
    /** Seconds for this car to reach `to`, by the rule for its tier. */
    long secondsAway(Driver d, Location to) {
        RouteProvider rule = byType.get(d.vehicle().type());
        if (rule == null) throw new IllegalArgumentException("no ETA rule for " + d.vehicle().type());
        return rule.etaSeconds(d.location(), to);
    }
    /** The simplest rule: road distance (the straight line times 1.35) at one average speed. */
    static RouteProvider atKmph(double kmph) {
        return (from, to) -> Math.round(from.distanceKm(to) * 1.35 / kmph * 3600);
    }
}

// ---- ext: coupons and tolls -- more wrappers, never more flags
/**
 * A percentage off, capped. A wrapper, like surge, so the order of the stack is visible where it is built instead of
 * hidden in an if-chain: surge first, then the coupon on the surged fare, then tolls on top. More than 100% off is
 * refused when the coupon is made: it would turn a fare into a payment to the rider.
 */
class CouponPricing implements PricingStrategy {
    private final PricingStrategy base;
    private final int offBasisPoints;
    private final long capPaise;
    CouponPricing(PricingStrategy base, int offBasisPoints, long capPaise) {
        if (offBasisPoints < 0 || offBasisPoints > 10_000 || capPaise < 0)
            throw new IllegalArgumentException("a coupon takes 0 to 100% off, with a cap of 0 or more");
        this.base = base; this.offBasisPoints = offBasisPoints; this.capPaise = capPaise;
    }
    public long price(FareBasis b) {
        long full = base.price(b);
        return full - Math.min(Math.multiplyExact(full, (long) offBasisPoints) / 10_000, capPaise);
    }
}

/** A flat amount the rider owes whatever the meter said: a toll, an airport levy, a night charge. */
class SurchargePricing implements PricingStrategy {
    private final PricingStrategy base;
    private final ToLongFunction<FareBasis> surcharge;
    SurchargePricing(PricingStrategy base, ToLongFunction<FareBasis> surcharge) { this.base = base; this.surcharge = surcharge; }
    public long price(FareBasis b) { return Math.addExact(base.price(b), surcharge.applyAsLong(b)); }
}

// ---- ext: real surge -- the multiplier comes from the numbers the index already holds
/** How many rides were asked for around a place lately: a sliding window of timestamps per grid cell. */
class DemandCounter {
    private final Map<String, Deque<Long>> byCell = new ConcurrentHashMap<>();
    private final long windowMs;
    DemandCounter(long windowMs) { this.windowMs = windowMs; }
    /** Record one request in its cell. O(1) amortised. */
    void record(Location where, long nowMs) {
        Deque<Long> q = byCell.computeIfAbsent(cell(where, 0, 0), k -> new ConcurrentLinkedDeque<>());
        q.addLast(nowMs);
        trim(q, nowMs);
    }
    /** Requests inside the window over the SAME nine cells the index hands to matching: demand and supply, one area. */
    int recent(Location where, long nowMs) {
        int n = 0;
        for (int dLat = -1; dLat <= 1; dLat++)
            for (int dLng = -1; dLng <= 1; dLng++) {
                Deque<Long> q = byCell.get(cell(where, dLat, dLng));
                if (q != null) { trim(q, nowMs); n += q.size(); }
            }
        return n;
    }
    private void trim(Deque<Long> q, long nowMs) {
        Long head;
        while ((head = q.peekFirst()) != null && head < nowMs - windowMs) q.pollFirst();
    }
    private static String cell(Location l, int dLat, int dLng) {
        return ((long) Math.floor(l.lat() / 0.01) + dLat) + ":" + ((long) Math.floor(l.lng() / 0.01) + dLng);
    }
}

/**
 * Surge by area and minute: riders wanting a car divided by cars available, clamped between 1.0x and 3.0x. It
 * reads the index and the demand counter and nothing else, so the service never learns what surge is.
 */
class ZoneSurge implements SurgeSource {
    private final DriverIndex index;
    private final DemandCounter demand;
    ZoneSurge(DriverIndex index, DemandCounter demand) { this.index = index; this.demand = demand; }
    public int basisPoints(FareBasis b) {
        int supply = 0;
        for (Driver d : index.nearby(b.pickup())) if (d.status() == DriverStatus.AVAILABLE) supply++;
        int want = demand.recent(b.pickup(), b.atMs());
        if (supply == 0) return want > 0 ? 30_000 : 10_000;
        int bp = (int) Math.min(30_000L, 10_000L * want / supply);
        return Math.max(10_000, bp);                                 // never a discount; that is a coupon's job
    }
}

// ---- ext: pooling -- one car, several riders, one fare to divide
/**
 * A pooled ride is not a new state machine: it is a trip with more than one rider and a fare to divide. The rule
 * that matters is the division, and it has exactly the Splitwise problem: the shares must add up to the fare to
 * the paise, so the last rider absorbs the rounding.
 */
class PoolFare {
    /** One rider's stretch of a pooled ride: the kilometres they were actually in the car. */
    record Leg(String riderId, double km) {}
    /** Divide one fare in proportion to the distance each rider travelled. The shares always sum to farePaise. */
    static Map<String, Long> split(long farePaise, List<Leg> legs) {
        double total = 0;
        for (Leg l : legs) {
            if (!(l.km() >= 0)) throw new IllegalArgumentException("a leg cannot be negative: " + l);
            total += l.km();
        }
        if (total <= 0) throw new IllegalArgumentException("no kilometres to divide the fare over");
        Map<String, Long> out = new LinkedHashMap<>();
        long allocated = 0;
        for (int i = 0; i < legs.size(); i++) {
            long share = (i == legs.size() - 1) ? farePaise - allocated             // the last leg absorbs the drift
                                                : Math.round(farePaise * legs.get(i).km() / total);
            allocated += share;
            out.put(legs.get(i).riderId(), share);
        }
        return out;
    }
    // matching changes too, and only matching: the rule scores the DETOUR a new rider would add to the live route
    // instead of the distance to the pickup, so it is another MatchingStrategy, not a change to the service.
}

// ---- ext: the car-pool version -- users offer seats on a route, others pick one by preference
/**
 * The other prompt companies call "ride sharing" (a Swiggy / MakeMyTrip machine-coding round): no map and no
 * radius. A user OFFERS a ride -- vehicle, seats, origin, destination, start, duration -- and another user SELECTS
 * one of the open rides on that route by a preference. Two rules carry the round: a vehicle has at most one open
 * ride, and a seat is never sold twice. Both are move 4 again: putIfAbsent on the vehicle, compare-and-set on seats.
 */
class CarPool {
    /** One offered ride. seatsLeft is the contended cell, so it only ever moves by compare-and-set. */
    static final class Ride {
        final String id, driver, vehicle, origin, destination;
        final long startMs, durationMs;
        private final AtomicInteger seatsLeft;
        private volatile boolean ended;
        Ride(String id, String driver, String vehicle, String origin, String destination, long startMs, long durationMs, int seats) {
            this.id = id; this.driver = driver; this.vehicle = vehicle; this.origin = origin; this.destination = destination;
            this.startMs = startMs; this.durationMs = durationMs; this.seatsLeft = new AtomicInteger(seats);
        }
        long endMs()    { return startMs + durationMs; }
        int seatsLeft() { return seatsLeft.get(); }
        /** Take n seats in one step, or none at all. */
        boolean take(int n) {
            while (true) {
                int left = seatsLeft.get();
                if (ended || left < n) return false;
                if (seatsLeft.compareAndSet(left, left - n)) return true;   // lost to another passenger: read again
            }
        }
        @Override public String toString() { return id + " " + vehicle + " " + origin + "->" + destination + " left " + seatsLeft.get(); }
    }
    /** A ride as it looked when the passenger searched. Sorting reads this copy, never a count that moves mid-sort. */
    record Seen(Ride ride, int left) {}
    /** How a passenger chooses among the open rides on his route: the enum carries the order, one constant each. */
    enum Preference {
        EARLIEST_ENDING(Comparator.comparingLong((Seen s) -> s.ride().endMs())),
        LOWEST_DURATION(Comparator.comparingLong((Seen s) -> s.ride().durationMs)),
        MOST_VACANT(Comparator.comparingInt(Seen::left).reversed());
        final Comparator<Seen> order;
        Preference(Comparator<Seen> order) { this.order = order; }
    }

    private final AtomicLong seq = new AtomicLong();
    private final Map<String, Ride> rides = new ConcurrentHashMap<>();              // ride id -> ride
    private final Map<String, List<Ride>> byRoute = new ConcurrentHashMap<>();      // "origin->destination" -> rides
    private final Map<String, Ride> openByVehicle = new ConcurrentHashMap<>();      // vehicle -> its one open ride
    private final Map<String, List<Ride>> offered = new ConcurrentHashMap<>(), taken = new ConcurrentHashMap<>();

    /** Offer a ride. Refused if this vehicle already has one open: putIfAbsent decides between two taps. */
    Ride offer(String driver, String vehicle, int seats, String origin, String destination, long startMs, long durationMs) {
        if (seats <= 0 || durationMs <= 0) throw new IllegalArgumentException("a ride needs seats and a duration");
        Ride r = new Ride("P" + seq.incrementAndGet(), driver, vehicle, origin, destination, startMs, durationMs, seats);
        if (openByVehicle.putIfAbsent(vehicle, r) != null)
            throw new IllegalStateException(vehicle + " already has an open ride");
        rides.put(r.id, r);
        byRoute.computeIfAbsent(origin + "->" + destination, k -> new CopyOnWriteArrayList<>()).add(r);
        offered.computeIfAbsent(driver, k -> new CopyOnWriteArrayList<>()).add(r);
        return r;
    }
    /**
     * Take seats on the best open ride of this route by the passenger's preference (and vehicle, if he named one).
     * If someone takes the last seats in between, the next-best ride is tried: the loser never waits.
     */
    Optional<Ride> select(String passenger, String origin, String destination, int seats, Preference pref, String vehicle) {
        if (seats <= 0) throw new IllegalArgumentException("ask for at least one seat");
        List<Seen> open = new ArrayList<>();
        for (Ride r : byRoute.getOrDefault(origin + "->" + destination, List.of())) {
            int left = r.seatsLeft();
            if (!r.ended && left >= seats && !r.driver.equals(passenger) && (vehicle == null || r.vehicle.equals(vehicle)))
                open.add(new Seen(r, left));
        }
        open.sort(pref.order);
        for (Seen s : open)
            if (s.ride().take(seats)) {
                taken.computeIfAbsent(passenger, k -> new CopyOnWriteArrayList<>()).add(s.ride());
                return Optional.of(s.ride());
            }
        return Optional.empty();
    }
    /** The driver ends the ride: no seat is sold after this, and the vehicle may offer a new ride. */
    void end(String rideId) {
        Ride r = rides.get(rideId);
        if (r == null) throw new NoSuchElementException("no ride " + rideId);
        r.ended = true;
        r.seatsLeft.set(0);                                          // a take() racing this end now fails its CAS
        openByVehicle.remove(r.vehicle, r);
    }
    /** Every ride this user offered. */
    List<Ride> offeredBy(String user) { return List.copyOf(offered.getOrDefault(user, List.of())); }
    /** Every ride this user took a seat on. */
    List<Ride> takenBy(String user)   { return List.copyOf(taken.getOrDefault(user, List.of())); }
}

// ---- ext: ratings -- a listener, because the money path must not wait for a star
/**
 * Stars, collected after a trip completes. It is an observer: the state machine announces COMPLETED and the rating
 * book hears it. The service never learns that ratings exist, and a rating rule can later feed a matching rule.
 */
class RatingBook implements TripObserver {
    private final Map<String, long[]> byDriver = new ConcurrentHashMap<>();   // driverId -> {sum, count}
    private final Map<String, String> pending = new ConcurrentHashMap<>();    // tripId -> driverId, awaiting a star
    public void onTrip(Trip t, TripStatus from, TripStatus to) {
        if (to == TripStatus.COMPLETED) pending.put(t.id(), t.driver().id());
    }
    /** The rider taps a star. Only a trip that actually completed can be rated, and only once. */
    void rate(String tripId, int stars) {
        if (stars < 1 || stars > 5) throw new IllegalArgumentException("stars must be 1..5: " + stars);
        String driverId = pending.remove(tripId);
        if (driverId == null) throw new IllegalStateException("no completed, unrated trip " + tripId);
        byDriver.compute(driverId, (k, v) -> v == null ? new long[]{stars, 1} : new long[]{v[0] + stars, v[1] + 1});
    }
    /** A driver's average, or 0 if nobody has rated him. */
    double averageOf(String driverId) {
        long[] v = byDriver.get(driverId);
        return v == null ? 0 : (double) v[0] / v[1];
    }
}

/**
 * "Nearest, then rating": every free car of the tier within 300 m of the nearest one counts as equally near, and
 * among those the best-rated wins. A floor (say 4.5 stars for a premium tier) filters first. A matching rule like
 * the others, reading the RatingBook; the service does not change.
 */
class RatedNearest implements MatchingStrategy {
    private static final double SAME_KM = 0.3;
    private final RatingBook ratings;
    private final double minStars;
    RatedNearest(RatingBook ratings, double minStars) { this.ratings = ratings; this.minStars = minStars; }
    public Optional<Driver> select(Location pickup, VehicleType type, List<Driver> candidates) {
        Map<Driver, Double> km = new HashMap<>();
        double nearest = Double.MAX_VALUE;
        for (Driver d : candidates) {
            if (d.status() != DriverStatus.AVAILABLE || d.vehicle().type() != type) continue;
            if (ratings.averageOf(d.id()) < minStars) continue;                  // the premium floor
            double k = d.location().distanceKm(pickup);
            km.put(d, k);
            nearest = Math.min(nearest, k);
        }
        Driver best = null; double bestStars = -1;
        for (Map.Entry<Driver, Double> e : km.entrySet()) {
            if (e.getValue() > nearest + SAME_KM) continue;                      // clearly further: not a tie
            double stars = ratings.averageOf(e.getKey().id());
            if (stars > bestStars || (stars == bestStars && e.getValue() < km.get(best))) { bestStars = stars; best = e.getKey(); }
        }
        return Optional.ofNullable(best);
    }
}

// ---- ext: the route each trip took -- Nykaa's "location history along with the exact route taken"
/**
 * The pings already arrive; the only question is where to keep the ones that belong to a trip. RouteLog IS a
 * DriverIndex and HOLDS one (a wrapper, like SurgePricing), so every ping passes through it on its way to the grid,
 * and it is also a TripObserver, which is how it learns when a trip starts and ends. The service changes by one
 * line: which index it is handed. The route also gives the fare a distance measured by the server, not a number
 * typed in by the driver's app.
 */
class RouteLog implements DriverIndex, TripObserver {
    private final DriverIndex inner;
    private final Map<String, List<Location>> openRoute = new ConcurrentHashMap<>();  // driver -> the route he is driving
    private final Map<String, List<Location>> routes = new ConcurrentHashMap<>();     // trip -> every point, in order
    RouteLog(DriverIndex inner) { this.inner = inner; }

    public void update(Driver d, Location where) {
        inner.update(d, where);
        List<Location> route = openRoute.get(d.id());
        if (route != null) route.add(where);                          // one append per ping, only while on a trip
    }
    public void remove(Driver d) { inner.remove(d); }
    public List<Driver> nearby(Location pickup) { return inner.nearby(pickup); }

    /** The meter starts: open a route at the pickup. The car stops: close it. Called after the move, like any observer. */
    public void onTrip(Trip t, TripStatus from, TripStatus to) {
        if (to == TripStatus.IN_PROGRESS) {
            List<Location> route = Collections.synchronizedList(new ArrayList<>(List.of(t.pickup())));
            routes.put(t.id(), route);
            openRoute.put(t.driver().id(), route);
        } else if (to == TripStatus.COMPLETED_UNPAID) {
            List<Location> route = routes.get(t.id());
            if (route != null) openRoute.remove(t.driver().id(), route);
        }
    }
    /** The exact route of one trip, as it was pinged. */
    List<Location> routeOf(String tripId) {
        List<Location> r = routes.getOrDefault(tripId, List.of());
        synchronized (r) { return List.copyOf(r); }
    }
    /** Kilometres along the pings, point to point. Real GPS jitters, so production smooths or snaps it to roads first. */
    double drivenKm(String tripId) {
        List<Location> r = routeOf(tripId);
        double km = 0;
        for (int i = 1; i < r.size(); i++) km += r.get(i - 1).distanceKm(r.get(i));
        return km;
    }
}

// ---- ext: a denser city -- the index is an interface, so the grid is one line where the service is built
/**
 * The known weakness of a uniform grid is density skew (far more cars in some cells than in others): one downtown
 * cell holds four thousand cars and the scan over them gets slow. The fix is resolution, and because DriverIndex is
 * an interface the fix is a new class: smaller cells and a wider ring downtown, bigger cells in the suburbs. A
 * production system uses a quadtree, a geohash prefix or Google S2 cells: the same idea with the size chosen per area.
 */
class PrecisionIndex implements DriverIndex {
    private final double cellDeg;
    private final int ring;                                          // how many cells out a read scans
    private final Map<Long, Set<Driver>> cells = new ConcurrentHashMap<>();
    private final Map<String, Long> cellOfDriver = new ConcurrentHashMap<>();
    PrecisionIndex(double cellDeg, int ring) { this.cellDeg = cellDeg; this.ring = ring; }
    public void update(Driver d, Location where) {
        d.moveTo(where);
        long cell = cellOf(where);
        Long seen = cellOfDriver.get(d.id());
        if (seen != null && seen.longValue() == cell) return;
        cellOfDriver.compute(d.id(), (id, old) -> {                  // one crossing at a time per driver, as in GridIndex
            if (old != null && old.longValue() == cell) return old;
            if (old != null) { Set<Driver> from = cells.get(old); if (from != null) from.remove(d); }
            cells.computeIfAbsent(cell, k -> ConcurrentHashMap.newKeySet()).add(d);
            return cell;
        });
    }
    public void remove(Driver d) {
        cellOfDriver.computeIfPresent(d.id(), (id, cell) -> {
            Set<Driver> from = cells.get(cell);
            if (from != null) from.remove(d);
            return null;
        });
    }
    public List<Driver> nearby(Location pickup) { return scan(pickup, ring); }
    /**
     * The other half of the density problem: a suburb whose nearby cells hold no FREE car of this tier (busy cars do
     * not count). Widen the ring until one turns up, and trust it only once it is closer than the ring's edge (r cells
     * from the pickup's own cell): then nobody outside can be nearer. Stop at the cap either way. The cap is a product
     * decision: a car twenty minutes away is a worse answer than "no cars right now", and it strips the suburb next
     * door of its own car. Each ring scanned costs (2r+1)^2 bucket lookups, so widening is cheap and bounded.
     */
    List<Driver> nearbyWidening(Location pickup, VehicleType type, int maxRing) {
        double cellKm = cellDeg * Math.min(110.57, 111.32 * Math.cos(Math.toRadians(pickup.lat())));  // a cell's narrow side
        for (int r = ring; r <= maxRing; r++) {
            List<Driver> out = scan(pickup, r);
            double best = Double.MAX_VALUE;
            for (Driver d : out)
                if (d.status() == DriverStatus.AVAILABLE && d.vehicle().type() == type)
                    best = Math.min(best, d.location().distanceKm(pickup));
            if (best <= r * cellKm || (r == maxRing && best < Double.MAX_VALUE)) return out;
        }
        return List.of();
    }
    private List<Driver> scan(Location pickup, int rings) {
        long latCell = (long) Math.floor(pickup.lat() / cellDeg), lngCell = (long) Math.floor(pickup.lng() / cellDeg);
        List<Driver> out = new ArrayList<>();
        for (long dLat = -rings; dLat <= rings; dLat++)
            for (long dLng = -rings; dLng <= rings; dLng++) {
                Set<Driver> bucket = cells.get(key(latCell + dLat, lngCell + dLng));
                if (bucket != null) out.addAll(bucket);
            }
        return out;
    }
    private long cellOf(Location l) { return key((long) Math.floor(l.lat() / cellDeg), (long) Math.floor(l.lng() / cellDeg)); }
    private static long key(long a, long b) { return (a << 32) ^ (b & 0xffff_ffffL); }
}

// ---- ext: persistence -- the compare-and-set becomes a conditional UPDATE, which is the same thing
/**
 * Beyond one process the driver's status cell cannot live in a JVM. It becomes a row, and the compare-and-set
 * becomes a conditional UPDATE: the database does exactly what the AtomicReference did, for the whole fleet.
 */
interface TripRepository {
    /** Write a trip once. False means this id already existed, which is what makes a client retry safe. */
    boolean insert(String tripId, String riderId, String driverId, TripStatus status);
    /** Move a trip only if it is still in `from`. The guarded transition, in the database. */
    boolean compareAndSetStatus(String tripId, TripStatus from, TripStatus to);
    /** What a trip's status is now, or empty if there is no such trip. */
    Optional<TripStatus> statusOf(String tripId);
}

/** The in-memory implementation, which is the same two operations the service already performs, wearing a coat. */
class InMemoryTripRepository implements TripRepository {
    private final Map<String, TripStatus> status = new ConcurrentHashMap<>();
    public boolean insert(String tripId, String riderId, String driverId, TripStatus s) {
        return status.putIfAbsent(tripId, s) == null;
    }
    public boolean compareAndSetStatus(String tripId, TripStatus from, TripStatus to) {
        return status.replace(tripId, from, to);
    }
    public Optional<TripStatus> statusOf(String tripId) { return Optional.ofNullable(status.get(tripId)); }
}
// the tables, one fact in one place (normalised):
//   rider(id PK, name)        vehicle(id PK, plate UNIQUE, type)        driver(id PK, name, vehicle_id FK, status)
//   trip(id PK, rider_id FK, driver_id FK, status, pickup, drop, km, minutes, fare_paise, fee_paise)
//   offer(id PK, trip_id FK, driver_id FK, outcome, offered_at)     -- "what did he accept and decline" is one SELECT
//   payment(id PK, trip_id FK, idempotency_key UNIQUE, paise, gateway_ref, status)
// the same operations in SQL, and the service's code does not change, only what it was handed:
//   UPDATE driver SET status = 'RESERVED' WHERE id = ? AND status = 'AVAILABLE';
//     -- 1 row updated means you won the car; 0 rows means somebody else did. That IS compareAndSet.
//   INSERT INTO trip (id, rider_id, driver_id, status) VALUES (?,?,?,'ASSIGNED') ON CONFLICT (id) DO NOTHING;
//     -- 0 rows inserted means a retried request: stop, the trip already exists
//   CREATE UNIQUE INDEX one_live_ride ON trip (rider_id) WHERE status NOT IN ('COMPLETED_UNPAID','COMPLETED','CANCELLED');
//     -- the rider's one-ride slot: a second open trip for him fails on the insert
//   UPDATE trip SET status = 'COMPLETED', payment_ref = ? WHERE id = ? AND status = 'COMPLETED_UNPAID';
//     -- the guarded transition, so two settlement workers cannot both complete the same trip

// ---- ext: the upfront fare -- quote before the ride, and hold the rider to it
/**
 * The rider sees a price before he taps, and is charged that price. The quote is the SAME pricing rule run on an
 * ESTIMATED basis -- the straight line stretched by a road factor, minutes at an assumed city speed -- so a quote
 * and a meter can never disagree about how a fare is built. The price and its multiplier are locked when he books:
 * surge that doubles while he is in the car changes nothing. Only a ride that turns out very different from the
 * estimate (over 15% longer or shorter: a new destination, a long detour) is re-priced from the meter, and even then
 * at the LOCKED multiplier. In Main.java that is one field, not a new interface: the trip remembers its quote id.
 */
class FareQuote {
    /** Roads are not straight lines, and a city car averages this. Product constants, not physics. */
    private static final double ROAD_FACTOR = 1.35, CITY_KMPH = 22.0, CHANGED_BY = 0.15;
    private final PricingStrategy base;                                      // the fare rule WITHOUT surge
    private final SurgeSource live;
    private final Map<String, Quote> quotes = new ConcurrentHashMap<>();
    private final AtomicLong seq = new AtomicLong();

    FareQuote(PricingStrategy base, SurgeSource live) { this.base = base; this.live = live; }

    /** What the rider was shown: the price, the multiplier inside it, and the distance it assumed. */
    record Quote(String id, long paise, int basisPoints, double estimatedKm) {}

    /** Price the ride before it happens, and remember the quote under its id. */
    Quote quote(VehicleType type, Location pickup, Location drop, long nowMs) {
        double km = pickup.distanceKm(drop) * ROAD_FACTOR;
        long minutes = Math.max(1, Math.round(km / CITY_KMPH * 60));
        FareBasis guess = new FareBasis(type, km, minutes, pickup, nowMs);
        int bp = live.basisPoints(guess);
        Quote q = new Quote("Q" + seq.incrementAndGet(), Math.multiplyExact(base.price(guess), (long) bp) / 10_000, bp, km);
        quotes.put(q.id(), q);
        return q;
    }
    /** The bill: the quoted price, unless the ride came out over 15% longer or shorter; then the meter, at the LOCKED multiplier. */
    long bill(String quoteId, VehicleType type, double drivenKm, long minutes, Location pickup, long atMs) {
        Quote q = quotes.get(quoteId);
        if (q == null) throw new IllegalArgumentException("no such quote: " + quoteId);   // never a silent 1.0x
        if (Math.abs(drivenKm - q.estimatedKm()) <= q.estimatedKm() * CHANGED_BY) return q.paise();   // the promise holds
        long meter = base.price(new FareBasis(type, drivenKm, minutes, pickup, atMs));
        return Math.multiplyExact(meter, (long) q.basisPoints()) / 10_000;
    }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) {
        long[] now = { 1_700_000_000_000L };
        Clock clock = () -> now[0];
        Location kormangala = new Location(12.9352, 77.6245);

        // offers: the nearest car lets it ring out, the next declines, the third accepts, and a late tap is refused
        GridIndex index = new GridIndex();
        List<Driver> fleet = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            Driver d = new Driver("D" + i, "driver" + i, new Vehicle("KA0" + i, VehicleType.GO),
                                  new Location(12.9352 + i * 0.0005, 77.6245));
            d.goOnline(); index.update(d, d.location()); fleet.add(d);
        }
        OfferDesk desk = new OfferDesk(index, new NearestDriver(), clock, 15_000);
        Offer first = desk.offer("R1", kormangala, VehicleType.GO).orElseThrow();
        now[0] += 16_000;
        int expired = desk.expireDue();
        Offer second = desk.offer("R1", kormangala, VehicleType.GO).orElseThrow();
        desk.decline(second.id());
        Offer third = desk.offer("R1", kormangala, VehicleType.GO).orElseThrow();
        boolean lateTap = desk.accept(first.id());
        boolean accepted = desk.accept(third.id());
        System.out.println("offers: " + first.driver().name() + " let it ring out (" + expired + " expired), "
            + second.driver().name() + " declined, " + third.driver().name() + " accepted=" + accepted
            + ", and " + first.driver().name() + "'s tap 16 s late counts=" + lateTap
            + "; history: D0 " + desk.historyOf("D0") + ", D1 " + desk.historyOf("D1") + ", D2 " + desk.historyOf("D2"));

        // fairness: the car that has waited longest wins, even though it is not the nearest
        fleet.get(2).release();                                              // he finished the accepted ride
        LongestIdleMatching fair = new LongestIdleMatching(clock);
        fair.onAvailable("D2"); now[0] += 60_000; fair.onAvailable("D1"); now[0] += 60_000; fair.onAvailable("D0");
        System.out.println("nearest picks " + new NearestDriver().select(kormangala, VehicleType.GO, fleet).map(Driver::name).orElse("-")
            + ", longest-idle picks " + fair.select(kormangala, VehicleType.GO, fleet).map(Driver::name).orElse("-"));

        // eta instead of distance: a river makes the nearest car the slowest
        RouteProvider routes = (from, to) -> from.equals(fleet.get(0).location()) ? 900 : 240;
        System.out.println("by ETA the answer is " + new EtaMatching(routes)
            .select(kormangala, VehicleType.GO, fleet).map(Driver::name).orElse("-") + " (the near car is across the river)");

        // eta by vehicle type: an auto and a GO parked on the same spot, 2 km out
        Location twoKm = new Location(12.9532, 77.6245);
        EtaByVehicle eta = new EtaByVehicle(Map.of(VehicleType.AUTO, EtaByVehicle.atKmph(18),
                                                   VehicleType.GO, EtaByVehicle.atKmph(24)));
        Driver auto = new Driver("A1", "auto", new Vehicle("KA-AUTO", VehicleType.AUTO), twoKm);
        Driver car = new Driver("G1", "car", new Vehicle("KA-GO", VehicleType.GO), twoKm);
        System.out.println("eta from 2 km out: auto " + eta.secondsAway(auto, kormangala) + " s, GO "
            + eta.secondsAway(car, kormangala) + " s");

        // the pricing stack, in the order the call site declares it
        FareBasis basis = new FareBasis(VehicleType.GO, 8.0, 24, kormangala, now[0]);
        PricingStrategy plain = new NormalPricing();
        PricingStrategy surged = new SurgePricing(plain, b -> 15_000);
        PricingStrategy couponed = new CouponPricing(surged, 2_000, Money.rupees("50.00"));
        PricingStrategy tolled = new SurchargePricing(couponed, b -> Money.rupees("35.00"));
        System.out.println("fare: base " + Money.fmt(plain.price(basis)) + " -> surge " + Money.fmt(surged.price(basis))
            + " -> 20% off, capped at 50 " + Money.fmt(couponed.price(basis))
            + " -> +35 toll " + Money.fmt(tolled.price(basis)));

        // real surge: six riders wanting a car around a pickup that has three free cars
        DemandCounter demand = new DemandCounter(5 * 60_000L);
        for (int i = 0; i < 6; i++) demand.record(kormangala, now[0]);
        ZoneSurge zone = new ZoneSurge(index, demand);
        long free = index.nearby(kormangala).stream().filter(d -> d.status() == DriverStatus.AVAILABLE).count();
        System.out.println("zone surge: 6 requests / " + free + " free cars = " + zone.basisPoints(basis) / 10_000.0
            + "x, so the fare is " + Money.fmt(new SurgePricing(plain, zone).price(basis)));

        // pooling: one fare, three riders, and the shares add up to the paise
        Map<String, Long> shares = PoolFare.split(Money.rupees("258.00"),
            List.of(new PoolFare.Leg("R1", 8.0), new PoolFare.Leg("R2", 5.0), new PoolFare.Leg("R3", 3.5)));
        long sum = shares.values().stream().mapToLong(Long::longValue).sum();
        System.out.println("pool split of 258.00 over 8.0/5.0/3.5 km -> " + shares + " summing to " + Money.fmt(sum));

        // the car-pool version: two rides offered Bangalore -> Mysore, a passenger picks by preference
        CarPool pool = new CarPool();
        long march21 = 1_710_995_400_000L;                                    // 10:00, the start of both rides
        pool.offer("John", "Swift KA-09-32321", 3, "Bangalore", "Mysore", march21, 3 * 3_600_000L);
        pool.offer("Rohan", "XUV KA-01-12345", 5, "Bangalore", "Mysore", march21, 4 * 3_600_000L);
        try { pool.offer("John", "Swift KA-09-32321", 2, "Bangalore", "Mysore", march21, 3_600_000L); }
        catch (IllegalStateException e) { System.out.println("car-pool: second offer refused: " + e.getMessage()); }
        System.out.println("car-pool: earliest ending -> " + pool.select("Smith", "Bangalore", "Mysore", 2, CarPool.Preference.EARLIEST_ENDING, null).orElseThrow()
            + "; most vacant -> " + pool.select("Asha", "Bangalore", "Mysore", 1, CarPool.Preference.MOST_VACANT, null).orElseThrow()
            + "; Smith took " + pool.takenBy("Smith").size() + ", John offered " + pool.offeredBy("John").size());

        // nearest, then rating: two cars 100 m apart, the better-rated one wins; a premium floor filters
        RideService rated = new RideService(new GridIndex());
        RatingBook book = new RatingBook();
        rated.setClock(clock); rated.addObserver(book);
        for (int i = 0; i < 2; i++) rated.addRider(new Rider("S" + i, "rider" + i));
        Driver nearOne = new Driver("N1", "Kiran", new Vehicle("KA-N1", VehicleType.GO), kormangala);
        Driver betterOne = new Driver("N2", "Latha", new Vehicle("KA-N2", VehicleType.GO), new Location(12.9361, 77.6245));
        rated.goOnline(nearOne, nearOne.location()); rated.goOnline(betterOne, betterOne.location());
        for (int i = 0; i < 2; i++) {                                         // one trip each, rated 3 and 5 stars
            Driver d = i == 0 ? nearOne : betterOne;
            Driver other = i == 0 ? betterOne : nearOne;
            rated.goOffline(other.id());
            Trip t = rated.requestRide("S" + i, kormangala, twoKm, VehicleType.GO).orElseThrow();
            rated.driverArrived(t.id()); rated.startTrip(t.id()); now[0] += 5 * 60_000L; rated.endTrip(t.id(), 2.0);
            book.rate(t.id(), i == 0 ? 3 : 5);
            rated.goOnline(other, other.location());
        }
        List<Driver> both = List.of(nearOne, betterOne);
        System.out.println("nearest picks " + new NearestDriver().select(kormangala, VehicleType.GO, both).map(Driver::name).orElse("-")
            + "; nearest-then-rating picks " + new RatedNearest(book, 0).select(kormangala, VehicleType.GO, both).map(Driver::name).orElse("-")
            + "; a 4.5-star floor leaves " + new RatedNearest(book, 4.5).select(kormangala, VehicleType.GO, List.of(nearOne)).map(Driver::name).orElse("nobody"));

        // the route each trip took: the pings pass through the log on their way to the grid
        RouteLog log = new RouteLog(new GridIndex());
        RideService traced = new RideService(log);
        traced.setClock(clock); traced.addObserver(log);
        traced.addRider(new Rider("R7", "Nita"));
        Driver dev = new Driver("V1", "Dev", new Vehicle("KA-V1", VehicleType.GO), kormangala);
        traced.goOnline(dev, kormangala);
        Trip ride = traced.requestRide("R7", kormangala, twoKm, VehicleType.GO).orElseThrow();
        traced.driverArrived(ride.id()); traced.startTrip(ride.id());
        for (int i = 1; i <= 4; i++) traced.ping("V1", new Location(12.9352 + i * 0.0045, 77.6245));   // four pings, 0.5 km apart
        now[0] += 6 * 60_000L;
        traced.endTrip(ride.id(), log.drivenKm(ride.id()));
        System.out.printf("route: %d points, %.3f km measured from the pings, fare %s%n",
            log.routeOf(ride.id()).size(), ride.distanceKm(), Money.fmt(ride.farePaise()));

        // a denser index: smaller cells, wider ring, same interface -- and a widening search for an empty suburb
        PrecisionIndex fine = new PrecisionIndex(0.0025, 2);
        for (Driver d : fleet) fine.update(d, d.location());
        Location suburb = new Location(12.9600, 77.6400);
        System.out.println("fine index (275 m cells, 5x5 ring) sees " + fine.nearby(kormangala).size()
            + " cars near the pickup, " + fine.nearby(suburb).size() + " out in the suburb, and widening to 20 rings finds "
            + fine.nearbyWidening(suburb, VehicleType.GO, 20).size());

        // the upfront fare: quoted at 1.5x; the real 8.0 km ride pays the quote, a detour or a much shorter ride is re-metered at 1.5x
        FareQuote quotes = new FareQuote(plain, b -> 15_000);
        FareQuote.Quote q = quotes.quote(VehicleType.GO, kormangala, new Location(12.9720, 77.5940), now[0]);
        System.out.printf("quote %s: %s at %.1fx for an estimated %.1f km; bill for the real 8.0 km / 24 min ride %s; "
            + "for an 11 km detour %s; for a 3 km change of plan %s%n", q.id(), Money.fmt(q.paise()), q.basisPoints() / 10_000.0,
            q.estimatedKm(), Money.fmt(quotes.bill(q.id(), VehicleType.GO, 8.0, 24, kormangala, now[0])),
            Money.fmt(quotes.bill(q.id(), VehicleType.GO, 11.0, 32, kormangala, now[0])),
            Money.fmt(quotes.bill(q.id(), VehicleType.GO, 3.0, 10, kormangala, now[0])));

        // ratings: the observer hears COMPLETED and nothing else in the system knows
        RideService svc = new RideService(new GridIndex());
        RatingBook stars = new RatingBook();
        svc.setClock(clock); svc.addObserver(stars);
        svc.addRider(new Rider("R1", "Meera"));
        Driver asha = new Driver("D9", "Asha", new Vehicle("KA09", VehicleType.GO), kormangala);
        svc.goOnline(asha, kormangala);
        Trip t = svc.requestRide("R1", kormangala, new Location(12.97, 77.59), VehicleType.GO).orElseThrow();
        RouteProvider live = (from, to) -> 90 + Math.round(from.distanceKm(to) / 18.0 * 3600);   // 18 km/h, plus the kerb
        System.out.println("eta: the rider's screen says " + RiderEta.secondsAway(live, t)
            + " s to the kerb -- answered on read from Asha's last ping, stored nowhere");
        svc.driverArrived(t.id()); svc.startTrip(t.id()); now[0] += 20 * 60_000L;
        svc.endTrip(t.id(), 6.0);
        stars.rate(t.id(), 5);
        System.out.println("ratings: Asha averages " + stars.averageOf("D9") + " over 1 trip; fare " + Money.fmt(t.farePaise()));

        // persistence: the conditional UPDATE is the compare-and-set
        TripRepository repo = new InMemoryTripRepository();
        System.out.println("repo insert " + repo.insert("T1", "R1", "D9", TripStatus.ASSIGNED)
            + ", the same insert again " + repo.insert("T1", "R1", "D9", TripStatus.ASSIGNED));
        System.out.println("repo IN_PROGRESS->COMPLETED_UNPAID from the wrong state: "
            + repo.compareAndSetStatus("T1", TripStatus.IN_PROGRESS, TripStatus.COMPLETED_UNPAID)
            + ", from the right one: " + repo.compareAndSetStatus("T1", TripStatus.ASSIGNED, TripStatus.ARRIVED)
            + ", now " + repo.statusOf("T1").orElseThrow());
    }
}
