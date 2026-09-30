import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Fifteen groups of claims the design makes, each proven by a few lines. Run it with
 * javac Main.java Extensions.java FailureTests.java && java FailureTests
 * It prints ALL PASS, or every failure and a non-zero exit code.
 */
public class FailureTests {
    static int failed = 0;

    /** Record one claim. Prints ok or FAIL with the claim's name. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "  ok   " : "  FAIL ") + what);
        if (!ok) failed++;
    }

    /** The page's store (10 pens, 5 mugs, 3 kurtis, SAVE10 and FLAT100) on a clock the test moves, with this bank. */
    static Store store(long[] now, PaymentGateway bank) {
        Store s = Main.stocked();
        s.configure(new ListPrice(), bank, Store.HOLD_MS);
        s.setClock(() -> now[0]);
        return s;
    }

    /** Run n threads that all start at the same instant (one latch), and wait for all of them. */
    static void race(int n, IntConsumerX body) throws InterruptedException {
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(n);
        for (int i = 0; i < n; i++) {
            final int k = i;
            new Thread(() -> {
                try { go.await(); body.accept(k); }
                catch (Exception e) { /* the body records its own outcome */ }
                finally { done.countDown(); }
            }).start();
        }
        go.countDown();
        if (!done.await(30, TimeUnit.SECONDS)) check(false, "a race did not finish in 30 s");
    }
    /** A thread body that may throw. */
    interface IntConsumerX { void accept(int k) throws Exception; }

    public static void main(String[] args) throws Exception {
        // 1. the race: a hundred buyers, ten pens
        System.out.println("1. a hundred buyers press Buy for ten pens at the same instant");
        long[] now = { Main.at(10, 0) };
        FakeGateway bank = new FakeGateway();
        Store sale = store(now, bank);
        List<Order> won = Collections.synchronizedList(new ArrayList<>());
        AtomicInteger soldOut = new AtomicInteger(), other = new AtomicInteger();
        race(100, k -> {
            try { won.add(sale.createOrder("buyer" + k, "k", Map.of("PEN", 1), null)); }
            catch (OrderRefused e) { if (e.reason == Reason.OUT_OF_STOCK) soldOut.incrementAndGet(); else other.incrementAndGet(); }
        });
        StockView pen = sale.stockOf("PEN");
        check(won.size() == 10, "exactly ten orders were placed");
        check(soldOut.get() == 90 && other.get() == 0, "the other ninety were told OUT_OF_STOCK, and nothing else went wrong");
        check(pen.available() == 0 && pen.reserved() == 10 && pen.sold() == 0, "PEN: available 0, reserved 10; never below zero");
        check(won.stream().map(o -> o.id).distinct().count() == 10, "ten different order ids");
        List<PayResult> results = Collections.synchronizedList(new ArrayList<>());
        List<Order> winners = List.copyOf(won);
        race(winners.size(), k -> results.add(sale.confirmOrder(winners.get(k).id)));
        check(results.size() == 10 && results.stream().allMatch(r -> r == PayResult.CONFIRMED), "all ten pay at the same instant: all confirmed");
        check(sale.stockOf("PEN").equals(new StockView(0, 0, 10)), "PEN: sold 10, reserved 0");
        check(bank.heldPaise() == 10 * 20_00, "the bank holds exactly ten pens' money, Rs 200");

        // 2. all or nothing
        System.out.println("2. one order, one line short: nothing is blocked");
        Store aon = store(now, new FakeGateway());
        try { aon.createOrder("zoya", "z1", Map.of("PEN", 2, "MUG", 1, "KURTI", 5), null); check(false, "a short order was placed"); }
        catch (OrderRefused e) { check(e.reason == Reason.OUT_OF_STOCK && e.getMessage().startsWith("KURTI"), "refused OUT_OF_STOCK, naming KURTI"); }
        check(aon.stockOf("PEN").equals(new StockView(10, 0, 0)) && aon.stockOf("MUG").equals(new StockView(5, 0, 0)),
              "PEN and MUG are untouched, although they came before KURTI");
        try { aon.createOrder("zoya", "z2", Map.of("PEN", 1, "SOCK", 1), null); check(false, "an unknown product was ordered"); }
        catch (OrderRefused e) { check(e.reason == Reason.UNKNOWN_PRODUCT, "an unknown SKU refuses the whole order"); }
        try { aon.createOrder("zoya", "z3", Map.of("PEN", 0), null); check(false, "zero pens were ordered"); }
        catch (OrderRefused e) { check(e.reason == Reason.BAD_QUANTITY, "a quantity of 0 is refused"); }
        check(aon.orderHistory("zoya").isEmpty() && aon.getInventory("PEN") == 10, "a refusal leaves no order and no block behind");

        // 3. the hold ends at exactly five minutes, with no thread
        System.out.println("3. the hold ends at exactly five minutes, and nobody has to run a thread for it");
        long[] t3 = { Main.at(10, 0) };
        Store hold = store(t3, new FakeGateway());
        Order held = hold.createOrder("ravi", "r", Map.of("KURTI", 3), "FLAT100");
        t3[0] = Main.at(10, 5) - 1;
        check(hold.getInventory("KURTI") == 0 && hold.order(held.id).status() == OrderStatus.PENDING_PAYMENT,
              "at 10:04:59.999 all three kurtis are still held");
        t3[0] = Main.at(10, 5);
        check(hold.getInventory("KURTI") == 3, "at 10:05:00.000 exactly, all three are back on sale");
        check(held.status() == OrderStatus.EXPIRED, "the order is EXPIRED");
        check(hold.couponUses("FLAT100") == 0, "its coupon use was given back");
        check(hold.confirmOrder(held.id) == PayResult.REFUSED, "paying an expired order is refused, and nothing is charged");

        // 4. the money arrives after the hold ended, or after a cancel
        System.out.println("4. the bank answers after the hold ended: refund, and the stock is not sold");
        long[] t4 = { Main.at(10, 0) };
        FakeGateway bank4 = new FakeGateway();
        Store late = store(t4, bank4);
        Order lo = late.createOrder("meera", "m", Map.of("KURTI", 1), null);
        late.configure(new ListPrice(), new PaymentGateway() {
            public boolean charge(String id, long paise) { t4[0] = Main.at(10, 6); return bank4.charge(id, paise); }   // answers at 10:06
            public void refund(String id) { bank4.refund(id); }
        }, Store.HOLD_MS);
        check(late.confirmOrder(lo.id) == PayResult.REFUNDED, "the money arrived at 10:06, after the 10:05 end: REFUNDED");
        check(bank4.charges.get() == 1 && bank4.heldPaise() == 0, "charged once and given back: the bank holds nothing");
        check(late.stockOf("KURTI").equals(new StockView(3, 0, 0)) && lo.status() == OrderStatus.EXPIRED,
              "the kurti was never sold; the order ended EXPIRED");
        long[] t4b = { Main.at(12, 0) };
        FakeGateway bank4b = new FakeGateway();
        Store both = store(t4b, bank4b);
        Order co = both.createOrder("asha", "a", Map.of("MUG", 2), null);
        both.configure(new ListPrice(), new PaymentGateway() {
            public boolean charge(String id, long paise) { both.cancelOrder(id); return bank4b.charge(id, paise); }   // she cancels while the bank works
            public void refund(String id) { bank4b.refund(id); }
        }, Store.HOLD_MS);
        check(both.confirmOrder(co.id) == PayResult.REFUNDED && co.status() == OrderStatus.CANCELLED,
              "cancelled while the bank was working: the late money is refunded");
        check(bank4b.heldPaise() == 0 && both.stockOf("MUG").equals(new StockView(5, 0, 0)), "no money kept, both mugs back on sale");

        // 5. a declined card keeps the hold
        System.out.println("5. a declined card: nothing moves, the hold keeps running, another card works");
        long[] t5 = { Main.at(10, 0) };
        FakeGateway bank5 = new FakeGateway();
        AtomicInteger tries = new AtomicInteger();
        Store dec = store(t5, new PaymentGateway() {
            public boolean charge(String id, long paise) { return tries.incrementAndGet() > 1 && bank5.charge(id, paise); }   // first card declined
            public void refund(String id) { bank5.refund(id); }
        });
        Order dO = dec.createOrder("asha", "a", Map.of("MUG", 2), null);
        check(dec.confirmOrder(dO.id) == PayResult.DECLINED && dO.status() == OrderStatus.PENDING_PAYMENT, "declined: still PENDING_PAYMENT");
        check(dec.stockOf("MUG").equals(new StockView(3, 2, 0)) && bank5.heldPaise() == 0, "the two mugs stay blocked for her, no money moved");
        t5[0] = Main.at(10, 4);
        check(dec.confirmOrder(dO.id) == PayResult.CONFIRMED && dec.stockOf("MUG").equals(new StockView(3, 0, 2)),
              "a second card at 10:04 confirms: two mugs sold");

        // 6. twenty taps on Pay
        System.out.println("6. twenty taps on Pay at once: one charge, one sale");
        FakeGateway bank6 = new FakeGateway();
        Store tap = store(new long[] { Main.at(10, 0) }, new PaymentGateway() {
            public boolean charge(String id, long paise) {
                try { Thread.sleep(5); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }   // a slow bank, so the taps overlap
                return bank6.charge(id, paise);
            }
            public void refund(String id) { bank6.refund(id); }
        });
        Order tapped = tap.createOrder("asha", "t", Map.of("MUG", 2), null);
        List<PayResult> taps = Collections.synchronizedList(new ArrayList<>());
        race(20, k -> taps.add(tap.confirmOrder(tapped.id)));
        check(taps.size() == 20 && taps.stream().allMatch(r -> r == PayResult.CONFIRMED), "all twenty taps answer CONFIRMED");
        check(bank6.charges.get() == 1 && bank6.heldPaise() == 2 * 299_00, "the money moved once: the order id is the bank's idempotency key");
        check(tap.stockOf("MUG").equals(new StockView(3, 0, 2)), "two mugs sold, not four");

        // 7. the same request twice
        System.out.println("7. the same createOrder twice, and twenty at once: one order, blocked once");
        Store idem = store(new long[] { Main.at(10, 0) }, new FakeGateway());
        Order first = idem.createOrder("asha", "tap-1", Map.of("MUG", 2), null);
        Order second = idem.createOrder("asha", "tap-1", Map.of("MUG", 2), null);
        check(first == second && idem.stockOf("MUG").reserved() == 2, "a retry with the same key returns the same order; two mugs blocked, not four");
        List<String> ids = Collections.synchronizedList(new ArrayList<>());
        race(20, k -> ids.add(idem.createOrder("ravi", "tap-2", Map.of("MUG", 1), null).id));
        check(ids.size() == 20 && new HashSet<>(ids).size() == 1 && idem.stockOf("MUG").reserved() == 3,
              "twenty copies of Ravi's request at once: one order, one mug blocked");
        check(!idem.createOrder("meera", "tap-1", Map.of("MUG", 1), null).id.equals(first.id), "a key belongs to one buyer: Meera's tap-1 is a new order");
        Order slash1 = idem.createOrder("a/b", "c", Map.of("PEN", 1), null);
        Order slash2 = idem.createOrder("a", "b/c", Map.of("PEN", 1), null);
        check(slash1 != slash2, "buyer 'a/b' with key 'c' and buyer 'a' with key 'b/c' are two orders, not one");
        idem.addToCart("zoya", "PEN", 2);
        Order zc = idem.checkout("zoya", "c-1", null);
        idem.addToCart("zoya", "PEN", 1);                                   // she adds a pen after her first checkout went through
        check(idem.checkout("zoya", "c-1", null) == zc && idem.viewCart("zoya").equals(Map.of("PEN", 1)),
              "a checkout retried after its cart was emptied returns the same order and leaves the new cart alone");

        // 8. coupon limits under a race
        System.out.println("8. a coupon for ten buyers, once each: exact under a race, given back by dead orders");
        long[] t8 = { Main.at(10, 0) };
        Store cp = store(t8, new FakeGateway());
        cp.addProduct("SOAP", "Soap", 100_00, 1000);
        cp.addCoupon(new Coupon("FIRST10", 1, 10, base -> new PercentOff(base, "FIRST10", 50, 1_000_00)));
        List<Order> withCoupon = Collections.synchronizedList(new ArrayList<>());
        AtomicInteger usedUp = new AtomicInteger();
        race(50, k -> {
            try { withCoupon.add(cp.createOrder("u" + k, "k", Map.of("SOAP", 1), "FIRST10")); }
            catch (OrderRefused e) { if (e.reason == Reason.COUPON_USED_UP) usedUp.incrementAndGet(); }
        });
        check(withCoupon.size() == 10 && usedUp.get() == 40 && cp.couponUses("FIRST10") == 10, "fifty buyers: exactly ten got it, forty were told COUPON_USED_UP");
        check(cp.stockOf("SOAP").reserved() == 10, "and the forty refusals blocked no soap");
        Order winner = withCoupon.get(0);
        for (Order o : withCoupon) if (o != winner) cp.confirmOrder(o.id);
        try { cp.createOrder(winner.userId, "again", Map.of("SOAP", 1), "FIRST10"); check(false, "a buyer used FIRST10 twice"); }
        catch (OrderRefused e) { check(e.reason == Reason.COUPON_USED_UP, "a winner cannot use it a second time"); }
        t8[0] = Main.at(10, 5);                                             // the one unpaid winner's hold ends
        check(cp.couponUses("FIRST10") == 9, "the unpaid order expired and gave its use back: 9 claimed");
        check(cp.createOrder("late-comer", "k", Map.of("SOAP", 1), "FIRST10").totalPaise() == 50_00, "so one more buyer gets it, at half price");
        try { cp.createOrder("tiny", "k", Map.of("PEN", 1), "FLAT100"); check(false, "FLAT100 applied to Rs 20"); }
        catch (OrderRefused e) { check(e.reason == Reason.COUPON_NOT_APPLICABLE && cp.couponUses("FLAT100") == 0, "FLAT100 on a Rs 20 order: refused, and no use spent"); }
        try { cp.createOrder("tiny", "k2", Map.of("PEN", 1), "NOPE"); check(false, "an unknown coupon applied"); }
        catch (OrderRefused e) { check(e.reason == Reason.UNKNOWN_COUPON, "an unknown code is refused"); }

        // 9. cancel and fulfil
        System.out.println("9. cancel before and after payment, twice, and after delivery");
        FakeGateway bank9 = new FakeGateway();
        Store cn = store(new long[] { Main.at(10, 0) }, bank9);
        Order unpaid = cn.createOrder("asha", "a1", Map.of("MUG", 2), null);
        check(cn.cancelOrder(unpaid.id) == OrderStatus.CANCELLED && cn.stockOf("MUG").equals(new StockView(5, 0, 0)), "unpaid: the block is released");
        check(cn.confirmOrder(unpaid.id) == PayResult.REFUSED && bank9.charges.get() == 0, "a cancelled order cannot be paid");
        Order paid = cn.createOrder("asha", "a2", Map.of("KURTI", 2), "SAVE10");
        cn.confirmOrder(paid.id);
        check(cn.cancelOrder(paid.id) == OrderStatus.CANCELLED && cn.stockOf("KURTI").equals(new StockView(3, 0, 0)), "paid: both kurtis go back on sale");
        check(bank9.heldPaise() == 0 && cn.couponUses("SAVE10") == 0, "the money and the coupon use come back");
        check(cn.cancelOrder(paid.id) == OrderStatus.CANCELLED && cn.stockOf("KURTI").equals(new StockView(3, 0, 0)), "a second cancel changes nothing");
        FakeGateway oldBank = new FakeGateway();
        cn.configure(new ListPrice(), oldBank, Store.HOLD_MS);
        Order switched = cn.createOrder("meera", "m1", Map.of("MUG", 1), null);
        cn.confirmOrder(switched.id);
        cn.configure(new ListPrice(), bank9, Store.HOLD_MS);                // the shop moves to another bank
        cn.cancelOrder(switched.id);
        check(oldBank.heldPaise() == 0, "the refund goes through the bank that took the money, not the one configured now");
        Order delivered = cn.createOrder("ravi", "r1", Map.of("PEN", 1), null);
        try { cn.fulfilOrder(delivered.id); check(false, "an unpaid order was delivered"); }
        catch (IllegalStateException e) { check(true, "an unpaid order cannot be marked fulfilled"); }
        cn.confirmOrder(delivered.id);
        cn.fulfilOrder(delivered.id);
        try { cn.cancelOrder(delivered.id); check(false, "a delivered order was cancelled"); }
        catch (IllegalStateException e) { check(delivered.status() == OrderStatus.FULFILLED, "a delivered order cannot be cancelled: that is a return"); }

        // 10. listeners
        System.out.println("10. listeners run after the unlock, and a broken one cannot break an order");
        Store ls = store(new long[] { Main.at(10, 0) }, new FakeGateway());
        List<String> heard = new CopyOnWriteArrayList<>();
        AtomicBoolean readWhileListening = new AtomicBoolean(false);
        ls.addObserver(e -> { throw new RuntimeException("the SMS provider is down"); });
        ls.addObserver(e -> heard.add(e.kind()));
        ls.addObserver(e -> {                      // ask the store from ANOTHER thread: it would wait for ever if the lock were held
            if (!e.kind().equals("CONFIRMED")) return;
            FutureTask<Integer> read = new FutureTask<>(() -> ls.getInventory("MUG"));
            new Thread(read).start();
            try { read.get(2, TimeUnit.SECONDS); readWhileListening.set(true); } catch (Exception ex) { readWhileListening.set(false); }
        });
        Order lso = ls.createOrder("asha", "a", Map.of("MUG", 1), null);
        check(ls.confirmOrder(lso.id) == PayResult.CONFIRMED, "a throwing listener did not stop the order");
        check(heard.equals(List.of("CREATED", "CONFIRMED")), "the next listener heard both events, in order");
        check(readWhileListening.get(), "another thread read the stock while the listeners ran: the lock was free");
        List<Long> seqs = new CopyOnWriteArrayList<>();
        Store numbered = store(new long[] { Main.at(10, 0) }, new FakeGateway());
        numbered.addObserver(e -> seqs.add(e.seq()));
        Order no = numbered.createOrder("asha", "a", Map.of("MUG", 1), null);
        numbered.confirmOrder(no.id);
        numbered.cancelOrder(no.id);
        check(seqs.size() == 3 && seqs.get(0) < seqs.get(1) && seqs.get(1) < seqs.get(2), "events are numbered under the lock, in the order they happened");
        List<String> texted = new ArrayList<>();
        LatestOnly sms = new LatestOnly(e -> texted.add(e.kind()));
        sms.onEvent(new StoreEvent("CANCELLED", "O9", "asha", List.of(), 0, 7));   // the newer event arrives first
        sms.onEvent(new StoreEvent("CONFIRMED", "O9", "asha", List.of(), 0, 6));
        check(texted.equals(List.of("CANCELLED")), "an older event that arrives late is dropped: she is never told 'confirmed' after 'cancelled'");

        // 11. the bank times out
        System.out.println("11. the bank times out: unknown, still pending; a retry charges once; no retry means a refund");
        long[] t11 = { Main.at(10, 0) };
        FakeGateway bank11 = new FakeGateway();
        Set<String> timedOutOnce = ConcurrentHashMap.newKeySet();
        Store to = store(t11, new PaymentGateway() {
            public boolean charge(String id, long paise) {
                bank11.charge(id, paise);                                  // the money moves...
                if (timedOutOnce.add(id)) throw new RuntimeException("gateway timeout");   // ...but the first reply is lost
                return true;
            }
            public void refund(String id) { bank11.refund(id); }
        });
        Order u1 = to.createOrder("asha", "a", Map.of("MUG", 1), null);
        check(to.confirmOrder(u1.id) == PayResult.UNKNOWN && u1.status() == OrderStatus.PENDING_PAYMENT, "first reply lost: UNKNOWN, still pending");
        check(to.confirmOrder(u1.id) == PayResult.CONFIRMED && bank11.charges.get() == 1, "the retry confirms, and the money moved once");
        Order u2 = to.createOrder("ravi", "r", Map.of("MUG", 1), null);
        check(to.confirmOrder(u2.id) == PayResult.UNKNOWN && bank11.holds(u2.id), "Ravi's reply is lost too; the bank does hold his money");
        t11[0] = Main.at(10, 5);
        to.getInventory("MUG");                                            // any call sweeps
        check(u2.status() == OrderStatus.EXPIRED && !bank11.holds(u2.id), "nobody retried: when his hold ended, the store refunded by order id");
        check(to.stockOf("MUG").equals(new StockView(4, 0, 1)), "one mug sold (Asha's), Ravi's back on sale");

        // 12. a refund that fails is kept
        System.out.println("12. a refund call that fails is kept for a retry, never forgotten");
        FakeGateway bank12 = new FakeGateway();
        Store rf = store(new long[] { Main.at(10, 0) }, new PaymentGateway() {
            public boolean charge(String id, long paise) { return bank12.charge(id, paise); }
            public void refund(String id) { throw new RuntimeException("the bank is down"); }
        });
        Order ro = rf.createOrder("asha", "a", Map.of("MUG", 1), null);
        rf.confirmOrder(ro.id);
        check(rf.cancelOrder(ro.id) == OrderStatus.CANCELLED && rf.getInventory("MUG") == 5, "the cancel still happens: the mug is back on sale");
        check(rf.refundsToRetry().equals(List.of(ro.id)), "and the order id waits on the retry list");

        // 13. money and units add up, after a random mix on eight threads
        System.out.println("13. a random mix on eight threads: every unit is in one bucket, and the money matches the orders");
        AtomicLong clock = new AtomicLong(Main.at(10, 0));
        FakeGateway bank13 = new FakeGateway();
        Store mix = Main.stocked();
        mix.configure(new ListPrice(), bank13, Store.HOLD_MS);
        mix.setClock(clock::get);
        Map<String, Integer> received = new ConcurrentHashMap<>(Map.of("PEN", 10, "MUG", 5, "KURTI", 3));
        String[] skus = { "PEN", "MUG", "KURTI" };
        race(8, k -> {
            Random rnd = new Random(k);
            for (int i = 0; i < 400; i++) {
                clock.addAndGet(700);                                      // time moves, so some holds end mid-run
                String user = "t" + k + "u" + (i % 7);
                try {
                    Map<String, Integer> want = new HashMap<>();
                    want.put(skus[rnd.nextInt(3)], 1 + rnd.nextInt(2));
                    if (rnd.nextBoolean()) want.put(skus[rnd.nextInt(3)], 1);
                    Order o = mix.createOrder(user, "k" + i, want, null);
                    int roll = rnd.nextInt(10);
                    if (roll < 6) mix.confirmOrder(o.id);
                    if (roll == 6) mix.cancelOrder(o.id);
                    if (roll == 7) { mix.confirmOrder(o.id); mix.cancelOrder(o.id); }
                    if (roll == 8 && mix.confirmOrder(o.id) == PayResult.CONFIRMED) mix.fulfilOrder(o.id);
                } catch (OrderRefused e) { /* out of stock is a normal answer */ }
                if (rnd.nextInt(20) == 0) { String s = skus[rnd.nextInt(3)]; mix.updateInventory(s, 2); received.merge(s, 2, Integer::sum); }
            }
        });
        clock.addAndGet(Store.HOLD_MS);
        mix.sweepExpired();
        long owed = 0;
        Map<String, Integer> soldBy = new HashMap<>();
        for (int k = 0; k < 8; k++)
            for (int u = 0; u < 7; u++)
                for (Order o : mix.orderHistory("t" + k + "u" + u))
                    if (o.status() == OrderStatus.CONFIRMED || o.status() == OrderStatus.FULFILLED) {
                        owed += o.totalPaise();
                        for (Line l : o.lines) soldBy.merge(l.sku(), l.qty(), Integer::sum);
                    }
        boolean units = true, sold = true;
        for (String s : skus) {
            StockView v = mix.stockOf(s);
            units &= v.available() + v.reserved() + v.sold() == received.get(s) && v.reserved() == 0 && v.available() >= 0;
            sold &= v.sold() == soldBy.getOrDefault(s, 0);
        }
        check(units, "for every SKU: available + reserved + sold = units received, and nothing is left reserved");
        check(sold, "sold units = the units of confirmed and delivered orders");
        check(bank13.heldPaise() == owed, "the bank holds exactly the totals of confirmed and delivered orders (" + Main.rs(owed) + ")");

        // 14. the cart blocks nothing; the seller cannot take back promised units
        System.out.println("14. the cart blocks nothing; checkout decides; a seller cannot take back blocked units");
        Store cs = store(new long[] { Main.at(10, 0) }, new FakeGateway());
        cs.addToCart("asha", "KURTI", 3);
        cs.addToCart("ravi", "KURTI", 3);
        check(cs.getInventory("KURTI") == 3, "two carts hold all three kurtis, and nothing is blocked");
        check(cs.cartTotal("asha", "SAVE10").totalPaise() == 1397_00, "the cart total with SAVE10: Rs 1497 less the Rs 100 cap");
        Order ac = cs.checkout("asha", "a", "SAVE10");
        check(ac.totalPaise() == 1397_00, "checkout charges what the cart showed");
        try { cs.checkout("ravi", "r", null); check(false, "the kurtis were sold twice"); }
        catch (OrderRefused e) { check(e.reason == Reason.OUT_OF_STOCK, "checkout decides: Ravi is told OUT_OF_STOCK"); }
        check(cs.viewCart("asha").isEmpty() && cs.viewCart("ravi").equals(Map.of("KURTI", 3)), "Asha's cart is empty; Ravi's refusal left his cart as it was");
        try { cs.addToCart("zoya", "KURTI", 1); check(false, "a kurti went into a cart with none available"); }
        catch (OrderRefused e) { check(e.reason == Reason.OUT_OF_STOCK, "adding what is not available is refused, as advice"); }
        try { cs.updateInventory("KURTI", -1); check(false, "a blocked kurti was taken back"); }
        catch (IllegalStateException e) { check(cs.stockOf("KURTI").equals(new StockView(0, 3, 0)), "the seller cannot take back units a buyer has blocked"); }
        check(cs.updateInventory("PEN", -4) == 6, "but can take back pens nobody has blocked");
        try { new Stock(5).reserve(-1); check(false, "a negative reserve was accepted"); }
        catch (IllegalStateException e) { check(true, "Stock refuses a move of -1 units instead of growing"); }
        cs.addToCart("zoya", "PEN", 3);
        try { cs.addToCart("zoya", "PEN", Integer.MAX_VALUE); check(false, "a cart overflowed"); }
        catch (OrderRefused e) { check(e.reason == Reason.OUT_OF_STOCK && cs.viewCart("zoya").equals(Map.of("PEN", 3)), "3 + a huge quantity cannot overflow the cart's check"); }

        // 15. the follow-ups keep their own promises
        System.out.println("15. the follow-ups keep their promises");
        StripedStock striped = new StripedStock();
        striped.add("PEN", 1_000); striped.add("MUG", 1_000);
        AtomicInteger rounds = new AtomicInteger();
        race(2, k -> {
            List<Line> order = k == 0 ? List.of(new Line("PEN", 1, 0), new Line("MUG", 1, 0)) : List.of(new Line("MUG", 1, 0), new Line("PEN", 1, 0));
            for (int i = 0; i < 20_000; i++) { if (striped.reserveAll(order)) striped.releaseAll(order); rounds.incrementAndGet(); }
        });
        check(rounds.get() == 40_000 && striped.view("PEN").equals(new StockView(1_000, 0, 0)),
              "per-SKU locks: {PEN, MUG} and {MUG, PEN} 20,000 times each, no deadlock, nothing lost");
        StripedStock ten = new StripedStock();
        ten.add("PEN", 10);
        AtomicInteger stripedWins = new AtomicInteger();
        race(100, k -> { if (ten.reserveAll(List.of(new Line("PEN", 1, 0)))) stripedWins.incrementAndGet(); });
        check(stripedWins.get() == 10 && ten.available("PEN") == 0, "per-SKU locks: a hundred buyers, ten pens, ten wins");
        StripedStock one = new StripedStock();
        one.add("PEN", 1);
        check(!one.reserveAll(List.of(new Line("PEN", 1, 0), new Line("PEN", 1, 0))) && one.available("PEN") == 1,
              "the same SKU on two lines is checked in total: one pen cannot fill 1 + 1");

        StockTable table = new StockTable();
        table.insert("PEN", 10); table.insert("MUG", 1);
        AtomicInteger rows = new AtomicInteger();
        race(50, k -> { if (table.reserveRow("PEN", 1)) rows.incrementAndGet(); });
        check(rows.get() == 10 && table.available("PEN") == 0 && table.reserved("PEN") == 10, "conditional UPDATE: fifty callers, ten rows updated");
        table.insert("PEN", 10);
        check(!table.reserveAll(Map.of("PEN", 2, "MUG", 2)) && table.available("PEN") == 10, "a short line rolls the earlier lines back");

        SoldOutGate gate = new SoldOutGate("PEN", 10);
        AtomicInteger entered = new AtomicInteger();
        race(200, k -> { if (gate.tryEnter()) entered.incrementAndGet(); });
        gate.onEvent(new StoreEvent("EXPIRED", "O1", "u", List.of(new Line("PEN", 1, 20_00)), 20_00, 1));
        check(entered.get() == 10 && gate.left() == 1, "the sold-out gate lets exactly ten in, and an expired order hands one ticket back");

        List<Line> pens = List.of(new Line("PEN", 6, 20_00));
        check(new BuyXGetY(new ListPrice(), "PEN", 2, 1).price(pens).totalPaise() == 80_00, "buy 2 get 1: six pens cost four");
        PricingRule twice = new BestOf(List.of(new PercentOff(new ListPrice(), "P20", 20, 1_000_00), new PercentOff(new ListPrice(), "P20", 20, 1_000_00)));
        check(twice.price(pens).totalPaise() == 96_00, "the same code applied twice does not stack: 20% once");

        SiteStock sites = new SiteStock();
        sites.addSite(new Site("BLR-1", Set.of("560034"), 1), Map.of("PEN", 2));
        sites.addSite(new Site("BLR-2", Set.of("560034"), 2), Map.of("PEN", 5, "MUG", 1));
        AllocationRule rule = new OneSiteElseSplit();
        check(sites.reserve(Map.of("PEN", 1, "MUG", 1), "560034", rule).plan().equals(Map.of("BLR-2", Map.of("MUG", 1, "PEN", 1))),
              "one parcel from the one site that has everything");
        check(sites.reserve(Map.of("PEN", 5), "560034", rule).plan().equals(Map.of("BLR-1", Map.of("PEN", 2), "BLR-2", Map.of("PEN", 3))),
              "no site has five pens: split, nearest first");
        check("insufficient product inventory".equals(sites.reserve(Map.of("PEN", 2), "560034", rule).refusal())
              && "pincode unserviceable".equals(sites.reserve(Map.of("PEN", 1), "110001", rule).refusal()), "short, and unserviceable, are refused by name");

        FakeSeller seller = new FakeSeller(Map.of("SAREE", 2));
        ExternalSellerStock external = new ExternalSellerStock(seller);
        seller.timeoutAfterBlockOnce = true;
        check(!external.reserve("O7", Map.of("SAREE", 1)) && seller.available("SAREE") == 2, "the seller blocked, then timed out: we release by order id");
        check(external.reserve("O8", Map.of("SAREE", 2)) && external.reserve("O8", Map.of("SAREE", 2)) && seller.available("SAREE") == 0,
              "a retried reserve with the same order id blocks once");

        long[] tb = { Main.at(10, 0) };
        Store bs = store(tb, new FakeGateway());
        Order lastKurtis = bs.createOrder("ravi", "r", Map.of("KURTI", 3), null);
        BackInStockAlerts alerts = new BackInStockAlerts(bs);
        bs.addObserver(alerts);
        alerts.watch("meera", "KURTI");
        tb[0] = Main.at(10, 5);
        bs.getInventory("KURTI");
        bs.updateInventory("KURTI", 1);
        check(lastKurtis.status() == OrderStatus.EXPIRED && alerts.sent.equals(List.of("meera: KURTI is back")), "back in stock: told once, not again on the restock");

        Store shop = Main.stocked();
        LossyLink link = new LossyLink(shop, 2);
        List<Long> waits = new ArrayList<>();
        Order viaRetry = new RetryingClient(waits::add, new Random(1), 4, 100, 2_000)
                .call(() -> link.createOrder("asha", "tap-9", Map.of("MUG", 2), null));
        check(shop.orderHistory("asha").size() == 1 && shop.stockOf("MUG").reserved() == 2 && waits.size() == 2 && viaRetry != null,
              "two lost replies, three calls, one order, two mugs blocked");
        AtomicInteger calls = new AtomicInteger();
        try {
            new RetryingClient(waits::add, new Random(1), 4, 100, 2_000).call(() -> { calls.incrementAndGet(); return shop.createOrder("ravi", "x", Map.of("KURTI", 9), null); });
            check(false, "nine kurtis were ordered");
        } catch (OrderRefused e) { check(calls.get() == 1, "a refusal is not retried: out of stock will not fix itself"); }

        Coupon parsed = CouponFactory.fromConfig("SAVE10|PERCENT|10|10000|1|1000");
        check(parsed.code().equals("SAVE10") && parsed.discount().apply(new ListPrice()).price(List.of(new Line("KURTI", 1, 499_00))).totalPaise() == 449_10,
              "a coupon built from a config line prices like the hand-written one");

        Platform platform = new Platform();
        platform.store("acme").addProduct("PEN", "Blue pen", 20_00, 1);
        platform.store("zeta").addProduct("PEN", "Red pen", 25_00, 5);
        platform.store("acme").createOrder("u", "k", Map.of("PEN", 1), null);
        check(platform.store("acme").getInventory("PEN") == 0 && platform.store("zeta").getInventory("PEN") == 5, "two stores on one platform share nothing");

        long[] ts = { Main.at(10, 0) };
        Store quiet = store(ts, new FakeGateway());
        quiet.createOrder("ravi", "r", Map.of("KURTI", 1), null);
        ts[0] = Main.at(10, 5);
        try (HoldSweeper sweeper = new HoldSweeper(quiet, 10)) {
            for (int i = 0; i < 300 && sweeper.ended.get() == 0; i++) Thread.sleep(10);
            check(sweeper.ended.get() == 1, "the background job ended the hold with no buyer calling");
        }

        System.out.println(failed == 0 ? "ALL PASS" : failed + " FAILED");
        if (failed > 0) System.exit(1);
    }
}
