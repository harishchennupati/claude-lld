import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_observer {
interface Listener<E> { void on(E event); }
static class EventBus<E> {
    private final java.util.List<Listener<E>> ls = new java.util.concurrent.CopyOnWriteArrayList<>();
    void subscribe(Listener<E> l) { ls.add(l); }
    void publish(E e) { for (Listener<E> l : ls) l.on(e); }   // iterate a snapshot; safe against concurrent subscribe
}
record Occupancy(String floor, int free) {}
static class Floor {
    final EventBus<Occupancy> bus = new EventBus<>();
    private int free = 10;
    void occupy() { int f; synchronized (this) { f = --free; } bus.publish(new Occupancy("F1", f)); }   // publish outside the lock
}
}
