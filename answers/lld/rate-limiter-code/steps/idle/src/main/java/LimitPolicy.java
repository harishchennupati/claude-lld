// How much a rule allows for this request: a fixed limit, or one from the customer's plan.
// One method, so a new way of setting limits is a new class and the limiter never changes.
interface LimitPolicy {
    Limit limitFor(Request request);
}
