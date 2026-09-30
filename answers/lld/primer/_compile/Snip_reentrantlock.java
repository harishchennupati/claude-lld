import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_reentrantlock {
static class ParkingLot {
    private final java.util.concurrent.locks.ReentrantLock lock = new java.util.concurrent.locks.ReentrantLock();
    String park(String plate) {
        lock.lock();
        try { return "spot for " + plate; }          // find + occupy + assign, atomic
        finally { lock.unlock(); }
    }
    boolean tryPark(String plate) throws InterruptedException {
        if (!lock.tryLock(200, java.util.concurrent.TimeUnit.MILLISECONDS)) return false;   // give up, do not queue
        try { return true; } finally { lock.unlock(); }
    }
}
}
