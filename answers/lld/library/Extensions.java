import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

// Reference code for every follow-up on page 05. Each block is one twist; nothing here edits Main.java.

// ---- ext: rules that change ----------------------------------------------------------------------------
/** Terms per tier: a table from tier to terms. One new class; the library never opens. */
final class TieredTerms implements LoanRules {
    private final Map<Tier, Terms> table = new EnumMap<>(Map.of(
        Tier.REGULAR, new Terms(3, 14, 2, 10_000),
        Tier.STUDENT, new Terms(2, 14, 1, 5_000),
        Tier.FACULTY, new Terms(10, 60, 3, 50_000)));
    /** The row for his tier. */
    public Terms termsFor(Member m) { return table.get(m.tier); }
}

/**
 * A grace period: a book back within `days` days of its due date costs nothing. Later than that, the wrapped rule
 * charges as usual, counted from the due date.
 */
final class GraceDays implements FinePolicy {
    private final FinePolicy base;
    private final int days;
    /** new GraceDays(new PerDayFine(2_000), 2): two free days. */
    GraceDays(FinePolicy base, int days) { this.base = base; this.days = days; }
    /** Zero inside the grace period, else whatever the wrapped rule says. */
    public long fine(Loan loan, LocalDate returnedOn) {
        long late = ChronoUnit.DAYS.between(loan.due, returnedOn);
        return late <= days ? 0 : base.fine(loan, returnedOn);
    }
}

/** Students pay half, rounded down to a whole rupee. It reads the member from the loan: no new interface needed. */
final class StudentRate implements FinePolicy {
    private final FinePolicy base;
    /** Wraps the rule whose fine is halved for students. */
    StudentRate(FinePolicy base) { this.base = base; }
    /** Half for a student, the full fine for everyone else. */
    public long fine(Loan loan, LocalDate returnedOn) {
        long f = base.fine(loan, returnedOn);
        return loan.member.tier == Tier.STUDENT ? f / 2 / 100 * 100 : f;
    }
}

/** Never more than the price of the book itself: past that point the library would rather have a new copy. */
final class CapAtPrice implements FinePolicy {
    private final FinePolicy base;
    /** Wraps the rule it caps. */
    CapAtPrice(FinePolicy base) { this.base = base; }
    /** The wrapped fine, or the book's price if that is smaller. */
    public long fine(Loan loan, LocalDate returnedOn) { return Math.min(base.fine(loan, returnedOn), loan.copy.book.pricePaise); }
}

// ---- ext: ladder rung 1: search off the lock -----------------------------------------------------------
/**
 * Rung 1: searches never take the library's lock. The catalogue changes a few times a day, so each change builds
 * a new index and swaps one volatile reference (copy-on-write: copy, change the copy, publish it in one write).
 * A search reads whichever index is current, with no lock at all. Word sets that did not change are shared.
 */
final class SnapshotCatalog {
    private volatile NavigableMap<String, Set<String>> words = Collections.emptyNavigableMap();
    private final ReentrantLock writers = new ReentrantLock();       // two additions at once must not lose each other

    /** Copy the map (not the sets), add this title's words, swap. O(words in the catalogue) per addition. */
    void add(String isbn, String title) {
        writers.lock();
        try {
            TreeMap<String, Set<String>> next = new TreeMap<>(words);
            for (String w : TokenIndex.split(title)) {
                Set<String> s = new TreeSet<>(next.getOrDefault(w, Set.of()));
                s.add(isbn);
                next.put(w, Collections.unmodifiableSet(s));
            }
            words = Collections.unmodifiableNavigableMap(next);      // one volatile write publishes it
        } finally { writers.unlock(); }
    }
    /** No lock: one volatile read, then a walk over one range of a map nobody will ever change. */
    List<String> find(String prefix, int limit) {
        NavigableMap<String, Set<String>> snap = words;
        LinkedHashSet<String> out = new LinkedHashSet<>();
        for (Set<String> s : snap.subMap(prefix, true, prefix + Character.MAX_VALUE, true).values())
            for (String isbn : s) { out.add(isbn); if (out.size() == limit) return new ArrayList<>(out); }
        return new ArrayList<>(out);
    }
}

// ---- ext: ladder rung 2: a lock per title --------------------------------------------------------------
/**
 * Rung 2: a lock per title, so members borrowing different titles never wait for each other. The loan limit
 * spans titles, so it leaves the title lock and becomes an atomic counter per member: claim a slot first
 * (compare-and-set), then take a copy under the title's lock, and give the slot back if none was free. A call
 * holds one lock at a time, so there is no lock order to get wrong. The price: while a failed claim is being
 * given back, a second checkout by the same member may hear LIMIT_REACHED. Never the reverse.
 */
final class TitleLocks {
    private final Map<String, ReentrantLock> locks = new ConcurrentHashMap<>();
    private final Map<String, Deque<String>> shelves = new ConcurrentHashMap<>();    // isbn -> barcodes on the shelf
    private final Map<String, AtomicInteger> out = new ConcurrentHashMap<>();         // member -> books he has out
    private final int maxLoans;
    /** Every member may have maxLoans books out. */
    TitleLocks(int maxLoans) { this.maxLoans = maxLoans; }

    /** Setup: a copy on its title's shelf. */
    void addCopy(String isbn, String barcode) {
        withTitle(isbn, () -> shelves.computeIfAbsent(isbn, k -> new ArrayDeque<>()).offer(barcode));
    }
    /** Claim a slot, then a copy; no copy means the slot goes back. Returns the barcode lent. */
    String checkout(String memberId, String isbn) {
        AtomicInteger n = out.computeIfAbsent(memberId, k -> new AtomicInteger());
        int had;
        do {
            had = n.get();
            if (had >= maxLoans) throw new Refused(Refusal.LIMIT_REACHED, memberId);
        } while (!n.compareAndSet(had, had + 1));                     // the slot is his
        String copy = withTitle(isbn, () -> { Deque<String> s = shelves.get(isbn); return s == null ? null : s.poll(); });
        if (copy == null) {
            n.decrementAndGet();                                     // no copy: give the slot back
            throw new Refused(Refusal.NOT_AVAILABLE, isbn);
        }
        return copy;
    }
    /** The copy goes back under its title's lock; then his slot is freed. */
    void giveBack(String memberId, String isbn, String barcode) {
        withTitle(isbn, () -> shelves.get(isbn).offer(barcode));
        out.get(memberId).decrementAndGet();
    }
    /** How many books he has out right now. */
    int loansOf(String memberId) { AtomicInteger n = out.get(memberId); return n == null ? 0 : n.get(); }
    /** Run the body under this title's lock, and only that lock. */
    private <T> T withTitle(String isbn, Supplier<T> body) {
        ReentrantLock l = locks.computeIfAbsent(isbn, k -> new ReentrantLock());
        l.lock();
        try { return body.get(); } finally { l.unlock(); }
    }
}

// ---- ext: several branches -----------------------------------------------------------------------------
/**
 * Twenty branches, one catalogue, one queue per title across all of them. A hold names the branch where the
 * member will collect. A copy that comes back at another branch cannot go on that branch's hold shelf: it goes
 * IN_TRANSIT to his branch, and only when the van delivers it is it READY. One new state, one more hop; the rule
 * "the queue before the shelf" does not change.
 */
final class BranchNetwork {
    /** Where a returned copy ends up. */
    enum Where { ON_SHELF, IN_TRANSIT, READY }
    /** A copy's next place: at which branch, in what state, and for whom (null = nobody). */
    record Placement(String barcode, String atBranch, Where where, String forMember) {}
    /** One member in a title's queue, and the branch where he will collect. */
    private record Waiter(String memberId, String pickupBranch) {}
    private final Map<String, Deque<Waiter>> queues = new HashMap<>();     // isbn -> FIFO across all branches
    private final ReentrantLock lock = new ReentrantLock();                // the queues are shared, so they have one owner

    /** Join the title's queue, naming the branch where he will collect. */
    void hold(String isbn, String memberId, String pickupBranch) {
        lock.lock();
        try { queues.computeIfAbsent(isbn, k -> new ArrayDeque<>()).offer(new Waiter(memberId, pickupBranch)); }
        finally { lock.unlock(); }
    }
    /** A copy comes back at a branch: the first member waiting gets it, here or in transit to his branch; nobody waiting, this branch's shelf. */
    Placement returned(String isbn, String barcode, String branch) {
        lock.lock();
        try {
            Deque<Waiter> q = queues.get(isbn);
            Waiter w = q == null ? null : q.poll();
            if (w == null) return new Placement(barcode, branch, Where.ON_SHELF, null);
            if (w.pickupBranch().equals(branch)) return new Placement(barcode, branch, Where.READY, w.memberId());
            return new Placement(barcode, w.pickupBranch(), Where.IN_TRANSIT, w.memberId());
        } finally { lock.unlock(); }
    }
    /** The van delivers: a copy in transit is now READY at its destination, and his pickup days start now. */
    Placement arrived(Placement p) {
        return p.where() == Where.IN_TRANSIT ? new Placement(p.barcode(), p.atBranch(), Where.READY, p.forMember()) : p;
    }
}

// ---- ext: flipkart ids ---------------------------------------------------------------------------------
/**
 * Flipkart's rule: a book's id is the first three letters of the author's last name plus a number: ROW1001,
 * ROW1002. One counter per prefix, created and advanced atomically, so two librarians adding Rowling books at
 * the same instant never get the same id.
 */
final class BookIdGenerator {
    private final ConcurrentHashMap<String, AtomicInteger> counters = new ConcurrentHashMap<>();
    private final int first;
    /** Numbers start after `first`: new BookIdGenerator(1000) gives ROW1001 first. */
    BookIdGenerator(int first) { this.first = first; }
    /** "J. K. Rowling" -> ROW1001. A last name shorter than three letters is padded with X ("Li" -> LIX1001). */
    String next(String author) {
        String[] parts = author.trim().split("\\s+");
        String last = parts[parts.length - 1].replaceAll("[^A-Za-z]", "").toUpperCase(Locale.ROOT);
        String prefix = (last + "XXX").substring(0, 3);
        return prefix + counters.computeIfAbsent(prefix, k -> new AtomicInteger(first)).incrementAndGet();
    }
}

// ---- ext: racks ----------------------------------------------------------------------------------------
/**
 * The workat.tech version: racks numbered 1..n, and a rack holds at most one copy of any book. A new or returned
 * copy goes to the lowest-numbered rack with no copy of its book; "borrow by book id" takes the copy on the
 * lowest rack. Per book: a BitSet of racks in use (nextClearBit finds the first free one) and a TreeMap from rack
 * to copy (firstEntry is the lowest). The shelf's ORDER is a rule, like the parking lot's queue of free spots.
 */
final class RackedShelf {
    private final int racks;
    private final Map<String, BitSet> used = new HashMap<>();                       // book id -> racks holding a copy of it
    private final Map<String, TreeMap<Integer, String>> onRack = new HashMap<>();   // book id -> rack -> copy id
    private final Map<String, String> bookOf = new HashMap<>();                     // copy id -> book id
    private final Map<String, Integer> rackOf = new HashMap<>();                    // copy id -> its rack, while on one
    private final Map<String, Integer> owned = new HashMap<>();                     // book id -> copies owned, borrowed ones too
    /** A library with racks 1..racks. */
    RackedShelf(int racks) { this.racks = racks; }

    /**
     * Add copies, all or nothing. A book can own at most one copy per rack, counting the copies that are out, because
     * each of those must find a rack when it comes back. Returns their racks, or null ("Rack not available").
     */
    synchronized List<Integer> add(String bookId, List<String> copyIds) {
        int have = owned.getOrDefault(bookId, 0);
        if (have + copyIds.size() > racks) return null;
        owned.put(bookId, have + copyIds.size());
        List<Integer> placed = new ArrayList<>();
        for (String c : copyIds) { bookOf.put(c, bookId); placed.add(place(bookId, c)); }
        return placed;
    }
    /** Borrow by book id: the copy on the lowest rack, as "copyId@rack", or null ("Not available"). O(log racks). */
    synchronized String borrowByBook(String bookId) {
        TreeMap<Integer, String> m = onRack.get(bookId);
        if (m == null || m.isEmpty()) return null;
        Map.Entry<Integer, String> e = m.pollFirstEntry();
        used.get(bookId).clear(e.getKey());
        rackOf.remove(e.getValue());
        return e.getValue() + "@" + e.getKey();
    }
    /** Borrow one named copy: take it off its rack. Returns the rack, or -1 when it is not on a rack. */
    synchronized int borrowCopy(String copyId) {
        Integer r = rackOf.remove(copyId);
        if (r == null) return -1;
        String book = bookOf.get(copyId);
        onRack.get(book).remove(r);
        used.get(book).clear(r);
        return r;
    }
    /** A returned copy goes to the first free rack for its book. Returns that rack; a copy already on a rack stays put. */
    synchronized int giveBack(String copyId) {
        Integer r = rackOf.get(copyId);
        return r != null ? r : place(bookOf.get(copyId), copyId);
    }

    /** The lowest rack with no copy of this book, found by nextClearBit from rack 1; -1 when every rack has one. */
    private int place(String bookId, String copyId) {
        BitSet u = used.computeIfAbsent(bookId, k -> new BitSet());
        int r = u.nextClearBit(1);
        if (r > racks) return -1;
        u.set(r);
        onRack.computeIfAbsent(bookId, k -> new TreeMap<>()).put(r, copyId);
        rackOf.put(copyId, r);
        return r;
    }
}

// ---- ext: reminders and a slow sms gateway ------------------------------------------------------------
/** The nightly job: a DUE_SOON notice for every loan due in the next `days` days. It reads one range of the due index. */
final class DueSoonReminder {
    private final Library lib;
    private final LibraryListener out;
    private final int days;
    /** Remind members whose books are due within `days` days, through this listener. */
    DueSoonReminder(Library lib, LibraryListener out, int days) { this.lib = lib; this.out = out; this.days = days; }
    /** Send the notices; returns how many went out. */
    int run() {
        LocalDate today = lib.today();
        List<Slip> soon = lib.dueBetween(today, today.plusDays(days));
        for (Slip s : soon) out.onEvent(new LibraryEvent(EventKind.DUE_SOON, s.memberId(), s.isbn(), s.barcode(), s.due(), 0));
        return soon.size();
    }
}

/**
 * A listener that never makes a desk wait. onEvent only appends to a queue, which takes microseconds; a worker
 * sends the SMS at the gateway's pace, and a message the gateway refuses goes back in the queue, not in the bin.
 */
final class SmsOutbox implements LibraryListener {
    private final BlockingQueue<LibraryEvent> queue = new LinkedBlockingQueue<>();
    final List<LibraryEvent> sent = new CopyOnWriteArrayList<>();
    /** Called by the library after the unlock: enqueue and return. */
    public void onEvent(LibraryEvent e) { queue.offer(e); }
    /** The worker's loop body: try each queued message once; one the gateway refuses or throws on is queued again. */
    int drain(Predicate<LibraryEvent> gateway) {
        List<LibraryEvent> batch = new ArrayList<>();
        queue.drainTo(batch);
        int ok = 0;
        for (LibraryEvent e : batch) {
            boolean delivered;
            try { delivered = gateway.test(e); } catch (RuntimeException down) { delivered = false; }
            if (delivered) { sent.add(e); ok++; } else queue.offer(e);
        }
        return ok;
    }
    /** Messages still waiting to be sent. */
    int pending() { return queue.size(); }
}

// ---- ext: persistence ----------------------------------------------------------------------------------
/** The library's state behind an interface, so the services above do not change when it moves to a database. */
interface LibraryRepository {
    /** Claim a copy for a member only if it is still on the shelf: true means he got it, false means someone else did. */
    boolean claim(String barcode, String memberId, LocalDate due);
    /** The copy is back on the shelf. */
    void release(String barcode);
    /** Barcodes of loans due before today, oldest first. */
    List<String> overdue(LocalDate today);
}

/**
 * The in-memory version a test uses. The claim is a compare-and-set on the copy's row, exactly what the UPDATE
 * below does in a database. The overdue list is a scan here, which is fine for a test double; the database uses
 * the partial index on due_on.
 */
final class InMemoryLibraryRepository implements LibraryRepository {
    private final ConcurrentHashMap<String, String> holder = new ConcurrentHashMap<>();   // barcode -> "" on the shelf, else member id
    private final ConcurrentHashMap<String, LocalDate> due = new ConcurrentHashMap<>();
    /** Setup: a copy on the shelf. */
    void addCopy(String barcode) { holder.put(barcode, ""); }
    /** One atomic step decides the winner: replace "" with his id only if it is still "". */
    public boolean claim(String barcode, String memberId, LocalDate dueOn) {
        if (!holder.replace(barcode, "", memberId)) return false;
        due.put(barcode, dueOn);
        return true;
    }
    /** Back on the shelf, no longer due. */
    public void release(String barcode) { due.remove(barcode); holder.put(barcode, ""); }
    /** Loans due before today, oldest first. */
    public List<String> overdue(LocalDate today) {
        return due.entrySet().stream().filter(e -> e.getValue().isBefore(today))
                  .sorted(Map.Entry.comparingByValue()).map(Map.Entry::getKey).toList();
    }
}

/** The same design as PostgreSQL tables. Walmart asked for the schema; Bloomberg for the overdue query. */
final class LibrarySql {
    /** Five tables, three indexes. The unique index is Flipkart's "one copy of a title per member", enforced by the database. */
    static final String SCHEMA = """
        CREATE TABLE book   (isbn VARCHAR(13) PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL,
                             price_paise BIGINT NOT NULL);
        CREATE TABLE copy   (barcode VARCHAR(20) PRIMARY KEY, isbn VARCHAR(13) NOT NULL REFERENCES book,
                             status VARCHAR(10) NOT NULL);                 -- AVAILABLE, LOANED, ON_HOLD, LOST
        CREATE TABLE member (id VARCHAR(20) PRIMARY KEY, name TEXT NOT NULL, tier VARCHAR(10) NOT NULL,
                             dues_paise BIGINT NOT NULL DEFAULT 0);
        CREATE TABLE loan   (id BIGINT PRIMARY KEY, barcode VARCHAR(20) NOT NULL REFERENCES copy,
                             member_id VARCHAR(20) NOT NULL REFERENCES member, isbn VARCHAR(13) NOT NULL,
                             borrowed_on DATE NOT NULL, due_on DATE NOT NULL, closed_on DATE,  -- returned or lost
                             renewals INT NOT NULL DEFAULT 0, charged_paise BIGINT NOT NULL DEFAULT 0);
        CREATE TABLE hold   (id BIGINT PRIMARY KEY, isbn VARCHAR(13) NOT NULL REFERENCES book,
                             member_id VARCHAR(20) NOT NULL REFERENCES member, placed_at TIMESTAMP NOT NULL,
                             status VARCHAR(10) NOT NULL, barcode VARCHAR(20), pickup_by DATE);
        CREATE INDEX loan_open_by_due ON loan (due_on) WHERE closed_on IS NULL;             -- the overdue report
        CREATE UNIQUE INDEX one_copy_each ON loan (member_id, isbn) WHERE closed_on IS NULL;
        CREATE INDEX hold_queue ON hold (isbn, placed_at) WHERE status = 'WAITING';         -- the FIFO queue
        """;
    /** Bloomberg's question: who has an overdue book, which one, and how late. */
    static final String OVERDUE = """
        SELECT m.id, m.name, b.title, l.barcode, l.due_on, CURRENT_DATE - l.due_on AS days_late
        FROM loan l JOIN member m ON m.id = l.member_id JOIN book b ON b.isbn = l.isbn
        WHERE l.closed_on IS NULL AND l.due_on < CURRENT_DATE
        ORDER BY l.due_on""";
    /** The checkout's claim: one row updated means the copy is his, zero means someone else got it first. */
    static final String CLAIM = "UPDATE copy SET status = 'LOANED' WHERE barcode = ? AND status = 'AVAILABLE'";
    /** Returns and holds for one title take this row lock first, so they are decided one at a time: move 4, in SQL. */
    static final String LOCK_TITLE = "SELECT isbn FROM book WHERE isbn = ? FOR UPDATE";
}

// ---- ext: the copy's life as a table ------------------------------------------------------------------
/** The copy's life as an explicit table: every move not listed throws, so a bug cannot lend a lost copy. */
final class CopyLife {
    static final Map<CopyStatus, Set<CopyStatus>> ALLOWED = new EnumMap<>(Map.of(
        CopyStatus.AVAILABLE, EnumSet.of(CopyStatus.LOANED, CopyStatus.ON_HOLD),
        CopyStatus.LOANED,    EnumSet.of(CopyStatus.AVAILABLE, CopyStatus.ON_HOLD, CopyStatus.LOST),
        CopyStatus.ON_HOLD,   EnumSet.of(CopyStatus.LOANED, CopyStatus.ON_HOLD, CopyStatus.AVAILABLE),
        CopyStatus.LOST,      EnumSet.noneOf(CopyStatus.class)));
    /** Move a copy, or throw if the table does not allow the move. */
    static void move(BookCopy c, CopyStatus to) {
        if (!ALLOWED.get(c.status).contains(to))
            throw new IllegalStateException(c.barcode + ": " + c.status + " -> " + to + " is not allowed");
        c.status = to;
    }
}

// ---- ext: e-books --------------------------------------------------------------------------------------
/**
 * An e-book: no barcode and no shelf, just N licences that may be out at once. A loan ends by itself on its due
 * date, so there is never a late fine, and the licence it frees goes straight to the first member waiting.
 * Different behaviour, so its own class, not a BookCopy subclass that would inherit a shelf it never uses.
 */
final class EbookLending {
    private final int loanDays;
    private int free;
    private final Deque<String> waiting = new ArrayDeque<>();
    private final TreeMap<LocalDate, List<String>> endsOn = new TreeMap<>();   // the day loans end -> who is reading
    private final Set<String> reading = new HashSet<>();
    private final ReentrantLock lock = new ReentrantLock();
    /** A title with this many licences, lent for loanDays days. */
    EbookLending(int licences, int loanDays) { this.free = licences; this.loanDays = loanDays; }

    /** Read now if a licence is free (true), else join the queue (false). Asking twice changes nothing. */
    boolean borrow(String member, LocalDate today) {
        lock.lock();
        try {
            if (reading.contains(member)) return true;
            if (waiting.contains(member)) return false;              // a scan of the queue: a sketch, fine at a few dozen
            if (free == 0) { waiting.offer(member); return false; }
            lend(member, today);
            return true;
        } finally { lock.unlock(); }
    }
    /** The nightly tick: loans that ended free their licences, and each freed licence goes to the next reader in line. */
    List<String> tick(LocalDate today) {
        lock.lock();
        try {
            SortedMap<LocalDate, List<String>> ended = endsOn.headMap(today, true);
            for (List<String> readers : ended.values()) { reading.removeAll(readers); free += readers.size(); }
            ended.clear();
            List<String> got = new ArrayList<>();
            while (free > 0 && !waiting.isEmpty()) { String m = waiting.poll(); lend(m, today); got.add(m); }
            return got;
        } finally { lock.unlock(); }
    }
    /** Licences not in use. */
    int free() { lock.lock(); try { return free; } finally { lock.unlock(); } }
    /** One licence to this member, ending loanDays from today. */
    private void lend(String member, LocalDate today) {
        free--;
        reading.add(member);
        endsOn.computeIfAbsent(today.plusDays(loanDays), d -> new ArrayList<>()).add(member);
    }
}

// ---- ext: items from a file ----------------------------------------------------------------------------
/** Factory, earned only when items arrive as text: one row per item, its kind in the first column, one maker per kind. */
final class CatalogImport {
    private final Map<String, BiConsumer<Library, String[]>> makers = Map.of(
        "BOOK", (lib, f) -> lib.addBook(f[1], f[2], f[3], Long.parseLong(f[4])),
        "COPY", (lib, f) -> lib.addCopy(f[1], f[2]));
    /** Apply one line such as BOOK|9780132350884|Clean Code|Robert C. Martin|60000. An unknown kind is refused. */
    void apply(Library lib, String line) {
        String[] f = line.split("\\|");
        BiConsumer<Library, String[]> make = makers.get(f[0]);
        if (make == null) throw new IllegalArgumentException("unknown kind: " + f[0]);
        make.accept(lib, f);
    }
}

/** Runs every extension once, so the page's follow-up code is code that has actually executed. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        long[] now = { Main.at(9, 1, 10, 0) };
        Library lib = new Library(Main.IST, 3);
        lib.setClock(() -> now[0]);
        String cc = "9780132350884";
        lib.addBook(cc, "Clean Code", "Robert C. Martin", 60_000);
        lib.addCopy(cc, "CC-1");
        lib.register("riya", "Riya", Tier.STUDENT);
        lib.register("prof", "Prof. Rao", Tier.FACULTY);

        System.out.println("-- rules that change: tiers, then a grace period, a student rate and a cap, wrapped");
        lib.configure(new TieredTerms(), new CapAtPrice(new StudentRate(new GraceDays(new PerDayFine(2_000), 2))));
        Slip s = lib.checkout("riya", cc);
        System.out.println("   riya (student) borrows " + s.barcode() + ", due " + s.due());
        now[0] = Main.at(9, 15 + 7, 10, 0);                                     // seven days late
        System.out.println("   back 7 days late: fine " + Main.rs(lib.returnCopy("CC-1").finePaise()) + " (7 x Rs 20, halved)");

        System.out.println("-- rung 1: search without the lock (copy-on-write)");
        SnapshotCatalog snap = new SnapshotCatalog();
        snap.add(cc, "Clean Code");
        snap.add("9780134494166", "Clean Architecture");
        System.out.println("   'clea' -> " + snap.find("clea", 10));

        System.out.println("-- rung 2: a lock per title, the limit as an atomic counter");
        TitleLocks titles = new TitleLocks(2);
        titles.addCopy("A", "A-1"); titles.addCopy("B", "B-1"); titles.addCopy("C", "C-1");
        System.out.println("   lent " + titles.checkout("m1", "A") + " and " + titles.checkout("m1", "B"));
        try { titles.checkout("m1", "C"); } catch (Refused r) { System.out.println("   a third title: " + r.why); }

        System.out.println("-- several branches: a copy returned at the wrong branch travels");
        BranchNetwork net = new BranchNetwork();
        net.hold(cc, "meera", "Indiranagar");
        BranchNetwork.Placement p = net.returned(cc, "CC-1", "Koramangala");
        System.out.println("   " + p + "  ->  " + net.arrived(p));

        System.out.println("-- Flipkart's ids");
        BookIdGenerator ids = new BookIdGenerator(1000);
        System.out.println("   " + ids.next("J. K. Rowling") + ", " + ids.next("J. K. Rowling") + ", " + ids.next("Yu Li"));

        System.out.println("-- workat.tech racks: first free rack, lowest rack first");
        RackedShelf racks = new RackedShelf(3);
        System.out.println("   add 3 copies -> racks " + racks.add("B1", List.of("c1", "c2", "c3")) + "; a 4th -> " + racks.add("B1", List.of("c4")));
        System.out.println("   borrow by book -> " + racks.borrowByBook("B1") + "; return c1 -> rack " + racks.giveBack("c1"));

        System.out.println("-- reminders, and an outbox in front of a slow SMS gateway");
        lib.configure(new StandardTerms(), new CappedFine(new PerDayFine(2_000), 50_000));
        lib.checkout("prof", cc);                                              // due in 14 days
        now[0] = Main.at(10, 4, 10, 0);                                        // due on the 6th: two days away
        SmsOutbox outbox = new SmsOutbox();
        System.out.println("   due-soon notices: " + new DueSoonReminder(lib, outbox, 2).run() + ", queued " + outbox.pending());
        System.out.println("   gateway down: sent " + outbox.drain(e -> { throw new RuntimeException("503"); }) + ", still queued " + outbox.pending());
        System.out.println("   gateway up:   sent " + outbox.drain(e -> true) + ", still queued " + outbox.pending());

        System.out.println("-- persistence: the claim is a compare-and-set on the row");
        InMemoryLibraryRepository repo = new InMemoryLibraryRepository();
        repo.addCopy("CC-9");
        LocalDate d = LocalDate.of(2026, 9, 15);
        System.out.println("   ravi claims " + repo.claim("CC-9", "ravi", d) + ", meera claims " + repo.claim("CC-9", "meera", d)
                           + "; overdue on 20 Sep: " + repo.overdue(LocalDate.of(2026, 9, 20)));
        System.out.println("   " + LibrarySql.CLAIM);

        System.out.println("-- the copy's life as a table");
        BookCopy lost = new BookCopy("X-1", new Book("x", "x", "x", 0));
        CopyLife.move(lost, CopyStatus.LOANED);
        CopyLife.move(lost, CopyStatus.LOST);
        try { CopyLife.move(lost, CopyStatus.LOANED); } catch (IllegalStateException e) { System.out.println("   " + e.getMessage()); }

        System.out.println("-- e-books: licences, loans that end by themselves");
        EbookLending ebook = new EbookLending(1, 14);
        LocalDate day1 = LocalDate.of(2026, 9, 1);
        System.out.println("   asha reads now: " + ebook.borrow("asha", day1) + "; ravi reads now: " + ebook.borrow("ravi", day1));
        System.out.println("   15 Sep tick: licence passed to " + ebook.tick(day1.plusDays(14)) + ", free " + ebook.free());

        System.out.println("-- items from a file (Factory)");
        CatalogImport importer = new CatalogImport();
        importer.apply(lib, "BOOK|9780134685991|Effective Java|Joshua Bloch|55000");
        importer.apply(lib, "COPY|9780134685991|EJ-1");
        System.out.println("   imported: " + lib.searchAuthor("bloch", 5));
    }
}
