import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

// The store: the same key always gets the same bucket, even when 16 threads ask for a new key at
// the same instant.
public class StoreDemo {
    public static void main(String[] args) throws InterruptedException {
        InMemoryBucketStore store = new InMemoryBucketStore();
        Limit limit = Limit.perSecond(5);
        String key = "plan|news-app|5/1000ms";
        List<Bucket> seen = new CopyOnWriteArrayList<>();
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        for (int t = 0; t < 16; t++) {
            pool.submit(() -> {
                start.await();
                seen.add(store.bucketFor(key, Algorithm.TOKEN_BUCKET, limit, 0));
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        pool.awaitTermination(10, TimeUnit.SECONDS);
        long distinct = seen.stream().distinct().count();
        System.out.println("16 threads asked for one new key: " + seen.size() + " answers, "
                + distinct + " bucket");
        Bucket other = store.bucketFor("plan|cricket-blog|5/1000ms", Algorithm.TOKEN_BUCKET,
                limit, 0);
        System.out.println("another key, another bucket: " + (other != seen.get(0))
                + "; buckets in the store: " + store.size());
        Check.that(distinct == 1 && store.size() == 2, "one bucket per key");
    }
}
