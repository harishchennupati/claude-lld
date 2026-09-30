import java.util.*;
import java.util.concurrent.*;

// targeted failure tests: each one proves a claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }
    static long sum(Collection<Long> xs) { long s = 0; for (long x : xs) s += x; return s; }

    public static void main(String[] args) throws Exception {
        Splitwise app = new Splitwise();

        // 1. fifty people post an expense to ONE group at the same instant: no update may be lost,
        //    and the sum of every balance must be exactly zero, because every paise owed is a paise owned.
        Group flat = app.newGroup("flat", "u0", "u1", "u2", "u3", "u4");
        List<Participant> five = List.of(Participant.of("u0"), Participant.of("u1"), Participant.of("u2"),
                                         Participant.of("u3"), Participant.of("u4"));
        ExecutorService pool = Executors.newFixedThreadPool(50);      // fifty threads, all parked on one latch
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> posted = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final int n = i;
            posted.add(pool.submit(() -> { go.await(); return flat.addExpense("x" + n, "u" + (n % 5), 100 + n, SplitType.EQUAL, five, "r" + n); }));
        }
        go.countDown();
        int applied = 0;
        for (Future<?> f : posted) { f.get(); applied++; }
        pool.shutdown();
        check(applied == 50, "50 concurrent expenses all landed");
        check(flat.history().size() == 50, "the audit log has 50 rows, not 49");
        check(sum(flat.balances().values()) == 0, "sum of all balances is exactly zero after the race");
        // the two maps must agree: what a user owes minus what is owed to them is the negative of their net
        boolean agree = true;
        Map<String, Map<String, Long>> owes = flat.owesTable();
        for (String u : flat.members()) {
            long out = sum(owes.getOrDefault(u, Map.of()).values()), in = 0;
            for (Map.Entry<String, Map<String, Long>> row : owes.entrySet()) in += row.getValue().getOrDefault(u, 0L);
            if (in - out != flat.netOf(u)) agree = false;
        }
        check(agree, "the pairwise map and the net map agree for every member");
        // and every number is exactly what one thread gets posting the same fifty expenses in order
        Group replay = app.newGroup("replay", "u0", "u1", "u2", "u3", "u4");
        for (int i = 0; i < 50; i++) replay.addExpense("x" + i, "u" + (i % 5), 100 + i, SplitType.EQUAL, five, "r" + i);
        check(flat.balances().equals(replay.balances()) && flat.owesTable().equals(replay.owesTable()),
              "every balance equals the same fifty expenses posted by one thread");

        // 2. an exact split that does not add up to the bill is refused, and NOTHING changes
        Group goa = app.newGroup("goa", "alice", "bob", "carol");
        goa.addExpense("e1", "alice", Money.rupees("300.00"), SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob"), Participant.of("carol")), "hotel");
        Map<String, Long> before = goa.balances();
        try {
            goa.addExpense("bad", "alice", Money.rupees("500.00"), SplitType.EXACT,
                List.of(new Participant("bob", Money.rupees("100.00")), new Participant("carol", Money.rupees("100.00"))), "oops");
            check(false, "an exact split that does not reconcile must throw");
        } catch (IllegalArgumentException e) { check(true, "exact split rejected: " + e.getMessage()); }
        check(before.equals(goa.balances()), "the rejected expense changed no balance");
        check(goa.history().size() == 1, "the rejected expense is not in the audit log");
        try {
            goa.addExpense("bad2", "alice", Money.rupees("500.00"), SplitType.PERCENT,
                List.of(new Participant("bob", 6000), new Participant("carol", 3000)), "oops");
            check(false, "percentages that do not add up to 100% must throw");
        } catch (IllegalArgumentException e) { check(true, "percent split rejected: " + e.getMessage()); }
        check(before.equals(goa.balances()), "the rejected percent expense changed no balance either");

        // 3. one rupee across three people: the paise must not vanish
        Group odd = app.newGroup("odd", "alice", "bob", "carol");
        odd.addExpense("r1", "alice", 100, SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob"), Participant.of("carol")), "chai");
        long shares = sum(odd.history().get(0).shares().stream().map(Share::paise).toList());
        check(shares == 100, "100 paise split three ways still sums to 100 (34 + 33 + 33)");
        check(odd.history().get(0).shares().get(0).paise() == 34, "the payer absorbs the odd paise: 34");
        check(sum(odd.balances().values()) == 0, "the balances of the rounded split sum to zero");
        check(odd.netOf("alice") == 66 && odd.netOf("bob") == -33, "alice is owed 66 paise, bob owes 33");

        // 4. delete reverses exactly, and keeps the row
        Group del = app.newGroup("del", "alice", "bob");
        Map<String, Long> empty = del.balances();
        del.addExpense("d1", "alice", Money.rupees("250.00"), SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob")), "pizza");
        check(del.netOf("bob") == -Money.rupees("125.00"), "bob owes 125.00 after the pizza");
        del.delete("d1");
        check(del.balances().equals(empty), "delete put every balance back exactly");
        check(del.owes("bob", "alice") == 0, "the pairwise entry is gone too");
        check(del.history().get(0).status() == ExpenseStatus.DELETED, "the expense is kept, marked DELETED");
        try { del.delete("d1"); check(false, "deleting twice must throw"); }
        catch (IllegalStateException e) { check(true, "a second delete is refused, not double-reversed"); }
        check(del.balances().equals(empty), "the refused second delete changed nothing");

        // 5. a settle-up brings the pair to zero
        Group s = app.newGroup("settle", "alice", "bob");
        s.addExpense("s0", "alice", Money.rupees("400.00"), SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob")), "cab");
        long owed = s.owes("bob", "alice");
        check(owed == Money.rupees("200.00"), "bob owes alice 200.00");
        s.settleUp("s1", "bob", "alice", owed);
        check(s.owes("bob", "alice") == 0 && s.owes("alice", "bob") == 0, "after the settle-up the pair is at zero");
        check(s.netOf("alice") == 0 && s.netOf("bob") == 0, "and both nets are zero");
        s.addExpense("s2", "alice", Money.rupees("100.00"), SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob")), "coffee");
        s.settleUp("s3", "bob", "alice", Money.rupees("20.00"));     // a PARTIAL payment
        check(s.owes("bob", "alice") == Money.rupees("30.00"), "a partial settle-up leaves the rest owed: 30.00");
        s.settleUp("s4", "bob", "alice", Money.rupees("100.00"));    // MORE than he owes: no special case
        check(s.owes("alice", "bob") == Money.rupees("70.00"), "overpaying just flips the pair: alice owes bob 70.00");

        // 6. simplify is a suggestion: it must not move anybody's net by a paise, and its transfers must clear everyone
        Group sim = app.newGroup("sim", "a", "b", "c", "d");
        sim.addExpense("p1", "a", Money.rupees("400.00"), SplitType.EQUAL,
            List.of(Participant.of("a"), Participant.of("b"), Participant.of("c"), Participant.of("d")), "villa");
        sim.addExpense("p2", "b", Money.rupees("120.00"), SplitType.EQUAL,
            List.of(Participant.of("c"), Participant.of("d")), "tickets");
        Map<String, Long> netBefore = sim.balances();
        List<Transfer> plan = sim.simplify();
        check(sim.balances().equals(netBefore), "simplify changed nobody's net");
        Map<String, Long> after = new TreeMap<>(netBefore);
        for (Transfer t : plan) { after.merge(t.from(), t.paise(), Long::sum); after.merge(t.to(), -t.paise(), Long::sum); }
        boolean allZero = after.values().stream().allMatch(v -> v == 0);
        check(allZero, "paying the suggested transfers clears every single person");
        check(plan.size() <= netBefore.size() - 1, "at most n-1 transfers for n people with a balance: " + plan.size());

        // 7. a notifier that throws must not break the expense
        Group noisy = app.newGroup("noisy", "alice", "bob");
        noisy.addObserver((gid, e) -> { throw new RuntimeException("push gateway is down"); });
        Expense landed = noisy.addExpense("n1", "alice", Money.rupees("100.00"), SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob")), "milk");
        check(landed != null && noisy.netOf("bob") == -Money.rupees("50.00"), "the expense landed although the notifier threw");
        check(noisy.history().size() == 1, "and it is in the audit log exactly once");

        // 8. a rule written next year that loses a paise is caught before anything is written
        Group buggy = app.newGroup("buggy", "alice", "bob");
        buggy.configure(Map.of(SplitType.EQUAL, (total, payer, parts) -> {         // deliberately wrong: drops a paise
            List<Share> out = new ArrayList<>();
            for (Participant p : parts) out.add(new Share(p.userId(), total / parts.size() - 1));
            return out;
        }), new MinCashFlow());
        try {
            buggy.addExpense("b1", "alice", Money.rupees("100.00"), SplitType.EQUAL,
                List.of(Participant.of("alice"), Participant.of("bob")), "broken rule");
            check(false, "a rule whose shares do not sum to the bill must be caught");
        } catch (IllegalStateException e) { check(true, "CheckedSplit caught the broken rule: " + e.getMessage()); }
        check(buggy.balances().isEmpty(), "and the broken rule wrote nothing at all");

        // 9. the same expense id twice (a retried request) is applied once
        Group idem = app.newGroup("idem", "alice", "bob");
        List<Participant> two = List.of(Participant.of("alice"), Participant.of("bob"));
        Expense first = idem.addExpense("k1", "alice", Money.rupees("80.00"), SplitType.EQUAL, two, "tea");
        Expense again = idem.addExpense("k1", "alice", Money.rupees("80.00"), SplitType.EQUAL, two, "tea");
        check(first == again && idem.netOf("bob") == -Money.rupees("40.00"), "a retried expense id is applied exactly once");

        // 10. money is exact: a thousand indivisible bills. In paise nothing is lost. The same sum in double
        //     drifts, which is the whole reason there is no double anywhere in Main.java.
        Group chai = app.newGroup("chai", "alice", "bob", "carol");
        List<Participant> trio = List.of(Participant.of("alice"), Participant.of("bob"), Participant.of("carol"));
        for (int i = 0; i < 1000; i++) chai.addExpense("c" + i, "alice", 100, SplitType.EQUAL, trio, "chai");
        check(sum(chai.balances().values()) == 0, "1000 bills of 1.00 split three ways still sum to exactly zero");
        check(chai.netOf("alice") == 66_000, "alice is owed exactly 660.00: 66 paise a time, a thousand times");
        double drift = 0;
        for (int i = 0; i < 1000; i++) drift += 1.00 / 3;              // the same split in rupees, as a double
        check(drift * 3 != 1000.0, "the same thousand splits in double do not add back to 1000.00: " + (drift * 3));

        // 11. nobody walks away from a debt: leaving is refused until that person's net is zero
        Group leave = app.newGroup("leave", "alice", "bob", "carol");
        leave.addExpense("l1", "alice", Money.rupees("300.00"), SplitType.EQUAL, trio, "taxi");
        try { leave.removeMember("carol"); check(false, "a member owing 100.00 must not be able to leave"); }
        catch (IllegalStateException e) { check(true, "leaving is refused while a balance is open: " + e.getMessage()); }
        leave.settleUp("l2", "carol", "alice", Money.rupees("100.00"));
        leave.removeMember("carol");
        check(!leave.members().contains("carol"), "once her net is zero, carol can leave");
        check(leave.history().size() == 2, "and her rows stay in the log: leaving is not erasing");
        try {
            leave.addExpense("l3", "alice", Money.rupees("50.00"), SplitType.EQUAL,
                List.of(Participant.of("alice"), Participant.of("carol")), "after she left");
            check(false, "an ex-member must not appear in a new expense");
        } catch (IllegalArgumentException e) { check(true, "an ex-member cannot be put in a new expense"); }
        // a zero net can hide a loop: bob owes carol 150.00 and carol owes alice 150.00. Her debts must pass through
        // her as she leaves, or two debts would name somebody who is gone and could never be settled.
        Group loop = app.newGroup("loop", "alice", "bob", "carol");
        loop.addExpense("o1", "carol", Money.rupees("150.00"), SplitType.EXACT,
            List.of(new Participant("bob", Money.rupees("150.00"))), "bob's ticket");
        loop.addExpense("o2", "alice", Money.rupees("150.00"), SplitType.EXACT,
            List.of(new Participant("carol", Money.rupees("150.00"))), "carol's ticket");
        Map<String, Long> netsBefore = loop.balances();
        Set<String> seen = loop.members();
        loop.removeMember("carol");
        check(loop.owes("bob", "carol") == 0 && loop.owes("carol", "alice") == 0, "after carol leaves, no pair names her");
        check(loop.owes("bob", "alice") == Money.rupees("150.00") && loop.balances().equals(netsBefore),
              "bob now owes alice 150.00, and nobody's net moved");
        check(seen.contains("carol"), "members() handed out a copy: the list taken earlier still has carol");
        Map<String, Long> netsAfter = loop.balances();
        try { loop.delete("o1"); check(false, "deleting an expense that names someone who left must be refused"); }
        catch (IllegalArgumentException e) { check(true, "an expense naming someone who left cannot be deleted"); }
        try {
            loop.edit("o2", "alice", Money.rupees("150.00"), SplitType.EXACT,
                List.of(new Participant("bob", Money.rupees("150.00"))), "moved to bob");
            check(false, "editing an expense that names someone who left must be refused");
        } catch (IllegalArgumentException e) { check(true, "nor edited: reversing it would reopen her balance"); }
        check(loop.balances().equals(netsAfter) && loop.netOf("carol") == 0, "and the refused changes moved nothing");

        // 12. the ladder's second rung needs no lock of ours and is still exact: 200 moves from 8 threads, one map
        PairLedger pairs = new PairLedger();
        ExecutorService pool2 = Executors.newFixedThreadPool(8);
        CountDownLatch go2 = new CountDownLatch(1);
        List<Future<?>> moves = new ArrayList<>();
        for (int i = 0; i < 200; i++) {
            final int n = i;
            moves.add(pool2.submit(() -> { go2.await(); pairs.move("u" + (n % 4), "v" + (n % 3), 100); return null; }));
        }
        go2.countDown();
        for (Future<?> f : moves) f.get();
        pool2.shutdown();
        long moved = 0;
        for (int a = 0; a < 4; a++) for (int b = 0; b < 3; b++) moved += pairs.owed("u" + a, "v" + b);
        check(moved == 200 * 100, "200 pair moves with no lock of ours all landed: " + Money.fmt(moved));
        pairs.move("u0", "v0", -pairs.owed("u0", "v0"));
        check(pairs.livePairs() == 11, "a pair that reaches zero drops out of the map: " + pairs.livePairs() + " left");

        // 13. one group per id. A second newGroup with a used id is refused (a plain put() would drop the first
        //     group and its balances), and two friends adding their first expense at the same instant share one group.
        Group dupGroup = app.newGroup("dup", "alice", "bob");
        dupGroup.addExpense("g1", "alice", Money.rupees("100.00"), SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob")), "lunch");
        try { app.newGroup("dup", "alice", "bob"); check(false, "a second group with the same id must be refused"); }
        catch (IllegalArgumentException e) { check(true, "a second group with the same id is refused"); }
        check(app.group("dup") == dupGroup && dupGroup.netOf("bob") == -Money.rupees("50.00"), "and the first group keeps its balances");
        int lost = 0;
        for (int t = 0; t < 200; t++) {
            Splitwise fresh = new Splitwise();
            CountDownLatch start = new CountDownLatch(1);
            ExecutorService both = Executors.newFixedThreadPool(2);
            List<Participant> pair = List.of(Participant.of("ann"), Participant.of("ben"));
            Future<?> a = both.submit(() -> { start.await(); return Friends.between(fresh, "ann", "ben").addExpense("f1", "ann", 100, SplitType.EQUAL, pair, "tea"); });
            Future<?> b = both.submit(() -> { start.await(); return Friends.between(fresh, "ben", "ann").addExpense("f2", "ben", 300, SplitType.EQUAL, pair, "cab"); });
            start.countDown(); a.get(); b.get(); both.shutdown();
            if (fresh.group("pair:ann:ben").history().size() != 2) lost++;
        }
        check(lost == 0, "two friends creating their pair at the same instant: one group, both expenses, in 200 of 200 runs");
        try {
            new Recurring("rent", "ann", 100, List.of(Participant.of("ann"), Participant.of("ben")), 0, 0);
            check(false, "a schedule with a zero period must be refused");
        } catch (IllegalArgumentException e) { check(true, "a schedule with a zero period is refused: post() would never end"); }

        // 14. greedy is short, not always the shortest. a owes 400 and b owes 300; c, d and e are owed 200, 200, 300:
        //     greedy makes four payments where three would do. On random groups the exact plan is never longer.
        Map<String, Long> tricky = Map.of("a", -40000L, "b", -30000L, "c", 20000L, "d", 20000L, "e", 30000L);
        List<Transfer> greedy = new MinCashFlow().simplify(tricky), fewest = new FewestPayments().simplify(tricky);
        check(greedy.size() == 4 && fewest.size() == 3, "greedy makes 4 payments where 3 would do: " + fewest);
        check(SimplifyProof.settlesEveryone(tricky, greedy) && SimplifyProof.settlesEveryone(tricky, fewest),
              "and both plans clear everyone");
        Random rnd = new Random(7);
        boolean exactOk = true;
        for (int t = 0; t < 300; t++) {
            Map<String, Long> net = new TreeMap<>();
            long total = 0;
            int people = 2 + rnd.nextInt(7);
            for (int i = 0; i < people - 1; i++) { long v = (rnd.nextInt(13) - 6) * 100L; net.put("p" + i, v); total += v; }
            net.put("p" + (people - 1), -total);
            List<Transfer> f = new FewestPayments().simplify(net);
            if (!SimplifyProof.settlesEveryone(net, f) || f.size() > new MinCashFlow().simplify(net).size()) exactOk = false;
        }
        check(exactOk, "on 300 random groups the exact plan clears everyone and is never longer than greedy");

        // 15. one user, many groups: the total is the sum over their groups, and joining moves no money
        Directory dir = new Directory(new Splitwise());
        Group trip2 = dir.create("trip", "alice", "bob");
        Group home = dir.create("home", "alice", "bob", "carol");
        trip2.addExpense("t1", "alice", Money.rupees("300.00"), SplitType.EQUAL,
            List.of(Participant.of("alice"), Participant.of("bob")), "taxi");
        home.addExpense("h1", "bob", Money.rupees("90.00"), SplitType.EQUAL, trio, "milk");
        dir.join("trip", "carol");
        check(dir.netEverywhere("bob") == -Money.rupees("90.00"), "bob everywhere: -150.00 on the trip, +60.00 at home = -90.00");
        check(dir.owesEverywhere("bob", "alice") == Money.rupees("120.00"), "bob owes alice 120.00 across both groups (150.00 - 30.00)");
        check(trip2.members().contains("carol") && trip2.netOf("carol") == 0, "carol joined the trip, and joining moved no money");
        check(AuditView.passbook(home, "carol").size() == 1 && AuditView.passbook(trip2, "carol").isEmpty(),
              "carol's passbook lists the milk at home and nothing from the trip");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
