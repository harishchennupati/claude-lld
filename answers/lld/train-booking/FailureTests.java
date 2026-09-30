import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * One test per claim the design makes. Each one is the bug that ships if the claim is dropped, so a regression
 * shows up as a FAIL line instead of two passengers on one berth between Pune and Solapur.
 */
public class FailureTests {
    static int failures = 0;
    /** Print PASS or FAIL for one claim, and count the failures. */
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /**
     * A gateway that keeps the idempotency contract and counts what it did, so a test can say "charged exactly
     * once": charges counts money actually taken, refunds counts references actually given back.
     */
    static class CountingGateway implements PaymentGateway {
        final AtomicInteger charges = new AtomicInteger(), refunds = new AtomicInteger();
        private final Map<String, String> byKey = new ConcurrentHashMap<>();
        private final Set<String> refunded = ConcurrentHashMap.newKeySet();
        private final boolean approve;
        CountingGateway(boolean approve) { this.approve = approve; }
        /** One reference per key; null when this gateway declines everything. */
        public String charge(String key, long paise) { if (!approve) return null; return byKey.computeIfAbsent(key, k -> "REF-" + charges.incrementAndGet()); }
        /** Counts each reference given back once. */
        public void refund(String ref, long paise) { if (refunded.add(ref)) refunds.incrementAndGet(); }
    }

    static final long[] now = { ZonedDateTime.of(2026, 10, 1, 9, 58, 0, 0, TrainRun.IST).toInstant().toEpochMilli() };
    static final long HOLD = 10 * 60_000L;
    static int nextDay = 10;
    static final String[] ST = { "CSMT", "PUNE", "SUR", "GTL", "SBC" };

    /** A service with the Deccan Arrow and the shared clock the tests move by hand. */
    static BookingService service() { BookingService s = new BookingService(() -> now[0], HOLD); s.addTrain(Main.deccanArrow()); return s; }
    /** A run of the Deccan Arrow on a date no other test uses. With 1 RAC berth: 7 bookable 3A berths; with 0: 8. */
    static TrainRun freshRun(BookingService s, int racBerths, int waitlistCap) { return s.addRun("12999", LocalDate.of(2026, 10, 2).plusDays(nextDay++), racBerths, waitlistCap); }
    /** A traveller with no preference. */
    static Traveller t(String name, int age) { return new Traveller(name, age, null); }
    /** n travellers aged 30 named prefix1 .. prefixN. */
    static List<Traveller> people(String prefix, int n) { List<Traveller> out = new ArrayList<>(); for (int i = 1; i <= n; i++) out.add(t(prefix + i, 30)); return out; }
    /** The label of the first passenger's place, or "-". */
    static String place(Pnr p) { Berth b = p.passengers.get(0).place; return b == null ? "-" : b.label(); }
    /** Every passenger's status, in order. */
    static List<PassengerStatus> statuses(Pnr p) { List<PassengerStatus> out = new ArrayList<>(); for (Passenger x : p.passengers) out.add(x.status); return out; }
    /** Run ids of search hits, in the order returned. */
    static List<String> ids(List<Journey> js) { List<String> out = new ArrayList<>(); for (Journey j : js) out.add(j.run().id); return out; }
    /** The free seats of one fare type of one flight, as a search sees them. */
    static List<String> seats(FlightDesk d, String flightNo, String fare) {
        for (Offer o : d.search("DEL", "BLR", 2, 0)) if (o.flight().number.equals(flightNo) && o.fareType().equals(fare)) return o.seats();
        return List.of();
    }
    /** A random journey along the Deccan Arrow's five stops, as two stop numbers a < b. */
    static int[] journey(Random r) { int a = r.nextInt(4); return new int[] { a, a + 1 + r.nextInt(4 - a) }; }

    /**
     * Every rule the run promises, checked from scratch; an empty list means all of them hold. Call it only when
     * no other thread is running. Checked: no segment of any place sold twice, and the bits equal the union of the
     * passengers on it; each status matches its place and its queue; nobody waits while a place fits his journey;
     * the waitlist is within its cap; a dead PNR has no live passenger.
     */
    static List<String> violations(TrainRun run) {
        List<String> bad = new ArrayList<>();
        List<Pnr> all = run.pnrs();
        for (TravelClass c : TravelClass.values()) {
            ClassInventory inv;
            try { inv = run.inventory(c); } catch (NoSuchElementException e) { continue; }
            Map<Berth, List<Passenger>> on = new IdentityHashMap<>();
            for (Pnr p : all) {
                if (p.cls != c) continue;
                boolean live = p.status == PnrStatus.PENDING_PAYMENT || p.status == PnrStatus.BOOKED;
                for (Passenger x : p.passengers) {
                    String who = p.id + " " + x.who.name();
                    if (live == (x.status == PassengerStatus.CANCELLED)) bad.add(who + " is " + x.status + " on a " + p.status + " PNR");
                    if (x.place != null) on.computeIfAbsent(x.place, k -> new ArrayList<>()).add(x);
                    boolean inRac = inv.rac.contains(x), inWl = inv.waitlist.contains(x);
                    switch (x.status) {
                        case CONFIRMED -> { if (x.place == null || x.place.shared || inRac || inWl) bad.add(who + ": CONFIRMED but not on a berth of his own"); }
                        case RAC -> {
                            if (x.place == null || !x.place.shared || !inRac || inWl) bad.add(who + ": RAC but not on a shared half in the RAC queue");
                            else if (ClassInventory.firstFree(inv.berths, p.from, p.to) != null) bad.add(who + " is RAC while a berth fits his journey");
                        }
                        case WAITLISTED -> {
                            if (x.place != null || inRac || !inWl) bad.add(who + ": WAITLISTED but not only on the waitlist");
                            else if (ClassInventory.firstFree(inv.berths, p.from, p.to) != null || ClassInventory.firstFree(inv.racHalves, p.from, p.to) != null)
                                bad.add(who + " waits while a place fits his journey");
                        }
                        case CANCELLED -> { if (x.place != null || inRac || inWl) bad.add(who + ": CANCELLED but still holding something"); }
                    }
                }
            }
            List<Berth> places = new ArrayList<>(inv.berths);
            places.addAll(inv.racHalves);
            int segs = run.train.segments();
            for (Berth b : places) {
                boolean[] covered = new boolean[segs];
                for (Passenger x : on.getOrDefault(b, List.of()))
                    for (int s = x.pnr.from; s < x.pnr.to; s++) { if (covered[s]) bad.add(b.label() + " segment " + s + " sold twice"); covered[s] = true; }
                for (int s = 0; s < segs; s++) if (covered[s] == b.isFree(s, s + 1)) bad.add(b.label() + " segment " + s + ": the bits disagree with its passengers");
            }
            if (inv.waitlist.size() > inv.waitlistCap) bad.add(c + " waitlist is over its cap");
        }
        return bad;
    }

    /** Runs every numbered test and prints ALL PASS, or exits non-zero. */
    public static void main(String[] args) throws Exception {
        CountingGateway pay = new CountingGateway(true);

        // 1. a berth is sold per segment: three passengers share B1/1 end to end, and an overlap goes elsewhere
        BookingService s1 = service();
        TrainRun r1 = freshRun(s1, 1, 3);
        Pnr x1 = s1.book(r1.id, "x", "CSMT", "PUNE", TravelClass.AC3, List.of(t("X", 30)), true);     // segment 0
        Pnr y1 = s1.book(r1.id, "y", "SUR", "SBC", TravelClass.AC3, List.of(t("Y", 30)), true);       // segments 2-3
        check(place(x1).equals("B1/1") && place(y1).equals("B1/1"), "CSMT-PUNE and SUR-SBC are both sold B1/1: " + place(x1) + ", " + place(y1));
        check(s1.availability(r1.id, "PUNE", "SUR", TravelClass.AC3).berths() == 7, "a search for PUNE-SUR still counts all seven berths, B1/1 included");
        Pnr z1 = s1.book(r1.id, "z", "PUNE", "SUR", TravelClass.AC3, List.of(t("Z", 30)), true);      // segment 1: the gap
        check(place(z1).equals("B1/1"), "PUNE-SUR fills the gap on B1/1: three passengers, one berth, touching at PUNE and SUR");
        Pnr w1 = s1.book(r1.id, "w", "CSMT", "SUR", TravelClass.AC3, List.of(t("W", 30)), true);
        check(!place(w1).equals("B1/1"), "CSMT-SUR overlaps them and is sold another berth: " + place(w1));
        check(violations(r1).isEmpty(), "no segment of any berth is sold twice " + violations(r1));

        // 2. fifty phones, the last berth, berths only: exactly one wins
        BookingService s2 = service();
        TrainRun r2 = freshRun(s2, 1, 3);
        s2.book(r2.id, "grp", "CSMT", "SBC", TravelClass.AC3, people("g", 6), true);
        int wins = Main.race(50, i -> s2.book(r2.id, "fan" + i, "CSMT", "SBC", TravelClass.AC3, List.of(t("Fan" + i, 30)), true));
        check(wins == 1, "fifty threads for the last berth: exactly one booking (" + wins + ")");
        check(s2.availability(r2.id, "CSMT", "SBC", TravelClass.AC3).berths() == 0 && violations(r2).isEmpty(), "no berth left and nothing sold twice");

        // 3. fifty phones on an empty class, one traveller each: 7 berths + 2 RAC halves + 3 waitlist = 12 places
        BookingService s3 = service();
        TrainRun r3 = freshRun(s3, 1, 3);
        int placed = Main.race(50, i -> s3.book(r3.id, "fan" + i, "PUNE", "GTL", TravelClass.AC3, List.of(t("Fan" + i, 30)), false));
        ClassInventory inv3 = r3.inventory(TravelClass.AC3);
        check(placed == 12, "fifty threads, empty 3A: exactly 12 get a place (" + placed + ")");
        check(inv3.rac.size() == 2 && inv3.waitlist.size() == 3, "2 on RAC, 3 on the waitlist; the other 38 were told REGRET");
        check(violations(r3).isEmpty(), "every invariant holds after the race " + violations(r3));

        // 4. a cancel moves RAC up to a berth and the waitlist up to RAC, earliest first, in the same locked step
        BookingService s4 = service();
        List<PnrEvent> heard = new CopyOnWriteArrayList<>();
        s4.addObserver(heard::add);
        TrainRun r4 = freshRun(s4, 1, 3);
        Pnr asha = s4.book(r4.id, "asha", "CSMT", "PUNE", TravelClass.AC3, List.of(t("Asha", 34)), false);
        Pnr ravi = s4.book(r4.id, "ravi", "PUNE", "SBC", TravelClass.AC3, List.of(t("Ravi", 41)), false);
        Pnr fam = s4.book(r4.id, "dev", "CSMT", "SBC", TravelClass.AC3, people("f", 6), false);
        Pnr meena = s4.book(r4.id, "meena", "SUR", "SBC", TravelClass.AC3, List.of(t("Meena", 38), t("Arjun", 15)), false);
        Pnr kiran = s4.book(r4.id, "kiran", "SUR", "SBC", TravelClass.AC3, List.of(t("Kiran", 29)), false);
        for (Pnr p : List.of(asha, ravi, fam, meena, kiran)) s4.pay(p.id, pay);
        check(s4.status(meena.id).equals(List.of("Meena RAC 1 B1/7 shared", "Arjun RAC 2 B1/7 shared")) && s4.status(kiran.id).equals(List.of("Kiran WL 1")),
              "before: Meena RAC 1 and Arjun RAC 2 share B1/7, Kiran is WL 1");
        heard.clear();
        s4.cancel(ravi.id, pay);
        check(s4.status(meena.id).equals(List.of("Meena CNF B1/1 LOWER", "Arjun RAC 1 B1/7 shared")), "Ravi cancels: Meena gets his berth, Arjun becomes RAC 1 " + s4.status(meena.id));
        check(s4.status(kiran.id).equals(List.of("Kiran RAC 2 B1/7 shared")), "Kiran moves from WL 1 to RAC 2, into Meena's half");
        check(heard.size() == 3 && heard.get(1).what().equals("RAC 1 -> CNF B1/1") && heard.get(2).what().startsWith("WL 1 -> RAC 2"),
              "they are told in that order, after the lock: " + heard);
        Pnr neel = s4.book(r4.id, "neel", "SUR", "SBC", TravelClass.AC3, List.of(t("Neel", 50)), false);
        check(neel.passengers.get(0).status == PassengerStatus.WAITLISTED, "a newcomer for the same journey is waitlisted: the berth went to the people already waiting");
        check(violations(r4).isEmpty(), "every invariant holds " + violations(r4));

        // 5. a waiter whose journey does not fit is skipped, and keeps his place
        BookingService s5 = service();
        TrainRun r5 = freshRun(s5, 0, 3);                                          // no RAC berth: 8 berths, a waitlist of 3
        Pnr shortOne = s5.book(r5.id, "s", "SUR", "SBC", TravelClass.AC3, List.of(t("S", 30)), true);   // B1/1 segments 2-3
        s5.book(r5.id, "f", "CSMT", "SUR", TravelClass.AC3, List.of(t("F", 30)), true);                  // B1/1 segments 0-1
        s5.book(r5.id, "g", "CSMT", "SBC", TravelClass.AC3, people("g", 6), true);                       // B1/2 .. B1/7
        s5.book(r5.id, "h", "CSMT", "SBC", TravelClass.AC3, List.of(t("H", 30)), true);                  // B1/8: full everywhere
        Pnr longWait = s5.book(r5.id, "l", "CSMT", "SBC", TravelClass.AC3, List.of(t("Long", 30)), false);
        Pnr shortWait = s5.book(r5.id, "m", "SUR", "SBC", TravelClass.AC3, List.of(t("Short", 30)), false);
        s5.cancel(shortOne.id, pay);                                               // frees B1/1 on segments 2-3 only
        check(s5.status(longWait.id).equals(List.of("Long WL 1")), "the first waiter needs CSMT-SBC, which B1/1 cannot give: he stays WL 1");
        check(s5.status(shortWait.id).equals(List.of("Short CNF B1/1 LOWER")), "the second waiter fits SUR-SBC and is confirmed on B1/1");
        check(violations(r5).isEmpty(), "every invariant holds " + violations(r5));

        // 6. a cancel and a newcomer at the same instant, a hundred times: the waiter always gets the berth
        int fair = 0;
        for (int round = 0; round < 100; round++) {
            BookingService s6 = service();
            TrainRun r6 = freshRun(s6, 0, 3);
            Pnr holder = s6.book(r6.id, "h", "CSMT", "SBC", TravelClass.AC3, List.of(t("H", 30)), true);   // B1/1
            s6.book(r6.id, "g", "CSMT", "SBC", TravelClass.AC3, people("g", 6), true);
            s6.book(r6.id, "g7", "CSMT", "SBC", TravelClass.AC3, List.of(t("G7", 30)), true);
            Pnr waiter = s6.book(r6.id, "w", "PUNE", "SUR", TravelClass.AC3, List.of(t("W", 30)), false);
            CyclicBarrier both = new CyclicBarrier(2);
            ExecutorService two = Executors.newFixedThreadPool(2);
            Future<Long> a = two.submit(() -> { both.await(); return s6.cancel(holder.id, pay); });
            Future<Pnr> b = two.submit(() -> { both.await(); return s6.book(r6.id, "n", "PUNE", "SUR", TravelClass.AC3, List.of(t("N", 30)), false); });
            a.get(5, TimeUnit.SECONDS);
            Pnr newcomer = b.get(5, TimeUnit.SECONDS);
            two.shutdown();
            if (place(waiter).equals("B1/1") && newcomer.passengers.get(0).status == PassengerStatus.WAITLISTED && violations(r6).isEmpty()) fair++;
        }
        check(fair == 100, "a cancel racing a newcomer, 100 rounds: the waiter got the freed berth every time (" + fair + ")");

        // 7. a group is all or nothing
        BookingService s7 = service();
        TrainRun r7 = freshRun(s7, 1, 3);
        s7.book(r7.id, "grp", "CSMT", "SBC", TravelClass.AC3, people("g", 6), true);           // one berth left, 2 RAC halves, 3 waitlist
        Availability before7 = s7.availability(r7.id, "CSMT", "SBC", TravelClass.AC3);
        try { s7.book(r7.id, "pair", "CSMT", "SBC", TravelClass.AC3, people("p", 2), true); check(false, "two travellers, berths only, one berth: must be refused"); }
        catch (NoPlaces e) { check(true, "two travellers, berths only, one berth free: refused (" + e.getMessage() + ")"); }
        check(s7.availability(r7.id, "CSMT", "SBC", TravelClass.AC3).equals(before7), "the refusal held nothing: " + before7.label());
        s7.book(r7.id, "one", "CSMT", "SBC", TravelClass.AC3, List.of(t("One", 30)), false);  // the last berth
        try { s7.book(r7.id, "six", "CSMT", "SBC", TravelClass.AC3, people("s", 6), false); check(false, "six travellers for five places: must be refused"); }
        catch (NoPlaces e) { check(true, "six travellers when 2 RAC halves and 3 waitlist places are left: refused whole (" + e.getMessage() + ")"); }
        Availability mid7 = s7.availability(r7.id, "CSMT", "SBC", TravelClass.AC3);
        check(mid7.racPlaces() == 2 && mid7.waitlisted() == 0, "not one of the six was put on RAC or the waitlist");
        Pnr three = s7.book(r7.id, "three", "CSMT", "SBC", TravelClass.AC3, people("t", 3), false);
        check(statuses(three).equals(List.of(PassengerStatus.RAC, PassengerStatus.RAC, PassengerStatus.WAITLISTED)), "three travellers fit: two share the RAC berth, one waits " + statuses(three));
        check(violations(r7).isEmpty(), "every invariant holds " + violations(r7));

        // 8. a broken berth rule cannot double-sell: the run checks every answer before it writes
        BookingService s8 = service();
        TrainRun r8 = freshRun(s8, 1, 3);
        s8.configure(new DistanceFare(), (free, group) -> { List<Berth> out = new ArrayList<>(); for (Traveller tr : group) out.add(free.get(0)); return out; }, new FullRefund());
        try { s8.book(r8.id, "bug", "CSMT", "SBC", TravelClass.AC3, people("b", 2), false); check(false, "one berth for two travellers must be refused"); }
        catch (IllegalStateException e) { check(true, "a rule that gives one berth to two travellers is refused: " + e.getMessage()); }
        s8.configure(new DistanceFare(), (free, group) -> { List<Berth> out = new ArrayList<>(); for (Traveller tr : group) out.add(null); return out; }, new FullRefund());
        try { s8.book(r8.id, "lazy", "CSMT", "SBC", TravelClass.AC3, people("l", 1), false); check(false, "a lazy rule must be refused"); }
        catch (IllegalStateException e) { check(true, "a rule that leaves a berth empty while a traveller would wait is refused"); }
        check(s8.availability(r8.id, "CSMT", "SBC", TravelClass.AC3).berths() == 7 && r8.pnrs().isEmpty(), "neither wrote anything: seven berths free, no PNR");

        // 9. a declined card keeps the places; ten minutes later the holds lapse and the waiter moves up
        BookingService s9 = service();
        TrainRun r9 = freshRun(s9, 0, 3);
        Pnr held = s9.book(r9.id, "held", "CSMT", "SBC", TravelClass.AC3, people("h", 6), true);
        Pnr held2 = s9.book(r9.id, "held2", "CSMT", "SBC", TravelClass.AC3, people("k", 2), true);   // all 8 berths held, none paid
        Pnr waiter9 = s9.book(r9.id, "w", "CSMT", "SBC", TravelClass.AC3, List.of(t("W", 30)), false);
        s9.pay(waiter9.id, pay);
        CountingGateway no = new CountingGateway(false);
        try { s9.pay(held.id, no); check(false, "a declined card must throw"); }
        catch (PaymentDeclined e) { check(true, "a declined card throws: " + e.getMessage()); }
        check(held.status == PnrStatus.PENDING_PAYMENT && s9.status(held.id).get(0).startsWith("h1 CNF"), "after the decline the berths are still held for the same PNR");
        check(no.refunds.get() == 0, "nothing was refunded: nothing was taken");
        now[0] = held.holdExpiresMs - 1;
        check(s9.status(waiter9.id).equals(List.of("W WL 1")), "one millisecond before ten minutes the holds are alive and the waiter waits");
        now[0] = held.holdExpiresMs;
        check(s9.status(waiter9.id).get(0).startsWith("W CNF"), "at ten minutes the next call releases the holds and confirms the waiter: " + s9.status(waiter9.id));
        check(held.status == PnrStatus.EXPIRED && held2.status == PnrStatus.EXPIRED, "both unpaid PNRs are EXPIRED, with no sweeper running");

        // 10. the bank answers after the hold ran out: refused, and the money goes back once
        BookingService s10 = service();
        TrainRun r10 = freshRun(s10, 1, 3);
        Pnr late = s10.book(r10.id, "asha", "PUNE", "SBC", TravelClass.AC3, List.of(t("Asha", 34)), false);
        CountingGateway slow = new CountingGateway(true) {
            public String charge(String key, long paise) { now[0] += HOLD + 1; return super.charge(key, paise); }   // the round trip outlived the hold
        };
        try { s10.pay(late.id, slow); check(false, "a payment after the hold must be refused"); }
        catch (HoldLapsed e) { check(true, "the money came back after the hold ran out: refused (" + e.getMessage() + ")"); }
        check(slow.charges.get() == 1 && slow.refunds.get() == 1, "charged once and refunded once");
        check(late.status == PnrStatus.EXPIRED && s10.availability(r10.id, "PUNE", "SBC", TravelClass.AC3).berths() == 7, "the PNR is EXPIRED and the berth is on sale again");

        // 11. the PNR is the idempotency key: a retry after a timeout, or two taps at once, is charged once
        BookingService s11 = service();
        TrainRun r11 = freshRun(s11, 1, 3);
        Pnr tara = s11.book(r11.id, "tara", "CSMT", "PUNE", TravelClass.AC3, List.of(t("Tara", 30)), false);
        CountingGateway flaky = new CountingGateway(true) {
            boolean first = true;
            public String charge(String key, long paise) {
                String r = super.charge(key, paise);
                if (first) { first = false; throw new RuntimeException("timeout after the money moved"); }
                return r;
            }
        };
        try { s11.pay(tara.id, flaky); } catch (RuntimeException e) { /* the app says "something went wrong"; she taps Pay again */ }
        s11.pay(tara.id, flaky);
        check(tara.status == PnrStatus.BOOKED && flaky.charges.get() == 1 && flaky.refunds.get() == 0, "a timeout, then Pay again: charged once (" + flaky.charges.get() + ")");
        Pnr uma = s11.book(r11.id, "uma", "CSMT", "PUNE", TravelClass.AC3, List.of(t("Uma", 30)), false);
        CyclicBarrier bothIn = new CyclicBarrier(2);
        CountingGateway meeting = new CountingGateway(true) {
            public String charge(String key, long paise) {
                try { bothIn.await(2, TimeUnit.SECONDS); } catch (Exception e) { throw new IllegalStateException(e); }   // both taps inside at once
                return super.charge(key, paise);
            }
        };
        ExecutorService taps = Executors.newFixedThreadPool(2);
        Future<Pnr> tapA = taps.submit(() -> s11.pay(uma.id, meeting)), tapB = taps.submit(() -> s11.pay(uma.id, meeting));
        tapA.get(5, TimeUnit.SECONDS);
        tapB.get(5, TimeUnit.SECONDS);
        taps.shutdown();
        check(uma.status == PnrStatus.BOOKED && meeting.charges.get() == 1 && meeting.refunds.get() == 0, "two taps on Pay at the same instant: one charge, nothing to refund");
        try { s11.pay(uma.id, meeting); check(false, "paying a BOOKED PNR must be refused"); }
        catch (IllegalStateException e) { check(meeting.charges.get() == 1, "paying a BOOKED PNR again is refused before any money moves"); }

        // 12. a listener that throws breaks nothing
        BookingService s12 = service();
        s12.addObserver(e -> { throw new RuntimeException("SMS gateway is down"); });
        List<PnrEvent> after12 = new CopyOnWriteArrayList<>();
        s12.addObserver(after12::add);
        TrainRun r12 = freshRun(s12, 1, 3);
        Pnr p12 = s12.book(r12.id, "vik", "CSMT", "SBC", TravelClass.AC3, List.of(t("Vik", 30)), false);
        s12.pay(p12.id, pay);
        check(p12.status == PnrStatus.BOOKED, "the booking completes although the first listener throws");
        check(after12.size() == 1 && after12.get(0).what().startsWith("BOOKED"), "the listener after the broken one still hears it");

        // 13. the refund rule: waitlisted passengers lose a clerkage fee; confirmed ones lose more as departure nears
        long[] clk = { now[0] };
        BookingService s13 = new BookingService(() -> clk[0], HOLD);
        s13.addTrain(Main.deccanArrow());
        s13.configure(new DistanceFare(), new FirstFreeBerths(), new RailwayRefund());
        TrainRun r13 = s13.addRun("12999", LocalDate.of(2026, 12, 1), 0, 3);
        TrainRun r13b = s13.addRun("12999", LocalDate.of(2026, 12, 2), 0, 3);
        long departPune = r13.departsMs(1);
        clk[0] = departPune - 70 * 3_600_000L;
        s13.book(r13b.id, "a", "PUNE", "SBC", TravelClass.AC3, people("a", 6), true);
        s13.book(r13b.id, "b", "PUNE", "SBC", TravelClass.AC3, people("b", 2), true);          // 8 berths held
        Pnr wl13 = s13.book(r13b.id, "wl", "PUNE", "SBC", TravelClass.AC3, List.of(t("WL", 30)), false);
        s13.pay(wl13.id, pay);
        check(s13.cancel(wl13.id, pay) == 121_520 - 6_000, "a waitlisted passenger loses only the clerkage fee: Rs 1,155.20 of Rs 1,215.20 back");
        Pnr unpaid = s13.book(r13b.id, "u", "PUNE", "SBC", TravelClass.AC3, List.of(t("U", 30)), false);
        int refundsBefore = pay.refunds.get();
        check(s13.cancel(unpaid.id, pay) == 0 && pay.refunds.get() == refundsBefore, "a hold that was never paid refunds nothing and calls no gateway");
        long[] hoursBefore = { 60, 30, 8, 2 };
        long[] expected = { 121_520 - 18_000, 121_520 - 30_380, 121_520 - 60_760, 0 };
        for (int k = 0; k < 4; k++) {
            clk[0] = departPune - hoursBefore[k] * 3_600_000L;
            Pnr p = s13.book(r13.id, "r" + k, "PUNE", "SBC", TravelClass.AC3, List.of(t("R" + k, 30)), false);
            s13.pay(p.id, pay);
            long back = s13.cancel(p.id, pay);
            check(back == expected[k], hoursBefore[k] + " hours before departure, a confirmed Rs 1,215.20 ticket gets " + Main.rupees(back) + " back");
        }

        // 14. search: by the day you board, only forwards along the route, earliest first
        BookingService s14 = service();
        s14.addTrain(new Train("12111", "Morning Link", List.of(new Stop("PUNE", 6 * 60, 0, 0), new Stop("SUR", 11 * 60, 0, 263),
            new Stop("SBC", 22 * 60, 0, 868)), List.of(new Coach("C1", TravelClass.AC3, 1))));
        for (LocalDate d : List.of(LocalDate.of(2026, 10, 2), LocalDate.of(2026, 10, 3))) { s14.addRun("12999", d, 1, 3); s14.addRun("12111", d, 1, 3); }
        List<String> puneSbc = ids(s14.search("PUNE", "SBC", LocalDate.of(2026, 10, 3)));
        check(puneSbc.equals(List.of("12111/2026-10-03", "12999/2026-10-03")), "PUNE-SBC on 3 Oct: the 06:00 first, then the 23:15 " + puneSbc);
        List<String> surSbc = ids(s14.search("SUR", "SBC", LocalDate.of(2026, 10, 3)));
        check(surSbc.equals(List.of("12999/2026-10-02", "12111/2026-10-03")), "SUR-SBC on 3 Oct finds the train that left Mumbai on the 2nd (04:30) before the 11:00 " + surSbc);
        check(s14.search("SBC", "PUNE", LocalDate.of(2026, 10, 3)).isEmpty(), "the wrong direction finds nothing");
        check(s14.search("CSMT", "XYZ", LocalDate.of(2026, 10, 3)).isEmpty(), "a station no train stops at finds nothing");
        check(s14.train("12999").stops.size() == 5, "search by train number gives the route and its five stops");

        // 15. availability reads AVAILABLE, then RAC, then WL, then REGRET as the class fills
        BookingService s15 = service();
        TrainRun r15 = freshRun(s15, 1, 3);
        List<String> labels = new ArrayList<>();
        labels.add(s15.availability(r15.id, "PUNE", "SUR", TravelClass.AC3).label());
        s15.book(r15.id, "a", "PUNE", "SUR", TravelClass.AC3, people("a", 6), false);
        s15.book(r15.id, "b", "PUNE", "SUR", TravelClass.AC3, people("b", 1), false);
        labels.add(s15.availability(r15.id, "PUNE", "SUR", TravelClass.AC3).label());
        s15.book(r15.id, "c", "PUNE", "SUR", TravelClass.AC3, people("c", 2), false);
        labels.add(s15.availability(r15.id, "PUNE", "SUR", TravelClass.AC3).label());
        s15.book(r15.id, "d", "PUNE", "SUR", TravelClass.AC3, people("d", 3), false);
        labels.add(s15.availability(r15.id, "PUNE", "SUR", TravelClass.AC3).label());
        check(labels.equals(List.of("AVAILABLE 7", "RAC 1", "WL 1", "REGRET")), "the label follows the class filling up, each number the next passenger's: " + labels);
        check(s15.availability(r15.id, "CSMT", "PUNE", TravelClass.AC3).label().equals("AVAILABLE 7"), "and CSMT-PUNE on the same run is still wide open");

        // 16. the model holds: 3,000 random operations on one thread, then 8 threads at once
        Random rnd = new Random(2026);
        BookingService s16 = service();
        List<PnrEvent> moves = new CopyOnWriteArrayList<>();
        s16.addObserver(e -> { if (e.what().contains("->")) moves.add(e); });
        TrainRun r16 = freshRun(s16, 1, 4);
        List<Pnr> live = new ArrayList<>();
        int broken = 0;
        for (int i = 0; i < 3000; i++) {
            int op = rnd.nextInt(10);
            try {
                if (op < 5) {
                    int[] j = journey(rnd);
                    live.add(s16.book(r16.id, "u", ST[j[0]], ST[j[1]], rnd.nextBoolean() ? TravelClass.AC3 : TravelClass.SLEEPER,
                        people("r" + i + "-", 1 + rnd.nextInt(3)), rnd.nextInt(4) == 0));
                } else if (op < 7 && !live.isEmpty()) s16.pay(live.get(rnd.nextInt(live.size())).id, pay);
                else if (op < 9 && !live.isEmpty()) s16.cancel(live.remove(rnd.nextInt(live.size())).id, pay);
                else now[0] += rnd.nextInt(4) * 60_000L;                          // up to three minutes: some holds lapse
            } catch (RuntimeException e) { /* NoPlaces, HoldLapsed, a cancel of an expired hold: all legal refusals */ }
            List<String> v = violations(r16);
            if (!v.isEmpty() && broken++ == 0) System.out.println("  first violation at operation " + i + ": " + v);
        }
        check(broken == 0, "3,000 random books, payments, cancels and clock moves: every invariant held after every one");
        check(moves.size() > 50, "the workload moved waiters up " + moves.size() + " times, so promotion was really exercised");
        TrainRun r16b = freshRun(s16, 1, 4);
        ExecutorService crowd = Executors.newFixedThreadPool(8);
        CountDownLatch go16 = new CountDownLatch(1);
        List<Future<Object>> jobs = new ArrayList<>();
        for (int th = 0; th < 8; th++) {
            int seed = th;
            jobs.add(crowd.submit(() -> {
                go16.await();
                Random r = new Random(seed);
                List<Pnr> mine = new ArrayList<>();
                for (int i = 0; i < 400; i++) {
                    try {
                        if (mine.isEmpty() || r.nextInt(3) > 0) {
                            int[] j = journey(r);
                            Pnr p = s16.book(r16b.id, "c" + seed, ST[j[0]], ST[j[1]], TravelClass.AC3, people("c" + seed + "-" + i + "-", 1 + r.nextInt(2)), false);
                            mine.add(p);
                            if (r.nextBoolean()) s16.pay(p.id, pay);
                        } else s16.cancel(mine.remove(r.nextInt(mine.size())).id, pay);
                    } catch (RuntimeException e) { /* a refusal */ }
                }
                return null;
            }));
        }
        go16.countDown();
        for (Future<Object> f : jobs) f.get(30, TimeUnit.SECONDS);
        crowd.shutdown();
        check(violations(r16b).isEmpty(), "8 threads x 400 random books, payments and cancels at once: every invariant holds at the end " + violations(r16b));

        // 17. edges are refused, and nothing is held
        BookingService s17 = service();
        TrainRun r17 = freshRun(s17, 1, 3);
        Object[][] edges = { { "PUNE", "PUNE", 1 }, { "SBC", "PUNE", 1 }, { "CSMT", "XYZ", 1 }, { "CSMT", "SBC", 0 }, { "CSMT", "SBC", 7 } };
        for (Object[] c : edges) {
            try { s17.book(r17.id, "e", (String) c[0], (String) c[1], TravelClass.AC3, people("e", (Integer) c[2]), false); check(false, "must be refused: " + Arrays.toString(c)); }
            catch (IllegalArgumentException e) { check(true, "refused: " + e.getMessage()); }
        }
        try { s17.book(r17.id, "e", "CSMT", "SBC", TravelClass.AC2, people("e", 1), false); check(false, "a class the train does not have must be refused"); }
        catch (NoSuchElementException e) { check(true, "refused: " + e.getMessage()); }
        long[] clk17 = { r17.departsMs(1) + 60_000 };                                // a minute after it left Pune
        BookingService s17b = new BookingService(() -> clk17[0], HOLD);
        s17b.addTrain(Main.deccanArrow());
        TrainRun r17b = s17b.addRun("12999", r17.date, 1, 3);
        try { s17b.book(r17b.id, "e", "PUNE", "SBC", TravelClass.AC3, people("e", 1), false); check(false, "boarding after the train left must be refused"); }
        catch (IllegalStateException e) { check(true, "refused: " + e.getMessage()); }
        Pnr fromSur = s17b.book(r17b.id, "e", "SUR", "SBC", TravelClass.AC3, people("s", 1), false);
        check(fromSur.status == PnrStatus.PENDING_PAYMENT, "but Solapur is still ahead of the train, so a Solapur boarding is sold");
        check(s17.availability(r17.id, "CSMT", "SBC", TravelClass.AC3).berths() == 7 && r17.pnrs().isEmpty(), "the refusals held nothing");

        // 18. fares: distance, a peak day, Tatkal with its floor, flexi, and the order of wrapping
        BookingService s18 = service();
        TrainRun r18 = freshRun(s18, 1, 3), other18 = freshRun(s18, 1, 3);
        FareRule base = new DistanceFare();
        check(base.farePaise(r18, 1, 4, TravelClass.AC3) == 121_520, "3A PUNE-SBC is 140 paise x 868 km = Rs 1,215.20");
        FareRule peak = new PeakDayFare(base, Set.of(r18.date), 120);
        check(peak.farePaise(r18, 1, 4, TravelClass.AC3) == 145_824 && peak.farePaise(other18, 1, 4, TravelClass.AC3) == 121_520,
              "a peak day pays 1.2x (Rs 1,458.24); the next day pays Rs 1,215.20");
        check(new TatkalFare(base).farePaise(r18, 1, 4, TravelClass.AC3) == 121_520 + 36_456, "Tatkal adds 30%: Rs 364.56, inside its floor and cap");
        check(new TatkalFare(base).farePaise(r18, 0, 1, TravelClass.AC3) == 26_880 + 30_000, "a short Tatkal journey pays the floor: 30% of Rs 268.80 is below Rs 300");
        FareRule flexi = new FlexiFare(base);
        check(flexi.farePaise(r18, 1, 4, TravelClass.AC3) == 121_520, "flexi on an empty class is the base fare");
        s18.book(r18.id, "g", "CSMT", "SBC", TravelClass.AC3, people("g", 4), true);          // 4 of 7 sold: 5 tenths
        check(flexi.farePaise(r18, 1, 4, TravelClass.AC3) == 182_280, "flexi with 4 of 7 berths sold: 1.5x, the cap");
        long inner = new TatkalFare(new FlexiFare(base)).farePaise(r18, 1, 4, TravelClass.AC3), outer = new FlexiFare(new TatkalFare(base)).farePaise(r18, 1, 4, TravelClass.AC3);
        check(inner == 222_280 && outer == 236_964, "the order of wrapping is a decision: flexi inside Tatkal " + Main.rupees(inner) + ", Tatkal inside flexi " + Main.rupees(outer));

        // 19. a family together: one coach when one coach has room, lower berths for the seniors, seniors first when short
        Train twoCoach = new Train("12888", "Two Coach", Main.deccanArrow().stops, List.of(new Coach("B1", TravelClass.AC3, 1), new Coach("B2", TravelClass.AC3, 1)));
        BookingService s19 = new BookingService(() -> now[0], HOLD);
        s19.addTrain(twoCoach);
        TrainRun r19 = s19.addRun("12888", LocalDate.of(2026, 12, 20), 1, 3);            // B1: 8 berths, B2: 7 (B2/7 is the RAC berth)
        s19.book(r19.id, "x", "CSMT", "SBC", TravelClass.AC3, people("x", 6), true);      // B1/1..6: only 2 left in B1
        s19.configure(new DistanceFare(), new FamilyChooser(), new FullRefund());
        Pnr family = s19.book(r19.id, "dev", "CSMT", "SBC", TravelClass.AC3,
            List.of(new Traveller("Dev", 45, BerthType.UPPER), t("Mira", 43), t("Nana", 72), t("Nani", 68)), false);
        List<String> famStatus = s19.status(family.id);
        check(famStatus.stream().allMatch(s -> s.contains(" B2/")), "four travellers, two berths left in B1: all four go to B2 together " + famStatus);
        check(famStatus.get(2).endsWith("LOWER") && famStatus.get(3).endsWith("LOWER") && famStatus.get(0).endsWith("UPPER"), "the two over sixty get lower berths, Dev his upper");
        TrainRun r19b = s19.addRun("12888", LocalDate.of(2026, 12, 21), 1, 3);
        s19.configure(new DistanceFare(), new FirstFreeBerths(), new FullRefund());
        s19.book(r19b.id, "x", "CSMT", "SBC", TravelClass.AC3, people("x", 6), true);
        s19.book(r19b.id, "y", "CSMT", "SBC", TravelClass.AC3, people("y", 6), true);
        s19.book(r19b.id, "z", "CSMT", "SBC", TravelClass.AC3, people("z", 1), true);      // 13 of 15: two berths left
        s19.configure(new DistanceFare(), new FamilyChooser(), new FullRefund());
        Pnr short19 = s19.book(r19b.id, "o", "CSMT", "SBC", TravelClass.AC3, List.of(t("Anil", 30), t("Bina", 31), t("Grandpa", 75)), false);
        check(statuses(short19).get(2) == PassengerStatus.CONFIRMED && statuses(short19).contains(PassengerStatus.RAC), "two berths for three: Grandpa, listed last, still gets one " + statuses(short19));

        // 20. the sideways index counts the same free berths as the walk, for every journey
        SegmentIndex idx = new SegmentIndex(r16.soldMasks(TravelClass.AC3), r16.train.segments());
        boolean same = true;
        for (int a = 0; a < 4; a++) for (int b = a + 1; b <= 4; b++) same &= idx.freeFor(a, b) == r16.availability(ST[a], ST[b], TravelClass.AC3).berths();
        check(same, "after the random workload, the sideways index and the walk agree on all ten journeys");

        // 21. a queue in front of the run: arrival order, and a full queue says "try again" at once
        BookingService s21 = service();
        TrainRun r21 = freshRun(s21, 1, 3);
        RunQueue q = new RunQueue("run-" + r21.id, 64);
        List<CompletableFuture<Pnr>> answers = new ArrayList<>();
        for (int i = 0; i < 10; i++) { String u = "tatkal" + i; answers.add(q.submit(() -> s21.book(r21.id, u, "CSMT", "SBC", TravelClass.AC3, List.of(t(u, 30)), true))); }
        List<Boolean> got = new ArrayList<>();
        for (CompletableFuture<Pnr> f : answers) { try { f.get(5, TimeUnit.SECONDS); got.add(true); } catch (ExecutionException e) { got.add(false); } }
        check(got.equals(List.of(true, true, true, true, true, true, true, false, false, false)), "ten requests for seven berths: the first seven, in arrival order, get them " + got);
        q.stop();
        RunQueue tiny = new RunQueue("tiny", 1);
        CountDownLatch started = new CountDownLatch(1), release = new CountDownLatch(1);
        tiny.submit(() -> { started.countDown(); try { release.await(); } catch (InterruptedException e) { } return 1; });   // keeps the worker busy
        started.await(2, TimeUnit.SECONDS);
        CompletableFuture<Integer> queued = tiny.submit(() -> 2), refused = tiny.submit(() -> 3);
        check(refused.isCompletedExceptionally() && !queued.isDone(), "the queue holds one: the third request is refused at once instead of waiting");
        release.countDown();
        check(queued.get(2, TimeUnit.SECONDS) == 2, "the queued request still runs once the worker is free");
        tiny.stop();

        // 22. the database stand-in: fifty conditional UPDATEs on one row, one winner; touching segments share a row; a group rolls back
        MaskStore db = new MaskStore();
        db.add("R", "B1/1"); db.add("R", "A9/9");
        ExecutorService pool22 = Executors.newFixedThreadPool(50);
        CountDownLatch go22 = new CountDownLatch(1);
        AtomicInteger won = new AtomicInteger();
        for (int i = 0; i < 50; i++) pool22.submit(() -> { go22.await(); if (db.sellAll("R", List.of("B1/1"), 1, 3)) won.incrementAndGet(); return null; });
        go22.countDown(); pool22.shutdown(); pool22.awaitTermination(5, TimeUnit.SECONDS);
        check(won.get() == 1, "fifty conditional UPDATEs for segments 1-3 of one berth: one row changed (" + won.get() + ")");
        check(db.sellAll("R", List.of("B1/1"), 3, 4) && !db.sellAll("R", List.of("B1/1"), 2, 4), "segments 3-4 of the same row sell; 2-4 overlaps and does not");
        check(!db.sellAll("R", List.of("B1/1", "A9/9"), 0, 2) && db.mask("R", "A9/9") == 0, "a group whose second row is taken rolls back the first: A9/9 is empty again");

        // 23. the flight desk: every seat or none, the wallet, cancel once, change without losing the booking, no deadlock
        FlightDesk fd = new FlightDesk();
        fd.addUser("u1", "Vinit", 500_000); fd.addUser("u2", "Neha", 150_000);
        fd.addFlight(new Flight("111", "6E", "DEL", "BLR", 2, 10 * 60 + 30).fare("F1", 100_000, "10a", "11c", "20b", "21a").fare("F2", 150_000, "1a", "1b"));
        fd.addFlight(new Flight("211", "6E", "DEL", "BLR", 2, 18 * 60 + 45).fare("F1", 120_000, "10a", "11c", "20b"));
        String fb1 = fd.book("u1", "111", 2, "F1", List.of("10a", "11c"));
        try { fd.book("u2", "111", 2, "F1", List.of("20b", "11c")); check(false, "a taken seat must refuse the booking"); }
        catch (IllegalStateException e) { check(fd.funds("u2") == 150_000 && seats(fd, "111", "F1").equals(List.of("20b", "21a")), "one taken seat refuses the whole booking: no money moved, 20b still free"); }
        try { fd.book("u2", "111", 2, "F2", List.of("1a", "1b")); check(false, "a short wallet must refuse the booking"); }
        catch (IllegalStateException e) { check(fd.funds("u2") == 150_000 && seats(fd, "111", "F2").size() == 2, "Rs 3,000 of seats with Rs 1,500 in the wallet: refused, nothing moved"); }
        fd.cancel("u1", fb1);
        check(fd.funds("u1") == 500_000 && seats(fd, "111", "F1").size() == 4, "cancel gives back the seats and the money");
        try { fd.cancel("u1", fb1); check(false, "a second cancel must be refused"); }
        catch (IllegalStateException e) { check(fd.funds("u1") == 500_000, "a second cancel is refused and refunds nothing twice"); }
        String fb2 = fd.book("u2", "211", 2, "F1", List.of("10a"));                         // Rs 1,200: Neha has Rs 300 left
        try { fd.change("u2", fb2, "111", 2, "F2", List.of("1a", "1b")); check(false, "a change she cannot afford must be refused"); }
        catch (IllegalStateException e) { check(fd.funds("u2") == 30_000 && !seats(fd, "211", "F1").contains("10a") && seats(fd, "111", "F2").contains("1a"), "a change she cannot afford is refused; the old booking is untouched"); }
        fd.change("u2", fb2, "111", 2, "F1", List.of("21a"));
        check(fd.funds("u2") == 50_000 && seats(fd, "211", "F1").contains("10a") && !seats(fd, "111", "F1").contains("21a"), "moving to a cheaper fare refunds Rs 200 and moves the seat");
        fd.addUser("a", "A", 100_000_000); fd.addUser("b", "B", 100_000_000);
        String ba = fd.book("a", "111", 2, "F1", List.of("20b")), bb = fd.book("b", "211", 2, "F1", List.of("11c"));
        ExecutorService swap = Executors.newFixedThreadPool(2);
        Future<Object> fa = swap.submit(() -> { for (int i = 0; i < 200; i++) fd.change("a", ba, i % 2 == 0 ? "211" : "111", 2, "F1", List.of("20b")); return null; });
        Future<Object> fbb = swap.submit(() -> { for (int i = 0; i < 200; i++) fd.change("b", bb, i % 2 == 0 ? "111" : "211", 2, "F1", List.of("11c")); return null; });
        boolean finished = true;
        try { fa.get(10, TimeUnit.SECONDS); fbb.get(10, TimeUnit.SECONDS); } catch (TimeoutException e) { finished = false; }
        swap.shutdownNow();
        check(finished, "two users moving between the same two flights in opposite directions, 200 times each: no deadlock");
        check(seats(fd, "111", "F1").equals(List.of("10a", "11c")) && seats(fd, "211", "F1").equals(List.of("10a", "20b")), "and every seat is exactly where it started");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
