import java.util.*;
import java.util.concurrent.*;

/**
 * Targeted failure tests: each one proves a claim the design makes on page 02, move 9. Run with
 * javac Main.java Extensions.java FailureTests.java && java FailureTests -- it prints ALL PASS or exits non-zero.
 */
public class FailureTests {
    static int failures = 0;
    /** One assertion, printed either way, counted when it fails. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }
    /** Every bank these tests build, so the last check can replay every ledger in all of them. */
    static final List<Bank> ALL = new ArrayList<>();
    /** A bank whose clock is the array the caller can move, so "six months later" costs no time at all. */
    static Bank bankAt(long[] now, Map<AccountKind, InterestRule> rules) {
        Bank b = new Bank();
        b.configure(rules, () -> now[0]);
        b.addCustomer(new Customer("c1", "Asha"));
        b.addCustomer(new Customer("c2", "Bharat"));
        ALL.add(b);
        return b;
    }

    public static void main(String[] args) throws Exception {
        long day = 24L * 3600 * 1000;
        long[] now = { 1_700_000_000_000L };

        // 1. an overdraft is a CURRENT-account thing. Savings stops at its floor; current sinks to its ceiling
        //    and refuses the step past it. Same code path, different rule objects.
        Bank bank = bankAt(now, Map.of(AccountKind.SAVINGS, new SimpleInterest(400)));
        SavingsAccount savings = bank.openSavings("SB-1", "c1", Money.inr("10000.00"), Money.inr("1000.00"));
        CurrentAccount current = bank.openCurrent("CA-1", "c2", Money.inr("10000.00"), Money.inr("50000.00"));
        try {
            savings.withdraw(Money.inr("9500.00"), "would break the floor");
            check(false, "a savings withdrawal through the minimum balance must be refused");
        } catch (RuleViolation e) { check(true, "savings refused: " + e.getMessage()); }
        current.withdraw(Money.inr("55000.00"), "supplier");
        check(current.balance().equals(Money.inr("-45000.00")), "a current account may run to " + current.balance());
        try {
            current.withdraw(Money.inr("6000.00"), "past the ceiling");
            check(false, "a current withdrawal past the overdraft ceiling must be refused");
        } catch (RuleViolation e) { check(true, "current refused at the ceiling: " + e.getMessage()); }

        // 2. a refused withdrawal writes NOTHING: not a row, not a paise, not an alert.
        Money before = savings.balance();
        int rowsBefore = savings.rowCount();
        try { savings.withdraw(Money.inr("100000.00"), "far too much"); } catch (RuleViolation ignored) {}
        check(before.equals(savings.balance()) && rowsBefore == savings.rowCount(),
              "the refused withdrawal changed neither the balance nor the ledger");

        // 3. interest for a period, on the injected clock, and only for the kind that earns it.
        //    INR 100000.00 at 4.00% for 365 days is exactly INR 4000.00, in integer paise.
        long[] t3 = { 1_700_000_000_000L };
        Bank b3 = bankAt(t3, Map.of(AccountKind.SAVINGS, new SimpleInterest(400)));
        SavingsAccount s3 = b3.openSavings("SB-3", "c1", Money.inr("100000.00"), Money.inr("0.00"));
        CurrentAccount c3 = b3.openCurrent("CA-3", "c2", Money.inr("100000.00"), Money.inr("0.00"));
        t3[0] += 365 * day;
        List<Txn> posted = b3.accrueInterest(365);
        check(posted.size() == 1 && posted.get(0).accountId().equals("SB-3"),
              "one interest row, on the savings account only");
        check(s3.balance().equals(Money.inr("104000.00")), "365 days at 4.00% on INR 100000 is " + s3.balance());
        check(c3.balance().equals(Money.inr("100000.00")), "the current account earned nothing");
        check(new SimpleInterest(400).on(Money.inr("100000.00"), 30).equals(Money.inr("328.76")),
              "thirty days is INR 328.76, rounded down to the paise");
        check(new PromoInterest(new SimpleInterest(400), 50).interest(c3, 365, t3[0]).equals(Money.inr("4500.00")),
              "the festival wrapper adds 0.50% to the same INR 100000 without touching the rule it wraps");

        // 4. the BASIS of interest. Asha's salary lands on the 28th. Paid on the balance as it stands, she earns
        //    a month on money that was there for three days; paid on the daily closing balances, she earns three
        //    days. Same rate, same account, same ledger: the rule decides, which is why it is handed the account.
        long[] t4 = { 1_700_000_000_000L };
        Bank b4 = bankAt(t4, Map.of());
        SavingsAccount late = b4.openSavings("SB-4", "c1", Money.inr("10000.00"), Money.inr("0.00"));
        t4[0] += 27 * day;
        late.deposit(Money.inr("100000.00"), "salary on the 28th");
        t4[0] += 3 * day;
        check(new SimpleInterest(400).interest(late, 30, t4[0]).equals(Money.inr("361.64")),
              "on the balance as it stands, thirty days pays " + new SimpleInterest(400).interest(late, 30, t4[0]));
        check(new DailyBalanceInterest(400).interest(late, 30, t4[0]).equals(Money.inr("65.75")),
              "on the daily closing balances the same month pays "
              + new DailyBalanceInterest(400).interest(late, 30, t4[0]) + ": the money was there for three days");

        // 5. month end takes as well as gives, and a charge is not a withdrawal: it does not run the vetoes.
        //    A savings account under the average balance pays 4% of the shortfall, even though a customer
        //    withdrawal of one rupee would be refused; the penalty never takes a balance below zero; a current
        //    account pays 18% a year on the days it spent in the red.
        long[] t5 = { 1_700_000_000_000L };
        Bank b5 = bankAt(t5, Map.of());
        SavingsAccount atTheLine = b5.openSavings("SB-5", "c1", Money.inr("5000.00"), Money.inr("5000.00"));
        SavingsAccount nearlyEmpty = b5.openSavings("SB-5E", "c1", Money.inr("100.00"), Money.inr("0.00"));
        CurrentAccount inTheRed = b5.openCurrent("CA-5", "c2", Money.inr("0.00"), Money.inr("100000.00"));
        inTheRed.withdraw(Money.inr("50000.00"), "a bad month");
        t5[0] += 30 * day;
        List<Txn> charged = MonthEndSweep.run(b5, List.of(new MinBalancePenalty(Money.inr("10000.00"), 400),
                                                          new OverdraftInterest(1800)), 30, t5[0]);
        check(charged.size() == 3 && charged.stream().allMatch(t -> t.type() == TxnType.FEE),
              "the sweep wrote one FEE row per charge, and nothing for the accounts that owed nothing");
        check(atTheLine.balance().equals(Money.inr("4800.00")),
              "4% of a 5,000 shortfall pushed the savings account below its floor: " + atTheLine.balance());
        check(nearlyEmpty.balance().paise() == 0,
              "4% of a 9,900 shortfall is 396.00, but the account held 100.00: it lands at " + nearlyEmpty.balance());
        try {
            atTheLine.withdraw(Money.inr("1.00"), "one rupee");
            check(false, "a customer withdrawal below the floor must still be refused");
        } catch (RuleViolation e) { check(true, "and a customer withdrawal is still vetoed: " + e.getMessage()); }
        check(inTheRed.balance().equals(Money.inr("-50739.72")),
              "thirty days overdrawn by INR 50000 at 18.00% cost INR 739.72: " + inTheRed.balance());

        // 6. sixteen ATMs on ONE account, all released together. The floor is checked and the row is written in
        //    the same lock hold, so the arithmetic is exact: INR 9,000 above the floor divided by INR 100 is
        //    ninety withdrawals, whatever order the threads ran in, and the ninety-first is refused.
        long[] t6a = { 1_700_000_000_000L };
        Bank b6a = bankAt(t6a, Map.of());
        SavingsAccount hot = b6a.openSavings("SB-6A", "c1", Money.inr("10000.00"), Money.inr("1000.00"));
        ExecutorService atms = Executors.newFixedThreadPool(16);
        CountDownLatch release = new CountDownLatch(1);
        List<Future<Integer>> tills = new ArrayList<>();
        for (int i = 0; i < 16; i++) tills.add(atms.submit(() -> {
            release.await();
            int took = 0;
            for (int k = 0; k < 12; k++) {
                try { hot.withdraw(Money.inr("100.00"), "atm"); took++; } catch (RuleViolation refused) { }
            }
            return took;
        }));
        release.countDown();
        int handedOut = 0;
        for (Future<Integer> f : tills) handedOut += f.get(20, TimeUnit.SECONDS);
        atms.shutdown();
        check(handedOut == 90, "192 attempts, exactly 90 succeeded: no thread slipped through the check");
        check(hot.balance().equals(Money.inr("1000.00")) && hot.rowCount() == 91,
              "the floor held to the paise and there are 90 rows plus the opening one: " + hot.balance());

        // 7. sixty-four threads firing transfers in BOTH directions between four accounts: no deadlock, and the
        //    bank's total assets are exactly what they were. A lost update would show up as a changed total.
        long[] t6 = { 1_700_000_000_000L };
        Bank b6 = bankAt(t6, Map.of());
        for (int i = 0; i < 4; i++) b6.openCurrent("A" + i, "c1", Money.inr("10000.00"), Money.inr("100000.00"));
        Money assetsBefore = b6.totalAssets(Money.INR);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> fired = new ArrayList<>();
        for (int i = 0; i < 64; i++) {
            final int n = i;
            fired.add(pool.submit(() -> {
                go.await();
                String a = "A" + (n % 4), b = "A" + ((n + 1) % 4);
                return b6.transfer("X" + n, n % 2 == 0 ? a : b, n % 2 == 0 ? b : a, Money.inr("100.00"), "r" + n);
            }));
        }
        go.countDown();
        int completed = 0;
        for (Future<?> f : fired) { f.get(20, TimeUnit.SECONDS); completed++; }   // a deadlock would time out here
        pool.shutdown();
        check(completed == 64, "all 64 opposing transfers finished: the lock order made a cycle impossible");
        check(assetsBefore.equals(b6.totalAssets(Money.INR)),
              "total assets are unchanged: " + assetsBefore + " -> " + b6.totalAssets(Money.INR));
        int rows = 0;
        for (Account a : b6.accounts()) rows += a.rowCount();
        check(rows == 4 + 128, "every transfer wrote exactly two rows, and none wrote three");

        // 8. an account nobody touches goes DORMANT, and one customer posting wakes it. Interest does not.
        long[] t7 = { 1_700_000_000_000L };
        Bank b7 = bankAt(t7, Map.of(AccountKind.SAVINGS, new SimpleInterest(400)));
        b7.dormantAfterDays(180);
        SavingsAccount idle = b7.openSavings("SB-5", "c1", Money.inr("5000.00"), Money.inr("0.00"));
        t7[0] += 100 * day;
        check(b7.markDormant() == 0 && idle.status() == AccountStatus.ACTIVE, "100 days idle is still ACTIVE");
        t7[0] += 100 * day;
        check(b7.markDormant() == 1 && idle.status() == AccountStatus.DORMANT, "200 days idle is DORMANT");
        b7.accrueInterest(200);
        check(idle.status() == AccountStatus.DORMANT, "the bank's own interest row did not wake it");
        idle.deposit(Money.inr("100.00"), "salary");
        check(idle.status() == AccountStatus.ACTIVE, "one customer posting woke it");

        // 9. closing is refused while money is inside, allowed at exactly zero, and CLOSED refuses everything.
        SavingsAccount leaving = bank.openSavings("SB-6", "c1", Money.inr("500.00"), Money.inr("0.00"));
        try {
            bank.close("SB-6");
            check(false, "closing an account that still holds money must be refused");
        } catch (RuleViolation e) { check(true, "close refused: " + e.getMessage()); }
        leaving.withdraw(leaving.balance(), "empty it");
        bank.close("SB-6");
        check(leaving.status() == AccountStatus.CLOSED && leaving.balance().paise() == 0, "closed at exactly zero");
        try {
            leaving.deposit(Money.inr("100.00"), "after closing");
            check(false, "a CLOSED account must refuse a deposit");
        } catch (AccountNotActive e) { check(true, "a closed account refuses postings: " + e.getMessage()); }
        SavingsAccount held = bank.openSavings("SB-6F", "c1", Money.inr("0.00"), Money.inr("0.00"));
        held.freeze();
        try {
            bank.close("SB-6F");
            check(false, "a FROZEN account must not be closed: a freeze is a legal hold");
        } catch (AccountNotActive e) { check(true, "a frozen account cannot be closed: " + e.getMessage()); }

        // 10. the same transfer id twice is ONE movement of money; and a transfer that failed claims no id,
        //    so the caller may retry that same id once the reason is fixed.
        long[] t9 = { 1_700_000_000_000L };
        Bank b9 = bankAt(t9, Map.of());
        CurrentAccount from = b9.openCurrent("CA-7", "c1", Money.inr("1000.00"), Money.inr("0.00"));
        CurrentAccount to = b9.openCurrent("CA-8", "c2", Money.inr("0.00"), Money.inr("0.00"));
        TransferReceipt first = b9.transfer("T-7", "CA-7", "CA-8", Money.inr("400.00"), "rent");
        TransferReceipt retry = b9.transfer("T-7", "CA-7", "CA-8", Money.inr("400.00"), "rent");
        check(first.equals(retry), "a retried transfer id returns the same receipt");
        check(from.balance().equals(Money.inr("600.00")) && to.balance().equals(Money.inr("400.00")),
              "and the money moved exactly once: " + from.balance() + " / " + to.balance());
        check(from.rowCount() == 2 && to.rowCount() == 2, "two rows each, not four");
        try {
            b9.transfer("T-7", "CA-7", "CA-8", Money.inr("50.00"), "a different transfer under the same id");
            check(false, "the same id for a DIFFERENT transfer must be refused, not answered with the old receipt");
        } catch (RuleViolation e) { check(true, "an id reused for a different transfer is refused: " + e.getMessage()); }
        try {
            b9.transfer("T-8", "CA-7", "CA-8", Money.inr("5000.00"), "more than there is");
            check(false, "a transfer with nothing behind it must be refused");
        } catch (RuleViolation e) { check(true, "transfer refused: " + e.getMessage()); }
        check(b9.receipt("T-8") == null && from.balance().equals(Money.inr("600.00")),
              "the failed transfer claimed no id and debited nothing, so T-8 can be retried");
        from.deposit(Money.inr("10000.00"), "top up");
        b9.transfer("T-8", "CA-7", "CA-8", Money.inr("5000.00"), "retried after the top-up");
        check(to.balance().equals(Money.inr("5400.00")), "and the retry of T-8 went through: " + to.balance());

        // 11. a listener that throws must not break a posting: they run after the lock, each in a try/catch.
        long[] t10 = { 1_700_000_000_000L };
        Bank b10 = bankAt(t10, Map.of());
        AuditLog audit = new AuditLog();
        b10.addListener((account, txn) -> { throw new RuntimeException("the SMS gateway is down"); });
        b10.addListener(audit);
        SavingsAccount s8 = b10.openSavings("SB-8", "c1", Money.inr("1000.00"), Money.inr("0.00"));
        s8.deposit(Money.inr("500.00"), "cash");
        check(s8.balance().equals(Money.inr("1500.00")), "the deposit landed despite a listener that throws");
        check(audit.size() == 1, "and the listener after the broken one still ran");

        // 12. a frozen destination is discovered BEFORE the source is debited
        long[] t11 = { 1_700_000_000_000L };
        Bank b11 = bankAt(t11, Map.of());
        CurrentAccount payer = b11.openCurrent("CA-91", "c1", Money.inr("1000.00"), Money.inr("0.00"));
        CurrentAccount frozen = b11.openCurrent("CA-92", "c2", Money.inr("0.00"), Money.inr("0.00"));
        frozen.freeze();
        try {
            b11.transfer("T-9", "CA-91", "CA-92", Money.inr("100.00"), "into a frozen account");
            check(false, "a transfer into a FROZEN account must be refused");
        } catch (AccountNotActive e) { check(true, "frozen destination refused: " + e.getMessage()); }
        check(payer.balance().equals(Money.inr("1000.00")) && payer.rowCount() == 1,
              "the source was never debited, because the destination was asked first");

        // 13. rules compose, and any implementation drops in: a one-line lambda veto beside the built-in floor
        SavingsAccount picky = b11.openSavings("SB-93", "c1", Money.inr("10000.00"), Money.inr("1000.00"));
        picky.addRule((account, amount, nowMs) -> {
            if (Money.inr("2000.00").lessThan(amount)) throw new RuleViolation("this branch caps cash at INR 2000.00");
        });
        picky.withdraw(Money.inr("2000.00"), "at the cap");
        try {
            picky.withdraw(Money.inr("2500.00"), "over the cap");
            check(false, "the handed-in rule must be able to refuse");
        } catch (RuleViolation e) { check(true, "a lambda rule composed with the floor: " + e.getMessage()); }

        // 14. money refuses to add two currencies, so a mixed amount can never reach a balance
        try {
            Money.inr("100.00").plus(Money.of(100, "USD"));
            check(false, "INR plus USD must throw");
        } catch (CurrencyMismatch e) { check(true, "money refused the mixed arithmetic: " + e.getMessage()); }

        // 15. the statement window is exact: the rows inside it, and the balances either side of it
        long[] ta = { 1_700_000_000_000L };
        Bank ba = bankAt(ta, Map.of());
        SavingsAccount sa = ba.openSavings("SB-A", "c1", Money.inr("1000.00"), Money.inr("0.00"));
        ta[0] += day;   sa.deposit(Money.inr("500.00"), "day 1");
        ta[0] += day;   sa.deposit(Money.inr("700.00"), "day 2");
        ta[0] += day;   sa.withdraw(Money.inr("200.00"), "day 3");
        Statement st = sa.statement(1_700_000_000_000L + day, 1_700_000_000_000L + 2 * day);
        check(st.rows().size() == 2 && st.opening().equals(Money.inr("1000.00"))
              && st.closing().equals(Money.inr("2200.00")),
              "the statement window holds exactly its own rows: " + st.opening() + " -> " + st.closing());

        // 16. the fee is asked BEFORE any money moves, and the source's rules must agree to the amount plus the fee.
        //     A pricing service that throws leaves both accounts as they were; a fee may not break the ceiling.
        long[] tf = { 1_700_000_000_000L };
        Bank bf = bankAt(tf, Map.of());
        CurrentAccount payerF = bf.openCurrent("CA-F1", "c1", Money.inr("1000.00"), Money.inr("0.00"));
        CurrentAccount payeeF = bf.openCurrent("CA-F2", "c2", Money.inr("0.00"), Money.inr("0.00"));
        bf.setFeePolicy((f, t, amount) -> { throw new IllegalStateException("the pricing service is down"); });
        try { bf.transfer("F-1", "CA-F1", "CA-F2", Money.inr("100.00"), "no price"); } catch (RuntimeException expected) { }
        check(payerF.rowCount() == 1 && payeeF.rowCount() == 1 && bf.receipt("F-1") == null,
              "a fee policy that throws left no row anywhere and no receipt, so F-1 can be retried");
        CurrentAccount payerG = bf.openCurrent("CA-G1", "c1", Money.inr("1000.00"), Money.inr("0.00"));
        bf.setFeePolicy((f, t, amount) -> Money.inr("25.00"));
        try {
            bf.transfer("F-2", "CA-G1", "CA-F2", Money.inr("1000.00"), "the fee would break the ceiling");
            check(false, "a fee that takes the balance past the ceiling must be refused: " + payerG.balance());
        } catch (RuleViolation e) { check(true, "the rules saw the amount plus the fee: " + e.getMessage()); }
        try { bf.transfer("F-3", "CA-G1", "CA-F2", Money.inr("975.00"), "exactly what the balance covers"); }
        catch (RuleViolation e) { check(false, "975.00 plus a 25.00 fee fits in 1000.00: " + e.getMessage()); }
        check(payerG.balance().paise() == 0, "975.00 plus the 25.00 fee takes the payer to exactly " + payerG.balance());

        // 17. a clock that steps back (a time-server correction) cannot put the ledger out of time order, which
        //     every binary search here depends on; and a statement "to the end of time" does not overflow.
        long[] tb = { 1_700_000_000_000L };
        Bank bb = bankAt(tb, Map.of());
        SavingsAccount back = bb.openSavings("SB-B", "c1", Money.inr("100.00"), Money.inr("0.00"));
        tb[0] += 2 * 3_600_000L;  back.deposit(Money.inr("1.00"), "at two o'clock");
        tb[0] -= 3_600_000L;      back.deposit(Money.inr("2.00"), "the clock stepped back an hour");
        List<Txn> rowsB = back.ledger();
        boolean inOrder = true;
        for (int i = 1; i < rowsB.size(); i++) if (rowsB.get(i).atMs() < rowsB.get(i - 1).atMs()) inOrder = false;
        check(inOrder, "the ledger stayed in time order although the clock went back an hour");
        check(back.statement(0, Long.MAX_VALUE).rows().size() == 3, "a statement up to Long.MAX_VALUE holds all three rows");

        // 18. a batch checks each account's status INSIDE its lock. A freeze that lands mid-batch (here, a rule
        //     that freezes the account it is asked about) skips that one account; the batch pays everybody else.
        long[] tz = { 1_700_000_000_000L };
        Bank bz = bankAt(tz, Map.of(AccountKind.SAVINGS, (account, days, nowMs) -> {
            if (account.id().equals("SB-Z1")) account.freeze();          // a court order arrives mid-batch
            return Money.inr("1.00");
        }));
        SavingsAccount z1 = bz.openSavings("SB-Z1", "c1", Money.inr("100.00"), Money.inr("0.00"));
        SavingsAccount z2 = bz.openSavings("SB-Z2", "c2", Money.inr("100.00"), Money.inr("0.00"));
        List<Txn> paidZ = new ArrayList<>();
        try { paidZ = bz.accrueInterest(30); } catch (RuntimeException e) { check(false, "the interest batch died: " + e); }
        check(paidZ.size() == 1 && z1.balance().equals(Money.inr("100.00")) && z2.balance().equals(Money.inr("101.00")),
              "the account frozen mid-batch got no row, and the other account was still paid");
        MonthlyCharge freezing = (account, days, nowMs) -> {
            if (account.id().equals("SB-Z2")) account.freeze();
            return Money.inr("1.00");
        };
        List<Txn> chargedZ = null;
        try { chargedZ = MonthEndSweep.run(bz, List.of(freezing), 30, tz[0]); }
        catch (RuntimeException e) { check(false, "the sweep died: " + e); }
        check(chargedZ != null && chargedZ.isEmpty(), "the month-end sweep skipped both frozen accounts the same way");

        // 19. a joint account. A small withdrawal that breaks the floor is REFUSED, not parked as "waiting for a
        //     signature"; and two owners signing the same large amounts at the same instant give exactly one
        //     withdrawal per amount and no errors, because the approval maps live under the account's lock.
        long[] tj = { 1_700_000_000_000L };
        JointAccount joint = new JointAccount("JT-9", List.of("c1", "c2"), Money.inr("10000.00"), Money.inr("1000.00"),
                                              Money.inr("50000.00"), () -> tj[0], List.of());
        try {
            Txn parked = joint.sign("c1", Money.inr("9500.00"), "breaks the floor");
            check(false, "a small withdrawal that breaks the floor must be refused, not parked: got " + parked);
        } catch (RuleViolation e) { check(true, "refused, not parked: " + e.getMessage()); }
        JointAccount rich = new JointAccount("JT-10", List.of("c1", "c2"), Money.inr("1000000000.00"), Money.inr("0.00"),
                                             Money.inr("50000.00"), () -> tj[0], List.of());
        int amounts = 1000;
        ExecutorService owners = Executors.newFixedThreadPool(2);
        CountDownLatch pen = new CountDownLatch(1);
        List<Future<Integer>> signers = new ArrayList<>();
        for (String owner : List.of("c1", "c2")) signers.add(owners.submit(() -> {
            pen.await();
            int errors = 0;
            for (int i = 0; i < amounts; i++) {
                try { rich.sign(owner, Money.of((50_001L + i) * 100, Money.INR), "large " + i); }
                catch (RuntimeException e) { errors++; }
            }
            return errors;
        }));
        pen.countDown();
        int signErrors = 0;
        for (Future<Integer> f : signers) signErrors += f.get(20, TimeUnit.SECONDS);
        owners.shutdown();
        check(signErrors == 0 && rich.rowCount() == 1 + amounts, "two owners, " + amounts + " large amounts at once: "
              + (rich.rowCount() - 1) + " withdrawals, " + signErrors + " errors");

        // 20. a loan whose job ran twice: instalment 0 paid twice is ONE payment, for the money AND for the loan's
        //     own outstanding (10,000 of principal plus 1% of 60,000 in interest).
        long[] tl = { 1_700_000_000_000L };
        Bank bl = bankAt(tl, Map.of());
        bl.openCurrent("LN-9", "c1", Money.inr("0.00"), Money.inr("0.00"));
        SavingsAccount borrower = bl.openSavings("SB-L9", "c1", Money.inr("100000.00"), Money.inr("0.00"));
        Loan loan = new Loan("LN-9", "SB-L9", Money.inr("60000.00"), 1200, 6);
        loan.pay(bl, 0);
        loan.pay(bl, 0);
        check(loan.outstanding().equals(Money.inr("50000.00")) && borrower.balance().equals(Money.inr("89400.00")),
              "instalment 0 run twice: outstanding " + loan.outstanding() + ", borrower " + borrower.balance());

        // 21. the database version: a refused debit rolls the id's claim back, so the same id can be retried and then
        //     really moves the money; it must never answer "already done" for money that never moved.
        AccountRepository repo = new InMemoryAccountRepository().open("A", 10_000).open("B", 0);
        boolean refusedFirst = !PersistedTransfer.transfer(repo, "db-1", "A", "B", 50_000, 0);
        repo.credit("A", 100_000);
        boolean retried = PersistedTransfer.transfer(repo, "db-1", "A", "B", 50_000, 0);
        check(refusedFirst && retried && repo.balance("B") == 50_000,
              "refused, topped up, retried with the same id: B holds " + Money.of(repo.balance("B"), Money.INR));

        // 22. edges at the door: an account cannot open below zero, and the owner index is read-only to callers.
        try {
            bank.openSavings("SB-NEG", "c1", Money.inr("-500.00"), Money.inr("0.00"));
            check(false, "a negative opening balance must be refused");
        } catch (RuleViolation e) { check(true, "a negative opening is refused: " + e.getMessage()); }
        try {
            bank.accountsOf("c1").clear();
            check(false, "a caller must not be able to clear the bank's owner index");
        } catch (UnsupportedOperationException e) {
            check(!bank.accountsOf("c1").isEmpty(), "the owner index is read-only");
        }

        // 23. a field written OUTSIDE the lock and read inside it must be volatile, or another thread may keep
        //     seeing the old value: the KYC status (the back office sets it) and the bank's fee policy.
        check(java.lang.reflect.Modifier.isVolatile(KycRule.class.getDeclaredField("status").getModifiers())
              && java.lang.reflect.Modifier.isVolatile(Bank.class.getDeclaredField("fees").getModifiers()),
              "KycRule.status and Bank.fees are volatile");

        // 24. the ledger explains the balance. Every row of every account in every bank these tests built is
        //     replayed from zero; each row's balanceAfter must be exactly where the replay arrives, and the last
        //     one must be the stored balance. This is the claim that the row and the field are written together.
        boolean reconciled = true;
        int replayed = 0;
        for (Bank b : ALL) for (Account a : b.accounts()) {
            Money running = Money.zero(a.currency());
            for (Txn t : a.ledger()) {
                running = switch (t.type()) {
                    case OPENING, DEPOSIT, TRANSFER_IN, INTEREST, REVERSAL -> running.plus(t.amount());
                    case WITHDRAW, TRANSFER_OUT, FEE -> running.minus(t.amount());
                };
                if (!running.equals(t.balanceAfter())) reconciled = false;
                replayed++;
            }
            if (!running.equals(a.balance())) reconciled = false;
        }
        check(reconciled, "all " + replayed + " rows in " + ALL.size() + " banks replay to the stored balances");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
