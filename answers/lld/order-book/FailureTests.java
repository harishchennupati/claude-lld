import java.util.*;
import java.util.concurrent.*;

// targeted failure tests: each one proves a claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }
    static MatchingEngine book(String symbol) { return new MatchingEngine(symbol, 5, 1); }   // tick 0.05, lot 1

    public static void main(String[] args) throws Exception {

        // 1. price-time priority: best price first, and inside a price the order that arrived first
        MatchingEngine e1 = book("INFY");
        e1.submit(Order.limit("early", "INFY", "ANA", Side.BUY, Ticks.of("100.00"), 100));
        e1.submit(Order.limit("late",  "INFY", "BEN", Side.BUY, Ticks.of("100.00"), 100));
        e1.submit(Order.limit("better","INFY", "CHE", Side.BUY, Ticks.of("100.05"), 100));
        SubmitResult swept = e1.submit(Order.limit("taker", "INFY", "DEV", Side.SELL, Ticks.of("100.00"), 250));
        check(swept.trades().get(0).buyOrderId().equals("better"), "the better price is taken first, whenever it arrived");
        check(swept.trades().get(1).buyOrderId().equals("early"), "inside one price, the order that arrived first fills first");
        check(swept.trades().get(2).buyOrderId().equals("late") && swept.trades().get(2).qty() == 50,
              "the last 50 lots go to the order behind it, not a lot more");
        check(swept.trades().get(0).priceTicks() == Ticks.of("100.05"),
              "the trade prints at the RESTING price, so the aggressor keeps the price improvement");

        // 2. a partial fill leaves the remainder resting, and it keeps its place in the queue
        MatchingEngine e2 = book("INFY");
        e2.submit(Order.limit("maker", "INFY", "ANA", Side.SELL, Ticks.of("100.00"), 100));
        SubmitResult part = e2.submit(Order.limit("big", "INFY", "BEN", Side.BUY, Ticks.of("100.00"), 300));
        check(part.filledQty() == 100 && part.restingQty() == 200, "a 300-lot buy against 100 resting: 100 filled, 200 rests");
        check(part.status() == OrderStatus.PARTIALLY_FILLED, "and its state is PARTIALLY_FILLED, not FILLED");
        check(e2.resting("big").remaining() == 200 && e2.restingQty(Side.BUY) == 200, "the book agrees: 200 lots bid");
        e2.submit(Order.limit("behind", "INFY", "CHE", Side.BUY, Ticks.of("100.00"), 500));
        SubmitResult next = e2.submit(Order.limit("seller", "INFY", "DEV", Side.SELL, Ticks.of("100.00"), 100));
        check(next.trades().get(0).buyOrderId().equals("big"), "the part-filled order is still in front of the one behind it");

        // 3. a market order sweeps every crossing level, at the makers' prices, and never rests
        MatchingEngine e3 = book("INFY");
        e3.submit(Order.limit("a1", "INFY", "ANA", Side.SELL, Ticks.of("100.00"), 100));
        e3.submit(Order.limit("a2", "INFY", "BEN", Side.SELL, Ticks.of("100.50"), 100));
        SubmitResult mkt = e3.submit(Order.market("m1", "INFY", "CHE", Side.BUY, 500));
        check(mkt.trades().size() == 2, "the market order swept both levels");
        check(mkt.trades().get(0).priceTicks() == Ticks.of("100.00")
              && mkt.trades().get(1).priceTicks() == Ticks.of("100.50"), "it paid each maker's own price, cheapest first");
        check(mkt.status() == OrderStatus.CANCELLED && mkt.restingQty() == 0 && e3.restingQty(Side.BUY) == 0,
              "the 300 lots it could not fill were thrown away: a market order never rests");
        check(e3.submit(Order.market("m2", "INFY", "DEV", Side.BUY, 100)).rejectReason() == null
              && e3.restingQty(Side.BUY) == 0, "a market order into an empty book fills nothing and still rests nothing");

        // 4. fill-or-kill is all or nothing, and a kill leaves the book exactly as it was
        MatchingEngine e4 = book("INFY");
        e4.submit(Order.limit("a1", "INFY", "ANA", Side.SELL, Ticks.of("100.00"), 100));
        e4.submit(Order.limit("a2", "INFY", "BEN", Side.SELL, Ticks.of("100.05"), 100));
        List<Rung> before = e4.depth(Side.SELL, 10);
        SubmitResult killed = e4.submit(Order.limit("fok", "INFY", "CHE", Side.BUY, Ticks.of("100.05"), 500, TimeInForce.FOK));
        check(killed.status() == OrderStatus.CANCELLED && killed.filledQty() == 0, "a fill-or-kill that cannot fill in full fills nothing");
        check(killed.rejectReason().contains("only 200 available"), "and it says why: " + killed.rejectReason());
        check(e4.depth(Side.SELL, 10).equals(before), "the book is untouched, level for level and lot for lot");
        SubmitResult ok = e4.submit(Order.limit("fok2", "INFY", "DEV", Side.BUY, Ticks.of("100.05"), 200, TimeInForce.FOK));
        check(ok.status() == OrderStatus.FILLED && ok.filledQty() == 200, "a fill-or-kill that CAN fill in full does, in one go");

        // 5. IOC takes what is there and cancels the rest
        MatchingEngine e5 = book("INFY");
        e5.submit(Order.limit("a1", "INFY", "ANA", Side.SELL, Ticks.of("100.00"), 120));
        SubmitResult ioc = e5.submit(Order.limit("ioc", "INFY", "BEN", Side.BUY, Ticks.of("100.00"), 500, TimeInForce.IOC));
        check(ioc.filledQty() == 120 && ioc.restingQty() == 0, "IOC took the 120 that were there and kept nothing");
        check(ioc.status() == OrderStatus.CANCELLED && e5.restingQty(Side.BUY) == 0, "the 380 it could not fill are gone, not resting");

        // 6. cancel and amend by id: what leaves the book, and what changes without leaving it
        MatchingEngine e6 = book("INFY");
        e6.submit(Order.limit("c1", "INFY", "ANA", Side.BUY, Ticks.of("100.00"), 100));
        e6.submit(Order.limit("c2", "INFY", "BEN", Side.BUY, Ticks.of("99.95"), 100));
        check(e6.cancel("c1"), "a resting order cancels");
        check(e6.quote().bidTicks() == Ticks.of("99.95"), "the emptied price level was pruned, so the top of book moved");
        check(!e6.cancel("c1"), "cancelling it twice returns false, it does not throw");
        check(!e6.cancel("never-existed"), "cancelling an unknown id returns false too");
        e6.submit(Order.limit("c3", "INFY", "CHE", Side.SELL, Ticks.of("99.95"), 100));
        check(!e6.cancel("c2"), "cancelling an order that has already filled returns false: a cancel racing a fill is ordinary life");
        check(e6.restingQty(Side.BUY) == 0 && e6.restingQty(Side.SELL) == 0, "and the book is empty, with nothing stuck in an index");
        MatchingEngine e6b = book("INFY");
        e6b.submit(Order.limit("front",  "INFY", "ANA", Side.BUY, Ticks.of("100.00"), 500));
        e6b.submit(Order.limit("behind", "INFY", "BEN", Side.BUY, Ticks.of("100.00"), 100));
        check(e6b.amendDown("front", 300), "a resting order can be amended down");
        check(!e6b.amendDown("front", 900), "but not up: raising a quantity is a cancel and a new order, so it says no");
        check(e6b.resting("front").filled() == 0 && e6b.resting("front").qty() == 300,
              "the amend shrank the ORDER: it did not look like a 200-lot fill to risk or to the journal");
        check(e6b.restingQty(Side.BUY) == 400, "and the level total came down with it: 400 lots bid, not 600");
        check(e6b.submit(Order.limit("s6", "INFY", "CHE", Side.SELL, Ticks.of("100.00"), 50))
                 .trades().get(0).buyOrderId().equals("front"), "and it kept its place at the front of the queue");

        // 7. the race: fifty threads crossing at one book. Every lot must be accounted for.
        MatchingEngine e7 = book("TCS");
        ConsoleTape tape = new ConsoleTape();
        e7.addListener(tape);
        List<Order> sent = Collections.synchronizedList(new ArrayList<>());
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> futures = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final int n = i;
            futures.add(pool.submit(() -> {
                go.await();
                Order o = Order.limit("r" + n, "TCS", "M" + (n % 5), n % 2 == 0 ? Side.BUY : Side.SELL,
                                      Ticks.of("3000.00"), n % 2 == 0 ? 100 : 80);
                sent.add(o);
                return e7.submit(o);
            }));
        }
        go.countDown();
        for (Future<?> f : futures) f.get();
        pool.shutdown();
        long bought = 0, sold = 0, sentBuy = 0, sentSell = 0, printed = 0, liveBid = 0, liveAsk = 0;
        boolean sane = true;
        for (Order o : sent) {
            if (o.remaining() < 0 || o.filled() + o.remaining() != o.qty()) sane = false;
            if (o.side() == Side.BUY) { bought += o.filled(); sentBuy += o.qty(); } else { sold += o.filled(); sentSell += o.qty(); }
            if (e7.resting(o.id()) != null) { if (o.side() == Side.BUY) liveBid += o.remaining(); else liveAsk += o.remaining(); }
        }
        for (Trade t : tape.printed()) printed += t.qty();
        check(sent.size() == 50, "all fifty orders were submitted");
        check(sane, "no order ever went negative, and filled + remaining == quantity for every one of them");
        check(bought == sold, "lots bought (" + bought + ") == lots sold (" + sold + "): nothing was invented or lost");
        check(printed == bought, "the tape printed exactly those " + printed + " lots, no more");
        check(sentBuy - bought == e7.restingQty(Side.BUY) && sentSell - sold == e7.restingQty(Side.SELL),
              "on each side: submitted = filled + still resting");
        check(liveBid == e7.restingQty(Side.BUY) && liveAsk == e7.restingQty(Side.SELL),
              "the id index and the price ladders agree: no cached level total drifted");

        // 8. a listener that throws, and an allocator that cheats, cannot corrupt the book
        MatchingEngine e8 = book("INFY");
        e8.addListener(new BookListener() {
            public void onTrade(Trade t) { throw new RuntimeException("the tape socket is down"); }
            public void onQuote(Quote q) { throw new RuntimeException("market data is down too"); }
        });
        e8.submit(Order.limit("m", "INFY", "ANA", Side.SELL, Ticks.of("100.00"), 100));
        SubmitResult through = e8.submit(Order.limit("t", "INFY", "BEN", Side.BUY, Ticks.of("100.00"), 100));
        check(through.status() == OrderStatus.FILLED && through.trades().size() == 1,
              "the trade happened although every listener threw: listeners run after the unlock, in a try/catch");
        MatchingEngine e9 = book("INFY");
        e9.configure((taker, level) -> List.of(new Allocation(level.queue().get(0).id(), 999_999)));  // a rulebook that overfills
        e9.submit(Order.limit("honest", "INFY", "ANA", Side.SELL, Ticks.of("100.00"), 100));
        List<Rung> untouched = e9.depth(Side.SELL, 10);
        try {
            e9.submit(Order.limit("victim", "INFY", "BEN", Side.BUY, Ticks.of("100.00"), 100));
            check(false, "an allocator handing out more than exists must be caught");
        } catch (IllegalStateException ex) { check(true, "CheckedAllocator caught the broken rulebook: " + ex.getMessage()); }
        check(e9.depth(Side.SELL, 10).equals(untouched) && e9.resting("honest").remaining() == 100,
              "and it wrote nothing: the plan is checked before a single lot moves");

        // 9. rejected orders write nothing at all, and time comes from the injected clock
        MatchingEngine e10 = book("INFY");
        e10.submit(Order.limit("rest", "INFY", "ANA", Side.SELL, Ticks.of("100.00"), 100));
        List<Rung> asBefore = e10.depth(Side.SELL, 10);
        check(e10.submit(Order.limit("bad1", "INFY", "BEN", Side.BUY, Ticks.of("100.03"), 10)).status() == OrderStatus.REJECTED,
              "a price off the 0.05 tick is rejected");
        check(e10.submit(Order.limit("bad2", "INFY", "BEN", Side.BUY, Ticks.of("100.00"), 0)).status() == OrderStatus.REJECTED,
              "a zero quantity is rejected");
        check(e10.submit(Order.limit("rest", "INFY", "CHE", Side.BUY, Ticks.of("99.00"), 10)).rejectReason().contains("already used"),
              "a reused order id is rejected, so a retried request cannot double-submit");
        check(e10.depth(Side.SELL, 10).equals(asBefore) && e10.restingQty(Side.BUY) == 0,
              "none of the three rejections touched the book");
        e10.setClock(() -> 1_700_000_000_000L);
        SubmitResult stamped = e10.submit(Order.limit("clocked", "INFY", "DEV", Side.BUY, Ticks.of("100.00"), 100));
        check(stamped.trades().get(0).atMs() == 1_700_000_000_000L, "the trade carries the injected instant, so a test can assert on it");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
