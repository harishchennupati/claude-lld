import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: pro-rata -- "this contract allocates pro-rata". A NEW class and one configure line; the engine does not move.
/**
 * Every resting order at the level gives up a slice proportional to its size, not its place in the
 * queue. The floor leaves dust, and the dust goes down the queue in arrival order, so time priority
 * is still the tie-break. Slices below minLot are dropped: a venue will not print two-lot fills.
 */
final class ProRataAllocator implements Allocator {
    private final long minLot;
    ProRataAllocator(long minLot) { this.minLot = minLot; }

    public List<Allocation> allocate(Order taker, PriceLevel level) {
        long want = Math.min(taker.remaining(), level.totalQty());
        long resting = level.totalQty();
        Map<String, Long> give = new LinkedHashMap<>();                     // queue order, so dust is deterministic
        long given = 0;
        for (Order maker : level.queue()) {
            long share = want * maker.remaining() / resting;                // floor: quantities are lots, not money
            if (share < minLot) share = 0;
            share = Math.min(share, maker.remaining());
            if (share > 0) { give.put(maker.id(), share); given += share; }
        }
        for (Order maker : level.queue()) {                                 // the dust, first come first served
            if (given == want) break;
            long already = give.getOrDefault(maker.id(), 0L);
            long extra = Math.min(maker.remaining() - already, want - given);
            if (extra > 0) { give.put(maker.id(), already + extra); given += extra; }
        }
        List<Allocation> plan = new ArrayList<>(give.size());
        give.forEach((id, q) -> plan.add(new Allocation(id, q)));
        return plan;
    }
}
// the only change at the call site:
//   engine.configure(new ProRataAllocator(1));
// the engine still wraps it in CheckedAllocator, so a rulebook that over-allocates is caught before any write.

// ---- ext: self-trade prevention -- a member must never trade against their own resting order
/**
 * A rule that wraps another rule: it takes the plan the real allocator made, drops the lines where
 * the maker belongs to the same member as the taker, and hands the freed lots to the next orders in
 * the queue. SKIP is the common venue default; CANCEL_NEWEST and CANCEL_OLDEST need the engine to
 * remove an order, so they belong in the engine, not in a pure allocator.
 */
final class SelfTradeGuard implements Allocator {
    private final Allocator base;
    private final AtomicLong skipped = new AtomicLong();
    SelfTradeGuard(Allocator base) { this.base = base; }
    /** How many lots this guard has refused to cross. Market surveillance asks for exactly this number. */
    long skippedLots() { return skipped.get(); }

    public List<Allocation> allocate(Order taker, PriceLevel level) {
        Map<String, Long> give = new LinkedHashMap<>();
        long allocated = 0;
        for (Allocation a : base.allocate(taker, level)) {
            Order maker = level.find(a.makerOrderId());
            if (maker != null && maker.memberId().equals(taker.memberId())) { skipped.addAndGet(a.qty()); continue; }
            give.put(a.makerOrderId(), a.qty());
            allocated += a.qty();
        }
        long left = taker.remaining() - allocated;                          // give the freed lots to somebody else
        for (Order maker : level.queue()) {
            if (left == 0) break;
            if (maker.memberId().equals(taker.memberId())) continue;
            long already = give.getOrDefault(maker.id(), 0L);
            long extra = Math.min(maker.remaining() - already, left);
            if (extra > 0) { give.put(maker.id(), already + extra); left -= extra; }
        }
        List<Allocation> plan = new ArrayList<>(give.size());
        give.forEach((id, q) -> plan.add(new Allocation(id, q)));
        return plan;
    }
}

// ---- ext: iceberg -- show 100 of 10,000 at a time, and refresh when the slice is gone
/**
 * An iceberg is not a new kind of order in the book: it is a small child order that keeps coming
 * back. This listener watches for its visible slice being exhausted and sends the next one, which
 * joins the BACK of the queue -- the price a hidden order pays for hiding.
 */
final class Iceberg implements BookListener {
    private final MatchingEngine engine;
    private final String baseId, symbol, memberId;
    private final Side side;
    private final long priceTicks, showQty;
    private long hidden;
    private volatile String visibleId;
    private int slice;

    Iceberg(MatchingEngine engine, String baseId, String symbol, String memberId, Side side,
            long priceTicks, long totalQty, long showQty) {
        this.engine = engine; this.baseId = baseId; this.symbol = symbol; this.memberId = memberId;
        this.side = side; this.priceTicks = priceTicks; this.hidden = totalQty; this.showQty = showQty;
    }
    /** Put the first slice in the book. */
    void start() { engine.addListener(this); showNext(); }
    /** Lots still hidden behind the displayed slice. */
    long hidden() { return hidden; }
    /** The id of the slice currently resting, or null when the iceberg is done. */
    String visibleId() { return visibleId; }

    public void onTrade(Trade t) {
        String mine = visibleId;
        if (mine == null) return;
        if (!mine.equals(t.buyOrderId()) && !mine.equals(t.sellOrderId())) return;
        if (engine.resting(mine) == null) showNext();                       // the slice is gone: show the next one
    }
    private void showNext() {
        if (hidden <= 0) { visibleId = null; return; }
        long q = Math.min(showQty, hidden);
        hidden -= q;
        visibleId = baseId + "#" + (++slice);
        engine.submit(Order.limit(visibleId, symbol, memberId, side, priceTicks, q));
    }
}

// ---- ext: stop orders -- parked until the last traded price crosses a trigger, then submitted for real
/**
 * A stop order is not in the book: it is parked in a side table and becomes an ordinary order the
 * moment a trade prints through its trigger. The table is two sorted maps, so finding everything
 * that fired is O(number fired), not O(number parked).
 */
final class StopBook implements BookListener {
    private final MatchingEngine engine;
    private final NavigableMap<Long, List<Order>> buyStops = new TreeMap<>();                      // fire when last >= key
    private final NavigableMap<Long, List<Order>> sellStops = new TreeMap<>(Comparator.reverseOrder()); // fire when last <= key
    StopBook(MatchingEngine engine) { this.engine = engine; engine.addListener(this); }

    /** Park an order until the tape prints through triggerTicks. */
    synchronized void park(long triggerTicks, Order o) {
        (o.side() == Side.BUY ? buyStops : sellStops).computeIfAbsent(triggerTicks, k -> new ArrayList<>()).add(o);
    }
    /** How many orders are still parked. */
    synchronized int parked() { return buyStops.values().stream().mapToInt(List::size).sum()
                                    + sellStops.values().stream().mapToInt(List::size).sum(); }

    public void onTrade(Trade t) {
        List<Order> fired = new ArrayList<>();
        synchronized (this) {
            while (!buyStops.isEmpty() && buyStops.firstKey() <= t.priceTicks()) fired.addAll(buyStops.pollFirstEntry().getValue());
            while (!sellStops.isEmpty() && sellStops.firstKey() >= t.priceTicks()) fired.addAll(sellStops.pollFirstEntry().getValue());
        }
        for (Order o : fired) engine.submit(o);                             // outside the book's lock: this is a listener
    }
}

// ---- ext: cancel-replace -- who keeps their place in the queue
/**
 * Shrinking a resting order keeps its queue place, because the order object never leaves the queue.
 * Raising the quantity or moving the price is a cancel and a new order, and the new order joins the
 * back. Every venue works this way, and every trader is annoyed by it.
 */
final class Replace {
    /** Returns what happened, in the words a trader would use. */
    static String replace(MatchingEngine engine, String orderId, String newId, long newPriceTicks, long newQty) {
        Order live = engine.resting(orderId);
        if (live == null) return "gone: it filled or was already cancelled";
        if (newPriceTicks == live.limitTicks() && newQty < live.remaining()
                && engine.amendDown(orderId, newQty)) return "amended down, queue place kept";
        if (!engine.cancel(orderId)) return "gone: it filled while we were replacing it";
        engine.submit(Order.limit(newId, live.symbol(), live.memberId(), live.side(), newPriceTicks, newQty));
        return "cancel and new, queue place lost";
    }
}

// ---- ext: the journal -- every command, in order, so the book can be rebuilt exactly
/**
 * What is written down is the COMMAND, not the book: every accepted order and every cancel, with the
 * sequence number the engine gave it. Replaying the commands into a fresh engine reproduces the same
 * trades, in the same order, because nothing in matching reads the wall clock or a random number.
 */
final class Journal implements BookListener {
    /** One recorded command. A cancel carries only the id. */
    record Entry(long n, String kind, String orderId, String symbol, String memberId, Side side,
                 OrderType type, TimeInForce tif, long priceTicks, long qty) {}
    private final List<Entry> log = Collections.synchronizedList(new ArrayList<>());
    private final AtomicLong n = new AtomicLong();

    public void onAccepted(Order o) {
        log.add(new Entry(n.incrementAndGet(), "SUBMIT", o.id(), o.symbol(), o.memberId(),
                          o.side(), o.type(), o.tif(), o.limitTicks(), o.qty()));
    }
    /** Called by the gateway when it asks for a cancel; the engine's own events cannot tell a user cancel from an IOC kill. */
    void cancelled(String orderId) { log.add(new Entry(n.incrementAndGet(), "CANCEL", orderId, null, null, null, null, null, 0, 0)); }
    /** Everything recorded, in order. */
    List<Entry> log() { return List.copyOf(log); }

    /** Rebuild a book from the log and return its tape. The tapes must match, trade for trade. */
    static ConsoleTape replay(List<Entry> log, long tickSize, long lotSize, String symbol) {
        MatchingEngine fresh = new MatchingEngine(symbol, tickSize, lotSize);
        ConsoleTape tape = new ConsoleTape();
        fresh.addListener(tape);
        for (Entry e : log) {
            if (e.kind().equals("CANCEL")) fresh.cancel(e.orderId());
            else fresh.submit(new Order(e.orderId(), e.symbol(), e.memberId(), e.side(), e.type(), e.tif(), e.priceTicks(), e.qty()));
        }
        return tape;
    }
}

// ---- ext: risk -- somebody new wants to know, and it costs one class
/**
 * Per-member net position, kept from the tape. It learns which member owns which order from
 * onAccepted, then adds and subtracts as trades print. It observes; it cannot stop a trade, which is
 * why real pre-trade risk sits in front of the engine, not behind it.
 */
final class RiskMonitor implements BookListener {
    private final Map<String, String> memberOf = new ConcurrentHashMap<>();
    private final Map<String, Long> position = new ConcurrentHashMap<>();
    private final long limitLots;
    private final List<String> alarms = Collections.synchronizedList(new ArrayList<>());
    RiskMonitor(long limitLots) { this.limitLots = limitLots; }

    public void onAccepted(Order o) { memberOf.put(o.id(), o.memberId()); }
    public void onTrade(Trade t) { move(memberOf.get(t.buyOrderId()), t.qty()); move(memberOf.get(t.sellOrderId()), -t.qty()); }
    private void move(String member, long lots) {
        if (member == null) return;
        long now = position.merge(member, lots, Long::sum);
        if (Math.abs(now) > limitLots) alarms.add(member + " is at " + now + " lots, over the " + limitLots + " limit");
    }
    /** A member's net position in lots: positive is long. */
    long positionOf(String member) { return position.getOrDefault(member, 0L); }
    /** Every limit breach seen so far. */
    List<String> alarms() { return List.copyOf(alarms); }
}

// ---- ext: the single writer -- the top rung of the ladder, where the lock disappears
/**
 * One thread owns the book and takes orders off a queue, so there is no contention left to lock
 * against. The caller gets a Future instead of an answer. This is what a production venue does, and
 * the only thing that changes is who calls submit().
 */
final class SingleWriter implements AutoCloseable {
    private final MatchingEngine engine;
    private final BlockingQueue<FutureTask<SubmitResult>> inbox = new ArrayBlockingQueue<>(4096);
    private final Thread writer;
    private volatile boolean running = true;

    SingleWriter(MatchingEngine engine) {
        this.engine = engine;
        this.writer = new Thread(this::drain, "book-writer");
        writer.setDaemon(true);
        writer.start();
    }
    /** Hand the order to the writer thread. The Future completes when the book has processed it. */
    Future<SubmitResult> submit(Order o) {
        FutureTask<SubmitResult> task = new FutureTask<>(() -> engine.submit(o));
        if (!inbox.offer(task)) throw new IllegalStateException("inbox full: back-pressure, tell the gateway to slow down");
        return task;
    }
    private void drain() {
        while (running) {
            try { FutureTask<SubmitResult> t = inbox.poll(50, TimeUnit.MILLISECONDS); if (t != null) t.run(); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); return; }
        }
    }
    public void close() { running = false; writer.interrupt(); }
}

// ---- ext: the race -- what the lock is actually preventing, in eight lines
/**
 * The gap, with the window widened to three milliseconds so it happens every time: two takers both
 * read "100 lots available", both decide to take 100, and both write. The venue sold two hundred
 * lots of a hundred-lot order. This is the whole argument for the lock.
 */
final class RaceDemo {
    /** Lots sold against a single 100-lot resting order, with no lock. Returns 200. */
    static long unguarded() throws InterruptedException { return run(null); }
    /** The same two takers, with one lock around read-and-write. Returns 100. */
    static long guarded() throws InterruptedException { return run(new java.util.concurrent.locks.ReentrantLock()); }

    private static long run(java.util.concurrent.locks.ReentrantLock lock) throws InterruptedException {
        long[] remaining = { 100 };
        AtomicLong sold = new AtomicLong();
        Runnable taker = () -> {
            if (lock != null) lock.lock();
            try {
                long saw = remaining[0];                                     // READ: "100 available"
                if (lock == null) try { Thread.sleep(3); } catch (InterruptedException ignored) {}
                if (saw >= 100) { remaining[0] = saw - 100; sold.addAndGet(100); }   // WRITE: "take 100"
            } finally { if (lock != null) lock.unlock(); }
        };
        Thread a = new Thread(taker), b = new Thread(taker);
        a.start(); b.start(); a.join(); b.join();
        return sold.get();
    }
}

/** Runs every extension once, so the reference code on page 05 is code that has actually executed. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        long TICK = 5, LOT = 1;

        // 1. pro-rata: the same level, two rulebooks, two different answers
        for (String rule : new String[] { "price-time", "pro-rata" }) {
            MatchingEngine e = new MatchingEngine("NIFTY", TICK, LOT);
            if (rule.equals("pro-rata")) e.configure(new ProRataAllocator(1));
            e.submit(Order.limit("m1", "NIFTY", "ANA", Side.SELL, Ticks.of("100.00"), 100));
            e.submit(Order.limit("m2", "NIFTY", "BEN", Side.SELL, Ticks.of("100.00"), 900));
            SubmitResult r = e.submit(Order.limit("taker", "NIFTY", "CHE", Side.BUY, Ticks.of("100.00"), 500));
            StringBuilder sb = new StringBuilder();
            for (Trade t : r.trades()) sb.append(t.sellOrderId()).append("=").append(t.qty()).append(" ");
            System.out.println(String.format("%-10s", rule) + " a 500-lot taker against 100 + 900 resting -> " + sb);
        }

        // 2. self-trade prevention: the member's own order is skipped and the lots go to somebody else
        MatchingEngine stp = new MatchingEngine("INFY", TICK, LOT);
        SelfTradeGuard guard = new SelfTradeGuard(new PriceTimeAllocator());
        stp.configure(guard);
        stp.submit(Order.limit("own", "INFY", "ANA", Side.SELL, Ticks.of("1500.00"), 300));
        stp.submit(Order.limit("other", "INFY", "BEN", Side.SELL, Ticks.of("1500.00"), 300));
        SubmitResult self = stp.submit(Order.limit("mine", "INFY", "ANA", Side.BUY, Ticks.of("1500.00"), 300));
        System.out.println("self-trade traded with " + self.trades().get(0).sellOrderId() + ", skipped "
                + guard.skippedLots() + " of ANA's own lots; ANA still rests " + stp.resting("own").remaining());

        // 3. iceberg: 1000 lots shown 100 at a time
        MatchingEngine ice = new MatchingEngine("TCS", TICK, LOT);
        Iceberg berg = new Iceberg(ice, "ice", "TCS", "DEV", Side.SELL, Ticks.of("3000.00"), 1000, 100);
        berg.start();
        System.out.println("iceberg    shows " + ice.restingQty(Side.SELL) + " lots, hides " + berg.hidden());
        ice.submit(Order.limit("eat", "TCS", "ESH", Side.BUY, Ticks.of("3000.00"), 250));
        System.out.println("iceberg    after a 250-lot buy: shown " + ice.restingQty(Side.SELL)
                + ", hidden " + berg.hidden() + ", visible slice " + berg.visibleId());

        // 4. stop orders: parked until the tape prints through the trigger
        MatchingEngine stops = new MatchingEngine("SBIN", TICK, LOT);
        StopBook table = new StopBook(stops);
        table.park(Ticks.of("795.00"), Order.market("stop1", "SBIN", "FIR", Side.SELL, 50));
        stops.submit(Order.limit("bid1", "SBIN", "GIR", Side.BUY, Ticks.of("799.00"), 500));
        stops.submit(Order.limit("ask1", "SBIN", "HAR", Side.SELL, Ticks.of("799.00"), 10));
        System.out.println("stop       a trade printed at 799.00, trigger is 795.00, still parked: " + table.parked());
        stops.cancel("bid1");                                               // the bid walks away, the price falls
        stops.submit(Order.limit("bid2", "SBIN", "IND", Side.BUY, Ticks.of("794.00"), 500));
        stops.submit(Order.limit("ask2", "SBIN", "JAY", Side.SELL, Ticks.of("794.00"), 10));
        System.out.println("stop       a trade printed at 794.00: parked " + table.parked()
                + ", and the fired 50-lot market sell left " + stops.restingQty(Side.BUY) + " lots bid (was 500)");

        // 5. cancel-replace: shrink keeps the place, everything else loses it
        MatchingEngine rep = new MatchingEngine("HDFC", TICK, LOT);
        rep.submit(Order.limit("first", "HDFC", "KAV", Side.BUY, Ticks.of("1600.00"), 500));
        rep.submit(Order.limit("second", "HDFC", "LAL", Side.BUY, Ticks.of("1600.00"), 500));
        System.out.println("replace    shrink:  " + Replace.replace(rep, "first", "first-b", Ticks.of("1600.00"), 300));
        System.out.println("replace    raise:   " + Replace.replace(rep, "first", "first-c", Ticks.of("1600.00"), 900));
        SubmitResult who = rep.submit(Order.limit("seller", "HDFC", "MEE", Side.SELL, Ticks.of("1600.00"), 100));
        System.out.println("replace    the next fill went to " + who.trades().get(0).buyOrderId() + " (it is in front now)");

        // 6. journal and replay: the same commands, the same tape
        MatchingEngine live = new MatchingEngine("WIPRO", TICK, LOT);
        Journal journal = new Journal();
        ConsoleTape liveTape = new ConsoleTape();
        live.addListener(journal); live.addListener(liveTape);
        live.submit(Order.limit("j0", "WIPRO", "ANA", Side.BUY, Ticks.of("400.10"), 100));
        live.submit(Order.limit("j1", "WIPRO", "BEN", Side.BUY, Ticks.of("400.00"), 300));
        live.submit(Order.limit("j2", "WIPRO", "CHE", Side.BUY, Ticks.of("400.05"), 200));
        live.cancel("j1"); journal.cancelled("j1");
        live.submit(Order.limit("j3", "WIPRO", "DEV", Side.SELL, Ticks.of("399.00"), 500));
        ConsoleTape replayed = Journal.replay(journal.log(), TICK, LOT, "WIPRO");
        System.out.println("journal    " + journal.log().size() + " commands, live tape " + liveTape.printed().size()
                + " trades, replayed tape " + replayed.printed().size()
                + ", identical=" + liveTape.printed().toString().equals(replayed.printed().toString()));

        // 7. risk: one more listener, and nothing else changes
        MatchingEngine risky = new MatchingEngine("ITC", TICK, LOT);
        RiskMonitor risk = new RiskMonitor(400);
        risky.addListener(risk);
        risky.submit(Order.limit("s", "ITC", "SELLER", Side.SELL, Ticks.of("450.00"), 1000));
        risky.submit(Order.limit("b", "ITC", "BUYER", Side.BUY, Ticks.of("450.00"), 500));
        System.out.println("risk       BUYER is " + risk.positionOf("BUYER") + " lots, SELLER " + risk.positionOf("SELLER")
                + ", alarms " + risk.alarms());

        // 8. the single writer: no contention left to lock against
        MatchingEngine shard = new MatchingEngine("ONGC", TICK, LOT);
        try (SingleWriter writer = new SingleWriter(shard)) {
            List<Future<SubmitResult>> sent = new ArrayList<>();
            for (int i = 0; i < 20; i++)
                sent.add(writer.submit(Order.limit("w" + i, "ONGC", "M" + i,
                        i % 2 == 0 ? Side.BUY : Side.SELL, Ticks.of("200.00"), 100)));
            long filled = 0;
            for (Future<SubmitResult> f : sent) filled += f.get(5, TimeUnit.SECONDS).filledQty();
            System.out.println("writer     20 orders through one thread, " + filled + " lots filled, lock never contended");
        }

        // 9. the race the lock prevents
        System.out.println("race       no lock: " + RaceDemo.unguarded() + " lots sold from a 100-lot order;  with the lock: "
                + RaceDemo.guarded());
    }
}
