# Meeting room booking and calendar, LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"meeting-rooms/Main.java").read_text()
ext   = (H/"meeting-rooms/Extensions.java").read_text()
tests = (H/"meeting-rooms/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+120])
    j = next(m for m in marks if m > i and b in ext[m:m+120])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("book", 30, [("a request comes in", "time, seats, equipment, guests"),
                      ("a free room that fits", "two lookups a room; the chooser picks"),
                      ("write it everywhere", "room, id map, each guest's calendar"),
                      ("invitations go out", "after the lock is released")]),
        ("move", 165, [("move B1 to 10:30", "or cancel: out of everything"),
                       ("prove the new time first", "same room if free, else another"),
                       ("then swap old for new", "writes that cannot fail"),
                       ("everyone asked again", "answers back to NEEDS_ACTION")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k*270
        pf += _bx(x, y, 250, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+250, y+27, x+270), True)
pf += _ar("M545 84 V95", dash=True) + _bx(330, 95, 430, 40, "taken, or nothing fits: refused, nothing written", "", dash=True)
pf += _tx(88, 262, "series", "var(--acc)", 13) + _tx(150, 262, "every Monday 16:00 until 19 Oct: every date is proven first; one clash and nothing is booked", "var(--text)", 12, "start")
pf += _tx(88, 292, "query", "var(--acc)", 13) + _tx(150, 292, "without scanning meetings: is Kaveri free 10-11? Kaveri's day? my week? the first 30 min three people and a room are free", "var(--text)", 12, "start")
pf += _tx(615, 324, "many people book at the same time: no room ever holds two overlapping meetings, and nothing is left half-done", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 340, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:00  asha: 6 people, video", ["10:00-11:00, any room", "Ganga seats 4; Narmada: no video",
                                       "Kaveri (8) and Yamuna (12) fit", "smallest that fits: Kaveri, B1"], True),
      ("09:05  ravi: Kaveri 10:30", ["B1 runs from 10:00 to 11:00", "11:00 is after 10:30: overlap",
                                    "refused: ROOM_TAKEN", "nothing is written"], False),
      ("09:10  meera: Kaveri 11:00", ["B1 is [10:00, 11:00)", "meera's is [11:00, 12:00)",
                                     "they touch; they do not overlap", "booked: B2, straight after"], False),
      ("09:30  fifty press Book", ["all want Yamuna 14:00-15:00", "the lock lets one through",
                                  "1 booked, 49 told it is taken", "Yamuna holds one meeting"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Book a named room, or any room that seats the group and has the equipment asked for; the smallest one that fits is picked.</li>
<li>Cancel a meeting: it leaves the room and every calendar.</li>
<li>Move a meeting to a new time: the same room if it is free, otherwise another that fits. A move that cannot happen changes nothing.</li>
<li>Invite people; each answers yes, maybe or no; a move asks them again.</li>
<li>Repeat a meeting daily or weekly until a date: all dates or none, naming the dates that clash.</li>
<li>Show a room's day and a person's week; list the free rooms for a time.</li>
<li>Find the first time when several people and a suitable room are all free.</li>
<li>Refuse a meeting in the past or longer than 12 hours.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many callers at the same time: a room never holds two overlapping meetings.</li>
<li>The overlap check is two lookups in a sorted map, O(log n), never a scan of the room's meetings.</li>
<li>The rules that change (which room, the time limits, double-booked people) are swappable without touching the service.</li>
<li>One source of truth: the service owns every room's calendar, every person's calendar and the answers, behind one lock.</li>
<li>Nothing half-done: a refused booking, move or series writes nothing at all.</li>
<li>Invitations never hold up a booking: they go out after the lock is released.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design a meeting room booking system for our office. Rooms have seats and equipment. People book a room, '
          'or ask for any room that fits, invite colleagues, cancel, move a meeting, repeat it every week, and find a '
          'time when everyone is free. Two meetings must never get the same room at the same time. I want working '
          'code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>An office has meeting rooms, each with a number of seats '
 'and some equipment: a video screen, a whiteboard. Someone asks for a room for a stretch of time. It can be a '
 'named room, or any room that seats the group and has what they need, and then the system picks one. The meeting '
 'goes into the room\'s calendar and into the calendar of everyone invited, and each guest answers yes, maybe or '
 'no. People cancel meetings, move them, repeat them every week until a date, and ask for the first time when '
 'several people and a suitable room are all free. Many people book at the same moment, so the one thing that must '
 'always be true (the invariant) is this: no room ever holds two meetings that overlap in time. A meeting that ends '
 'at 11:00 and one that starts at 11:00 do not overlap.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that books, cancels and moves a few meetings. The interviewer is watching for, in this '
 'order: the questions you ask before typing (does 11:00-12:00 clash with 10:00-11:00? who picks the room?); which '
 'classes exist and which one owns each room\'s calendar; booking and cancelling working end to end; the overlap '
 'check, and whether it scans every meeting or does two lookups in a sorted map; what happens when two people press '
 'Book for the same room at the same instant; where the rules that change live (which room to pick, the longest '
 'meeting, office hours), so a change is a new class and not an edit; and why a move that fails leaves the meeting '
 'where it was. Then the twists: repeating meetings, a free time for several people, a hold that expires, a '
 'waiting list, closed intervals, persistence.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Does a meeting that ends at 11:00 clash with one that starts at 11:00?</td><td>No: a meeting is [start, end), it owns its start minute but not its end minute</td><td>The overlap test and the two lookups (moves 5, 9)</td></tr>'
 '<tr><td>Does the person pick the room, or does the system?</td><td>Both: a named room, or any room that fits, smallest first</td><td>A room chooser behind an interface (move 3)</td></tr>'
 '<tr><td>Seats and equipment?</td><td>Each room has seats and a set of equipment; a request asks for both</td><td>One line, <code>Room.fits</code> (moves 1, 5)</td></tr>'
 '<tr><td>Any limits: the longest meeting, office hours, the past?</td><td>At most 12 hours, never in the past; office hours are a rule you can add</td><td>Time rules that wrap each other (move 3)</td></tr>'
 '<tr><td>Can a person be in two meetings at once?</td><td>Yes, and the reply says so; a room never can</td><td>A conflict rule, handed in (move 3)</td></tr>'
 '<tr><td>Do many people book at the same time?</td><td>Yes, from many threads</td><td>One owner and one lock (moves 4, 7)</td></tr>'
 '<tr><td>A repeating meeting: every date, or whatever is free?</td><td>Every date or none, and name the dates that clash</td><td>Prove every date, then write (move 6)</td></tr>'
 '<tr><td>One office, in memory, one process?</td><td>Yes; buildings, persistence, holds and waiting lists come later</td><td>Each is one of the five twist moves (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> times are whole minutes and a meeting is [start, end); a room never '
 'holds two overlapping meetings, while a person may; "any room" means the smallest that fits, then the lowest id; '
 'a move and a series are proven first and written after; invitations go out after the lock; one office, in '
 'memory, one process. Named as out of scope: holds that expire, waiting lists, several buildings, closed '
 'intervals, persistence; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "an EMPLOYEE books a ROOM for a TIME; the MEETING goes in the ROOM'S CALENDAR and each GUEST'S; guests ANSWER", "var(--text)", 12.5)
for k, (t, sub, acc) in enumerate([("Room", "seats, equipment", 1), ("RoomTimeline", "one room's meetings", 1),
                                   ("Booking", "room, time, guests", 1), ("PersonCalendar", "one person's meetings", 1),
                                   ("Interval", "start, end: overlaps?", 1), ("employee", "a name: a String id", 0),
                                   ("Rsvp", "four answers: an enum", 0)]):
    x = 20 + k*172
    m1 += _bx(x, 110, 160, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + 80))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state of its own: an id, or a fixed list of values", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("is Kaveri free 10:00-11:00?", "RoomTimeline  (owns one room's meetings)", "timeline.isFree(w)"),
                                       ("show asha's week", "PersonCalendar  (owns one person's meetings)", "calendar.overlapping(w)"),
                                       ("book any room for six", "BookingService  (owns every calendar + the lock)", "service.scheduleMeeting(r)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 213, "a verb whose state is spread over two classes goes to the class that owns both: that class becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 232, "\"book\" reads every room and writes one room plus every guest's calendar, so it belongs to the service and to nothing smaller", "var(--muted)", 11)
MV[2] = _mv(1230, 245, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 80, 250, 100, "BookingService", "configure(chooser, policy, ...)", acc=True)
for k, (t, sub, impl) in enumerate([("RoomChooser", "smallest fit, lowest id, least idle", "SmallestFit / LowestId / LeastIdleTime"),
                                    ("BookingPolicy", "12 hours, office hours, not in the past", "MaxLength / OfficeHours / NotInPast"),
                                    ("ConflictPolicy", "a guest is busy: invite or refuse", "InviteAnyway / RefuseIfBusy"),
                                    ("CalendarListener", "mail, door screen, audit log", "Mailer / RoomAuditLog")]):
    y = 20 + k*58
    m3 += _ar("M280 130 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 440, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 275, "dashed green = handed in. The service never builds a rule, so a new room rule is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 295, "and one time rule WRAPS another: new NotInPast(new MaxLength(new AnyTime(), 720)). That wrapping is Decorator, born right here.", "var(--acc)", 11)
MV[3] = _mv(1230, 310, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 210, 44, "asha", "reads: Yamuna 14-15 free") + _bx(30, 110, 210, 44, "ravi", "reads: Yamuna 14-15 free")
m4 += _bx(360, 70, 190, 44, "Yamuna 14:00-15:00", "free", acc=True)
m4 += _ar("M240 52 H360 V70") + _ar("M240 132 H360 V114") + _tx(300, 40, "read", "var(--muted)", 10.5) + _tx(300, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="590" y="20" width="290" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(735, 45, "the gap", RED, 12) + _tx(735, 70, "both saw free, both write:", RED, 11) + _tx(735, 90, "two meetings, one room", RED, 11)
m4 += _tx(735, 130, "fix: check and write as ONE step", "var(--text)", 11)
m4 += _bx(910, 40, 290, 100, "BookingService.lock", "check + every write = one step", acc=True)
m4 += _tx(1055, 165, "the lock lives where the shared state lives", "var(--muted)", 10.5)
m4 += _tx(1055, 185, "the mailer is told AFTER the unlock, never inside", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its shape; then the two lookups drawn on Kaveri's morning
m5 = _D
for k, (q, shape, cost) in enumerate([("does 10:30-11:30 clash in Kaveri?", "TreeMap&lt;start, Booking&gt;: the one before, the one after", "O(log n)"),
                                      ("Kaveri's day on the door screen?", "the same TreeMap: subMap(day start, day end)", "O(log n + k)"),
                                      ("meeting B7, to cancel or move it?", "Map&lt;id, Booking&gt;", "O(1)"),
                                      ("asha's week?", "TreeSet by (start, id), from start - longest", "O(log n + k)"),
                                      ("which rooms seat 6 with video?", "a scan of the rooms: about 200, say it", "O(R log n)"),
                                      ("ravi's answer to B1?", "Map&lt;id, Map&lt;guest, Rsvp&gt;&gt;", "O(1)")]):
    y = 16 + k*46
    m5 += _bx(30, y, 360, 38, q, "the question") + _ar("M390 %s H450" % (y+19), True)
    m5 += _bx(450, y, 520, 38, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+19), True) + _bx(1030, y, 170, 38, cost, "")
# the two lookups, drawn: Kaveri has 09:00-10:00, 11:00-12:00, 13:00-14:00; someone asks for 10:30-11:30
X0, PX = 100, 150            # 08:00 at x=100, 150 px an hour
def hx(h): return X0 + (h - 8) * PX
m5 += '<path d="M%s 372 H%s" stroke="var(--line)" stroke-width="1.3"/>' % (hx(8), hx(15))
for h in range(8, 16):
    m5 += '<path d="M%s 368 V376" stroke="var(--line)"/>' % hx(h) + _tx(hx(h), 392, "%02d:00" % h, "var(--muted)", 10.5)
for (a, b, lab) in [(9, 10, "09:00-10:00"), (11, 12, "11:00-12:00"), (13, 14, "13:00-14:00")]:
    m5 += _bx(hx(a), 318, hx(b) - hx(a), 40, lab, "", acc=False)
m5 += _tx(40, 342, "Kaveri", "var(--acc)", 12, "start")
m5 += _bx(hx(10.5), 412, PX, 40, "10:30-11:30?", "", acc=True, dash=True)
m5 += _ar("M%s 425 H%s V360" % (hx(10.5), hx(10) - 15), True) + _tx(hx(10) - 25, 436, "floorEntry(10:30): 09:00-10:00", "var(--text)", 11, "end")
m5 += _tx(hx(10) - 25, 452, "ends 10:00, before 10:30: no clash", "var(--muted)", 10.5, "end")
m5 += _ar("M%s 425 H%s V360" % (hx(11.5), hx(11.5) + 30), True) + _tx(hx(11.5) + 45, 436, "higherEntry(10:30): 11:00-12:00", "var(--text)", 11, "start")
m5 += _tx(hx(11.5) + 45, 452, "starts 11:00, before 11:30: CLASH", RED, 10.5, "start")
m5 += _tx(615, 482, "only these two can touch a new meeting, because one room's meetings never overlap each other: two lookups, not a scan", "var(--muted)", 11)
MV[5] = _mv(1230, 495, m5)

# move 6: the life of a meeting, and the ORDER inside reschedule
m6 = _D + _bx(30, 30, 190, 44, "BOOKED", "in its room + calendars", acc=True) + _bx(400, 30, 190, 44, "CANCELLED", "out of everything")
m6 += _ar("M220 52 H400", True) + _tx(310, 45, "cancelBooking", "var(--acc)", 10.5)
m6 += _ar("M125 74 V100 H60 V74", True) + _tx(70, 118, "reschedule: same id, new time", "var(--acc)", 10.5, "start")
m6 += _bx(30, 140, 190, 44, "NEEDS_ACTION", "a guest's answer") + _bx(300, 140, 290, 44, "ACCEPTED / TENTATIVE / DECLINED", "any answer, changeable")
m6 += _ar("M220 162 H300", True) + _ar("M445 184 V208 H125 V184") + _tx(285, 222, "a move resets every answer: they agreed to the old time", "var(--muted)", 10.5)
m6 += '<rect x="620" y="20" width="590" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(915, 44, "the order inside reschedule(), and why", "var(--text)", 12)
for k, l in enumerate(["1 the time rules: 12 hours at most, not in the past",
                       "2 a room: the same one if free (its own old time does not count), else the chooser",
                       "3 the people, by the conflict rule",
                       "4 only now: out of the old room and calendars, into the new ones",
                       "steps 1-3 only read: a refusal leaves the meeting where it was",
                       "a series: every date proven first, then every date written"]):
    m6 += _tx(635, 68 + k*25, l, "var(--muted)" if k > 3 else "var(--text)", 11, "start")
m6 += _tx(615, 250, "an illegal call THROWS (an unknown room, an answer from someone not invited); a refusal RETURNS a reason (taken, nothing fits, a rule)", "var(--muted)", 11)
MV[6] = _mv(1230, 265, m6)

# move 7: what is inside the lock, and ten callers at the same instant
m7 = _D + _card(30, 20, 540, 150, "inside the lock (measured: 200 rooms, 10,000 meetings)",
                ["a named room: the rules, two lookups, a few puts: under 1 us", "any room: two lookups in each of 200 rooms: ~5 us",
                 "a year of weekly dates, 53 of them: ~10 us", "the first free slot, 3 people, a busy week: ~50 us",
                 "a room's day for the door screen: ~0.3 us"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside the lock: milliseconds to seconds",
            ["each invitation mail: ~100 ms to the mail server", "the network to the caller: ~50 ms",
             "the person choosing a time: seconds", "a stuck mail server holds up nobody's booking"])
m7 += _tx(615, 200, "ten people press Book for \"any room\" at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 214, 106, 40, "person %d" % (k+1), "waits %d us" % (k*5), acc=(k == 9))
m7 += _tx(615, 282, "the tenth waits about 45 microseconds for the lock, then ~50 ms for the network: one by one is true, and nobody can tell", "var(--muted)", 11)
MV[7] = _mv(1230, 296, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["5,000 people and 200 rooms: about 10,000 bookings a day",
                       "the busiest hour, a third of them: about 1 booking a second",
                       "+ 1 slot search + 20 calendar reads a second: ~60 us of lock",
                       "busy about 0.006% of the time: waits are rare and tiny",
                       "the heavy one is the slot finder: a read that makes writers wait"]):
    m8 += _tx(35, 66 + k*24, l, RED if k == 4 else "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 a read-write lock", "calendars, door screens and slot searches read side by side"),
                              ("2 a lock per room", "rooms never wait for each other; a move locks two, in id order"),
                              ("3 the database decides", "an exclusion constraint, or SELECT ... FOR UPDATE on the room")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("10:00-11:00, then 11:00-12:00 refused", "[start, end): they touch and never overlap; test 1"),
                                ("a meeting starting inside yours missed", "the 2nd lookup is the first meeting after the START; tests 2, 3 (20,000 probes)"),
                                ("two people, one room, one instant", "check and every write under one lock; test 8: 50 threads, one winner"),
                                ("a move fails halfway, old slot lost", "prove first, swap last; test 6: refused move, 10:00 still held"),
                                ("a move clashes with its own old time", "the check ignores the meeting being moved; test 6"),
                                ("week 3 of a series clashes", "every date proven first; test 7: nothing written, 12 Oct reported"),
                                ("the mail server hangs or throws", "listeners after the unlock, in a try/catch; test 9")]):
    y = 18 + k*42
    m9 += _bx(30, y, 320, 38, bad, "") + _ar("M350 %s H400" % (y+19), True) + _bx(400, y, 800, 38, fix, "", acc=True)
m9 += _tx(615, 334, "every claim this design makes has a failure test: FailureTests.java runs eighteen of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 347, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 850)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface RoomChooser { RoomTimeline choose(free, when); }", None), ("a new room rule is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new OfficeHours(new NotInPast(new MaxLength(new AnyTime(), 720)), 8, 20, zone)", None), ("add a time rule instead of editing one", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(events) after the unlock; Mailer implements CalendarListener", None), ("invitations never hold up a booking", None)],
          [("State", "var(--text)"), ("move 6", None), ("enum Rsvp + the order in reschedule: rules, room, people, swap", None), ("a failed move cannot leave half a meeting", None)],
          [("Builder, light", "var(--text)"), ("move 1", None), ("MeetingRequest.of(...).forSeats(6).needing(VIDEO).inviting(\"ravi\")", None), ("seven fields, four optional, still readable", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("callers are HANDED the service; nothing calls getInstance()", "var(--muted)"), ("every test builds a fresh service", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("RecurrenceFactory.parse(\"FREQ=WEEKLY;UNTIL=20261221\") once rules come as text", "var(--muted)"), ("today a series is Recurrence.weekly(...)", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 275, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 290, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("RoomTimeline: one room's meetings. PersonCalendar: one person's. Service: flow + lock.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("LeastIdleTime is a new file plus one configure() line", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("chooser.choose(free, w);  never \"is this the smallest-fit one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("RoomChooser, BookingPolicy, ConflictPolicy, CalendarListener, Clock", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("svc.setClock(() -&gt; mondayAt0830);  svc.configure(new LowestId(), ...)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "lowest id, least idle, a 30-min grid", "a new class behind the existing interface, plus one configure line", "", "move 3"),
        ("someone new wants to know", "a door screen, a room's audit log", "one more listener; the booking path does not change at all", "", "move 4"),
        ("a new step in a life", "HELD until confirmed, WAITLISTED", "a new state, and the order at its critical step", "", "move 6"),
        ("a new invariant across items", "a series; a class of 10 seats", "every check and every write inside the SAME lock: all or nothing", "", "move 4"),
        ("state that must outlive the process", "a database; many app servers", "the meetings behind a repository; the overlap check becomes",
         "EXCLUDE USING gist (room_id WITH =, during WITH &amp;&amp;): the database refuses it", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the room's timeline, the overlap check and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: an <b>employee</b> books a <b>room</b> for a <b>time</b>; the <b>meeting</b> goes into "
 "the <b>room's calendar</b> and each <b>guest's</b>; guests <b>answer</b>. A room has an id, seats and equipment that "
 "never change: a small immutable class, a Java record (a class whose fields are fixed at construction). A room's "
 "calendar holds the meetings in that room, sorted by start: <code>RoomTimeline</code>, the one thing that must never "
 "overlap. A meeting has a room, a time, an organiser and guests: <code>Booking</code>. A person's calendar holds their "
 "meetings, because \"my week\" is asked of it: <code>PersonCalendar</code>. A stretch of time has a start, an end and "
 "one question, do two of them overlap: <code>Interval</code>. An employee has nothing we keep beyond a name, so it is a "
 "String id, not a class; an answer is one of four values, an enum. The service that holds all of it and the lock is "
 "<code>BookingService</code>.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Is Kaveri free at ten?\" reads Kaveri's meetings, so it is a method on the room's calendar: "
 "<code>timeline.isFree(w)</code>. \"Show asha's week\" reads asha's meetings: <code>calendar.overlapping(w)</code>. "
 "\"Book any room for six\" reads every room's calendar and writes one of them plus every guest's calendar at once. Only "
 "the service sees all of that, so <code>service.scheduleMeeting(r)</code>. The same test places the rest: cancel, move "
 "and answer touch a meeting's room, calendars and answers, so they are service methods too; \"do these two meetings "
 "overlap?\" touches only two times, so it is <code>Interval.overlaps</code>. When a verb's state is spread over several "
 "classes it goes to the class that owns them all, and that class becomes the orchestrator (the one class that runs the "
 "flow and calls the others).", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Which room to hand out will change: the smallest that fits today, the lowest room id in one company's version, the "
 "least idle time left over in Uber's follow-up. The time rules will change: the longest meeting (12 hours in "
 "Cleartrip's version), office hours, nothing in the past. What to do when a guest is already busy will change: a "
 "calendar like Google's invites anyway, a stricter office refuses. And somebody will want to be told: the invitation "
 "mail, a screen on the room's door, an audit log. Each becomes a one-method interface the service is <i>given</i> in "
 "<code>configure()</code> and never builds itself. This is where the patterns come from, not the other way round: a "
 "swappable rule behind an interface is <b>Strategy</b>; a time rule that wraps another instead of replacing it is "
 "<b>Decorator</b>; a service that announces \"B1 moved\" without knowing who listens is <b>Observer</b>. Do them; do "
 "not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two people press Book for Yamuna, 14:00 to 15:00, at the same instant. Both read \"free\"; both write; the room now "
 "holds two meetings. That gap between the check and the write is the whole race. So the check and every write (the "
 "room's calendar, the id map, every guest's calendar, the answers) must be one step under one lock, in the class that "
 "owns all of them: the service. One lock also keeps those indexes in step with each other: nobody can ever see a "
 "meeting in a room that is missing from its organiser's calendar. Anything that only listens, like the mailer, is "
 "called after the lock is released, inside a try/catch (so an error it throws is caught and logged). A dead mail "
 "server cannot stall a booking.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers without a scan.",
 "\"Does 10:30-11:30 clash in Kaveri?\" is the question of the round, and the naive answer, a loop over the room's "
 "meetings, is a scan inside the lock. Keep each room's meetings in a TreeMap (a map kept sorted by its keys) from start "
 "minute to meeting. Because one room's meetings never overlap each other, only two of them can touch a new one. The "
 "first is the last meeting starting at or before the new start (<code>floorEntry</code>): it clashes if it ends after "
 "the new start. The second is the first meeting starting after the new start (<code>higherEntry</code>): it clashes if "
 "it starts before the new end. Two lookups, O(log n). Get the second one wrong and you miss a meeting that starts "
 "inside yours: one candidate at Uber looked up the first meeting after the END and was rejected (follow-up 1). A "
 "person's calendar is different, because a person may be double-booked: there a window query starts one "
 "longest-meeting early. \"Which rooms fit?\" is a scan of the rooms, about 200 of them: say so rather than hide it.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A meeting is booked, may be moved any number of times (same id, new time), and may end cancelled. A guest's answer "
 "goes from NEEDS_ACTION to accepted, maybe or declined, and back to NEEDS_ACTION when the meeting moves, because they "
 "agreed to the old time. Writing that down forces the question the interviewer will ask: what if a move fails "
 "halfway? The answer is an order. Check the time rules. Find a room: the same one if it is free, where the meeting's "
 "own old time does not count, or else another that fits. Check the people. Only then swap: remove the old copy from "
 "the room and every calendar, insert the new one. Steps one to three only read, so a refusal leaves the meeting exactly "
 "where it was, and the swap is map writes that cannot fail. A weekly series follows the same rule at a bigger size: "
 "every date is checked first, and one clash means nothing is written and the clashing dates come back. One more "
 "distinction worth saying aloud: an illegal call throws, because it is a bug; a refused booking returns a reason, "
 "because it is a normal Monday.", 6),
("Move 7: yes, the lock makes bookings happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked: if every booking takes the same lock, is the whole office now one queue? It is, for "
 "microseconds. Measured on a laptop with 200 rooms and 10,000 meetings in the week: booking a named room holds the "
 "lock for under a microsecond, and \"any room\" checks all 200 rooms with two lookups each in about 5 microseconds. "
 "A year of weekly dates takes about 10. The heaviest thing inside is the slot finder, about 50 microseconds for three busy "
 "people over a week. Everything slow is outside: the invitation mails (a mail server takes about a tenth of a second "
 "for each), the network, the person deciding. So when ten people press Book at the same instant, the tenth waits "
 "about 45 microseconds for the lock and then 50 ms for the network. One by one is true, and nobody can tell, as long as "
 "nothing slow gets inside.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A 5,000-person office with 200 rooms books about 10,000 meetings a day. Put a third of them in the busiest hour and "
 "that is about one booking a second, with perhaps one slot search and twenty calendar reads alongside: 5 + 50 + 6 "
 "microseconds, about 0.06 ms of lock in every second. The lock is busy about 0.006% of the time, so nothing needs "
 "building yet. Then name the ladder, in the order you would climb it. Rung one: reads far outnumber bookings, and the "
 "slot finder is a read, so a read-write lock (many readers at once, one writer alone) lets calendars, door screens and "
 "searches run side by side. Rung two: a lock per room, so bookings in different rooms never wait for each other; a "
 "move between two rooms takes both locks in room-id order, so two moves can never wait on each other for ever (a "
 "deadlock). Rung three: many app servers, and the database decides with an exclusion constraint or a row lock on the "
 "room. Say the arithmetic first: climbing the ladder without it is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Each row is a few lines in FailureTests.java, which runs eighteen tests and prints ALL PASS or exits non-zero. Two are "
 "worth writing in front of the interviewer. The race: fifty threads wait on one latch (a gate that opens for all of "
 "them at once) and book Yamuna at 14:00; exactly one gets it, forty-nine are told it is taken, and the room holds one "
 "meeting, not zero. The overlap proof: the two-lookup check is compared with a plain scan of every meeting on 20,000 "
 "random times, and they never disagree. The row candidates forget is the fifth. A meeting moved half an hour later "
 "overlaps its own old time, so a check that does not ignore it refuses a move that is perfectly fine.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; each name has one sentence behind it because a move produced it. Two rows are worth saying "
 "without being asked. Builder earned only a light form: a request has seven fields and four are optional, so "
 "<code>MeetingRequest</code> has with-methods that each return a changed copy, and there is no separate builder class. "
 "Factory has not earned a place yet: a series is built in code with <code>Recurrence.weekly(until)</code>. It earns one "
 "the moment rules arrive as text, like the calendar-file rule <code>FREQ=WEEKLY;UNTIL=20261221</code>: one parser "
 "instead of a growing switch (follow-up 18). A pattern without a move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is not a list to recite; it is the check that the moves did their job. Every letter is a line that already "
 "existed because a move produced it, so the honest answer to \"which SOLID principles did you apply?\" is \"move 2 gave "
 "me S, move 3 gave me O, L, I and D\" rather than five definitions. The one worth demonstrating instead of claiming is "
 "D: because the clock is handed in, the test that proves \"not in the past\" moves a variable from 08:30 to 10:00 and "
 "books again, with no sleeping and no flaky timing.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Two of the five need more than the picture gives them. A hold (Amazon's \"selected but not booked yet\") is a new step "
 "in a meeting's life: it takes the room like a booking and carries a deadline. Every call sweeps the expired holds "
 "first, so no timer thread is needed. And when the state must outlive the process, the meetings go behind a repository "
 "(an interface with save and load), and the overlap check becomes the database's job. In Postgres one exclusion "
 "constraint refuses any two rows for the same room whose time ranges overlap. In MySQL you lock the room's row with "
 "<code>SELECT ... FOR UPDATE</code>, check, then insert. Either way one atomic step (nothing can run between its check "
 "and its write) decides the winner, the same idea as the lock one layer down. Page 05 has the code for each.", 12),
]

# ============================================================ page 03: the class diagram
uml_reset()
# callers and the values that go in and out (left column, x 10-262)
put("main", 10, 20, 252, "Main", [], ["office(): 4 rooms, clock 08:30", "main: the morning + two races"])
put("cli", 10, 106, 252, "CommandDriver", [], ["run(line): String  (Cleartrip)"], "extensions")
put("req", 10, 184, 252, "MeetingRequest", ["organizer, title", "when: Interval", "seats, needs, guests"],
    ["of(organizer, start, end)", "titled / forSeats", "needing / inviting"], "record")
put("results", 10, 346, 252, "Result | SeriesResult | Slot", ["Result: status, booking,", "  reason, busy", "SeriesResult: seriesId,",
    "  booked, clashes", "Slot: when, roomId"], ["ok(): the first two"], "record")
put("status", 10, 508, 252, "Status", ["BOOKED, MOVED, ROOM_TAKEN,", "NO_ROOM_FITS, RULE_BROKEN,", "GUEST_BUSY"], [], "enum")
put("time", 10, 620, 252, "Time", ["OFFICE: Asia/Kolkata"], ["at(y, mo, d, h, mi): long", "hm(minute) / day(minute)"])
# the root and what it owns (centre, x 300-630)
put("svc", 300, 20, 330, "BookingService",
    ["rooms: Map&lt;id, RoomTimeline&gt;", "byId: Map&lt;id, Booking&gt;", "calendars: Map&lt;person, PersonCalendar&gt;",
     "answers: Map&lt;id, Map&lt;guest, Rsvp&gt;&gt;", "series: Map&lt;seriesId, Set&lt;id&gt;&gt;", "lock: ReentrantLock",
     "chooser, policy, conflicts, clock", "listeners: List&lt;CalendarListener&gt;"],
    ["configure(chooser, policy, conflicts)", "setClock / addListener / addRoom", "scheduleMeeting(req): Result",
     "bookRoom(roomId, req): Result", "cancelBooking(id): boolean", "reschedule(id, to): Result",
     "bookRecurring(roomId, req, rule)", "cancelSeries(seriesId): int", "respond(id, guest, rsvp)",
     "getAvailableRooms(w, seats, needs)", "listBookingsForRoom / ForEmployee", "busyTimes(person, w) / answerOf",
     "findFirstSlot(who, min, w, seats, needs)", "get(id) / audit() / size()"])
put("timeline", 300, 462, 330, "RoomTimeline", ["room: Room", "byStart: TreeMap&lt;start, Booking&gt;"],
    ["isFree(w, ignoreId): boolean", "add(b) / remove(b)", "between(w): List&lt;Booking&gt;", "firstOpening(from, min, until)",
     "before(t) / after(t) / all()"])
put("person", 300, 642, 330, "PersonCalendar", ["meetings: TreeSet by (start, id)", "longest: long"],
    ["add(b) / remove(b) / contains(b)", "overlapping(w): List&lt;Booking&gt;"])
put("booking", 300, 774, 330, "Booking", ["id, roomId, organizer, title: String", "when: Interval", "seats: int, needs: Set&lt;Feature&gt;",
                                          "guests: List&lt;String&gt;, seriesId: String"],
    ["everyone(): organiser + guests", "movedTo(room, w): Booking"], "record")
# values and enums (x 670-890); the band beside the service keeps gaps where the injected rules cross
put("recur", 670, 20, 220, "Recurrence", ["everyDays: int", "until: LocalDate", "zone: ZoneId"], ["weekly(until) / daily(until)", "dates(first): List"], "record")
put("event", 670, 166, 220, "CalendarEvent", ["kind: Change", "booking, before: Booking", "person, answer: Rsvp"], [], "record")
put("change", 670, 276, 220, "Change", ["BOOKED, MOVED,", "CANCELLED, ANSWERED"], [], "enum")
put("room", 670, 470, 220, "Room", ["id, building: String", "floor, capacity: int", "features: Set&lt;Feature&gt;"], ["fits(seats, needs)"], "record")
put("feature", 670, 600, 220, "Feature", ["VIDEO, WHITEBOARD,", "PROJECTOR, PHONE"], [], "enum")
put("rsvp", 670, 694, 220, "Rsvp", ["NEEDS_ACTION, ACCEPTED,", "TENTATIVE, DECLINED"], [], "enum")
put("interval", 670, 800, 220, "Interval", ["start, end: long (minutes)"], ["overlaps(o): boolean", "minutes(): long"], "record")
# the rules handed in (x 950-1210)
put("chooser", 950, 20, 260, "RoomChooser", [], ["choose(free, when): RoomTimeline"], "interface")
put("choosers", 950, 96, 260, "SmallestFit | LowestId", [], ["min by (seats, id) | min by id"])
put("wrap2", 950, 168, 260, "OfficeHours | AnyTime", [], ["08-20 on one day | always null"])
put("policy", 950, 240, 260, "BookingPolicy", [], ["whyNot(when, now): String"], "interface")
put("wrap1", 950, 322, 260, "MaxLength | NotInPast", ["base: BookingPolicy"], ["whyNot: base first, then own"])
put("conflict", 950, 418, 260, "ConflictPolicy", [], ["refuse(busyPeople): boolean"], "interface")
put("conflicts", 950, 496, 260, "InviteAnyway | RefuseIfBusy", [], ["false | !busy.isEmpty()"])
put("listener", 950, 570, 260, "CalendarListener", [], ["onEvent(e: CalendarEvent)"], "interface")
put("mailer", 950, 648, 260, "Mailer", ["sent: List&lt;String&gt;"], ["onEvent: invite, move, answer"])
put("clock", 950, 744, 260, "Clock", [], ["nowMinutes(): long"], "interface")

edges = [
 # implementations (OfficeHours | AnyTime sits above its interface, the wrappers below it)
 ln(B["choosers"]["t"], B["chooser"]["b"], "inherit"),
 ln(B["wrap2"]["b"], B["policy"]["t"], "inherit"),
 ln(B["wrap1"]["t"], B["policy"]["b"], "inherit"),
 ln(B["wrap1"]["r"], (B["policy"]["r"][0], B["policy"]["r"][1] + 10), "assoc", "", [(1222, B["wrap1"]["r"][1]), (1222, B["policy"]["r"][1] + 10)]),
 ln(B["conflicts"]["t"], B["conflict"]["b"], "inherit"),
 ln(B["mailer"]["t"], B["listener"]["b"], "inherit"),
 # the root owns its maps; what each map holds
 ln(B["svc"]["b"], B["timeline"]["t"], "compose", "1..* by room id"),
 ln((310, 414), B["person"]["l"], "compose", "", [(310, 432), (284, 432), (284, B["person"]["l"][1])]),
 ln((320, 414), B["booking"]["l"], "compose", "", [(320, 442), (274, 442), (274, B["booking"]["l"][1])]),
 ln((630, 596), (630, 812), "assoc", "", [(652, 596), (652, 812)]),
 ln(B["person"]["b"], B["booking"]["t"], "assoc", "by (start, id)"),
 ln((630, 527), (670, 527), "assoc", ""),
 ln((630, 849), (670, 849), "assoc", ""),
 ln(B["room"]["b"], B["feature"]["t"], "assoc", ""),
 ln((630, 85), (670, 85), "assoc", ""),
 ln((630, 213), (670, 213), "assoc", ""),
 ln(B["event"]["b"], B["change"]["t"], "assoc", ""),
 # the rules are handed in; the listeners are told (lanes between the value column and the rules)
 ln((630, 158), B["chooser"]["l"], "inject", "", [(910, 158), (910, B["chooser"]["l"][1])]),
 ln((630, 268), B["policy"]["l"], "inject", "", [(900, 268), (900, B["policy"]["l"][1])]),
 ln((630, 364), B["conflict"]["l"], "inject", "", [(920, 364), (920, B["conflict"]["l"][1])]),
 ln((630, 384), B["listener"]["l"], "notify", "", [(930, 384), (930, B["listener"]["l"][1])]),
 ln((630, 404), B["clock"]["l"], "inject", "", [(940, 404), (940, B["clock"]["l"][1])]),
 # callers, and the values in and out
 ln(B["main"]["r"], (300, B["main"]["r"][1]), "assoc", "calls"),
 ln(B["cli"]["r"], (300, B["cli"]["r"][1]), "assoc", ""),
 ln(B["req"]["r"], (300, B["req"]["r"][1]), "assoc", "in"),
 ln((300, 404), (262, 404), "assoc", "out"),
 ln((B["results"]["b"][0], B["results"]["b"][1]), B["status"]["t"], "assoc", ""),
]
UMLSVG = uml_svg(1230, 980, edges, legend_y=952)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values; &laquo;record&raquo; = a small immutable class whose fields are set once; &laquo;extensions&raquo; = it '
 'lives in Extensions.java). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow '
 'triangle = implements. Filled diamond = owns: the service owns every room\'s timeline, every person\'s calendar and '
 'the meetings by id. Plain arrow = references or returns: a timeline holds its room and its meetings, a person\'s '
 'calendar holds meetings, a meeting holds its interval, the service takes a request and hands back a Result, a '
 'SeriesResult or a Slot (one box, three small records). The arrow from MaxLength | NotInPast round to BookingPolicy '
 'is one time rule wrapping another. Dashed green = handed in through '
 '<code>configure()</code> or <code>setClock()</code>. Dotted blue = notifies: the one call the service makes after it has '
 'released the lock. <b>Where state lives:</b> a room\'s meetings live only in its RoomTimeline, a person\'s only in '
 'their PersonCalendar, the answers only in the service\'s map; the service is the only class that writes to more than '
 'one of them, and only under its lock. Booking, Room, Interval and the requests are records, so they can be handed to '
 'any thread without a lock. Everything in the right-hand column is handed in and can be replaced without opening the '
 'service.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does and what it guarantees; read only those first for the shape, then the bodies. '
 'Start with <code>BookingService.bookLocked</code> and <code>reschedule</code>, about sixty lines between them, which are '
 'the whole interview; then <code>RoomTimeline.isFree</code>, the two lookups. Each copy button copies that whole file. '
 'Below Main.java: Extensions.java (every follow-up\'s reference code, with an <code>ExtDemo</code> main that runs all of '
 'it) and FailureTests.java (eighteen claims proven; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; '
 'java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT +
 '</div>Before typing, write your six to eight clarifying questions; the first two are "does 11:00-12:00 clash with '
 '10:00-11:00?" and "who picks the room?". Then type in the order of Main.java: <code>Interval</code> with its one-line '
 'overlap test; <code>Room</code> and <code>Booking</code>; the room\'s TreeMap with the two-lookup <code>isFree</code>; the '
 'request; the rule interfaces with one implementation each (room chooser, time rule, conflict rule, clock, listener); '
 'the service with its lock (<code>scheduleMeeting</code> and <code>bookRoom</code>, <code>cancelBooking</code>, then '
 '<code>reschedule</code> in its order); and a main with the race. If the clock runs out, the one thing that must exist '
 'is booking and cancelling under one lock with the two-lookup check on [start, end). The people\'s calendars, the '
 'series and the slot finder are the second half hour.</div></div>')

FU = [
("Uber's version: the rooms are just ids, and scheduleMeeting(start, end) returns a room or an error. Write it in fifteen minutes. And what got one candidate rejected?", "functional", 10,
 "It is this page's service with two changes at the edge. The version below is codezym's (a practice site that tags it "
 "to Uber, Salesforce and Amazon): the chooser returns the lexicographically smallest free room id (the first in dictionary order), and times are "
 "<i>closed</i>, so [10, 20] and [20, 30] clash. A closed [s, e] is stored as the half-open [s, e + 1), and nothing "
 "inside changes; <code>bookMeeting</code> returns the room, or \"\" when none is free. Uber's own wording, "
 "<code>scheduleMeeting</code> returning a reservation id with the room, is the same call with a generated id. The "
 "rejected candidate (LeetCode Discuss, 2025) looked up the first meeting starting at or after the new meeting's END. "
 "That meeting can never overlap, so a meeting starting inside the new one was never seen: [5, 11) was booked on top "
 "of [10, 15). The fix is the page's second lookup, the first meeting after the START. The interviewer had called it "
 "\"a data-structure question\": the sorted map per room is the data structure they wanted to see.",
 sect(src, "    boolean isFree(Interval w", "    void add(Booking b)") + "\n" + X("the short version asked at Uber", "least idle time and the audit log")),

("Two people press Book for the same hour in Yamuna at the same instant. Prove it cannot double-book, with a test.", "non-functional", 10,
 "The race lives between reading \"Yamuna is free at 14:00\" and writing the meeting in. <code>bookLocked</code> does "
 "the rules, the check and every write inside one lock, so no other caller can run in that gap. The proof is a test, "
 "not a paragraph: fifty threads wait on one latch, the latch opens, all fifty book Yamuna 14:00-15:00, and the test "
 "counts one BOOKED and forty-nine ROOM_TAKEN. It then checks that the room holds exactly one meeting, because \"one "
 "winner\" would also be true if the meeting had been lost. The second half runs fifty threads booking, moving and "
 "cancelling at random, 2,000 calls, and then audits: no two meetings overlap in any room, and the rooms, the ids and "
 "every calendar agree.",
 T("        // 8. the race", "        // 9. listeners")),

("One lock for the whole office. Does that scale, or is every booking now in one queue?", "non-functional", 5,
 "It is one queue, for microseconds. Measured with 200 rooms and 10,000 meetings: a named room holds the lock for under "
 "a microsecond, any room for about 5 microseconds, the slot finder for about 50 with three busy people over a week. A 5,000-person "
 "office books about one meeting a second in its busiest hour; with a search and twenty reads alongside, that is about "
 "0.06 ms of lock a second. The mails, the network and the person deciding are all outside it. To grow, climb in this "
 "order. First a read-write lock, because calendars, door screens and searches are reads. Then a lock per room, below: "
 "a booking takes one room's lock, \"any room\" tries rooms one lock at a time, and a move takes both rooms' locks in id "
 "order, so two moves never wait on each other. Then the database decides. Know what the second rung costs: a room and "
 "its people's calendars no longer change in one step.",
 X("a lock per room", "time zones")),

("A move fails halfway. What is the state of the system? Show me the code.", "functional", 10,
 "Nothing is half done. <code>reschedule</code> checks the time rules, then finds a room (the same one if it is free at "
 "the new time, where the meeting's own old time does not count, otherwise the chooser picks another that fits), then "
 "checks the people. All three only read. If any of them refuses, it returns the reason with the meeting exactly as it "
 "was, still holding its old room. Only after all three pass does it swap: remove the old copy from the room, the id "
 "map and each calendar, then insert the new copy under the same id. Those are map writes that cannot fail. Every guest "
 "is asked again, because they agreed to the old time. The test fills the only other video room, asks for 11:00-12:00, "
 "gets NO_ROOM_FITS, and checks that 10:00 is still held and ravi's calendar still shows it.",
 sect(src, "    Result reschedule(String meetingId", "    SeriesResult bookRecurring(")),

("Repeat it every Monday until 21 December. What if week three clashes? Do you store the rule or every date? Cancel one date, or all?", "functional", 10,
 "<code>bookRecurring</code> turns the rule into dates first, outside the lock, because that is pure arithmetic. Inside the "
 "lock it checks every date (the time rules, the room, the people) and writes nothing until all have passed. One clash "
 "means nothing is booked and the clashing dates come back, so the person can pick another room or skip that week. "
 "When all pass, each date is written as its own meeting with a shared series id: <code>cancelBooking</code> removes one "
 "date, <code>cancelSeries</code> the rest. Storing each date keeps the overlap check the same two lookups as any "
 "meeting, which is why a series must end and is capped at 400 dates. A calendar that allows \"forever\" stores the rule "
 "plus its exceptions and expands only the weeks on screen; the calendar-file standard (iCalendar) and the Google "
 "Calendar API both work that way. That is the answer to Zepto's \"store the rule or the instances?\". Each date is "
 "counted in days on the local calendar, so 16:00 stays 16:00 (follow-up 15).",
 sect(src, "    SeriesResult bookRecurring(", "    void respond(String meetingId") + "\n" + sect(src, "record Recurrence", "final class RoomTimeline")),

("Find the first 30 minutes when asha, ravi and meera are all free, with a room for three with video. And if no time suits all of them?", "functional", 10,
 "<code>findFirstSlot</code> collects each person's busy times inside the window (a declined meeting does not count), "
 "sorts them and merges overlapping or touching ones into blocks: the classic merge-intervals step. The gaps between the "
 "blocks are when all of them are free. For each gap long enough, it asks every room that fits for its first opening "
 "inside the gap, walking that room's sorted meetings; the earliest opening wins, and when several rooms open at that "
 "minute the chooser picks. On the page's morning, 10:30-11:30 and 11:00-12:00 merge into one block, the quarter hour "
 "before it is too short, and the answer is 12:00 in Ganga. When no time suits everyone (Adobe's \"all or the most\"), "
 "<code>MostAvailable</code> tries only the window's start and the end of each meeting, counts who is free at each, and "
 "keeps the earliest best. A test checks the finder against trying every minute on 60 random days.",
 sect(src, "    Optional<Slot> findFirstSlot(", "    List<String> audit()") + "\n" + X("the time most people can make", "tennis courts at Atlassian")),

("Cleartrip's version is a command line: rooms on floors of buildings, BOOK u1 1:5 b1 7 c1, SEARCH with optional filters, at most 12 hours, and SUGGEST the next three free slots.", "functional", 10,
 "The service does not change; the command driver is a thin caller that parses a line, calls one method and prints one "
 "line. A room's id is building/floor/room, so c1 on floor 7 of b1 is unique across buildings, and the room carries its "
 "building and floor for filtering. BOOK is <code>bookRoom</code> with the 12-hour cap as the time rule. SEARCH is "
 "<code>getAvailableRooms</code>: two lookups in each room, never a scan of meetings, filtered by building and floor when "
 "they are given. LIST BOOKING is <code>listBookingsForRoom</code> over the floor's rooms: one sorted-map range each. "
 "SUGGEST tries each later whole hour of the same length and names the first free room, until it has three. Bad input, "
 "such as an unknown building, comes back as an ERROR line and never as a stack trace. That is what Cleartrip's prompt "
 "asks for (\"fail gracefully with a proper error message\"), and Flipkart's and Udaan's say the same.",
 X("the command-line version asked at Cleartrip", "hold, then confirm") + "\n" + sect(src, "    List<Room> getAvailableRooms(", "    List<Booking> listBookingsForEmployee(")),

("Uber's follow-ups: rooms now have capacities; choose the room that leaves the least idle time around the meeting; keep an audit log per room and delete entries after X days.", "twist", 10,
 "Capacity is already in <code>Room.fits</code>. Least idle time is a new chooser. For each free room that fits, it adds "
 "the gap back to the room's previous meeting and the gap on to its next one (to the edge of the day when there is "
 "none), and takes the smallest. With Yamuna free only 9-10 and Kaveri free 9-12, a 9-10 meeting goes to Yamuna and "
 "fills its gap exactly, although smallest-fit would have picked the smaller Kaveri. The audit log is a listener, so the "
 "booking code never knows it exists. It keeps, per room, a TreeMap from the minute an entry was written to the entries. "
 "Deleting everything older than X days is one <code>headMap(cutoff).clear()</code>, which touches only the entries it "
 "deletes. A move between rooms is written under both.",
 X("least idle time and the audit log", "the command-line version asked at Cleartrip")),

("Rules change mid-round: no meeting over 12 hours, office hours only, nothing in the past, then slots on a 30-minute grid. Where does each one go?", "functional", 5,
 "Each is a class that wraps the rule before it and adds one check. It asks the wrapped rule first and returns its "
 "reason if there is one, otherwise its own. So a new rule is a new class and one changed line in "
 "<code>configure()</code>, and <code>BookingService</code> never opens. Unlike prices that stack (surge then cap and cap "
 "then surge give different bills), the order barely matters here: every rule must pass, so the order changes only "
 "which reason you see first. The grid rule has one trap worth "
 "saying aloud. India is five and a half hours ahead of UTC, so a grid checked on UTC minutes puts the hour marks at half "
 "past; the rule reads the wall clock in the office's zone instead. A test shows that 10:00 in India is 04:30 UTC and is "
 "still allowed on a whole-hour grid.",
 sect(src, "interface BookingPolicy", "interface ConflictPolicy") + "\n" + X("a time rule on a grid", "the time most people can make")
 + "\n// the one line that changes in the setup:\nsvc.configure(new SmallestFit(),\n    new SlotGrid(new OfficeHours(new NotInPast(new MaxLength(new AnyTime(), 12 * 60)), 8, 20, Time.OFFICE), 30, Time.OFFICE),\n    new InviteAnyway());\n"),

("Amazon's twist: a user picks a slot but has not confirmed it yet. Hold it for ten minutes; if they never confirm, free it.", "twist", 10,
 "A hold is a real booking, so nobody else can take the room, and a desk remembers it with its deadline. "
 "<code>confirm()</code> before the deadline removes the deadline, and the booking simply stays. There is no timer "
 "thread: every call first sweeps the holds whose deadline has passed and cancels them, so an abandoned hold is released "
 "on the next touch. Confirm and expiry are decided under the desk's lock, so exactly one of them wins for each hold. "
 "The service is always called outside that lock, so the two locks are never taken in opposite orders. Time comes from "
 "the injected clock, so the test moves the clock ten minutes instead of sleeping, then checks that confirm returns "
 "false and the room can be booked again.",
 X("hold, then confirm", "capacity above one")),

("Now it is a gym class with 20 seats, or a doctor's 30-minute slot: capacity above one, a waiting list, tiers (Platinum 10 classes, Gold 5, Silver 3), and no cancelling in the last 30 minutes.", "twist", 10,
 "The shape changes from one meeting per room per time to up to N members per class. So a class holds a set of members "
 "and a queue of those waiting, all behind one desk lock. <code>book()</code> is idempotent (a retry that arrives twice "
 "is applied once). It refuses a member who is already in an overlapping class (the doctor version: one patient, one slot "
 "at a time) or has used up their tier, and otherwise seats or queues them. <code>cancel()</code> refuses inside the last "
 "30 minutes, gives the class back to the member's quota, and then seats the first waiting member who is still allowed, "
 "in the same lock. So the freed seat is never lost and never given twice. The ranked list of open slots takes a "
 "Comparator (start time today, a doctor's rating tomorrow): Strategy again. The race test: thirty members, ten seats, "
 "one instant, exactly ten seated.",
 X("capacity above one", "a time rule on a grid")),

("Invitations: every guest gets one, the organiser hears each answer, a move asks everyone again. Then Zepto's: share my calendar with view or edit rights, and let a guest propose a new time.", "twist", 10,
 "Answers live in the service, one map per meeting, and a move resets them to NEEDS_ACTION because the guests agreed "
 "to the old time. Every change becomes an event published after the lock is released, so a slow or broken mail "
 "server cannot hold up a booking; the Mailer is one listener. Sharing is data: per owner, a map from viewer to access "
 "(busy blocks only by default, VIEW, or EDIT). <code>view()</code> shows titles and rooms only to VIEW or EDIT; everyone "
 "else sees \"busy 10:00-11:00\". <code>move()</code> refuses anyone who is not the organiser and has no EDIT. A proposal "
 "is stored, not applied. When the organiser accepts it, it is just <code>reschedule()</code>, so it is all or nothing "
 "for free.",
 sect(src, "    void respond(String meetingId", "    // ---------------- the reads") + "\n" + X("sharing and proposals at Zepto", "persistence")),

("Atlassian's tennis club: assign each booking to a court, using as few courts as possible. Then each court needs X minutes of cleaning after a booking, then Y minutes of maintenance after every K bookings.", "twist", 10,
 "This is LeetCode 253 plus the assignment. Sort by start and keep the courts in a min-heap (a priority queue whose head "
 "is the smallest), ordered by the minute each court is free again. For each booking, reuse the court that is free "
 "earliest if it is free by the booking's start, otherwise open a new court: O(n log n). Cleaning and maintenance change "
 "only one line, the minute a court is free again: finish + X, plus Y after every K-th booking. With cleaning the greedy "
 "choice is still optimal, because it is the same problem with every booking X minutes longer. With maintenance it is a "
 "sound greedy, not a proven minimum; say so. The count alone is a sweep over the sorted starts and finishes. A test "
 "checks 200 random days: no court is double-booked, and the count equals the most bookings running at one moment.",
 X("tennis courts at Atlassian", "sharing and proposals at Zepto")),

("Persist it, on several app servers. How does the database stop two servers booking the same room?", "twist", 5,
 "The meetings go behind a repository interface (insert, delete, read a room's window), and the in-memory version is "
 "one implementation; the service above it does not change. The interesting method is <code>insertIfFree</code>. Across "
 "servers a Java lock protects nothing, so the database must refuse the overlap itself. In Postgres one exclusion "
 "constraint does it: no two rows with the same room whose time ranges overlap; a range built with <code>tstzrange(start, end)</code> is "
 "half-open by default, the same rule as <code>Interval</code>. In MySQL, lock the room's row with <code>SELECT ... FOR UPDATE</code>, "
 "check for an overlapping booking, then insert, in one transaction. If rooms and calendars were separate services, "
 "\"book the room and write six calendars\" would span both. The textbook answer is two-phase commit (every side "
 "prepares, then every side commits). The usual answer is one database, or writing the booking and an \"invite\" row in "
 "one transaction and sending the invitations afterwards.",
 X("persistence", "a lock per room")),

("Where does time come from, and what changes when the team is in London?", "design", 5,
 "Times are whole minutes since 1970 in UTC, and the service is handed a <code>Clock</code>. So a test says \"Monday "
 "08:30\" and later \"10:00\" by moving a variable, and the not-in-the-past rule is tested without sleeping. Zones "
 "matter only at the edges (reading and printing) and in two rules: office hours and repeating meetings. A weekly 09:00 "
 "meeting in London crosses the night the UK clocks go back, 25 October 2026. Adding 7 x 1440 minutes keeps the UTC "
 "time, so the meeting drifts to 08:00. <code>Recurrence</code> adds seven days on London's calendar and stays at 09:00. "
 "It also counts every date from the first one, so a 01:30 meeting on the one night that has no 01:30 moves to 02:30, "
 "and the next day is back at 01:30.",
 T("        // 10. the time rules", "        // 11. the conflict rule") + "\n" + T("        // 13. time zones", "        // 14. the short version")),

("Which pattern is where, and why did each one earn its place?", "design", 5,
 "Each one is what a move produced, so name the move, then the line. Strategy is move 3: which room, the time rules and "
 "the conflict rule will all change, so each is a one-method interface the service is handed in "
 "<code>configure()</code>. Decorator is the time rules: OfficeHours wraps NotInPast, which wraps MaxLength, each adding "
 "one check. Observer is move 4's rule that mail must never be inside the lock: the service publishes an event and never "
 "learns who listens. The order in <code>reschedule</code> is move 6: nothing is written until the new time is proven. "
 "The absences are worth saying too: no Singleton, because callers are handed the service and every test builds a fresh "
 "one; no Factory until recurrence rules arrive as text.",
 sect(src, "interface RoomChooser", "interface BookingPolicy") + "\n" + sect(src, "final class MaxLength", "final class OfficeHours")
 + "\n// Observer: the service announces after the unlock; it never learns who listens\ninterface CalendarListener { void onEvent(CalendarEvent e); }\npublish(events);   // AFTER lock.unlock()\n"),

("Which SOLID letter is where in this code?", "design", 5,
 "Not one of them was aimed at; each is a line some move already produced. S: <code>RoomTimeline</code> changes only when "
 "one room's meetings do, <code>PersonCalendar</code> only when one person's do, and the service only when the flow "
 "does. O: least idle time and the 30-minute grid were each a new class and one changed argument, and the service never "
 "opened. L: the service calls <code>chooser.choose(free, w)</code> and never asks which chooser it has. I: every "
 "interface has one method, so a fake for a test is a lambda: <code>e -&gt; { throw new RuntimeException(); }</code> is "
 "a broken mail server. D: the service depends on the interfaces it is handed, which is exactly why a test can hand it "
 "a clock and a strict conflict rule.",
 sect(src, "    void configure(RoomChooser c", "    // ---------------- booking")
 + "\n// L: any chooser drops in; the service never checks which one it got\nRoomTimeline t = chooser.choose(free, w);\n// I: one method each, so a fake is a lambda\nls.addListener(e -> { throw new RuntimeException(\"mail server down\"); });\n// D: the test hands in the clock\nsvc.setClock(() -> now[0]);\n"),

("An enum of equipment, or a Room subclass per kind of room? And where would a Factory pay?", "design", 3,
 "An enum, until a kind of room gains behaviour of its own. Video, whiteboard and projector differ only in whether a "
 "meeting may ask for them, so they are data: a set on the room, checked with one <code>containsAll</code>. A phone booth "
 "is a room with one seat, not a class. A subclass earns its place when a room must <i>do</i> something, for example a "
 "hybrid room whose camera must be switched on five minutes before each meeting: that is behaviour on a schedule. "
 "Factory pays when recurrence rules arrive as text. A calendar-file rule like "
 "<code>FREQ=WEEKLY;INTERVAL=2;UNTIL=20261221</code> is parsed in one place, and anything it does not support is refused "
 "by name rather than half understood.",
 "// data, not classes: equipment is a set on the room\nenum Feature { VIDEO, WHITEBOARD, PROJECTOR, PHONE }\nboolean fits(int seats, Set<Feature> needs) { return capacity >= seats && features.containsAll(needs); }\n\n"
 + X("a recurrence from a string", "Runs every extension")),
]

build(dict(
    slug="meeting-rooms", title="Meeting Room Booking and Calendar",
    subtitle="LLD &middot; Java &middot; OpenJDK 21 &middot; demo, 18 failure tests and a 50-thread race pass",
    problem_body=PROBLEM_BODY,
    derivation_lead=("Run these on any LLD (parking lot, elevator, BookMyShow) and the class diagram, the lock, the "
                     "tests, the patterns, SOLID and the answer to every twist fall out in that order; nothing is "
                     "chosen up front, and nothing is named before the move that produced it."),
    moves=[(t, MV[k], txt) for (t, txt, k) in MOVES],
    uml_svg=UMLSVG, how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", src), ("Extensions.java", ext), ("FailureTests.java", tests)],
    test_class="FailureTests",
    implement_card_html=IMPLEMENT,
    followups=FU,
))
