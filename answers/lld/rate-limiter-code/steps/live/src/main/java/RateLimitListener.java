// Told about every decision after it is made: metrics, logs, alerts. The limiter does not know
// who listens (the Observer pattern), and a listener that throws must not break a request.
@FunctionalInterface
interface RateLimitListener {
    void onDecision(RequestContext request, RateLimitResult result);
}
