import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

// The limiter the API calls. For each request: the rules that cover it, each rule's bucket for
// this request, and the request passes only if every bucket allows it. Counting is the buckets'
// job, where they live is the store's, which rules exist is the rule book's, and time is the
// clock's: all handed in, so none of them is hard-wired here.
class RuleBasedRateLimiter implements RateLimiter {
    //@ until live
    private final RuleBook rules;
    //@ end
    //@ from live
    // Ops can replace the rules while requests run: one write of this field. A request reads it
    // once, so it uses the old book or the new one, never half of each.
    private volatile RuleBook rules;
    //@ end
    private final BucketStore store;
    private final Clock clock;
    // Registered at startup, read on every request: a copy-on-write list needs no lock to read.
    private final List<RateLimitListener> listeners = new CopyOnWriteArrayList<>();

    RuleBasedRateLimiter(RuleBook rules, BucketStore store, Clock clock) {
        this.rules = rules;
        this.store = store;
        this.clock = clock;
    }

    void addListener(RateLimitListener listener) {
        listeners.add(listener);
    }
    //@ from live

    // New rules, no restart. Unchanged rules keep their buckets (same key); a changed limit is a
    // new key, so its buckets start fresh, and the old ones go in the next idle sweep.
    void replaceRules(RuleBook next) {
        rules = next;
    }
    //@ end

    @Override
    public RateLimitResult check(RequestContext request) {
        long now = clock.nowMillis();                     // one instant for every rule
        List<Bucket> charged = new ArrayList<>();
        long remaining = RateLimitResult.UNLIMITED;
        RateLimitResult result = null;
        //@ until live
        for (RateLimitRule rule : rules.matching(request)) {
        //@ end
        //@ from live
        RuleBook book = rules;                            // read once: one book per request
        for (RateLimitRule rule : book.matching(request)) {
        //@ end
            Bucket bucket = bucketFor(rule, request, now);
            Decision d = bucket.tryConsume(request.cost(), now);
            if (!d.allowed()) {
                // All or nothing: give back what the earlier rules took for this request.
                for (Bucket spent : charged) {
                    spent.refund(request.cost(), now);
                }
                result = RateLimitResult.refused(d, rule.name());
                break;
            }
            charged.add(bucket);
            remaining = Math.min(remaining, d.remaining());   // the tightest rule decides
        }
        if (result == null) {
            result = RateLimitResult.allowed(remaining);
        }
        tell(request, result);
        return result;
    }

    // A bucket key has three parts: the rule, whose budget, and the limit. With the limit in the
    // key, a client that upgrades from FREE to PRO gets a PRO bucket on its very next request.
    private Bucket bucketFor(RateLimitRule rule, RequestContext request, long now) {
        Limit limit = rule.limits().limitFor(request);
        String key = rule.name() + "|" + rule.scope().keyOf(request) + "|" + limit;
        return store.bucketFor(key, rule.algorithm(), limit, now);
    }

    // After the decision, holding no lock. A listener that throws is skipped: a broken
    // dashboard must never turn into a broken API.
    private void tell(RequestContext request, RateLimitResult result) {
        for (RateLimitListener listener : listeners) {
            try {
                listener.onDecision(request, result);
            } catch (RuntimeException broken) {
                // In production: log it. The request goes on either way.
            }
        }
    }
}
