import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_semaphore {
java.util.concurrent.Semaphore permits = new java.util.concurrent.Semaphore(3);   // max 3 concurrent downloads
void download(String url) throws InterruptedException {
    permits.acquire();
    try { /* fetch */ } finally { permits.release(); }
}
int parallelSum(java.util.List<Integer> xs, java.util.concurrent.ExecutorService pool) throws InterruptedException {
    java.util.concurrent.CountDownLatch done = new java.util.concurrent.CountDownLatch(xs.size());
    java.util.concurrent.atomic.AtomicInteger sum = new java.util.concurrent.atomic.AtomicInteger();
    for (int x : xs) pool.submit(() -> { sum.addAndGet(x); done.countDown(); });
    done.await();                                     // wait until every task counted down
    return sum.get();
}
java.util.concurrent.CyclicBarrier bond = new java.util.concurrent.CyclicBarrier(3, () -> System.out.println("H2O"));
}
