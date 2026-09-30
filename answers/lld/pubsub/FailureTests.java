import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// targeted failure tests: each one proves a claim the page makes (move 9, and the follow-ups that name a test number).
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }
    static List<String> payloads(Batch b) { return b.messages().stream().map(Message::payload).toList(); }

    /** A clock the test owns: "now" is whatever it says, and a backoff is recorded instead of waited for. */
    static final class TestClock implements Clock {
        volatile long now = 1_700_000_000_000L;
        final List<Long> sleeps = new CopyOnWriteArrayList<>();
        public long nowMs() { return now; }
        @Override public void sleepMs(long ms) { sleeps.add(ms); now += ms; }
    }

    public static void main(String[] args) throws Exception {

        // 1. fifty threads publish into ONE topic at the same instant: every offset must be handed out exactly
        //    once, the log must hold all of them, and each publisher's own messages must be in increasing order.
        Broker race = new Broker(200_000);
        race.configure(new FixedDelayRetry(3, 1), new InMemoryDeadLetters());
        AtomicLong consumed = new AtomicLong();
        race.subscribe("counter", "ticks", m -> consumed.incrementAndGet());
        int threads = 50, each = 40, total = threads * each;
        ExecutorService pool = Executors.newFixedThreadPool(16);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<List<Long>>> runs = new ArrayList<>();
        for (int t = 0; t < threads; t++) {
            final int me = t;
            runs.add(pool.submit(() -> {
                go.await();
                List<Long> mine = new ArrayList<>(each);
                for (int k = 0; k < each; k++) mine.add(race.publish("ticks", "p" + me, me + ":" + k));
                return mine;
            }));
        }
        go.countDown();
        Set<Long> offsets = new HashSet<>();
        boolean ordered = true;
        for (Future<List<Long>> f : runs) {
            List<Long> mine = f.get();
            offsets.addAll(mine);
            for (int k = 1; k < mine.size(); k++) if (mine.get(k) <= mine.get(k - 1)) ordered = false;
        }
        pool.shutdown();
        check(offsets.size() == total, "2000 concurrent publishes got 2000 DISTINCT offsets, none duplicated");
        check(race.topic("ticks").tailOffset() == total, "the log holds all 2000: none was lost to a concurrent add");
        boolean contiguous = true;
        for (long off = 0; off < total; off++) if (race.topic("ticks").readAt(off) == null) contiguous = false;
        check(contiguous, "the offsets are contiguous 0..1999: no hole anywhere in the log");
        check(ordered, "each publisher's own messages kept their order relative to each other");
        check(Main.awaitUntil(() -> consumed.get() == total, 5000), "one subscriber received all 2000 of them");
        race.close();

        // 2. fan-out: three subscribers each get every message, in order, from ONE copy of the log
        Broker fan = new Broker(1_000);
        fan.configure(new FixedDelayRetry(3, 1), new InMemoryDeadLetters());
        List<List<String>> seen = List.of(new CopyOnWriteArrayList<>(), new CopyOnWriteArrayList<>(), new CopyOnWriteArrayList<>());
        for (int i = 0; i < 3; i++) { final int n = i; fan.subscribe("sub" + i, "news", m -> seen.get(n).add(m.payload())); }
        List<String> expected = new ArrayList<>();
        for (int i = 0; i < 20; i++) { fan.publish("news", "k", "n" + i); expected.add("n" + i); }
        check(Main.awaitUntil(() -> seen.stream().allMatch(l -> l.size() == 20), 3000), "all three subscribers received all 20");
        check(seen.stream().allMatch(l -> l.equals(expected)), "and each received them in publish order");
        check(fan.topic("news").retained() == 20, "the topic stored 20 messages once, not 60: fan-out is three cursors, not three copies");
        fan.close();

        // 3. a subscriber restarts: it resumes at the offset it had committed, sees nothing twice and misses nothing
        Broker rs = new Broker(1_000);
        rs.configure(new FixedDelayRetry(3, 1), new InMemoryDeadLetters());
        List<String> before = new CopyOnWriteArrayList<>(), after = new CopyOnWriteArrayList<>();
        rs.subscribe("reader", "feed", m -> before.add(m.payload()));
        for (int i = 0; i < 5; i++) rs.publish("feed", "k", "m" + i);
        Main.awaitUntil(() -> before.size() == 5, 2000);
        long saved = rs.sub("reader").offset();
        check(saved == 5, "the cursor after five acknowledged messages is 5, the offset it will read NEXT");
        rs.unsubscribe("reader");
        for (int i = 5; i < 10; i++) rs.publish("feed", "k", "m" + i);           // published while it was down
        rs.subscribe("reader", "feed", m -> after.add(m.payload()), SubscribeOptions.opts().fromOffset(saved));
        check(Main.awaitUntil(() -> after.size() == 5, 2000), "the restarted subscriber picked up five messages");
        check(after.equals(List.of("m5", "m6", "m7", "m8", "m9")), "exactly the five it had not seen: no repeat, no gap");
        rs.close();

        // 4. the handler throws, then works: it is retried on the policy's schedule and the cursor moves only after
        TestClock clock4 = new TestClock();
        Broker rt = new Broker(1_000);
        rt.setClock(clock4);
        InMemoryDeadLetters parked4 = new InMemoryDeadLetters();
        rt.configure(new ExponentialBackoff(5, 10, 1_000), parked4);
        AtomicInteger calls = new AtomicInteger();
        rt.subscribe("flaky", "jobs", m -> { if (calls.incrementAndGet() < 3) throw new IllegalStateException("gateway timeout"); });
        rt.publish("jobs", null, "job-1");
        check(Main.awaitUntil(() -> rt.sub("flaky").delivered() == 1, 2000), "the message was delivered in the end");
        check(calls.get() == 3, "the handler ran three times: two failures and the success");
        check(clock4.sleeps.equals(List.of(10L, 20L)), "the waits doubled -- 10 ms then 20 ms -- straight from the injected clock");
        check(rt.sub("flaky").offset() == 1, "the cursor moved only after the handler returned: at-least-once, not at-most-once");
        check(parked4.size() == 0, "nothing was dead-lettered, because the retry eventually worked");
        rt.close();

        // 5. a message nobody can handle: retried per the policy, parked, and the subscription CARRIES ON
        TestClock clock5 = new TestClock();
        Broker dl = new Broker(1_000);
        dl.setClock(clock5);
        InMemoryDeadLetters parked5 = new InMemoryDeadLetters();
        dl.configure(new ExponentialBackoff(4, 10, 1_000), parked5);
        List<String> handled = new CopyOnWriteArrayList<>();
        dl.subscribe("strict", "jobs", m -> {
            if (m.payload().equals("poison")) throw new IllegalArgumentException("cannot parse");
            handled.add(m.payload());
        });
        dl.publish("jobs", null, "a"); dl.publish("jobs", null, "poison"); dl.publish("jobs", null, "b");
        check(Main.awaitUntil(() -> dl.sub("strict").offset() == 3, 3000), "the cursor reached the end: giving up never stalls a subscription");
        check(handled.equals(List.of("a", "b")), "the two good messages were handled, the poison one was stepped over");
        check(parked5.size() == 1 && parked5.all().get(0).attempts() == 4, "the poison message is parked, with four attempts recorded");
        check(clock5.sleeps.equals(List.of(10L, 20L, 40L)), "the three waits before giving up were 10, 20 and 40 ms");
        check(dl.sub("strict").delivered() == 2 && dl.sub("strict").deadLettered() == 1, "counts: 2 delivered, 1 dead-lettered");
        dl.close();

        // 6. retention overtakes a slow subscriber: the head is dropped, the cursor is fast-forwarded, and the gap is COUNTED
        Broker ret = new Broker(10);
        ret.configure(new FixedDelayRetry(3, 1), new InMemoryDeadLetters());
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        AtomicLong got = new AtomicLong();
        Subscription slowpoke = ret.subscribe("slowpoke", "firehose", m -> {
            if (got.get() == 0) { entered.countDown(); release.await(); }        // stuck on the very first message
            got.incrementAndGet();
        });
        ret.publish("firehose", null, "m0");
        check(entered.await(2, TimeUnit.SECONDS), "the subscriber is inside the handler for offset 0, cursor not yet moved");
        for (int i = 1; i < 50; i++) ret.publish("firehose", null, "m" + i);
        check(ret.topic("firehose").retained() == 10, "retention keeps only the last ten messages");
        check(ret.topic("firehose").droppedCount() == 40, "forty were trimmed off the head of the log");
        release.countDown();
        check(Main.awaitUntil(() -> slowpoke.delivered() == 11, 3000), "the subscriber caught up on what is still there: 11 delivered");
        check(slowpoke.missed() == 39, "the 39 messages retention dropped under it are COUNTED: visible loss beats invisible loss");
        check(slowpoke.delivered() + slowpoke.missed() == 50, "all fifty are accounted for, none quietly vanished");
        ret.close();

        // 7. one slow subscriber stalls neither the publisher nor the other subscribers
        Broker sl = new Broker(1_000);
        sl.configure(new FixedDelayRetry(3, 1), new InMemoryDeadLetters());
        AtomicLong fast = new AtomicLong();
        sl.subscribe("fast", "mixed", m -> fast.incrementAndGet());
        sl.subscribe("slow", "mixed", m -> Thread.sleep(200));                   // 200 ms per message, on purpose
        long t0 = System.nanoTime();
        for (int i = 0; i < 6; i++) sl.publish("mixed", "k", "m" + i);
        long publishMs = (System.nanoTime() - t0) / 1_000_000;
        check(publishMs < 100, "six publishes returned in " + publishMs + " ms: a publisher never waits for a handler");
        check(Main.awaitUntil(() -> fast.get() == 6, 3000), "the fast subscriber got all six immediately");
        check(sl.sub("slow").delivered() < 6, "the slow one is still behind (" + sl.sub("slow").lag() + " to go) and that is its own problem");
        sl.close();

        // 8. a handler that always throws, and a listener that always throws, isolate: everyone else is unaffected
        Broker iso = new Broker(1_000);
        InMemoryDeadLetters parked8 = new InMemoryDeadLetters();
        iso.configure(new FixedDelayRetry(2, 1), parked8);
        iso.addListener(e -> { if (e.type() == EventType.PUBLISHED) throw new RuntimeException("metrics is down"); });
        AtomicLong good = new AtomicLong();
        iso.subscribe("bad", "events", m -> { throw new IllegalStateException("always fails"); });
        iso.subscribe("good", "events", m -> good.incrementAndGet());
        iso.subscribe("keys", "events", m -> {}, SubscribeOptions.opts().filter(m -> "IN".equals(m.key())));
        for (int i = 0; i < 5; i++) check(iso.publish("events", i % 2 == 0 ? "IN" : "US", "m" + i) == i,
                                          "publish " + i + " returned offset " + i + " although the listener threw");
        check(Main.awaitUntil(() -> good.get() == 5 && iso.sub("bad").offset() == 5, 3000),
              "the good subscriber got all five while the failing one dead-lettered all five");
        check(parked8.size() == 5, "all five were parked by the failing subscription, and none by anybody else");
        check(iso.sub("keys").delivered() == 3 && iso.sub("keys").skipped() == 2,
              "the filtered subscription handled 3 of 5 and stepped over 2 without calling its handler");
        iso.close();

        // 9. a retry policy written next year that never gives up cannot stall a subscription: BoundedRetry caps it
        TestClock clock9 = new TestClock();
        Broker cap = new Broker(1_000);
        cap.setClock(clock9);
        InMemoryDeadLetters parked9 = new InMemoryDeadLetters();
        cap.configure((attempt, failure) -> 0, parked9);                          // "always retry, immediately"
        AtomicInteger tries = new AtomicInteger();
        cap.subscribe("forever", "jobs", m -> { tries.incrementAndGet(); throw new IllegalStateException("always"); });
        cap.publish("jobs", null, "x"); cap.publish("jobs", null, "y");
        check(Main.awaitUntil(() -> cap.sub("forever").offset() == 2, 3000), "both messages were finished with, not retried forever");
        check(tries.get() == 2 * Broker.MAX_ATTEMPTS, "the wrapper stopped each one at " + Broker.MAX_ATTEMPTS + " attempts: " + tries.get() + " handler calls");
        check(parked9.size() == 2, "and both ended up in the dead-letter sink");
        cap.close();
        Broker cap2 = new Broker(1_000);
        InMemoryDeadLetters parked9b = new InMemoryDeadLetters();
        cap2.configure((attempt, failure) -> { throw new IllegalStateException("a bug in the policy"); }, parked9b);
        cap2.subscribe("broken", "jobs", m -> { throw new IllegalStateException("always"); });
        cap2.publish("jobs", null, "x"); cap2.publish("jobs", null, "y");
        check(Main.awaitUntil(() -> cap2.sub("broken").offset() == 2, 3000) && parked9b.size() == 2,
              "a policy that THROWS counts as giving up: both parked, the cursor at the end, the dispatcher alive");
        cap2.close();

        // 10. pause holds back the very next message; resume carries on from exactly there; unsubscribe ends the
        //     thread; STOPPED is final
        Broker ps = new Broker(1_000);
        ps.configure(new FixedDelayRetry(3, 1), new InMemoryDeadLetters());
        List<String> heard = new CopyOnWriteArrayList<>();
        Subscription sub = ps.subscribe("watcher", "clicks", m -> heard.add(m.payload()));
        for (int i = 0; i < 3; i++) ps.publish("clicks", "k", "c" + i);
        Main.awaitUntil(() -> heard.size() == 3, 2000);
        sub.pause();
        ps.publish("clicks", "k", "c3"); ps.publish("clicks", "k", "c4");        // at once: the dispatcher is still in awaitAt
        Thread.sleep(150);
        check(sub.offset() == 3 && sub.lag() == 2 && heard.size() == 3,
              "paused: nothing was handed over after pause() returned; the cursor stayed at 3 and the lag grew to 2");
        sub.resume();
        check(Main.awaitUntil(() -> heard.size() == 5, 2000), "resumed: it picked up exactly where it stopped");
        check(ps.unsubscribe("watcher"), "unsubscribe removed it");
        check(Main.awaitUntil(() -> !sub.running(), 2000), "and its dispatch loop actually returned, so the thread does not leak");
        sub.pause(); sub.resume();
        check(sub.state() == SubState.STOPPED, "STOPPED is final: pause() and resume() on a stopped subscription change nothing");
        check(!ps.unsubscribe("watcher"), "unsubscribing twice is false, not an exception");
        ps.close();

        // 11. the lost wakeup: a dispatcher parked inside awaitAt is woken by the publish itself, not by a timeout.
        //     The check and the wait are under the SAME lock the publisher signals under, inside a while loop.
        Broker wk = new Broker(1_000);
        wk.configure(new FixedDelayRetry(3, 1), new InMemoryDeadLetters());
        Topic quiet = wk.topic("late-news");
        long t11 = System.nanoTime();
        check(quiet.awaitAt(0, 60) == null && (System.nanoTime() - t11) / 1_000_000 >= 55,
              "with nothing published, awaitAt waits its whole timeout and returns null rather than a message");
        ExecutorService waiter = Executors.newSingleThreadExecutor();
        Future<Long> woke = waiter.submit(() -> {                                 // parks for up to five seconds
            long t = System.nanoTime();
            return quiet.awaitAt(0, 5_000) == null ? -1L : (System.nanoTime() - t) / 1_000_000;
        });
        Thread.sleep(60);                                                         // it is asleep in awaitNanos by now
        wk.publish("late-news", null, "extra");
        long wokeMs = woke.get();
        check(wokeMs >= 0, "the parked reader was handed the message the publisher appended");
        check(wokeMs < 2_000, "and the publish itself woke it after " + wokeMs + " ms, not the 5,000 ms timeout: no wakeup was lost");
        waiter.shutdown();
        wk.close();

        // 12. shutting down in the middle of a delivery: the thread ends at once and the message is NOT committed
        Broker sd = new Broker(1_000);
        InMemoryDeadLetters parked12 = new InMemoryDeadLetters();
        sd.configure(new FixedDelayRetry(10, 60_000), parked12);                  // a minute between attempts, on purpose
        CountDownLatch threw = new CountDownLatch(1);
        Subscription stuck = sd.subscribe("stuck", "slowjobs", m -> { threw.countDown(); throw new IllegalStateException("downstream is down"); });
        sd.publish("slowjobs", null, "j1");
        check(threw.await(2, TimeUnit.SECONDS), "the handler ran and threw, so the dispatcher is now asleep in a 60-second backoff");
        long t12 = System.nanoTime();
        sd.unsubscribe("stuck");
        boolean ended = Main.awaitUntil(() -> !stuck.running(), 2000);
        long stopMs = (System.nanoTime() - t12) / 1_000_000;
        check(ended && stopMs < 1_000, "unsubscribe ended the dispatch loop in " + stopMs + " ms, not 60 s: stop() interrupts a parked thread");
        check(stuck.offset() == 0, "the cursor never moved: a shutdown in the middle of a delivery commits nothing");
        check(parked12.size() == 0, "and nothing was dead-lettered -- the message is unfinished, not given up on");
        List<String> again = new CopyOnWriteArrayList<>();
        sd.subscribe("stuck2", "slowjobs", m -> again.add(m.payload()), SubscribeOptions.opts().fromOffset(stuck.offset()));
        check(Main.awaitUntil(() -> again.equals(List.of("j1")), 2000), "a replacement starting at that cursor is handed it again: at-least-once, proven");
        sd.close();

        // 13. seek while a message is in the handler: the dispatcher applies the seek before its next read, so the
        //     replay starts exactly where it was asked to and nothing is skipped
        Broker sk = new Broker(1_000);
        List<Long> order = new CopyOnWriteArrayList<>();
        CountDownLatch holding = new CountDownLatch(1), letGo = new CountDownLatch(1);
        Subscription replayer = sk.subscribe("replayer", "log", m -> {
            if (m.offset() == 3 && holding.getCount() > 0) { holding.countDown(); letGo.await(); }
            order.add(m.offset());
        }, SubscribeOptions.opts().fromEarliest());
        for (int i = 0; i < 5; i++) sk.publish("log", "k", "m" + i);
        check(holding.await(2, TimeUnit.SECONDS), "the handler is holding offset 3 when another thread calls seek(0)");
        replayer.seek(0);
        letGo.countDown();
        check(Main.awaitUntil(() -> order.size() == 9, 2000) && order.equals(List.of(0L, 1L, 2L, 3L, 0L, 1L, 2L, 3L, 4L)),
              "3 finished, then the replay began at 0 itself, not at 1: " + order);
        sk.close();

        // 14. a filter that throws (here: a message with no key) fails like a handler: retried, parked, and the
        //     subscription carries on instead of dying on the spot
        Broker fl = new Broker(1_000);
        InMemoryDeadLetters parked14 = new InMemoryDeadLetters();
        fl.configure(new FixedDelayRetry(2, 1), parked14);
        List<String> india = new CopyOnWriteArrayList<>();
        Subscription picky = fl.subscribe("india", "orders", m -> india.add(m.payload()),
            SubscribeOptions.opts().filter(m -> m.key().startsWith("IN")));       // m.key() is null for the first message
        fl.publish("orders", null, "no-key"); fl.publish("orders", "IN-1", "o1");
        fl.publish("orders", "US-1", "o2");   fl.publish("orders", "IN-2", "o3");
        check(Main.awaitUntil(() -> picky.offset() == 4, 2000), "the cursor reached the end: the throwing filter did not kill the dispatcher");
        check(india.equals(List.of("o1", "o3")) && picky.skipped() == 1 && parked14.size() == 1,
              "the two IN orders were handled, the US one skipped, the keyless one parked");
        fl.close();

        // 15. an interrupt means stop. A handler that throws InterruptedException by itself ends its subscription
        //     cleanly, instead of leaving the thread spinning at full CPU on an interrupt that nobody clears
        Broker ir = new Broker(1_000);
        AtomicInteger irCalls = new AtomicInteger();
        Subscription quitter = ir.subscribe("quitter", "jobs", m -> {
            if (irCalls.incrementAndGet() == 1) throw new InterruptedException("raised inside the handler");
        });
        ir.publish("jobs", null, "j1");
        check(Main.awaitUntil(() -> !quitter.running(), 2000) && quitter.state() == SubState.STOPPED,
              "the dispatch loop ended and the subscription says STOPPED");
        check(quitter.offset() == 0 && irCalls.get() == 1, "the cursor never moved, and the handler was not called again");
        ir.close();

        // 16. the wall clock steps back: a timestamp never goes below the one before it, so seek-by-time stays right
        TestClock back = new TestClock();
        Broker tb = new Broker(1_000);
        tb.setClock(back);
        back.now = 10_000; tb.publish("ticks", null, "a");
        back.now = 4_000;  tb.publish("ticks", null, "b");                        // the clock was stepped back six seconds
        back.now = 12_000; tb.publish("ticks", null, "c");
        Topic ticks = tb.topic("ticks");
        check(ticks.readAt(1).atMs() == 10_000, "b was stamped 10,000, not 4,000: time inside one log never goes backwards");
        check(TimeSeek.offsetAt(ticks, 5_000) == 0, "so 'everything since 5,000' starts at a (offset 0), not at c");
        tb.close();

        // 17. guaranteed delivery: eight publishers go through the back-pressure gate into a ring of 16 with one slow
        //     reader. No publish may overwrite a message the reader has not handled yet
        Broker gd = new Broker(16);
        AtomicLong handled17 = new AtomicLong();
        Subscription slowReader = gd.subscribe("slow", "orders", m -> { Thread.sleep(1); handled17.incrementAndGet(); });
        BackPressure gate = new BackPressure(gd);
        ExecutorService pubs = Executors.newFixedThreadPool(8);
        CountDownLatch go17 = new CountDownLatch(1);
        List<Future<?>> sent = new ArrayList<>();
        for (int p = 0; p < 8; p++) {
            final int me = p;
            sent.add(pubs.submit(() -> { go17.await(); for (int k = 0; k < 25; k++) gate.publish("orders", "k", me + ":" + k, 10_000); return null; }));
        }
        go17.countDown();
        for (Future<?> f : sent) f.get();
        pubs.shutdown();
        check(Main.awaitUntil(() -> handled17.get() == 200, 5000), "the slow reader handled all 200");
        check(slowReader.missed() == 0, "and missed none: no publish overwrote a message it had not read");
        gd.close();

        // 18. pull instead of push: consume() moves nothing, ack() commits, a filter leaves messages out, and a long
        //     poll is woken by the publish itself
        Broker pb = new Broker(1_000);
        PullConsumers pull = new PullConsumers(pb);
        pull.subscribe("orders", "billing", true, Filter.all());
        pull.subscribe("orders", "india", true, m -> "IN".equals(m.key()));
        for (int i = 0; i < 5; i++) pb.publish("orders", i % 2 == 0 ? "IN" : "US", "o" + i);
        Batch first = pull.consume("orders", "billing", 3, 0), repeat = pull.consume("orders", "billing", 3, 0);
        check(payloads(first).equals(List.of("o0", "o1", "o2")) && payloads(repeat).equals(payloads(first)),
              "without an ack the same three come back: a consumer that crashed before ack() loses nothing");
        pull.ack("orders", "billing", first.next());
        check(payloads(pull.consume("orders", "billing", 10, 0)).equals(List.of("o3", "o4")), "after ack(3) the next batch starts at offset 3");
        Batch in = pull.consume("orders", "india", 10, 0);
        check(payloads(in).equals(List.of("o0", "o2", "o4")) && in.next() == 5,
              "the filtered consumer got the three IN orders, and its ack will step over the two US ones");
        pull.ack("orders", "india", in.next());
        ExecutorService poller = Executors.newSingleThreadExecutor();
        Future<Long> waited = poller.submit(() -> {
            long t = System.nanoTime();
            Batch b = pull.consume("orders", "india", 10, 5_000);                 // nothing new yet: a long poll
            return b.messages().isEmpty() ? -1L : (System.nanoTime() - t) / 1_000_000;
        });
        Thread.sleep(60);
        pb.publish("orders", "IN", "o5");
        long waitedMs = waited.get();
        check(waitedMs >= 0 && waitedMs < 2_000, "the long poll was woken by the publish after " + waitedMs + " ms, not by its 5,000 ms timeout");
        poller.shutdown();
        pb.close();

        // 19. persistence: a tab or a newline inside a payload survives, lines written out of order come back at their
        //     own offsets and times, and a restore does not write everything to the file a second time
        Path file = Files.createTempFile("pubsub-test", ".tsv");
        FileStore store = new FileStore(file);
        store.append(new Message(1, "audit", "k", "line one\nline two", Map.of(), 2_000));   // offset 1 reached the file first
        store.append(new Message(0, "audit", null, "a\ttab", Map.of(), 1_000));
        Broker restarted = new Broker(1_000);
        restarted.addListener(e -> {                                              // the same "store every publish" listener as before
            if (e.type() != EventType.PUBLISHED) return;
            try { store.append(restarted.topic(e.topic()).readAt(e.offset())); } catch (IOException io) { throw new UncheckedIOException(io); }
        });
        check(Recovery.restore(restarted, store, "audit") == 2, "both stored messages were read back");
        Message r0 = restarted.topic("audit").readAt(0), r1 = restarted.topic("audit").readAt(1);
        check(r0 != null && r1 != null && "a\ttab".equals(r0.payload()) && "line one\nline two".equals(r1.payload()) && r0.key() == null,
              "each came back at its own offset, with the tab and the newline intact");
        check(r0.atMs() == 1_000 && r1.atMs() == 2_000, "with the time it was stored with, not the time of the restart");
        check(Files.readAllLines(file).size() == 2, "and the restore wrote nothing back to the file: a replay is not a new publish");
        Files.deleteIfExists(file);
        restarted.close();

        // 20. one IdempotentHandler shared by eight threads, as a consumer group shares it: every distinct id is
        //     handled exactly once, and the remembered ids stay consistent under the lock
        AtomicLong charged = new AtomicLong();
        IdempotentHandler shared = new IdempotentHandler(m -> charged.incrementAndGet(), 100);
        ExecutorService members = Executors.newFixedThreadPool(8);
        CountDownLatch go20 = new CountDownLatch(1);
        List<Future<?>> ran = new ArrayList<>();
        for (int p = 0; p < 8; p++) {
            final int me = p;
            ran.add(members.submit(() -> {
                go20.await();
                for (int k = 0; k < 20_000; k++) shared.onMessage(new Message(k, "charges", null, "c", Map.of("id", me + ":" + k), 0));
                return null;
            }));
        }
        go20.countDown();
        boolean finished = true;
        for (Future<?> f : ran) { try { f.get(10, TimeUnit.SECONDS); } catch (TimeoutException hung) { finished = false; } }
        members.shutdownNow();
        check(finished && charged.get() == 160_000 && shared.duplicates() == 0,
              "160,000 distinct ids from 8 threads: each charged once, none taken for a duplicate, no thread stuck");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
