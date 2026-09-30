import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * One targeted test per claim the design makes on page 02. Each block is a failure a reviewer found on some
 * rate limiter somewhere; all of them must now pass. Run: javac Main.java Extensions.java FailureTests.java
 * &amp;&amp; java FailureTests
 */
public class FailureTests {
    static int failures = 0;
    /** Print one claim and remember whether it held. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }
    /** Try n calls of cost 1 on one key at the current instant; count the ones admitted. */
    static int admitted(Limiter l, String key, int n) {
        int ok = 0;
        for (int i = 0; i < n; i++) if (l.allow(key, 1).allowed()) ok++;
        return ok;
    }

    public static void main(String[] args) throws Exception {

        // 1. burst then refill, on an injected clock: no Thread.sleep anywhere in this suite
        ManualClock clock = new ManualClock(0);
        RateLimiter limiter = new RateLimiter();
        limiter.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), clock);
        int burst = 0;
        for (int i = 0; i < 5; i++) if (limiter.allow("acme").allowed()) burst++;
        Decision sixth = limiter.allow("acme");
        check(burst == 5, "the burst of five is admitted");
        check(!sixth.allowed(), "the sixth call in the same millisecond is refused");
        check(sixth.retryAfterMs() == 200, "it is told to come back in " + sixth.retryAfterMs() + "ms, not to retry now");
        clock.advance(200);
        check(limiter.allow("acme").allowed(), "200ms later exactly one permit exists, and it is granted");
        check(!limiter.allow("acme").allowed(), "and only one: the second call at that instant is refused");

        // 2. the fixed window doubles the limit at the boundary; the sliding counter does not
        ManualClock fw = new ManualClock(0);
        RateLimiter fixed = new RateLimiter();
        fixed.configure(new FixedWindow(), new FlatRules(new Rule(5, 1_000L, 5)), fw);
        fw.advance(900);
        int before = 0;
        for (int i = 0; i < 5; i++) if (fixed.allow("k").allowed()) before++;
        fw.advance(100);                                    // the first millisecond of the next window
        int after = 0;
        for (int i = 0; i < 5; i++) if (fixed.allow("k").allowed()) after++;
        check(before + after == 10, "fixed window: " + (before + after) + " calls in 100ms on a limit of 5 per second");

        ManualClock sw = new ManualClock(0);
        RateLimiter sliding = new RateLimiter();
        sliding.configure(new SlidingWindowCounter(), new FlatRules(new Rule(5, 1_000L, 5)), sw);
        sw.advance(900);
        int sBefore = 0;
        for (int i = 0; i < 5; i++) if (sliding.allow("k").allowed()) sBefore++;
        sw.advance(100);
        int sAfter = 0;
        for (int i = 0; i < 5; i++) if (sliding.allow("k").allowed()) sAfter++;
        check(sBefore == 5 && sAfter == 0, "sliding counter: " + (sBefore + sAfter) + " over the same boundary");

        // 3. a hundred threads, one key, one instant: exactly the limit gets through
        ManualClock frozen = new ManualClock(0);
        RateLimiter hot = new RateLimiter();
        hot.configure(new TokenBucket(), new FlatRules(new Rule(50, 1_000L, 50)), frozen);
        CountDownLatch start = new CountDownLatch(1), done = new CountDownLatch(100);
        AtomicInteger admitted = new AtomicInteger();
        ExecutorService pool = Executors.newFixedThreadPool(32);
        for (int i = 0; i < 100; i++) pool.submit(() -> {
            try { start.await(); if (hot.allow("hot").allowed()) admitted.incrementAndGet(); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            finally { done.countDown(); }
        });
        start.countDown();
        done.await();
        pool.shutdown();
        check(admitted.get() == 50, "100 threads on one key, limit 50: exactly " + admitted.get() + " admitted");
        check(hot.remaining("hot") == 0, "and the bucket is empty afterwards, not negative");

        // 4. a key nobody has seen starts with a full burst, and keys never share a budget
        check(limiter.remaining("never-seen") == 5, "an unknown key reports a full burst without being created");
        check(limiter.size() == 1, "and asking about it did not create a state for it");
        RateLimiter two = new RateLimiter();
        ManualClock tc = new ManualClock(0);
        two.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), tc);
        for (int i = 0; i < 5; i++) two.allow("alice");
        check(!two.allow("alice").allowed() && two.allow("bob").allowed(), "alice is out of permits; bob is untouched");

        // 5. a clock that goes backwards must not mint permits
        ManualClock back = new ManualClock(10_000);
        RateLimiter b = new RateLimiter();
        b.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), back);
        for (int i = 0; i < 5; i++) b.allow("k");
        back.advance(-5_000);                               // NTP drags the wall clock back five seconds
        check(!b.allow("k").allowed(), "no permit is minted while the clock is behind");
        back.advance(5_000);                                // and back to where it was
        check(!b.allow("k").allowed(), "and none is minted for the time the clock travelled twice");
        back.advance(200);
        check(b.allow("k").allowed(), "real elapsed time still mints normally afterwards");

        // 6. the sweeper drops only idle keys, and dropping one loses nothing
        ManualClock sc = new ManualClock(0);
        RateLimiter sweepable = new RateLimiter();
        sweepable.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), sc);
        for (int i = 0; i < 5; i++) sweepable.allow("idle");
        sc.advance(90_000);
        sweepable.allow("live");
        check(sweepable.sweepIdle(60_000) == 1 && sweepable.size() == 1, "the idle key is dropped, the live one is kept");
        check(sweepable.remaining("idle") == 5, "the dropped key is back at a full burst - which it had refilled to anyway");
        check(sweepable.remaining("live") == 4, "the live key kept the permit it spent");

        // 7. a metrics listener that throws cannot break a decision
        ManualClock oc = new ManualClock(0);
        RateLimiter obs = new RateLimiter();
        obs.configure(new TokenBucket(), new FlatRules(new Rule(3, 1_000L, 3)), oc);
        obs.addObserver((k, d) -> { throw new RuntimeException("the metrics sidecar is down"); });
        MetricsCounter good = new MetricsCounter();
        obs.addObserver(good);
        int through = 0;
        for (int i = 0; i < 5; i++) if (obs.allow("k").allowed()) through++;
        check(through == 3, "three admitted although the first listener throws on every call");
        check(good.allowed() == 3 && good.refused() == 2, "and the listener after the broken one still heard all five");

        // 8. permits are never minted: a refund stops at the burst, and a lowered burst clamps the bucket down
        ManualClock rc = new ManualClock(0);
        RateLimiter r = new RateLimiter();
        r.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), rc);
        for (int i = 0; i < 5; i++) r.allow("k");
        r.refund("k", 3);
        check(r.remaining("k") == 3, "three permits given back after three calls that never happened");
        r.refund("k", 100);
        check(r.remaining("k") == 5, "a refund of a hundred still leaves the burst of five, not a hundred");
        TierRules live = new TierRules(Rule.perMinute(600, 100));
        RateLimiter sale = new RateLimiter();
        sale.configure(new TokenBucket(), live, new ManualClock(0));
        check(sale.allow("acme").remaining() == 99, "a key on a 600-a-minute plan starts at a burst of 100");
        live.setRule(Tier.FREE, Rule.perMinute(60, 10));    // ops lowers the plan while the process runs
        check(sale.allow("acme").remaining() == 9, "the burst drops to 10 on the next decision, and the held tokens drop with it");

        // 9. the leaky bucket is not a different answer: GCRA admits exactly what the token bucket admits,
        //    at 10 a second (100 ms a permit) and at 3 a second (333 1/3 ms, where any rounding would show)
        for (Rule same : List.of(new Rule(10, 1_000L, 5), new Rule(3, 1_000L, 3))) {
            ManualClock tbc = new ManualClock(0), gc = new ManualClock(0);
            RateLimiter tb = new RateLimiter(), gcra = new RateLimiter();
            tb.configure(new TokenBucket(), new FlatRules(same), tbc);
            gcra.configure(new Gcra(), new FlatRules(same), gc);
            StringBuilder tbRun = new StringBuilder(), gcraRun = new StringBuilder();
            for (long jump : new long[] { 0, 100, 234, 332, 1, 1_000 }) {   // the clock jumps, then 8 calls at once
                tbc.advance(jump); gc.advance(jump);
                for (int i = 0; i < 8; i++) {
                    tbRun.append(tb.allow("k").allowed() ? '1' : '0');
                    gcraRun.append(gcra.allow("k").allowed() ? '1' : '0');
                }
            }
            check(tbRun.toString().equals(gcraRun.toString()), "gcra admits the same calls as the token bucket at "
                  + same.permits() + " a second: " + tbRun + " vs " + gcraRun);
        }

        // 10. a call bigger than the whole bucket is refused for good; a refusal says what is really left
        RateLimiter big = new RateLimiter();
        big.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), new ManualClock(0));
        Decision huge = big.allow("k", 6);
        check(!huge.allowed() && huge.retryAfterMs() == Decision.NEVER,
              "a call costing 6 on a burst of 5 is refused for good, not told to wait");
        big.allow("k", 2);
        Decision heavy = big.allow("k", 4);
        check(!heavy.allowed() && heavy.remaining() == 3, "a refused call of 4 reports the 3 permits really left, not 0");

        // 11. an unknown key answers what a new key would have, whatever the algorithm
        RateLimiter perMin = new RateLimiter();
        perMin.configure(new FixedWindow(), new FlatRules(Rule.perMinute(60, 10)), new ManualClock(0));
        long unseen = perMin.remaining("never-seen");
        perMin.allow("seen");
        check(unseen == 60 && perMin.remaining("seen") == 59, "fixed window, 60 a minute: an unseen key has 60, not the burst of 10");

        // 12. Retry-After is the shortest wait that works, for the sliding counter and for the log
        ManualClock cc = new ManualClock(500);
        RateLimiter counter = new RateLimiter();
        counter.configure(new SlidingWindowCounter(), new FlatRules(new Rule(10, 1_000L, 10)), cc);
        admitted(counter, "k", 10);                                    // this window is full at 500 ms
        long wait = counter.allow("k").retryAfterMs();
        cc.advance(wait - 1);
        boolean early = counter.allow("k").allowed();
        cc.advance(1);
        check(wait == 600 && !early && counter.allow("k").allowed(),
              "sliding counter: told to wait " + wait + "ms; 1ms sooner is refused, at " + wait + "ms it is admitted");
        ManualClock lc = new ManualClock(0);
        RateLimiter log = new RateLimiter();
        log.configure(new SlidingWindowLog(), new FlatRules(new Rule(3, 1_000L, 3)), lc);
        log.allow("k"); lc.advance(100); log.allow("k"); lc.advance(100); log.allow("k");   // stamps at 0, 100, 200
        long waitTwo = log.allow("k", 2).retryAfterMs();               // a call of 2 needs the two oldest gone
        lc.advance(waitTwo);
        check(waitTwo == 900 && log.allow("k", 2).allowed(), "sliding log: a call costing 2 waits " + waitTwo + "ms, for the second-oldest stamp");

        // 13. the sweeper deletes a key between a caller's lookup and its lock: the caller's permit is not lost
        ManualClock rc2 = new ManualClock(0);
        RateLimiter swept = new RateLimiter();
        swept.configure(new TokenBucket(), new FlatRules(new Rule(5, 1_000L, 5)), rc2);
        swept.allow("k");
        rc2.advance(90_000);                                           // "k" has been idle for 90 s
        KeyState old = swept.stateOf("k");
        old.lock.lock();                                               // hold k's lock, so the caller stops at it
        Thread caller = new Thread(() -> swept.allow("k"));
        caller.start();
        long giveUp = System.nanoTime() + 5_000_000_000L;
        while (!old.lock.hasQueuedThreads() && System.nanoTime() < giveUp) Thread.onSpinWait();   // it found k, waits
        swept.sweepIdle(60_000);                                       // same thread, and the lock is re-entrant
        old.lock.unlock();
        caller.join();
        check(swept.remaining("k") == 4, "a key swept while a caller waited on its lock: the caller retried on a new state");

        // 14. compare-and-set: a thread that read the clock before another thread's swap mints nothing
        ManualClock stale = new ManualClock(1_000);
        CasBucket cas = new CasBucket(new Rule(5, 1_000L, 5), stale);
        admitted(cas, "k", 4);                                         // 1 left, measured at 1000 ms
        stale.advance(-1_000);                                         // this caller's clock reading is older
        cas.allow("k", 1);                                             // it takes the last permit
        stale.advance(1_000);                                          // back at 1000 ms: no real time has passed
        check(admitted(cas, "k", 5) == 0, "compare-and-set bucket: a stale clock read does not move the bucket's time back");

        // 15. twelve pods, one Redis: time comes from the server, so a pod whose clock is wrong changes nothing
        ManualClock server = new ManualClock(0);
        RedisLike shared = new RedisLike(server);
        Rule fleet = new Rule(5, 1_000L, 5);
        Limiter podA = new RedisTokenBucket(shared, fleet), podB = new RedisTokenBucket(shared, fleet);
        admitted(podA, "acme", 5);
        server.advance(200);                                           // one permit's worth of real time
        check(podB.allow("acme", 1).allowed() && !podA.allow("acme", 1).allowed(),
              "Redis's clock: 200ms later exactly one permit exists for the whole fleet, whichever pod asks");

        // 16. credits (Atlassian's follow-up): unused permits carry over, capped at burst - permits
        ManualClock wc = new ManualClock(0);
        RateLimiter credit = new RateLimiter();
        credit.configure(new CreditWindow(), new FlatRules(new Rule(5, 1_000L, 8)), wc);   // 5 a second, 3 saved at most
        int fresh = admitted(credit, "k", 10);                         // a new key: 5 plus a full bank of 3
        wc.advance(1_000);
        int afterBusy = admitted(credit, "k", 10);                     // the last second left nothing to save
        wc.advance(2_000);
        int afterQuiet = admitted(credit, "k", 10);                    // a quiet second saved 5, capped at 3
        check(fresh == 8 && afterBusy == 5 && afterQuiet == 8,
              "credits: " + fresh + " in a first second, " + afterBusy + " after a busy one, " + afterQuiet + " after a quiet one");

        // 17. the hit counter: every hit from four threads counted, forgotten 300 s later, late hits dropped
        HitCounter hc = new HitCounter();
        Thread[] hitters = new Thread[4];
        for (int t = 0; t < 4; t++) { hitters[t] = new Thread(() -> { for (int i = 0; i < 25_000; i++) hc.hit(100); }); hitters[t].start(); }
        for (Thread t : hitters) t.join();
        check(hc.getHits(100) == 100_000 && hc.getHits(399) == 100_000 && hc.getHits(400) == 0,
              "hit counter: 100,000 hits from 4 threads all counted, and gone 300 s later");
        hc.hit(400); hc.hit(100);                                      // 400 takes over slot 100; a late hit for 100
        check(hc.getHits(400) == 1, "a hit that arrives after its slot moved on is dropped, not added to the new second");

        System.out.println(failures == 0 ? "\nALL PASS" : "\n" + failures + " FAILED");
        if (failures > 0) System.exit(1);
    }
}
