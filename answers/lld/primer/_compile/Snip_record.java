import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_record {
record Money(long paise) {                     // integer minor units, never double
    Money { if (paise < 0) throw new IllegalArgumentException("negative"); }   // compact validator
    Money plus(Money o) { return new Money(paise + o.paise); }
}
record OrderPlaced(String orderId, Money total, long ts) {}    // an event: immutable, comparable by value
static final class Ticket {                            // pre-record style: final fields, no setters
    private final String id; private final long entryMs;
    Ticket(String id, long entryMs) { this.id = id; this.entryMs = entryMs; }
    String id() { return id; }
}
}
