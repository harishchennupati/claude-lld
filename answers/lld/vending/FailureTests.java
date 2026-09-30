import java.util.*;
import java.util.concurrent.*;

/**
 * Fourteen claims the design makes, each proven by a few lines. Run it with
 * javac Main.java Extensions.java FailureTests.java && java FailureTests
 * It prints ALL PASS, or the first failure and a non-zero exit code.
 */
public class FailureTests {
    static int failed = 0;

    /** Record one claim. Prints ok or FAIL with the claim's name. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "  ok   " : "  FAIL ") + what);
        if (!ok) failed++;
    }

    /** A machine with one column and a float big enough to make change. */
    static VendingMachine machine(int qty) {
        VendingMachine vm = new VendingMachine();
        vm.addSlot(new Slot("B1", new Product("DMK", "Dairy Milk", 2500), 8, qty));
        vm.loadFloat(Coin.R1, 10);
        vm.loadFloat(Coin.R2, 10);
        vm.loadFloat(Coin.R5, 6);
        vm.loadFloat(Coin.R10, 4);
        return vm;
    }

    public static void main(String[] args) throws Exception {
        // 1. two terminals press for the last unit: exactly one item leaves, and no paise is lost
        System.out.println("1. forty panels, one unit left");
        VendingMachine race = machine(1);
        int floatBefore = race.floatPaise();
        int panels = 40;
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(panels);
        List<Outcome> out = Collections.synchronizedList(new ArrayList<>());
        for (int i = 0; i < panels; i++)
            new Thread(() -> {
                try { go.await(); out.add(race.purchase("B1", List.of(Coin.R20, Coin.R10))); }
                catch (Exception e) { /* counted as no sale */ }
                finally { done.countDown(); }
            }).start();
        go.countDown();
        done.await();
        long sold = out.stream().filter(o -> o.item() != null).count();
        int handedBack = out.stream().filter(o -> o.item() == null).mapToInt(Outcome::paise).sum();
        check(sold == 1, "exactly one panel got the item, " + (panels - 1) + " were refused");
        check(race.qty("B1") == 0, "the column ended at zero, never below");
        check(handedBack == (panels - 1) * 3000, "every refused panel got its whole Rs 30 back");
        check(race.floatPaise() == floatBefore + 2500, "the float grew by exactly one price, Rs 25");

        // 2. the float cannot make change: refuse, refund in full, touch nothing
        System.out.println("2. the float cannot make change");
        VendingMachine lop = new VendingMachine();
        lop.addSlot(new Slot("B1", new Product("DMK", "Dairy Milk", 2500), 8, 3));
        lop.loadFloat(Coin.R10, 1);                                   // Rs 15 change is impossible
        lop.insertCoin(Coin.R20);
        lop.insertCoin(Coin.R20);
        Outcome refused = lop.select("B1");
        check(refused.status() == Status.NO_CHANGE, "the sale is refused, not half done");
        check(Coin.total(refused.coins()) == 4000, "the whole Rs 40 is refunded");
        check(lop.qty("B1") == 3, "stock is exactly what it was");
        check(lop.floatPaise() == 1000, "the float is exactly what it was");
        check(lop.state() == MachineState.IDLE, "the machine is idle again");

        // 3. the coin return hands back exactly the coins that went in
        System.out.println("3. cancel");
        VendingMachine cancel = machine(1);
        cancel.insertCoin(Coin.R10);
        cancel.insertCoin(Coin.R2);
        cancel.insertCoin(Coin.R2);
        List<Coin> back = cancel.cancel();
        check(back.equals(List.of(Coin.R10, Coin.R2, Coin.R2)), "the same three coins, same denominations");
        check(cancel.escrowPaise() == 0, "nothing is left in escrow");
        check(cancel.collect().paise() == 1400, "and the same Rs 14 is in the tray");

        // 4. the motor jams: nothing dispensed, everything refunded, no stock lost
        System.out.println("4. the motor jams");
        VendingMachine jam = machine(3);
        jam.configure(new ListPrice(), new BackoffChange(), code -> false);
        int floatWas = jam.floatPaise();
        jam.insertCoin(Coin.R20);
        jam.insertCoin(Coin.R10);
        Outcome jammed = jam.select("B1");
        check(jammed.status() == Status.JAMMED, "the press reports a jam");
        check(Coin.total(jammed.coins()) == 3000, "the whole Rs 30 is refunded");
        check(jam.qty("B1") == 3, "no unit was taken off the coil");
        check(jam.floatPaise() == floatWas, "the float never moved");

        // 5. restocking, and the pager that fires when a column hits zero
        System.out.println("5. restock and the empty-column alert");
        VendingMachine stock = machine(1);
        RestockAlert pager = new RestockAlert();
        stock.addObserver(pager);
        stock.purchase("B1", List.of(Coin.R20, Coin.R10));
        check(stock.qty("B1") == 0, "the last unit sold");
        check(pager.empty.equals(List.of("B1")), "the pager was told which column is empty");
        check(stock.restock("B1", 5) == 5 && stock.qty("B1") == 5, "restock puts five back");
        check(stock.restock("B1", 100) == 3, "and it never goes past the column's capacity of 8");

        // 6. screens and pagers: told after the unlock, so a broken or slow one cannot hold a sale up
        System.out.println("6. screens and pagers");
        VendingMachine noisy = machine(2);
        noisy.addObserver(e -> { throw new RuntimeException("screen is dead"); });
        Outcome still = noisy.purchase("B1", List.of(Coin.R20, Coin.R10));
        check(still.item() != null, "the item still dropped");
        check(noisy.qty("B1") == 1, "and the stock still moved");
        final boolean[] readable = { false };                         // a screen that asks the machine from its own thread
        noisy.addObserver(e -> {
            FutureTask<Integer> ask = new FutureTask<>(() -> noisy.qty("B1"));
            new Thread(ask).start();
            try { readable[0] = ask.get(1, TimeUnit.SECONDS) == 0; } catch (Exception x) { readable[0] = false; }
        });
        noisy.purchase("B1", List.of(Coin.R20, Coin.R10));
        check(readable[0], "even a one-step purchase tells its screens after the unlock: they can read the machine");
        RestockAlert busyPager = new RestockAlert();                  // after the unlock means in parallel
        java.io.PrintStream screen = System.out;
        System.setOut(new java.io.PrintStream(java.io.OutputStream.nullOutputStream()));
        Thread[] sellers = new Thread[8];
        for (int i = 0; i < sellers.length; i++)
            (sellers[i] = new Thread(() -> { for (int k = 0; k < 20_000; k++) busyPager.onEvent(new MachineEvent("SOLD", "A1", 0, 0)); })).start();
        for (Thread s : sellers) s.join();
        System.setOut(screen);
        check(busyPager.empty.size() == 160_000, "eight sales reporting at once: the pager keeps all 160,000 alerts");

        // 7. an action that the current mode does not allow is refused, loudly
        System.out.println("7. illegal moves");
        VendingMachine strict = machine(2);
        final boolean[] refusedInsert = { false }, refusedSelect = { false };
        strict.configure(new ListPrice(), new BackoffChange(), code -> {     // a coin pushed in mid-drop
            try { strict.insertCoin(Coin.R1); } catch (IllegalStateException e) { refusedInsert[0] = true; }
            try { strict.select("B1"); }       catch (IllegalStateException e) { refusedSelect[0] = true; }
            return true;
        });
        strict.purchase("B1", List.of(Coin.R20, Coin.R10));
        check(refusedInsert[0], "a coin pushed in while the flap is open is refused");
        check(refusedSelect[0], "so is a second press of the button");
        boolean threw = false;
        try { machine(1).select("B1"); } catch (IllegalStateException e) { threw = true; }
        check(threw, "pressing a slot with no money in is refused");
        boolean empty = false;
        try { machine(1).collect(); } catch (IllegalStateException e) { empty = true; }
        check(empty, "taking from an empty tray is refused, not a silent null");

        // 8. the price comes from the injected clock, so happy hour is testable at any hour
        System.out.println("8. time is handed in");
        VendingMachine hh = machine(3);
        long[] now = { at(10, 0) };
        hh.setClock(() -> now[0]);
        hh.configure(new HappyHourDiscount(new ListPrice(), () -> now[0], 16, 18, 20), new BackoffChange(), new Motor());
        check(hh.priceOf("B1") == 2500, "at 10:00 the column costs its list price, Rs 25");
        now[0] = at(16, 30);
        check(hh.priceOf("B1") == 2000, "at 16:30 the same column costs Rs 20");
        hh.insertCoin(Coin.R20);
        Outcome cheap = hh.select("B1");
        check(cheap.status() == Status.SOLD && cheap.paise() == 0, "Rs 20 buys it outright during happy hour");

        // 9. he feeds a coin in and walks away: after thirty seconds the money is his again, not the machine's
        System.out.println("9. money left inside comes back by itself");
        VendingMachine left = machine(3);
        long[] t = { at(12, 0) };
        left.setClock(() -> t[0]);
        left.insertCoin(Coin.R20);
        check(left.escrowPaise() == 2000, "Rs 20 sits in escrow while he is standing there");
        t[0] += 31_000;                                               // thirty-one seconds later, no sleeping
        left.insertCoin(Coin.R1);                                     // the next touch sweeps before it runs
        check(left.escrowPaise() == 100, "the abandoned Rs 20 is out of the escrow");
        check(left.qty("B1") == 3 && left.floatPaise() == 10000, "no stock and no float moved while it sat there");
        check(Coin.total(left.collect().coins()) == 2000, "and all Rs 20 of it is waiting in the tray");
        VendingMachine slow = machine(3);                             // but a customer still feeding coins is not cut off
        slow.setClock(() -> t[0]);
        slow.insertCoin(Coin.R20);
        t[0] += 20_000;
        slow.insertCoin(Coin.R10);                                    // twenty seconds later: this coin restarts the clock
        t[0] += 11_000;                                               // thirty-one seconds after the FIRST coin
        boolean stillHis;
        try { stillHis = slow.select("B1").sold(); } catch (IllegalStateException cutOff) { stillHis = false; }
        check(stillHis, "coins at 0 s and 20 s, a press at 31 s: it sells, because the timer runs from the last touch");

        // 10. two sales and nobody reaches in: the tray keeps both items instead of overwriting the first
        System.out.println("10. the tray keeps what nobody took");
        VendingMachine bin = machine(3);
        bin.insertCoin(Coin.R20); bin.insertCoin(Coin.R10); bin.select("B1");
        bin.insertCoin(Coin.R20); bin.insertCoin(Coin.R10); bin.select("B1");
        Outcome both = bin.collect();
        check(both.items().size() == 2, "two bars are waiting, not one");
        check(Coin.total(both.coins()) == 1000, "with both lots of change, Rs 10 in all");
        check(bin.qty("B1") == 1, "and the column went down by exactly two");

        // 11. a one-step buyer (a phone, a kiosk) never spends the coins of the customer standing at the machine
        System.out.println("11. whose money is in the escrow");
        VendingMachine shared = machine(3);
        shared.insertCoin(Coin.R20);                                  // he is standing there with Rs 20 in
        boolean phoneRefused = false;
        try { shared.purchase("B1", List.of(Coin.R20, Coin.R10)); } catch (IllegalStateException busy) { phoneRefused = true; }
        check(phoneRefused, "a phone purchase is refused while his coins are in");
        check(shared.escrowPaise() == 2000 && shared.qty("B1") == 3, "his Rs 20 is still his, and no unit moved");
        shared.cancel();
        shared.collect();
        check(shared.purchase("B1", List.of(Coin.R20, Coin.R10)).item() != null, "once he has his coins back, the phone buys");

        // 12. a discount still leaves a price that coins can pay
        System.out.println("12. prices stay in whole rupees");
        VendingMachine odd = machine(3);
        odd.setClock(() -> at(16, 30));
        odd.configure(new HappyHourDiscount(new ListPrice(), () -> at(16, 30), 16, 18, 15), new BackoffChange(), new Motor());
        check(odd.priceOf("B1") == 2100, "15% off Rs 25 is Rs 21, not Rs 21.25, which no coin could pay");
        odd.insertCoin(Coin.R20);
        odd.insertCoin(Coin.R5);
        Outcome oddSale = odd.select("B1");
        check(oddSale.sold() && oddSale.paise() == 400, "so Rs 25 buys it, with Rs 4 change");

        // 13. the operator cannot push a count below zero, and can close a machine somebody walked away from
        System.out.println("13. the operator's inputs");
        VendingMachine op = machine(3);
        boolean stockRefused = false, floatRefused = false;
        try { op.restock("B1", -5); } catch (IllegalArgumentException e) { stockRefused = true; }
        try { op.loadFloat(Coin.R10, -9); } catch (IllegalArgumentException e) { floatRefused = true; }
        check(stockRefused && floatRefused && op.qty("B1") == 3 && op.floatPaise() == 10000,
              "a negative restock or float load is refused, and nothing moves");
        long[] shift = { at(9, 0) };
        op.setClock(() -> shift[0]);
        op.insertCoin(Coin.R10);                                      // somebody puts Rs 10 in and walks off
        shift[0] += 60_000;
        try { op.setService(true); } catch (IllegalStateException e) { /* checked below */ }
        check(op.state() == MachineState.OUT_OF_SERVICE && op.collect().paise() == 1000,
              "a minute later the operator can close it, and the Rs 10 is in the tray");

        // 14. the follow-ups keep their own promises: a hold loses no unit, a card never keeps money for nothing
        System.out.println("14. follow-ups");
        Inventory shelf = new Inventory();
        shelf.addSlot(new Slot("A1", new Product("LAY", "Lays", 2000), 8, 2));
        shelf.addSlot(new Slot("A2", new Product("COK", "Coke", 3500), 8, 1));
        long[] wall = { 0 };
        HoldDesk desk = new HoldDesk(shelf, () -> wall[0], 30_000);
        desk.hold("A2", "ravi");
        desk.hold("A1", "ravi");                                      // he changes his mind
        check(shelf.slot("A2").qty() == 1, "a second hold by the same customer gives the first unit back");
        wall[0] += 31_000;
        desk.hold("A1", "meera");                                     // the next touch sweeps the expired hold
        check(shelf.slot("A1").qty() == 1 && shelf.slot("A2").qty() == 1, "after the expiry no unit is lost");
        Map<String, Integer> bank = new HashMap<>();                  // what each sale id has taken from the customer
        CardTerminal lostReply = new CardTerminal() {
            public boolean charge(String id, int paise) { bank.merge(id, paise, Integer::sum); throw new RuntimeException("timeout"); }
            public boolean refund(String id) { bank.remove(id); return true; }
        };
        Outcome unknown = new CardCheckout(shelf, new Motor(), lostReply).buy("A1", 2000);
        check(!unknown.sold() && bank.isEmpty() && shelf.slot("A1").qty() == 1,
              "the charge went through but the reply timed out: refunded by its sale id, nothing dropped");
        CardTerminal bankDown = new CardTerminal() {
            public boolean charge(String id, int paise) { return true; }
            public boolean refund(String id) { return false; }
        };
        CardCheckout stuck = new CardCheckout(shelf, code -> false, bankDown);
        stuck.buy("A1", 2000);
        check(stuck.refundsToRetry.size() == 1, "a refund that fails is kept for a retry, not forgotten");

        System.out.println(failed == 0 ? "ALL PASS" : failed + " FAILED");
        if (failed > 0) System.exit(1);
    }

    /** A fixed moment on 15 September 2026 in Kolkata, so the tests never depend on when they run. */
    static long at(int hour, int minute) {
        return java.time.LocalDateTime.of(2026, 9, 15, hour, minute)
                 .atZone(java.time.ZoneId.of("Asia/Kolkata")).toInstant().toEpochMilli();
    }
}
