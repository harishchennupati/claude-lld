import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;

/**
 * Time in this file is a long: whole minutes since 1970-01-01 00:00 UTC. The office's wall clock
 * (Asia/Kolkata) is used only at the edges, to read "Monday 10:00" in and to print it out.
 */
final class Time {
    static final ZoneId OFFICE = ZoneId.of("Asia/Kolkata");
    private Time() {}
    /** The minute of a wall-clock time in the office. */
    static long at(int year, int month, int day, int hour, int minute) {
        return LocalDateTime.of(year, month, day, hour, minute).atZone(OFFICE).toEpochSecond() / 60;
    }
    /** The wall-clock reading of a minute in a zone. */
    static ZonedDateTime local(long minute, ZoneId zone) { return Instant.ofEpochSecond(minute * 60).atZone(zone); }
    /** "10:00", office time. Plain arithmetic on the zone's offset, because refusal messages are built under the lock. */
    static String hm(long minute) {
        long local = minute + OFFICE.getRules().getOffset(Instant.ofEpochSecond(minute * 60)).getTotalSeconds() / 60;
        int h = (int) Math.floorMod(local / 60, 24L), m = (int) Math.floorMod(local, 60L);
        return (h < 10 ? "0" : "") + h + (m < 10 ? ":0" : ":") + m;
    }
    /** "Mon 12 Oct", office time. */
    static String day(long minute) {
        ZonedDateTime z = local(minute, OFFICE);
        return z.getDayOfWeek().toString().substring(0, 1) + z.getDayOfWeek().toString().substring(1, 3).toLowerCase()
               + " " + z.getDayOfMonth() + " " + z.getMonth().toString().substring(0, 1)
               + z.getMonth().toString().substring(1, 3).toLowerCase();
    }
}

/**
 * A stretch of time [start, end): it includes its start minute and stops just before its end minute,
 * so 10:00-11:00 and 11:00-12:00 touch but do not overlap. Immutable; it must end after it starts.
 */
record Interval(long start, long end) {
    Interval {
        if (end <= start) throw new IllegalArgumentException("a meeting must end after it starts");
    }
    /** The whole overlap rule for half-open intervals: each one starts before the other ends. */
    boolean overlaps(Interval o) { return start < o.end && o.start < end; }
    /** Length in minutes. */
    long minutes() { return end - start; }
    /** "10:00-11:00", office time. */
    @Override public String toString() { return Time.hm(start) + "-" + Time.hm(end); }
}

/** Equipment a room can have. A fixed list, so an enum; a meeting asks for a set of these. */
enum Feature { VIDEO, WHITEBOARD, PROJECTOR, PHONE }

/**
 * A room's fixed facts: its id, where it is, how many it seats, what it has. Nothing here changes; the
 * room's bookings live in its RoomTimeline, which the service owns.
 */
record Room(String id, String building, int floor, int capacity, Set<Feature> features) {
    Room {
        if (capacity <= 0) throw new IllegalArgumentException("room " + id + " must seat someone");
        features = Set.copyOf(features);
    }
    /** Seats enough people and has every piece of equipment asked for. */
    boolean fits(int seats, Set<Feature> needs) { return capacity >= seats && features.containsAll(needs); }
}

/**
 * What someone asks for: who organises it, its title, when, how many seats, which equipment, whom to
 * invite. Immutable; each with-method returns a changed copy, so a request reads like a sentence:
 * MeetingRequest.of("asha", ten, eleven).forSeats(6).needing(Feature.VIDEO).inviting("ravi", "meera").
 */
record MeetingRequest(String organizer, String title, Interval when, int seats, Set<Feature> needs, List<String> guests) {
    MeetingRequest {
        if (seats <= 0) throw new IllegalArgumentException("a meeting needs at least one seat");
        needs = Set.copyOf(needs);
        guests = List.copyOf(new LinkedHashSet<>(guests));              // each guest once, in the order given
        if (guests.contains(organizer)) throw new IllegalArgumentException(organizer + " organises; not also a guest");
    }
    /** One seat, called "meeting", no equipment, no guests: the with-methods add the rest. */
    static MeetingRequest of(String organizer, long start, long end) {
        return new MeetingRequest(organizer, "meeting", new Interval(start, end), 1, Set.of(), List.of());
    }
    /** The same request with a title. */
    MeetingRequest titled(String t) { return new MeetingRequest(organizer, t, when, seats, needs, guests); }
    /** The same request needing n seats. */
    MeetingRequest forSeats(int n) { return new MeetingRequest(organizer, title, when, n, needs, guests); }
    /** The same request needing this equipment. */
    MeetingRequest needing(Feature... f) { return new MeetingRequest(organizer, title, when, seats, Set.of(f), guests); }
    /** Invite people; the seats grow to at least everyone invited plus the organiser. */
    MeetingRequest inviting(String... names) {
        Set<String> g = new LinkedHashSet<>(guests);
        g.addAll(List.of(names));
        return new MeetingRequest(organizer, title, when, Math.max(seats, g.size() + 1), needs, new ArrayList<>(g));
    }
}

/**
 * One confirmed meeting in one room. Immutable: moving it makes a new Booking with the same id, swapped
 * in under the lock, so whoever holds an old copy holds a consistent picture, never a half-changed one.
 */
record Booking(String id, String roomId, Interval when, String organizer, String title, int seats,
               Set<Feature> needs, List<String> guests, String seriesId) {
    Booking {
        needs = Set.copyOf(needs);                        // immutable copies, so a Booking is safe on any thread
        guests = List.copyOf(guests);
    }
    /** Calendars list meetings by start, then by id. */
    static final Comparator<Booking> BY_START =
        Comparator.comparingLong((Booking b) -> b.when().start()).thenComparing(Booking::id);
    /** The organiser first, then the guests: everyone whose calendar shows this meeting. */
    List<String> everyone() {
        List<String> all = new ArrayList<>();
        all.add(organizer);
        all.addAll(guests);
        return all;
    }
    /** The same meeting at another time, perhaps in another room. */
    Booking movedTo(String room, Interval w) {
        return new Booking(id, room, w, organizer, title, seats, needs, guests, seriesId);
    }
    /** "B1 Kaveri 10:00-11:00". */
    @Override public String toString() { return id + " " + roomId + " " + when; }
}

/** A guest's answer. It starts as NEEDS_ACTION, may change any time, and goes back to NEEDS_ACTION when the meeting moves. */
enum Rsvp { NEEDS_ACTION, ACCEPTED, TENTATIVE, DECLINED }

/** How a request ended. A refusal is a normal answer and is returned; bad input (an unknown room) throws. */
enum Status { BOOKED, MOVED, ROOM_TAKEN, NO_ROOM_FITS, RULE_BROKEN, GUEST_BUSY }

/**
 * The answer to a booking or a move: the status; the booking as it now stands (the new one, or after a
 * refused move the old one, untouched); why not; and who already had a meeting at that time.
 */
record Result(Status status, Booking booking, String reason, List<String> busy) {
    /** True when something was written. */
    boolean ok() { return status == Status.BOOKED || status == Status.MOVED; }
}

/** A series: every date booked and the series id, or nothing booked and the dates that clash. */
record SeriesResult(String seriesId, List<Booking> booked, List<Interval> clashes, String reason) {
    /** True when every date was booked. */
    boolean ok() { return seriesId != null; }
}

/** A time and a room that is free then: what the slot finder returns. */
record Slot(Interval when, String roomId) {}

/**
 * How a meeting repeats: every `everyDays` days (1 = daily, 7 = weekly) up to and including the date
 * `until`, at the same wall-clock time in `zone`. At most 400 dates, so one series never holds the lock long.
 */
record Recurrence(int everyDays, LocalDate until, ZoneId zone) {
    static final int MAX_DATES = 400;
    Recurrence {
        if (everyDays <= 0) throw new IllegalArgumentException("repeat every 1 day or more");
    }
    /** Weekly in the office's zone. */
    static Recurrence weekly(LocalDate until) { return new Recurrence(7, until, Time.OFFICE); }
    /** Daily in the office's zone. */
    static Recurrence daily(LocalDate until) { return new Recurrence(1, until, Time.OFFICE); }
    /**
     * Every date of the series, the first included. Pure: it touches nothing. Each date is counted in days
     * from the FIRST one, in the series' zone, so 09:00 stays 09:00 across a daylight-saving change.
     */
    List<Interval> dates(Interval first) {
        ZonedDateTime start = Time.local(first.start(), zone);
        if (until.isBefore(start.toLocalDate())) throw new IllegalArgumentException("the series ends before it starts");
        List<Interval> out = new ArrayList<>();
        for (long k = 0; ; k++) {
            ZonedDateTime d = start.plusDays(k * everyDays);
            if (d.toLocalDate().isAfter(until)) break;
            if (out.size() == MAX_DATES) throw new IllegalArgumentException("more than " + MAX_DATES + " dates");
            long s = d.toEpochSecond() / 60;
            if (!out.isEmpty() && out.get(out.size() - 1).end() > s) throw new IllegalArgumentException("each meeting runs into the next");
            out.add(new Interval(s, s + first.minutes()));
        }
        return out;
    }
}

/**
 * One room's bookings, by start minute. The invariant it keeps: no two of them overlap. It is only used
 * under the service's lock; a chooser may read it, never change it.
 */
final class RoomTimeline {
    final Room room;
    private final TreeMap<Long, Booking> byStart = new TreeMap<>();

    RoomTimeline(Room room) { this.room = room; }

    /**
     * Is [start, end) free here? Two lookups, O(log n). Because this room's bookings never overlap, only
     * the last one starting at or before our start can run into us from the left, and only the first one
     * starting after our start can run into us from the right. ignoreId lets a meeting move over its own
     * old time.
     */
    boolean isFree(Interval w, String ignoreId) {
        Map.Entry<Long, Booking> before = byStart.floorEntry(w.start());
        if (before != null && !before.getValue().id().equals(ignoreId) && before.getValue().when().end() > w.start()) return false;
        Map.Entry<Long, Booking> after = byStart.higherEntry(w.start());
        if (after != null && after.getValue().id().equals(ignoreId)) after = byStart.higherEntry(after.getKey());
        return after == null || after.getKey() >= w.end();
    }
    /** Put a booking in. The caller proved the time free under the same lock; the check here is a guard against a bug. */
    void add(Booking b) {
        if (!isFree(b.when(), null)) throw new IllegalStateException("overlap in " + room.id() + ": " + b);
        byStart.put(b.when().start(), b);
    }
    /** Take a booking out, only if it is the one stored at its start. */
    void remove(Booking b) { byStart.remove(b.when().start(), b); }
    /** The bookings that overlap a window, in order: the room's day. O(log n + k). */
    List<Booking> between(Interval w) {
        Long from = byStart.floorKey(w.start());
        List<Booking> out = new ArrayList<>();
        for (Booking b : byStart.subMap(from == null ? w.start() : from, true, w.end(), false).values())
            if (b.when().end() > w.start()) out.add(b);
        return out;
    }
    /**
     * The first minute t >= from such that [t, t + minutes) is free here and ends by `until`, or -1.
     * Walks the gaps between bookings from `from` on: O(log n + bookings passed).
     */
    long firstOpening(long from, long minutes, long until) {
        long t = from;
        Map.Entry<Long, Booking> before = byStart.floorEntry(from);
        if (before != null) t = Math.max(t, before.getValue().when().end());
        for (Booking b : byStart.tailMap(from, false).values()) {
            if (b.when().start() - t >= minutes || b.when().start() >= until) break;   // this gap is long enough, or we are past the window
            t = b.when().end();
        }
        return t + minutes <= until ? t : -1;
    }
    /** The last booking starting before minute t, or null: the left neighbour of a free slot. */
    Booking before(long t) { Map.Entry<Long, Booking> e = byStart.lowerEntry(t); return e == null ? null : e.getValue(); }
    /** The first booking starting at or after minute t, or null: the right neighbour of a free slot. */
    Booking after(long t) { Map.Entry<Long, Booking> e = byStart.ceilingEntry(t); return e == null ? null : e.getValue(); }
    /** Every booking in order, a copy: for the race test's audit. */
    List<Booking> all() { return new ArrayList<>(byStart.values()); }
}

/**
 * One person's meetings, by start then id, so "my week" is a range query. Unlike a room, a person may be
 * double-booked (when the conflict rule allows it), so a window query cannot stop at one neighbour: it
 * starts `longest` minutes early, because nothing that starts earlier can still be running.
 */
final class PersonCalendar {
    private final TreeSet<Booking> meetings = new TreeSet<>(Booking.BY_START);
    private long longest = 1;                                  // the longest meeting ever added, in minutes

    /** Add a meeting. */
    void add(Booking b) { meetings.add(b); longest = Math.max(longest, b.when().minutes()); }
    /** Remove a meeting (the version stored, same start and id). */
    void remove(Booking b) { meetings.remove(b); }
    /** Is this exact meeting here? For the audit. */
    boolean contains(Booking b) { return meetings.contains(b); }
    /** Meetings overlapping a window, in order. O(log n + k): only those starting in [start - longest, end) can. */
    List<Booking> overlapping(Interval w) {
        List<Booking> out = new ArrayList<>();
        for (Booking b : meetings.subSet(probe(w.start() - longest), true, probe(w.end()), false))
            if (b.when().overlaps(w)) out.add(b);
        return out;
    }
    /** A stand-in Booking used only as a search key: it sorts before every real meeting that starts at `start`. */
    private static Booking probe(long start) {
        return new Booking("", "", new Interval(start, start + 1), "", "", 1, Set.of(), List.of(), null);
    }
}

/** Where "now" comes from, in minutes. Handed in, so a test can say "Monday 08:30" and mean it. */
interface Clock { long nowMinutes(); }

/**
 * Which of the free rooms that fit gets the meeting: a rule that changes by company (smallest that fits,
 * lowest id, least idle time left over). The list is never empty; the chooser reads it and returns one.
 */
interface RoomChooser { RoomTimeline choose(List<RoomTimeline> freeAndFitting, Interval when); }

/** The smallest room that fits, then the lowest id: big rooms stay free for big meetings. The default. */
final class SmallestFit implements RoomChooser {
    /** Fewest seats first, then id. */
    public RoomTimeline choose(List<RoomTimeline> free, Interval when) {
        return Collections.min(free, Comparator.comparingInt((RoomTimeline t) -> t.room.capacity()).thenComparing(t -> t.room.id()));
    }
}

/** The lowest room id, whatever its size: the rule in the "lexicographically smallest room" versions. */
final class LowestId implements RoomChooser {
    /** Smallest id. */
    public RoomTimeline choose(List<RoomTimeline> free, Interval when) {
        return Collections.min(free, Comparator.comparing((RoomTimeline t) -> t.room.id()));
    }
}

/**
 * A rule about WHEN a meeting may happen: the longest meeting, office hours, nothing in the past. It
 * returns why not, or null when the time is allowed. Rules wrap each other, so a new rule edits no old one.
 */
interface BookingPolicy { String whyNot(Interval when, long now); }

/** Allows every time: the innermost rule, which the others wrap. */
final class AnyTime implements BookingPolicy {
    /** Always allowed. */
    public String whyNot(Interval when, long now) { return null; }
}

/** No meeting longer than a cap (12 hours in Cleartrip's version). Wraps the rule before it. */
final class MaxLength implements BookingPolicy {
    private final BookingPolicy base;
    private final long maxMinutes;
    MaxLength(BookingPolicy base, long maxMinutes) { this.base = base; this.maxMinutes = maxMinutes; }
    /** The wrapped rule first, then the length. */
    public String whyNot(Interval w, long now) {
        String why = base.whyNot(w, now);
        if (why != null) return why;
        return w.minutes() > maxMinutes ? "longer than " + maxMinutes / 60 + " hours" : null;
    }
}

/** No meeting may start before now. Wraps the rule before it. */
final class NotInPast implements BookingPolicy {
    private final BookingPolicy base;
    NotInPast(BookingPolicy base) { this.base = base; }
    /** The wrapped rule first, then the start against the clock. */
    public String whyNot(Interval w, long now) {
        String why = base.whyNot(w, now);
        if (why != null) return why;
        return w.start() < now ? "starts in the past" : null;
    }
}

/** Only inside office hours, on one day, in a zone: for example 08:00 to 20:00. Wraps the rule before it. */
final class OfficeHours implements BookingPolicy {
    private final BookingPolicy base;
    private final int openHour, closeHour;
    private final ZoneId zone;
    OfficeHours(BookingPolicy base, int openHour, int closeHour, ZoneId zone) {
        this.base = base; this.openHour = openHour; this.closeHour = closeHour; this.zone = zone;
    }
    /** The wrapped rule first, then: starts at or after opening, ends by closing, same day. */
    public String whyNot(Interval w, long now) {
        String why = base.whyNot(w, now);
        if (why != null) return why;
        ZonedDateTime s = Time.local(w.start(), zone), e = Time.local(w.end(), zone);
        boolean inside = s.toLocalDate().equals(e.toLocalDate()) && s.getHour() >= openHour
                         && e.getHour() * 60 + e.getMinute() <= closeHour * 60;
        return inside ? null : "outside office hours " + openHour + ":00-" + closeHour + ":00";
    }
}

/**
 * What to do when some of the people are already in another meeting at that time. Rooms never double-book;
 * people may, depending on the company: a calendar like Google's invites anyway, a stricter one refuses.
 */
interface ConflictPolicy { boolean refuse(List<String> busyPeople); }

/** Book anyway and report who has a clash. The default: people can be double-booked, rooms cannot. */
final class InviteAnyway implements ConflictPolicy {
    /** Never refuses. */
    public boolean refuse(List<String> busy) { return false; }
}

/** Refuse when anyone is busy: nobody is ever in two meetings at once. */
final class RefuseIfBusy implements ConflictPolicy {
    /** Refuses when the list is not empty. */
    public boolean refuse(List<String> busy) { return !busy.isEmpty(); }
}

/** What happened to a meeting. */
enum Change { BOOKED, MOVED, CANCELLED, ANSWERED }

/** One change, as a snapshot taken inside the lock: the meeting now, the meeting before (a move), who answered and how. */
record CalendarEvent(Change kind, Booking booking, Booking before, String person, Rsvp answer) {}

/**
 * Anyone who wants to hear: invitations by mail, a screen on the room's door, an audit log. Called after
 * the lock is released, on the caller's thread, so two calls can overlap: a listener keeps itself thread-safe.
 */
interface CalendarListener { void onEvent(CalendarEvent e); }

/**
 * The mail robot: an invitation to every guest, a note when a meeting moves or is cancelled, a note to the
 * organiser when a guest answers. It prints here and keeps what it sent, for tests.
 */
final class Mailer implements CalendarListener {
    final List<String> sent = Collections.synchronizedList(new ArrayList<>());   // two bookings can report at once

    /** Write the mail for one change. */
    public void onEvent(CalendarEvent e) {
        Booking b = e.booking();
        String line = switch (e.kind()) {
            case BOOKED    -> "to " + b.guests() + ": " + b.organizer() + " invites you to " + b.title() + ", " + b.roomId() + " " + Time.day(b.when().start()) + " " + b.when();
            case MOVED     -> "to " + b.guests() + ": " + b.title() + " moved from " + e.before().roomId() + " " + e.before().when() + " to " + b.roomId() + " " + b.when() + "; please answer again";
            case CANCELLED -> "to " + b.guests() + ": " + b.title() + " " + Time.day(b.when().start()) + " " + b.when() + " is cancelled";
            case ANSWERED  -> "to " + b.organizer() + ": " + e.person() + " " + e.answer() + " " + b.title();
        };
        if (e.kind() == Change.ANSWERED || !b.guests().isEmpty()) {
            sent.add(line);
            System.out.println("   [mail] " + line);
        }
    }
}

/**
 * The aggregate root: the only owner of every room's timeline, every person's calendar, the bookings by id
 * and the guests' answers, and the only holder of the lock that guards them. Each public method is one
 * critical section, and the listeners hear about it only after the lock is released.
 */
final class BookingService {
    private final ReentrantLock lock = new ReentrantLock();
    private final Map<String, RoomTimeline> rooms = new TreeMap<>();              // by room id, in id order
    private final Map<String, Booking> byId = new HashMap<>();                     // every live meeting
    private final Map<String, PersonCalendar> calendars = new HashMap<>();         // by person
    private final Map<String, Map<String, Rsvp>> answers = new HashMap<>();        // meeting id -> guest -> answer
    private final Map<String, Set<String>> series = new HashMap<>();               // series id -> its meeting ids
    private final List<CalendarListener> listeners = new CopyOnWriteArrayList<>();
    private long nextMeeting = 0, nextSeries = 0;                                  // ids, only written under the lock
    private RoomChooser chooser = new SmallestFit();
    private BookingPolicy policy = new NotInPast(new MaxLength(new AnyTime(), 12 * 60));
    private ConflictPolicy conflicts = new InviteAnyway();
    private Clock clock = () -> System.currentTimeMillis() / 60_000;

    /**
     * Hand in the rules. The service never builds one itself, so a new rule is a new file and this one
     * line. Under the lock, so a rule switched on a running service is seen whole.
     */
    void configure(RoomChooser c, BookingPolicy p, ConflictPolicy cp) {
        lock.lock();
        try { chooser = c; policy = p; conflicts = cp; } finally { lock.unlock(); }
    }
    /** Tests and replays hand in their own clock. */
    void setClock(Clock c) { lock.lock(); try { clock = c; } finally { lock.unlock(); } }
    /** Subscribe a mailer, a door screen, an audit log. */
    void addListener(CalendarListener l) { listeners.add(l); }
    /** Add a room; a second room with the same id is refused. */
    void addRoom(Room r) {
        lock.lock();
        try {
            if (rooms.containsKey(r.id())) throw new IllegalArgumentException("room " + r.id() + " exists");
            rooms.put(r.id(), new RoomTimeline(r));
        } finally { lock.unlock(); }
    }

    // ---------------- booking ----------------

    /** Book any room that fits and is free; the chooser picks which. */
    Result scheduleMeeting(MeetingRequest r) { return book(null, r); }
    /** Book this room, or nothing. */
    Result bookRoom(String roomId, MeetingRequest r) { return book(roomId, r); }

    /** Take the lock, run the booking (bookLocked, just below), and tell the listeners only after the unlock. */
    private Result book(String roomId, MeetingRequest r) {
        List<CalendarEvent> events = new ArrayList<>();
        Result out;
        lock.lock();
        try { out = bookLocked(roomId, r, events); } finally { lock.unlock(); }
        publish(events);                                                           // the mailer hears AFTER the lock
        return out;
    }

    /**
     * THE critical step; the caller holds the lock. In this order: the time rules; a room (the named one if
     * it fits and is free, or every free room that fits and the chooser picks one); the people, by the
     * conflict rule; and only then the writes into every index, none of which can fail. A refusal at any
     * step has written nothing.
     */
    private Result bookLocked(String roomId, MeetingRequest r, List<CalendarEvent> events) {
        String why = policy.whyNot(r.when(), clock.nowMinutes());
        if (why != null) return refused(Status.RULE_BROKEN, null, why);
        RoomTimeline pick;
        if (roomId != null) {
            RoomTimeline t = timeline(roomId);
            if (!t.room.fits(r.seats(), r.needs()))
                return refused(Status.NO_ROOM_FITS, null, roomId + " seats " + t.room.capacity() + " and has " + t.room.features());
            if (!t.isFree(r.when(), null)) return refused(Status.ROOM_TAKEN, null, roomId + " is taken " + r.when());
            pick = t;
        } else {
            List<RoomTimeline> free = freeRooms(r.when(), r.seats(), r.needs(), null);
            if (free.isEmpty()) return refused(Status.NO_ROOM_FITS, null, "no free room seats " + r.seats() + " with " + r.needs() + " at " + r.when());
            pick = chosen(free, r.when());
        }
        List<String> everyone = new ArrayList<>(List.of(r.organizer()));
        everyone.addAll(r.guests());
        List<String> busy = busyPeople(everyone, r.when(), null);
        if (conflicts.refuse(busy)) return new Result(Status.GUEST_BUSY, null, busy + " already in a meeting", busy);
        Booking b = new Booking("B" + (++nextMeeting), pick.room.id(), r.when(), r.organizer(), r.title(),
                                r.seats(), r.needs(), r.guests(), null);            // from here down: writes that cannot fail
        insert(b);
        events.add(new CalendarEvent(Change.BOOKED, b, null, null, null));
        return new Result(Status.BOOKED, b, null, busy);
    }

    /** Cancel one meeting: out of its room, out of every calendar, answers dropped. False when there is no such meeting. */
    boolean cancelBooking(String meetingId) {
        Booking b;
        lock.lock();
        try {
            b = byId.get(meetingId);
            if (b == null) return false;                                           // never booked, or cancelled already
            erase(b);
            answers.remove(b.id());
            if (b.seriesId() != null) {
                Set<String> s = series.get(b.seriesId());
                s.remove(b.id());
                if (s.isEmpty()) series.remove(b.seriesId());
            }
        } finally { lock.unlock(); }
        publish(List.of(new CalendarEvent(Change.CANCELLED, b, null, null, null)));
        return true;
    }

    /**
     * Move a meeting to a new time: the same room if it is free then (the meeting's own old time does not
     * count), else the chooser picks another room that fits. In this order: the rules, a room, the people;
     * only then the swap, and every guest is asked again. A refusal leaves the meeting exactly where it was.
     */
    Result reschedule(String meetingId, Interval to) {
        List<CalendarEvent> events = new ArrayList<>();
        Result out;
        lock.lock();
        try {
            Booking old = byId.get(meetingId);
            if (old == null) throw new NoSuchElementException("no meeting " + meetingId);
            if (to.equals(old.when())) return new Result(Status.MOVED, old, null, List.of());   // already there: nobody is asked again
            String why = policy.whyNot(to, clock.nowMinutes());
            if (why != null) return refused(Status.RULE_BROKEN, old, why);
            RoomTimeline target = rooms.get(old.roomId());
            if (!target.isFree(to, old.id())) {
                List<RoomTimeline> free = freeRooms(to, old.seats(), old.needs(), old.id());
                if (free.isEmpty()) return refused(Status.NO_ROOM_FITS, old, "no room free " + to + "; " + old + " stays");
                target = chosen(free, to);
            }
            List<String> busy = busyPeople(old.everyone(), to, old.id());
            if (conflicts.refuse(busy)) return new Result(Status.GUEST_BUSY, old, busy + " already in a meeting", busy);
            Booking moved = old.movedTo(target.room.id(), to);                     // proven: now the swap, writes only
            erase(old);
            insert(moved);                                                         // answers start again at NEEDS_ACTION
            events.add(new CalendarEvent(Change.MOVED, moved, old, null, null));
            out = new Result(Status.MOVED, moved, null, busy);
        } finally { lock.unlock(); }
        publish(events);
        return out;
    }

    /**
     * Book one room on every date of a series, all or nothing. Every date is checked first (the rules, the
     * room, the people); if any fails, nothing is written and the failing dates come back. Only when all
     * are proven is every date written, inside the same lock.
     */
    SeriesResult bookRecurring(String roomId, MeetingRequest first, Recurrence rule) {
        List<Interval> dates = rule.dates(first.when());                          // pure: worked out before the lock
        List<CalendarEvent> events = new ArrayList<>();
        SeriesResult out;
        lock.lock();
        try {
            RoomTimeline t = timeline(roomId);
            if (!t.room.fits(first.seats(), first.needs()))
                return new SeriesResult(null, List.of(), dates, roomId + " does not fit this meeting");
            List<String> everyone = new ArrayList<>(List.of(first.organizer()));
            everyone.addAll(first.guests());
            long now = clock.nowMinutes();
            List<Interval> clashes = new ArrayList<>();
            for (Interval d : dates)
                if (policy.whyNot(d, now) != null || !t.isFree(d, null) || conflicts.refuse(busyPeople(everyone, d, null)))
                    clashes.add(d);
            if (!clashes.isEmpty()) return new SeriesResult(null, List.of(), clashes, clashes.size() + " of " + dates.size() + " dates clash");
            String sid = "S" + (++nextSeries);
            List<Booking> made = new ArrayList<>();
            Set<String> ids = new LinkedHashSet<>();
            for (Interval d : dates) {                                             // every date proven: write them all
                Booking b = new Booking("B" + (++nextMeeting), roomId, d, first.organizer(), first.title(),
                                        first.seats(), first.needs(), first.guests(), sid);
                insert(b);
                made.add(b);
                ids.add(b.id());
                events.add(new CalendarEvent(Change.BOOKED, b, null, null, null));
            }
            series.put(sid, ids);
            out = new SeriesResult(sid, made, List.of(), null);
        } finally { lock.unlock(); }
        publish(events);
        return out;
    }

    /** Cancel every remaining date of a series in one step. Returns how many were cancelled. */
    int cancelSeries(String seriesId) {
        List<CalendarEvent> events = new ArrayList<>();
        lock.lock();
        try {
            Set<String> ids = series.remove(seriesId);
            if (ids == null) return 0;
            for (String id : ids) {
                Booking b = byId.get(id);
                erase(b);
                answers.remove(id);
                events.add(new CalendarEvent(Change.CANCELLED, b, null, null, null));
            }
        } finally { lock.unlock(); }
        publish(events);
        return events.size();
    }

    /** A guest answers. The organiser is told after the unlock. Throws when this person was not invited. */
    void respond(String meetingId, String guest, Rsvp answer) {
        if (answer == Rsvp.NEEDS_ACTION) throw new IllegalArgumentException("NEEDS_ACTION is not an answer");
        CalendarEvent e;
        lock.lock();
        try {
            Booking b = byId.get(meetingId);
            if (b == null) throw new NoSuchElementException("no meeting " + meetingId);
            Map<String, Rsvp> a = answers.get(meetingId);
            if (!a.containsKey(guest)) throw new IllegalArgumentException(guest + " is not invited to " + meetingId);
            a.put(guest, answer);
            e = new CalendarEvent(Change.ANSWERED, b, null, guest, answer);
        } finally { lock.unlock(); }
        publish(List.of(e));
    }

    // ---------------- the reads (each under the lock, so none sees a half-done change) ----------------

    /** A meeting by id, or null. */
    Booking get(String meetingId) { lock.lock(); try { return byId.get(meetingId); } finally { lock.unlock(); } }
    /** A person's answer; the organiser always counts as ACCEPTED. */
    Rsvp answerOf(String meetingId, String person) {
        lock.lock();
        try {
            Booking b = byId.get(meetingId);
            if (b == null) throw new NoSuchElementException("no meeting " + meetingId);
            return answerLocked(b, person);
        } finally { lock.unlock(); }
    }
    /** The rooms that seat `seats`, have `needs` and are free for all of w, in id order. O(R log n) for R rooms. */
    List<Room> getAvailableRooms(Interval w, int seats, Set<Feature> needs) {
        lock.lock();
        try {
            List<Room> out = new ArrayList<>();
            for (RoomTimeline t : freeRooms(w, seats, needs, null)) out.add(t.room);
            return out;
        } finally { lock.unlock(); }
    }
    /** A room's meetings overlapping a window (its day on the door screen), in order. O(log n + k). */
    List<Booking> listBookingsForRoom(String roomId, Interval window) {
        lock.lock();
        try { return timeline(roomId).between(window); } finally { lock.unlock(); }
    }
    /** A person's meetings overlapping a window, organised or invited, in order. O(log n + k). */
    List<Booking> listBookingsForEmployee(String person, Interval window) {
        lock.lock();
        try {
            PersonCalendar c = calendars.get(person);
            return c == null ? List.of() : c.overlapping(window);
        } finally { lock.unlock(); }
    }

    /** A person's busy times in a window: their meetings minus the ones they declined, read in one step. */
    List<Interval> busyTimes(String person, Interval window) {
        lock.lock();
        try { return busyLocked(person, window); } finally { lock.unlock(); }
    }

    /**
     * The first `minutes`-long slot inside `window` when every one of `who` is free (a declined meeting
     * does not count) and some room fits: merge everyone's busy time into blocks, walk the gaps between
     * the blocks, and in each gap long enough ask every fitting room for its first opening. When several
     * rooms open at that same minute, the chooser picks.
     */
    Optional<Slot> findFirstSlot(List<String> who, long minutes, Interval window, int seats, Set<Feature> needs) {
        if (minutes <= 0) throw new IllegalArgumentException("a slot lasts at least a minute");
        lock.lock();
        try {
            List<Interval> busy = new ArrayList<>();
            for (String p : who) busy.addAll(busyLocked(p, window));
            List<Interval> walls = merge(busy);
            walls.add(new Interval(window.end(), window.end() + 1));              // a last wall where the window ends
            long t = window.start();
            for (Interval wall : walls) {
                long gapEnd = Math.min(wall.start(), window.end());
                if (gapEnd - t >= minutes) {
                    long best = -1;
                    List<RoomTimeline> openAtBest = new ArrayList<>();
                    for (RoomTimeline room : rooms.values()) {
                        if (!room.room.fits(seats, needs)) continue;
                        long open = room.firstOpening(t, minutes, gapEnd);
                        if (open < 0) continue;
                        if (best < 0 || open < best) { best = open; openAtBest.clear(); }
                        if (open == best) openAtBest.add(room);
                    }
                    if (best >= 0) {
                        Interval slot = new Interval(best, best + minutes);
                        return Optional.of(new Slot(slot, chosen(openAtBest, slot).room.id()));
                    }
                }
                t = Math.max(t, wall.end());
            }
            return Optional.empty();
        } finally { lock.unlock(); }
    }

    /** Sort by start and fuse overlapping or touching intervals: [9:00,10:00) [9:30,11:00) [11:00,12:00) become [9:00,12:00). */
    static List<Interval> merge(List<Interval> in) {
        List<Interval> sorted = new ArrayList<>(in);
        sorted.sort(Comparator.comparingLong(Interval::start));
        List<Interval> out = new ArrayList<>();
        for (Interval i : sorted) {
            if (!out.isEmpty() && i.start() <= out.get(out.size() - 1).end()) {
                Interval last = out.remove(out.size() - 1);
                out.add(new Interval(last.start(), Math.max(last.end(), i.end())));
            } else out.add(i);
        }
        return out;
    }

    /**
     * A self-check for the race test: no two meetings overlap in any room, and every index agrees with the
     * meetings by id. Returns the problems found; empty means consistent.
     */
    List<String> audit() {
        lock.lock();
        try {
            List<String> bad = new ArrayList<>();
            int inRooms = 0;
            for (RoomTimeline t : rooms.values()) {
                List<Booking> all = t.all();
                inRooms += all.size();
                for (int i = 0; i < all.size(); i++) {
                    if (byId.get(all.get(i).id()) != all.get(i)) bad.add(all.get(i) + " in " + t.room.id() + " is not the live copy");
                    if (i > 0 && all.get(i - 1).when().overlaps(all.get(i).when())) bad.add("overlap in " + t.room.id() + ": " + all.get(i - 1) + " / " + all.get(i));
                }
            }
            if (inRooms != byId.size()) bad.add(inRooms + " meetings in rooms, " + byId.size() + " by id");
            for (Booking b : byId.values())
                for (String p : b.everyone())
                    if (!calendars.get(p).contains(b)) bad.add(b.id() + " missing from " + p + "'s calendar");
            return bad;
        } finally { lock.unlock(); }
    }
    /** How many meetings are booked. */
    int size() { lock.lock(); try { return byId.size(); } finally { lock.unlock(); } }

    // ---------------- the private helpers (all called under the lock) ----------------

    /** The timeline of a room, or an exception naming the unknown id. */
    private RoomTimeline timeline(String roomId) {
        RoomTimeline t = rooms.get(roomId);
        if (t == null) throw new NoSuchElementException("no room " + roomId);
        return t;
    }
    /** Every room that fits and is free for w, in id order: R rooms, two lookups each. */
    private List<RoomTimeline> freeRooms(Interval w, int seats, Set<Feature> needs, String ignoreId) {
        List<RoomTimeline> out = new ArrayList<>();
        for (RoomTimeline t : rooms.values()) if (t.room.fits(seats, needs) && t.isFree(w, ignoreId)) out.add(t);
        return out;
    }
    /** Ask the chooser, and refuse an answer that was not one of the rooms offered. */
    private RoomTimeline chosen(List<RoomTimeline> free, Interval w) {
        RoomTimeline t = chooser.choose(free, w);
        if (!free.contains(t)) throw new IllegalStateException("the chooser returned a room that was not offered");
        return t;
    }
    /** Everyone among `who` with another meeting overlapping w. A declined meeting and the meeting being moved do not count. */
    private List<String> busyPeople(List<String> who, Interval w, String ignoreId) {
        List<String> busy = new ArrayList<>();
        for (String p : who) {
            PersonCalendar c = calendars.get(p);
            if (c == null) continue;
            for (Booking b : c.overlapping(w))
                if (!b.id().equals(ignoreId) && answerLocked(b, p) != Rsvp.DECLINED) { busy.add(p); break; }
        }
        return busy;
    }
    /** The times a person is taken inside a window; a meeting they declined does not count. */
    private List<Interval> busyLocked(String person, Interval window) {
        List<Interval> out = new ArrayList<>();
        PersonCalendar c = calendars.get(person);
        if (c != null)
            for (Booking b : c.overlapping(window)) if (answerLocked(b, person) != Rsvp.DECLINED) out.add(b.when());
        return out;
    }
    /** The organiser counts as ACCEPTED; a guest has whatever they last answered. */
    private Rsvp answerLocked(Booking b, String person) {
        if (b.organizer().equals(person)) return Rsvp.ACCEPTED;
        return answers.get(b.id()).getOrDefault(person, Rsvp.NEEDS_ACTION);
    }
    /** Write one meeting into every index: the room, the id map, each calendar, the answers. Only puts. */
    private void insert(Booking b) {
        rooms.get(b.roomId()).add(b);
        byId.put(b.id(), b);
        for (String p : b.everyone()) calendars.computeIfAbsent(p, k -> new PersonCalendar()).add(b);
        Map<String, Rsvp> a = new HashMap<>();
        for (String g : b.guests()) a.put(g, Rsvp.NEEDS_ACTION);
        answers.put(b.id(), a);
    }
    /** Remove one meeting from the room, the id map and each calendar (the answers are the caller's business). */
    private void erase(Booking b) {
        rooms.get(b.roomId()).remove(b);
        byId.remove(b.id());
        for (String p : b.everyone()) calendars.get(p).remove(b);
    }
    /** A refusal: nothing written; the meeting as it still stands (or null). */
    private static Result refused(Status s, Booking kept, String why) { return new Result(s, kept, why, List.of()); }
    /** Tell every listener, outside the lock, catching anything one throws. */
    private void publish(List<CalendarEvent> events) {
        for (CalendarEvent e : events)
            for (CalendarListener l : listeners) {
                try { l.onEvent(e); } catch (RuntimeException ex) { System.err.println("[listener failed] " + ex.getMessage()); }
            }
    }
}

/** Runs the morning the page describes, then two many-thread races that check the room invariant. */
public class Main {
    /** A minute on Monday 28 September 2026, office time. */
    static long mon(int h, int m) { return Time.at(2026, 9, 28, h, m); }
    /** A stretch of Monday. */
    static Interval mon(int h1, int m1, int h2, int m2) { return new Interval(mon(h1, m1), mon(h2, m2)); }

    /** The office the page describes: four rooms on two floors, and a clock that says Monday 08:30. */
    static BookingService office() {
        BookingService s = new BookingService();
        s.setClock(() -> mon(8, 30));
        s.addRoom(new Room("Ganga",   "B1", 1, 4,  Set.of(Feature.VIDEO)));
        s.addRoom(new Room("Kaveri",  "B1", 1, 8,  Set.of(Feature.VIDEO, Feature.WHITEBOARD)));
        s.addRoom(new Room("Narmada", "B1", 2, 8,  Set.of(Feature.WHITEBOARD)));
        s.addRoom(new Room("Yamuna",  "B1", 2, 12, Set.of(Feature.VIDEO, Feature.PROJECTOR)));
        return s;
    }

    public static void main(String[] args) throws Exception {
        BookingService s = office();
        s.addListener(new Mailer());

        System.out.println("-- 09:00 Asha: any room for 6 with video, 10:00-11:00");
        Result r1 = s.scheduleMeeting(MeetingRequest.of("asha", mon(10, 0), mon(11, 0)).titled("design review")
                                          .forSeats(6).needing(Feature.VIDEO).inviting("ravi", "meera"));
        System.out.println("   " + r1.status() + " " + r1.booking() + "  (Ganga seats 4, Narmada has no video, Kaveri 8 < Yamuna 12)");

        System.out.println("-- 09:05 Ravi: Kaveri, 10:30-11:30");
        Result r2 = s.bookRoom("Kaveri", MeetingRequest.of("ravi", mon(10, 30), mon(11, 30)));
        System.out.println("   " + r2.status() + ": " + r2.reason());

        System.out.println("-- 09:10 Meera: Kaveri, 11:00-12:00, straight after B1");
        Result r3 = s.bookRoom("Kaveri", MeetingRequest.of("meera", mon(11, 0), mon(12, 0)).titled("1:1"));
        System.out.println("   " + r3.status() + " " + r3.booking() + "  (11:00 is where B1 ends: they touch, they do not overlap)");

        System.out.println("-- 09:15 Ravi declines B1");
        s.respond(r1.booking().id(), "ravi", Rsvp.DECLINED);

        System.out.println("-- 09:20 Asha moves B1 to 10:30-11:30: Kaveri is busy from 11:00, so another room");
        Result m1 = s.reschedule(r1.booking().id(), mon(10, 30, 11, 30));
        System.out.println("   " + m1.status() + " " + m1.booking() + "; ravi's answer is now " + s.answerOf(m1.booking().id(), "ravi"));

        s.bookRoom("Yamuna", MeetingRequest.of("kiran", mon(11, 30), mon(12, 30)));
        System.out.println("-- 09:25 Asha tries 11:00-12:00: Kaveri and Yamuna both busy then, Ganga too small, Narmada no video");
        Result m2 = s.reschedule(r1.booking().id(), mon(11, 0, 12, 0));
        System.out.println("   " + m2.status() + ": " + m2.reason());

        System.out.println("-- the first 30 minutes after 10:15 when asha, ravi and meera are all free, with a room for 3 with video");
        Optional<Slot> slot = s.findFirstSlot(List.of("asha", "ravi", "meera"), 30, mon(10, 15, 13, 0), 3, Set.of(Feature.VIDEO));
        System.out.println("   " + slot.map(x -> x.when() + " in " + x.roomId()).orElse("none") + "  (busy 10:30-11:30 and 11:00-12:00 merge into one block)");

        System.out.println("-- a weekly sync in Narmada, Mondays 16:00-17:00 until 19 Oct, all or nothing");
        long oct12 = Time.at(2026, 10, 12, 16, 0);
        Result kiran = s.bookRoom("Narmada", MeetingRequest.of("kiran", oct12, oct12 + 60));
        MeetingRequest sync = MeetingRequest.of("asha", mon(16, 0), mon(17, 0)).titled("weekly sync").inviting("ravi");
        SeriesResult first = s.bookRecurring("Narmada", sync, Recurrence.weekly(LocalDate.of(2026, 10, 19)));
        System.out.println("   refused: " + first.reason() + ", " + Time.day(first.clashes().get(0).start()) + " " + first.clashes().get(0) + "; meetings still " + s.size());
        s.cancelBooking(kiran.booking().id());
        SeriesResult again = s.bookRecurring("Narmada", sync, Recurrence.weekly(LocalDate.of(2026, 10, 19)));
        System.out.println("   after kiran cancels: " + again.seriesId() + " with " + again.booked().size() + " dates");

        System.out.println("-- Kaveri's Monday on the door screen: " + s.listBookingsForRoom("Kaveri", mon(0, 0, 23, 59)));
        System.out.println("-- asha's Monday: " + s.listBookingsForEmployee("asha", mon(0, 0, 23, 59)));

        // the race: fifty people press Book for Yamuna 14:00-15:00 at the same instant
        BookingService race = office();
        int n = 50;
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(n);
        List<Result> results = Collections.synchronizedList(new ArrayList<>());
        for (int i = 0; i < n; i++) {
            final String who = "p" + i;
            new Thread(() -> {
                try { go.await(); results.add(race.bookRoom("Yamuna", MeetingRequest.of(who, mon(14, 0), mon(15, 0)))); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done.countDown(); }
            }).start();
        }
        go.countDown();
        done.await();
        long won = results.stream().filter(Result::ok).count();
        System.out.println("-- fifty people, one room, one hour: booked " + won + " (must be 1), refused " + (n - won));

        // and fifty threads booking, moving and cancelling at random: no room may ever hold two overlapping meetings
        BookingService busy = office();
        int threads = 50;
        CountDownLatch go2 = new CountDownLatch(1), done2 = new CountDownLatch(threads);
        for (int i = 0; i < threads; i++) {
            final int seed = i;
            new Thread(() -> {
                Random rnd = new Random(seed);
                List<String> mine = new ArrayList<>();
                try {
                    go2.await();
                    for (int k = 0; k < 40; k++) {
                        int op = rnd.nextInt(10);
                        if (op < 7 || mine.isEmpty()) {
                            long start = mon(8, 45) + 15L * rnd.nextInt(40);
                            Result r = busy.scheduleMeeting(MeetingRequest.of("u" + seed, start, start + 15L * (1 + rnd.nextInt(8)))
                                                                .forSeats(1 + rnd.nextInt(10)));
                            if (r.ok()) mine.add(r.booking().id());
                        } else if (op < 9) {
                            long start = mon(8, 45) + 15L * rnd.nextInt(40);
                            busy.reschedule(mine.get(rnd.nextInt(mine.size())), new Interval(start, start + 30));
                        } else busy.cancelBooking(mine.remove(rnd.nextInt(mine.size())));
                    }
                } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done2.countDown(); }
            }).start();
        }
        go2.countDown();
        done2.await();
        List<String> problems = busy.audit();
        System.out.println("-- fifty threads, 2,000 random books, moves and cancels: " + busy.size()
                           + " meetings left; problems found: " + (problems.isEmpty() ? "none" : problems));
    }
}
