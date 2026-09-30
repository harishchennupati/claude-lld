import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.time.*;

/**
 * One test per claim the design makes. Each one is the bug that happens if the claim is dropped, so a
 * regression shows up as a FAIL line rather than as a customer with two tickets for seat B4.
 */
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /**
     * A gateway that keeps the idempotency contract and counts what it did, so a test can assert "charged
     * exactly once": charges counts money actually taken, refunds counts references actually given back.
     */
    static class CountingGateway implements PaymentProcessor {
        final AtomicInteger charges = new AtomicInteger(), refunds = new AtomicInteger();
        private final Map<String, String> byKey = new ConcurrentHashMap<>();
        private final Set<String> refunded = ConcurrentHashMap.newKeySet();
        private final boolean approve;
        CountingGateway(boolean approve) { this.approve = approve; }
        public String charge(String key, long paise) {
            if (!approve) return null;
            return byKey.computeIfAbsent(key, k -> "REF-" + charges.incrementAndGet());   // one charge per key
        }
        public void refund(String ref, long paise) { if (refunded.add(ref)) refunds.incrementAndGet(); }
        /** What the gateway did under a key: its answer to "did that charge happen?" */
        String refFor(String key) { return byKey.get(key); }
    }

    static long[] now = { Instant.parse("2026-09-15T12:00:00Z").toEpochMilli() };
    static final long HOLD = 5 * 60_000L;
    static Screen screen() {
        List<Seat> seats = new ArrayList<>();
        for (int i = 1; i <= 6; i++) seats.add(new Seat("B", i, SeatClass.GOLD));
        for (int i = 1; i <= 2; i++) seats.add(new Seat("C", i, SeatClass.PLATINUM));
        return new Screen("T-1", seats);
    }

    public static void main(String[] args) throws Exception {
        Clock clock = () -> now[0];
        Screen sc = screen();
        Show six  = new Show("SIX",  "Interstellar", sc, Instant.parse("2026-09-15T18:00:00Z").toEpochMilli(), clock, HOLD);
        Show nine = new Show("NINE", "Interstellar", sc, Instant.parse("2026-09-15T21:00:00Z").toEpochMilli(), clock, HOLD);
        BookingService svc = new BookingService();
        svc.configure(new ClassPricing(), new AdjacentSeats());
        svc.addShow(six); svc.addShow(nine);

        // 1. fifty phones, one seat, one latch: exactly one hold
        ExecutorService pool = Executors.newFixedThreadPool(50);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Booking>> tries = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            String u = "fan-" + i;
            tries.add(pool.submit(() -> { go.await(); return svc.hold("SIX", u, List.of("C1")); }));
        }
        go.countDown();
        int wins = 0;
        for (Future<Booking> f : tries) { try { f.get(); wins++; } catch (ExecutionException e) { /* SeatUnavailable */ } }
        pool.shutdown();
        check(wins == 1, "fifty threads on one seat: exactly one hold (" + wins + ")");
        check(six.statusOf("C1") == SeatStatus.HELD, "the seat is HELD, not sold and not free");
        check(six.freeCount(SeatClass.PLATINUM) == 1, "one platinum seat left of two");

        // 2. the card is declined: nothing is released, the seat comes back only when the hold lapses
        Booking b2 = svc.hold("SIX", "raj", List.of("B1"));
        CountingGateway no = new CountingGateway(false);
        try { svc.confirm(b2.id, no); check(false, "a declined card must throw"); }
        catch (PaymentDeclined e) { check(true, "a declined card throws: " + e.getMessage()); }
        check(six.statusOf("B1") == SeatStatus.HELD && b2.status == BookingStatus.PENDING,
              "after the decline the seat is still HELD and the booking still PENDING");
        check(no.refunds.get() == 0, "nothing was refunded: nothing was taken");
        now[0] += HOLD - 1;
        check(six.statusOf("B1") == SeatStatus.HELD, "one millisecond before five minutes the hold is still alive");
        now[0] += 1;
        check(six.statusOf("B1") == SeatStatus.AVAILABLE, "at exactly five minutes the hold is dead and the seat reads free, with no sweeper");
        Booking b2b = svc.hold("SIX", "sara", List.of("B1"));
        check(b2b.status == BookingStatus.PENDING && b2.status == BookingStatus.EXPIRED,
              "the next user gets it; the dead booking is EXPIRED");
        svc.release(b2b.id);

        // 3. the gateway is slower than the hold: confirm is refused and the money is given back
        Booking b3 = svc.hold("SIX", "asha", List.of("B2"));
        CountingGateway slow = new CountingGateway(true) {
            public String charge(String key, long paise) { now[0] += HOLD + 1; return super.charge(key, paise); }   // the round trip outlived the hold
        };
        try { svc.confirm(b3.id, slow); check(false, "confirm after the hold expired must throw"); }
        catch (HoldLapsed e) { check(true, "confirm after expiry is refused: " + e.getMessage()); }
        check(slow.charges.get() == 1 && slow.refunds.get() == 1, "the card was charged once and refunded once");
        check(six.statusOf("B2") == SeatStatus.AVAILABLE && b3.status == BookingStatus.EXPIRED,
              "the seat is on sale again and the booking is EXPIRED, not SOLD");

        // 4. a second confirm sells nothing twice and charges nothing twice
        Booking b4 = svc.hold("SIX", "meena", List.of("B3"));
        CountingGateway once = new CountingGateway(true);
        svc.confirm(b4.id, once);
        check(six.statusOf("B3") == SeatStatus.SOLD && b4.status == BookingStatus.CONFIRMED,
              "the first confirm sells the seat");
        try { svc.confirm(b4.id, once); check(false, "a second confirm must be refused"); }
        catch (IllegalStateException e) { check(true, "a second confirm is refused: " + e.getMessage()); }
        check(once.charges.get() == 1, "the card was charged exactly once");
        check(six.freeCount(SeatClass.GOLD) == 5, "one gold seat sold, five free");

        // 5. cancelling a confirmed booking gives the seat back and refunds once
        svc.cancel(b4.id, once);
        check(six.statusOf("B3") == SeatStatus.AVAILABLE && b4.status == BookingStatus.CANCELLED,
              "cancel returns the seat to AVAILABLE");
        check(once.refunds.get() == 1 && six.freeCount(SeatClass.GOLD) == 6, "refunded once and the count is back to six");

        // 6. a listener that throws must not break the booking
        svc.addObserver((event, b) -> { throw new RuntimeException("sms gateway is down"); });
        Analytics analytics = new Analytics();
        svc.addObserver(analytics);
        Booking b6 = svc.hold("SIX", "vikram", List.of("B4"));
        svc.confirm(b6.id, new CountingGateway(true));
        check(b6.status == BookingStatus.CONFIRMED && six.statusOf("B4") == SeatStatus.SOLD,
              "the booking confirms although the first listener threw");
        check(analytics.counts.getOrDefault("CONFIRMED", 0) == 1, "the listener after the broken one still heard it");

        // 7. three seats together, when no three are together: nothing is held
        Booking b7 = svc.hold("NINE", "x", List.of("B2", "B5"));          // gold left free: B1, B3, B4, B6 -- B3+B4 is a run of two
        svc.confirm(b7.id, new CountingGateway(true));
        int freeBefore = nine.freeCount(SeatClass.GOLD);
        try { svc.holdBest("NINE", "family", SeatClass.GOLD, 3); check(false, "an impossible adjacent request must throw"); }
        catch (SeatUnavailable e) { check(true, "no run of three: " + e.getMessage()); }
        check(nine.freeCount(SeatClass.GOLD) == freeBefore, "the failed request held nothing (" + freeBefore + " still free)");
        for (String id : List.of("B1", "B3", "B4", "B6")) check(nine.statusOf(id) == SeatStatus.AVAILABLE, "seat " + id + " untouched by the failed request");
        Booking b7b = svc.holdBest("NINE", "couple", SeatClass.GOLD, 2);
        check(b7b.seatIds().equals(List.of("B3", "B4")), "a run of two is found and taken together: " + b7b.seatIds());

        // 8. the headline: a chair sold at 6pm is still free at 9pm
        svc.release(b7b.id);
        check(six.statusOf("B4") == SeatStatus.SOLD && nine.statusOf("B4") == SeatStatus.AVAILABLE,
              "the same chair is SOLD at 6pm and AVAILABLE at 9pm");

        // 9. a cap per user: one script asking for the whole house gets exactly its quota, and gets it back
        Show capShow = new Show("CAP", "Interstellar", sc, Instant.parse("2026-09-15T15:00:00Z").toEpochMilli(), clock, HOLD);
        svc.addShow(capShow);
        SeatCap cap = new SeatCap(3, clock);
        ExecutorService botPool = Executors.newFixedThreadPool(8);
        CountDownLatch botGo = new CountDownLatch(1);
        List<Future<Booking>> botTries = new ArrayList<>();
        for (String sid : List.of("B1", "B2", "B3", "B4", "B5", "B6", "C1", "C2"))
            botTries.add(botPool.submit(() -> { botGo.await(); return cap.hold(svc, "CAP", "bot", List.of(sid)); }));
        botGo.countDown();
        int botWins = 0;
        for (Future<Booking> f : botTries) { try { f.get(); botWins++; } catch (ExecutionException e) { /* at the limit */ } }
        botPool.shutdown();
        check(botWins == 3, "eight threads for one user with a cap of three: exactly three holds (" + botWins + ")");
        check(cap.used("CAP", "bot") == 3, "the quota counter agrees with the seats actually held");
        now[0] += HOLD + 1;                                              // the script walks away; its holds lapse
        boolean again;
        try { cap.hold(svc, "CAP", "bot", List.of("B1")); again = true; } catch (SeatUnavailable e) { again = false; }
        check(again && cap.used("CAP", "bot") == 1, "when its holds lapse, the quota comes back by itself");

        // 10. the gateway times out: nothing confirmed, nothing released, then settled from the gateway
        Booking b10 = svc.hold("NINE", "nikhil", List.of("C1"));
        CountingGateway timingOut = new CountingGateway(true) {
            public String charge(String key, long paise) { super.charge(key, paise); throw new PaymentUnknown("read timeout after 30 s"); }
        };
        ReconcilingConfirm rec = new ReconcilingConfirm(svc, timingOut::refFor);
        check(rec.confirm(b10.id, timingOut) == null, "a timeout confirms nothing and throws nothing at the caller");
        check(b10.status == BookingStatus.PENDING && nine.statusOf("C1") == SeatStatus.HELD,
              "after the timeout the booking is still PENDING and the seat still HELD");
        check(timingOut.refunds.get() == 0, "nothing was refunded while the outcome was unknown");
        check(rec.settle(b10.id, timingOut) != null && b10.status == BookingStatus.CONFIRMED,
              "settle asks the gateway by the booking id, finds the charge and finishes the booking");
        check(timingOut.charges.get() == 1 && nine.statusOf("C1") == SeatStatus.SOLD, "the card was charged exactly once");

        // the same timeout, but the hold dies before anybody settles: the money comes back, the seat goes on sale
        Booking b10b = svc.hold("NINE", "ira", List.of("C2"));
        CountingGateway timingOut2 = new CountingGateway(true) {
            public String charge(String key, long paise) { super.charge(key, paise); throw new PaymentUnknown("read timeout after 30 s"); }
        };
        ReconcilingConfirm rec2 = new ReconcilingConfirm(svc, timingOut2::refFor);
        rec2.confirm(b10b.id, timingOut2);
        now[0] += HOLD + 1;                                              // nobody settled in time
        check(rec2.settle(b10b.id, timingOut2) == null, "settling after the hold died confirms nothing");
        check(timingOut2.refunds.get() == 1 && nine.statusOf("C2") == SeatStatus.AVAILABLE && b10b.status == BookingStatus.EXPIRED,
              "the money is refunded, the seat is back on sale and the booking is EXPIRED");

        // 11. cancelling: the seat always comes back, the money follows the refund policy
        CountingGateway desk = new CountingGateway(true);
        CancelWithRefund cancelDesk = new CancelWithRefund(svc, new TieredRefund(), clock);
        Booking full = svc.hold("SIX", "ganesh", List.of("B5"));
        svc.confirm(full.id, desk);
        now[0] = six.startMs - 180 * 60_000L;                            // three hours before the show
        check(cancelDesk.cancel(full.id, desk) == full.amountPaise, "three hours before the show: all " + full.amountPaise + " paise back");
        Booking half = svc.hold("SIX", "hema", List.of("B6"));
        svc.confirm(half.id, desk);
        now[0] = six.startMs - 45 * 60_000L;                             // forty-five minutes before
        check(cancelDesk.cancel(half.id, desk) == half.amountPaise / 2, "forty-five minutes before: half the money back");
        Booking late = svc.hold("SIX", "ivan", List.of("B1"));
        svc.confirm(late.id, desk);
        now[0] = six.startMs + 10 * 60_000L;                             // ten minutes after it started
        check(cancelDesk.cancel(late.id, desk) == 0, "after the show started: no money back");
        check(six.statusOf("B1") == SeatStatus.AVAILABLE && late.status == BookingStatus.CANCELLED,
              "the seat still goes back on sale even when the refund is nothing");
        check(desk.refunds.get() == 2, "two of the three cancels sent money, and each sent it once");

        // 12. the booking id is the idempotency key: a retry after a timeout, or two taps at once, is charged once
        Show pay = new Show("PAY", "Interstellar", sc, Instant.parse("2026-09-16T18:00:00Z").toEpochMilli(), clock, HOLD);
        svc.addShow(pay);
        Booking t1 = svc.hold("PAY", "tara", List.of("B1"));
        CountingGateway flaky = new CountingGateway(true) {
            boolean first = true;
            public String charge(String key, long paise) {
                String r = super.charge(key, paise);
                if (first) { first = false; throw new PaymentUnknown("timeout after the money moved"); }
                return r;
            }
        };
        try { svc.confirm(t1.id, flaky); } catch (PaymentUnknown e) { /* the app says "something went wrong"; the user taps Pay again */ }
        svc.confirm(t1.id, flaky);
        check(t1.status == BookingStatus.CONFIRMED && flaky.charges.get() == 1 && flaky.refunds.get() == 0,
              "a timeout, then Pay again: charged once, not twice (" + flaky.charges.get() + ")");
        Booking t2 = svc.hold("PAY", "uma", List.of("B2"));
        CyclicBarrier bothIn = new CyclicBarrier(2);
        CountingGateway meeting = new CountingGateway(true) {
            public String charge(String key, long paise) {
                try { bothIn.await(2, TimeUnit.SECONDS); } catch (Exception e) { throw new IllegalStateException(e); }   // both taps inside at once
                return super.charge(key, paise);
            }
        };
        ExecutorService taps = Executors.newFixedThreadPool(2);
        Future<Booking> tapA = taps.submit(() -> svc.confirm(t2.id, meeting));
        Future<Booking> tapB = taps.submit(() -> svc.confirm(t2.id, meeting));
        try { tapA.get(); tapB.get(); } catch (ExecutionException e) { check(false, "a tap failed: " + e.getCause()); }
        taps.shutdown();
        check(t2.status == BookingStatus.CONFIRMED && meeting.charges.get() == 1 && meeting.refunds.get() == 0,
              "two taps on Pay at the same instant: one charge, nothing to refund (" + meeting.charges.get() + " charges)");

        // 13. the webhook reports one payment three times: the seats are sold once and nothing is refunded
        Booking w = svc.hold("PAY", "wen", List.of("B3"));
        CountingGateway gw = new CountingGateway(true);
        String paid = gw.charge(w.id, w.amountPaise);                   // the user paid on the gateway's page
        PaymentWebhook hook = new PaymentWebhook(svc);
        for (int i = 0; i < 3; i++) hook.onPaymentCaptured(w.id, paid, gw);
        check(hook.commits.get() == 1 && w.status == BookingStatus.CONFIRMED && gw.refunds.get() == 0,
              "one payment reported three times: sold once, nothing refunded");

        // 14. a late release of a CONFIRMED booking changes nothing and tells nobody it expired
        Analytics heard = new Analytics();
        svc.addObserver(heard);
        Booking r = svc.hold("PAY", "vera", List.of("B4"));
        svc.confirm(r.id, new CountingGateway(true));
        svc.release(r.id);                                               // "the user closed the tab", arriving after the payment
        check(r.status == BookingStatus.CONFIRMED && pay.statusOf("B4") == SeatStatus.SOLD && heard.counts.getOrDefault("EXPIRED", 0) == 0,
              "a late release of a confirmed booking changes nothing and sends no EXPIRED message");

        // 15. edges: an empty request, zero seats, a coupon over 100%, the weekend in the theatre's own time zone
        int goldBefore = pay.freeCount(SeatClass.GOLD);
        try { svc.hold("PAY", "zed", List.of()); check(false, "an empty hold must throw"); }
        catch (IllegalArgumentException e) { check(true, "an empty hold is refused: " + e.getMessage()); }
        try { svc.holdBest("PAY", "zed", SeatClass.GOLD, 0); check(false, "a hold of zero seats must throw"); }
        catch (IllegalArgumentException e) { check(true, "a hold of zero seats is refused: " + e.getMessage()); }
        check(pay.freeCount(SeatClass.GOLD) == goldBefore, "neither left a booking or moved a seat");
        try { new CouponPricing(new ClassPricing(), 150); check(false, "a coupon over 100% must be refused"); }
        catch (IllegalArgumentException e) { check(true, "a coupon over 100% is refused, so no price goes negative"); }
        Show lateFriday = new Show("FRI", "Interstellar", sc, Instant.parse("2026-09-18T19:30:00Z").toEpochMilli(), clock, HOLD);  // Sat 01:00 in Bengaluru
        PricingRule surge = new WeekendSurgePricing(new ClassPricing(), ZoneId.of("Asia/Kolkata"), 150);
        check(surge.pricePaise(lateFriday, sc.seats.get(0)) == 37_500 && surge.pricePaise(six, sc.seats.get(0)) == 25_000,
              "1am Saturday in Bengaluru (still Friday in UTC) pays 1.5x: 37,500 paise; a Tuesday pays 25,000");

        // 16. per-seat compare-and-set takes seats in one fixed order, so opposite-order groups cannot both give up
        List<String> tried = new ArrayList<>();
        CasShow cas = new CasShow();
        for (String id : List.of("C1", "C2")) cas.add(new CasSeat(id) { boolean tryHold(String bk) { tried.add(id); return super.tryHold(bk); } });
        cas.hold(List.of("C2", "C1"), "BK-x");
        check(tried.equals(List.of("C1", "C2")), "a group asking for C2+C1 tries C1 first: " + tried);

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
