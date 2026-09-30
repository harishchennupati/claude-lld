import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

/**
 * A product in the catalogue: its SKU (stock keeping unit: the product's id), its name, and its price in
 * paise (100 paise = one rupee), so money is always a whole number and never a double.
 */
record Product(String sku, String name, long pricePaise) {}

/**
 * One line of an order: how many of which SKU, at the price it had when the order was placed. The price is
 * copied in, so a later price change never alters an order that already exists.
 */
record Line(String sku, int qty, long unitPaise) {
    /** What this line costs before any discount. */
    long paise() { return qty * unitPaise; }
}

/** A copy of one product's three counts, for a screen or a test. */
record StockView(int available, int reserved, int sold) {
    /** Printed the way the page talks about it. */
    public String toString() { return "available " + available + ", reserved " + reserved + ", sold " + sold; }
}

/**
 * The count of one product, split three ways: available (anyone may buy it), reserved (blocked for an order
 * that is waiting to be paid; Meesho calls this "blocked") and sold. Every unit is in exactly one of the three,
 * so the sum changes only when a seller adds or removes units. Guarded by the store's lock; every move that
 * would take a count below zero throws.
 */
final class Stock {
    private int available, reserved, sold;

    Stock(int available) {
        if (available < 0) throw new IllegalArgumentException("stock of " + available);
        this.available = available;
    }
    /** Units anyone may buy right now. */
    int available() { return available; }
    /** The three counts, copied. */
    StockView view() { return new StockView(available, reserved, sold); }
    /** Block n units for an order: available -> reserved. */
    void reserve(int n) { need(n, available, "reserve"); available -= n; reserved += n; }
    /** Give a block back (the order expired or was cancelled before payment): reserved -> available. */
    void release(int n) { need(n, reserved, "release"); reserved -= n; available += n; }
    /** The order was paid: reserved -> sold. */
    void commit(int n) { need(n, reserved, "commit"); reserved -= n; sold += n; }
    /** A paid order was cancelled before it shipped: sold -> available. */
    void putBack(int n) { need(n, sold, "put back"); sold -= n; available += n; }
    /** A seller adds n units, or with a negative n takes back units that nobody has blocked or bought. */
    void restock(int n) {
        if (n < 0) need(-n, available, "take back");
        else if ((long) available + n > Integer.MAX_VALUE) throw new IllegalArgumentException("restock of " + n + " overflows");
        available += n;
    }
    /** Refuse a move of n units out of a count that holds only have (n below zero is refused too). */
    private static void need(int n, int have, String move) {
        if (n < 0 || n > have) throw new IllegalStateException("stock would go negative: " + move + " " + n + " of " + have);
    }
}

/**
 * The catalogue and the stock of every product, keyed by SKU, so "how many PEN are free?" is one map lookup.
 * It knows the all-or-nothing rule for a list of lines. It has no lock of its own: the store's lock guards it.
 */
final class Inventory {
    private final Map<String, Product> catalog = new HashMap<>();
    private final Map<String, Stock> stock = new HashMap<>();

    /** Add a new product with its starting count. A SKU that already exists is refused: restock it instead. */
    void add(Product p, int qty) {
        if (catalog.containsKey(p.sku())) throw new IllegalArgumentException(p.sku() + " exists; use updateInventory");
        catalog.put(p.sku(), p);
        stock.put(p.sku(), new Stock(qty));
    }
    /** The product behind a SKU, or null. O(1). */
    Product product(String sku) { return catalog.get(sku); }
    /** The stock of a SKU. O(1). An unknown SKU is refused with the reason a caller can show. */
    Stock stock(String sku) {
        Stock s = stock.get(sku);
        if (s == null) throw new OrderRefused(Reason.UNKNOWN_PRODUCT, "no product " + sku);
        return s;
    }
    /**
     * Turn "these SKUs, these quantities" into priced lines, in SKU order. An unknown SKU or a quantity below
     * one is refused here, before anything is touched.
     */
    List<Line> price(Map<String, Integer> wanted) {
        List<Line> lines = new ArrayList<>();
        for (Map.Entry<String, Integer> w : new TreeMap<>(wanted).entrySet()) {
            Product p = catalog.get(w.getKey());
            if (p == null) throw new OrderRefused(Reason.UNKNOWN_PRODUCT, "no product " + w.getKey());
            if (w.getValue() == null || w.getValue() < 1) throw new OrderRefused(Reason.BAD_QUANTITY, w.getValue() + " x " + w.getKey());
            lines.add(new Line(p.sku(), w.getValue(), p.pricePaise()));
        }
        return List.copyOf(lines);
    }
    /** The first line that cannot be blocked right now, or null when every line can. Reads only. */
    Line firstShort(List<Line> lines) {
        for (Line l : lines) if (stock(l.sku()).available() < l.qty()) return l;
        return null;
    }
    /** Block every line. The caller checked firstShort under the same lock, so none of these can fail. */
    void reserveAll(List<Line> lines) { for (Line l : lines) stock(l.sku()).reserve(l.qty()); }
    /** Give every line's block back. */
    void releaseAll(List<Line> lines) { for (Line l : lines) stock(l.sku()).release(l.qty()); }
    /** Every line was paid for: reserved -> sold. */
    void commitAll(List<Line> lines) { for (Line l : lines) stock(l.sku()).commit(l.qty()); }
    /** Every line of a paid order that was cancelled goes back on sale: sold -> available. */
    void putBackAll(List<Line> lines) { for (Line l : lines) stock(l.sku()).putBack(l.qty()); }
}

/**
 * A buyer's cart: which SKUs and how many of each, kept in SKU order. It is only a wish list and blocks no
 * stock, so ten carts can hold the last unit; checkout decides who gets it. Guarded by the store's lock.
 */
final class Cart {
    private final TreeMap<String, Integer> items = new TreeMap<>();

    /** Add qty of a SKU; a SKU already in the cart just gets more. */
    void add(String sku, int qty) { items.merge(sku, qty, Integer::sum); }
    /** Take qty of a SKU out; going down to zero removes the line. */
    void remove(String sku, int qty) {
        Integer have = items.get(sku);
        if (have == null) return;
        if (qty >= have) items.remove(sku); else items.put(sku, have - qty);
    }
    /** How many of a SKU are in the cart, 0 when none. */
    int qty(String sku) { return items.getOrDefault(sku, 0); }
    /** A copy of the items, in SKU order. */
    Map<String, Integer> items() { return new TreeMap<>(items); }
    /** True when there is nothing in it. */
    boolean isEmpty() { return items.isEmpty(); }
}

/**
 * A price: the subtotal of the lines, the discounts taken off (one label each, like "SAVE10 -Rs 100.00"),
 * and the total to pay, all in paise. Immutable: each discount makes a new quote.
 */
record Quote(long subtotalPaise, List<String> discounts, long totalPaise) {
    /** This quote with one more discount taken off. The total never goes below zero. */
    Quote less(String label, long offPaise) {
        long off = Math.max(0, Math.min(offPaise, totalPaise));
        List<String> d = new ArrayList<>(discounts);
        d.add(label + " -" + Main.rs(off));
        return new Quote(subtotalPaise, List.copyOf(d), totalPaise - off);
    }
    /** Printed in rupees, the way a bill shows it. */
    public String toString() { return "subtotal " + Main.rs(subtotalPaise) + ", " + discounts + ", total " + Main.rs(totalPaise); }
}

/**
 * How a list of lines is priced. Behind an interface because it WILL change mid-round: offers, coupons,
 * buy-two-get-one. Rules wrap each other (the Decorator pattern), and the wrapping order is the order in which
 * the discounts apply.
 */
interface PricingRule { Quote price(List<Line> lines); }

/** The plain rule: the sum of unit price times quantity, no discount. */
final class ListPrice implements PricingRule {
    /** The subtotal, and the same number as the total. */
    public Quote price(List<Line> lines) {
        long sum = 0;
        for (Line l : lines) sum += l.paise();
        return new Quote(sum, List.of(), sum);
    }
}

/** A percentage off whatever the wrapped rule charges, with a cap: "10% off, up to Rs 100". Rounded down to a paise. */
final class PercentOff implements PricingRule {
    private final PricingRule inner;
    private final String label;
    private final int percent;
    private final long capPaise;

    PercentOff(PricingRule inner, String label, int percent, long capPaise) {
        if (percent < 0 || percent > 100) throw new IllegalArgumentException(percent + "% off");
        this.inner = inner; this.label = label; this.percent = percent; this.capPaise = capPaise;
    }
    /** The wrapped price, less percent of its total, never more than the cap. */
    public Quote price(List<Line> lines) {
        Quote q = inner.price(lines);
        long off = Math.min(capPaise, q.totalPaise() * percent / 100);
        return off > 0 ? q.less(label, off) : q;
    }
}

/**
 * A flat amount off when the cart's value before any discount (the subtotal) reaches a minimum: "Rs 100 off on
 * orders above Rs 999", the way Flipkart's billing task states it.
 */
final class FlatOff implements PricingRule {
    private final PricingRule inner;
    private final String label;
    private final long offPaise, minCartPaise;

    FlatOff(PricingRule inner, String label, long offPaise, long minCartPaise) {
        this.inner = inner; this.label = label; this.offPaise = offPaise; this.minCartPaise = minCartPaise;
    }
    /** The wrapped price, less the flat amount when the subtotal is at least the minimum. */
    public Quote price(List<Line> lines) {
        Quote q = inner.price(lines);
        return q.subtotalPaise() >= minCartPaise ? q.less(label, offPaise) : q;
    }
}

/**
 * A code a buyer types at checkout: the discount it adds, and two limits, uses per buyer and uses in total.
 * discount wraps the store's pricing in this coupon's rule, e.g. base -> new PercentOff(base, "SAVE10", 10, 100_00).
 */
record Coupon(String code, int perUserLimit, int totalLimit, UnaryOperator<PricingRule> discount) {}

/**
 * Every coupon and how many times it has been used, in total and by each buyer. A use is claimed in the same
 * locked step that blocks the stock, and given back when that order dies unpaid or is cancelled, exactly like
 * a unit of stock. Guarded by the store's lock.
 */
final class CouponBook {
    private final Map<String, Coupon> byCode = new HashMap<>();
    private final Map<String, Integer> used = new HashMap<>();                   // code -> uses by everybody
    private final Map<String, Map<String, Integer>> usedBy = new HashMap<>();    // code -> buyer -> that buyer's uses

    /** Register a coupon. */
    void add(Coupon c) { byCode.put(c.code(), c); }
    /**
     * The store's pricing with this coupon wrapped round it, or a refusal: an unknown code, a coupon used up
     * for everybody, or used up for this buyer. Reads only; claim() is what counts a use.
     */
    PricingRule ruleFor(String code, String userId, PricingRule base) {
        Coupon c = byCode.get(code);
        if (c == null) throw new OrderRefused(Reason.UNKNOWN_COUPON, "no coupon " + code);
        if (used.getOrDefault(code, 0) >= c.totalLimit())
            throw new OrderRefused(Reason.COUPON_USED_UP, code + " has been used " + c.totalLimit() + " times");
        if (usedBy.getOrDefault(code, Map.of()).getOrDefault(userId, 0) >= c.perUserLimit())
            throw new OrderRefused(Reason.COUPON_USED_UP, userId + " has already used " + code);
        return c.discount().apply(base);
    }
    /** Count one use, by this buyer. Called only after ruleFor passed, under the same lock. */
    void claim(String code, String userId) {
        used.merge(code, 1, Integer::sum);
        usedBy.computeIfAbsent(code, k -> new HashMap<>()).merge(userId, 1, Integer::sum);
    }
    /** Give one use back: the order that used it expired or was cancelled. */
    void giveBack(String code, String userId) {
        used.merge(code, -1, Integer::sum);
        usedBy.get(code).merge(userId, -1, Integer::sum);
    }
    /** How many uses are claimed right now. */
    int used(String code) { return used.getOrDefault(code, 0); }
}

/**
 * The life of an order. Which move is legal from which state is a table, not an if-chain: a new state is one
 * more row, and any move not in the table throws.
 */
enum OrderStatus {
    PENDING_PAYMENT, CONFIRMED, FULFILLED, CANCELLED, EXPIRED;

    private static final Map<OrderStatus, Set<OrderStatus>> NEXT = new EnumMap<>(OrderStatus.class);
    static {
        NEXT.put(PENDING_PAYMENT, EnumSet.of(CONFIRMED, CANCELLED, EXPIRED));
        NEXT.put(CONFIRMED, EnumSet.of(FULFILLED, CANCELLED));
        NEXT.put(FULFILLED, EnumSet.noneOf(OrderStatus.class));     // delivered: a return is a different flow
        NEXT.put(CANCELLED, EnumSet.noneOf(OrderStatus.class));
        NEXT.put(EXPIRED, EnumSet.noneOf(OrderStatus.class));
    }
    /** True when the table allows this move. */
    boolean canMoveTo(OrderStatus next) { return NEXT.get(this).contains(next); }
}

/**
 * One order: who placed it, its priced lines, the quote it will be charged, the coupon it used, and the moment
 * its hold ends. Its status changes only under the store's lock, through moveTo.
 */
final class Order {
    final String id, userId, couponCode;
    final List<Line> lines;
    final Quote quote;
    final long holdUntilMs;
    private volatile OrderStatus status = OrderStatus.PENDING_PAYMENT;   // volatile: a reader outside the lock sees the latest
    PaymentGateway chargedVia;               // guarded by the store's lock: the bank a charge was sent to, null = none yet

    Order(String id, String userId, List<Line> lines, Quote quote, String couponCode, long holdUntilMs) {
        this.id = id; this.userId = userId; this.lines = lines; this.quote = quote;
        this.couponCode = couponCode; this.holdUntilMs = holdUntilMs;
    }
    /** The status right now. */
    OrderStatus status() { return status; }
    /** What the buyer pays, in paise. */
    long totalPaise() { return quote.totalPaise(); }
    /** The moment the hold ends: from then on, an unpaid order's stock is back on sale. */
    long holdUntilMs() { return holdUntilMs; }
    /** Move along the life cycle; a move the table does not allow throws and names both states. */
    void moveTo(OrderStatus next) {
        if (!status.canMoveTo(next)) throw new IllegalStateException(id + ": " + status + " -> " + next + " is not allowed");
        status = next;
    }
}

/** Why an order, a cart change or a coupon was refused. The caller shows it; nothing changed. */
enum Reason { UNKNOWN_PRODUCT, BAD_QUANTITY, EMPTY_ORDER, OUT_OF_STOCK, UNKNOWN_COUPON, COUPON_USED_UP, COUPON_NOT_APPLICABLE }

/** A refusal with its error code (PhonePe's prompt asks for one). Thrown before anything is changed. */
final class OrderRefused extends RuntimeException {
    final Reason reason;

    OrderRefused(Reason reason, String message) { super(message); this.reason = reason; }
}

/**
 * How confirmOrder ended. CONFIRMED: paid and the stock is sold (also the answer to a second, duplicate
 * call). DECLINED: nothing moved, and the hold keeps running, so another card may be tried. UNKNOWN: the bank
 * did not answer in time, so the order stays pending; a retry is charged at most once. REFUNDED: the money
 * arrived after the hold ended or the order was cancelled, so it was sent back. REFUSED: the order was already
 * over, and nothing was charged.
 */
enum PayResult { CONFIRMED, DECLINED, UNKNOWN, REFUNDED, REFUSED }

/**
 * How money moves. The order id is the idempotency key (a unique id per payment, so a request that arrives
 * twice is charged once): at most one charge per order id, and charging again while that id holds money takes
 * nothing more. false = declined; a timeout throws, and then nobody knows whether money moved. refund gives back
 * whatever that order id holds, and does nothing when it holds nothing, so it is always safe to call.
 */
interface PaymentGateway {
    /** Take the order's total. true = paid, false = declined; an exception means the outcome is unknown. */
    boolean charge(String orderId, long paise);
    /** Give back whatever this order id holds, if anything. */
    void refund(String orderId);
}

/**
 * An in-memory bank that keeps the gateway's promise: at most one charge per order id, and a refund gives back
 * what that id holds. heldPaise() is the money the shop really holds, so a test can compare it with the orders.
 */
final class FakeGateway implements PaymentGateway {
    private final Map<String, Long> held = new ConcurrentHashMap<>();   // order id -> paise taken and not given back
    final AtomicInteger charges = new AtomicInteger();                  // how many times money actually moved in

    /** Take the money once per order id; asking again while it is held takes nothing more. */
    public boolean charge(String orderId, long paise) {
        if (held.putIfAbsent(orderId, paise) == null) charges.incrementAndGet();
        return true;
    }
    /** Give back what this order id holds, if anything. */
    public void refund(String orderId) { held.remove(orderId); }
    /** All the money the shop holds right now. */
    long heldPaise() {
        long sum = 0;
        for (long p : held.values()) sum += p;
        return sum;
    }
    /** True while this order id holds money. */
    boolean holds(String orderId) { return held.containsKey(orderId); }
}

/** Where time comes from. Handed in, so a test can say "five minutes later" without sleeping. */
interface Clock { long nowMs(); }

/**
 * Something that happened, for listeners: an order event (CREATED, CONFIRMED, EXPIRED, CANCELLED, FULFILLED)
 * with the order's lines, or RESTOCKED with one line for the SKU and the units added. seq is taken under the
 * lock, so it gives the true order of events even when two threads deliver them in the other order.
 */
record StoreEvent(String kind, String orderId, String userId, List<Line> lines, long paise, long seq) {
    /** The event for an order that just changed state. */
    static StoreEvent of(String kind, Order o, long seq) { return new StoreEvent(kind, o.id, o.userId, o.lines, o.totalPaise(), seq); }
}

/**
 * Anyone who wants to hear what the store did: an SMS sender, a back-in-stock alert, a seller dashboard.
 * Called after the lock is released, on the thread that did the work, so two calls can overlap.
 */
interface StoreObserver { void onEvent(StoreEvent e); }

/** Texts the buyer on every order event. It prints here; a real one calls an SMS provider, which is slow. */
final class BuyerSms implements StoreObserver {
    /** One line per order event; restocks are not the buyer's business. */
    public void onEvent(StoreEvent e) {
        if (e.orderId() != null)
            System.out.println("   [sms to " + e.userId() + "] order " + e.orderId() + " " + e.kind() + ", " + Main.rs(e.paise()));
    }
}

/**
 * The store: the only owner of the stock, the carts, the orders, the coupon counts and the queue of running
 * holds, and the only holder of the lock that guards them. Every public method is one short locked section,
 * and every one that reads stock, orders or coupons first sweeps the holds whose time is up. Nothing slow runs
 * under the lock: the bank is called between two short sections, and listeners and refunds run after the unlock.
 */
final class Store {
    /** How long an unpaid order blocks its stock: Meesho's five minutes. */
    static final long HOLD_MS = 5 * 60_000;

    private final ReentrantLock lock = new ReentrantLock();
    private final Inventory inventory = new Inventory();
    private final CouponBook coupons = new CouponBook();
    private final Map<String, Cart> carts = new HashMap<>();                  // user -> cart
    private final Map<String, Order> orders = new HashMap<>();                // order id -> order
    private final Map<String, Map<String, String>> byKey = new HashMap<>();   // user -> idempotency key -> order id
    private final Map<String, List<Order>> history = new HashMap<>();         // user -> orders, oldest first
    private final PriorityQueue<Order> holds =                                // running holds, the soonest end first
            new PriorityQueue<>(Comparator.comparingLong(Order::holdUntilMs));
    private final List<StoreObserver> observers = new CopyOnWriteArrayList<>();
    private final Queue<String> refundsToRetry = new ConcurrentLinkedQueue<>();   // order ids whose refund call failed
    private final AtomicLong nextId = new AtomicLong(1000);
    private long eventSeq;                                                    // guarded by the lock: numbers the events
    private PricingRule pricing = new ListPrice();
    private PaymentGateway gateway = new FakeGateway();
    private long holdMs = HOLD_MS;
    private Clock clock = System::currentTimeMillis;

    /** Hand in the rules: pricing, the payment gateway and the hold time. The store never builds one itself. */
    void configure(PricingRule pricing, PaymentGateway gateway, long holdMs) {
        if (holdMs <= 0) throw new IllegalArgumentException("a hold of " + holdMs + " ms");
        lock.lock();
        try { this.pricing = pricing; this.gateway = gateway; this.holdMs = holdMs; } finally { lock.unlock(); }
    }
    /** Tests hand in their own clock. */
    void setClock(Clock c) { lock.lock(); try { clock = c; } finally { lock.unlock(); } }
    /** Subscribe a listener. */
    void addObserver(StoreObserver o) { observers.add(o); }
    /** Register a coupon. */
    void addCoupon(Coupon c) { lock.lock(); try { coupons.add(c); } finally { lock.unlock(); } }

    // ---------------- the seller's side ----------------

    /** A new product with its price and its starting count (Meesho's addProduct). */
    void addProduct(String sku, String name, long pricePaise, int qty) {
        lock.lock();
        try { inventory.add(new Product(sku, name, pricePaise), qty); } finally { lock.unlock(); }
    }

    /**
     * A seller restocks (delta above zero) or takes back units nobody has blocked or bought (delta below zero):
     * Meesho's updateInventory. Returns the new available count; a restock is announced after the unlock.
     */
    int updateInventory(String sku, int delta) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try {
            sweep(after);
            Stock s = inventory.stock(sku);
            s.restock(delta);
            if (delta > 0) {
                StoreEvent e = new StoreEvent("RESTOCKED", null, null,
                        List.of(new Line(sku, delta, inventory.product(sku).pricePaise())), 0, ++eventSeq);
                after.add(() -> publish(e));
            }
            return s.available();
        } finally { lock.unlock(); runAfter(after); }
    }

    /** How many units of a SKU anyone may buy right now (Meesho's getInventory). One lookup, after the sweep. */
    int getInventory(String sku) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try { sweep(after); return inventory.stock(sku).available(); } finally { lock.unlock(); runAfter(after); }
    }

    /** The three counts of a SKU, read together so they always add up. */
    StockView stockOf(String sku) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try { sweep(after); return inventory.stock(sku).view(); } finally { lock.unlock(); runAfter(after); }
    }

    // ---------------- the buyer's cart ----------------

    /**
     * Put qty of a SKU in the buyer's cart. It checks the product exists and that the cart would not ask for
     * more than is available right now, but it blocks nothing: that check is advice, and checkout decides.
     */
    void addToCart(String userId, String sku, int qty) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try {
            sweep(after);
            if (qty < 1) throw new OrderRefused(Reason.BAD_QUANTITY, qty + " x " + sku);
            Stock s = inventory.stock(sku);
            Cart cart = carts.computeIfAbsent(userId, u -> new Cart());
            if ((long) cart.qty(sku) + qty > s.available())
                throw new OrderRefused(Reason.OUT_OF_STOCK, sku + ": only " + s.available() + " left");
            cart.add(sku, qty);
        } finally { lock.unlock(); runAfter(after); }
    }

    /** Take qty of a SKU out of the buyer's cart. */
    void removeFromCart(String userId, String sku, int qty) {
        lock.lock();
        try { Cart cart = carts.get(userId); if (cart != null) cart.remove(sku, qty); } finally { lock.unlock(); }
    }

    /** The buyer's cart, in SKU order. */
    Map<String, Integer> viewCart(String userId) {
        lock.lock();
        try { Cart cart = carts.get(userId); return cart == null ? Map.of() : cart.items(); } finally { lock.unlock(); }
    }

    /** What the cart would cost now, with the coupon if one is given: the same code checkout uses, claiming nothing. */
    Quote cartTotal(String userId, String couponCode) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try {
            sweep(after);
            Cart cart = carts.get(userId);
            if (cart == null || cart.isEmpty()) throw new OrderRefused(Reason.EMPTY_ORDER, userId + "'s cart is empty");
            return quote(userId, inventory.price(cart.items()), couponCode);
        } finally { lock.unlock(); runAfter(after); }
    }

    // ---------------- orders ----------------

    /**
     * Check out the buyer's whole cart: every line is blocked for the hold time, all or none, and the cart is
     * emptied. A retry with the same idempotency key returns the same order and touches nothing.
     */
    Order checkout(String userId, String idempotencyKey, String couponCode) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try {
            sweep(after);
            Order earlier = replay(userId, idempotencyKey);
            if (earlier != null) return earlier;                      // the retry of a checkout that already worked
            Cart cart = carts.get(userId);
            if (cart == null || cart.isEmpty()) throw new OrderRefused(Reason.EMPTY_ORDER, userId + "'s cart is empty");
            Order o = place(userId, idempotencyKey, cart.items(), couponCode, after);
            carts.remove(userId);                                     // everything in it is now in the order
            return o;
        } finally { lock.unlock(); runAfter(after); }
    }

    /**
     * Place an order for these SKUs and quantities (Meesho's createOrder, PhonePe's createOrder): every line is
     * blocked for the hold time, all or none. A retry with the same idempotency key returns the same order.
     */
    Order createOrder(String userId, String idempotencyKey, Map<String, Integer> wanted, String couponCode) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try {
            sweep(after);
            Order earlier = replay(userId, idempotencyKey);
            if (earlier != null) return earlier;
            return place(userId, idempotencyKey, wanted, couponCode, after);
        } finally { lock.unlock(); runAfter(after); }
    }

    /**
     * Pay for an order and, when the money arrives in time, sell its blocked stock (Meesho's confirmOrder, which
     * runs once payment succeeds). In three steps: under the lock, check there is something to pay for; with NO
     * lock held, charge the bank, using the order id as the idempotency key; under the lock again, commit only if
     * the order is still pending and its hold has not ended, and otherwise send the money back.
     */
    PayResult confirmOrder(String orderId) {
        List<Runnable> after = new ArrayList<>();
        Order o;
        PaymentGateway bank;
        lock.lock();
        try {
            sweep(after);
            o = find(orderId);
            if (o.status() == OrderStatus.CONFIRMED || o.status() == OrderStatus.FULFILLED) return PayResult.CONFIRMED;
            if (o.status() != OrderStatus.PENDING_PAYMENT) return PayResult.REFUSED;   // expired or cancelled: charge nothing
            bank = gateway;
            o.chargedVia = bank;                      // from now on, if this order dies unpaid, this bank refunds it by id
        } finally { lock.unlock(); runAfter(after); }

        boolean paid;
        try { paid = bank.charge(o.id, o.totalPaise()); }            // OUTSIDE the lock: a bank takes a second or two
        catch (RuntimeException timeout) { return PayResult.UNKNOWN; }   // did money move? unknown: stays pending
        if (!paid) return PayResult.DECLINED;                         // nothing moved; the hold keeps running

        lock.lock();
        try {
            if (o.status() == OrderStatus.PENDING_PAYMENT && clock.nowMs() < o.holdUntilMs) {
                inventory.commitAll(o.lines);                         // still ours and still in time: reserved -> sold
                o.moveTo(OrderStatus.CONFIRMED);
                announce("CONFIRMED", o, after);
                return PayResult.CONFIRMED;
            }
            if (o.status() == OrderStatus.CONFIRMED || o.status() == OrderStatus.FULFILLED)
                return PayResult.CONFIRMED;                           // a racing call committed this same charge
            if (o.status() == OrderStatus.PENDING_PAYMENT) endUnpaid(o, OrderStatus.EXPIRED, after);   // ran out meanwhile; queues the refund
            else refundLater(o, after);                               // expired or cancelled by someone else meanwhile
            return PayResult.REFUNDED;
        } finally { lock.unlock(); runAfter(after); }
    }

    /**
     * Cancel an order. Unpaid: its block is released. Paid but not delivered: its units go back on sale and the
     * money is refunded after the unlock. Already cancelled or expired: nothing more happens. Delivered: refused,
     * because goods that have reached the buyer come back as a return, not a cancel.
     */
    OrderStatus cancelOrder(String orderId) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try {
            sweep(after);
            Order o = find(orderId);
            switch (o.status()) {
                case PENDING_PAYMENT -> endUnpaid(o, OrderStatus.CANCELLED, after);
                case CONFIRMED -> {
                    inventory.putBackAll(o.lines);                    // sold -> available
                    if (o.couponCode != null) coupons.giveBack(o.couponCode, o.userId);
                    o.moveTo(OrderStatus.CANCELLED);
                    refundLater(o, after);
                    announce("CANCELLED", o, after);
                }
                case FULFILLED -> throw new IllegalStateException(orderId + " was delivered: that is a return, not a cancel");
                default -> { }                                        // CANCELLED or EXPIRED: nothing left to undo
            }
            return o.status();
        } finally { lock.unlock(); runAfter(after); }
    }

    /** Mark a paid order delivered (PhonePe's FULFILLED). Only a CONFIRMED order may move here. */
    void fulfilOrder(String orderId) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try {
            sweep(after);
            Order o = find(orderId);
            o.moveTo(OrderStatus.FULFILLED);
            announce("FULFILLED", o, after);
        } finally { lock.unlock(); runAfter(after); }
    }

    /** End every hold whose time is up. Every method already does this first; a background job may call it too. */
    int sweepExpired() {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try { return sweep(after); } finally { lock.unlock(); runAfter(after); }
    }

    /** One order by id, after the sweep, so its status is never a stale PENDING_PAYMENT. O(1). */
    Order order(String orderId) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try { sweep(after); return find(orderId); } finally { lock.unlock(); runAfter(after); }
    }

    /** A buyer's orders, oldest first (the order history). O(1) to find, O(k) to copy k orders. */
    List<Order> orderHistory(String userId) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try { sweep(after); return List.copyOf(history.getOrDefault(userId, List.of())); } finally { lock.unlock(); runAfter(after); }
    }

    /** How many uses of a coupon are claimed right now, after the sweep has given back those of dead orders. */
    int couponUses(String code) {
        List<Runnable> after = new ArrayList<>();
        lock.lock();
        try { sweep(after); return coupons.used(code); } finally { lock.unlock(); runAfter(after); }
    }

    /** Order ids whose refund call failed; a retry job calls refund again, which is safe. */
    List<String> refundsToRetry() { return List.copyOf(refundsToRetry); }

    // ---------------- the private steps; the caller holds the lock ----------------

    /** The order an earlier call with this buyer's idempotency key created, or null. */
    private Order replay(String userId, String key) {
        String id = byKey.getOrDefault(userId, Map.of()).get(key);
        return id == null ? null : orders.get(id);
    }

    /**
     * THE critical step of checkout. In this order: price every line and check every line and the coupon,
     * touching nothing, so a refusal changes nothing; then write: block every line, count the coupon use, and
     * create the order with its hold. Under one lock, so nobody can take the stock between the check and the
     * write.
     */
    private Order place(String userId, String key, Map<String, Integer> wanted, String couponCode, List<Runnable> after) {
        if (wanted.isEmpty()) throw new OrderRefused(Reason.EMPTY_ORDER, "nothing to order");
        List<Line> lines = inventory.price(wanted);
        Line short_ = inventory.firstShort(lines);
        if (short_ != null)
            throw new OrderRefused(Reason.OUT_OF_STOCK, short_.sku() + ": wanted " + short_.qty()
                                   + ", only " + inventory.stock(short_.sku()).available() + " left");
        Quote q = quote(userId, lines, couponCode);
        // every check passed and nothing has been touched: now write all of it
        inventory.reserveAll(lines);
        if (couponCode != null) coupons.claim(couponCode, userId);
        Order o = new Order("O" + nextId.incrementAndGet(), userId, lines, q, couponCode, clock.nowMs() + holdMs);
        orders.put(o.id, o);
        byKey.computeIfAbsent(userId, u -> new HashMap<>()).put(key, o.id);
        history.computeIfAbsent(userId, u -> new ArrayList<>()).add(o);
        holds.add(o);
        announce("CREATED", o, after);
        return o;
    }

    /** The price of these lines for this buyer, with the coupon when there is one; a coupon that takes nothing off is refused. */
    private Quote quote(String userId, List<Line> lines, String couponCode) {
        Quote plain = pricing.price(lines);
        if (couponCode == null) return plain;
        Quote q = coupons.ruleFor(couponCode, userId, pricing).price(lines);
        if (q.totalPaise() >= plain.totalPaise())
            throw new OrderRefused(Reason.COUPON_NOT_APPLICABLE, couponCode + " takes nothing off this order");
        return q;
    }

    /**
     * End every hold whose time is up: pop the queue while its head has ended. An entry whose order was paid or
     * cancelled meanwhile is simply skipped. A hold ends AT holdUntilMs: at 4:59.999 it is still held. O(log n)
     * per order over its whole life, never a scan.
     */
    private int sweep(List<Runnable> after) {
        long now = clock.nowMs();
        int ended = 0;
        while (!holds.isEmpty() && holds.peek().holdUntilMs <= now) {
            Order o = holds.poll();
            if (o.status() != OrderStatus.PENDING_PAYMENT) continue;
            endUnpaid(o, OrderStatus.EXPIRED, after);
            ended++;
        }
        return ended;
    }

    /**
     * An unpaid order ends (EXPIRED or CANCELLED): its block and its coupon use are given back. If a charge was
     * ever sent, a refund by order id is queued to that bank, which gives back money that might have moved and
     * does nothing otherwise.
     */
    private void endUnpaid(Order o, OrderStatus end, List<Runnable> after) {
        inventory.releaseAll(o.lines);
        if (o.couponCode != null) coupons.giveBack(o.couponCode, o.userId);
        o.moveTo(end);
        if (o.chargedVia != null) refundLater(o, after);
        announce(end.name(), o, after);
    }

    /**
     * Queue a refund for after the unlock, through the bank that took the money (not whichever bank is configured
     * now). A refund that fails is kept for a retry, never forgotten.
     */
    private void refundLater(Order o, List<Runnable> after) {
        PaymentGateway bank = o.chargedVia != null ? o.chargedVia : gateway;
        after.add(() -> {
            try { bank.refund(o.id); } catch (RuntimeException e) { refundsToRetry.add(o.id); }
        });
    }

    /** The order behind an id, or a clear failure. */
    private Order find(String orderId) {
        Order o = orders.get(orderId);
        if (o == null) throw new NoSuchElementException("no order " + orderId);
        return o;
    }

    /** Build the event now, under the lock, with the next number, and queue its publishing for after the unlock. */
    private void announce(String kind, Order o, List<Runnable> after) {
        StoreEvent e = StoreEvent.of(kind, o, ++eventSeq);
        after.add(() -> publish(e));
    }

    /** Run what a locked section queued: refunds and listeners. Called only after the unlock. */
    private void runAfter(List<Runnable> after) { for (Runnable r : after) r.run(); }

    /** Tell every listener, catching anything they throw, so a broken listener cannot break an order. */
    private void publish(StoreEvent e) {
        for (StoreObserver o : observers) {
            try { o.onEvent(e); } catch (RuntimeException ex) { System.err.println("[listener failed] " + ex.getMessage()); }
        }
    }
}

/** Runs a demo of one afternoon at the store, then a hundred buyers racing for the last ten pens. */
public class Main {
    /** Paise printed as rupees. */
    static String rs(long paise) { return String.format("Rs %d.%02d", paise / 100, paise % 100); }

    /** A store stocked the way the page describes it: ten pens, five mugs, three kurtis, and two coupons. */
    static Store stocked() {
        Store s = new Store();
        s.addProduct("PEN", "Blue pen", 20_00, 10);
        s.addProduct("MUG", "Coffee mug", 299_00, 5);
        s.addProduct("KURTI", "Cotton kurti", 499_00, 3);
        s.addCoupon(new Coupon("SAVE10", 1, 1000, base -> new PercentOff(base, "SAVE10", 10, 100_00)));
        s.addCoupon(new Coupon("FLAT100", 1, 1000, base -> new FlatOff(base, "FLAT100", 100_00, 999_00)));
        return s;
    }

    /** A moment on 15 September 2026 in Kolkata, so the demo prints the same every time. */
    static long at(int hour, int minute) {
        return java.time.LocalDateTime.of(2026, 9, 15, hour, minute)
                 .atZone(java.time.ZoneId.of("Asia/Kolkata")).toInstant().toEpochMilli();
    }

    public static void main(String[] args) throws Exception {
        long[] now = { at(10, 0) };
        Store store = stocked();
        FakeGateway bank = new FakeGateway();
        store.configure(new ListPrice(), bank, Store.HOLD_MS);
        store.setClock(() -> now[0]);
        store.addObserver(new BuyerSms());

        System.out.println("-- 10:00 Asha fills her cart and checks out with SAVE10");
        store.addToCart("asha", "KURTI", 2);
        store.addToCart("asha", "MUG", 1);
        System.out.println("   cart " + store.viewCart("asha") + "; total with SAVE10 "
                           + rs(store.cartTotal("asha", "SAVE10").totalPaise()));
        Order o1 = store.checkout("asha", "tap-1", "SAVE10");
        System.out.println("   " + o1.id + " " + o1.status() + ", " + rs(o1.totalPaise()) + " " + o1.quote.discounts()
                           + "; KURTI " + store.stockOf("KURTI"));
        Order again = store.checkout("asha", "tap-1", "SAVE10");
        System.out.println("   the app retries with the same key: " + again.id + ", the same order; KURTI "
                           + store.stockOf("KURTI"));

        System.out.println("-- 10:01 she pays, and her app sends it twice");
        now[0] = at(10, 1);
        System.out.println("   " + store.confirmOrder(o1.id) + ", then " + store.confirmOrder(o1.id) + "; charged "
                           + bank.charges.get() + " time; the bank holds " + rs(bank.heldPaise()) + "; KURTI " + store.stockOf("KURTI"));

        System.out.println("-- 10:02 Ravi blocks the last kurti and never pays");
        now[0] = at(10, 2);
        Order o2 = store.createOrder("ravi", "r-1", Map.of("KURTI", 1), null);
        System.out.println("   " + o2.id + " holds it until 10:07; KURTI available " + store.getInventory("KURTI"));
        now[0] = at(10, 7);
        System.out.println("   10:07: KURTI available " + store.getInventory("KURTI") + "; " + o2.id + " is " + o2.status());

        System.out.println("-- 10:08 Meera's bank answers after her hold has ended: the money goes back");
        now[0] = at(10, 8);
        Order o3 = store.createOrder("meera", "m-1", Map.of("KURTI", 1), null);
        store.configure(new ListPrice(), new PaymentGateway() {     // a slow bank: six minutes pass during the charge
            public boolean charge(String id, long paise) { now[0] = at(10, 14); return bank.charge(id, paise); }
            public void refund(String id) { bank.refund(id); }
        }, Store.HOLD_MS);
        PayResult late = store.confirmOrder(o3.id);
        System.out.println("   " + late + "; " + o3.id + " is " + o3.status() + "; the bank holds " + rs(bank.heldPaise())
                           + "; KURTI " + store.stockOf("KURTI"));
        store.configure(new ListPrice(), bank, Store.HOLD_MS);

        System.out.println("-- one order, one line short: nothing is blocked");
        try { store.createOrder("zoya", "z-1", Map.of("PEN", 2, "KURTI", 5), null); }
        catch (OrderRefused e) { System.out.println("   refused " + e.reason + " (" + e.getMessage() + "); PEN " + store.stockOf("PEN")); }

        System.out.println("-- Asha cancels before it ships: stock back on sale, money back");
        System.out.println("   " + store.cancelOrder(o1.id) + "; KURTI " + store.stockOf("KURTI") + "; the bank holds "
                           + rs(bank.heldPaise()) + "; SAVE10 uses " + store.couponUses("SAVE10"));

        // the race: a hundred buyers press Buy for the last ten pens at the same instant
        Store sale = stocked();
        FakeGateway saleBank = new FakeGateway();
        sale.configure(new ListPrice(), saleBank, Store.HOLD_MS);
        System.out.println("-- a hundred buyers, ten pens, the same instant");
        int buyers = 100;
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(buyers);
        List<Order> won = Collections.synchronizedList(new ArrayList<>());
        AtomicInteger soldOut = new AtomicInteger();
        for (int i = 0; i < buyers; i++) {
            final String user = "buyer" + i;
            new Thread(() -> {
                try { go.await(); won.add(sale.createOrder(user, "key-" + user, Map.of("PEN", 1), null)); }
                catch (OrderRefused e) { if (e.reason == Reason.OUT_OF_STOCK) soldOut.incrementAndGet(); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done.countDown(); }
            }).start();
        }
        go.countDown();
        done.await();
        System.out.println("   orders " + won.size() + " (must be 10); out of stock " + soldOut.get() + "; PEN " + sale.stockOf("PEN"));

        CountDownLatch pay = new CountDownLatch(1), paid = new CountDownLatch(won.size());
        for (Order o : List.copyOf(won))
            new Thread(() -> {
                try { pay.await(); sale.confirmOrder(o.id); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { paid.countDown(); }
            }).start();
        pay.countDown();
        paid.await();
        System.out.println("   all ten pay at once: PEN " + sale.stockOf("PEN") + "; the bank holds " + rs(saleBank.heldPaise())
                           + " (10 x Rs 20)");
    }
}
