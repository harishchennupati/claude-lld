import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * One test per claim the design makes. Each one reproduces a failure an ATM actually has in the field -- a
 * retained card, a PIN guessed across visits, an empty cassette, a decline, a jam, a bank that never
 * answers or throws, a customer who walks away mid-visit, a drawer running dry -- and proves the code ends
 * in a state where the customer has lost nothing and the cash in the machine still matches the money that
 * left the accounts.
 */
public class FailureTests {
    static int failures = 0;
    /** Print one line per claim and remember how many were wrong. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }
    static final Clock CLOCK = () -> 1_757_000_000_000L;      // a fixed "today", so nothing depends on the wall clock

    /** A machine with its own cassettes, wired to the bank handed in. */
    static ATM machine(String id, BankService bank, NoteFeeder feeder, int[] counts) {
        CashDispenser d = new CashDispenser(feeder);
        Note[] all = Note.values();
        for (int i = 0; i < counts.length; i++) d.refill(all[i], counts[i]);
        ATM a = new ATM(id, bank, d);
        a.setClock(CLOCK);
        a.configure(new AmountRules(100, 25_000, 100), new FewestNotes());
        return a;
    }

    public static void main(String[] args) throws Exception {
        InMemoryBank core = new InMemoryBank();
        core.issueCard("CARD-1", "1234");

        // 1. three wrong PINs retain the card: the visit ends and nothing is left in the slot
        core.issueCard("CARD-LOCK", "1234");                          // its own card: the bank blocks the card itself
        core.open("A1", 10_000);
        ATM m1 = machine("T1", core, new WorkingFeeder(), new int[] { 2, 4, 3, 5 });
        m1.insertCard(new Card("CARD-LOCK", "A1"));
        for (int i = 0; i < 2; i++)
            try { m1.enterPin("0000"); check(false, "a wrong PIN must be refused"); } catch (IllegalArgumentException e) { }
        boolean retained = false;
        try { m1.enterPin("0000"); } catch (CardRetained e) { retained = true; }
        check(retained, "the third wrong PIN retains the card");
        check(m1.state() == SessionState.IDLE, "after a retained card the machine is IDLE, not holding a session");
        try { m1.balance(); check(false, "a balance enquiry with no card must be refused"); }
        catch (IllegalStateException e) { check(true, "an action with no card is refused: " + e.getMessage()); }

        // 2. the cassettes cannot make the amount: refused BEFORE the bank is asked
        core.open("A2", 10_000);
        FlakyBank watch = new FlakyBank(core);
        ATM m2 = machine("T2", watch, new WorkingFeeder(), new int[] { 0, 1, 0, 0 });   // one 500 note, nothing else
        m2.insertCard(new Card("CARD-1", "A2"));
        m2.enterPin("1234");
        Withdrawal w2 = null;
        try { m2.withdraw(1_000); check(false, "must refuse"); } catch (WithdrawalFailed f) { w2 = f.w; }
        check(w2.state == TxnState.REFUSED, "an amount the cassettes cannot make is REFUSED: " + w2.note);
        check(watch.debits.get() == 0, "the bank was never asked, so no money moved");
        check(core.balance("A2") == 10_000, "the balance is untouched");

        // 3. the bank declines after the notes were reserved: every note goes back
        core.open("A3", 500);
        ATM m3 = machine("T3", core, new WorkingFeeder(), new int[] { 0, 4, 0, 0 });    // 2,000 in 500s
        m3.insertCard(new Card("CARD-1", "A3"));
        m3.enterPin("1234");
        Withdrawal w3 = null;
        try { m3.withdraw(1_000); check(false, "must refuse"); } catch (WithdrawalFailed f) { w3 = f.w; }
        check(w3.state == TxnState.REFUSED, "a declined debit dispenses nothing: " + w3.note);
        check(core.balance("A3") == 500, "the balance is exactly what it was");
        check(m3.state() == SessionState.AUTHENTICATED, "the customer is still in the session and can ask for less");
        Withdrawal ok3 = m3.withdraw(500);
        check(ok3.state == TxnState.DISPENSED && core.balance("A3") == 0, "a smaller amount then works: " + ok3.notes);

        // 4. the dispenser jams AFTER the debit: the account is credited back, the notes are retracted
        core.open("A4", 10_000);
        CashDispenser jam = new CashDispenser(new JammingFeeder(1));
        jam.refill(Note.N500, 4);
        ATM m4 = new ATM("T4", core, jam);
        m4.setClock(CLOCK);
        m4.insertCard(new Card("CARD-1", "A4"));
        m4.enterPin("1234");
        Withdrawal w4 = null;
        try { m4.withdraw(1_000); check(false, "a jam must be reported"); } catch (WithdrawalFailed f) { w4 = f.w; }
        check(w4.state == TxnState.REVERSED, "a jam after the debit is REVERSED, not swallowed");
        check(core.balance("A4") == 10_000, "the customer got nothing and was charged nothing");
        check(jam.retracted() == 2 && jam.cash() == 1_000, "the two stuck notes are in the retract bin, not back in the cassette");

        // 5. the bank never answers: dispense nothing, record UNKNOWN, reverse it later -- never debit to "ask"
        core.open("A5", 10_000);
        FlakyBank slow = new FlakyBank(core);
        slow.next(BankReply.TIMEOUT);                                 // the request was lost before the bank saw it
        ATM m5 = machine("T5", slow, new WorkingFeeder(), new int[] { 0, 4, 0, 0 });
        m5.insertCard(new Card("CARD-1", "A5"));
        m5.enterPin("1234");
        Withdrawal w5 = null;
        try { m5.withdraw(1_000); check(false, "a timeout must not look like success"); } catch (WithdrawalFailed f) { w5 = f.w; }
        check(w5.state == TxnState.UNKNOWN, "a bank that does not answer leaves the row UNKNOWN");
        check(core.balance("A5") == 10_000, "nothing was debited while nobody knew");
        check(m5.unresolved().size() == 1, "the row is waiting for reconciliation");
        new Reconciler(core).settle(m5.unresolved());
        check(w5.state == TxnState.REFUSED && core.balance("A5") == 10_000,
              "reconciliation finds the debit never landed and says so, without debiting to find out: " + w5.state);
        check(core.debit("A5", 1_000, w5.key) == BankReply.DECLINED && core.balance("A5") == 10_000,
              "and the lost request, turning up late under the same key, can no longer take the money");
        core.open("A5b", 10_000);                                     // the dangerous kind: it landed, the answer was lost
        ATM m5b = machine("T5b", new FlakyBank(core).landsButTimesOut(), new WorkingFeeder(), new int[] { 0, 4, 0, 0 });
        m5b.insertCard(new Card("CARD-1", "A5b"));
        m5b.enterPin("1234");
        try { m5b.withdraw(1_000); } catch (WithdrawalFailed ignored) { }
        check(core.balance("A5b") == 9_000 && m5b.unresolved().size() == 1, "the money left, nothing was dispensed, the row is UNKNOWN");
        new Reconciler(core).settle(m5b.journal());                   // handed EVERY row: it touches only the UNKNOWN one
        check(core.balance("A5b") == 10_000 && m5b.unresolved().isEmpty(), "the reversal gives it back, exactly once");

        // 6. note selection is exact, and backs off a drawer greed alone cannot pay from
        CashDispenser odd = new CashDispenser(new WorkingFeeder());
        odd.refill(Note.N500, 1); odd.refill(Note.N200, 3);
        EnumMap<Note, Integer> plan = odd.reserve(600);
        long sum = 0;
        for (Map.Entry<Note, Integer> e : plan.entrySet()) sum += (long) e.getKey().value * e.getValue();
        check(sum == 600 && plan.get(Note.N200) == 3, "600 from {500x1, 200x3} backs off the 500 and pays 200x3");
        check(odd.count(Note.N500) == 1 && odd.count(Note.N200) == 0, "only the notes in the plan left the cassettes");
        CashDispenser few = new CashDispenser(new WorkingFeeder());
        few.refill(Note.N2000, 5); few.refill(Note.N500, 10); few.refill(Note.N100, 10);
        check(few.reserve(2_600).equals(new EnumMap<>(Map.of(Note.N2000, 1, Note.N500, 1, Note.N100, 1))),
              "2,600 is three notes, not thirteen");
        check(few.reserve(50) == null, "an amount no combination can make is refused, not approximated");
        CashDispenser lc = new CashDispenser(new WorkingFeeder());
        lc.refill(Note.N500, 1); lc.refill(Note.N200, 3);
        lc.setSelection(new GreedyOnly());
        check(lc.reserve(600) == null && lc.cash() == 1_100, "LeetCode 2241's rule (largest first, never step back) refuses that 600");

        // 7. a receipt printer that throws cannot break a withdrawal
        core.open("A7", 10_000);
        ATM m7 = machine("T7", core, new WorkingFeeder(), new int[] { 0, 4, 0, 0 });
        m7.addObserver(e -> { throw new RuntimeException("printer out of paper"); });
        AuditLog audit = new AuditLog();
        m7.addObserver(audit);
        m7.insertCard(new Card("CARD-1", "A7"));
        m7.enterPin("1234");
        Withdrawal w7 = m7.withdraw(1_000);
        check(w7.state == TxnState.DISPENSED && core.balance("A7") == 9_000, "the withdrawal succeeds although the printer threw");
        check(audit.count("WITHDRAW") == 1, "the listener after the broken one still heard about it");

        // 8. the same idempotency key moves money exactly once
        core.open("A8", 10_000);
        BankReply first = core.debit("A8", 1_000, "KEY-8");
        BankReply again = core.debit("A8", 1_000, "KEY-8");
        check(first == BankReply.OK && again == BankReply.OK && core.balance("A8") == 9_000,
              "a retried debit under the same key returns the first answer and charges once");

        // 9. forty machines, one account: the balance never goes below zero and the cash adds up
        core.open("RACE", 10_000);
        int machines = 40;
        List<ATM> fleet = new ArrayList<>();
        List<CashDispenser> drawers = new ArrayList<>();
        for (int i = 0; i < machines; i++) {
            CashDispenser d = new CashDispenser(new WorkingFeeder());
            d.refill(Note.N500, 2);
            drawers.add(d);
            ATM a = new ATM("R" + i, core, d);
            a.setClock(CLOCK);
            fleet.add(a);
        }
        ExecutorService pool = Executors.newFixedThreadPool(machines);
        CountDownLatch go = new CountDownLatch(1);
        AtomicInteger paid = new AtomicInteger();
        AtomicLong handedOut = new AtomicLong();
        for (ATM a : fleet) pool.submit(() -> {
            a.insertCard(new Card("CARD-1", "RACE"));
            a.enterPin("1234");
            go.await();
            try { handedOut.addAndGet(a.withdraw(500).amount); paid.incrementAndGet(); } catch (WithdrawalFailed ignored) { }
            return null;
        });
        go.countDown();
        pool.shutdown();
        pool.awaitTermination(20, TimeUnit.SECONDS);
        long stillInDrawers = 0;
        for (CashDispenser d : drawers) stillInDrawers += d.cash();
        check(paid.get() == 20, "exactly twenty of forty machines paid out, not twenty-one: " + paid.get());
        check(core.balance("RACE") == 0, "the balance landed exactly on zero and never went below it");
        check(handedOut.get() == 10_000 && stillInDrawers == 40_000 - 10_000,
              "the cash that left the drawers equals the money that left the account");

        // 10. a decorator must not break idempotency: the same key twice is a retry, not a second withdrawal
        core.open("A10", 100_000);
        DailyCap cap = new DailyCap(core, 20_000, CLOCK, ZoneId.of("Asia/Kolkata"));
        check(cap.debit("A10", 15_000, "K10") == BankReply.OK, "15,000 is under the 20,000 daily cap");
        check(cap.debit("A10", 15_000, "K10") == BankReply.OK,
              "the SAME key again gives the same answer; the cap does not count a retry twice and decline it");
        check(core.balance("A10") == 85_000, "and the money moved exactly once");
        check(cap.debit("A10", 10_000, "K10-b") == BankReply.DECLINED, "a genuinely new 10,000 is over the cap");

        // 11. the watchdog takes the card back, and it cannot cut into a withdrawal already in flight
        core.open("A11", 10_000);
        FlakyBank slowLink = new FlakyBank(core).slowBy(400);         // the bank takes 400 ms to answer
        ATM m11 = machine("T11", slowLink, new WorkingFeeder(), new int[] { 0, 4, 0, 0 });
        ScheduledExecutorService clockThread = Executors.newSingleThreadScheduledExecutor();
        SessionWatchdog dog = new SessionWatchdog(m11, 50, clockThread);
        m11.insertCard(new Card("CARD-1", "A11"));
        m11.enterPin("1234");
        dog.touch();                                                  // the customer goes quiet: 50 ms to live
        Withdrawal w11 = m11.withdraw(1_000);                         // ... while a 400 ms bank call is running
        check(w11.state == TxnState.DISPENSED && core.balance("A11") == 9_000,
              "the watchdog woke up mid-withdrawal and the withdrawal still finished whole");
        long deadline = System.currentTimeMillis() + 3_000;
        while (m11.state() != SessionState.IDLE && System.currentTimeMillis() < deadline) Thread.sleep(10);
        check(dog.fired.get() == 1 && m11.state() == SessionState.IDLE,
              "and the card came out the moment the lock was free, not in the middle of the money");
        clockThread.shutdownNow();

        // 12. the drawer runs low: one more observer hears it, and the ATM did not learn a new word
        core.open("A12", 100_000);
        CashDispenser thin = new CashDispenser(new WorkingFeeder());
        thin.refill(Note.N500, 6);                                    // 3,000 in the drawer
        ATM m12 = new ATM("T12", core, thin);
        m12.setClock(CLOCK);
        LowCashAlert low = new LowCashAlert(thin, 2_000);
        m12.addObserver(low);
        m12.insertCard(new Card("CARD-1", "A12"));
        m12.enterPin("1234");
        m12.withdraw(500);                                            // 2,500 left: still above the floor
        check(low.alerts.isEmpty(), "no page while the drawer is above the floor");
        m12.withdraw(1_000);                                          // 1,500 left: under it
        check(low.alerts.size() == 1, "one page the moment the drawer crosses the floor: " + low.alerts);
        m12.withdraw(500);                                            // 1,000 left: still under it
        check(low.alerts.size() == 1, "and it does not page again on every withdrawal after that");

        // 13. wrong PINs are counted on the CARD: taking it out after two does not buy fresh tries
        core.issueCard("CARD-13", "1234");
        core.open("A13", 10_000);
        ATM m13 = machine("T13", core, new WorkingFeeder(), new int[] { 0, 4, 0, 0 });
        m13.insertCard(new Card("CARD-13", "A13"));
        for (int i = 0; i < 2; i++) try { m13.enterPin("0000"); } catch (IllegalArgumentException e) { }
        m13.ejectCard();                                              // out, and straight back in
        m13.insertCard(new Card("CARD-13", "A13"));
        boolean kept = false;
        try { m13.enterPin("0000"); } catch (CardRetained e) { kept = true; } catch (IllegalArgumentException e) { }
        check(kept, "the third wrong PIN keeps the card, although it was taken out and put back after two");
        ATM next13 = machine("T13b", core, new WorkingFeeder(), new int[] { 0, 4, 0, 0 });
        next13.insertCard(new Card("CARD-13", "A13"));
        boolean keptAgain = false;
        try { next13.enterPin("1234"); } catch (CardRetained e) { keptAgain = true; }
        check(keptAgain, "a blocked card is kept by the next machine too, even with the right PIN");

        // 14. the link dies in the middle of a debit: an exception is treated as "nobody knows", and nothing leaks
        core.open("A14", 10_000);
        CashDispenser d14 = new CashDispenser(new WorkingFeeder());
        d14.refill(Note.N500, 4);
        ATM m14 = new ATM("T14", new FlakyBank(core).linkDownFor(1), d14);
        m14.setClock(CLOCK);
        m14.insertCard(new Card("CARD-1", "A14"));
        m14.enterPin("1234");
        Withdrawal w14 = null;
        try { m14.withdraw(1_000); } catch (WithdrawalFailed f) { w14 = f.w; } catch (RuntimeException e) { }
        check(w14 != null && w14.state == TxnState.UNKNOWN && m14.unresolved().size() == 1,
              "a bank call that throws leaves an UNKNOWN row the reconciler can see, not a crash and a PENDING row");
        check(d14.cash() == 2_000 && m14.state() == SessionState.AUTHENTICATED,
              "every reserved note is back in the cassette, and the customer is still in the session");

        // 15. the notes jam AND the credit-back cannot reach the bank: the row must not look settled
        core.open("A15", 10_000);
        FlakyBank cut = new FlakyBank(core);
        CashDispenser d15 = new CashDispenser(notes -> { cut.linkDownFor(1); throw new RuntimeException("jam, and the link drops"); });
        d15.refill(Note.N500, 4);
        ATM m15 = new ATM("T15", cut, d15);
        m15.setClock(CLOCK);
        m15.insertCard(new Card("CARD-1", "A15"));
        m15.enterPin("1234");
        Withdrawal w15 = null;
        try { m15.withdraw(1_000); } catch (WithdrawalFailed f) { w15 = f.w; } catch (RuntimeException e) { }
        check(w15 != null && w15.state == TxnState.UNKNOWN && core.balance("A15") == 9_000,
              "debited, nothing dispensed, credit-back unconfirmed: the row says UNKNOWN, not DEBITED");
        new Reconciler(core).settle(m15.unresolved());
        new Reconciler(core).settle(List.of(w15));                    // a second run finds nothing left to do
        check(w15.state == TxnState.REVERSED && core.balance("A15") == 10_000, "the reconciler gives the money back, once");

        // 16. a deposit is what the note reader counted: nothing counted is nothing credited
        core.open("A16", 10_000);
        ATM m16 = machine("T16", core, new WorkingFeeder(), new int[] { 0, 4, 0, 0 });
        m16.insertCard(new Card("CARD-1", "A16"));
        m16.enterPin("1234");
        check(m16.deposit(new EnumMap<>(Map.of(Note.N500, 3, Note.N100, 2))) == 1_700 && core.balance("A16") == 11_700,
              "three 500s and two 100s credit exactly 1,700");
        int refusedDeposits = 0;
        try { m16.deposit(new EnumMap<>(Map.of(Note.N500, -1))); } catch (IllegalArgumentException e) { refusedDeposits++; }
        try { m16.deposit(new EnumMap<>(Note.class)); } catch (IllegalArgumentException e) { refusedDeposits++; }
        check(refusedDeposits == 2 && core.balance("A16") == 11_700, "a negative count or an empty tray is refused, and the balance does not move");

        // 17. the daily cap counts the bank's LOCAL day, and a jammed withdrawal does not eat the limit
        ZoneId india = ZoneId.of("Asia/Kolkata");
        long[] now = { ZonedDateTime.of(2026, 9, 26, 5, 0, 0, 0, india).toInstant().toEpochMilli() };   // 05:00 in Mumbai
        core.open("A17", 100_000);
        DailyCap local = new DailyCap(core, 20_000, () -> now[0], india);
        check(local.debit("A17", 15_000, "K17-a") == BankReply.OK, "15,000 at 05:00");
        now[0] += 3_600_000;                                          // 06:00: a UTC day rolled over at 05:30, this one did not
        check(local.debit("A17", 10_000, "K17-b") == BankReply.DECLINED, "10,000 more at 06:00 the same morning is over the cap");
        now[0] += 19 * 3_600_000;                                     // 01:00 the next night: a new local day
        check(local.debit("A17", 10_000, "K17-c") == BankReply.OK, "after midnight in Mumbai the limit is fresh");
        core.open("A17j", 100_000);
        CashDispenser d17 = new CashDispenser(new JammingFeeder(1));
        d17.refill(Note.N2000, 20); d17.refill(Note.N500, 20);
        ATM m17 = new ATM("T17", new DailyCap(core, 20_000, () -> now[0], india), d17);
        m17.setClock(() -> now[0]);
        m17.insertCard(new Card("CARD-1", "A17j"));
        m17.enterPin("1234");
        try { m17.withdraw(15_000); } catch (WithdrawalFailed jammed) { }
        Withdrawal w17 = null;
        try { w17 = m17.withdraw(10_000); } catch (WithdrawalFailed f) { }
        check(w17 != null && w17.state == TxnState.DISPENSED, "a jammed 15,000 was reversed, so it does not count: 10,000 more is paid");

        // 18. the state-object version: a kept card leaves the machine idle and ready for the next customer
        core.issueCard("CARD-18", "1234");
        StateMachine sm = new StateMachine(core, new CashDispenser(new WorkingFeeder()));
        sm.insertCard(new Card("CARD-18", "A1"));
        for (int i = 0; i < 3; i++) try { sm.enterPin("0000"); } catch (RuntimeException e) { }
        boolean ready = true;
        try { sm.insertCard(new Card("CARD-1", "A1")); } catch (IllegalStateException e) { ready = false; }
        check(ready && sm.where().equals("HasCardState"), "after the card is kept the state machine is IDLE and takes the next card");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
