// How much a rule allows for one request. The config has two kinds of answer, a fixed limit or
// one taken from the customer's plan, and the rule must not care which it holds (Strategy).
// A third kind later (per region, or per plan and endpoint) is a third class; nothing else changes.
interface LimitPolicy {
    Limit limitFor(Request request);
}
