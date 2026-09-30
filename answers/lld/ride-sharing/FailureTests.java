import java.util.*;
import java.util.concurrent.*;

// targeted failure tests: each one proves a claim the design makes on page 02, move 9, or on a page 05 card.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    static final Location PICKUP = new Location(12.9352, 77.6245);
    static final Location DROP   = new Location(12.9720, 77.5940);
    static long[] now = { 1_700_000_000_000L };

    /** A fresh service on a fresh grid, driven by the test's own clock. */
    static RideService service(GridIndex index, PaymentProcessor pay, PricingStrategy pricing) {
        RideService svc = new RideService(index);
        svc.configure(new NearestDriver(), pricing, new StandardCancellation(), pay);
        svc.setClock(() -> now[0]);
        return svc;
    }
    static Driver car(String id, String name, VehicleType type, double lat, double lng) {
        return new Driver(id, name, new Vehicle("KA" + id, type), new Location(lat, lng));
    }

    public static void main(String[] args) throws Exception {

        // 1. the race: two riders reaching for the same car must not both get it. Fifty threads, one car,
        //    then two hundred threads and forty cars: the count of trips must equal the count of cars exactly.
        for (int[] size : new int[][]{{1, 50}, {40, 200}}) {
            int cars = size[0], riders = size[1];
            GridIndex index = new GridIndex();
            RideService svc = service(index, new CardPayment(), new NormalPricing());
            List<Driver> fleet = new ArrayList<>();
            for (int i = 0; i < cars; i++) {
                Driver d = car("d" + i, "driver" + i, VehicleType.GO, 12.9352, 77.6245);
                svc.goOnline(d, d.location()); fleet.add(d);
            }
            for (int i = 0; i < riders; i++) svc.addRider(new Rider("r" + i, "rider" + i));
            ExecutorService pool = Executors.newFixedThreadPool(16);
            CountDownLatch go = new CountDownLatch(1);
            List<Future<Optional<Trip>>> futures = new ArrayList<>();
            for (int i = 0; i < riders; i++) {
                final String rid = "r" + i;
                futures.add(pool.submit(() -> { go.await(); return svc.requestRide(rid, PICKUP, DROP, VehicleType.GO); }));
            }
            go.countDown();
            Set<String> claimed = new HashSet<>(); Set<String> tripIds = new HashSet<>();
            for (Future<Optional<Trip>> f : futures) f.get().ifPresent(t -> { claimed.add(t.driver().id()); tripIds.add(t.id()); });
            pool.shutdown();
            check(tripIds.size() == cars, riders + " riders, " + cars + " car(s): exactly " + cars + " trips were created");
            check(claimed.size() == cars, "and no car was handed to two riders");
            long busy = fleet.stream().filter(d -> d.status() == DriverStatus.RESERVED).count();
            check(busy == cars, "every car that was claimed is RESERVED, none is still AVAILABLE");
        }

        // 2. matching: the NEAREST car of the RIGHT tier, and nobody outside the neighbourhood or offline
        GridIndex index = new GridIndex();
        RideService svc = service(index, new CardPayment(), new NormalPricing());
        svc.addRider(new Rider("R1", "Meera")); svc.addRider(new Rider("R2", "Ravi")); svc.addRider(new Rider("R3", "Nita"));
        Driver near    = car("D1", "Bilal", VehicleType.GO,      12.9354, 77.6246);   //  ~25 m
        Driver farIsh  = car("D2", "Asha",  VehicleType.GO,      12.9380, 77.6260);   // ~355 m
        Driver premier = car("D3", "Chen",  VehicleType.PREMIER, 12.9353, 77.6245);   //  ~11 m, wrong tier
        Driver away    = car("D4", "Dev",   VehicleType.GO,      12.9600, 77.6400);   // ~3.2 km, outside the 9 cells
        Driver offline = car("D5", "Evan",  VehicleType.GO,      12.9352, 77.6245);   // sitting on the pickup point
        for (Driver d : List.of(near, farIsh, premier, away)) svc.goOnline(d, d.location());
        Trip first = svc.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        check(first.driver() == near, "the nearest GO car was chosen, not the nearest car of any tier");
        check(!index.nearby(PICKUP).contains(offline), "a driver who never went online is not in the index at all");
        Trip second = svc.requestRide("R2", PICKUP, DROP, VehicleType.GO).orElseThrow();
        check(second.driver() == farIsh, "the second rider got the next-nearest GO car");
        check(svc.requestRide("R3", PICKUP, DROP, VehicleType.GO).isEmpty(),
              "a car 3 km away is never offered: the scan is nine cells, not the fleet");
        check(svc.requestRide("R3", PICKUP, DROP, VehicleType.PREMIER).orElseThrow().driver() == premier,
              "asking for PREMIER gets the PREMIER car, which was nearest all along");

        // 3. an out-of-order call throws BEFORE it writes, so the trip is exactly as it was
        Trip t = svc.trip(first.id());
        try { svc.endTrip(t.id(), 5.0); check(false, "ending a trip that never started must throw"); }
        catch (IllegalStateException e) { check(true, "out-of-order endTrip refused: " + e.getMessage()); }
        check(t.status() == TripStatus.ASSIGNED && t.farePaise() == 0 && t.distanceKm() == 0,
              "the refused call left the trip untouched: still ASSIGNED, no fare, no distance");
        svc.driverArrived(t.id());
        svc.startTrip(t.id());
        try { svc.cancelTrip(t.id()); check(false, "cancelling a moving car must throw"); }
        catch (IllegalStateException e) { check(true, "cancel after the meter started is refused: " + e.getMessage()); }
        check(t.status() == TripStatus.IN_PROGRESS && t.driver().status() == DriverStatus.ON_TRIP,
              "and the refused cancel left the trip running and the driver ON_TRIP");
        now[0] += 24 * 60_000L;
        svc.endTrip(t.id(), 8.0);
        try { svc.endTrip(t.id(), 8.0); check(false, "ending the same trip twice must throw"); }
        catch (IllegalStateException e) { check(true, "a second endTrip is refused, not charged again"); }

        // 4. every path that takes a car out of the pool puts it back, and the fee depends on the state
        check(near.status() == DriverStatus.AVAILABLE, "the finished trip put the car back into the pool");
        Trip early = svc.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        Driver claimed = early.driver();
        svc.cancelTrip(early.id());
        check(early.feePaise() == 0, "cancelling while the driver has only just set off is free");
        check(claimed.status() == DriverStatus.AVAILABLE, "and the car is back in the pool immediately");
        Trip late = svc.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        svc.driverArrived(late.id());
        now[0] += 5 * 60_000L;
        svc.cancelTrip(late.id());
        check(late.feePaise() == Money.rupees("30.00"), "cancelling with the driver at the kerb costs 30.00");
        check(late.driver().status() == DriverStatus.AVAILABLE, "and that car is back in the pool too");

        // 5. the fare comes from the injected clock and the driven distance, exactly, and surge multiplies it
        CardPayment cash = new CardPayment();
        GridIndex gi = new GridIndex();
        RideService plain = service(gi, cash, new NormalPricing());
        plain.addRider(new Rider("R1", "Meera"));
        Driver go = car("G1", "Asha", VehicleType.GO, 12.9352, 77.6245);
        plain.goOnline(go, go.location());
        Trip ride = plain.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        plain.driverArrived(ride.id()); plain.startTrip(ride.id());
        now[0] += 24 * 60_000L;
        plain.endTrip(ride.id(), 8.0);
        check(ride.minutes() == 24, "the ride lasted exactly 24 minutes by the injected clock");
        check(ride.farePaise() == Money.rupees("172.00"), "GO fare = 40 base + 12x8 km + 1.50x24 min = 172.00");
        RideService surged = service(new GridIndex(), new CardPayment(), new SurgePricing(new NormalPricing(), b -> 15_000));
        surged.addRider(new Rider("R1", "Meera"));
        Driver go2 = car("G2", "Bilal", VehicleType.GO, 12.9352, 77.6245);
        surged.goOnline(go2, go2.location());
        Trip hot = surged.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        surged.driverArrived(hot.id()); surged.startTrip(hot.id());
        now[0] += 24 * 60_000L;
        surged.endTrip(hot.id(), 8.0);
        check(hot.farePaise() == Money.rupees("258.00"), "the surge wrapper multiplied the same ride by 1.5: 258.00");
        check(hot.farePaise() == ride.farePaise() * 3 / 2, "and it multiplied, it did not re-derive the fare");

        // 6. the card declines AFTER the ride: the trip is COMPLETED_UNPAID, the car is free, the retry charges once
        boolean[] declining = { true };
        CardPayment real = new CardPayment();
        RideService flaky = service(new GridIndex(), (riderId, paise, key) -> {
            if (declining[0]) throw new PaymentDeclined("card declined");
            return real.charge(riderId, paise, key);
        }, new NormalPricing());
        flaky.addRider(new Rider("R1", "Meera"));
        Driver auto = car("A1", "Frank", VehicleType.AUTO, 12.9352, 77.6245);
        flaky.goOnline(auto, auto.location());
        Trip unpaid = flaky.requestRide("R1", PICKUP, DROP, VehicleType.AUTO).orElseThrow();
        flaky.driverArrived(unpaid.id()); flaky.startTrip(unpaid.id());
        now[0] += 10 * 60_000L;
        flaky.endTrip(unpaid.id(), 4.0);
        check(unpaid.status() == TripStatus.COMPLETED_UNPAID, "a declined card leaves the trip COMPLETED_UNPAID");
        check(unpaid.farePaise() == Money.rupees("62.00"), "the fare is still recorded: 20 + 8x4 km + 1x10 min = 62.00");
        check(auto.status() == DriverStatus.AVAILABLE, "the driver is free anyway: a card must never strand a car");
        check(unpaid.paymentRef().isEmpty(), "and nothing pretends the money moved");
        declining[0] = false;
        flaky.retryPayment(unpaid.id());
        check(unpaid.status() == TripStatus.COMPLETED && !unpaid.paymentRef().isEmpty(), "the retry completed the trip");
        check(real.charges() == 1, "money moved exactly once");
        try { flaky.retryPayment(unpaid.id()); check(false, "retrying a paid trip must throw"); }
        catch (IllegalStateException e) { check(true, "a retry on a paid trip is refused before the gateway is called"); }
        check(real.charges() == 1, "and the money still moved only once");
        //    the gateway takes the money and then times out: we do not know it moved, so the retry must not move it again
        CardPayment ledger = new CardPayment();
        boolean[] answerLost = { true };
        RideService unsure = service(new GridIndex(), (riderId, paise, key) -> {
            String ref = ledger.charge(riderId, paise, key);                            // the money really moved...
            if (answerLost[0]) { answerLost[0] = false; throw new PaymentDeclined("gateway timed out"); }   // ...the reply did not
            return ref;
        }, new NormalPricing());
        unsure.addRider(new Rider("R1", "Meera"));
        Driver u1 = car("U1", "Ravi", VehicleType.GO, 12.9352, 77.6245);
        unsure.goOnline(u1, u1.location());
        Trip unknown = unsure.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        unsure.driverArrived(unknown.id()); unsure.startTrip(unknown.id());
        now[0] += 24 * 60_000L;
        unsure.endTrip(unknown.id(), 8.0);
        check(unknown.status() == TripStatus.COMPLETED_UNPAID && ledger.charges() == 1, "a timeout leaves the trip unpaid in our books, though the money moved");
        unsure.retryPayment(unknown.id());
        check(unknown.status() == TripStatus.COMPLETED && ledger.charges() == 1,
              "the retry sent the same key, so the gateway returned the first charge instead of taking 172.00 twice");

        // 7. a listener that throws cannot break a trip: observers run after the state has already moved
        RideService noisy = service(new GridIndex(), new CardPayment(), new NormalPricing());
        noisy.addObserver((trip, from, to) -> { throw new RuntimeException("push gateway is down"); });
        noisy.addRider(new Rider("R1", "Meera"));
        Driver quiet = car("Q1", "Asha", VehicleType.GO, 12.9352, 77.6245);
        noisy.goOnline(quiet, quiet.location());
        Trip ok = noisy.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        noisy.driverArrived(ok.id()); noisy.startTrip(ok.id());
        now[0] += 12 * 60_000L;
        noisy.endTrip(ok.id(), 6.0);
        check(ok.status() == TripStatus.COMPLETED, "the trip completed although every notification threw");
        check(ok.farePaise() == Money.rupees("130.00"), "and the fare is right: 40 + 12x6 km + 1.50x12 min = 130.00");
        check(quiet.status() == DriverStatus.AVAILABLE, "and the car went back into the pool");

        // 8. the ping path: cheap, correct, and a driver who goes offline disappears from matching
        GridIndex pings = new GridIndex();
        RideService moving = service(pings, new CardPayment(), new NormalPricing());
        moving.addRider(new Rider("R1", "Meera"));
        Driver roamer = car("M1", "Dev", VehicleType.GO, 12.9352, 77.6245);
        moving.goOnline(roamer, roamer.location());
        long rewritesAfterOnline = pings.rewrites();
        for (int i = 0; i < 200; i++) moving.ping("M1", new Location(12.9352 + i * 0.000002, 77.6245));
        check(pings.pings() == 201, "201 pings arrived (the one at sign-on plus 200)");
        check(pings.rewrites() == rewritesAfterOnline, "none of the 200 rewrote the grid: the car never left its cell");
        check(pings.nearby(PICKUP).contains(roamer), "and he is still found at the pickup point");
        moving.ping("M1", new Location(12.9600, 77.6400));                    // 3 km away: a real cell crossing
        check(pings.rewrites() == rewritesAfterOnline + 1, "crossing a cell boundary rewrote the grid exactly once");
        check(!pings.nearby(PICKUP).contains(roamer), "he is no longer found at the old place");
        check(pings.nearby(new Location(12.9600, 77.6400)).contains(roamer), "and he is found at the new one");
        check(moving.requestRide("R1", PICKUP, DROP, VehicleType.GO).isEmpty(), "so a rider at the old place gets no car");
        moving.goOffline("M1");
        check(pings.nearby(new Location(12.9600, 77.6400)).isEmpty(), "going offline removes him from the index entirely");
        moving.ping("M1", new Location(12.9600, 77.6400));                    // a ping that was already in flight
        check(pings.nearby(new Location(12.9600, 77.6400)).isEmpty(), "and a late ping after sign-off does not put him back");
        Trip busy = svc.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        svc.driverArrived(busy.id()); svc.startTrip(busy.id());
        try { svc.goOffline(busy.driver().id()); check(false, "a driver must not vanish mid-ride"); }
        catch (IllegalStateException e) { check(true, "a driver cannot go offline while ON_TRIP"); }

        // 9. one rider, one live ride: a second tap must not become a second car, and the slot comes back at the end
        RideService one = service(new GridIndex(), new CardPayment(), new NormalPricing());
        one.addRider(new Rider("R1", "Meera"));
        Driver c1 = car("C1", "Asha",  VehicleType.GO, 12.9352, 77.6245);
        Driver c2 = car("C2", "Bilal", VehicleType.GO, 12.9353, 77.6246);
        one.goOnline(c1, c1.location()); one.goOnline(c2, c2.location());
        Trip held = one.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        try { one.requestRide("R1", PICKUP, DROP, VehicleType.GO); check(false, "a second tap must be refused"); }
        catch (IllegalStateException e) { check(true, "the second tap is refused: " + e.getMessage()); }
        check(one.trips().size() == 1, "the refused tap created no second trip");
        check(c2.status() == DriverStatus.AVAILABLE, "and it claimed no second car");
        check(one.activeTripOf("R1").orElseThrow() == held, "the app is told which ride he is already on");
        one.driverArrived(held.id()); one.startTrip(held.id());
        now[0] += 8 * 60_000L;
        one.endTrip(held.id(), 3.0);
        check(one.activeTripOf("R1").isEmpty(), "when the ride ends the rider's slot comes back");
        check(one.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow() != held, "so he can book again at once");

        RideService taps = service(new GridIndex(), new CardPayment(), new NormalPricing());
        taps.addRider(new Rider("R9", "Ravi"));
        List<Driver> five = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            Driver d = car("F" + i, "spare" + i, VehicleType.GO, 12.9352, 77.6245);
            taps.goOnline(d, d.location()); five.add(d);
        }
        ExecutorService tapPool = Executors.newFixedThreadPool(8);
        CountDownLatch tap = new CountDownLatch(1);
        List<Future<Optional<Trip>>> taken = new ArrayList<>();
        for (int i = 0; i < 20; i++)
            taken.add(tapPool.submit(() -> {
                tap.await();
                try { return taps.requestRide("R9", PICKUP, DROP, VehicleType.GO); }
                catch (IllegalStateException refused) { return Optional.<Trip>empty(); }   // the rider slot was taken
            }));
        tap.countDown();
        int rides = 0;
        for (Future<Optional<Trip>> f : taken) if (f.get().isPresent()) rides++;
        tapPool.shutdown();
        check(rides == 1, "twenty simultaneous taps from one rider produced exactly one ride");
        check(five.stream().filter(d -> d.status() != DriverStatus.AVAILABLE).count() == 1,
              "and exactly one of the five cars left the pool: putIfAbsent decided, not luck");

        // 10. something throws half-way through a request: the rider's slot and any car it claimed are handed back
        boolean[] routingDown = { true };
        RideService fragile = new RideService(new GridIndex());
        fragile.configure((p, type, cands) -> {
            if (routingDown[0]) throw new IllegalStateException("routing service timed out");
            return new NearestDriver().select(p, type, cands);
        }, new NormalPricing(), new StandardCancellation(), new CardPayment());
        boolean[] clockDown = { false };
        fragile.setClock(() -> { if (clockDown[0]) { clockDown[0] = false; throw new IllegalStateException("clock unavailable"); } return now[0]; });
        fragile.addRider(new Rider("R1", "Meera"));
        Driver only = car("X1", "Asha", VehicleType.GO, 12.9352, 77.6245);
        fragile.goOnline(only, only.location());
        try { fragile.requestRide("R1", PICKUP, DROP, VehicleType.GO); check(false, "a request whose rule throws must throw"); }
        catch (IllegalStateException e) { check(e.getMessage().contains("routing"), "the rule's failure reaches the caller: " + e.getMessage()); }
        routingDown[0] = false;
        clockDown[0] = true;                                                  // this time it fails AFTER the car is claimed
        try { fragile.requestRide("R1", PICKUP, DROP, VehicleType.GO); check(false, "a request whose clock throws must throw"); }
        catch (IllegalStateException e) { check(e.getMessage().contains("clock"), "a failure after the car was claimed reaches the caller too"); }
        check(only.status() == DriverStatus.AVAILABLE, "and the car it had claimed is back in the pool, not stuck RESERVED");
        boolean rebooked;
        try { rebooked = fragile.requestRide("R1", PICKUP, DROP, VehicleType.GO).isPresent(); }
        catch (IllegalStateException e) { rebooked = false; }
        check(rebooked, "and his slot came back, so his next tap books a car instead of 'already has a ride'");

        // 11. a payment retry on a trip that is still running is refused BEFORE the gateway is called
        CardPayment gateway = new CardPayment();
        RideService eager = service(new GridIndex(), gateway, new NormalPricing());
        eager.addRider(new Rider("R1", "Meera"));
        Driver e1 = car("E1", "Bilal", VehicleType.GO, 12.9352, 77.6245);
        eager.goOnline(e1, e1.location());
        Trip running = eager.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        eager.driverArrived(running.id()); eager.startTrip(running.id());
        try { eager.retryPayment(running.id()); check(false, "a retry on a running trip must be refused"); }
        catch (IllegalStateException e) { check(true, "a retry on a running trip is refused: " + e.getMessage()); }
        check(gateway.charges() == 0, "and the gateway was never called, so the trip's key is still unused");
        now[0] += 24 * 60_000L;
        eager.endTrip(running.id(), 8.0);
        check(running.paymentRef().endsWith("-172.00"),
              "so the real end charges the real 172.00, not a 0.00 left under the key by the early retry: " + running.paymentRef());

        // 12. a distance that is negative, not a number, or infinite is refused before anything is written
        CardPayment meterPay = new CardPayment();
        RideService meter = service(new GridIndex(), meterPay, new NormalPricing());
        meter.addRider(new Rider("R1", "Meera"));
        Driver k1 = car("K1", "Chen", VehicleType.GO, 12.9352, 77.6245);
        meter.goOnline(k1, k1.location());
        Trip odd = meter.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        meter.driverArrived(odd.id()); meter.startTrip(odd.id());
        now[0] += 10 * 60_000L;
        for (double bad : new double[]{-10.0, Double.NaN, Double.POSITIVE_INFINITY}) {
            try { meter.endTrip(odd.id(), bad); check(false, bad + " km must be refused, not billed"); }
            catch (RuntimeException e) { check(e instanceof IllegalArgumentException, bad + " km is refused as bad input"); }
        }
        check(odd.status() == TripStatus.IN_PROGRESS && meterPay.charges() == 0, "and the ride is still running, with no money moved");

        // 13. one object per driver id: a second object under a known id is refused, so no ghost stays claimable
        RideService registry = service(new GridIndex(), new CardPayment(), new NormalPricing());
        registry.addRider(new Rider("R1", "Meera"));
        Driver dev1 = car("D7", "Dev", VehicleType.GO, 12.9352, 77.6245);
        Driver dev2 = car("D7", "Dev", VehicleType.GO, 12.9352, 77.6245);        // his phone restarted and signed on afresh
        registry.goOnline(dev1, dev1.location());
        try { registry.goOnline(dev2, dev2.location()); check(false, "a second object for D7 must be refused"); }
        catch (IllegalArgumentException e) { check(true, "a second object for D7 is refused: " + e.getMessage()); }
        registry.goOffline("D7");
        check(registry.requestRide("R1", PICKUP, DROP, VehicleType.GO).isEmpty(), "after D7 goes offline no rider can be sent to him");

        // 14. racing pings: one driver's pings handled on eight threads at once leave him in exactly ONE cell
        GridIndex storm = new GridIndex();
        Driver drifter = car("S1", "Drifter", VehicleType.GO, 12.9352, 77.6245);
        drifter.goOnline(); storm.update(drifter, drifter.location());
        List<Location> visited = Collections.synchronizedList(new ArrayList<>());
        ExecutorService pingers = Executors.newFixedThreadPool(8);
        CountDownLatch burst = new CountDownLatch(1);
        for (int th = 0; th < 8; th++) {
            final int lane = th;
            pingers.submit(() -> {
                burst.await();
                for (int i = 0; i < 500; i++) {                                  // every ping lands in a cell no other ping uses
                    Location l = new Location(10.0 + lane + (i / 20) * 0.03, 70.0 + (i % 20) * 0.03);
                    visited.add(l);
                    storm.update(drifter, l);
                }
                return null;
            });
        }
        burst.countDown(); pingers.shutdown(); pingers.awaitTermination(60, TimeUnit.SECONDS);
        Location parked = new Location(20.0, 80.0);
        storm.update(drifter, parked);
        long ghosts = visited.stream().filter(l -> storm.nearby(l).contains(drifter)).count();
        check(ghosts == 0 && storm.nearby(parked).contains(drifter),
              "4,000 racing pings later he is found where he parked and nowhere else (cells still holding him: " + ghosts + ")");

        // 15. extension claims: widening finds a FREE car, surge counts one area, a coupon cannot pay the rider,
        //     and an upfront quote is what the rider pays
        PrecisionIndex sparse = new PrecisionIndex(0.0025, 1);
        Driver busyNear = car("W1", "Busy", VehicleType.GO, 12.9352, 77.6245);
        busyNear.goOnline(); busyNear.reserve(); sparse.update(busyNear, busyNear.location());
        Driver freeFar = car("W2", "Free", VehicleType.GO, 12.9352 + 0.0075, 77.6245);   // three small cells north
        freeFar.goOnline(); sparse.update(freeFar, freeFar.location());
        check(sparse.nearbyWidening(PICKUP, VehicleType.GO, 10).contains(freeFar), "widening walks past a busy car to the free one three cells out");
        GridIndex hub = new GridIndex();
        for (int i = 0; i < 3; i++) { Driver d = car("Z" + i, "z" + i, VehicleType.GO, 12.9352, 77.6245); d.goOnline(); hub.update(d, d.location()); }
        DemandCounter asks = new DemandCounter(5 * 60_000L);
        for (int i = 0; i < 6; i++) asks.record(new Location(12.9452, 77.6245), now[0]);   // one cell north: inside the nine
        FareBasis at = new FareBasis(VehicleType.GO, 8.0, 24, PICKUP, now[0]);
        check(new ZoneSurge(hub, asks).basisPoints(at) == 20_000, "surge counts demand over the same nine cells as supply: 6 asks / 3 cars = 2.0x");
        try { new CouponPricing(new NormalPricing(), 12_000, Money.rupees("1000.00")); check(false, "a 120% coupon must be refused"); }
        catch (IllegalArgumentException e) { check(true, "a coupon over 100% is refused when it is made"); }
        FareQuote upfront = new FareQuote(new NormalPricing(), b -> 15_000);
        FareQuote.Quote shown = upfront.quote(VehicleType.GO, PICKUP, DROP, now[0]);
        check(upfront.bill(shown.id(), VehicleType.GO, 8.0, 24, PICKUP, now[0]) == shown.paise(),
              "a ride within 15% of the estimate pays exactly the quote, " + Money.fmt(shown.paise()));
        check(upfront.bill(shown.id(), VehicleType.GO, 3.0, 10, PICKUP, now[0]) < shown.paise(),
              "a ride far shorter than the estimate (a changed destination) is re-metered, not charged the full quote");
        try { upfront.bill("Q404", VehicleType.GO, 8.0, 24, PICKUP, now[0]); check(false, "an unknown quote must be refused"); }
        catch (IllegalArgumentException e) { check(true, "an unknown quote id is refused, never billed at 1.0x"); }

        // 16. offers with a deadline: never two offers for one driver, a late tap cannot take a newer offer, a decline moves on
        GridIndex offerGrid = new GridIndex();
        List<Driver> trio = new ArrayList<>();
        for (int i = 0; i < 3; i++) {
            Driver d = car("O" + i, "o" + i, VehicleType.GO, 12.9352 + i * 0.0005, 77.6245);
            d.goOnline(); offerGrid.update(d, d.location()); trio.add(d);
        }
        OfferDesk desk = new OfferDesk(offerGrid, new NearestDriver(), () -> now[0], 15_000);
        ExecutorService dispatchers = Executors.newFixedThreadPool(8);
        CountDownLatch ring = new CountDownLatch(1);
        List<Future<Optional<Offer>>> made = new ArrayList<>();
        for (int i = 0; i < 30; i++) {
            final String rid = "q" + i;
            made.add(dispatchers.submit(() -> { ring.await(); return desk.offer(rid, PICKUP, VehicleType.GO); }));
        }
        ring.countDown();
        int offersMade = 0;
        for (Future<Optional<Offer>> f : made) if (f.get().isPresent()) offersMade++;
        dispatchers.shutdown();
        check(offersMade == 3 && trio.stream().allMatch(d -> desk.historyOf(d.id()).size() == 1),
              "30 riders at once, 3 cars: exactly 3 offers, one per driver, never two at once");
        now[0] += 16_000;
        check(desk.expireDue() == 3 && trio.stream().allMatch(d -> d.status() == DriverStatus.AVAILABLE),
              "nobody tapped in 15 s: all 3 offers expired and the cars are back in the pool");
        String staleOffer = desk.historyOf("O0").get(0).id();
        Offer fresh = desk.offer("late-rider", PICKUP, VehicleType.GO).orElseThrow();
        check(fresh.driver() == trio.get(0) && !desk.accept(staleOffer),
              "his tap on the OLD offer is refused, although his status reads RESERVED again");
        check(fresh.outcome() == Offer.Outcome.PENDING && trio.get(0).status() == DriverStatus.RESERVED, "and the new offer is untouched");
        desk.decline(fresh.id());
        Offer next = desk.offer("late-rider", PICKUP, VehicleType.GO).orElseThrow();
        check(next.driver() != trio.get(0) && desk.accept(next.id()), "after a decline the next-nearest driver is asked, not the same one again");
        check(desk.historyOf("O0").size() == 2 && desk.historyOf("O0").get(1).outcome() == Offer.Outcome.DECLINED,
              "and his history shows what he let expire and what he declined");

        // 17. the car-pool version: a seat is never sold twice, and a vehicle has one open ride
        CarPool carPool = new CarPool();
        CarPool.Ride swift = carPool.offer("John", "KA-09-32321", 3, "Bangalore", "Mysore", now[0], 3 * 3_600_000L);
        ExecutorService passengers = Executors.newFixedThreadPool(8);
        CountDownLatch doors = new CountDownLatch(1);
        List<Future<Optional<CarPool.Ride>>> seats = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            final String p = "p" + i;
            seats.add(passengers.submit(() -> { doors.await(); return carPool.select(p, "Bangalore", "Mysore", 1, CarPool.Preference.MOST_VACANT, null); }));
        }
        doors.countDown();
        int seated = 0;
        for (Future<Optional<CarPool.Ride>> f : seats) if (f.get().isPresent()) seated++;
        passengers.shutdown();
        check(seated == 3 && swift.seatsLeft() == 0, "20 passengers at once for 3 seats: exactly 3 seated, none oversold");
        try { carPool.offer("John", "KA-09-32321", 2, "Bangalore", "Mysore", now[0], 3_600_000L); check(false, "a second open ride on one vehicle must be refused"); }
        catch (IllegalStateException e) { check(true, "a second open ride on the same vehicle is refused"); }
        carPool.end(swift.id);
        check(carPool.offer("John", "KA-09-32321", 2, "Mysore", "Bangalore", now[0], 3_600_000L) != null,
              "once the ride ends, the vehicle can offer the next one");
        check(carPool.offeredBy("John").size() == 2 && carPool.takenBy("p0").size() + carPool.takenBy("p1").size() <= 2,
              "and the per-user history lists what each one offered and took");

        // 18. the map's nearest free cars, and the route log that measures a trip from its own pings
        RideService mapped = service(new GridIndex(), new CardPayment(), new NormalPricing());
        Driver m0 = car("N0", "near", VehicleType.GO, 12.9354, 77.6246), mBusy = car("N1", "busy", VehicleType.GO, 12.9353, 77.6245);
        Driver mFar = car("N2", "far", VehicleType.GO, 12.9380, 77.6260), mAuto = car("N3", "auto", VehicleType.AUTO, 12.9352, 77.6245);
        for (Driver d : List.of(m0, mBusy, mFar, mAuto)) mapped.goOnline(d, d.location());
        mBusy.reserve();
        check(mapped.nearestFree(PICKUP, VehicleType.GO, 5).equals(List.of(m0, mFar)), "the map lists free cars of the tier only, nearest first");
        check(mapped.nearestFree(PICKUP, VehicleType.GO, 1).equals(List.of(m0)), "and k = 1 keeps just the nearest");
        RouteLog log = new RouteLog(new GridIndex());
        RideService traced = new RideService(log);
        traced.configure(new NearestDriver(), new NormalPricing(), new StandardCancellation(), new CardPayment());
        traced.setClock(() -> now[0]); traced.addObserver(log);
        traced.addRider(new Rider("R1", "Meera"));
        Driver v1 = car("V1", "Dev", VehicleType.GO, 12.9352, 77.6245);
        traced.goOnline(v1, v1.location());
        traced.ping("V1", new Location(12.9353, 77.6245));                     // before any trip: belongs to no route
        Trip routed = traced.requestRide("R1", PICKUP, DROP, VehicleType.GO).orElseThrow();
        traced.driverArrived(routed.id()); traced.startTrip(routed.id());
        for (int i = 1; i <= 3; i++) traced.ping("V1", new Location(12.9352 + i * 0.0045, 77.6245));   // three pings ~0.5 km apart
        now[0] += 6 * 60_000L;
        traced.endTrip(routed.id(), log.drivenKm(routed.id()));
        traced.ping("V1", new Location(12.9600, 77.6245));                     // after the trip: not added to it
        check(log.routeOf(routed.id()).size() == 4, "the route holds the pickup and the three pings of the ride, nothing before or after");
        check(Math.abs(routed.distanceKm() - 1.5) < 0.01, "and the fare's distance was measured from them: " + String.format("%.3f", routed.distanceKm()) + " km");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
