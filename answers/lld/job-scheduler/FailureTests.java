import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Sixteen claims the design makes, each proven by a few lines. Timing claims use a ManualClock and no
 * threads, so nothing sleeps; race claims use real threads. Run it with
 * javac Main.java Extensions.java FailureTests.java && java FailureTests
 * It prints ALL PASS, or each failure and a non-zero exit code.
 */
public class FailureTests {
    static int failed = 0;

    /** Record one claim. Prints ok or FAIL with the claim. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "  ok   " : "  FAIL ") + what);
        if (!ok) failed++;
    }

    /** Drive a scheduler by hand: at each step run everything due (again and again at the same instant), then move the clock. */
    static void drive(Scheduler s, ManualClock c, long untilMs, long stepMs) {
        while (c.nowMs() <= untilMs) {
            List<ScheduledJob> due;
            while (!(due = s.pollDue(c.nowMs())).isEmpty()) for (ScheduledJob j : due) s.runJob(j);
            c.advance(stepMs);
        }
    }

    /** The start times of a fixed-rate job whose second run takes 2,500 ms, under one misfire policy. */
    static List<Long> misfireStarts(Misfire m) {
        ManualClock c = new ManualClock(0);
        Scheduler s = new Scheduler(1, c);
        List<Long> starts = new ArrayList<>();
        s.schedule(JobSpec.of("report", () -> { starts.add(c.nowMs()); c.advance(starts.size() == 2 ? 2_500 : 100); })
                .every(new FixedRate(1_000)).misfire(m));
        drive(s, c, 4_000, 50);
        return starts;
    }

    public static void main(String[] args) throws Exception {
        // 1. due order: jobs leave in time order, and never before their time
        System.out.println("1. due order");
        ManualClock c1 = new ManualClock(0);
        Scheduler s1 = new Scheduler(1, c1);
        List<String> order1 = new ArrayList<>();
        s1.schedule(JobSpec.of("c", () -> order1.add("c")).in(300));
        s1.schedule(JobSpec.of("a", () -> order1.add("a")).in(100));
        s1.schedule(JobSpec.of("b", () -> order1.add("b")).in(200));
        s1.schedule(JobSpec.of("b2", () -> order1.add("b2")).in(200));
        check(s1.pollDue(99).isEmpty(), "at 99 ms nothing is due: the earliest job is for 100 ms");
        drive(s1, c1, 400, 1);
        check(order1.equals(List.of("a", "b", "b2", "c")), "they ran in time order, equal times first-come first-served: " + order1);

        // 2. the lost wakeup: an earlier job must wake a dispatcher that is asleep planning for a later one
        System.out.println("2. an earlier job wakes the sleeping dispatcher");
        Scheduler s2 = new Scheduler(1, Clock.system());
        s2.start();
        s2.schedule(() -> {}, 5_000);                              // the dispatcher goes to sleep for 5 s
        Thread.sleep(50);
        CountDownLatch ran2 = new CountDownLatch(1);
        long t2 = System.nanoTime();
        s2.schedule(ran2::countDown, 50);
        boolean woke = ran2.await(2, TimeUnit.SECONDS);
        long ms2 = (System.nanoTime() - t2) / 1_000_000;
        check(woke && ms2 < 1_000, "a 50 ms job submitted while the dispatcher slept towards a 5 s job ran after " + ms2 + " ms");
        s2.shutdownNow();
        check(s2.awaitTermination(2_000), "shutdownNow ended the dispatcher mid-sleep");

        // 3. cancel: before it starts it never runs, and its dependents are skipped; once running, cancel loses
        System.out.println("3. cancel before and during a run");
        ManualClock c3 = new ManualClock(0);
        Scheduler s3 = new Scheduler(1, c3);
        AtomicInteger ran3 = new AtomicInteger();
        s3.schedule(JobSpec.of("backup", ran3::incrementAndGet).in(100));
        s3.schedule(JobSpec.of("upload", ran3::incrementAndGet).after("backup"));
        check(s3.cancel("backup"), "cancel before its time returns true");
        drive(s3, c3, 500, 10);
        check(ran3.get() == 0 && s3.status("backup") == JobState.CANCELLED, "the cancelled job never ran");
        check(s3.status("upload") == JobState.SKIPPED, "the job waiting for it was skipped, not left waiting for ever");
        int[] tries3 = {0};
        s3.schedule(JobSpec.of("pay", () -> { tries3[0]++; throw new IOException("bank down"); })
                .retry(new ExponentialBackoff(10, 100, 5, null)));
        List<ScheduledJob> taken = s3.pollDue(c3.nowMs());          // the dispatcher got there first
        check(!s3.cancel("pay"), "cancel after the dispatcher took it returns false: exactly one of the two wins");
        for (ScheduledJob j : taken) s3.runJob(j);
        drive(s3, c3, c3.nowMs() + 500, 10);
        check(tries3[0] == 1 && s3.status("pay") == JobState.CANCELLED, "the running job finished its attempt, and no retry followed");

        // 4. cancel racing the dispatcher, 2,000 times: for every job exactly one side wins
        System.out.println("4. cancel races the dispatcher");
        Scheduler s4 = new Scheduler(4, Clock.system());
        s4.start();
        int n4 = 2_000;
        AtomicIntegerArray ran4 = new AtomicIntegerArray(n4);
        boolean[] won4 = new boolean[n4];
        Random rnd4 = new Random(4);
        for (int i = 0; i < n4; i++) { int k = i; s4.schedule(JobSpec.of("c" + k, () -> ran4.incrementAndGet(k)).in(rnd4.nextInt(20))); }
        List<Integer> shuffled = new ArrayList<>();
        for (int i = 0; i < n4; i++) shuffled.add(i);
        Collections.shuffle(shuffled, rnd4);
        Thread canceller = new Thread(() -> {
            int k = 0;
            for (int i : shuffled) {
                won4[i] = s4.cancel("c" + i);
                if (++k % 100 == 0) try { Thread.sleep(1); } catch (InterruptedException e) { return; }
            }
        });
        canceller.start();
        canceller.join();
        s4.shutdown();
        s4.awaitTermination(10_000);
        int bad4 = 0, cancelled4 = 0, runs4 = 0;
        for (int i = 0; i < n4; i++) {
            boolean ran = ran4.get(i) == 1;
            if (ran4.get(i) > 1 || ran == won4[i]) bad4++;
            if (won4[i]) { cancelled4++; if (s4.status("c" + i) != JobState.CANCELLED) bad4++; } else runs4++;
        }
        check(bad4 == 0, "every job either ran once or was cancelled, never both and never neither");
        check(cancelled4 > 0 && runs4 > 0, "both sides won some races: " + cancelled4 + " cancelled, " + runs4 + " ran");

        // 5. a fixed pool: never more than N at once, and all N really used
        System.out.println("5. at most N jobs run at once");
        Scheduler s5 = new Scheduler(4, Clock.system());
        s5.start();
        AtomicInteger in5 = new AtomicInteger(), most5 = new AtomicInteger();
        CountDownLatch done5 = new CountDownLatch(40);
        for (int i = 0; i < 40; i++)
            s5.schedule(() -> {
                most5.accumulateAndGet(in5.incrementAndGet(), Math::max);
                Thread.sleep(20);
                in5.decrementAndGet();
                done5.countDown();
            }, 0);
        check(done5.await(10, TimeUnit.SECONDS) && most5.get() == 4, "40 jobs of 20 ms on 4 workers: the most at once was " + most5.get());
        s5.shutdown();
        s5.awaitTermination(2_000);
        ManualClock c5 = new ManualClock(0);
        Scheduler bp = new Scheduler(2, c5);
        bp.limitPending(10);
        for (int i = 0; i < 10; i++) bp.schedule(JobSpec.of("b" + i, () -> {}).in(100));
        boolean full5 = false, again5 = true;
        try { bp.schedule(JobSpec.of("b10", () -> {})); } catch (RejectedExecutionException e) { full5 = true; }
        drive(bp, c5, 200, 10);
        try { bp.schedule(JobSpec.of("b11", () -> {})); } catch (RejectedExecutionException e) { again5 = false; }
        check(full5 && again5, "back-pressure: with a limit of 10 unfinished jobs the 11th is refused, and accepted again once they ran");

        // 6. fixed rate counts from the planned start; fixed delay from the end of the run
        System.out.println("6. fixed rate and fixed delay, with a ManualClock");
        ManualClock c6 = new ManualClock(0);
        Scheduler s6 = new Scheduler(1, c6);
        List<Long> rate6 = new ArrayList<>(), delay6 = new ArrayList<>();
        s6.schedule(JobSpec.of("rate", () -> { rate6.add(c6.nowMs()); c6.advance(300); }).every(new FixedRate(1_000)));
        drive(s6, c6, 2_900, 50);
        s6.cancel("rate");
        c6.set(10_000);
        s6.schedule(JobSpec.of("delay", () -> { delay6.add(c6.nowMs()); c6.advance(300); }).every(new FixedDelay(1_000)));
        drive(s6, c6, 12_900, 50);
        check(rate6.equals(List.of(0L, 1_000L, 2_000L)), "fixed rate 1 s with 300 ms runs starts at " + rate6 + ": no drift");
        check(delay6.equals(List.of(10_000L, 11_300L, 12_600L)), "fixed delay 1 s starts at " + delay6 + ": 1 s after each end");

        // 7. a run longer than its period: never two runs at once; the missed slots follow the Misfire rule
        System.out.println("7. a run longer than its period");
        Scheduler s7 = new Scheduler(4, Clock.system());
        s7.start();
        AtomicInteger in7 = new AtomicInteger(), most7 = new AtomicInteger(), runs7 = new AtomicInteger();
        String id7 = s7.scheduleAtFixedRate(() -> {
            most7.accumulateAndGet(in7.incrementAndGet(), Math::max);
            Thread.sleep(25);
            in7.decrementAndGet();
            runs7.incrementAndGet();
        }, 0, 5);
        Thread.sleep(300);
        s7.cancel(id7);
        s7.shutdown();
        s7.awaitTermination(2_000);
        check(most7.get() == 1 && runs7.get() >= 5, "25 ms runs every 5 ms, 4 idle workers: " + runs7.get() + " runs, never two at once");
        check(misfireStarts(Misfire.RUN_ALL).equals(List.of(0L, 1_000L, 3_500L, 3_600L, 4_000L)), "RUN_ALL: the missed 2 s and 3 s slots run back to back at 3.5 s and 3.6 s");
        check(misfireStarts(Misfire.RUN_ONCE).equals(List.of(0L, 1_000L, 3_500L, 4_000L)), "RUN_ONCE: one run at 3.5 s stands in for both, then 4 s on time");
        check(misfireStarts(Misfire.SKIP).equals(List.of(0L, 1_000L, 4_000L)), "SKIP: nothing late; the next run is the 4 s slot");

        // 8. retries: exponential backoff, then FAILED; jitter stays inside its bounds
        System.out.println("8. retries with backoff");
        ManualClock c8 = new ManualClock(0);
        Scheduler s8 = new Scheduler(1, c8);
        List<Long> at8 = new ArrayList<>();
        s8.schedule(JobSpec.of("flaky", () -> { at8.add(c8.nowMs()); throw new IOException("down"); })
                .retry(new ExponentialBackoff(100, 10_000, 4, null)));
        int[] tries8 = {0};
        s8.schedule(JobSpec.of("sometimes", () -> { if (++tries8[0] < 3) throw new IOException("busy"); })
                .retry(new ExponentialBackoff(100, 10_000, 4, null)));
        drive(s8, c8, 2_000, 10);
        check(at8.equals(List.of(0L, 100L, 300L, 700L)), "four attempts at " + at8 + ": waits of 100, 200, 400 ms");
        check(s8.status("flaky") == JobState.FAILED, "after the fourth failure it is FAILED, not retried again");
        check(tries8[0] == 3 && s8.status("sometimes") == JobState.DONE, "a job that fails twice then works ends DONE after 3 attempts");
        ExponentialBackoff jit = new ExponentialBackoff(100, 1_000, 10, new Random(1));
        boolean inBounds = true;
        for (int k = 1; k <= 9; k++)
            for (int r = 0; r < 200; r++) {
                long full = Math.min(1_000, 100L << (k - 1)), w = jit.delayMs(k, null);
                inBounds &= w >= full / 2 && w <= full;
            }
        check(inBounds, "with jitter every wait lies between half and all of 100, 200, 400 ..., capped at 1,000");
        check(jit.delayMs(10, null) == RetryPolicy.GIVE_UP, "the tenth failure of a 10-attempt policy gives up");

        // 9. a job that throws, even an Error, kills neither its worker nor the dispatcher
        System.out.println("9. a throwing job");
        Scheduler s9 = new Scheduler(1, Clock.system());
        s9.start();
        s9.schedule(JobSpec.of("boom", () -> { throw new IllegalStateException("boom"); }));
        s9.schedule(JobSpec.of("overflow", () -> { throw new StackOverflowError(); }));
        CountDownLatch after9 = new CountDownLatch(1);
        s9.schedule(JobSpec.of("after", after9::countDown).in(20));
        check(after9.await(2, TimeUnit.SECONDS), "after an exception and an Error, the only worker still runs the next job");
        check(s9.status("boom") == JobState.FAILED && s9.status("overflow") == JobState.FAILED, "both throwers are FAILED, with their errors recorded");
        CountDownLatch after9b = new CountDownLatch(1);
        s9.schedule(JobSpec.of("bad-rule", () -> {}).every((planned, ended) -> { throw new IllegalStateException("bad trigger"); }));
        s9.schedule(JobSpec.of("after-rule", after9b::countDown).in(20));
        check(after9b.await(2, TimeUnit.SECONDS) && s9.status("bad-rule") == JobState.FAILED,
              "a Trigger that throws ends its job FAILED; it neither strands the job RUNNING nor kills the worker");
        s9.shutdown();
        s9.awaitTermination(2_000);

        // 10. which due job first: higher priority when workers are short; the rule is handed in
        System.out.println("10. priority among due jobs");
        ManualClock c10 = new ManualClock(0);
        Scheduler s10 = new Scheduler(1, c10);
        List<String> order10 = new ArrayList<>();
        s10.schedule(JobSpec.of("low", () -> order10.add("low")).in(10).priority(1));
        s10.schedule(JobSpec.of("high", () -> order10.add("high")).in(20).priority(9));
        s10.schedule(JobSpec.of("mid", () -> order10.add("mid")).in(30).priority(5));
        c10.set(100);
        drive(s10, c10, 100, 1);
        check(order10.equals(List.of("high", "mid", "low")), "three due at once, one worker: " + order10);
        order10.clear();
        s10.configure(Scheduler.BY_DUE);                            // a different rule, handed in
        s10.schedule(JobSpec.of("low2", () -> order10.add("low2")).in(10).priority(1));
        s10.schedule(JobSpec.of("high2", () -> order10.add("high2")).in(20).priority(9));
        c10.set(200);
        drive(s10, c10, 200, 1);
        check(order10.equals(List.of("low2", "high2")), "with the earliest-due rule handed in: " + order10);

        // 11. prerequisites: a job starts only after all of them are DONE; two finishing together release it once
        System.out.println("11. prerequisites");
        ManualClock c11 = new ManualClock(0);
        Scheduler s11 = new Scheduler(1, c11);
        List<String> order11 = new ArrayList<>();
        JobState[] deployWhenAEnded = new JobState[1];
        s11.scheduleAll(List.of(
                JobSpec.of("deploy", () -> order11.add("deploy")).after("build-a", "build-b"),
                JobSpec.of("build-a", () -> order11.add("build-a")),
                JobSpec.of("build-b", () -> { deployWhenAEnded[0] = s11.status("deploy"); order11.add("build-b"); })));
        drive(s11, c11, 50, 1);
        check(order11.equals(List.of("build-a", "build-b", "deploy")), "deploy ran last: " + order11);
        check(deployWhenAEnded[0] == JobState.BLOCKED, "with one of two prerequisites done, deploy was still BLOCKED");
        int rounds = 30, lateOrTwice = 0;
        for (int round = 0; round < rounds; round++) {
            Scheduler r = new Scheduler(8, Clock.system());
            r.start();
            CyclicBarrier together = new CyclicBarrier(8);
            AtomicLong lastEnd = new AtomicLong();
            AtomicInteger deployRuns = new AtomicInteger();
            long[] deployStart = new long[1];
            List<JobSpec> batch = new ArrayList<>();
            String[] pre = new String[8];
            for (int p = 0; p < 8; p++) {
                pre[p] = "p" + p;
                batch.add(JobSpec.of(pre[p], () -> { together.await(); lastEnd.accumulateAndGet(System.nanoTime(), Math::max); }));
            }
            CountDownLatch deployed = new CountDownLatch(1);
            batch.add(JobSpec.of("deploy", () -> { deployStart[0] = System.nanoTime(); deployRuns.incrementAndGet(); deployed.countDown(); }).after(pre));
            r.scheduleAll(batch);
            deployed.await(5, TimeUnit.SECONDS);
            r.shutdown();
            r.awaitTermination(5_000);
            if (deployRuns.get() != 1 || deployStart[0] < lastEnd.get()) lateOrTwice++;
        }
        check(lateOrTwice == 0, rounds + " rounds of 8 prerequisites finishing together: deploy ran exactly once each time, after all 8");

        // 12. a failed prerequisite skips everything behind it; other jobs still run
        System.out.println("12. a failed prerequisite");
        ManualClock c12 = new ManualClock(0);
        Scheduler s12 = new Scheduler(2, c12);
        List<String> ran12 = new ArrayList<>();
        s12.scheduleAll(List.of(
                JobSpec.of("migrate", () -> { throw new IllegalStateException("schema lock"); }),
                JobSpec.of("deploy", () -> ran12.add("deploy")).after("migrate"),
                JobSpec.of("smoke", () -> ran12.add("smoke")).after("deploy"),
                JobSpec.of("notify", () -> ran12.add("notify")).after("migrate"),
                JobSpec.of("lint", () -> ran12.add("lint"))));
        drive(s12, c12, 50, 1);
        check(s12.status("migrate") == JobState.FAILED, "migrate FAILED");
        check(s12.status("deploy") == JobState.SKIPPED && s12.status("smoke") == JobState.SKIPPED
              && s12.status("notify") == JobState.SKIPPED, "deploy, smoke (two steps behind) and notify were SKIPPED");
        check(ran12.equals(List.of("lint")), "lint, which waits for nothing, still ran: " + ran12);
        s12.schedule(JobSpec.of("rollback-report", () -> ran12.add("late")).after("migrate"));
        check(s12.status("rollback-report") == JobState.SKIPPED, "a job submitted later, waiting for the failed one, is SKIPPED at once");

        // 13. a batch with a cycle is refused with its path, and nothing from it is kept
        System.out.println("13. cycles and bad prerequisites are refused at submit");
        ManualClock c13 = new ManualClock(0);
        Scheduler s13 = new Scheduler(1, c13);
        String msg = "";
        try {
            s13.scheduleAll(List.of(JobSpec.of("x", () -> {}).after("z"), JobSpec.of("y", () -> {}).after("x"),
                                    JobSpec.of("z", () -> {}).after("y"), JobSpec.of("w", () -> {})));
        } catch (IllegalArgumentException e) { msg = e.getMessage(); }
        check(msg.contains("x -> z -> y -> x"), "refused with the path: " + msg);
        check(s13.status("w") == null && s13.counts().values().stream().mapToInt(Integer::intValue).sum() == 0,
              "all or nothing: not even w, which had no cycle, was kept");
        boolean unknown = false, recurring = false, self = false;
        try { s13.schedule(JobSpec.of("a", () -> {}).after("ghost")); } catch (IllegalArgumentException e) { unknown = true; }
        s13.schedule(JobSpec.of("tick", () -> {}).every(new FixedRate(1_000)));
        try { s13.schedule(JobSpec.of("b", () -> {}).after("tick")); } catch (IllegalArgumentException e) { recurring = true; }
        try { s13.schedule(JobSpec.of("me", () -> {}).after("me")); } catch (IllegalArgumentException e) { self = true; }
        check(unknown && recurring && self, "an unknown prerequisite, a recurring one, and a job waiting for itself are all refused");
        List<JobSpec> chain = new ArrayList<>();
        for (int i = 0; i < 20_000; i++) chain.add(i == 0 ? JobSpec.of("s0", () -> {}) : JobSpec.of("s" + i, () -> {}).after("s" + (i - 1)));
        check(s13.scheduleAll(chain).size() == 20_000, "a chain of 20,000 jobs is accepted: the check is a loop, not recursion");
        List<JobSpec> loop = new ArrayList<>();
        for (int i = 0; i < 20_000; i++) loop.add(JobSpec.of("q" + i, () -> {}).after("q" + ((i + 1) % 20_000)));
        boolean bigCycle = false;
        try { s13.scheduleAll(loop); } catch (IllegalArgumentException e) { bigCycle = e.getMessage().startsWith("cycle"); }
        check(bigCycle, "a cycle through 20,000 jobs is found without a stack overflow");

        // 14. graceful shutdown: one-shots finish, recurring jobs stop, new jobs are refused
        System.out.println("14. shutdown()");
        Scheduler s14 = new Scheduler(2, Clock.system());
        s14.start();
        CountDownLatch later14 = new CountDownLatch(1);
        AtomicInteger ticks14 = new AtomicInteger();
        s14.schedule(JobSpec.of("later", later14::countDown).in(150));
        s14.schedule(JobSpec.of("tick", ticks14::incrementAndGet).every(new FixedRate(10)));
        Thread.sleep(50);
        s14.shutdown();
        boolean refused14 = false;
        try { s14.schedule(() -> {}, 0); } catch (RejectedExecutionException e) { refused14 = true; }
        boolean ended14 = s14.awaitTermination(3_000);
        check(later14.getCount() == 0 && ended14, "the job due in 150 ms still ran after shutdown(), then the threads ended");
        int t14 = ticks14.get();
        Thread.sleep(40);
        check(ticks14.get() == t14 && s14.status("tick") == JobState.CANCELLED, "the recurring job stopped and is CANCELLED");
        check(refused14, "a new job after shutdown() is refused");

        // 15. shutdownNow: returns what never started, interrupts what runs, ends at once
        System.out.println("15. shutdownNow()");
        Scheduler s15 = new Scheduler(1, Clock.system());
        s15.start();
        CountDownLatch sleeping = new CountDownLatch(1);
        AtomicBoolean interrupted15 = new AtomicBoolean();
        s15.schedule(JobSpec.of("sleeper", () -> {
            sleeping.countDown();
            try { Thread.sleep(10_000); } catch (InterruptedException e) { interrupted15.set(true); throw e; }
        }));
        s15.schedule(JobSpec.of("far", () -> {}).in(60_000));
        s15.schedule(JobSpec.of("queued", () -> {}).in(0));        // due, but the only worker is busy
        s15.scheduleAll(List.of(JobSpec.of("report", () -> {}).after("sleeper"),        // a chain waiting behind the sleeper
                                JobSpec.of("email", () -> {}).after("report")));
        sleeping.await();
        long t15 = System.nanoTime();
        List<String> never = s15.shutdownNow();
        boolean ended15 = s15.awaitTermination(2_000);
        long ms15 = (System.nanoTime() - t15) / 1_000_000;
        check(new HashSet<>(never).equals(Set.of("far", "queued", "report", "email")), "it returned the four jobs that never started: " + never);
        check(interrupted15.get() && ended15 && ms15 < 1_500, "the sleeping job was interrupted and every thread ended in " + ms15 + " ms");
        check(s15.status("sleeper") == JobState.CANCELLED && s15.status("far") == JobState.CANCELLED
              && s15.status("report") == JobState.CANCELLED && s15.status("email") == JobState.CANCELLED,
              "all of them are CANCELLED, including a chain of waiting jobs (none half-cancelled, half-skipped)");

        // 16. listeners hear after the lock is released; a broken one changes nothing; the counts add up
        System.out.println("16. listeners and counts");
        ManualClock c16 = new ManualClock(0);
        Scheduler s16 = new Scheduler(2, c16);
        AtomicBoolean lockFree = new AtomicBoolean(true);
        List<RunRecord> heard = Collections.synchronizedList(new ArrayList<>());
        s16.addListener(r -> { throw new IllegalStateException("broken dashboard"); });
        s16.addListener(r -> {
            Thread other = new Thread(s16::counts);               // would block if the lock were still held
            other.start();
            try { other.join(1_000); } catch (InterruptedException e) { return; }
            if (other.isAlive()) lockFree.set(false);
            heard.add(r);
        });
        s16.schedule(JobSpec.of("ok", () -> {}));
        s16.schedule(JobSpec.of("bad", () -> { throw new IOException("disk full"); }));
        s16.schedule(JobSpec.of("never", () -> {}).in(1_000));
        s16.cancel("never");
        drive(s16, c16, 10, 1);
        check(lockFree.get() && heard.size() == 3, "3 records heard, each after the lock was released, despite a listener that throws");
        Map<JobState, Integer> n16 = s16.counts();
        check(n16.get(JobState.DONE) == 1 && n16.get(JobState.FAILED) == 1 && n16.get(JobState.CANCELLED) == 1
              && n16.values().stream().mapToInt(Integer::intValue).sum() == 3, "counts: " + n16);

        System.out.println(failed == 0 ? "ALL PASS" : failed + " FAILED");
        System.exit(failed == 0 ? 0 : 1);
    }
}
