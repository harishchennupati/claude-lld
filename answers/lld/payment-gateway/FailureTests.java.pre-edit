import java.util.*;
import java.util.concurrent.*;

// targeted failure tests: each one proves a claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    static final long[] NOW = { 1_700_000_000_000L };
    static final PaymentMethod CARD = new PaymentMethod(PaymentMethodType.CARD, "tok_visa_1", "**** 1111");
    static final PaymentMethod UPI  = new PaymentMethod(PaymentMethodType.UPI, "a@okhdfc", "a@okhdfc");

    /** A gateway wired to the acquirers it is given, with no risk rules and a fee of zero. */
    static PaymentService gatewayOver(PaymentProcessor... acquirers) {
        PaymentService gw = new PaymentService();
        gw.setClock(() -> NOW[0]);
        List<String> order = new ArrayList<>();
        for (PaymentProcessor p : acquirers) { gw.addProcessor(p); order.add(p.name()); }
        gw.configure(new PreferredRouting(Map.of(PaymentMethodType.CARD, order, PaymentMethodType.UPI, order)),
                     new BpsFee(0), new RetrySafeFailuresOnly(3), List.of());
        gw.register(new Merchant("m1", "Shop", "https://shop.example/hooks"));
        return gw;
    }

    public static void main(String[] args) throws Exception {
        // 1. fifty threads send the SAME idempotency key at the same instant -- the retry storm that makes every
        //    payments post-mortem. Exactly one request may reach the acquirer, and all fifty callers must get back
        //    the very same payment. The putIfAbsent on the key is the whole of it.
        CardAcquirer solo = new CardAcquirer("SOLO", 200, Currency.INR);
        PaymentService busy = gatewayOver(solo);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<String>> sent = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            sent.add(pool.submit(() -> {
                go.await();
                return busy.pay("ord-RACE", "m1", Money.rupees("1000.00"), Currency.INR, CARD).id();
            }));
        }
        go.countDown();
        Set<String> ids = new HashSet<>();
        for (Future<String> f : sent) ids.add(f.get(10, TimeUnit.SECONDS));
        check(ids.size() == 1, "fifty retries of one key produced one payment (" + ids.size() + ")");
        check(solo.calls() == 1, "exactly one request reached the acquirer (" + solo.calls() + ")");
        check(busy.byKey("ord-RACE").state() == PaymentState.AUTHORIZED, "and that one payment is AUTHORIZED");

        // 2. the acquirer takes the money and then the socket dies. The payment must NOT be recorded as a success,
        //    must NOT be retried and must NOT be failed over -- the only honest state is "I do not know".
        CardAcquirer flaky = new CardAcquirer("FLAKY", 200, Currency.INR);
        CardAcquirer spare = new CardAcquirer("SPARE", 200, Currency.INR);
        PaymentService t2 = gatewayOver(flaky, spare);
        flaky.mode(VendorMode.TIMEOUT_CHARGED);
        Payment lost = t2.pay("ord-2", "m1", Money.rupees("700.00"), Currency.INR, CARD);
        check(lost.state() == PaymentState.UNKNOWN, "a timeout leaves the payment UNKNOWN, not FAILED and not captured");
        check(lost.capturedPaise() == 0, "nothing is recorded as captured while the outcome is unknown");
        check(flaky.calls() == 1 && spare.calls() == 0, "one call was made, and a timeout never fails over to the next acquirer");
        t2.pay("ord-2", "m1", Money.rupees("700.00"), Currency.INR, CARD);         // the client retries the HTTP call
        check(flaky.calls() == 1, "a client retry of an unknown payment makes no second call (" + flaky.calls() + ")");
        check(t2.unresolved().contains(lost.id()), "the payment is on the reconciliation job's list");

        // 3. the only honest way out of an UNKNOWN: ask the acquirer about the exact key we sent. It answers in
        //    both directions -- it took the money, or it never saw the request -- and the payment lands accordingly.
        flaky.mode(VendorMode.HEALTHY);                                            // the status API is up again
        NOW[0] += 60_000;
        int settled = t2.reconcile(30_000);
        check(settled == 1 && lost.state() == PaymentState.AUTHORIZED,
              "the status query resolved the unknown payment to " + lost.state());
        check(flaky.calls() == 1, "asking about a charge is not a second charge (" + flaky.calls() + ")");
        check(t2.unresolved().isEmpty(), "and it is off the job's list");

        UpiSwitch gone = new UpiSwitch("GONE", 0);
        PaymentService t3 = gatewayOver(gone);
        gone.mode(VendorMode.TIMEOUT_LOST);
        Payment vanished = t3.pay("ord-3", "m1", Money.rupees("99.00"), Currency.INR, UPI);
        check(vanished.state() == PaymentState.UNKNOWN, "a request that died on the way out is UNKNOWN too");
        gone.mode(VendorMode.HEALTHY);
        NOW[0] += 60_000;
        t3.reconcile(30_000);
        check(vanished.state() == PaymentState.FAILED && vanished.capturedPaise() == 0,
              "the acquirer never saw it, so it settles as FAILED with nothing captured");

        // 4. a refund may never exceed what was actually captured, and a refusal must reserve nothing -- otherwise
        //    the next honest refund is refused for a reservation that was never released.
        CardAcquirer ok4 = new CardAcquirer("OK4", 200, Currency.INR);
        PaymentService t4 = gatewayOver(ok4);
        Payment big = t4.pay("ord-4", "m1", Money.rupees("1000.00"), Currency.INR, CARD);
        t4.capture(big.id());
        Refund tooMuch = t4.refund("rf-a", big.id(), Money.rupees("1200.00"));
        check(tooMuch.state() == RefundState.FAILED, "a refund over the captured amount is refused: " + tooMuch.failureReason());
        check(big.refundedPaise() == 0 && big.refundReservedPaise() == 0, "and it reserved nothing");
        Refund good = t4.refund("rf-b", big.id(), Money.rupees("1000.00"));
        check(good.state() == RefundState.SUCCEEDED && big.state() == PaymentState.REFUNDED,
              "the full amount still refunds afterwards");
        Refund replay = t4.refund("rf-b", big.id(), Money.rupees("1000.00"));
        check(replay == good && big.refundedPaise() == Money.rupees("1000.00"),
              "a retried refund key returns the same refund and moves the money once");
        Payment authOnly = t4.pay("ord-4b", "m1", Money.rupees("500.00"), Currency.INR, CARD);
        check(t4.refund("rf-c", authOnly.id(), 100).state() == RefundState.FAILED,
              "an authorized-but-not-captured payment cannot be refunded");

        // 5. twenty support agents refund a hundred rupees each, at the same instant, against a thousand-rupee
        //    capture. Exactly ten may win. A single counter written AFTER the acquirer call would let more through,
        //    because they would all have been decided from the same read; reserve-then-settle is why they cannot.
        CardAcquirer ok5 = new CardAcquirer("OK5", 200, Currency.INR);
        PaymentService t5 = gatewayOver(ok5);
        Payment pot = t5.pay("ord-5", "m1", Money.rupees("1000.00"), Currency.INR, CARD);
        t5.capture(pot.id());
        CountDownLatch go5 = new CountDownLatch(1);
        List<Future<RefundState>> tries = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            final int n = i;
            tries.add(pool.submit(() -> {
                go5.await();
                return t5.refund("rf5-" + n, pot.id(), Money.rupees("100.00")).state();
            }));
        }
        go5.countDown();
        int won = 0;
        for (Future<RefundState> f : tries) if (f.get(10, TimeUnit.SECONDS) == RefundState.SUCCEEDED) won++;
        check(won == 10, "exactly ten of twenty concurrent refunds succeeded (" + won + ")");
        check(pot.refundedPaise() == Money.rupees("1000.00"), "and they add up to exactly what was captured");
        check(pot.refundReservedPaise() == 0, "every losing refund gave its reservation back");
        check(pot.state() == PaymentState.REFUNDED, "the payment is REFUNDED, not over-refunded");
        pool.shutdown();

        // 6. acquirer callbacks are at-least-once and out of order. A duplicate, and a report of something older
        //    than what we already know, must both change nothing -- and one that IS news must land.
        CardAcquirer ok6 = new CardAcquirer("OK6", 200, Currency.INR);
        PaymentService t6 = gatewayOver(ok6);
        Payment w = t6.pay("ord-6", "m1", Money.rupees("600.00"), Currency.INR, CARD);
        t6.capture(w.id());
        check(!t6.handleWebhook(w.id(), PaymentState.AUTHORIZED, "ref", NOW[0]),
              "a late 'authorized' after a capture is dropped on rank");
        check(!t6.handleWebhook(w.id(), PaymentState.CAPTURED, "ref", NOW[0]), "a duplicate 'captured' is dropped too");
        check(!t6.handleWebhook(w.id(), PaymentState.PENDING, "ref", NOW[0]), "'pending' is not an outcome and is ignored");
        t6.refund("rf6", w.id(), Money.rupees("200.00"));
        check(w.state() == PaymentState.PARTIALLY_REFUNDED && !t6.handleWebhook(w.id(), PaymentState.CAPTURED, "ref", NOW[0]),
              "a 'captured' arriving after a partial refund is dropped and the state holds");
        CardAcquirer ok6b = new CardAcquirer("OK6B", 200, Currency.INR);
        PaymentService t6b = gatewayOver(ok6b);
        ok6b.mode(VendorMode.TIMEOUT_CHARGED);
        Payment race = t6b.pay("ord-6b", "m1", Money.rupees("300.00"), Currency.INR, CARD);
        check(t6b.handleWebhook(race.id(), PaymentState.AUTHORIZED, "ok6b_ref", NOW[0]) && race.state() == PaymentState.AUTHORIZED,
              "a webhook that beats the status query closes the unknown payment");
        check(t6b.unresolved().isEmpty(), "and takes it off the reconciliation list");

        // 7. the primary acquirer refuses the connection. Nothing was charged, so failing over is safe and must
        //    happen; the same test proves the opposite case -- a timeout is never failed over.
        CardAcquirer down = new CardAcquirer("DOWN", 180, Currency.INR);
        CardAcquirer backup = new CardAcquirer("BACKUP", 220, Currency.INR);
        PaymentService t7 = gatewayOver(down, backup);
        down.mode(VendorMode.DOWN);
        Payment over = t7.pay("ord-7", "m1", Money.rupees("800.00"), Currency.INR, CARD);
        check(over.state() == PaymentState.AUTHORIZED && over.acquirer().equals("BACKUP"),
              "an unreachable acquirer fails over to the next one (" + over.acquirer() + ")");
        check(down.calls() == 0 && backup.calls() == 1, "the dead acquirer was never charged and the backup once");
        down.mode(VendorMode.TIMEOUT_CHARGED);
        Payment noFailover = t7.pay("ord-7b", "m1", Money.rupees("800.00"), Currency.INR, CARD);
        check(noFailover.state() == PaymentState.UNKNOWN && backup.calls() == 1,
              "a timeout at the primary is NOT failed over: the money may already have moved");
        CircuitBreaker breaker = new CircuitBreaker(down, 2, 30_000, () -> NOW[0]);
        try { breaker.authorize("x1", 100, Currency.INR, CARD); } catch (RuntimeException e) { /* first failure */ }
        try { breaker.authorize("x2", 100, Currency.INR, CARD); } catch (RuntimeException e) { /* second: it trips */ }
        check(breaker.open(), "the circuit breaker wrapped around a failing acquirer is open");

        // 8. a merchant's webhook endpoint is down, or their handler throws. Neither may touch the money.
        CardAcquirer ok8 = new CardAcquirer("OK8", 200, Currency.INR);
        PaymentService t8 = gatewayOver(ok8);
        t8.addListener(e -> { throw new RuntimeException("merchant handler blew up"); });
        MerchantWebhook hooks = new MerchantWebhook((url, e) -> false, 3);
        hooks.register(new Merchant("m1", "Shop", "https://shop.example/hooks"));
        t8.addListener(hooks);
        Payment safe = t8.pay("ord-8", "m1", Money.rupees("450.00"), Currency.INR, CARD);
        t8.capture(safe.id());
        check(safe.state() == PaymentState.CAPTURED && safe.capturedPaise() == Money.rupees("450.00"),
              "the payment captured although a listener threw and the merchant's endpoint was down");
        check(hooks.delivered() == 0 && hooks.dropped() > 0,
              "the webhook gave up after its retries and counted it (" + hooks.dropped() + " dropped)");
        check(t8.reconcile(0) == 0, "the books still balance: nothing captured more than it took, nothing over-refunded");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
