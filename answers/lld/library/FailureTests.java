import java.time.*;
import java.util.*;
import java.util.concurrent.*;

/**
 * Fourteen claims the design makes, each proven by a few lines. Run it with
 * javac Main.java Extensions.java FailureTests.java && java FailureTests
 * It prints ALL PASS, or the failures and a non-zero exit code.
 */
public class FailureTests {
    static int failed = 0;
    static final String CC = "9780132350884", EJ = "9780134685991", CA = "9780134494166", PP = "9780135957059";

    /** Record one claim. Prints ok or FAIL with the claim's name. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "  ok   " : "  FAIL ") + what);
        if (!ok) failed++;
    }
    /** The reason a call was refused, or null if it went through. */
    static Refusal refusal(Runnable r) {
        try { r.run(); return null; } catch (Refused e) { return e.why; }
    }
    /** 10:00 on a day of September 2026 in Kolkata; day 31 and later roll into October. */
    static long day(int d) { return Main.at(9, 1, 10, 0) + (d - 1) * 86_400_000L; }
    /** A library on the test's clock: four titles, no copies yet, and the members named. */
    static Library fresh(long[] now, String... memberIds) {
        Library lib = new Library(Main.IST, 3);
        lib.setClock(() -> now[0]);
        lib.configure(new StandardTerms(), new CappedFine(new PerDayFine(2_000), 50_000));
        lib.addBook(CC, "Clean Code", "Robert C. Martin", 60_000);
        lib.addBook(EJ, "Effective Java", "Joshua Bloch", 55_000);
        lib.addBook(CA, "Clean Architecture", "Robert C. Martin", 50_000);
        lib.addBook(PP, "The Pragmatic Programmer", "David Thomas", 70_000);
        for (String id : memberIds) lib.register(id, id, Tier.REGULAR);
        return lib;
    }
    /** A listener that remembers what it heard; safe to call from many threads. */
    static final class Heard implements LibraryListener {
        final List<LibraryEvent> events = new CopyOnWriteArrayList<>();
        public void onEvent(LibraryEvent e) { events.add(e); }
        /** Did this member get a notice of this kind? */
        boolean got(EventKind k, String member) { return events.stream().anyMatch(e -> e.kind() == k && e.memberId().equals(member)); }
    }

    public static void main(String[] args) throws Exception {
        // 1. the last copy: fifty members at one latch, exactly one loan
        System.out.println("1. fifty members, one copy");
        long[] t1 = { day(1) };
        List<String> fifty = new ArrayList<>();
        for (int i = 0; i < 50; i++) fifty.add("m" + i);
        Library one = fresh(t1, fifty.toArray(new String[0]));
        one.addCopy(PP, "PP-1");
        CountDownLatch go = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        List<Future<Refusal>> tries = new ArrayList<>();
        for (String id : fifty) tries.add(pool.submit(() -> { go.await(); return refusal(() -> one.checkout(id, PP)); }));
        go.countDown();
        int won = 0, notAvailable = 0;
        for (Future<Refusal> f : tries) { Refusal r = f.get(); if (r == null) won++; else if (r == Refusal.NOT_AVAILABLE) notAvailable++; }
        check(won == 1 && notAvailable == 49, "exactly one loan; the other 49 were told NOT_AVAILABLE");
        check(one.onShelf(PP) == 0 && one.status("PP-1") == CopyStatus.LOANED, "the shelf is empty and the copy is LOANED, not lost");
        check(one.borrowersOf(PP).size() == 1, "and exactly one member has it");

        // 2. three returns cross twenty requests: no copy on the shelf while anyone waits, in every round
        System.out.println("2. returns racing requests, 30 rounds");
        boolean allHeld = true;
        for (int round = 0; round < 30; round++) {
            long[] t2 = { day(10) };
            Library busy = fresh(t2);
            for (int i = 1; i <= 3; i++) busy.addCopy(CA, "CA-" + i);
            for (int i = 0; i < 3; i++) { busy.register("b" + i, "b", Tier.REGULAR); busy.checkout("b" + i, CA); }
            for (int i = 0; i < 20; i++) busy.register("w" + i, "w", Tier.REGULAR);
            Desk desk = new Desk(busy);
            CountDownLatch start = new CountDownLatch(1);
            List<Future<?>> jobs = new ArrayList<>();
            for (int i = 1; i <= 3; i++) { String bc = "CA-" + i; jobs.add(pool.submit(() -> { start.await(); return busy.returnCopy(bc); })); }
            for (int i = 0; i < 20; i++) { String id = "w" + i; jobs.add(pool.submit(() -> { start.await(); return desk.borrow(id, CA); })); }
            start.countDown();
            for (Future<?> f : jobs) f.get();
            int served = 0, waiting = 0, both = 0;
            for (int i = 0; i < 20; i++) {
                boolean lent = !busy.loansOf("w" + i).isEmpty();
                HoldSlip h = busy.holdOf("w" + i, CA);
                if (lent) served++;
                if (h != null && h.status() == HoldStatus.READY) served++;
                if (h != null && h.status() == HoldStatus.WAITING) waiting++;
                if (lent && h != null) both++;
            }
            if (served != 3 || waiting != 17 || both != 0 || busy.onShelf(CA) != 0) allHeld = false;
        }
        check(allHeld, "every round: 3 members served, 17 waiting, nobody served twice, 0 copies on the shelf");

        // 3. the limit, and one copy of a title per member
        System.out.println("3. the limit");
        long[] t3 = { day(1) };
        Library lim = fresh(t3, "ravi");
        lim.addCopy(CC, "CC-1"); lim.addCopy(CC, "CC-2"); lim.addCopy(EJ, "EJ-1"); lim.addCopy(CA, "CA-1"); lim.addCopy(PP, "PP-1");
        lim.checkout("ravi", CC); lim.checkout("ravi", EJ); lim.checkout("ravi", CA);
        check(refusal(() -> lim.checkout("ravi", PP)) == Refusal.LIMIT_REACHED, "a fourth book is refused: LIMIT_REACHED");
        check(lim.onShelf(PP) == 1, "and the refused copy never left the shelf");
        lim.returnCopy("EJ-1");
        check(refusal(() -> lim.checkout("ravi", CC)) == Refusal.ALREADY_HAS_TITLE, "a second Clean Code is refused although CC-2 is on the shelf");
        check(refusal(() -> lim.checkout("ravi", PP)) == null, "after one return, the fourth title goes through");

        // 4. the FIFO queue: a returned copy goes to the first in line, never to the shelf or a stranger
        System.out.println("4. the queue");
        long[] t4 = { day(1) };
        Library q = fresh(t4, "asha", "meera", "kabir", "ravi", "dev");
        q.addCopy(CC, "CC-1");
        q.checkout("asha", CC);
        q.placeHold("meera", CC); q.placeHold("kabir", CC); q.placeHold("ravi", CC);
        check(q.position("meera", CC) == 1 && q.position("kabir", CC) == 2 && q.position("ravi", CC) == 3, "positions 1, 2, 3 in the order they asked");
        List<String> order = new ArrayList<>();
        order.add(q.returnCopy("CC-1").heldFor());
        check(q.onShelf(CC) == 0 && q.status("CC-1") == CopyStatus.ON_HOLD, "the returned copy skips the shelf");
        check(refusal(() -> q.checkout("dev", CC)) == Refusal.NOT_AVAILABLE, "a walk-in cannot borrow the copy set aside for meera");
        check(refusal(() -> q.checkout("kabir", CC)) == Refusal.NOT_AVAILABLE, "nor can kabir, who is second");
        q.checkout("meera", CC); order.add(q.returnCopy("CC-1").heldFor());
        q.checkout("kabir", CC); order.add(q.returnCopy("CC-1").heldFor());
        q.checkout("ravi", CC);  order.add(q.returnCopy("CC-1").heldFor());
        check(order.equals(Arrays.asList("meera", "kabir", "ravi", null)), "served meera, kabir, ravi, then the shelf: " + order);
        check(q.onShelf(CC) == 1, "with nobody left waiting, the copy is on the shelf");

        // 5. the pickup date: the copy waits three days, then moves to the next member, then to the shelf
        System.out.println("5. he never collects it");
        long[] t5 = { day(10) };
        Library pick = fresh(t5, "asha", "meera", "kabir");
        Heard heard5 = new Heard();
        pick.addListener(heard5);
        pick.addCopy(CC, "CC-1");
        pick.checkout("asha", CC);
        pick.placeHold("meera", CC); pick.placeHold("kabir", CC);
        t5[0] = day(14);
        pick.returnCopy("CC-1");
        check(pick.holdOf("meera", CC).pickupBy().equals(LocalDate.of(2026, 9, 17)), "set aside for meera until the 17th");
        t5[0] = day(17);
        check(pick.holdOf("meera", CC).status() == HoldStatus.READY, "on the 17th it is still hers");
        t5[0] = day(18);
        check(pick.holdOf("meera", CC) == null && pick.holdOf("kabir", CC).status() == HoldStatus.READY,
              "on the 18th the first call hands it to kabir; no timer thread, no sleep");
        check(heard5.got(EventKind.HOLD_EXPIRED, "meera") && heard5.got(EventKind.HOLD_READY, "kabir"), "meera hears it expired, kabir hears it is ready");
        t5[0] = day(22);
        check(pick.onShelf(CC) == 1 && pick.status("CC-1") == CopyStatus.AVAILABLE, "kabir never came either and nobody waits: back on the shelf");

        // 6. renewal: refused while others wait, beyond two renewals, and when overdue
        System.out.println("6. renewal");
        long[] t6 = { day(1) };
        Library ren = fresh(t6, "ravi", "asha", "meera");
        ren.addCopy(EJ, "EJ-1"); ren.addCopy(CC, "CC-1");
        ren.checkout("ravi", EJ);                                                  // due the 15th
        t6[0] = day(10);
        check(ren.renew("EJ-1").due().equals(LocalDate.of(2026, 9, 29)), "renewed on the 10th: due the 15th becomes the 29th");
        t6[0] = day(16);
        check(ren.overdue().isEmpty(), "on the 16th it is not overdue: the loan moved in the due index");
        check(ren.renew("EJ-1").due().equals(LocalDate.of(2026, 10, 13)), "a second renewal: the 13th of October");
        check(refusal(() -> ren.renew("EJ-1")) == Refusal.RENEWAL_LIMIT, "a third is refused");
        ren.checkout("asha", CC);
        ren.placeHold("meera", CC);
        check(refusal(() -> ren.renew("CC-1")) == Refusal.OTHERS_WAITING, "asha cannot renew while meera waits");
        ren.cancelHold("meera", CC);
        t6[0] = day(40);
        check(refusal(() -> ren.renew("CC-1")) == Refusal.OVERDUE, "and an overdue book is not renewed: return it and pay");

        // 7. fines: the due date is free, then Rs 20 a day, never more than Rs 500; owing more than Rs 100 blocks borrowing
        System.out.println("7. fines");
        long[] t7 = { day(1) };
        Library fin = fresh(t7, "asha");
        fin.addCopy(PP, "PP-1");
        fin.checkout("asha", PP);                                                  // due the 15th
        t7[0] = day(15);
        check(fin.returnCopy("PP-1").finePaise() == 0, "back on the due date: no fine");
        fin.checkout("asha", PP);                                                  // due the 29th
        t7[0] = day(30);
        check(fin.returnCopy("PP-1").finePaise() == 2_000, "one day late: Rs 20");
        fin.checkout("asha", PP);                                                  // due the 14th of October
        t7[0] = day(44 + 40);
        check(fin.returnCopy("PP-1").finePaise() == 50_000, "forty days late: capped at Rs 500, not Rs 800");
        check(fin.dues("asha") == 52_000, "both fines are on her account: Rs 520");
        check(refusal(() -> fin.checkout("asha", PP)) == Refusal.OWES_FINES, "owing more than Rs 100, she cannot borrow");
        boolean badAmount = false;
        try { fin.payFine("asha", 0); } catch (IllegalArgumentException e) { badAmount = true; }
        fin.payFine("asha", 52_000);
        check(badAmount && fin.dues("asha") == 0 && refusal(() -> fin.checkout("asha", PP)) == null, "a zero payment is refused; once she pays, she borrows");

        // 8. the fine rule throws halfway through a return: nothing changed, the retry charges once
        System.out.println("8. a broken fine rule, and a double scan");
        long[] t8 = { day(1) };
        Library brk = fresh(t8, "asha", "meera");
        brk.addCopy(CC, "CC-1");
        brk.checkout("asha", CC);
        brk.placeHold("meera", CC);
        brk.configure(new StandardTerms(), (loan, d) -> { throw new RuntimeException("holiday calendar is down"); });
        t8[0] = day(17);
        boolean threw = false;
        try { brk.returnCopy("CC-1"); } catch (RuntimeException e) { threw = true; }
        check(threw && brk.loansOf("asha").size() == 1 && brk.status("CC-1") == CopyStatus.LOANED, "the return failed and the book is still on asha's card");
        check(brk.position("meera", CC) == 1 && brk.dues("asha") == 0, "meera is still first in line; asha owes nothing yet");
        brk.configure(new StandardTerms(), (loan, d) -> -500);                    // a rule that would pay the member
        boolean refusedNegative = false;
        try { brk.returnCopy("CC-1"); } catch (IllegalStateException e) { refusedNegative = true; }
        check(refusedNegative && brk.dues("asha") == 0 && brk.status("CC-1") == CopyStatus.LOANED, "a rule that returns a negative fine is refused too, and changes nothing");
        brk.configure(new StandardTerms(), new CappedFine(new PerDayFine(2_000), 50_000));
        Receipt r8 = brk.returnCopy("CC-1");
        check(r8.finePaise() == 4_000 && "meera".equals(r8.heldFor()), "the retry: Rs 40 for two days, and the copy goes to meera");
        check(refusal(() -> brk.returnCopy("CC-1")) == Refusal.NOT_ON_LOAN && brk.dues("asha") == 4_000, "a second scan is refused: no second fine");

        // 9. listeners: a broken one cannot stop a return or the others; they run after the unlock
        System.out.println("9. listeners");
        long[] t9 = { day(1) };
        Library lis = fresh(t9, "asha", "meera");
        lis.addListener(e -> { throw new RuntimeException("SMS gateway is down"); });
        Heard heard9 = new Heard();
        lis.addListener(heard9);
        final boolean[] readable = { false };
        lis.addListener(e -> {                                                     // a listener that asks the library, from another thread
            FutureTask<Integer> ask = new FutureTask<>(() -> lis.onShelf(CC));
            new Thread(ask).start();
            try { readable[0] = ask.get(1, TimeUnit.SECONDS) == 0; } catch (Exception x) { readable[0] = false; }
        });
        lis.addCopy(CC, "CC-1");
        lis.checkout("asha", CC);
        lis.placeHold("meera", CC);
        Receipt r9 = lis.returnCopy("CC-1");
        check("meera".equals(r9.heldFor()) && heard9.got(EventKind.HOLD_READY, "meera"), "the SMS listener threw, the return still went through, the next listener still heard");
        check(readable[0], "a listener can read the library: it is called after the unlock, not inside it");

        // 10. every path that frees a copy puts the queue before the shelf
        System.out.println("10. every way a copy frees up");
        long[] t10 = { day(1) };
        Library paths = fresh(t10, "asha", "meera", "kabir", "ravi", "dev");
        paths.addCopy(CC, "CC-1");
        paths.checkout("asha", CC);
        paths.placeHold("meera", CC); paths.placeHold("kabir", CC); paths.placeHold("ravi", CC);
        paths.cancelHold("meera", CC);
        check("kabir".equals(paths.returnCopy("CC-1").heldFor()), "a cancelled hold is skipped: the copy goes to kabir");
        paths.cancelHold("kabir", CC);
        check(paths.holdOf("ravi", CC).status() == HoldStatus.READY, "kabir cancels his READY hold: the copy moves on to ravi");
        check(refusal(() -> paths.unregister("ravi")) == null && paths.onShelf(CC) == 1, "ravi leaves: his copy goes back on the shelf, nobody waits");
        paths.checkout("dev", CC);
        paths.placeHold("asha", CC);
        paths.addCopy(CC, "CC-2");
        check(paths.holdOf("asha", CC).status() == HoldStatus.READY && paths.onShelf(CC) == 0, "a new copy goes to asha, who was waiting, not to the shelf");
        check(refusal(() -> paths.unregister("dev")) == Refusal.HAS_LOANS, "dev cannot leave with a book out");

        // 11. a lost book: the price plus the fine so far; the queue keeps its places for the next copy
        System.out.println("11. a lost book");
        long[] t11 = { day(1) };
        Library lost = fresh(t11, "asha", "meera");
        lost.addCopy(PP, "PP-1");
        lost.checkout("asha", PP);                                                 // due the 15th
        lost.placeHold("meera", PP);
        t11[0] = day(20);
        check(lost.reportLost("PP-1") == 70_000 + 5 * 2_000, "lost on the 20th: Rs 700 for the book + Rs 100 for five days");
        check(lost.status("PP-1") == CopyStatus.LOST && lost.loansOf("asha").isEmpty(), "the copy is out of circulation and her slot is free");
        check(lost.position("meera", PP) == 1, "meera keeps her place");
        lost.addCopy(PP, "PP-2");
        check(lost.holdOf("meera", PP).status() == HoldStatus.READY, "and the replacement copy goes straight to her");

        // 12. search: word prefixes, both fields, the limit, any case
        System.out.println("12. search");
        long[] t12 = { day(1) };
        Library cat = fresh(t12);
        cat.addCopy(CC, "CC-1"); cat.addCopy(CC, "CC-2");
        check(cat.searchTitle("clea", 10).stream().map(Found::title).toList().equals(List.of("Clean Code", "Clean Architecture")), "'clea' finds both Clean books");
        check(cat.searchTitle("CLEAN co", 10).stream().map(Found::title).toList().equals(List.of("Clean Code")), "'CLEAN co' finds only Clean Code");
        check(cat.searchTitle("clean", 1).size() == 1 && cat.searchTitle("", 5).isEmpty() && cat.searchTitle("zzz", 5).isEmpty(), "the limit holds; empty and unknown queries find nothing");
        check(cat.searchAuthor("mart", 10).size() == 2 && cat.searchAuthor("bloch", 10).get(0).title().equals("Effective Java"), "author prefixes: 'mart' finds Robert C. Martin twice");
        check(cat.searchTitle("clean code", 5).get(0).onShelf() == 2, "a hit says how many copies are on the shelf");

        // 13. the follow-ups keep their own promises (Extensions.java)
        System.out.println("13. follow-ups: rules, ids, racks, locks");
        long[] t13 = { day(1) };
        Library ext = fresh(t13);
        ext.register("riya", "Riya", Tier.STUDENT);
        ext.register("ravi", "Ravi", Tier.REGULAR);
        ext.configure(new TieredTerms(), new CapAtPrice(new StudentRate(new GraceDays(new PerDayFine(2_000), 2))));
        ext.addCopy(CC, "CC-1"); ext.addCopy(EJ, "EJ-1"); ext.addCopy(CA, "CA-1"); ext.addCopy(PP, "PP-1");
        ext.checkout("riya", CC); ext.checkout("riya", EJ);
        check(refusal(() -> ext.checkout("riya", CA)) == Refusal.LIMIT_REACHED, "a student may have two books, not three");
        ext.checkout("ravi", CA);
        t13[0] = day(17);                                                          // two days late
        check(ext.returnCopy("CA-1").finePaise() == 0, "two days late is inside the grace period: no fine");
        t13[0] = day(22);                                                          // seven days late
        check(ext.returnCopy("CC-1").finePaise() == 7_000, "a student seven days late pays half of Rs 140: Rs 70");
        ext.checkout("ravi", PP);                                                  // due the 5th of October
        t13[0] = day(35 + 400);
        check(ext.returnCopy("PP-1").finePaise() == 70_000, "four hundred days late: capped at the book's price, Rs 700");
        BookIdGenerator gen = new BookIdGenerator(1000);
        Set<String> made = ConcurrentHashMap.newKeySet();
        List<Future<?>> adds = new ArrayList<>();
        for (int i = 0; i < 1_000; i++) adds.add(pool.submit(() -> made.add(gen.next("J. K. Rowling"))));
        for (Future<?> f : adds) f.get();
        check(made.size() == 1_000 && made.contains("ROW1001") && made.contains("ROW2000"), "1,000 Rowling books added at once: 1,000 different ids, ROW1001 to ROW2000");
        RackedShelf racks = new RackedShelf(3);
        check(racks.add("B1", List.of("c1", "c2")).equals(List.of(1, 2)) && racks.add("B1", List.of("c3", "c4")) == null,
              "racks: copies go to racks 1 and 2; two more do not fit and none is placed");
        check(racks.borrowByBook("B1").equals("c1@1") && racks.giveBack("c1") == 1, "borrow by book id takes rack 1; the return goes back to rack 1");
        racks.borrowByBook("B1");                                                  // c1 is out again: rack 1 is empty
        check(racks.add("B1", List.of("c3")) != null && racks.add("B1", List.of("c5")) == null && racks.giveBack("c1") > 0,
              "with c1 out, a third copy fits but a fourth is refused, so c1 still finds a rack when it comes back");
        TitleLocks titles = new TitleLocks(3);
        titles.addCopy("T", "T-1");
        List<Future<Refusal>> grab = new ArrayList<>();
        CountDownLatch go13 = new CountDownLatch(1);
        for (int i = 0; i < 40; i++) { String id = "p" + i; grab.add(pool.submit(() -> { go13.await(); return refusal(() -> titles.checkout(id, "T")); })); }
        go13.countDown();
        int got = 0, slots = 0;
        for (Future<Refusal> f : grab) if (f.get() == null) got++;
        for (int i = 0; i < 40; i++) slots += titles.loansOf("p" + i);
        check(got == 1 && slots == 1, "a lock per title: forty members, one copy, one loan, and the 39 losers gave their slots back");
        for (int i = 0; i < 5; i++) titles.addCopy("S" + i, "S" + i + "-1");
        List<Future<Refusal>> spree = new ArrayList<>();
        for (int i = 0; i < 5; i++) { String isbn = "S" + i; spree.add(pool.submit(() -> refusal(() -> titles.checkout("greedy", isbn)))); }
        int greedyGot = 0;
        for (Future<Refusal> f : spree) if (f.get() == null) greedyGot++;
        check(greedyGot == 3 && titles.loansOf("greedy") == 3, "one member, five titles at once, limit three: exactly three loans");

        // 14. more follow-ups: branches, reminders, the outbox, persistence, the copy's table, e-books
        System.out.println("14. follow-ups: branches, reminders, storage, e-books");
        BranchNetwork net = new BranchNetwork();
        net.hold(CC, "meera", "Indiranagar");
        BranchNetwork.Placement p = net.returned(CC, "CC-1", "Koramangala");
        check(p.where() == BranchNetwork.Where.IN_TRANSIT && p.atBranch().equals("Indiranagar") && net.arrived(p).where() == BranchNetwork.Where.READY,
              "returned at the wrong branch: in transit to meera's branch, READY when it arrives");
        check(net.returned(CC, "CC-2", "Koramangala").where() == BranchNetwork.Where.ON_SHELF, "with nobody waiting, it stays on this branch's shelf");
        long[] t14 = { day(1) };
        Library rem = fresh(t14, "asha", "ravi");
        rem.addCopy(CC, "CC-1"); rem.addCopy(EJ, "EJ-1");
        rem.checkout("asha", CC);                                                  // due the 15th
        t14[0] = day(3);
        rem.checkout("ravi", EJ);                                                  // due the 17th
        t14[0] = day(13);
        Heard due = new Heard();
        check(new DueSoonReminder(rem, due, 2).run() == 1 && due.got(EventKind.DUE_SOON, "asha"), "on the 13th only asha's book (due the 15th) is within two days");
        SmsOutbox outbox = new SmsOutbox();
        outbox.onEvent(new LibraryEvent(EventKind.HOLD_READY, "meera", CC, "CC-1", LocalDate.of(2026, 9, 17), 0));
        check(outbox.drain(e -> { throw new RuntimeException("503"); }) == 0 && outbox.pending() == 1, "the gateway is down: the message stays queued");
        check(outbox.drain(e -> true) == 1 && outbox.pending() == 0, "the gateway is back: it is sent once");
        InMemoryLibraryRepository repo = new InMemoryLibraryRepository();
        repo.addCopy("CC-9");
        List<Future<Boolean>> claims = new ArrayList<>();
        CountDownLatch go14 = new CountDownLatch(1);
        for (int i = 0; i < 50; i++) { String id = "c" + i; claims.add(pool.submit(() -> { go14.await(); return repo.claim("CC-9", id, LocalDate.of(2026, 9, 15)); })); }
        go14.countDown();
        int claimed = 0;
        for (Future<Boolean> f : claims) if (f.get()) claimed++;
        check(claimed == 1 && repo.overdue(LocalDate.of(2026, 9, 16)).equals(List.of("CC-9")), "fifty claims on one row: one wins; the overdue list finds it");
        BookCopy odd = new BookCopy("X-1", new Book("x", "x", "x", 0));
        CopyLife.move(odd, CopyStatus.LOANED);
        CopyLife.move(odd, CopyStatus.LOST);
        boolean refusedMove = false;
        try { CopyLife.move(odd, CopyStatus.LOANED); } catch (IllegalStateException e) { refusedMove = true; }
        check(refusedMove, "the copy's table refuses to lend a lost copy");
        EbookLending ebook = new EbookLending(2, 14);
        LocalDate d1 = LocalDate.of(2026, 9, 1);
        boolean a = ebook.borrow("asha", d1), b = ebook.borrow("ravi", d1), c = ebook.borrow("meera", d1);
        check(a && b && !c && ebook.free() == 0, "two licences: asha and ravi read, meera waits");
        check(ebook.tick(d1.plusDays(13)).isEmpty() && ebook.tick(d1.plusDays(14)).equals(List.of("meera")) && ebook.free() == 1,
              "on day 14 both loans end by themselves; one licence goes to meera, one is free");
        pool.shutdown();

        System.out.println(failed == 0 ? "ALL PASS" : failed + " FAILED");
        if (failed > 0) System.exit(1);
    }
}
