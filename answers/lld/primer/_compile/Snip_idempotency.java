import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_idempotency {
static class PaymentService {
    private final java.util.concurrent.ConcurrentHashMap<String, String> results = new java.util.concurrent.ConcurrentHashMap<>();
    String pay(String idempotencyKey, long paise) {
        if (paise <= 0) throw new IllegalArgumentException("amount");            // fail fast
        String prior = results.putIfAbsent(idempotencyKey, "PENDING");
        if (prior != null) return prior;                                       // retry: return the first outcome
        String result = "PAID:" + paise;                                       // charge once
        results.put(idempotencyKey, result);
        return result;
    }
}
static final class Ticket {
    private boolean closed;
    synchronized void close() { if (closed) throw new IllegalStateException("already closed"); closed = true; }   // invariant lives here
}
}
