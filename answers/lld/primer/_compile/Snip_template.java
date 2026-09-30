import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_template {
static abstract class PaymentFlow {
    final boolean pay(long amt) { if (!validate(amt)) return false; boolean ok = charge(amt); record(amt, ok); return ok; }   // the template
    protected boolean validate(long amt) { return amt > 0; }
    protected abstract boolean charge(long amt);
    protected void record(long amt, boolean ok) {}
}
static class CardFlow extends PaymentFlow { protected boolean charge(long amt) { return true; } }
interface Handler { boolean handle(String req); }          // chain: first handler that returns true stops it
static class Pipeline {
    private final java.util.List<Handler> hs = new java.util.ArrayList<>();
    Pipeline add(Handler h) { hs.add(h); return this; }
    boolean run(String req) { for (Handler h : hs) if (h.handle(req)) return true; return false; }
}
}
