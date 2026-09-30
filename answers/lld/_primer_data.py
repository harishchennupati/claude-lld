# Java primer cards. Each code snippet = members of a class (methods + nested types), compiled inside a wrapper.
CARDS = [
# ---------------- A. LANGUAGE FOR LLD ----------------
dict(sec="A", id="enum", name="enum with fields and behaviour", one="A fixed set of named constants that can carry data and methods -- your sizes, states, order types.",
tell="An enum is a class with a fixed, named set of instances. Give it fields and a constructor and it replaces magic strings and if-chains; give it an abstract method and each constant can behave differently (a tiny State/Strategy without extra classes). Use EnumMap/EnumSet with it: array-backed, faster than HashMap.",
code='''enum SpotType {
    SMALL(10), COMPACT(20), LARGE(40);          // each constant carries its hourly rate
    final int rate;
    SpotType(int rate) { this.rate = rate; }
}
enum Op {                                       // constants with behaviour
    ADD { int apply(int a, int b) { return a + b; } },
    MUL { int apply(int a, int b) { return a * b; } };
    abstract int apply(int a, int b);
}
int price(SpotType t, int hours) { return t.rate * hours; }
java.util.EnumMap<SpotType, Integer> free = new java.util.EnumMap<>(SpotType.class);''',
mistake="Comparing enums with equals() when == is correct and null-safe; storing enum state as a String column of the model.",
say="\"Sizes are an enum, not strings -- the compiler catches a typo and EnumMap gives me O(1) per-size counts.\""),

dict(sec="A", id="interface", name="interface vs abstract class", one="Interface = a contract (what you can do). Abstract class = a partial implementation (what you are).",
tell="Program to the interface: services depend on PricingStrategy, never on FlatHourlyPricing. A class can implement many interfaces but extend one class -- so interfaces are for capabilities (Payable, Observer), abstract classes for a shared skeleton with state (Vehicle with a plate). Default methods let an interface ship a fallback without breaking implementers.",
code='''interface PricingStrategy {
    double price(long minutes);
    default double priceHours(long h) { return price(h * 60); }   // shared fallback, no state
}
abstract class Vehicle {                        // shared state + a hook
    final String plate;
    Vehicle(String plate) { this.plate = plate; }
    abstract int wheels();
}
class Car extends Vehicle { Car(String p) { super(p); } int wheels() { return 4; } }''',
mistake="Making an abstract class where an interface would do (locks the implementer into your hierarchy); putting state in interfaces via static mutable fields.",
say="\"Anything that will be swapped is an interface I inject; anything sharing fields is an abstract base.\""),

dict(sec="A", id="record", name="record and immutability", one="A record is an immutable data carrier with equals/hashCode/toString for free -- ideal for ids, events, DTOs.",
tell="Final fields set in the constructor, no setters. Immutable objects are thread-safe by construction and safe as map keys. Records give you that in one line and generate equals, hashCode and toString from the components. Mutation returns a new object (withX methods).",
code='''record Money(long paise) {                     // integer minor units, never double
    Money { if (paise < 0) throw new IllegalArgumentException("negative"); }   // compact validator
    Money plus(Money o) { return new Money(paise + o.paise); }
}
record OrderPlaced(String orderId, Money total, long ts) {}    // an event: immutable, comparable by value
final class Ticket {                            // pre-record style: final fields, no setters
    private final String id; private final long entryMs;
    Ticket(String id, long entryMs) { this.id = id; this.entryMs = entryMs; }
    String id() { return id; }
}''',
mistake="A record holding a mutable List and handing it out (callers mutate your 'immutable' object); money as double.",
say="\"Events and ids are records -- immutable, value-equal, safe to share across threads.\""),

dict(sec="A", id="equals", name="equals and hashCode contract", one="If two objects are equal they must have the same hashCode -- or your HashMap silently loses them.",
tell="HashMap and HashSet find a bucket by hashCode, then confirm with equals. Override one without the other and lookups fail randomly. Use the fields that define identity, keep them immutable (a key that changes hash after insertion is lost forever). Records and Objects.hash make this mechanical.",
code='''final class SpotId {
    private final String floor; private final int number;
    SpotId(String floor, int number) { this.floor = floor; this.number = number; }
    @Override public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SpotId s)) return false;         // pattern-match instanceof
        return number == s.number && floor.equals(s.floor);
    }
    @Override public int hashCode() { return java.util.Objects.hash(floor, number); }
}''',
mistake="Using a mutable object as a HashMap key; implementing equals with getClass() when instanceof was intended (or vice versa) without knowing why.",
say="\"Keys are immutable value objects with equals and hashCode over the identity fields.\""),

dict(sec="A", id="generics", name="generics you actually need", one="Type parameters on your own classes and methods; bounded types for 'anything comparable'; wildcards only when reading.",
tell="Write a generic class when the container does not care what it holds (Cache<K,V>, Repository<T,ID>). Bound it when you need a capability: <T extends Comparable<T>>. For parameters that are only read, accept List<? extends T>; you rarely need more than that in a round.",
code='''interface Repository<T, ID> {
    java.util.Optional<T> findById(ID id);
    void save(T entity);
}
class InMemoryRepo<T, ID> implements Repository<T, ID> {
    private final java.util.Map<ID, T> store = new java.util.concurrent.ConcurrentHashMap<>();
    private final java.util.function.Function<T, ID> idOf;
    InMemoryRepo(java.util.function.Function<T, ID> idOf) { this.idOf = idOf; }
    public java.util.Optional<T> findById(ID id) { return java.util.Optional.ofNullable(store.get(id)); }
    public void save(T e) { store.put(idOf.apply(e), e); }
}
static <T extends Comparable<T>> T max(java.util.List<? extends T> xs) {
    T best = xs.get(0);
    for (T x : xs) if (x.compareTo(best) > 0) best = x;
    return best;
}''',
mistake="Raw types (List instead of List<Ticket>); trying to new T() or T[] (erasure forbids it -- pass a factory).",
say="\"The repository is generic over entity and id, so every service gets the same in-memory store.\""),

dict(sec="A", id="collections", name="the collections cheat-sheet", one="Pick by operation you need: O(1) lookup, ordered, sorted, FIFO, priority.",
tell="ArrayList for indexed lists. ArrayDeque for stack and queue (never LinkedList, never Stack). HashMap for O(1) lookup; LinkedHashMap keeps insertion order -- and with accessOrder=true plus removeEldestEntry it is an LRU in ten lines. TreeMap when you need floor/ceiling/range (price ladders, time windows). PriorityQueue for 'smallest next' (min-heap by default; pass a comparator for max). EnumMap for enum keys.",
code='''java.util.Deque<Integer> stack = new java.util.ArrayDeque<>();     // push/pop/peek; also offer/poll for FIFO
java.util.TreeMap<Integer, Integer> book = new java.util.TreeMap<>();  // book.floorKey(x), book.firstEntry(), headMap(x)
java.util.PriorityQueue<int[]> byDist = new java.util.PriorityQueue<>((a, b) -> Integer.compare(a[1], b[1]));
class LruCache<K, V> extends java.util.LinkedHashMap<K, V> {
    private final int cap;
    LruCache(int cap) { super(16, 0.75f, true); this.cap = cap; }        // accessOrder = true
    @Override protected boolean removeEldestEntry(java.util.Map.Entry<K, V> e) { return size() > cap; }
}''',
mistake="Iterating a HashMap and expecting order; removing from a list while iterating it (ConcurrentModificationException -- use an Iterator or removeIf).",
say="\"LinkedHashMap in access order with removeEldestEntry is the LRU; I only hand-roll the doubly linked list if they ask for it.\""),

dict(sec="A", id="streams", name="lambdas, streams and comparators -- the 20% you use", one="Sort with Comparator.comparing, group with Collectors.groupingBy, and stop there in a round.",
tell="Lambdas implement single-method interfaces (Runnable, Comparator, Function). Comparator.comparing(...).thenComparing(...).reversed() reads like the requirement. Streams are fine for a one-line filter/map/collect; a for-loop is clearer for anything with state or early exit. Never stream inside a hot lock.",
code='''record Order(String id, int price, long ts) {}
java.util.List<Order> sorted(java.util.List<Order> os) {
    return os.stream()
             .sorted(java.util.Comparator.comparingInt(Order::price).reversed().thenComparingLong(Order::ts))
             .toList();
}
java.util.Map<Integer, java.util.List<Order>> byPrice(java.util.List<Order> os) {
    return os.stream().collect(java.util.stream.Collectors.groupingBy(Order::price));
}
int total(java.util.List<Order> os) { return os.stream().mapToInt(Order::price).sum(); }''',
mistake="Comparator subtraction (a.price - b.price) overflows; using streams for side effects; forgetting that toList() is unmodifiable.",
say="\"Price-time priority is one comparator: highest price, then earliest timestamp.\""),

dict(sec="A", id="exceptions", name="exceptions: checked, unchecked, custom", one="Throw unchecked for programming and state errors; make a small domain hierarchy; never swallow.",
tell="RuntimeException subclasses (IllegalArgumentException, IllegalStateException) need no throws clause and are what you want in a round. Checked exceptions (IOException, InterruptedException) force handling -- when catching InterruptedException, re-set the interrupt flag. Custom exceptions carry a reason code; one base class per domain lets callers catch broadly.",
code='''class DomainException extends RuntimeException { DomainException(String m) { super(m); } }
class InsufficientFundsException extends DomainException {
    final long shortBy;
    InsufficientFundsException(long shortBy) { super("short by " + shortBy); this.shortBy = shortBy; }
}
void withdraw(long balance, long amt) {
    if (amt <= 0) throw new IllegalArgumentException("amount must be positive");
    if (amt > balance) throw new InsufficientFundsException(amt - balance);
}
void sleepQuietly(long ms) {
    try { Thread.sleep(ms); }
    catch (InterruptedException e) { Thread.currentThread().interrupt(); }   // never swallow the interrupt
}''',
mistake="catch (Exception e) {} with an empty body; throwing generic RuntimeException with a string nobody can switch on.",
say="\"Domain errors are unchecked with a small hierarchy, so the API layer can map them to responses in one place.\""),

# ---------------- B. CONCURRENCY ----------------
dict(sec="B", id="threads", name="threads, Runnable, Callable, ExecutorService", one="Never new Thread() in a round: submit tasks to an executor, get Futures back, shut it down.",
tell="An ExecutorService owns a pool of threads. submit(Runnable) returns Future<?>; submit(Callable<T>) returns Future<T> whose get() blocks and rethrows the task's exception wrapped in ExecutionException. Always shutdown() and awaitTermination -- a live pool keeps the JVM alive. Size: CPU-bound = cores; IO-bound = more.",
code='''java.util.concurrent.ExecutorService pool = java.util.concurrent.Executors.newFixedThreadPool(4);
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
}''',
mistake="Calling future.get() inside the loop that submits (serialises everything); forgetting shutdown; swallowing ExecutionException.",
say="\"I submit to a fixed pool and collect Futures; the pool size is the concurrency limit, not the thread count in my code.\""),

dict(sec="B", id="synchronized", name="synchronized and the intrinsic lock", one="Every object has one lock; synchronized takes it for the block or method. Simple, reentrant, no timeout.",
tell="synchronized(obj) makes a block mutually exclusive on obj's monitor and publishes writes to the next thread that takes the same lock (visibility comes with the lock). A synchronized method locks this -- fine for small classes, dangerous when this is visible to callers who might lock it too. It is reentrant: a thread holding the lock can re-enter. No tryLock, no fairness, no interruptibility -- that is when you move to ReentrantLock.",
code='''class Counter {
    private int n;                                   // guarded by this
    synchronized void inc() { n++; }                 // read-modify-write is 3 ops; the lock makes it one
    synchronized int get() { return n; }             // reads need the lock too, for visibility
}
class Account {
    private final Object lock = new Object();        // private lock: callers cannot deadlock you
    private long balance;
    void deposit(long amt) { synchronized (lock) { balance += amt; } }
}''',
mistake="Synchronizing the write but not the read; synchronizing on a String literal or a boxed Integer (shared JVM-wide); check-then-act outside the lock.",
say="\"Counter is guarded by its own lock; both the increment and the read take it, because visibility needs the lock too.\""),

dict(sec="B", id="volatile", name="volatile: visibility, not atomicity", one="volatile guarantees every thread sees the latest write. It does not make ++ atomic.",
tell="Without volatile or a lock, a thread may cache a field forever and never see another thread's write. volatile forces reads and writes to main memory and forbids reordering around them. It is the right tool for a flag (running = false) and for the double-checked-locking singleton. It is the wrong tool for counters: n++ is read-modify-write and two threads still lose updates.",
code='''class Worker implements Runnable {
    private volatile boolean running = true;         // flag: one writer, many readers
    public void run() { while (running) { /* work */ } }
    void stop() { running = false; }                 // seen by run() promptly
}
class BrokenCounter {
    private volatile int n;
    void inc() { n++; }                              // WRONG under contention: lost updates
}''',
mistake="Believing volatile int fixes a counter; using a non-volatile boolean as a stop flag (the loop may never exit).",
say="\"The stop flag is volatile -- I need visibility, not atomicity. The counter is an AtomicInteger.\""),

dict(sec="B", id="reentrantlock", name="ReentrantLock: tryLock, fairness, finally", one="An explicit lock you can try with a timeout, make fair, and pair with Conditions. Always unlock in finally.",
tell="lock() then the critical section then unlock() in a finally block -- an exception without the finally leaves the lock held forever. tryLock(timeout) lets you fail instead of block (deadlock avoidance, back-pressure). new ReentrantLock(true) is fair: FIFO handoff at a throughput cost. It is reentrant like synchronized. Use it when you need any of these; otherwise synchronized is less code.",
code='''class ParkingLot {
    private final java.util.concurrent.locks.ReentrantLock lock = new java.util.concurrent.locks.ReentrantLock();
    String park(String plate) {
        lock.lock();
        try { return "spot for " + plate; }          // find + occupy + assign, atomic
        finally { lock.unlock(); }
    }
    boolean tryPark(String plate) throws InterruptedException {
        if (!lock.tryLock(200, java.util.concurrent.TimeUnit.MILLISECONDS)) return false;   // give up, do not queue
        try { return true; } finally { lock.unlock(); }
    }
}''',
mistake="unlock() outside finally; locking in one method and unlocking in another; holding the lock while doing IO or calling observers that might lock too.",
say="\"Explicit lock with unlock in finally; I'd use tryLock with a timeout at the gate so a stuck lot fails fast instead of piling threads.\""),

dict(sec="B", id="rwlock", name="ReadWriteLock: many readers, one writer", one="Readers share, writers exclude. Wins when reads dominate; costs more than a plain lock otherwise.",
tell="ReentrantReadWriteLock hands out a read lock (shared) and a write lock (exclusive). A config cache read a million times and updated hourly is the textbook case. Upgrading read to write is not allowed (deadlock) -- release the read lock, take the write lock, re-check. For very read-heavy data consider a volatile reference to an immutable snapshot instead: zero lock on read.",
code='''class ConfigCache {
    private final java.util.concurrent.locks.ReadWriteLock rw = new java.util.concurrent.locks.ReentrantReadWriteLock();
    private final java.util.Map<String, String> map = new java.util.HashMap<>();
    String get(String k) {
        rw.readLock().lock();
        try { return map.get(k); } finally { rw.readLock().unlock(); }
    }
    void put(String k, String v) {
        rw.writeLock().lock();
        try { map.put(k, v); } finally { rw.writeLock().unlock(); }
    }
}
class SnapshotCache {                                // lock-free reads: swap an immutable map
    private volatile java.util.Map<String, String> snap = java.util.Map.of();
    String get(String k) { return snap.get(k); }
    void replaceAll(java.util.Map<String, String> m) { snap = java.util.Map.copyOf(m); }
}''',
mistake="Trying to upgrade a read lock to a write lock; using RW lock when writes are frequent (readers starve or it is slower than a mutex).",
say="\"Reads dominate, so a read-write lock -- or better, readers hit a volatile immutable snapshot and never lock at all.\""),

dict(sec="B", id="condition", name="Condition / wait-notify: waiting for a state", one="Block until something becomes true, without spinning. Always wait in a while loop.",
tell="A Condition is tied to a lock: await() releases the lock and sleeps; signal()/signalAll() wakes waiters, who re-acquire the lock and must re-check the predicate -- spurious wake-ups and lost races are real, so the check is a while, never an if. wait/notify on an Object is the same idea with synchronized. Bounded buffer, blocking queue, H2O, print-in-order: all of them are this pattern.",
code='''class BoundedBuffer<T> {
    private final java.util.Deque<T> q = new java.util.ArrayDeque<>();
    private final int cap;
    private final java.util.concurrent.locks.ReentrantLock lock = new java.util.concurrent.locks.ReentrantLock();
    private final java.util.concurrent.locks.Condition notFull = lock.newCondition(), notEmpty = lock.newCondition();
    BoundedBuffer(int cap) { this.cap = cap; }
    void put(T x) throws InterruptedException {
        lock.lock();
        try { while (q.size() == cap) notFull.await(); q.addLast(x); notEmpty.signal(); }
        finally { lock.unlock(); }
    }
    T take() throws InterruptedException {
        lock.lock();
        try { while (q.isEmpty()) notEmpty.await(); T x = q.pollFirst(); notFull.signal(); return x; }
        finally { lock.unlock(); }
    }
}''',
mistake="if instead of while around await; signal() when several waiters wait on different predicates share one condition (use signalAll or two conditions); calling await without holding the lock.",
say="\"Two conditions, notFull and notEmpty, each awaited in a while loop -- that is the whole producer-consumer.\""),

dict(sec="B", id="atomic", name="Atomic* and the CAS loop", one="compareAndSet(expected, new) succeeds only if nobody changed it -- lock-free updates for counters, flags, references.",
tell="AtomicInteger.incrementAndGet is an atomic read-modify-write with no lock. For anything more complex, loop: read old, compute new, CAS; retry on failure. AtomicReference lets you CAS a whole immutable state object -- the lock-free way to claim a parking spot or flip a state machine. LongAdder beats AtomicLong under heavy contention for counters you only read occasionally.",
code='''java.util.concurrent.atomic.AtomicInteger seq = new java.util.concurrent.atomic.AtomicInteger();
int nextId() { return seq.incrementAndGet(); }
java.util.concurrent.atomic.AtomicReference<String> occupant = new java.util.concurrent.atomic.AtomicReference<>();
boolean claimSpot(String plate) { return occupant.compareAndSet(null, plate); }   // wins or loses, no lock
java.util.concurrent.atomic.AtomicLong balance = new java.util.concurrent.atomic.AtomicLong(100);
boolean withdraw(long amt) {
    while (true) {                                   // the CAS loop
        long cur = balance.get();
        if (cur < amt) return false;
        if (balance.compareAndSet(cur, cur - amt)) return true;   // someone else moved it: retry
    }
}''',
mistake="get() then set() as two steps (that is the race you were avoiding); CAS on a mutable object's field instead of swapping an immutable value.",
say="\"The spot's occupant is an AtomicReference; claiming it is one compareAndSet from null -- no lock, and a loser just tries the next spot.\""),

dict(sec="B", id="chm", name="ConcurrentHashMap: computeIfAbsent, merge, putIfAbsent", one="A thread-safe map whose compound operations are atomic per key -- your get-or-create and counter in one call.",
tell="HashMap corrupts under concurrent writes; Collections.synchronizedMap locks the whole map. ConcurrentHashMap locks per bin, and its compute methods make read-modify-write atomic for that key: computeIfAbsent for get-or-create (one lock per key, built lazily), merge for counters, putIfAbsent for claim-once. Iteration is weakly consistent: no exception, may miss concurrent updates. Do not block inside a compute function.",
code='''java.util.concurrent.ConcurrentHashMap<String, java.util.concurrent.locks.ReentrantLock> locks = new java.util.concurrent.ConcurrentHashMap<>();
java.util.concurrent.locks.ReentrantLock lockFor(String key) {
    return locks.computeIfAbsent(key, k -> new java.util.concurrent.locks.ReentrantLock());   // per-key lock, striped by key
}
java.util.concurrent.ConcurrentHashMap<String, Integer> hits = new java.util.concurrent.ConcurrentHashMap<>();
void hit(String url) { hits.merge(url, 1, Integer::sum); }                      // atomic counter per key
java.util.concurrent.ConcurrentHashMap<String, String> claims = new java.util.concurrent.ConcurrentHashMap<>();
boolean claim(String seat, String user) { return claims.putIfAbsent(seat, user) == null; }   // first writer wins''',
mistake="if (!map.containsKey(k)) map.put(k, v) -- two steps, racy; holding a lock inside computeIfAbsent; assuming size() is exact under load.",
say="\"putIfAbsent is my claim-once: the first thread to write the seat wins, the second sees a non-null and is rejected.\""),

dict(sec="B", id="blockingqueue", name="BlockingQueue: producer-consumer without writing a lock", one="put blocks when full, take blocks when empty. The bounded queue is your back-pressure.",
tell="ArrayBlockingQueue(cap) is the bounded buffer from the Condition card, already written and tested. Producers put, consumers take; the capacity limits memory and slows producers when consumers fall behind. offer(x, timeout) and poll(timeout) give up instead of blocking. Shut down with a poison pill or by interrupting consumers. LinkedBlockingQueue is unbounded by default -- say why you bounded it.",
code='''java.util.concurrent.BlockingQueue<String> q = new java.util.concurrent.ArrayBlockingQueue<>(1000);
static final String POISON = "__stop__";
void producer(java.util.List<String> jobs) throws InterruptedException {
    for (String j : jobs) q.put(j);                  // blocks when 1000 are waiting: back-pressure
    q.put(POISON);
}
void consumer() throws InterruptedException {
    while (true) {
        String j = q.take();                          // blocks when empty, no spinning
        if (j.equals(POISON)) return;
        process(j);
    }
}
void process(String j) {}''',
mistake="An unbounded queue with a slow consumer (OOM); busy-polling with poll() in a loop; forgetting how consumers stop.",
say="\"A bounded ArrayBlockingQueue: put blocks producers when consumers lag, which is the back-pressure -- no lock code of my own.\""),

dict(sec="B", id="semaphore", name="Semaphore, CountDownLatch, CyclicBarrier", one="Permits for 'at most N at once'; a latch for 'wait until N things are done'; a barrier for 'all meet here, then continue'.",
tell="Semaphore(N): acquire before the limited resource, release in finally -- a connection pool, a rate cap, H2O's two hydrogens. CountDownLatch(N): workers countDown, the waiter awaits once; it cannot be reset. CyclicBarrier(N): N threads await each other and then all proceed; reusable, with an optional action at the trip -- the H2O 'three atoms bond' pattern.",
code='''java.util.concurrent.Semaphore permits = new java.util.concurrent.Semaphore(3);   // max 3 concurrent downloads
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
java.util.concurrent.CyclicBarrier bond = new java.util.concurrent.CyclicBarrier(3, () -> System.out.println("H2O"));''',
mistake="release() outside finally (a leaked permit shrinks your pool forever); reusing a CountDownLatch; a barrier with the wrong party count hangs forever.",
say="\"Semaphore of N permits caps concurrency; release is in finally so an exception can never leak a permit.\""),

dict(sec="B", id="deadlock", name="deadlock, lock ordering, and lock striping", one="Two locks taken in opposite orders deadlock. Fix by a global order, a single lock, or tryLock with timeout.",
tell="Transfer(a, b) locking a then b while another thread does transfer(b, a) is the classic. Always acquire multiple locks in a canonical order (by id), or take one coarser lock, or tryLock both with a timeout and back off. Striping: instead of one global lock, an array of N locks indexed by hash(key) % N -- keys on different stripes proceed in parallel, the same key always serialises. That is the 'lock per floor / per size bucket' upgrade.",
code='''class Bank {
    void transfer(Account from, Account to, long amt) {
        Account first = from.id < to.id ? from : to, second = first == from ? to : from;   // canonical order
        synchronized (first) { synchronized (second) { from.balance -= amt; to.balance += amt; } }
    }
    static class Account { final int id; long balance; Account(int id) { this.id = id; } }
}
class Striped {
    private final java.util.concurrent.locks.ReentrantLock[] stripes = new java.util.concurrent.locks.ReentrantLock[16];
    Striped() { for (int i = 0; i < 16; i++) stripes[i] = new java.util.concurrent.locks.ReentrantLock(); }
    java.util.concurrent.locks.ReentrantLock forKey(Object k) { return stripes[(k.hashCode() & 0x7fffffff) % 16]; }
}''',
mistake="Locking on the objects in argument order; a global lock 'to be safe' that serialises every gate; forgetting that hashCode can be negative when picking a stripe.",
say="\"Two accounts, one order: lower id first, always. Under many gates I stripe the lock by floor so different floors park in parallel.\""),

dict(sec="B", id="immutability", name="immutability and confinement: the sync you do not write", one="If it never changes, or only one thread ever sees it, it needs no lock. Design for that first.",
tell="The best concurrency answer is often 'this object is immutable' or 'this state is owned by one thread'. Events, ids, config snapshots: immutable, share freely. Per-request state: confined to the thread, no sharing. ThreadLocal gives each thread its own copy (a formatter, a request context) -- clear it in a pool or it leaks between requests. Copy-on-write (CopyOnWriteArrayList, volatile snapshot swap) for listener lists that change rarely and are read constantly.",
code='''final class Snapshot { final java.util.Map<String, Integer> free; Snapshot(java.util.Map<String, Integer> f) { free = java.util.Map.copyOf(f); } }
class Board {
    private volatile Snapshot latest = new Snapshot(java.util.Map.of());    // readers: one volatile read, no lock
    void publish(java.util.Map<String, Integer> free) { latest = new Snapshot(free); }
    int free(String size) { return latest.free.getOrDefault(size, 0); }
}
java.util.concurrent.CopyOnWriteArrayList<Runnable> listeners = new java.util.concurrent.CopyOnWriteArrayList<>();   // iterate freely, add rarely
static final ThreadLocal<StringBuilder> BUF = ThreadLocal.withInitial(StringBuilder::new);''',
mistake="Sharing a mutable collection through a 'final' field and thinking final made it safe; CopyOnWrite for a list that changes on every request.",
say="\"The board reads a volatile immutable snapshot; the writer swaps it. No lock on the read path at all.\""),

dict(sec="B", id="completable", name="CompletableFuture: composing async work (SDE-3)", one="Chain async steps with thenApply/thenCompose, join fan-outs with allOf, add timeouts and fallbacks.",
tell="supplyAsync runs a task on a pool and returns a future you can compose without blocking. thenApply transforms, thenCompose chains another async call, thenCombine joins two, allOf waits for many, exceptionally supplies a fallback, orTimeout fails after a deadline. This is how you fan out to three services and join -- the pattern behind a feed that calls counters, media and profile in parallel.",
code='''java.util.concurrent.ExecutorService io = java.util.concurrent.Executors.newFixedThreadPool(8);
java.util.concurrent.CompletableFuture<String> fetchUser(String id) { return java.util.concurrent.CompletableFuture.supplyAsync(() -> "user:" + id, io); }
java.util.concurrent.CompletableFuture<Integer> fetchLikes(String id) { return java.util.concurrent.CompletableFuture.supplyAsync(() -> 42, io); }
String page(String id) {
    var user = fetchUser(id).orTimeout(300, java.util.concurrent.TimeUnit.MILLISECONDS);
    var likes = fetchLikes(id).exceptionally(e -> 0);                                    // degrade, do not fail the page
    return user.thenCombine(likes, (u, l) -> u + " likes=" + l).join();               // join = get() without checked exception
}''',
mistake="Calling join() inside a thenApply (blocks the pool thread); running IO on the common ForkJoinPool; no timeout on a remote call.",
say="\"Three independent fetches fan out as CompletableFutures on an IO pool and join with thenCombine; the non-critical one degrades with exceptionally.\""),

dict(sec="B", id="memorymodel", name="the memory model in three sentences (SDE-3)", one="Without a happens-before edge, a thread may never see another's write. Locks, volatile, and thread start/join create edges.",
tell="Java lets the compiler and CPU reorder and cache. A write is guaranteed visible to a read only if there is a happens-before chain between them: unlock happens-before the next lock of the same monitor; a volatile write happens-before a subsequent volatile read; Thread.start happens-before the thread's actions; a thread's actions happen-before join() returns; executor submit happens-before the task; future.get sees the task's writes. Every 'is this safe?' question reduces to 'where is the edge?'",
code='''class Config {
    private static volatile Config INSTANCE;             // volatile: the write of the fully built object is published
    static Config get() {
        Config c = INSTANCE;
        if (c == null) {
            synchronized (Config.class) {                 // double-checked locking, correct only with volatile
                c = INSTANCE;
                if (c == null) INSTANCE = c = new Config();
            }
        }
        return c;
    }
}
enum Registry { INSTANCE; }                                // the singleton with no such problem at all''',
mistake="Double-checked locking without volatile (a thread can see a non-null, half-constructed object); 'it works on my machine' as a visibility argument.",
say="\"The write is published by the unlock; the reader takes the same lock, so there is a happens-before edge and it sees it.\""),

# ---------------- C. SOLID ----------------
dict(sec="C", id="srp", name="S -- single responsibility", one="One class, one reason to change. The tell: a class whose name needs 'and'.",
tell="OrderService that validates, prices, persists and emails changes for four different reasons and is tested four ways at once. Split by reason-to-change: a validator, a pricer, a repository, a notifier -- the service orchestrates. In a round, the smell is one class over ~150 lines or a method that reads like a checklist.",
code='''// BEFORE: one class, four reasons to change
class OrderServiceBefore {
    void place(String order) { /* validate */ /* price */ /* save to db */ /* send email */ }
}
// AFTER: each concern is its own class; the service only orchestrates
interface Validator { void validate(String o); }
interface Pricer { long price(String o); }
interface OrderRepo { void save(String o, long price); }
interface Notifier { void placed(String o); }
class OrderService {
    private final Validator v; private final Pricer p; private final OrderRepo r; private final Notifier n;
    OrderService(Validator v, Pricer p, OrderRepo r, Notifier n) { this.v = v; this.p = p; this.r = r; this.n = n; }
    void place(String o) { v.validate(o); long price = p.price(o); r.save(o, price); n.placed(o); }
}''',
mistake="Splitting by noun instead of by reason-to-change (a 'Utils' class is not SRP); splitting so far that a feature touches ten files.",
say="\"Pricing changes for business reasons, persistence for infra reasons -- different classes, so a pricing change never risks the save.\""),

dict(sec="C", id="ocp", name="O -- open for extension, closed for modification", one="Add a new case by adding a class, not by editing a switch that already works.",
tell="A switch over payment types grows a case every quarter and every case re-tests the others. Put the varying behaviour behind an interface and register implementations; the caller never changes. Strategy, State and the Factory registry are all OCP in practice. The honest limit: some switches over a closed enum are fine -- OCP is for the axis that actually varies.",
code='''// BEFORE: every new method edits this switch
double feeBefore(String type, double amt) {
    switch (type) { case "CARD": return amt * 0.02; case "UPI": return 0; default: throw new IllegalArgumentException(); }
}
// AFTER: a new method is a new class registered once
interface FeePolicy { double fee(double amt); }
class CardFee implements FeePolicy { public double fee(double a) { return a * 0.02; } }
class UpiFee implements FeePolicy { public double fee(double a) { return 0; } }
java.util.Map<String, FeePolicy> policies = new java.util.HashMap<>(java.util.Map.of("CARD", new CardFee(), "UPI", new UpiFee()));
double fee(String type, double amt) { return policies.get(type).fee(amt); }''',
mistake="instanceof chains over a hierarchy (the hierarchy is telling you to add a method); over-abstracting an axis that never varies.",
say="\"Adding weekend pricing was a new class and one line at the call site -- the lot did not change. That is open-closed doing its job.\""),

dict(sec="C", id="lsp", name="L -- Liskov substitution", one="A subtype must be usable anywhere the parent is, without surprises: no stricter preconditions, no weaker guarantees, no thrown 'not supported'.",
tell="Square extends Rectangle breaks setWidth. A ReadOnlyList that throws on add breaks every caller of List. The fix is usually composition or a different interface split: model what the thing can actually do. In a round: if an override throws UnsupportedOperationException, or a caller checks the concrete type before calling, LSP is broken.",
code='''// BEFORE: subtype weakens the contract
class Bird { void fly() {} }
class Penguin extends Bird { @Override void fly() { throw new UnsupportedOperationException(); } }   // callers of Bird now crash
// AFTER: model the capability, not the taxonomy
interface Flyer { void fly(); }
class Sparrow implements Flyer { public void fly() {} }
class Emperor { void swim() {} }                       // a penguin is simply not a Flyer
void migrate(java.util.List<Flyer> flock) { for (Flyer f : flock) f.fly(); }   // never checks types''',
mistake="'is-a' chosen from real-world taxonomy instead of behaviour; overriding to no-op or throw.",
say="\"Any PricingStrategy drops in for another; the lot never downcasts or checks which one it got. That is substitutability.\""),

dict(sec="C", id="isp", name="I -- interface segregation", one="Small, role-specific interfaces. Nobody should implement methods they do not need.",
tell="A fat Worker interface with work(), eat(), sleep() forces a RobotWorker to implement eat(). Split by client need: Workable, Feedable. In LLD this is why PricingStrategy has one method and PaymentProcessor is separate -- a cash payment is never asked to price a ticket. Rule of thumb: an interface is named for a capability and has one to three methods.",
code='''// BEFORE: one fat interface
interface Machine { void print(); void scan(); void fax(); }
class BasicPrinter implements Machine { public void print() {} public void scan() { throw new UnsupportedOperationException(); } public void fax() { throw new UnsupportedOperationException(); } }
// AFTER: roles
interface Printer { void print(); }
interface Scanner { void scan(); }
class Simple implements Printer { public void print() {} }
class AllInOne implements Printer, Scanner { public void print() {} public void scan() {} }''',
mistake="One 'Service' interface with twelve methods that every implementation half-stubs; splitting into one-method interfaces for things always used together.",
say="\"One-method interfaces: a payment processor is never forced to know about pricing.\""),

dict(sec="C", id="dip", name="D -- dependency inversion (and injection)", one="Depend on abstractions; hand dependencies in through the constructor. The class never news its collaborators.",
tell="OrderService that does new MySqlRepo() inside is welded to MySQL and untestable. Depend on the Repo interface and receive it in the constructor; the composition root (main, or a DI framework) decides the concrete class. Constructor injection over setters: the object is valid the moment it exists. This is also the answer to 'how do you unit-test a singleton': you do not call getInstance inside -- you inject.",
code='''// BEFORE: welded to a concrete class, cannot be tested without a database
class ReportBefore { private final MySqlRepo repo = new MySqlRepo(); }
class MySqlRepo { java.util.List<String> all() { return java.util.List.of(); } }
// AFTER: depend on the interface, inject the implementation
interface Repo { java.util.List<String> all(); }
class Report {
    private final Repo repo;
    Report(Repo repo) { this.repo = repo; }             // constructor injection: valid on construction
    int count() { return repo.all().size(); }
}
class InMemoryRepo implements Repo { public java.util.List<String> all() { return java.util.List.of("a", "b"); } }
// composition root: new Report(new InMemoryRepo()) in tests, new Report(new SqlRepo()) in prod''',
mistake="Service locators and static getInstance() calls buried in business code; setter injection that leaves the object half-configured.",
say="\"The lot is handed its strategies through configure; in tests I hand it fakes. It never constructs a collaborator itself.\""),

# ---------------- D. PATTERNS ----------------
dict(sec="D", id="strategy", name="Strategy -- a swappable algorithm", one="Pain: 'they will want to change this rule'. Shape: an interface for the rule, injected.",
tell="Pricing, spot assignment, eviction policy, matching rule, rate-limit algorithm, payment method. The context holds a reference to the interface and calls it; a new rule is a new class. Name it only when the swap is real -- the moment the interviewer changes the rule mid-round is the moment it earns its name.",
code='''interface EvictionPolicy<K> { K victim(java.util.Collection<K> keys); }
class EvictLru<K> implements EvictionPolicy<K> { public K victim(java.util.Collection<K> keys) { return keys.iterator().next(); } }
class Cache<K, V> {
    private final java.util.Map<K, V> map = new java.util.LinkedHashMap<>();
    private final EvictionPolicy<K> policy; private final int cap;
    Cache(int cap, EvictionPolicy<K> policy) { this.cap = cap; this.policy = policy; }   // injected
    void put(K k, V v) { if (map.size() >= cap && !map.containsKey(k)) map.remove(policy.victim(map.keySet())); map.put(k, v); }
}''',
mistake="A strategy that needs six context fields passed in (it is not one algorithm, it is the whole class); announcing Strategy before any rule has varied.",
say="\"Eviction is a policy I inject; LRU today, LFU tomorrow, cache untouched.\""),

dict(sec="D", id="factory", name="Factory -- creation logic in one place", one="Pain: creation needs a decision (type string, config, environment). Shape: one method that returns the interface.",
tell="When new Car(...) versus new Truck(...) depends on input, put the decision in a factory so callers get a Vehicle and never a switch. A static factory method is enough in a round; a registry map from key to supplier is the extensible version (open-closed). Abstract Factory is a family of related products (a UI kit) -- name it only if asked.",
code='''interface Vehicle { int wheels(); }
class Bike implements Vehicle { public int wheels() { return 2; } }
class Car implements Vehicle { public int wheels() { return 4; } }
class VehicleFactory {
    private static final java.util.Map<String, java.util.function.Supplier<Vehicle>> REG =
        new java.util.HashMap<>(java.util.Map.of("bike", Bike::new, "car", Car::new));
    static Vehicle create(String type) {
        var s = REG.get(type.toLowerCase());
        if (s == null) throw new IllegalArgumentException("unknown vehicle: " + type);
        return s.get();
    }
    static void register(String type, java.util.function.Supplier<Vehicle> s) { REG.put(type, s); }   // new type, no edit
}''',
mistake="A factory for a class with one implementation; a switch inside the factory that grows forever when a registry map would not.",
say="\"Creation from a type string goes through a registry factory, so a new vehicle type is a registration, not an edit.\""),

dict(sec="D", id="observer", name="Observer -- publish a change, do not call the listeners by name", one="Pain: 'the board / email / audit log must update, but the core must not know about them'. Shape: subject keeps listeners, notifies on change.",
tell="The parking floor publishes 'occupancy changed'; the display board, the metrics and the audit log subscribe. The floor never imports any of them. Keep the listener list copy-on-write so notifying while someone subscribes is safe, and never call listeners while holding your own lock -- publish after unlock, or hand the event to a queue.",
code='''interface Listener<E> { void on(E event); }
class EventBus<E> {
    private final java.util.List<Listener<E>> ls = new java.util.concurrent.CopyOnWriteArrayList<>();
    void subscribe(Listener<E> l) { ls.add(l); }
    void publish(E e) { for (Listener<E> l : ls) l.on(e); }   // iterate a snapshot; safe against concurrent subscribe
}
record Occupancy(String floor, int free) {}
class Floor {
    final EventBus<Occupancy> bus = new EventBus<>();
    private int free = 10;
    void occupy() { int f; synchronized (this) { f = --free; } bus.publish(new Occupancy("F1", f)); }   // publish outside the lock
}''',
mistake="Notifying inside the critical section (a slow listener blocks every gate; a listener that locks back deadlocks you); a listener that throws and stops the others.",
say="\"The floor publishes an occupancy event after it releases its lock; the board is a subscriber the floor never names.\""),

dict(sec="D", id="state", name="State -- behaviour depends on which state you are in", one="Pain: methods full of 'if (status == X)'. Shape: one class per state, the context delegates, transitions return the next state.",
tell="Vending machine, elevator, order lifecycle, ticket lifecycle, connection. Each state implements the same interface; illegal operations in a state are explicit (throw or no-op) instead of buried in a switch. Transitions are the only place state changes. For simple lifecycles an enum with a transition table is enough -- say so.",
code='''interface VmState { VmState insertCoin(Vm vm); VmState select(Vm vm); }
class Idle implements VmState {
    public VmState insertCoin(Vm vm) { vm.credit++; return new HasCoin(); }
    public VmState select(Vm vm) { throw new IllegalStateException("insert a coin first"); }
}
class HasCoin implements VmState {
    public VmState insertCoin(Vm vm) { vm.credit++; return this; }
    public VmState select(Vm vm) { vm.credit--; vm.dispensed++; return vm.credit > 0 ? this : new Idle(); }
}
class Vm {
    int credit, dispensed; private VmState state = new Idle();
    void insertCoin() { state = state.insertCoin(this); }
    void select() { state = state.select(this); }
}
enum OrderStatus { CREATED, PAID, SHIPPED, DELIVERED, CANCELLED }       // simple lifecycles: enum + a transition check''',
mistake="A giant switch on status in every method; states that reach into the context's private fields; allowing any transition.",
say="\"Ticket status is a small state machine: lost is one transition that bills the cap, not an if scattered through unpark.\""),

dict(sec="D", id="command", name="Command -- an action as an object (undo, queue, replay)", one="Pain: undo/redo, scheduling, audit of operations. Shape: execute() and undo() on an object that captures its arguments.",
tell="Text editor, spreadsheet, task scheduler, transaction log. Each user action becomes a Command with enough captured state to reverse itself; a history stack gives undo, a second stack gives redo. Commands can be queued, retried, logged, replayed -- which is why an append-only log of commands is also event sourcing's cousin.",
code='''interface Command { void execute(); void undo(); }
class Editor { final StringBuilder text = new StringBuilder(); }
class Insert implements Command {
    private final Editor ed; private final int at; private final String s;
    Insert(Editor ed, int at, String s) { this.ed = ed; this.at = at; this.s = s; }
    public void execute() { ed.text.insert(at, s); }
    public void undo() { ed.text.delete(at, at + s.length()); }
}
class History {
    private final java.util.Deque<Command> done = new java.util.ArrayDeque<>(), undone = new java.util.ArrayDeque<>();
    void run(Command c) { c.execute(); done.push(c); undone.clear(); }
    void undo() { if (!done.isEmpty()) { Command c = done.pop(); c.undo(); undone.push(c); } }
    void redo() { if (!undone.isEmpty()) { Command c = undone.pop(); c.execute(); done.push(c); } }
}''',
mistake="Undo implemented by snapshotting the whole document per keystroke (Memento is for that, and it is heavy); clearing redo forgotten after a new command.",
say="\"Every edit is a Command with its own undo; two stacks give undo and redo, and the same objects can be logged and replayed.\""),

dict(sec="D", id="decorator", name="Decorator -- wrap to add behaviour, keep the interface", one="Pain: 'add surge / logging / caching / retry to X without touching X'. Shape: implement the same interface, hold the wrapped one.",
tell="WeekendSurge wraps FlatHourly; a CachingRepo wraps a Repo; a RetryingClient wraps a Client. Each decorator implements the interface and delegates, adding its behaviour before or after. They stack in any order. The tell that it is Decorator and not Strategy: it keeps the original and calls it.",
code='''interface Pricing { double price(long minutes); }
class Flat implements Pricing { public double price(long m) { return Math.ceil(m / 60.0) * 20; } }
class Surge implements Pricing {                       // wraps, does not replace
    private final Pricing base; private final double factor;
    Surge(Pricing base, double factor) { this.base = base; this.factor = factor; }
    public double price(long m) { return base.price(m) * factor; }
}
class Capped implements Pricing {
    private final Pricing base; private final double cap;
    Capped(Pricing base, double cap) { this.base = base; this.cap = cap; }
    public double price(long m) { return Math.min(cap, base.price(m)); }
}
Pricing weekend = new Capped(new Surge(new Flat(), 1.5), 500);   // stacks: cap(surge(flat))''',
mistake="Subclassing Flat to make Surge (one subclass per combination explodes); a decorator that changes the interface (that is Adapter).",
say="\"Surge wraps the base rule and multiplies -- a Decorator, so surge-plus-cap is just two wraps.\""),

dict(sec="D", id="builder", name="Builder -- constructing an object with many optional parts", one="Pain: a constructor with eight parameters, four of them nullable. Shape: a fluent builder that validates in build().",
tell="Search queries, HTTP requests, configuration, an Order with optional coupon, address, notes. The builder collects parts by name, applies defaults, validates once in build(), and returns an immutable object. In a round, mention it when a constructor call would need comments to read.",
code='''final class Request {
    final String url, method; final java.util.Map<String, String> headers; final int timeoutMs;
    private Request(Builder b) { url = b.url; method = b.method; headers = java.util.Map.copyOf(b.headers); timeoutMs = b.timeoutMs; }
    static Builder to(String url) { return new Builder(url); }
    static final class Builder {
        private final String url; private String method = "GET"; private int timeoutMs = 1000;
        private final java.util.Map<String, String> headers = new java.util.HashMap<>();
        Builder(String url) { this.url = url; }
        Builder method(String m) { method = m; return this; }
        Builder header(String k, String v) { headers.put(k, v); return this; }
        Builder timeout(int ms) { timeoutMs = ms; return this; }
        Request build() { if (timeoutMs <= 0) throw new IllegalStateException("timeout"); return new Request(this); }
    }
}
Request r = Request.to("/x").method("POST").header("a", "b").timeout(500).build();''',
mistake="A builder for a two-field class; a builder that returns a mutable object; validation spread over setters instead of build().",
say="\"Eight optional fields: a builder with defaults and one validation in build, returning an immutable request.\""),

dict(sec="D", id="singleton", name="Singleton -- exactly one, and why you avoid it", one="Pain: one registry, one connection pool, one lot. Shape: enum singleton or a static holder; then inject it anyway.",
tell="The enum singleton is thread-safe, serialisation-safe and one line. The holder idiom (nested static class) is lazy and safe without volatile. Double-checked locking needs volatile. Then the senior sentence: the singleton is a composition-root convenience -- business classes receive it through the constructor, never call getInstance, or they cannot be tested.",
code='''enum Registry { INSTANCE; final java.util.Map<String, String> m = new java.util.concurrent.ConcurrentHashMap<>(); }
class Pool {
    private Pool() {}
    private static class Holder { static final Pool INSTANCE = new Pool(); }   // lazy, thread-safe by class-init rules
    static Pool get() { return Holder.INSTANCE; }
}
class Service {
    private final Pool pool;
    Service(Pool pool) { this.pool = pool; }              // injected -- tests pass a fake
}''',
mistake="getInstance() calls sprinkled through services; mutable global state disguised as a singleton; DCL without volatile.",
say="\"One lot instance via a holder, but every service gets it injected -- so tests never touch the static.\""),

dict(sec="D", id="template", name="Template Method and Chain of Responsibility", one="Template: a fixed skeleton with overridable steps. Chain: a request passes handlers until one takes it.",
tell="Template Method: an abstract class defines the algorithm's steps in order (validate, execute, record) and subclasses fill hooks -- payment flows, report generation. Chain of Responsibility: handlers linked in sequence, each decides to handle or pass -- request filters, approval levels, ATM dispensing by denomination, logging levels. Prefer composition (a list of handlers) over a linked chain in a round.",
code='''abstract class PaymentFlow {
    final boolean pay(long amt) { if (!validate(amt)) return false; boolean ok = charge(amt); record(amt, ok); return ok; }   // the template
    protected boolean validate(long amt) { return amt > 0; }
    protected abstract boolean charge(long amt);
    protected void record(long amt, boolean ok) {}
}
class CardFlow extends PaymentFlow { protected boolean charge(long amt) { return true; } }
interface Handler { boolean handle(String req); }          // chain: first handler that returns true stops it
class Pipeline {
    private final java.util.List<Handler> hs = new java.util.ArrayList<>();
    Pipeline add(Handler h) { hs.add(h); return this; }
    boolean run(String req) { for (Handler h : hs) if (h.handle(req)) return true; return false; }
}''',
mistake="Template Method hierarchies three levels deep (prefer Strategy composition); a chain where every handler must be called (that is a pipeline, not CoR).",
say="\"Approval is a chain: manager, director, VP -- each handles or passes; adding a level is a new handler.\""),

dict(sec="D", id="adapter", name="Adapter, Facade, Proxy -- the wrapping trio", one="Adapter converts an interface; Facade simplifies a subsystem; Proxy controls access to the same interface.",
tell="Adapter: your PaymentProcessor interface over a third-party SDK with a different shape. Facade: one BookingFacade over inventory, payment and notification so the controller makes one call. Proxy: same interface as the real object, adds lazy loading, access control, caching or rate limiting in front. In a round, name them in one sentence and move on.",
code='''interface PaymentProcessor { boolean pay(long paise); }
class StripeSdk { String charge(double dollars) { return "ok"; } }                 // foreign shape
class StripeAdapter implements PaymentProcessor {
    private final StripeSdk sdk = new StripeSdk();
    public boolean pay(long paise) { return sdk.charge(paise / 100.0).equals("ok"); }
}
class BookingFacade {                                                              // one call for the controller
    boolean book(String seat, String user, long paise) { return true; /* inventory, payment, notify */ }
}
class RateLimitedProcessor implements PaymentProcessor {                          // proxy: same interface, gate in front
    private final PaymentProcessor real; private final java.util.concurrent.Semaphore permits = new java.util.concurrent.Semaphore(10);
    RateLimitedProcessor(PaymentProcessor real) { this.real = real; }
    public boolean pay(long p) { if (!permits.tryAcquire()) return false; try { return real.pay(p); } finally { permits.release(); } }
}''',
mistake="Calling the SDK directly from services (no seam to test or swap); a facade that becomes the new god class.",
say="\"The SDK sits behind an adapter that implements my PaymentProcessor, so the service never sees Stripe.\""),

dict(sec="D", id="repository", name="Repository and the models / services / repositories split", one="Models hold data and invariants. Services hold use cases. Repositories hold storage. Nothing else.",
tell="The three-layer split is what interviewers expect in a machine-coding round. Models: entities and value objects with their own invariants (a Ticket cannot close twice). Services: one per use case cluster, orchestrating models and repositories, owning the locks. Repositories: Map-backed today, a database tomorrow, behind an interface. Controllers or gates are thin. Ids are generated in one place.",
code='''record Seat(String id) {}
final class Booking { final String id, seatId, userId; Booking(String id, String s, String u) { this.id = id; seatId = s; userId = u; } }
interface BookingRepo { java.util.Optional<Booking> bySeat(String seatId); void save(Booking b); }
class InMemoryBookingRepo implements BookingRepo {
    private final java.util.Map<String, Booking> bySeat = new java.util.concurrent.ConcurrentHashMap<>();
    public java.util.Optional<Booking> bySeat(String s) { return java.util.Optional.ofNullable(bySeat.get(s)); }
    public void save(Booking b) { if (bySeat.putIfAbsent(b.seatId, b) != null) throw new IllegalStateException("seat taken"); }
}
class BookingService {
    private final BookingRepo repo; private final java.util.concurrent.atomic.AtomicLong ids = new java.util.concurrent.atomic.AtomicLong();
    BookingService(BookingRepo repo) { this.repo = repo; }
    Booking book(Seat seat, String user) { Booking b = new Booking("b" + ids.incrementAndGet(), seat.id(), user); repo.save(b); return b; }
}''',
mistake="Business rules inside the repository; services reaching into other services' maps; models with public mutable fields.",
say="\"Models, services, repositories. The service owns the use case and the lock; the repository is a map behind an interface.\""),

# ---------------- E. PRINCIPLES BEYOND SOLID ----------------
dict(sec="E", id="composition", name="composition over inheritance", one="Has-a beats is-a unless the subtype is truly a kind-of and shares the base's contract.",
tell="Inheritance couples you to the parent's implementation and gives one axis of variation. Composition lets you combine behaviours (a Vehicle has an Engine and a Pricing) and swap them at runtime. Use inheritance for Car is-a Vehicle where the whole contract holds; use composition for everything that is a capability or a policy. Decorator and Strategy are composition.",
code='''// inheritance explosion: SportsCarWithSunroofAndTurbo ...
// composition: one class, capabilities plugged in
interface Engine { int hp(); }
interface Roof { boolean opens(); }
class Turbo implements Engine { public int hp() { return 300; } }
class Sunroof implements Roof { public boolean opens() { return true; } }
final class Car {
    private final Engine engine; private final Roof roof;
    Car(Engine e, Roof r) { engine = e; roof = r; }
    int hp() { return engine.hp(); }
}''',
mistake="Deep hierarchies for feature combinations; protected fields as a sharing mechanism.",
say="\"Car has-an Engine; I compose rather than subclass so options combine without a class per combination.\""),

dict(sec="E", id="encapsulate", name="encapsulate what varies, program to interfaces, law of Demeter", one="Find the axis that changes, hide it behind an interface, and stop reaching through objects.",
tell="Every pattern is 'encapsulate what varies' applied somewhere. Program to interfaces so callers never depend on a concrete class. Law of Demeter: talk to your friends, not your friends' friends -- order.getCustomer().getAddress().getCity() means Order should expose what you need, or the chain will break when any link changes. Tell, don't ask: ask the object to do the thing instead of pulling its data out and deciding for it.",
code='''// asking (train wreck) vs telling
class City { final String name; City(String n) { name = n; } }
class Address { final City city; Address(City c) { city = c; } }
class Customer { final Address address; Customer(Address a) { address = a; } }
class Order {
    private final Customer customer; Order(Customer c) { customer = c; }
    String shipCity() { return customer.address.city.name; }        // Order knows its own shape; callers ask Order
    boolean shipsTo(String city) { return shipCity().equals(city); } // tell, don't ask
}''',
mistake="Getters for every field then logic outside the object; chains three dots deep in service code.",
say="\"The order answers shipsTo; nobody outside walks customer-address-city.\""),

dict(sec="E", id="idempotency", name="idempotency, fail-fast, and invariants in the model", one="Any operation a client may retry must be safe to repeat; validate at the boundary; keep invariants inside the object.",
tell="Payments, bookings, likes: the client retries on timeout, so the service must dedupe by an idempotency key (client-generated id) -- putIfAbsent on the key, return the original result. Fail fast: validate arguments at the entry point and throw; never let a bad state travel. Invariants live in the model's methods (Ticket.close throws if already closed), not in every caller.",
code='''class PaymentService {
    private final java.util.concurrent.ConcurrentHashMap<String, String> results = new java.util.concurrent.ConcurrentHashMap<>();
    String pay(String idempotencyKey, long paise) {
        if (paise <= 0) throw new IllegalArgumentException("amount");            // fail fast
        String prior = results.putIfAbsent(idempotencyKey, "PENDING");
        if (prior != null) return prior;                                       // retry: return the first outcome
        String result = "PAID:" + paise;                                       // charge once
        results.put(idempotencyKey, result);
        return result;
    }
}
final class Ticket {
    private boolean closed;
    synchronized void close() { if (closed) throw new IllegalStateException("already closed"); closed = true; }   // invariant lives here
}''',
mistake="Dedupe by amount-and-user (two legitimate identical payments collide); invariants checked in some callers and not others.",
say="\"The client sends an idempotency key; putIfAbsent makes the retry return the original result instead of charging twice.\""),

dict(sec="E", id="kiss", name="KISS, YAGNI, DRY -- and when to stop", one="Build the simplest thing that meets the stated requirement; say what you would add if asked.",
tell="In a round, over-engineering loses as many points as under-engineering. Two implementations of an interface justify the interface; one does not, unless the interviewer has hinted at the swap. Duplication of two lines is cheaper than a wrong abstraction. The senior move is to name the extension and not build it: 'if you need nearest-spot I would add a second assignment strategy here.'",
code='''// YAGNI: one pricing rule today -> a method, not a Strategy hierarchy
class Lot1 { double price(long minutes) { return Math.ceil(minutes / 60.0) * 20; } }
// the moment a second rule is asked for -> now the interface earns its place
interface Pricing { double price(long minutes); }
class Lot2 { private final Pricing p; Lot2(Pricing p) { this.p = p; } double price(long m) { return p.price(m); } }''',
mistake="Six interfaces before any behaviour; a generic event bus for one listener; abstract base classes 'for the future'.",
say="\"One rule today, so a method. If you want surge I will extract an interface right here -- it is a two-minute change.\""),

dict(sec="E", id="testing", name="how you would test it -- the sentence that ends the round well", one="Unit tests on the model invariants and the service with fake repos; a concurrency test that races the invariant.",
tell="Name three: (1) model tests -- Ticket.close twice throws; (2) service tests with an in-memory repo injected -- book a taken seat is rejected; (3) a race test -- N threads on one seat, exactly one wins, run on an executor with a latch so they start together. Mention property-style tests for a matching engine (no crossed book after any sequence). This is why you injected everything.",
code='''void raceTest(java.util.concurrent.ExecutorService pool) throws Exception {
    java.util.concurrent.ConcurrentHashMap<String, String> seat = new java.util.concurrent.ConcurrentHashMap<>();
    java.util.concurrent.CountDownLatch go = new java.util.concurrent.CountDownLatch(1);
    java.util.concurrent.atomic.AtomicInteger wins = new java.util.concurrent.atomic.AtomicInteger();
    java.util.List<java.util.concurrent.Future<?>> fs = new java.util.ArrayList<>();
    for (int i = 0; i < 50; i++) { String u = "u" + i; fs.add(pool.submit(() -> { go.await(); if (seat.putIfAbsent("A1", u) == null) wins.incrementAndGet(); return null; })); }
    go.countDown();                                     // all 50 start together
    for (var f : fs) f.get();
    if (wins.get() != 1) throw new AssertionError("expected 1 winner, got " + wins.get());
}''',
mistake="'I would write unit tests' with no example; a race test where threads start sequentially and never actually race.",
say="\"Fifty threads released by one latch on one seat; the assertion is exactly one winner. That test is why the lock is a claim and not a hope.\""),
]
