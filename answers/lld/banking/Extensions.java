import java.util.*;
import java.util.concurrent.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: a daily cap on cash withdrawals -- one new class and one addRule line, and it composes with the floor
/**
 * "Cap ATM withdrawals at INR 3,000 a day." A cap is stateful: it has to remember what today already cost. As an
 * overridden method on SavingsAccount there is nowhere clean to keep that memory; as a rule object it is one
 * class with a private counter, updated through the onWithdrawn hook. It composes with the minimum balance,
 * because every rule on the account must agree. Its fields are only ever touched inside the account's lock.
 * Rules see every debit, transfers included; a cash-only cap would need the channel passed to check().
 */
final class DailyLimitRule implements WithdrawalRule {
    private final Money cap;
    private long day = -1;                                          // which UTC day the counter belongs to
    private long spentPaise = 0;                                    // guarded by the account lock, like the balance

    /** @param cap the most that may leave this account in one calendar day. */
    DailyLimitRule(Money cap) { this.cap = cap; }

    /** Refuse anything that would take today's total past the cap. A new day starts the count at zero. */
    public void check(Account account, Money amount, long nowMs) {
        long today = nowMs / 86_400_000L;                           // UTC days; a real bank would use the branch's zone
        long already = (today == day) ? spentPaise : 0;
        if (already + amount.paise() > cap.paise())
            throw new RuleViolation("daily cap " + cap + ": " + Money.of(already, cap.currency())
                                    + " already taken today, " + amount + " would break it");
    }

    /** The memory: only called after the row was written, so a refused withdrawal never counts against the cap. */
    public void onWithdrawn(Account account, Money amount, long nowMs) {
        long today = nowMs / 86_400_000L;
        if (today != day) { day = today; spentPaise = 0; }
        spentPaise += amount.paise();
    }
    /** What is left of today's allowance. */
    Money remainingToday(long nowMs) {
        long today = nowMs / 86_400_000L;
        return Money.of(cap.paise() - (today == day ? spentPaise : 0), cap.currency());
    }
}
// the whole change at the call site:
//     asha.addRule(new DailyLimitRule(Money.inr("3000.00")));

// ---- ext: interest on the daily closing balance -- the basis is the rule's choice, and the ledger is the record
/**
 * What a savings account is really paid on. An Indian bank pays interest on the CLOSING BALANCE OF EVERY DAY,
 * not on whatever happens to be in the account when the batch runs, so money paid in on the 28th earns three
 * days and not a month. The rule reads the ledger to get those daily balances — which is exactly why
 * InterestRule is handed the account and not a number. The division happens once, at the end, so the whole
 * period is rounded down a single time instead of once a day.
 */
final class DailyBalanceInterest implements InterestRule {
    private final int annualBasisPoints;

    /** @param annualBasisPoints hundredths of a percent a year: 400 is 4.00%. */
    DailyBalanceInterest(int annualBasisPoints) { this.annualBasisPoints = annualBasisPoints; }

    /** Sum the days' closing balances (an overdrawn day earns nothing), then apply the rate once. */
    public Money interest(Account account, int days, long nowMs) {
        if (days <= 0) return Money.zero(account.currency());
        long sum = 0;
        for (long closing : DailyBalances.closingPaise(account, days, nowMs)) if (closing > 0) sum += closing;
        return Money.of(sum * annualBasisPoints / (10_000L * 365L), account.currency());
    }
}

/**
 * The closing balance of each of the last N days, read off the ledger. Every row carries the balance after it
 * and the rows are already in time order, so one day is a binary search: one O(n) copy of the rows, then
 * O(N log n). Interest is a batch job, so one copy per account is the right price for not holding the lock.
 */
final class DailyBalances {
    static final long DAY_MS = 24L * 3600 * 1000;

    /** Index 0 is the closing balance of the day that ends at nowMs, index 1 the day before, and so on back N days. */
    static long[] closingPaise(Account account, int days, long nowMs) {
        List<Txn> rows = account.ledger();
        long[] closing = new long[days];
        for (int d = 0; d < days; d++) closing[d] = balanceBefore(rows, nowMs - (long) d * DAY_MS);
        return closing;
    }

    /**
     * The balance after the last row strictly BEFORE this instant (a day's end), or zero if the account did not
     * exist yet. Strictly: a row stamped exactly at midnight belongs to the day that starts then, not the one ending.
     */
    private static long balanceBefore(List<Txn> rows, long ms) {
        int lo = 0, hi = rows.size();
        while (lo < hi) { int mid = (lo + hi) >>> 1; if (rows.get(mid).atMs() < ms) lo = mid + 1; else hi = mid; }
        return lo == 0 ? 0 : rows.get(lo - 1).balanceAfter().paise();
    }
}

// ---- ext: a charge instead of a veto -- the minimum-balance penalty, and interest on an overdraft
/**
 * What the bank takes at the end of a period, as opposed to what it pays. Same shape as InterestRule, opposite
 * direction, and zero is the normal answer. Kept separate from WithdrawalRule on purpose: a veto happens at the
 * moment of a withdrawal, a charge happens at the end of a month and cannot refuse anything. The sweep calls it
 * with the account's lock held, so it must be quick and must never touch another account (a second lock taken
 * out of id order could deadlock with a transfer).
 */
interface MonthlyCharge {
    /** What this account owes the bank for the period ending at nowMs. Never negative; zero means no row. */
    Money charge(Account account, int days, long nowMs);
}

/**
 * "Do not refuse her, charge her." A real savings account does not bounce a withdrawal for breaking the minimum
 * balance; it lets the balance fall and bills a penalty once a month, on the AVERAGE of the daily closing
 * balances. Swapping the MinBalanceRule veto for this charge is a one-line change at the call site and touches
 * nothing else — the same move as the daily cap, in the other direction. Two RBI rules shape the number: the
 * charge is a share of the shortfall (not a flat fee), and it may never take the balance below zero.
 */
final class MinBalancePenalty implements MonthlyCharge {
    private final Money required;
    private final int shortfallBasisPoints;

    /**
     * @param required the average monthly balance the product promises
     * @param shortfallBasisPoints the share of the shortfall charged, in hundredths of a per cent: 400 = 4%
     */
    MinBalancePenalty(Money required, int shortfallBasisPoints) {
        this.required = required; this.shortfallBasisPoints = shortfallBasisPoints;
    }

    /** Savings only: a share of (required - average daily closing balance), capped at what the account holds. */
    public Money charge(Account account, int days, long nowMs) {
        if (account.kind() != AccountKind.SAVINGS || days <= 0) return Money.zero(account.currency());
        long sum = 0;
        for (long closing : DailyBalances.closingPaise(account, days, nowMs)) sum += closing;
        long shortfall = required.paise() - sum / days;
        if (shortfall <= 0) return Money.zero(account.currency());
        long fee = shortfall * shortfallBasisPoints / 10_000L;
        return Money.of(Math.min(fee, Math.max(0, account.balance().paise())), account.currency());  // never below zero
    }
}

/**
 * The other half of "what differs between savings and current": a current account that sits overdrawn pays for
 * it. The rate is applied to the negative part of each day's closing balance, so an afternoon in the red costs
 * a day and not a month, and an account that never went under pays nothing without a special case.
 */
final class OverdraftInterest implements MonthlyCharge {
    private final int annualBasisPoints;

    /** @param annualBasisPoints the overdraft rate: 1800 is 18.00% a year. */
    OverdraftInterest(int annualBasisPoints) { this.annualBasisPoints = annualBasisPoints; }

    /** Current accounts only; the sum of the days spent below zero, charged once at the end. */
    public Money charge(Account account, int days, long nowMs) {
        if (account.kind() != AccountKind.CURRENT || days <= 0) return Money.zero(account.currency());
        long owed = 0;
        for (long closing : DailyBalances.closingPaise(account, days, nowMs)) if (closing < 0) owed += -closing;
        return Money.of(owed * annualBasisPoints / (10_000L * 365L), account.currency());
    }
}

/**
 * The end-of-month batch: every charge against every account, each as its own FEE row so a statement can
 * explain it. A charge deliberately does NOT run the withdrawal rules — it is the bank taking its own money,
 * and the penalty for breaking the minimum balance may push the balance further below that minimum (never below
 * zero: the penalty caps itself). Each charge is computed and written in ONE hold of the account's lock, so a
 * withdrawal cannot slip in between the cap and the row; the hold lasts microseconds, one account at a time.
 */
final class MonthEndSweep {
    /** Post every charge that came out positive. Returns the rows written, for a test or a report. */
    static List<Txn> run(Bank bank, List<MonthlyCharge> charges, int days, long nowMs) {
        List<Txn> posted = new ArrayList<>();
        for (Account a : bank.accounts()) {
            for (MonthlyCharge c : charges) {
                Txn row = null;
                a.lockAccount();
                try {
                    Money amount = c.charge(a, days, nowMs);
                    if (amount.paise() > 0) row = a.postFeeRow(amount, null, c.getClass().getSimpleName());
                } catch (AccountNotActive frozenOrClosed) {         // checked inside the lock; the batch goes on
                } finally { a.unlockAccount(); }
                if (row != null) { a.publish(row); posted.add(row); }   // listeners hear after the unlock
            }
        }
        return posted;
    }
}

// ---- ext: a joint account -- two owners, and anything large needs a second signature
/**
 * Two owners on one balance. The only new state is the owner set; everything that makes it a joint account is a
 * rule: above a threshold a withdrawal is refused until a second, different owner has signed for that exact
 * amount. The signature arms the rule; the withdrawal spends it, through the same onWithdrawn hook the daily cap
 * uses, so one signature can never pay for two withdrawals. Both maps are guarded by the account's lock, like
 * the balance: check and onWithdrawn already run inside it, and JointAccount.sign takes it around sign().
 */
final class DualApprovalRule implements WithdrawalRule {
    private final Money threshold;
    private final Map<Long, Set<String>> signatures = new HashMap<>();   // amount in paise -> who has signed
    private final Set<Long> armed = new HashSet<>();                     // amounts with two distinct signatures

    /** @param threshold the amount above which one owner is not enough. */
    DualApprovalRule(Money threshold) { this.threshold = threshold; }

    /** True when this amount needs a second owner. */
    boolean needsTwo(Money amount) { return threshold.lessThan(amount); }

    /** Record a signature; returns true once two different owners have signed for this amount. Lock held. */
    boolean sign(String ownerId, Money amount) {
        Set<String> who = signatures.computeIfAbsent(amount.paise(), k -> new HashSet<>());
        who.add(ownerId);
        if (who.size() >= 2) { armed.add(amount.paise()); return true; }
        return false;
    }
    /** Small amounts pass; large ones need the amount to be armed by a second owner. */
    public void check(Account account, Money amount, long nowMs) {
        if (needsTwo(amount) && !armed.contains(amount.paise()))
            throw new RuleViolation("a withdrawal over " + threshold + " needs a second owner's signature");
    }
    /** Spend the signature: one approval, one withdrawal. */
    public void onWithdrawn(Account account, Money amount, long nowMs) {
        armed.remove(amount.paise());
        signatures.remove(amount.paise());
    }
}

/**
 * An account with more than one owner. It is a plain Account plus a set of owners and the approval rule; the
 * balance, the ledger, the lock and the posting path are exactly the ones every other account uses.
 */
final class JointAccount extends Account {
    private final Set<String> owners;
    private final DualApprovalRule approvals;

    /** Open a joint account. The first owner is the primary for reporting; both may sign. */
    JointAccount(String id, List<String> owners, Money opening, Money minBalance, Money approvalThreshold,
                 Clock clock, List<AccountListener> listeners) {
        super(id, owners.get(0), AccountKind.SAVINGS, opening, clock, listeners);
        this.owners = new LinkedHashSet<>(owners);
        this.approvals = new DualApprovalRule(approvalThreshold);
        addRule(new MinBalanceRule(minBalance));
        addRule(approvals);                                          // two vetoes, and both must agree
    }
    /** Who may sign. */
    Set<String> owners() { return Collections.unmodifiableSet(owners); }
    /**
     * One owner asks for money. Under the threshold it simply goes through; over it, the first call parks the
     * request and returns null, and the second owner's call performs the withdrawal. Any other refusal (the
     * minimum balance, say) is thrown, never mistaken for "waiting for a signature".
     */
    Txn sign(String ownerId, Money amount, String note) {
        if (!owners.contains(ownerId)) throw new RuleViolation(ownerId + " does not own " + id());
        if (!approvals.needsTwo(amount)) return withdraw(amount, note);   // one owner is enough
        boolean armed;
        lockAccount();                                                    // the rule's maps live under this lock
        try { armed = approvals.sign(ownerId, amount); } finally { unlockAccount(); }
        return armed ? withdraw(amount, note) : null;                     // first owner: parked; second: done
    }
}

// ---- ext: a standing instruction -- rent on the first of every month, and a job that ran twice pays once
/**
 * Rent, an SIP, an EMI: a schedule that posts real transfers. The interesting part is not the schedule, it is
 * the transfer id: it carries the period number, so running the job twice — or on two threads at the same
 * moment — pays each period exactly once, because Bank.transfer is idempotent by that id (a retry with the same
 * id does nothing new). Across two servers the same id needs a shared store: the unique index further down.
 */
final class StandingInstruction {
    private final String id, fromId, toId;
    private final Money amount;
    private final long startMs, periodMs;

    /** @param id the instruction's name, which becomes the prefix of every transfer id it creates. */
    StandingInstruction(String id, String fromId, String toId, Money amount, long startMs, long periodMs) {
        this.id = id; this.fromId = fromId; this.toId = toId; this.amount = amount;
        this.startMs = startMs; this.periodMs = periodMs;
    }
    /** Pay every period that has fallen due by nowMs. Safe to call as often as you like, from anywhere. */
    List<TransferReceipt> runUpTo(Bank bank, long nowMs) {
        List<TransferReceipt> paid = new ArrayList<>();
        for (long period = 0; startMs + period * periodMs <= nowMs; period++)
            paid.add(bank.transfer(id + "#" + period, fromId, toId, amount, id + " period " + period));
        return paid;
    }
}

// ---- ext: a loan as a schedule -- the outstanding falls, and each instalment is an ordinary transfer
/**
 * A loan is not a new kind of money: it is an amount still owed plus a schedule of instalments, each one an
 * ordinary transfer from the borrower's account into the loan account. This one uses equal principal with
 * interest on the reducing outstanding, so every number is exact integer paise. (A bank's EMI uses the annuity
 * formula; BigDecimal.pow(n) computes (1 + r)^n exactly, so no double is needed: round the instalment to paise
 * once and let the LAST instalment absorb the rounding, so the loan still closes at zero.)
 */
final class Loan {
    private final String loanAccountId, borrowerAccountId;
    private final Money principal;
    private final int annualBasisPoints, months;
    private Money outstanding;
    private int paid = 0;                                            // instalments already paid, in order

    /** @param principal what was lent; @param months how many equal-principal instalments. */
    Loan(String loanAccountId, String borrowerAccountId, Money principal, int annualBasisPoints, int months) {
        this.loanAccountId = loanAccountId; this.borrowerAccountId = borrowerAccountId;
        this.principal = principal; this.annualBasisPoints = annualBasisPoints; this.months = months;
        this.outstanding = principal;
    }
    /** What is still owed. */
    synchronized Money outstanding() { return outstanding; }
    /** The interest part of the next instalment: one month on what is still outstanding. */
    synchronized Money interestDue() {
        return Money.of(outstanding.paise() * annualBasisPoints / (10_000L * 12L), outstanding.currency());
    }
    /**
     * Pay instalment n: principal/months plus this month's interest, moved from the borrower's account to the
     * loan account by an ordinary transfer, with an id that contains n so a repeated job cannot double-charge.
     * A repeat of an instalment already paid returns its receipt and leaves the outstanding alone, so the loan's
     * own numbers are as safe as the money. The last instalment absorbs the rounding, so the loan closes at zero.
     */
    synchronized TransferReceipt pay(Bank bank, int n) {
        String id = loanAccountId + "#emi" + n;
        if (n < paid) return bank.receipt(id);                          // the job ran twice: nothing changes
        if (n != paid || n >= months) throw new RuleViolation("instalment " + n + " is not the next one due");
        Money principalPart = (n == months - 1) ? outstanding
                            : Money.of(principal.paise() / months, principal.currency());
        Money due = principalPart.plus(interestDue());
        TransferReceipt r = bank.transfer(id, borrowerAccountId, loanAccountId, due, "emi " + (n + 1) + " of " + months);
        outstanding = outstanding.minus(principalPart);                 // only after the money moved
        paid++;
        return r;
    }
}

// ---- ext: KYC -- an unverified account may receive money, but not take much out
/**
 * KYC is a state, and the consequence of the state is a rule. Nothing in Account or Bank changes: the status
 * lives on the rule that reads it, and a verified customer's rule simply stops refusing. Note the shape — this
 * is the same move as the daily cap, which is what "a new rule is a new class" is supposed to feel like.
 */
enum KycStatus { PENDING, VERIFIED, EXPIRED }

/**
 * Caps withdrawals while the customer's papers are not in order. The status is set by the back office from
 * outside the account's lock, so it is volatile: the next withdrawal on any thread sees the latest value.
 */
final class KycRule implements WithdrawalRule {
    private final Money capWhilePending;
    private volatile KycStatus status = KycStatus.PENDING;
    /** @param capWhilePending the most an unverified account may take out in one go. */
    KycRule(Money capWhilePending) { this.capWhilePending = capWhilePending; }
    /** Move the customer along their KYC life. */
    void set(KycStatus s) { status = s; }
    /** VERIFIED passes everything; PENDING and EXPIRED are capped. */
    public void check(Account account, Money amount, long nowMs) {
        if (status != KycStatus.VERIFIED && capWhilePending.lessThan(amount))
            throw new RuleViolation("KYC is " + status + ": withdrawals are capped at " + capWhilePending);
    }
}

// ---- ext: a fee on a transfer -- a third row, written inside the same two locks
/**
 * A flat fee on anything above a threshold. The policy itself is trivial; the design point is when it is asked:
 * Bank.transfer asks it before any money moves, the source's rules must agree to the amount plus the fee, and
 * the fee row is written in the same two-lock hold, so no other thread ever sees the transfer without its fee.
 */
final class FlatFeeAboveThreshold implements FeePolicy {
    private final Money threshold, fee;
    /** @param threshold transfers above this are charged; @param fee the flat charge. */
    FlatFeeAboveThreshold(Money threshold, Money fee) { this.threshold = threshold; this.fee = fee; }
    /** The flat fee, or null when the transfer is small enough to be free. */
    public Money feeFor(Account from, Account to, Money amount) { return threshold.lessThan(amount) ? fee : null; }
}
// the whole change at the call site:
//     bank.setFeePolicy(new FlatFeeAboveThreshold(Money.inr("100000.00"), Money.inr("25.00")));

// ---- ext: persistence and a second server -- the conditional UPDATE is the lock, moved into the database
/**
 * When the balance outlives the process, the account lock is no longer the thing that decides the winner: the
 * database is. The debit becomes one conditional UPDATE whose WHERE clause carries the rule, so two servers
 * racing on the same account cannot both succeed, and the transfer id gets a unique index, so a retried request
 * inserts nothing the second time. Both are the same idea as the in-memory version, one level down.
 */
interface AccountRepository {
    /** UPDATE accounts SET paise = paise - ? WHERE id = ? AND paise - ? >= floor -- true if one row changed. */
    boolean debitIfAllowed(String accountId, long paise, long floorPaise);
    /** UPDATE accounts SET paise = paise + ? WHERE id = ? -- a credit has no condition to fail on. */
    void credit(String accountId, long paise);
    /** INSERT INTO transfers(id) VALUES (?) ON CONFLICT DO NOTHING -- true if this caller inserted the row. */
    boolean claimTransfer(String transferId);
    /** What a ROLLBACK does to the claim: the id is free again, so a refused transfer can be retried. */
    void releaseTransfer(String transferId);
    /** SELECT paise FROM accounts WHERE id = ?. */
    long balance(String accountId);
}

/** A hash map pretending to be a table, so the shape of the calls can be run and tested here. */
final class InMemoryAccountRepository implements AccountRepository {
    private final Map<String, Long> rows = new ConcurrentHashMap<>();
    private final Set<String> transfers = ConcurrentHashMap.newKeySet();
    /** Seed a row, the way a migration would. */
    InMemoryAccountRepository open(String accountId, long paise) { rows.put(accountId, paise); return this; }
    /** The compare-and-set: compute the new value and write it only if the condition still holds. */
    public boolean debitIfAllowed(String accountId, long paise, long floorPaise) {
        Long[] ok = { null };
        rows.computeIfPresent(accountId, (k, current) -> {
            if (current - paise < floorPaise) return current;                  // the WHERE clause said no
            ok[0] = current - paise; return current - paise;
        });
        return ok[0] != null;
    }
    /** An unconditional add. */
    public void credit(String accountId, long paise) { rows.merge(accountId, paise, Long::sum); }
    /** The unique index on the transfer id, doing the idempotency. */
    public boolean claimTransfer(String transferId) { return transfers.add(transferId); }
    /** The rollback of a claim. */
    public void releaseTransfer(String transferId) { transfers.remove(transferId); }
    /** Read one row. */
    public long balance(String accountId) { return rows.getOrDefault(accountId, 0L); }
}

/**
 * The whole two-server transfer: claim the id, debit conditionally, credit. No application lock anywhere. In
 * the database the three statements are ONE transaction, so a refused debit rolls the claim back with it;
 * here that rollback is the releaseTransfer call, and it is what lets the caller retry the same id later.
 */
final class PersistedTransfer {
    /** Returns false when the debit's condition failed; true when the money moved or had already moved. */
    static boolean transfer(AccountRepository repo, String transferId, String fromId, String toId,
                            long paise, long floorPaise) {
        if (!repo.claimTransfer(transferId)) return true;                      // somebody already did this one
        if (!repo.debitIfAllowed(fromId, paise, floorPaise)) {                 // the rule lives in the WHERE clause
            repo.releaseTransfer(transferId);                                  // ROLLBACK: nothing moved, id free
            return false;
        }
        repo.credit(toId, paise);
        return true;
    }
}

/**
 * Runs every extension once, so the reference code on page 05 is code that actually executes rather than a
 * snippet in a slide. Compile with Main.java and run: java ExtDemo.
 */
class ExtDemo {
    public static void main(String[] args) {
        long day = 24L * 3600 * 1000, month = 30L * day;
        long[] now = { 1_700_000_000_000L };
        Bank bank = new Bank();
        bank.configure(Map.of(AccountKind.SAVINGS, new SimpleInterest(400)), () -> now[0]);
        bank.addCustomer(new Customer("c1", "Asha"));
        bank.addCustomer(new Customer("c2", "Bharat"));

        // 1. the daily cap: one class, one line, and it composes with the minimum balance
        SavingsAccount asha = bank.openSavings("SB-1", "c1", Money.inr("50000.00"), Money.inr("1000.00"));
        DailyLimitRule cap = new DailyLimitRule(Money.inr("3000.00"));
        asha.addRule(cap);
        asha.withdraw(Money.inr("2000.00"), "atm");
        try { asha.withdraw(Money.inr("1500.00"), "atm again"); }
        catch (RuleViolation e) { System.out.println("daily cap: " + e.getMessage()); }
        System.out.println("left today " + cap.remainingToday(now[0]) + ", balance " + asha.balance());
        now[0] += day;                                                         // tomorrow, the allowance is back
        asha.withdraw(Money.inr("2500.00"), "atm tomorrow");
        System.out.println("tomorrow the cap resets: balance " + asha.balance());

        // 2. a joint account: the second signature is what makes the large withdrawal happen
        JointAccount joint = new JointAccount("JT-1", List.of("c1", "c2"), Money.inr("200000.00"),
                Money.inr("1000.00"), Money.inr("50000.00"), () -> now[0], List.of());
        System.out.println("one owner asks for INR 80000: " + joint.sign("c1", Money.inr("80000.00"), "car"));
        Txn done = joint.sign("c2", Money.inr("80000.00"), "car");
        System.out.println("the second owner signs: " + done + ", balance " + joint.balance());

        // 3. a standing instruction, run twice on purpose
        CurrentAccount landlord = bank.openCurrent("CA-9", "c2", Money.inr("0.00"), Money.inr("0.00"));
        bank.openSavings("SB-R", "c1", Money.inr("100000.00"), Money.inr("0.00"));   // no daily cap on this one
        StandingInstruction rent = new StandingInstruction("rent", "SB-R", "CA-9", Money.inr("12000.00"),
                                                           now[0], month);
        rent.runUpTo(bank, now[0] + 2 * month);
        rent.runUpTo(bank, now[0] + 2 * month);                                // the job ran twice
        System.out.println("rent after running the job twice: landlord holds " + landlord.balance()
                           + " over " + landlord.rowCount() + " rows");

        // 4. a loan: equal principal plus interest on the reducing outstanding, closing at exactly zero
        CurrentAccount loanAccount = bank.openCurrent("LN-1", "c1", Money.inr("0.00"), Money.inr("0.00"));
        bank.openSavings("SB-2", "c1", Money.inr("100000.00"), Money.inr("0.00"));
        Loan loan = new Loan("LN-1", "SB-2", Money.inr("60000.00"), 1200, 6);
        for (int i = 0; i < 6; i++) loan.pay(bank, i);
        System.out.println("loan outstanding after six instalments: " + loan.outstanding()
                           + ", loan account holds " + loanAccount.balance());

        // 5. KYC: a state, whose consequence is a rule
        SavingsAccount newbie = bank.openSavings("SB-3", "c2", Money.inr("90000.00"), Money.inr("0.00"));
        KycRule kyc = new KycRule(Money.inr("10000.00"));
        newbie.addRule(kyc);
        try { newbie.withdraw(Money.inr("25000.00"), "big"); }
        catch (RuleViolation e) { System.out.println("kyc: " + e.getMessage()); }
        kyc.set(KycStatus.VERIFIED);
        newbie.withdraw(Money.inr("25000.00"), "big, after verification");
        System.out.println("after verification the same withdrawal works: " + newbie.balance());

        // 6. a fee: a third row inside the same two locks as the transfer
        bank.setFeePolicy(new FlatFeeAboveThreshold(Money.inr("10000.00"), Money.inr("25.00")));
        Money before = newbie.balance();
        bank.transfer("F-1", "SB-3", "CA-9", Money.inr("20000.00"), "big transfer");
        System.out.println("transfer of INR 20000 with a fee: " + before + " -> " + newbie.balance()
                           + " (20000 + 25), rows end with " + newbie.ledger().get(newbie.rowCount() - 1).type());

        // 7. the basis of interest: the same money, the same rate, two honest answers
        long[] later = { 1_700_000_000_000L };
        Bank b2 = new Bank();
        b2.configure(Map.of(), () -> later[0]);
        b2.addCustomer(new Customer("c1", "Asha"));
        SavingsAccount late = b2.openSavings("SB-L", "c1", Money.inr("10000.00"), Money.inr("0.00"));
        later[0] += 27 * day;
        late.deposit(Money.inr("100000.00"), "salary on the 28th");
        later[0] += 3 * day;
        System.out.println("30 days at 4%: on the balance as it stands = "
                           + new SimpleInterest(400).interest(late, 30, later[0])
                           + ", on the daily closing balances = "
                           + new DailyBalanceInterest(400).interest(late, 30, later[0]));

        // 8. month end: a penalty instead of a veto, and interest on the days spent overdrawn
        SavingsAccount thin = b2.openSavings("SB-T", "c1", Money.inr("500.00"), Money.inr("0.00"));
        CurrentAccount red = b2.openCurrent("CA-T", "c1", Money.inr("0.00"), Money.inr("100000.00"));
        red.withdraw(Money.inr("50000.00"), "a bad month");
        later[0] += 30 * day;
        List<Txn> charges = MonthEndSweep.run(b2, List.of(new MinBalancePenalty(Money.inr("10000.00"), 400),
                                                          new OverdraftInterest(1800)), 30, later[0]);
        System.out.println("month-end charges: " + charges.size() + " rows -> thin " + thin.balance()
                           + " (4% of a 9,500 shortfall), overdrawn " + red.balance());

        // 9. persistence: the conditional UPDATE is the lock, and the unique index is the idempotency
        AccountRepository repo = new InMemoryAccountRepository().open("A", 100_000).open("B", 0);
        System.out.println("db transfer 700.00: " + PersistedTransfer.transfer(repo, "t1", "A", "B", 70_000, 0));
        System.out.println("the same request again: " + PersistedTransfer.transfer(repo, "t1", "A", "B", 70_000, 0)
                           + " and A still holds " + Money.of(repo.balance("A"), Money.INR));
        System.out.println("one more, which the WHERE clause refuses: "
                           + PersistedTransfer.transfer(repo, "t2", "A", "B", 70_000, 0));
    }
}
