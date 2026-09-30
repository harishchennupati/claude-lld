import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: roll at midnight -- the same rotation, keyed on a clock bucket instead of a byte count
/**
 * Rolls when the calendar bucket changes: a new hour, a new day, whatever periodMs says. It reuses the
 * handle-swap the base class already has and asks the injected Clock what time it is, so a test can roll
 * three days in a microsecond.
 */
final class TimeRollingFileAppender extends FileAppender {
    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd-HH").withZone(ZoneOffset.UTC);

    private final Clock clock;
    private final long periodMs;
    private long bucket;
    private int rolls;

    /** @param periodMs the length of one file, in milliseconds: 3600_000 for hourly, 86_400_000 for daily */
    TimeRollingFileAppender(String name, LogFormatter formatter, LogLevel threshold, Path path, Clock clock, long periodMs) {
        super(name, formatter, threshold, path, LogLevel.ERROR);
        this.clock = clock; this.periodMs = periodMs; this.bucket = clock.nowMs() / periodMs;
    }

    /** Runs under the sink's lock, so the check, the swap and the write are one step. */
    protected void write(LogEvent e, String line) throws IOException {
        long now = clock.nowMs() / periodMs;
        if (now != bucket && bytesWritten > 0) {
            closeWriter();
            rolls++;
            Files.move(path, path.resolveSibling(path.getFileName() + "." + STAMP.format(Instant.ofEpochMilli(bucket * periodMs))),
                StandardCopyOption.REPLACE_EXISTING);
            openWriter(false);
        }
        bucket = now;
        super.write(e, line);
    }

    /** How many times a new period started a new file. */
    int rolls() { lock.lock(); try { return rolls; } finally { lock.unlock(); } }
}

// ---- ext: one file per tenant -- a sink that picks a sink, created lazily and capped
/**
 * Reads a key off the event's context and forwards to the delegate for that key, building one lazily the
 * first time a tenant appears. The cap matters: keys that come from request data are user input, and an
 * uncapped map of sinks is a file-handle leak with a pretty name.
 */
final class RoutingAppender implements LogAppender {
    private final String name;
    private final String contextKey;
    private final java.util.function.Function<String, LogAppender> factory;
    private final int maxRoutes;
    private final ConcurrentHashMap<String, LogAppender> routes = new ConcurrentHashMap<>();
    private final AtomicLong unrouted = new AtomicLong();
    private volatile boolean started;

    /** @param contextKey which MDC key decides the destination; @param factory how to build a sink for one key */
    RoutingAppender(String name, String contextKey, java.util.function.Function<String, LogAppender> factory, int maxRoutes) {
        this.name = name; this.contextKey = contextKey; this.factory = factory; this.maxRoutes = maxRoutes;
    }

    public String name() { return name; }

    /** No key, or the cap reached, means the event is counted and dropped rather than opening file 100,001. */
    public void append(LogEvent e) {
        String key = e.context().get(contextKey);
        if (key == null) { unrouted.incrementAndGet(); return; }
        LogAppender target = routes.get(key);
        if (target == null) {
            if (routes.size() >= maxRoutes) { unrouted.incrementAndGet(); return; }
            target = routes.computeIfAbsent(key, k -> { LogAppender a = factory.apply(k); a.start(); return a; });
        }
        target.append(e);
    }

    public void start() { started = true; }

    /** Closes every sink it built. Nothing else knows those sinks exist. */
    public void close() {
        started = false;
        for (LogAppender a : routes.values()) { try { a.close(); } catch (RuntimeException ex) { Status.error(name + ": close", ex); } }
    }

    /** How many tenants have a file. */
    int routeCount() { return routes.size(); }

    /** Events with no key, or beyond the cap. */
    long unroutedCount() { return unrouted.get(); }
}

// ---- ext: mask before anything hits disk -- a formatter that wraps a formatter
/**
 * The Decorator again, one level down: it takes any layout, lets it build the line, then redacts the line.
 * Because it is a formatter it runs outside the sink's lock, once, and every sink downstream inherits it.
 */
final class MaskingFormatter implements LogFormatter {
    private static final Pattern CARD = Pattern.compile("\\b\\d(?:[ -]?\\d){12,18}\\b");
    private static final Pattern EMAIL = Pattern.compile("\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}\\b");

    private final LogFormatter inner;

    /** @param inner the layout being wrapped: text, JSON, or another masker */
    MaskingFormatter(LogFormatter inner) { this.inner = inner; }

    /** Card numbers keep their last four; e-mail addresses keep their domain. */
    public String format(LogEvent e) {
        String line = inner.format(e);
        Matcher m = CARD.matcher(line);
        StringBuilder sb = new StringBuilder(line.length());
        while (m.find()) {
            String digits = m.group().replaceAll("\\D", "");
            String rep = luhn(digits) ? "****-****-****-" + digits.substring(digits.length() - 4) : m.group();
            m.appendReplacement(sb, Matcher.quoteReplacement(rep));
        }
        m.appendTail(sb);
        return EMAIL.matcher(sb.toString()).replaceAll(x -> "***@" + x.group().substring(x.group().indexOf('@') + 1));
    }

    /** The checksum every card number satisfies. It is what keeps a long id or a timestamp from being redacted. */
    static boolean luhn(String digits) {
        int sum = 0;
        boolean alt = false;
        for (int i = digits.length() - 1; i >= 0; i--) {
            int d = digits.charAt(i) - '0';
            if (alt) { d *= 2; if (d > 9) d -= 9; }
            sum += d;
            alt = !alt;
        }
        return sum % 10 == 0;
    }
}

// ---- ext: log less -- sampling, and a cap on one repeated line, both behind the filter seam
/**
 * Keeps one DEBUG event in N and leaves everything at or above the bar alone. Adding it to a subtree turns
 * that subtree's volume down without touching a logger, a sink or a formatter.
 */
final class SamplingFilter implements LogFilter {
    private final int keepOneIn;
    private final LogLevel untouchedFrom;
    private final AtomicLong seen = new AtomicLong();

    /** @param keepOneIn 100 keeps one per cent; @param untouchedFrom at and above this level nothing is sampled */
    SamplingFilter(int keepOneIn, LogLevel untouchedFrom) { this.keepOneIn = keepOneIn; this.untouchedFrom = untouchedFrom; }

    /** NEUTRAL means "no opinion, carry on": the event survives unless something else denies it. */
    public FilterDecision decide(LogEvent e) {
        if (e.level().atLeast(untouchedFrom)) return FilterDecision.NEUTRAL;
        return seen.incrementAndGet() % keepOneIn == 0 ? FilterDecision.NEUTRAL : FilterDecision.DENY;
    }
}

/**
 * The mid-round rule change: a retry loop logged four hundred thousand identical WARNs and paged somebody.
 * This caps how often one distinct line may appear in a window. The counter is a compare-and-set over an
 * immutable window rather than a lock, because this sits on the hot path of every call.
 */
final class RateLimitFilter implements LogFilter {
    /** The count so far and when the window started, swapped as one value so it can never be half-updated. */
    private record Window(long startMs, int used) {}

    private final ConcurrentHashMap<String, AtomicReference<Window>> windows = new ConcurrentHashMap<>();
    private final int maxPerWindow;
    private final long windowMs;
    private final Clock clock;
    private final LogLevel untouchedFrom;
    private final int maxKeys;
    private final AtomicLong suppressed = new AtomicLong();

    /** @param untouchedFrom ERROR and above are never throttled: you do not silence the thing that wakes you */
    RateLimitFilter(int maxPerWindow, long windowMs, Clock clock, LogLevel untouchedFrom, int maxKeys) {
        this.maxPerWindow = maxPerWindow; this.windowMs = windowMs; this.clock = clock;
        this.untouchedFrom = untouchedFrom; this.maxKeys = maxKeys;
    }

    /** Keyed by logger plus message, so a thousand distinct lines are unaffected and one repeated line is capped. */
    public FilterDecision decide(LogEvent e) {
        if (e.level().atLeast(untouchedFrom)) return FilterDecision.NEUTRAL;
        String key = e.loggerName() + "|" + e.message();
        AtomicReference<Window> ref = windows.get(key);
        if (ref == null) {
            if (windows.size() >= maxKeys) return FilterDecision.NEUTRAL;
            ref = windows.computeIfAbsent(key, k -> new AtomicReference<>(new Window(clock.nowMs(), 0)));
        }
        while (true) {
            Window w = ref.get();
            long now = clock.nowMs();
            Window next = now - w.startMs() >= windowMs ? new Window(now, 1) : new Window(w.startMs(), w.used() + 1);
            if (next.used() > maxPerWindow) { suppressed.incrementAndGet(); return FilterDecision.DENY; }
            if (ref.compareAndSet(w, next)) return FilterDecision.NEUTRAL;
        }
    }

    /** How many lines were suppressed. Export it, or the cap is a lie told to whoever reads the log. */
    long suppressedCount() { return suppressed.get(); }
}

// ---- ext: context that cannot leak -- a scope a pooled thread cannot forget to clear
/**
 * The MDC bug that only shows up in production: a pooled thread keeps a request id and stamps it on the next
 * tenant's lines. try-with-resources makes forgetting impossible, because close() runs on every path out.
 */
final class MdcScope implements AutoCloseable {
    private final Map<String, String> saved;

    /** Saves whatever this thread already had, then adds the new keys. */
    MdcScope(Map<String, String> add) {
        saved = Mdc.snapshot();
        add.forEach(Mdc::put);
    }

    /** Two keys, the common case: MdcScope.of("rid", id). */
    static MdcScope of(String k, String v) { return new MdcScope(Map.of(k, v)); }

    /** Puts the thread's context back exactly as it was, including "empty". */
    public void close() {
        Mdc.clear();
        saved.forEach(Mdc::put);
    }
}

// ---- ext: ship the logs -- the appender as a network client, batched and at-least-once
/** Whatever actually moves bytes off the box: HTTP, gRPC, a Kafka producer. A lambda in a test. */
interface LogTransport {
    /** Send one batch under an id the far side can use to recognise a repeat. May throw; the sink catches it. */
    void send(String batchId, List<String> lines);
}

/**
 * A sink that talks to a collector. It batches, and it clears the buffer only after the send returns: a
 * failed send leaves the lines exactly where they were and the next flush retries them, which is why the
 * batch carries an id -- at-least-once delivery plus an id at the far side is exactly-once storage.
 */
final class HttpShipperAppender implements LogAppender {
    private final String name;
    private final LogFormatter formatter;
    private final LogTransport transport;
    private final int batchSize;
    private final int maxPending;
    private final List<String> pending = new ArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();
    private final AtomicLong batches = new AtomicLong();
    private final AtomicLong dropped = new AtomicLong();
    private volatile boolean started;

    /** @param maxPending the ceiling on the retry buffer: a collector that stays down must not eat the heap */
    HttpShipperAppender(String name, LogFormatter formatter, LogTransport transport, int batchSize, int maxPending) {
        this.name = name; this.formatter = formatter; this.transport = transport;
        this.batchSize = batchSize; this.maxPending = maxPending;
    }

    public String name() { return name; }

    /** Format outside the lock, as always; the lock covers only the buffer and the send. */
    public void append(LogEvent e) {
        if (!started) return;
        String line;
        try { line = formatter.format(e); } catch (RuntimeException ex) { Status.error(name + ": format", ex); return; }
        lock.lock();
        try {
            pending.add(line);
            if (pending.size() >= batchSize) flushLocked();
        } finally { lock.unlock(); }
    }

    public void start() { started = true; }

    /** Flush what is left, then stop. Anything that still will not send is counted, never silently binned. */
    public void close() {
        if (!started) return;
        started = false;
        lock.lock();
        try { flushLocked(); dropped.addAndGet(pending.size()); pending.clear(); }
        finally { lock.unlock(); }
    }

    /** Batches accepted by the collector. */
    long batchesSent() { return batches.get(); }

    /** Lines given up on: the retry buffer overflowed, or the collector was still down at close. */
    long droppedCount() { return dropped.get(); }

    /** Called with the lock held. The order is the whole point: send, and only then forget. */
    private void flushLocked() {
        if (pending.isEmpty()) return;
        String batchId = name + "-" + (batches.get() + 1);
        try {
            transport.send(batchId, List.copyOf(pending));
            batches.incrementAndGet();
            pending.clear();
        } catch (RuntimeException ex) {
            Status.error(name + ": send failed, will retry " + pending.size() + " lines", ex);
            while (pending.size() > maxPending) { pending.remove(0); dropped.incrementAndGet(); }
        }
    }
}

// ---- ext: configuration that outlives the process -- a repository for the level tree, and a hot reload
/** Where the level tree is kept between runs: a file, a table, a config service. One interface, two methods. */
interface LevelStore {
    /** logger name to level name, as text, because that is what a config file holds. */
    Map<String, String> load();

    /** Replace what is stored. In SQL: DELETE then INSERT inside one transaction, or an upsert per row. */
    void save(Map<String, String> levels);
}

/** The obvious implementation, for a test and for the demo. A file or a table is the same two methods. */
final class InMemoryLevelStore implements LevelStore {
    private volatile Map<String, String> data = new LinkedHashMap<>();

    public Map<String, String> load() { return new LinkedHashMap<>(data); }

    public void save(Map<String, String> levels) { data = new LinkedHashMap<>(levels); }
}

/**
 * A client of the framework, not a new concept inside it: it reads the store and calls the same setLevel
 * every test calls by hand. Because level is a volatile field, a reload takes effect on the very next call.
 */
final class Configurator {
    private Configurator() {}

    /** Apply a stored tree to a live context. Unknown names simply create the node, which is harmless. */
    static void apply(LoggerContext ctx, Map<String, String> levels) {
        levels.forEach((name, level) -> {
            try { ctx.getLogger(name).setLevel(LogLevel.valueOf(level)); }
            catch (IllegalArgumentException ex) { Status.error("bad level in config: " + name + "=" + level, ex); }
        });
    }

    /** Read every level anybody has set, so it can be written back. */
    static Map<String, String> snapshot(LoggerContext ctx) {
        Map<String, String> out = new LinkedHashMap<>();
        for (String n : ctx.names()) {
            LogLevel own = ctx.getLogger(n).level();
            if (own != null) out.put(n, own.name());
        }
        return out;
    }

    /** Ctrl-C must not lose the async tail. One line in main(), and shutdown() drains every queue. */
    static void installShutdownHook(LoggerContext ctx) {
        Runtime.getRuntime().addShutdownHook(new Thread(ctx::shutdown, "log-shutdown"));
    }
}

// ---- ext: why System.out is slow -- the same lines, one flush per call against one flush per buffer
/** Measures the cost of flushing on every line, which is what an autoflush PrintStream does for you. */
final class ConsoleCost {
    private ConsoleCost() {}

    /** Writes n lines to a file through an autoflush stream and returns the milliseconds it took. */
    static long autoflushMs(Path file, int n) throws IOException {
        try (PrintStream out = new PrintStream(new FileOutputStream(file.toFile()), true, StandardCharsets.UTF_8)) {
            long t0 = System.nanoTime();
            for (int i = 0; i < n; i++) out.println("12:00:00.000 INFO  [main] com.shop - line " + i);
            return (System.nanoTime() - t0) / 1_000_000;
        }
    }

    /** The same n lines through a 64 KB buffer, flushed once. Same bytes, one system call instead of n. */
    static long bufferedMs(Path file, int n) throws IOException {
        try (PrintStream out = new PrintStream(new BufferedOutputStream(new FileOutputStream(file.toFile()), 65536), false, StandardCharsets.UTF_8)) {
            long t0 = System.nanoTime();
            for (int i = 0; i < n; i++) out.println("12:00:00.000 INFO  [main] com.shop - line " + i);
            out.flush();
            return (System.nanoTime() - t0) / 1_000_000;
        }
    }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        Path dir = Files.createTempDirectory("logger-ext");
        LoggerContext ctx = new LoggerContext();
        long[] now = { 1_789_205_400_000L };
        ctx.setClock(() -> now[0]);
        Clock clock = () -> now[0];

        // roll at midnight: three days of logs, three files, in a microsecond
        Path daily = dir.resolve("daily.log");
        TimeRollingFileAppender timeRoll = new TimeRollingFileAppender("daily", new TextFormatter(), LogLevel.TRACE,
            daily, clock, 86_400_000L);
        Logger day = ctx.getLogger("com.shop.day");
        day.addAppender(timeRoll);
        day.setAdditive(false);
        for (int d = 0; d < 3; d++) { day.info("day " + d); now[0] += 86_400_000L; }
        timeRoll.close();
        System.out.println("time rolling: " + timeRoll.rolls() + " rolls, files "
            + Files.list(dir).map(p -> p.getFileName().toString()).sorted().toList());

        // one file per tenant
        RoutingAppender router = new RoutingAppender("per-tenant", "tenant",
            k -> new FileAppender("tenant-" + k, dir.resolve("tenant-" + k + ".log")), 2);
        router.start();
        Logger multi = ctx.getLogger("com.shop.multi");
        multi.addAppender(router);
        multi.setAdditive(false);
        for (String t : List.of("acme", "globex", "acme", "initech")) {
            try (MdcScope s = MdcScope.of("tenant", t)) { multi.info("hello from " + t); }
        }
        multi.info("no tenant on this one");
        router.close();
        System.out.println("routing: " + router.routeCount() + " tenant files (cap 2), "
            + router.unroutedCount() + " events with no route");

        // masking: the same line, redacted once, outside every sink's lock
        MemoryAppender masked = new MemoryAppender("masked", new MaskingFormatter(new TextFormatter()), LogLevel.TRACE);
        Logger pay = ctx.getLogger("com.shop.pay");
        pay.addAppender(masked);
        pay.setAdditive(false);
        pay.info("refund to 4111 1111 1111 1111 for ann.smith@example.com");
        System.out.println("masking: " + masked.lines().get(0));

        // sampling and the rate limit, both behind the filter seam
        MemoryAppender sampled = new MemoryAppender("sampled");
        Logger noisy = ctx.getLogger("com.shop.noisy");
        noisy.setLevel(LogLevel.DEBUG);
        noisy.addAppender(sampled);
        noisy.setAdditive(false);
        noisy.addFilter(new SamplingFilter(10, LogLevel.WARN));
        for (int i = 0; i < 100; i++) noisy.debug("chatter " + i);
        for (int i = 0; i < 5; i++) noisy.warn("this is never sampled");
        System.out.println("sampling: 100 DEBUG + 5 WARN -> " + sampled.lines().size() + " lines kept");

        MemoryAppender capped = new MemoryAppender("capped");
        Logger retry = ctx.getLogger("com.shop.retry");
        retry.addAppender(capped);
        retry.setAdditive(false);
        RateLimitFilter limiter = new RateLimitFilter(3, 60_000L, clock, LogLevel.ERROR, 1000);
        retry.addFilter(limiter);
        for (int i = 0; i < 400; i++) retry.warn("connection refused, retrying");
        for (int i = 0; i < 4; i++) retry.error("gave up");
        System.out.println("rate limit: 400 identical WARNs -> " + capped.lines().size()
            + " lines (3 WARN + 4 ERROR), suppressed " + limiter.suppressedCount());
        now[0] += 61_000L;
        retry.warn("connection refused, retrying");
        System.out.println("rate limit: a minute later the window reopens -> " + capped.lines().size() + " lines");

        // shipping: a collector that fails once, then accepts; nothing is lost and the batch id repeats
        List<String> received = new ArrayList<>();
        List<String> ids = new ArrayList<>();
        boolean[] down = { true };
        LogTransport transport = (batchId, lines) -> {
            if (down[0]) { down[0] = false; throw new RuntimeException("collector 503"); }
            ids.add(batchId);
            received.addAll(lines);
        };
        HttpShipperAppender shipper = new HttpShipperAppender("ship", new JsonFormatter(), transport, 2, 100);
        Logger ship = ctx.getLogger("com.shop.ship");
        ship.addAppender(shipper);
        ship.setAdditive(false);
        for (int i = 0; i < 4; i++) ship.info("event " + i);
        shipper.close();
        System.out.println("shipping: collector failed the first batch; received " + received.size()
            + " of 4 lines, batch ids " + ids + ", dropped " + shipper.droppedCount());

        // configuration that outlives the process
        LevelStore store = new InMemoryLevelStore();
        store.save(Map.of("com.shop.db", "DEBUG"));
        Configurator.apply(ctx, store.load());
        System.out.println("config: com.shop.db is now " + ctx.getLogger("com.shop.db").effectiveLevel()
            + "; saving back " + Configurator.snapshot(ctx).size() + " explicit levels");

        // why System.out is slow
        int n = 20_000;
        long auto = ConsoleCost.autoflushMs(dir.resolve("auto.txt"), n);
        long buffered = ConsoleCost.bufferedMs(dir.resolve("buffered.txt"), n);
        System.out.println("console cost: " + n + " lines, one flush per line " + auto
            + " ms vs one flush per buffer " + buffered + " ms");

        ctx.shutdown();
        System.out.println("extensions done; files under " + dir);
    }
}
