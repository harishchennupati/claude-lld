import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Eighteen claims the design makes, each proven by a few lines. Run it with
 * javac Main.java Extensions.java FailureTests.java && java FailureTests
 * It prints ALL PASS, or the failures and a non-zero exit code.
 */
public class FailureTests {
    static int failed = 0;

    /** Record one claim. Prints ok or FAIL with the claim's name. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "  ok   " : "  FAIL ") + what);
        if (!ok) failed++;
    }
    /** A minute on the test Monday. */
    static long mon(int h, int m) { return Main.mon(h, m); }
    /** A stretch of the test Monday. */
    static Interval mon(int h1, int m1, int h2, int m2) { return Main.mon(h1, m1, h2, m2); }
    /** A one-seat request on the test Monday. */
    static MeetingRequest req(String who, int h1, int m1, int h2, int m2) { return MeetingRequest.of(who, mon(h1, m1), mon(h2, m2)); }
    /** Free by the definition: no placed interval overlaps w. */
    static boolean scanFree(List<Interval> placed, Interval w) {
        for (Interval p : placed) if (p.overlaps(w)) return false;
        return true;
    }

    public static void main(String[] args) throws Exception {
        // 1. back to back: 10:00-11:00 and 11:00-12:00 share a boundary and do not clash
        System.out.println("1. back-to-back meetings");
        BookingService s = Main.office();
        check(s.bookRoom("Kaveri", req("a", 10, 0, 11, 0)).ok(), "10:00-11:00 booked");
        check(s.bookRoom("Kaveri", req("b", 11, 0, 12, 0)).ok(), "11:00-12:00 booked straight after: they touch, they do not overlap");
        check(s.bookRoom("Kaveri", req("c", 9, 0, 10, 0)).ok(), "09:00-10:00 booked straight before");
        check(s.bookRoom("Kaveri", req("d", 10, 59, 11, 1)).status() == Status.ROOM_TAKEN, "10:59-11:01 clashes with both");

        // 2. an overlap is caught on both sides, and the rejected candidate's check misses one
        System.out.println("2. an overlap is caught on both sides");
        BookingService o = Main.office();
        o.bookRoom("Kaveri", req("a", 10, 0, 11, 0));
        check(o.bookRoom("Kaveri", req("b", 9, 30, 10, 30)).status() == Status.ROOM_TAKEN, "09:30-10:30 runs into it: caught by the first meeting AFTER our start");
        check(o.bookRoom("Kaveri", req("b", 10, 30, 11, 30)).status() == Status.ROOM_TAKEN, "10:30-11:30 starts inside it: caught by the last meeting BEFORE our start");
        check(o.bookRoom("Kaveri", req("b", 9, 0, 12, 0)).status() == Status.ROOM_TAKEN, "09:00-12:00 swallows it: caught after");
        check(o.bookRoom("Kaveri", req("b", 10, 15, 10, 45)).status() == Status.ROOM_TAKEN, "10:15-10:45 sits inside it: caught before");
        check(RoomBooking.rejectedIsFree(new TreeMap<>(Map.of(600, 660)), 570, 630), "the rejected Uber check calls 09:30-10:30 free: it looked after the END");

        // 3. the two lookups agree with scanning every meeting, with and without ignoring one
        System.out.println("3. two lookups = a full scan");
        RoomTimeline t = new RoomTimeline(new Room("X", "", 0, 10, Set.of()));
        List<Interval> placed = new ArrayList<>();
        Map<String, Interval> byId = new HashMap<>();
        Random rnd = new Random(7);
        for (int i = 0; i < 3000; i++) {
            long s0 = rnd.nextInt(100_000);
            Interval w = new Interval(s0, s0 + 1 + rnd.nextInt(90));
            if (scanFree(placed, w)) {
                t.add(new Booking("X" + i, "X", w, "p", "", 1, Set.of(), List.of(), null));
                placed.add(w);
                byId.put("X" + i, w);
            }
        }
        List<String> ids = new ArrayList<>(byId.keySet());
        int disagree = 0;
        for (int i = 0; i < 20_000; i++) {
            long s0 = rnd.nextInt(100_000);
            Interval w = new Interval(s0, s0 + 1 + rnd.nextInt(120));
            String ignore = rnd.nextBoolean() ? ids.get(rnd.nextInt(ids.size())) : null;
            List<Interval> others = new ArrayList<>(placed);
            if (ignore != null) others.remove(byId.get(ignore));
            if (t.isFree(w, ignore) != scanFree(others, w)) disagree++;
        }
        check(placed.size() > 500 && disagree == 0, "on 20,000 random probes (half ignoring one meeting) the two lookups agree with a scan of " + placed.size());

        // 4. seats and equipment: the smallest room that fits; nothing fits; a named room too small
        System.out.println("4. seats and equipment");
        BookingService f = Main.office();
        Result six = f.scheduleMeeting(req("a", 10, 0, 11, 0).forSeats(6).needing(Feature.VIDEO));
        check(six.ok() && six.booking().roomId().equals("Kaveri"), "6 with video -> Kaveri (Ganga seats 4, Narmada has no video, Yamuna is bigger)");
        Result again = f.scheduleMeeting(req("b", 10, 0, 11, 0).forSeats(6).needing(Feature.VIDEO));
        check(again.ok() && again.booking().roomId().equals("Yamuna"), "the same request again: Kaveri is taken, so Yamuna");
        check(f.scheduleMeeting(req("c", 10, 0, 11, 0).forSeats(20)).status() == Status.NO_ROOM_FITS, "20 people: no room fits");
        check(f.bookRoom("Ganga", req("d", 12, 0, 13, 0).forSeats(5)).status() == Status.NO_ROOM_FITS, "5 people in the 4-seat Ganga: refused, not squeezed in");
        check(f.scheduleMeeting(req("e", 12, 0, 13, 0).needing(Feature.PHONE)).status() == Status.NO_ROOM_FITS, "no room has a phone");
        check(f.getAvailableRooms(mon(10, 0, 11, 0), 1, Set.of()).stream().map(Room::id).toList().equals(List.of("Ganga", "Narmada")),
              "free 10:00-11:00: Ganga and Narmada, in id order");

        // 5. cancel frees the room and every calendar; a second cancel is refused
        System.out.println("5. cancel");
        BookingService c = Main.office();
        Result m = c.bookRoom("Kaveri", req("asha", 10, 0, 11, 0).inviting("ravi"));
        check(c.cancelBooking(m.booking().id()), "cancel returns true");
        check(c.listBookingsForRoom("Kaveri", mon(0, 0, 23, 59)).isEmpty() && c.listBookingsForEmployee("ravi", mon(0, 0, 23, 59)).isEmpty(),
              "the room and ravi's calendar are empty again");
        check(c.bookRoom("Kaveri", req("meera", 10, 0, 11, 0)).ok(), "the freed hour can be booked by someone else");
        check(!c.cancelBooking(m.booking().id()) && !c.cancelBooking("B999"), "a second cancel, or an unknown id, returns false");

        // 6. a move: a refused one keeps the old slot; one over its own old time works; answers reset
        System.out.println("6. moving a meeting");
        BookingService mv = Main.office();
        Result b1 = mv.bookRoom("Kaveri", req("asha", 10, 0, 11, 0).forSeats(6).needing(Feature.VIDEO).inviting("ravi"));
        mv.respond(b1.booking().id(), "ravi", Rsvp.ACCEPTED);
        mv.bookRoom("Yamuna", req("x", 10, 0, 12, 0));                             // the only other room for 6 with video
        mv.bookRoom("Kaveri", req("y", 11, 30, 12, 30));
        Result refused = mv.reschedule(b1.booking().id(), mon(11, 0, 12, 0));
        check(refused.status() == Status.NO_ROOM_FITS && refused.booking().equals(b1.booking()), "11:00-12:00 is refused and the result hands back the meeting as it was");
        check(mv.bookRoom("Kaveri", req("z", 10, 0, 10, 30)).status() == Status.ROOM_TAKEN, "its old hour is still held: nobody else can take 10:00");
        check(mv.listBookingsForEmployee("ravi", mon(0, 0, 23, 59)).equals(List.of(b1.booking())), "ravi's calendar still shows 10:00-11:00");
        Result over = mv.reschedule(b1.booking().id(), mon(10, 30, 11, 30));
        check(over.status() == Status.MOVED && over.booking().roomId().equals("Kaveri"), "10:30-11:30 overlaps its own old hour and still stays in Kaveri");
        check(mv.answerOf(b1.booking().id(), "ravi") == Rsvp.NEEDS_ACTION, "a new time asks ravi again: his answer is back to NEEDS_ACTION");
        mv.respond(b1.booking().id(), "ravi", Rsvp.ACCEPTED);
        check(mv.reschedule(b1.booking().id(), mon(10, 30, 11, 30)).ok() && mv.answerOf(b1.booking().id(), "ravi") == Rsvp.ACCEPTED,
              "moving it to the time it already has changes nothing: ravi's yes stands");
        check(mv.audit().isEmpty(), "every index agrees after the moves");

        // 7. recurring: all or nothing, the clashing date reported; cancel one date, then the rest
        System.out.println("7. a weekly series");
        BookingService r = Main.office();
        long oct12 = Time.at(2026, 10, 12, 16, 0);
        Result blocker = r.bookRoom("Narmada", MeetingRequest.of("kiran", oct12, oct12 + 60));
        MeetingRequest sync = req("asha", 16, 0, 17, 0).titled("sync").inviting("ravi");
        SeriesResult no = r.bookRecurring("Narmada", sync, Recurrence.weekly(LocalDate.of(2026, 10, 19)));
        check(!no.ok() && no.clashes().equals(List.of(new Interval(oct12, oct12 + 60))), "12 Oct clashes: refused, and that date is reported");
        check(r.size() == 1 && r.listBookingsForEmployee("ravi", new Interval(mon(0, 0), mon(0, 0) + 30 * 1440)).isEmpty(), "nothing was written: not one of the other three dates");
        r.cancelBooking(blocker.booking().id());
        SeriesResult yes = r.bookRecurring("Narmada", sync, Recurrence.weekly(LocalDate.of(2026, 10, 19)));
        check(yes.ok() && yes.booked().size() == 4, "after the clash is gone: four dates, one series");
        check(r.cancelBooking(yes.booked().get(1).id()) && r.cancelSeries(yes.seriesId()) == 3 && r.size() == 0, "one date cancelled alone, then the series takes the other three");

        // 8. the race: one room, one hour, fifty threads; then fifty threads at random: no overlap anywhere
        System.out.println("8. the race");
        BookingService race = Main.office();
        int n = 50;
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(n);
        List<Result> results = Collections.synchronizedList(new ArrayList<>());
        for (int i = 0; i < n; i++) {
            final String who = "p" + i;
            new Thread(() -> {
                try { go.await(); results.add(race.bookRoom("Yamuna", req(who, 14, 0, 15, 0))); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done.countDown(); }
            }).start();
        }
        go.countDown();
        done.await();
        check(results.stream().filter(Result::ok).count() == 1, "fifty callers, one room, one hour: exactly one booked");
        check(results.stream().filter(x -> x.status() == Status.ROOM_TAKEN).count() == n - 1, "the other forty-nine were told it is taken");
        check(race.listBookingsForRoom("Yamuna", mon(0, 0, 23, 59)).size() == 1, "and the room holds one meeting, not zero");
        BookingService busy = Main.office();
        CountDownLatch go2 = new CountDownLatch(1), done2 = new CountDownLatch(n);
        AtomicInteger errors = new AtomicInteger();
        for (int i = 0; i < n; i++) {
            final int seed = i;
            new Thread(() -> {
                Random rr = new Random(seed);
                List<String> mine = new ArrayList<>();
                try {
                    go2.await();
                    for (int k = 0; k < 40; k++) {
                        int op = rr.nextInt(10);
                        long st = mon(8, 45) + 15L * rr.nextInt(40);
                        if (op < 7 || mine.isEmpty()) {
                            Result x = busy.scheduleMeeting(MeetingRequest.of("u" + seed, st, st + 15L * (1 + rr.nextInt(8))).forSeats(1 + rr.nextInt(10))
                                                               .inviting("g" + rr.nextInt(20)));
                            if (x.ok()) mine.add(x.booking().id());
                        } else if (op < 9) busy.reschedule(mine.get(rr.nextInt(mine.size())), new Interval(st, st + 30));
                        else busy.cancelBooking(mine.remove(rr.nextInt(mine.size())));
                    }
                } catch (Exception e) { errors.incrementAndGet(); }
                finally { done2.countDown(); }
            }).start();
        }
        go2.countDown();
        done2.await();
        check(errors.get() == 0 && busy.audit().isEmpty(), "fifty threads, 2,000 books, moves and cancels: no overlapping pair in any room, every index agrees");

        // 9. listeners hear after the unlock: a stuck one blocks nobody, a throwing one undoes nothing
        System.out.println("9. listeners run after the unlock");
        BookingService ls = Main.office();
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        ls.addListener(e -> {
            if (e.booking().organizer().equals("slow")) {
                entered.countDown();
                try { release.await(5, TimeUnit.SECONDS); } catch (InterruptedException ie) { Thread.currentThread().interrupt(); }
            }
        });
        Thread slow = new Thread(() -> ls.bookRoom("Ganga", req("slow", 10, 0, 11, 0)));
        slow.start();
        entered.await(5, TimeUnit.SECONDS);
        long t0 = System.nanoTime();
        Result fast = ls.bookRoom("Kaveri", req("fast", 10, 0, 11, 0));
        long waitedMs = (System.nanoTime() - t0) / 1_000_000;
        release.countDown();
        slow.join();
        check(fast.ok() && waitedMs < 1000, "while one caller's listener is stuck, another caller books in " + waitedMs + " ms: the lock was already free");
        BookingService th = Main.office();
        th.addListener(e -> { throw new RuntimeException("mail server down"); });
        Result kept = th.bookRoom("Ganga", req("a", 10, 0, 11, 0));
        check(kept.ok() && th.listBookingsForRoom("Ganga", mon(0, 0, 23, 59)).size() == 1, "a throwing listener undoes nothing: the booking stands");
        check(th.bookRoom("Ganga", req("b", 11, 0, 12, 0)).ok(), "and the next booking still works");

        // 10. the time rules read the injected clock
        System.out.println("10. time rules and the clock");
        BookingService tr = Main.office();                                         // the clock says Monday 08:30
        check(tr.bookRoom("Ganga", req("a", 8, 0, 9, 0)).status() == Status.RULE_BROKEN, "08:00 when it is 08:30: starts in the past");
        check(tr.bookRoom("Ganga", MeetingRequest.of("a", mon(9, 0), mon(9, 0) + 13 * 60)).status() == Status.RULE_BROKEN, "13 hours: refused, the cap is 12");
        check(tr.bookRoom("Ganga", MeetingRequest.of("a", mon(9, 0), mon(9, 0) + 12 * 60)).ok(), "exactly 12 hours is allowed");
        tr.configure(new SmallestFit(), new OfficeHours(new NotInPast(new MaxLength(new AnyTime(), 720)), 8, 20, Time.OFFICE), new InviteAnyway());
        check(tr.bookRoom("Kaveri", req("b", 19, 30, 20, 30)).status() == Status.RULE_BROKEN, "office hours 08-20: 19:30-20:30 runs past closing");
        check(tr.bookRoom("Kaveri", req("b", 19, 0, 20, 0)).ok(), "19:00-20:00 ends exactly at closing: allowed");
        long[] now = {mon(10, 0)};
        tr.setClock(() -> now[0]);
        check(tr.bookRoom("Narmada", req("c", 9, 30, 10, 30)).status() == Status.RULE_BROKEN, "move the clock to 10:00 and 09:30 is in the past: no sleeping, no flakiness");

        // 11. the conflict rule: invite anyway reports; refuse-if-busy writes nothing; a declined meeting frees you
        System.out.println("11. people who are already busy");
        BookingService cf = Main.office();
        cf.bookRoom("Ganga", req("ravi", 10, 0, 11, 0));
        Result anyway = cf.bookRoom("Kaveri", req("asha", 10, 30, 11, 30).inviting("ravi"));
        check(anyway.ok() && anyway.busy().equals(List.of("ravi")), "invite anyway (the default): booked, and ravi's clash is reported");
        cf.configure(new SmallestFit(), new NotInPast(new MaxLength(new AnyTime(), 720)), new RefuseIfBusy());
        int before = cf.size();
        Result strict = cf.bookRoom("Yamuna", req("meera", 11, 0, 12, 0).inviting("ravi"));
        check(strict.status() == Status.GUEST_BUSY && strict.busy().equals(List.of("ravi")) && cf.size() == before,
              "refuse if busy: ravi is in asha's 10:30-11:30, so refused and nothing written");
        cf.respond(anyway.booking().id(), "ravi", Rsvp.DECLINED);
        check(cf.busyTimes("ravi", mon(9, 0, 13, 0)).equals(List.of(mon(10, 0, 11, 0))), "after declining, ravi is busy only in his own 10:00-11:00");
        check(cf.bookRoom("Yamuna", req("meera", 11, 0, 12, 0).inviting("ravi")).ok(), "once ravi declines, that meeting no longer makes him busy");

        // 12. the slot finder: the page's example, then random days against trying every minute
        System.out.println("12. the first free slot");
        BookingService sf = Main.office();
        Result d1 = sf.scheduleMeeting(req("asha", 10, 0, 11, 0).forSeats(6).needing(Feature.VIDEO).inviting("ravi", "meera"));
        sf.bookRoom("Kaveri", req("meera", 11, 0, 12, 0));
        sf.reschedule(d1.booking().id(), mon(10, 30, 11, 30));
        sf.bookRoom("Yamuna", req("kiran", 11, 30, 12, 30));
        Optional<Slot> got = sf.findFirstSlot(List.of("asha", "ravi", "meera"), 30, mon(10, 15, 13, 0), 3, Set.of(Feature.VIDEO));
        check(got.isPresent() && got.get().when().equals(mon(12, 0, 12, 30)) && got.get().roomId().equals("Ganga"),
              "the page's example: 12:00-12:30 in Ganga (10:15-10:30 is too short; 10:30-12:00 is one merged block)");
        int wrong = 0;
        Random rs = new Random(11);
        List<Set<Feature>> needsOf = List.of(Set.of(), Set.of(Feature.VIDEO), Set.of(Feature.WHITEBOARD));
        for (int k = 0; k < 60; k++) {
            BookingService day = Main.office();
            for (int q = 0; q < 25; q++) {
                long st = mon(9, 0) + 15L * rs.nextInt(36);
                String org = "p" + rs.nextInt(6), guest = "p" + rs.nextInt(6);
                MeetingRequest mr = MeetingRequest.of(org, st, st + 15L * (1 + rs.nextInt(8)));
                if (!guest.equals(org)) mr = mr.inviting(guest);
                Result x = day.scheduleMeeting(mr.forSeats(1 + rs.nextInt(6)));
                if (x.ok() && !x.booking().guests().isEmpty() && rs.nextInt(3) == 0) day.respond(x.booking().id(), guest, Rsvp.DECLINED);
            }
            List<String> who = List.of("p0", "p" + (1 + rs.nextInt(2)), "p" + (3 + rs.nextInt(3)));
            long minutes = 15L * (1 + rs.nextInt(6));
            int seats = 1 + rs.nextInt(8);
            Set<Feature> needs = needsOf.get(rs.nextInt(3));
            long ws = mon(9, 0) + 15L * rs.nextInt(20);
            Interval window = new Interval(ws, ws + 60L * (2 + rs.nextInt(7)));
            Map<String, List<Interval>> busyOf = new HashMap<>();                  // worked out independently: meetings minus declines
            for (String p : who) {
                List<Interval> taken = new ArrayList<>();
                for (Booking b : day.listBookingsForEmployee(p, window)) if (day.answerOf(b.id(), p) != Rsvp.DECLINED) taken.add(b.when());
                busyOf.put(p, taken);
            }
            long expect = -1;
            for (long t1 = window.start(); t1 + minutes <= window.end() && expect < 0; t1++) {
                Interval slot = new Interval(t1, t1 + minutes);
                boolean everyoneFree = true;
                for (String p : who) if (!scanFree(busyOf.get(p), slot)) everyoneFree = false;
                if (everyoneFree && !day.getAvailableRooms(slot, seats, needs).isEmpty()) expect = t1;
            }
            Optional<Slot> ans = day.findFirstSlot(who, minutes, window, seats, needs);
            boolean ok = expect < 0 ? ans.isEmpty()
                       : ans.isPresent() && ans.get().when().start() == expect
                         && day.getAvailableRooms(ans.get().when(), seats, needs).stream().anyMatch(rm -> rm.id().equals(ans.get().roomId()));
            if (!ok) wrong++;
        }
        check(wrong == 0, "60 random days: the slot finder matches trying every minute, and its room really is free and fits");

        // 13. time zones: a weekly 09:00 London meeting stays 09:00 across the clock change
        System.out.println("13. time zones");
        long first = TimeZones.at(TimeZones.LONDON, 2026, 10, 19, 9, 0);
        List<Interval> right = new Recurrence(7, LocalDate.of(2026, 11, 9), TimeZones.LONDON).dates(new Interval(first, first + 60));
        List<Interval> naive = TimeZones.naiveWeekly(new Interval(first, first + 60), 4);
        check(right.size() == 4 && right.stream().allMatch(i -> TimeZones.hm(i.start(), TimeZones.LONDON).equals("09:00")), "Recurrence: 09:00 London time on all four Mondays");
        check(TimeZones.hm(naive.get(1).start(), TimeZones.LONDON).equals("08:00"), "adding 7 x 1440 minutes: 08:00 once the clocks have gone back");
        long gapFirst = TimeZones.at(TimeZones.LONDON, 2026, 3, 28, 1, 30);
        List<Interval> gap = new Recurrence(1, LocalDate.of(2026, 3, 30), TimeZones.LONDON).dates(new Interval(gapFirst, gapFirst + 30));
        check(TimeZones.hm(gap.get(1).start(), TimeZones.LONDON).equals("02:30") && TimeZones.hm(gap.get(2).start(), TimeZones.LONDON).equals("01:30"),
              "a daily 01:30 across the spring-forward night: only the night with no 01:30 moves; the next day is back at 01:30");

        // 14. the short version, Uber's least idle time, and the audit log
        System.out.println("14. the short version and Uber's follow-ups");
        RoomBooking rb = new RoomBooking(List.of("roomA", "roomB"));
        check(rb.bookMeeting("m1", 10, 20).equals("roomA") && rb.bookMeeting("m2", 15, 25).equals("roomB") && rb.bookMeeting("m3", 20, 30).equals("")
              && rb.cancelMeeting("m1") && rb.bookMeeting("m4", 20, 30).equals("roomA"), "codezym example 1: roomA, roomB, \"\" (20 clashes: closed ranges), true, roomA");
        RoomBooking rb2 = new RoomBooking(List.of("Z1", "A1", "M3"));
        check(rb2.bookMeeting("x", 5, 5).equals("A1") && rb2.bookMeeting("y", 5, 6).equals("M3") && !rb2.cancelMeeting("nope")
              && rb2.bookMeeting("z", 6, 10).equals("A1"), "codezym example 2: A1, M3, false, A1 (5..5 and 6..10 do not overlap)");
        BookingService u = Main.office(), plain = Main.office();
        for (BookingService day : List.of(u, plain)) {
            day.setClock(() -> mon(7, 0));
            for (String room : List.of("Kaveri", "Yamuna")) day.bookRoom(room, req("x", 8, 0, 9, 0));
            day.bookRoom("Yamuna", req("y", 10, 0, 11, 0));                        // Yamuna is free 9-10 only
            day.bookRoom("Kaveri", req("y", 12, 0, 13, 0));                        // Kaveri is free 9-12
        }
        check(plain.scheduleMeeting(req("z", 9, 0, 10, 0).forSeats(6).needing(Feature.VIDEO)).booking().roomId().equals("Kaveri"),
              "the same day under smallest-fit: Kaveri, the 8-seat room");
        u.configure(new LeastIdleTime(), new NotInPast(new MaxLength(new AnyTime(), 720)), new InviteAnyway());
        long[] auditNow = {mon(7, 0)};
        RoomAuditLog log = new RoomAuditLog(() -> auditNow[0]);
        u.addListener(log);
        Result tight = u.scheduleMeeting(req("z", 9, 0, 10, 0).forSeats(6).needing(Feature.VIDEO));
        check(tight.booking().roomId().equals("Yamuna"), "least idle time: Yamuna (free 9-10 exactly), not Kaveri (free 9-12), though Kaveri is smaller");
        auditNow[0] += 3 * 1440;
        u.cancelBooking(tight.booking().id());
        auditNow[0] += 5 * 1440;
        check(log.purgeOlderThan(7) == 1 && log.entries("Yamuna").size() == 1, "the audit log deletes the entry older than 7 days and keeps the newer one");

        // 15. holds, and classes with capacity above one
        System.out.println("15. holds, gym classes, doctors' slots");
        BookingService hs = Main.office();
        long[] clock = {mon(9, 0)};
        hs.setClock(() -> clock[0]);
        HoldDesk desk = new HoldDesk(hs, () -> clock[0], 10);
        Result held = desk.hold("Ganga", req("asha", 14, 0, 15, 0));
        check(hs.bookRoom("Ganga", req("ravi", 14, 0, 15, 0)).status() == Status.ROOM_TAKEN, "a hold keeps others out like a booking");
        clock[0] += 10;
        check(!desk.confirm(held.booking().id()) && hs.bookRoom("Ganga", req("ravi", 14, 0, 15, 0)).ok(), "at its deadline the hold is gone and the room is free again");
        Result held2 = desk.hold("Kaveri", req("asha", 14, 0, 15, 0));
        clock[0] += 5;
        check(desk.confirm(held2.booking().id()) && desk.releaseExpired() == 0 && hs.get(held2.booking().id()) != null, "confirmed in time: it stays after the deadline");
        ClassDesk gym = new ClassDesk(() -> mon(6, 0));
        gym.addClass(new ClassSlot("HIIT", "HIIT", mon(7, 0, 8, 0), 10));
        List<ClassDesk.Answer> answers = Collections.synchronizedList(new ArrayList<>());
        CountDownLatch go3 = new CountDownLatch(1), done3 = new CountDownLatch(30);
        for (int i = 0; i < 30; i++) {
            gym.addMember("m" + i, Tier.GOLD);
            final String who = "m" + i;
            new Thread(() -> {
                try { go3.await(); answers.add(gym.book(who, "HIIT")); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done3.countDown(); }
            }).start();
        }
        go3.countDown();
        done3.await();
        check(Collections.frequency(answers, ClassDesk.Answer.BOOKED) == 10 && Collections.frequency(answers, ClassDesk.Answer.WAITLISTED) == 20,
              "thirty members, ten seats, one instant: exactly ten seated, twenty waiting");
        String firstWaiting = gym.waiting("HIIT").get(0), leaver = gym.seated("HIIT").get(0);
        check(gym.cancel(leaver, "HIIT") == ClassDesk.Answer.CANCELLED && gym.seated("HIIT").contains(firstWaiting) && gym.seated("HIIT").size() == 10,
              "a cancel seats the first member waiting, and only one");
        check(gym.book(firstWaiting, "HIIT") == ClassDesk.Answer.ALREADY_BOOKED && gym.seated("HIIT").size() == 10, "booking twice is booking once");
        ClassDesk late = new ClassDesk(() -> mon(6, 31));
        late.addMember("s", Tier.SILVER);
        for (int k = 0; k < 4; k++) late.addClass(new ClassSlot("C" + k, "yoga", mon(7 + k, 0, 8 + k, 0), 5));
        late.addClass(new ClassSlot("O", "overlap", mon(7, 30, 8, 30), 5));
        check(late.book("s", "C0") == ClassDesk.Answer.BOOKED && late.book("s", "O") == ClassDesk.Answer.OVERLAPS, "one member cannot be in two overlapping classes (or two doctors at once)");
        check(late.book("s", "C1") == ClassDesk.Answer.BOOKED && late.book("s", "C2") == ClassDesk.Answer.BOOKED && late.book("s", "C3") == ClassDesk.Answer.NO_CLASSES_LEFT,
              "Silver means three classes: the fourth is refused");
        check(late.cancel("s", "C0") == ClassDesk.Answer.TOO_LATE && late.cancel("s", "C1") == ClassDesk.Answer.CANCELLED && late.book("s", "C3") == ClassDesk.Answer.BOOKED,
              "06:31 is too late to leave the 07:00 class; leaving the 08:00 one gives the class back");

        // 16. tennis courts: as few as possible, never two bookings on a court at once
        System.out.println("16. tennis courts");
        Random rc = new Random(5);
        int badPlans = 0;
        for (int k = 0; k < 200; k++) {
            List<CourtBooking> dayb = new ArrayList<>();
            for (int i = 0; i < 30; i++) { int st = rc.nextInt(600); dayb.add(new CourtBooking(i, st, st + 10 + rc.nextInt(90))); }
            int clean = k % 2 == 0 ? 0 : 15;
            Map<Integer, Integer> plan = CourtPlanner.assignCourts(dayb, clean, k % 3 == 0 ? 3 : 0, 30);
            Map<Integer, List<CourtBooking>> perCourt = new HashMap<>();
            for (CourtBooking b : dayb) perCourt.computeIfAbsent(plan.get(b.id()), x -> new ArrayList<>()).add(b);
            for (List<CourtBooking> l : perCourt.values()) {
                l.sort(Comparator.comparingInt(CourtBooking::start));
                for (int i = 1; i < l.size(); i++) if (l.get(i).start() < l.get(i - 1).finish() + clean) badPlans++;
            }
            if (clean == 0 && k % 3 != 0 && perCourt.size() != CourtPlanner.minCourts(dayb)) badPlans++;
        }
        check(badPlans == 0, "200 random days: no court is double-booked (cleaning included), and with no cleaning the court count equals the most bookings at one moment");
        check(CourtPlanner.conflict(new CourtBooking(1, 9, 11), new CourtBooking(2, 10, 12)) && !CourtPlanner.conflict(new CourtBooking(1, 9, 11), new CourtBooking(2, 11, 12)),
              "9-11 and 10-12 clash; 9-11 and 11-12 do not");

        // 17. the database refuses an overlap itself; a lock per room keeps the invariant and never deadlocks
        System.out.println("17. persistence and a lock per room");
        InMemoryBookingRepository repo = new InMemoryBookingRepository();
        CountDownLatch go4 = new CountDownLatch(1), done4 = new CountDownLatch(50);
        AtomicInteger stored = new AtomicInteger();
        for (int i = 0; i < 50; i++) {
            final int k = i;
            new Thread(() -> {
                try { go4.await(); if (repo.insertIfFree(new Booking("R" + k, "Kaveri", mon(10, 0, 11, 0), "p" + k, "", 1, Set.of(), List.of(), null))) stored.incrementAndGet(); }
                catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                finally { done4.countDown(); }
            }).start();
        }
        go4.countDown();
        done4.await();
        check(stored.get() == 1 && repo.forRoom("Kaveri", mon(0, 0, 23, 59)).size() == 1, "fifty app servers insert the same room and hour: one row");
        PerRoomBooker pr = new PerRoomBooker(List.of(new Room("A", "", 0, 4, Set.of()), new Room("B", "", 0, 8, Set.of()), new Room("C", "", 0, 12, Set.of())));
        Booking inA = pr.bookRoom("A", "x", mon(12, 0, 13, 0)), inB = pr.bookRoom("B", "y", mon(14, 0, 15, 0));
        Thread m1 = new Thread(() -> { for (int k = 0; k < 5000; k++) pr.move(inA.id(), k % 2 == 0 ? "B" : "A", mon(12, 0, 13, 0)); });
        Thread m2 = new Thread(() -> { for (int k = 0; k < 5000; k++) pr.move(inB.id(), k % 2 == 0 ? "A" : "B", mon(14, 0, 15, 0)); });
        m1.start(); m2.start(); m1.join(10_000); m2.join(10_000);
        check(!m1.isAlive() && !m2.isAlive() && pr.overlaps() == 0, "10,000 moves between two rooms in both directions at once: no deadlock (locks in id order), no overlap");

        // 18. the calendar side: permissions, proposals, the time most can make, rules from strings, a grid, Cleartrip's commands
        System.out.println("18. the calendar side and the command-line version");
        BookingService sc = Main.office();
        SharedCalendars share = new SharedCalendars(sc);
        Result mt = sc.bookRoom("Kaveri", req("asha", 10, 0, 11, 0).titled("pricing").inviting("ravi"));
        share.share("asha", "meera", Access.VIEW);
        check(share.view("kiran", "asha", mon(0, 0, 23, 59)).equals(List.of("busy 10:00-11:00")) && share.view("meera", "asha", mon(0, 0, 23, 59)).get(0).startsWith("pricing"),
              "without a grant you see only busy blocks; with VIEW you see the title");
        boolean refusedEdit = false;
        try { share.move("meera", mt.booking().id(), mon(12, 0, 13, 0)); } catch (SecurityException e) { refusedEdit = true; }
        check(refusedEdit, "VIEW cannot move the meeting");
        String prop = share.propose("ravi", mt.booking().id(), mon(15, 0, 16, 0));
        check(share.accept("asha", prop).status() == Status.MOVED && sc.get(mt.booking().id()).when().equals(mon(15, 0, 16, 0)), "ravi proposes 15:00, asha accepts, the meeting moves");
        BookingService ma = Main.office();
        ma.bookRoom("Ganga", req("p1", 10, 0, 12, 0));
        ma.bookRoom("Kaveri", req("p2", 10, 0, 11, 0));
        ma.bookRoom("Narmada", req("p3", 11, 0, 13, 0));
        MostAvailable.Pick pick = MostAvailable.find(ma, List.of("p1", "p2", "p3"), 60, mon(10, 0, 13, 0));
        check(pick.when().equals(mon(12, 0, 13, 0)) && pick.free().equals(List.of("p1", "p2")), "no hour suits all three: 12:00 suits two, the most");
        Recurrence every2 = RecurrenceFactory.parse("FREQ=WEEKLY;INTERVAL=2;UNTIL=20261109", Time.OFFICE);
        boolean unsupported = false;
        try { RecurrenceFactory.parse("FREQ=WEEKLY;BYDAY=MO;UNTIL=20261109", Time.OFFICE); } catch (IllegalArgumentException e) { unsupported = true; }
        check(every2.everyDays() == 14 && every2.dates(mon(16, 0, 17, 0)).size() == 4 && unsupported, "an RRULE every two weeks gives 4 dates; an unsupported part is refused by name");
        BookingPolicy hourGrid = new SlotGrid(new AnyTime(), 60, Time.OFFICE);
        check(hourGrid.whyNot(mon(10, 0, 11, 0), 0) == null && mon(10, 0) % 60 != 0 && hourGrid.whyNot(mon(10, 30, 11, 30), 0) != null,
              "a whole-hour grid on the wall clock allows 10:00 (which is 04:30 UTC) and refuses 10:30");
        CommandDriver cli = new CommandDriver(LocalDate.of(2026, 9, 28));
        for (String cmd : List.of("ADD BUILDING b1", "ADD FLOOR b1 7", "ADD CONFROOM b1 7 c1 6", "ADD CONFROOM b1 7 c2 10", "BOOK u1 1:5 b1 7 c1", "BOOK u2 3:10 b1 7 c2")) cli.run(cmd);
        check(cli.run("SEARCH 3:10 b1 7").equals("No Rooms available") && cli.run("SUGGEST 3:10").equals("5:12 b1/7/c1, 6:13 b1/7/c1, 7:14 b1/7/c1")
              && cli.run("BOOK u3 1:14 b1 7 c1").equals("ERROR: longer than 12 hours") && cli.run("LIST BOOKING b1 7").equals("1:5 7 b1 c1\n3:10 7 b1 c2")
              && cli.run("BOOK u4 1:2 b9 7 c1").equals("ERROR: no building b9"), "Cleartrip's commands: search, suggest, the 12-hour cap, the list, a clear error for a bad building");

        System.out.println(failed == 0 ? "ALL PASS" : failed + " FAILED");
        if (failed > 0) System.exit(1);
    }
}
