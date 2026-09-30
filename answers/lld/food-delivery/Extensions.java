import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: eta -- how long until it arrives, from the state the order already has
/**
 * "Where is my order?" answered as a number of minutes: what the kitchen still owes, plus the ride. It reads
 * the order's own timestamps and an injected clock, so it is a pure function of state and testable to the minute.
 */
final class Eta {
    private final Clock clock;
    private final double kmPerHour;

    Eta(Clock clock, double kmPerHour) { this.clock = clock; this.kmPerHour = kmPerHour; }

    /** Minutes from now until this order lands. rider may be null (nobody assigned yet). */
    long minutesFor(Order o, Restaurant r, DeliveryPartner rider) {
        // the kitchen's clock starts when the kitchen starts, not when the customer paid: until then the
        // whole prep time is still owed. That is what the PREPARING stamp on the order is for.
        long startedAt = o.stamps().getOrDefault(OrderState.PREPARING, clock.nowMs());
        long cooked = Math.max(0, (clock.nowMs() - startedAt) / 60_000);
        long kitchen = switch (o.state()) {
            case PLACED, ACCEPTED, PREPARING -> Math.max(0, r.prepMinutes() - cooked);
            default -> 0;                                   // READY or later: the food exists
        };
        double km = o.state() == OrderState.PICKED_UP && rider != null
                  ? rider.at().kmTo(o.dropAt())                              // already on the way
                  : (rider == null ? 0 : rider.at().kmTo(r.at())) + r.at().kmTo(o.dropAt());
        return kitchen + Math.round(km / kmPerHour * 60);
    }
}

// ---- ext: multi-restaurant basket -- one tap, two kitchens, and the honest answer about the payment
/**
 * One basket spanning two restaurants fans out into one order per restaurant, because stock, prep and the
 * rider all belong to a restaurant. There is no distributed transaction here: if the second order fails, the
 * first is cancelled, which refunds it. That compensation IS the answer -- say it rather than hiding it.
 */
final class MultiRestaurantBasket {
    private final Map<String, Map<String, Integer>> byRestaurant = new LinkedHashMap<>();

    /** Add an item, tagged with the restaurant it came from. */
    void add(String restaurantId, String itemId, int qty) {
        byRestaurant.computeIfAbsent(restaurantId, k -> new LinkedHashMap<>()).merge(itemId, qty, Integer::sum);
    }

    /** Place one order per restaurant. Each key is derived from the tap, so a retry of the tap is still safe. */
    List<Order> checkout(OrderService svc, String customerId, Geo dropAt, String tapKey, List<String> coupons) {
        List<Order> placed = new ArrayList<>();
        try {
            for (Map.Entry<String, Map<String, Integer>> e : byRestaurant.entrySet()) {
                Cart leg = new Cart(customerId, e.getKey(), dropAt);          // one cart per kitchen
                e.getValue().forEach(leg::add);
                placed.add(svc.placeOrder(tapKey + "#" + e.getKey(), leg, coupons));
            }
            return placed;
        } catch (RuntimeException fail) {
            for (Order done : placed) svc.cancel(done.id());      // compensate; each order refunds itself
            throw fail;
        }
    }
}

// ---- ext: scheduled orders -- a booking released at "serve at" minus the prep time and the ride
/**
 * A pre-order is not a new state: it is a booking that becomes an ordinary order later. The scheduler releases
 * it when the kitchen must start (serve time, minus the prep time, minus the ride), and the id it uses is
 * derived from the booking, so a tick that runs twice places it exactly once.
 */
final class Scheduler {
    /** What the customer booked and when they want to eat. */
    record Booking(String id, String customerId, String restaurantId, Geo dropAt,
                   Map<String, Integer> items, long serveAtMs) {}

    private final List<Booking> pending = new ArrayList<>();
    private final List<String> failed = new ArrayList<>();
    private final double kmPerHour;

    Scheduler(double kmPerHour) { this.kmPerHour = kmPerHour; }

    synchronized void book(Booking b) { pending.add(b); }

    /** Place every booking whose kitchen must start by now. Safe to call as often as you like. */
    synchronized List<Order> tick(OrderService svc, long nowMs) {
        List<Order> released = new ArrayList<>();
        for (Iterator<Booking> it = pending.iterator(); it.hasNext(); ) {
            Booking b = it.next();
            Restaurant r = svc.restaurant(b.restaurantId());
            long rideMs = Math.round(r.at().kmTo(b.dropAt()) / kmPerHour * 3_600_000);
            long startBy = b.serveAtMs() - r.prepMinutes() * 60_000L - rideMs;
            if (nowMs < startBy) continue;
            Cart cart = new Cart(b.customerId(), b.restaurantId(), b.dropAt());   // its own cart, not hers
            b.items().forEach(cart::add);
            try { released.add(svc.placeOrder("booking:" + b.id(), cart, List.of())); }
            catch (RuntimeException e) { failed.add(b.id() + ": " + e.getMessage()); }   // one bad booking
            it.remove();                                                            // never blocks the rest
        }
        return released;
    }

    /** Bookings that could not be placed (sold out, card declined), for the customer to be told. */
    synchronized List<String> failed() { return List.copyOf(failed); }
}

// ---- ext: pooling -- one rider, two drops: the boolean flip becomes a permit
/**
 * Batching changes exactly one thing: a rider's free/busy flag was a single boolean, so a compare-and-set
 * fitted; with capacity it becomes a counter, so the same "one indivisible claim" is a Semaphore permit.
 * Everything else -- the ranking, the queue, the terminal release -- is untouched.
 */
final class PooledPartner {
    private final String id;
    private final Semaphore seats;
    private final Set<String> carrying = ConcurrentHashMap.newKeySet();

    PooledPartner(String id, int capacity) { this.id = id; this.seats = new Semaphore(capacity); }

    String id() { return id; }
    /** Take one seat for this order, or fail. The atomic step, same role as DeliveryPartner.claim(). */
    boolean claim(String orderId) {
        if (!seats.tryAcquire()) return false;
        carrying.add(orderId);
        return true;
    }
    /** Give the seat back when that drop is done. */
    void release(String orderId) {
        if (carrying.remove(orderId)) seats.release();
    }
    /** Seats still free. A ranking rule prefers a rider already going your way with a seat left. */
    int freeSeats() { return seats.availablePermits(); }
    /** The orders on this trip. */
    Set<String> carrying() { return Set.copyOf(carrying); }
}

// ---- ext: the rider says no -- an offer with a deadline, and a ranking that remembers
/**
 * Push assignment lies a little: a reserved rider can still refuse or go silent. An offer holds him, asks, and
 * hands him straight back on a no or a timeout, then the search continues with the next candidate. The refusal
 * is recorded, and the ranking rule below pushes a flaky rider down the list instead of banning him.
 */
final class OfferDesk {
    /** How a rider answers an offer. In production this is a push notification and a reply with a deadline. */
    interface Rider { boolean accepts(String orderId, long deadlineMs); }

    private final Map<String, Integer> misses = new ConcurrentHashMap<>();

    /**
     * True if he took it. A yes attaches him with the order's own guarded claim, so an order cancelled or
     * dispatched while he was deciding does not keep him. Otherwise he is released before this returns.
     */
    boolean offer(DeliveryPartner p, Order o, Rider rider, long deadlineMs) {
        if (!p.claim(o.id())) return false;                     // somebody else got him first
        boolean yes;
        try { yes = rider.accepts(o.id(), deadlineMs); }
        catch (RuntimeException e) { yes = false; }             // silence counts as a refusal
        if (yes && o.takePartner(p.id())) return true;          // the same second claim the dispatcher uses
        p.release();
        if (!yes) misses.merge(p.id(), 1, Integer::sum);
        return false;
    }

    /** How many offers this rider has turned down. */
    int missesOf(String partnerId) { return misses.getOrDefault(partnerId, 0); }

    /** Nearest first, but each refusal costs a rider half a kilometre of rank. A new class; nothing else moves. */
    AssignmentRule ranking(double penaltyKmPerMiss) {
        return (free, pickup) -> {
            List<DeliveryPartner> sorted = new ArrayList<>(free);
            sorted.sort(Comparator.comparingDouble(
                p -> p.at().kmTo(pickup) + penaltyKmPerMiss * missesOf(p.id())));
            List<String> ids = new ArrayList<>();
            for (DeliveryPartner p : sorted) ids.add(p.id());
            return ids;
        };
    }
}

// ---- ext: a new pricing rule -- membership, which waives the fee and the surge
/**
 * The whole point of the pricing chain: a new commercial rule is a new class and one line in the list. It must
 * sit after the fee rules, because it discounts what they added.
 */
final class MembershipWaiver implements PricingRule {
    private final Set<String> members;
    MembershipWaiver(Set<String> members) { this.members = members; }
    public Bill apply(Bill running, PriceCtx ctx) {
        if (!members.contains(ctx.customerId())) return running;
        return running.addDiscount(running.delivery() + running.surge());
    }
}

// ---- ext: ratings and search -- Flipkart's FoodKart: who delivers to my pincode, best rated or cheapest first
/**
 * Restaurants are onboarded with the pincodes they deliver to. A customer rates a DELIVERED order from 1 to 5,
 * once, and a restaurant's rating is a running average kept as a sum and a count, so reading it is O(1).
 * "What can I order here?" lists the restaurants for that pincode that still have the dish, in the order asked.
 */
final class Catalog {
    /** One line of the answer: the restaurant, the dish at today's price, and the rating in tenths. */
    record Listing(String restaurantId, String restaurant, MenuItem dish, int ratingTenths) {}

    /** The sort orders are rules handed in, like pricing: add one without touching find(). */
    static final Comparator<Listing> BEST_RATED = Comparator.comparingInt(Listing::ratingTenths).reversed();
    static final Comparator<Listing> CHEAPEST = Comparator.comparingLong(l -> l.dish().pricePaise());

    private final Map<String, Set<Restaurant>> byPincode = new ConcurrentHashMap<>();
    private final Map<String, long[]> stars = new ConcurrentHashMap<>();       // restaurant id -> {sum, count}
    private final Set<String> rated = ConcurrentHashMap.newKeySet();          // order ids already rated

    /** List a restaurant under every pincode it delivers to. Calling it again moves its area. */
    void onboard(Restaurant r, Set<String> pincodes) {
        for (Set<Restaurant> listed : byPincode.values()) listed.remove(r);
        for (String pin : pincodes) byPincode.computeIfAbsent(pin, k -> ConcurrentHashMap.newKeySet()).add(r);
    }

    /** Rate a delivered order, 1 to 5, once. The comment is stored beside it; the average needs only stars. */
    void rate(Order o, int stars, String comment) {
        if (o.state() != OrderState.DELIVERED) throw new IllegalStateException("only a delivered order can be rated");
        if (stars < 1 || stars > 5) throw new IllegalArgumentException("stars go from 1 to 5");
        if (!rated.add(o.id())) throw new IllegalStateException(o.id() + " is already rated");
        this.stars.merge(o.restaurantId(), new long[] { stars, 1 }, (a, b) -> new long[] { a[0] + b[0], a[1] + b[1] });
    }

    /** The average in tenths of a star, rounded: 43 means 4.3. Integer maths, so no 4.2999. 0 = not rated yet. */
    int ratingTenths(String restaurantId) {
        long[] s = stars.get(restaurantId);
        return s == null ? 0 : (int) ((s[0] * 10 + s[1] / 2) / s[1]);
    }

    /** Who delivers to this pincode and has this dish in stock right now, sorted. O(k log k) for k restaurants. */
    List<Listing> find(String pincode, String itemId, Comparator<Listing> order) {
        List<Listing> out = new ArrayList<>();
        for (Restaurant r : byPincode.getOrDefault(pincode, Set.of())) {
            if (r.stockOf(itemId) <= 0) continue;                  // it must deliver here AND have the dish
            for (MenuItem m : r.menu())
                if (m.id().equals(itemId)) out.add(new Listing(r.id(), r.name(), m, ratingTenths(r.id())));
        }
        out.sort(order);
        return out;
    }
}

// ---- ext: the system picks the kitchen -- Intuit's round: cheapest (or best rated) that has it all, never over capacity
/**
 * The customer names dishes, not a restaurant. Rank a snapshot of the kitchens that have every dish (the
 * strategy is a Comparator: cheapest basket, or best rated), then try them in that order. A kitchen may cook
 * only so many items at once: a Semaphore of that many permits per kitchen, taken before the order is placed
 * and given back when the food leaves (PICKED_UP) or the order dies. The ranking guesses; the permit decides.
 */
final class KitchenPicker implements OrderObserver {
    private final Map<String, Semaphore> permits = new ConcurrentHashMap<>();
    private final Map<String, Integer> cooking = new ConcurrentHashMap<>();   // order id -> permits it holds

    /** How many items this kitchen can have cooking at once. */
    void capacity(String restaurantId, int items) { permits.put(restaurantId, new Semaphore(items)); }

    /** The default strategy: the cheapest basket first, at today's menu prices. */
    static Comparator<Restaurant> cheapest(Map<String, Integer> dishes) {
        return Comparator.comparingLong(r -> basketPaise(r, dishes));
    }
    /** The other strategy the round asks for: the best-rated kitchen first, from the catalog's running averages. */
    static Comparator<Restaurant> bestRated(Catalog catalog) {
        return Comparator.comparingInt((Restaurant r) -> catalog.ratingTenths(r.id())).reversed();
    }

    /** Place the order at the best kitchen that has room. Throws if every kitchen with all the dishes is full. */
    Order place(OrderService svc, String tapKey, String customerId, Geo dropAt, Map<String, Integer> dishes,
                List<Restaurant> kitchens, Comparator<Restaurant> strategy) {
        int items = 0;
        for (int q : dishes.values()) items += q;
        List<Restaurant> ranked = new ArrayList<>();
        for (Restaurant r : kitchens) if (hasAll(r, dishes)) ranked.add(r);
        ranked.sort(strategy);
        for (Restaurant r : ranked) {
            Semaphore kitchen = permits.get(r.id());
            if (kitchen == null || !kitchen.tryAcquire(items)) continue;     // full right now: the next one
            Cart cart = new Cart(customerId, r.id(), dropAt);
            dishes.forEach(cart::add);
            try {
                Order o = svc.placeOrder(tapKey + "@" + r.id(), cart, List.of());
                cooking.put(o.id(), items);
                if (o.state() == OrderState.PICKED_UP || o.state().isTerminal()) giveBack(o);   // died already
                return o;
            } catch (RuntimeException e) {
                kitchen.release(items);                                        // nothing half-done
                if (hasAll(r, dishes)) throw e;           // it still has the food: the card failed, so stop here
            }                                             // it sold out in the gap: try the next kitchen
        }
        throw new IllegalStateException("every kitchen that has all of it is full right now");
    }

    /** The food left the kitchen, or the order died: its permits go back, exactly once. */
    public void onState(Order o, OrderState from) {
        if (o.state() == OrderState.PICKED_UP || o.state().isTerminal()) giveBack(o);
    }
    private void giveBack(Order o) {
        Integer n = cooking.remove(o.id());
        if (n != null) permits.get(o.restaurantId()).release(n);
    }

    private static boolean hasAll(Restaurant r, Map<String, Integer> dishes) {
        for (Map.Entry<String, Integer> d : dishes.entrySet()) if (r.stockOf(d.getKey()) < d.getValue()) return false;
        return basketPaise(r, dishes) < Long.MAX_VALUE;
    }
    private static long basketPaise(Restaurant r, Map<String, Integer> dishes) {
        long total = 0;
        for (Map.Entry<String, Integer> d : dishes.entrySet()) {
            MenuItem m = null;
            for (MenuItem x : r.menu()) if (x.id().equals(d.getKey())) m = x;
            if (m == null) return Long.MAX_VALUE;                              // not on this menu
            total += m.pricePaise() * d.getValue();
        }
        return total;
    }
}

// ---- ext: commands out of order -- Flipkart 2025: the input is shuffled; apply it in timestamp order
/**
 * The round's input is a list of timestamped commands that arrive shuffled. Each line becomes a Command object
 * with its time; a heap (PriorityQueue) hands them back oldest first, ties in arrival order, and the clock the
 * service reads is moved to each command's time before it runs, so the order's stamps follow the timeline.
 */
final class CommandReplay {
    /** One line of input: when it happened, what it says, and what to run. seq breaks ties in arrival order. */
    record Command(long atMs, long seq, String text, Runnable action) {}

    /** A clock the replay moves. Hand it to the service with setClock, so every stamp is the command's time. */
    static final class ManualClock implements Clock {
        private volatile long now;
        public long nowMs() { return now; }
        void set(long atMs) { now = atMs; }
    }

    private final PriorityQueue<Command> pending =
        new PriorityQueue<>(Comparator.comparingLong(Command::atMs).thenComparingLong(Command::seq));
    private final ManualClock clock = new ManualClock();
    private long arrived;

    Clock clock() { return clock; }

    /** Queue one command, in whatever order the input gives it. O(log n). */
    void submit(long atMs, String text, Runnable action) { pending.add(new Command(atMs, arrived++, text, action)); }

    /** Run everything oldest first. A command that fails is logged and the rest still run. */
    List<String> runAll() {
        List<String> log = new ArrayList<>();
        for (Command c; (c = pending.poll()) != null; ) {
            clock.set(c.atMs());
            try { c.action().run(); log.add(c.atMs() + " " + c.text() + ": ok"); }
            catch (RuntimeException e) { log.add(c.atMs() + " " + c.text() + ": " + e.getMessage()); }
        }
        return log;
    }
}

// ---- ext: unknown payment -- the charge that timed out, and the sweep that finds the money again
/**
 * The one outcome "pay, then commit" cannot rule out: the gateway takes the money and the answer never comes
 * back. Refusing to create the order is right -- but the customer has been charged and nothing points at his
 * money. The fix is a line of bookkeeping and a sweep: write the attempt down BEFORE the call, mark it
 * UNKNOWN when the call dies, and ask the gateway later what really happened.
 */
final class ChargeBook implements ChargeLog {
    /** One charge attempt, as the log knows it right now. */
    record Attempt(String chargeId, String customerId, long paise, ChargeOutcome outcome) {}

    private final Map<String, Attempt> byCharge = new ConcurrentHashMap<>();

    public void record(String chargeId, String customerId, long paise, ChargeOutcome outcome) {
        byCharge.put(chargeId, new Attempt(chargeId, customerId, paise, outcome));
    }
    /** The rows in one state: UNKNOWN charges and owed refunds are the only ones the reconciler looks at. */
    List<Attempt> having(ChargeOutcome outcome) {
        List<Attempt> out = new ArrayList<>();
        for (Attempt a : byCharge.values()) if (a.outcome() == outcome) out.add(a);
        return out;
    }
    /** What the log says about one charge, or null if it never heard of it. */
    ChargeOutcome outcomeOf(String chargeId) {
        Attempt a = byCharge.get(chargeId);
        return a == null ? null : a.outcome();
    }
}

/** What the gateway tells us, minutes later, when we ask what really happened to a charge. */
interface Settlement {
    /** True if the money really did leave the customer. */
    boolean wasCharged(String chargeId);
}

/**
 * The sweep. An UNKNOWN charge can never belong to an order -- the order is only built after a charge that
 * answered -- so if the money moved, it is an orphan and goes back. A refund still owed (the gateway failed
 * when the order was cancelled) is sent again. Writing the answer into the log is what makes the sweep
 * idempotent: run it twice and the customer is refunded once.
 */
final class Reconciler {
    private final ChargeBook book;
    private final Settlement settlement;
    private final PaymentProcessor payments;

    Reconciler(ChargeBook book, Settlement settlement, PaymentProcessor payments) {
        this.book = book; this.settlement = settlement; this.payments = payments;
    }
    /** Refund every orphan charge and every owed refund. Returns how many went out on this pass. Run on a timer. */
    int sweep() {
        int refunded = 0;
        for (ChargeBook.Attempt a : book.having(ChargeOutcome.UNKNOWN)) {
            if (settlement.wasCharged(a.chargeId())) {
                payments.refund(a.chargeId(), a.paise());
                book.record(a.chargeId(), a.customerId(), a.paise(), ChargeOutcome.REFUNDED);
                refunded++;
            } else {
                book.record(a.chargeId(), a.customerId(), a.paise(), ChargeOutcome.DECLINED);
            }
        }
        for (ChargeBook.Attempt a : book.having(ChargeOutcome.REFUND_OWED)) {
            try { payments.refund(a.chargeId(), a.paise()); }
            catch (RuntimeException stillDown) { continue; }             // still owed: the next pass tries again
            book.record(a.chargeId(), a.customerId(), a.paise(), ChargeOutcome.REFUNDED);
            refunded++;
        }
        return refunded;
    }
}

// ---- ext: a gateway that dies -- the stand-in that makes the unknown outcome testable
/** A gateway that captures the money and then dies before it can answer: the case UNKNOWN exists for. */
final class TimeoutGateway implements PaymentProcessor {
    private final Set<String> captured = ConcurrentHashMap.newKeySet();
    private final AtomicInteger refunds = new AtomicInteger();
    private volatile boolean dying = true;

    /** Stop timing out and behave like an ordinary gateway again. */
    void recover() { dying = false; }
    public boolean charge(String chargeId, long paise) {
        captured.add(chargeId);                                  // the money HAS moved...
        if (dying) throw new RuntimeException("gateway timed out after capturing " + chargeId);
        return true;                                             // ...and this time we got to say so
    }
    public void refund(String chargeId, long paise) { captured.remove(chargeId); refunds.incrementAndGet(); }
    /** The view a reconciler asks, minutes later. */
    Settlement settlement() { return captured::contains; }
    /** How many refunds it has issued, so a test can prove one orphan is refunded exactly once. */
    int refundCount() { return refunds.get(); }
}

// ---- ext: live tracking -- high-frequency GPS, deliberately off the state path
/**
 * The rider's position arrives a few times a second; an order changes state six times in an hour. Putting the
 * first through the state observers would drown them, so location gets its own topic per order. Nothing here
 * touches an order lock, which is why a slow map client cannot stall a transition.
 */
final class LocationStream {
    private final Map<String, List<Consumer<Geo>>> byOrder = new ConcurrentHashMap<>();

    /** The customer's map subscribes to one order. */
    void subscribe(String orderId, Consumer<Geo> sink) {
        byOrder.computeIfAbsent(orderId, k -> new CopyOnWriteArrayList<>()).add(sink);
    }
    /** The rider app pushes a fix. A broken subscriber is skipped, exactly as on the state path. */
    void push(String orderId, Geo where) {
        for (Consumer<Geo> sink : byOrder.getOrDefault(orderId, List.of())) {
            try { sink.accept(where); } catch (RuntimeException ignored) { }
        }
    }
    /** Drop the topic once the order is terminal, so a finished order costs no memory. */
    void close(String orderId) { byOrder.remove(orderId); }
}

// ---- ext: persistence -- the repository, the conditional UPDATE, and the outbox
/**
 * Beyond one process the order's lock cannot help, so the guarded transition becomes a conditional UPDATE and
 * the database performs the same atomic step:
 *
 *   INSERT INTO orders (id, key, state, total) VALUES (?, ?, 'PLACED', ?) ON CONFLICT (key) DO NOTHING;
 *   UPDATE orders SET state = ? WHERE id = ? AND state = ?;    -- 0 rows = somebody else moved it first
 *   INSERT INTO outbox (order_id, event) VALUES (?, ?);        -- same transaction as the UPDATE
 *
 * The outbox is why the notification is exactly-once-ish: the event is committed with the state change, and a
 * separate sender drains it, so a crash between the two is impossible.
 */
interface OrderRepository {
    /** Insert unless this idempotency key is already there. False means the retry found the first order. */
    boolean insertIfAbsent(String orderId, String idempotencyKey, OrderState state);
    /** The conditional UPDATE. False means the row was not in `expected` any more: somebody else won. */
    boolean compareAndSetState(String orderId, OrderState expected, OrderState next);
    /** Append an event in the same transaction as the state change. */
    void appendOutbox(String orderId, String event);
    /** Take everything the sender has not sent yet. */
    List<String> drainOutbox();
}

/** A map-backed stand-in, so the seam can be demonstrated without a database. */
final class InMemoryOrderRepository implements OrderRepository {
    private final Map<String, OrderState> states = new ConcurrentHashMap<>();
    private final Map<String, String> byKey = new ConcurrentHashMap<>();
    private final Queue<String> outbox = new ConcurrentLinkedQueue<>();

    public boolean insertIfAbsent(String orderId, String key, OrderState state) {
        if (byKey.putIfAbsent(key, orderId) != null) return false;
        states.put(orderId, state);
        return true;
    }
    public boolean compareAndSetState(String orderId, OrderState expected, OrderState next) {
        return states.replace(orderId, expected, next);
    }
    public void appendOutbox(String orderId, String event) { outbox.add(orderId + ":" + event); }
    public List<String> drainOutbox() {
        List<String> out = new ArrayList<>();
        for (String e = outbox.poll(); e != null; e = outbox.poll()) out.add(e);
        return out;
    }
    /** The stored state, for the demo. */
    OrderState stateOf(String orderId) { return states.get(orderId); }
}

/** Runs every extension once, so the follow-up code on page 05 is code that has actually executed. */
class ExtDemo {
    public static void main(String[] args) {
        long[] now = { 1_700_000_000_000L };
        Clock clock = () -> now[0];
        FakeGateway gateway = new FakeGateway();
        OrderService svc = new OrderService();
        svc.setClock(clock);
        svc.configure(List.of(new ItemTotal(),
                              new DistanceFee(Money.rupees("20.00"), Money.rupees("8.00")),
                              new SurgeFee(15_000),
                              new MembershipWaiver(Set.of("anita"))),
                      new NearestFree(), new StandardCancellation(Money.rupees("50.00")), gateway);
        svc.setDemand((r, t) -> true);

        Restaurant truffles = new Restaurant("r-kora", "Truffles", new Geo(12.9352, 77.6245), 18);
        truffles.put(new MenuItem("paneer", "Paneer Tikka", Money.rupees("249.00")), 50);
        Restaurant sweets = new Restaurant("r-sweet", "Adyar Ananda", new Geo(12.9360, 77.6250), 6);
        sweets.put(new MenuItem("jamun", "Gulab Jamun", Money.rupees("90.00")), 50);
        svc.register(truffles);
        svc.register(sweets);
        DeliveryPartner rider = new DeliveryPartner("p-1", new Geo(12.9355, 77.6250));
        svc.register(rider);
        Geo home = new Geo(12.9352, 77.6495);

        // a member pays no delivery fee and no surge: a new rule, one line in the list
        svc.openCart("anita", "r-kora", home);
        svc.addToCart("anita", "r-kora", "paneer", 1);
        Order member = svc.placeOrder("m-1", "anita", List.of());
        System.out.println("membership: " + member.bill());

        // eta, from the order's own state: 18 minutes of kitchen plus the ride, counting down as it cooks
        Eta eta = new Eta(clock, 22);
        System.out.println("eta just after placing:      " + eta.minutesFor(member, truffles, null) + " min");
        svc.accept(member.id());
        svc.startPreparing(member.id());
        now[0] += 10 * 60_000;                                          // ten minutes on the tawa
        System.out.println("eta ten minutes into cooking: " + eta.minutesFor(member, truffles, null) + " min");

        // live tracking: its own topic, off the state path
        LocationStream gps = new LocationStream();
        gps.subscribe(member.id(), where -> System.out.println("   [map] rider at " + where.lat() + "," + where.lng()));
        svc.markReady(member.id());
        gps.push(member.id(), rider.at());
        gps.close(member.id());

        // offers instead of push (the push rule ranks nobody): the rider says no, then yes
        svc.pickUp(member.id());
        svc.deliver(member.id());                                       // rider back in the pool
        OrderService offers = new OrderService();
        offers.configure(List.of(new ItemTotal()), (free, pickup) -> List.of(), new StandardCancellation(0), gateway);
        offers.register(truffles);
        DeliveryPartner ravi = new DeliveryPartner("p-2", new Geo(12.9355, 77.6250));
        offers.register(ravi);
        Order next = place(offers, "anita", "r-kora", home, "m-2");
        offers.accept(next.id()); offers.startPreparing(next.id()); offers.markReady(next.id());   // it waits
        OfferDesk desk = new OfferDesk();
        boolean no = desk.offer(ravi, next, (id, deadline) -> false, now[0] + 15_000);
        boolean yes = desk.offer(ravi, next, (id, deadline) -> true, now[0] + 15_000);
        System.out.println("offers: first took=" + no + " (misses " + desk.missesOf("p-2") + "), second took=" + yes
            + ", the order's rider is " + next.partnerId());

        // one tap, two restaurants
        MultiRestaurantBasket basket = new MultiRestaurantBasket();
        basket.add("r-kora", "paneer", 1);
        basket.add("r-sweet", "jamun", 2);
        List<Order> both = basket.checkout(svc, "bala", home, "tap-9", List.of());
        System.out.println("multi-restaurant: " + both.size() + " orders, totals "
            + Money.fmt(both.get(0).bill().total()) + " + " + Money.fmt(both.get(1).bill().total()));

        // a pre-order, released when the kitchen must start (18 min prep + a 7 min ride), and a tick that runs twice
        Scheduler sched = new Scheduler(22);
        long dinner = now[0] + 3 * 3600_000L;
        sched.book(new Scheduler.Booking("b-1", "carol", "r-kora", home, Map.of("paneer", 2), dinner));
        svc.openCart("carol", "r-sweet", home);                          // meanwhile she is browsing sweets
        svc.addToCart("carol", "r-sweet", "jamun", 1);
        now[0] = dinner - 26 * 60_000L;
        System.out.println("scheduled: released 26 min before = " + sched.tick(svc, now[0]).size());
        now[0] = dinner - 25 * 60_000L;
        List<Order> released = sched.tick(svc, now[0]);
        List<Order> twice = sched.tick(svc, now[0]);
        Order hers = svc.placeOrder("c-1", "carol", List.of());         // her own cart was not touched
        System.out.println("scheduled: released 25 min before = " + released.size() + ", a second tick = " + twice.size()
            + ", and her own cart still checks out at " + hers.restaurantId());

        // pooling: one rider, two drops
        PooledPartner pooled = new PooledPartner("pp-1", 2);
        System.out.println("pooling: claims " + pooled.claim("o-a") + " " + pooled.claim("o-b")
            + " " + pooled.claim("o-c") + " (third must be false), seats free " + pooled.freeSeats());
        pooled.release("o-a");
        System.out.println("pooling: after one drop, seats free " + pooled.freeSeats());

        // a gateway that took the money and never answered: no order, and the sweep finds the charge
        TimeoutGateway flaky = new TimeoutGateway();
        ChargeBook book = new ChargeBook();
        OrderService money = new OrderService();
        money.setChargeLog(book);
        money.configure(List.of(new ItemTotal()), new NearestFree(), new StandardCancellation(0), flaky);
        Restaurant dosas = new Restaurant("r-rec", "Rec Tiffins", new Geo(12.9300, 77.6200), 10);
        dosas.put(new MenuItem("dosa", "Masala Dosa", Money.rupees("120.00")), 5);
        money.register(dosas);
        money.openCart("dev", "r-rec", home);
        money.addToCart("dev", "r-rec", "dosa", 1);
        try { money.placeOrder("u-1", "dev", List.of()); }
        catch (RuntimeException e) { System.out.println("unknown outcome: " + e.getMessage()); }
        Reconciler sweep = new Reconciler(book, flaky.settlement(), flaky);
        System.out.println("reconciler: refunded " + sweep.sweep() + " orphan, a second sweep refunds "
            + sweep.sweep() + ", gateway refunds " + flaky.refundCount() + ", dosa stock " + dosas.stockOf("dosa"));

        // FoodKart: who delivers to my pincode, best rated or cheapest first
        Catalog catalog = new Catalog();
        Restaurant court1 = new Restaurant("fc-1", "Food Court-1", new Geo(12.9352, 77.6245), 15);
        court1.put(new MenuItem("thali", "NI Thali", Money.rupees("100.00")), 5);
        Restaurant court2 = new Restaurant("fc-2", "Food Court-2", new Geo(12.9360, 77.6250), 15);
        court2.put(new MenuItem("thali", "SI Thali", Money.rupees("120.00")), 3);
        svc.register(court1);
        svc.register(court2);
        catalog.onboard(court1, Set.of("560102", "560076"));
        catalog.onboard(court2, Set.of("560076"));
        catalog.rate(deliverOne(svc, "nitesh", "fc-1", "thali", "fk-1"), 3, "Good Food");
        catalog.rate(deliverOne(svc, "vatsal", "fc-2", "thali", "fk-2"), 5, "Nice Food");
        System.out.println("catalog 560076, best rated: " + names(catalog.find("560076", "thali", Catalog.BEST_RATED))
            + "  cheapest: " + names(catalog.find("560076", "thali", Catalog.CHEAPEST)));

        // Intuit: the system picks the kitchen, cheapest first, never over its capacity
        KitchenPicker picker = new KitchenPicker();
        svc.addObserver(picker);
        picker.capacity("fc-1", 2);                                     // two items cooking at once
        picker.capacity("fc-2", 4);
        Map<String, Integer> two = Map.of("thali", 2);
        List<Restaurant> kitchens = List.of(court1, court2);
        Order k1 = picker.place(svc, "ip-1", "hari", home, two, kitchens, KitchenPicker.cheapest(two));
        Order k2 = picker.place(svc, "ip-2", "sri", home, two, kitchens, KitchenPicker.cheapest(two));
        svc.cancel(k1.id());                                            // its permits go back
        Order k3 = picker.place(svc, "ip-3", "arun", home, two, kitchens, KitchenPicker.cheapest(two));
        System.out.println("picker: " + k1.restaurantId() + " (cheapest), then " + k2.restaurantId()
            + " (fc-1 is full), and after a cancel " + k3.restaurantId() + " again");

        // Flipkart 2025: commands arrive shuffled and run in timestamp order, with the clock moved to each one
        CommandReplay replay = new CommandReplay();
        svc.setClock(replay.clock());
        Order[] late = new Order[1];
        replay.submit(3_000, "start cooking", () -> svc.startPreparing(late[0].id()));
        replay.submit(1_000, "place", () -> late[0] = place(svc, "ravi", "r-kora", home, "cmd-1"));
        replay.submit(2_000, "accept", () -> svc.accept(late[0].id()));
        System.out.println("replay: " + replay.runAll() + " -> " + late[0].state() + ", stamps " + late[0].stamps());

        // persistence: the conditional UPDATE and the outbox
        OrderRepository repo = new InMemoryOrderRepository();
        System.out.println("repo insert " + repo.insertIfAbsent("o-1", "k-1", OrderState.PLACED)
            + ", the same key again " + repo.insertIfAbsent("o-2", "k-1", OrderState.PLACED));
        boolean first = repo.compareAndSetState("o-1", OrderState.PLACED, OrderState.ACCEPTED);
        boolean second = repo.compareAndSetState("o-1", OrderState.PLACED, OrderState.CANCELLED);
        repo.appendOutbox("o-1", "ACCEPTED");
        System.out.println("two servers move the same order: " + first + " / " + second
            + ", outbox " + repo.drainOutbox());
    }

    /** Helper: open a cart, add one paneer, place it. */
    private static Order place(OrderService svc, String who, String restaurantId, Geo drop, String key) {
        svc.openCart(who, restaurantId, drop);
        svc.addToCart(who, restaurantId, "paneer", 1);
        return svc.placeOrder(key, who, List.of());
    }

    /** Helper: order one dish and walk it all the way to DELIVERED; the rider comes from the pool. */
    private static Order deliverOne(OrderService svc, String who, String restaurantId, String item, String key) {
        svc.openCart(who, restaurantId, new Geo(12.9352, 77.6495));
        svc.addToCart(who, restaurantId, item, 1);
        Order o = svc.placeOrder(key, who, List.of());
        svc.accept(o.id()); svc.startPreparing(o.id()); svc.markReady(o.id()); svc.pickUp(o.id()); svc.deliver(o.id());
        return o;
    }

    /** Helper: "Food Court-2 5.0 120.00" for each listing. */
    private static List<String> names(List<Catalog.Listing> found) {
        List<String> out = new ArrayList<>();
        for (Catalog.Listing l : found)
            out.add(l.restaurant() + " " + (l.ratingTenths() / 10) + "." + (l.ratingTenths() % 10) + " " + Money.fmt(l.dish().pricePaise()));
        return out;
    }
}
