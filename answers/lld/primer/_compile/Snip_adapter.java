import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_adapter {
interface PaymentProcessor { boolean pay(long paise); }
static class StripeSdk { String charge(double dollars) { return "ok"; } }                 // foreign shape
static class StripeAdapter implements PaymentProcessor {
    private final StripeSdk sdk = new StripeSdk();
    public boolean pay(long paise) { return sdk.charge(paise / 100.0).equals("ok"); }
}
static class BookingFacade {                                                              // one call for the controller
    boolean book(String seat, String user, long paise) { return true; /* inventory, payment, notify */ }
}
static class RateLimitedProcessor implements PaymentProcessor {                          // proxy: same interface, gate in front
    private final PaymentProcessor real; private final java.util.concurrent.Semaphore permits = new java.util.concurrent.Semaphore(10);
    RateLimitedProcessor(PaymentProcessor real) { this.real = real; }
    public boolean pay(long p) { if (!permits.tryAcquire()) return false; try { return real.pay(p); } finally { permits.release(); } }
}
}
