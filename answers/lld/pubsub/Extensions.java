import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: consumer groups -- competing consumers, where each message is handled by exactly ONE member
/**
 * Fan-out gives every subscriber every message. A consumer group is the other shape: three workers share the
 * load and each message is handled once. It needs no new broker code at all — a group member is a normal
 * subscription with a filter that accepts only its own slice of the key space. Messages with the same key
 * always land on the same member, so per-key order survives.
 */
final class ConsumerGroup {
    /** Start `members` subscriptions on one topic, each taking one slice. Returns them so a caller can stop one. */
    static List<Subscription> join(Broker broker, String groupId, String topic, int members, Handler handler) {
        List<Subscription> out = new ArrayList<>();
        for (int i = 0; i < members; i++) {
            final int slot = i;
            out.add(broker.subscribe(groupId + "#" + i, topic, handler,
                SubscribeOptions.opts().fromEarliest().filter(m -> slotOf(m, members) == slot)));
        }
        return out;
    }
    /** Which member owns this message: by key if there is one, else round-robin by offset. */
    static int slotOf(Message m, int members) {
        long h = m.key() == null ? m.offset() : (m.key().hashCode() & 0x7fffffffL);
        return (int) Math.floorMod(h, members);
    }
    // the honest price of doing it with filters: every member walks the whole log and skips 2 messages in 3.
    // Kafka gives each member its OWN partition log instead, which is the partitions extension below — the
    // same idea one level down, and the reason real consumer groups rebalance partitions rather than keys.
}

// ---- ext: never retry a message that can never work -- one decorator, no change to any policy or to Subscription
/** A failure that will fail identically forever: a malformed payload, a schema mismatch, a deleted account. */
class PermanentFailure extends Exception {
    PermanentFailure(String message) { super(message); }
}

/**
 * Wraps ANY retry policy and refuses to retry a permanent failure: "exponential backoff, but never five times
 * on a message that can never work". A new class and one line at the subscribe call; ExponentialBackoff,
 * Subscription, Topic and Broker are all untouched, which is the whole point of the interface.
 */
final class NoRetryFor implements RetryPolicy {
    private final RetryPolicy base;
    private final Class<? extends Exception> permanent;
    NoRetryFor(RetryPolicy base, Class<? extends Exception> permanent) { this.base = base; this.permanent = permanent; }
    public long backoffMs(int attempt, Exception failure) {
        if (permanent.isInstance(failure)) return -1;                    // straight to the dead-letter sink
        return base.backoffMs(attempt, failure);
    }
}

// ---- ext: a dead-letter TOPIC -- park failures where a human tool can subscribe to them and replay them
/**
 * The sink that a production broker ships with: instead of a list nobody reads, a message nobody could process
 * is published to "<topic>.dlq" with why-it-failed in the headers. The dead-letter queue is then just another
 * topic, so the repair tool is just another subscriber and a replay is just another publish.
 */
final class DeadLetterTopic implements DeadLetterSink {
    private final Broker broker;
    private final String suffix;
    DeadLetterTopic(Broker broker, String suffix) { this.broker = broker; this.suffix = suffix; }
    public void park(Dead d) {
        Message m = d.message();
        broker.publish(m.topic() + suffix, m.key(), m.payload(),
            Map.of("dlq.reason", d.reason(),
                   "dlq.attempts", String.valueOf(d.attempts()),
                   "dlq.subscription", d.subscriptionId(),
                   "dlq.origin", m.topic() + "@" + m.offset()));
    }
    /** Replay one parked message back onto its original topic, once it is fixed. */
    static long replay(Broker broker, Message parked) {
        String origin = parked.headers().get("dlq.origin");
        String topic = origin == null ? parked.topic() : origin.substring(0, origin.lastIndexOf('@'));
        return broker.publish(topic, parked.key(), parked.payload());
    }
}

// ---- ext: exactly-once for the handler -- at-least-once plus a memory of ids, which is the only honest version
/**
 * At-least-once means duplicates, so the handler must be idempotent: handling a message twice must have the same
 * effect as handling it once. When the business code is not, this decorator gets there: it remembers the ids
 * already handled and skips a repeat. The memory is bounded, because an unbounded one is a slow leak. It is also
 * locked, because one instance is often shared: ConsumerGroup hands the same handler to every member's thread.
 * In production the ids live in the database, written in the same transaction as the business change.
 */
final class IdempotentHandler implements Handler {
    private final Handler base;
    private final AtomicLong duplicates = new AtomicLong();
    private final LinkedHashMap<String, Boolean> seen;
    IdempotentHandler(Handler base, int remember) {
        this.base = base;
        this.seen = new LinkedHashMap<>(16, 0.75f, false) {
            @Override protected boolean removeEldestEntry(Map.Entry<String, Boolean> eldest) { return size() > remember; }
        };
    }
    public void onMessage(Message m) throws Exception {
        String id = m.headers().getOrDefault("id", m.topic() + "@" + m.offset());
        synchronized (seen) {
            if (seen.put(id, Boolean.TRUE) != null) { duplicates.incrementAndGet(); return; }   // already done: ack it again
        }
        try { base.onMessage(m); }                                       // outside the lock: members still run side by side
        catch (Exception e) { synchronized (seen) { seen.remove(id); } throw e; }   // a failure is not "done": retry it
    }
    /** How many repeats were swallowed. The number that tells you at-least-once is doing its job. */
    long duplicates() { return duplicates.get(); }
}

// ---- ext: pull instead of push -- consume() and ack(), the shape of Razorpay's statement and codezym's Kafka task
/** One batch handed to a pulling consumer, and the offset to acknowledge once all of it is done. */
record Batch(List<Message> messages, long next) {}

/**
 * The same log and the same cursors, but nobody pushes: a consumer calls consume() when it is ready. consume()
 * reads from the committed cursor and moves nothing, so a consumer that crashes before ack() is handed the same
 * batch again: at-least-once. ack(next) commits the whole batch at once. A filter leaves messages out of the
 * batch, and the ack steps over them too. No thread per consumer: one that is down simply stops calling, and its
 * cursor waits where it was. One caller per consumer id at a time; two callers would be handed the same batch.
 */
final class PullConsumers {
    private final Broker broker;
    private final Map<String, AtomicLong> cursors = new ConcurrentHashMap<>();   // "topic/consumer" -> next offset to read
    private final Map<String, Filter> filters = new ConcurrentHashMap<>();
    PullConsumers(Broker broker) { this.broker = broker; }

    /** Register a consumer: a new one starts at the end of the log, or at the oldest message the ring still holds. */
    void subscribe(String topic, String consumerId, boolean fromEarliest, Filter filter) {
        Topic t = broker.topic(topic);
        cursors.putIfAbsent(topic + "/" + consumerId, new AtomicLong(fromEarliest ? t.earliestOffset() : t.tailOffset()));
        filters.put(topic + "/" + consumerId, filter);
    }
    /**
     * Up to max messages from the committed cursor, in order, leaving out what the filter rejects. Moves nothing.
     * With waitMs above zero and nothing new, it waits in awaitAt until a publish wakes it: a long poll.
     */
    Batch consume(String topic, String consumerId, int max, long waitMs) throws InterruptedException {
        Topic t = broker.topic(topic);
        long next = t.clamp(cursor(topic, consumerId).get());           // what the ring overwrote is gone: start past it
        if (waitMs > 0) t.awaitAt(next, waitMs);                        // long poll: back as soon as offset `next` exists
        List<Message> out = new ArrayList<>();
        Filter f = filters.get(topic + "/" + consumerId);
        for (Message m; out.size() < max && (m = t.readAt(next)) != null; next++)
            if (f.accepts(m)) out.add(m);
        return new Batch(out, next);
    }
    /** The consumer finished everything below `next`: commit it. Never backwards, never past the end of the log. */
    void ack(String topic, String consumerId, long next) {
        long upTo = Math.min(next, broker.topic(topic).tailOffset());
        cursor(topic, consumerId).accumulateAndGet(upTo, Math::max);
    }
    /** The committed cursor: the next offset this consumer will be handed. */
    long committed(String topic, String consumerId) { return cursor(topic, consumerId).get(); }
    private AtomicLong cursor(String topic, String consumerId) {
        AtomicLong c = cursors.get(topic + "/" + consumerId);
        if (c == null) throw new NoSuchElementException("not subscribed: " + consumerId + " on " + topic);
        return c;
    }
}

// ---- ext: guaranteed delivery -- a full ring makes the publisher wait for the slowest subscriber (back-pressure)
/**
 * By default a full ring overwrites its oldest message and counts the loss: Kafka's choice. Razorpay's statement
 * asks for the opposite: every subscriber gets every message, even one that was down for an hour. Then a publish
 * must never overwrite a message some subscriber has not read. It waits for the slowest subscriber, and is
 * refused after a budget. That is back-pressure: the slow side pushes back on the fast side. The check and the
 * publish run one publisher at a time per topic, so two publishers can never both take the last free slot.
 * Every publisher of the topic must come through here.
 */
final class BackPressure {
    private final Broker broker;
    private final Map<String, ReentrantLock> gates = new ConcurrentHashMap<>();
    BackPressure(Broker broker) { this.broker = broker; }

    /** Publish once the ring has a slot no subscriber still needs. Wait while it has none, then refuse loudly. */
    long publish(String topic, String key, String payload, long budgetMs) throws InterruptedException {
        Topic t = broker.topic(topic);
        ReentrantLock gate = gates.computeIfAbsent(topic, k -> new ReentrantLock());
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(budgetMs);
        while (true) {
            gate.lock();
            try {                                                       // check and publish as one step
                if (t.tailOffset() - broker.slowestCursor(topic) < t.capacity()) return broker.publish(topic, key, payload);
            } finally { gate.unlock(); }
            if (System.nanoTime() >= deadline)
                throw new IllegalStateException("back-pressure: every slot of " + topic + " holds a message somebody has not read");
            Thread.sleep(1);                                            // nobody signals when a cursor moves: look again in 1 ms
        }
    }
    // the three answers for a full log, in the order a system usually grows through them: overwrite the oldest and
    // count it (the default ring, Kafka's choice); make the publisher wait (this); or spill the oldest messages to
    // disk and read them back when the slow consumer returns (Razorpay's plus point; the FileStore below is that file).
}

// ---- ext: lag metrics and an alarm -- the observer earning its keep
/**
 * A listener that counts what the broker does, plus the alarm a dashboard actually needs: which subscribers are
 * falling behind. The counts come from events; the lag comes from the O(1) numbers the subscriptions already
 * keep, so nothing is scanned and no counter can drift from the truth.
 */
final class LagMonitor implements BrokerListener {
    private final EnumMap<EventType, AtomicLong> counts = new EnumMap<>(EventType.class);
    LagMonitor() { for (EventType t : EventType.values()) counts.put(t, new AtomicLong()); }
    public void onEvent(Event e) { counts.get(e.type()).incrementAndGet(); }
    /** How many of this kind of event the broker has emitted. */
    long count(EventType t) { return counts.get(t).get(); }
    /** Every subscription more than `threshold` messages behind, worst first. */
    static List<String> alarming(Broker broker, long threshold) {
        List<Map.Entry<String, Long>> over = new ArrayList<>();
        broker.lagReport().forEach((id, lag) -> { if (lag > threshold) over.add(Map.entry(id, lag)); });
        over.sort((a, b) -> Long.compare(b.getValue(), a.getValue()));
        List<String> out = new ArrayList<>();
        for (Map.Entry<String, Long> e : over) out.add(e.getKey() + " (" + e.getValue() + " behind)");
        return out;
    }
}

// ---- ext: partitions -- N logs behind one name, so N publishers never meet, and order still holds per key
/**
 * Rung 1 of the ladder from move 8. One topic is one log and one lock; a partitioned topic is N logs and N
 * locks, with the key deciding which. Two publishers using different keys never wait for each other, and
 * per-key order survives because a key always lands in the same partition, which has one subscription and one
 * thread. What is lost is total order across the topic — exactly the trade Kafka makes.
 */
final class PartitionedTopic {
    private final Broker broker;
    private final String name;
    private final int partitions;
    PartitionedTopic(Broker broker, String name, int partitions) {
        this.broker = broker; this.name = name; this.partitions = partitions;
    }
    /** The partition this key belongs to, forever. Changing the count reshuffles keys, which is why it is fixed. */
    int partitionOf(String key) { return key == null ? 0 : (int) Math.floorMod(key.hashCode() & 0x7fffffffL, partitions); }
    /** The name of one underlying topic. */
    String partitionName(int p) { return name + "-p" + p; }
    /** Publish into the key's partition. One lock per partition, so N publishers scale linearly. */
    long publish(String key, String payload) { return broker.publish(partitionName(partitionOf(key)), key, payload); }
    /** One subscription per partition, all running the same handler: per-key order, N threads. */
    List<Subscription> subscribeAll(String subId, Handler h) {
        List<Subscription> out = new ArrayList<>();
        for (int p = 0; p < partitions; p++)
            out.add(broker.subscribe(subId + "-p" + p, partitionName(p), h, SubscribeOptions.opts().fromEarliest()));
        return out;
    }
}

// ---- ext: persistence -- the log on disk, and the cursors too, so a restart resumes instead of starting over
/** The seam. The topic's ring becomes a cache of the newest part of this file; nothing else in the design changes. */
interface MessageStore {
    /** Append one message after the topic gave it its offset. The line carries the offset, so a replay puts it back in place. */
    void append(Message m) throws IOException;
    /** Every stored message of one topic, in offset order. One sequential file read. */
    List<Message> replay(String topic) throws IOException;
}

/**
 * One append-only text file, one message per line: offset, topic, key, payload, timestamp. Key and payload are
 * Base64, so a tab or a newline inside them cannot break a line. A real one uses fixed-size files ("segments")
 * and forces each write to disk (FileChannel.force) before the publish returns.
 */
final class FileStore implements MessageStore {
    private final Path file;
    FileStore(Path file) throws IOException { this.file = file; if (!Files.exists(file)) Files.createFile(file); }
    public synchronized void append(Message m) throws IOException {
        String line = m.offset() + "\t" + m.topic() + "\t" + enc(m.key()) + "\t" + enc(m.payload()) + "\t" + m.atMs() + "\n";
        Files.writeString(file, line, StandardCharsets.UTF_8, StandardOpenOption.APPEND);
    }
    /** Lines may be out of order, because two publishers' listeners can write in either order: sort by offset. */
    public List<Message> replay(String topic) throws IOException {
        List<Message> out = new ArrayList<>();
        for (String line : Files.readAllLines(file, StandardCharsets.UTF_8)) {
            String[] f = line.split("\t", -1);
            if (f.length == 5 && f[1].equals(topic))
                out.add(new Message(Long.parseLong(f[0]), f[1], dec(f[2]), dec(f[3]), Map.of(), Long.parseLong(f[4])));
        }
        out.sort(Comparator.comparingLong(Message::offset));
        return out;
    }
    private static String enc(String s) { return s == null ? "-" : Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8)); }
    private static String dec(String f) { return f.equals("-") ? null : new String(Base64.getDecoder().decode(f), StandardCharsets.UTF_8); }
}

/** Where a subscriber's committed cursor lives across a restart. In Kafka this is the __consumer_offsets topic. */
interface OffsetStore {
    /** Remember that this subscription has finished everything below `offset`. */
    void commit(String subscriptionId, long offset);
    /** The remembered cursor, or the default for a subscriber that has never run. */
    long committed(String subscriptionId, long orElse);
}

/** The in-memory version, which is the file version wearing a different coat. */
final class InMemoryOffsets implements OffsetStore {
    private final Map<String, Long> at = new ConcurrentHashMap<>();
    public void commit(String subscriptionId, long offset) { at.put(subscriptionId, offset); }
    public long committed(String subscriptionId, long orElse) { return at.getOrDefault(subscriptionId, orElse); }
}

/** Restore a broker from a store after a restart, then resume each subscriber from its committed cursor. */
final class Recovery {
    /**
     * Put every stored message of a topic back into a fresh broker, at its own offset and with its own time.
     * Straight into the topic, not through publish(): a replay is not a new message, so no listener may store it again.
     */
    static int restore(Broker broker, MessageStore store, String topic) throws IOException {
        Topic t = broker.topic(topic);
        List<Message> stored = store.replay(topic);
        for (Message m : stored) {
            Message back = t.append(m.key(), m.payload(), m.headers(), m.atMs());
            if (back.offset() != m.offset()) throw new IllegalStateException("the stored log has a gap or a repeat at " + m.offset());
        }
        return stored.size();
    }
    /** Subscribe where this subscriber left off. One line, because the cursor was always just a number. */
    static Subscription resume(Broker broker, OffsetStore offsets, String subId, String topic, Handler h) {
        return broker.subscribe(subId, topic, h, SubscribeOptions.opts().fromOffset(offsets.committed(subId, 0)));
    }
    // and the two-process answer: this is where an in-process broker stops being the right tool. The log moves
    // out (Kafka, Pulsar, a table with a monotonic id), the topic's lock becomes the partition leader's, and the
    // cursor becomes a committed offset in the broker's own store. Every class here keeps its name — which is
    // why "explain Kafka" and "explain this file" are the same explanation at two sizes.
}

// ---- ext: replay from a point in time -- because nobody remembers an offset, they remember "since 9am"
/** Offset lookup by timestamp: a binary search over the ring, because append never lets a timestamp go down. */
final class TimeSeek {
    /** The first offset at or after this instant; the tail if everything retained is older. O(log n). */
    static long offsetAt(Topic topic, long atMs) {
        long lo = topic.earliestOffset(), hi = topic.tailOffset();
        while (lo < hi) {
            long mid = lo + (hi - lo) / 2;
            Message m = topic.readAt(mid);
            if (m == null || m.atMs() >= atMs) hi = mid; else lo = mid + 1;
        }
        return lo;
    }
}

// ---- ext: the Kafka mapping -- every class in Main.java has a name in the system they will compare this to
/** The table to put on the whiteboard when they ask "so how is this different from Kafka?". */
final class KafkaMapping {
    static final String[][] ROWS = {
        {"Topic (the ring + head offset)", "one partition's log: segment files on disk"},
        {"Message.offset", "the partition offset: same meaning, only ever goes up"},
        {"ring size; the oldest is overwritten", "retention.ms / retention.bytes: old segments are deleted"},
        {"Subscription.cursor (AtomicLong)", "a committed offset in the __consumer_offsets topic"},
        {"one dispatcher thread per subscription", "one consumer in a group, polling its partitions"},
        {"PullConsumers.consume / ack", "poll() / commitSync(): a Kafka consumer pulls"},
        {"Filter on the key (ConsumerGroup)", "partition assignment inside a consumer group"},
        {"cursor.incrementAndGet() after the handler", "enable.auto.commit=false, then commitSync() after processing"},
        {"DeadLetterSink", "a .dlq topic: not in Kafka itself; Kafka Connect and Spring Kafka add one"},
        {"lag() = tail - cursor", "consumer lag, the one metric that matters"},
        {"fast-forward when the ring overwrote", "OffsetOutOfRange, then auto.offset.reset=earliest"},
    };
    /** Print it, so the mapping is code rather than something you hope to remember. */
    static void print() {
        for (String[] r : ROWS) System.out.printf("  %-42s -> %s%n", r[0], r[1]);
    }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        Broker broker = new Broker(50);
        LagMonitor metrics = new LagMonitor();
        broker.addListener(metrics);
        broker.configure(new ExponentialBackoff(4, 1, 20), new DeadLetterTopic(broker, ".dlq"));

        // 1. consumer group: three workers, nine messages, each handled exactly once, same key to the same worker
        Map<String, List<String>> byWorker = new ConcurrentHashMap<>();
        ConsumerGroup.join(broker, "billing", "orders", 3, m -> {
            byWorker.computeIfAbsent(Thread.currentThread().getName() + "/" + ConsumerGroup.slotOf(m, 3),
                k -> new CopyOnWriteArrayList<>()).add(m.payload());
        });
        String[] keys = {"acc-1", "acc-2", "acc-3"};
        for (int i = 0; i < 9; i++) broker.publish("orders", keys[i % 3], "order-" + i);
        Main.awaitUntil(() -> byWorker.values().stream().mapToInt(List::size).sum() == 9, 2000);
        System.out.println("consumer group: 9 messages over " + byWorker.size() + " workers, "
            + byWorker.values().stream().mapToInt(List::size).sum() + " handled in total, no duplicates="
            + (new HashSet<>(byWorker.values().stream().flatMap(List::stream).toList()).size() == 9));

        // 2 + 3. a permanent failure goes straight to the dead-letter TOPIC; a transient one is retried
        AtomicInteger transientTries = new AtomicInteger();
        List<String> dlq = new CopyOnWriteArrayList<>();
        broker.subscribe("dlq-reader", "payments.dlq", m -> dlq.add(m.payload() + " <- " + m.headers().get("dlq.reason")),
            SubscribeOptions.opts().fromEarliest());
        broker.subscribe("payments", "payments", m -> {
            if (m.payload().startsWith("junk")) throw new PermanentFailure("not JSON");
            if (transientTries.incrementAndGet() <= 2) throw new IllegalStateException("gateway timeout");
        }, SubscribeOptions.opts().fromEarliest().retry(new NoRetryFor(new ExponentialBackoff(6, 1, 20), PermanentFailure.class)));
        broker.publish("payments", "a", "junk-1");
        broker.publish("payments", "b", "good-1");
        Main.awaitUntil(() -> dlq.size() == 1 && broker.sub("payments").delivered() == 1, 2000);
        System.out.println("permanent failure parked after " + broker.sub("payments").deadLettered()
            + " give-up, transient retried " + broker.sub("payments").retried() + " times; dlq topic holds " + dlq);

        // 4. exactly-once for the handler: the same message id delivered twice, the business code runs once
        AtomicInteger charged = new AtomicInteger();
        IdempotentHandler once = new IdempotentHandler(m -> charged.incrementAndGet(), 1000);
        broker.subscribe("charges", "charges", once, SubscribeOptions.opts().fromEarliest());
        for (int i = 0; i < 3; i++) broker.publish("charges", "c", "charge-7", Map.of("id", "txn-7"));
        Main.awaitUntil(() -> broker.sub("charges").delivered() == 3, 2000);
        System.out.println("idempotent handler: 3 deliveries, " + charged.get() + " charge, "
            + once.duplicates() + " duplicates swallowed");

        // 5. pull: consume() moves nothing, ack() commits the batch, a filtered consumer skips what is not its own
        PullConsumers pull = new PullConsumers(broker);
        pull.subscribe("refunds", "ledger", true, Filter.all());
        pull.subscribe("refunds", "india", true, m -> "IN".equals(m.key()));
        for (int i = 0; i < 5; i++) broker.publish("refunds", i % 2 == 0 ? "IN" : "US", "refund-" + i);
        Batch first = pull.consume("refunds", "ledger", 3, 0);
        Batch again = pull.consume("refunds", "ledger", 3, 0);                 // no ack yet: the same three again
        pull.ack("refunds", "ledger", first.next());
        Batch in = pull.consume("refunds", "india", 10, 0);
        System.out.println("pull: ledger got " + first.messages().size() + ", then the same " + again.messages().size()
            + " before its ack; committed now " + pull.committed("refunds", "ledger") + "; india got "
            + in.messages().stream().map(Message::payload).toList() + ", next ack " + in.next());

        // 6. guaranteed delivery: a subscriber that is down (paused) holds the ring; the publisher waits, is refused, then gets in
        Broker tiny = new Broker(4);
        Subscription down = tiny.subscribe("down", "bursty", m -> {});
        down.pause();
        BackPressure gate = new BackPressure(tiny);
        for (int i = 0; i < 4; i++) gate.publish("bursty", "k", "burst-" + i, 100);
        try {
            gate.publish("bursty", "k", "burst-x", 120);
            System.out.println("back-pressure: published");
        } catch (IllegalStateException e) {
            System.out.println("back-pressure: refused -- " + e.getMessage());
        }
        down.resume();
        System.out.println("after resume: burst-x published at offset " + gate.publish("bursty", "k", "burst-x", 2_000)
            + ", the subscriber missed " + down.missed());
        tiny.close();

        // 7. the lag alarm: a slow subscriber falls behind and the alarm names it
        broker.subscribe("molasses", "bursty", m -> Thread.sleep(50), SubscribeOptions.opts().fromEarliest());
        for (int i = 0; i < 4; i++) broker.publish("bursty", "k", "burst-" + i);
        System.out.println("lag alarm (>1 behind): " + LagMonitor.alarming(broker, 1));
        System.out.println("metrics: published=" + metrics.count(EventType.PUBLISHED)
            + " delivered=" + metrics.count(EventType.DELIVERED)
            + " retried=" + metrics.count(EventType.RETRIED)
            + " dead=" + metrics.count(EventType.DEAD_LETTERED)
            + " skipped=" + metrics.count(EventType.SKIPPED));

        // 8. partitions: same key, same partition, order kept per key, four locks instead of one
        PartitionedTopic trades = new PartitionedTopic(broker, "trades", 4);
        Map<String, List<String>> perKey = new ConcurrentHashMap<>();
        trades.subscribeAll("tape", m -> perKey.computeIfAbsent(m.key(), k -> new CopyOnWriteArrayList<>()).add(m.payload()));
        for (int i = 0; i < 6; i++) { trades.publish("INFY", "infy-" + i); trades.publish("TCS", "tcs-" + i); }
        Main.awaitUntil(() -> perKey.getOrDefault("INFY", List.of()).size() == 6
                           && perKey.getOrDefault("TCS", List.of()).size() == 6, 2000);
        System.out.println("partitions: INFY on p" + trades.partitionOf("INFY") + " -> " + perKey.get("INFY")
            + "  (order per key kept=" + perKey.get("INFY").equals(List.of("infy-0", "infy-1", "infy-2", "infy-3", "infy-4", "infy-5")) + ")");

        // 9. persistence: write the log to a file, restart into a fresh broker, resume a subscriber at its cursor
        Path file = Files.createTempFile("pubsub-log", ".tsv");
        FileStore store = new FileStore(file);
        OffsetStore offsets = new InMemoryOffsets();
        Broker before = new Broker(1000);
        before.addListener(e -> {
            if (e.type() == EventType.PUBLISHED) {
                try { store.append(before.topic(e.topic()).readAt(e.offset())); } catch (IOException io) { throw new UncheckedIOException(io); }
            }
        });
        for (int i = 0; i < 5; i++) before.publish("events", "e", "event-" + i);
        offsets.commit("reader", 3);                                       // this subscriber had finished the first three
        before.close();

        Broker after = new Broker(1000);
        int restored = Recovery.restore(after, store, "events");
        List<String> resumed = new CopyOnWriteArrayList<>();
        Recovery.resume(after, offsets, "reader", "events", m -> resumed.add(m.payload()));
        Main.awaitUntil(() -> resumed.size() == 2, 2000);
        System.out.println("persistence: " + restored + " messages restored from " + file.getFileName()
            + ", the reader resumed at offset 3 and saw " + resumed);

        // 10. replay from a point in time, with the clock handed in so the timestamps are exactly what we say
        Broker timed = new Broker(100);
        long[] tick = { 1_700_000_000_000L };
        timed.setClock(() -> tick[0]);
        for (int i = 0; i < 5; i++) { timed.publish("clicks", "c", "click-" + i); tick[0] += 60_000; }   // one a minute
        long cut = 1_700_000_000_000L + 3 * 60_000;
        System.out.println("seek by time: three minutes in, the first offset at or after is "
            + TimeSeek.offsetAt(timed.topic("clicks"), cut) + " (click-3)");
        timed.close();

        // 11. the mapping they will ask for
        System.out.println("how this maps onto Kafka:");
        KafkaMapping.print();

        after.close();
        broker.close();
        Files.deleteIfExists(file);
    }
}
