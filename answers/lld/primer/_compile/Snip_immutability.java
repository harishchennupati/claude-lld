import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_immutability {
static final class Snapshot { final java.util.Map<String, Integer> free; Snapshot(java.util.Map<String, Integer> f) { free = java.util.Map.copyOf(f); } }
static class Board {
    private volatile Snapshot latest = new Snapshot(java.util.Map.of());    // readers: one volatile read, no lock
    void publish(java.util.Map<String, Integer> free) { latest = new Snapshot(free); }
    int free(String size) { return latest.free.getOrDefault(size, 0); }
}
java.util.concurrent.CopyOnWriteArrayList<Runnable> listeners = new java.util.concurrent.CopyOnWriteArrayList<>();   // iterate freely, add rarely
static final ThreadLocal<StringBuilder> BUF = ThreadLocal.withInitial(StringBuilder::new);
}
