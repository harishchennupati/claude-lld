import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_threads {
java.util.concurrent.ExecutorService pool = java.util.concurrent.Executors.newFixedThreadPool(4);
int runAll(java.util.List<java.util.concurrent.Callable<Integer>> tasks) throws Exception {
    java.util.List<java.util.concurrent.Future<Integer>> fs = new java.util.ArrayList<>();
    for (var t : tasks) fs.add(pool.submit(t));
    int sum = 0;
    for (var f : fs) {
        try { sum += f.get(2, java.util.concurrent.TimeUnit.SECONDS); }
        catch (java.util.concurrent.ExecutionException e) { throw (Exception) e.getCause(); }
    }
    return sum;
}
void stop() throws InterruptedException {
    pool.shutdown();
    if (!pool.awaitTermination(5, java.util.concurrent.TimeUnit.SECONDS)) pool.shutdownNow();
}
}
