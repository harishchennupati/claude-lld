import java.time.Instant;
import java.time.ZoneId;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: a new channel -- one class, one registry line, and the compiler points at the rest
/**
 * WhatsApp. The whole channel is this: one class implementing Sender, one line in the map handed to
 * configure(), and one template registered for it. Nothing in the engine, the queue, the guards or the state
 * machine moves. The one cost that is not free: Channel is an enum, so a real WhatsApp needs a constant of its
 * own, and the exhaustive switch in Recipient.addressFor then fails to compile until you say which address it
 * uses -- which is the compiler doing your review for you. Key the registry by String and even that disappears.
 */
final class WhatsAppSender implements Sender {
    private final AtomicInteger calls = new AtomicInteger();
    public Channel channel() { return Channel.IN_APP; }          // a real one gets its own constant; see the note above
    public SendResult send(Recipient to, RenderedMessage m, String idempotencyKey) {
        calls.incrementAndGet();
        String number = to.phone();
        if (number == null || !number.startsWith("+")) return SendResult.permanentFailure("not an E.164 number: " + number);
        return SendResult.sent("wa/" + Integer.toHexString(idempotencyKey.hashCode()));
    }
    int calls() { return calls.get(); }
}

// ---- ext: a flaky provider is eating the workers -- stop calling it for a while (Decorator)
/**
 * A circuit breaker that IS a Sender, so the engine cannot tell the difference. After `threshold` failures in a
 * row it opens for `openMs` and answers TRANSIENT_FAILURE without making a network call, which means a dead SMS
 * gateway costs nothing instead of parking every worker on a socket timeout. One success closes it again.
 */
final class CircuitBreakerSender implements Sender {
    private final Sender base; private final int threshold; private final long openMs; private final Clock clock;
    private final AtomicInteger consecutiveFailures = new AtomicInteger();
    private final AtomicLong openUntilMs = new AtomicLong();
    private final AtomicInteger shortCircuited = new AtomicInteger();
    CircuitBreakerSender(Sender base, int threshold, long openMs, Clock clock) {
        this.base = base; this.threshold = threshold; this.openMs = openMs; this.clock = clock;
    }
    public Channel channel() { return base.channel(); }
    public SendResult send(Recipient to, RenderedMessage m, String idempotencyKey) {
        long now = clock.nowMs();
        if (now < openUntilMs.get()) {
            shortCircuited.incrementAndGet();
            return SendResult.transientFailure("circuit open for " + base.channel() + ", no call made");
        }
        SendResult result = base.send(to, m, idempotencyKey);
        switch (result.outcome()) {
            case SENT, PERMANENT -> consecutiveFailures.set(0);      // a permanent failure is the provider working fine
            case TRANSIENT, UNKNOWN -> { if (consecutiveFailures.incrementAndGet() >= threshold) openUntilMs.set(now + openMs); }
        }
        return result;
    }
    /** How many calls the breaker swallowed. The number you would put on a dashboard. */
    int shortCircuited() { return shortCircuited.get(); }
    boolean isOpen() { return clock.nowMs() < openUntilMs.get(); }
}

// ---- ext: the provider caps us at N per second -- a token bucket in front of it (Decorator)
/**
 * A token bucket (a counter that refills at a fixed rate; each send spends one token) in front of a provider,
 * again as a Sender that wraps a Sender. One bucket per user by default; hand in r -> "all" and it is the
 * provider's own limit instead (Amazon's 5,000 a minute: capacity 5000, refill 83.3 a second). The bucket is one
 * immutable record (tokens plus the instant they were measured) inside an AtomicReference, so "refill by elapsed
 * time, then spend one" is a single compare-and-set: two threads cannot both spend the last token, and no bucket
 * blocks another. Being refused is a TRANSIENT failure, so the engine's own backoff does the waiting for us.
 */
final class RateLimitedSender implements Sender {
    private record Bucket(double tokens, long stampMs) {}
    private final Sender base; private final double capacity, refillPerSecond; private final Clock clock;
    private final Function<Recipient, String> bucketOf;
    private final ConcurrentHashMap<String, AtomicReference<Bucket>> buckets = new ConcurrentHashMap<>();
    /** One bucket per user. */
    RateLimitedSender(Sender base, double capacity, double refillPerSecond, Clock clock) {
        this(base, capacity, refillPerSecond, clock, Recipient::userId);
    }
    /** One bucket per whatever `bucketOf` names: the user, or r -> "all" for the provider's own limit. */
    RateLimitedSender(Sender base, double capacity, double refillPerSecond, Clock clock, Function<Recipient, String> bucketOf) {
        this.base = base; this.capacity = capacity; this.refillPerSecond = refillPerSecond; this.clock = clock; this.bucketOf = bucketOf;
    }
    public Channel channel() { return base.channel(); }
    public SendResult send(Recipient to, RenderedMessage m, String idempotencyKey) {
        if (!tryAcquire(bucketOf.apply(to))) return SendResult.transientFailure("rate limited on " + base.channel());
        return base.send(to, m, idempotencyKey);
    }
    private boolean tryAcquire(String key) {
        AtomicReference<Bucket> ref = buckets.computeIfAbsent(key, k -> new AtomicReference<>(new Bucket(capacity, clock.nowMs())));
        while (true) {
            Bucket current = ref.get();
            long now = Math.max(clock.nowMs(), current.stampMs());          // a clock stepped back counts as no time passing
            double refilled = Math.min(capacity, current.tokens() + (now - current.stampMs()) / 1000.0 * refillPerSecond);
            if (refilled < 1.0) return false;
            if (ref.compareAndSet(current, new Bucket(refilled - 1.0, now))) return true;
        }
    }
}

// ---- ext: delivery receipts -- SENT is not the end of the story
/**
 * The webhook. It listens for SENT, remembers which provider reference belongs to which record and attempt, and
 * turns a later callback into one rank-ordered move. Everything hard about out-of-order webhooks was already
 * solved by the rank rule: a receipt for an attempt we have moved past is dropped, a DELIVERED outranks every
 * other terminal state, and the same receipt twice changes nothing the second time.
 */
final class ReceiptWebhook implements DeliveryListener {
    private record Origin(String notificationId, int attempt) {}
    private final NotificationService service;
    private final ConcurrentHashMap<String, Origin> byProviderRef = new ConcurrentHashMap<>();
    ReceiptWebhook(NotificationService service) { this.service = service; }
    public void onTransition(DeliveryRecord r, DeliveryState from, DeliveryState to, String detail) {
        if (to == DeliveryState.SENT) byProviderRef.put(detail, new Origin(r.notification().id(), r.attempt()));
    }
    /** Called by the HTTP handler. True means the record moved; false means the callback was stale or a repeat. */
    boolean deliveredAt(String providerRef) { return apply(providerRef, DeliveryState.DELIVERED, "receipt: handset ack"); }
    /** A hard bounce: the address exists at us but not at the provider. Terminal, and it outranks SENT. */
    boolean bounced(String providerRef, String why) { return apply(providerRef, DeliveryState.FAILED_FINAL, "bounce: " + why); }
    private boolean apply(String providerRef, DeliveryState state, String detail) {
        Origin o = byProviderRef.get(providerRef);
        return o != null && service.onReceipt(o.notificationId(), o.attempt(), state, detail);
    }
}

// ---- ext: priority lanes -- a flood of CRITICAL must not starve the marketing queue for ever
/**
 * One queue ordered by priority is right until somebody floods the top class: LOW then never runs. The
 * production answer is a lane per class with its own workers and its own bound, so each class is guaranteed a
 * share of the pool instead of competing for it. Each lane is a whole NotificationService, so only the routing
 * in front changes. One trap: each lane has its own gates, so two lanes must never share a guard that counts,
 * like the daily cap. Give each lane its own, or admit in one place and split only the delivery queues.
 */
final class PriorityLanes {
    private final Map<Priority, NotificationService> lanes = new EnumMap<>(Priority.class);
    /** Give each class its own workers. CRITICAL gets few but is never behind anything; LOW gets the leftovers. */
    PriorityLanes lane(Priority p, NotificationService service) { lanes.put(p, service); return this; }
    /** Route by class. The caller's code does not change at all. */
    DeliveryRecord submit(Notification n) {
        NotificationService s = lanes.get(n.priority());
        if (s == null) throw new IllegalStateException("no lane for " + n.priority());
        return s.submit(n);
    }
    void startAll() { lanes.values().forEach(NotificationService::start); }
    void shutdownAll() { lanes.values().forEach(NotificationService::shutdown); }
    /** The cheaper half-measure when you do not want four pools: age a record's effective priority while it waits. */
    static int effectivePriority(Priority declared, long waitedMs, long ageEveryMs) {
        return Math.max(0, declared.ordinal() - (int) (waitedMs / ageEveryMs));
    }
}

// ---- ext: batching for email -- twenty alerts in a minute should be one digest
/**
 * Batching belongs ABOVE the engine, not inside a Sender: a Sender that buffered would have to answer SENT
 * before the provider had seen anything, and that lie is exactly what the three-way SendResult exists to avoid.
 * So the collector holds submits for a window, then submits ONE notification whose parameters are the joined
 * lines. Every guard, retry and receipt then works on the digest, unchanged.
 */
final class DigestCollector {
    private final NotificationService service; private final long windowMs; private final int maxLines;
    private final Map<String, List<String>> pending = new HashMap<>();
    private final Map<String, Long> openedAtMs = new HashMap<>();
    private final Clock clock;
    DigestCollector(NotificationService service, Clock clock, long windowMs, int maxLines) {
        this.service = service; this.clock = clock; this.windowMs = windowMs; this.maxLines = maxLines;
    }
    /** Add one line for a user. Returns the digest's record when this line closed the batch, otherwise null. */
    DeliveryRecord add(String userId, String line) {
        List<String> ready;
        synchronized (this) {
            List<String> lines = pending.computeIfAbsent(userId, k -> new ArrayList<>());
            openedAtMs.putIfAbsent(userId, clock.nowMs());
            lines.add(line);
            boolean full = lines.size() >= maxLines;
            boolean old = clock.nowMs() - openedAtMs.get(userId) >= windowMs;
            if (!full && !old) return null;
            ready = take(userId);
        }
        return send(userId, ready);                          // outside the lock: submit calls guards and listeners
    }
    /** Send whatever is held for this user as one message. Called by the timer as well, for a half-full batch. */
    DeliveryRecord flush(String userId) {
        List<String> ready;
        synchronized (this) { ready = take(userId); }
        return ready == null || ready.isEmpty() ? null : send(userId, ready);
    }
    private List<String> take(String userId) { openedAtMs.remove(userId); return pending.remove(userId); }
    /**
     * No de-dup key: nobody retries a digest, and a key made from the clock would make two batches closed in the
     * same millisecond look like one, so the second would be refused as a duplicate and its lines lost.
     */
    private DeliveryRecord send(String userId, List<String> lines) {
        return service.submit(Notification.to(userId, Channel.EMAIL, "digest")
                .category("transactional")
                .params(Map.of("count", String.valueOf(lines.size()), "lines", String.join("; ", lines)))
                .build());
    }
}

// ---- ext: campaign pacing -- a million marketing pushes must not become one spike
/**
 * A campaign is a million submits, and submitting them in a loop puts a million records in the queue in a
 * second. Pacing spreads them across a window using the same injected Scheduler the retries use: batch k goes in
 * at start + k * (window / batches). Nothing else changes, and every message is still an ordinary notification,
 * so opt-outs, caps and quiet hours all still apply to it.
 */
final class CampaignPacer {
    private final NotificationService service; private final Scheduler scheduler;
    CampaignPacer(NotificationService service, Scheduler scheduler) { this.service = service; this.scheduler = scheduler; }
    /** Spread `all` evenly across `windowMs` in `batches` chunks. Returns immediately; the scheduler does the rest. */
    void run(List<Notification> all, long windowMs, int batches) {
        int size = Math.max(1, (all.size() + batches - 1) / batches);
        for (int b = 0, from = 0; from < all.size(); b++, from += size) {
            List<Notification> chunk = List.copyOf(all.subList(from, Math.min(all.size(), from + size)));   // our own copy: it is read later, on the timer
            long delay = (long) b * windowMs / batches;
            scheduler.schedule(() -> chunk.forEach(service::submit), delay);
        }
    }
}

// ---- ext: persistence and the outbox -- the same CAS, written in SQL
/**
 * Everything in memory today becomes two tables. The whole in-memory design survives because the rank rule maps
 * straight onto a conditional UPDATE: the database refuses the stale write exactly as the compare-and-set does.
 *
 *   INSERT INTO notification (id, idem_key, payload, rank) VALUES (?, ?, ?, 0) ON CONFLICT DO NOTHING;
 *   UPDATE notification SET state = ?, attempt = ?, rank = ? WHERE id = ? AND rank < ?;
 *
 * idem_key (user | channel | the caller's key) has a UNIQUE index, so the INSERT is also the de-dup claim: of two
 * submits with one key, one row goes in and the other inserts nothing (Redis: SET key 1 NX PX ttl). The claim
 * must be on that key, never on our own id, because a client's retry arrives with a new id. The UPDATE is
 * moveTo(): one row updated is a transition accepted, zero rows is moveTo() returning false. The outbox pattern
 * makes the hand-off to the queue crash-safe: the submit transaction writes the row AND an outbox row (a note
 * that says "put this on the queue"), and a relay reads the outbox and enqueues, so a crash between "recorded"
 * and "queued" is recovered instead of lost. With ten instances the id must be unique across all of them (a
 * UUID), not "n-" plus one process's counter.
 */
interface NotificationRepository {
    /** Insert the row once. False means it is already there (in SQL: this id, or this idempotency key). */
    boolean insertIfAbsent(String notificationId, String payload);
    /** The conditional update. False means a newer rank is already stored, so this write is stale and dropped. */
    boolean advance(String notificationId, DeliveryState state, int attempt, long rank);
    /** What the row says now, for a support screen or for recovery after a restart. */
    Progress read(String notificationId);
}

/** A map that behaves exactly like those two SQL statements, so the semantics can be tested without a database. */
final class InMemoryRepository implements NotificationRepository {
    private final ConcurrentHashMap<String, Progress> rows = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, String> payloads = new ConcurrentHashMap<>();
    public boolean insertIfAbsent(String notificationId, String payload) {
        boolean first = payloads.putIfAbsent(notificationId, payload) == null;
        if (first) rows.put(notificationId, new Progress(0, DeliveryState.CREATED, "inserted"));
        return first;
    }
    public boolean advance(String notificationId, DeliveryState state, int attempt, long rank) {
        while (true) {
            Progress current = rows.get(notificationId);
            if (current == null) return false;
            if (rank <= current.rank()) return false;                       // WHERE rank < ? matched no rows
            if (rows.replace(notificationId, current, new Progress(attempt, state, "persisted"))) return true;
        }
    }
    public Progress read(String notificationId) { return rows.get(notificationId); }
}

/**
 * Copies every accepted transition into the repository, after it happened in memory. A listener, so the engine
 * never learns about SQL. It is a write-through copy, not the outbox: in production the table is the truth and
 * moveTo() IS the UPDATE, so there is no second write to lose in a crash.
 */
final class WriteThroughListener implements DeliveryListener {
    private final NotificationRepository repo;
    WriteThroughListener(NotificationRepository repo) { this.repo = repo; }
    public void onTransition(DeliveryRecord r, DeliveryState from, DeliveryState to, String detail) {
        repo.insertIfAbsent(r.notification().id(), r.notification().toString());
        repo.advance(r.notification().id(), to, r.attempt(), Progress.rankOf(r.attempt(), to));
    }
}

// ---- ext: exactly once is impossible -- and the code says so out loud
/**
 * There is no exactly-once send to a remote gateway, and pretending otherwise is the mistake this design exists
 * to avoid. The gateway call has three outcomes, not two: yes, no, and no answer. On "no answer" you must choose
 * between never sending (and losing real messages when the reply was merely lost) and sending again (and risking
 * a duplicate). This service chooses at-least-once and then removes the duplicate at the only place it can be
 * removed -- the provider -- by carrying the SAME idempotency key on every attempt. That is effectively-once:
 * at-least-once delivery plus an idempotent receiver. UNKNOWN is the state that makes the choice visible instead
 * of hiding it behind a boolean.
 */
final class EffectivelyOnce {
    /** What a retry looks like from the provider's side: same key, so the second call is recognised, not resent. */
    static String explain(DeliveryRecord record) {
        Notification n = record.notification();
        return "key=" + n.idempotencyKey() + " attempt=" + record.attempt() + " state=" + record.state()
             + " -> the provider sees one key and collapses attempts 2..n into the first accepted send";
    }
    /** The only honest reconciliation for a record stuck at UNKNOWN when the budget runs out: ask, do not guess. */
    static String reconcile(DeliveryRecord record) {
        return record.state() == DeliveryState.UNKNOWN || record.state() == DeliveryState.SENDING
                ? "query the provider by " + record.notification().idempotencyKey() + " and set the state from THEIR answer"
                : "nothing to reconcile: " + record.state();
    }
}

// ---- ext: jittered backoff -- ten thousand retries must not come back in the same millisecond
/** Wraps any retry policy and spreads each wait over [50%, 100%] of it, so a recovered provider is not stampeded. */
final class JitteredBackoff implements RetryPolicy {
    private final RetryPolicy base; private final Random random;
    JitteredBackoff(RetryPolicy base, Random random) { this.base = base; this.random = random; }
    public boolean shouldRetry(int attemptsSoFar) { return base.shouldRetry(attemptsSoFar); }
    public long backoffMs(int attemptsSoFar) {
        long full = base.backoffMs(attemptsSoFar);
        return full / 2 + (long) (random.nextDouble() * (full / 2.0));
    }
}

// ---- ext: one message, several channels -- the fallback ladder, and what must NOT climb it
/**
 * "Try push; if push fails, send the same thing by SMS; if that fails, email." A ladder -- and it sits ABOVE the
 * engine on purpose. Each rung is a real notification with its own record, its own guards and its own retries,
 * so "where is n-8" still has exactly one answer per send, instead of one record carrying three outcomes.
 *
 * The rule to say out loud in the room: only a FAILURE climbs. FAILED_FINAL (the provider refused it, or the
 * retry budget ran out) and EXPIRED (the deadline passed before a gateway was called) escalate. SUPPRESSED does
 * NOT -- a mute, a daily cap, a duplicate or a cancel is a decision somebody made, and reaching a user on SMS
 * because they turned push off is how a notification service ends up in front of a regulator. SENT does not end
 * the ladder by itself: a hard bounce that arrives later (FAILED_FINAL from the webhook) is a failure, and climbs.
 * A cancelled rung cannot climb, because a finished record never moves again except to DELIVERED.
 *
 * It is a DeliveryListener, so it runs after the transition has been committed and with no lock held, which is
 * why calling submit() from here is safe. A production ladder hands the next rung to the same Scheduler the
 * retries use, so a worker thread is never spent on admission.
 */
final class ChannelLadder implements DeliveryListener {
    private final NotificationService service;
    private final List<Channel> rungs;
    private final Function<Channel, Notification> sameMessageOn;
    private final Map<String, Integer> rungOf = new ConcurrentHashMap<>();   // notification id -> which rung it is
    private final AtomicInteger escalations = new AtomicInteger();

    ChannelLadder(NotificationService service, List<Channel> rungs, Function<Channel, Notification> sameMessageOn) {
        this.service = service; this.rungs = List.copyOf(rungs); this.sameMessageOn = sameMessageOn;
    }
    /** Send on the top rung. Every rung below it is climbed by onTransition, or never. */
    DeliveryRecord start() { return sendRung(0); }

    private DeliveryRecord sendRung(int rung) {
        Notification n = sameMessageOn.apply(rungs.get(rung));
        rungOf.put(n.id(), rung);                                  // recorded BEFORE submit, which can fire at once
        return service.submit(n);
    }
    /** A rung that failed climbs; a rung that was refused on purpose, or accepted, does not. */
    public void onTransition(DeliveryRecord r, DeliveryState from, DeliveryState to, String why) {
        Integer rung = rungOf.get(r.notification().id());
        if (rung == null) return;                                            // not one of ours
        if (to != DeliveryState.FAILED_FINAL && to != DeliveryState.EXPIRED) return;
        if (rung + 1 >= rungs.size()) return;                                // the bottom rung: now a dead letter
        if (rungOf.remove(r.notification().id()) == null) return;   // claim the climb, the same way move 4 claims a key
        escalations.incrementAndGet();
        sendRung(rung + 1);
    }
    /** How many rungs we climbed. Zero is the answer you want: the first channel worked. */
    int escalations() { return escalations.get(); }
}

// ---- ext: ten instances behind a load balancer -- and evicting what nobody is using
/**
 * Two in-memory stores are all that stop this running on ten machines. The de-dup store becomes one Redis call,
 * SET key 1 NX PX ttl, which is the same single atomic claim putIfAbsent was; the per-channel token bucket
 * becomes a small Lua script that refills and spends in one round trip. The queue becomes a broker with a topic
 * per priority class. Nothing in the engine changes, because it never knew where the stores lived.
 *
 * The version below is the in-memory one plus the sweep that a TTL gives you for free in Redis: without it, a
 * process that has seen ten million keys holds ten million entries for ever.
 */
final class SweepingDedupeStore implements DedupeStore {
    private final ConcurrentHashMap<String, Long> expiryByKey = new ConcurrentHashMap<>();
    public boolean claim(String key, long nowMs, long ttlMs) {
        while (true) {
            Long previous = expiryByKey.putIfAbsent(key, nowMs + ttlMs);    // Redis: SET key 1 NX PX ttlMs
            if (previous == null) return true;
            if (previous > nowMs) return false;
            if (expiryByKey.replace(key, previous, nowMs + ttlMs)) return true;
        }
    }
    public void release(String key) { expiryByKey.remove(key); }            // Redis: DEL key
    /** Drop every key whose window has closed. Run it on the timer; Redis does this for you. */
    int sweep(long nowMs) {
        int before = expiryByKey.size();
        expiryByKey.entrySet().removeIf(e -> e.getValue() <= nowMs);
        return before - expiryByKey.size();
    }
    int size() { return expiryByKey.size(); }
}

// ---- ext: over the daily limit, hold it for tomorrow instead of dropping it (Microsoft)
/**
 * Microsoft's version of the cap: two a day per user, and the third is held for tomorrow, not dropped. It is a
 * guard that wraps the daily cap and turns its "no" into "not today": a Decorator on a guard. It needs nothing
 * new from the engine, because a parked message is judged again when it wakes. At the user's midnight it meets
 * tomorrow's cap like any new message, and quiet hours, if it is in the list, moves it on to 08:00.
 */
final class HoldForTomorrowGuard implements DeliveryGuard {
    private final DailyCapGuard cap;
    HoldForTomorrowGuard(DailyCapGuard cap) { this.cap = cap; }
    public String name() { return cap.name(); }
    public Verdict check(Notification n, Recipient r, long nowMs) {
        Verdict v = cap.check(n, r, nowMs);
        if (v.kind() != Verdict.Kind.SUPPRESS) return v;
        long midnight = Instant.ofEpochMilli(nowMs).atZone(r.zone()).toLocalDate().plusDays(1)
                               .atStartOfDay(r.zone()).toInstant().toEpochMilli();     // the user's midnight, not ours
        return Verdict.defer(midnight, "daily limit reached, held until tomorrow");
    }
    public void undo(Notification n, Recipient r) { cap.undo(n, r); }
}

// ---- ext: order events to the people on the order (Cleartrip) -- a table, not a broker
/** The three moments in an order's life that people are told about. */
enum OrderEvent { PLACED, SHIPPED, DELIVERED }
/** Who is on an order. Each role hears some events by default. */
enum Role { CUSTOMER, SELLER, LOGISTICS }

/**
 * Cleartrip's machine-coding version: an order event goes only to the people on THAT order, each on the channels
 * they chose. By default the customer hears every event, the seller only PLACED and logistics only SHIPPED, on
 * every channel; anyone can unsubscribe from an event or change its channels. One event becomes one ordinary
 * notification per person and channel, so guards, retries and records all still apply, and the order system never
 * waits: submit only queues. Their panel wanted this demoable in 90 minutes, not a Kafka cluster.
 */
final class OrderNotifier {
    private static final Map<Role, Set<OrderEvent>> HEARS = Map.of(
            Role.CUSTOMER, EnumSet.allOf(OrderEvent.class),
            Role.SELLER, EnumSet.of(OrderEvent.PLACED),
            Role.LOGISTICS, EnumSet.of(OrderEvent.SHIPPED));
    private final NotificationService service;
    private final Set<Channel> allChannels;
    private final ConcurrentHashMap<String, Map<Role, String>> people = new ConcurrentHashMap<>();   // order id -> role -> user
    private final ConcurrentHashMap<String, Set<Channel>> chosen = new ConcurrentHashMap<>();       // "user|event" -> channels

    OrderNotifier(NotificationService service, Set<Channel> allChannels) { this.service = service; this.allChannels = Set.copyOf(allChannels); }
    /** Who is on this order. Only these people ever hear about its events. */
    void linkOrder(String orderId, Map<Role, String> stakeholders) { people.put(orderId, Map.copyOf(stakeholders)); }
    /** Replace one person's channels for one event, for every order. An empty set is an unsubscribe. */
    void subscribe(String userId, OrderEvent e, Set<Channel> channels) { chosen.put(userId + "|" + e, Set.copyOf(channels)); }
    /** Stop hearing about this event on any order. */
    void unsubscribe(String userId, OrderEvent e) { subscribe(userId, e, Set.of()); }
    /** Add or drop one channel. compute() makes the read-change-write one atomic step per key, so two edits at once never lose one. */
    void changeChannel(String userId, Role role, OrderEvent e, Channel c, boolean on) {
        chosen.compute(userId + "|" + e, (k, old) -> {
            Set<Channel> s = EnumSet.noneOf(Channel.class);
            s.addAll(old != null ? old : defaults(role, e));
            if (on) s.add(c); else s.remove(c);
            return Set.copyOf(s);
        });
    }
    /** The order system calls this and returns at once. Publishing the same event twice sends nothing new. */
    List<DeliveryRecord> publish(String orderId, OrderEvent e) { return send(orderId, e, null, orderId + "|" + e); }
    /** Cleartrip's bonus: send an old event again to one role, on the channels they have TODAY. A fresh key, because a replay is meant to go out again. */
    List<DeliveryRecord> replay(String orderId, OrderEvent e, Role who) { return send(orderId, e, who, orderId + "|" + e + "|replay-" + UUID.randomUUID()); }

    private List<DeliveryRecord> send(String orderId, OrderEvent e, Role only, String key) {
        List<DeliveryRecord> out = new ArrayList<>();
        for (Map.Entry<Role, String> p : people.getOrDefault(orderId, Map.of()).entrySet()) {
            if (only != null && p.getKey() != only) continue;
            for (Channel c : chosen.getOrDefault(p.getValue() + "|" + e, defaults(p.getKey(), e)))
                out.add(service.submit(Notification.to(p.getValue(), c, "order-" + e).category("order")
                        .dedupeKey(key + "|" + p.getKey()).params(Map.of("order", orderId)).build()));
        }
        return out;
    }
    private Set<Channel> defaults(Role role, OrderEvent e) { return HEARS.get(role).contains(e) ? allChannels : Set.of(); }
}

// ---- ext: "Order Placed" must arrive before "Order Shipped" (Ajio) -- one in flight per key
/**
 * Two workers, or one retry, can reorder two messages: PLACED gets a 503, waits 200 ms for its retry, and SHIPPED
 * overtakes it. The fix is one message in flight per ordering key (the order id): the next one is submitted only
 * when the one before it is SENT or finished. It is a listener above the engine, so the engine does not change.
 * SENT is the strongest order we control; for "the phone shows them in order", wait for DELIVERED and pay the delay.
 */
final class InOrderDispatcher implements DeliveryListener {
    private final NotificationService service;
    private final Map<String, ArrayDeque<Notification>> waiting = new HashMap<>();  // key -> the ones behind the one in flight
    private final Map<String, String> keyOf = new ConcurrentHashMap<>();            // id of the one in flight -> its key
    InOrderDispatcher(NotificationService service) { this.service = service; }

    /** Submit now if nothing with this key is in flight; otherwise wait behind it. Null means "waiting its turn". */
    DeliveryRecord send(String key, Notification n) {
        synchronized (this) {
            ArrayDeque<Notification> behind = waiting.get(key);
            if (behind != null) { behind.add(n); return null; }
            waiting.put(key, new ArrayDeque<>());                    // present = one in flight for this key
            keyOf.put(n.id(), key);
        }
        return submitOrSkip(n);                                      // outside the lock: submit calls listeners
    }
    /** When the one in flight is SENT or finished, submit the next one for its key. */
    public void onTransition(DeliveryRecord r, DeliveryState from, DeliveryState to, String why) {
        if (to == DeliveryState.SENT || to.terminal()) moveOn(r.notification().id());
    }
    private void moveOn(String id) {
        String key = keyOf.remove(id);
        if (key == null) return;                                     // not ours, or its SENT already moved the key on
        Notification next;
        synchronized (this) {
            next = waiting.get(key).poll();
            if (next == null) { waiting.remove(key); return; }
            keyOf.put(next.id(), key);
        }
        submitOrSkip(next);
    }
    /** A submit that throws (no template, no such user) must not block its key for ever: move on, then rethrow. */
    private DeliveryRecord submitOrSkip(Notification n) {
        try { return service.submit(n); }
        catch (RuntimeException e) { moveOn(n.id()); throw e; }
    }
}

/** Runs every extension above, so the follow-up answers on page 05 are code that has actually executed. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        long[] now = { 1_000_000L };
        Clock clock = () -> now[0];
        Scheduler inline = (task, delayMs) -> task.run();

        InMemoryTemplates templates = new InMemoryTemplates()
                .register("promo", Channel.PUSH, new MessageTemplate("{{pct}}% off", "ends midnight"))
                .register("otp", Channel.SMS, new MessageTemplate("OTP", "{{code}} is your code"))
                .register("digest", Channel.EMAIL, new MessageTemplate("{{count}} updates", "{{lines}}"))
                .register("alert", Channel.IN_APP, new MessageTemplate("ALERT", "{{what}}"));
        ZoneId ist = ZoneId.of("Asia/Kolkata");
        InMemoryDirectory people = new InMemoryDirectory()
                .add(new Recipient("u1", "ravi@example.com", "+91900000001", "tok-1", ist))
                .add(new Recipient("u2", "meera@example.com", "+91900000002", "tok-2", ist));

        // 1. a new channel: one class, one line in the registry
        WhatsAppSender whatsapp = new WhatsAppSender();
        NotificationService wa = new NotificationService(1, 1_000);
        wa.configure(templates, people, new ExponentialBackoff(2, 1, 10), List.of(),
                Map.of(Channel.IN_APP, whatsapp), clock, inline);
        wa.start();
        DeliveryRecord viaWhatsApp = wa.submit(Notification.to("u1", Channel.IN_APP, "alert").params(Map.of("what", "card used in Dubai")).build());
        wa.awaitIdle(2_000);
        System.out.println("new channel: " + viaWhatsApp.state() + " after " + whatsapp.calls() + " call, zero engine edits");
        wa.shutdown();

        // 2 + 3. the circuit breaker and the rate limiter, both wrapping the same sender
        FlakySmsSender broken = new FlakySmsSender(99, false);                 // never recovers
        CircuitBreakerSender breaker = new CircuitBreakerSender(broken, 2, 60_000, clock);
        NotificationService cb = new NotificationService(1, 1_000);
        cb.configure(templates, people, new ExponentialBackoff(5, 1, 10), List.of(),
                Map.of(Channel.SMS, breaker), clock, inline);
        cb.start();
        DeliveryRecord doomed = cb.submit(Notification.to("u1", Channel.SMS, "otp").params(Map.of("code", "1")).build());
        cb.awaitIdle(2_000);
        System.out.println("circuit breaker: " + doomed.state() + " after " + doomed.attempt() + " attempts; "
                + breaker.shortCircuited() + " of them never touched the network; open=" + breaker.isOpen());
        cb.shutdown();

        PushSender rawPush = new PushSender();
        RateLimitedSender limited = new RateLimitedSender(rawPush, 2, 0.0001, clock);   // two, then effectively none
        NotificationService rl = new NotificationService(1, 1_000);
        rl.configure(templates, people, new ExponentialBackoff(1, 1, 10), List.of(),
                Map.of(Channel.PUSH, limited), clock, inline);
        rl.start();
        int sent = 0;
        for (int i = 0; i < 5; i++) {
            DeliveryRecord r = rl.submit(Notification.to("u1", Channel.PUSH, "promo").params(Map.of("pct", "5")).build());
            rl.awaitIdle(2_000);
            if (r.state() == DeliveryState.SENT) sent++;
        }
        System.out.println("rate limiter: five submits, " + sent + " reached the gateway (" + rawPush.calls() + " real calls)");
        rl.shutdown();

        // 4. delivery receipts
        PushSender plain = new PushSender();
        NotificationService receipts = new NotificationService(1, 1_000);
        receipts.configure(templates, people, new ExponentialBackoff(2, 1, 10), List.of(),
                Map.of(Channel.PUSH, plain), clock, inline);
        ReceiptWebhook webhook = new ReceiptWebhook(receipts);
        receipts.addListener(webhook);
        receipts.start();
        DeliveryRecord watched = receipts.submit(Notification.to("u2", Channel.PUSH, "promo").params(Map.of("pct", "7")).build());
        receipts.awaitIdle(2_000);
        String providerRef = watched.detail();
        boolean first = webhook.deliveredAt(providerRef), repeat = webhook.deliveredAt(providerRef);
        System.out.println("receipts: " + watched.state() + "; first callback applied=" + first + ", the same callback again=" + repeat);
        receipts.shutdown();

        // 5. priority lanes
        NotificationService critical = new NotificationService(1, 100), low = new NotificationService(1, 100);
        for (NotificationService s : List.of(critical, low))
            s.configure(templates, people, new ExponentialBackoff(2, 1, 10), List.of(), Map.of(Channel.PUSH, new PushSender()), clock, inline);
        PriorityLanes lanes = new PriorityLanes().lane(Priority.CRITICAL, critical).lane(Priority.LOW, low);
        lanes.startAll();
        lanes.submit(Notification.to("u1", Channel.PUSH, "promo").priority(Priority.CRITICAL).params(Map.of("pct", "1")).build());
        lanes.submit(Notification.to("u1", Channel.PUSH, "promo").priority(Priority.LOW).params(Map.of("pct", "2")).build());
        critical.awaitIdle(2_000); low.awaitIdle(2_000);
        System.out.println("lanes: a LOW message still ran while CRITICAL was busy; ageing after 10 min gives LOW rank "
                + PriorityLanes.effectivePriority(Priority.LOW, 600_000, 300_000));
        lanes.shutdownAll();

        // 6 + 7. digests and campaign pacing
        EmailSender mail = new EmailSender();
        NotificationService bulk = new NotificationService(2, 10_000);
        bulk.configure(templates, people, new ExponentialBackoff(2, 1, 10), List.of(),
                Map.of(Channel.EMAIL, mail, Channel.PUSH, new PushSender()), clock, inline);
        bulk.start();
        DigestCollector digest = new DigestCollector(bulk, clock, 60_000, 3);
        digest.add("u1", "invoice 1 paid"); digest.add("u1", "invoice 2 paid");
        DeliveryRecord sentDigest = digest.add("u1", "invoice 3 paid");
        bulk.awaitIdle(2_000);
        System.out.println("digest: three events became " + (sentDigest == null ? 0 : 1) + " email, state " + sentDigest.state());

        List<Notification> campaign = new ArrayList<>();
        for (int i = 0; i < 20; i++) campaign.add(Notification.to("u2", Channel.PUSH, "promo").priority(Priority.LOW).params(Map.of("pct", "3")).build());
        new CampaignPacer(bulk, inline).run(campaign, 3_600_000, 4);
        bulk.awaitIdle(3_000);
        System.out.println("pacing: a 20-message campaign went out in 4 batches instead of one spike");
        bulk.shutdown();

        // 8. persistence: the conditional UPDATE refuses the stale write exactly as the CAS does
        InMemoryRepository repo = new InMemoryRepository();
        repo.insertIfAbsent("n-1", "payload");
        boolean twice = repo.insertIfAbsent("n-1", "payload");
        repo.advance("n-1", DeliveryState.QUEUED, 1, Progress.rankOf(1, DeliveryState.QUEUED));
        repo.advance("n-1", DeliveryState.SENDING, 1, Progress.rankOf(1, DeliveryState.SENDING));
        repo.advance("n-1", DeliveryState.SENT, 2, Progress.rankOf(2, DeliveryState.SENT));
        boolean stale = repo.advance("n-1", DeliveryState.SENT, 1, Progress.rankOf(1, DeliveryState.SENT));
        System.out.println("repository: second insert=" + twice + ", stale update=" + stale + ", row now " + repo.read("n-1").state());

        // 9. effectively once, said out loud
        System.out.println("effectively once: " + EffectivelyOnce.explain(watched));
        System.out.println("reconcile:        " + EffectivelyOnce.reconcile(doomed));

        // 10. jitter
        RetryPolicy jittered = new JitteredBackoff(new ExponentialBackoff(5, 1_000, 30_000), new Random(7));
        System.out.println("jitter: three waits that would all have been 2000 ms -> "
                + jittered.backoffMs(2) + ", " + jittered.backoffMs(2) + ", " + jittered.backoffMs(2) + " ms");

        // 11. the shared store, and the sweep a TTL gives you for free
        SweepingDedupeStore shared = new SweepingDedupeStore();
        shared.claim("a", now[0], 10); shared.claim("b", now[0], 10_000);
        now[0] += 100;
        System.out.println("shared store: " + shared.size() + " keys, swept " + shared.sweep(now[0]) + ", " + shared.size() + " left");

        // 12. the fallback ladder: push has no device token, so the SAME message goes out by SMS instead
        templates.register("alert", Channel.PUSH, new MessageTemplate("ALERT", "{{what}}"))
                 .register("alert", Channel.SMS, new MessageTemplate("ALERT", "{{what}}"));
        people.add(new Recipient("u3", "raj@example.com", "+91900000003", null, ist));    // no device token
        PushSender noToken = new PushSender();
        FlakySmsSender goodSms = new FlakySmsSender(0, true);
        NotificationService ladderService = new NotificationService(1, 1_000);
        ladderService.configure(templates, people, new ExponentialBackoff(2, 1, 10), List.of(),
                Map.of(Channel.PUSH, noToken, Channel.SMS, goodSms), clock, inline);
        ChannelLadder ladder = new ChannelLadder(ladderService, List.of(Channel.PUSH, Channel.SMS),
                channel -> Notification.to("u3", channel, "alert").priority(Priority.CRITICAL)
                                       .params(Map.of("what", "a card was used in Dubai")).build());
        ladderService.addListener(ladder);
        ladderService.start();
        DeliveryRecord firstRung = ladder.start();
        ladderService.awaitIdle(2_000);
        System.out.println("ladder: push " + firstRung.state() + ", climbed " + ladder.escalations()
                + " rung, and the SMS gateway was called " + goodSms.calls() + " time");
        ladderService.shutdown();

        // 13. over the daily limit: held for tomorrow, not dropped (Microsoft)
        DailyCapGuard two = new DailyCapGuard(2);
        EmailSender jobsMail = new EmailSender();
        List<Runnable> tomorrow = Collections.synchronizedList(new ArrayList<>());
        NotificationService jobs = new NotificationService(1, 100);
        jobs.configure(templates, people, new ExponentialBackoff(2, 1, 10), List.of(new HoldForTomorrowGuard(two)),
                Map.of(Channel.EMAIL, jobsMail), clock, (task, delayMs) -> tomorrow.add(task));
        jobs.start();
        List<DeliveryRecord> done = new ArrayList<>();
        for (int i = 1; i <= 3; i++)
            done.add(jobs.submit(Notification.to("u1", Channel.EMAIL, "digest").params(Map.of("count", "1", "lines", "job " + i + " finished")).build()));
        String third = done.get(2).state() + " (" + done.get(2).detail() + ")";
        now[0] += 86_400_000L;                                              // the next day
        new ArrayList<>(tomorrow).forEach(Runnable::run);
        jobs.awaitIdle(2_000);
        System.out.println("daily limit: the third was " + third + ", then " + done.get(2).state() + " the next day; "
                + jobsMail.calls() + " e-mails in all");
        jobs.shutdown();

        // 14. order events to the people on the order (Cleartrip)
        for (OrderEvent e : OrderEvent.values())
            for (Channel c : List.of(Channel.EMAIL, Channel.PUSH))
                templates.register("order-" + e, c, new MessageTemplate("Order {{order}}", "is " + e));
        people.add(new Recipient("s1", "shop@example.com", "+91900000011", "tok-s1", ist))
              .add(new Recipient("l1", "rider@example.com", "+91900000012", "tok-l1", ist));
        NotificationService shop = new NotificationService(2, 1_000);
        shop.configure(templates, people, new ExponentialBackoff(2, 1, 10), List.of(new DedupeGuard(new InMemoryDedupeStore(), 60_000)),
                Map.of(Channel.EMAIL, new EmailSender(), Channel.PUSH, new PushSender()), clock, inline);
        shop.start();
        OrderNotifier orders = new OrderNotifier(shop, EnumSet.of(Channel.EMAIL, Channel.PUSH));
        orders.linkOrder("O-1", Map.of(Role.CUSTOMER, "u1", Role.SELLER, "s1", Role.LOGISTICS, "l1"));
        List<DeliveryRecord> shipped = orders.publish("O-1", OrderEvent.SHIPPED);
        List<DeliveryRecord> again = orders.publish("O-1", OrderEvent.SHIPPED);
        shop.awaitIdle(2_000);
        long fresh = again.stream().filter(r -> r.state() != DeliveryState.SUPPRESSED).count();
        System.out.println("order events: SHIPPED became " + shipped.size() + " messages (customer and logistics, two channels"
                + " each, the seller none); publishing it again sent " + fresh + " more");

        // 15. one in flight per order, so PLACED always reaches the gateway before SHIPPED (Ajio)
        InOrderDispatcher inOrder = new InOrderDispatcher(shop);
        shop.addListener(inOrder);
        DeliveryRecord placed = inOrder.send("O-2", Notification.to("u1", Channel.PUSH, "order-PLACED").params(Map.of("order", "O-2")).build());
        DeliveryRecord behind = inOrder.send("O-2", Notification.to("u1", Channel.PUSH, "order-SHIPPED").params(Map.of("order", "O-2")).build());
        shop.awaitIdle(2_000);
        System.out.println("in order: PLACED " + placed.state() + "; SHIPPED waited its turn (" + (behind == null)
                + ") and was sent after it: " + shop.historyOf("u1").get(shop.historyOf("u1").size() - 1).state());
        shop.shutdown();
    }
}
