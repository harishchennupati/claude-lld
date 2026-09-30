import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Targeted failure tests: each block proves one claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /** Retries and defers run on the calling thread, so the whole suite is deterministic and never sleeps. */
    static final Scheduler INLINE = (task, delayMs) -> task.run();

    /** Every state every record ever reached, in order. */
    static final class Trace implements DeliveryListener {
        final Map<String, List<DeliveryState>> byId = new ConcurrentHashMap<>();
        public void onTransition(DeliveryRecord r, DeliveryState from, DeliveryState to, String detail) {
            byId.computeIfAbsent(r.notification().id(), k -> Collections.synchronizedList(new ArrayList<>())).add(to);
        }
        List<DeliveryState> of(DeliveryRecord r) { return byId.getOrDefault(r.notification().id(), List.of()); }
    }

    /** An adapter that blows up on its first call for a key, the way a null pointer in a client library does. */
    static final class BoomSender implements Sender {
        private final ConcurrentHashMap<String, AtomicInteger> calls = new ConcurrentHashMap<>();
        public Channel channel() { return Channel.PUSH; }
        public SendResult send(Recipient to, RenderedMessage m, String key) {
            if (calls.computeIfAbsent(key, k -> new AtomicInteger()).incrementAndGet() == 1)
                throw new IllegalStateException("null pointer deep inside the provider SDK");
            return SendResult.sent("push/ok");
        }
    }

    /** A push gateway that answers 503 to the first PLACED it sees, and remembers what got through, in order. */
    static final class FirstPlacedFails implements Sender {
        final List<String> through = Collections.synchronizedList(new ArrayList<>());
        private final AtomicBoolean failedOnce = new AtomicBoolean();
        public Channel channel() { return Channel.PUSH; }
        public SendResult send(Recipient to, RenderedMessage m, String key) {
            if (m.body().contains("PLACED") && failedOnce.compareAndSet(false, true)) return SendResult.transientFailure("503");
            through.add(m.body());
            return SendResult.sent("push/" + through.size());
        }
    }

    static final ZoneId IST = ZoneId.of("Asia/Kolkata");          // UTC+5:30

    /** The instant that is hour:minute in India on a fixed day. */
    static long atIndia(int hour, int minute) {
        return LocalDate.of(2026, 9, 26).atTime(hour, minute).atZone(IST).toInstant().toEpochMilli();
    }
    /** Poll until `done` is true, for at most two seconds: for the few checks that wait on a worker thread. */
    static boolean waitUntil(java.util.function.BooleanSupplier done) throws InterruptedException {
        long end = System.currentTimeMillis() + 2_000;
        while (!done.getAsBoolean() && System.currentTimeMillis() < end) Thread.sleep(1);
        return done.getAsBoolean();
    }
    /** Run every task a test scheduler has parked, including any that those tasks park in turn. */
    static void runParked(List<Runnable> parked) {
        while (true) {
            List<Runnable> now;
            synchronized (parked) { if (parked.isEmpty()) return; now = new ArrayList<>(parked); parked.clear(); }
            now.forEach(Runnable::run);
        }
    }

    static InMemoryTemplates templates() {
        return new InMemoryTemplates()
                .register("otp", Channel.SMS, new MessageTemplate("OTP", "{{code}} is your code"))
                .register("promo", Channel.PUSH, new MessageTemplate("{{pct}}% off", "ends midnight"))
                .register("receipt", Channel.EMAIL, new MessageTemplate("Receipt", "you paid {{amt}}"));
    }
    static InMemoryDirectory people() {
        return new InMemoryDirectory()
                .add(new Recipient("u1", "ravi@example.com", "+91900000001", "tok-1", IST))
                .add(new Recipient("u3", "no-at-sign", "+91900000003", "tok-3", IST));
    }

    public static void main(String[] args) throws Exception {

        // 1. fifty threads submit the SAME idempotency key at the same instant. The claim is one atomic
        //    operation, so exactly one wins and the human's phone buzzes exactly once.
        PushSender push = new PushSender();
        InMemoryDedupeStore dedupe = new InMemoryDedupeStore();
        NotificationService race = new NotificationService(4, 10_000);
        race.configure(templates(), people(), new ExponentialBackoff(3, 1, 100),
                List.of(new DedupeGuard(dedupe, 60_000)), Map.of(Channel.PUSH, push), () -> 1_000L, INLINE);
        race.start();
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<DeliveryRecord>> futures = new ArrayList<>();
        for (int i = 0; i < 50; i++)
            futures.add(pool.submit(() -> { go.await(); return race.submit(Notification.to("u1", Channel.PUSH, "promo")
                    .dedupeKey("order-9001").params(Map.of("pct", "10")).build()); }));
        go.countDown();
        int admitted = 0, duplicates = 0;
        for (Future<DeliveryRecord> f : futures) {
            DeliveryRecord r = f.get();
            if (r.state() == DeliveryState.SUPPRESSED && r.detail().contains("duplicate")) duplicates++; else admitted++;
        }
        pool.shutdown();
        race.awaitIdle(5_000);
        check(admitted == 1, "exactly one of fifty identical submits was admitted (got " + admitted + ")");
        check(duplicates == 49, "the other forty-nine were suppressed as duplicates (got " + duplicates + ")");
        check(push.calls() == 1, "the gateway was called exactly once, so the human got one message");
        check(dedupe.size() == 1, "one key is held, not fifty");
        race.shutdown();

        // 2. the gateway times out twice and then accepts. The message must go out on attempt 3 with the SAME
        //    idempotency key, and the backoff must double: 100, 200, 400, capped.
        FlakySmsSender flaky = new FlakySmsSender(2, true);
        Trace trace = new Trace();
        NotificationService retry = new NotificationService(1, 10_000);
        retry.configure(templates(), people(), new ExponentialBackoff(4, 100, 10_000),
                List.of(), Map.of(Channel.SMS, flaky), () -> 1_000L, INLINE);
        retry.addListener(trace);
        retry.start();
        DeliveryRecord otp = retry.submit(Notification.to("u1", Channel.SMS, "otp")
                .priority(Priority.CRITICAL).params(Map.of("code", "4821")).build());
        retry.awaitIdle(5_000);
        check(otp.state() == DeliveryState.SENT, "two timeouts then a success ends SENT, not FAILED (got " + otp.state() + ")");
        check(otp.attempt() == 3, "it took exactly three attempts (got " + otp.attempt() + ")");
        check(flaky.calls() == 3, "the gateway was called three times with one key");
        check(trace.of(otp).contains(DeliveryState.UNKNOWN), "a timeout is recorded as UNKNOWN, never as FAILED");
        RetryPolicy backoff = new ExponentialBackoff(4, 100, 10_000);
        check(backoff.backoffMs(1) == 100 && backoff.backoffMs(2) == 200 && backoff.backoffMs(3) == 400,
              "the backoff doubles: 100, 200, 400 ms");
        check(backoff.backoffMs(20) == 10_000, "and it stops at the cap instead of overflowing to a year");
        check(!backoff.shouldRetry(4) && backoff.shouldRetry(3), "the budget is four attempts, then dead letter");
        retry.shutdown();

        // 3. a malformed address is permanent: one call, no retry, straight to dead letter.
        EmailSender email = new EmailSender();
        NotificationService perm = new NotificationService(1, 10_000);
        perm.configure(templates(), people(), new ExponentialBackoff(4, 1, 100),
                List.of(), Map.of(Channel.EMAIL, email), () -> 1_000L, INLINE);
        perm.start();
        DeliveryRecord bad = perm.submit(Notification.to("u3", Channel.EMAIL, "receipt").params(Map.of("amt", "10")).build());
        perm.awaitIdle(5_000);
        check(bad.state() == DeliveryState.FAILED_FINAL, "a bad address fails permanently (got " + bad.state() + ")");
        check(bad.attempt() == 1, "and it is not retried even once (attempt " + bad.attempt() + ")");
        check(email.calls() == 1, "the provider was called exactly once");
        check(perm.deadLetters().size() == 1, "it is in the dead-letter list a human drains");
        perm.shutdown();

        // 4. the deadline passed while it waited in the queue: the gateway must never be called at all.
        PushSender counted = new PushSender();
        long[] clock = { 10_000_000L };
        NotificationService expiry = new NotificationService(1, 10_000);
        expiry.configure(templates(), people(), new ExponentialBackoff(4, 1, 100),
                List.of(), Map.of(Channel.PUSH, counted), () -> clock[0], INLINE);
        expiry.start();
        DeliveryRecord late = expiry.submit(Notification.to("u1", Channel.PUSH, "promo")
                .deadlineMs(clock[0] - 1).params(Map.of("pct", "5")).build());
        expiry.awaitIdle(5_000);
        check(late.state() == DeliveryState.EXPIRED, "a message past its deadline is EXPIRED (got " + late.state() + ")");
        check(counted.calls() == 0, "and the gateway was never called for it");
        expiry.shutdown();

        // 5. the rank rule: a stale receipt, a late DELIVERED, and a cancel that arrives before a worker starts.
        Notification n5 = Notification.to("u1", Channel.SMS, "otp").params(Map.of("code", "1")).build();
        DeliveryRecord rec = new DeliveryRecord(n5, new RenderedMessage("t", "b"), List.of());
        rec.moveTo(1, DeliveryState.QUEUED, "q1");
        rec.moveTo(1, DeliveryState.SENDING, "s1");
        rec.moveTo(1, DeliveryState.RETRY_SCHEDULED, "timed out");
        rec.moveTo(2, DeliveryState.QUEUED, "q2");
        rec.moveTo(2, DeliveryState.SENDING, "s2");
        check(!rec.moveTo(1, DeliveryState.SENT, "receipt for attempt 1"), "a receipt for attempt 1 is ignored while attempt 2 is in flight");
        check(rec.state() == DeliveryState.SENDING && rec.attempt() == 2, "and it changed nothing: still SENDING on attempt 2");
        check(rec.moveTo(2, DeliveryState.SENT, "gateway ok"), "the receipt for the attempt in flight is accepted");
        check(rec.moveTo(2, DeliveryState.DELIVERED, "handset ack"), "DELIVERED outranks SENT");
        check(!rec.moveTo(2, DeliveryState.SENT, "a second, later copy of the SENT webhook"), "a repeated older receipt is ignored");
        DeliveryRecord dead = new DeliveryRecord(n5, new RenderedMessage("t", "b"), List.of());
        dead.moveTo(1, DeliveryState.QUEUED, "q"); dead.moveTo(1, DeliveryState.SENDING, "s");
        dead.moveTo(1, DeliveryState.FAILED_FINAL, "gave up");
        check(dead.moveTo(1, DeliveryState.DELIVERED, "it arrived after all"), "a DELIVERED receipt still wins after we gave up");
        check(!dead.moveTo(1, DeliveryState.FAILED_FINAL, "stale"), "and nothing can push it back to FAILED");
        DeliveryRecord cancelled = new DeliveryRecord(n5, new RenderedMessage("t", "b"), List.of());
        cancelled.moveTo(1, DeliveryState.QUEUED, "q");
        check(cancelled.cancelIfNotStarted(), "a queued message can be cancelled");
        check(!cancelled.moveTo(1, DeliveryState.SENDING, "worker picked it up"), "a worker cannot start a cancelled message");
        cancelled.moveTo(1, DeliveryState.QUEUED, "q");
        DeliveryRecord sending = new DeliveryRecord(n5, new RenderedMessage("t", "b"), List.of());
        sending.moveTo(1, DeliveryState.QUEUED, "q"); sending.moveTo(1, DeliveryState.SENDING, "s");
        check(!sending.cancelIfNotStarted(), "a message already at the gateway cannot be cancelled, and we do not pretend");

        // 6. quiet hours defers instead of dropping, to 08:00 sharp on the recipient's clock (India is UTC+5:30),
        //    and an OTP walks through it.
        QuietHoursGuard quiet = new QuietHoursGuard(21, 8, Set.of(Channel.SMS, Channel.PUSH));
        Recipient india = new Recipient("u1", "r@example.com", "+91", "tok", IST);
        long threeAm = atIndia(3, 0), eightAm = atIndia(8, 0);
        Notification promo = Notification.to("u1", Channel.PUSH, "promo").category("marketing").params(Map.of("pct", "9")).build();
        Notification code = Notification.to("u1", Channel.SMS, "otp").priority(Priority.CRITICAL).params(Map.of("code", "1")).build();
        Verdict v = quiet.check(promo, india, threeAm);
        check(v.kind() == Verdict.Kind.DEFER, "a promo at 03:00 local is deferred, not dropped");
        check(v.untilMs() == eightAm, "it is held for exactly five hours, until 08:00 local");
        check(quiet.check(promo, india, atIndia(3, 40)).untilMs() == eightAm, "at 03:40 it is held until 08:00 sharp, not 08:40");
        check(quiet.check(promo, india, eightAm - 1).kind() == Verdict.Kind.DEFER
              && quiet.check(promo, india, eightAm).kind() == Verdict.Kind.ALLOW, "07:59:59.999 is quiet; 08:00:00 is not");
        check(quiet.check(promo, india, atIndia(22, 30)).untilMs() == eightAm + 86_400_000L, "at 22:30 it waits for tomorrow's 08:00");
        check(quiet.check(code, india, threeAm).kind() == Verdict.Kind.ALLOW, "an OTP at 03:00 goes out anyway");
        Trace nightTrace = new Trace();
        PushSender nightPush = new PushSender();
        AtomicLong nightClock = new AtomicLong(threeAm);
        Scheduler wakeOnTime = (task, delayMs) -> { nightClock.addAndGet(delayMs); task.run(); };   // jump ahead, then run
        NotificationService night = new NotificationService(1, 10_000);
        night.configure(templates(), people(), new ExponentialBackoff(3, 1, 100),
                List.of(quiet), Map.of(Channel.PUSH, nightPush), nightClock::get, wakeOnTime);
        night.addListener(nightTrace);
        night.start();
        DeliveryRecord held = night.submit(Notification.to("u1", Channel.PUSH, "promo").category("marketing").params(Map.of("pct", "9")).build());
        night.awaitIdle(5_000);
        check(nightTrace.of(held).contains(DeliveryState.DEFERRED), "the record passed through DEFERRED on its way out");
        check(held.state() == DeliveryState.SENT, "and it was sent when the window opened, not thrown away");
        night.shutdown();

        // 7. the daily cap RESERVES a slot, and a later guard's refusal gives it back: a duplicate submit must
        //    not quietly eat the user's quota.
        DailyCapGuard cap = new DailyCapGuard(2);
        InMemoryDedupeStore keys = new InMemoryDedupeStore();
        NotificationService capped = new NotificationService(1, 10_000);
        capped.configure(templates(), people(), new ExponentialBackoff(3, 1, 100),
                List.of(cap, new DedupeGuard(keys, 60_000)), Map.of(Channel.EMAIL, new EmailSender()), () -> 1_000L, INLINE);
        capped.start();
        capped.submit(Notification.to("u1", Channel.EMAIL, "receipt").dedupeKey("k1").params(Map.of("amt", "1")).build());
        check(cap.usedToday("u1") == 1, "the first message spent one of the two daily slots");
        DeliveryRecord dup = capped.submit(Notification.to("u1", Channel.EMAIL, "receipt").dedupeKey("k1").params(Map.of("amt", "1")).build());
        check(dup.state() == DeliveryState.SUPPRESSED && dup.detail().contains("duplicate"), "the second submit of the same key is a duplicate");
        check(cap.usedToday("u1") == 1, "and the duplicate gave the reserved slot back: still one used, not two");
        capped.submit(Notification.to("u1", Channel.EMAIL, "receipt").dedupeKey("k2").params(Map.of("amt", "2")).build());
        check(cap.usedToday("u1") == 2, "a different message spends the second slot");
        DeliveryRecord over = capped.submit(Notification.to("u1", Channel.EMAIL, "receipt").dedupeKey("k3").params(Map.of("amt", "3")).build());
        check(over.state() == DeliveryState.SUPPRESSED && over.detail().contains("already had 2 today"), "the third is capped, with the reason on the record");
        check(keys.size() == 2, "and the capped message never claimed an idempotency key");
        check(capped.historyOf("u1").size() == 4 && capped.historyOf("u1").get(3).detail().contains("already had 2"),
              "the per-user log holds all four, refused ones included, each with its reason");
        capped.awaitIdle(5_000);
        capped.shutdown();

        // 8. a listener that throws and an adapter that throws are both contained.
        Trace boomTrace = new Trace();
        NotificationService noisy = new NotificationService(1, 10_000);
        noisy.configure(templates(), people(), new ExponentialBackoff(3, 1, 100),
                List.of(), Map.of(Channel.PUSH, new BoomSender()), () -> 1_000L, INLINE);
        noisy.addListener((r, from, to, detail) -> { throw new RuntimeException("the metrics sink is down"); });
        noisy.addListener(boomTrace);
        noisy.start();
        DeliveryRecord survived = noisy.submit(Notification.to("u1", Channel.PUSH, "promo").params(Map.of("pct", "3")).build());
        noisy.awaitIdle(5_000);
        check(survived.state() == DeliveryState.SENT, "a listener that throws on every transition stops nothing");
        check(boomTrace.of(survived).contains(DeliveryState.UNKNOWN), "an adapter that throws is recorded as UNKNOWN, not as a lost worker");
        check(survived.attempt() == 2, "and the retry got it out on the second attempt");
        noisy.shutdown();

        // 9. back-pressure: the queue is full, so the message is refused at the door -- and everything the
        //    guards had already reserved for it is handed back. Nothing half-done, not even on the unhappy path.
        DailyCapGuard capB = new DailyCapGuard(10);
        InMemoryDedupeStore keysB = new InMemoryDedupeStore();
        PushSender neverCalled = new PushSender();
        NotificationService full = new NotificationService(0, 1);        // no workers, and room for exactly one
        full.configure(templates(), people(), new ExponentialBackoff(3, 1, 100),
                List.of(capB, new DedupeGuard(keysB, 60_000)), Map.of(Channel.PUSH, neverCalled), () -> 1_000L, INLINE);
        DeliveryRecord fits = full.submit(Notification.to("u1", Channel.PUSH, "promo").dedupeKey("b1").params(Map.of("pct", "1")).build());
        DeliveryRecord refused = full.submit(Notification.to("u1", Channel.PUSH, "promo").dedupeKey("b2").params(Map.of("pct", "2")).build());
        check(fits.state() == DeliveryState.QUEUED, "the first message fits in a queue of one");
        check(refused.state() == DeliveryState.SUPPRESSED && refused.detail().contains("back-pressure"),
                "the second is refused at the door, with the reason on the record (got " + refused.detail() + ")");
        check(neverCalled.calls() == 0, "a refused message never reaches a gateway");
        check(capB.usedToday("u1") == 1, "and it gave back the daily slot it had reserved: one used, not two");
        check(keysB.size() == 1, "and released the key it had claimed, so the caller's retry is not a duplicate");
        full.shutdown();

        // 10. the fallback ladder: a FAILURE climbs to the next channel, a deliberate refusal does not.
        InMemoryTemplates alerts = new InMemoryTemplates()
                .register("alert", Channel.PUSH, new MessageTemplate("ALERT", "{{what}}"))
                .register("alert", Channel.SMS, new MessageTemplate("ALERT", "{{what}}"));
        InMemoryDirectory reachable = new InMemoryDirectory()
                .add(new Recipient("u9", "u9@example.com", "+91900000009", null, IST))      // no device token at all
                .add(new Recipient("u8", "u8@example.com", "+91900000008", "tok-8", IST));  // reachable on push
        PushSender pushA = new PushSender();
        FlakySmsSender smsA = new FlakySmsSender(0, true);
        NotificationService climbs = new NotificationService(1, 100);
        climbs.configure(alerts, reachable, new ExponentialBackoff(2, 1, 10), List.of(),
                Map.of(Channel.PUSH, pushA, Channel.SMS, smsA), () -> 1_000L, INLINE);
        ChannelLadder ladder = new ChannelLadder(climbs, List.of(Channel.PUSH, Channel.SMS),
                channel -> Notification.to("u9", channel, "alert").priority(Priority.CRITICAL)
                                       .params(Map.of("what", "a card was used in Dubai")).build());
        climbs.addListener(ladder);
        climbs.start();
        DeliveryRecord rung1 = ladder.start();
        climbs.awaitIdle(5_000);
        check(rung1.state() == DeliveryState.FAILED_FINAL, "push fails permanently: that user has no device token");
        check(ladder.escalations() == 1, "so the ladder climbed exactly one rung (got " + ladder.escalations() + ")");
        check(smsA.calls() == 1, "and the same message went out by SMS, once");
        climbs.shutdown();

        PushSender pushB = new PushSender();
        FlakySmsSender smsB = new FlakySmsSender(0, true);
        NotificationService polite = new NotificationService(1, 100);
        polite.configure(alerts, reachable, new ExponentialBackoff(2, 1, 10),
                List.of(new PreferenceGuard(new InMemoryPreferences().mute("u8", Channel.PUSH, "marketing"))),
                Map.of(Channel.PUSH, pushB, Channel.SMS, smsB), () -> 1_000L, INLINE);
        ChannelLadder respectful = new ChannelLadder(polite, List.of(Channel.PUSH, Channel.SMS),
                channel -> Notification.to("u8", channel, "alert").priority(Priority.LOW).category("marketing")
                                       .params(Map.of("what", "40% off")).build());
        polite.addListener(respectful);
        polite.start();
        DeliveryRecord mutedRung = respectful.start();
        polite.awaitIdle(5_000);
        check(mutedRung.state() == DeliveryState.SUPPRESSED, "a muted channel is SUPPRESSED, which is a decision, not a failure");
        check(respectful.escalations() == 0, "so the ladder does NOT climb past an opt-out");
        check(smsB.calls() == 0, "and the user who turned push off was not chased onto SMS");
        polite.shutdown();

        // 11. a parked message is judged again when it wakes. At 03:00 a client sends one push twice (its HTTP call
        //     timed out), and a news push is parked too; at 07:00 the user mutes news. At 08:00 the retry meets the
        //     claim, the mute is honoured, and the one message that goes out counts on the day it is sent.
        AtomicLong dawnClock = new AtomicLong(threeAm);
        List<Runnable> parked11 = Collections.synchronizedList(new ArrayList<>());
        InMemoryPreferences dawnPrefs = new InMemoryPreferences();
        DailyCapGuard dawnCap = new DailyCapGuard(5);
        PushSender dawnPush = new PushSender();
        NotificationService dawn = new NotificationService(1, 100);
        dawn.configure(templates(), people(), new ExponentialBackoff(3, 1, 100),
                List.of(new PreferenceGuard(dawnPrefs), new QuietHoursGuard(21, 8, Set.of(Channel.PUSH)), dawnCap,
                        new DedupeGuard(new InMemoryDedupeStore(), 60_000)),
                Map.of(Channel.PUSH, dawnPush), dawnClock::get, (task, delayMs) -> parked11.add(task));
        dawn.start();
        DeliveryRecord sale = dawn.submit(Notification.to("u1", Channel.PUSH, "promo").category("marketing")
                .dedupeKey("sale-3am").params(Map.of("pct", "20")).build());
        DeliveryRecord saleAgain = dawn.submit(Notification.to("u1", Channel.PUSH, "promo").category("marketing")
                .dedupeKey("sale-3am").params(Map.of("pct", "20")).build());
        DeliveryRecord news = dawn.submit(Notification.to("u1", Channel.PUSH, "promo").category("news").params(Map.of("pct", "0")).build());
        check(sale.state() == DeliveryState.DEFERRED && saleAgain.state() == DeliveryState.DEFERRED
              && news.state() == DeliveryState.DEFERRED && dawnCap.usedToday("u1") == 0, "at 03:00 all three are parked, and nothing is reserved for them");
        dawnPrefs.mute("u1", Channel.PUSH, "news");                        // 07:00: the user turns news off
        dawnClock.set(eightAm);
        runParked(parked11);
        dawn.awaitIdle(5_000);
        check(dawnPush.calls() == 1, "at 08:00 the phone buzzes once, not three times (got " + dawnPush.calls() + ")");
        check(saleAgain.state() == DeliveryState.SUPPRESSED && saleAgain.detail().contains("duplicate"), "the client's retry met the claim");
        check(news.state() == DeliveryState.SUPPRESSED && news.detail().contains("opted out"), "the mute set at 07:00 was honoured at 08:00");
        check(dawnCap.usedToday("u1") == 1, "and the one that went out counts against the day it was sent");
        dawn.shutdown();

        // 12. a finished record stays finished. A caller cancels a queued push, and its deadline passes before a
        //     worker reaches it. It must still say "cancelled": EXPIRED is a failure, a failure climbs the fallback
        //     ladder, and the user would get an SMS for a message the caller took back.
        AtomicLong cancelClock = new AtomicLong(1_000L);
        FlakySmsSender smsC = new FlakySmsSender(0, true);
        NotificationService taken = new NotificationService(1, 100);
        taken.configure(alerts, reachable, new ExponentialBackoff(2, 1, 10), List.of(),
                Map.of(Channel.PUSH, new PushSender(), Channel.SMS, smsC), cancelClock::get, INLINE);
        ChannelLadder cancelLadder = new ChannelLadder(taken, List.of(Channel.PUSH, Channel.SMS),
                channel -> Notification.to("u8", channel, "alert").deadlineMs(channel == Channel.PUSH ? 5_000L : Long.MAX_VALUE)
                                       .params(Map.of("what", "your cab is here")).build());
        taken.addListener(cancelLadder);
        DeliveryRecord pushRung = cancelLadder.start();                    // queued; the workers have not started
        check(taken.cancel(pushRung.notification().id()), "the caller cancels it while it waits in the queue");
        cancelClock.set(10_000L);                                           // its deadline passes
        taken.start();
        taken.awaitIdle(5_000);
        check(pushRung.state() == DeliveryState.SUPPRESSED, "it still says cancelled, not EXPIRED (got " + pushRung.state() + ")");
        check(cancelLadder.escalations() == 0 && smsC.calls() == 0, "so the ladder did not text the user a message the caller took back");
        check(!pushRung.moveTo(1, DeliveryState.FAILED_FINAL, "a late timer"), "and no later move can turn it into a failure");
        taken.shutdown();

        // 13. the policies above the engine. Two digests closed in the same millisecond are two batches, not a
        //     duplicate; a paced campaign keeps its own copy of the list; a clock stepped back takes no tokens.
        EmailSender digestMail = new EmailSender();
        NotificationService bulk = new NotificationService(1, 100);
        bulk.configure(templates().register("digest", Channel.EMAIL, new MessageTemplate("{{count}} updates", "{{lines}}")),
                people(), new ExponentialBackoff(3, 1, 100), List.of(new DedupeGuard(new InMemoryDedupeStore(), 60_000)),
                Map.of(Channel.EMAIL, digestMail), () -> 5_000L, INLINE);
        bulk.start();
        DigestCollector digest = new DigestCollector(bulk, () -> 5_000L, 60_000, 2);
        digest.add("u1", "invoice 1 paid"); DeliveryRecord firstDigest = digest.add("u1", "invoice 2 paid");
        digest.add("u1", "invoice 3 paid"); DeliveryRecord secondDigest = digest.add("u1", "invoice 4 paid");
        bulk.awaitIdle(5_000);
        check(firstDigest.state() == DeliveryState.SENT && secondDigest.state() == DeliveryState.SENT,
              "two digests closed in the same millisecond both go out (got " + secondDigest + ")");
        List<Runnable> paced = Collections.synchronizedList(new ArrayList<>());
        List<Notification> campaign = new ArrayList<>();
        for (int i = 0; i < 4; i++) campaign.add(Notification.to("u1", Channel.EMAIL, "receipt").params(Map.of("amt", "" + i)).build());
        new CampaignPacer(bulk, (task, delayMs) -> paced.add(task)).run(campaign, 60_000, 2);
        campaign.clear();                                                    // the caller reuses its list before the timer fires
        boolean pacedOk;
        try { runParked(paced); pacedOk = true; } catch (ConcurrentModificationException e) { pacedOk = false; }
        bulk.awaitIdle(5_000);
        check(pacedOk && digestMail.calls() == 6, "each paced chunk went out from its own copy, after the caller cleared the list");
        bulk.shutdown();
        AtomicLong bucketClock = new AtomicLong(36_000_000L);
        RateLimitedSender bucket = new RateLimitedSender(new PushSender(), 2, 1, bucketClock::get);   // two tokens, one more a second
        Recipient ravi = people().lookup("u1");
        RenderedMessage words = new RenderedMessage("t", "b");
        bucket.send(ravi, words, "k1");                                      // one token left
        bucketClock.addAndGet(-3_600_000L);                                  // NTP steps the clock back an hour
        check(bucket.send(ravi, words, "k2").outcome() == SendOutcome.SENT, "a clock stepped back an hour still leaves the token that was there");

        // 14. Microsoft's version: two a day per user, and the third is held for tomorrow instead of dropped. It
        //     wakes at the user's midnight, is judged again, and counts against tomorrow's cap, not today's.
        AtomicLong jobClock = new AtomicLong(atIndia(10, 0));
        List<Runnable> parked14 = Collections.synchronizedList(new ArrayList<>());
        DailyCapGuard twoADay = new DailyCapGuard(2);
        EmailSender jobMail = new EmailSender();
        NotificationService jobs = new NotificationService(1, 100);
        jobs.configure(templates(), people(), new ExponentialBackoff(3, 1, 100), List.of(new HoldForTomorrowGuard(twoADay)),
                Map.of(Channel.EMAIL, jobMail), jobClock::get, (task, delayMs) -> parked14.add(task));
        jobs.start();
        List<DeliveryRecord> jobDone = new ArrayList<>();
        for (int i = 1; i <= 3; i++) jobDone.add(jobs.submit(Notification.to("u1", Channel.EMAIL, "receipt").params(Map.of("amt", "" + i)).build()));
        check(jobDone.get(2).state() == DeliveryState.DEFERRED && jobDone.get(2).detail().contains("tomorrow"),
              "the third of the day is held for tomorrow, not dropped (got " + jobDone.get(2) + ")");
        check(waitUntil(() -> jobMail.calls() == 2), "the first two went out today");
        jobClock.set(atIndia(0, 0) + 86_400_000L);                          // the user's midnight
        runParked(parked14);
        jobs.awaitIdle(5_000);
        check(jobDone.get(2).state() == DeliveryState.SENT && jobMail.calls() == 3, "at midnight it is judged again and goes out");
        check(twoADay.usedToday("u1") == 1, "and it counts against the new day's cap: one used, one left");
        jobs.shutdown();

        // 15. Cleartrip's version: an order event goes to the people on that order, on the channels they chose.
        //     SHIPPED reaches the customer and logistics but not the seller; the same event twice sends nothing new;
        //     a replay goes out again, on the channels the customer has today.
        InMemoryTemplates orderTemplates = new InMemoryTemplates();
        for (OrderEvent e : OrderEvent.values())
            for (Channel c : List.of(Channel.EMAIL, Channel.PUSH))
                orderTemplates.register("order-" + e, c, new MessageTemplate("Order {{order}}", "is " + e));
        InMemoryDirectory shopPeople = new InMemoryDirectory()
                .add(new Recipient("c1", "c1@example.com", "+91900000021", "tok-c1", IST))
                .add(new Recipient("s1", "s1@example.com", "+91900000022", "tok-s1", IST))
                .add(new Recipient("l1", "l1@example.com", "+91900000023", "tok-l1", IST));
        EmailSender orderMail = new EmailSender();
        PushSender orderPush = new PushSender();
        NotificationService shop = new NotificationService(2, 100);
        shop.configure(orderTemplates, shopPeople, new ExponentialBackoff(3, 1, 100),
                List.of(new DedupeGuard(new InMemoryDedupeStore(), 60_000)),
                Map.of(Channel.EMAIL, orderMail, Channel.PUSH, orderPush), () -> 1_000L, INLINE);
        shop.start();
        OrderNotifier notifier = new OrderNotifier(shop, EnumSet.of(Channel.EMAIL, Channel.PUSH));
        notifier.linkOrder("O-1", Map.of(Role.CUSTOMER, "c1", Role.SELLER, "s1", Role.LOGISTICS, "l1"));
        notifier.subscribe("c1", OrderEvent.SHIPPED, Set.of(Channel.EMAIL));          // this customer wants e-mail only for SHIPPED
        List<DeliveryRecord> shippedOnce = notifier.publish("O-1", OrderEvent.SHIPPED);
        List<DeliveryRecord> shippedTwice = notifier.publish("O-1", OrderEvent.SHIPPED);   // the order system retried
        shop.awaitIdle(5_000);
        Set<String> who = new TreeSet<>();
        for (DeliveryRecord r : shippedOnce) who.add(r.notification().userId() + ":" + r.notification().channel());
        check(who.equals(new TreeSet<>(Set.of("c1:EMAIL", "l1:EMAIL", "l1:PUSH"))),
              "SHIPPED went to the customer by e-mail and to logistics on both channels, not to the seller (got " + who + ")");
        check(shippedTwice.stream().allMatch(r -> r.state() == DeliveryState.SUPPRESSED), "publishing the same event again sent nothing new");
        check(orderMail.calls() == 2 && orderPush.calls() == 1, "three messages reached the gateways, not six");
        notifier.unsubscribe("s1", OrderEvent.PLACED);
        check(notifier.publish("O-1", OrderEvent.PLACED).stream().noneMatch(r -> r.notification().userId().equals("s1")),
              "a seller who unsubscribed from PLACED hears nothing");
        notifier.changeChannel("c1", Role.CUSTOMER, OrderEvent.SHIPPED, Channel.EMAIL, false);
        notifier.changeChannel("c1", Role.CUSTOMER, OrderEvent.SHIPPED, Channel.PUSH, true);   // e-mail off, push on
        List<DeliveryRecord> replayed = notifier.replay("O-1", OrderEvent.SHIPPED, Role.CUSTOMER);
        shop.awaitIdle(5_000);
        check(replayed.size() == 1 && replayed.get(0).notification().channel() == Channel.PUSH
              && replayed.get(0).state() == DeliveryState.SENT, "a replay goes out again, on the channel the customer has today");
        shop.shutdown();

        // 16. Ajio's follow-up: "Order Placed" must reach the gateway before "Order Shipped". Without a rule, PLACED
        //     gets a 503, waits for its retry, and SHIPPED overtakes it; one message in flight per order fixes it.
        for (boolean ordered : new boolean[] { false, true }) {
            List<Runnable> retries = Collections.synchronizedList(new ArrayList<>());
            FirstPlacedFails gateway = new FirstPlacedFails();
            NotificationService ajio = new NotificationService(1, 100);
            ajio.configure(orderTemplates, shopPeople, new ExponentialBackoff(3, 200, 1_000), List.of(),
                    Map.of(Channel.PUSH, gateway), () -> 1_000L, (task, delayMs) -> retries.add(task));
            InOrderDispatcher inOrder = new InOrderDispatcher(ajio);
            ajio.addListener(inOrder);
            ajio.start();
            Notification placedN = Notification.to("c1", Channel.PUSH, "order-PLACED").params(Map.of("order", "O-7")).build();
            Notification shippedN = Notification.to("c1", Channel.PUSH, "order-SHIPPED").params(Map.of("order", "O-7")).build();
            if (ordered) { inOrder.send("O-7", placedN); inOrder.send("O-7", shippedN); }
            else { ajio.submit(placedN); ajio.submit(shippedN); }
            waitUntil(() -> retries.size() == 1 && (ordered || gateway.through.size() == 1));   // PLACED failed once and waits
            runParked(retries);                                                                  // its 200 ms are up
            ajio.awaitIdle(5_000);
            List<String> seen = List.copyOf(gateway.through);
            if (!ordered) check(seen.equals(List.of("is SHIPPED", "is PLACED")), "without it, SHIPPED overtakes the PLACED that waits for its retry (got " + seen + ")");
            else check(seen.equals(List.of("is PLACED", "is SHIPPED")), "with one in flight per order, PLACED reaches the gateway first (got " + seen + ")");
            ajio.shutdown();
        }

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
