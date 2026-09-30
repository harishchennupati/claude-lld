import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

// Reference code for every follow-up on page 05. Each block is one twist; nothing here edits Main.java.

// ---- ext: buy X get Y --------------------------------------------------------------------------------
/**
 * "Buy two pens, get one free": for every x + y units of one SKU, y of them cost nothing. One more rule that
 * wraps the rule before it (Decorator), so the store and every other rule stay as they are.
 */
final class BuyXGetY implements PricingRule {
    private final PricingRule inner;
    private final String sku;
    private final int buy, free;

    BuyXGetY(PricingRule inner, String sku, int buy, int free) {
        if (buy < 1 || free < 1) throw new IllegalArgumentException("buy " + buy + " get " + free);
        this.inner = inner; this.sku = sku; this.buy = buy; this.free = free;
    }
    /** The wrapped price, less the free units: (qty / (buy + free)) x free x unit price. */
    public Quote price(List<Line> lines) {
        Quote q = inner.price(lines);
        for (Line l : lines)
            if (l.sku().equals(sku)) {
                long off = (long) (l.qty() / (buy + free)) * free * l.unitPaise();
                if (off > 0) q = q.less("BUY" + buy + "GET" + free + " " + sku, off);
            }
        return q;
    }
}

/**
 * Several codes on one order, but only the best one counts (Flipkart's billing task: "if P10 and P20 are both
 * applied, only the highest is used"). It prices the order with each candidate and keeps the cheapest, so
 * applying the same code twice can never stack.
 */
final class BestOf implements PricingRule {
    private final List<PricingRule> candidates;

    BestOf(List<PricingRule> candidates) { this.candidates = List.copyOf(candidates); }
    /** The candidate quote with the lowest total; the first one wins a tie. */
    public Quote price(List<Line> lines) {
        Quote best = null;
        for (PricingRule r : candidates) {
            Quote q = r.price(lines);
            if (best == null || q.totalPaise() < best.totalPaise()) best = q;
        }
        return best;
    }
}

// ---- ext: a lock per SKU -----------------------------------------------------------------------------
/**
 * Rung one of the ladder: a lock per SKU instead of one lock for the store, so buyers of different products
 * never wait for each other (Meesho's per-product locks). An order with several lines takes its SKUs' locks in
 * SKU order, always the same order, so two orders for {PEN, MUG} and {MUG, PEN} can never each hold one lock
 * and wait for the other (a deadlock). All or nothing still holds: check every line, then write every line,
 * while holding all of that order's locks.
 */
final class StripedStock {
    private final Map<String, Stock> stock = new ConcurrentHashMap<>();
    private final Map<String, ReentrantLock> locks = new ConcurrentHashMap<>();

    /** Add a SKU with its count. Setup only. */
    void add(String sku, int qty) { stock.put(sku, new Stock(qty)); locks.put(sku, new ReentrantLock()); }
    /** Available units of one SKU, under that SKU's lock only. */
    int available(String sku) {
        ReentrantLock l = locks.get(sku);
        l.lock();
        try { return stock.get(sku).available(); } finally { l.unlock(); }
    }
    /** Block every line or none. The locks are taken in SKU order and given back in reverse. */
    boolean reserveAll(List<Line> lines) {
        Map<String, Integer> need = totals(lines);                   // a SKU named twice is checked once, in total
        List<ReentrantLock> held = lockInOrder(need.keySet());
        try {
            for (Map.Entry<String, Integer> n : need.entrySet())       // check all, touch nothing
                if (stock.get(n.getKey()).available() < n.getValue()) return false;
            need.forEach((sku, n) -> stock.get(sku).reserve(n));       // then write all
            return true;
        } finally { unlock(held); }
    }
    /** Give every line's block back. */
    void releaseAll(List<Line> lines) {
        Map<String, Integer> need = totals(lines);
        List<ReentrantLock> held = lockInOrder(need.keySet());
        try { need.forEach((sku, n) -> stock.get(sku).release(n)); } finally { unlock(held); }
    }
    /** The three counts of a SKU. */
    StockView view(String sku) {
        ReentrantLock l = locks.get(sku);
        l.lock();
        try { return stock.get(sku).view(); } finally { l.unlock(); }
    }
    /** The quantity per SKU, sorted by SKU. */
    private static Map<String, Integer> totals(List<Line> lines) {
        Map<String, Integer> t = new TreeMap<>();
        for (Line l : lines) t.merge(l.sku(), l.qty(), Integer::sum);
        return t;
    }
    /** Take these SKUs' locks in sorted order: the one rule that makes a deadlock impossible. */
    private List<ReentrantLock> lockInOrder(Set<String> sortedSkus) {
        List<ReentrantLock> held = new ArrayList<>();
        for (String sku : sortedSkus) { ReentrantLock l = locks.get(sku); l.lock(); held.add(l); }
        return held;
    }
    /** Give the locks back, last taken first. */
    private static void unlock(List<ReentrantLock> held) {
        for (int i = held.size() - 1; i >= 0; i--) held.get(i).unlock();
    }
}

/**
 * Many stores on one platform (Harness's "design Shopify"): each store has its own catalogue, stock and lock,
 * so two stores never wait for each other. Splitting by store is free, because stores never share stock.
 */
final class Platform {
    private final Map<String, Store> stores = new ConcurrentHashMap<>();

    /** The store of one tenant, created on first use. */
    Store store(String storeId) { return stores.computeIfAbsent(storeId, id -> new Store()); }
}

// ---- ext: sold-out gate ------------------------------------------------------------------------------
/**
 * A flash sale: a million buyers want the same 1,000 units. A counter in front of the store lets at most as
 * many buyers in as there are units, with a compare-and-set (write the new count only if it still holds the
 * value just read, as one hardware step). Everyone else hears "sold out" in about 50 ns and never touches the
 * lock. A buyer who got in but whose order dies unpaid gives the ticket back through the listener.
 */
final class SoldOutGate implements StoreObserver {
    private final String sku;
    private final AtomicInteger tickets;

    SoldOutGate(String sku, int units) { this.sku = sku; this.tickets = new AtomicInteger(units); }
    /** Take one ticket if any is left. Never goes below zero, with no lock. */
    boolean tryEnter() { return tickets.getAndUpdate(n -> n > 0 ? n - 1 : n) > 0; }
    /** Hand a ticket back: this buyer's checkout failed, or his order died unpaid. */
    void giveBack(int n) { tickets.addAndGet(n); }
    /** Tickets left. */
    int left() { return tickets.get(); }
    /** An order holding this SKU expired or was cancelled: its units are for sale again, so are its tickets. */
    public void onEvent(StoreEvent e) {
        if (!e.kind().equals("EXPIRED") && !e.kind().equals("CANCELLED")) return;
        for (Line l : e.lines()) if (l.sku().equals(sku)) giveBack(l.qty());
    }
}

// ---- ext: background sweeper -------------------------------------------------------------------------
/**
 * Every store method already ends the holds that are due before it runs, so a busy store needs no thread for
 * it. A quiet store might go ten minutes without a call; this job calls sweepExpired every second so the stock
 * and the "your order expired" messages never wait for the next buyer. One daemon thread.
 */
final class HoldSweeper implements AutoCloseable {
    private final ScheduledExecutorService timer = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "hold-sweeper");
        t.setDaemon(true);
        return t;
    });
    final AtomicInteger ended = new AtomicInteger();

    /** Start sweeping this store every periodMs. */
    HoldSweeper(Store store, long periodMs) {
        timer.scheduleWithFixedDelay(() -> {
            try { ended.addAndGet(store.sweepExpired()); }
            catch (RuntimeException e) { System.err.println("[sweeper] " + e.getMessage()); }   // a task that throws is never run again
        }, periodMs, periodMs, TimeUnit.MILLISECONDS);
    }
    /** Stop the job. */
    public void close() { timer.shutdownNow(); }
}

// ---- ext: back in stock ------------------------------------------------------------------------------
/**
 * "Notify me when it is back": buyers who watch a sold-out SKU are told once, when units come back, whether
 * from a restock, an expired hold or a cancelled order. A listener, so the store does not change. It reads the
 * store again (listeners run after the unlock, so that is safe), and remove() on the watch list is atomic, so
 * two events racing each other tell a buyer once, not twice.
 */
final class BackInStockAlerts implements StoreObserver {
    private final Store store;
    private final Map<String, Set<String>> watchers = new ConcurrentHashMap<>();   // SKU -> buyers waiting
    final List<String> sent = new CopyOnWriteArrayList<>();

    BackInStockAlerts(Store store) { this.store = store; }
    /** A buyer asks to be told when this SKU is back. */
    void watch(String userId, String sku) { watchers.computeIfAbsent(sku, k -> ConcurrentHashMap.newKeySet()).add(userId); }
    /** Units came back to some SKUs: tell their watchers once, and forget them. */
    public void onEvent(StoreEvent e) {
        if (!Set.of("RESTOCKED", "EXPIRED", "CANCELLED").contains(e.kind())) return;
        for (Line l : e.lines()) {
            if (!watchers.containsKey(l.sku()) || store.getInventory(l.sku()) == 0) continue;
            Set<String> waiting = watchers.remove(l.sku());          // atomic: only one event gets the list
            if (waiting != null) for (String u : waiting) sent.add(u + ": " + l.sku() + " is back");
        }
    }
}

/**
 * Listeners run after the unlock, so two threads can deliver one order's events in the wrong order: the SMS
 * would say "cancelled", then "confirmed". Every event carries a number taken under the lock; this wrapper
 * passes an order's event on only when it is newer than the last one it passed for that order. compute() runs
 * one order's check-and-send as one step, so two events of the same order can never cross inside it.
 */
final class LatestOnly implements StoreObserver {
    private final StoreObserver inner;
    private final Map<String, Long> lastSeen = new ConcurrentHashMap<>();   // order id -> newest event number passed on

    LatestOnly(StoreObserver inner) { this.inner = inner; }
    /** Pass on a newer event; drop an older one. Restocks have no order and always pass. */
    public void onEvent(StoreEvent e) {
        if (e.orderId() == null) { inner.onEvent(e); return; }
        lastSeen.compute(e.orderId(), (id, last) -> {
            if (last != null && last > e.seq()) return last;                  // older than what was sent: drop it
            inner.onEvent(e);
            return e.seq();
        });
    }
}

// ---- ext: warehouses ---------------------------------------------------------------------------------
/** A warehouse or a seller's site: an id, the pincodes it delivers to, and a rank (lower = nearer, preferred). */
record Site(String id, Set<String> pincodes, int rank) {}

/** The answer to "who ships this?": a plan (site -> SKU -> units), or the reason nothing can ship. */
record Allocation(Map<String, Map<String, Integer>> plan, String refusal) {
    /** True when there is a plan. */
    boolean ok() { return plan != null; }
    /** Printed as the plan, or the refusal. */
    public String toString() { return ok() ? plan.toString() : refusal; }
}

/**
 * Which site ships which units. Behind an interface because it changes: nearest first, cheapest shipping,
 * one parcel whenever possible. Returns site -> (SKU -> qty), or null when the order cannot be filled.
 */
interface AllocationRule {
    Map<String, Map<String, Integer>> plan(Map<String, Integer> wanted, String pincode, List<Site> sites, SiteStock stock);
}

/**
 * The stock of every SKU at every site, under one lock, so "plan and reserve" is one step: two buyers can
 * never both be promised the last unit at the Pune warehouse.
 */
final class SiteStock {
    private final Map<String, Map<String, Integer>> counts = new HashMap<>();   // site -> SKU -> units
    private final List<Site> sites = new ArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();

    /** Add a site with its starting counts. Setup only. */
    void addSite(Site s, Map<String, Integer> skus) { sites.add(s); counts.put(s.id(), new HashMap<>(skus)); }
    /** Units of a SKU at a site; the caller holds the lock, or it is setup. */
    int at(String siteId, String sku) { return counts.get(siteId).getOrDefault(sku, 0); }
    /**
     * Plan with the rule and reserve the plan, under one lock. The refusals are the answers the multi-seller
     * version of the task expects: "pincode unserviceable" and "insufficient product inventory".
     */
    Allocation reserve(Map<String, Integer> wanted, String pincode, AllocationRule rule) {
        lock.lock();
        try {
            if (sites.stream().noneMatch(s -> s.pincodes().contains(pincode))) return new Allocation(null, "pincode unserviceable");
            Map<String, Map<String, Integer>> plan = rule.plan(wanted, pincode, sites, this);
            if (plan == null) return new Allocation(null, "insufficient product inventory");
            plan.forEach((site, skus) -> skus.forEach((sku, n) -> counts.get(site).merge(sku, -n, Integer::sum)));
            return new Allocation(plan, null);
        } finally { lock.unlock(); }
    }
}

/**
 * One parcel when a single site can send everything, nearest site first; otherwise split the order across the
 * sites that deliver to that pincode, nearest first. null when even all of them together are short.
 */
final class OneSiteElseSplit implements AllocationRule {
    /** The plan, or null. Reads only; SiteStock.reserve applies it. */
    public Map<String, Map<String, Integer>> plan(Map<String, Integer> wanted, String pincode, List<Site> sites, SiteStock stock) {
        List<Site> serving = new ArrayList<>();
        for (Site s : sites) if (s.pincodes().contains(pincode)) serving.add(s);
        serving.sort(Comparator.comparingInt(Site::rank));
        for (Site s : serving) {                                          // 1. one parcel, from the nearest site that has it all
            boolean all = true;
            for (Map.Entry<String, Integer> w : wanted.entrySet()) all &= stock.at(s.id(), w.getKey()) >= w.getValue();
            if (all) return Map.of(s.id(), new TreeMap<>(wanted));
        }
        Map<String, Map<String, Integer>> plan = new TreeMap<>();         // 2. split, nearest first
        for (Map.Entry<String, Integer> w : new TreeMap<>(wanted).entrySet()) {
            int need = w.getValue();
            for (Site s : serving) {
                int take = Math.min(need, stock.at(s.id(), w.getKey()));
                if (take > 0) { plan.computeIfAbsent(s.id(), k -> new TreeMap<>()).put(w.getKey(), take); need -= take; }
                if (need == 0) break;
            }
            if (need > 0) return null;
        }
        return plan;
    }
}

// ---- ext: external seller ----------------------------------------------------------------------------
/**
 * PhonePe's twist: some items belong to an external seller, and his stock is reached only through his API.
 * Every call carries our order id, so a retried call is applied once, and release is safe to repeat.
 */
interface SellerApi {
    /** Units he says are available. */
    int available(String sku);
    /** Block these lines for our order id; true = blocked. May time out. */
    boolean reserve(String orderId, Map<String, Integer> lines);
    /** Our order was paid: his blocked units are sold. */
    void confirm(String orderId);
    /** Our order died: give his block back. Does nothing when there is no block. */
    void release(String orderId);
}

/**
 * Where an order's stock comes from: our own warehouse or a seller's API. The store would pick the source by
 * the order's seller; every line of one order comes from one seller (PhonePe's rule), so no order ever needs
 * all-or-nothing across two sources.
 */
interface StockSource {
    /** Block the lines for this order id, all or none. */
    boolean reserve(String orderId, Map<String, Integer> lines);
    /** The order was paid. */
    void confirm(String orderId);
    /** The order died unpaid. */
    void release(String orderId);
}

/**
 * The external seller behind our StockSource. His reserve is a network call, so it must never run under the
 * store's lock; it runs before the order is written, like the bank's charge. A timeout means we do not know
 * whether he blocked anything, so we release by order id, which is safe either way, and refuse the order.
 */
final class ExternalSellerStock implements StockSource {
    private final SellerApi api;
    final List<String> releasesToRetry = new CopyOnWriteArrayList<>();

    ExternalSellerStock(SellerApi api) { this.api = api; }
    /** Ask the seller; a timeout is treated as "no" and undone by order id. */
    public boolean reserve(String orderId, Map<String, Integer> lines) {
        try { return api.reserve(orderId, lines); }
        catch (RuntimeException timeout) { release(orderId); return false; }
    }
    /** Tell the seller the order was paid. */
    public void confirm(String orderId) { api.confirm(orderId); }
    /** Give the seller's block back; a failed call is kept for a retry. */
    public void release(String orderId) {
        try { api.release(orderId); } catch (RuntimeException e) { releasesToRetry.add(orderId); }
    }
}

/** A seller's API in memory, keyed by our order id, that can be told to time out AFTER blocking, once. */
final class FakeSeller implements SellerApi {
    private final Map<String, Integer> stock = new ConcurrentHashMap<>();
    private final Map<String, Map<String, Integer>> blocks = new ConcurrentHashMap<>();
    volatile boolean timeoutAfterBlockOnce;

    FakeSeller(Map<String, Integer> start) { stock.putAll(start); }
    /** Units free at the seller. */
    public int available(String sku) { return stock.getOrDefault(sku, 0); }
    /** Block once per order id; a repeat is a no-op that answers true. */
    public synchronized boolean reserve(String orderId, Map<String, Integer> lines) {
        if (blocks.containsKey(orderId)) return true;
        for (Map.Entry<String, Integer> l : lines.entrySet()) if (available(l.getKey()) < l.getValue()) return false;
        lines.forEach((sku, n) -> stock.merge(sku, -n, Integer::sum));
        blocks.put(orderId, Map.copyOf(lines));
        if (timeoutAfterBlockOnce) { timeoutAfterBlockOnce = false; throw new RuntimeException("seller API timed out"); }
        return true;
    }
    /** The block becomes a sale. */
    public synchronized void confirm(String orderId) { blocks.remove(orderId); }
    /** Give a block back; nothing when there is none. */
    public synchronized void release(String orderId) {
        Map<String, Integer> b = blocks.remove(orderId);
        if (b != null) b.forEach((sku, n) -> stock.merge(sku, n, Integer::sum));
    }
}

// ---- ext: persistence --------------------------------------------------------------------------------
/**
 * The same design on a database, for many machines. The lock becomes the row: a reserve is ONE conditional
 * UPDATE that succeeds only while enough units are available, so the database decides the winner. The hold is
 * the order row's status plus hold_until, and the idempotency key is a UNIQUE index, so a retried INSERT fails
 * and the retry reads the order it already made. Redis does the same with a script that checks and takes in
 * one step, plus a key that expires, for "lock 10 pens for five minutes".
 */
final class Sql {
    static final String SCHEMA = """
        CREATE TABLE stock  (sku TEXT PRIMARY KEY, available INT NOT NULL CHECK (available >= 0),
                             reserved INT NOT NULL CHECK (reserved >= 0), sold INT NOT NULL);
        CREATE TABLE orders (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, idem_key TEXT NOT NULL,
                             status TEXT NOT NULL, total_paise BIGINT NOT NULL, hold_until TIMESTAMP NOT NULL,
                             UNIQUE (user_id, idem_key));
        CREATE TABLE order_lines (order_id TEXT, sku TEXT, qty INT, unit_paise BIGINT, PRIMARY KEY (order_id, sku));
        CREATE INDEX pending_by_hold ON orders (hold_until) WHERE status = 'PENDING_PAYMENT';""";
    /** One line of a reserve: 1 row updated = blocked; 0 rows = not enough left (another buyer got there). */
    static final String RESERVE = "UPDATE stock SET available = available - ?, reserved = reserved + ? WHERE sku = ? AND available >= ?";
    /** The sweeper: end holds that are due, and learn which ones, so their lines can be released in the same transaction. */
    static final String EXPIRE = "UPDATE orders SET status = 'EXPIRED' WHERE status = 'PENDING_PAYMENT' AND hold_until <= now() RETURNING id";
    /** Redis: check and take in one step; the hold key disappears by itself after five minutes. */
    static final String REDIS_LUA = """
        if tonumber(redis.call('GET', KEYS[1])) >= tonumber(ARGV[1]) then
          redis.call('DECRBY', KEYS[1], ARGV[1]); redis.call('SET', KEYS[2], ARGV[1], 'PX', 300000); return 1
        end
        return 0""";
    private Sql() {}
}

/**
 * The stock table in memory, with the database's guarantee: each row update is atomic
 * (ConcurrentHashMap.compute runs it as one step for that key). A multi-line reserve takes the rows in SKU
 * order, as a transaction would lock them, and undoes the lines already taken if a later one gets 0 rows,
 * which is what ROLLBACK does for you in a real database. One difference: here another caller can see those
 * lines in between and be refused; a database keeps the rows locked until COMMIT, so that caller waits instead.
 */
final class StockTable {
    private final Map<String, int[]> rows = new ConcurrentHashMap<>();   // sku -> {available, reserved, sold}

    /** INSERT one row. */
    void insert(String sku, int available) { rows.put(sku, new int[] { available, 0, 0 }); }
    /** The RESERVE statement for one line: true when exactly one row was updated. */
    boolean reserveRow(String sku, int qty) {
        boolean[] updated = { false };
        rows.computeIfPresent(sku, (k, r) -> {
            if (r[0] < qty) return r;                         // WHERE available >= ? failed: 0 rows
            updated[0] = true;
            return new int[] { r[0] - qty, r[1] + qty, r[2] };
        });
        return updated[0];
    }
    /** Give one line's block back. */
    void releaseRow(String sku, int qty) { rows.computeIfPresent(sku, (k, r) -> new int[] { r[0] + qty, r[1] - qty, r[2] }); }
    /** Every line or none: rows in SKU order; on a 0-row line, undo the earlier ones (the ROLLBACK). */
    boolean reserveAll(Map<String, Integer> lines) {
        List<Map.Entry<String, Integer>> done = new ArrayList<>();
        for (Map.Entry<String, Integer> l : new TreeMap<>(lines).entrySet()) {
            if (!reserveRow(l.getKey(), l.getValue())) {
                for (Map.Entry<String, Integer> d : done) releaseRow(d.getKey(), d.getValue());
                return false;
            }
            done.add(l);
        }
        return true;
    }
    /** available of one row. */
    int available(String sku) { return rows.get(sku)[0]; }
    /** reserved of one row. */
    int reserved(String sku) { return rows.get(sku)[1]; }
}

// ---- ext: client retry -------------------------------------------------------------------------------
/** The network lost the reply: the call may or may not have reached the store. The one error worth retrying. */
final class NetworkTimeout extends RuntimeException {
    NetworkTimeout(String message) { super(message); }
}

/** How a retry waits. Handed in, so a test does not sleep. */
interface Sleeper { void sleep(long ms) throws InterruptedException; }

/**
 * The client side of "the same order arrives twice": it retries only a timeout, never a refusal (out of
 * stock will not fix itself), waits longer each time with random jitter (full jitter: a random wait between 0
 * and base x 2^attempt, capped), so a thousand phones do not retry in step, and sends the SAME idempotency key
 * every time, so a retry of a call that did reach the store returns the order it already made.
 */
final class RetryingClient {
    private final Sleeper sleeper;
    private final Random random;
    private final int attempts;
    private final long baseMs, capMs;

    RetryingClient(Sleeper sleeper, Random random, int attempts, long baseMs, long capMs) {
        this.sleeper = sleeper; this.random = random; this.attempts = attempts; this.baseMs = baseMs; this.capMs = capMs;
    }
    /** Call until it answers, a timeout at a time; a refusal or the last timeout goes to the caller. */
    <T> T call(Supplier<T> request) throws InterruptedException {
        for (int attempt = 0; ; attempt++) {
            try { return request.get(); }
            catch (NetworkTimeout t) {
                if (attempt + 1 >= attempts) throw t;
                long ceiling = attempt >= 30 ? capMs : Math.min(capMs, baseMs << attempt);   // no overflow on a long run
                sleeper.sleep((long) (random.nextDouble() * ceiling));
            }
        }
    }
}

/** A network that loses the store's reply the first n times: the call REACHES the store, the answer does not come back. */
final class LossyLink {
    private final Store store;
    private int losses;

    LossyLink(Store store, int losses) { this.store = store; this.losses = losses; }
    /** createOrder through the link. */
    synchronized Order createOrder(String userId, String key, Map<String, Integer> wanted, String coupon) {
        Order o = store.createOrder(userId, key, wanted, coupon);
        if (losses-- > 0) throw new NetworkTimeout("reply lost for " + o.id);
        return o;
    }
}

// ---- ext: coupons from config ------------------------------------------------------------------------
/**
 * Where a Factory finally pays: coupons that arrive as lines from an admin screen or a config file, so a new
 * campaign is data, not code. "SAVE10|PERCENT|10|10000|1|1000" = 10% off, up to Rs 100, once per buyer, 1,000
 * uses; "FLAT100|FLAT|10000|99900|1|500" = Rs 100 off above Rs 999.
 */
final class CouponFactory {
    /** One config line -> one Coupon, or a clear error naming the line. */
    static Coupon fromConfig(String line) {
        String[] p = line.split("\\|");
        if (p.length != 6) throw new IllegalArgumentException("bad coupon line: " + line);
        String code = p[0];
        long a = Long.parseLong(p[2]), b = Long.parseLong(p[3]);
        int perUser = Integer.parseInt(p[4]), total = Integer.parseInt(p[5]);
        return switch (p[1]) {
            case "PERCENT" -> new Coupon(code, perUser, total, base -> new PercentOff(base, code, (int) a, b));
            case "FLAT" -> new Coupon(code, perUser, total, base -> new FlatOff(base, code, a, b));
            default -> throw new IllegalArgumentException("unknown coupon kind " + p[1] + " in " + line);
        };
    }
    private CouponFactory() {}
}

/** Runs every extension once, so the page's follow-up code is code that has actually run. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        List<Line> cart = List.of(new Line("KURTI", 2, 499_00), new Line("PEN", 3, 20_00));

        System.out.println("-- stacked rules: buy 2 get 1 on pens, then 10% (cap Rs 100), then Rs 100 off above Rs 999");
        PricingRule stack = new FlatOff(new PercentOff(new BuyXGetY(new ListPrice(), "PEN", 2, 1), "SAVE10", 10, 100_00), "FLAT100", 100_00, 999_00);
        System.out.println("   " + stack.price(cart));
        PricingRule best = new BestOf(List.of(new PercentOff(new ListPrice(), "P10", 10, 1_000_00), new PercentOff(new ListPrice(), "P20", 20, 1_000_00)));
        System.out.println("   P10 and P20 on one order, best only: " + best.price(cart));

        System.out.println("-- a lock per SKU, taken in SKU order");
        StripedStock striped = new StripedStock();
        striped.add("PEN", 10); striped.add("MUG", 5);
        System.out.println("   {MUG:5, PEN:11} -> " + striped.reserveAll(List.of(new Line("MUG", 5, 0), new Line("PEN", 11, 0)))
                           + ", PEN " + striped.view("PEN") + "; {MUG:1, PEN:1} -> " + striped.reserveAll(List.of(new Line("PEN", 1, 0), new Line("MUG", 1, 0))));
        Platform shopify = new Platform();
        shopify.store("acme").addProduct("PEN", "Blue pen", 20_00, 10);
        shopify.store("zeta").addProduct("PEN", "Red pen", 25_00, 2);
        System.out.println("   two tenants, two locks: acme PEN " + shopify.store("acme").getInventory("PEN") + ", zeta PEN " + shopify.store("zeta").getInventory("PEN"));

        System.out.println("-- the sold-out gate in front of a flash sale");
        Store sale = Main.stocked();
        SoldOutGate gate = new SoldOutGate("PEN", sale.getInventory("PEN"));
        sale.addObserver(gate);
        int in = 0, turnedAway = 0;
        for (int i = 0; i < 1000; i++) {
            if (!gate.tryEnter()) { turnedAway++; continue; }
            sale.createOrder("fan" + i, "k", Map.of("PEN", 1), null);
            in++;
        }
        System.out.println("   1000 buyers: " + in + " reached the store, " + turnedAway + " heard 'sold out' without the lock; PEN " + sale.stockOf("PEN"));

        System.out.println("-- the background sweeper ends holds even when nobody calls");
        long[] now = { Main.at(10, 0) };
        Store quiet = Main.stocked();
        quiet.setClock(() -> now[0]);
        quiet.createOrder("ravi", "r-1", Map.of("KURTI", 3), null);
        now[0] = Main.at(10, 5);
        try (HoldSweeper sweeper = new HoldSweeper(quiet, 20)) {
            for (int i = 0; i < 100 && sweeper.ended.get() == 0; i++) Thread.sleep(10);
            System.out.println("   holds ended by the job: " + sweeper.ended.get() + "; KURTI " + quiet.stockOf("KURTI"));
        }

        System.out.println("-- back in stock: told once, when a hold expires");
        now[0] = Main.at(11, 0);
        Order last = quiet.createOrder("ravi", "r-2", Map.of("KURTI", 3), null);
        BackInStockAlerts alerts = new BackInStockAlerts(quiet);
        quiet.addObserver(alerts);
        alerts.watch("meera", "KURTI");
        now[0] = Main.at(11, 6);
        quiet.getInventory("KURTI");                       // any call sweeps; the listener hears EXPIRED
        quiet.updateInventory("KURTI", 2);                 // a restock later does not tell her again
        System.out.println("   " + last.id + " " + last.status() + "; alerts sent " + alerts.sent);
        List<String> texted = new ArrayList<>();
        LatestOnly sms = new LatestOnly(e -> texted.add(e.kind()));
        sms.onEvent(new StoreEvent("CANCELLED", "O9", "asha", List.of(), 0, 7));   // event 7 is delivered first
        sms.onEvent(new StoreEvent("CONFIRMED", "O9", "asha", List.of(), 0, 6));   // the older event 6 arrives late
        System.out.println("   events 7 (CANCELLED) and then 6 (CONFIRMED) arrive; the SMS sends only " + texted);

        System.out.println("-- warehouses: one parcel when a site has it all, else split, nearest first");
        SiteStock sites = new SiteStock();
        sites.addSite(new Site("BLR-1", Set.of("560001", "560034"), 1), Map.of("PEN", 2, "MUG", 1));
        sites.addSite(new Site("BLR-2", Set.of("560034"), 2), Map.of("PEN", 5, "MUG", 5));
        AllocationRule rule = new OneSiteElseSplit();
        System.out.println("   560034 wants {PEN:1, MUG:1}: " + sites.reserve(Map.of("PEN", 1, "MUG", 1), "560034", rule));
        System.out.println("   560034 wants {PEN:6}: " + sites.reserve(Map.of("PEN", 6), "560034", rule) + "  (split: no site has six)");
        System.out.println("   560034 wants {PEN:1}: " + sites.reserve(Map.of("PEN", 1), "560034", rule));
        System.out.println("   110001 wants {PEN:1}: " + sites.reserve(Map.of("PEN", 1), "110001", rule));

        System.out.println("-- an external seller's stock, reached through his API");
        FakeSeller seller = new FakeSeller(Map.of("SAREE", 2));
        ExternalSellerStock external = new ExternalSellerStock(seller);
        System.out.println("   reserve O1: " + external.reserve("O1", Map.of("SAREE", 1)) + ", seller has " + seller.available("SAREE") + " left");
        seller.timeoutAfterBlockOnce = true;
        System.out.println("   reserve O2 times out: " + external.reserve("O2", Map.of("SAREE", 1)) + ", seller has " + seller.available("SAREE") + " left (the block was undone by order id)");

        System.out.println("-- the database decides: a conditional UPDATE per line");
        StockTable table = new StockTable();
        table.insert("MUG", 1); table.insert("PEN", 10);
        System.out.println("   {PEN:2, MUG:2}: " + table.reserveAll(Map.of("PEN", 2, "MUG", 2)) + "; PEN available " + table.available("PEN") + " (rolled back)");
        System.out.println("   {PEN:2, MUG:1}: " + table.reserveAll(Map.of("PEN", 2, "MUG", 1)) + "; PEN available " + table.available("PEN"));
        System.out.println("   " + Sql.RESERVE);

        System.out.println("-- the reply is lost twice; the client retries with the same key");
        Store shop = Main.stocked();
        LossyLink link = new LossyLink(shop, 2);
        List<Long> waits = new ArrayList<>();
        RetryingClient client = new RetryingClient(waits::add, new Random(7), 4, 100, 2_000);
        Order o = client.call(() -> link.createOrder("asha", "tap-9", Map.of("MUG", 2), null));
        System.out.println("   " + o.id + " after waits " + waits + " ms; MUG " + shop.stockOf("MUG") + " (blocked once); orders " + shop.orderHistory("asha").size());

        System.out.println("-- coupons from config lines");
        Coupon save = CouponFactory.fromConfig("SAVE10|PERCENT|10|10000|1|1000");
        Coupon flat = CouponFactory.fromConfig("FLAT100|FLAT|10000|99900|1|500");
        List<Line> small = List.of(new Line("PEN", 3, 20_00));
        System.out.println("   " + save.code() + ": " + save.discount().apply(new ListPrice()).price(cart));
        System.out.println("   " + flat.code() + " on a Rs 60 cart (below Rs 999, nothing off): " + flat.discount().apply(new ListPrice()).price(small));
    }
}
