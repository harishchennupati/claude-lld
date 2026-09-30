import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is one twist; nothing here edits Main.java.

// ---- ext: the short version asked at Uber -------------------------------------------------------------
/**
 * The short version (Uber's coding rounds; codezym tags it Uber, Salesforce, Amazon): rooms are just ids,
 * bookMeeting(meetingId, start, end) returns the lexicographically smallest free room or "", and times are
 * CLOSED: [10, 20] and [20, 30] clash. It is the same service with two changes at the edge: the LowestId
 * chooser, and a closed [s, e] stored as the half-open [s, e + 1).
 */
final class RoomBooking {
    private final BookingService svc = new BookingService();
    private final Map<String, String> meetings = new HashMap<>();          // caller's meeting id -> booking id

    RoomBooking(List<String> roomIds) {
        svc.configure(new LowestId(), new AnyTime(), new InviteAnyway());
        for (String id : roomIds) svc.addRoom(new Room(id, "", 0, Integer.MAX_VALUE, Set.of()));
    }
    /** The smallest free room id for the closed range [start, end], or "" when no room can host it. */
    synchronized String bookMeeting(String meetingId, int startTime, int endTime) {
        if (endTime < startTime || meetings.containsKey(meetingId)) return "";
        Result r = svc.scheduleMeeting(MeetingRequest.of(meetingId, startTime, endTime + 1L));
        if (!r.ok()) return "";
        meetings.put(meetingId, r.booking().id());
        return r.booking().roomId();
    }
    /** True only when the meeting exists and is active; it is then cancelled. */
    synchronized boolean cancelMeeting(String meetingId) {
        String id = meetings.remove(meetingId);
        return id != null && svc.cancelBooking(id);
    }

    /**
     * What a candidate rejected at Uber (2025) wrote, cut down to the check. It asks for the first meeting
     * starting at or after the new meeting's END. That meeting can never overlap, so a meeting that starts
     * INSIDE the new one is never seen. The right second lookup is the first meeting after the START.
     */
    static boolean rejectedIsFree(TreeMap<Integer, Integer> startToEnd, int start, int end) {
        Map.Entry<Integer, Integer> floor = startToEnd.floorEntry(start);
        Map.Entry<Integer, Integer> ceil = startToEnd.ceilingEntry(end);          // the bug: should be higherEntry(start)
        boolean clash = (floor != null && floor.getValue() > start) || (ceil != null && ceil.getKey() < end);
        return !clash;
    }
}

// ---- ext: least idle time and the audit log -------------------------------------------------------------
/**
 * Uber's follow-up: give the meeting to the room that leaves the least idle time around it ("spillage"):
 * the gap back to the room's previous meeting plus the gap on to its next one, each counted to the edge of
 * that day when there is none. Room 1 free 9-10 and room 2 free 9-12: a 9-10 meeting takes room 1.
 */
final class LeastIdleTime implements RoomChooser {
    /** Least idle minutes, then the smallest room, then id. */
    public RoomTimeline choose(List<RoomTimeline> free, Interval w) {
        return Collections.min(free, Comparator.comparingLong((RoomTimeline t) -> idle(t, w))
                                               .thenComparingInt(t -> t.room.capacity()).thenComparing(t -> t.room.id()));
    }
    /** Minutes the room would sit empty just before and just after w, within w's day. */
    static long idle(RoomTimeline t, Interval w) {
        LocalDate day = Time.local(w.start(), Time.OFFICE).toLocalDate();
        long dayStart = day.atStartOfDay(Time.OFFICE).toEpochSecond() / 60;
        long dayEnd = day.plusDays(1).atStartOfDay(Time.OFFICE).toEpochSecond() / 60;
        Booking prev = t.before(w.start()), next = t.after(w.end());
        long left = w.start() - Math.max(dayStart, prev == null ? dayStart : prev.when().end());
        long right = Math.min(dayEnd, next == null ? dayEnd : next.when().start()) - w.end();
        return Math.max(0, left) + Math.max(0, right);
    }
}

/**
 * Uber's other follow-up: an audit log per room (what was booked, moved, cancelled or answered, and when),
 * with entries older than X days deleted. A listener, so the booking code never knows it exists. Per room
 * a TreeMap keyed by the minute an entry was written, so the purge is one headMap(cutoff).clear() that
 * touches only what it deletes.
 */
final class RoomAuditLog implements CalendarListener {
    private final Clock clock;
    private final Map<String, TreeMap<Long, List<String>>> byRoom = new HashMap<>();

    RoomAuditLog(Clock clock) { this.clock = clock; }
    /** Write the change under its room; a move between rooms is written under both. */
    public synchronized void onEvent(CalendarEvent e) {
        long now = clock.nowMinutes();
        String line = e.kind() + " " + e.booking().id() + " " + e.booking().when() + (e.person() == null ? "" : " " + e.person() + " " + e.answer());
        write(e.booking().roomId(), now, line);
        if (e.before() != null && !e.before().roomId().equals(e.booking().roomId())) write(e.before().roomId(), now, line + " (moved out)");
    }
    /** Delete every entry written more than `days` days ago. Returns how many went. */
    synchronized int purgeOlderThan(int days) {
        long cutoff = clock.nowMinutes() - days * 1440L;
        int gone = 0;
        for (TreeMap<Long, List<String>> log : byRoom.values()) {
            SortedMap<Long, List<String>> old = log.headMap(cutoff);
            for (List<String> l : old.values()) gone += l.size();
            old.clear();
        }
        return gone;
    }
    /** A room's entries, oldest first. */
    synchronized List<String> entries(String roomId) {
        List<String> out = new ArrayList<>();
        for (List<String> l : byRoom.getOrDefault(roomId, new TreeMap<>()).values()) out.addAll(l);
        return out;
    }
    /** Append one line under a room and a minute. */
    private void write(String room, long now, String line) {
        byRoom.computeIfAbsent(room, k -> new TreeMap<>()).computeIfAbsent(now, k -> new ArrayList<>()).add(line);
    }
}

// ---- ext: the command-line version asked at Cleartrip ---------------------------------------------------
/**
 * Cleartrip's machine-coding version: commands in, lines out, rooms on floors of buildings, slots in whole
 * hours of one day, at most 12 hours, a search with optional building, floor and seats, and SUGGEST for the
 * next three times that are free. A thin caller: it parses and prints; the service decides everything.
 *   ADD BUILDING b1 | ADD FLOOR b1 7 | ADD CONFROOM b1 7 c1 6 | BOOK u1 1:5 b1 7 c1 | CANCEL u1 1:5 b1 7 c1
 *   LIST BOOKING b1 7 | SEARCH 2:3 [b1 [7 [3]]] | SUGGEST 3:10
 */
final class CommandDriver {
    private final BookingService svc = new BookingService();
    private final LocalDate day;
    private final Map<String, Set<Integer>> floors = new TreeMap<>();      // the buildings and their floors, for validation
    private final Map<String, List<String>> roomsByFloor = new TreeMap<>(); // "b1/7" -> its room ids, for LIST BOOKING

    CommandDriver(LocalDate day) {
        this.day = day;
        svc.configure(new SmallestFit(), new MaxLength(new AnyTime(), 12 * 60), new InviteAnyway());
    }
    /** Run one command and return what it prints. Bad input comes back as an ERROR line, never a crash. */
    String run(String line) {
        String[] w = line.trim().split("\\s+");
        try {
            String cmd = w[0] + (w[0].equals("ADD") || w[0].equals("LIST") ? " " + w[1] : "");
            return switch (cmd) {
                case "ADD BUILDING" -> { floors.putIfAbsent(w[2], new TreeSet<>()); yield "Added building " + w[2] + " into the system."; }
                case "ADD FLOOR" -> { building(w[2]).add(Integer.parseInt(w[3])); yield "Added floor " + w[3] + " in building " + w[2] + "."; }
                case "ADD CONFROOM" -> {
                    floor(w[2], w[3]);
                    svc.addRoom(new Room(id(w[2], w[3], w[4]), w[2], Integer.parseInt(w[3]), w.length > 5 ? Integer.parseInt(w[5]) : 10, Set.of()));
                    roomsByFloor.computeIfAbsent(w[2] + "/" + w[3], k -> new ArrayList<>()).add(id(w[2], w[3], w[4]));
                    yield "Added conference room " + w[4] + " on floor " + w[3] + " in " + w[2] + ".";
                }
                case "BOOK" -> {
                    floor(w[3], w[4]);
                    Result r = svc.bookRoom(id(w[3], w[4], w[5]), MeetingRequest.of(w[1], slot(w[2]).start(), slot(w[2]).end()));
                    yield r.ok() ? "Booked " + w[5] + " " + w[2] + " for " + w[1] + " (" + r.booking().id() + ")" : "ERROR: " + r.reason();
                }
                case "CANCEL" -> {
                    for (Booking b : svc.listBookingsForRoom(id(w[3], w[4], w[5]), slot(w[2])))
                        if (b.when().equals(slot(w[2])) && b.organizer().equals(w[1]) && svc.cancelBooking(b.id())) yield "Cancelled " + w[5] + " " + w[2] + ".";
                    yield "ERROR: " + w[1] + " has no booking of " + w[5] + " at " + w[2];
                }
                case "LIST BOOKING" -> {
                    floor(w[2], w[3]);
                    StringBuilder out = new StringBuilder();
                    Interval whole = new Interval(hour(0), hour(24));
                    for (String room : roomsByFloor.getOrDefault(w[2] + "/" + w[3], List.of()))
                        for (Booking b : svc.listBookingsForRoom(room, whole))
                            out.append(hours(b.when())).append(' ').append(w[3]).append(' ').append(w[2]).append(' ').append(room.substring(room.lastIndexOf('/') + 1)).append('\n');
                    yield out.length() == 0 ? "No bookings" : out.toString().trim();
                }
                case "SEARCH" -> {
                    int seats = w.length > 4 ? Integer.parseInt(w[4]) : 1;
                    List<String> hits = new ArrayList<>();
                    for (Room r : svc.getAvailableRooms(slot(w[1]), seats, Set.of()))
                        if ((w.length < 3 || r.building().equals(w[2])) && (w.length < 4 || r.floor() == Integer.parseInt(w[3])))
                            hits.add(r.id().substring(r.id().lastIndexOf('/') + 1) + " " + r.floor() + " " + r.building());
                    yield hits.isEmpty() ? "No Rooms available" : String.join("\n", hits);
                }
                case "SUGGEST" -> String.join(", ", suggest(slot(w[1]), 3));
                default -> "ERROR: unknown command: " + line;
            };
        } catch (RuntimeException e) { return "ERROR: " + e.getMessage(); }
    }
    /** The next `count` start hours after the asked-for one, same length, where some room is free; the room is named. */
    List<String> suggest(Interval asked, int count) {
        List<String> out = new ArrayList<>();
        long len = asked.minutes();
        for (long s = asked.start() + 60; s + len <= hour(24) && out.size() < count; s += 60) {
            List<Room> free = svc.getAvailableRooms(new Interval(s, s + len), 1, Set.of());
            if (!free.isEmpty()) out.add(hours(new Interval(s, s + len)) + " " + free.get(0).id());
        }
        return out;
    }
    /** "1:5" -> 01:00-05:00 on the driver's day. */
    private Interval slot(String hh) {
        String[] p = hh.split(":");
        return new Interval(hour(Integer.parseInt(p[0])), hour(Integer.parseInt(p[1])));
    }
    /** The minute of a whole hour of the day, office time (24 = the next midnight). */
    private long hour(int h) { return day.atStartOfDay(Time.OFFICE).plusHours(h).toEpochSecond() / 60; }
    /** 01:00-05:00 -> "1:5". */
    private String hours(Interval i) { return (i.start() - hour(0)) / 60 + ":" + (i.end() - hour(0)) / 60; }
    /** A room id unique across buildings: b1/7/c1. */
    private static String id(String b, String f, String room) { return b + "/" + f + "/" + room; }
    /** A known building's floors, or an error. */
    private Set<Integer> building(String b) {
        Set<Integer> f = floors.get(b);
        if (f == null) throw new NoSuchElementException("no building " + b);
        return f;
    }
    /** Check that a floor exists in a building. */
    private void floor(String b, String f) {
        if (!building(b).contains(Integer.parseInt(f))) throw new NoSuchElementException("no floor " + f + " in " + b);
    }
}

// ---- ext: hold, then confirm ----------------------------------------------------------------------------
/**
 * "Selected but not booked yet" (Amazon): a hold takes the room like a booking, so nobody else can, and
 * carries a deadline. confirm() before the deadline keeps it; after it, the hold is already released.
 * Every call sweeps expired holds first, so no timer thread is needed. The desk's lock guards only its own
 * map of deadlines; the service is always called outside it.
 */
final class HoldDesk {
    private final BookingService svc;
    private final Clock clock;
    private final long holdMinutes;
    private final Map<String, Long> deadline = new HashMap<>();              // meeting id -> the minute its hold ends
    private final ReentrantLock lock = new ReentrantLock();

    HoldDesk(BookingService svc, Clock clock, long holdMinutes) { this.svc = svc; this.clock = clock; this.holdMinutes = holdMinutes; }
    /** Hold a room: a real booking, remembered here with its deadline. */
    Result hold(String roomId, MeetingRequest r) {
        releaseExpired();
        Result res = svc.bookRoom(roomId, r);
        if (res.ok()) {
            lock.lock();
            try { deadline.put(res.booking().id(), clock.nowMinutes() + holdMinutes); } finally { lock.unlock(); }
        }
        return res;
    }
    /** Keep the hold for good. False when it expired (the room is free again) or was never held. */
    boolean confirm(String meetingId) {
        releaseExpired();
        lock.lock();
        try { return deadline.remove(meetingId) != null; } finally { lock.unlock(); }
    }
    /** Cancel every hold whose deadline has passed; exactly one of confirm and expiry wins, under the lock. Returns how many. */
    int releaseExpired() {
        List<String> gone = new ArrayList<>();
        lock.lock();
        try {
            long now = clock.nowMinutes();
            for (Iterator<Map.Entry<String, Long>> it = deadline.entrySet().iterator(); it.hasNext(); ) {
                Map.Entry<String, Long> e = it.next();
                if (e.getValue() <= now) { gone.add(e.getKey()); it.remove(); }
            }
        } finally { lock.unlock(); }
        for (String id : gone) svc.cancelBooking(id);                          // outside the desk's lock
        return gone.size();
    }
}

// ---- ext: capacity above one: gym classes and doctors' slots -------------------------------------------
/** A membership tier and how many classes it lets a member book (PhonePe's version: 10, 5, 3). */
enum Tier {
    PLATINUM(10), GOLD(5), SILVER(3);
    final int classes;
    Tier(int classes) { this.classes = classes; }
}

/** One class, or one doctor's slot (capacity 1): its time, its seats, who is in, who waits, in order. */
final class ClassSlot {
    final String id, title;
    final Interval when;
    final int capacity;
    final Set<String> booked = new LinkedHashSet<>();                      // guarded by the desk's lock
    final Deque<String> waiting = new ArrayDeque<>();                      // first in, first promoted

    ClassSlot(String id, String title, Interval when, int capacity) {
        this.id = id; this.title = title; this.when = when; this.capacity = capacity;
    }
}

/**
 * Gym classes and doctors' slots: the meeting-room core with capacity above one, behind one lock. book() is
 * idempotent (a retry is not a second seat), refuses a member who is already in an overlapping class or has
 * no classes left in their tier, and queues when the class is full. cancel() works until 30 minutes before
 * the start, gives the class back to the member's quota, and seats the first waiting member who is still
 * allowed, inside the same lock, so a freed seat is never lost and never given twice.
 */
final class ClassDesk {
    /** How a request ended. */
    enum Answer { BOOKED, ALREADY_BOOKED, WAITLISTED, OVERLAPS, NO_CLASSES_LEFT, TOO_LATE, NOT_BOOKED, CANCELLED }
    static final long CANCEL_CUTOFF_MINUTES = 30;
    private final ReentrantLock lock = new ReentrantLock();
    private final Map<String, ClassSlot> classes = new HashMap<>();
    private final Map<String, Tier> tiers = new HashMap<>();
    private final Map<String, Integer> used = new HashMap<>();              // classes booked, per member
    private final Map<String, List<ClassSlot>> mine = new HashMap<>();       // member -> classes booked
    private final Clock clock;

    ClassDesk(Clock clock) { this.clock = clock; }
    /** Register a member with a tier. */
    void addMember(String m, Tier t) { lock.lock(); try { tiers.put(m, t); } finally { lock.unlock(); } }
    /** Schedule a class. */
    void addClass(ClassSlot c) { lock.lock(); try { classes.put(c.id, c); } finally { lock.unlock(); } }
    /** A seat, or a place in the queue. */
    Answer book(String member, String classId) {
        lock.lock();
        try {
            ClassSlot c = cls(classId);
            if (c.booked.contains(member)) return Answer.ALREADY_BOOKED;          // a retry changes nothing
            if (c.waiting.contains(member)) return Answer.WAITLISTED;
            Answer no = allowed(member, c);
            if (no != null) return no;
            if (c.booked.size() < c.capacity) { seat(member, c); return Answer.BOOKED; }
            c.waiting.addLast(member);
            return Answer.WAITLISTED;
        } finally { lock.unlock(); }
    }
    /** Give up a seat (or a place in the queue); the first waiting member who is still allowed takes the seat. */
    Answer cancel(String member, String classId) {
        lock.lock();
        try {
            ClassSlot c = cls(classId);
            if (c.waiting.remove(member)) return Answer.CANCELLED;
            if (!c.booked.contains(member)) return Answer.NOT_BOOKED;
            if (clock.nowMinutes() > c.when.start() - CANCEL_CUTOFF_MINUTES) return Answer.TOO_LATE;
            c.booked.remove(member);
            used.merge(member, -1, Integer::sum);
            mine.get(member).remove(c);
            while (!c.waiting.isEmpty() && c.booked.size() < c.capacity) {
                String next = c.waiting.pollFirst();
                if (allowed(next, c) == null) seat(next, c);                         // one who can no longer take it is skipped
            }
            return Answer.CANCELLED;
        } finally { lock.unlock(); }
    }
    /** The ids of classes with a free seat, in the order the handed-in ranking says: start time today, a doctor's rating tomorrow. */
    List<String> open(Comparator<ClassSlot> ranking) {
        lock.lock();
        try {
            List<ClassSlot> free = new ArrayList<>();
            for (ClassSlot c : classes.values()) if (c.booked.size() < c.capacity) free.add(c);
            free.sort(ranking);
            List<String> ids = new ArrayList<>();
            for (ClassSlot c : free) ids.add(c.id);
            return ids;                                     // ids, not the slots: their sets are guarded by this lock
        } finally { lock.unlock(); }
    }
    /** Who is in, and who waits, in order: a copy. */
    List<String> seated(String classId) { lock.lock(); try { return new ArrayList<>(cls(classId).booked); } finally { lock.unlock(); } }
    /** The waiting list, first first: a copy. */
    List<String> waiting(String classId) { lock.lock(); try { return new ArrayList<>(cls(classId).waiting); } finally { lock.unlock(); } }
    /** Why a member may not take this class, or null when they may. */
    private Answer allowed(String member, ClassSlot c) {
        Tier t = tiers.get(member);
        if (t == null) throw new NoSuchElementException("no member " + member);
        if (used.getOrDefault(member, 0) >= t.classes) return Answer.NO_CLASSES_LEFT;
        for (ClassSlot other : mine.getOrDefault(member, List.of())) if (other.when.overlaps(c.when)) return Answer.OVERLAPS;
        return null;
    }
    /** Give a member a seat and count it against their tier. */
    private void seat(String member, ClassSlot c) {
        c.booked.add(member);
        used.merge(member, 1, Integer::sum);
        mine.computeIfAbsent(member, k -> new ArrayList<>()).add(c);
    }
    /** A class by id, or an exception naming it. */
    private ClassSlot cls(String id) {
        ClassSlot c = classes.get(id);
        if (c == null) throw new NoSuchElementException("no class " + id);
        return c;
    }
}

// ---- ext: a time rule on a grid -------------------------------------------------------------------------
/**
 * One more time rule, stacked on the others without editing them: a meeting starts and ends on a grid (30
 * minutes for Flipkart's doctors, whole hours in Cleartrip's version). The grid is read on the WALL clock:
 * India is UTC+5:30, so a grid on UTC minutes would put the hour marks at half past. Every rule must pass,
 * so the order of wrapping changes only which reason is reported first.
 */
final class SlotGrid implements BookingPolicy {
    private final BookingPolicy base;
    private final int gridMinutes;
    private final ZoneId zone;
    SlotGrid(BookingPolicy base, int gridMinutes, ZoneId zone) { this.base = base; this.gridMinutes = gridMinutes; this.zone = zone; }
    /** The wrapped rule first, then: start and end on the grid, local time. */
    public String whyNot(Interval w, long now) {
        String why = base.whyNot(w, now);
        if (why != null) return why;
        ZonedDateTime s = Time.local(w.start(), zone), e = Time.local(w.end(), zone);
        boolean onGrid = (s.getHour() * 60 + s.getMinute()) % gridMinutes == 0 && (e.getHour() * 60 + e.getMinute()) % gridMinutes == 0;
        return onGrid ? null : "slots are " + gridMinutes + " minutes, on the " + gridMinutes + "-minute marks";
    }
}

// ---- ext: the time most people can make -----------------------------------------------------------------
/**
 * Adobe's variant: no time suits everyone, so find the time the MOST people can make. The only starts worth
 * trying are the window's start and the end of someone's meeting (any other start can slide earlier without
 * losing anyone), so count who is free at each and keep the best, earliest first.
 */
final class MostAvailable {
    /** The chosen time, who can come, who cannot. */
    record Pick(Interval when, List<String> free, List<String> busy) {}
    /** O(C x P x k) for C candidate starts, P people and k meetings each in the window. */
    static Pick find(BookingService svc, List<String> who, long minutes, Interval window) {
        Map<String, List<Interval>> busy = new LinkedHashMap<>();
        TreeSet<Long> starts = new TreeSet<>(List.of(window.start()));
        for (String p : who) {
            List<Interval> taken = svc.busyTimes(p, window);
            busy.put(p, taken);
            for (Interval i : taken) starts.add(i.end());
        }
        Pick best = null;
        for (long t : starts) {
            if (t + minutes > window.end()) break;
            Interval slot = new Interval(t, t + minutes);
            List<String> free = new ArrayList<>(), out = new ArrayList<>();
            for (String p : who) (busy.get(p).stream().anyMatch(i -> i.overlaps(slot)) ? out : free).add(p);
            if (best == null || free.size() > best.free().size()) best = new Pick(slot, free, out);
        }
        return best;
    }
}

// ---- ext: tennis courts at Atlassian ---------------------------------------------------------------------
/** One tennis-court booking in Atlassian's "Expanding Tennis Club": an id and [start, finish). */
record CourtBooking(int id, int start, int finish) {}

/**
 * Give every booking a court, using as few courts as possible (LeetCode 253, plus the assignment). Sort by
 * start; keep the courts in a min-heap by the minute each is free again; reuse the one free earliest if it
 * is free by this start, else open a new court. O(n log n). Level 2 adds X minutes of cleaning after every
 * booking, and level 3 adds Y minutes of maintenance after every K bookings on a court: both only change
 * the minute a court is free again.
 */
final class CourtPlanner {
    /** booking id -> court number (0, 1, 2 ...). clean = X; maintainEvery = K (0 = never); maintain = Y. */
    static Map<Integer, Integer> assignCourts(List<CourtBooking> bookings, int clean, int maintainEvery, int maintain) {
        List<CourtBooking> sorted = new ArrayList<>(bookings);
        sorted.sort(Comparator.comparingInt(CourtBooking::start).thenComparingInt(CourtBooking::id));
        PriorityQueue<int[]> free = new PriorityQueue<>(Comparator.comparingInt((int[] c) -> c[0]).thenComparingInt(c -> c[1]));
        Map<Integer, Integer> plan = new LinkedHashMap<>();
        int courts = 0;
        for (CourtBooking b : sorted) {
            int[] c = !free.isEmpty() && free.peek()[0] <= b.start() ? free.poll() : new int[] {0, courts++, 0};   // {free at, court, bookings so far}
            c[2]++;
            c[0] = b.finish() + clean + (maintainEvery > 0 && c[2] % maintainEvery == 0 ? maintain : 0);
            plan.put(b.id(), c[1]);
            free.add(c);
        }
        return plan;
    }
    /** Only the count: the most bookings running at one moment. A sweep over the sorted starts and finishes. */
    static int minCourts(List<CourtBooking> bookings) {
        int[] starts = bookings.stream().mapToInt(CourtBooking::start).sorted().toArray();
        int[] ends = bookings.stream().mapToInt(CourtBooking::finish).sorted().toArray();
        int running = 0, most = 0, j = 0;
        for (int s : starts) {
            while (ends[j] <= s) { j++; running--; }            // a court freed at s can be reused at s
            running++;
            most = Math.max(most, running);
        }
        return most;
    }
    /** The first question of the round: do two bookings clash? */
    static boolean conflict(CourtBooking a, CourtBooking b) { return a.start() < b.finish() && b.start() < a.finish(); }
}

// ---- ext: sharing and proposals at Zepto ----------------------------------------------------------------
/** What one person may do with another's calendar: see only busy blocks (the default), see the details, or edit. */
enum Access { FREE_BUSY, VIEW, EDIT }

/**
 * Zepto's follow-ups: share a calendar with view or edit permission, and let a guest propose a new time
 * that the organiser accepts. Permissions are data (per owner: who -> access), checked at every entry
 * point; an accepted proposal is just reschedule(), so it is all or nothing for free.
 */
final class SharedCalendars {
    /** A guest's suggestion: this meeting at that time. */
    record Proposal(String meetingId, String from, Interval when) {}
    private final BookingService svc;
    private final Map<String, Map<String, Access>> grants = new ConcurrentHashMap<>();    // owner -> (viewer -> access)
    private final Map<String, Proposal> proposals = new ConcurrentHashMap<>();
    private final AtomicInteger nextProposal = new AtomicInteger();

    SharedCalendars(BookingService svc) { this.svc = svc; }
    /** The owner lets `viewer` see or edit. */
    void share(String owner, String viewer, Access a) { grants.computeIfAbsent(owner, k -> new ConcurrentHashMap<>()).put(viewer, a); }
    /** What `viewer` may do with `owner`'s calendar; everyone may edit their own. */
    Access accessOf(String owner, String viewer) {
        return owner.equals(viewer) ? Access.EDIT : grants.getOrDefault(owner, Map.of()).getOrDefault(viewer, Access.FREE_BUSY);
    }
    /** The owner's window as the viewer may see it: titles and rooms, or only "busy" blocks. */
    List<String> view(String viewer, String owner, Interval window) {
        boolean details = accessOf(owner, viewer) != Access.FREE_BUSY;
        List<String> out = new ArrayList<>();
        for (Booking b : svc.listBookingsForEmployee(owner, window)) out.add(details ? b.title() + " " + b.roomId() + " " + b.when() : "busy " + b.when());
        return out;
    }
    /** Move a meeting as `editor`: its organiser, or someone the organiser gave EDIT. */
    Result move(String editor, String meetingId, Interval to) {
        Booking b = svc.get(meetingId);
        if (b == null) throw new NoSuchElementException("no meeting " + meetingId);
        if (accessOf(b.organizer(), editor) != Access.EDIT) throw new SecurityException(editor + " may not edit " + b.organizer() + "'s meetings");
        return svc.reschedule(meetingId, to);
    }
    /** A guest proposes a new time; nothing moves yet. Returns the proposal's id. */
    String propose(String guest, String meetingId, Interval to) {
        Booking b = svc.get(meetingId);
        if (b == null || !b.guests().contains(guest)) throw new IllegalArgumentException(guest + " is not a guest of " + meetingId);
        String id = "P" + nextProposal.incrementAndGet();
        proposals.put(id, new Proposal(meetingId, guest, to));
        return id;
    }
    /** The organiser (or an editor) accepts: the meeting moves, all or nothing, and the proposal is used up. */
    Result accept(String editor, String proposalId) {
        Proposal p = proposals.remove(proposalId);
        if (p == null) throw new NoSuchElementException("no proposal " + proposalId);
        return move(editor, p.meetingId(), p.when());
    }
}

// ---- ext: persistence -----------------------------------------------------------------------------------
/**
 * The meetings behind an interface, so they can live in a database. The method that matters is insertIfFree:
 * once several app servers book the same room, the database itself must refuse an overlap.
 *   Postgres, one constraint:
 *     CREATE EXTENSION btree_gist;
 *     CREATE TABLE booking (id text PRIMARY KEY, room_id text NOT NULL, during tstzrange NOT NULL,
 *       organizer text NOT NULL, EXCLUDE USING gist (room_id WITH =, during WITH &&));
 *     -- a range is '[)' unless you say otherwise: half-open, the same rule as Interval
 *   MySQL, a row lock on the room, then check and insert in one transaction:
 *     BEGIN; SELECT id FROM room WHERE id = ? FOR UPDATE;
 *     SELECT 1 FROM booking WHERE room_id = ? AND start_at < ? AND end_at > ? LIMIT 1;  -- INSERT only if empty
 *     COMMIT;
 */
interface BookingRepository {
    /** Store the meeting unless it overlaps one already in its room: the database's all-or-nothing check. */
    boolean insertIfFree(Booking b);
    /** Delete by id; false when there is no such row. */
    boolean delete(String meetingId);
    /** A room's meetings overlapping a window. */
    List<Booking> forRoom(String roomId, Interval window);
}

/** The in-memory stand-in: a lock per room plays the part of the row lock (or of the constraint). */
final class InMemoryBookingRepository implements BookingRepository {
    private final Map<String, List<Booking>> rows = new ConcurrentHashMap<>();          // room id -> its rows
    private final Map<String, Object> roomLocks = new ConcurrentHashMap<>();
    private final Map<String, String> roomOf = new ConcurrentHashMap<>();                // meeting id -> room id

    /** Lock the room, look for an overlap, insert only if there is none. */
    public boolean insertIfFree(Booking b) {
        synchronized (roomLock(b.roomId())) {
            List<Booking> room = rows.computeIfAbsent(b.roomId(), k -> new ArrayList<>());
            for (Booking o : room) if (o.when().overlaps(b.when())) return false;   // start_at < ? AND end_at > ?
            room.add(b);
            roomOf.put(b.id(), b.roomId());
            return true;
        }
    }
    /** Delete under the room's lock. */
    public boolean delete(String meetingId) {
        String room = roomOf.remove(meetingId);
        if (room == null) return false;
        synchronized (roomLock(room)) { return rows.get(room).removeIf(b -> b.id().equals(meetingId)); }
    }
    /** Read under the room's lock. */
    public List<Booking> forRoom(String roomId, Interval window) {
        synchronized (roomLock(roomId)) {
            List<Booking> out = new ArrayList<>();
            for (Booking b : rows.getOrDefault(roomId, List.of())) if (b.when().overlaps(window)) out.add(b);
            out.sort(Booking.BY_START);
            return out;
        }
    }
    /** One lock object per room, made on first use. */
    private Object roomLock(String roomId) { return roomLocks.computeIfAbsent(roomId, k -> new Object()); }
}

// ---- ext: a lock per room -------------------------------------------------------------------------------
/**
 * Rung 2 of the ladder: a lock per room instead of one for the office. A named room takes one lock; "any
 * room" tries the fitting rooms smallest first, one lock at a time, checking again under each; moving a
 * meeting between rooms takes both locks in room-id order, so two moves can never wait for each other.
 * What it gives up: the room and the people's calendars no longer change in one step (calendars left out here).
 */
final class PerRoomBooker {
    private final Map<String, RoomTimeline> rooms = new TreeMap<>();       // filled in the constructor, never changed: safe to read
    private final Map<String, ReentrantLock> locks = new HashMap<>();
    private final Map<String, Booking> live = new ConcurrentHashMap<>();    // meeting id -> current copy
    private final AtomicLong nextId = new AtomicLong();

    PerRoomBooker(List<Room> all) {
        for (Room r : all) { rooms.put(r.id(), new RoomTimeline(r)); locks.put(r.id(), new ReentrantLock()); }
    }
    /** This room or nothing (null). Only this room's lock is taken. */
    Booking bookRoom(String roomId, String who, Interval w) {
        ReentrantLock l = locks.get(roomId);
        l.lock();
        try {
            RoomTimeline t = rooms.get(roomId);
            if (!t.isFree(w, null)) return null;
            Booking b = new Booking("P" + nextId.incrementAndGet(), roomId, w, who, "meeting", 1, Set.of(), List.of(), null);
            t.add(b);
            live.put(b.id(), b);
            return b;
        } finally { l.unlock(); }
    }
    /** Any room that seats `seats`, smallest first, one lock at a time; a room taken meanwhile is skipped. */
    Booking bookAny(String who, Interval w, int seats) {
        List<RoomTimeline> order = new ArrayList<>(rooms.values());
        order.sort(Comparator.comparingInt((RoomTimeline t) -> t.room.capacity()).thenComparing(t -> t.room.id()));
        for (RoomTimeline t : order) {
            if (!t.room.fits(seats, Set.of())) continue;
            Booking b = bookRoom(t.room.id(), who, w);
            if (b != null) return b;
        }
        return null;
    }
    /** Move a meeting to a room and a time: both rooms locked, lower id first, checked, then swapped. Null when refused. */
    Booking move(String meetingId, String toRoom, Interval to) {
        Booking b = live.get(meetingId);
        String a = b.roomId().compareTo(toRoom) <= 0 ? b.roomId() : toRoom, z = a.equals(b.roomId()) ? toRoom : b.roomId();
        locks.get(a).lock();
        try {
            locks.get(z).lock();                                               // the same room twice is fine: re-entrant
            try {
                if (live.get(meetingId) != b) return null;                     // it moved while we were locking: the caller retries
                if (!rooms.get(toRoom).isFree(to, b.id())) return null;
                Booking moved = b.movedTo(toRoom, to);
                rooms.get(b.roomId()).remove(b);
                rooms.get(toRoom).add(moved);
                live.put(meetingId, moved);
                return moved;
            } finally { locks.get(z).unlock(); }
        } finally { locks.get(a).unlock(); }
    }
    /** How many overlapping pairs there are in all rooms (must be 0), each room read under its lock. */
    int overlaps() {
        int bad = 0;
        for (RoomTimeline t : rooms.values()) {
            locks.get(t.room.id()).lock();
            try {
                List<Booking> all = t.all();
                for (int i = 1; i < all.size(); i++) if (all.get(i - 1).when().overlaps(all.get(i).when())) bad++;
            } finally { locks.get(t.room.id()).unlock(); }
        }
        return bad;
    }
}

// ---- ext: time zones ------------------------------------------------------------------------------------
/**
 * A weekly 09:00 meeting for a London team, across the night the UK clocks go back (Sunday 25 Oct 2026).
 * Adding 7 x 1440 minutes keeps the UTC time, so 09:00 becomes 08:00 in London; Recurrence adds 7 days on
 * London's calendar and stays at 09:00. Store instants, expand rules in the organiser's zone, convert to show.
 */
final class TimeZones {
    static final ZoneId LONDON = ZoneId.of("Europe/London");
    private TimeZones() {}
    /** The naive series: the first date plus k weeks of minutes. */
    static List<Interval> naiveWeekly(Interval first, int count) {
        List<Interval> out = new ArrayList<>();
        for (int k = 0; k < count; k++) out.add(new Interval(first.start() + k * 7 * 1440L, first.end() + k * 7 * 1440L));
        return out;
    }
    /** "09:00" on a zone's clock. */
    static String hm(long minute, ZoneId zone) {
        ZonedDateTime z = Time.local(minute, zone);
        return String.format("%02d:%02d", z.getHour(), z.getMinute());
    }
    /** The minute of a wall-clock time in a zone. */
    static long at(ZoneId zone, int y, int mo, int d, int h, int mi) { return LocalDateTime.of(y, mo, d, h, mi).atZone(zone).toEpochSecond() / 60; }
}

// ---- ext: a recurrence from a string --------------------------------------------------------------------
/**
 * Factory, where it earns its place: the rule arrives as text, an iCalendar RRULE such as
 * "FREQ=WEEKLY;INTERVAL=2;UNTIL=20261221", and one parser turns it into a Recurrence. Until rules arrive as
 * strings, Recurrence.weekly(...) is enough and a factory would be decoration.
 */
final class RecurrenceFactory {
    private RecurrenceFactory() {}
    /** FREQ=DAILY or WEEKLY, an optional INTERVAL, and UNTIL as a date; anything else is refused by name. */
    static Recurrence parse(String rrule, ZoneId zone) {
        Map<String, String> parts = new HashMap<>();
        for (String p : rrule.split(";")) {
            String[] kv = p.split("=", 2);
            if (kv.length != 2) throw new IllegalArgumentException("not KEY=VALUE: " + p);
            parts.put(kv[0].trim().toUpperCase(), kv[1].trim());
        }
        for (String k : parts.keySet())
            if (!Set.of("FREQ", "INTERVAL", "UNTIL").contains(k)) throw new IllegalArgumentException(k + " is not supported");
        int step = switch (parts.getOrDefault("FREQ", "")) {
            case "DAILY" -> 1;
            case "WEEKLY" -> 7;
            default -> throw new IllegalArgumentException("FREQ must be DAILY or WEEKLY: " + rrule);
        };
        String until = parts.get("UNTIL");
        if (until == null) throw new IllegalArgumentException("UNTIL is required: a series must end");
        int interval = Integer.parseInt(parts.getOrDefault("INTERVAL", "1"));
        return new Recurrence(step * interval, LocalDate.parse(until.substring(0, 8), DateTimeFormatter.BASIC_ISO_DATE), zone);
    }
}

/** Runs every extension once, so the page's follow-up code is code that has actually executed. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        System.out.println("-- the short version (codezym's RoomBooking, closed intervals, smallest id)");
        RoomBooking rb = new RoomBooking(List.of("roomA", "roomB"));
        System.out.println("   m1 10-20 -> " + rb.bookMeeting("m1", 10, 20) + ", m2 15-25 -> " + rb.bookMeeting("m2", 15, 25)
                           + ", m3 20-30 -> '" + rb.bookMeeting("m3", 20, 30) + "', cancel m1 -> " + rb.cancelMeeting("m1")
                           + ", m4 20-30 -> " + rb.bookMeeting("m4", 20, 30));
        TreeMap<Integer, Integer> one = new TreeMap<>(Map.of(600, 660));
        System.out.println("   the rejected check says 09:30-10:30 is free next to 10:00-11:00: " + RoomBooking.rejectedIsFree(one, 570, 630));

        System.out.println("-- least idle time, and the audit log");
        BookingService u = Main.office();
        long[] now = {Main.mon(7, 0)};
        u.setClock(() -> now[0]);
        RoomAuditLog audit = new RoomAuditLog(() -> now[0]);
        u.addListener(audit);
        for (String room : List.of("Kaveri", "Yamuna")) u.bookRoom(room, MeetingRequest.of("x", Main.mon(8, 0), Main.mon(9, 0)));
        u.bookRoom("Yamuna", MeetingRequest.of("y", Main.mon(10, 0), Main.mon(11, 0)));    // Yamuna is free 9-10 only
        u.bookRoom("Kaveri", MeetingRequest.of("y", Main.mon(12, 0), Main.mon(13, 0)));    // Kaveri is free 9-12
        u.configure(new LeastIdleTime(), new NotInPast(new MaxLength(new AnyTime(), 720)), new InviteAnyway());
        Result tight = u.scheduleMeeting(MeetingRequest.of("z", Main.mon(9, 0), Main.mon(10, 0)).forSeats(6).needing(Feature.VIDEO));
        System.out.println("   09:00-10:00 for 6 with video -> " + tight.booking().roomId()
                           + " (it fills Yamuna's gap exactly; Kaveri would sit idle 10:00-12:00; smallest-fit would have picked Kaveri)");
        now[0] += 8 * 1440;
        System.out.println("   Yamuna's log: " + audit.entries("Yamuna") + "; purged after a week: " + audit.purgeOlderThan(7));

        System.out.println("-- Cleartrip's commands");
        CommandDriver cli = new CommandDriver(LocalDate.of(2026, 9, 28));
        for (String c : List.of("ADD BUILDING b1", "ADD FLOOR b1 7", "ADD CONFROOM b1 7 c1 6", "ADD CONFROOM b1 7 c2 10",
                                "BOOK u1 1:5 b1 7 c1", "BOOK u2 3:4 b1 7 c1", "BOOK u2 3:10 b1 7 c2", "SEARCH 3:10 b1 7",
                                "SUGGEST 3:10", "BOOK u3 1:14 b1 7 c1", "LIST BOOKING b1 7", "CANCEL u1 1:5 b1 7 c1", "SEARCH 2:3 b1 7 8"))
            System.out.println("   > " + c + "\n     " + cli.run(c).replace("\n", "\n     "));

        System.out.println("-- hold, then confirm");
        BookingService hs = Main.office();
        long[] clock = {Main.mon(9, 0)};
        hs.setClock(() -> clock[0]);
        HoldDesk desk = new HoldDesk(hs, () -> clock[0], 10);
        Result held = desk.hold("Ganga", MeetingRequest.of("asha", Main.mon(14, 0), Main.mon(15, 0)));
        System.out.println("   held " + held.booking() + "; someone else meanwhile: " + hs.bookRoom("Ganga", MeetingRequest.of("ravi", Main.mon(14, 0), Main.mon(15, 0))).status());
        clock[0] += 11;
        System.out.println("   confirm after 11 minutes: " + desk.confirm(held.booking().id()) + "; the room is free again: "
                           + hs.bookRoom("Ganga", MeetingRequest.of("ravi", Main.mon(14, 0), Main.mon(15, 0))).ok());

        System.out.println("-- gym classes: capacity 2, a waiting list, tiers");
        ClassDesk gym = new ClassDesk(() -> Main.mon(6, 0));
        gym.addMember("a", Tier.SILVER); gym.addMember("b", Tier.GOLD); gym.addMember("c", Tier.PLATINUM);
        gym.addClass(new ClassSlot("Y7", "Yoga", Main.mon(7, 0, 8, 0), 2));
        System.out.println("   a " + gym.book("a", "Y7") + ", b " + gym.book("b", "Y7") + ", c " + gym.book("c", "Y7") + ", a again " + gym.book("a", "Y7"));
        System.out.println("   b cancels: " + gym.cancel("b", "Y7") + "; seated " + gym.seated("Y7") + ", waiting " + gym.waiting("Y7"));
        gym.addClass(new ClassSlot("H6", "HIIT", Main.mon(6, 30, 7, 15), 10));
        System.out.println("   classes with a free seat, earliest first: " + gym.open(Comparator.comparingLong(c -> c.when.start())));

        System.out.println("-- a 30-minute grid on the wall clock");
        BookingPolicy grid = new SlotGrid(new AnyTime(), 30, Time.OFFICE);
        System.out.println("   10:15-10:45 -> " + grid.whyNot(Main.mon(10, 15, 10, 45), 0) + "; 10:30-11:00 -> "
                           + Objects.requireNonNullElse(grid.whyNot(Main.mon(10, 30, 11, 0), 0), "allowed"));

        System.out.println("-- the time most people can make");
        BookingService ma = Main.office();
        ma.bookRoom("Ganga", MeetingRequest.of("p1", Main.mon(10, 0), Main.mon(12, 0)));
        ma.bookRoom("Kaveri", MeetingRequest.of("p2", Main.mon(10, 0), Main.mon(11, 0)));
        ma.bookRoom("Narmada", MeetingRequest.of("p3", Main.mon(11, 0), Main.mon(13, 0)));
        MostAvailable.Pick pick = MostAvailable.find(ma, List.of("p1", "p2", "p3"), 60, Main.mon(10, 0, 13, 0));
        System.out.println("   " + pick.when() + ": free " + pick.free() + ", busy " + pick.busy());

        System.out.println("-- tennis courts");
        List<CourtBooking> day = List.of(new CourtBooking(1, 9, 11), new CourtBooking(2, 10, 12), new CourtBooking(3, 11, 13), new CourtBooking(4, 12, 14));
        System.out.println("   courts " + CourtPlanner.assignCourts(day, 0, 0, 0) + ", min " + CourtPlanner.minCourts(day)
                           + "; with 1 hour of cleaning " + CourtPlanner.assignCourts(day, 1, 0, 0));

        System.out.println("-- sharing and proposals");
        BookingService sc = Main.office();
        SharedCalendars share = new SharedCalendars(sc);
        Result m = sc.bookRoom("Kaveri", MeetingRequest.of("asha", Main.mon(10, 0), Main.mon(11, 0)).titled("pricing").inviting("ravi"));
        share.share("asha", "meera", Access.VIEW);
        System.out.println("   meera sees " + share.view("meera", "asha", Main.mon(0, 0, 23, 59)) + "; kiran sees " + share.view("kiran", "asha", Main.mon(0, 0, 23, 59)));
        String p = share.propose("ravi", m.booking().id(), Main.mon(15, 0, 16, 0));
        System.out.println("   ravi proposes 15:00; asha accepts: " + share.accept("asha", p).booking());

        System.out.println("-- the repository refuses an overlap itself: fifty servers, one room, one hour");
        InMemoryBookingRepository repo = new InMemoryBookingRepository();
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(50);
        AtomicInteger stored = new AtomicInteger();
        for (int i = 0; i < 50; i++) {
            final int k = i;
            new Thread(() -> {
                try { go.await(); if (repo.insertIfFree(new Booking("R" + k, "Kaveri", Main.mon(10, 0, 11, 0), "p" + k, "", 1, Set.of(), List.of(), null))) stored.incrementAndGet(); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done.countDown(); }
            }).start();
        }
        go.countDown();
        done.await();
        System.out.println("   rows stored: " + stored.get());

        System.out.println("-- a lock per room: forty threads, any room, the same hour; then moves both ways at once");
        PerRoomBooker pr = new PerRoomBooker(List.of(new Room("A", "", 0, 4, Set.of()), new Room("B", "", 0, 8, Set.of()), new Room("C", "", 0, 12, Set.of())));
        List<Booking> got = Collections.synchronizedList(new ArrayList<>());
        CountDownLatch go2 = new CountDownLatch(1), done2 = new CountDownLatch(40);
        for (int i = 0; i < 40; i++) {
            final int k = i;
            new Thread(() -> {
                try { go2.await(); Booking b = pr.bookAny("p" + k, Main.mon(10, 0, 11, 0), 1); if (b != null) got.add(b); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done2.countDown(); }
            }).start();
        }
        go2.countDown();
        done2.await();
        Booking inA = pr.bookRoom("A", "x", Main.mon(12, 0, 13, 0)), inB = pr.bookRoom("B", "y", Main.mon(14, 0, 15, 0));
        Thread t1 = new Thread(() -> { for (int k = 0; k < 2000; k++) pr.move(inA.id(), k % 2 == 0 ? "B" : "A", Main.mon(12, 0, 13, 0)); });
        Thread t2 = new Thread(() -> { for (int k = 0; k < 2000; k++) pr.move(inB.id(), k % 2 == 0 ? "A" : "B", Main.mon(14, 0, 15, 0)); });
        t1.start(); t2.start(); t1.join(); t2.join();
        System.out.println("   booked " + got.size() + " of 40 (three rooms); moves finished, overlapping pairs: " + pr.overlaps());

        System.out.println("-- time zones: a weekly 09:00 in London across 25 Oct 2026");
        long first = TimeZones.at(TimeZones.LONDON, 2026, 10, 19, 9, 0);
        List<Interval> right = new Recurrence(7, LocalDate.of(2026, 11, 9), TimeZones.LONDON).dates(new Interval(first, first + 60));
        List<Interval> naive = TimeZones.naiveWeekly(new Interval(first, first + 60), 4);
        StringBuilder sb = new StringBuilder();
        for (int k = 0; k < 4; k++) sb.append(TimeZones.hm(right.get(k).start(), TimeZones.LONDON)).append(" vs ").append(TimeZones.hm(naive.get(k).start(), TimeZones.LONDON)).append("; ");
        System.out.println("   Recurrence vs +7x1440 minutes: " + sb);

        System.out.println("-- a recurrence from an RRULE");
        Recurrence r = RecurrenceFactory.parse("FREQ=WEEKLY;INTERVAL=2;UNTIL=20261109", Time.OFFICE);
        System.out.println("   every " + r.everyDays() + " days until " + r.until() + ": " + r.dates(Main.mon(16, 0, 17, 0)).size() + " dates");
    }
}
