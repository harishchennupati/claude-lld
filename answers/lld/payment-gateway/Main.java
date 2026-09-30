import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/** The currencies this gateway settles in. One currency per payment, always; FX is a follow-up, not a special case. */
enum Currency { INR, USD }

/** Exact money, in paise (a hundredth of a rupee). There is no double in this file; these helpers are the only boundary. */
final class Money {
    /** Parse "1234.50" into 123450 paise, exactly. Used at the edge (a form, a JSON body), never inside the arithmetic. */
    static long rupees(String amount) { return new java.math.BigDecimal(amount).movePointRight(2).longValueExact(); }
    /** Print 123450 paise as "1234.50". Presentation only. */
    static String fmt(long paise) {
        String sign = paise < 0 ? "-" : ""; long a = Math.abs(paise);
        return sign + (a / 100) + "." + String.format("%02d", a % 100);
    }
    /** Basis points of an amount: 200 bp = 2%. Integer arithmetic, rounded down, so a fee can never invent a paise. */
    static long bps(long paise, long basisPoints) { return paise * basisPoints / 10_000; }
}

/** What the customer paid with. The gateway routes on this and logs it; it never branches on it to move money. */
enum PaymentMethodType { CARD, UPI, NETBANKING }

/**
 * The instrument, already tokenised. There is no card number anywhere in this file: the gateway holds a token the
 * vault gave it and a display string safe to print. That is the whole of PCI scope in one record.
 */
record PaymentMethod(PaymentMethodType type, String token, String display) {
    @Override public String toString() { return type + " " + display; }
}

/** Who is being paid. An id, a name and where to call back when something happens to one of their payments. */
record Merchant(String id, String name, String webhookUrl) { }

/**
 * A payment's life, written down once as data instead of scattered as if-statements.
 *
 * Two things live here. canGoTo() is the legality table: capturing a declined payment is not a bug to catch later,
 * it is an edge that does not exist. outcomeRank() is the ordering: acquirer webhooks arrive late, twice and out of
 * order, so every outcome gets a rank and a report that does not beat the highest rank reached is dropped.
 */
enum PaymentState {
    CREATED, PENDING, AUTHORIZED, CAPTURED, PARTIALLY_REFUNDED, REFUNDED, FAILED, UNKNOWN;

    private static final Map<PaymentState, Set<PaymentState>> NEXT = new EnumMap<>(PaymentState.class);
    static {
        NEXT.put(CREATED,            EnumSet.of(PENDING, FAILED));
        // PENDING -> CREATED and UNKNOWN -> AUTHORIZED are the un-claim edges: the call provably never reached the
        // acquirer, so the claim is handed back and the payment is exactly where it was.
        NEXT.put(PENDING,            EnumSet.of(AUTHORIZED, CAPTURED, FAILED, UNKNOWN, CREATED));
        NEXT.put(AUTHORIZED,         EnumSet.of(PENDING, CAPTURED, FAILED));
        NEXT.put(UNKNOWN,            EnumSet.of(AUTHORIZED, CAPTURED, FAILED, CREATED));
        NEXT.put(CAPTURED,           EnumSet.of(PARTIALLY_REFUNDED, REFUNDED));
        NEXT.put(PARTIALLY_REFUNDED, EnumSet.of(PARTIALLY_REFUNDED, REFUNDED));
        NEXT.put(REFUNDED,           EnumSet.noneOf(PaymentState.class));
        NEXT.put(FAILED,             EnumSet.noneOf(PaymentState.class));
    }

    /** Is this move legal at all? Asked before every state change, by the response path and the webhook path alike. */
    boolean canGoTo(PaymentState next) { return NEXT.get(this).contains(next); }

    /**
     * How far along the payment this outcome is. CREATED, PENDING and UNKNOWN are not outcomes at all, so they rank
     * zero: they say "a call is in flight", never "this is what happened". A webhook is applied only if its rank
     * beats the highest rank the payment has ever reached, which is what makes duplicates and reordering free.
     */
    int outcomeRank() {
        return switch (this) {
            case CREATED, PENDING, UNKNOWN -> 0;
            case AUTHORIZED, FAILED -> 1;
            case CAPTURED -> 2;
            case PARTIALLY_REFUNDED -> 3;
            case REFUNDED -> 4;
        };
    }
}

/** A refund's life. UNKNOWN means the acquirer was called and never answered; the reservation stays until it does. */
enum RefundState { PENDING, SUCCEEDED, FAILED, UNKNOWN }

/** Where time comes from. Injected, so a test can put the clock anywhere it likes and move it. */
interface Clock { long nowMs(); }

/** A rule refused this payment before anything was attempted. Nothing was charged and nothing was written. */
class PaymentRejected extends RuntimeException {
    PaymentRejected(String reason) { super(reason); }
}

/**
 * The acquirer was called and never answered. THE dangerous failure: the money may or may not have moved, so the
 * payment becomes UNKNOWN, no second call is made and no other acquirer is tried. Only the status API settles it.
 */
class ProcessorTimeout extends RuntimeException {
    ProcessorTimeout(String reason) { super(reason); }
}

/**
 * The call never left the building -- a refused connection, an open circuit, a rejected request. Nothing was
 * charged, so this one is safe: the claim is handed back and the next acquirer on the route is tried.
 */
class ProcessorUnavailable extends RuntimeException {
    ProcessorUnavailable(String reason) { super(reason); }
}

/** What an acquirer says happened. NOT_FOUND is the status API's way of saying "I never saw that request". */
enum Outcome { AUTHORIZED, CAPTURED, DECLINED, REFUNDED, NOT_FOUND }

/** One answer from an acquirer: what happened, the acquirer's own reference, and why if it said no. */
record ProcessorResult(Outcome outcome, String ref, String reason) {
    /** A successful answer with the acquirer's reference on it. */
    static ProcessorResult ok(Outcome o, String ref) { return new ProcessorResult(o, ref, ""); }
    /** A refusal, with the acquirer's reason attached so the merchant can be told something useful. */
    static ProcessorResult no(Outcome o, String reason) { return new ProcessorResult(o, "", reason); }
}

/**
 * One acquirer, behind our vocabulary. Every vendor speaks a different dialect; each implementation is the adapter
 * that translates exactly one of them, so the gateway never learns a vendor's names.
 *
 * The contract that matters: every call takes OUR idempotency key, so calling twice with the same key charges once
 * at their end too, and statusOf(key) answers what happened to it. That is what makes an UNKNOWN recoverable.
 */
interface PaymentProcessor {
    /** The acquirer's name, used by routing and stored on the payment so a retry goes back to the same one. */
    String name();
    /** Can this acquirer take this method in this currency? Asked by routing, never by the payment flow. */
    boolean supports(PaymentMethodType type, Currency currency);
    /** What this acquirer charges, in basis points. 200 bp = 2%. Read by the fee policy and by cost-based routing. */
    long feeBps();
    /** True for rails with no auth/capture split (UPI): authorize() already moved the money. */
    boolean capturesOnAuthorize();
    /** Reserve the money. Throws ProcessorTimeout (unknown) or ProcessorUnavailable (nothing happened). */
    ProcessorResult authorize(String idemKey, long paise, Currency currency, PaymentMethod method);
    /** Move the reserved money. Same two failure modes, same meaning. */
    ProcessorResult capture(String idemKey, String acquirerRef, long paise);
    /** Send money back. Same two failure modes. */
    ProcessorResult refund(String idemKey, String acquirerRef, long paise);
    /** What happened to the request we sent under this key? The only honest way out of an UNKNOWN. */
    ProcessorResult statusOf(String idemKey);
}

/** What the simulated vendor does next. A test sets it; a real HTTP client would simply succeed or fail. */
enum VendorMode {
    /** Everything works. */                                                           HEALTHY,
    /** The acquirer says no (bad card, no funds). A business outcome, not a failure. */ DECLINE,
    /** The connection is refused: nothing was charged, so failing over is safe. */      DOWN,
    /** The acquirer did the work and then the socket died. The expensive one. */        TIMEOUT_CHARGED,
    /** The request died before the acquirer saw it, and we cannot tell the difference. */ TIMEOUT_LOST
}

/**
 * A card acquirer, simulated. It remembers what it did per idempotency key, which is what a real acquirer does and
 * the reason we pass our own id down as the key: asking twice never charges twice, at either end.
 */
class CardAcquirer implements PaymentProcessor {
    private final String name; private final long feeBps; private final EnumSet<Currency> currencies;
    private final Map<String, ProcessorResult> byKey = new ConcurrentHashMap<>();
    private final AtomicInteger calls = new AtomicInteger();
    private volatile VendorMode mode = VendorMode.HEALTHY;

    CardAcquirer(String name, long feeBps, Currency... currencies) {
        this.name = name; this.feeBps = feeBps;
        this.currencies = EnumSet.copyOf(Arrays.asList(currencies));
    }
    public String name() { return name; }
    public long feeBps() { return feeBps; }
    public boolean capturesOnAuthorize() { return false; }
    public boolean supports(PaymentMethodType type, Currency c) {
        return (type == PaymentMethodType.CARD || type == PaymentMethodType.NETBANKING) && currencies.contains(c);
    }
    /** Point the vendor at a failure mode. Tests only. */
    void mode(VendorMode m) { mode = m; }
    /** How many requests actually reached this vendor. The number the race test asserts on. */
    int calls() { return calls.get(); }

    public ProcessorResult authorize(String idemKey, long paise, Currency c, PaymentMethod method) {
        return call(idemKey, Outcome.AUTHORIZED, "declined by issuer");
    }
    public ProcessorResult capture(String idemKey, String acquirerRef, long paise) {
        return call(idemKey, Outcome.CAPTURED, "capture refused: authorization expired");
    }
    public ProcessorResult refund(String idemKey, String acquirerRef, long paise) {
        return call(idemKey, Outcome.REFUNDED, "refund refused by issuer");
    }
    public ProcessorResult statusOf(String idemKey) {
        ProcessorResult seen = byKey.get(idemKey);
        return seen != null ? seen : ProcessorResult.no(Outcome.NOT_FOUND, name + " never saw " + idemKey);
    }

    /** One vendor round trip, with the vendor's own idempotency in front of it and the failure modes behind it. */
    private ProcessorResult call(String idemKey, Outcome success, String declineReason) {
        if (mode == VendorMode.DOWN) throw new ProcessorUnavailable(name + " refused the connection");
        ProcessorResult seen = byKey.get(idemKey);
        if (seen != null) return seen;                                  // the vendor's own idempotency, not ours
        calls.incrementAndGet();
        if (mode == VendorMode.TIMEOUT_LOST) throw new ProcessorTimeout(name + " did not answer in 3000 ms");
        if (mode == VendorMode.DECLINE) {
            ProcessorResult no = ProcessorResult.no(Outcome.DECLINED, declineReason);
            byKey.put(idemKey, no); return no;
        }
        ProcessorResult yes = ProcessorResult.ok(success, name.toLowerCase() + "_" + idemKey);
        byKey.put(idemKey, yes);                                        // the work is done...
        if (mode == VendorMode.TIMEOUT_CHARGED) throw new ProcessorTimeout(name + " did not answer in 3000 ms");
        return yes;                                                     // ...and only now do we get to hear about it
    }
}

/**
 * A UPI switch. Different rail, different shape: there is no authorize-then-capture, the money moves in one step.
 * The gateway never learns this -- it asks capturesOnAuthorize() and the flow is otherwise identical.
 */
class UpiSwitch implements PaymentProcessor {
    private final String name; private final long feeBps;
    private final Map<String, ProcessorResult> byKey = new ConcurrentHashMap<>();
    private final AtomicInteger calls = new AtomicInteger();
    private volatile VendorMode mode = VendorMode.HEALTHY;

    UpiSwitch(String name, long feeBps) { this.name = name; this.feeBps = feeBps; }
    public String name() { return name; }
    public long feeBps() { return feeBps; }
    public boolean capturesOnAuthorize() { return true; }
    public boolean supports(PaymentMethodType type, Currency c) { return type == PaymentMethodType.UPI && c == Currency.INR; }
    /** Point the switch at a failure mode. Tests only. */
    void mode(VendorMode m) { mode = m; }
    /** How many requests actually reached this vendor. */
    int calls() { return calls.get(); }

    /** On UPI the collect request IS the capture, so this returns CAPTURED and there is nothing left to do. */
    public ProcessorResult authorize(String idemKey, long paise, Currency c, PaymentMethod method) {
        return collect(idemKey, Outcome.CAPTURED, "collect request declined by the payer's bank");
    }
    /** Already captured. Called only if someone captures a UPI payment by mistake; it is a no-op, not an error. */
    public ProcessorResult capture(String idemKey, String acquirerRef, long paise) {
        return ProcessorResult.ok(Outcome.CAPTURED, acquirerRef);
    }
    public ProcessorResult refund(String idemKey, String acquirerRef, long paise) {
        return collect(idemKey, Outcome.REFUNDED, "refund declined by the payer's bank");
    }
    public ProcessorResult statusOf(String idemKey) {
        ProcessorResult seen = byKey.get(idemKey);
        return seen != null ? seen : ProcessorResult.no(Outcome.NOT_FOUND, name + " never saw " + idemKey);
    }
    private ProcessorResult collect(String idemKey, Outcome success, String declineReason) {
        if (mode == VendorMode.DOWN) throw new ProcessorUnavailable(name + " is not reachable");
        ProcessorResult seen = byKey.get(idemKey);
        if (seen != null) return seen;
        calls.incrementAndGet();
        if (mode == VendorMode.TIMEOUT_LOST) throw new ProcessorTimeout(name + " did not answer in 3000 ms");
        if (mode == VendorMode.DECLINE) {
            ProcessorResult no = ProcessorResult.no(Outcome.DECLINED, declineReason);
            byKey.put(idemKey, no); return no;
        }
        ProcessorResult yes = ProcessorResult.ok(success, name.toLowerCase() + "_" + idemKey);
        byKey.put(idemKey, yes);
        if (mode == VendorMode.TIMEOUT_CHARGED) throw new ProcessorTimeout(name + " did not answer in 3000 ms");
        return yes;
    }
}

/**
 * A circuit breaker wrapped around ANY acquirer. It is a PaymentProcessor that holds a PaymentProcessor, so a
 * vendor written next year gets breaking for free and no vendor adapter has ever heard of it.
 *
 * After `threshold` consecutive failures it trips: every call fails instantly as ProcessorUnavailable, which the
 * router reads as "try the next one". After the cool-off it lets one call through and closes on the first success.
 */
class CircuitBreaker implements PaymentProcessor {
    private interface Call { ProcessorResult run(); }
    private final PaymentProcessor inner; private final int threshold; private final long coolOffMs;
    private final Clock clock;
    private final AtomicInteger consecutiveFailures = new AtomicInteger();
    private volatile long openedAtMs = 0;

    CircuitBreaker(PaymentProcessor inner, int threshold, long coolOffMs, Clock clock) {
        this.inner = inner; this.threshold = threshold; this.coolOffMs = coolOffMs; this.clock = clock;
    }
    /** The wrapped acquirer's own name, so routing and the stored processor name do not know the wrapper exists. */
    public String name() { return inner.name(); }
    public boolean supports(PaymentMethodType t, Currency c) { return inner.supports(t, c); }
    public long feeBps() { return inner.feeBps(); }
    public boolean capturesOnAuthorize() { return inner.capturesOnAuthorize(); }
    public ProcessorResult authorize(String k, long paise, Currency c, PaymentMethod m) { return guard(() -> inner.authorize(k, paise, c, m)); }
    public ProcessorResult capture(String k, String ref, long paise) { return guard(() -> inner.capture(k, ref, paise)); }
    public ProcessorResult refund(String k, String ref, long paise) { return guard(() -> inner.refund(k, ref, paise)); }
    public ProcessorResult statusOf(String k) { return inner.statusOf(k); }      // asking is always allowed
    /** True while the breaker is open. Exposed for a health screen; the flow never asks. */
    boolean open() {
        if (openedAtMs == 0) return false;
        if (clock.nowMs() - openedAtMs < coolOffMs) return true;
        openedAtMs = 0; consecutiveFailures.set(0);                     // half-open: let the next call decide
        return false;
    }
    private ProcessorResult guard(Call c) {
        if (open()) throw new ProcessorUnavailable(inner.name() + ": circuit is open");
        try {
            ProcessorResult r = c.run();
            consecutiveFailures.set(0);
            return r;
        } catch (ProcessorUnavailable | ProcessorTimeout e) {
            if (consecutiveFailures.incrementAndGet() >= threshold) openedAtMs = clock.nowMs();
            throw e;
        }
    }
}

/**
 * Which acquirers may take this payment, best first. The whole list is returned rather than one acquirer, because
 * the tail of it IS the failover plan. Swapped live during an incident; the gateway never builds one.
 */
interface RoutingPolicy {
    /** The acquirers that can take this payment, in the order they should be tried. Empty means nobody can. */
    List<PaymentProcessor> route(PaymentMethodType type, Currency currency, long paise, List<PaymentProcessor> all);
}

/** Route by relationship: a preferred acquirer per method, then anyone else who supports it, as the failover tail. */
class PreferredRouting implements RoutingPolicy {
    private final Map<PaymentMethodType, List<String>> preferred;
    PreferredRouting(Map<PaymentMethodType, List<String>> preferred) {
        this.preferred = new EnumMap<>(preferred);
    }
    public List<PaymentProcessor> route(PaymentMethodType type, Currency currency, long paise, List<PaymentProcessor> all) {
        List<String> order = preferred.getOrDefault(type, List.of());
        List<PaymentProcessor> able = new ArrayList<>();
        for (PaymentProcessor p : all) if (p.supports(type, currency)) able.add(p);
        able.sort(Comparator.comparingInt(p -> {
            int i = order.indexOf(p.name());
            return i < 0 ? order.size() : i;                            // unlisted acquirers sit at the back
        }));
        return able;
    }
}

/** What we charge the merchant for this payment. The rule most likely to change on a Friday afternoon. */
interface FeePolicy {
    /** The fee in paise, taken out of what the merchant is settled. Never taken out of what the customer pays. */
    long feeFor(long paise, PaymentMethodType type, PaymentProcessor acquirer);
}

/** A flat paise charge plus the acquirer's own basis points. Integer arithmetic, rounded down. */
class BpsFee implements FeePolicy {
    private final long flatPaise;
    BpsFee(long flatPaise) { this.flatPaise = flatPaise; }
    public long feeFor(long paise, PaymentMethodType type, PaymentProcessor acquirer) {
        return flatPaise + Money.bps(paise, acquirer.feeBps());
    }
}

/** When a failed acquirer call may be tried again on the next acquirer in the route. */
interface RetryPolicy {
    /** True to try the next acquirer. Called with the number of acquirers tried so far and the failure. */
    boolean retry(int attemptsSoFar, RuntimeException failure);
}

/**
 * The only safe retry policy: retry a call that provably never reached the acquirer, never one that timed out.
 * A timeout means the money may already have moved, and retrying it is how a customer gets charged twice.
 */
class RetrySafeFailuresOnly implements RetryPolicy {
    private final int maxAttempts;
    RetrySafeFailuresOnly(int maxAttempts) { this.maxAttempts = maxAttempts; }
    public boolean retry(int attemptsSoFar, RuntimeException failure) {
        return failure instanceof ProcessorUnavailable && attemptsSoFar < maxAttempts;
    }
}

/** One check run before a payment is attempted. It may read anything; it must write nothing. Refuses by throwing. */
interface RiskRule {
    /** Throw PaymentRejected to refuse. Runs outside every lock, before a single acquirer is called. */
    void check(String merchantId, long paise, PaymentMethod method, long nowMs);
}

/** A ceiling per method: cards over the cap need a step-up, which is a follow-up, so today they are refused. */
class AmountCapRule implements RiskRule {
    private final Map<PaymentMethodType, Long> caps;
    AmountCapRule(Map<PaymentMethodType, Long> caps) { this.caps = new EnumMap<>(caps); }
    public void check(String merchantId, long paise, PaymentMethod method, long nowMs) {
        Long cap = caps.get(method.type());
        if (cap != null && paise > cap)
            throw new PaymentRejected("over the " + method.type() + " cap: " + Money.fmt(paise) + " > " + Money.fmt(cap));
    }
}

/** What happened to a payment, as a value. Listeners get this, never the Payment, so they cannot change it. */
record PaymentEvent(String paymentId, String merchantId, PaymentState state, long paise, long capturedPaise,
                    long refundedPaise, String acquirer, String reason, long atMs) {
    @Override public String toString() {
        return paymentId + " " + state + " " + Money.fmt(paise) + (acquirer.isEmpty() ? "" : " via " + acquirer)
             + (reason.isEmpty() ? "" : " (" + reason + ")");
    }
}

/** Someone who wants to know a payment moved. Called AFTER every lock is released, never inside one. */
interface PaymentListener {
    /** Told about every state change. Must not throw; if it does, the gateway swallows it and carries on. */
    void onEvent(PaymentEvent e);
}

/** How a webhook actually leaves the building. Handed in so a test can make the network fail on demand. */
interface WebhookEndpoint {
    /** True if the merchant's server accepted it. */
    boolean post(String url, PaymentEvent e);
}

/**
 * The merchant's callback, with retries. Delivery is at-least-once: it retries a refused POST up to maxAttempts and
 * then gives up and counts it, because a merchant's slow server must never hold up a payment.
 */
class MerchantWebhook implements PaymentListener {
    private final Map<String, String> urls = new ConcurrentHashMap<>();
    private final WebhookEndpoint endpoint; private final int maxAttempts;
    private final AtomicInteger delivered = new AtomicInteger(), dropped = new AtomicInteger();

    MerchantWebhook(WebhookEndpoint endpoint, int maxAttempts) { this.endpoint = endpoint; this.maxAttempts = maxAttempts; }
    /** Where this merchant wants to be called. Setup only. */
    void register(Merchant m) { urls.put(m.id(), m.webhookUrl()); }
    /** How many callbacks the merchants accepted. */
    int delivered() { return delivered.get(); }
    /** How many were given up on after maxAttempts. */
    int dropped() { return dropped.get(); }

    public void onEvent(PaymentEvent e) {
        String url = urls.get(e.merchantId());
        if (url == null) return;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            if (endpoint.post(url, e)) { delivered.incrementAndGet(); return; }
        }
        dropped.incrementAndGet();
    }
}

/** The audit trail: every event, in order, appended and never edited. The cheapest listener there is. */
class AuditLog implements PaymentListener {
    private final List<PaymentEvent> events = new CopyOnWriteArrayList<>();
    public void onEvent(PaymentEvent e) { events.add(e); }
    /** Every event ever seen, oldest first. */
    List<PaymentEvent> events() { return List.copyOf(events); }
    /** Every event for one payment, oldest first. O(n) over the log; a real one would be indexed. */
    List<PaymentEvent> of(String paymentId) {
        List<PaymentEvent> out = new ArrayList<>();
        for (PaymentEvent e : events) if (e.paymentId().equals(paymentId)) out.add(e);
        return out;
    }
}

/** One attempt to send money back, linked to the payment it belongs to. A refund is a transaction, not a field. */
class Refund {
    private final String id, idemKey, paymentId; private final long paise, createdMs;
    private volatile RefundState state = RefundState.PENDING;
    private volatile String acquirerRef = "", failureReason = "";

    Refund(String id, String idemKey, String paymentId, long paise, long createdMs) {
        this.id = id; this.idemKey = idemKey; this.paymentId = paymentId; this.paise = paise; this.createdMs = createdMs;
    }
    String id() { return id; }
    String idemKey() { return idemKey; }
    String paymentId() { return paymentId; }
    long paise() { return paise; }
    long createdMs() { return createdMs; }
    RefundState state() { return state; }
    String acquirerRef() { return acquirerRef; }
    String failureReason() { return failureReason; }
    /** The acquirer sent the money back. */
    void succeed(String ref) { this.acquirerRef = ref; this.state = RefundState.SUCCEEDED; }
    /** Refused, and the payment's reservation has been handed back. */
    void fail(String reason) { this.failureReason = reason; this.state = RefundState.FAILED; }
    /** The acquirer never answered. The reservation STAYS held until the status query settles it. */
    void unknown(String reason) { this.failureReason = reason; this.state = RefundState.UNKNOWN; }
    @Override public String toString() {
        return id + " " + Money.fmt(paise) + " of " + paymentId + " " + state
             + (failureReason.isEmpty() ? "" : " (" + failureReason + ")");
    }
}

/**
 * One payment, and the only thing in the system that may change a payment's state. It owns its state, its money
 * and its OWN lock: two payments never wait for each other, and the same payment's fifty retries are serialised
 * for half a microsecond each.
 *
 * The lock is private and every method here takes it and gives it back before returning. That is deliberate: the
 * flow in PaymentService cannot hold a lock across a network call because it is never handed one.
 */
class Payment {
    private final String id, idemKey, merchantId;
    private final long paise; private final Currency currency; private final PaymentMethod method;
    private final long createdMs;
    private final ReentrantLock lock = new ReentrantLock();

    private PaymentState state = PaymentState.CREATED;   // guarded by lock
    private PaymentState claimedFrom = PaymentState.CREATED;  // guarded by lock: what the in-flight claim came from
    private int rankReached = 0;                         // guarded by lock: only ever grows
    private String acquirer = "", acquirerRef = "", inFlightKey = "", reason = "";   // guarded by lock
    private long feePaise, capturedPaise, refundedPaise, refundReservedPaise, lastChangeMs;  // guarded by lock

    Payment(String id, String idemKey, String merchantId, long paise, Currency currency, PaymentMethod method, long createdMs) {
        this.id = id; this.idemKey = idemKey; this.merchantId = merchantId; this.paise = paise;
        this.currency = currency; this.method = method; this.createdMs = createdMs; this.lastChangeMs = createdMs;
    }
    String id() { return id; }
    String idemKey() { return idemKey; }
    String merchantId() { return merchantId; }
    long paise() { return paise; }
    Currency currency() { return currency; }
    PaymentMethod method() { return method; }
    long createdMs() { return createdMs; }

    /** The state, read under the lock so nobody sees it half-written. O(1). */
    PaymentState state() { lock.lock(); try { return state; } finally { lock.unlock(); } }
    /** The acquirer that holds this payment. A capture or a refund must go back to the same one. */
    String acquirer() { lock.lock(); try { return acquirer; } finally { lock.unlock(); } }
    /** The acquirer's own reference for this payment, needed by capture and refund. */
    String acquirerRef() { lock.lock(); try { return acquirerRef; } finally { lock.unlock(); } }
    /** The key the in-flight call was sent under. The status query asks about exactly this key. */
    String inFlightKey() { lock.lock(); try { return inFlightKey; } finally { lock.unlock(); } }
    /** What the in-flight claim moved away from, so a call that never happened can be un-claimed exactly. */
    PaymentState claimedFrom() { lock.lock(); try { return claimedFrom; } finally { lock.unlock(); } }
    /** Why it failed, or an empty string. */
    String reason() { lock.lock(); try { return reason; } finally { lock.unlock(); } }
    /** What we charge the merchant for this payment. */
    long feePaise() { lock.lock(); try { return feePaise; } finally { lock.unlock(); } }
    /** How much has actually moved. Zero until the payment is captured. */
    long capturedPaise() { lock.lock(); try { return capturedPaise; } finally { lock.unlock(); } }
    /** How much has been sent back and settled. */
    long refundedPaise() { lock.lock(); try { return refundedPaise; } finally { lock.unlock(); } }
    /** How much is promised to in-flight refunds but not yet settled. */
    long refundReservedPaise() { lock.lock(); try { return refundReservedPaise; } finally { lock.unlock(); } }
    /** What may still be refunded: captured minus settled minus reserved. The cap every refund is checked against. */
    long refundablePaise() {
        lock.lock();
        try { return capturedPaise - refundedPaise - refundReservedPaise; } finally { lock.unlock(); }
    }
    /** When the state last changed. Used by the reconciliation job to find calls that have been in flight too long. */
    long lastChangeMs() { lock.lock(); try { return lastChangeMs; } finally { lock.unlock(); } }

    /**
     * THE compare-and-set. Move from `expected` to `claimed` if and only if the payment is still in `expected`, and
     * remember what we claimed from and under which key. Exactly one caller can win; everyone else gets false and
     * opens no socket. This is the whole of "the customer is charged once".
     */
    boolean claim(PaymentState expected, PaymentState claimed, String acquirerName, long fee, String callKey, long nowMs) {
        lock.lock();
        try {
            if (state != expected || !state.canGoTo(claimed)) return false;
            claimedFrom = state; state = claimed;
            acquirer = acquirerName; feePaise = fee; inFlightKey = callKey; lastChangeMs = nowMs;
            return true;
        } finally { lock.unlock(); }
    }

    /**
     * The ONE method that records an outcome, used by the acquirer's answer and by its webhook alike -- which is
     * why an out-of-order webhook costs nothing. It applies only if the outcome is a legal next move AND its rank
     * beats the highest rank this payment has reached. A duplicate, a late "authorized" after a capture and a
     * replayed callback are all silently dropped. Returns true if anything changed.
     */
    boolean settle(PaymentState outcome, String ref, String why, long nowMs) {
        lock.lock();
        try {
            if (outcome.outcomeRank() <= rankReached) return false;      // a report of an older truth
            if (!state.canGoTo(outcome)) return false;                   // an edge that does not exist
            state = outcome; rankReached = outcome.outcomeRank(); lastChangeMs = nowMs;
            if (!ref.isEmpty()) acquirerRef = ref;
            reason = why;
            if (outcome == PaymentState.CAPTURED) capturedPaise = paise;
            claimedFrom = state; inFlightKey = "";
            return true;
        } finally { lock.unlock(); }
    }

    /**
     * The call was made and never answered. The payment becomes UNKNOWN, the claim is NOT handed back (so nothing
     * retries it blindly) and the rank is untouched (so the acquirer's eventual webhook still counts). Only the
     * status query or the reconciliation job may move it on from here.
     */
    boolean markUnknown(String why, long nowMs) {
        lock.lock();
        try {
            if (!state.canGoTo(PaymentState.UNKNOWN)) return false;
            state = PaymentState.UNKNOWN; reason = why; lastChangeMs = nowMs;
            return true;
        } finally { lock.unlock(); }
    }

    /**
     * Hand the claim back. Legal only when the call provably never reached the acquirer, or when the status query
     * has confirmed it never happened: the payment returns to exactly the state it was claimed from.
     */
    boolean revertClaim(String why, long nowMs) {
        lock.lock();
        try {
            if (!state.canGoTo(claimedFrom)) return false;
            state = claimedFrom; reason = why; inFlightKey = ""; lastChangeMs = nowMs;
            return true;
        } finally { lock.unlock(); }
    }

    /**
     * Promise this much of the captured money to a refund that is about to be attempted. The check and the write
     * are one step under the lock, which is the point: two refunds decided from the same read would together
     * exceed what was captured. Returns false if there is not enough left.
     */
    boolean reserveRefund(long amount) {
        lock.lock();
        try {
            if (state != PaymentState.CAPTURED && state != PaymentState.PARTIALLY_REFUNDED) return false;
            if (amount <= 0 || capturedPaise - refundedPaise - refundReservedPaise < amount) return false;
            refundReservedPaise += amount;
            return true;
        } finally { lock.unlock(); }
    }
    /** The refund was refused or never left: give the promise back so the money can be refunded by someone else. */
    void releaseRefund(long amount) {
        lock.lock();
        try { refundReservedPaise -= amount; } finally { lock.unlock(); }
    }
    /** The acquirer sent it back: turn the promise into a fact and move the payment along its life. */
    void settleRefund(long amount, long nowMs) {
        lock.lock();
        try {
            refundReservedPaise -= amount; refundedPaise += amount; lastChangeMs = nowMs;
            PaymentState next = refundedPaise >= capturedPaise ? PaymentState.REFUNDED : PaymentState.PARTIALLY_REFUNDED;
            if (state.canGoTo(next)) { state = next; rankReached = Math.max(rankReached, next.outcomeRank()); }
        } finally { lock.unlock(); }
    }

    @Override public String toString() {
        lock.lock();
        try {
            return id + " " + Money.fmt(paise) + " " + currency + " " + method + " " + state
                 + (acquirer.isEmpty() ? "" : " via " + acquirer)
                 + (capturedPaise > 0 ? " captured " + Money.fmt(capturedPaise) : "")
                 + (refundedPaise > 0 ? " refunded " + Money.fmt(refundedPaise) : "")
                 + (reason.isEmpty() ? "" : " (" + reason + ")");
        } finally { lock.unlock(); }
    }
}

/**
 * The gateway. It owns the registries, sequences one payment end to end, and decides no policy: routing, fees,
 * retries, risk rules, listeners and the clock are all handed in.
 *
 * The order at a payment IS the design, and it is this: claim the idempotency key with one putIfAbsent, which is
 * the compare-and-set that makes a retried request safe; run the risk rules and pick the route, both pure and both
 * outside every lock; take the payment's lock only long enough to move CREATED to PENDING, which claims the right
 * to call the acquirer; call the acquirer OUTSIDE the lock with a timeout, because that is the irreversible step
 * and nothing slow may sit inside a lock; take the lock again to record what it said; release; then tell the
 * merchant. Nothing is ever written as success before the acquirer says success, so a timeout leaves a payment
 * that says "ask again" instead of a payment that lies.
 */
class PaymentService {
    private final Map<String, Merchant> merchants = new ConcurrentHashMap<>();
    private final Map<String, Payment> byId = new ConcurrentHashMap<>();
    private final Map<String, Payment> byKey = new ConcurrentHashMap<>();          // idempotency key -> the one attempt
    private final Map<String, List<Payment>> byMerchant = new ConcurrentHashMap<>();
    private final Map<String, Refund> refundsById = new ConcurrentHashMap<>();
    private final Map<String, Refund> refundsByKey = new ConcurrentHashMap<>();
    private final Map<String, List<Refund>> refundsByPayment = new ConcurrentHashMap<>();
    private final Set<String> unresolved = ConcurrentHashMap.newKeySet();          // payments whose outcome is UNKNOWN
    private final List<PaymentProcessor> processors = new CopyOnWriteArrayList<>();
    private final Map<String, PaymentProcessor> byAcquirer = new ConcurrentHashMap<>();
    private final List<PaymentListener> listeners = new CopyOnWriteArrayList<>();
    private final AtomicLong nextId = new AtomicLong(1);

    private volatile RoutingPolicy routing = (t, c, paise, all) -> {
        List<PaymentProcessor> able = new ArrayList<>();
        for (PaymentProcessor p : all) if (p.supports(t, c)) able.add(p);
        return able;
    };
    private volatile FeePolicy fees = (paise, type, acquirer) -> 0;
    private volatile RetryPolicy retries = new RetrySafeFailuresOnly(2);
    private volatile List<RiskRule> riskRules = List.of();
    private volatile Clock clock = System::currentTimeMillis;

    /** Hand in the policy. The gateway never builds a rule, which is why a test can hand it a broken one. */
    void configure(RoutingPolicy routing, FeePolicy fees, RetryPolicy retries, List<RiskRule> riskRules) {
        this.routing = routing; this.fees = fees; this.retries = retries; this.riskRules = List.copyOf(riskRules);
    }
    /** Tests hand in a fixed clock, so "seven days old" is whatever the test says it is. */
    void setClock(Clock c) { clock = c; }
    /** Add an acquirer. Order does not matter: the routing policy decides who is tried and in what order. */
    void addProcessor(PaymentProcessor p) { processors.add(p); byAcquirer.put(p.name(), p); }
    /** Subscribe a listener. Setup only; listeners are called after every lock is released. */
    void addListener(PaymentListener l) { listeners.add(l); }
    /** Register a merchant. O(1). */
    void register(Merchant m) { merchants.put(m.id(), m); }
    /** The merchant, or an error. O(1). */
    Merchant merchant(String id) {
        Merchant m = merchants.get(id);
        if (m == null) throw new NoSuchElementException("no such merchant: " + id);
        return m;
    }
    /** One payment by our id. O(1). */
    Payment payment(String id) {
        Payment p = byId.get(id);
        if (p == null) throw new NoSuchElementException("no such payment: " + id);
        return p;
    }
    /** The one attempt behind an idempotency key, if there is one. O(1). */
    Payment byKey(String idemKey) { return byKey.get(idemKey); }
    /** One refund by our id. O(1). */
    Refund refundById(String id) {
        Refund r = refundsById.get(id);
        if (r == null) throw new NoSuchElementException("no such refund: " + id);
        return r;
    }
    /** Every payment of one merchant, newest last. O(1) to find the list, never a scan of every payment. */
    List<Payment> paymentsOf(String merchantId) { return List.copyOf(byMerchant.getOrDefault(merchantId, List.of())); }
    /** Every refund of one payment. O(1) to find the list. */
    List<Refund> refundsOf(String paymentId) { return List.copyOf(refundsByPayment.getOrDefault(paymentId, List.of())); }
    /** The payments whose outcome we do not know. Maintained as they happen, so the job never scans. */
    Set<String> unresolved() { return Set.copyOf(unresolved); }

    /**
     * Take a payment. Idempotent by key: the same key always yields the very same Payment object, whatever happened
     * to it, so a retried HTTP request cannot charge twice. Never throws for a business outcome -- a decline, a
     * risk refusal and a missing route all come back as a Payment you can read the state of.
     */
    Payment pay(String idemKey, String merchantId, long paise, Currency currency, PaymentMethod method) {
        if (paise <= 0) throw new IllegalArgumentException("amount must be positive: " + paise);
        merchant(merchantId);                                            // unknown merchant is a caller error
        Payment seen = byKey.get(idemKey);
        if (seen != null) return seen;                                   // fast path: an obvious retry, no id burned
        long now = clock.nowMs();

        Payment fresh = new Payment("pay_" + nextId.getAndIncrement(), idemKey, merchantId, paise, currency, method, now);
        Payment prior = byKey.putIfAbsent(idemKey, fresh);               // THE compare-and-set: one key, one attempt
        if (prior != null) return prior;
        byId.put(fresh.id(), fresh);
        byMerchant.computeIfAbsent(merchantId, k -> new CopyOnWriteArrayList<>()).add(fresh);

        try {
            for (RiskRule r : riskRules) r.check(merchantId, paise, method, now);   // pure, no lock, no network
        } catch (PaymentRejected refusal) {
            fresh.settle(PaymentState.FAILED, "", refusal.getMessage(), now);
            publish(fresh);
            return fresh;
        }
        List<PaymentProcessor> route = routing.route(method.type(), currency, paise, processors);
        if (route.isEmpty()) {
            fresh.settle(PaymentState.FAILED, "", "no acquirer takes " + method.type() + " in " + currency, now);
            publish(fresh);
            return fresh;
        }
        authorizeAlong(fresh, route);
        publish(fresh);
        return fresh;
    }

    /**
     * Walk the route until one acquirer answers. A ProcessorUnavailable means the call never left the building, so
     * the claim is handed back and the next acquirer is tried. A ProcessorTimeout means the opposite: the money may
     * have moved, so we stop, mark the payment UNKNOWN and let the status query settle it. That single distinction
     * is the difference between a gateway and a double-charging machine.
     */
    private void authorizeAlong(Payment p, List<PaymentProcessor> route) {
        RuntimeException last = null;
        for (int i = 0; i < route.size(); i++) {
            PaymentProcessor acquirer = route.get(i);
            long fee = fees.feeFor(p.paise(), p.method().type(), acquirer);
            long now = clock.nowMs();
            if (!p.claim(PaymentState.CREATED, PaymentState.PENDING, acquirer.name(), fee, p.id(), now)) return;
            try {
                ProcessorResult r = acquirer.authorize(p.id(), p.paise(), p.currency(), p.method());  // OUTSIDE the lock
                switch (r.outcome()) {
                    case CAPTURED -> p.settle(PaymentState.CAPTURED, r.ref(), "", clock.nowMs());
                    case AUTHORIZED -> p.settle(PaymentState.AUTHORIZED, r.ref(), "", clock.nowMs());
                    default -> p.settle(PaymentState.FAILED, r.ref(), r.reason(), clock.nowMs());
                }
                return;
            } catch (ProcessorTimeout t) {
                p.markUnknown("timeout at " + acquirer.name() + ": " + t.getMessage(), clock.nowMs());
                unresolved.add(p.id());
                return;                                                  // never fail over after a timeout
            } catch (ProcessorUnavailable u) {
                last = u;
                p.revertClaim(acquirer.name() + " unavailable: " + u.getMessage(), clock.nowMs());
                if (!retries.retry(i + 1, u)) break;
            }
        }
        p.settle(PaymentState.FAILED, "", last == null ? "no acquirer accepted it" : last.getMessage(), clock.nowMs());
    }

    /**
     * Move an authorized payment's money. The same shape as pay(): claim AUTHORIZED to PENDING under the lock, call
     * the acquirer outside it, record the answer. A declined capture does NOT void the authorization -- the claim
     * is handed back and the merchant may try again before the authorization expires.
     */
    Payment capture(String paymentId) {
        Payment p = payment(paymentId);
        PaymentProcessor acquirer = byAcquirer.get(p.acquirer());
        if (acquirer == null) return p;
        String key = p.id() + ":cap";
        if (!p.claim(PaymentState.AUTHORIZED, PaymentState.PENDING, acquirer.name(), p.feePaise(), key, clock.nowMs()))
            return p;                                                    // not authorized, or someone already has it
        try {
            ProcessorResult r = acquirer.capture(key, p.acquirerRef(), p.paise());   // OUTSIDE the lock
            if (r.outcome() == Outcome.CAPTURED) p.settle(PaymentState.CAPTURED, r.ref(), "", clock.nowMs());
            else p.revertClaim(r.reason(), clock.nowMs());
        } catch (ProcessorTimeout t) {
            p.markUnknown("capture timeout at " + acquirer.name(), clock.nowMs());
            unresolved.add(p.id());
        } catch (ProcessorUnavailable u) {
            p.revertClaim(acquirer.name() + " unavailable: " + u.getMessage(), clock.nowMs());
        }
        publish(p);
        return p;
    }

    /**
     * Send some of a captured payment back. Reserve-then-settle: the amount is promised under the payment's lock
     * BEFORE the acquirer is called, and turned into a fact only when the acquirer says yes. A single counter
     * updated after the call would let two refunds decided from the same read together exceed what was captured.
     * Idempotent by its own key, like every other write.
     */
    Refund refund(String refundKey, String paymentId, long paise) {
        if (paise <= 0) throw new IllegalArgumentException("refund must be positive: " + paise);
        Payment p = payment(paymentId);
        Refund seen = refundsByKey.get(refundKey);
        if (seen != null) return seen;
        long now = clock.nowMs();
        Refund fresh = new Refund("rfnd_" + nextId.getAndIncrement(), refundKey, paymentId, paise, now);
        Refund prior = refundsByKey.putIfAbsent(refundKey, fresh);
        if (prior != null) return prior;
        refundsById.put(fresh.id(), fresh);
        refundsByPayment.computeIfAbsent(paymentId, k -> new CopyOnWriteArrayList<>()).add(fresh);

        if (!p.reserveRefund(paise)) {                                    // check and write as ONE step
            fresh.fail("cannot refund " + Money.fmt(paise) + " of " + p.id() + ": it is " + p.state()
                     + " with " + Money.fmt(p.refundablePaise()) + " refundable");
            return fresh;
        }
        PaymentProcessor acquirer = byAcquirer.get(p.acquirer());
        try {
            ProcessorResult r = acquirer.refund(fresh.id(), p.acquirerRef(), paise);  // OUTSIDE the lock
            if (r.outcome() == Outcome.REFUNDED) { p.settleRefund(paise, clock.nowMs()); fresh.succeed(r.ref()); }
            else { p.releaseRefund(paise); fresh.fail(r.reason()); }
        } catch (ProcessorTimeout t) {
            fresh.unknown("timeout at " + acquirer.name());               // the reservation STAYS held
        } catch (ProcessorUnavailable u) {
            p.releaseRefund(paise); fresh.fail(u.getMessage());
        }
        publish(p);
        return fresh;
    }

    /**
     * An acquirer calls us back. Delivery is at-least-once and out of order, and neither matters: this is the same
     * settle() the response path uses, so a duplicate loses on rank and a late "authorized" after a capture is
     * dropped. Returns true if the report changed anything.
     */
    boolean handleWebhook(String paymentId, PaymentState reported, String acquirerRef, long atMs) {
        Payment p = byId.get(paymentId);
        if (p == null) return false;                                      // a callback for something we never sent
        if (reported.outcomeRank() == 0) return false;                    // a webhook only ever reports an outcome
        boolean changed = p.settle(reported, acquirerRef, "", atMs);
        if (changed) { unresolved.remove(paymentId); publish(p); }
        return changed;
    }

    /**
     * The only honest way out of an UNKNOWN: ask the acquirer what happened to the exact key we sent. NOT_FOUND
     * means it never saw the request, so the claim is handed back (a capture) or the payment fails (an authorize).
     * Safe to call as often as you like -- settle() is rank-guarded, so a second answer changes nothing.
     */
    boolean resolveUnknown(String paymentId) {
        Payment p = payment(paymentId);
        if (p.state() != PaymentState.UNKNOWN) { unresolved.remove(paymentId); return false; }
        PaymentProcessor acquirer = byAcquirer.get(p.acquirer());
        if (acquirer == null) return false;
        ProcessorResult r;
        try { r = acquirer.statusOf(p.inFlightKey()); }
        catch (RuntimeException e) { return false; }                      // still down: the job will come back
        long now = clock.nowMs();
        boolean settled = switch (r.outcome()) {
            case CAPTURED -> p.settle(PaymentState.CAPTURED, r.ref(), "", now);
            case AUTHORIZED -> p.settle(PaymentState.AUTHORIZED, r.ref(), "", now);
            case DECLINED, NOT_FOUND -> p.claimedFrom() == PaymentState.CREATED
                    ? p.settle(PaymentState.FAILED, "", "the acquirer never took it: " + r.reason(), now)
                    : p.revertClaim("the capture never reached the acquirer", now);
            default -> false;
        };
        if (settled) { unresolved.remove(paymentId); publish(p); }
        return settled;
    }

    /**
     * The job that closes the books. It finishes every payment whose outcome has been unknown for longer than
     * staleMs by asking the acquirer, then checks the one invariant that must hold for every payment: you can
     * never have sent back more than you took. Returns the number of payments it settled.
     */
    int reconcile(long staleMs) {
        int settled = 0;
        long now = clock.nowMs();
        for (String id : List.copyOf(unresolved)) {
            Payment p = byId.get(id);
            if (p != null && now - p.lastChangeMs() >= staleMs && resolveUnknown(id)) settled++;
        }
        for (Payment p : byId.values()) {
            if (p.capturedPaise() > p.paise())
                throw new IllegalStateException(p.id() + " captured more than it took");
            if (p.refundedPaise() + p.refundReservedPaise() > p.capturedPaise())
                throw new IllegalStateException(p.id() + " refunded more than it captured");
        }
        return settled;
    }

    /**
     * What this merchant is owed: everything captured, less everything refunded, less our fees. O(k) over that
     * merchant's own payments off the index, never a scan of the whole gateway.
     */
    long settlementOf(String merchantId) {
        long total = 0;
        for (Payment p : byMerchant.getOrDefault(merchantId, List.of())) {
            if (p.capturedPaise() == 0) continue;
            total += p.capturedPaise() - p.refundedPaise() - p.feePaise();
        }
        return total;
    }

    /** Tell every listener, outside every lock, and survive one that throws. */
    private void publish(Payment p) {
        PaymentEvent e = new PaymentEvent(p.id(), p.merchantId(), p.state(), p.paise(), p.capturedPaise(),
                                          p.refundedPaise(), p.acquirer(), p.reason(), clock.nowMs());
        for (PaymentListener l : listeners) {
            try { l.onEvent(e); } catch (RuntimeException ex) { System.err.println("[listener failed] " + ex.getMessage()); }
        }
    }
}

/**
 * Proof it works: a card payment authorized then captured, a UPI payment captured in one step, a retried request,
 * a decline, a failover when the primary acquirer is down, a timeout that becomes UNKNOWN and is then closed by
 * the status query, partial refunds up to the cap and one paise past it, an out-of-order webhook -- and then fifty
 * threads sending the SAME idempotency key at once, with exactly one charge at the acquirer.
 */
public class Main {
    public static void main(String[] args) throws Exception {
        long[] now = { 1_700_000_000_000L };
        Clock clock = () -> now[0];

        CardAcquirer hdfc = new CardAcquirer("HDFC", 180, Currency.INR, Currency.USD);
        CardAcquirer axis = new CardAcquirer("AXIS", 220, Currency.INR);
        UpiSwitch npci = new UpiSwitch("NPCI", 0);

        PaymentService gw = new PaymentService();
        gw.setClock(clock);
        gw.addProcessor(new CircuitBreaker(hdfc, 3, 30_000, clock));
        gw.addProcessor(new CircuitBreaker(axis, 3, 30_000, clock));
        gw.addProcessor(new CircuitBreaker(npci, 3, 30_000, clock));
        gw.configure(new PreferredRouting(Map.of(PaymentMethodType.CARD, List.of("HDFC", "AXIS"),
                                                 PaymentMethodType.UPI, List.of("NPCI"))),
                     new BpsFee(Money.rupees("2.00")),
                     new RetrySafeFailuresOnly(2),
                     List.of(new AmountCapRule(Map.of(PaymentMethodType.CARD, Money.rupees("200000.00")))));

        Merchant shop = new Merchant("m_chai", "Chai Point", "https://chaipoint.example/hooks");
        gw.register(shop);
        MerchantWebhook hooks = new MerchantWebhook((url, e) -> true, 3);
        hooks.register(shop);
        gw.addListener(hooks);
        AuditLog audit = new AuditLog();
        gw.addListener(audit);

        PaymentMethod card = new PaymentMethod(PaymentMethodType.CARD, "tok_visa_9f21", "**** 1111");
        PaymentMethod upi  = new PaymentMethod(PaymentMethodType.UPI, "harish@okhdfc", "harish@okhdfc");

        // a card payment: authorize reserves, capture moves it
        Payment p1 = gw.pay("ord-1001", "m_chai", Money.rupees("1000.00"), Currency.INR, card);
        System.out.println("authorized: " + p1);
        gw.capture(p1.id());
        System.out.println("captured:   " + p1 + "  fee " + Money.fmt(p1.feePaise()));

        // UPI has no auth/capture split; the flow does not notice
        Payment p2 = gw.pay("ord-1002", "m_chai", Money.rupees("240.00"), Currency.INR, upi);
        System.out.println("upi:        " + p2);

        // the same request twice (a phone on a bad network): one charge, the same payment back
        Payment again = gw.pay("ord-1001", "m_chai", Money.rupees("1000.00"), Currency.INR, card);
        System.out.println("retry of ord-1001 returned the same payment: " + (again == p1)
            + ", HDFC saw " + hdfc.calls() + " requests (one authorize, one capture -- the retry made none)");

        // a decline is an answer, not a failure: FAILED, nothing captured
        hdfc.mode(VendorMode.DECLINE);
        Payment p3 = gw.pay("ord-1003", "m_chai", Money.rupees("500.00"), Currency.INR, card);
        System.out.println("declined:   " + p3);
        hdfc.mode(VendorMode.HEALTHY);

        // the primary acquirer refuses the connection: nothing was charged, so the route fails over to AXIS
        hdfc.mode(VendorMode.DOWN);
        Payment p4 = gw.pay("ord-1004", "m_chai", Money.rupees("750.00"), Currency.INR, card);
        System.out.println("failover:   " + p4);
        hdfc.mode(VendorMode.HEALTHY);

        // the acquirer takes the money and then the socket dies: UNKNOWN, and NOT retried
        npci.mode(VendorMode.TIMEOUT_CHARGED);
        Payment p5 = gw.pay("ord-1005", "m_chai", Money.rupees("99.00"), Currency.INR, upi);
        System.out.println("timeout:    " + p5 + "   unresolved=" + gw.unresolved());
        npci.mode(VendorMode.HEALTHY);
        now[0] += 60_000;                                   // an hour of the job's patience, in one line
        System.out.println("reconciled " + gw.reconcile(30_000) + " payment(s); now: " + p5);

        // refunds: part of it, the rest of it, then one paise too far
        System.out.println("refund 300: " + gw.refund("rf-1", p1.id(), Money.rupees("300.00")) + " -> " + p1.state());
        System.out.println("refund 700: " + gw.refund("rf-2", p1.id(), Money.rupees("700.00")) + " -> " + p1.state());
        System.out.println("one paise more: " + gw.refund("rf-3", p1.id(), 1));

        // a webhook that arrives late and out of order is dropped on rank
        boolean changed = gw.handleWebhook(p1.id(), PaymentState.AUTHORIZED, "hdfc_late", now[0]);
        System.out.println("late 'authorized' webhook after a refund changed anything: " + changed + ", still " + p1.state());

        System.out.println("settlement for " + shop.name() + ": " + Money.fmt(gw.settlementOf("m_chai")));
        System.out.println("webhooks delivered: " + hooks.delivered() + ", audit lines: " + audit.events().size());

        // fifty threads, one idempotency key, at the same instant: exactly one charge
        CardAcquirer solo = new CardAcquirer("SOLO", 200, Currency.INR);
        PaymentService busy = new PaymentService();
        busy.setClock(clock);
        busy.addProcessor(solo);
        busy.configure(new PreferredRouting(Map.of(PaymentMethodType.CARD, List.of("SOLO"))),
                       new BpsFee(0), new RetrySafeFailuresOnly(2), List.of());
        busy.register(new Merchant("m_x", "X", "https://x.example/hooks"));

        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<String>> sent = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            sent.add(pool.submit(() -> {
                go.await();
                return busy.pay("ord-RACE", "m_x", Money.rupees("1000.00"), Currency.INR, card).id();
            }));
        }
        go.countDown();
        Set<String> ids = new HashSet<>();
        for (Future<String> f : sent) ids.add(f.get(10, TimeUnit.SECONDS));
        pool.shutdown();
        System.out.println("50 threads, one key: distinct payments=" + ids.size()
            + ", requests that reached the acquirer=" + solo.calls()
            + ", state=" + busy.byKey("ord-RACE").state());
        if (ids.size() != 1 || solo.calls() != 1) throw new AssertionError("the customer was charged more than once");
    }
}
