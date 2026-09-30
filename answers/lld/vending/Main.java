import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.time.*;

/**
 * The coins and notes the machine accepts. Each is worth a fixed number of paise (100 paise = one rupee),
 * so all money in this file is an int and never a double.
 */
enum Coin {
    R1(100), R2(200), R5(500), R10(1000), R20(2000);
    final int paise;
    Coin(int paise) { this.paise = paise; }
    /** What a handful of coins is worth, in paise. */
    static int total(Collection<Coin> coins) {
        int sum = 0;
        for (Coin c : coins) sum += c.paise;
        return sum;
    }
    /** The denominations from biggest to smallest: the order change-making walks. */
    static List<Coin> descending() {
        List<Coin> all = new ArrayList<>(List.of(values()));
        all.sort((a, b) -> b.paise - a.paise);
        return all;
    }
}

/**
 * A catalogue entry: what the thing is and what it lists for. Slots point at products; a product can sit
 * in many machines, so it is referenced, never owned.
 */
record Product(String sku, String name, int listPaise) {}

/**
 * One column of the machine: the code you press, the product behind it, and how many are left. The count
 * is only ever read or written under the machine's lock.
 */
final class Slot {
    final String code;
    final Product product;
    final int capacity;
    private int qty;                                   // guarded by VendingMachine.lock

    Slot(String code, Product product, int capacity, int qty) {
        this.code = code; this.product = product; this.capacity = capacity; this.qty = qty;
    }
    /** How many are left. Under the machine's lock. */
    int qty() { return qty; }
    /** Take one off the coil. Called only after the item has physically dropped, so it can never lose stock. */
    void takeOne() {
        if (qty <= 0) throw new IllegalStateException("slot " + code + " is empty");
        qty--;
    }
    /** Operator refill, capped by the column's capacity. Returns how many actually went in; a negative n is refused. */
    int refill(int n) {
        if (n < 0) throw new IllegalArgumentException("cannot refill " + n + " into " + code);
        int room = Math.min(n, capacity - qty);
        qty += room;
        return room;
    }
}

/**
 * All the slots, keyed by the code on the keypad, so "what is behind A1?" is one map lookup. Owned by the
 * machine and guarded by its lock.
 */
final class Inventory {
    private final Map<String, Slot> slots = new HashMap<>();

    /** Install a column. Setup and operator only. */
    void addSlot(Slot s) { slots.put(s.code, s); }
    /** The slot behind a code, or null when no such code exists. O(1). */
    Slot slot(String code) { return slots.get(code); }
    /** Every slot's remaining count, for an operator screen. */
    Map<String, Integer> counts() {
        Map<String, Integer> out = new TreeMap<>();
        for (Slot s : slots.values()) out.put(s.code, s.qty());
        return out;
    }
}

/**
 * The coin float: how many of each denomination the machine is holding to give as change. An EnumMap, so
 * every count is one array index. Owned by the machine and guarded by its lock.
 */
final class CoinBox {
    private final Map<Coin, Integer> counts = new EnumMap<>(Coin.class);

    CoinBox() { for (Coin c : Coin.values()) counts.put(c, 0); }
    /** Operator load. Setup and refill only; a negative n is refused, so no count can go below zero. */
    void load(Coin c, int n) {
        if (n < 0) throw new IllegalArgumentException("cannot load " + n + " x " + c);
        counts.merge(c, n, Integer::sum);
    }
    /** Absorb coins into the float. Called on a committed sale, never before. */
    void deposit(Collection<Coin> coins) { for (Coin c : coins) counts.merge(c, 1, Integer::sum); }
    /** Pay coins out of the float. Throws if a coin is not there, which would mean the plan was stale. */
    void withdraw(Collection<Coin> coins) {
        for (Coin c : coins) {
            int n = counts.get(c);
            if (n == 0) throw new IllegalStateException("float has no " + c);
            counts.put(c, n - 1);
        }
    }
    /** How many of one denomination are in the float. O(1). */
    int count(Coin c) { return counts.get(c); }
    /** What the float is worth, in paise. O(number of denominations) = O(5). */
    int totalPaise() {
        int sum = 0;
        for (Map.Entry<Coin, Integer> e : counts.entrySet()) sum += e.getKey().paise * e.getValue();
        return sum;
    }
    /** A copy of the counts, for an operator screen. */
    Map<Coin, Integer> snapshot() { return new EnumMap<>(counts); }
    /**
     * A copy of float PLUS the coins still in escrow: everything change could be made from. Pure, so the
     * machine can ask "could I make this change?" without ever touching the float.
     */
    Map<Coin, Integer> poolWith(Collection<Coin> escrow) {
        Map<Coin, Integer> pool = new EnumMap<>(counts);
        for (Coin c : escrow) pool.merge(c, 1, Integer::sum);
        return pool;
    }
}

/** How a press of a slot ended. The display shows this; it is not an error unless the machine says so. */
enum Status { SOLD, SOLD_OUT, UNKNOWN_SLOT, NEED_MORE, NO_CHANGE, JAMMED, COLLECTED }

/**
 * What a press produced: the outcome, whatever is now waiting in the tray, the coins that came with it, and
 * a number whose meaning depends on the status (NEED_MORE: how much is still short; everything else: the
 * paise in the coins). Items is a LIST because the tray keeps everything until somebody reaches in.
 */
record Outcome(Status status, List<Product> items, List<Coin> coins, int paise) {
    /** True only when an item actually dropped. */
    boolean sold() { return status == Status.SOLD; }
    /** The first item, or null when nothing dropped: the shorthand every caller and test wants. */
    Product item() { return items.isEmpty() ? null : items.get(0); }
}

/**
 * The bin behind the flap: everything waiting for the customer's hand. Items and their change after a sale,
 * refunded coins after a cancel, a refusal or a timed-out escrow. It KEEPS them: a second sale never
 * overwrites the bar the last customer forgot. Owned by the machine, guarded by its lock.
 */
final class Tray {
    private final List<Product> items = new ArrayList<>();
    private final List<Coin> coins = new ArrayList<>();

    /** Drop a sold item and its change in, on top of anything already waiting. */
    void put(Product p, List<Coin> change) { items.add(p); coins.addAll(change); }
    /** Drop coins in with no item: a cancel, a refusal, or an escrow that timed out. */
    void putCoins(List<Coin> back) { coins.addAll(back); }
    /** Nothing to pick up. */
    boolean isEmpty() { return items.isEmpty() && coins.isEmpty(); }
    /** Empty the whole bin into the customer's hand. Throws when there is nothing there. */
    Outcome take() {
        if (isEmpty()) throw new IllegalStateException("the tray is empty");
        Outcome o = new Outcome(Status.COLLECTED, List.copyOf(items), List.copyOf(coins), Coin.total(coins));
        items.clear(); coins.clear();
        return o;
    }
}

/** The four modes the machine can be in. A mode decides which actions are legal, nothing else. */
enum MachineState { IDLE, HAS_MONEY, DISPENSING, OUT_OF_SERVICE }

/** Everything a customer or an operator can do to the machine. PURCHASE is the one-step buy: coins and press together. */
enum Action { INSERT, SELECT, CANCEL, COLLECT, SERVICE, PURCHASE }

/**
 * Which actions are legal in which mode: a table, not an if-chain, so a new mode is one more row and no
 * existing line is edited. Anything not in the row is refused loudly. PURCHASE is only in the IDLE row:
 * while a walk-up customer's coins are in, a one-step buyer is refused instead of spending them.
 */
final class Legal {
    static final Map<MachineState, Set<Action>> ALLOWED = new EnumMap<>(MachineState.class);
    static {
        ALLOWED.put(MachineState.IDLE,           EnumSet.of(Action.INSERT, Action.CANCEL, Action.COLLECT, Action.SERVICE, Action.PURCHASE));
        ALLOWED.put(MachineState.HAS_MONEY,      EnumSet.of(Action.INSERT, Action.SELECT, Action.CANCEL, Action.COLLECT));
        ALLOWED.put(MachineState.DISPENSING,     EnumSet.noneOf(Action.class));
        ALLOWED.put(MachineState.OUT_OF_SERVICE, EnumSet.of(Action.CANCEL, Action.COLLECT, Action.SERVICE));
    }
    private Legal() {}
}

/** Where time comes from. Handed in, so a test can say "16:30 on a Tuesday" and prices are replayable. */
interface Clock { long nowMs(); }

/** What a slot costs right now. Behind an interface because it WILL change mid-round: offers, happy hour. */
interface PricingStrategy { int priceOf(Slot s); }

/** The plain rule: the price printed on the column. */
final class ListPrice implements PricingStrategy {
    /** The product's list price, in paise. */
    public int priceOf(Slot s) { return s.product.listPaise(); }
}

/**
 * A rule that WRAPS another rule instead of replacing it: the wrapped price, minus a percentage, between
 * two hours of the day. The hour comes from the handed-in clock, never from the wall clock.
 */
final class HappyHourDiscount implements PricingStrategy {
    private final PricingStrategy base;
    private final Clock clock;
    private final int fromHour, toHour, offPercent;
    private final ZoneId zone = ZoneId.of("Asia/Kolkata");

    HappyHourDiscount(PricingStrategy base, Clock clock, int fromHour, int toHour, int offPercent) {
        if (offPercent < 0 || offPercent > 100) throw new IllegalArgumentException("discount of " + offPercent + "%");
        this.base = base; this.clock = clock; this.fromHour = fromHour; this.toHour = toHour; this.offPercent = offPercent;
    }
    /**
     * The base price, less the discount when the clock says we are inside the window, rounded DOWN to a
     * whole rupee: the smallest coin is Rs 1, so a price like Rs 21.25 could never be paid or changed.
     */
    public int priceOf(Slot s) {
        int price = base.priceOf(s);
        int hour = Instant.ofEpochMilli(clock.nowMs()).atZone(zone).getHour();
        if (hour < fromHour || hour >= toHour) return price;
        int cut = price - (price * offPercent) / 100;
        return cut - cut % Coin.R1.paise;                    // 15% off Rs 25 is Rs 21, in the customer's favour
    }
}

/**
 * How change is made. Given what coins are available and how much is owed, hand back a list of coins, or
 * null when it cannot be done. PURE: it never touches the float, so a refusal costs nothing.
 */
interface ChangeStrategy { List<Coin> plan(Map<Coin, Integer> available, int amountPaise); }

/** Biggest coin first, one pass, no going back. Fast, and enough while the float is well stocked. */
final class GreedyChange implements ChangeStrategy {
    /** One pass biggest-first; null when the remainder cannot be finished. */
    public List<Coin> plan(Map<Coin, Integer> available, int amountPaise) {
        List<Coin> out = new ArrayList<>();
        int left = amountPaise;
        for (Coin c : Coin.descending()) {
            int take = Math.min(available.getOrDefault(c, 0), left / c.paise);
            for (int i = 0; i < take; i++) out.add(c);
            left -= take * c.paise;
        }
        return left == 0 ? List.copyOf(out) : null;
    }
}

/**
 * Biggest coin first, but it puts a coin back and tries again when the tail dead-ends. This is the default:
 * a real float is lopsided, and greedy alone refuses sales the machine could complete.
 */
final class BackoffChange implements ChangeStrategy {
    /** A list of coins worth exactly the amount, or null when no combination of what is there adds up. */
    public List<Coin> plan(Map<Coin, Integer> available, int amountPaise) {
        List<Coin> out = new ArrayList<>();
        return fill(Coin.descending(), 0, available, amountPaise, out) ? List.copyOf(out) : null;
    }
    /** Take as many of coin i as fit, then fewer, then fewer: the first tail that reaches zero wins. */
    private boolean fill(List<Coin> denoms, int i, Map<Coin, Integer> have, int left, List<Coin> out) {
        if (left == 0) return true;
        if (i == denoms.size()) return false;
        Coin c = denoms.get(i);
        int max = Math.min(have.getOrDefault(c, 0), left / c.paise);
        for (int k = max; k >= 0; k--) {
            for (int j = 0; j < k; j++) out.add(c);
            if (fill(denoms, i + 1, have, left - k * c.paise, out)) return true;
            for (int j = 0; j < k; j++) out.remove(out.size() - 1);
        }
        return false;
    }
}

/**
 * The motor behind a column: it turns the coil and the item falls. The one irreversible thing the machine
 * does, and the one thing that can fail physically. Handed in, so tests can jam it.
 */
interface Dispenser { boolean drop(String slotCode); }

/** The real motor. In this model it always turns. */
final class Motor implements Dispenser {
    /** Turn the coil behind a code; true when the item fell. */
    public boolean drop(String slotCode) { return true; }
}

/** Something worth telling a screen or an operator about, taken as a snapshot inside the lock. */
record MachineEvent(String kind, String slotCode, int qtyLeft, int floatPaise) {}

/**
 * Anyone who wants to hear what the machine did. Called after the lock is released, never inside it, on
 * whichever thread made the sale, so two calls can overlap: an observer keeps its own state thread-safe.
 */
interface MachineObserver { void onEvent(MachineEvent e); }

/** The screen on the front. Prints what happened. */
final class Display implements MachineObserver {
    /** Show the event. */
    public void onEvent(MachineEvent e) {
        System.out.println("   [display] " + e.kind() + " " + e.slotCode() + ", " + e.qtyLeft()
                           + " left, float " + Main.rs(e.floatPaise()));
    }
}

/** The operator's pager: it only cares about a column that just hit zero. */
final class RestockAlert implements MachineObserver {
    final List<String> empty = Collections.synchronizedList(new ArrayList<>());   // two sales can report at once
    /** Record and print a column that just ran out. */
    public void onEvent(MachineEvent e) {
        if (e.qtyLeft() == 0 && e.kind().equals("SOLD")) {
            empty.add(e.slotCode());
            System.out.println("   [restock alert] " + e.slotCode() + " is empty");
        }
    }
}

/**
 * The machine: the only owner of the slots, the coin float, the escrow and the tray, and the only holder
 * of the lock that guards them. Every entry point is one critical section, and nothing is committed until
 * the item has physically dropped.
 */
final class VendingMachine {
    /** How long coins may sit unspent after the customer's last coin or press, before the machine hands them back. */
    static final long ESCROW_TIMEOUT_MS = 30_000;

    private final Inventory inventory = new Inventory();
    private final CoinBox coinBox = new CoinBox();
    private final Tray tray = new Tray();
    private final List<Coin> escrow = new ArrayList<>();          // what this customer has put in, not yet ours
    private long lastTouchMs;                                     // when this customer last pushed a coin or pressed a code
    private final ReentrantLock lock = new ReentrantLock();
    private final List<MachineObserver> observers = new CopyOnWriteArrayList<>();
    private MachineState state = MachineState.IDLE;
    private PricingStrategy pricing = new ListPrice();
    private ChangeStrategy changeRule = new BackoffChange();
    private Dispenser motor = new Motor();
    private Clock clock = System::currentTimeMillis;

    /**
     * Hand in the rules. The machine never builds one itself, so a new offer or a new change algorithm is
     * a new file and this one line. Under the lock, so a rule switched on a running machine is seen whole.
     */
    void configure(PricingStrategy p, ChangeStrategy c, Dispenser d) {
        lock.lock();
        try { pricing = p; changeRule = c; motor = d; } finally { lock.unlock(); }
    }
    /** Tests and replays hand in their own clock. */
    void setClock(Clock c) { lock.lock(); try { clock = c; } finally { lock.unlock(); } }
    /** Subscribe a screen, a pager, a telemetry sink. */
    void addObserver(MachineObserver o) { observers.add(o); }
    /** Install a column. */
    void addSlot(Slot s) { lock.lock(); try { inventory.addSlot(s); } finally { lock.unlock(); } }

    // ---------------- the customer's four buttons ----------------

    /** Push a coin into the slot. It sits in escrow: it is not the machine's money until a sale commits. */
    void insertCoin(Coin c) {
        lock.lock();
        try {
            expireEscrow();
            require(Action.INSERT);
            escrow.add(c);
            lastTouchMs = clock.nowMs();                     // every coin restarts the thirty seconds
            state = MachineState.HAS_MONEY;
        } finally { lock.unlock(); }
    }

    /** Press a slot: take the lock, run the sale (sell, just below), and tell the observers only after the unlock. */
    Outcome select(String code) {
        List<MachineEvent> events = new ArrayList<>();
        Outcome out;
        lock.lock();
        try { out = sell(code, events); } finally { lock.unlock(); }
        publish(events);                                     // the screen hears AFTER the lock
        return out;
    }

    /**
     * THE critical step; the caller holds the lock. In this order: refuse for a reason that touches
     * nothing (no such code, sold out, not enough money); prove the change can be made from float plus
     * escrow WITHOUT touching the float; only then turn the motor, the one irreversible act; and only when
     * the item has fallen, commit -- stock down one, escrow into the float, change out of the float, both
     * into the tray. A refusal or a jam leaves every count exactly as it was. The sale's event goes into
     * events, for the caller to publish once the lock is released.
     */
    private Outcome sell(String code, List<MachineEvent> events) {
        expireEscrow();
        require(Action.SELECT);
        lastTouchMs = clock.nowMs();                         // a press restarts the thirty seconds too
        Slot s = inventory.slot(code);
        int paid = Coin.total(escrow);

        if (s == null)      return new Outcome(Status.UNKNOWN_SLOT, List.of(), List.of(), paid);
        if (s.qty() == 0)   return new Outcome(Status.SOLD_OUT, List.of(), List.of(), paid);
        int price = pricing.priceOf(s);
        if (paid < price)   return new Outcome(Status.NEED_MORE, List.of(), List.of(), price - paid);

        List<Coin> change = changeRule.plan(coinBox.poolWith(escrow), paid - price);   // pure: nothing moves
        if (change == null) {
            List<Coin> back = refundToTray();
            return new Outcome(Status.NO_CHANGE, List.of(), back, paid);
        }

        state = MachineState.DISPENSING;                     // the flap is open: nothing else may run until it shuts
        boolean dropped;
        try { dropped = motor.drop(code); } catch (RuntimeException jam) { dropped = false; }
        if (!dropped) {
            List<Coin> back = refundToTray();
            return new Outcome(Status.JAMMED, List.of(), back, paid);
        }

        s.takeOne();                                         // from here down: field writes that cannot fail
        coinBox.deposit(escrow);
        escrow.clear();
        coinBox.withdraw(change);
        tray.put(s.product, change);
        state = MachineState.IDLE;
        events.add(new MachineEvent("SOLD", code, s.qty(), coinBox.totalPaise()));
        return new Outcome(Status.SOLD, List.of(s.product), change, Coin.total(change));
    }

    /** Coin return: exactly the coins this customer put in go to the tray, and the list is handed back. */
    List<Coin> cancel() {
        lock.lock();
        try {
            expireEscrow();
            require(Action.CANCEL);
            return refundToTray();
        } finally { lock.unlock(); }
    }

    /** Empty the tray into the customer's hand. Throws when there is nothing to take. */
    Outcome collect() {
        lock.lock();
        try {
            expireEscrow();
            require(Action.COLLECT);
            return tray.take();
        } finally { lock.unlock(); }
    }

    /**
     * One buyer's whole transaction as a single locked step: their coins go in, the slot is pressed, and
     * the tray is emptied before any other terminal can touch a count. This is what a phone app, a kiosk or
     * the race test calls. Legal only in IDLE: while a walk-up customer's coins are in escrow it is refused,
     * because spending them would hand one customer's money to another.
     */
    Outcome purchase(String code, List<Coin> paid) {
        List<MachineEvent> events = new ArrayList<>();
        Outcome o;
        lock.lock();
        try {
            expireEscrow();
            require(Action.PURCHASE);                       // somebody else's coins are in: refuse, never spend them
            for (Coin c : paid) insertCoin(c);              // re-entrant: this thread already holds the lock
            o = sell(code, events);
            if (!o.sold()) cancel();                        // a one-shot buyer never leaves money behind
            if (!tray.isEmpty()) o = collect();
        } finally { lock.unlock(); }
        publish(events);                                    // after the OUTER unlock, never inside it
        return o;
    }

    // ---------------- the operator ----------------

    /** Refill a column. Returns how many went in; the rest did not fit. */
    int restock(String code, int n) {
        int added;
        MachineEvent event;
        lock.lock();
        try {
            Slot s = inventory.slot(code);
            if (s == null) throw new NoSuchElementException("no slot " + code);
            added = s.refill(n);
            event = new MachineEvent("RESTOCKED", code, s.qty(), coinBox.totalPaise());
        } finally { lock.unlock(); }
        publish(List.of(event));
        return added;
    }
    /** Put change into the float. */
    void loadFloat(Coin c, int n) {
        lock.lock();
        try { coinBox.load(c, n); } finally { lock.unlock(); }
    }
    /**
     * Take the machine out of service, or put it back. Refused while a customer has money in (SERVICE is not
     * in the HAS_MONEY row), so nobody is stranded mid-sale; an escrow abandoned for thirty seconds is swept first.
     */
    void setService(boolean outOfService) {
        lock.lock();
        try {
            expireEscrow();
            require(Action.SERVICE);
            state = outOfService ? MachineState.OUT_OF_SERVICE : MachineState.IDLE;
        } finally { lock.unlock(); }
    }

    // ---------------- the reads ----------------

    /** Which mode the machine is in. */
    MachineState state() { lock.lock(); try { return state; } finally { lock.unlock(); } }
    /** What this customer has put in and not yet spent, in paise. */
    int escrowPaise() { lock.lock(); try { return Coin.total(escrow); } finally { lock.unlock(); } }
    /** What the float is worth, in paise. */
    int floatPaise() { lock.lock(); try { return coinBox.totalPaise(); } finally { lock.unlock(); } }
    /** A copy of the float's counts, for an operator screen or a "can you make change?" check. */
    Map<Coin, Integer> floatSnapshot() { lock.lock(); try { return coinBox.snapshot(); } finally { lock.unlock(); } }
    /** How many are left in a column. One map lookup. */
    int qty(String code) {
        lock.lock();
        try { Slot s = inventory.slot(code); return s == null ? -1 : s.qty(); } finally { lock.unlock(); }
    }
    /** What a column costs right now, after whatever pricing rule is installed. */
    int priceOf(String code) {
        lock.lock();
        try { Slot s = inventory.slot(code); return s == null ? -1 : pricing.priceOf(s); } finally { lock.unlock(); }
    }
    /** Every column's count, for an operator screen: a copy of every column, so O(columns), a few dozen. */
    Map<String, Integer> stockCounts() { lock.lock(); try { return inventory.counts(); } finally { lock.unlock(); } }

    // ---------------- the private helpers ----------------

    /**
     * Money is never held for ever. Thirty seconds after the customer's last coin or press, the coins go to
     * the tray before the next button runs, so a press after that is a press with no money in. Every button
     * calls this under the lock, which is why there is no timer thread and no sweeper to get wrong.
     */
    private void expireEscrow() {
        if (!escrow.isEmpty() && clock.nowMs() - lastTouchMs >= ESCROW_TIMEOUT_MS) refundToTray();
    }
    /** Refuse an action the current mode does not allow, by name, so the failure is obvious. */
    private void require(Action a) {
        if (!Legal.ALLOWED.get(state).contains(a))
            throw new IllegalStateException(a + " is not allowed while " + state);
    }
    /** Move the whole escrow to the tray and go back to idle. The only way money leaves unspent. */
    private List<Coin> refundToTray() {
        List<Coin> back = List.copyOf(escrow);
        escrow.clear();
        tray.putCoins(back);
        if (state != MachineState.OUT_OF_SERVICE) state = MachineState.IDLE;
        return back;
    }
    /** Tell everyone who subscribed, outside the lock, catching anything they throw. */
    private void publish(List<MachineEvent> events) {
        for (MachineEvent e : events)
            for (MachineObserver o : observers) {
                try { o.onEvent(e); } catch (RuntimeException ex) { System.err.println("[observer failed] " + ex.getMessage()); }
            }
    }
}

/**
 * The front panel: the coin slot and the keypad. It remembers nothing of its own, it only calls the
 * machine. A second panel that pays and presses in one step (buy) changes nothing about the design; a
 * second COIN SLOT would, because each slot needs its own escrow (Extensions: PanelEscrow).
 */
final class FrontPanel {
    private final String id;
    private final VendingMachine machine;

    FrontPanel(String id, VendingMachine machine) { this.id = id; this.machine = machine; }
    /** Which panel this is, for logs. */
    String id() { return id; }
    /** Push a coin in. */
    void insert(Coin c) { machine.insertCoin(c); }
    /** Press a slot. */
    Outcome press(String code) { return machine.select(code); }
    /** Pay and press in one go, as a phone app or a kiosk does. Refused while a walk-up customer's coins are in. */
    Outcome buy(String code, List<Coin> coins) { return machine.purchase(code, coins); }
}

/** Runs a demo of the machine, then a many-thread race for the last item in a column. */
public class Main {
    /** Paise printed as rupees. */
    static String rs(int paise) { return "Rs " + (paise / 100) + "." + String.format("%02d", paise % 100); }

    /** A machine stocked the way the page describes it: three columns and a small float. */
    static VendingMachine stocked() {
        VendingMachine vm = new VendingMachine();
        vm.addSlot(new Slot("A1", new Product("LAY", "Lays", 2000), 8, 3));
        vm.addSlot(new Slot("A2", new Product("COK", "Coke", 3500), 8, 2));
        vm.addSlot(new Slot("B1", new Product("DMK", "Dairy Milk", 2500), 8, 3));
        vm.loadFloat(Coin.R1, 10);
        vm.loadFloat(Coin.R2, 10);
        vm.loadFloat(Coin.R5, 6);
        vm.loadFloat(Coin.R10, 4);
        return vm;
    }

    public static void main(String[] args) throws Exception {
        VendingMachine vm = stocked();
        RestockAlert pager = new RestockAlert();
        vm.addObserver(new Display());
        vm.addObserver(pager);

        System.out.println("-- a normal sale: Dairy Milk at " + rs(2500) + ", paid with Rs 30");
        vm.insertCoin(Coin.R20);
        vm.insertCoin(Coin.R10);
        Outcome sale = vm.select("B1");
        System.out.println("   " + sale.status() + " " + sale.item().name() + ", change " + sale.coins()
                           + " = " + rs(sale.paise()) + "; B1 left " + vm.qty("B1"));
        System.out.println("   tray -> " + vm.collect().item().name());

        System.out.println("-- not enough money, then the coin return");
        vm.insertCoin(Coin.R10);
        Outcome short_ = vm.select("A2");
        System.out.println("   " + short_.status() + ": " + rs(short_.paise()) + " more needed; escrow still "
                           + rs(vm.escrowPaise()));
        System.out.println("   cancel gives back " + vm.cancel() + "; escrow " + rs(vm.escrowPaise()));
        vm.collect();

        System.out.println("-- he feeds a coin in and walks away: the money comes back by itself");
        VendingMachine walked = stocked();
        long[] t = { LocalDateTime.of(2026, 9, 15, 12, 0).atZone(ZoneId.of("Asia/Kolkata")).toInstant().toEpochMilli() };
        walked.setClock(() -> t[0]);
        walked.insertCoin(Coin.R20);
        t[0] += 31_000;                                              // thirty-one seconds later
        walked.insertCoin(Coin.R1);                                  // the next touch sweeps first
        System.out.println("   escrow is now " + rs(walked.escrowPaise()) + "; the abandoned "
                           + rs(Coin.total(walked.collect().coins())) + " is waiting in the tray");

        System.out.println("-- the float cannot make change: refuse, refund, stock untouched");
        VendingMachine lop = new VendingMachine();
        lop.addSlot(new Slot("B1", new Product("DMK", "Dairy Milk", 2500), 8, 3));
        lop.loadFloat(Coin.R10, 1);                                  // Rs 10 only: Rs 15 change is impossible
        lop.insertCoin(Coin.R20);
        lop.insertCoin(Coin.R20);
        Outcome refused = lop.select("B1");
        System.out.println("   " + refused.status() + ", refunded " + refused.coins() + "; B1 left "
                           + lop.qty("B1") + "; float " + rs(lop.floatPaise()));
        lop.collect();

        System.out.println("-- greedy alone would refuse this sale; backing off finds the coins");
        Map<Coin, Integer> lopsided = new EnumMap<>(Map.of(Coin.R5, 1, Coin.R2, 3));
        System.out.println("   greedy for " + rs(600) + " from {R5 x1, R2 x3}: " + new GreedyChange().plan(lopsided, 600));
        System.out.println("   backoff for " + rs(600) + " from {R5 x1, R2 x3}: " + new BackoffChange().plan(lopsided, 600));

        System.out.println("-- happy hour: the same column, priced by the injected clock");
        VendingMachine hh = stocked();
        long fourThirty = LocalDateTime.of(2026, 9, 15, 16, 30).atZone(ZoneId.of("Asia/Kolkata")).toInstant().toEpochMilli();
        hh.setClock(() -> fourThirty);
        hh.configure(new HappyHourDiscount(new ListPrice(), () -> fourThirty, 16, 18, 20), new BackoffChange(), new Motor());
        System.out.println("   B1 lists at " + rs(2500) + ", at 16:30 it costs " + rs(hh.priceOf("B1")));

        // the race: forty panels press for the last Lays at the same instant
        VendingMachine last = stocked();
        while (last.qty("A1") > 1) last.purchase("A1", List.of(Coin.R20));    // burn down to one
        last.addObserver(pager);
        System.out.println("-- forty panels press A1 at the same instant, " + last.qty("A1") + " left");
        int panels = 40;
        CountDownLatch go = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(panels);
        List<Outcome> results = Collections.synchronizedList(new ArrayList<>());
        int floatBefore = last.floatPaise();
        for (int i = 0; i < panels; i++) {
            final FrontPanel panel = new FrontPanel("P" + i, last);
            new Thread(() -> {
                try { go.await(); results.add(panel.buy("A1", List.of(Coin.R20))); }
                catch (Exception e) { results.add(new Outcome(Status.JAMMED, List.of(), List.of(), 0)); }
                finally { done.countDown(); }
            }).start();
        }
        go.countDown();
        done.await();
        long sold = results.stream().filter(o -> o.item() != null).count();
        long handedBack = results.stream().filter(o -> o.item() == null).mapToInt(Outcome::paise).sum();
        System.out.println("   items dispensed: " + sold + " (must be 1); refused: " + (panels - sold)
                           + "; money handed back " + rs((int) handedBack));
        System.out.println("   A1 left " + last.qty("A1") + "; float grew by "
                           + rs(last.floatPaise() - floatBefore) + " (exactly one price)");
        System.out.println("   restock alerts: " + pager.empty);
    }
}
