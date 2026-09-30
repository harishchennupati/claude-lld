import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_atomic {
java.util.concurrent.atomic.AtomicInteger seq = new java.util.concurrent.atomic.AtomicInteger();
int nextId() { return seq.incrementAndGet(); }
java.util.concurrent.atomic.AtomicReference<String> occupant = new java.util.concurrent.atomic.AtomicReference<>();
boolean claimSpot(String plate) { return occupant.compareAndSet(null, plate); }   // wins or loses, no lock
java.util.concurrent.atomic.AtomicLong balance = new java.util.concurrent.atomic.AtomicLong(100);
boolean withdraw(long amt) {
    while (true) {                                   // the CAS loop
        long cur = balance.get();
        if (cur < amt) return false;
        if (balance.compareAndSet(cur, cur - amt)) return true;   // someone else moved it: retry
    }
}
}
