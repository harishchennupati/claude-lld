import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.time.*;

// ---- ext: a background sweeper reclaims lapsed holds -- for the display, never for correctness
/**
 * Walks every show every few seconds and hands lapsed holds back. Correctness never depended on it: a
 * lapsed hold is already treated as free by the next caller. This only makes the free count catch up sooner.
 */
class HoldSweeper {
    private final List<Show> shows;
    private final ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor(
        r -> { Thread t = new Thread(r, "sweeper"); t.setDaemon(true); return t; });
    HoldSweeper(List<Show> shows) { this.shows = shows; }
    /** Start sweeping. Each pass takes each show's lock for a few microseconds and releases it. */
    void start(long everyMs) {
        timer.scheduleAtFixedRate(() -> {
            for (Show s : shows) {
                try { s.sweepExpired(); } catch (RuntimeException e) { /* one bad show must not kill the timer */ }
            }
        }, everyMs, everyMs, TimeUnit.MILLISECONDS);
    }
    void stop() { timer.shutdownNow(); }
    /** One pass by hand, for tests: how many holds were reclaimed. */
    int sweepOnce() { int n = 0; for (Show s : shows) n += s.sweepExpired(); return n; }
}
// A DelayQueue<Booking> (Java's queue that hands out each item only when its time comes) keyed on holdExpiresMs
// is the same idea without the polling. Both are optimisations of the lazy path.

// ---- ext: many theatres and screens -- search is an index hop, and each show carries its own lock
/**
 * The read path: city, then movie, then that movie's shows sorted by start time. A time window is a range
 * read on the sorted map, so tonight's search never walks next week's shows. It never takes a show's lock,
 * so browsing cannot slow booking down.
 */
class ShowIndex {
    /** One show as search sees it: the theatre it is in, and the show. */
    record Listing(String theatreId, Show show) {}
    // city -> movie -> start time -> listings. ConcurrentSkipListMap is Java's thread-safe sorted map.
    private final Map<String, Map<String, ConcurrentSkipListMap<Long, List<Listing>>>> index = new ConcurrentHashMap<>();
    /** Register a show for search. Setup, or whenever a theatre publishes a new day. */
    void add(Theatre theatre, Show show) {
        index.computeIfAbsent(theatre.city, c -> new ConcurrentHashMap<>())
             .computeIfAbsent(show.movie, m -> new ConcurrentSkipListMap<>())
             .computeIfAbsent(show.startMs, t -> new CopyOnWriteArrayList<>()).add(new Listing(theatre.id, show));
    }
    /** Shows of one movie in one city that start inside [fromMs, toMs), earliest first. Two hops, then O(log n + k). */
    List<Listing> search(String city, String movie, long fromMs, long toMs) {
        ConcurrentSkipListMap<Long, List<Listing>> byStart = index.getOrDefault(city, Map.of()).get(movie);
        List<Listing> out = new ArrayList<>();
        if (byStart != null) for (List<Listing> same : byStart.subMap(fromMs, true, toMs, false).values()) out.addAll(same);
        return out;
    }
    /** The machine-coding "list cinemas" call: theatres in a city showing a movie in the window, sorted by id. */
    SortedSet<String> cinemas(String city, String movie, long fromMs, long toMs) {
        SortedSet<String> out = new TreeSet<>();
        for (Listing l : search(city, movie, fromMs, toMs)) out.add(l.theatreId());
        return out;
    }
}

// ---- ext: a waitlist -- when a seat comes back, the head of the queue gets it held for them
/**
 * One queue per show and class. Whoever sees a seat come back calls offer: a listener on CANCELLED, or the
 * sweeper for a lapsed hold. The first person waiting gets that seat HELD in their name for the usual
 * window, so the offer is a real hold, not an email telling them to go and race for it.
 */
class Waitlist {
    private final Map<String, Deque<String>> queues = new ConcurrentHashMap<>();
    private static String key(Show s, SeatClass c) { return s.id + "/" + c; }
    /** Join the back of the queue for this show and class. */
    void join(Show show, SeatClass cls, String userId) {
        queues.computeIfAbsent(key(show, cls), k -> new ConcurrentLinkedDeque<>()).add(userId);
    }
    /** How many are waiting. */
    int size(Show show, SeatClass cls) { Deque<String> q = queues.get(key(show, cls)); return q == null ? 0 : q.size(); }
    /**
     * A seat became free: hold it for the head of the queue and hand back their booking, or null when
     * nobody is waiting or somebody else already took it.
     */
    Booking offer(BookingService svc, Show show, SeatClass cls, String seatId) {
        Deque<String> q = queues.get(key(show, cls));
        String user = q == null ? null : q.poll();
        if (user == null) return null;
        try { return svc.hold(show.id, user, List.of(seatId)); }
        catch (SeatUnavailable e) { q.addFirst(user); return null; }        // somebody was faster: keep their place
    }
}

// ---- ext: dynamic pricing and coupons -- new rules behind the same one-method interface
/** The price climbs as the class fills: full price when empty, up to 1.6x when sold out. Integer paise, rounded down. */
class DemandPricing implements PricingRule {
    private final PricingRule base;
    DemandPricing(PricingRule base) { this.base = base; }
    public long pricePaise(Show show, Seat seat) {
        int total = 0; for (Seat s : show.screen.seats) if (s.seatClass == seat.seatClass) total++;
        if (total == 0) return base.pricePaise(show, seat);
        long taken = total - show.freeCount(seat.seatClass);   // re-takes the show's lock: a ReentrantLock lets its holder back in
        return base.pricePaise(show, seat) * (100L * total + 60L * taken) / (100L * total);
    }
}
/** A coupon takes a percentage off whatever the rule under it decided. Another Decorator, same interface. */
class CouponPricing implements PricingRule {
    private final PricingRule base; private final int percentOff;
    CouponPricing(PricingRule base, int percentOff) {
        if (percentOff < 0 || percentOff > 100) throw new IllegalArgumentException("a coupon is 0 to 100 per cent off, not " + percentOff);
        this.base = base; this.percentOff = percentOff;
    }
    public long pricePaise(Show show, Seat seat) { return base.pricePaise(show, seat) * (100 - percentOff) / 100; }
}

// ---- ext: persistence -- the seat claim becomes a conditional UPDATE, the database's compare-and-set
/**
 * The tables are the classes: movie, theatre, screen, seat, show, booking, booking_seat, and show_seat with
 * one row per seat per show, the only table the race touches:
 *   show_seat(show_id, seat_id, status, hold_booking, hold_expires)   primary key (show_id, seat_id)
 * A hold is a status and an expiry time on that row (its TTL), never a database lock held across payment.
 * A group claim is ONE transaction. Optimistic: one conditional UPDATE, and the row count decides:
 *   UPDATE show_seat SET status='HELD', hold_booking=?, hold_expires=?
 *    WHERE show_id=? AND seat_id IN (?,?,?)
 *      AND (status='AVAILABLE' OR (status='HELD' AND hold_expires <= ?))
 *   -- 3 rows changed: COMMIT.  Fewer: ROLLBACK, somebody else won a seat.
 * Pessimistic, same result: SELECT ... WHERE show_id=? AND seat_id IN (...) FOR UPDATE; check; UPDATE; COMMIT.
 */
interface ShowSeatRepository {
    /** The group claim above: every seat HELD for this booking, or none of them. */
    boolean claimAll(String showId, List<String> seatIds, String bookingId, long expiresMs, long nowMs);
    /** UPDATE show_seat SET status='SOLD' WHERE show_id=? AND seat_id=? AND status='HELD' AND hold_booking=? AND hold_expires > ? */
    boolean sell(String showId, String seatId, String bookingId, long nowMs);
    String status(String showId, String seatId);
}
/**
 * A stand-in for the database: one row per show and seat, and every write is a compare-and-set on the row.
 * A refused row is "zero rows updated": somebody else got there first, exactly the answer the lock gave.
 * The group claim takes rows in seat-id order and puts back the ones it took if any row refuses: the ROLLBACK.
 */
class ConditionalRowStore implements ShowSeatRepository {
    /** One row: the three columns that decide the race. */
    record Row(String status, String bookingId, long expiresMs) {}
    private final ConcurrentHashMap<String, Row> rows = new ConcurrentHashMap<>();
    private static String k(String showId, String seatId) { return showId + "#" + seatId; }
    void put(String showId, String seatId) { rows.put(k(showId, seatId), new Row("AVAILABLE", null, 0)); }
    public boolean claimAll(String showId, List<String> seatIds, String bookingId, long expiresMs, long nowMs) {
        Row mine = new Row("HELD", bookingId, expiresMs);
        Map<String, Row> taken = new LinkedHashMap<>();                          // key -> the row as it was
        for (String seatId : new TreeSet<>(seatIds)) {                           // one fixed order for every caller
            String key = k(showId, seatId);
            Row cur = rows.get(key);
            boolean claimable = cur != null && (cur.status().equals("AVAILABLE")
                || (cur.status().equals("HELD") && cur.expiresMs() <= nowMs));   // the WHERE clause, for one row
            if (claimable && rows.replace(key, cur, mine)) { taken.put(key, cur); continue; }
            taken.forEach((kk, was) -> rows.replace(kk, mine, was));             // ROLLBACK: nothing stays HELD
            return false;
        }
        return true;                                                             // COMMIT
    }
    public boolean sell(String showId, String seatId, String bookingId, long nowMs) {
        String key = k(showId, seatId);
        Row cur = rows.get(key);
        if (cur == null || !cur.status().equals("HELD")
            || !bookingId.equals(cur.bookingId()) || cur.expiresMs() <= nowMs) return false;
        return rows.replace(key, cur, new Row("SOLD", bookingId, 0));
    }
    public String status(String showId, String seatId) { Row r = rows.get(k(showId, seatId)); return r == null ? null : r.status(); }
}

// ---- ext: the payment webhook -- the gateway reports one payment three times; the seats are sold once
/**
 * A webhook (the gateway calling our server back to report a payment) can arrive more than once, and after
 * the app's own confirm. It charges nothing: it commits with the reference it was told. A repeat finds the
 * booking CONFIRMED with that same reference and does nothing; a payment we cannot use goes back, once.
 */
class PaymentWebhook {
    private final BookingService svc;
    final AtomicInteger commits = new AtomicInteger();
    PaymentWebhook(BookingService svc) { this.svc = svc; }
    /** One callback, "this payment succeeded for this booking". Safe to receive any number of times. */
    Booking onPaymentCaptured(String bookingId, String paymentRef, PaymentProcessor pay) {
        Booking b = svc.find(bookingId);
        try {
            if (b.show.commit(b, paymentRef)) { commits.incrementAndGet(); return b; }   // the first report sells the seats
            if (paymentRef.equals(b.paymentRef)) return b;                              // the same payment again: nothing to do
        } catch (HoldLapsed e) { /* the hold died before the gateway called back */ }
        pay.refund(paymentRef, b.amountPaise);                                          // a second payment, or a dead hold
        return null;
    }
}

// ---- ext: a gateway that times out -- the third outcome, and the reconciliation that closes it
/**
 * The gateway neither approved nor declined: the call timed out. The money may have moved and may not
 * have. Until somebody finds out which, nothing may be confirmed and nothing may be released.
 */
class PaymentUnknown extends RuntimeException { PaymentUnknown(String m) { super(m); } }

/** Asks the gateway what happened under one idempotency key: the reference if it charged, null if it never did. */
interface PaymentQuery { String refFor(String idempotencyKey); }

/**
 * Confirm that survives a timeout. The gateway was given the booking id as the idempotency key, so a
 * timeout leaves a booking still PENDING, its seats still HELD, and a key to ask about. If the user presses
 * Pay again, confirm simply runs again: the same key is never charged twice. If the user has gone, settle()
 * asks the gateway, then finishes the booking with the reference it already has, or gives the money back.
 */
class ReconcilingConfirm {
    private final BookingService svc;
    private final PaymentQuery query;
    ReconcilingConfirm(BookingService svc, PaymentQuery query) { this.svc = svc; this.query = query; }
    /** Try to confirm. A timeout is not a failure: it returns null and changes nothing at all. */
    Booking confirm(String bookingId, PaymentProcessor pay) {
        try { return svc.confirm(bookingId, pay); }
        catch (PaymentUnknown e) { return null; }                // seats still HELD, booking still PENDING
    }
    /** Minutes later, with nobody pressing Pay: ask the gateway by key, then finish the job or hand the money back. */
    Booking settle(String bookingId, PaymentProcessor pay) {
        Booking b = svc.find(bookingId);
        if (b.status == BookingStatus.CONFIRMED) return b;       // a retry already finished it
        String ref = query.refFor(b.id);                         // the key the gateway was given: the booking id
        if (ref == null) return null;                            // it never charged: let the hold lapse by itself
        try { if (b.show.commit(b, ref) || ref.equals(b.paymentRef)) return b; }   // commit with THAT ref: no second charge
        catch (HoldLapsed e) { /* the hold died while the outcome was unknown */ }
        pay.refund(ref, b.amountPaise);                          // money moved, the seat did not: give it back
        return null;
    }
}

// ---- ext: a refund policy -- how much money comes back depends on how close the show is
/** How much of a cancelled booking is returned, in paise. Another rule that changes, so another interface. */
interface RefundPolicy { long refundPaise(Booking b, long nowMs); }

/** The usual cinema rule: everything back until two hours before, half until twenty minutes, nothing after. */
class TieredRefund implements RefundPolicy {
    public long refundPaise(Booking b, long nowMs) {
        long minutesToShow = (b.show.startMs - nowMs) / 60_000L;
        if (minutesToShow >= 120) return b.amountPaise;
        if (minutesToShow >= 20) return b.amountPaise / 2;       // integer paise: half of 25,000 is 12,500 exactly
        return 0;                                                // the seat still comes back; the money does not
    }
}

/**
 * Cancel with a policy. The seat returns to the market whatever the money does: the amount is decided from
 * frozen fields before anything moves, the seats come back under the show's lock, the refund is sent after.
 */
class CancelWithRefund {
    private final BookingService svc;
    private final RefundPolicy policy;
    private final Clock clock;
    CancelWithRefund(BookingService svc, RefundPolicy policy, Clock clock) { this.svc = svc; this.policy = policy; this.clock = clock; }
    /** Cancel, and return the paise actually sent back. */
    long cancel(String bookingId, PaymentProcessor pay) {
        Booking b = svc.find(bookingId);
        long back = policy.refundPaise(b, clock.nowMs());        // decided before the seats move
        b.show.cancel(b);                                        // under the lock: on sale again immediately
        if (back > 0) pay.refund(b.paymentRef, back);            // outside the lock: a slow refund holds no seat
        return back;
    }
}

// ---- ext: a cap per user -- one script must not hold the whole house
/**
 * At most N seats per user per show, counting only what they hold or bought RIGHT NOW: a lapsed hold, a
 * release and a cancel give the quota back by themselves. One user's requests queue on a small per-user
 * lock, so two threads of one script can never both see "one seat left". The order is always the user's
 * lock, then the show's lock inside svc.hold, so the two can never deadlock.
 */
class SeatCap {
    private final int maxPerUser;
    private final Clock clock;
    private final ConcurrentHashMap<String, List<Booking>> byUser = new ConcurrentHashMap<>();   // "show/user" -> bookings
    SeatCap(int maxPerUser, Clock clock) { this.maxPerUser = maxPerUser; this.clock = clock; }
    /** Hold through the cap. Throws SeatUnavailable when this user is already at their limit for this show. */
    Booking hold(BookingService svc, String showId, String userId, List<String> seatIds) {
        List<Booking> mine = byUser.computeIfAbsent(showId + "/" + userId, k -> new ArrayList<>());
        synchronized (mine) {                                     // count and hold are one step for this user
            if (live(mine) + seatIds.size() > maxPerUser)
                throw new SeatUnavailable(userId + " is at the limit of " + maxPerUser + " seats for " + showId);
            Booking b = svc.hold(showId, userId, seatIds);
            mine.add(b);
            return b;
        }
    }
    /** How many seats this user holds or bought right now, for the message the app shows them. */
    int used(String showId, String userId) {
        List<Booking> mine = byUser.get(showId + "/" + userId);
        if (mine == null) return 0;
        synchronized (mine) { return live(mine); }
    }
    private int live(List<Booking> mine) {
        long now = clock.nowMs(); int n = 0;
        for (Booking b : mine)
            if (b.status == BookingStatus.CONFIRMED || (b.status == BookingStatus.PENDING && b.holdExpiresMs > now)) n += b.seats.size();
        return n;
    }
}

// ---- ext: per-seat compare-and-set instead of the show lock -- more concurrency, real rollback
/** One seat claimed without any lock: the holder is swapped from null to a booking id in one hardware step. */
class CasSeat {
    final String id;
    private final AtomicReference<String> holder = new AtomicReference<>();
    CasSeat(String id) { this.id = id; }
    boolean tryHold(String bookingId) { return holder.compareAndSet(null, bookingId); }   // exactly one caller wins
    void release(String bookingId) { holder.compareAndSet(bookingId, null); }             // never drop somebody else's hold
    String holder() { return holder.get(); }
}
/**
 * The lock-free version of a group hold: take the seats one at a time, in seat-id order, and on the first
 * refusal give back everything already taken. The fixed order means two groups asking for the same seats
 * cannot each take one and both give up. More concurrency than one lock; the rollback is the price.
 */
class CasShow {
    private final Map<String, CasSeat> seats = new LinkedHashMap<>();
    void add(CasSeat s) { seats.put(s.id, s); }
    List<CasSeat> hold(List<String> ids, String bookingId) {
        List<CasSeat> got = new ArrayList<>();
        for (String id : new TreeSet<>(ids)) {                                  // one fixed order for every caller
            CasSeat s = seats.get(id);
            if (s != null && s.tryHold(bookingId)) { got.add(s); continue; }
            for (CasSeat back : got) back.release(bookingId);                 // all-or-nothing, by hand
            return List.of();
        }
        return got;
    }
}
// Once there are four app servers, no JVM lock and no AtomicReference helps: the hold must live outside the
// process. SET seatKey bookingId NX PX 300000 is this same compare-and-set, and releasing it is a
// compare-and-delete so one server can never drop another server's hold. A group needs all its keys in one
// step: one Lua script (a small program Redis runs without interruption) checks every key, then sets them all.

/** Runs every extension once so the reference code on page 05 is code that actually executed. */
class ExtDemo {
    static Screen smallScreen() {
        List<Seat> seats = new ArrayList<>();
        for (int i = 1; i <= 4; i++) seats.add(new Seat("A", i, SeatClass.SILVER));
        for (int i = 1; i <= 4; i++) seats.add(new Seat("B", i, SeatClass.GOLD));
        return new Screen("EXT-1", seats);
    }
    public static void main(String[] args) throws Exception {
        long[] now = { Instant.parse("2026-09-15T12:00:00Z").toEpochMilli() };
        Clock clock = () -> now[0];
        long hold = 60_000L;
        Screen sc = smallScreen();
        Theatre forum = new Theatre("FORUM", "Bengaluru", List.of(sc));
        Show six  = new Show("X-6PM", "Dune", sc, Instant.parse("2026-09-15T18:00:00Z").toEpochMilli(), clock, hold);
        Show nine = new Show("X-9PM", "Dune", sc, Instant.parse("2026-09-15T21:00:00Z").toEpochMilli(), clock, hold);
        BookingService svc = new BookingService();
        svc.addShow(six); svc.addShow(nine);

        // search across shows: an index hop and a range read, no lock taken
        ShowIndex index = new ShowIndex(); index.add(forum, six); index.add(forum, nine);
        long dayStart = Instant.parse("2026-09-15T00:00:00Z").toEpochMilli();
        System.out.println("search Bengaluru/Dune today: " + index.search("Bengaluru", "Dune", dayStart, dayStart + 86_400_000L).size()
            + " shows, cinemas " + index.cinemas("Bengaluru", "Dune", dayStart, dayStart + 86_400_000L));

        // sweeper: a lapsed hold is already free, the sweep only tidies the count
        Booking abandoned = svc.hold("X-6PM", "ghost", List.of("A1"));
        now[0] += hold + 1;
        HoldSweeper sweeper = new HoldSweeper(List.of(six, nine));
        System.out.println("before the sweep A1 shows as " + six.statusOf("A1") + "; the sweep reclaimed " + sweeper.sweepOnce() + " hold, booking is " + abandoned.status);

        // dynamic pricing and a coupon stack on the flat rule
        PricingRule demand = new CouponPricing(new DemandPricing(new ClassPricing()), 10);
        System.out.println("gold, empty show, 10% coupon = " + demand.pricePaise(six, sc.seats.get(4)) + " paise");
        svc.hold("X-6PM", "a", List.of("B1", "B2"));
        System.out.println("gold, half the class held, same coupon = " + demand.pricePaise(six, sc.seats.get(6)) + " paise");

        // a waitlist hands a returned seat to whoever was first
        Waitlist wl = new Waitlist();
        wl.join(nine, SeatClass.GOLD, "priya");
        Booking offered = wl.offer(svc, nine, SeatClass.GOLD, "B4");
        System.out.println("waitlist: " + (offered == null ? "nobody waiting" : offered.userId + " now holds " + offered.seatIds()) + "; queue left = " + wl.size(nine, SeatClass.GOLD));

        // the database's compare-and-set: fifty threads, one row, one winner; a group is all or nothing
        ConditionalRowStore db = new ConditionalRowStore(); db.put("X-6PM", "A9"); db.put("X-6PM", "A8");
        ExecutorService pool = Executors.newFixedThreadPool(50);
        CountDownLatch go = new CountDownLatch(1); AtomicInteger wins = new AtomicInteger();
        for (int i = 0; i < 50; i++) { String bk = "BK-" + i; pool.submit(() -> { go.await(); if (db.claimAll("X-6PM", List.of("A9"), bk, now[0] + hold, now[0])) wins.incrementAndGet(); return null; }); }
        go.countDown(); pool.shutdown(); pool.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("conditional UPDATE race: 50 claims on one row, winners = " + wins.get() + ", row = " + db.status("X-6PM", "A9"));
        if (wins.get() != 1) throw new AssertionError("two rows claimed");
        System.out.println("group A8+A9 when A9 is taken: " + db.claimAll("X-6PM", List.of("A8", "A9"), "BK-g", now[0] + hold, now[0]) + ", A8 = " + db.status("X-6PM", "A8"));

        // the webhook: the gateway reports one payment three times, the seat is sold once
        Booking b = svc.hold("X-9PM", "asha", List.of("A2"));
        PaymentProcessor upi = new UpiPayment();
        String ref = upi.charge(b.id, b.amountPaise);                              // the user paid on the gateway's page
        PaymentWebhook hook = new PaymentWebhook(svc);
        for (int i = 0; i < 3; i++) hook.onPaymentCaptured(b.id, ref, upi);
        System.out.println("three webhook calls: commits = " + hook.commits.get() + ", booking " + b.id + " is " + b.status);

        // a gateway that times out: nothing confirmed, nothing released, then reconciled from the gateway by key
        Booking t = svc.hold("X-9PM", "nikhil", List.of("A3"));
        Map<String, String> gatewayBook = new ConcurrentHashMap<>();                // what the gateway really did, by key
        PaymentProcessor timingOut = new PaymentProcessor() {
            public String charge(String key, long paise) { gatewayBook.put(key, "REF-TIMEOUT"); throw new PaymentUnknown("read timeout after 30 s"); }
            public void refund(String ref, long paise) { }
        };
        ReconcilingConfirm rec = new ReconcilingConfirm(svc, gatewayBook::get);
        Booking afterTimeout = rec.confirm(t.id, timingOut);
        System.out.println("after the timeout: booking is " + t.status + ", seat A3 is " + nine.statusOf("A3") + ", returned " + afterTimeout);
        System.out.println("after settle: booking is " + (rec.settle(t.id, timingOut) == null ? "not confirmed" : t.status) + ", seat A3 is " + nine.statusOf("A3"));

        // a cancel an hour before the show: the seat comes back in full, the money by the policy
        Booking c = svc.hold("X-6PM", "divya", List.of("B3"));
        PaymentProcessor card = new CardPayment();
        svc.confirm(c.id, card);
        now[0] = six.startMs - 60 * 60_000L;                                   // one hour before the 6pm show
        CancelWithRefund desk = new CancelWithRefund(svc, new TieredRefund(), clock);
        System.out.println("cancel one hour before a " + c.amountPaise + " paise booking: " + desk.cancel(c.id, card)
            + " paise back, seat B3 is " + six.statusOf("B3"));

        // one script, one user, a cap of three: counted live, so a lapsed hold gives the quota back
        SeatCap cap = new SeatCap(3, clock);
        int got = 0;
        for (String sid : List.of("A1", "A2", "A4", "B1", "B2")) {
            try { cap.hold(svc, "X-9PM", "bot", List.of(sid)); got++; } catch (SeatUnavailable e) { /* at the limit */ }
        }
        System.out.println("a bot asking for five seats with a cap of three got " + got + " (quota used " + cap.used("X-9PM", "bot") + ")");
        now[0] += hold + 1;                                                     // its holds lapse
        System.out.println("after its holds lapse the quota used is " + cap.used("X-9PM", "bot"));

        // the lock-free alternative, with its rollback
        CasShow cas = new CasShow(); cas.add(new CasSeat("C1")); cas.add(new CasSeat("C2"));
        System.out.println("CAS hold of C1+C2: " + cas.hold(List.of("C1", "C2"), "BK-a").size() + " seats");
        System.out.println("a second group asking for C2+C1 gets: " + cas.hold(List.of("C2", "C1"), "BK-b").size() + " seats (it tried C1 first and took nothing)");
    }
}
