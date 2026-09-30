import java.util.*;
import java.util.concurrent.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: the mid-round pricing change -- "from today, 0.5% on transfers over 10,000, capped at 100"
/**
 * The whole rule change is one new class. Nothing in WalletService, Ledger, Account or Transaction moves,
 * because pricing went behind FeePolicy in move 3. A threshold, a percentage and a cap, in integer paise.
 */
class CappedPercentFee implements FeePolicy {
    private final long thresholdPaise, capPaise; private final long basisPoints;
    CappedPercentFee(long thresholdPaise, long basisPoints, long capPaise) {
        this.thresholdPaise = thresholdPaise; this.basisPoints = basisPoints; this.capPaise = capPaise;
    }
    public long feeFor(long amountPaise, Account from, Account to) {
        if (from.type().house()) return 0;                         // the house does not charge itself
        if (amountPaise <= thresholdPaise) return 0;
        long fee = amountPaise * basisPoints / 10_000;             // 50 bp = 0.5%, integer arithmetic throughout
        return Math.min(fee, capPaise);
    }
}

// ---- ext: top-up through a payment gateway -- the UNKNOWN outcome, and the reconciliation job that closes it
/** What the card network said. UNKNOWN is the one that matters: the money may or may not have left the bank. */
enum GatewayOutcome { SUCCESS, FAILED, UNKNOWN }

/** The outside world's money. charge() is the irreversible action; statusOf() is how we ask again later. */
interface PaymentGateway {
    /** Charge the card. Idempotent on the same key at the gateway's end too, which is why we pass ours through. */
    GatewayOutcome charge(String idemKey, String card, long paise);
    /** What happened to that charge, asked again after a timeout. */
    GatewayOutcome statusOf(String idemKey);
}

/**
 * Top-up done in the only safe order: charge the card FIRST, and credit the wallet only once the charge is
 * known to have succeeded. If the gateway times out we credit nothing and remember the key; a reconciliation
 * job asks the gateway again and finishes the job. Crediting first and charging after is how wallets give away
 * money.
 */
class GatewayTopUp {
    private final WalletService wallet; private final PaymentGateway gateway;
    private final Map<String, long[]> pending = new LinkedHashMap<>();      // key -> { paise }
    private final Map<String, String> forAccount = new LinkedHashMap<>();   // key -> account id

    GatewayTopUp(WalletService wallet, PaymentGateway gateway) { this.wallet = wallet; this.gateway = gateway; }

    /** "credited", "declined" or "pending": the third one is a real answer, not a failure to answer. */
    String topUp(String idemKey, String accountId, String card, long paise) {
        GatewayOutcome out = gateway.charge(idemKey, card, paise);
        if (out == GatewayOutcome.SUCCESS) { wallet.topUp(idemKey, accountId, paise); return "credited"; }
        if (out == GatewayOutcome.FAILED) return "declined";
        pending.put(idemKey, new long[] { paise }); forAccount.put(idemKey, accountId);
        return "pending";                                                   // nothing credited: the books are clean
    }

    /**
     * Ask the gateway again about every unknown charge and finish it. Safe to run as often as you like: the
     * wallet's top-up is idempotent on the same key, so a double reconciliation cannot double-credit.
     */
    int reconcile() {
        int closed = 0;
        for (String key : new ArrayList<>(pending.keySet())) {
            GatewayOutcome out = gateway.statusOf(key);
            if (out == GatewayOutcome.UNKNOWN) continue;                    // still unknown: leave it pending
            if (out == GatewayOutcome.SUCCESS) wallet.topUp(key, forAccount.get(key), pending.get(key)[0]);
            pending.remove(key); forAccount.remove(key); closed++;
        }
        return closed;
    }
    /** How many charges are still unresolved. A dashboard number somebody is paid to watch. */
    int stillPending() { return pending.size(); }
}

// ---- ext: multi-currency -- the rate is captured at the moment of the transfer, through two FX house accounts
/** Today's rate, handed in. A test hands in a fixed one; production hands in the treasury desk's. */
interface FxRates {
    /** Convert minor units from one currency to another, rounded down to the minor unit. */
    long convert(long minor, Currency from, Currency to);
}

/**
 * A cross-currency payment as two ordinary postings, each balanced inside ONE currency: the sender's rupees go
 * into the INR FX account, and the receiver's dollars come out of the USD FX account. The two house accounts
 * hold the position the treasury desk squares later, and each leg keeps its own currency's books at zero.
 */
class FxTransfer {
    private final WalletService wallet; private final FxRates rates;
    FxTransfer(WalletService wallet, FxRates rates) { this.wallet = wallet; this.rates = rates; }

    /** Two legs, two keys derived from the caller's one key, so a retry is still exactly-once on both. */
    List<Transaction> send(String idemKey, String fromId, String toId, long minor) {
        Account from = wallet.account(fromId), to = wallet.account(toId);
        long converted = rates.convert(minor, from.currency(), to.currency());
        String memo = "fx " + from.currency() + "->" + to.currency() + " " + minor + "/" + converted;
        Transaction out = wallet.transfer(idemKey + "#out", fromId, "fx-" + from.currency(), minor, memo);
        Transaction in = wallet.transfer(idemKey + "#in", "fx-" + to.currency(), toId, converted, memo);
        return List.of(out, in);
    }
}

// ---- ext: holds -- authorise 500 at the pump, capture 380 when the tank is full
/**
 * A hold is money that is still in the account but may not be spent. available() = balance - holds, and every
 * rule that asks "can he cover it" asks available(), not balance(). The hold itself moves no money; the capture
 * is an ordinary transfer, so the ledger never learns a new shape.
 */
class Holds {
    private final WalletService wallet;
    private final Map<String, long[]> byHold = new ConcurrentHashMap<>();   // hold id -> { paise }
    private final Map<String, String> account = new ConcurrentHashMap<>();  // hold id -> account id
    private final Map<String, Long> heldOn = new ConcurrentHashMap<>();     // account id -> paise on hold

    Holds(WalletService wallet) { this.wallet = wallet; }

    /** Spendable money: the balance minus everything already promised to somebody else. */
    long available(String accountId) { return wallet.balanceOf(accountId) - heldOn.getOrDefault(accountId, 0L); }

    /** Promise up to `paise` to a merchant. Refused if the available balance cannot cover it. */
    void authorise(String holdId, String accountId, long paise) {
        synchronized (this) {
            if (available(accountId) < paise) throw new TransferRejected("hold " + holdId + ": available is " + Money.fmt(available(accountId)));
            byHold.put(holdId, new long[] { paise }); account.put(holdId, accountId);
            heldOn.merge(accountId, paise, Long::sum);
        }
    }
    /** Take what was actually used, release the rest, and move the money as an ordinary transfer. */
    Transaction capture(String holdId, String idemKey, String toId, long paise) {
        long[] held = byHold.get(holdId);
        if (held == null) throw new NoSuchElementException("no such hold: " + holdId);
        if (paise > held[0]) throw new TransferRejected("capture " + Money.fmt(paise) + " exceeds the hold " + Money.fmt(held[0]));
        release(holdId);                                                    // free it first, then spend it
        return wallet.transfer(idemKey, account.get(holdId), toId, paise, "capture of " + holdId);
    }
    /** Give the money back to the available balance. The balance never moved, so nothing is posted. */
    synchronized void release(String holdId) {
        long[] held = byHold.remove(holdId);
        if (held == null) return;
        heldOn.merge(account.get(holdId), -held[0], Long::sum);
    }
}

// ---- ext: cashback -- a new listener, zero edits to transfer(). The trap is the loop it can start
/**
 * One percent back on every person-to-person payment, paid out of a promo house account. It is a listener, so
 * it runs after the locks are released, which is exactly why it may call the wallet again. The guard is the
 * memo: a cashback posting must not trigger another cashback, or the promo account drains one percent at a
 * time until the rounding stops it.
 */
class Cashback implements TxnListener {
    private final WalletService wallet; private final String promoId; private final long basisPoints;
    Cashback(WalletService wallet, String promoId, long basisPoints) {
        this.wallet = wallet; this.promoId = promoId; this.basisPoints = basisPoints;
    }
    public void onTxn(Transaction t) {
        if (t.status() != TxnStatus.COMPLETED) return;
        if (t.memo().startsWith("cashback")) return;                        // the guard that stops the loop
        if (wallet.account(t.fromId()).type() != AccountType.USER
         || wallet.account(t.toId()).type() != AccountType.USER) return;    // person to person only
        long back = t.amountPaise() * basisPoints / 10_000;
        if (back <= 0) return;
        wallet.transfer("cb-" + t.id(), promoId, t.fromId(), back, "cashback for " + t.id());
    }
}

// ---- ext: persistence -- the balance behind a repository, and the conditional UPDATE that replaces the lock
/**
 * What the account table looks like when the wallet outlives the process. The version column is the lock: an
 * UPDATE that names the version it read either changes one row or changes none, and changing none means
 * somebody else got there first, so the caller re-reads and tries again.
 *
 *   UPDATE account SET balance = ?, version = version + 1 WHERE id = ? AND version = ?
 *   INSERT INTO txn (idem_key, ...) VALUES (?, ...) ON CONFLICT (idem_key) DO NOTHING
 */
interface AccountRepository {
    /** The balance and the version it was read at: { balance, version }. */
    long[] load(String accountId);
    /** The conditional UPDATE. Returns false if the row moved under us, which is the signal to retry. */
    boolean compareAndSetBalance(String accountId, long expectedVersion, long newBalance);
    /** The idempotency insert. True the first time a key is seen, false every time after. */
    boolean claimKey(String idemKey);
}

/** A tiny in-memory stand-in that behaves exactly like the two SQL statements above. */
class InMemoryAccountRepository implements AccountRepository {
    private final Map<String, long[]> rows = new ConcurrentHashMap<>();     // id -> { balance, version }
    private final Set<String> keys = ConcurrentHashMap.newKeySet();
    public long[] load(String accountId) { return rows.computeIfAbsent(accountId, k -> new long[] { 0, 0 }).clone(); }
    public synchronized boolean compareAndSetBalance(String accountId, long expectedVersion, long newBalance) {
        long[] row = rows.computeIfAbsent(accountId, k -> new long[] { 0, 0 });
        if (row[1] != expectedVersion) return false;                        // WHERE version = ? matched no row
        row[0] = newBalance; row[1]++;
        return true;
    }
    public boolean claimKey(String idemKey) { return keys.add(idemKey); }
}

// ---- ext: standing instructions -- rent on the first of every month, with a key that cannot double-charge
/**
 * A scheduled payment. The interesting part is not the schedule, it is the key: it contains the period number,
 * so running the job twice, or running it on two servers, pays each period exactly once. That is the same
 * property that makes a retried HTTP request safe.
 */
class StandingInstruction {
    private final String id, fromId, toId; private final long paise, startMs, periodMs;
    StandingInstruction(String id, String fromId, String toId, long paise, long startMs, long periodMs) {
        this.id = id; this.fromId = fromId; this.toId = toId; this.paise = paise; this.startMs = startMs; this.periodMs = periodMs;
    }
    /**
     * Pay every period that is due by `nowMs`, and return how many periods this run actually paid. Safe to call
     * again and again: a period whose key already exists is skipped, so a second run pays nothing. A period that
     * was refused keeps its refusal; retrying it needs an attempt number in the key, which is a product decision.
     */
    int runUpTo(WalletService wallet, long nowMs) {
        int paid = 0;
        for (long p = 0; startMs + p * periodMs <= nowMs; p++) {
            String key = id + "#" + p;
            if (wallet.byKey(key) != null) continue;                    // this period has already been attempted
            try { wallet.transfer(key, fromId, toId, paise, id + " period " + p); paid++; }
            catch (TransferRejected r) { /* refused: the reason is on the transaction under this key */ }
        }
        return paid;
    }
}

// ---- ext: settlement -- sweep the merchants' balances out to the bank at the end of the day
/**
 * At the end of the day every merchant's wallet balance leaves for their real bank account. It is an ordinary
 * withdrawal per merchant, so it is auditable and reversible like everything else; the key names the day, so
 * running the batch twice settles once.
 */
class Settlement {
    /** Sweep each merchant to zero. Returns the total moved, in paise. */
    static long sweep(WalletService wallet, List<String> merchantIds, String dayKey) {
        long moved = 0;
        for (String m : merchantIds) {
            long due = wallet.balanceOf(m);
            if (due <= 0) continue;
            wallet.withdraw("settle-" + dayKey + "-" + m, m, due);
            moved += due;
        }
        return moved;
    }
}

// ---- ext: the audit view -- what a transaction did, straight from the journal it wrote
/** Prints one transaction's journal lines. Nothing is computed: the journal already says everything. */
class AuditView {
    /** Every entry written by one transaction, in the order they were appended. */
    static String print(WalletService wallet, String txnId) {
        StringBuilder sb = new StringBuilder();
        Transaction t = wallet.txn(txnId);
        sb.append("  ").append(t).append("\n");
        for (LedgerEntry e : wallet.ledger().journal())
            if (e.txnId().equals(txnId)) sb.append("    ").append(e).append("\n");
        return sb.toString();
    }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) {
        WalletService wallet = new WalletService("bank", "fee", Currency.INR);
        long[] now = { 1_700_000_000_000L };
        wallet.setClock(() -> now[0]);
        wallet.configure(List.of(new SameCurrencyRule()),
                         new CappedPercentFee(Money.rupees("10000.00"), 50, Money.rupees("100.00")));
        wallet.open("ann", AccountType.USER, Currency.INR);
        wallet.open("ben", AccountType.USER, Currency.INR);
        wallet.open("shop", AccountType.MERCHANT, Currency.INR);
        wallet.topUp("seed-ann", "ann", Money.rupees("100000.00"));

        // the pricing change: one new class, nothing else moved
        wallet.transfer("p1", "ann", "ben", Money.rupees("9000.00"), "under the threshold");
        wallet.transfer("p2", "ann", "ben", Money.rupees("20000.00"), "0.5% = 100, at the cap");
        System.out.println("capped percent fee collected: " + Money.fmt(wallet.balanceOf("fee"))
            + " (nothing on 9000.00, the cap on 20000.00)");

        // the gateway top-up: SUCCESS, FAILED, and the UNKNOWN that a job closes later
        Map<String, GatewayOutcome> answers = new LinkedHashMap<>();
        PaymentGateway gw = new PaymentGateway() {
            public GatewayOutcome charge(String key, String card, long paise) { return answers.getOrDefault(key, GatewayOutcome.SUCCESS); }
            public GatewayOutcome statusOf(String key) { return answers.getOrDefault(key + "!later", GatewayOutcome.UNKNOWN); }
        };
        GatewayTopUp top = new GatewayTopUp(wallet, gw);
        answers.put("g2", GatewayOutcome.FAILED);
        answers.put("g3", GatewayOutcome.UNKNOWN);
        System.out.println("gateway g1 -> " + top.topUp("g1", "ben", "4111", Money.rupees("500.00"))
            + ", g2 -> " + top.topUp("g2", "ben", "4111", Money.rupees("500.00"))
            + ", g3 -> " + top.topUp("g3", "ben", "4111", Money.rupees("500.00")));
        answers.put("g3!later", GatewayOutcome.SUCCESS);                    // the charge did go through after all
        System.out.println("reconciled " + top.reconcile() + " unknown charge(s); pending now " + top.stillPending()
            + "; ben " + Money.fmt(wallet.balanceOf("ben")));

        // multi-currency: two legs, each balanced inside its own currency
        wallet.open("fx-INR", AccountType.BANK_SETTLEMENT, Currency.INR);
        wallet.open("fx-USD", AccountType.BANK_SETTLEMENT, Currency.USD);
        wallet.open("dana", AccountType.USER, Currency.USD);
        FxRates rates = (minor, from, to) -> from == to ? minor : from == Currency.INR ? minor / 90 : minor * 90;
        List<Transaction> fx = new FxTransfer(wallet, rates).send("fx-1", "ann", "dana", Money.rupees("9000.00"));
        System.out.println("fx legs " + fx.get(0).id() + " / " + fx.get(1).id()
            + ": dana " + Money.fmt(wallet.balanceOf("dana")) + " USD, fx-INR " + Money.fmt(wallet.balanceOf("fx-INR")));

        // holds: authorise 500 at the pump, capture 380
        Holds holds = new Holds(wallet);
        holds.authorise("h1", "ben", Money.rupees("500.00"));
        System.out.println("ben balance " + Money.fmt(wallet.balanceOf("ben")) + ", available "
            + Money.fmt(holds.available("ben")) + " while the hold is live");
        holds.capture("h1", "cap-1", "shop", Money.rupees("380.00"));
        System.out.println("after the capture: shop " + Money.fmt(wallet.balanceOf("shop"))
            + ", ben available " + Money.fmt(holds.available("ben")));

        // cashback: a listener, and the guard that stops it feeding itself
        wallet.open("promo", AccountType.BANK_SETTLEMENT, Currency.INR);
        wallet.addListener(new Cashback(wallet, "promo", 100));             // 1%
        wallet.transfer("cb-test", "ann", "ben", Money.rupees("300.00"), "lunch");
        System.out.println("1% cashback on a 300.00 payment paid out " + Money.fmt(-wallet.balanceOf("promo"))
            + "; the promo account is now " + Money.fmt(wallet.balanceOf("promo")) + ", and it did not feed itself");

        // persistence: the conditional UPDATE, and the idempotency insert
        AccountRepository repo = new InMemoryAccountRepository();
        long[] row = repo.load("ann");
        System.out.println("optimistic update at the version we read: " + repo.compareAndSetBalance("ann", row[1], 50000)
            + ", the same update replayed: " + repo.compareAndSetBalance("ann", row[1], 50000));
        System.out.println("idempotency insert: first " + repo.claimKey("pay-9") + ", again " + repo.claimKey("pay-9"));

        // standing instruction: run the job twice on purpose
        StandingInstruction rent = new StandingInstruction("rent", "ann", "ben", Money.rupees("15000.00"),
                                                           now[0], 30L * 24 * 3600 * 1000);
        now[0] += 60L * 24 * 3600 * 1000;                                    // two months later
        int first = rent.runUpTo(wallet, now[0]), second = rent.runUpTo(wallet, now[0]);
        System.out.println("standing instruction: " + first + " periods paid, the job re-run paid " + second + " more");

        // settlement and the audit view
        long swept = Settlement.sweep(wallet, List.of("shop"), "2026-09-13");
        System.out.println("settled " + Money.fmt(swept) + " to the bank; shop is now " + Money.fmt(wallet.balanceOf("shop")));
        System.out.print("audit of the capture:\n" + AuditView.print(wallet, wallet.byKey("cap-1").id()));
        System.out.println("everything still reconciles: " + wallet.reconcile());
    }
}
