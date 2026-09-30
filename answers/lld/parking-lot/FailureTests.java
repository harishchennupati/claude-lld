import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.time.*;
import java.io.*;

/**
 * Every claim this design makes, proved. Each block is one row of move 9: a way the parking lot can go
 * wrong, and the few lines that show it does not. Run: javac Main.java Extensions.java FailureTests.java
 * && java FailureTests
 */
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }
    static final long SAT_10AM = Instant.parse("2026-09-05T10:00:00Z").toEpochMilli();   // a Saturday
    static final long TUE_10AM = Instant.parse("2026-09-08T10:00:00Z").toEpochMilli();   // a Tuesday

    /** A lot with one floor of the given spots, a fixed clock, flat pricing and smallest fit. */
    static ParkingLot lot(long[] now, ParkingFloor floor) {
        ParkingLot lot = new ParkingLot();
        lot.configure(new FlatHourlyPricing(), new SmallestFitStrategy());
        lot.setClock(() -> now[0]);
        lot.addFloor(floor);
        return lot;
    }
    static ParkingFloor floor(String id, Object... idsAndTypes) {
        ParkingFloor f = new ParkingFloor(id);
        for (int i = 0; i < idsAndTypes.length; i += 2) f.addSpot(new ParkingSpot((String) idsAndTypes[i], (SpotType) idsAndTypes[i + 1]));
        return f;
    }

    public static void main(String[] args) throws Exception {
        long[] now = { SAT_10AM };

        // 1. the fit table: smallest fitting size first, so large spots stay free for trucks
        ParkingLot fit = lot(now, floor("F1", "S1", SpotType.SMALL, "C1", SpotType.COMPACT, "L1", SpotType.LARGE));
        check(fit.park(new Motorcycle("M1")).spot.id.equals("S1"), "a motorcycle takes the SMALL spot, not the compact one");
        check(fit.park(new Car("C-1")).spot.id.equals("C1"), "a car takes the COMPACT spot, not the large one");
        check(fit.park(new Truck("T-1")).spot.id.equals("L1"), "a truck takes the LARGE spot, the only size that fits it");
        check(fit.isFullFor(VehicleType.TRUCK) && fit.isFullFor(VehicleType.CAR), "now full for trucks and cars");
        try { fit.park(new Truck("T-2")); check(false, "a second truck must be rejected"); }
        catch (IllegalStateException e) { check(true, "a second truck is rejected: " + e.getMessage()); }

        // 2. payment fails at exit: nothing changes, the driver retries and succeeds
        ParkingLot pay = lot(now, floor("F1", "C1", SpotType.COMPACT));
        pay.park(new Car("AAA"));
        check(pay.isFullFor(VehicleType.CAR), "spot taken after park");
        try { pay.unpark("AAA", (key, paise) -> PaymentStatus.DECLINED); check(false, "failed payment must throw"); }
        catch (IllegalStateException e) { check(true, "failed payment throws: " + e.getMessage()); }
        check(pay.isFullFor(VehicleType.CAR), "after a failed payment the spot is still held");
        check(pay.unpark("AAA", new CashPayment()) == 2_000L, "the driver retries with cash and pays Rs 20 (2000 paise)");
        check(!pay.isFullFor(VehicleType.CAR), "spot recovered after the successful retry");

        // 3. an observer that throws must not corrupt parking
        ParkingFloor noisy = floor("F1", "C1", SpotType.COMPACT);
        ParkingLot obs = lot(now, noisy);
        noisy.addObserver((id, free) -> { throw new RuntimeException("board is down"); });
        check(obs.park(new Car("BBB")) != null && obs.isFullFor(VehicleType.CAR), "park succeeds although the board threw");
        obs.unpark("BBB", new CashPayment());
        check(!obs.isFullFor(VehicleType.CAR), "unpark succeeds although the board threw; the spot is back");

        // 4. lost ticket: the cap is charged, and a failed payment changes nothing
        ParkingLot lost = lot(now, floor("F1", "C1", SpotType.COMPACT));
        ExitGate exit = new ExitGate(lost);
        lost.park(new Car("CCC"));
        try { exit.lostTicket("CCC", (key, paise) -> PaymentStatus.DECLINED, 20_000); check(false, "failed cap payment must throw"); }
        catch (IllegalStateException e) { check(true, "a failed cap payment throws"); }
        check(lost.isFullFor(VehicleType.CAR), "after the failed cap payment the spot is still held");
        check(exit.lostTicket("CCC", new CashPayment(), 20_000) == 20_000L, "the retry pays the daily cap (Rs 200) through the exit gate");
        check(lost.availability().get(SpotType.COMPACT) == 1, "the spot is freed exactly once");

        // 5. a second checkout must be rejected, not free the spot twice
        ParkingLot twice = lot(now, floor("F1", "C1", SpotType.COMPACT));
        twice.park(new Car("DDD"));
        twice.unpark("DDD", new CashPayment());
        try { twice.unpark("DDD", new CashPayment()); check(false, "a second checkout must throw"); }
        catch (NoSuchElementException e) { check(true, "a second checkout is rejected"); }
        check(twice.availability().get(SpotType.COMPACT) == 1, "one physical spot, one free entry (not two)");

        // 6. the same plate at two gates: the second is refused, one spot is used
        ParkingLot dup = lot(now, floor("F1", "C1", SpotType.COMPACT, "C2", SpotType.COMPACT));
        dup.park(new Car("SAME"));
        try { dup.park(new Car("SAME")); check(false, "a duplicate plate must be refused"); }
        catch (IllegalStateException e) { check(true, "the same plate at a second gate is refused"); }
        check(dup.availability().get(SpotType.COMPACT) == 1, "the duplicate consumed no second spot");

        // 7. billing: any started hour is billed, and a minute is never free
        ParkingLot bill = lot(now, floor("F1", "C1", SpotType.COMPACT));
        bill.park(new Car("E1")); now[0] += 3_600_000L;
        check(bill.unpark("E1", new CashPayment()) == 2_000L, "exactly 60 minutes on compact bills 1 hour = 2000 paise");
        bill.park(new Car("E2")); now[0] += 3_600_000L + 1;
        check(bill.unpark("E2", new CashPayment()) == 4_000L, "60 minutes and 1 millisecond bills 2 hours = 4000 paise");
        bill.park(new Car("E3")); now[0] += 1;
        check(bill.unpark("E3", new CashPayment()) == 2_000L, "1 millisecond still bills the first hour = 2000 paise");

        // 8. the weekend rule reads the injected clock, not the wall clock
        now[0] = SAT_10AM;
        ParkingLot sat = lot(now, floor("F1", "C1", SpotType.COMPACT));
        sat.configure(new WeekendSurgePricing(new FlatHourlyPricing(), ZoneId.of("UTC")), new SmallestFitStrategy());
        sat.park(new Car("FFF")); now[0] += 3_600_000L;                    // Saturday 10:00 to 11:00
        check(sat.unpark("FFF", new CashPayment()) == 3_000L, "Saturday by the injected clock: 2000 x 1.5 = 3000 paise");
        now[0] = TUE_10AM;
        sat.park(new Car("GGG"));
        check(sat.unpark("GGG", new CashPayment()) == 2_000L, "the same code on a Tuesday: no surge, 2000 paise");
        now[0] = SAT_10AM;

        // 9. taking a spot that is not free is a programming error, not a slow path
        ParkingFloor guard = floor("F1", "C1", SpotType.COMPACT);
        try { guard.take(new ParkingSpot("ghost", SpotType.COMPACT)); check(false, "must throw"); }
        catch (IllegalStateException e) { check(true, "take() refuses a spot that is not in the free queue"); }

        // 10. the count the board asks for, per floor, O(1) and under the lock
        ParkingLot counts = lot(now, floor("F1", "C1", SpotType.COMPACT, "C2", SpotType.COMPACT));
        counts.addFloor(floor("F2", "C3", SpotType.COMPACT, "L2", SpotType.LARGE));
        check(counts.freeCount("F2", SpotType.COMPACT) == 1, "F2 has one free compact, counted without scanning spots");
        counts.park(new Car("H1"));                                        // goes to F1: the first floor that fits
        check(counts.freeCount("F1", SpotType.COMPACT) == 1 && counts.freeCount("F2", SpotType.COMPACT) == 1, "the park moved only F1's count");
        check(counts.availability().get(SpotType.COMPACT) == 2, "lot-wide availability is the sum of the floors");
        try { counts.freeCount("F9", SpotType.COMPACT); check(false, "an unknown floor must throw"); }
        catch (NoSuchElementException e) { check(true, "an unknown floor is an error, not a zero"); }

        // 11. the race: fifty gates, one compact spot, one latch, exactly one winner
        ParkingLot race = lot(now, floor("F1", "C1", SpotType.COMPACT));
        EntryGate gate = new EntryGate(race);
        ExecutorService pool = Executors.newFixedThreadPool(50);          // one thread per gate: all fifty wait at the latch together
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Ticket>> tries = new ArrayList<>();
        for (int i = 0; i < 50; i++) { String plate = "R" + i; tries.add(pool.submit(() -> { go.await(); return gate.admit(new Car(plate)); })); }
        go.countDown();
        int wins = 0;
        for (Future<Ticket> f : tries) { try { f.get(); wins++; } catch (ExecutionException e) { /* "Lot full for CAR" */ } }
        pool.shutdown();
        check(wins == 1, "50 gates raced for the last spot; winners = " + wins);
        check(race.isFullFor(VehicleType.CAR), "the lot is full afterwards: one spot, one car");
        check(race.availability().get(SpotType.COMPACT) == 0, "no spot was handed out twice and none was lost");

        // 12. nearest to the exit: the floor's queue order decides, and vacating puts it back in order
        Map<String, Integer> metres = Map.of("C1", 50, "C2", 10, "C3", 30);
        ParkingFloor near = new ParkingFloor("F1", Nearest.nearestFirst(metres));
        for (String id : List.of("C1", "C2", "C3")) near.addSpot(new ParkingSpot(id, SpotType.COMPACT));
        ParkingLot nearLot = new ParkingLot();
        nearLot.setClock(() -> now[0]);
        nearLot.configure(new FlatHourlyPricing(), new NearestToExit(metres));
        nearLot.addFloor(near);
        check(nearLot.park(new Car("N1")).spot.id.equals("C2"), "the first car gets C2, ten metres from the exit");
        check(nearLot.park(new Car("N2")).spot.id.equals("C3"), "the second gets C3 at thirty metres, not C1 at fifty");
        nearLot.unpark("N1", new CashPayment());                            // C2 goes back into the heap
        check(nearLot.park(new Car("N3")).spot.id.equals("C2"), "a vacated spot re-enters in distance order, so C2 is handed out again");

        // 13. pricing rules stack, and the order of wrapping is the answer
        ParkingLot stackLot = lot(now, floor("F1", "C1", SpotType.COMPACT));
        PricingStrategy stack = new MonthlyPassPricing(
            new DailyCapPricing(new WeekendSurgePricing(new FreeGracePricing(new FlatHourlyPricing(), 15), ZoneId.of("UTC")), 10_000),
            Set.of("PASS-1"));
        stackLot.configure(stack, new SmallestFitStrategy());
        stackLot.park(new Car("S1")); now[0] += 10 * 60_000L;
        check(stackLot.unpark("S1", new CashPayment()) == 0L, "ten minutes is inside the fifteen-minute grace: free");
        stackLot.park(new Car("S2")); now[0] += 90 * 60_000L;
        check(stackLot.unpark("S2", new CashPayment()) == 6_000L, "ninety minutes on a Saturday: 2h x 2000 x 1.5 = 6000 paise");
        stackLot.park(new Car("S3")); now[0] += 20 * 3_600_000L;
        check(stackLot.unpark("S3", new CashPayment()) == 10_000L, "twenty hours hits the cap of 10000 paise, because the cap wraps the surge");
        stackLot.park(new Car("PASS-1")); now[0] += 5 * 3_600_000L;
        check(stackLot.unpark("PASS-1", new CashPayment()) == 0L, "a monthly pass holder pays nothing and still frees the spot");
        check(stackLot.availability().get(SpotType.COMPACT) == 1, "every one of those exits freed its spot");

        // 14. electric spots: a charger is behaviour, so it is a subclass, and the meter is on the bill
        now[0] = SAT_10AM;
        ParkingFloor evFloor = new ParkingFloor("F1");
        evFloor.addSpot(new ParkingSpot("C1", SpotType.COMPACT));
        evFloor.addSpot(new EvSpot("EV1", SpotType.COMPACT, 7.0, () -> now[0]));
        ParkingLot evLot = new ParkingLot();
        evLot.setClock(() -> now[0]);
        evLot.configure(new ChargingPricing(new FlatHourlyPricing(), 1_200), new EvAwareAssignment(new SmallestFitStrategy()));
        evLot.addFloor(evFloor);
        check(evLot.park(new Car("PETROL")).spot.id.equals("C1"), "a petrol car does not take the charger while an ordinary spot is free");
        check(evLot.park(new ElectricCar("TESLA")).spot.id.equals("EV1"), "the electric car gets the charging spot");
        now[0] += 2 * 3_600_000L;
        check(evLot.unpark("TESLA", new CardPayment()) == 20_800L, "the bill is 2h x 2000 parking + 14 kWh x 1200 = 20800 paise");
        check(evLot.unpark("PETROL", new CardPayment()) == 4_000L, "the petrol car's bill has no charge on it");
        check(evLot.park(new Car("LATE1")).spot.id.equals("C1"), "with both free again, the petrol car still avoids the charger");
        check(evLot.park(new Car("LATE2")).spot.id.equals("EV1"), "but it does take the charger when that is the last spot left");

        // 15. reservations: a booked spot is held, expires, and comes back
        now[0] = SAT_10AM;
        ParkingFloor resFloor = floor("F1", "C1", SpotType.COMPACT, "C2", SpotType.COMPACT);
        ParkingLot resLot = lot(now, resFloor);
        ReservationDesk desk = new ReservationDesk(List.of(resFloor), new SmallestFitStrategy(), () -> now[0]);
        check(desk.reserve("BOOK", VehicleType.CAR, now[0] + 30 * 60_000L) != null, "the booking holds a fitting spot");
        check(resFloor.freeCount(SpotType.COMPACT) == 1, "the held spot has left the free queue: one is left for walk-ins");
        desk.reserve("LATE", VehicleType.CAR, now[0] + 10 * 60_000L);
        check(resFloor.freeCount(SpotType.COMPACT) == 0, "two bookings hold two spots");
        try { resLot.park(new Car("WALKIN")); check(false, "a walk-in must be rejected while both spots are held"); }
        catch (IllegalStateException e) { check(true, "the walk-in is rejected: both spots are booked"); }
        check(desk.claim(new Car("BOOK")) != null, "the car that turns up in time gets its ticket");
        now[0] += 11 * 60_000L;
        check(desk.sweep() == 1, "the booking nobody claimed is swept back once its deadline passes");
        check(resFloor.freeCount(SpotType.COMPACT) == 1, "and its spot is free again for whoever turns up");
        try { desk.claim(new Car("LATE")); check(false, "a swept reservation must not be claimable"); }
        catch (NoSuchElementException e) { check(true, "the late car finds no reservation and must park as a walk-in"); }
        check(resLot.park(new Car("WALKIN")) != null, "the walk-in turned away a minute ago now parks in the swept spot");

        // 16. the display board at a thousand updates a second: coalesce, never queue
        CoalescingBoard board = new CoalescingBoard();
        ParkingFloor boardFloor = floor("F1", "C1", SpotType.COMPACT);
        boardFloor.addObserver(board);
        ParkingLot boardLot = lot(now, boardFloor);
        for (int i = 0; i < 1000; i++) board.onChange("F1", Map.of(SpotType.COMPACT, i));
        board.render();
        check(board.renderCount() == 1, "1000 updates became 1 render: intermediate snapshots are dropped, not queued");
        check(board.lastRendered().get(SpotType.COMPACT) == 999, "and what it shows is the newest count, not the oldest");
        check(boardLot.park(new Car("BRD")) != null, "a gate is never slowed by the board: onChange is one map write");

        // 17. the same claim in a database: a conditional UPDATE, fifty callers, one row
        SpotTable table = new SpotTable();
        table.insert("C1");
        ExecutorService dbPool = Executors.newFixedThreadPool(8);
        CountDownLatch dbGo = new CountDownLatch(1);
        AtomicInteger rows = new AtomicInteger();
        List<Future<?>> dbTries = new ArrayList<>();
        for (int i = 0; i < 50; i++) { String plate = "D" + i; dbTries.add(dbPool.submit(() -> { dbGo.await(); rows.addAndGet(table.claim("C1", plate)); return null; })); }
        dbGo.countDown();
        for (Future<?> f : dbTries) f.get();
        dbPool.shutdown();
        check(rows.get() == 1, "UPDATE ... WHERE plate IS NULL: 50 callers, 1 row updated");
        check(table.release("C1", "nobody") == 0, "releasing someone else's spot updates no rows");
        check(table.release("C1", table.plateOf("C1")) == 1, "the owner's release updates exactly one row");

        // 18. a truck needs two adjacent spots: both, or nothing at all
        ParkingFloor truckFloor = floor("F1", "L1", SpotType.LARGE, "L2", SpotType.LARGE, "L3", SpotType.LARGE);
        TruckParking trucks = new TruckParking(new AdjacentAssignment(Map.of("L1", "L2", "L2", "L3")));
        MultiSpotTicket first = trucks.park(new Truck("TR1"), truckFloor);
        check(first != null && first.spots.size() == 2, "the first truck gets a pair of neighbours");
        check(trucks.park(new Truck("TR2"), truckFloor) == null, "the second truck gets nothing: one lone spot is not a pair");
        check(truckFloor.freeCount(SpotType.LARGE) == 1, "and nothing was half-taken: exactly one large spot is still free");
        trucks.release(first, truckFloor);
        check(truckFloor.freeCount(SpotType.LARGE) == 3, "releasing gives both spots back together");

        // 19. the ticket's life as a table: an illegal move throws instead of quietly passing
        try { TicketState.ISSUED.to(TicketState.CLOSED); check(false, "closing before paying must throw"); }
        catch (IllegalStateException e) { check(true, "ISSUED -> CLOSED is refused by the transition table"); }
        check(TicketState.ISSUED.to(TicketState.PAYING).to(TicketState.PAID).to(TicketState.CLOSED) == TicketState.CLOSED, "ISSUED -> PAYING -> PAID -> CLOSED is the legal path");

        // 20. the ladder rungs still hold the invariant
        CasFloor cas = new CasFloor();
        cas.add(new CasSpot("C1", SpotType.COMPACT));
        ExecutorService casPool = Executors.newFixedThreadPool(8);
        CountDownLatch casGo = new CountDownLatch(1);
        AtomicInteger casWins = new AtomicInteger();
        for (int i = 0; i < 50; i++) { String plate = "X" + i; casPool.submit(() -> { casGo.await(); if (cas.claim(new Car(plate)) != null) casWins.incrementAndGet(); return null; }); }
        casGo.countDown(); casPool.shutdown(); casPool.awaitTermination(5, TimeUnit.SECONDS);
        check(casWins.get() == 1, "rung 2, no lock at all: 50 compare-and-set claims, 1 winner");
        ParkingFloor fa = floor("F1", "C1", SpotType.COMPACT), fb = floor("F2", "C2", SpotType.COMPACT);
        FloorLocked perFloor = new FloorLocked(List.of(fa, fb), new SmallestFitStrategy());
        perFloor.park(new Car("P1"));
        check(perFloor.park(new Car("P2")).floor.id.equals("F2"), "rung 1, a lock per floor: the second car spills onto F2");

        // 21. money is a long count of paise (100 paise = one rupee), so every fee is exact
        now[0] = SAT_10AM;
        ParkingFloor tariffFloor = new ParkingFloor("F1");
        tariffFloor.addSpot(new EvSpot("EV1", SpotType.COMPACT, 7.0, () -> now[0]));
        ParkingLot tariff = new ParkingLot();
        tariff.setClock(() -> now[0]);
        tariff.configure(new ChargingPricing(new FlatHourlyPricing(), 710), new SmallestFitStrategy());   // Rs 7.10 a kWh
        tariff.addFloor(tariffFloor);
        tariff.park(new ElectricCar("EV-7")); now[0] += 2 * 3_600_000L;
        check(tariff.unpark("EV-7", new CardPayment()) == 13_940L, "2 h x Rs 20 + 14 kWh x Rs 7.10 = 13940 paise exactly (in double rupees: 139.39999999999998)");
        Ticket odd = new Ticket(new ParkingSpot("X1", SpotType.COMPACT), tariffFloor, new Car("ODD"), SAT_10AM);
        odd.exitMs = SAT_10AM;
        check(new WeekendSurgePricing(t -> 1_001L, ZoneId.of("UTC")).price(odd) == 1_502L, "1.5x in whole paise: 1001 x 1.5 = 1501.5, and the half paisa rounds up to 1502");

        // 22. a timeout, then a retry: the same key, so the driver is charged once
        ParkingLot flaky = lot(now, floor("F1", "C1", SpotType.COMPACT));
        flaky.park(new Car("TMO"));
        IdempotentGateway gateway = new IdempotentGateway(true);        // the first charge goes through, but its answer times out
        try { flaky.unpark("TMO", gateway); check(false, "a timeout must not look like a success"); }
        catch (IllegalStateException e) { check(true, "the timeout is reported as not confirmed: " + e.getMessage()); }
        check(flaky.isFullFor(VehicleType.CAR), "while the outcome is unknown the ticket is PENDING and the spot is still held");
        check(flaky.unpark("TMO", gateway) == 2_000L && gateway.charges() == 1, "the retry sends the same key: the gateway returns its first answer, one charge of 2000 paise");
        check(!flaky.isFullFor(VehicleType.CAR), "and the retry committed: the spot is free again");

        // 23. a slow card at one exit holds no lock: a park at another gate goes straight through,
        //     and a second checkout of the same ticket is refused while the first is PAYING
        ParkingLot slow = lot(now, floor("F1", "C1", SpotType.COMPACT, "C2", SpotType.COMPACT));
        slow.park(new Car("SLOW"));
        CountDownLatch inCall = new CountDownLatch(1), cardAnswers = new CountDownLatch(1);
        PaymentProcessor slowCard = (key, paise) -> {
            inCall.countDown();                                            // the card call has started
            try { cardAnswers.await(); } catch (InterruptedException e) { return PaymentStatus.UNKNOWN; }
            return PaymentStatus.OK;
        };
        ExecutorService gates = Executors.newFixedThreadPool(3);
        Future<Long> exiting = gates.submit(() -> slow.unpark("SLOW", slowCard));
        inCall.await();                                                    // exit gate 1 is now waiting on the card
        check(finishesWithin(gates.submit(() -> slow.park(new Car("FAST"))), 2), "a park at another gate completes while a card payment is in flight: no lock is held during the call");
        check(refusedWithin(gates.submit(() -> slow.unpark("SLOW", new CashPayment())), 2), "a second checkout of the same ticket while it is PAYING is refused at once, not queued and not charged");
        cardAnswers.countDown();                                           // the card says OK
        check(exiting.get() == 2_000L, "the first checkout completes once the card answers: 2000 paise");
        gates.shutdown();

        // 24. the Gojek / GoTo version: the statement's own command script, output compared exactly
        String script = String.join("\n",
            "create_parking_lot 6", "park KA-01-HH-1234 White", "park KA-01-HH-9999 White", "park KA-01-BB-0001 Black",
            "park KA-01-HH-7777 Red", "park KA-01-HH-2701 Blue", "park KA-01-HH-3141 Black", "leave 4", "status",
            "park KA-01-P-333 White", "park DL-12-AA-9999 White", "registration_numbers_for_cars_with_colour White",
            "slot_numbers_for_cars_with_colour White", "slot_number_for_registration_number KA-01-HH-3141",
            "slot_number_for_registration_number MH-04-AY-1111");
        String expected = String.join("\n",
            "Created a parking lot with 6 slots", "Allocated slot number: 1", "Allocated slot number: 2", "Allocated slot number: 3",
            "Allocated slot number: 4", "Allocated slot number: 5", "Allocated slot number: 6", "Slot number 4 is free",
            "Slot No.    Registration No    Colour",
            "1           KA-01-HH-1234      White",
            "2           KA-01-HH-9999      White",
            "3           KA-01-BB-0001      Black",
            "5           KA-01-HH-2701      Blue",
            "6           KA-01-HH-3141      Black",
            "Allocated slot number: 4", "Sorry, parking lot is full", "KA-01-HH-1234, KA-01-HH-9999, KA-01-P-333", "1, 2, 4",
            "6", "Not found") + "\n";
        ByteArrayOutputStream printed = new ByteArrayOutputStream();
        new CommandShell().run(new BufferedReader(new StringReader(script)), new PrintStream(printed, true));
        check(printed.toString().replace("\r\n", "\n").equals(expected), "the Gojek command script prints exactly the expected output: the freed slot 4 is the next one given");

        // 25. a declined card, then another card: a gateway keeps its FIRST answer per key, so the second try
        //     must carry a new key, or it would be told "declined" again whatever card is used
        ParkingLot declined = lot(now, floor("F1", "C1", SpotType.COMPACT));
        declined.park(new Car("DEC"));
        Map<String, PaymentStatus> firstAnswer = new ConcurrentHashMap<>();
        int[] gatewayCalls = {0};
        PaymentProcessor strictGateway = (key, paise) -> firstAnswer.computeIfAbsent(key, k -> ++gatewayCalls[0] == 1 ? PaymentStatus.DECLINED : PaymentStatus.OK);
        try { declined.unpark("DEC", strictGateway); check(false, "the first card must be declined"); }
        catch (IllegalStateException ex) { check(true, "the first card is declined and nothing is committed"); }
        long secondTry;
        try { secondTry = declined.unpark("DEC", strictGateway); } catch (IllegalStateException ex) { secondTry = -1; }
        check(secondTry == 2_000L && firstAnswer.size() == 2, "the second card goes out under a new key (attempt 1) and is charged: 2000 paise");

        // 26. a timeout, then the driver offers cash: the unconfirmed card payment is retried where it
        //     started, so the driver is never charged by card AND in cash
        ParkingLot mixed = lot(now, floor("F1", "C1", SpotType.COMPACT));
        mixed.park(new Car("MIX"));
        IdempotentGateway card = new IdempotentGateway(true);            // the card was charged, but the answer timed out
        int[] cashTaken = {0};
        PaymentProcessor cash = (key, paise) -> { cashTaken[0]++; return PaymentStatus.OK; };
        try { mixed.unpark("MIX", card); check(false, "a timeout must not look like a success"); }
        catch (IllegalStateException ex) { check(true, "the card timed out: the ticket waits as PENDING"); }
        check(mixed.unpark("MIX", cash) == 2_000L && card.charges() == 1 && cashTaken[0] == 0, "the retry goes back to the card gateway, which confirms its one charge; no cash is taken on top");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }

    /** True if the task finished within the given seconds; a task stuck behind a lock times out instead. */
    static boolean finishesWithin(Future<?> f, int seconds) throws InterruptedException {
        try { f.get(seconds, TimeUnit.SECONDS); return true; } catch (TimeoutException | ExecutionException e) { return false; }
    }
    /** True if the task was refused (IllegalStateException) within the given seconds, not run and not stuck. */
    static boolean refusedWithin(Future<?> f, int seconds) throws InterruptedException {
        try { f.get(seconds, TimeUnit.SECONDS); return false; }
        catch (ExecutionException e) { return e.getCause() instanceof IllegalStateException; }
        catch (TimeoutException e) { return false; }
    }
}
