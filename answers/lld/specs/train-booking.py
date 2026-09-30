# Train and flight seat booking (IRCTC / Cleartrip) LLD workbench.
# problem -> twelve moves, each a picture -> the class diagram -> the whole code -> follow-ups and practice.
# What is different from BookMyShow: a berth is sold per SEGMENT of the route; RAC and the waitlist move up on a
# cancel; a group is all or nothing; search is by stations and the boarding date. Hold-then-pay is BookMyShow's order.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

SRC = (H / "train-booking/Main.java").read_text()
EXT = (H / "train-booking/Extensions.java").read_text()
TST = (H / "train-booking/FailureTests.java").read_text()

def cut(src, a, b=None):
    """raw slice between two exact markers, keeping the first marker's whole line"""
    i = src.index(a)
    i = src.rfind("\n", 0, i) + 1
    j = src.index(b, i) if b else len(src)
    return src[i:j].rstrip() + "\n"

def X(a):
    """one '// ---- ext:' block of Extensions.java, found by a phrase in its banner"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", EXT)] + [EXT.index("/** Runs every extension")]
    i = next(m for m in marks if a in EXT[m:m + 160])
    j = next(m for m in marks if m > i)
    return EXT[i:j].rstrip() + "\n"

def sl(src, a, b=None):
    """sect(), but keeping the indentation of the Javadoc's first line, so the snippet reads as it does in the file"""
    s = sect(src, a, b)
    i = src.index(s.split("\n")[0] + "\n" + s.split("\n")[1]) if s.count("\n") > 1 else src.index(s.rstrip())
    return src[src.rfind("\n", 0, i) + 1:i] + s

RED = "#ff6b6b"

# ============================================================ page 01 pictures

# what the code must do: book and cancel, with search and expiry as lines
pf = _D
rows = [("book", 30, [("a group, a journey, a class", "4 people, PUNE to SBC, 3A"),
                      ("free on every segment?", "one word test per berth"),
                      ("a place for each: all or none", "berth, else RAC half, else WL"),
                      ("PNR held for ten minutes", "pay outside the lock: BOOKED")]),
        ("cancel", 170, [("cancel a PNR", "a ticket, or an unpaid hold"),
                         ("give its segments back", "the same locked step as the next"),
                         ("move the waiters up", "RAC to a berth, WL to RAC, in order"),
                         ("refund, then tell them", "after the unlock: money, SMS")])]
for lab, y, boxes in rows:
    pf += _tx(80, y + 31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k * 270
        pf += _bx(x, y, 250, 54, b[0], b[1], acc=(k == 1 if lab == "book" else k == 2))
        if k < 3: pf += _ar("M%s %s H%s" % (x + 250, y + 27, x + 270), True)
pf += _ar("M545 84 V96", dash=True) + _bx(395, 96, 300, 40, "the group does not fit: nothing held", "", dash=True)
pf += _tx(80, 266, "search", "var(--acc)", 13)
pf += _tx(150, 266, "at any moment: which trains run PUNE to SBC on 3 Oct?  how many 3A berths are free from SUR to SBC?", "var(--text)", 12, "start")
pf += _tx(80, 296, "expire", "var(--acc)", 13)
pf += _tx(150, 296, "a hold not paid within ten minutes is released by the next call on its run, and its berths go to the waiters first", "var(--text)", 12, "start")
pf += _tx(615, 332, "many phones on one run at the same instant: no segment of a berth is ever sold twice, and a freed berth goes to the earliest waiter who fits, before anyone new", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 348, pf)

# one morning, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:58  Asha: CSMT to PUNE, 3A", ["first free berth for segment 0", "B1/1, a lower berth", "B1/1 bits: 1 0 0 0", "Rs 268.80, paid: BOOKED"], True),
      ("09:59  Ravi: PUNE to SBC, 3A", ["segments 1 to 3 of B1/1 are free", "B1/1 again: he boards, she leaves", "B1/1 bits: 1 1 1 1", "Rs 1,215.20, paid: BOOKED"], True),
      ("10:05  3A full from SUR to SBC", ["a family of six took the rest", "Meena, Arjun: RAC 1 and RAC 2,", "sharing the side lower B1/7", "Kiran: WL 1"], False),
      ("10:20  Ravi cancels", ["B1/1 free again, PUNE to SBC", "Meena: RAC 1 -> CNF B1/1", "Kiran: WL 1 -> RAC 2, on B1/7", "refund, then the two SMSes"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k * 290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x + 125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x + 125)
    pe += _card(x, 60, 250, 112, t, lines, acc=acc)
P_EX = _mv(1230, 188, pe)

# ============================================================ derivation move pictures
MV = {}

# 1: the nouns, and the berth that is sold by the segment
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a PASSENGER books a BERTH in a COACH of a TRAIN that runs on a DATE, from one STATION to another; he gets a PNR, or waits", "var(--text)", 12.5)
for k, (t, sub, acc) in enumerate([("Train", "the timetable: a route", 1), ("TrainRun", "one date: berths, lock", 1),
                                   ("ClassInventory", "3A: berths and queues", 1), ("Berth", "one bit per segment", 1),
                                   ("Pnr", "journey, fare, status", 1), ("Passenger", "his status, his place", 1),
                                   ("Station", "a code: no class", 0)]):
    x = 20 + k * 172
    m1 += _bx(x, 104, 160, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V104" % (x + 80))
stn = ["CSMT", "PUNE", "SUR", "GTL", "SBC"]
m1 += _tx(215, 232, "B1/1", "var(--text)", 13, "end")
m1 += '<path d="M250 218 H970" stroke="var(--line)" stroke-width="1.5"/>'
for k, s in enumerate(stn):
    x = 250 + k * 180
    m1 += '<circle cx="%s" cy="218" r="4" fill="var(--muted)"/>' % x + _tx(x, 198, s, "var(--muted)", 11)
m1 += '<rect x="254" y="206" width="172" height="26" rx="4" fill="var(--bg3)" stroke="var(--acc)"/>' + _tx(340, 223, "Asha: segment 0", "var(--text)", 11)
m1 += '<rect x="434" y="206" width="532" height="26" rx="4" fill="var(--bg3)" stroke="var(--acc2)"/>' + _tx(700, 223, "Ravi: segments 1, 2, 3", "var(--text)", 11)
m1 += _tx(1000, 223, "bits: 1 1 1 1", "var(--acc)", 11.5, "start")
m1 += _tx(615, 270, "solid = has its own state, becomes a class.   dashed = no state of its own: a value or a method", "var(--muted)", 11)
m1 += _tx(615, 292, "the split that decides the design: a berth has no free-or-sold flag; it has one bit per segment, and PUNE is where Asha's bits end and Ravi's begin", "var(--acc)", 11.5)
MV[1] = _mv(1230, 306, m1)

# 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("is B1/1 free from SUR to SBC?", "Berth  (owns its segment bits)", "berth.isFree(2, 4)"),
                                       ("hold 4 berths PUNE to SBC, or none", "TrainRun  (owns berths, queues, lock)", "run.book(user, from, to, cls, group)"),
                                       ("move the waiters up after a cancel", "TrainRun  (the same state, same lock)", "promoteLocked(inventory, events)"),
                                       ("find trains PUNE to SBC on 3 Oct", "BookingService  (owns the station index)", "svc.search(from, to, date)"),
                                       ("charge the card", "PaymentGateway  (owns no state here)", "gateway.charge(pnrId, paise)")]):
    y = 20 + k * 54
    m2 += _bx(30, y, 340, 44, verb, "the verb") + _ar("M370 %s H410" % (y + 22), True)
    m2 += _bx(410, y, 420, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H870" % (y + 22), True)
    m2 += _bx(870, y, 330, 44, meth, "the method")
m2 += _tx(615, 310, "a verb whose state spans many objects goes to the one that owns them all: the run. A verb that owns nothing, like a charge, is handed in and runs outside every lock", "var(--muted)", 11)
MV[2] = _mv(1230, 324, m2)

# 3: rules -> one-method interfaces handed in
m3 = _D + _bx(30, 110, 240, 110, "BookingService", "configure(fare, chooser, refund)", acc=True)
for k, (t, sub, impls) in enumerate([("FareRule", "class x km; festival week; Tatkal", "DistanceFare / PeakDayFare / TatkalFare"),
                                     ("BerthChooser", "first free; one coach; seniors low", "FirstFreeBerths / FamilyChooser"),
                                     ("RefundRule", "everything back; by hours left", "FullRefund / RailwayRefund"),
                                     ("PaymentGateway", "UPI, card; it can say no", "UpiGateway / a declining fake"),
                                     ("PnrObserver", "SMS on WL -> CNF, analytics", "SmsNotifier / a counting listener")]):
    y = 20 + k * 58
    m3 += _ar("M270 165 H330 V%s H400" % (y + 22), True, True) + _bx(400, y, 330, 44, t, sub, dash=True)
    m3 += _bx(770, y, 430, 44, impls, "the classes that can be handed in") + _ar("M770 %s H730" % (y + 22))
m3 += _tx(615, 322, "dashed green = handed in: three rules through configure(), listeners through addObserver(), the gateway at pay() time. The service builds none of them", "var(--muted)", 11)
m3 += _tx(615, 342, "new PeakDayFare(new DistanceFare(), peakDays, 120): one fare rule wrapping another is Decorator, born right here", "var(--acc)", 11)
MV[3] = _mv(1230, 356, m3)

# 4: the gap, twice: two phones on one berth, and a newcomer between a cancel and the promotion
m4 = _D + _bx(30, 30, 190, 44, "phone 1", "reads: B1/8 free") + _bx(30, 110, 190, 44, "phone 2", "reads: B1/8 free")
m4 += _bx(340, 70, 190, 44, "B1/8, PUNE to SBC", "no bits set", acc=True)
m4 += _ar("M220 52 H340 V70") + _ar("M220 132 H340 V114") + _tx(280, 44, "read", "var(--muted)", 10.5) + _tx(280, 150, "read", "var(--muted)", 10.5)
m4 += '<rect x="560" y="20" width="300" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(710, 45, "the gap", RED, 12) + _tx(710, 70, "both saw it free, both write:", RED, 11) + _tx(710, 90, "one berth, two tickets", RED, 11)
m4 += _tx(710, 130, "fix: decide and write as ONE step", "var(--text)", 11)
m4 += _bx(890, 40, 310, 100, "TrainRun.lock", "decide all, then write all: one step", acc=True)
m4 += _tx(30, 196, "the train's own gap:", "var(--acc)", 12, "start")
for k, (t, sub, bad) in enumerate([("Ravi cancels", "B1/1 free, PUNE to SBC", False), ("a newcomer books", "he takes B1/1", True),
                                   ("the promotion runs", "Meena, RAC 1, finds nothing", True)]):
    x = 200 + k * 250
    m4 += _bx(x, 178, 220, 44, t, sub, dash=bad)
    if k < 2: m4 += _ar("M%s 200 H%s" % (x + 220, x + 250))
m4 += _tx(960, 196, "fix: release and promote", "var(--text)", 11, "start") + _tx(960, 214, "inside the SAME locked step", "var(--text)", 11, "start")
m4 += _tx(615, 250, "one lock per run (a train on a date): two trains, or two dates of one train, never wait for each other; listeners are called after the unlock", "var(--muted)", 11)
MV[4] = _mv(1230, 264, m4)

# 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("which run is 12999 on 2 Oct?", "Map&lt;runId, TrainRun&gt;  on the service", "O(1)"),
                                      ("which trains stop at PUNE, then SBC?", "Map&lt;station, Map&lt;train, stop number&gt;&gt;", "O(trains at PUNE)"),
                                      ("is B1/1 free on segments 2 and 3?", "BitSet per berth: nextSetBit(2) &gt;= 4", "O(1): one word"),
                                      ("which berths are free PUNE to SBC?", "walk the class's berths once", "~250 tests, ~1 us"),
                                      ("who is next on RAC, on the waitlist?", "LinkedHashSet&lt;Passenger&gt;: order + O(1) remove", "O(1)"),
                                      ("PNR 4210000007?", "Map&lt;pnr, run&gt; on the service, Map&lt;pnr, Pnr&gt; on the run", "O(1)"),
                                      ("which unpaid holds have lapsed?", "ArrayDeque of holds: all last 10 minutes, oldest first", "O(1) each")]):
    y = 18 + k * 48
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H440" % (y + 20), True)
    m5 += _bx(440, y, 560, 40, shape, "the shape", acc=True) + _ar("M1000 %s H1030" % (y + 20), True)
    m5 += _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 364, "every scan avoided here is a scan avoided INSIDE the lock, which is the only place a scan would have cost anybody anything", "var(--muted)", 11)
MV[5] = _mv(1230, 378, m5)

# 6: two state machines and the order at the critical steps
m6 = _D + _tx(30, 26, "Passenger", "var(--acc)", 12.5, "start")
m6 += _bx(30, 36, 160, 44, "WAITLISTED", "a queue number") + _bx(290, 36, 160, 44, "RAC", "half a side lower", acc=True)
m6 += _bx(550, 36, 160, 44, "CONFIRMED", "a berth of his own", acc=True) + _bx(750, 36, 140, 44, "CANCELLED", "all given back")
m6 += _ar("M190 58 H290", True) + _tx(240, 50, "a half fits", "var(--muted)", 10)
m6 += _ar("M450 58 H550", True) + _tx(500, 50, "a berth fits", "var(--muted)", 10)
m6 += _ar("M110 80 V104 H630 V80", True, True) + _tx(370, 118, "a berth fits his whole journey: straight up", "var(--muted)", 10)
m6 += _ar("M710 58 H750", dash=True) + _tx(820, 98, "from any state", "var(--muted)", 10)
m6 += _tx(30, 150, "Pnr", "var(--acc)", 12.5, "start")
m6 += _bx(30, 170, 200, 44, "PENDING_PAYMENT", "places held 10 minutes", acc=True) + _bx(330, 170, 170, 44, "BOOKED", "paid: the ticket", acc=True)
m6 += _bx(600, 170, 150, 44, "CANCELLED", "a ticket, or a hold") + _bx(330, 250, 170, 40, "EXPIRED", "never paid")
m6 += _ar("M130 170 V150 H675 V170", dash=True) + _tx(420, 144, "a hold given up", "var(--muted)", 10)
m6 += _ar("M230 192 H330", True) + _tx(280, 184, "paid in time", "var(--muted)", 10)
m6 += _ar("M500 192 H600", dash=True) + _tx(550, 184, "cancel", "var(--muted)", 10)
m6 += _ar("M130 214 V270 H330", dash=True) + _tx(145, 262, "ten minutes pass", "var(--muted)", 10, "start")
m6 += '<rect x="915" y="20" width="295" height="292" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(1062, 44, "the order, and why", "var(--text)", 12)
for k, (l, hi) in enumerate([("book, under the lock:", 1), ("1 release lapsed holds first", 1), ("2 decide every place, write nothing", 1),
                             ("3 all fit: write all; else throw", 1), ("pay, NO lock: charge, key = the PNR", 1),
                             ("commit, locked: PENDING? then BOOKED", 1), ("commit, locked: lapsed? refund it", 0),
                             ("cancel, locked: work out the refund,", 1), ("then give back, move the waiters up", 1),
                             ("after the unlock: refund, the SMSes", 0)]):
    m6 += _tx(928, 70 + k * 24, l, "var(--text)" if hi else "var(--muted)", 11, "start")
m6 += _tx(460, 338, "a passenger only ever moves up, and a freed berth never sits free while someone who fits is waiting", "var(--muted)", 11)
MV[6] = _mv(1230, 352, m6)

# 7: what is inside the lock, and ten phones at once
m7 = _D + _card(30, 20, 540, 160, "inside the run's lock: about 2 microseconds a booking",
                ["release lapsed holds: a peek at the head of a queue", "walk the class's berths once: ~250 one-word tests",
                 "check the chooser's answer; count RAC and waitlist room", "write each passenger's bits; put the PNR in a map",
                 "a cancel adds the promotion walk: at worst ~0.1 ms"], acc=True)
m7 += _ar("M570 100 H640", True) + _tx(605, 90, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 160, "outside the lock: milliseconds to minutes",
            ["the payment gateway: about 1,500,000 us", "the SMS \"WL 3 -> CNF B1/12\": after the unlock",
             "search: the station index, no run's lock at all", "the user typing six names: a minute",
             "nothing slow is ever inside: that is the whole trick"])
m7 += _tx(615, 210, "ten phones press Book on the same run at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k * 118
    m7 += _bx(x, 224, 106, 40, "phone %d" % (k + 1), "waits %d us" % (k * 2), acc=(k == 9))
m7 += _tx(615, 292, "the tenth phone waits about 18 microseconds for the lock, then a second and a half at the bank with the lock long released: one at a time is true, and nobody can tell", "var(--muted)", 11)
MV[7] = _mv(1230, 306, m7)

# 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one lock per run: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a booking holds the lock ~2 us; an availability count ~0.5 us",
                       "Tatkal at 10:00 on a hot train: say 3,000 tries in minute one",
                       "50 a second x 2 us = 100 us of lock per second: 0.01% busy",
                       "5,000 a second on one run, from bots: 10 ms per second, 1%",
                       "the bank inside the lock: 1.5 s each, under 1 booking a second"]):
    m8 += _tx(35, 66 + k * 24, l, RED if k == 4 else "var(--muted)", 11, "start")
m8 += _tx(900, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 reads off the lock", "search gets a copy of the berth masks; the sideways index (page 05)"),
                              ("2 a lock per class", "3A and sleeper share no berth and no queue, so they need not share a lock"),
                              ("3 one writer per run, or the database's lock", "a queue per run (a Kafka partition), or SELECT ... FOR UPDATE on the run")]):
    m8 += _bx(600, 58 + k * 50, 600, 42, t, sub, acc=(k == 0))
m8 += _tx(615, 224, "say the arithmetic first: at 0.01% busy, every rung is code nobody needs yet", "var(--muted)", 11)
MV[8] = _mv(1230, 238, m8)

# 9: what can go wrong, and the test for each
m9 = _D
for k, (t, sub, fix) in enumerate([("two phones, the last berth", "one berth, two tickets", "decide and write in one locked step; test 2: 50 threads, one winner; test 3: exactly 12 places"),
                                   ("overlapping segments", "two people, one berth, one night", "the bit test covers every segment; test 1: three people share B1/1, the overlap goes elsewhere"),
                                   ("a newcomer after a cancel", "the waiter is skipped", "release and promote in one locked step; test 6: 100 races, the waiter wins every time"),
                                   ("a group that half fits", "two booked, two dropped", "decide all, then write all; test 7: refused whole, and nothing is held"),
                                   ("the card fails, or is too slow", "a berth lost, or sold twice", "hold, pay outside, commit re-checks; tests 9, 10: the hold stays, or the money goes back"),
                                   ("a hold nobody pays", "a berth held for ever", "every call releases lapsed holds first; test 9: at ten minutes the waiter is confirmed"),
                                   ("the SMS gateway throws", "the promotion dies with it", "publish after the unlock, inside a catch; test 12: the booking completes")]):
    y = 20 + k * 46
    m9 += _bx(30, y, 300, 40, t, sub) + _ar("M330 %s H380" % (y + 20), True) + _bx(380, y, 820, 40, fix, "", acc=True)
m9 += _tx(615, 358, "and a model check: 3,000 random operations, then 8 threads at once, with every invariant checked from scratch (test 16). FailureTests runs 23 tests, 93 checks", "var(--muted)", 11)
MV[9] = _mv(1230, 372, m9)

# 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface FareRule { long farePaise(run, from, to, cls); }", None), ("swap a rule without opening the run", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new PeakDayFare(new DistanceFare(), peakDays, 120)", None), ("add to a fare instead of copying it", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(events) after lock.unlock(); SmsNotifier hears WL -&gt; CNF", None), ("the run never learns what an SMS is", None)],
          [("State", "var(--text)"), ("move 6", None), ("PassengerStatus + PnrStatus, and the fixed promotion order", None), ("a passenger only ever moves up", None)],
          [("Factory", "var(--muted)"), ("not yet", None), ("coaches arrive built; it pays when layouts come from a file", "var(--muted)"), ("say 'not yet, and here is why'", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("never here", None), ("main builds one BookingService; every test builds its own", "var(--muted)"), ("a global is a test you cannot write", "var(--muted)")],
          [("Builder, Command", "var(--muted)"), ("never", None), ("no move produced them", "var(--muted)"), ("a pattern without a move is decoration", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 275, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 290, m10)

# 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 555)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Berth: its bits. TrainRun: its places, queues, lock. BookingService: the order of steps.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("Tatkal = one new class and one changed configure() line", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("fare.farePaise(this, from, to, cls) * group.size();  never 'is it Tatkal?'", None)],
          [("I", "var(--acc)"), ("small interfaces, so a fake for a test is one line", None), ("move 3", None), ("FareRule, BerthChooser, RefundRule, Clock, PnrObserver: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("new BookingService(() -&gt; now[0], HOLD);  svc.pay(pnr, a gateway that declines)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# 12: every twist is one of five moves
m12 = _D
tw = [("a new rule", "Tatkal, flexi-fare, a refund by hours", "a new class behind the existing interface + one configure line", "", "move 3"),
      ("someone new wants to know", "SMS on WL -> CNF, the chart, analytics", "one more observer; the booking path does not change a line", "", "move 3"),
      ("a new step in a life", "chart prepared: waitlisted e-tickets refunded", "a new status, and the one method that moves a PNR into it", "", "move 6"),
      ("a new invariant across berths", "a family in one coach; a Tatkal quota", "decide and write inside the SAME locked step: all or nothing", "", "move 4"),
      ("state that must outlive the process", "persist it; many servers", "the maps behind tables; a berth claim becomes a conditional UPDATE",
       "UPDATE run_berth SET sold_mask = sold_mask | :m WHERE ... AND (sold_mask &amp; :m) = 0", "move 5 + this one")]
for k, (t, sub, fix, fsub, mv) in enumerate(tw):
    y = 24 + k * 54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y + 22), True) + _bx(420, y, 660, 44, fix, fsub, acc=True) + _tx(1150, y + 27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the order decide, write, pay, commit never changes: each adds a class, a listener, a status or a step inside the lock", "var(--muted)", 11)
MV[12] = _mv(1230, 326, m12)

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the caller, the listener, the clock, and the catalog that never changes
put("app", 10, 20, 235, "Booking app / kiosk", ["svc: BookingService"], ["search &rarr; book &rarr; pay", "cancel(pnr) / status(pnr)"])
put("obs", 10, 150, 235, "PnrObserver", [], ["onEvent(e: PnrEvent)"], "interface")
put("sms", 10, 240, 235, "SmsNotifier", [], ["onEvent &rarr; send the SMS"])
put("clock", 10, 318, 235, "Clock", [], ["nowMs(): long"], "interface")
put("train", 10, 408, 235, "Train", ["number, name: String", "stops: List&lt;Stop&gt;", "coaches: List&lt;Coach&gt;", "stopNo: Map&lt;station, int&gt;"],
    ["stopNo(station): int", "segments() / km(a, b)"])
put("stop", 10, 588, 235, "Stop / Coach", ["Stop(station, timeMin,", "     dayOffset, km)", "Coach(id, cls, bays)"], [], "record")
put("tclass", 10, 700, 235, "TravelClass", ["SLEEPER, AC3, AC2"], [], "enum")
put("btype", 10, 778, 235, "BerthType", ["LOWER, MIDDLE, UPPER,", "SIDE_LOWER, SIDE_UPPER"], [], "enum")
# centre column: the orchestrator, the aggregate root, the class inventory, the berth
put("svc", 290, 20, 340, "BookingService", ["trains / runs: Map&lt;id, ..&gt;", "atStation: Map&lt;station, Map&lt;train, stop&gt;&gt;", "byPnr: Map&lt;pnr, TrainRun&gt;",
    "fare / chooser / refund: the rules", "observers, clock, holdMs"],
    ["configure(fare, chooser, refund)", "addTrain(t) / addRun(no, date, rac, wl)", "search(from, to, date): List&lt;Journey&gt;",
     "availability(run, from, to, cls)", "book(run, user, from, to, cls, group, ..)", "pay(pnr, gateway): Pnr", "cancel(pnr, gateway): long refunded"])
put("run", 290, 318, 340, "TrainRun", ["train: Train,  date: LocalDate", "classes: Map&lt;TravelClass, ClassInventory&gt;", "pnrs: Map&lt;pnr, Pnr&gt;",
    "holds: ArrayDeque&lt;Pnr&gt;  (oldest first)", "lock: ReentrantLock  (fair)", "clock, holdMs, observers"],
    ["book(user, from, to, cls, group, ..): Pnr", "commit(pnr, ref): boolean", "cancel(pnr, rule): long", "availability(from, to, cls)",
     "status(pnr) / sweep() / soldMasks(cls)", "-sweepLocked / expireLocked", "-releaseLocked / promoteLocked"])
put("inv", 290, 646, 340, "ClassInventory", ["berths: List&lt;Berth&gt;", "racHalves: List&lt;Berth&gt;  (2 per RAC berth)", "rac: LinkedHashSet&lt;Passenger&gt;",
    "waitlist: LinkedHashSet&lt;Passenger&gt;", "waitlistCap: int"], ["free(places, from, to) / firstFree(..)", "position(queue, passenger)"])
put("berth", 290, 842, 340, "Berth", ["coach, number, type: BerthType", "shared: boolean  (an RAC half)", "sold: BitSet  (bit i = segment i)"],
    ["isFree(from, to) / take / release", "mask(): long / label()"])
# middle-right column: the PNR's status enum above it (clear of the injected lines), the PNR, its passengers
put("pstatus", 665, 200, 245, "PnrStatus", ["PENDING_PAYMENT, BOOKED,", "EXPIRED, CANCELLED"], [], "enum")
put("pnr", 665, 318, 245, "Pnr", ["id, userId: String", "run: TrainRun,  cls", "from, to: stop numbers", "passengers: List&lt;Passenger&gt;",
    "amountPaise: long", "holdExpiresMs: long", "status: PnrStatus", "paymentRef: String"], [])
put("pass", 665, 520, 245, "Passenger", ["who: Traveller", "pnr: Pnr", "status: PassengerStatus", "place: Berth  (null on WL)"], [])
put("xstatus", 665, 640, 245, "PassengerStatus", ["CONFIRMED, RAC,", "WAITLISTED, CANCELLED"], [], "enum")
put("vals", 665, 740, 245, "the value records", ["Traveller(name, age, pref)", "Journey(run, from, to, ..)", "Availability(berths, rac, wl)", "PnrEvent(pnr, name, what)"], [], "record")
# right column: the rules and the gateway, each with its implementations
put("fare", 950, 20, 260, "FareRule", [], ["farePaise(run, from, to, cls)"], "interface")
put("fares", 950, 104, 260, "DistanceFare", ["PER_KM: Map&lt;class, paise&gt;"], ["farePaise &rarr; rate x km"])
put("peak", 950, 196, 260, "PeakDayFare", ["base: FareRule, peakDays"], ["farePaise &rarr; base x 1.2 on a peak day"])
put("chooser", 950, 300, 260, "BerthChooser", [], ["choose(free, group): List&lt;Berth&gt;"], "interface")
put("first", 950, 384, 260, "FirstFreeBerths", [], ["choose &rarr; first free, in order"])
put("refund", 950, 462, 260, "RefundRule", [], ["refundPaise(pnr, nowMs): long"], "interface")
put("full", 950, 546, 260, "FullRefund", [], ["refundPaise &rarr; the whole amount"])
put("pay", 950, 624, 260, "PaymentGateway", [], ["charge(key, paise): ref | null", "refund(ref, paise)"], "interface")
put("upi", 950, 724, 260, "UpiGateway", [], ["charge &rarr; one ref per key"])
put("errs", 950, 802, 260, "the three exceptions", [], ["NoPlaces: the group does not fit", "HoldLapsed: the places are gone", "PaymentDeclined: the bank said no"])

edges = [
    ln(B["sms"]["t"], B["obs"]["b"], "inherit"),
    ln(B["fares"]["t"], B["fare"]["b"], "inherit"),
    ln((B["peak"]["t"][0] - 70, B["peak"]["t"][1]), (B["fare"]["b"][0] - 70, B["fare"]["b"][1]), "inherit"),
    ln(B["peak"]["r"], (B["fare"]["r"][0], B["fare"]["r"][1] + 10), "assoc", "", [(1222, B["peak"]["r"][1]), (1222, B["fare"]["r"][1] + 10)]),
    ln(B["first"]["t"], B["chooser"]["b"], "inherit"),
    ln(B["full"]["t"], B["refund"]["b"], "inherit"),
    ln(B["upi"]["t"], B["pay"]["b"], "inherit"),
    # the catalog on the left
    ln(B["train"]["b"], B["stop"]["t"], "compose", "stops, coaches"),
    ln(B["stop"]["b"], B["tclass"]["t"], "assoc"),
    # the spine: service owns runs, a run owns one inventory per class and its PNRs, an inventory owns berths
    ln(B["svc"]["b"], B["run"]["t"], "compose", "runs"),
    ln(B["run"]["b"], B["inv"]["t"], "compose", "one per class"),
    ln(B["inv"]["b"], B["berth"]["t"], "compose", "berths, halves"),
    ln((630, 420), (665, 420), "compose"),
    ln(B["pnr"]["t"], B["pstatus"]["b"], "assoc"),
    ln(B["pnr"]["b"], B["pass"]["t"], "compose"),
    ln(B["pass"]["b"], B["xstatus"]["t"], "assoc"),
    ln((665, 572), (630, 900), "assoc", "", [(648, 572), (648, 900)]),
    ln((290, 380), (245, 460), "assoc", "", [(260, 380), (260, 460)]),
    ln((245, 350), (290, 350), "inject"),
    ln((290, 930), (245, 818), "assoc", "", [(262, 930), (262, 818)]),
    # the rules, handed in through configure(); the gateway through pay()
    ln((630, 110), B["fare"]["l"], "inject", "injected", [(920, 110), (920, B["fare"]["l"][1])]),
    ln((630, 130), B["chooser"]["l"], "inject", "", [(928, 130), (928, B["chooser"]["l"][1])]),
    ln((630, 150), B["refund"]["l"], "inject", "", [(936, 150), (936, B["refund"]["l"][1])]),
    ln((630, 170), B["pay"]["l"], "inject", "", [(943, 170), (943, B["pay"]["l"][1])]),
    ln((290, 540), (245, 177), "notify", "", [(278, 540), (278, 177)]),
    ln((245, 60), (290, 60), "assoc", "calls"),
    '<text x="795" y="512" font-size="10.5" fill="var(--muted)">1..6</text>',
]
UMLSVG = uml_svg(1230, 1000, edges, legend_y=975)

HOW_TO_READ = (
    '<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed list of values; '
    '&laquo;record&raquo; = an immutable value). Middle: its fields, the state it holds. Bottom: its methods; a leading minus '
    'marks a private helper that runs with the lock already held. <b>The arrows.</b> Hollow triangle = implements. Filled '
    'diamond = owns: the service owns the runs, a run owns one ClassInventory per class and its PNRs, an inventory owns its '
    'berths and RAC halves, a PNR owns its one to six passengers. Plain arrow = references: a passenger points at the berth '
    'or RAC half he sits on, a berth at its BerthType. Dashed green = handed in and never built here: the three rules '
    'through <code>configure()</code>, the clock through the constructor, the gateway as an argument to <code>pay()</code>. '
    'Dotted blue = notifies, after the lock is released. <b>Where state lives:</b> the left column is the catalog (a train, '
    'its stops and coaches) and never changes while anybody books. Every field that changes during a booking is on a Berth, '
    'a Passenger, a Pnr or the TrainRun itself, and every write to one of them happens inside that run\'s lock. The service '
    'holds no berth state: it owns the indexes, runs book, pay and commit in order, and is the only class that talks to the bank.')

# ============================================================ page 01: the problem
PROMPT = ('"Design IRCTC\'s ticket booking. Users search trains between two stations on a date, book berths for a group, pay '
          'and cancel; a berth sold from Mumbai to Pune must be sold again from Pune onwards, and when a class is full people '
          'go on RAC and the waitlist and move up when someone cancels. Thousands want the last berth at 10:00. I want working '
          'code, not a diagram. Go."')

REQ = ('<div class="req"><div><b>Functional requirements</b><ul>'
       '<li>Search trains between two stations on a date, where the date is the day the passenger boards; show a train\'s route by its number.</li>'
       '<li>Availability: how many berths of a class are free for a journey, then RAC places, then the waitlist.</li>'
       '<li>Book up to six passengers from one station to another in one class: each gets a berth, an RAC place or a waitlist number, or none of them does. An option: berths only.</li>'
       '<li>A berth is sold per segment: sold from Mumbai to Pune, it is sold again from Pune onwards.</li>'
       '<li>Hold the places for ten minutes while the user pays; the ticket (a BOOKED PNR; a PNR is the booking reference) exists only after the payment.</li>'
       '<li>Cancel: the segments come back, RAC moves up to berths and the waitlist to RAC, earliest first, and money goes back.</li>'
       '<li>Fares by class and distance; refunds by the hours left; both changeable.</li>'
       '<li>A PNR enquiry: each passenger\'s current status, such as CNF B1/23 (confirmed, coach B1, berth 23), RAC 2, or WL 4 (fourth on the waitlist).</li></ul></div>'
       '<div><b>Non-functional requirements</b><ul>'
       '<li>Many users on one run at once: no segment of a berth is sold twice; the last berth has exactly one winner.</li>'
       '<li>Fair: a freed berth goes to the earliest waiter whose journey fits, before any new booking.</li>'
       '<li>Nothing half-done: a group is placed whole or not at all; a failed payment keeps the hold; a late one is refunded.</li>'
       '<li>Fast: "is this berth free for this journey" is one word test; availability is one pass over a class; search is an index lookup.</li>'
       '<li>Fare, berth choice, refund and payment swappable without opening the run.</li>'
       '<li>Money in integer paise: a double loses fractions of a paisa across a sum.</li>'
       '<li>In memory, one process, no database (say it; a follow-up adds the tables).</li></ul></div></div>')

PROBLEM_BODY = (
    '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
    '<div class="move"><h3>The problem, in plain words</h3><p>Indian Railways sells berths on trains that run a fixed route of '
    'stations, once a day. A train on one date is a <b>run</b>; its berths sit in coaches, and each coach belongs to a class '
    '(sleeper, 3A, 2A) with its own price. Unlike a cinema seat, a berth is sold for only part of the route: from the station '
    'where the passenger boards to the one where he gets off. So one berth can carry Asha from Mumbai to Pune and Ravi from Pune '
    'to Bengaluru, and what is really sold is a <b>segment</b>: the track between two neighbouring stops. When a class has no '
    'berth left for a journey, the next passengers get <b>RAC</b> (reservation against cancellation: two people share one '
    'side-lower berth), then a place on a capped <b>waitlist</b>, and a cancellation moves them up. The rule that must always '
    'hold (the invariant): no segment of any berth is sold to two people, and a berth that comes free goes to the earliest '
    'waiting passenger whose journey fits, before anyone new can take it.</p></div>'
    '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a '
    '<code>main</code> that sells one berth twice on different segments, fills a class, cancels, and races fifty threads for the '
    'last berth. The interviewer is watching for, in this order: the questions you ask before typing (does a berth resell per '
    'segment, what happens when a class is full); which classes exist and which one owns which state, above all the split '
    'between the train (a timetable) and the run (that train on one date), and a berth that stores segments instead of a '
    'free-or-sold flag; book and cancel working end to end, with RAC and the waitlist moving up; what happens when two people '
    'press Book for the last berth; where the rules that change live (fare, which berth, refund, payment), so a change is a new '
    'class and not an edit; and what happens when the payment fails or arrives after the hold. Then the twists: search by '
    'stations and date, availability at scale, a family in one coach, the database tables and locking, Tatkal at 10:00 (the last-minute quota that opens '
    'the day before travel), and the flight version.</p></div>'
    '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
    '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
    '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
    '<tr><td>Is a berth sold for the whole route, or again after its passenger gets off?</td><td>Again: a passenger holds a berth only between his two stations</td><td>A berth stores sold segments, not a flag (moves 1, 5)</td></tr>'
    '<tr><td>What does one booking contend on: the train, the date, the class?</td><td>One train on one date: a run, with a new run every day</td><td>TrainRun owns everything a booking changes, behind one lock (moves 1, 4)</td></tr>'
    '<tr><td>Which classes and berths; do preferences matter?</td><td>Sleeper, 3A, 2A in bays of eight; preferences best-effort</td><td>A class inventory; berth choice behind an interface (moves 3, 5)</td></tr>'
    '<tr><td>When a class is full: RAC and a waitlist? How many?</td><td>Two RAC passengers per side-lower berth kept for RAC; a capped waitlist</td><td>Two queues and the promotion order (move 6)</td></tr>'
    '<tr><td>Groups: how many per ticket, and what if only some fit?</td><td>Up to six; every one gets some place or none does; a "berths only" option</td><td>Decide all, then write all, under one lock (moves 4, 6)</td></tr>'
    '<tr><td>Are berths held while the user pays? Can payment fail?</td><td>Yes, for ten minutes; it can decline or be slow</td><td>Hold, pay outside the lock, commit: BookMyShow\'s order (move 6)</td></tr>'
    '<tr><td>How are fares and refunds worked out?</td><td>By class and distance; refunds by the hours left</td><td>Fare and refund rules behind interfaces (move 3)</td></tr>'
    '<tr><td>One process, or a database and many servers? Flights too?</td><td>One process, in memory; the rest named</td><td>Follow-ups on page 05 (move 12)</td></tr></table></div>'
    '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ +
    '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
    '<div class="grade"><b>Say before typing:</b> a run is one train on one date, with one lock; a berth is sold per segment, '
    'and a journey covers its segments half-open, so getting off at Pune and boarding at Pune do not clash; up to six '
    'passengers per PNR, every one placed or none; RAC is two people on one side-lower berth, the waitlist has a cap, and a '
    'freed berth goes to the waiters first; a ten-minute hold, payment outside the lock, the PNR as the idempotency key (a unique '
    'id per payment, so a retry is charged once); money in paise; one process, in memory. Named as out of scope: the database tables, search at scale, Tatkal, refund rules, a '
    'family in one coach, flights, many servers; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
DER_LEAD = ('Run these twelve on any LLD and the class diagram, the lock, the tests, the patterns, SOLID and the answer to '
            'every twist fall out in that order. Nothing is chosen up front, and no pattern is named before the move that '
            'produced it. For this problem the first move decides everything: a berth is not sold, a segment of it is.')

MOVES = [
("Move 1: underline the nouns, and see that a berth is not sold: a segment of it is.",
 "Reading the prompt again: a <b>passenger</b> books a <b>berth</b> in a <b>coach</b> of a <b>train</b> that runs on a "
 "<b>date</b>, from one <b>station</b> to another; he gets a <b>PNR</b> (the booking reference), or waits. A train has a number, "
 "a route and a coach layout, and none of that changes while people book: <code>Train</code> is a timetable. What is sold is "
 "that train on one date, so it is its own class, <code>TrainRun</code>, with its own berth objects; the run of the 2nd and the "
 "run of the 3rd never share a field. One class of travel on a run (its 3A) has berths, RAC places and a waitlist: "
 "<code>ClassInventory</code>. A PNR has passengers, a journey, a fare and a status, and each <code>Passenger</code> has his own "
 "status and place. A station is only a code and search is a question, so neither becomes a class. Then the move that decides "
 "the design: is a berth free? A yes-or-no flag cannot say \"sold to Asha as far as Pune, free after\". So a <code>Berth</code> "
 "keeps one bit per segment, and a booking sets the bits of its journey.", 1),

("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Is B1/1 free from Solapur to Bengaluru\" reads the berth's bits, so <code>berth.isFree(2, 4)</code>. \"Hold four berths from "
 "Pune to Bengaluru, or none\" touches many berths, the RAC places, the waitlist and the PNR map at once; only the run owns all "
 "of them, so <code>run.book(...)</code>. \"Move the waiters up\" touches the same state, so it lives in the same class under the "
 "same lock. \"Find the trains from Pune to Bengaluru on the 3rd\" reads an index that spans every train, so it belongs to the "
 "orchestrator, <code>BookingService.search</code>. The orchestrator is the class that runs the steps in order and owns no "
 "berth of its own. \"Charge the card\" touches none of our state, so it is handed in and called outside every lock. A verb "
 "whose state spans many objects goes to the one that owns them all; that is how a small <code>Berth</code> and one busy "
 "<code>TrainRun</code> appear without planning them.", 2),

("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Fares will change: by class and distance today, a festival week tomorrow, Tatkal and flexi-fare (a price that rises as the train fills) the round after. Which berth "
 "a passenger gets will change: the first free one today, a family in one coach and lower berths for seniors tomorrow. Refunds "
 "depend on the hours left before departure. Payment can say no. And somebody must be told when a waitlisted ticket confirms. "
 "Each becomes a one-method interface the service is <i>given</i> and never builds: three rules through <code>configure()</code>, "
 "listeners through <code>addObserver()</code>, the gateway as an argument to <code>pay()</code>. This is where the patterns come "
 "from, not the other way round. A swappable rule behind an interface is <b>Strategy</b>. A rule that wraps another and adds "
 "to it (a festival surcharge over the distance fare) is <b>Decorator</b>. A run that announces \"WL 1 moved to RAC 2\" to "
 "whoever subscribed, without knowing what an SMS is, is <b>Observer</b>. Write them; do not announce them.", 3),

("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two phones read \"B1/8 is free from Pune to Bengaluru\" in the same millisecond and both write it. Between the read and the "
 "write is the gap, and the gap is one berth with two tickets. So deciding a place for every passenger and writing them all "
 "must be one step, under one lock, in the class that owns the berths: the run. One <code>ReentrantLock</code> per run (Java's "
 "standard lock; re-entrant means the thread holding it may take it again). The run is what callers really fight over, so two "
 "trains, or two dates of one train, never wait for each other. The train has a second gap of its own. If a cancel gave B1/1 "
 "back in one step and moved the waiters up in another, a new booking could land in between and take the berth Meena has "
 "waited for since morning. So the release and the promotion happen inside the same locked section. The clock is read inside "
 "the lock too, and listeners are called only after it is released.", 4),

("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Which run is 12999 on the 2nd\": a map from run id to run. \"Which trains stop at Pune and then at Bengaluru\": a map from "
 "station to (train, stop number), filled when a train is added, so search walks only the trains that stop at Pune. \"Is B1/1 "
 "free on segments 2 and 3\": a <code>BitSet</code> (Java's growable array of bits) per berth; the first sold bit at or after "
 "segment 2 must be at 4 or later. Up to 64 segments that is one 64-bit word, the same cost for any journey. \"Which berths "
 "are free from Pune to Bengaluru\": the one walk on the booking path, one test per berth, about a microsecond for 250. \"Who "
 "is next on RAC or the waitlist\": a <code>LinkedHashSet</code>, which keeps arrival order and still removes a passenger in "
 "O(1) when he cancels from the middle. \"Which holds have lapsed\": every hold lasts the same ten minutes, so they lapse in "
 "the order they were made and the oldest is always at the head of a queue. Every scan avoided here is a scan avoided inside "
 "the lock.", 5),

("Move 6: a passenger and a PNR each have a life cycle, and the ORDER at the critical steps is the design.",
 "A passenger is WAITLISTED, RAC, CONFIRMED or CANCELLED, and he only moves up: WL to RAC, RAC to a berth, or WL straight to a "
 "berth when one fits his whole journey. A PNR is PENDING_PAYMENT while its places are held, BOOKED once paid, EXPIRED after "
 "ten unpaid minutes, CANCELLED if given back. Each is a small state machine (a fixed set of states and the moves allowed "
 "between them), and writing them down forces the order. Booking, under the lock: release lapsed holds first, decide a place "
 "for every passenger while writing nothing, refuse the whole group if one does not fit, and only then write them all. "
 "Payment runs after the unlock with the PNR as the idempotency key, and the commit books only a PNR that is still PENDING: "
 "BookMyShow's order, reused. Cancel, under the lock: work out the refund from the statuses as they are, give the segments "
 "back, and move the waiters up earliest first, skipping anyone whose journey does not fit. One difference from BookMyShow: "
 "a lapsed hold cannot simply read as free, because a freed berth belongs to the waitlist first. So every call on a run "
 "releases lapsed holds, and promotes, before it reads anything.", 6),

("Move 7: yes, one lock per run makes bookings happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself first: if every booking on a run takes the same lock, is a Tatkal "
 "morning now a queue? It is, for about two microseconds a booking. That is measured on a laptop with 256 berths in the class "
 "and a 20-stop route: a book-and-cancel pair took 3 to 5 microseconds. The left-hand box is all of it: a peek at the holds "
 "queue, one walk over the class's berths testing one word each, and a few field writes. A cancel adds the promotion walk; "
 "at its worst (108 waiters, none of whom fits) it took about a tenth of a millisecond, still the slowest thing inside. "
 "Everything slow is outside: the bank, the SMS, the search, the user typing names. One at a time is true and nobody can "
 "tell, as long as nothing slow gets inside. The sharp edge: the fare and refund rules run inside the lock, so they must stay "
 "arithmetic.", 7),

("Move 8: say the arithmetic, then name the ladder.",
 "Do the arithmetic out loud; it is four numbers and it ends the argument. Say a hot train gets three thousand booking attempts "
 "in the first minute of Tatkal: fifty a second, two microseconds each, a hundred microseconds of lock in every second, busy "
 "one hundredth of one per cent. Even five thousand a second on one run, from bots, keeps the lock one per cent busy. The "
 "number that decides the design is the red one: put the bank's second and a half inside the lock and the run books fewer "
 "than one ticket a second, so that minute's three thousand would take over an hour. Then the ladder, cheapest first. Rung "
 "one moves reads off the lock: search pages get a copy of the berth masks, and the sideways index on page 05. Rung two is a "
 "lock per class, safe here because 3A and sleeper share no berth and no queue. Rung three is one writer per run (a queue, "
 "or a Kafka partition per run) or the database's own row lock. Climbing without the arithmetic is complexity nobody asked "
 "for.", 8),

("Move 9: list what can go wrong, and write the test for each before the hour is over.",
 "The table is the list; the file is the proof. Every row is a bug that ships the moment the matching line of the design is "
 "dropped, and every row is a few lines in FailureTests.java. Three need a trick to test at all. The races start fifty "
 "threads behind one latch (a gate that opens for all of them at once), so they really collide. The expiry tests move an "
 "injected clock instead of sleeping ten minutes. And the strongest test is a model check: thousands of random bookings, "
 "payments, cancels and clock moves, with every invariant checked from scratch after each one (no segment sold twice, nobody "
 "waiting while a place fits his journey, every status matching its queue). The tests have teeth: take the lock out and the "
 "race sells more places than exist; take the promotion out and nine checks fail, the model check among them.", 9),

("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; what is worth practising is the order you say it in. Name the move first and the pattern second: "
 "\"fares will change, so the service is handed a one-method rule; that is Strategy\". The first half is a design decision; "
 "\"I used Strategy\" on its own is a label. Observer has its best reason on this page: a waitlisted ticket confirms while its "
 "passenger sleeps, and the SMS must go out after the lock, where a dead SMS gateway cannot stall the next booking. The grey "
 "rows are worth as much as the others. \"Factory has not earned a place yet; coach layouts read from a file would make me "
 "add one\" says more than a fifth pattern doing nothing.", 10),

("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is a check you run after the design, not a list you design towards. Every row points back at a move, and a letter "
 "with no move behind it means you recited it rather than did it. The letter doing the most work here is D. The service is "
 "handed its clock, its rules and its gateway, and that single habit is the only reason a test can jump ten minutes forward, "
 "hand in a bank that declines, and count the charges.", 11),

("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The picture is the answer sheet: match the twist to one of the five, say which one aloud, then type. Two are worth "
 "rehearsing. A new invariant across berths (a family in one coach, a quota of berths kept for Tatkal) is not a search "
 "problem but a locking problem: choose and write inside the same locked step, or another booking takes a berth between your "
 "choosing and your writing. State that must outlive the process moves behind tables, and the berth claim becomes a "
 "conditional UPDATE on a 64-bit mask column: set the journey's bits only where none of them is set yet, and zero rows "
 "changed means somebody else won. That is the database's compare-and-set (write only if the value is still what you "
 "expect, as one atomic step), the same idea as the lock one layer down. For all five, the order decide, write, pay, commit "
 "never changes. Page 05 has the working code for each.", 12),
]
MOVES = [(t, MV[k], txt) for (t, txt, k) in MOVES]

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each class '
              'and method says what it does and what it guarantees; read only those first for the shape, then the bodies, '
              'starting with <code>TrainRun.book</code> and <code>promoteLocked</code>, which are the whole interview. Each copy '
              'button copies that whole file. Below Main.java: Extensions.java (the reference code for every follow-up, with an '
              '<code>ExtDemo</code> main that runs all of it) and FailureTests.java (23 tests, 93 checks; '
              '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3><button class="timer" data-min="60">start 60:00</button></div>'
             '<div class="cb"><div class="prompt">' + PROMPT + '</div>Before typing, write your six to eight clarifying questions; then '
             'type in the order of Main.java: the enums (TravelClass, BerthType, PassengerStatus, PnrStatus), the records (Stop, '
             'Coach, Traveller), Train, Berth with its bitmap, Passenger and Pnr, the three small exceptions, Clock and the five '
             'one-method interfaces with one implementation each, ClassInventory, the TrainRun with its lock and the order inside '
             '<code>book</code> and <code>cancel</code>, the BookingService with the station index and the payment between the two '
             'locked halves, and a main with the race. If the clock runs out, the part that must exist is <code>Berth.isFree</code> '
             'and <code>take</code>, <code>TrainRun.book</code> and <code>cancel</code> with the promotion under one lock, and '
             'search. The ten-minute hold, the RAC halves, the fare and refund rules and the listeners come after.</div></div>')

FU = [
("Fares will change: a festival week costs more, then Tatkal, then flexi-fare. Where does each one go, without touching TrainRun?", "functional", 10,
 "Fare is already an interface, so each one is a new class that wraps the rule before it, and the run never opens. "
 "<code>PeakDayFare</code> asks the wrapped rule and multiplies by 120 per cent when the run's date is a peak day; it reads the "
 "run's date, not the clock, so a September booking for a Diwali train pays the Diwali fare. <code>TatkalFare</code> adds 30 per "
 "cent of the fare, but never less than a floor or more than a cap for the class. <code>FlexiFare</code> adds 10 per cent for every tenth of "
 "the class already sold on that journey, up to 50 per cent; it reads the run inside <code>book</code>, where the lock is already "
 "held, which is safe because the lock is re-entrant. The order of wrapping is a decision to say out loud: on the test's train, "
 "with four of seven berths sold, flexi inside Tatkal costs Rs 2,222.80 and Tatkal inside flexi Rs 2,369.64, because the cap "
 "applies to a different number.",
 sl(SRC, "final class PeakDayFare", "// \"the family wants") + "\n" + X("fares that change")),

("Fifty people press Book for the last 3A berth at once. Prove one wins. Pessimistic or optimistic locking?", "non-functional", 10,
 "The race lives between reading \"B1/8 is free\" and writing it. <code>book</code> does both inside the run's lock, in two passes: "
 "the first decides a place for every passenger and writes nothing, the second writes them all. The proof is two tests: fifty "
 "threads behind one latch want the last berth with \"berths only\", and exactly one booking comes back; fifty more hit an empty "
 "class of seven berths, two RAC halves and a waitlist of three, and exactly twelve get a place. That is pessimistic locking "
 "(take the lock, then read and write); optimistic locking lets everyone read and writes only if nothing changed meanwhile, and "
 "card 3 has both in SQL. The lock is created fair, so the thread that has waited longest goes next: Zepto's \"handle concurrent "
 "booking requests in a fair manner\". Intuit's \"the first 120 users fly free\" has the same shape: claim the counter inside the "
 "same lock, or <code>UPDATE promo SET used = used + 1 WHERE used &lt; 120</code>.",
 sl(SRC, "    Pnr book(String userId", "    boolean commit(Pnr p") + "\n" + cut(TST, "        // 2. fifty phones", "        // 4. a cancel moves")),

("A berth is booked from station 1 to 3 and again from 5 to 10. Who else can buy it, and what does a search from 3 to 4 show?", "functional", 10,
 "Anyone whose journey lies inside the gap, 3 to 5 or any part of it. A berth keeps one bit per segment, and a journey from stop "
 "a to stop b covers segments a up to b minus one: half-open, so a passenger getting off at 3 and another boarding at 3 share no "
 "segment. <code>isFree(a, b)</code> finds the first sold bit at or after a and says free if it is at b or later, one word for up "
 "to 64 segments. <code>take</code> refuses to set a bit that is already set, so even a buggy caller cannot sell a segment twice. "
 "A search from 3 to 4 counts this berth, because segment 3 is unsold. The test sells B1/1 for Mumbai to Pune and for Solapur "
 "to Bengaluru, finds it still counted from Pune to Solapur, sells that gap to a third passenger, and sends an overlapping "
 "journey to another berth.",
 sl(SRC, "final class Berth", "final class Passenger") + "\n" + cut(TST, "        // 1. a berth is sold per segment", "        // 2. fifty phones")),

("The class is full. Put people on RAC and the waitlist, and move them up when someone cancels.", "functional", 10,
 "A class keeps three tiers: berths, RAC halves (each side-lower berth kept for RAC carries two passengers, each half with its "
 "own segment bits), and a capped waitlist. A booking gives each passenger the best tier that fits his journey. A cancel gives "
 "the segments back and then, still inside the lock, walks the RAC queue earliest first: the first passenger whose whole "
 "journey now fits a berth is confirmed on it, and his half goes back. Then it walks the waitlist, giving each a berth if one "
 "fits, else an RAC half. A waiter whose journey does not fit is skipped and keeps his place, so a Solapur passenger can be "
 "confirmed ahead of a Mumbai one who needs more of the berth than came back. Each move is an event, told after the unlock; the "
 "second test races a cancel against a newcomer a hundred times, and the waiter gets the berth every time.",
 sl(SRC, "    private void promoteLocked", "    private List<String> statusLocked") + "\n"
 + cut(TST, "        // 5. a waiter whose journey", "        // 7. a group is all or nothing")),

("A family of four: all together or not at all, in one coach, with the grandparents on lower berths.", "twist", 10,
 "All or nothing is in the run: it decides a place for every traveller before writing anything, and if the group does not fit "
 "(berths, RAC and the waitlist's room together) it throws, and not one place was taken. \"Berths only\" is a flag: fewer free "
 "berths than travellers and the booking is refused whole, like IRCTC's option to book only if confirmed berths are allotted. "
 "Which berths is the chooser's job, so the family rule is one new class. It uses one coach when a coach has room for everyone, "
 "gives travellers of sixty and over the lower berths first, then each traveller's own preference, then anything; when there are "
 "fewer berths than travellers, seniors get them first. The run still checks its answer: one entry per traveller, every berth "
 "from the free list, none twice, and no berth left empty while someone would wait.",
 X("a family together") + "\n" + cut(TST, "        // 7. a group is all or nothing", "        // 8. a broken berth rule")),

("Search: trains from Pune to Bengaluru on 3 October, including the one that left Mumbai the night before.", "functional", 10,
 "Adding a train fills an index from station to (train, stop number). Search looks up the trains that stop at Pune, keeps those "
 "that stop at Bengaluru further along the route, and finds each one's run. The date is the day the passenger boards, so for a "
 "train that reaches his station on its second day the run is the one that started the day before: the start date is the "
 "boarding date minus that stop's day offset. Results come back earliest departure first, and no run's lock is taken, so "
 "browsing never slows booking. In SQL (Goldman Sachs asked for the query) it is the train_stop table joined to itself on the "
 "train number, with the boarding stop before the destination, joined to train_run on the computed start date.",
 sl(SRC, "    void addTrain(Train t)", "    TrainRun addRun(") + "\n" + sl(SRC, "    List<Journey> search(", "    Availability availability(String runId")
 + "\n// the same search in SQL: the route joined to itself, then the run that started day_offset days earlier\n"
   "//   SELECT a.train_no, a.time_min AS departs, b.time_min AS arrives\n"
   "//   FROM train_stop a JOIN train_stop b ON b.train_no = a.train_no AND b.seq > a.seq\n"
   "//   JOIN train_run r ON r.train_no = a.train_no AND r.origin_date = :date - a.day_offset\n"
   "//   WHERE a.station_code = :from AND b.station_code = :to\n"
   "//   ORDER BY a.day_offset DESC, a.time_min;\n"),

("The search page shows availability for 40 trains, 10,000 times a second. Keep it fast, and keep it off the booking lock.", "non-functional", 5,
 "It is already fast: a count walks the class's berths once, one word test each, about half a microsecond for 256 berths, so ten "
 "thousand counts a second keep a run's lock about half a per cent busy. When that stops being enough, the next rung is a copy. "
 "Take every berth's 64-bit mask under the lock once, and turn the bitmaps sideways: for each segment, one bit per berth, set "
 "where the berth is free on that segment. The berths free for a journey are then the AND of its segments' rows, and the count "
 "is the number of set bits: four segments times four words, instead of 256 tests, and readers never touch the lock. The test "
 "builds it after the random workload and it agrees with the walk on all ten journeys.",
 sl(SRC, "    Availability availability(String fromStation", "    List<String> status(Pnr p)") + "\n" + X("availability without the walk")),

("The card is declined, or the bank answers after the hold has run out. When exactly is the ticket issued?", "functional", 10,
 "This is BookMyShow's order, reused. <code>book</code> holds the places for ten minutes and returns a PENDING PNR. "
 "<code>pay</code> charges with no lock held, with the PNR as the idempotency key; a decline throws and releases nothing, so the "
 "user can try another card while the hold lasts. <code>commit</code> then takes the lock, releases lapsed holds first, and books "
 "only a PNR that is still PENDING: that is the moment the ticket exists, a BOOKED PNR with its berth numbers (Walmart's "
 "\"after successful payment, generate the ticket with seat allocation\"). If the bank took longer than the hold, the PNR is "
 "already EXPIRED and its berths may belong to a waiter now, so the commit refuses and the money is refunded once. A timeout "
 "leaves the PNR PENDING: a retry reuses the key, and a job that asks the gateway by key settles one nobody retried (the "
 "BookMyShow page has that code).",
 sl(SRC, "    Pnr pay(String pnrId", "    long cancel(String pnrId") + "\n" + sl(SRC, "    boolean commit(Pnr p", "    long cancel(Pnr p, RefundRule rule)")
 + "\n" + cut(TST, "        // 10. the bank answers", "        // 11. the PNR is the idempotency key")),

("A confirmed passenger cancels 30 hours before departure. How much comes back, and who gets the berth?", "functional", 5,
 "Two decisions, made in one locked step in this order. The refund rule runs first, while every passenger's status is still what "
 "it was. The railway's rule, with illustrative amounts, charges a confirmed passenger a flat fee until 48 hours before "
 "departure, a quarter of his fare until 12 hours, half until 4, and everything after; an RAC or waitlisted passenger loses only "
 "a small fixed fee (the railway calls it clerkage). Thirty hours before, the Rs 1,215.20 ticket loses a quarter and Rs 911.40 comes back. Then the segments "
 "go back and the waiters move up in the same step, and the refund goes out after the unlock. A cancelled hold that was never "
 "paid refunds nothing and calls no gateway.",
 sl(SRC, "    long cancel(Pnr p, RefundRule rule)", "    Availability availability(String fromStation") + "\n" + X("the railway's refund rule")),

("One lock per run. What happens at 10:00 when Tatkal opens, and where would a queue like Kafka go?", "non-functional", 5,
 "The arithmetic first: a booking holds the run's lock for about two microseconds, so even five thousand attempts a second on "
 "one hot train keep it one per cent busy; what breaks at 10:00 is everything around the lock, such as the web servers, the "
 "bank and the bots. Goldman Sachs asked where Kafka fits in IRCTC, and this is the honest place: in front of each run, one "
 "partition per run with one consumer, so a run's bookings are applied one at a time in arrival order and the user waits on a "
 "request id, not a lock. The code is that idea inside one process: a worker thread per run and a bounded queue. A full queue "
 "refuses at once and tells the user to try again, which is back-pressure (pushing back on callers instead of queueing without "
 "limit). The test sends ten requests for seven berths through it, and the first seven, in arrival order, get them.",
 X("a queue in front of a run") + "\n" + cut(TST, "        // 21. a queue in front of the run", "        // 22. the database stand-in")),

("Persist it: which tables (payments included), the booking query, and pessimistic or optimistic locking.", "twist", 10,
 "The tables are the classes: station, train, train_stop, coach, train_run, run_berth, pnr, passenger, and payment with its "
 "idempotency key unique, the table a Flipkart candidate forgot. The one table the race touches is run_berth: one row per berth "
 "per run, with a 64-bit column of sold segments, the same bitmap as in memory. Optimistic: one conditional UPDATE sets the "
 "journey's bits only where none is set; one row changed means you got it, zero means someone else did, and a group is one "
 "transaction that rolls back if any row refuses. Pessimistic: lock the run's row with <code>SELECT ... FOR UPDATE</code>, then "
 "read, decide and write, which is the ReentrantLock one layer down. Either way a cancel and its promotions are written in the "
 "same transaction, and no database lock is held across the payment, because the hold is a status and an expiry time on the "
 "PNR row.",
 X("persistence")),

("Now it is flights (Cleartrip's machine-coding round): sectors, fare types each with its own list of seats, and users pay from a wallet.", "twist", 10,
 "A flight flies one sector, so there are no segments: a seat is simply sold or not, and the hard part moves to fare types and "
 "money. Each fare type has a price and its own set of seats. A booking takes the flight's lock, checks every seat is free in "
 "that one fare type, debits the whole price from the wallet, and only then removes the seats; a taken seat or a short wallet "
 "refuses the booking and moves nothing. Cancel puts the seats back and credits the wallet, once. Search looks up the flights on "
 "that sector and date and returns each fare type with at least the asked-for number of seats, earliest first. Money is integer "
 "paise, although the original prompt says \"a decimal number\".",
 sl(EXT, "final class FlightFare", "record Offer") + "\n" + sl(EXT, "    List<Offer> search(String from", "    List<Offer> searchPreferred(")
 + "\n" + sl(EXT, "    String book(String userId, String flightNo", "    void change(String userId")),

("Move a booking to another flight without ever losing the first one (Cleartrip's bonus question).", "twist", 10,
 "A change touches two flights, so it takes two locks, and two locks are where deadlocks come from: if one user moves from 111 to "
 "211 while another moves from 211 to 111, each can hold one lock and wait for the other for ever. So every call takes flight "
 "locks in one fixed order, by key, and the user's wallet last. Inside, every check runs before anything moves: the new seats "
 "are free (his own seats count as free when he stays on the same fare) and the wallet covers the difference. Only then does "
 "the old fare get its seats back and the new one lose them, so a refusal leaves the old booking exactly as it was. The test "
 "swaps two users between the two flights in opposite directions two hundred times each, and fails if either is still waiting "
 "after ten seconds.",
 sl(EXT, "    void change(String userId", "    List<String> bookings(String userId)") + "\n" + cut(TST, "        fd.addUser(\"a\"", "        System.out.println(failures")),

("Where does time come from, and how do you test a hold lapsing and the waitlist moving up without sleeping?", "design", 5,
 "The service hands every run a <code>Clock</code>, a one-method interface, and the run reads it inside the lock. A test hands in "
 "a lambda over a one-element array and moves it. The test holds all eight berths without paying, puts a paid passenger on the "
 "waitlist, and moves the clock to one millisecond before ten minutes: he still waits. At ten minutes exactly the next call "
 "releases both holds and confirms him, with no sweeper running, because every call releases lapsed holds first. The sweeper "
 "exists only so that the SMS goes out within seconds when nobody touches the run for an hour.",
 sl(SRC, "interface Clock", "// \"fares will change") + "\n" + cut(TST, "        // 9. a declined card", "        // 10. the bank answers")
 + "\n" + X("a sweeper")),

("Which pattern is where, and why did each one earn its place?", "design", 5,
 "Each pattern is a line you can point at. Strategy: <code>FareRule</code>, <code>BerthChooser</code> and <code>RefundRule</code> "
 "handed in through <code>configure</code>, and the run builds none. Decorator: <code>PeakDayFare</code> holds a base rule and "
 "scales what it returns, so Tatkal and flexi-fare stack the same way. Observer: <code>publish</code> runs after "
 "<code>lock.unlock()</code> and wraps each listener in a catch, so a dead SMS gateway cannot stop a promotion. State: two status "
 "enums and a fixed promotion order, so a passenger only ever moves up. Two are absent on purpose: no Factory, because coaches "
 "arrive already built, and no Singleton, because <code>main</code> builds one service and every test builds its own.",
 sl(SRC, "interface FareRule", "/** The base rule") + "\n" + sl(SRC, "final class PeakDayFare", "// \"the family wants") + "\n"
 + sl(SRC, "    private void publish(", "final class BookingService").rstrip().rstrip("}").rstrip() + "\n"),

("Which SOLID letter is where in this code?", "design", 5,
 "Not one of them was aimed at; each is a line a move already produced. S: a <code>Berth</code> changes only when its bits do, a "
 "<code>TrainRun</code> when its places and queues do, the <code>BookingService</code> when the order of steps does. O: Tatkal, "
 "flexi-fare, the family chooser and the railway refund were four new classes and no edit to the run. L: the run calls "
 "<code>fare.farePaise(...)</code> and never asks which rule it got. I: every interface has one method, so a declining bank is "
 "four lines in a test. D: the service is handed its clock, its rules and its gateway, which is why the tests can move time and "
 "fail payments.",
 sl(SRC, "    void configure(FareRule fare", "    void addObserver(") + "\n" + sl(SRC, "interface BerthChooser", "/** The default: the first free")
 + "\n" + sl(SRC, "interface RefundRule", "/** The default: everything back") + "\n" + cut(SRC, "    static PaymentGateway declining()", None).rstrip().rstrip("}").rstrip() + "\n"),

("Enums for the class and the berth type, or subclasses? And where would a Factory pay?", "design", 3,
 "Enums, until a kind gains behaviour of its own. Travel classes differ only in their rate and their layout, so a class is a row "
 "in the fare table; berth types differ only in position, so a type is a value the chooser reads. A class with rules of its own "
 "(a chair car sold by the seat with window and aisle, a first-class coupe sold as a whole cabin) is behaviour, and that is when "
 "a coach-layout subclass pays. A Factory earns its place when layouts arrive as configuration: eight berths a bay in sleeper "
 "and 3A, six in 2A, rows of five in a chair car. A registry from a layout name to a builder then makes a new coach type one "
 "registration instead of one more case in a growing switch.",
 "// data, not classes: a travel class is a row, a berth type is a position in the bay\n"
 + cut(SRC, "    private static final Map<TravelClass, Long> PER_KM", "    /** Rate times")
 + cut(SRC, "    private static final BerthType[] BAY", "    private static final AtomicLong PNR_SEQ")
 + "\n// a sketch: a factory once layouts come from configuration, so a new coach type is one registration\n"
   "Map<String, BiFunction<String, Integer, List<Berth>>> layouts = Map.of(\n"
   "    \"SL\", (coachId, bays) -> bays(coachId, bays, BAY),        // eight a bay\n"
   "    \"2A\", (coachId, bays) -> bays(coachId, bays, TWO_TIER),   // six a bay: no middle berths\n"
   "    \"CC\", (coachId, rows) -> seats(coachId, rows, 5));        // a chair car: rows of five seats\n"
   "List<Berth> berths = layouts.get(coach.layout()).apply(coach.id(), coach.bays());\n"),
]

# ranked by how often India-hiring companies ask them (research/train-booking.md): race, search, tables, segments, flights,
# RAC and the waitlist, cancel, availability, a family, changing a flight, payment, fares, Tatkal; then the design questions
FU = [FU[i] for i in [1, 5, 10, 2, 11, 3, 8, 6, 4, 12, 7, 0, 9, 13, 14, 15, 16]]

# ============================================================ build
build(dict(
    slug="train-booking",
    title="Train and Flight Seat Booking",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 23 failure tests (93 checks), two 50-thread races and a model check pass",
    problem_body=PROBLEM_BODY,
    derivation_lead=DER_LEAD,
    moves=MOVES,
    uml_svg=UMLSVG,
    how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", SRC), ("Extensions.java", EXT), ("FailureTests.java", TST)],
    test_class="FailureTests",
    followups=FU,
    implement_card_html=IMPLEMENT,
))
