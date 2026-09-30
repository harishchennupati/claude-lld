import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_condition {
static class BoundedBuffer<T> {
    private final java.util.Deque<T> q = new java.util.ArrayDeque<>();
    private final int cap;
    private final java.util.concurrent.locks.ReentrantLock lock = new java.util.concurrent.locks.ReentrantLock();
    private final java.util.concurrent.locks.Condition notFull = lock.newCondition(), notEmpty = lock.newCondition();
    BoundedBuffer(int cap) { this.cap = cap; }
    void put(T x) throws InterruptedException {
        lock.lock();
        try { while (q.size() == cap) notFull.await(); q.addLast(x); notEmpty.signal(); }
        finally { lock.unlock(); }
    }
    T take() throws InterruptedException {
        lock.lock();
        try { while (q.isEmpty()) notEmpty.await(); T x = q.pollFirst(); notFull.signal(); return x; }
        finally { lock.unlock(); }
    }
}
}
