import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// targeted failure tests: each one proves a claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    static final Geo SHOP = new Geo(12.9352, 77.6245);
    static final Geo HOME = new Geo(12.9352, 77.6495);                 // 2.7 km away, billed as 3

    /** A service with the standard chain and a gateway the test can watch. */
    static OrderService service(PaymentProcessor gateway, List<PricingRule> rules, String cancelFee) {
        OrderService s = new OrderService();
        s.configure(rules, new NearestFree(), new StandardCancellation(Money.rupees(cancelFee)), gateway);
        return s;
    }
    /** The standard chain: food, distance fee, surge, a capped 40% coupon, a flat coupon. */
    static List<PricingRule> chain() {
        return List.of(new ItemTotal(),
                       new DistanceFee(Money.rupees("20.00"), Money.rupees("8.00")),
                       new SurgeFee(15_000),
                       new CappedDiscount(new PercentCoupon("TASTY40", 4000), Money.rupees("120.00")),
                       new FlatCoupon("NEWUSER", Money.rupees("50.00")));
    }
    /** Open a cart, add one line, place it. */
    static Order place(OrderService s, String who, String rid, String item, int qty, String key, List<String> coupons) {
        s.openCart(who, rid, HOME);
        s.addToCart(who, rid, item, qty);
        return s.placeOrder(key, who, coupons);
    }

    /** Place one dish and walk it all the way to DELIVERED; the rider comes from the pool. */
    static Order delivered(OrderService s, String who, String rid, String item, String key) {
        Order o = place(s, who, rid, item, 1, key, List.of());
        s.accept(o.id()); s.startPreparing(o.id()); s.markReady(o.id()); s.pickUp(o.id()); s.deliver(o.id());
        return o;
    }
    /** A restaurant with one dish, registered with the service. */
    static Restaurant kitchen(OrderService s, String id, String item, String price, int units) {
        Restaurant r = new Restaurant(id, id, SHOP, 5);
        r.put(new MenuItem(item, item, Money.rupees(price)), units);
        s.register(r);
        return r;
    }

    /** A rule written next year: it adds a packaging fee to the delivery line but forgets the total. */
    static final class SloppyRule implements PricingRule {
        public Bill apply(Bill running, PriceCtx ctx) {
            return new Bill(running.items(), running.delivery() + 2000, running.surge(),
                            running.discount(), running.total());
        }
    }

    /** A gateway whose refund call fails until recover(): the refund's own "no answer". */
    static final class RefundsDown implements PaymentProcessor {
        private volatile boolean down = true;
        final AtomicInteger refunds = new AtomicInteger();
        public boolean charge(String chargeId, long paise) { return true; }
        public void refund(String chargeId, long paise) {
            if (down) throw new RuntimeException("refund API down");
            refunds.incrementAndGet();
        }
        void recover() { down = false; }
    }

    public static void main(String[] args) throws Exception {

        // 1. thirty phones, ten portions, two each: the stock decides, exactly five orders exist,
        //    and the card is touched exactly five times.
        FakeGateway g1 = new FakeGateway();
        OrderService s1 = service(g1, List.of(new ItemTotal()), "0.00");
        Restaurant rush = new Restaurant("r1", "Meghana", SHOP, 15);
        rush.put(new MenuItem("thali", "Andhra Thali", Money.rupees("300.00")), 10);
        s1.register(rush);
        ExecutorService pool = Executors.newFixedThreadPool(12);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Boolean>> tries = new ArrayList<>();
        for (int i = 0; i < 30; i++) {
            final String who = "c" + i;
            s1.openCart(who, "r1", HOME);
            s1.addToCart(who, "r1", "thali", 2);
            tries.add(pool.submit(() -> {
                go.await();
                try { s1.placeOrder("k" + who, who, List.of()); return true; }
                catch (RuntimeException e) { return false; }
            }));
        }
        go.countDown();
        int won = 0;
        for (Future<Boolean> f : tries) if (f.get()) won++;
        check(won == 5, "30 phones raced for 10 portions at 2 each: exactly 5 orders exist (" + won + ")");
        check(rush.stockOf("thali") == 0, "the stock landed on exactly zero, never below");
        check(g1.chargeCount() == 5, "the card was touched exactly 5 times, once per winner");

        // 2. one unavailable line rejects the WHOLE order, and nothing else moves
        FakeGateway g2 = new FakeGateway();
        OrderService s2 = service(g2, chain(), "50.00");
        Restaurant shop = new Restaurant("r2", "Truffles", SHOP, 18);
        shop.put(new MenuItem("paneer", "Paneer Tikka", Money.rupees("249.00")), 6);
        shop.put(new MenuItem("naan", "Butter Naan", Money.rupees("60.00")), 2);
        s2.register(shop);
        s2.openCart("anita", "r2", HOME);
        s2.addToCart("anita", "r2", "paneer", 2);
        s2.addToCart("anita", "r2", "naan", 5);                        // only 2 left
        try {
            s2.placeOrder("a1", "anita", List.of());
            check(false, "an unavailable line must reject the whole order");
        } catch (IllegalStateException e) {
            check(true, "an unavailable line rejects the whole order: " + e.getMessage());
        }
        check(shop.stockOf("paneer") == 6 && shop.stockOf("naan") == 2, "the in-stock line was not reserved either");
        check(g2.chargeCount() == 0, "and the card was never touched");

        // 3. the coupon chain: percent first, capped, then flat -- and the parts always add up to the total
        s2.setDemand((r, t) -> true);
        s2.openCart("anita", "r2", HOME);
        s2.addToCart("anita", "r2", "paneer", 2);
        s2.addToCart("anita", "r2", "naan", 1);
        Order priced = s2.placeOrder("a2", "anita", List.of("TASTY40", "NEWUSER"));
        Bill b = priced.bill();
        check(b.items() == 55800 && b.delivery() == 4400 && b.surge() == 2200,
              "items 558.00, delivery 44.00 (20 + 8 x 3 km), surge 22.00 (1.5x on the fee)");
        check(b.discount() == 17000, "40% of 558.00 is 223.20 but the cap is 120.00, plus a flat 50.00 = 170.00");
        check(b.total() == 45400 && b.items() + b.delivery() + b.surge() - b.discount() == b.total(),
              "total 454.00, and the parts add up to it exactly");

        // and a rule written next year that leaves the parts out of step is caught before the card is touched
        FakeGateway g3 = new FakeGateway();
        OrderService s3 = service(g3, List.of(new ItemTotal(), new SloppyRule()), "0.00");
        Restaurant broken = new Restaurant("r3", "Broken", SHOP, 10);
        broken.put(new MenuItem("x", "Thing", Money.rupees("100.00")), 5);
        s3.register(broken);
        try {
            place(s3, "bala", "r3", "x", 1, "b1", List.of());
            check(false, "a rule whose parts do not add up must be caught");
        } catch (IllegalStateException e) {
            check(true, "CheckedRule caught the broken rule: " + e.getMessage());
        }
        check(broken.stockOf("x") == 5 && g3.chargeCount() == 0, "the broken rule reserved nothing and charged nothing");

        // 4. a declined card creates no order at all, and hands the food back
        FakeGateway g4 = new FakeGateway();
        g4.declineContaining("ch-");
        OrderService s4 = service(g4, chain(), "50.00");
        Restaurant late = new Restaurant("r4", "Empire", SHOP, 12);
        late.put(new MenuItem("roll", "Kathi Roll", Money.rupees("150.00")), 4);
        s4.register(late);
        try {
            place(s4, "carol", "r4", "roll", 2, "c1", List.of());
            check(false, "a declined card must not create an order");
        } catch (IllegalStateException e) {
            check(true, "a declined card throws instead of placing: " + e.getMessage());
        }
        check(late.stockOf("roll") == 4, "the reserved rolls went straight back on the shelf");
        check(g4.refundCount() == 0, "and no refund was needed, because nothing was ever committed");

        // 5. cancel before the kitchen starts is free; after it starts, the fee is kept
        FakeGateway g5 = new FakeGateway();
        OrderService s5 = service(g5, List.of(new ItemTotal()), "50.00");
        Restaurant kit = new Restaurant("r5", "Kitchen", SHOP, 20);
        kit.put(new MenuItem("dosa", "Masala Dosa", Money.rupees("120.00")), 10);
        s5.register(kit);
        Order early = place(s5, "d1", "r5", "dosa", 1, "e1", List.of());
        Refund r1 = s5.cancel(early.id());
        check(r1.refundedPaise() == 12000 && r1.keptPaise() == 0, "cancelled while PLACED: the whole 120.00 came back");
        check(kit.stockOf("dosa") == 10, "and the uncooked dosa went back on the shelf");

        Order cooking = place(s5, "d2", "r5", "dosa", 1, "e2", List.of());
        s5.accept(cooking.id());
        s5.startPreparing(cooking.id());
        Refund r2 = s5.cancel(cooking.id());
        check(r2.refundedPaise() == 7000 && r2.keptPaise() == 5000, "cancelled while PREPARING: 50.00 fee kept, 70.00 back");
        check(kit.stockOf("dosa") == 9, "and the dosa already on the tawa was not put back");

        // 5b. a stricter rule handed in (Flipkart 2025: an accepted order cannot be cancelled): the policy says no
        OrderService strict = new OrderService();
        strict.configure(List.of(new ItemTotal()), new NearestFree(), (order, from, now) -> {
            if (from != OrderState.PLACED) throw new IllegalStateException("an accepted order cannot be cancelled");
            return order.bill().total();
        }, new FakeGateway());
        kitchen(strict, "r5s", "dosa", "120.00", 10);
        Order taken = place(strict, "d4", "r5s", "dosa", 1, "e4", List.of());
        strict.accept(taken.id());
        try { strict.cancel(taken.id()); check(false, "the stricter policy must refuse"); }
        catch (IllegalStateException e) { check(taken.state() == OrderState.ACCEPTED, "a policy that refuses leaves the order untouched: " + e.getMessage()); }

        // 6. the state machine refuses a skipped step and a late cancellation
        s5.register(new DeliveryPartner("r5-rider", SHOP));
        Order live = place(s5, "d3", "r5", "dosa", 1, "e3", List.of());
        s5.accept(live.id()); s5.startPreparing(live.id()); s5.markReady(live.id());
        try { s5.deliver(live.id()); check(false, "READY -> DELIVERED must be refused"); }
        catch (IllegalStateException e) { check(true, "a skipped step is refused: " + e.getMessage()); }
        s5.pickUp(live.id());
        try { s5.cancel(live.id()); check(false, "a cancel after pickup must be refused"); }
        catch (IllegalStateException e) { check(true, "no cancelling once the rider has it: " + e.getMessage()); }
        s5.deliver(live.id());
        check(live.state() == OrderState.DELIVERED && live.state().isTerminal(), "DELIVERED is terminal");

        // 7. one rider, two orders ready at the same instant: exactly one claim wins
        FakeGateway g6 = new FakeGateway();
        OrderService s6 = service(g6, List.of(new ItemTotal()), "0.00");
        Restaurant busy = new Restaurant("r6", "Busy", SHOP, 10);
        busy.put(new MenuItem("wrap", "Wrap", Money.rupees("200.00")), 50);
        s6.register(busy);
        s6.register(new DeliveryPartner("only-one", new Geo(12.9353, 77.6246)));
        Order o1 = place(s6, "f1", "r6", "wrap", 1, "g1", List.of());
        Order o2 = place(s6, "f2", "r6", "wrap", 1, "g2", List.of());
        for (Order o : List.of(o1, o2)) { s6.accept(o.id()); s6.startPreparing(o.id()); }
        CountDownLatch go2 = new CountDownLatch(1);
        Future<Boolean> a = pool.submit(() -> { go2.await(); return s6.markReady(o1.id()); });
        Future<Boolean> c = pool.submit(() -> { go2.await(); return s6.markReady(o2.id()); });
        go2.countDown();
        int got = (a.get() ? 1 : 0) + (c.get() ? 1 : 0);
        check(got == 1, "two orders, one rider: exactly one assignment won (" + got + ")");
        check(s6.waitingCount() == 1, "the loser is queued, not failed");
        Order carrying = o1.partnerId() != null ? o1 : o2;
        Order waiting  = carrying == o1 ? o2 : o1;
        s6.pickUp(carrying.id());
        s6.deliver(carrying.id());
        check(waiting.partnerId() != null && s6.waitingCount() == 0,
              "delivering hands the rider back, and the waiting order takes him");

        // 8. a listener that throws cannot break an order, and the same tap twice is one order and one charge
        s6.addObserver((o, from) -> { throw new RuntimeException("push gateway down"); });
        Order survived = place(s6, "f3", "r6", "wrap", 1, "g3", List.of());
        s6.accept(survived.id());
        check(survived.state() == OrderState.ACCEPTED, "a notifier that throws did not stop the transition");
        int before = g6.chargeCount();
        Order retry = s6.placeOrder("g3", "f3", List.of());
        check(retry == survived && g6.chargeCount() == before,
              "the same idempotency key returns the first order and charges nothing more");
        Order other = place(s6, "f4", "r6", "wrap", 1, "g3", List.of());   // another customer, the same key
        check(other != survived && other.customerId().equals("f4") && g6.chargeCount() == before + 1,
              "another customer who sends the same key gets his own order, never the first customer's");

        // 9. the restaurant rejects an order the customer has already paid for
        FakeGateway g7 = new FakeGateway();
        OrderService s7 = service(g7, List.of(new ItemTotal()), "0.00");
        Restaurant shut = new Restaurant("r7", "Shut", SHOP, 10);
        shut.put(new MenuItem("idli", "Idli", Money.rupees("80.00")), 4);
        s7.register(shut);
        Order paid = place(s7, "h1", "r7", "idli", 2, "h1k", List.of());
        Refund back = s7.reject(paid.id());
        check(back.refundedPaise() == 16000 && g7.refundCount() == 1,
              "a restaurant that refuses a paid order refunds the whole 160.00");
        check(shut.stockOf("idli") == 4, "and the two idlis go back on the shelf");
        check(paid.state() == OrderState.REJECTED && shut.liveQueue().isEmpty(), "REJECTED, and off the tablet");
        try { s7.accept(paid.id()); check(false, "a rejected order must not be acceptable"); }
        catch (IllegalStateException e) { check(true, "and nobody can accept it afterwards: " + e.getMessage()); }

        // 10. the gateway takes the money and never answers: no order, and the sweep refunds the orphan once
        TimeoutGateway g8 = new TimeoutGateway();
        ChargeBook book = new ChargeBook();
        OrderService s8 = service(g8, List.of(new ItemTotal()), "0.00");
        s8.setChargeLog(book);
        Restaurant tiff = new Restaurant("r8", "Tiffins", SHOP, 10);
        tiff.put(new MenuItem("vada", "Medu Vada", Money.rupees("90.00")), 6);
        s8.register(tiff);
        try {
            place(s8, "j1", "r8", "vada", 2, "j1k", List.of());
            check(false, "an unknown payment outcome must not place an order");
        } catch (IllegalStateException e) {
            check(true, "a gateway that never answered leaves no order: " + e.getMessage());
        }
        check(tiff.stockOf("vada") == 6, "the vadas went straight back on the shelf");
        check(book.having(ChargeOutcome.UNKNOWN).size() == 1, "the attempt is on record as UNKNOWN: the only trace of the money");
        Reconciler reconciler = new Reconciler(book, g8.settlement(), g8);
        check(reconciler.sweep() == 1 && g8.refundCount() == 1, "the sweep asks the gateway and refunds the orphan");
        check(reconciler.sweep() == 0 && g8.refundCount() == 1, "a second sweep refunds nothing: it is idempotent");
        g8.recover();
        place(s8, "j1", "r8", "vada", 2, "j1k", List.of());
        check(tiff.stockOf("vada") == 4, "and the customer's retry, on the same key, places one real order");

        // 11. a rider coming free races an order becoming ready: nobody waits while a rider stands idle
        FakeGateway g9 = new FakeGateway();
        OrderService s9 = service(g9, List.of(new ItemTotal()), "0.00");
        Restaurant track = new Restaurant("r9", "Race Kitchen", SHOP, 5);
        track.put(new MenuItem("bun", "Bun", Money.rupees("100.00")), 2000);
        s9.register(track);
        s9.register(new DeliveryPartner("solo", new Geo(12.9353, 77.6246)));
        int stranded = 0;
        for (int round = 0; round < 150; round++) {
            Order carried = place(s9, "x" + round, "r9", "bun", 1, "xa" + round, List.of());
            Order next = place(s9, "y" + round, "r9", "bun", 1, "xb" + round, List.of());
            for (Order o : List.of(carried, next)) { s9.accept(o.id()); s9.startPreparing(o.id()); }
            s9.markReady(carried.id());                                   // takes the only rider
            CountDownLatch gate = new CountDownLatch(1);
            Future<?> dropping = pool.submit(() -> { gate.await(); s9.pickUp(carried.id()); s9.deliver(carried.id()); return null; });
            Future<?> readying = pool.submit(() -> { gate.await(); return s9.markReady(next.id()); });
            gate.countDown();
            dropping.get(); readying.get();
            if (next.partnerId() == null) stranded++;                     // a free rider and a waiting order
            s9.pickUp(next.id()); s9.deliver(next.id());                  // reset for the next round
        }
        check(stranded == 0, "150 rounds of deliver-races-ready: never once did an order wait for an idle rider");

        // and two riders coming free at the same instant must not both be given to the same waiting order
        OrderService s10 = service(new FakeGateway(), List.of(new ItemTotal()), "0.00");
        Restaurant two = new Restaurant("r10", "Two Riders", SHOP, 5);
        two.put(new MenuItem("bun", "Bun", Money.rupees("100.00")), 2000);
        s10.register(two);
        DeliveryPartner ra = new DeliveryPartner("ra", new Geo(12.9353, 77.6246));
        DeliveryPartner rb = new DeliveryPartner("rb", new Geo(12.9354, 77.6247));
        s10.register(ra); s10.register(rb);
        int doubled = 0;
        for (int round = 0; round < 150; round++) {
            Order a1 = place(s10, "p" + round, "r10", "bun", 1, "pa" + round, List.of());
            Order a2 = place(s10, "q" + round, "r10", "bun", 1, "qa" + round, List.of());
            Order waits = place(s10, "w" + round, "r10", "bun", 1, "wa" + round, List.of());
            for (Order o : List.of(a1, a2, waits)) { s10.accept(o.id()); s10.startPreparing(o.id()); s10.markReady(o.id()); }
            CountDownLatch gate = new CountDownLatch(1);
            Future<?> d1 = pool.submit(() -> { gate.await(); s10.pickUp(a1.id()); s10.deliver(a1.id()); return null; });
            Future<?> d2 = pool.submit(() -> { gate.await(); s10.pickUp(a2.id()); s10.deliver(a2.id()); return null; });
            gate.countDown();
            d1.get(); d2.get();
            int idle = (ra.isAvailable() ? 1 : 0) + (rb.isAvailable() ? 1 : 0);
            if (waits.partnerId() == null || idle != 1) doubled++;        // one carries it, one is free
            s10.pickUp(waits.id()); s10.deliver(waits.id());
        }
        check(doubled == 0, "150 rounds of two hand-backs at once: one rider took the waiting order, one stayed free");

        // 12. the customer cancels at the instant a rider is being found: the rider must not stay with a dead order
        CountDownLatch ranking = new CountDownLatch(1), carryOn = new CountDownLatch(1);
        AssignmentRule slow = (free, pickup) -> {                      // a ranking that pauses mid-dispatch
            ranking.countDown();
            try { carryOn.await(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            return new NearestFree().rank(free, pickup);
        };
        OrderService s12 = new OrderService();
        s12.configure(List.of(new ItemTotal()), slow, new StandardCancellation(0), new FakeGateway());
        kitchen(s12, "r12", "bun", "100.00", 10);
        DeliveryPartner lone = new DeliveryPartner("lone", SHOP);
        s12.register(lone);
        Order gone = place(s12, "z1", "r12", "bun", 1, "z1k", List.of());
        s12.accept(gone.id()); s12.startPreparing(gone.id());
        Future<Boolean> dispatching = pool.submit(() -> s12.markReady(gone.id()));
        ranking.await();                                               // the dispatcher is mid-ranking...
        s12.cancel(gone.id());                                         // ...and the customer cancels right now
        carryOn.countDown();
        dispatching.get();
        check(lone.isAvailable() && gone.partnerId() == null,
              "a cancel that lands mid-dispatch leaves the rider free, not stuck with a cancelled order");

        // 13. two riders come free at the same instant while two orders wait: both orders get one
        AtomicBoolean armed = new AtomicBoolean();
        AtomicInteger calls = new AtomicInteger();
        CyclicBarrier together = new CyclicBarrier(2);
        AssignmentRule inStep = (free, pickup) -> {                    // once armed, the first two rankings meet
            if (armed.get() && calls.incrementAndGet() <= 2)
                try { together.await(2, TimeUnit.SECONDS); } catch (Exception e) { }
            return new NearestFree().rank(free, pickup);
        };
        OrderService s13 = new OrderService();
        s13.configure(List.of(new ItemTotal()), inStep, new StandardCancellation(0), new FakeGateway());
        kitchen(s13, "r13", "bun", "100.00", 10);
        s13.register(new DeliveryPartner("rc", SHOP));
        s13.register(new DeliveryPartner("rd", SHOP));
        List<Order> four = new ArrayList<>();
        for (int i = 0; i < 4; i++) {                                  // the first two ride, the last two wait
            Order o = place(s13, "t" + i, "r13", "bun", 1, "tk" + i, List.of());
            s13.accept(o.id()); s13.startPreparing(o.id()); s13.markReady(o.id());
            four.add(o);
        }
        s13.pickUp(four.get(0).id()); s13.pickUp(four.get(1).id());
        armed.set(true);
        Future<?> drop1 = pool.submit(() -> { s13.deliver(four.get(0).id()); return null; });
        Future<?> drop2 = pool.submit(() -> { s13.deliver(four.get(1).id()); return null; });
        drop1.get(); drop2.get();
        check(four.get(2).partnerId() != null && four.get(3).partnerId() != null && s13.waitingCount() == 0,
              "two riders freed at the same instant: both waiting orders got one, and nobody idles");

        // 14. nobody picks up an order that has no rider, and a rider who logs in takes a waiting order at once
        OrderService s14 = service(new FakeGateway(), List.of(new ItemTotal()), "0.00");
        kitchen(s14, "r14", "bun", "100.00", 10);
        Order lonely = place(s14, "l1", "r14", "bun", 1, "l1k", List.of());
        s14.accept(lonely.id()); s14.startPreparing(lonely.id()); s14.markReady(lonely.id());   // no riders yet
        try { s14.pickUp(lonely.id()); check(false, "an order with no rider must not be picked up"); }
        catch (IllegalStateException e) { check(true, "no rider, no pickup: " + e.getMessage()); }
        s14.register(new DeliveryPartner("late", SHOP));
        check("late".equals(lonely.partnerId()) && s14.waitingCount() == 0,
              "a rider who logs in while an order waits is given it at once");

        // 15. the refund fails during a cancel: the rider and the food still go back, and the refund is owed
        RefundsDown g15 = new RefundsDown();
        ChargeBook book15 = new ChargeBook();
        OrderService s15 = service(g15, List.of(new ItemTotal()), "0.00");
        s15.setChargeLog(book15);
        kitchen(s15, "r15", "bun", "100.00", 10);
        DeliveryPartner rr = new DeliveryPartner("rr", SHOP);
        s15.register(rr);
        Order owed = place(s15, "u1", "r15", "bun", 1, "u1k", List.of());
        s15.accept(owed.id()); s15.startPreparing(owed.id()); s15.markReady(owed.id());   // rr carries it
        try { s15.cancel(owed.id()); } catch (RuntimeException e) { check(false, "the cancel threw: " + e.getMessage()); }
        check(rr.isAvailable() && owed.state() == OrderState.CANCELLED, "a refund that fails does not strand the rider");
        check(book15.having(ChargeOutcome.REFUND_OWED).size() == 1, "the refund is on record as owed, not lost");
        g15.recover();
        Reconciler sweeper = new Reconciler(book15, chargeId -> true, g15);
        check(sweeper.sweep() == 1 && sweeper.sweep() == 0 && g15.refunds.get() == 1,
              "the sweep sends the owed refund once, and a second sweep sends nothing");

        // 16. a rider who says yes to an offer is the order's rider, and is handed back after the drop
        OrderService s16 = new OrderService();
        s16.configure(List.of(new ItemTotal()), (free, pickup) -> List.of(), new StandardCancellation(0), new FakeGateway());
        kitchen(s16, "r16", "bun", "100.00", 10);
        DeliveryPartner ro = new DeliveryPartner("ro", SHOP);
        s16.register(ro);
        Order offered = place(s16, "v1", "r16", "bun", 1, "v1k", List.of());
        s16.accept(offered.id()); s16.startPreparing(offered.id()); s16.markReady(offered.id());   // it waits
        boolean took = new OfferDesk().offer(ro, offered, (id, deadline) -> true, 0);
        check(took && "ro".equals(offered.partnerId()), "a rider who accepts an offer is attached to the order");
        s16.pickUp(offered.id()); s16.deliver(offered.id());
        check(ro.isAvailable(), "and he is back in the pool after the drop");

        // 17. a booking for 20:00 is released early enough to ARRIVE at 20:00, through its own cart
        OrderService s17 = service(new FakeGateway(), List.of(new ItemTotal()), "0.00");
        Restaurant dinner = new Restaurant("r17", "Dinner", SHOP, 18);         // 18 minutes of cooking
        dinner.put(new MenuItem("bun", "Bun", Money.rupees("100.00")), 50);
        s17.register(dinner);
        Restaurant shutK = new Restaurant("r17x", "Shut", SHOP, 30);
        shutK.put(new MenuItem("bun", "Bun", Money.rupees("100.00")), 5);
        shutK.setOpen(false);
        s17.register(shutK);
        Scheduler sch = new Scheduler(22);                                     // HOME is a 7.4 minute ride away
        long eight = 1_700_000_000_000L;
        sch.book(new Scheduler.Booking("bad", "w1", "r17x", HOME, Map.of("bun", 1), eight));
        sch.book(new Scheduler.Booking("b1", "w1", "r17", HOME, Map.of("bun", 2), eight));
        s17.openCart("w1", "r17", HOME);                                       // meanwhile she is browsing
        s17.addToCart("w1", "r17", "bun", 1);
        check(sch.tick(s17, eight - 26 * 60_000L).isEmpty() && sch.failed().size() == 1,
              "26 minutes before, nothing is due; the closed kitchen's booking fails on its own");
        check(sch.tick(s17, eight - 25 * 60_000L).size() == 1,
              "25 minutes before, it is released: 18 minutes of cooking plus 7 of riding, so it lands at 20:00");
        check(s17.placeOrder("w1-own", "w1", List.of()).lines().get(0).qty() == 1,
              "and the customer's own cart was left alone: it still checks out with her one bun");

        // 18. Flipkart's FoodKart: a rating is the average of delivered orders, once each; the listing is sorted
        OrderService s18 = service(new FakeGateway(), List.of(new ItemTotal()), "0.00");
        Restaurant fc1 = kitchen(s18, "fc1", "thali", "100.00", 5), fc2 = kitchen(s18, "fc2", "thali", "120.00", 3);
        s18.register(new DeliveryPartner("d18", SHOP));
        Catalog cat = new Catalog();
        cat.onboard(fc1, Set.of("560102", "560076"));
        cat.onboard(fc2, Set.of("560076"));
        Order ate1 = delivered(s18, "e1", "fc1", "thali", "k1"), ate2 = delivered(s18, "e2", "fc1", "thali", "k2");
        cat.rate(ate1, 3, "ok");
        cat.rate(ate2, 4, "");
        cat.rate(delivered(s18, "e3", "fc2", "thali", "k3"), 5, "Nice Food");
        check(cat.ratingTenths("fc1") == 35 && cat.ratingTenths("fc2") == 50, "fc1 is (3 + 4) / 2 = 3.5 and fc2 is 5.0, in integer tenths");
        try { cat.rate(ate1, 1, "again"); check(false, "an order must not be rated twice"); }
        catch (IllegalStateException e) { check(true, "an order is rated once: " + e.getMessage()); }
        List<Catalog.Listing> best = cat.find("560076", "thali", Catalog.BEST_RATED);
        List<Catalog.Listing> cheap = cat.find("560076", "thali", Catalog.CHEAPEST);
        check(best.get(0).restaurantId().equals("fc2") && cheap.get(0).restaurantId().equals("fc1")
              && cat.find("560102", "thali", Catalog.CHEAPEST).size() == 1,
              "560076 best rated: fc2 first; cheapest: fc1 first; 560102 sees only fc1");
        KitchenPicker byStars = new KitchenPicker();
        byStars.capacity("fc1", 10);
        byStars.capacity("fc2", 10);
        Order starred = byStars.place(s18, "st", "e5", HOME, Map.of("thali", 1), List.of(fc1, fc2), KitchenPicker.bestRated(cat));
        check(starred.restaurantId().equals("fc2"), "the best-rated strategy sends an order to fc2, though fc1 is cheaper");
        fc2.setStock("thali", 0);
        check(cat.find("560076", "thali", Catalog.BEST_RATED).size() == 1, "a kitchen with none left drops out of the list");

        // 19. Intuit's version: the system picks the kitchen, and 12 customers at once never overfill one
        OrderService s19 = service(new FakeGateway(), List.of(new ItemTotal()), "0.00");
        Restaurant cheapK = kitchen(s19, "ka", "thali", "100.00", 100), dearK = kitchen(s19, "kb", "thali", "150.00", 100);
        KitchenPicker picker = new KitchenPicker();
        s19.addObserver(picker);
        picker.capacity("ka", 4);                                      // items it can cook at once
        picker.capacity("kb", 6);
        Map<String, Integer> twoThalis = Map.of("thali", 2);
        CountDownLatch go19 = new CountDownLatch(1);
        List<Future<Order>> picks = new ArrayList<>();
        for (int i = 0; i < 12; i++) {
            final String who = "m" + i;
            picks.add(pool.submit(() -> {
                go19.await();
                try { return picker.place(s19, "mk", who, HOME, twoThalis, List.of(cheapK, dearK), KitchenPicker.cheapest(twoThalis)); }
                catch (IllegalStateException full) { return null; }
            }));
        }
        go19.countDown();
        List<Order> atCheap = new ArrayList<>();
        int atDear = 0, turnedAway = 0;
        for (Future<Order> f : picks) {
            Order o = f.get();
            if (o == null) turnedAway++; else if (o.restaurantId().equals("ka")) atCheap.add(o); else atDear++;
        }
        check(atCheap.size() == 2 && atDear == 3 && turnedAway == 7,
              "12 at once, 2 thalis each: the cheap kitchen takes 2 orders (4 items), the dear one 3 (6), 7 are told all are full");
        s19.cancel(atCheap.get(0).id());
        Order next19 = picker.place(s19, "mk", "m99", HOME, twoThalis, List.of(cheapK, dearK), KitchenPicker.cheapest(twoThalis));
        check(next19.restaurantId().equals("ka"), "a cancel gives the cheap kitchen its room back, so the next order goes there");
        CommandReplay replay = new CommandReplay();                   // the same round's input arrives shuffled
        s19.setClock(replay.clock());
        Order[] fed = new Order[1];
        replay.submit(300, "start cooking", () -> s19.startPreparing(fed[0].id()));
        replay.submit(100, "place", () -> fed[0] = place(s19, "n1", "ka", "thali", 1, "n1k", List.of()));
        replay.submit(200, "accept", () -> s19.accept(fed[0].id()));
        List<String> ran = replay.runAll();
        check(fed[0].state() == OrderState.PREPARING && fed[0].stamps().get(OrderState.PLACED) == 100
              && fed[0].stamps().get(OrderState.PREPARING) == 300 && ran.get(0).startsWith("100 place"),
              "commands fed as 300, 100, 200 run as 100, 200, 300, and each stamp is its command's time");

        pool.shutdown();
        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
