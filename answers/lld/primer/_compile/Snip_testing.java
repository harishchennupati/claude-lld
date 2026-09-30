import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_testing {
void raceTest(java.util.concurrent.ExecutorService pool) throws Exception {
    java.util.concurrent.ConcurrentHashMap<String, String> seat = new java.util.concurrent.ConcurrentHashMap<>();
    java.util.concurrent.CountDownLatch go = new java.util.concurrent.CountDownLatch(1);
    java.util.concurrent.atomic.AtomicInteger wins = new java.util.concurrent.atomic.AtomicInteger();
    java.util.List<java.util.concurrent.Future<?>> fs = new java.util.ArrayList<>();
    for (int i = 0; i < 50; i++) { String u = "u" + i; fs.add(pool.submit(() -> { go.await(); if (seat.putIfAbsent("A1", u) == null) wins.incrementAndGet(); return null; })); }
    go.countDown();                                     // all 50 start together
    for (var f : fs) f.get();
    if (wins.get() != 1) throw new AssertionError("expected 1 winner, got " + wins.get());
}
}
