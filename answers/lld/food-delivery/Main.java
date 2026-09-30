import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * An order's life. The legal moves are DATA -- one table, right here -- and not if-chains scattered over the
 * service, which is what makes "you cannot cancel once the rider has it" a readable rule instead of a bug
 * somebody finds in production. A state with no successors is terminal.
 */
enum OrderState {
    PLACED, ACCEPTED, PREPARING, READY, PICKED_UP, DELIVERED, CANCELLED, REJECTED;

    private static final Map<OrderState, Set<OrderState>> NEXT = new EnumMap<>(OrderState.class);
    static {
        NEXT.put(PLACED,    EnumSet.of(ACCEPTED, REJECTED, CANCELLED));
        NEXT.put(ACCEPTED,  EnumSet.of(PREPARING, CANCELLED));
        NEXT.put(PREPARING, EnumSet.of(READY, CANCELLED));
        NEXT.put(READY,     EnumSet.of(PICKED_UP, CANCELLED));
        NEXT.put(PICKED_UP, EnumSet.of(DELIVERED));            // on the road: no going back
        NEXT.put(DELIVERED, EnumSet.noneOf(OrderState.class));
        NEXT.put(CANCELLED, EnumSet.noneOf(OrderState.class));
        NEXT.put(REJECTED,  EnumSet.noneOf(OrderState.class));
    }
    /** True if this order may legally move to target. Every mutation in the service asks this first. */
    boolean canGoTo(OrderState target) { return NEXT.get(this).contains(target); }
    /** True if nothing may follow this state: DELIVERED, CANCELLED, REJECTED. */
    boolean isTerminal() { return NEXT.get(this).isEmpty(); }
    /** The legal successors, for a diagram or an error message. */
    Set<OrderState> next() { return NEXT.get(this); }
}

/** A rider is free, carrying an order, or logged out. The AVAILABLE to ASSIGNED flip is the contended one. */
enum PartnerState { OFFLINE, AVAILABLE, ASSIGNED }

/** Exact money, in paise. There is no double anywhere near a rupee in this file; these two are the boundary. */
final class Money {
    /** Parse "249.00" into 24900 paise, exactly. Used at the edge (a form, a menu upload), never in the maths. */
    static long rupees(String amount) { return new java.math.BigDecimal(amount).movePointRight(2).longValueExact(); }
    /** Print 24900 paise as "249.00". Presentation only. */
    static String fmt(long paise) {
        String sign = paise < 0 ? "-" : ""; long a = Math.abs(paise);
        return sign + (a / 100) + "." + String.format("%02d", a % 100);
    }
}

/** A point on the map. Distance is the only place a double is allowed, and it never touches a price directly. */
record Geo(double lat, double lng) {
    /** Kilometres, flat-earth approximation -- good to a few metres over a city, and swappable for haversine. */
    double kmTo(Geo o) {
        double dy = (lat - o.lat) * 110.574;
        double dx = (lng - o.lng) * 111.320 * Math.cos(Math.toRadians((lat + o.lat) / 2));
        return Math.sqrt(dx * dx + dy * dy);
    }
}

/** One line on a restaurant's menu. Immutable: the price here is authoritative and is copied at checkout. */
record MenuItem(String id, String name, long pricePaise) {}

/** One line of a placed order: the name and the price as they were when the customer paid. */
record OrderLine(String itemId, String name, long unitPaise, int qty) {
    /** What this line costs: unit price times quantity, in paise. */
    long amountPaise() { return unitPaise * qty; }
}

/**
 * A priced basket. The four parts and the total are stored separately on purpose, so a pricing rule can get
 * them out of step -- and CheckedRule catches it before the card is charged.
 */
record Bill(long items, long delivery, long surge, long discount, long total) {
    static final Bill EMPTY = new Bill(0, 0, 0, 0, 0);
    /** Set the item subtotal (the first rule in the chain). */
    Bill withItems(long p)   { return new Bill(p, delivery, surge, discount, p + delivery + surge - discount); }
    /** Add a delivery fee. */
    Bill addDelivery(long p) { return new Bill(items, delivery + p, surge, discount, total + p); }
    /** Add a surge amount on top of the delivery fee. */
    Bill addSurge(long p)    { return new Bill(items, delivery, surge + p, discount, total + p); }
    /** Take money off: a coupon, a refund of a fee, a loyalty credit. */
    Bill addDiscount(long p) { return new Bill(items, delivery, surge, discount + p, total - p); }
    @Override public String toString() {
        return "items " + Money.fmt(items) + " + delivery " + Money.fmt(delivery) + " + surge " + Money.fmt(surge)
             + " - discount " + Money.fmt(discount) + " = " + Money.fmt(total);
    }
}

/** Everything a pricing rule is allowed to look at. A rule reads this and the running bill, and nothing else. */
record PriceCtx(String restaurantId, String customerId, double km, boolean busy,
                List<String> coupons, List<OrderLine> lines) {}

/** What a cancellation gave back and what it kept. Returned to the caller so the app can show both numbers. */
record Refund(long refundedPaise, long keptPaise) {}

/** Where time comes from. Injected, so a test can stamp an order with any instant it likes. */
interface Clock { long nowMs(); }

// "marketing will change the fee and the coupons during the round" -> hide each behind an interface -> Strategy
/**
 * One step of the price. Each rule takes the running bill and returns a richer one; the service applies the
 * list in order. A rule must keep the parts and the total in step -- CheckedRule enforces that for every rule.
 */
interface PricingRule {
    /** The bill after this rule has had its say. Never mutates the bill it was given. */
    Bill apply(Bill running, PriceCtx ctx);
}

/** Who should carry this order. Returns a RANKED list, because the top choice may be taken in the gap. */
interface AssignmentRule {
    /** Candidate rider ids, best first, from a snapshot of the free riders. May be empty. */
    List<String> rank(List<DeliveryPartner> free, Geo pickup);
}

/** How much money goes back when an order is cancelled. Changes with the season; injected, never hard-coded. */
interface CancellationPolicy {
    /** Paise to refund for this order cancelled out of state `from` at nowMs. Never more than the total. */
    long refundPaise(Order order, OrderState from, long nowMs);
}

/** The card gateway. The slow, irreversible step: it is called outside every lock, and only once per order. */
interface PaymentProcessor {
    /** True if the money moved, false if the bank said no. Throwing means "I do not know" -- see ChargeLog. */
    boolean charge(String chargeId, long paise);
    /** Give money back for a charge that succeeded. Called on cancel, on a rejection, and by the reconciler. */
    void refund(String chargeId, long paise);
}

/**
 * What we know about one charge. UNKNOWN is the dangerous one: the money may or may not have left the
 * customer. REFUND_OWED is written before a refund is sent and stays until the gateway confirms it, so a
 * refund that fails is retried by the sweep instead of lost. REFUNDED means the money went back.
 */
enum ChargeOutcome { ATTEMPTED, CHARGED, DECLINED, UNKNOWN, REFUND_OWED, REFUNDED }

/**
 * Where a charge is written down BEFORE the gateway is called, and again after, with what we learned. Without
 * this line a timed-out charge is money nobody can find: no order to look up, and no record that we ever tried.
 */
interface ChargeLog {
    /** Record one step of one charge attempt. Must not throw: it is on the checkout path. */
    void record(String chargeId, String customerId, long paise, ChargeOutcome outcome);
}

/** Anybody who wants to hear that an order moved: the customer app, the restaurant tablet, analytics. */
interface OrderObserver {
    /**
     * Called AFTER the state is committed and the lock is released. `from` is null when the order was just
     * placed, and equal to the current state when the event is "a rider was assigned" rather than a move.
     * Must not throw; if it does, the service logs it and carries on.
     */
    void onState(Order order, OrderState from);
}

/** Is this restaurant's area busy right now? The input to surge, injected so a test can turn the rain on. */
interface Demand {
    /** True if delivery is scarce around this restaurant at this instant. */
    boolean busy(String restaurantId, long nowMs);
}

/** The first rule in every chain: what the food costs, at the prices snapshotted at checkout. */
final class ItemTotal implements PricingRule {
    public Bill apply(Bill running, PriceCtx ctx) {
        long items = 0;
        for (OrderLine l : ctx.lines()) items += l.amountPaise();
        return running.withItems(items);
    }
}

/** A flat pickup fee plus a per-kilometre fee, rounded up to the next whole kilometre. */
final class DistanceFee implements PricingRule {
    private final long basePaise, perKmPaise;
    DistanceFee(long basePaise, long perKmPaise) { this.basePaise = basePaise; this.perKmPaise = perKmPaise; }
    public Bill apply(Bill running, PriceCtx ctx) {
        return running.addDelivery(basePaise + perKmPaise * (long) Math.ceil(ctx.km()));
    }
}

/** Rain, a cricket final, a Friday night: a multiplier on the delivery fee only, never on the food. */
final class SurgeFee implements PricingRule {
    private final long multBps;                                   // 15000 = 1.5x
    SurgeFee(long multBps) { this.multBps = multBps; }
    public Bill apply(Bill running, PriceCtx ctx) {
        if (!ctx.busy()) return running;
        return running.addSurge(running.delivery() * (multBps - 10_000) / 10_000);
    }
}

/** A percentage off the food (not the fees), in basis points: 4000 = 40%. Fires only if its code was used. */
final class PercentCoupon implements PricingRule {
    private final String code; private final long offBps;
    PercentCoupon(String code, long offBps) { this.code = code; this.offBps = offBps; }
    public Bill apply(Bill running, PriceCtx ctx) {
        if (!ctx.coupons().contains(code)) return running;
        return running.addDiscount(running.items() * offBps / 10_000);
    }
}

/** A flat amount off, never more than what is still owed, so a coupon can take the bill to zero but not below. */
final class FlatCoupon implements PricingRule {
    private final String code; private final long offPaise;
    FlatCoupon(String code, long offPaise) { this.code = code; this.offPaise = offPaise; }
    public Bill apply(Bill running, PriceCtx ctx) {
        if (!ctx.coupons().contains(code)) return running;
        return running.addDiscount(Math.min(offPaise, running.total()));
    }
}

/**
 * DECORATOR. Wraps any discount rule and caps what it took off: "40% off, up to 120 rupees". The inner rule
 * does not know it is capped, so one cap class serves every coupon written this year and next.
 */
final class CappedDiscount implements PricingRule {
    private final PricingRule inner; private final long capPaise;
    CappedDiscount(PricingRule inner, long capPaise) { this.inner = inner; this.capPaise = capPaise; }
    public Bill apply(Bill running, PriceCtx ctx) {
        Bill after = inner.apply(running, ctx);
        long took = after.discount() - running.discount();
        return took <= capPaise ? after : running.addDiscount(capPaise);
    }
}

/**
 * DECORATOR. Wraps EVERY rule the service is handed and refuses a bill whose parts do not add up to its total,
 * or that went negative. A rule written next year cannot charge a customer a number nobody can explain.
 */
final class CheckedRule implements PricingRule {
    private final PricingRule inner;
    CheckedRule(PricingRule inner) { this.inner = inner; }
    public Bill apply(Bill running, PriceCtx ctx) {
        Bill out = inner.apply(running, ctx);
        String who = inner.getClass().getSimpleName();
        if (out.items() < 0 || out.delivery() < 0 || out.surge() < 0 || out.discount() < 0)
            throw new IllegalStateException(who + " produced a negative line: " + out);
        if (out.items() + out.delivery() + out.surge() - out.discount() != out.total())
            throw new IllegalStateException(who + " left the parts and the total out of step: " + out);
        if (out.total() < 0) throw new IllegalStateException(who + " made the total negative: " + out);
        return out;
    }
}

/** The default assignment rule: whoever is free and closest to the restaurant, nearest first. */
final class NearestFree implements AssignmentRule {
    public List<String> rank(List<DeliveryPartner> free, Geo pickup) {
        List<DeliveryPartner> sorted = new ArrayList<>(free);
        sorted.sort(Comparator.comparingDouble(p -> p.at().kmTo(pickup)));
        List<String> ids = new ArrayList<>(sorted.size());
        for (DeliveryPartner p : sorted) ids.add(p.id());
        return ids;
    }
}

/** Free until the kitchen starts cooking; after that the food exists, so a flat fee is kept and the rest returns. */
final class StandardCancellation implements CancellationPolicy {
    private final long feePaise;
    StandardCancellation(long feePaise) { this.feePaise = feePaise; }
    public long refundPaise(Order order, OrderState from, long nowMs) {
        long total = order.bill().total();
        if (from == OrderState.PLACED || from == OrderState.ACCEPTED) return total;   // nothing has been cooked
        return Math.max(0, total - feePaise);                                         // PREPARING or READY
    }
}

/** A stand-in for the card gateway: counts calls, and declines any card on its blocked list. */
final class FakeGateway implements PaymentProcessor {
    private final Set<String> declineFor = ConcurrentHashMap.newKeySet();
    private final AtomicInteger charges = new AtomicInteger(), refunds = new AtomicInteger();
    /** Make every charge whose id contains this marker fail, so a test can force a decline. */
    void declineContaining(String marker) { declineFor.add(marker); }
    public boolean charge(String chargeId, long paise) {
        charges.incrementAndGet();
        for (String m : declineFor) if (chargeId.contains(m)) return false;
        return true;
    }
    public void refund(String chargeId, long paise) { refunds.incrementAndGet(); }
    /** How many times the card was touched -- the number the "no order, no charge" tests assert on. */
    int chargeCount() { return charges.get(); }
    /** How many refunds were issued. */
    int refundCount() { return refunds.get(); }
}

/** The customer's phone: prints every state change. A deliberately dumb observer, to show the seam. */
final class CustomerApp implements OrderObserver {
    private final boolean quiet;
    CustomerApp(boolean quiet) { this.quiet = quiet; }
    public void onState(Order o, OrderState from) {
        if (quiet) return;
        if (from == null)               System.out.println("   [app] " + o.id() + ": placed");
        else if (from == o.state())     System.out.println("   [app] " + o.id() + ": rider " + o.partnerId() + " assigned");
        else                            System.out.println("   [app] " + o.id() + ": " + from + " -> " + o.state());
    }
}

/**
 * A restaurant: its menu, how much of each item is left, whether it is open, and its own lock. The lock is
 * per restaurant because the stock is per restaurant: two restaurants never wait for each other.
 */
final class Restaurant {
    private final String id, name;
    private final Geo at;
    private final int prepMinutes;
    private final Map<String, MenuItem> menu = new LinkedHashMap<>();
    private final Map<String, Integer> stock = new HashMap<>();
    private final Set<String> liveOrders = new LinkedHashSet<>();      // O(1) in, O(1) out, arrival order
    private final ReentrantLock lock = new ReentrantLock();
    private volatile boolean open = true;

    Restaurant(String id, String name, Geo at, int prepMinutes) {
        this.id = id; this.name = name; this.at = at; this.prepMinutes = prepMinutes;
    }
    String id() { return id; }
    String name() { return name; }
    Geo at() { return at; }
    /** How long the kitchen takes, in minutes. Used by the ETA extension, never by the state machine. */
    int prepMinutes() { return prepMinutes; }
    /** Open or shut. A closed restaurant rejects at reserve time, inside the lock. */
    void setOpen(boolean o) { open = o; }

    /** Put an item on the menu with a starting stock count. */
    void put(MenuItem item, int units) {
        lock.lock();
        try { menu.put(item.id(), item); stock.put(item.id(), units); } finally { lock.unlock(); }
    }
    /** Set how many of an item are left (the kitchen ran out, or the evening batch arrived). */
    void setStock(String itemId, int units) {
        lock.lock();
        try { stock.put(itemId, units); } finally { lock.unlock(); }
    }
    /** How many are left. A read, for tests and for the menu screen. */
    int stockOf(String itemId) {
        lock.lock();
        try { return stock.getOrDefault(itemId, 0); } finally { lock.unlock(); }
    }
    /** The menu as the customer sees it. */
    List<MenuItem> menu() {
        lock.lock();
        try { return List.copyOf(menu.values()); } finally { lock.unlock(); }
    }

    /**
     * THE RACE. Check every line against the live menu and stock, and only then take the stock down --
     * all of the lines or none of them, inside one lock, so two customers can never both get the last portion.
     * Returns the lines priced at today's menu prices: the order is never priced by the client.
     */
    List<OrderLine> reserve(Map<String, Integer> want) {
        lock.lock();
        try {
            if (!open) throw new IllegalStateException(name + " is closed right now");
            if (want.isEmpty()) throw new IllegalArgumentException("an empty cart cannot be checked out");
            List<OrderLine> lines = new ArrayList<>(want.size());
            for (Map.Entry<String, Integer> e : want.entrySet()) {          // 1. check everything first
                MenuItem item = menu.get(e.getKey());
                if (item == null) throw new IllegalArgumentException(e.getKey() + " is not on this menu");
                int have = stock.getOrDefault(e.getKey(), 0);
                if (e.getValue() <= 0) throw new IllegalArgumentException("quantity must be positive");
                if (have < e.getValue())
                    throw new IllegalStateException(item.name() + ": only " + have + " left, " + e.getValue() + " wanted");
                lines.add(new OrderLine(item.id(), item.name(), item.pricePaise(), e.getValue()));
            }
            for (OrderLine l : lines) stock.merge(l.itemId(), -l.qty(), Integer::sum);   // 2. only now, write
            return List.copyOf(lines);
        } finally { lock.unlock(); }
    }

    /** Put reserved stock back: the card was declined, the restaurant rejected, or the customer cancelled early. */
    void giveBack(List<OrderLine> lines) {
        lock.lock();
        try { for (OrderLine l : lines) stock.merge(l.itemId(), l.qty(), Integer::sum); } finally { lock.unlock(); }
    }
    /** Add an order to this restaurant's live queue (the tablet's screen). */
    void enqueue(String orderId) { lock.lock(); try { liveOrders.add(orderId); } finally { lock.unlock(); } }
    /** Take an order off the live queue: it reached a terminal state. */
    void dequeue(String orderId) { lock.lock(); try { liveOrders.remove(orderId); } finally { lock.unlock(); } }
    /** The tablet's queue, in arrival order. O(1) to add and remove; this copy is O(n) and is a read. */
    List<String> liveQueue() { lock.lock(); try { return List.copyOf(liveOrders); } finally { lock.unlock(); } }
}

/**
 * A customer's basket, bound to one restaurant at the moment it is opened. The single-restaurant rule is
 * enforced here, at add time, rather than hoped for at checkout.
 */
final class Cart {
    private final String customerId, restaurantId;
    private final Geo dropAt;
    private final LinkedHashMap<String, Integer> lines = new LinkedHashMap<>();

    Cart(String customerId, String restaurantId, Geo dropAt) {
        this.customerId = customerId; this.restaurantId = restaurantId; this.dropAt = dropAt;
    }
    String customerId() { return customerId; }
    String restaurantId() { return restaurantId; }
    /** Where the food is going. Fixed when the cart is opened, so the fee cannot change under the customer. */
    Geo dropAt() { return dropAt; }
    /** Add or increase a line. Synchronized because the customer may be tapping on a phone and a tablet. */
    synchronized void add(String itemId, int qty) { lines.merge(itemId, qty, Integer::sum); }
    /** Drop a line entirely. */
    synchronized void remove(String itemId) { lines.remove(itemId); }
    /** A frozen copy in the order the customer added things, so checkout prices a basket that cannot move. */
    synchronized Map<String, Integer> snapshot() {
        return Collections.unmodifiableMap(new LinkedHashMap<>(lines));
    }
    /** Empty it, once its order exists. */
    synchronized void clear() { lines.clear(); }
    /** True if there is nothing to check out. */
    synchronized boolean isEmpty() { return lines.isEmpty(); }
}

/**
 * A placed order. Its lines and its bill never change after checkout -- they are the receipt. Its state and
 * its rider do, and both change only under this order's own lock.
 */
final class Order {
    private final String id, customerId, restaurantId, chargeId;
    private final List<OrderLine> lines;
    private final Bill bill;
    private final Geo dropAt;
    private final long placedAtMs;
    private final ReentrantLock lock = new ReentrantLock();
    private final EnumMap<OrderState, Long> stamps = new EnumMap<>(OrderState.class);
    private volatile String partner;                        // written under the lock, read without it
    private volatile OrderState state = OrderState.PLACED;

    Order(String id, String customerId, String restaurantId, String chargeId,
          List<OrderLine> lines, Bill bill, Geo dropAt, long placedAtMs) {
        this.id = id; this.customerId = customerId; this.restaurantId = restaurantId; this.chargeId = chargeId;
        this.lines = lines; this.bill = bill; this.dropAt = dropAt; this.placedAtMs = placedAtMs;
        stamps.put(OrderState.PLACED, placedAtMs);
    }
    String id() { return id; }
    String customerId() { return customerId; }
    String restaurantId() { return restaurantId; }
    /** The gateway's id for the one charge this order made. Refunds quote it. */
    String chargeId() { return chargeId; }
    List<OrderLine> lines() { return lines; }
    /** The receipt: what was charged and why, frozen at checkout. */
    Bill bill() { return bill; }
    /** Where the food is going. Fixed at checkout, so a moved pin cannot reprice a paid order. */
    Geo dropAt() { return dropAt; }
    long placedAtMs() { return placedAtMs; }
    /** The current state. Volatile, so "where is my order?" is a lock-free read. */
    OrderState state() { return state; }
    /** The rider carrying it, or null. Volatile, so the read takes no lock. */
    String partnerId() { return partner; }
    /**
     * THE SECOND CLAIM. The rider was claimed with a compare-and-set on the rider; this claims the ORDER, under
     * its lock, and only while it is READY with no rider. Two dispatchers can each win a different rider for
     * one waiting order, and the customer can cancel at that instant: the loser hands his rider straight back.
     */
    boolean takePartner(String id) {
        lock.lock();
        try {
            if (state != OrderState.READY || partner != null) return false;
            partner = id;
            return true;
        } finally { lock.unlock(); }
    }
    /** Let the rider go. Only called on a terminal path, when takePartner can no longer succeed. */
    void clearPartner() { partner = null; }
    void lock() { lock.lock(); }
    void unlock() { lock.unlock(); }
    /** Commit a state, with the instant it happened. Only ever called with this order's lock held. */
    void moveTo(OrderState to, long atMs) { state = to; stamps.put(to, atMs); }
    /** When each state was reached. A copy, taken under the lock, so a reader never sees a half-written map. */
    Map<OrderState, Long> stamps() {
        lock.lock();
        try { return new EnumMap<>(stamps); } finally { lock.unlock(); }
    }
}

/**
 * A rider. The only contended state is the free/busy flag, and it is a single field, so a compare-and-set
 * fits and no lock is needed: the winner of the CAS is the one who gets him.
 */
final class DeliveryPartner {
    private final String id;
    private final AtomicReference<PartnerState> state = new AtomicReference<>(PartnerState.AVAILABLE);
    private volatile Geo at;
    private volatile String orderId;

    DeliveryPartner(String id, Geo at) { this.id = id; this.at = at; }
    String id() { return id; }
    /** Last known position. Written by the rider app's GPS stream, read by the assignment rule. */
    Geo at() { return at; }
    void moveTo(Geo g) { at = g; }
    PartnerState state() { return state.get(); }
    boolean isAvailable() { return state.get() == PartnerState.AVAILABLE; }
    /** The order he is carrying, or null. */
    String orderId() { return orderId; }
    /**
     * Take this rider for an order. One indivisible step: whoever wins the compare-and-set has him, and the
     * loser simply tries the next candidate. This is the whole of "a rider is never double-booked".
     */
    boolean claim(String forOrderId) {
        if (!state.compareAndSet(PartnerState.AVAILABLE, PartnerState.ASSIGNED)) return false;
        orderId = forOrderId;
        return true;
    }
    /** Hand him back to the pool. Called on every terminal path, which is what stops the fleet leaking riders. */
    void release() {
        orderId = null;
        state.compareAndSet(PartnerState.ASSIGNED, PartnerState.AVAILABLE);
    }
    /** Log out (end of shift). Only allowed while free. */
    boolean goOffline() { return state.compareAndSet(PartnerState.AVAILABLE, PartnerState.OFFLINE); }
    /** Log back in. OrderService.register calls it, then lets the waiting orders see him. */
    void goOnline() { state.compareAndSet(PartnerState.OFFLINE, PartnerState.AVAILABLE); }
}

/**
 * The orchestrator: it owns the registries, is handed the rules, and is the only place the order of operations
 * at checkout is written down. It holds no lock of its own -- the locks live where the state lives: the
 * restaurant's lock guards stock, each order's lock guards its state and its rider, and the rider's own
 * free/busy flag is a compare-and-set.
 */
final class OrderService {
    private final Map<String, Restaurant> restaurants = new ConcurrentHashMap<>();
    private final Map<String, DeliveryPartner> partners = new ConcurrentHashMap<>();
    private final Map<String, Order> orders = new ConcurrentHashMap<>();
    private final Map<String, Cart> carts = new ConcurrentHashMap<>();          // one open cart per customer
    private final Map<String, InFlight> byKey = new ConcurrentHashMap<>();      // idempotency key -> the attempt
    private final ConcurrentLinkedDeque<String> waitingForRider = new ConcurrentLinkedDeque<>();
    private final List<OrderObserver> observers = new CopyOnWriteArrayList<>();
    private final AtomicInteger orderSeq = new AtomicInteger(), chargeSeq = new AtomicInteger();

    private List<PricingRule> pricing = List.of();
    private AssignmentRule assignment = new NearestFree();
    private CancellationPolicy cancellation = new StandardCancellation(0);
    private PaymentProcessor payments;
    private Demand demand = (r, t) -> false;
    private Clock clock = System::currentTimeMillis;
    private ChargeLog chargeLog = (id, who, paise, outcome) -> { };     // no-op until somebody hands one in

    /** Hand in every rule that can change. The service builds none of them; that is the whole point. */
    void configure(List<PricingRule> pricing, AssignmentRule assignment,
                   CancellationPolicy cancellation, PaymentProcessor payments) {
        List<PricingRule> checked = new ArrayList<>(pricing.size());
        for (PricingRule r : pricing) checked.add(new CheckedRule(r));     // Decorator: police every rule
        this.pricing = List.copyOf(checked);
        this.assignment = assignment; this.cancellation = cancellation; this.payments = payments;
    }
    /** Where "is it busy?" comes from. A test flips it on to make surge fire. */
    void setDemand(Demand d) { demand = d; }
    /** Where time comes from. A test hands in a fixed instant. */
    void setClock(Clock c) { clock = c; }
    /** Where charge attempts are written down, so a charge whose answer never came back can be found again. */
    void setChargeLog(ChargeLog l) { chargeLog = l; }
    /** Add a listener. Called after the state is committed and the lock released, never inside it. */
    void addObserver(OrderObserver o) { observers.add(o); }

    void register(Restaurant r) { restaurants.put(r.id(), r); }
    /** A rider logs in (new, or back from a break). He is one more free rider, so the waiting orders get a look. */
    void register(DeliveryPartner p) { partners.put(p.id(), p); p.goOnline(); drainWaiting(); }
    Restaurant restaurant(String id) { return restaurants.get(id); }
    DeliveryPartner partner(String id) { return partners.get(id); }
    /** An order by id: O(1), and the read path for "where is my order?". */
    Order order(String id) { return orders.get(id); }
    /** How many READY orders are waiting for a rider right now. */
    int waitingCount() { return waitingForRider.size(); }

    /** Open a basket for this customer at this restaurant. Opening a second one replaces the first. */
    Cart openCart(String customerId, String restaurantId, Geo dropAt) {
        if (!restaurants.containsKey(restaurantId)) throw new IllegalArgumentException("no such restaurant");
        Cart c = new Cart(customerId, restaurantId, dropAt);
        carts.put(customerId, c);
        return c;
    }
    /**
     * Add to the customer's open cart. The single-restaurant invariant is enforced here: an item from another
     * restaurant is refused, rather than discovered at checkout when the customer has already committed.
     */
    void addToCart(String customerId, String restaurantId, String itemId, int qty) {
        Cart c = carts.get(customerId);
        if (c == null) throw new IllegalStateException("no open cart for " + customerId);
        if (!c.restaurantId().equals(restaurantId))
            throw new IllegalStateException("this cart belongs to " + c.restaurantId() + "; clear it first");
        c.add(itemId, qty);
    }

    /** One attempt at placing an order, so a retried tap waits for the first instead of paying twice. */
    private static final class InFlight {
        private final CountDownLatch done = new CountDownLatch(1);
        private volatile Order order;
        private volatile RuntimeException failure;
        Order await() {
            try { done.await(); } catch (InterruptedException e) {
                Thread.currentThread().interrupt(); throw new IllegalStateException("interrupted while retrying");
            }
            if (failure != null) throw failure;
            return order;
        }
        void succeed(Order o) { order = o; done.countDown(); }
        void fail(RuntimeException e) { failure = e; done.countDown(); }
    }

    /**
     * THE CRITICAL STEP, in this order and no other: claim the idempotency key; reserve the stock under the
     * restaurant's lock (all lines or none); price it outside every lock; charge the card, which is the slow
     * irreversible bit; and only if the money moved does an order exist. A decline hands the stock back and
     * leaves the system exactly as it was, so the customer can try another card.
     */
    Order placeOrder(String idempotencyKey, String customerId, List<String> coupons) {
        Cart cart = carts.get(customerId);
        if (cart == null) throw new IllegalStateException("nothing in the cart");
        return placeOrder(idempotencyKey, cart, coupons);
    }

    /**
     * The same checkout for a cart that is not the customer's open one: a booking, or one leg of a split basket.
     * The key is scoped to the customer, so two apps that happen to send the same key never share an order.
     */
    Order placeOrder(String idempotencyKey, Cart cart, List<String> coupons) {
        String key = cart.customerId() + "/" + idempotencyKey;
        InFlight mine = new InFlight();
        InFlight running = byKey.putIfAbsent(key, mine);
        if (running != null) return running.await();          // the same tap twice: one order, one charge
        try {
            Order placed = doPlace(cart, coupons);
            mine.succeed(placed);
            return placed;
        } catch (RuntimeException e) {
            byKey.remove(key, mine);                          // a failed attempt frees the key for a real retry
            mine.fail(e);
            throw e;
        }
    }

    /** The critical step itself, numbered below. Nothing is committed until the money has moved. */
    private Order doPlace(Cart cart, List<String> coupons) {
        if (cart.isEmpty()) throw new IllegalStateException("nothing in the cart");
        String customerId = cart.customerId();
        Restaurant r = restaurants.get(cart.restaurantId());
        if (r == null) throw new IllegalArgumentException("no such restaurant");

        // 1. under the restaurant's lock: validate against the live menu and take the stock down, all or none.
        List<OrderLine> lines = r.reserve(cart.snapshot());
        Order o;
        try {
            // 2. price it with no lock held. Rules can throw; nothing outside the reservation has moved yet.
            PriceCtx ctx = new PriceCtx(r.id(), customerId, r.at().kmTo(cart.dropAt()),
                                        demand.busy(r.id(), clock.nowMs()), List.copyOf(coupons), lines);
            Bill bill = Bill.EMPTY;
            for (PricingRule rule : pricing) bill = rule.apply(bill, ctx);

            // 3. the irreversible external action, outside every lock. Nothing has been committed yet.
            //    Write the attempt down BEFORE the call: if the answer never comes back, this row is the only
            //    proof we tried, and the reconciler uses it to ask the gateway later.
            String chargeId = "ch-" + chargeSeq.incrementAndGet();
            chargeLog.record(chargeId, customerId, bill.total(), ChargeOutcome.ATTEMPTED);
            boolean paid;
            try { paid = payments.charge(chargeId, bill.total()); }
            catch (RuntimeException gatewayDied) {                      // a timeout: we do NOT know
                chargeLog.record(chargeId, customerId, bill.total(), ChargeOutcome.UNKNOWN);
                throw new IllegalStateException("payment outcome unknown for " + chargeId
                                              + "; no order was created and the charge will be reconciled");
            }
            chargeLog.record(chargeId, customerId, bill.total(),
                             paid ? ChargeOutcome.CHARGED : ChargeOutcome.DECLINED);
            if (!paid) throw new IllegalStateException("payment declined for " + Money.fmt(bill.total()));

            // 4. the money moved, so now -- and only now -- an order exists.
            o = new Order("o-" + orderSeq.incrementAndGet(), customerId, r.id(), chargeId,
                          lines, bill, cart.dropAt(), clock.nowMs());
            orders.put(o.id(), o);
            r.enqueue(o.id());
            cart.clear();
        } catch (RuntimeException e) {
            r.giveBack(lines);                                 // a decline or a bad rule returns the food
            throw e;
        }
        publish(o, null);                                      // 5. after everything is committed
        return o;
    }

    /** The restaurant accepts. PLACED to ACCEPTED, and nothing else may follow from PLACED except reject/cancel. */
    void accept(String orderId) { transition(need(orderId), OrderState.ACCEPTED); }
    /** The kitchen starts. After this, a cancellation costs the customer the cancellation fee. */
    void startPreparing(String orderId) { transition(need(orderId), OrderState.PREPARING); }
    /** The rider has it. Only an order that has a rider can be picked up. */
    void pickUp(String orderId) {
        Order o = need(orderId);
        if (o.partnerId() == null) throw new IllegalStateException(orderId + " has no rider yet, so nobody can pick it up");
        transition(o, OrderState.PICKED_UP);
    }

    /**
     * The food is ready: commit the state, then look for a rider, outside the order's lock. If nobody is free
     * the order joins the queue FIRST and only then looks again -- a rider freed in the gap between a failed
     * claim and the enqueue would otherwise be missed, and the order would sit there with a rider idle.
     */
    boolean markReady(String orderId) {
        Order o = need(orderId);
        transition(o, OrderState.READY);
        if (!tryAssign(o)) waitingForRider.addLast(o.id());   // nobody free is a normal outcome, not an exception
        drainWaiting();                       // ...and look again: a rider may have come free in the gap
        return o.partnerId() != null;
    }

    /**
     * Ask the rule for candidates, then take the first one the compare-and-set gives us. Losing the CAS is
     * expected: the ranking was a snapshot, and the winner is decided by claim(), not by the ranking. Then the
     * second claim, on the order. Returns false only if no rider could be claimed; true means the order is
     * settled: it has this rider, or it had another or was cancelled, and this one went straight back.
     */
    private boolean tryAssign(Order o) {
        Restaurant r = restaurants.get(o.restaurantId());
        for (int attempt = 0; attempt < 3; attempt++) {
            List<DeliveryPartner> free = new ArrayList<>();
            for (DeliveryPartner p : partners.values()) if (p.isAvailable()) free.add(p);
            List<String> ranked = assignment.rank(free, r.at());
            if (ranked.isEmpty()) return false;
            for (String id : ranked) {
                DeliveryPartner p = partners.get(id);
                if (p != null && p.claim(o.id())) {
                    if (!o.takePartner(id)) { p.release(); return true; }   // the caller drains: he is free again
                    publish(o, o.state());
                    return true;
                }
            }
        }
        return false;
    }

    /** Delivered: the terminal happy path. The rider is handed back and the waiting queue is drained. */
    void deliver(String orderId) {
        Order o = need(orderId);
        transition(o, OrderState.DELIVERED);
        restaurants.get(o.restaurantId()).dequeue(orderId);
        handBack(o);
    }

    /** The restaurant refuses the order: the food goes back on the shelf, then the whole bill is refunded. */
    Refund reject(String orderId) {
        Order o = need(orderId);
        transition(o, OrderState.REJECTED);
        restaurants.get(o.restaurantId()).giveBack(o.lines());
        restaurants.get(o.restaurantId()).dequeue(orderId);
        handBack(o);                                           // our own state first: none of it can fail
        refund(o, o.bill().total());                           // then the money, which can
        return new Refund(o.bill().total(), 0);
    }

    /**
     * The customer (or the restaurant) cancels. The refund is decided by the injected policy, inside the lock,
     * from the state it is cancelling out of. Then the food, the queue and the rider are handed back, and the
     * refund goes last, because it is the only step that can fail.
     */
    Refund cancel(String orderId) {
        Order o = need(orderId);
        OrderState from;
        long refund;
        o.lock();
        try {
            from = o.state();
            if (!from.canGoTo(OrderState.CANCELLED))
                throw new IllegalStateException(orderId + " is " + from + ": too late to cancel");
            refund = cancellation.refundPaise(o, from, clock.nowMs());
            o.moveTo(OrderState.CANCELLED, clock.nowMs());
        } finally { o.unlock(); }

        if (from == OrderState.PLACED || from == OrderState.ACCEPTED)
            restaurants.get(o.restaurantId()).giveBack(o.lines());      // not cooked yet: the food goes back
        restaurants.get(o.restaurantId()).dequeue(orderId);
        handBack(o);
        refund(o, refund);
        publish(o, from);
        return new Refund(refund, o.bill().total() - refund);
    }

    /**
     * Send money back, written down first exactly like a charge: REFUND_OWED before the call, REFUNDED after.
     * If the gateway throws, the row stays owed and the sweep sends it later; the cancel has already happened.
     */
    private void refund(Order o, long paise) {
        if (paise <= 0) return;                                          // a zero refund is not a gateway call
        chargeLog.record(o.chargeId(), o.customerId(), paise, ChargeOutcome.REFUND_OWED);
        try {
            payments.refund(o.chargeId(), paise);
            chargeLog.record(o.chargeId(), o.customerId(), paise, ChargeOutcome.REFUNDED);
        } catch (RuntimeException gatewayDown) {
            System.out.println("   [warn] refund for " + o.id() + " is owed; the sweep will send it");
        }
    }

    /** The guarded read-check-write. The only way an order's state ever changes. */
    private OrderState transition(Order o, OrderState to) {
        OrderState from;
        o.lock();
        try {
            from = o.state();
            if (!from.canGoTo(to))
                throw new IllegalStateException(o.id() + ": " + from + " -> " + to + " is not a legal move"
                                             + " (legal: " + from.next() + ")");
            o.moveTo(to, clock.nowMs());
        } finally { o.unlock(); }
        publish(o, from);                                   // AFTER the unlock
        return from;
    }

    /** Give the rider back and give the next waiting order a chance. Missing this leaks one rider per delivery. */
    private void handBack(Order o) {
        String pid = o.partnerId();
        if (pid == null) return;
        DeliveryPartner p = partners.get(pid);
        if (p != null) p.release();
        o.clearPartner();
        drainWaiting();
    }

    /**
     * Match waiting orders with free riders, oldest first, until riders or orders run out. Every event that
     * adds to either side -- an order becomes ready, a rider is handed back or logs in -- ends here. A waiting
     * order is NOT taken out of the queue while we try: if it were, a hand-back running at the same instant
     * would look at an empty queue and walk away, and the order would wait for a rider who is standing there.
     */
    private void drainWaiting() {
        for (String id; (id = waitingForRider.peekFirst()) != null; ) {
            Order w = orders.get(id);
            if (w != null && w.state() == OrderState.READY && w.partnerId() == null && !tryAssign(w))
                return;                                      // nobody free: everyone behind him waits too
            waitingForRider.remove(id);                      // he has a rider, or no longer needs one: next
        }
    }

    /** Tell everyone who is listening. A listener that throws is logged and skipped; the order is already safe. */
    private void publish(Order o, OrderState from) {
        for (OrderObserver ob : observers) {
            try { ob.onState(o, from); }
            catch (RuntimeException e) { System.out.println("   [warn] observer failed: " + e.getMessage()); }
        }
    }

    private Order need(String orderId) {
        Order o = orders.get(orderId);
        if (o == null) throw new IllegalArgumentException("no such order: " + orderId);
        return o;
    }
}

/** A demo of one lunch order end to end, then the two races this design exists to survive. */
public class Main {
    public static void main(String[] args) throws Exception {
        FakeGateway gateway = new FakeGateway();
        OrderService svc = new OrderService();
        svc.configure(
            List.of(new ItemTotal(),
                    new DistanceFee(Money.rupees("20.00"), Money.rupees("8.00")),
                    new SurgeFee(15_000),                                        // 1.5x on the fee when busy
                    new CappedDiscount(new PercentCoupon("TASTY40", 4000), Money.rupees("120.00")),
                    new FlatCoupon("NEWUSER", Money.rupees("50.00"))),
            new NearestFree(), new StandardCancellation(Money.rupees("50.00")), gateway);
        svc.setDemand((r, t) -> true);                                           // it is raining
        svc.addObserver(new CustomerApp(false));

        Restaurant truffles = new Restaurant("r-kora", "Truffles Koramangala", new Geo(12.9352, 77.6245), 18);
        truffles.put(new MenuItem("paneer", "Paneer Tikka", Money.rupees("249.00")), 3);
        truffles.put(new MenuItem("naan",   "Butter Naan",  Money.rupees("60.00")), 40);
        truffles.put(new MenuItem("biryani","Chicken Biryani", Money.rupees("320.00")), 25);
        svc.register(truffles);
        for (int i = 0; i < 4; i++) svc.register(new DeliveryPartner("p-" + (10 + i), new Geo(12.9352 + i * 0.004, 77.6260)));

        // ---------------- one order, end to end
        Geo home = new Geo(12.9352, 77.6495);                                    // 2.7 km away, billed as 3
        svc.openCart("anita", "r-kora", home);
        svc.addToCart("anita", "r-kora", "paneer", 2);
        svc.addToCart("anita", "r-kora", "naan", 1);
        Order o = svc.placeOrder("tap-1", "anita", List.of("TASTY40"));
        System.out.println("placed " + o.id() + "  " + o.bill());
        System.out.println("   paneer left after the reservation: " + truffles.stockOf("paneer"));
        svc.accept(o.id());
        svc.startPreparing(o.id());
        svc.markReady(o.id());
        System.out.println("   rider " + o.partnerId() + " has it");
        svc.pickUp(o.id());
        svc.deliver(o.id());
        System.out.println("   final state " + o.state() + ", rider back in the pool: "
            + (svc.partner("p-10").isAvailable() || svc.partner("p-11").isAvailable()));

        // ---------------- a retried tap is the same order and one charge
        int before = gateway.chargeCount();
        Order again = svc.placeOrder("tap-1", "anita", List.of("TASTY40"));
        System.out.println("retried tap-1 -> " + again.id() + " (same order: " + (again == o)
            + ", extra charges: " + (gateway.chargeCount() - before) + ")");

        // ---------------- a declined card leaves nothing behind
        gateway.declineContaining("ch-");                                        // every card fails now
        svc.openCart("bala", "r-kora", home);
        svc.addToCart("bala", "r-kora", "biryani", 1);
        int biryaniBefore = truffles.stockOf("biryani");
        try { svc.placeOrder("tap-2", "bala", List.of()); }
        catch (IllegalStateException e) { System.out.println("expected: " + e.getMessage()); }
        System.out.println("   biryani stock after the decline: " + truffles.stockOf("biryani")
            + " (was " + biryaniBefore + ")");

        // ---------------- the last portions: thirty phones, ten portions, two each
        Restaurant rush = new Restaurant("r-rush", "Meghana Lunch", new Geo(12.9352, 77.6245), 15);
        rush.put(new MenuItem("thali", "Andhra Thali", Money.rupees("300.00")), 10);
        svc.register(rush);
        FakeGateway clean = new FakeGateway();
        svc.configure(List.of(new ItemTotal(), new DistanceFee(Money.rupees("20.00"), Money.rupees("8.00"))),
                      new NearestFree(), new StandardCancellation(Money.rupees("50.00")), clean);
        int phones = 30;
        ExecutorService pool = Executors.newFixedThreadPool(12);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Boolean>> tries = new ArrayList<>();
        for (int i = 0; i < phones; i++) {
            final String who = "c" + i;
            svc.openCart(who, "r-rush", home);
            svc.addToCart(who, "r-rush", "thali", 2);
            tries.add(pool.submit(() -> {
                go.await();
                try { svc.placeOrder("k-" + who, who, List.of()); return true; }
                catch (RuntimeException e) { return false; }
            }));
        }
        go.countDown();
        int won = 0;
        for (Future<Boolean> f : tries) if (f.get()) won++;
        System.out.println(phones + " phones raced for 10 thalis at 2 each: winners=" + won
            + " stock left=" + rush.stockOf("thali") + " charges=" + clean.chargeCount() + " (must be 5, 0, 5)");
        if (won != 5 || rush.stockOf("thali") != 0 || clean.chargeCount() != 5)
            throw new AssertionError("the last-portion race lost or double-sold an item");

        // ---------------- forty ready orders, twelve riders: nobody is double-booked
        OrderService fleet = new OrderService();
        FakeGateway fg = new FakeGateway();
        fleet.configure(List.of(new ItemTotal()), new NearestFree(), new StandardCancellation(0), fg);
        Restaurant big = new Restaurant("r-big", "Empire", new Geo(12.93, 77.62), 12);
        big.put(new MenuItem("roll", "Kathi Roll", Money.rupees("150.00")), 500);
        fleet.register(big);
        for (int i = 0; i < 12; i++) fleet.register(new DeliveryPartner("f-" + i, new Geo(12.93 + i * 0.001, 77.62)));
        List<Order> ready = new ArrayList<>();
        for (int i = 0; i < 40; i++) {
            fleet.openCart("d" + i, "r-big", home);
            fleet.addToCart("d" + i, "r-big", "roll", 1);
            Order x = fleet.placeOrder("f-" + i, "d" + i, List.of());
            fleet.accept(x.id()); fleet.startPreparing(x.id());
            ready.add(x);
        }
        CountDownLatch go2 = new CountDownLatch(1);
        List<Future<?>> readied = new ArrayList<>();
        for (Order x : ready) readied.add(pool.submit(() -> { go2.await(); return fleet.markReady(x.id()); }));
        go2.countDown();
        for (Future<?> f : readied) f.get();
        pool.shutdown();
        Map<String, String> heldBy = new HashMap<>();
        int assigned = 0, clashes = 0;
        for (Order x : ready) {
            if (x.partnerId() == null) continue;
            assigned++;
            String prev = heldBy.put(x.partnerId(), x.id());
            if (prev != null) clashes++;
        }
        System.out.println("40 orders ready at once, 12 riders: assigned=" + assigned + " double-booked=" + clashes
            + " waiting=" + fleet.waitingCount() + " (must be 12, 0, 28)");
        if (assigned != 12 || clashes != 0 || fleet.waitingCount() != 28)
            throw new AssertionError("a rider was double-booked or an order was lost");
        String carried = heldBy.values().iterator().next();
        fleet.pickUp(carried);
        fleet.deliver(carried);
        System.out.println("one delivery hands a rider back, and a waiting order takes him: waiting="
            + fleet.waitingCount());
    }
}
