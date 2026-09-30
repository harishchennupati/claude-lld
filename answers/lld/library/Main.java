import java.time.*;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;
import java.util.function.*;

/** Where one physical copy is right now. ON_HOLD means set aside on the hold shelf for one member, until a pickup date. */
enum CopyStatus { AVAILABLE, LOANED, ON_HOLD, LOST }

/**
 * A hold's life: WAITING in its title's queue; READY once a copy is set aside for the member; then COLLECTED
 * (he borrowed it), EXPIRED (he did not come in time) or CANCELLED.
 */
enum HoldStatus { WAITING, READY, COLLECTED, EXPIRED, CANCELLED }

/** A loan's life: ACTIVE until the copy comes back (RETURNED) or is reported LOST. */
enum LoanStatus { ACTIVE, RETURNED, LOST }

/** A member's tier. Data for the rules, not a subclass: StandardTerms ignores it, a tiered rule reads it. */
enum Tier { REGULAR, STUDENT, FACULTY }

/** What a notice is about. The library sends the first three itself; a nightly job sends DUE_SOON. */
enum EventKind { HOLD_READY, HOLD_EXPIRED, FINE_CHARGED, DUE_SOON }

/**
 * Why the library said no. A refusal is a normal answer at a desk, so it carries a reason that a desk can show
 * and a test can check.
 */
enum Refusal {
    UNKNOWN_MEMBER, UNKNOWN_BOOK, UNKNOWN_COPY, DUPLICATE_ID,
    NOT_AVAILABLE, LIMIT_REACHED, OWES_FINES, ALREADY_HAS_TITLE,
    NOT_ON_LOAN, NO_HOLD, OTHERS_WAITING, RENEWAL_LIMIT, OVERDUE, HAS_LOANS
}

/** Thrown when the library refuses. Every refusal happens before the first write, so nothing has changed. */
final class Refused extends RuntimeException {
    final Refusal why;
    /** A refusal with its reason and the detail a desk would print. */
    Refused(Refusal why, String detail) { super(why + ": " + detail); this.why = why; }
}

/**
 * A title in the catalogue: one ISBN, one title, one author, and the price of a replacement copy. It owns its
 * copies, the queue of copies on the shelf, and the FIFO queue of members waiting for it. Only the library
 * changes it, and only under the library's lock.
 */
final class Book {
    final String isbn, title, author;
    final long pricePaise;                                     // charged when a copy is lost
    final List<BookCopy> copies = new ArrayList<>();           // every copy, for "who has this book?"
    private final Deque<BookCopy> shelf = new ArrayDeque<>();  // the AVAILABLE copies; the head is lent next
    private final Deque<Hold> waiting = new ArrayDeque<>();    // FIFO; a cancelled hold is dropped when it reaches the front

    /** A title with no copies yet. */
    Book(String isbn, String title, String author, long pricePaise) {
        this.isbn = isbn; this.title = title; this.author = author; this.pricePaise = pricePaise;
    }
    /** The copy that would be lent next, without taking it; null when the shelf is empty. O(1). */
    BookCopy peekShelf()     { return shelf.peek(); }
    /** Take the head of the shelf. O(1). */
    BookCopy takeFromShelf() { return shelf.poll(); }
    /** Put a free copy on the shelf. Only placeCopy calls it, and only when nobody is waiting. O(1). */
    void shelve(BookCopy c)  { shelf.offer(c); }
    /** How many copies are on the shelf right now. O(1). */
    int onShelf()            { return shelf.size(); }
    /** Join the back of the queue. O(1). */
    void enqueue(Hold h)     { waiting.offer(h); }
    /**
     * The first hold that is still WAITING, or null. A cancelled hold stays in the queue until it reaches the
     * front and is dropped here, once. So a cancel costs O(1), and this costs O(1) on average.
     */
    Hold firstWaiting() {
        while (!waiting.isEmpty() && waiting.peek().status != HoldStatus.WAITING) waiting.poll();
        return waiting.peek();
    }
    /** Take the first live hold off the queue, or return null when nobody is waiting. */
    Hold nextInLine() {
        Hold h = firstWaiting();
        if (h != null) waiting.poll();
        return h;
    }
    /** This member's place in the queue (1 = next), or 0 if he is not waiting. O(queue length). */
    int position(Member m) {
        int n = 0;
        for (Hold h : waiting)
            if (h.status == HoldStatus.WAITING) { n++; if (h.member == m) return n; }
        return 0;
    }
}

/** One physical copy with its own barcode. Dumb on purpose: it knows its title and where it is. */
final class BookCopy {
    final String barcode;
    final Book book;
    CopyStatus status = CopyStatus.AVAILABLE;                  // written only by the library, under its lock
    /** A copy of one title. */
    BookCopy(String barcode, Book book) { this.barcode = barcode; this.book = book; }
}

/**
 * A registered reader. His loans are kept by ISBN, so "has he reached his limit?" and "does he already have
 * this title?" are one lookup each. His live holds are kept by ISBN too. Dues are what he owes, in paise.
 */
final class Member {
    final String id, name;
    final Tier tier;
    final Map<String, Loan> loans = new HashMap<>();           // isbn -> active loan: one copy of a title at a time
    final Map<String, Hold> holds = new HashMap<>();           // isbn -> a hold that is WAITING or READY
    long duesPaise;                                            // unpaid fines and lost-book charges
    /** A member who owes nothing and has nothing out. */
    Member(String id, String name, Tier tier) { this.id = id; this.name = name; this.tier = tier; }
}

/** One copy lent to one member. The due date is a key in the library's due index, so only the library changes it. */
final class Loan {
    final int id;
    final BookCopy copy;
    final Member member;
    final LocalDate borrowedOn;
    LocalDate due;
    int renewals;
    LoanStatus status = LoanStatus.ACTIVE;
    LocalDate closedOn;                                        // the day it came back, or was reported lost
    long chargedPaise;                                         // the late fine, or the lost-book charge
    /** A loan that starts today and is due on the given day. */
    Loan(int id, BookCopy copy, Member member, LocalDate borrowedOn, LocalDate due) {
        this.id = id; this.copy = copy; this.member = member; this.borrowedOn = borrowedOn; this.due = due;
    }
}

/** A member's place in a title's queue. READY means a copy is on the hold shelf for him until pickupBy, inclusive. */
final class Hold {
    final int id;
    final Member member;
    final Book book;
    HoldStatus status = HoldStatus.WAITING;
    BookCopy copy;                                             // the copy set aside for him, while READY
    LocalDate pickupBy;                                        // set when it becomes READY
    /** A new hold, waiting. */
    Hold(int id, Member member, Book book) { this.id = id; this.member = member; this.book = book; }
}

/** What a member takes home: a copy, its title and the due date. An immutable copy, safe to read after the lock. */
record Slip(String barcode, String isbn, String title, String memberId, LocalDate due, int renewals) {}

/** A hold as the member sees it: READY with a copy and a pickup date, or WAITING at a position (1 = next). */
record HoldSlip(String memberId, String isbn, HoldStatus status, int position, String barcode, LocalDate pickupBy) {}

/** The result of a return: the fine charged, and who the copy is now set aside for (null = back on the shelf). */
record Receipt(String barcode, long finePaise, String heldFor) {}

/** One search hit: the title, and how many of its copies are on the shelf right now. */
record Found(String isbn, String title, String author, int onShelf, int copies) {}

/** One notice for the listeners, built under the lock and delivered after it. */
record LibraryEvent(EventKind kind, String memberId, String isbn, String barcode, LocalDate date, long paise) {}

/** What a member may do: books at once, days per loan, renewals, and the most he may owe and still borrow. */
record Terms(int maxLoans, int loanDays, int maxRenewals, long maxDuesPaise) {}

/** The borrowing rules. They change (tiers, a holiday season), so they are handed in, and handed the whole member. */
interface LoanRules { Terms termsFor(Member m); }

/** Everyone the same: 3 books at once, 14 days each, 2 renewals, no borrowing while owing more than Rs 100. */
final class StandardTerms implements LoanRules {
    private static final Terms ALL = new Terms(3, 14, 2, 10_000);
    /** The same terms for every member. */
    public Terms termsFor(Member m) { return ALL; }
}

/**
 * The late fine, in paise, for a loan that comes back on a given day. Handed the whole loan, so a rule can read
 * the book (a cap at its price) or the member (a student rate) without a new interface.
 */
interface FinePolicy { long fine(Loan loan, LocalDate returnedOn); }

/** A flat rate for every day after the due date. Back on the due date itself: no fine. */
final class PerDayFine implements FinePolicy {
    private final long perDayPaise;
    /** Rs 20 a day is new PerDayFine(2_000). */
    PerDayFine(long perDayPaise) { this.perDayPaise = perDayPaise; }
    /** Days late times the rate; zero when on time or early. */
    public long fine(Loan loan, LocalDate returnedOn) {
        long late = ChronoUnit.DAYS.between(loan.due, returnedOn);
        return late <= 0 ? 0 : late * perDayPaise;
    }
}

/** Wraps any fine rule and never charges more than a cap. A new class; the library did not change (Decorator). */
final class CappedFine implements FinePolicy {
    private final FinePolicy base;
    private final long capPaise;
    /** new CappedFine(new PerDayFine(2_000), 50_000): Rs 20 a day, never more than Rs 500. */
    CappedFine(FinePolicy base, long capPaise) { this.base = base; this.capPaise = capPaise; }
    /** The wrapped rule's fine, or the cap if that is smaller. */
    public long fine(Loan loan, LocalDate returnedOn) { return Math.min(base.fine(loan, returnedOn), capPaise); }
}

/** Anyone who wants to hear what happened: an SMS sender, an e-mail job, the hold-shelf printer. Called after the lock. */
interface LibraryListener { void onEvent(LibraryEvent e); }

/** Prints each notice. A real one sends an SMS. */
final class NoticePrinter implements LibraryListener {
    /** One line per notice. */
    public void onEvent(LibraryEvent e) {
        String what = switch (e.kind()) {
            case HOLD_READY   -> e.barcode() + " is on the hold shelf for you; collect it by " + e.date();
            case HOLD_EXPIRED -> e.barcode() + " waited for you until " + e.date() + " and has been passed on";
            case FINE_CHARGED -> "a charge of " + Main.rs(e.paise()) + " was added for " + e.barcode();
            case DUE_SOON     -> e.barcode() + " is due on " + e.date();
        };
        System.out.println("   [sms to " + e.memberId() + "] " + what);
    }
}

/** Where time comes from. Handed in, so a test can say "the 15th of September" and mean it. */
interface Clock { long nowMs(); }

/**
 * Words to ISBNs, kept sorted, so "every word that starts with clea" is one range of the map. Finding the range
 * costs O(log n); each match after that costs one step, and the caller's limit stops the walk.
 */
final class TokenIndex {
    private final TreeMap<String, Set<String>> index = new TreeMap<>();   // "clean" -> {isbn, isbn}

    /** File every word of the text under this ISBN. */
    void add(String text, String isbn) {
        for (String w : split(text)) index.computeIfAbsent(w, k -> new TreeSet<>()).add(isbn);
    }
    /** ISBNs that have a word starting with the prefix and pass the filter, at most limit of them. */
    List<String> find(String prefix, Predicate<String> keep, int limit) {
        List<String> out = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (Set<String> isbns : index.subMap(prefix, true, prefix + Character.MAX_VALUE, true).values())
            for (String isbn : isbns)
                if (seen.add(isbn) && keep.test(isbn)) {
                    out.add(isbn);
                    if (out.size() == limit) return out;
                }
        return out;
    }
    /** Lower-case words; anything that is not a letter or a digit separates them. */
    static List<String> split(String text) {
        List<String> out = new ArrayList<>();
        for (String w : text.toLowerCase(Locale.ROOT).split("[^\\p{L}\\p{N}]+")) if (!w.isEmpty()) out.add(w);
        return out;
    }
}

/** The titles by ISBN, plus two word indexes (title words, author words) for search. Only the library changes it. */
final class Catalog {
    private final Map<String, Book> byIsbn = new HashMap<>();
    private final TokenIndex titleWords = new TokenIndex(), authorWords = new TokenIndex();

    /** Add a title and index its words. */
    void add(Book b) { byIsbn.put(b.isbn, b); titleWords.add(b.title, b.isbn); authorWords.add(b.author, b.isbn); }
    /** One title by ISBN, or null. O(1). */
    Book get(String isbn) { return byIsbn.get(isbn); }
    /** Titles in which every word of the query starts a word of the title: "clean co" finds Clean Code. */
    List<Book> byTitle(String query, int limit)  { return search(titleWords, b -> b.title, query, limit); }
    /** The same over author names: "bloch" finds Joshua Bloch's books. */
    List<Book> byAuthor(String query, int limit) { return search(authorWords, b -> b.author, query, limit); }

    /** The first word walks the index; the other words filter each candidate. Stops at the limit. */
    private List<Book> search(TokenIndex idx, Function<Book, String> field, String query, int limit) {
        List<String> words = TokenIndex.split(query);
        if (words.isEmpty() || limit <= 0) return List.of();
        List<String> rest = words.subList(1, words.size());
        Predicate<String> hasAll = isbn -> {
            List<String> have = TokenIndex.split(field.apply(byIsbn.get(isbn)));
            for (String w : rest) if (have.stream().noneMatch(h -> h.startsWith(w))) return false;
            return true;
        };
        List<Book> out = new ArrayList<>();
        for (String isbn : idx.find(words.get(0), hasAll, limit)) out.add(byIsbn.get(isbn));
        return out;
    }
}

/**
 * The aggregate root and the only writer: the catalogue, the copies, the members, the loans, the holds and ONE
 * lock. Every public call goes through locked(): take the lock, hand on any held copy whose pickup date has
 * passed, do the work, release the lock, and only then tell the listeners.
 */
final class Library {
    private final Catalog catalog = new Catalog();
    private final Map<String, BookCopy> copies = new HashMap<>();          // barcode -> copy
    private final Map<String, Member> members = new HashMap<>();           // id -> member
    private final Map<String, Loan> onLoan = new HashMap<>();              // barcode -> its active loan
    private final TreeMap<LocalDate, Set<Loan>> byDue = new TreeMap<>();   // active loans by due date
    private final PriorityQueue<Hold> readyByDeadline =                    // READY holds, earliest pickup date first
        new PriorityQueue<>(Comparator.comparing((Hold h) -> h.pickupBy).thenComparingInt(h -> h.id));
    private final ReentrantLock lock = new ReentrantLock();
    private final List<LibraryListener> listeners = new CopyOnWriteArrayList<>();
    private final AtomicInteger ids = new AtomicInteger();
    private final ZoneId zone;
    private final int pickupDays;
    private volatile LoanRules rules = new StandardTerms();
    private volatile FinePolicy fines = new CappedFine(new PerDayFine(2_000), 50_000);
    private volatile Clock clock = System::currentTimeMillis;

    /** A library in one time zone, where a copy on the hold shelf waits pickupDays days for its member. */
    Library(ZoneId zone, int pickupDays) { this.zone = zone; this.pickupDays = pickupDays; }

    /** Hand in the rules. The library never builds one, so a new rule costs one changed line here. */
    void configure(LoanRules r, FinePolicy f) { rules = r; fines = f; }
    /** Tests hand in a clock they control. */
    void setClock(Clock c) { clock = c; }
    /** Subscribe a listener. It hears every notice after the lock is released. */
    void addListener(LibraryListener l) { listeners.add(l); }
    /** Today's date in the library's zone, from the handed-in clock. */
    LocalDate today() { return Instant.ofEpochMilli(clock.nowMs()).atZone(zone).toLocalDate(); }

    // ---------------- the catalogue and the members

    /** Add a title. A duplicate ISBN is refused. */
    void addBook(String isbn, String title, String author, long pricePaise) {
        locked(call -> {
            if (catalog.get(isbn) != null) throw new Refused(Refusal.DUPLICATE_ID, isbn);
            catalog.add(new Book(isbn, title, author, pricePaise));
            return null;
        });
    }
    /** Add a copy. Like a returned copy, it goes to the first member waiting for its title, and only then to the shelf. */
    void addCopy(String isbn, String barcode) {
        locked(call -> {
            Book b = book(isbn);
            if (copies.containsKey(barcode)) throw new Refused(Refusal.DUPLICATE_ID, barcode);
            BookCopy c = new BookCopy(barcode, b);
            b.copies.add(c);
            copies.put(barcode, c);
            placeCopy(c, call);
            return null;
        });
    }
    /** Register a member. A duplicate id is refused. */
    void register(String id, String name, Tier tier) {
        locked(call -> {
            if (members.containsKey(id)) throw new Refused(Refusal.DUPLICATE_ID, id);
            members.put(id, new Member(id, name, tier));
            return null;
        });
    }
    /**
     * Unregister. Refused while he has a book out or owes money. His holds are cancelled, and a copy that was set
     * aside for him goes to the next member in line.
     */
    void unregister(String memberId) {
        locked(call -> {
            Member m = member(memberId);
            if (!m.loans.isEmpty()) throw new Refused(Refusal.HAS_LOANS, memberId + " has " + m.loans.size() + " book(s) out");
            if (m.duesPaise > 0) throw new Refused(Refusal.OWES_FINES, memberId + " owes " + Main.rs(m.duesPaise));
            for (Hold h : List.copyOf(m.holds.values())) cancel(h, call);
            members.remove(memberId);
            return null;
        });
    }

    // ---------------- lending: the four calls a desk makes

    /**
     * Lend a copy of this title. His own copy from the hold shelf if one is set aside for him, else the head of the
     * shelf. Every rule is checked before the first write, so a refusal changes nothing.
     */
    Slip checkout(String memberId, String isbn) {
        return locked(call -> {
            Member m = member(memberId);
            Book b = book(isbn);
            Terms t = rules.termsFor(m);                                   // handed-in code runs before any write
            if (m.loans.containsKey(isbn)) throw new Refused(Refusal.ALREADY_HAS_TITLE, memberId + " already has " + b.title);
            if (m.loans.size() >= t.maxLoans()) throw new Refused(Refusal.LIMIT_REACHED, memberId + " has " + t.maxLoans() + " books out");
            if (m.duesPaise > t.maxDuesPaise()) throw new Refused(Refusal.OWES_FINES, memberId + " owes " + Main.rs(m.duesPaise));
            Hold mine = m.holds.get(isbn);
            boolean fromHoldShelf = mine != null && mine.status == HoldStatus.READY;
            BookCopy copy = fromHoldShelf ? mine.copy : b.peekShelf();     // a copy held for someone else is not on the shelf
            if (copy == null)
                throw new Refused(Refusal.NOT_AVAILABLE, b.title + (mine != null ? ": you are number " + b.position(m) + " in the queue" : ": place a hold"));
            // commit: nothing below can fail
            if (fromHoldShelf) { mine.status = HoldStatus.COLLECTED; mine.copy = null; m.holds.remove(isbn); }
            else b.takeFromShelf();
            copy.status = CopyStatus.LOANED;
            Loan loan = new Loan(ids.incrementAndGet(), copy, m, call.today(), call.today().plusDays(t.loanDays()));
            onLoan.put(copy.barcode, loan);
            m.loans.put(isbn, loan);
            index(loan);
            return slip(loan);
        });
    }

    /**
     * Place a hold. If a copy is on the shelf it is set aside for him at once (READY); otherwise he joins the back
     * of the FIFO queue (WAITING). Either way no copy sits on the shelf while someone waits for its title.
     */
    HoldSlip placeHold(String memberId, String isbn) {
        return locked(call -> {
            Member m = member(memberId);
            Book b = book(isbn);
            if (m.loans.containsKey(isbn) || m.holds.containsKey(isbn))
                throw new Refused(Refusal.ALREADY_HAS_TITLE, memberId + " already has or awaits " + b.title);
            Hold h = new Hold(ids.incrementAndGet(), m, b);
            m.holds.put(isbn, h);
            BookCopy free = b.takeFromShelf();
            if (free != null) setAside(h, free, call);                       // a copy is on the shelf: it is his
            else b.enqueue(h);                                               // none: the back of the queue
            return holdSlip(h);
        });
    }

    /** Cancel his hold. A WAITING hold is skipped when it reaches the front; a READY one hands its copy to the next member. */
    void cancelHold(String memberId, String isbn) {
        locked(call -> {
            Member m = member(memberId);
            Hold h = m.holds.get(isbn);
            if (h == null) throw new Refused(Refusal.NO_HOLD, memberId + " has no hold on " + isbn);
            cancel(h, call);
            return null;
        });
    }

    /**
     * Check a copy back in. The order is the design: find the loan (do not remove it); ask the fine rule, which is
     * handed-in code and may throw while nothing has changed; then commit (close the loan, free his slot, add the
     * fine); then placeCopy gives the copy to the first member waiting, or to the shelf. Listeners hear after the
     * unlock. A second scan of the same barcode finds no loan and is refused, so nobody is fined twice.
     */
    Receipt returnCopy(String barcode) {
        return locked(call -> {
            Loan loan = activeLoan(barcode);
            long fine = fineFor(loan, call.today());                        // may throw: nothing has changed yet
            // commit: nothing below can fail
            onLoan.remove(barcode);
            unindex(loan);
            loan.status = LoanStatus.RETURNED;
            loan.closedOn = call.today();
            loan.chargedPaise = fine;
            loan.member.loans.remove(loan.copy.book.isbn);
            if (fine > 0) {
                loan.member.duesPaise += fine;
                call.events().add(new LibraryEvent(EventKind.FINE_CHARGED, loan.member.id, loan.copy.book.isbn, barcode, call.today(), fine));
            }
            String heldFor = placeCopy(loan.copy, call);                      // the queue before the shelf
            return new Receipt(barcode, fine, heldFor);
        });
    }

    /**
     * Renew: one more loan period on the due date. Refused when the book is overdue, when he has used his renewals,
     * and when anyone is waiting for the title. The due date is the key of the due index, so the loan leaves the
     * index before the date changes and goes back in after.
     */
    Slip renew(String barcode) {
        return locked(call -> {
            Loan loan = activeLoan(barcode);
            Terms t = rules.termsFor(loan.member);
            if (call.today().isAfter(loan.due)) throw new Refused(Refusal.OVERDUE, barcode + " was due on " + loan.due);
            if (loan.renewals >= t.maxRenewals()) throw new Refused(Refusal.RENEWAL_LIMIT, barcode + " renewed " + loan.renewals + " times");
            if (loan.copy.book.firstWaiting() != null) throw new Refused(Refusal.OTHERS_WAITING, loan.copy.book.title + " has a queue");
            unindex(loan);
            loan.due = loan.due.plusDays(t.loanDays());
            loan.renewals++;
            index(loan);
            return slip(loan);
        });
    }

    /**
     * The member lost the copy. The charge is the book's price plus the fine so far, added to his dues. The copy
     * leaves circulation; members waiting for the title keep their places for the next copy that frees up.
     */
    long reportLost(String barcode) {
        return locked(call -> {
            Loan loan = activeLoan(barcode);
            long charge = loan.copy.book.pricePaise + fineFor(loan, call.today());      // handed-in code first
            onLoan.remove(barcode);
            unindex(loan);
            loan.status = LoanStatus.LOST;
            loan.closedOn = call.today();
            loan.chargedPaise = charge;
            loan.member.loans.remove(loan.copy.book.isbn);
            loan.member.duesPaise += charge;
            loan.copy.status = CopyStatus.LOST;
            call.events().add(new LibraryEvent(EventKind.FINE_CHARGED, loan.member.id, loan.copy.book.isbn, barcode, call.today(), charge));
            return charge;
        });
    }

    /** He pays some or all of what he owes, in cash at the desk. */
    void payFine(String memberId, long paise) {
        locked(call -> {
            Member m = member(memberId);
            if (paise <= 0 || paise > m.duesPaise) throw new IllegalArgumentException("pay between 1 paise and " + Main.rs(m.duesPaise));
            m.duesPaise -= paise;
            return null;
        });
    }

    /** The nightly job. It does nothing of its own: every call already hands on holds whose pickup date has passed. */
    void expireHolds() { locked(call -> null); }

    // ---------------- reads: each one a lookup, never a scan of the whole library

    /** Titles matching a title query, with how many copies are on the shelf. O(log n + limit). */
    List<Found> searchTitle(String query, int limit)  { return locked(call -> found(catalog.byTitle(query, limit))); }
    /** Titles matching an author query. O(log n + limit). */
    List<Found> searchAuthor(String query, int limit) { return locked(call -> found(catalog.byAuthor(query, limit))); }
    /** Copies of this title on the shelf right now. O(1). */
    int onShelf(String isbn) { return locked(call -> book(isbn).onShelf()); }
    /** His place in the queue for this title (1 = next), or 0. O(queue length). */
    int position(String memberId, String isbn) { return locked(call -> book(isbn).position(member(memberId))); }
    /** His hold on this title, or null. O(1) to find, plus the queue walk for a WAITING position. */
    HoldSlip holdOf(String memberId, String isbn) {
        return locked(call -> { Hold h = member(memberId).holds.get(isbn); return h == null ? null : holdSlip(h); });
    }
    /** Flipkart's audit, one way: the books this member has out. O(his loans). */
    List<Slip> loansOf(String memberId) {
        return locked(call -> member(memberId).loans.values().stream().map(this::slip).sorted(Comparator.comparing(Slip::barcode)).toList());
    }
    /** Flipkart's audit, the other way: the members who have a copy of this title. O(copies of the title). */
    List<String> borrowersOf(String isbn) {
        return locked(call -> {
            List<String> who = new ArrayList<>();
            for (BookCopy c : book(isbn).copies) { Loan l = onLoan.get(c.barcode); if (l != null) who.add(l.member.id); }
            return who;
        });
    }
    /** Loans past their due date, oldest first. O(log n + k): a range of the due index, not a scan of every loan. */
    List<Slip> overdue() { return locked(call -> slips(byDue.headMap(call.today(), false))); }
    /** Loans due between two days, inclusive; the nightly reminder asks for the next two days. O(log n + k). */
    List<Slip> dueBetween(LocalDate from, LocalDate to) {
        return locked(call -> from.isAfter(to) ? List.<Slip>of() : slips(byDue.subMap(from, true, to, true)));
    }
    /** What he owes, in paise. O(1). */
    long dues(String memberId) { return locked(call -> member(memberId).duesPaise); }
    /** Where this copy is. O(1). */
    CopyStatus status(String barcode) { return locked(call -> copy(barcode).status); }

    // ---------------- the private helpers: all run under the lock

    /** One call's working set: the day it runs on, read once from the clock, and the notices to send after the unlock. */
    private record Call(LocalDate today, List<LibraryEvent> events) {}

    /**
     * The one way in. Lock; hand on held copies whose pickup date has passed; run the body; unlock; then tell the
     * listeners. The notices go out even when the body refused, because the sweep may already have set a copy
     * aside for someone, and he must hear about it.
     */
    private <T> T locked(Function<Call, T> body) {
        List<LibraryEvent> events = new ArrayList<>();
        lock.lock();
        try {
            Call call = new Call(today(), events);
            sweep(call);
            return body.apply(call);
        } finally {
            lock.unlock();
            publish(events);                                               // after the unlock: a slow listener holds up nobody
        }
    }

    /**
     * Where a free copy goes: to the first member still waiting for its title, else back on the shelf. Every path
     * that frees a copy comes through here (a return, a new copy, an expired or cancelled hold, a member leaving),
     * so a copy can never sit on the shelf while someone waits for it. Returns who it went to, or null.
     */
    private String placeCopy(BookCopy c, Call call) {
        Hold next = c.book.nextInLine();                                   // drops cancelled holds from the front
        if (next != null) { setAside(next, c, call); return next.member.id; }
        c.status = CopyStatus.AVAILABLE;
        c.book.shelve(c);
        return null;
    }

    /** Put a copy on the hold shelf for this hold's member, with a pickup date, and queue a notice for him. */
    private void setAside(Hold h, BookCopy c, Call call) {
        h.status = HoldStatus.READY;
        h.copy = c;
        h.pickupBy = call.today().plusDays(pickupDays);
        c.status = CopyStatus.ON_HOLD;
        readyByDeadline.add(h);
        call.events().add(new LibraryEvent(EventKind.HOLD_READY, h.member.id, h.book.isbn, c.barcode, h.pickupBy, 0));
    }

    /** Cancel one hold. WAITING: marked, and dropped when it reaches the front. READY: its copy goes to the next member. */
    private void cancel(Hold h, Call call) {
        boolean wasReady = h.status == HoldStatus.READY;
        BookCopy c = h.copy;
        h.status = HoldStatus.CANCELLED;
        h.copy = null;
        h.member.holds.remove(h.book.isbn);
        if (wasReady) placeCopy(c, call);                                  // left in the deadline heap; dropped when it reaches the top
    }

    /**
     * Hand on every held copy whose pickup date has passed. The heap's head is the earliest date, so when nothing
     * has expired this is one peek. Stale entries (collected or cancelled holds) are dropped as they surface.
     */
    private void sweep(Call call) {
        while (!readyByDeadline.isEmpty()) {
            Hold h = readyByDeadline.peek();
            if (h.status != HoldStatus.READY) { readyByDeadline.poll(); continue; }
            if (!call.today().isAfter(h.pickupBy)) return;                  // the earliest pickup date has not passed
            readyByDeadline.poll();
            BookCopy c = h.copy;
            h.status = HoldStatus.EXPIRED;
            h.copy = null;
            h.member.holds.remove(h.book.isbn);
            call.events().add(new LibraryEvent(EventKind.HOLD_EXPIRED, h.member.id, h.book.isbn, c.barcode, h.pickupBy, 0));
            placeCopy(c, call);                                            // the next member in line, else the shelf
        }
    }

    /** Ask the handed-in fine rule, and refuse an answer below zero: a broken rule must not pay the member. */
    private long fineFor(Loan loan, LocalDate day) {
        long fine = fines.fine(loan, day);
        if (fine < 0) throw new IllegalStateException("a fine rule returned " + fine);
        return fine;
    }

    /** Tell every listener about every notice, each in its own try/catch, so one broken listener cannot stop the others. */
    private void publish(List<LibraryEvent> events) {
        for (LibraryEvent e : events)
            for (LibraryListener l : listeners) {
                try { l.onEvent(e); } catch (RuntimeException ex) { System.err.println("   [listener failed] " + ex.getMessage()); }
            }
    }

    /** The member, or a refusal. */
    private Member member(String id) {
        Member m = members.get(id);
        if (m == null) throw new Refused(Refusal.UNKNOWN_MEMBER, id);
        return m;
    }
    /** The title, or a refusal. */
    private Book book(String isbn) {
        Book b = catalog.get(isbn);
        if (b == null) throw new Refused(Refusal.UNKNOWN_BOOK, isbn);
        return b;
    }
    /** The copy, or a refusal. */
    private BookCopy copy(String barcode) {
        BookCopy c = copies.get(barcode);
        if (c == null) throw new Refused(Refusal.UNKNOWN_COPY, barcode);
        return c;
    }
    /** The active loan behind this barcode, or a refusal: unknown copy, or a copy that is not out. */
    private Loan activeLoan(String barcode) {
        Loan loan = onLoan.get(barcode);
        if (loan == null) throw new Refused(copies.containsKey(barcode) ? Refusal.NOT_ON_LOAN : Refusal.UNKNOWN_COPY, barcode);
        return loan;
    }
    /** File an active loan under its due date. */
    private void index(Loan l) {
        byDue.computeIfAbsent(l.due, d -> new TreeSet<>(Comparator.comparingInt((Loan x) -> x.id))).add(l);
    }
    /** Take a loan out of the due index; drop the date when nothing else is due that day. */
    private void unindex(Loan l) {
        Set<Loan> day = byDue.get(l.due);
        day.remove(l);
        if (day.isEmpty()) byDue.remove(l.due);
    }
    /** The member's copy of a loan: immutable. */
    private Slip slip(Loan l) { return new Slip(l.copy.barcode, l.copy.book.isbn, l.copy.book.title, l.member.id, l.due, l.renewals); }
    /** The member's copy of a hold: immutable. */
    private HoldSlip holdSlip(Hold h) {
        return new HoldSlip(h.member.id, h.book.isbn, h.status, h.status == HoldStatus.WAITING ? h.book.position(h.member) : 0,
                            h.copy == null ? null : h.copy.barcode, h.pickupBy);
    }
    /** Search hits with their shelf counts, read under the lock. */
    private List<Found> found(List<Book> books) {
        List<Found> out = new ArrayList<>();
        for (Book b : books) out.add(new Found(b.isbn, b.title, b.author, b.onShelf(), b.copies.size()));
        return out;
    }
    /** Every loan in a range of the due index, as slips, in date order. */
    private List<Slip> slips(SortedMap<LocalDate, Set<Loan>> range) {
        List<Slip> out = new ArrayList<>();
        for (Set<Loan> day : range.values()) for (Loan l : day) out.add(slip(l));
        return out;
    }
}

/**
 * A thin caller at the counter, or a kiosk: no state and no lock of its own. It turns a request into library
 * calls and says what the member sees.
 */
final class Desk {
    private final Library lib;
    /** A desk in front of one library. */
    Desk(Library lib) { this.lib = lib; }

    /**
     * Flipkart's one request: lend a copy now if one is free for him, else put him in the FIFO queue. Two library
     * calls, and still safe: if a copy comes back in between, placeHold sets it aside for him at once.
     */
    String borrow(String memberId, String isbn) {
        try {
            Slip s = lib.checkout(memberId, isbn);
            return memberId + ": lent " + s.barcode() + ", due " + s.due();
        } catch (Refused no) {
            if (no.why != Refusal.NOT_AVAILABLE) return memberId + ": refused, " + no.why;
        }
        try {
            HoldSlip h = lib.placeHold(memberId, isbn);
            return h.status() == HoldStatus.READY
                ? memberId + ": a copy just came back; " + h.barcode() + " is on the hold shelf for you until " + h.pickupBy()
                : memberId + ": no copy free; you are number " + h.position() + " in the queue";
        } catch (Refused no) {
            if (no.why != Refusal.ALREADY_HAS_TITLE) throw no;
            return memberId + ": already in the queue, number " + lib.position(memberId, isbn);
        }
    }
    /** Scan a returned copy and say where it goes next. */
    String giveBack(String barcode) {
        Receipt r = lib.returnCopy(barcode);
        return "returned " + barcode + (r.finePaise() > 0 ? ", fine " + Main.rs(r.finePaise()) : ", no fine")
             + (r.heldFor() == null ? ", back on the shelf" : ", set aside for " + r.heldFor());
    }
}

/**
 * Proof it runs: the afternoon from page 01, then two races. Fifty members want the last copy (exactly one gets
 * it), and three returns cross twenty requests (no copy on the shelf while anyone waits).
 */
public class Main {
    static final ZoneId IST = ZoneId.of("Asia/Kolkata");

    public static void main(String[] args) throws Exception {
        long[] now = { at(8, 29, 10, 0) };
        Library lib = new Library(IST, 3);
        lib.setClock(() -> now[0]);
        lib.configure(new StandardTerms(), new CappedFine(new PerDayFine(2_000), 50_000));   // Rs 20 a day, at most Rs 500
        lib.addListener(new NoticePrinter());
        String cc = "9780132350884", ej = "9780134685991", ca = "9780134494166";
        lib.addBook(cc, "Clean Code", "Robert C. Martin", 60_000);
        lib.addBook(ej, "Effective Java", "Joshua Bloch", 55_000);
        lib.addBook(ca, "Clean Architecture", "Robert C. Martin", 50_000);
        lib.addCopy(cc, "CC-1"); lib.addCopy(cc, "CC-2"); lib.addCopy(ej, "EJ-1"); lib.addCopy(ca, "CA-1");
        for (String id : List.of("asha", "ravi", "meera", "kabir")) lib.register(id, id, Tier.REGULAR);
        Desk desk = new Desk(lib);

        System.out.println("29 Aug  " + desk.borrow("asha", cc));                 // CC-1, due 12 Sep
        now[0] = at(9, 1, 10, 0);
        System.out.println("1 Sep   " + desk.borrow("ravi", cc));                 // CC-2, the last one on the shelf
        now[0] = at(9, 1, 10, 5);
        System.out.println("1 Sep   " + desk.borrow("meera", cc));                // number 1 in the queue
        System.out.println("1 Sep   " + desk.borrow("kabir", cc));                // number 2
        try { lib.renew("CC-2"); } catch (Refused r) { System.out.println("1 Sep   ravi renews CC-2: " + r.why); }
        System.out.println("        search 'clea': " + lib.searchTitle("clea", 10).stream().map(Found::title).toList()
                           + "; author 'bloch': " + lib.searchAuthor("bloch", 10).stream().map(Found::title).toList());

        now[0] = at(9, 14, 17, 30);
        System.out.println("14 Sep  " + desk.giveBack("CC-1"));                   // two days late: Rs 40; held for meera
        now[0] = at(9, 18, 9, 0);
        lib.expireHolds();                                                        // meera never came: kabir is next
        System.out.println("18 Sep  kabir's hold: " + lib.holdOf("kabir", cc) + "; on the shelf: " + lib.onShelf(cc));
        System.out.println("18 Sep  " + desk.borrow("kabir", cc));                // he collects CC-1
        System.out.println("        overdue today: " + lib.overdue().stream().map(s -> s.barcode() + " (" + s.memberId() + ")").toList()
                           + "; asha owes " + rs(lib.dues("asha")));

        races();
    }

    /** The two races. Each one checks its invariant and throws if it does not hold. */
    static void races() throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(16);

        // race 1: fifty members, one copy, released by one latch: exactly one loan
        Library one = new Library(IST, 3);
        String pp = "9780135957059";
        one.addBook(pp, "The Pragmatic Programmer", "David Thomas", 70_000);
        one.addCopy(pp, "PP-1");
        for (int i = 0; i < 50; i++) one.register("m" + i, "member " + i, Tier.REGULAR);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Slip>> tries = new ArrayList<>();
        for (int i = 0; i < 50; i++) { String id = "m" + i; tries.add(pool.submit(() -> { go.await(); return one.checkout(id, pp); })); }
        go.countDown();
        int loans = 0;
        for (Future<Slip> f : tries) { try { f.get(); loans++; } catch (ExecutionException e) { /* NOT_AVAILABLE for the other 49 */ } }
        System.out.println("race 1: loans = " + loans + " (must be 1), on the shelf = " + one.onShelf(pp));
        if (loans != 1) throw new AssertionError("one copy lent twice");

        // race 2: three returns and twenty requests at the same instant
        Library busy = new Library(IST, 3);
        String dd = "9781449373320";
        busy.addBook(dd, "Designing Data-Intensive Applications", "Martin Kleppmann", 90_000);
        for (int i = 1; i <= 3; i++) busy.addCopy(dd, "DD-" + i);
        for (int i = 0; i < 3; i++) { busy.register("b" + i, "borrower " + i, Tier.REGULAR); busy.checkout("b" + i, dd); }
        for (int i = 0; i < 20; i++) busy.register("w" + i, "wants it " + i, Tier.REGULAR);
        Desk counter = new Desk(busy);
        CountDownLatch start = new CountDownLatch(1);
        List<Future<?>> jobs = new ArrayList<>();
        for (int i = 1; i <= 3; i++) { String bc = "DD-" + i; jobs.add(pool.submit(() -> { start.await(); return busy.returnCopy(bc); })); }
        for (int i = 0; i < 20; i++) { String id = "w" + i; jobs.add(pool.submit(() -> { start.await(); return counter.borrow(id, dd); })); }
        start.countDown();
        for (Future<?> f : jobs) f.get();
        pool.shutdown();
        int lent = 0, setAside = 0, waiting = 0;
        for (int i = 0; i < 20; i++) {
            if (!busy.loansOf("w" + i).isEmpty()) lent++;
            HoldSlip h = busy.holdOf("w" + i, dd);
            if (h != null && h.status() == HoldStatus.READY) setAside++;
            if (h != null && h.status() == HoldStatus.WAITING) waiting++;
        }
        System.out.println("race 2: lent " + lent + ", set aside " + setAside + ", waiting " + waiting
                           + ", on the shelf " + busy.onShelf(dd) + " (served must be 3, waiting 17, shelf 0)");
        if (lent + setAside != 3 || waiting != 17 || busy.onShelf(dd) != 0) throw new AssertionError("a copy on the shelf while someone waits");
    }

    /** Paise as rupees: 4000 -> "Rs 40". */
    static String rs(long paise) { return paise % 100 == 0 ? "Rs " + paise / 100 : String.format("Rs %.2f", paise / 100.0); }
    /** A moment in 2026 in Kolkata, so the demo never depends on when it runs. */
    static long at(int month, int day, int hour, int minute) {
        return LocalDateTime.of(2026, month, day, hour, minute).atZone(IST).toInstant().toEpochMilli();
    }
}
