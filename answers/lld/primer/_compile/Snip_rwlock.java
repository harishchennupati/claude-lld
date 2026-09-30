import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_rwlock {
static class ConfigCache {
    private final java.util.concurrent.locks.ReadWriteLock rw = new java.util.concurrent.locks.ReentrantReadWriteLock();
    private final java.util.Map<String, String> map = new java.util.HashMap<>();
    String get(String k) {
        rw.readLock().lock();
        try { return map.get(k); } finally { rw.readLock().unlock(); }
    }
    void put(String k, String v) {
        rw.writeLock().lock();
        try { map.put(k, v); } finally { rw.writeLock().unlock(); }
    }
}
static class SnapshotCache {                                // lock-free reads: swap an immutable map
    private volatile java.util.Map<String, String> snap = java.util.Map.of();
    String get(String k) { return snap.get(k); }
    void replaceAll(java.util.Map<String, String> m) { snap = java.util.Map.copyOf(m); }
}
}
