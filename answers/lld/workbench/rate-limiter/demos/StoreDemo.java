import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

// 16 threads meet a new customer at the same instant: they must all get one counter.
public class StoreDemo {
    public static void main(String[] args) throws InterruptedException {
        CounterStore store = new InMemoryCounterStore(Algorithm.TOKEN_BUCKET);
        List<Counter> seen = new CopyOnWriteArrayList<>();
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        for (int t = 0; t < 16; t++) {
            pool.submit(() -> {
                start.await();
                seen.add(store.counterFor("news-app", Limit.perSecond(5), 0));
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);
        long distinct = seen.stream().distinct().count();
        System.out.println("16 threads asked for news-app's counter: " + distinct + " counter");
        Check.that(distinct == 1, "one counter per key");
    }
}
