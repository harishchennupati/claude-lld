import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// targeted failure tests: each one proves a claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;

    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /** Sends the framework's own error channel to a buffer, so a test that expects failures stays quiet. */
    static ByteArrayOutputStream quietStatus() {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        Status.sink(new PrintStream(buf, true));
        Status.reset();
        return buf;
    }

    public static void main(String[] args) throws Exception {
        Path dir = Files.createTempDirectory("logger-tests");
        ByteArrayOutputStream status = quietStatus();

        // 1. fifty threads log to ONE file through a bounded queue at the same instant: every line must be
        //    whole, every line must be there, and each thread's own lines must be in the order it wrote them.
        LoggerContext ctx = new LoggerContext();
        Path file = dir.resolve("race.log");
        FileAppender fileSink = new FileAppender("file", new TextFormatter(), LogLevel.TRACE, file, LogLevel.OFF);
        AsyncAppender async = new AsyncAppender("async", fileSink, 8192, OverflowPolicy.BLOCK, LogLevel.ERROR);
        Logger web = ctx.getLogger("com.shop.web");
        web.addAppender(async);
        web.setAdditive(false);
        int writers = 50, lines = 20;
        Main.runConcurrently(writers, i -> { for (int k = 0; k < lines; k++) web.info("t" + i + "-" + k); });
        async.close();
        List<String> got = Files.readAllLines(file);
        check(got.size() == writers * lines, "50 threads x 20 lines all reached the file: " + got.size());
        check(async.droppedCount() == 0, "a queue deep enough and a BLOCK policy dropped nothing");
        check(got.stream().allMatch(l -> l.matches(".* INFO  \\[.*\\] com\\.shop\\.web - t\\d+-\\d+")),
              "every line is whole: no two writers interleaved inside one line");
        check(Main.perThreadOrderKept(got), "each thread's own lines are in the order that thread wrote them");
        check(new HashSet<>(got).size() == got.size(), "no line was written twice");

        // 2. the gate is first, and it is free: a switched-off call builds nothing at all
        LoggerContext c2 = new LoggerContext();
        MemoryAppender mem = new MemoryAppender("mem");
        c2.configure(LogLevel.INFO, List.of(mem), List.of());
        Logger quiet = c2.getLogger("com.shop.hot");
        AtomicInteger built = new AtomicInteger();
        for (int i = 0; i < 1000; i++) quiet.debug(() -> { built.incrementAndGet(); return "cart=" + new int[7]; });
        check(built.get() == 0, "1000 disabled DEBUG calls never called the message supplier");
        check(mem.lines().isEmpty(), "and wrote nothing");
        quiet.info(() -> { built.incrementAndGet(); return "enabled"; });
        check(built.get() == 1 && mem.lines().size() == 1, "an enabled call does call the supplier, exactly once");
        check(!quiet.isEnabled(LogLevel.DEBUG) && quiet.isEnabled(LogLevel.ERROR), "the gate agrees with the level");

        // 3. the tree: inherit, override, change at runtime, and stop inheriting sinks
        LoggerContext c3 = new LoggerContext();
        MemoryAppender shared = new MemoryAppender("shared");
        c3.configure(LogLevel.INFO, List.of(shared), List.of());
        Logger shop = c3.getLogger("com.shop");
        Logger checkout = c3.getLogger("com.shop.checkout");
        check(checkout.parent() == shop && shop.parent() == c3.getLogger("com"), "the tree is built by chopping at the dots");
        check(c3.getLogger("com.shop.checkout") == checkout, "one name means one object, forever");
        check(checkout.level() == null && checkout.effectiveLevel() == LogLevel.INFO, "a child with no level inherits ROOT's");
        checkout.debug("invisible");
        check(shared.lines().isEmpty(), "so its DEBUG is silent");
        shop.setLevel(LogLevel.DEBUG);
        checkout.debug("visible now");
        check(shared.lines().size() == 1, "turning an ancestor to DEBUG takes effect on the next call, with no restart");
        checkout.setLevel(LogLevel.WARN);
        checkout.info("invisible again");
        check(shared.lines().size() == 1, "a child's own level beats its ancestor's");
        checkout.setLevel(null);
        MemoryAppender own = new MemoryAppender("own");
        checkout.addAppender(own);
        checkout.info("two sinks");
        check(own.lines().size() == 1 && shared.lines().size() == 2, "additivity on: the line reaches the child's sink AND the shared one");
        checkout.setAdditive(false);
        checkout.info("one sink");
        check(own.lines().size() == 2 && shared.lines().size() == 2, "additivity off: the walk to the ancestors stops");

        // 4. one lock per sink: the same events into an unlocked counter and a locked one
        LoggerContext c4 = new LoggerContext();
        UnsafeCountingAppender unsafe = new UnsafeCountingAppender();
        SafeCountingAppender safe = new SafeCountingAppender("safe");
        Logger race = c4.getLogger("com.shop.race");
        race.addAppender(unsafe);
        race.addAppender(safe);
        race.setAdditive(false);
        int threads = 8, each = 2000, published = threads * each;
        Main.runConcurrently(threads, i -> { for (int k = 0; k < each; k++) race.info("tick"); });
        check(safe.count() == published, "the counter inside the sink's lock is exact: " + safe.count() + " of " + published);
        check(unsafe.count() <= published, "the counter with no lock lost updates: " + unsafe.count() + " of " + published);

        // 5. a storm bigger than the queue: bounded memory, and every lost event is counted
        LoggerContext c5 = new LoggerContext();
        SlowAppender slow = new SlowAppender("slow", 2);
        AsyncAppender small = new AsyncAppender("small", slow, 16, OverflowPolicy.DROP_NEWEST, LogLevel.FATAL);
        Logger storm = c5.getLogger("com.shop.storm");
        storm.addAppender(small);
        storm.setAdditive(false);
        int offered = 500, peak = 0;
        for (int i = 0; i < offered; i++) { storm.info("storm " + i); peak = Math.max(peak, small.queueDepth()); }
        small.close();
        check(peak <= 16, "the queue never went past its 16-event ceiling: peak depth " + peak + ", bounded by the capacity");
        check(slow.written() + small.droppedCount() == offered,
              "written " + slow.written() + " + dropped " + small.droppedCount() + " = offered " + offered);
        check(small.droppedCount() > 0, "under a storm a DROP_NEWEST sink really does shed load");
        LoggerContext c5b = new LoggerContext();
        MemoryAppender keeper = new MemoryAppender("keeper");
        AsyncAppender blocking = new AsyncAppender("blocking", keeper, 8, OverflowPolicy.BLOCK, LogLevel.ERROR);
        Logger audit = c5b.getLogger("com.shop.audit");
        audit.addAppender(blocking);
        audit.setAdditive(false);
        for (int i = 0; i < 200; i++) audit.info("audit " + i);
        blocking.close();
        check(keeper.lines().size() == 200 && blocking.droppedCount() == 0,
              "the same queue with a BLOCK policy makes the caller wait and loses nothing: " + keeper.lines().size());

        // 6. nothing the framework touches may throw into the application
        LoggerContext c6 = new LoggerContext();
        Status.reset();
        MemoryAppender survivor = new MemoryAppender("survivor");
        Logger risky = c6.getLogger("com.shop.risky");
        risky.addAppender(new Main.ThrowingAppender());
        risky.addAppender(survivor);
        risky.addFilter(e -> { throw new RuntimeException("broken filter"); });
        risky.setAdditive(false);
        risky.error("payment declined", new IllegalStateException("gateway timeout"));
        check(survivor.lines().size() == 1, "a sink that throws did not stop the next sink from getting the line");
        check(survivor.lines().get(0).contains("IllegalStateException"), "and the throwable is on the line");
        MemoryAppender bad = new MemoryAppender("bad", e -> { throw new RuntimeException("broken layout"); }, LogLevel.TRACE);
        risky.addAppender(bad);
        risky.warn("still fine");
        check(survivor.lines().size() == 2, "a formatter that throws cost only its own line");
        risky.info(() -> { throw new RuntimeException("broken supplier"); });
        check(survivor.lines().size() == 2, "a message supplier that throws wrote nothing and did not propagate");
        check(Status.errorCount() >= 4, "each failure was reported on the framework's own channel: " + Status.errorCount());

        // 7. rotation: the file rolls at the size, and not one line is lost across the files
        LoggerContext c7 = new LoggerContext();
        Path rollPath = dir.resolve("rolling.log");
        RollingFileAppender roller = new RollingFileAppender("roll", new TextFormatter(), LogLevel.TRACE, rollPath, 512);
        Logger big = c7.getLogger("com.shop.big");
        big.addAppender(roller);
        big.setAdditive(false);
        for (int i = 0; i < 60; i++) big.info("line " + i);
        int rolls = roller.rolls();
        roller.close();
        long total = 0;
        try (var s = Files.list(dir)) {
            for (Path p : s.toList())
                if (p.getFileName().toString().startsWith("rolling.log")) total += Files.readAllLines(p).size();
        }
        check(rolls >= 3, "60 lines into a 512-character file rolled " + rolls + " times");
        check(total == 60, "every line survived the rotation: " + total + " across the files");
        check(roller.bytesWritten() <= 512, "the live file is under the limit: " + roller.bytesWritten() + " characters");

        // 8. shutdown drains what was accepted, and the context on a line is the one from the call, not the write
        LoggerContext c8 = new LoggerContext();
        MemoryAppender late = new MemoryAppender("late");
        AsyncAppender tail = new AsyncAppender("tail", late, 1024, OverflowPolicy.BLOCK, LogLevel.ERROR);
        Logger job = c8.getLogger("com.shop.job");
        job.addAppender(tail);
        job.setAdditive(false);
        Mdc.put("rid", "req-A");
        for (int i = 0; i < 300; i++) job.info("work " + i);
        Mdc.put("rid", "req-B");
        Mdc.clear();
        c8.shutdown();
        check(late.lines().size() == 300, "close() wrote everything that was accepted before it: " + late.lines().size());
        check(late.lines().stream().allMatch(l -> l.contains("rid=req-A")),
              "every line carries the context from the moment of the call, not from the moment of the write");
        job.info("after shutdown");
        check(late.lines().size() == 300, "an event offered after close is counted, never half-written");
        check(tail.droppedCount() == 1, "and that one is on the dropped counter: " + tail.droppedCount());

        // 9. a stack trace is many physical lines and still ONE record. The whole block is one write under one
        //    lock, so eight threads throwing at the same instant can never splice their traces together.
        LoggerContext c9 = new LoggerContext();
        Path traces = dir.resolve("traces.log");
        FileAppender traceSink = new FileAppender("trace", new TextFormatter(), LogLevel.TRACE, traces, LogLevel.OFF);
        Logger boom = c9.getLogger("com.shop.boom");
        boom.addAppender(traceSink);
        boom.setAdditive(false);
        int throwers = 8, throws_ = 100;
        Main.runConcurrently(throwers, i -> {
            Throwable t = new IllegalStateException("boom from t" + i, new ArithmeticException("root cause t" + i));
            for (int k = 0; k < throws_; k++) boom.error("failed t" + i + "-" + k, t);
        });
        traceSink.close();
        List<String> phys = Files.readAllLines(traces);
        int records = 0, spliced = 0;
        String owner = null;
        for (String l : phys) {
            java.util.regex.Matcher h = java.util.regex.Pattern.compile("^\\d\\d:\\d\\d:\\d\\d\\.\\d\\d\\d .* - failed t(\\d+)-\\d+$").matcher(l);
            if (h.matches()) { records++; owner = h.group(1); }
            else if (owner == null) spliced++;                                   // a trace line with no header above it
            else if (l.startsWith("java.lang.IllegalStateException") && !l.endsWith("boom from t" + owner)) spliced++;
            else if (l.startsWith("Caused by: java.lang.ArithmeticException") && !l.endsWith("root cause t" + owner)) spliced++;
        }
        check(records == throwers * throws_, "8 threads x 100 exceptions are " + records + " records");
        check(spliced == 0, "every stack-trace line sits inside the record that owns it: no two threads spliced");
        check(phys.size() > records * 3, "and a record really is several physical lines: " + phys.size() + " lines for " + records + " records");
        check(phys.stream().anyMatch(l -> l.startsWith("Caused by: java.lang.ArithmeticException")), "the cause chain is written too, not just the top exception");

        // 10. the two rule changes an interviewer adds mid-round, both on the filter seam
        LoggerContext c10 = new LoggerContext();
        long[] t10 = { 1_789_205_400_000L };
        c10.setClock(() -> t10[0]);
        MemoryAppender capped = new MemoryAppender("capped");
        Logger retry = c10.getLogger("com.shop.retry");
        retry.addAppender(capped);
        retry.setAdditive(false);
        RateLimitFilter limiter = new RateLimitFilter(3, 60_000L, () -> t10[0], LogLevel.ERROR, 1000);
        retry.addFilter(limiter);
        for (int i = 0; i < 400; i++) retry.warn("connection refused, retrying");
        check(capped.lines().size() == 3, "400 identical WARNs inside one minute reached the sink 3 times: " + capped.lines().size());
        check(limiter.suppressedCount() == 397, "and the 397 it suppressed are counted, not hidden: " + limiter.suppressedCount());
        for (int i = 0; i < 4; i++) retry.error("gave up");
        check(capped.lines().size() == 7, "ERROR is never throttled: you do not silence the thing that wakes you");
        for (int i = 0; i < 50; i++) retry.warn("a different line " + i);
        check(capped.lines().size() == 57, "the cap is per distinct line, so 50 other WARNs went through untouched");
        t10[0] += 61_000L;
        retry.warn("connection refused, retrying");
        check(capped.lines().size() == 58, "and a minute later the window reopens");
        MemoryAppender sampled = new MemoryAppender("sampled");
        Logger noisy = c10.getLogger("com.shop.noisy");
        noisy.setLevel(LogLevel.DEBUG);
        noisy.addAppender(sampled);
        noisy.setAdditive(false);
        noisy.addFilter(new SamplingFilter(10, LogLevel.WARN));
        for (int i = 0; i < 100; i++) noisy.debug("chatter " + i);
        for (int i = 0; i < 5; i++) noisy.warn("never sampled");
        check(sampled.lines().size() == 15, "one DEBUG in ten kept and every WARN kept: " + sampled.lines().size());

        // 11. masking runs once, in the layout, and the Luhn check is what keeps it off an ordinary long number
        LoggerContext c11 = new LoggerContext();
        MemoryAppender masked = new MemoryAppender("masked", new MaskingFormatter(new TextFormatter()), LogLevel.TRACE);
        Logger pay = c11.getLogger("com.shop.pay");
        pay.addAppender(masked);
        pay.setAdditive(false);
        pay.info("refund to 4111 1111 1111 1111 for ann.smith@example.com");
        pay.info("order 1234567890123456 for request 1789205400000123456");
        String m0 = masked.lines().get(0), m1 = masked.lines().get(1);
        check(m0.contains("****-****-****-1111") && !m0.contains("4111 1111"), "the card number is redacted with its last four kept");
        check(m0.contains("***@example.com") && !m0.contains("ann.smith"), "and the address keeps only its domain");
        check(m1.contains("1234567890123456") && m1.contains("1789205400000123456"),
              "a sixteen-digit order number and a long request id are left alone: that is what the Luhn check buys");

        // 12. the sink as a network client: the buffer is cleared only AFTER the send returns
        List<String> shipped = new ArrayList<>();
        List<String> batchIds = new ArrayList<>();
        boolean[] down = { true };
        LogTransport flaky = (batchId, batch) -> {
            if (down[0]) { down[0] = false; throw new RuntimeException("collector 503"); }
            batchIds.add(batchId);
            shipped.addAll(batch);
        };
        LoggerContext c12 = new LoggerContext();
        HttpShipperAppender shipper = new HttpShipperAppender("ship", new JsonFormatter(), flaky, 2, 100);
        Logger ship = c12.getLogger("com.shop.ship");
        ship.addAppender(shipper);
        ship.setAdditive(false);
        for (int i = 0; i < 4; i++) ship.info("event " + i);
        shipper.close();
        check(shipped.size() == 4 && shipper.droppedCount() == 0,
              "the collector failed the first batch and not one line was lost: " + shipped.size() + " of 4");
        check(batchIds.size() == 2, "the failed lines went out in the next batch, under a batch id: " + batchIds);
        LoggerContext c12b = new LoggerContext();
        HttpShipperAppender deadEnd = new HttpShipperAppender("dead", new JsonFormatter(),
            (id, batch) -> { throw new RuntimeException("collector still down"); }, 2, 4);
        Logger far = c12b.getLogger("com.shop.far");
        far.addAppender(deadEnd);
        far.setAdditive(false);
        for (int i = 0; i < 20; i++) far.info("event " + i);
        deadEnd.close();
        check(deadEnd.droppedCount() == 20 && deadEnd.batchesSent() == 0,
              "a collector that never comes back sheds down to its retry cap and counts every line: " + deadEnd.droppedCount());

        // 13. the context a pooled thread cannot forget to put back
        Mdc.clear();
        Mdc.put("rid", "outer");
        try (MdcScope s = MdcScope.of("rid", "inner")) {
            check("inner".equals(Mdc.snapshot().get("rid")), "inside the scope the new value is the one that rides on the line");
        }
        check("outer".equals(Mdc.snapshot().get("rid")), "and on the way out the thread's context is exactly what it was: " + Mdc.snapshot());
        Mdc.clear();
        try (MdcScope s = MdcScope.of("tenant", "acme")) { /* the work of one request */ }
        check(Mdc.snapshot().isEmpty(), "a thread that started empty ends empty: that is what stops a pooled thread leaking a tenant");

        // 14. the other two rotations: keyed on the injected clock, and one file per tenant with a cap
        LoggerContext c14 = new LoggerContext();
        long[] t14 = { 1_789_205_400_000L };
        TimeRollingFileAppender byTime = new TimeRollingFileAppender("daily", new TextFormatter(), LogLevel.TRACE,
            dir.resolve("daily.log"), () -> t14[0], 86_400_000L);
        Logger day = c14.getLogger("com.shop.day");
        day.addAppender(byTime);
        day.setAdditive(false);
        for (int d = 0; d < 3; d++) { day.info("day " + d); t14[0] += 86_400_000L; }
        byTime.close();
        long dayLines = 0;
        try (var s = Files.list(dir)) {
            for (Path p : s.toList())
                if (p.getFileName().toString().startsWith("daily.log")) dayLines += Files.readAllLines(p).size();
        }
        check(byTime.rolls() == 2, "three days through an injected clock started " + byTime.rolls() + " new files, in a microsecond");
        check(dayLines == 3, "and all three lines survived the rotation: " + dayLines);
        RoutingAppender router = new RoutingAppender("per-tenant", "tenant",
            k -> new FileAppender("tenant-" + k, dir.resolve("tenant-" + k + ".log")), 2);
        Logger multi = c14.getLogger("com.shop.multi");
        multi.addAppender(router);
        multi.setAdditive(false);
        for (String t : List.of("acme", "globex", "acme", "initech"))
            try (MdcScope s = MdcScope.of("tenant", t)) { multi.info("hello from " + t); }
        multi.info("no tenant on this one");
        router.close();
        check(router.routeCount() == 2, "the per-tenant cap held at 2 files: a key that comes from request data cannot leak handles");
        check(router.unroutedCount() == 2, "the tenant past the cap and the event with no key were counted, not silently binned: " + router.unroutedCount());

        Status.sink(System.err);
        if (status.size() > 0 && failures != 0) System.out.println("status channel said: " + status);
        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
