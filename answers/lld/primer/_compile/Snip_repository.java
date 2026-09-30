import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_repository {
record Seat(String id) {}
static final class Booking { final String id, seatId, userId; Booking(String id, String s, String u) { this.id = id; seatId = s; userId = u; } }
interface BookingRepo { java.util.Optional<Booking> bySeat(String seatId); void save(Booking b); }
static class InMemoryBookingRepo implements BookingRepo {
    private final java.util.Map<String, Booking> bySeat = new java.util.concurrent.ConcurrentHashMap<>();
    public java.util.Optional<Booking> bySeat(String s) { return java.util.Optional.ofNullable(bySeat.get(s)); }
    public void save(Booking b) { if (bySeat.putIfAbsent(b.seatId, b) != null) throw new IllegalStateException("seat taken"); }
}
static class BookingService {
    private final BookingRepo repo; private final java.util.concurrent.atomic.AtomicLong ids = new java.util.concurrent.atomic.AtomicLong();
    BookingService(BookingRepo repo) { this.repo = repo; }
    Booking book(Seat seat, String user) { Booking b = new Booking("b" + ids.incrementAndGet(), seat.id(), user); repo.save(b); return b; }
}
}
