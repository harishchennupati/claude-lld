import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * The note denominations this machine stocks, declared LARGEST FIRST so the enum's own order is the order
 * the note picker tries them in. Whole rupees only: cash can never have a rounding error.
 */
enum Note {
    N2000(2000), N500(500), N200(200), N100(100);
    final int value;
    Note(int value) { this.value = value; }
}

/**
 * Where the machine is in one customer's visit. Every public method names the states it is legal in, and
 * the ALLOWED table below names which move may follow which; everything else throws.
 */
enum SessionState { IDLE, CARD_INSERTED, AUTHENTICATED, TRANSACTION, DISPENSING, EJECTED }

/**
 * The life of ONE withdrawal attempt. PENDING is the moment before the bank is asked. Everything after it
 * is a fact about money: REFUSED (nothing moved), DEBITED (money left the account), DISPENSED (the customer
 * is holding it), REVERSED (it jammed, so we credited it back), UNKNOWN (nobody knows yet whether money
 * moved: the bank never answered, or a give-back was not confirmed; the reconciler settles it).
 */
enum TxnState { PENDING, REFUSED, DEBITED, DISPENSED, REVERSED, UNKNOWN }

/** What the bank says to a debit. TIMEOUT is not a "no": it means nobody knows yet, so do not dispense. */
enum BankReply { OK, DECLINED, TIMEOUT }

/**
 * What the bank says to a PIN. The bank counts wrong PINs per CARD, across every visit and every machine, so
 * taking the card out and putting it back buys no fresh tries. BLOCKED means: keep the card.
 */
enum PinCheck { OK, WRONG, BLOCKED }

/** Time, handed in rather than read, so a test can put the machine on any day at any hour. */
interface Clock { long nowMs(); }

/** The plastic: the number on the front and the account it resolves to. Immutable; it holds no money. */
final class Card {
    final String number, accountId;
    Card(String number, String accountId) { this.number = number; this.accountId = accountId; }
}

/**
 * Which session moves are legal. A table, not a chain of if-statements, so a new step in the visit is one
 * more row and every illegal move is rejected for free.
 */
final class Transitions {
    static final Map<SessionState, Set<SessionState>> ALLOWED = new EnumMap<>(Map.of(
        SessionState.IDLE,          EnumSet.of(SessionState.CARD_INSERTED),
        SessionState.CARD_INSERTED, EnumSet.of(SessionState.AUTHENTICATED, SessionState.EJECTED),
        SessionState.AUTHENTICATED, EnumSet.of(SessionState.TRANSACTION, SessionState.EJECTED),
        SessionState.TRANSACTION,   EnumSet.of(SessionState.DISPENSING, SessionState.AUTHENTICATED, SessionState.EJECTED),
        SessionState.DISPENSING,    EnumSet.of(SessionState.AUTHENTICATED, SessionState.EJECTED),
        SessionState.EJECTED,       EnumSet.of(SessionState.IDLE)));
}

/**
 * One customer's visit: the card in the slot and where the visit has got to. A fresh Session is built on
 * every card insertion. The count of wrong PINs is deliberately NOT here: it belongs to the card, so the
 * bank keeps it (see PinCheck).
 */
final class Session {
    final String id;
    final Card card;                                  // null only for the idle session
    final long startedMs;
    SessionState state;
    Session(String id, Card card, long startedMs, SessionState state) {
        this.id = id; this.card = card; this.startedMs = startedMs; this.state = state;
    }
}

/**
 * One row in the machine's journal: everything known about one withdrawal attempt. It is written before
 * the bank is asked and never deleted, so an operator always has a row to reconcile from (in memory here;
 * on disk once the journal is persisted, page 05). The key is the idempotency key: the bank applies one key
 * exactly once.
 */
final class Withdrawal {
    final int id;
    final String atmId, accountId, key;
    final long amount, startedMs;
    EnumMap<Note, Integer> notes = new EnumMap<>(Note.class);   // the reserved plan; empty until reserved
    volatile TxnState state = TxnState.PENDING;                 // volatile: a reconciler may settle it from another thread
    volatile String note = "";                                   // why, in English, for the receipt
    Withdrawal(int id, String atmId, String accountId, long amount, long startedMs) {
        this.id = id; this.atmId = atmId; this.accountId = accountId; this.amount = amount;
        this.startedMs = startedMs; this.key = atmId + "-" + id;
    }
    /** Mark this attempt as "no money moved, and here is why". Returns this so callers can `return w.refuse(..)`. */
    Withdrawal refuse(String why) { state = TxnState.REFUSED; note = why; return this; }
    /** How many notes of each denomination were handed over (or reserved). */
    int noteCount() { int n = 0; for (int c : notes.values()) n += c; return n; }
    public String toString() { return "#" + id + " " + amount + " " + state + (note.isEmpty() ? "" : " (" + note + ")"); }
}

/** Thrown when a withdrawal did not end with cash in the customer's hand. Carries the journal row. */
class WithdrawalFailed extends RuntimeException {
    final Withdrawal w;
    WithdrawalFailed(Withdrawal w) { super(w.state + ": " + w.note); this.w = w; }
}

/** Thrown when three wrong PINs have been entered: the card is inside the machine and stays there. */
class CardRetained extends RuntimeException {
    CardRetained(String msg) { super(msg); }
}

/** The dispenser hardware failed with the notes half out of the slot. */
class HardwareFault extends RuntimeException {
    HardwareFault(String msg) { super(msg); }
}

/**
 * Something worth telling a receipt printer or an audit log about. A value, not a callback, so a listener
 * can be added without the ATM knowing what it does.
 */
final class AtmEvent {
    final String atmId, kind, accountId;
    final long amount, atMs;
    final Withdrawal txn;                            // null for card events
    AtmEvent(String atmId, String kind, String accountId, long amount, long atMs, Withdrawal txn) {
        this.atmId = atmId; this.kind = kind; this.accountId = accountId; this.amount = amount;
        this.atMs = atMs; this.txn = txn;
    }
}

/** Anyone who wants to know what the machine did. Called AFTER the lock is released. */
interface AtmObserver { void onEvent(AtmEvent e); }

/** Prints a slip. Deliberately trivial: it must never be able to affect a transaction. */
class ReceiptPrinter implements AtmObserver {
    public void onEvent(AtmEvent e) {
        if (e.txn != null) System.out.println("   [receipt] " + e.atmId + " " + e.txn);
    }
}

/** Keeps every event in memory, which is what an auditor reads afterwards. */
class AuditLog implements AtmObserver {
    final List<AtmEvent> events = new CopyOnWriteArrayList<>();
    public void onEvent(AtmEvent e) { events.add(e); }
    int count(String kind) { int n = 0; for (AtmEvent e : events) if (e.kind.equals(kind)) n++; return n; }
}

/**
 * Everything the machine cannot do by itself. The one load-bearing method is debit: it must check the
 * balance and subtract it as ONE indivisible step, and it must apply the same key at most once.
 */
interface BankService {
    /** Check a PIN. The bank counts wrong ones per card, on every machine; a right PIN resets the count. */
    PinCheck authenticate(String cardNumber, String pin);
    /** The current balance, for a balance enquiry. */
    long balance(String accountId);
    /** Take the money if it is there, as one step. The same key twice moves money once. */
    BankReply debit(String accountId, long amount, String key);
    /** Put money in (a deposit). The same key twice moves money once. */
    void credit(String accountId, long amount, String key);
    /**
     * Undo the debit made under this key if it landed, and make sure it can never land later. True means the
     * money went back. Safe to send again and again: the give-back is one credit, under key + "-rev".
     */
    boolean reverse(String accountId, long amount, String key);
}

/**
 * A stand-in for the bank's core, written the way the real one has to behave: the balance is one
 * AtomicLong per account and the only writer is a compare-and-set loop, so two terminals debiting the same
 * account at the same instant can never both see the old balance. The key map is the idempotency record.
 * The wrong-PIN counts live here too, one per card, because the card is the bank's and not the visit's.
 */
class InMemoryBank implements BankService {
    static final int PIN_LIMIT = 3;                                            // wrong PINs in a row before a card is blocked
    private final Map<String, AtomicLong> balances = new ConcurrentHashMap<>();
    private final Map<String, String> pins = new ConcurrentHashMap<>();       // card number -> PIN
    private final Map<String, Integer> wrongPins = new ConcurrentHashMap<>(); // card number -> wrong PINs in a row
    private final Map<String, BankReply> applied = new ConcurrentHashMap<>(); // idempotency key -> what happened
    final AtomicInteger casRetries = new AtomicInteger();                     // how often a debit lost the race

    /** Open an account with a starting balance, in whole rupees. */
    void open(String accountId, long rupees) { balances.put(accountId, new AtomicLong(rupees)); }
    /** Attach a card number and its PIN to an account. */
    void issueCard(String cardNumber, String pin) { pins.put(cardNumber, pin); }

    /**
     * Check the PIN and count per CARD in one step: compute runs one caller at a time for the same card. A
     * right PIN resets the count; once the count reaches the limit, even the right PIN answers BLOCKED.
     */
    public PinCheck authenticate(String cardNumber, String pin) {
        int wrong = wrongPins.compute(cardNumber, (card, n) -> {
            int before = n == null ? 0 : n;
            if (before >= PIN_LIMIT) return before;                           // blocked stays blocked
            return pin.equals(pins.get(card)) ? 0 : before + 1;
        });
        if (wrong == 0) return PinCheck.OK;
        return wrong >= PIN_LIMIT ? PinCheck.BLOCKED : PinCheck.WRONG;
    }
    public long balance(String accountId) { return balances.get(accountId).get(); }

    /**
     * Check-and-subtract as one step. computeIfAbsent runs the body at most once per key, so a retried
     * request returns the first answer instead of debiting twice -- and two threads arriving with the SAME
     * key queue behind each other inside the map, so even a simultaneous retry cannot double-debit.
     * Different keys run side by side; they only wait for each other in the rare case that they share a
     * bucket of the map.
     */
    public BankReply debit(String accountId, long amount, String key) {
        if (amount <= 0) return BankReply.DECLINED;                          // a "debit" of -500 would be a credit
        return applied.computeIfAbsent(key, k -> cas(accountId, -amount));
    }
    /** Put money in, once per key. A credit of zero or less is a bug in the caller, never a deposit. */
    public void credit(String accountId, long amount, String key) {
        if (amount <= 0) throw new IllegalArgumentException("a credit must be positive, not " + amount);
        applied.computeIfAbsent(key, k -> cas(accountId, amount));
    }

    /**
     * The reversal. putIfAbsent, in one step, either finds the debit's answer or plants a DECLINED in its
     * place. So a debit that was lost on the way and turns up later finds that DECLINED and moves nothing.
     */
    public boolean reverse(String accountId, long amount, String key) {
        BankReply first = applied.putIfAbsent(key, BankReply.DECLINED);
        if (first != BankReply.OK) return false;                              // it never landed: nothing to give back
        credit(accountId, amount, key + "-rev");                               // it landed: give it back, once
        return true;
    }

    /** The single writer of a balance: read, decide, compare-and-set, and retry against the FRESH value. */
    private BankReply cas(String accountId, long delta) {
        AtomicLong bal = balances.get(accountId);
        if (bal == null) return BankReply.DECLINED;
        for (;;) {
            long now = bal.get();
            if (now + delta < 0) return BankReply.DECLINED;          // a balance never goes negative
            if (bal.compareAndSet(now, now + delta)) return BankReply.OK;
            casRetries.incrementAndGet();                            // somebody else got in: read again
        }
    }
}

/**
 * The rule that turns an amount into a set of notes. Behind an interface because it is the first thing an
 * interviewer changes: fewest notes today, "ration the 2000s" tomorrow.
 */
interface NoteSelection {
    /** The notes to hand over, or null if this stock cannot make exactly this amount. */
    EnumMap<Note, Integer> select(EnumMap<Note, Integer> stock, long amount);
}

/**
 * Fewest notes first, with a back-off. Pure greed is wrong: 600 from {500 x 1, 200 x 3, 100 x 0} dead-ends
 * on the 500, while 200 x 3 pays it exactly. So each denomination tries its greediest count first and then
 * steps down. Being exhaustive, it finds a combination whenever one exists; and because it walks the notes
 * largest first and takes as many of each as it can, on 2000/500/200/100 the first combination it finds is
 * also the fewest-note one. The search stays small: each count is capped by the cassette AND by the amount
 * (at most 12 notes of 2000 in 25,000), and an amount bigger than the whole drawer is refused before any
 * search. For a denomination set where greed-first is not optimal, swap the body for a bounded coin-change
 * table; the interface does not move.
 */
class FewestNotes implements NoteSelection {
    public EnumMap<Note, Integer> select(EnumMap<Note, Integer> stock, long amount) {
        long inDrawer = 0;
        for (Map.Entry<Note, Integer> e : stock.entrySet()) inDrawer += (long) e.getKey().value * e.getValue();
        if (amount > inDrawer) return null;                          // more than the whole drawer: do not search
        EnumMap<Note, Integer> plan = new EnumMap<>(Note.class);
        return pick(Note.values(), 0, stock, amount, plan) ? plan : null;
    }
    private boolean pick(Note[] notes, int i, Map<Note, Integer> stock, long left, EnumMap<Note, Integer> plan) {
        if (left == 0) return true;
        if (i == notes.length) return false;
        Note n = notes[i];
        int most = (int) Math.min(left / n.value, stock.getOrDefault(n, 0));
        for (int take = most; take >= 0; take--) {                   // greedy first, then back off
            if (take > 0) plan.put(n, take); else plan.remove(n);
            if (pick(notes, i + 1, stock, left - (long) take * n.value, plan)) return true;
        }
        plan.remove(n);
        return false;
    }
}

/** The hardware that physically pushes notes into the slot. An interface so a test can jam it. */
interface NoteFeeder { void feed(EnumMap<Note, Integer> notes); }

/** The working feeder: it always succeeds. */
class WorkingFeeder implements NoteFeeder { public void feed(EnumMap<Note, Integer> notes) { } }

/**
 * The cassettes and the note pusher. It owns the note counts and its own lock, because reserving notes
 * (choose a combination AND subtract it) has to be one step or a refill thread could invalidate the plan
 * between the two halves. Nothing slow ever happens inside this lock.
 */
class CashDispenser {
    private final EnumMap<Note, Integer> stock = new EnumMap<>(Note.class);
    private final ReentrantLock lock = new ReentrantLock();
    private final NoteFeeder feeder;
    private NoteSelection selection = new FewestNotes();
    private int retracted;                                            // notes that jammed and went to the bin

    CashDispenser(NoteFeeder feeder) { this.feeder = feeder; for (Note n : Note.values()) stock.put(n, 0); }
    /** The picking rule, handed in. The dispenser never builds one. */
    void setSelection(NoteSelection s) { selection = s; }
    /** Load notes into a cassette. Takes the lock: a refill may happen while a customer is at the machine. */
    void refill(Note n, int howMany) { lock.lock(); try { stock.merge(n, howMany, Integer::sum); } finally { lock.unlock(); } }
    /** How many of this note are in the cassette. */
    int count(Note n) { lock.lock(); try { return stock.get(n); } finally { lock.unlock(); } }
    /** All the money still inside the cassettes. */
    long cash() { lock.lock(); try { long t = 0; for (Note n : Note.values()) t += (long) stock.get(n) * n.value; return t; } finally { lock.unlock(); } }
    /** How many notes ended up in the retract bin after a jam. */
    int retracted() { lock.lock(); try { return retracted; } finally { lock.unlock(); } }

    /**
     * Choose the notes for this amount AND take them out of the cassettes, as one step. Returns null when
     * no combination of the notes in stock makes exactly this amount -- and that answer arrives BEFORE the
     * bank is asked, which is the whole point of reserving.
     */
    EnumMap<Note, Integer> reserve(long amount) {
        lock.lock();
        try {
            EnumMap<Note, Integer> plan = selection.select(stock, amount);
            if (plan == null) return null;
            for (Map.Entry<Note, Integer> e : plan.entrySet()) stock.merge(e.getKey(), -e.getValue(), Integer::sum);
            return plan;
        } finally { lock.unlock(); }
    }

    /** Put a reservation back, note for note. Used when the bank says no after the notes were reserved. */
    void release(EnumMap<Note, Integer> plan) {
        lock.lock();
        try { for (Map.Entry<Note, Integer> e : plan.entrySet()) stock.merge(e.getKey(), e.getValue(), Integer::sum); }
        finally { lock.unlock(); }
    }

    /**
     * Hand the reserved notes to the customer. If the hardware jams the notes are NOT put back in the
     * cassette -- they are physically stuck, so they are counted into the retract bin and the cash in the
     * machine still adds up.
     */
    void push(EnumMap<Note, Integer> plan) {
        try {
            feeder.feed(plan);
        } catch (RuntimeException e) {
            lock.lock();
            try { for (int c : plan.values()) retracted += c; } finally { lock.unlock(); }
            throw new HardwareFault(e.getMessage());
        }
    }
}

/**
 * A rule about the amount itself, checked before anything is touched. One method, handed in, so "minimum
 * 100", "multiples of 100" and "no more than 25,000 a go" are configuration and not an edit.
 */
interface WithdrawalPolicy {
    /** null means allowed; any other string is the reason the customer is shown. */
    String refuse(String accountId, long amount, long nowMs);
}

/** The everyday rule: a minimum, a per-transaction ceiling, and a multiple of the smallest note. */
class AmountRules implements WithdrawalPolicy {
    private final long min, max, step;
    AmountRules(long min, long max, long step) { this.min = min; this.max = max; this.step = step; }
    public String refuse(String accountId, long amount, long nowMs) {
        if (amount < min)      return "the minimum is " + min;
        if (amount > max)      return "the most in one go is " + max;
        if (amount % step != 0) return "amounts must be a multiple of " + step;
        return null;
    }
}

/**
 * One machine. It owns the session, the journal and one lock; it is handed the bank, the dispenser, the
 * clock and the rules, and it builds none of them. Every public method takes the lock, checks the session
 * is in a state where the action is legal, and tells the listeners only after the lock is released.
 */
class ATM {
    private static final AtomicInteger SEQ = new AtomicInteger();
    final String id;
    private final BankService bank;
    private final CashDispenser dispenser;
    private final ReentrantLock lock = new ReentrantLock();
    private final List<AtmObserver> observers = new CopyOnWriteArrayList<>();
    private final List<Withdrawal> journal = new ArrayList<>();                 // read and written under the lock
    private Clock clock = System::currentTimeMillis;
    private WithdrawalPolicy policy = new AmountRules(100, 25_000, 100);
    private Session session;

    ATM(String id, BankService bank, CashDispenser dispenser) {
        this.id = id; this.bank = bank; this.dispenser = dispenser;
        this.session = new Session(id + "-0", null, 0, SessionState.IDLE);
    }
    /** Hand in the rules. The machine never constructs a rule of its own. */
    void configure(WithdrawalPolicy policy, NoteSelection selection) {
        this.policy = policy; dispenser.setSelection(selection);
    }
    /** Hand in time, so a test can decide what "today" is. */
    void setClock(Clock c) { this.clock = c; }
    /** Add a listener. It is called after the lock is released and its exceptions are swallowed. */
    void addObserver(AtmObserver o) { observers.add(o); }
    /** Where the visit has got to. */
    SessionState state() { lock.lock(); try { return session.state; } finally { lock.unlock(); } }
    /** Every withdrawal attempt this machine has made, oldest first. Never pruned. */
    List<Withdrawal> journal() { lock.lock(); try { return List.copyOf(journal); } finally { lock.unlock(); } }
    /** The rows whose outcome nobody knows. An operator reconciles these. A scan of every row, asked rarely. */
    List<Withdrawal> unresolved() {
        lock.lock();
        try {
            List<Withdrawal> out = new ArrayList<>();
            for (Withdrawal w : journal) if (w.state == TxnState.UNKNOWN) out.add(w);
            return out;
        } finally { lock.unlock(); }
    }

    /** Take a card and start a visit. Legal only when the machine is idle. */
    void insertCard(Card card) {
        lock.lock();
        try {
            require(SessionState.IDLE);
            session = new Session(id + "-" + SEQ.incrementAndGet(), card, clock.nowMs(), SessionState.IDLE);
            to(SessionState.CARD_INSERTED);
        } finally { lock.unlock(); }
        publish(new AtmEvent(id, "CARD_IN", card.accountId, 0, clock.nowMs(), null));
    }

    /**
     * Try a PIN. The bank counts the wrong ones per card; when it answers BLOCKED the machine keeps the card:
     * the session ends and the state goes back to IDLE with nothing in the slot to hand back.
     */
    void enterPin(String pin) {
        PinCheck r;
        lock.lock();
        try {
            require(SessionState.CARD_INSERTED);
            r = bank.authenticate(session.card.number, pin);
            if (r == PinCheck.OK) to(SessionState.AUTHENTICATED);
            if (r == PinCheck.BLOCKED) {
                to(SessionState.EJECTED);                 // the card goes into the capture bin, not the slot
                to(SessionState.IDLE);
            }
        } finally { lock.unlock(); }
        if (r == PinCheck.BLOCKED) {
            publish(new AtmEvent(id, "CARD_RETAINED", "", 0, clock.nowMs(), null));
            throw new CardRetained("too many wrong PINs on this card: the card has been retained");
        }
        if (r == PinCheck.WRONG) throw new IllegalArgumentException("wrong PIN, try again");
    }

    /** The balance on the card's account. Legal only once the PIN was right. */
    long balance() {
        lock.lock();
        try { require(SessionState.AUTHENTICATED); return bank.balance(session.card.accountId); }
        finally { lock.unlock(); }
    }

    /**
     * Pay cash in. The amount is what the note reader COUNTED, never a number the customer typed: a machine
     * that credits a typed amount pays out for an empty tray. The notes drop into the deposit bin; the money
     * side is one credit at the bank, under this deposit's own key. Returns the amount credited.
     */
    long deposit(EnumMap<Note, Integer> counted) {
        long amount = 0;
        for (Map.Entry<Note, Integer> e : counted.entrySet()) {
            if (e.getValue() < 0) throw new IllegalArgumentException("a note count cannot be negative");
            amount += (long) e.getKey().value * e.getValue();
        }
        if (amount == 0) throw new IllegalArgumentException("nothing was counted, so nothing is credited");
        String account;
        lock.lock();
        try {
            require(SessionState.AUTHENTICATED);
            account = session.card.accountId;
            bank.credit(account, amount, id + "-dep-" + SEQ.incrementAndGet());
        } finally { lock.unlock(); }
        publish(new AtmEvent(id, "DEPOSIT", account, amount, clock.nowMs(), null));
        return amount;
    }

    /**
     * Take cash out. The order is the design: write the row and check the rule, RESERVE the notes, ask the
     * bank to debit with an idempotency key, and only then push the notes. A refusal at either of the first
     * two steps has moved no money at all; a jam after the debit is reversed (one credit, under a second key);
     * a bank that never answers dispenses nothing and leaves an UNKNOWN row for the reconciler.
     */
    Withdrawal withdraw(long amount) {
        Withdrawal w;
        lock.lock();
        try { w = doWithdraw(amount); } finally { lock.unlock(); }
        publish(new AtmEvent(id, "WITHDRAW", w.accountId, amount, clock.nowMs(), w));   // after the unlock
        if (w.state != TxnState.DISPENSED) throw new WithdrawalFailed(w);
        return w;
    }

    /** The withdrawal itself, always called with the lock held. It never throws for a business outcome. */
    private Withdrawal doWithdraw(long amount) {
        require(SessionState.AUTHENTICATED);
        Withdrawal w = new Withdrawal(SEQ.incrementAndGet(), id, session.card.accountId, amount, clock.nowMs());
        journal.add(w);                                             // written BEFORE the bank is asked

        String no = policy.refuse(w.accountId, amount, clock.nowMs());
        if (no != null) return w.refuse(no);                        // nothing has been touched

        to(SessionState.TRANSACTION);
        EnumMap<Note, Integer> plan = dispenser.reserve(amount);    // reserve BEFORE the debit
        if (plan == null) { to(SessionState.AUTHENTICATED); return w.refuse("the cassettes cannot make " + amount); }
        w.notes = plan;

        BankReply reply;
        try { reply = bank.debit(w.accountId, amount, w.key); }    // the irreversible step
        catch (RuntimeException e) { reply = BankReply.TIMEOUT; }  // a call that throws is not a "no" either
        if (reply == BankReply.DECLINED) {
            dispenser.release(plan);                                // every note goes back
            to(SessionState.AUTHENTICATED);
            return w.refuse("the bank declined");
        }
        if (reply == BankReply.TIMEOUT) {
            dispenser.release(plan);                                // hand out nothing while nobody knows
            to(SessionState.AUTHENTICATED);
            w.state = TxnState.UNKNOWN;
            w.note = "the bank did not answer; this row is for reconciliation";
            return w;
        }

        w.state = TxnState.DEBITED;                                 // the money has left the account
        to(SessionState.DISPENSING);
        try {
            dispenser.push(plan);
            w.state = TxnState.DISPENSED;
        } catch (HardwareFault f) {
            try {
                bank.reverse(w.accountId, amount, w.key);           // give it back: one credit, under key + "-rev"
                w.state = TxnState.REVERSED;
                w.note = "dispenser jammed (" + f.getMessage() + "); the account was credited back";
            } catch (RuntimeException e) {                          // the give-back did not get through either
                w.state = TxnState.UNKNOWN;
                w.note = "dispenser jammed and the credit-back was not confirmed; the reconciler will reverse it";
            }
        }
        to(SessionState.AUTHENTICATED);
        return w;
    }

    /** Give the card back and end the visit. */
    void ejectCard() {
        String account;
        lock.lock();
        try {
            if (session.state == SessionState.IDLE) return;
            account = session.card == null ? "" : session.card.accountId;
            to(SessionState.EJECTED);
            to(SessionState.IDLE);
        } finally { lock.unlock(); }
        publish(new AtmEvent(id, "CARD_OUT", account, 0, clock.nowMs(), null));
    }

    /** Refuse an action that this state does not allow, naming the state it happened in. */
    private void require(SessionState wanted) {
        if (session.state != wanted)
            throw new IllegalStateException("illegal here: the machine is " + session.state + ", not " + wanted);
    }
    /** Move the session on, but only along an edge the table allows. */
    private void to(SessionState next) {
        if (!Transitions.ALLOWED.get(session.state).contains(next))
            throw new IllegalStateException("illegal move " + session.state + " -> " + next);
        session.state = next;
    }
    /** Tell the listeners. Always outside the lock, and a listener that throws is its own problem. */
    private void publish(AtmEvent e) {
        for (AtmObserver o : observers) {
            try { o.onEvent(e); } catch (RuntimeException ignored) { }
        }
    }
}

/**
 * Proof it works: a happy withdrawal and a deposit, the wrong-PIN lockout that survives taking the card out,
 * a lopsided drawer that greed alone could not pay, and forty machines racing for one account's last rupees
 * with exactly the right number of winners and a balance that never goes below zero.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        InMemoryBank bank = new InMemoryBank();
        bank.open("ACC-1", 10_000);
        bank.issueCard("4111-1111", "1234");
        bank.issueCard("4111-2222", "1234");                 // a second card, for the wrong-PIN demo

        CashDispenser cash = new CashDispenser(new WorkingFeeder());
        cash.refill(Note.N2000, 2); cash.refill(Note.N500, 4); cash.refill(Note.N200, 3); cash.refill(Note.N100, 5);
        ATM atm = new ATM("ATM-01", bank, cash);
        atm.configure(new AmountRules(100, 25_000, 100), new FewestNotes());
        AuditLog audit = new AuditLog();
        atm.addObserver(new ReceiptPrinter());
        atm.addObserver(audit);

        Card card = new Card("4111-1111", "ACC-1");
        atm.insertCard(card);
        atm.enterPin("1234");
        System.out.println("balance: " + atm.balance());
        Withdrawal w = atm.withdraw(2700);
        System.out.println("dispensed " + w.notes + " = " + w.noteCount() + " notes; balance now " + atm.balance());
        try { atm.withdraw(2750); } catch (WithdrawalFailed f) { System.out.println("expected: " + f.getMessage()); }
        long in = atm.deposit(new EnumMap<>(Map.of(Note.N500, 2, Note.N100, 3)));
        System.out.println("deposited " + in + ", counted by the note reader; balance now " + atm.balance());
        atm.ejectCard();

        // wrong PINs are counted on the CARD: taking it out after two does not buy fresh tries
        Card other = new Card("4111-2222", "ACC-1");
        atm.insertCard(other);
        for (int i = 1; i <= 2; i++) {
            try { atm.enterPin("0000"); } catch (IllegalArgumentException e) { System.out.println("try " + i + ": " + e.getMessage()); }
        }
        atm.ejectCard();                                     // out, and straight back in
        atm.insertCard(other);
        try { atm.enterPin("0000"); }
        catch (CardRetained e) { System.out.println("try 3, after putting the card back: " + e.getMessage()); }
        System.out.println("machine is " + atm.state() + " with the card in the capture bin");

        // a lopsided drawer: 600 from {500 x 1, 200 x 3} -- greed alone dead-ends on the 500
        CashDispenser odd = new CashDispenser(new WorkingFeeder());
        odd.refill(Note.N500, 1); odd.refill(Note.N200, 3);
        ATM atm2 = new ATM("ATM-02", bank, odd);
        bank.open("ACC-2", 5_000);
        atm2.insertCard(new Card("4111-1111", "ACC-2"));
        atm2.enterPin("1234");
        System.out.println("600 from a lopsided drawer: " + atm2.withdraw(600).notes);
        atm2.ejectCard();

        // the race: forty machines, one account with 10,000 left, everyone asking for 500
        bank.open("ACC-RACE", 10_000);
        int machines = 40;
        List<ATM> fleet = new ArrayList<>();
        for (int i = 0; i < machines; i++) {
            CashDispenser d = new CashDispenser(new WorkingFeeder());
            d.refill(Note.N500, 2);
            ATM a = new ATM("ATM-R" + i, bank, d);
            fleet.add(a);
        }
        ExecutorService pool = Executors.newFixedThreadPool(machines);   // all forty really at once
        CountDownLatch go = new CountDownLatch(1);
        AtomicInteger paid = new AtomicInteger(), refused = new AtomicInteger();
        AtomicLong handedOut = new AtomicLong();
        for (ATM a : fleet) {
            pool.submit(() -> {
                a.insertCard(new Card("4111-1111", "ACC-RACE"));
                a.enterPin("1234");
                go.await();
                try { Withdrawal x = a.withdraw(500); paid.incrementAndGet(); handedOut.addAndGet(x.amount); }
                catch (WithdrawalFailed f) { refused.incrementAndGet(); }
                a.ejectCard();
                return null;
            });
        }
        go.countDown();
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("race: " + paid.get() + " paid, " + refused.get() + " refused, "
            + handedOut.get() + " handed out, balance " + bank.balance("ACC-RACE"));
        if (paid.get() != 20 || bank.balance("ACC-RACE") != 0)
            throw new AssertionError("the bank is not the single writer!");

        // the same race with no machine around it, so the compare-and-set is the only thing in the way
        bank.open("ACC-CAS", 10_000);
        ExecutorService raw = Executors.newFixedThreadPool(32);
        AtomicInteger won = new AtomicInteger();
        for (int i = 0; i < 200; i++) {
            final int n = i;
            raw.submit(() -> { if (bank.debit("ACC-CAS", 100, "cas-" + n) == BankReply.OK) won.incrementAndGet(); });
        }
        raw.shutdown();
        raw.awaitTermination(10, TimeUnit.SECONDS);
        System.out.println("bank alone: " + won.get() + " of 200 debits of 100 got through, balance "
            + bank.balance("ACC-CAS") + ", debits that lost the race and read again: " + bank.casRetries.get());
        System.out.println("audit rows: " + audit.events.size() + ", withdrawals seen: " + audit.count("WITHDRAW"));
    }
}
