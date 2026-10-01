// How much a rule allows for one request. The config has two kinds of answer, a fixed limit
// or one taken from the customer's plan.
// Why an interface: the rule holds this promise and never knows which kind it has (Strategy). A
// third kind later (per region, or per plan and endpoint) is a third class; nothing else changes.
interface LimitPolicy {
    Limit limitFor(Request request);
}
