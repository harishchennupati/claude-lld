import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_exceptions {
static class DomainException extends RuntimeException { DomainException(String m) { super(m); } }
static class InsufficientFundsException extends DomainException {
    final long shortBy;
    InsufficientFundsException(long shortBy) { super("short by " + shortBy); this.shortBy = shortBy; }
}
void withdraw(long balance, long amt) {
    if (amt <= 0) throw new IllegalArgumentException("amount must be positive");
    if (amt > balance) throw new InsufficientFundsException(amt - balance);
}
void sleepQuietly(long ms) {
    try { Thread.sleep(ms); }
    catch (InterruptedException e) { Thread.currentThread().interrupt(); }   // never swallow the interrupt
}
}
