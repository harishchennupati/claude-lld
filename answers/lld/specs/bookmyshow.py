# Movie ticket booking (BookMyShow) LLD workbench.
# problem -> twelve moves, each a picture -> the class diagram -> the whole code -> follow-ups and practice.
import sys, pathlib
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

SRC = (H / "bookmyshow/Main.java").read_text()
EXT = (H / "bookmyshow/Extensions.java").read_text()
TST = (H / "bookmyshow/FailureTests.java").read_text()

def cut(src, a, b=None):
    """raw slice between two exact markers, keeping the first marker's line"""
    i = src.index(a)
    i = src.rfind("\n", 0, i) + 1
    j = src.index(b, i) if b else len(src)
    return src[i:j].rstrip() + "\n"

def X(a, b):
    """one '// ---- ext:' block of Extensions.java"""
    import re as _re
    marks = [m.start() for m in _re.finditer(r"(?m)^// ---- ext:", EXT)] + [EXT.index("/** Runs every extension")]
    i = next(m for m in marks if a in EXT[m:m + 160])
    j = next(m for m in marks if m > i)
    return EXT[i:j].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ problem page pictures

# what the code must do: hold, then pay-and-confirm, with the seat map as a line
pf = _D
rows = [("hold", 30, [("a user picks seats", "B3 and B4 at the 6pm show"),
                      ("is every one of them free?", "a lapsed hold counts as free"),
                      ("mark them all HELD", "by this booking, for five minutes"),
                      ("a booking, PENDING", "its seats and its amount, frozen")]),
        ("pay &amp; confirm", 165, [("charge the card", "no lock; keyed by the booking id"),
                      ("still ours, still in time?", "re-checked under the lock"),
                      ("mark them all SOLD", "the booking is CONFIRMED"),
                      ("the SMS, the analytics", "after the lock is released")])]
for lab, y, boxes in rows:
    pf += _tx(80, y + 31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k * 270
        pf += _bx(x, y, 250, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x + 250, y + 27, x + 270), True)
pf += _ar("M545 84 V95", dash=True) + _bx(420, 95, 250, 40, "one seat taken: nothing is held", "", dash=True)
pf += _ar("M545 219 V230", dash=True) + _bx(385, 230, 320, 40, "the hold lapsed: refund, refuse", "", dash=True)
pf += _tx(80, 296, "seat map", "var(--acc)", 13)
pf += _tx(150, 296, "at any moment, without scanning the screen: is B4 free at the 9pm show?  how many gold seats are left?", "var(--text)", 12, "start")
pf += _tx(80, 324, "cancel", "var(--acc)", 13)
pf += _tx(150, 324, "seats back on sale under the lock, the money back outside it, the listeners last: nothing is ever left half-given-back", "var(--text)", 12, "start")
pf += _tx(615, 358, "many phones hit the same show at the same instant: one chair must never become two tickets, and a failed payment must leave nothing half-done", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 373, pf)

# one evening, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("18:41:02  asha taps B4", ["B4 at the 6pm show is AVAILABLE", "held for her until 18:46:02", "booking BK7, PENDING, Rs 250.00", "gold free: 5 of 6"], True),
      ("18:41:02.000  raj taps B4", ["the same millisecond, another phone", "the show's lock lets exactly one in", "raj is told: seat B4 is HELD", "nothing was half-written"], False),
      ("18:43:10  asha's card clears", ["the gateway took 1.4 s, no lock held", "re-check: still hers, 2m52s left", "only now: B4 SOLD, BK7 CONFIRMED", "the SMS goes out after the unlock"], True),
      ("18:46:03  meena taps C1", ["C1 was held by a card that declined", "that hold died three seconds ago", "no sweeper ran: her hold reclaims it", "meena holds C1, booking BK9"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k * 290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x + 125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x + 125)
    pe += _card(x, 60, 250, 110, t, lines, acc=acc)
P_EX = _mv(1230, 185, pe)

# ============================================================ derivation move pictures
MV = {}

# 1: the nouns, and the split that decides everything
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a USER picks a SHOW (a MOVIE on a SCREEN at a TIME), reads the SEAT MAP, HOLDS SEATS for a few minutes, PAYS, gets a BOOKING", "var(--text)", 12.5)
for k, (t, sub, acc) in enumerate([("Seat", "row, number, class", 1), ("Screen", "its fixed seat layout", 1),
                                   ("Show", "its seats, its lock", 1), ("ShowSeat", "status, holder, expiry", 1),
                                   ("Booking", "seats, amount, status", 1), ("seat map", "a question: a method", 0)]):
    x = 25 + k * 200
    m1 += _bx(x, 110, 180, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + 90))
m1 += _tx(615, 186, "solid = has its own state, becomes a class.   dashed = no state of its own: a caller or a method", "var(--muted)", 11)
m1 += _tx(615, 208, "the split that decides the whole design: a SEAT is a chair and has no status; a SHOW SEAT is that chair at one show, and that is where the status lives", "var(--acc)", 11.5)
MV[1] = _mv(1230, 222, m1)

# 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("is this seat free right now?", "ShowSeat  (owns status and expiry)", "ss.freeAt(now)"),
                                       ("hold these seats, all or nothing", "Show  (owns the seats, the bookings, the lock)", "show.hold(user, ids, pricing)"),
                                       ("charge the card", "PaymentProcessor  (owns no state here)", "pay.charge(bookingId, paise)"),
                                       ("sell the seats we still hold", "Show  (the same state, the same lock)", "show.commit(booking, ref)")]):
    y = 20 + k * 54
    m2 += _bx(30, y, 340, 44, verb, "the verb") + _ar("M370 %s H410" % (y + 22), True)
    m2 += _bx(410, y, 420, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H870" % (y + 22), True)
    m2 += _bx(870, y, 330, 44, meth, "the method")
m2 += _tx(615, 256, "a verb whose state is spread over many seats goes to the class that owns them all: the show. A verb that owns nothing, like charging a card, is handed in and runs outside the lock.", "var(--muted)", 11)
MV[2] = _mv(1230, 268, m2)

# 3: rules -> one-method interfaces handed in
m3 = _D + _bx(30, 75, 230, 110, "BookingService", "configure(pricing, policy)", acc=True)
for k, (t, sub, impls) in enumerate([("PricingRule", "class rate today, surge tomorrow", "ClassPricing / WeekendSurge / Demand"),
                                     ("SeatPolicy", "any free seat, or three together", "AnyFreeSeats / AdjacentSeats"),
                                     ("PaymentProcessor", "UPI, card, wallet; it can say no", "UpiPayment / CardPayment"),
                                     ("BookingObserver", "SMS, analytics, a data pipe", "SmsNotifier / Analytics")]):
    y = 20 + k * 58
    m3 += _ar("M260 130 H330 V%s H400" % (y + 22), True, True) + _bx(400, y, 330, 44, t, sub, dash=True)
    m3 += _bx(770, y, 430, 44, impls, "the classes that can be handed in") + _ar("M770 %s H730" % (y + 22))
m3 += _tx(615, 266, "dashed green = handed in: two rules through configure(), listeners through addObserver(), the gateway at confirm() time. The service builds none", "var(--muted)", 11)
MV[3] = _mv(1230, 280, m3)

# 4: the gap between reading and writing
m4 = _D + _bx(30, 30, 170, 44, "phone 1", "reads: B4 free") + _bx(30, 110, 170, 44, "phone 2", "reads: B4 free")
m4 += _bx(330, 70, 190, 44, "ShowSeat B4", "AVAILABLE", acc=True)
m4 += _ar("M200 52 H330 V70") + _ar("M200 132 H330 V114") + _tx(260, 40, "read", "var(--muted)", 10.5) + _tx(260, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="545" y="20" width="300" height="140" rx="6" fill="none" stroke="#f38ba8" stroke-dasharray="4 3"/>'
m4 += _tx(695, 45, "the gap", "#f38ba8", 12) + _tx(695, 70, "both saw AVAILABLE, both write HELD:", "#f38ba8", 11) + _tx(695, 90, "one chair, two tickets", "#f38ba8", 11)
m4 += _tx(695, 130, "fix: check and take as ONE step, one lock", "var(--text)", 11)
m4 += _bx(875, 40, 325, 100, "Show.lock", "check all + hold all = one step", acc=True)
m4 += _tx(615, 180, "the lock lives where the shared state lives: on the show, not on the service and not on the seat", "var(--muted)", 11)
m4 += _tx(615, 200, "the clock is read INSIDE the lock too, so two callers can never disagree about whether a hold has lapsed; listeners are called after the unlock", "var(--muted)", 11)
MV[4] = _mv(1230, 214, m4)

# 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, sub, cost) in enumerate([("is seat B4 free in THIS show?", "Map&lt;seatId, ShowSeat&gt;  on the show", "screen order, so 'adjacent' means what it says", "O(1)"),
                                           ("which booking is BK7?", "Map&lt;bookingId, Booking&gt;  on its show", "plus Map&lt;bookingId, Show&gt; on the service: which show", "O(1)"),
                                           ("how many gold seats are left?", "Map&lt;SeatClass, Integer&gt;  a counter", "moved by one at every hold, release and cancel", "O(1)"),
                                           ("which seats does BK7 hold?", "Booking.seats: the list, frozen at hold", "confirm can never reprice or drop one", "O(1), no search"),
                                           ("three gold seats together?", "walk the show's seats once, keep the free gold ones", "the only walk on the booking path: ~1 us for 300 seats", "O(seats on screen)")]):
    y = 20 + k * 50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H440" % (y + 20), True)
    m5 += _bx(440, y, 560, 40, shape, sub, acc=True) + _ar("M1000 %s H1030" % (y + 20), True)
    m5 += _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 290, "every scan avoided here is a scan avoided INSIDE the lock, which is the only place a scan would have cost anybody anything", "var(--muted)", 11)
MV[5] = _mv(1230, 303, m5)

# 6: two state machines and the order at the critical step
m6 = _D + _tx(30, 26, "ShowSeat", "var(--acc)", 12.5, "start")
m6 += _bx(30, 34, 160, 44, "AVAILABLE", "nobody has it") + _bx(330, 34, 160, 44, "HELD", "one booking, until t", acc=True) + _bx(630, 34, 160, 44, "SOLD", "paid for", acc=True)
m6 += _ar("M190 56 H330", True) + _tx(260, 48, "hold: all or nothing", "var(--muted)", 10)
m6 += _ar("M490 56 H630", True) + _tx(560, 48, "commit: re-checked", "var(--muted)", 10)
m6 += _ar("M410 78 V104 H110 V78", dash=True) + _tx(260, 118, "the hold lapses, or is released", "var(--muted)", 10)
m6 += _ar("M710 78 V136 H110 V78", dash=True) + _tx(430, 150, "cancelled: back on sale, money back", "var(--muted)", 10)
m6 += _tx(30, 178, "Booking", "var(--acc)", 12.5, "start")
m6 += _bx(30, 190, 160, 44, "PENDING", "seats only held") + _bx(330, 190, 160, 44, "CONFIRMED", "paid and sold", acc=True)
m6 += _bx(630, 186, 160, 40, "CANCELLED", "given back") + _bx(630, 246, 160, 40, "EXPIRED", "the hold died")
m6 += _ar("M190 212 H330", True) + _tx(260, 204, "paid AND still ours", "var(--muted)", 10)
m6 += _ar("M110 234 V266 H630", dash=True) + _tx(370, 260, "the hold lapsed, or was released", "var(--muted)", 10)
m6 += _ar("M490 206 H630", dash=True) + _tx(560, 198, "cancelled", "var(--muted)", 10)
m6 += '<rect x="830" y="20" width="370" height="298" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(1015, 44, "the order, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  lock: is every seat free?  then all HELD", "2  UNLOCK. charge, key = the booking id",
                       "3  lock: still HELD by us, not expired?", "     only then SOLD, booking CONFIRMED",
                       "a decline releases nothing: the hold just", "runs out and the seat comes back by itself",
                       "a hold that lapsed at step 3: refund, refuse", "a retry or a double tap: same key, one charge",
                       "no answer from the gateway: confirm nothing,", "release nothing; retry, or ask by the key"]):
    m6 += _tx(845, 68 + k * 24, l, "var(--text)" if k < 4 else "var(--muted)", 11, "start")
m6 += _tx(615, 340, "two little state machines and one rule: nothing is committed before the money has moved, and nothing is trusted across the gap where the lock was not held", "var(--muted)", 11)
MV[6] = _mv(1230, 354, m6)

# 7: what is inside the lock, and two hundred phones at once
m7 = _D + _card(30, 20, 540, 160, "inside the show's lock: about 2 microseconds",
                ["look up three seat ids in a map", "read three statuses and three expiry stamps",
                 "price three seats: three table lookups", "write status, holder and expiry on three seats",
                 "put the booking in a map, move one counter"], acc=True)
m7 += _ar("M570 100 H640", True) + _tx(605, 90, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 160, "outside the lock: milliseconds to seconds",
            ["the payment gateway: about 1,500,000 us", "the SMS and the analytics pipe: after the unlock",
             "drawing the seat map: after a short locked read", "the user choosing where to sit: 30 seconds",
             "nothing slow is ever inside: that is the whole trick"])
m7 += _tx(615, 210, "two hundred phones press on the same hot show at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k * 118
    m7 += _bx(x, 224, 106, 40, "phone %d" % (k + 1), "waits %s us" % ("0" if k == 0 else "%.0f" % (k * 2)), acc=(k == 9))
m7 += _tx(615, 292, "the tenth phone waits eighteen microseconds for the lock, then spends a second and a half at the gateway with the lock long released: one at a time is true, and nobody can tell", "var(--muted)", 11)
MV[7] = _mv(1230, 305, m7)

# 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one lock per show: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["locked part of a three-seat hold: ~2 us; of a confirm: ~1 us",
                       "a blockbuster's hot show at peak: ~200 hold attempts a second",
                       "200 x 2 us = 400 us of lock in every 1,000,000 us: busy 0.04%",
                       "about one request in 2,500 waits, and it waits two microseconds",
                       "put the 1.5 s gateway INSIDE and the show does 0.67 bookings a second"]):
    m8 += _tx(35, 66 + k * 24, l, RED if k == 4 else "var(--muted)", 11, "start")
m8 += _tx(880, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 lock-free reads of the seat map", "volatile fields + a snapshot: the display never takes the show's lock"),
                              ("2 compare-and-set per seat", "holder null &#8594; booking id, in seat-id order; roll back on a refusal"),
                              ("3 move the hold out of the process", "SET seat bookingId NX PX 300000: the only rung that survives four servers")]):
    m8 += _bx(600, 58 + k * 50, 600, 42, t, sub, acc=(k == 0))
m8 += _tx(615, 222, "say the arithmetic first: every rung costs code, and two of these three are only worth it once a number says so", "var(--muted)", 11)
MV[8] = _mv(1230, 236, m8)

# 9: what can go wrong, and the test for each
m9 = _D
for k, (t, sub, fix) in enumerate([("two phones, one seat", "one chair, two tickets", "check all and take all under one lock; test: 50 threads, one latch, exactly one hold"),
                                   ("the card is declined", "the seat is lost, or wrongly freed", "release nothing; the hold runs out; test: decline, then the seat returns at expiry"),
                                   ("the gateway outlives the hold", "the seat is sold twice", "re-check the hold under the lock; test: a gateway that moves the clock past expiry"),
                                   ("a retry, or two taps on Pay", "charged twice", "the booking id is the idempotency key; test: two taps at once, one charge, no refund"),
                                   ("the SMS gateway throws", "the booking dies with it", "publish after the unlock, inside a catch; test: a listener that always throws"),
                                   ("three together, none free", "half a booking", "choose and take in one locked section; test: nothing held after the refusal"),
                                   ("the gateway never answers", "money gone, seat gone, nobody knows", "confirm nothing, release nothing, settle from the gateway later; test: a timeout, then a settle")]):
    y = 24 + k * 46
    m9 += _bx(30, y, 300, 40, t, sub) + _ar("M330 %s H380" % (y + 20), True) + _bx(380, y, 820, 40, fix, "", acc=True)
m9 += _tx(615, 368, "every claim here has a test: FailureTests.java runs these seven plus the cancel, the refunds, the cap, the webhook and the edges -- 53 checks; it must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 382, m9)

# 10: the patterns, named after the fact
cols = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 830)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface PricingRule { long pricePaise(Show, Seat); }  via configure()", None), ("swap a rule without opening the show", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("WeekendSurgePricing(base): base.pricePaise(...) x 1.5 on a weekend show", None), ("add to a rule instead of copying it", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(event, booking) after the unlock; SmsNotifier, Analytics listen", None), ("the user hears; the show never learns what SMS is", None)],
          [("State", "var(--text)"), ("move 6", None), ("SeatStatus + BookingStatus, and the order hold, pay, re-check, sell", None), ("an illegal move cannot happen", None)],
          [("Factory", "var(--muted)"), ("not yet", None), ("screens arrive built; it pays when a layout is read from a file", "var(--muted)"), ("say 'not yet, and here is what would make me'", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("never here", None), ("main builds one BookingService and hands it out; tests build their own", "var(--muted)"), ("one global is one test you cannot write", "var(--muted)")],
          [("Builder, Command, Template", "var(--muted)"), ("never", None), ("no move produced them", "var(--muted)"), ("a pattern without a move is decoration", "var(--muted)")]]
m10 = _D + _table(20, 20, cols, rows10, rowh=30, widths=1190)
m10 += _tx(615, 275, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 290, m10)

# 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 555)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("ShowSeat: its own status. Show: its seats, its lock, the order. BookingService: the sequence.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("weekend surge = one new class and one changed configure() line", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("total += pricing.pricePaise(this, ss.seat);  never 'is it the surge one?'", None)],
          [("I", "var(--acc)"), ("small interfaces, so a fake for a test is one line", None), ("move 3", None), ("PricingRule, SeatPolicy, Clock, BookingObserver: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("new Show(..., () -&gt; now[0], holdMs);   svc.confirm(id, a gateway that declines)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# 12: every twist is one of five moves
m12 = _D
tw = [("a new rule", "surge, demand, a coupon, best-available", "a new class behind the existing interface + one configure line", "", "move 3"),
      ("someone new wants to know", "SMS, analytics, the big screen in the lobby", "one more observer; the booking path does not change a line", "", "move 3"),
      ("a new step in a life", "a partial cancel, a refund still pending", "a new state, and the one method that moves a booking into it", "", "move 6"),
      ("a new invariant across seats", "three seats must be next to each other", "choose AND take inside the SAME locked section: all or nothing", "", "move 4"),
      ("state that must outlive the process", "persist it; four app servers", "the maps behind a repository, and the hold becomes a conditional UPDATE", "UPDATE show_seat SET status='HELD' WHERE seat=? AND status='AVAILABLE': the database's compare-and-set", "move 5 + this one")]
for k, (t, sub, fix, fsub, mv) in enumerate(tw):
    y = 24 + k * 54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y + 22), True) + _bx(420, y, 660, 44, fix, fsub, acc=True) + _tx(1150, y + 27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the order hold, pay, sell never changes: each adds a class, a listener, a state or a step inside the lock", "var(--muted)", 11)
MV[12] = _mv(1230, 326, m12)

# ============================================================ UML
uml_reset()
# left column: the callers, the listeners, the injected clock, and the catalog that never changes
put("checkout", 10, 20, 225, "Checkout / kiosk", ["svc: BookingService"], ["pay pressed &rarr; hold()", "gateway returned &rarr; confirm()"])
put("obs", 10, 150, 225, "BookingObserver", [], ["onBooking(event, booking)"], "interface")
put("listeners", 10, 245, 225, "SmsNotifier | Analytics", [], ["onBooking(...) &rarr; send / count"])
put("clock", 10, 330, 225, "Clock", [], ["nowMs(): long"], "interface")
put("theatre", 10, 420, 225, "Theatre", ["id, city: String", "screens: List&lt;Screen&gt;"], [])
put("screen", 10, 520, 225, "Screen", ["id: String", "seats: List&lt;Seat&gt;"], [])
put("seat", 10, 620, 225, "Seat", ["id, row: String", "number: int", "seatClass: SeatClass", "no status lives here"], [])
put("sclass", 10, 750, 225, "SeatClass", ["SILVER, GOLD, PLATINUM"], [], "enum")
# centre column: the orchestrator, the aggregate root, and the seat it owns
put("svc", 300, 20, 320, "BookingService", ["shows: Map&lt;id, Show&gt;", "byBooking: Map&lt;bookingId, Show&gt;", "pricing: PricingRule", "policy: SeatPolicy", "observers: List&lt;BookingObserver&gt;"],
    ["configure(pricing, policy)", "hold(show, user, seatIds): Booking", "holdBest(show, user, class, n)", "confirm(bookingId, pay): Booking", "cancel(bookingId, pay) / release(id)"])
put("show", 300, 280, 320, "Show", ["id, movie: String", "screen: Screen", "startMs: long", "seats: Map&lt;seatId, ShowSeat&gt;", "bookings: Map&lt;id, Booking&gt;", "free: Map&lt;SeatClass, Integer&gt;", "lock: ReentrantLock", "clock: Clock,  holdMs: long"],
    ["hold(user, ids, pricing): Booking", "holdBest(user, class, n, policy, ..)", "commit(booking, ref): boolean", "release(b): boolean / cancel(b): long", "freeCount(class) / statusOf(id)", "seatMap() / sweepExpired()"])
put("showseat", 300, 640, 320, "ShowSeat", ["seat: Seat", "status: SeatStatus", "holdBookingId: String", "holdExpiresMs: long"], ["freeAt(now): boolean"])
# middle-right column: the booking and the two state enums, each under the class it belongs to
put("booking", 655, 340, 235, "Booking", ["id, userId: String", "show: Show", "seats: List&lt;ShowSeat&gt;", "amountPaise: long", "holdExpiresMs: long", "status: BookingStatus", "paymentRef: String"], [])
put("bstatus", 655, 530, 235, "BookingStatus", ["PENDING, CONFIRMED,", "CANCELLED, EXPIRED"], [], "enum")
put("sstatus", 655, 640, 235, "SeatStatus", ["AVAILABLE, HELD, SOLD"], [], "enum")
put("errors", 655, 748, 290, "the three exceptions", [], ["SeatUnavailable &mdash; a seat was taken",
    "HoldLapsed &mdash; the hold died first", "PaymentDeclined &mdash; the card said no"])
# right column: the rules that get handed in, each with its implementations
put("pricing", 950, 20, 250, "PricingRule", [], ["pricePaise(show, seat): long"], "interface")
put("classp", 950, 110, 250, "ClassPricing", ["RATE: Map&lt;SeatClass, Long&gt;"], ["pricePaise &rarr; RATE[class]"])
put("surge", 950, 215, 250, "WeekendSurgePricing", ["base: PricingRule"], ["pricePaise &rarr; base x 1.5"])
put("policy", 950, 330, 250, "SeatPolicy", [], ["choose(free, n): List&lt;ShowSeat&gt;"], "interface")
put("policies", 950, 420, 250, "AnyFreeSeats | AdjacentSeats", [], ["choose &rarr; first n | n in a row"])
put("pay", 950, 530, 250, "PaymentProcessor", [], ["charge(key, paise): String ref", "refund(ref, paise)"], "interface")
put("pays", 950, 650, 250, "UpiPayment | CardPayment", [], ["charge(key, ..) &rarr; one ref per key"])

edges = [
    ln(B["listeners"]["t"], B["obs"]["b"], "inherit"),
    ln(B["classp"]["t"], B["pricing"]["b"], "inherit"),
    ln((B["surge"]["t"][0] - 60, B["surge"]["t"][1]), (B["pricing"]["b"][0] - 60, B["pricing"]["b"][1]), "inherit"),
    ln(B["surge"]["l"], (B["pricing"]["l"][0] - 15, B["pricing"]["l"][1] + 12), "assoc", "", [(B["pricing"]["l"][0] - 15, B["surge"]["l"][1])]),
    ln(B["policies"]["t"], B["policy"]["b"], "inherit"),
    ln(B["pays"]["t"], B["pay"]["b"], "inherit"),
    # the catalog, top to bottom on the left
    ln(B["theatre"]["b"], B["screen"]["t"], "compose", "1..*"),
    ln(B["screen"]["b"], B["seat"]["t"], "compose", "1..*"),
    ln(B["seat"]["b"], B["sclass"]["t"], "assoc"),
    # the spine: service owns shows, a show owns one ShowSeat per chair and its bookings
    ln(B["svc"]["b"], B["show"]["t"], "compose", "shows"),
    ln(B["show"]["b"], B["showseat"]["t"], "compose", "one per chair"),
    ln(B["show"]["r"], B["booking"]["l"], "compose"),
    ln(B["showseat"]["l"], B["seat"]["r"], "assoc"),
    ln((300, 540), (235, 540), "assoc", "layout"),
    ln((235, 357), (300, 357), "inject", "injected"),
    # a booking points at its show seats; each state enum sits under its own class
    ln((655, 460), (620, 730), "assoc", "", [(637, 460), (637, 730)]),
    ln(B["booking"]["b"], B["bstatus"]["t"], "assoc"),
    ln((620, 715), (772, 690), "assoc", "", [(772, 715)]),
    # the rules, handed in through configure()
    ln((620, 88), B["pricing"]["l"], "inject", "injected", [(936, 88), (936, B["pricing"]["l"][1])]),
    ln((620, 112), B["policy"]["l"], "inject", "", [(920, 112), (920, B["policy"]["l"][1])]),
    ln((620, 136), B["pay"]["l"], "inject", "", [(908, 136), (908, B["pay"]["l"][1])]),
    ln((300, 177), (235, 177), "notify", "notifies"),
    ln((235, 65), (300, 65), "assoc", "calls"),
    '<text x="643" y="622" font-size="10.5" fill="var(--muted)">seats</text>',
    '<text x="800" y="858" text-anchor="middle" font-size="10.5" fill="var(--muted)">all three extend RuntimeException; none of them leaves a seat half-taken</text>',
]
UMLSVG = uml_svg(1230, 920, edges, legend_y=893)

# ============================================================ page 1: the problem
REQ = ('<div class="req"><div><b>Functional requirements</b><ul>'
       '<li>A show is one movie, on one screen, at one time; its seats are its own.</li>'
       '<li>Hold: take one or more named seats for a few minutes, all of them or none.</li>'
       '<li>Pay, then confirm: the seats become sold only after the money moved.</li>'
       '<li>A hold that is not confirmed in time dies, and the seats come back.</li>'
       '<li>Cancel a confirmed booking: the seats go back on sale and the money goes back.</li>'
       '<li>Price by seat class, and changeable (weekends cost more) without touching the flow.</li>'
       '<li>"Three seats together" as well as "these three seats".</li>'
       '<li>Answer "is B4 free at the 9pm show?" and "how many gold seats are left?"</li></ul></div>'
       '<div><b>Non-functional requirements</b><ul>'
       '<li>Many phones on one show at the same time: one chair is never two tickets.</li>'
       '<li>Nothing half-done: a declined card leaves the state exactly as it was; a retried payment is charged once.</li>'
       '<li>Seat lookup, a hold of named seats and the free count are O(1) per seat; only "three together" walks the screen, once.</li>'
       '<li>Pricing, seat choice and payment swappable without changing the core.</li>'
       '<li>One source of truth for a seat at a show: its ShowSeat, under its show\'s lock.</li>'
       '<li>Money is integer paise. A double loses fractions of a rupee across a sum.</li>'
       '<li>In memory, one process, no database (say it; a follow-up adds one).</li></ul></div></div>')

PROMPT = ('"Design the booking part of BookMyShow. A user picks a show, picks seats, gets a few minutes to pay, and the '
          'seats must not be sold to anybody else in the meantime. Two people will tap the same seat at the same moment. '
          'I want working code, not a diagram. Go."')

PROBLEM_BODY = (
    '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
    '<div class="move"><h3>The problem, in plain words</h3><p>A cinema chain sells seats for shows. A <b>show</b> is one movie, '
    'on one screen, at one time: the 6pm and the 9pm show use the same physical chairs but sell them separately. A user opens '
    'a show, sees which seats are free, picks some, and the system must take those seats off the market for a few minutes while '
    'the user pays. If the payment goes through, the seats are sold; if it fails or the user walks away, the seats come back '
    'on sale by themselves. Hundreds of phones hit a popular show in the same second. So the rule that must always hold '
    '(the invariant) is this: one chair at one show never becomes two tickets, and a group booking is all of its seats or '
    'none of them.</p></div>'
    '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a '
    '<code>main</code> that books a seat end to end and a race that proves the invariant. The interviewer is watching for, in '
    'this order: the questions you ask before typing; which classes exist and which one owns which state (and whether you '
    'split the chair from the chair-at-a-show); hold, pay and confirm working end to end; what happens when two phones tap '
    'the same seat in the same millisecond; where the rules that will change (price, which seats, how to pay) live, so a '
    'change is a new class and not an edit; and what happens when the card is declined or the gateway is slower than your '
    'hold. Then the twists: surge pricing, three seats together, a sweeper, a waitlist, the database tables, four app '
    'servers, a webhook (the gateway calling back to report a payment) that arrives three times, and a gateway that never '
    'answers at all.</p></div>'
    '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
    '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
    '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
    '<tr><td>Do users hold seats and then pay, or is it booked on the click?</td><td>Hold with a five-minute window, then pay</td><td>The HELD state, the expiry, and the order hold, pay, sell (moves 4, 6)</td></tr>'
    '<tr><td>Can the same chair be sold at two different shows?</td><td>Yes: availability belongs to the show, not the chair</td><td>Seat splits into Seat and ShowSeat (move 1)</td></tr>'
    '<tr><td>One process, or several app servers?</td><td>One, in memory, today</td><td>A ReentrantLock per show; a follow-up moves it out (moves 4, 12)</td></tr>'
    '<tr><td>Is payment real, and can it fail or be slow?</td><td>Mocked behind an interface; it can decline and can take seconds</td><td>Payment outside the lock, and the re-check inside it (move 6)</td></tr>'
    '<tr><td>How is a seat priced?</td><td>A flat rate per seat class; weekends cost more</td><td>Pricing behind an interface, surge as a wrapper (move 3)</td></tr>'
    '<tr><td>Must a group of seats be together, and is it all-or-nothing?</td><td>All-or-nothing always; together only if asked</td><td>Two passes under one lock, and a seat policy (moves 3, 4)</td></tr>'
    '<tr><td>Are cancellation and refunds in scope?</td><td>Cancel yes; a full refund today, a tiered one as a follow-up</td><td>The CANCELLED state, refund on the payment interface, a refund policy on page 05 (move 6)</td></tr>'
    '<tr><td>Search, seat maps, waitlists, analytics?</td><td>Out of scope for the hour, but named aloud</td><td>Each is one of the five twist moves, with code on page 05 (move 12)</td></tr></table></div>'
    '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ +
    '<div class="move"><h3>One evening, replayed</h3></div>' + P_EX +
    '<div class="grade"><b>Say before typing:</b> one process, in memory; a chair has no status, a chair-at-a-show does; a hold '
    'lasts five minutes and dies on its own; money is integer paise; a group is all its seats or none. Named as out of scope: '
    'search and the catalog, seat maps at scale, waitlists, partial refunds, the database, four app servers; each is a follow-up '
    'on page 05.</div>')

# ============================================================ page 2: the twelve moves
DER_LEAD = ('Run these twelve on any LLD and the class diagram, the lock, the tests, the patterns, SOLID and the answer to '
            'every twist fall out in that order. Nothing is chosen up front, and no pattern is named before the move that '
            'produced it. For this problem the first move is the one that decides everything: one of the nouns splits in two.')

MOVES = [
("Move 1: underline the nouns, and watch one of them split in two.",
 "Reading the prompt again: a <b>user</b> opens a <b>show</b> (a <b>movie</b> on a <b>screen</b> at a <b>time</b>), reads the "
 "<b>seat map</b>, holds some <b>seats</b>, <b>pays</b>, and gets a <b>booking</b>. Screen has a fixed layout: a class. Seat has "
 "a row, a number and a class: a class. Show has its own time and its own inventory: a class. Booking has seats, an amount and a "
 "status: a class. The user is a caller, so it is a string id, not a model, and the seat map is a question I answer, so it is a "
 "method. Then the move that decides the whole design: is a seat free? That cannot be a field on <code>Seat</code>, because the "
 "same chair is free at 6pm and sold at 9pm and one boolean would make those two shows fight over one field. So <b>Seat</b> "
 "splits: the chair stays immutable and shared, and a new class <b>ShowSeat</b> holds the status of that chair at one show. "
 "Every other decision on this page rests on that line.", 1),

("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Is this seat free right now\" reads a status and an expiry stamp, both on the show seat, so <code>showSeat.freeAt(now)</code>. "
 "\"Hold these three seats, all or nothing\" touches three show seats, the bookings map and the free counts at once; only the "
 "show sees all of them, so <code>show.hold(user, ids, pricing)</code>. \"Charge the card\" touches none of our state at all, so it "
 "is handed in and called by the orchestrator, not by the show. The orchestrator is BookingService: it runs the steps in order "
 "and owns no seat state. \"Sell the seats we still hold\" touches the same state as the hold, "
 "so it is the same class and the same lock: <code>show.commit(booking, ref)</code>. A verb whose state is spread over many "
 "objects goes to the class that owns them all; that is how a small ShowSeat and one busy Show appear without planning them.", 2),

("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Price will change: flat per class today, one and a half times on weekends tomorrow, demand-based the round after. Which seats "
 "to hand out will change: any free ones today, three together tomorrow. How to pay will change: UPI, card, wallet, and it can say "
 "no. Who must be told will change: the user, then analytics, then the screen in the lobby. Each becomes a small interface the "
 "service is <i>given</i> and never builds: pricing and seat choice through <code>configure()</code>, the listeners through "
 "<code>addObserver()</code>, the gateway as an argument to <code>confirm()</code>. This is where the patterns come from, not the "
 "other way round. A swappable rule behind an interface is <b>Strategy</b>. A rule that wraps another and adds to it (weekend surge "
 "over the flat rate) is <b>Decorator</b>. A service that announces \"this booking confirmed\" to whoever subscribed, without knowing "
 "what an SMS is, is <b>Observer</b>. I write them; I do not announce them.", 3),

("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two phones read \"B4 is AVAILABLE\" in the same millisecond and both write \"HELD\". Between the read and the write is the gap, and "
 "the gap is the whole problem: one chair, two tickets. So checking every requested seat and taking every requested seat must be "
 "one indivisible step, in the class that owns those seats: the show. One <code>ReentrantLock</code> per show (Java's standard "
 "lock; re-entrant means the thread that holds it may take it again). The show is the natural unit of contention, the thing "
 "callers actually fight over. Two different shows never wait for each other, while one lock on the whole cinema would make "
 "the 9pm screen queue behind the 6pm one. The clock is read inside the lock too, so two callers can never disagree about whether a hold "
 "has lapsed. And anything that only listens, like the SMS, is called after the lock is released, never inside it.", 4),

("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Is B4 free in this show\": a map from seat id to show seat, kept in screen order so that \"adjacent\" still means something. "
 "\"Which booking is BK7\": a map by booking id on the show. A second, tiny map on the service, booking id to show, routes a caller "
 "who has only the id in one hop. \"How many gold seats are left\": a counter per seat class, moved by one at every hold, "
 "release and cancel, instead of counting seats. \"Which seats does this booking hold\": the list on the booking, frozen when the "
 "hold was taken, so confirm can never quietly reprice or drop one. Only one question on the booking path needs a walk, \"three "
 "gold seats together\": it walks the screen's seats once, about a microsecond for three hundred. Every scan avoided here is a scan "
 "avoided inside the lock, which is the only place a scan would have cost anybody anything.", 5),

("Move 6: a seat and a booking each have a life cycle, and the ORDER at the critical step is the design.",
 "A show seat is AVAILABLE, or HELD by one booking until a moment in time, or SOLD. A booking is PENDING while it only holds seats, "
 "CONFIRMED once the money moved and the seats were committed, EXPIRED if the hold died first, CANCELLED if a sale was given back. "
 "Each is a small state machine: a fixed set of states and the moves allowed between them. "
 "Writing those down forces the question the interviewer is waiting to ask: what if the payment fails, or is slower than the hold? "
 "The answer is an order. One, under the lock: check every seat is free, then mark them all HELD. Two, with no lock held at all: "
 "charge the card, which takes a second or two. Three, under the lock again: the seats must still be HELD by <i>this</i> booking and "
 "the hold must not have expired; only then do they become SOLD. A declined card releases nothing, so the user can try another card "
 "and the hold simply runs out if they do not. A hold that lapsed while the card was being charged is refunded and refused, which is "
 "the one line that makes selling a seat twice impossible. The booking id goes to the gateway as the idempotency key (a unique id "
 "for this payment, so a retry that arrives twice is charged once). So a retry, or two taps on Pay at the same instant, costs the "
 "user one charge. And the third answer a gateway can give is no answer at all. A timeout is neither a yes nor a no: the booking "
 "stays PENDING, the seats stay held, and a retry with the same key, or a later question to the gateway, settles it.", 6),

("Move 7: yes, one lock per show makes holds happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself first: if every hold on this show takes the same lock, is a blockbuster "
 "now a queue? It is, for about two microseconds at worst (a laptop measures a tenth of a microsecond), which is the left-hand box: lookups, "
 "status reads and field writes, and nothing else. One at a time is true and nobody can tell, as long as nothing slow ever gets "
 "inside. That last clause is the whole rule, and "
 "it has one sharp edge worth saying before you are asked: the pricing rule is called inside the lock, so it must stay arithmetic. "
 "The day somebody writes a rule that calls a service to price a seat, price the seats before taking the lock and pass the amount "
 "in.", 7),

("Move 8: say the arithmetic, then name the ladder.",
 "Do the arithmetic out loud. It is four numbers and twenty seconds, and it ends the argument about whether one lock per show is a "
 "bottleneck. At two hundred holds a second, the lock is busy four hundredths of one per cent of the time. The number that actually "
 "decides the design is the red one: move the gateway inside the lock and the same show falls to 0.67 bookings a second, and the "
 "queue never drains. The ladder on the right answers \"and if that were not enough?\", in the order you would really climb it. "
 "Rung one reads the seat map with no lock: the seat fields are volatile (every thread sees their latest value), so the phone gets "
 "a snapshot, a copy of one moment. Rung two is compare-and-set per seat: set the holder only if it is still empty, in one hardware "
 "step. It costs real rollback code, and the seats must be taken in one fixed order, or two groups can both give up. Only rung three "
 "survives a second app server. Climbing without the arithmetic is complexity nobody asked for.", 8),

("Move 9: list what can go wrong, and write the test for each before the hour is over.",
 "The table is the list; the file is the proof. Every row is a bug that ships the moment the matching line of the design is dropped, "
 "and every row is a few lines in FailureTests.java. Three of them need a trick to test at all. The race starts fifty threads "
 "behind one latch (a gate that opens for all of them at once), so they really do collide. Time comes from an injected clock, so "
 "an expiry test moves the clock instead of sleeping for five minutes. And the nastiest test in the file is that same trick in a "
 "costume: a payment processor whose <code>charge</code> pushes the clock past the hold before it returns. That is exactly a "
 "gateway that took longer than your window. A design that cannot show its tests is a claim.", 9),

("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; what is worth practising is the order you say it in. Name the move first and the pattern second: "
 "\"price will change, so it sits behind a one-method interface the service is handed; that is Strategy\". The first half "
 "is a design decision; \"I used Strategy\" on its own is a label. The three grey rows are worth as much as the four above them. "
 "An interviewer learns more from \"Factory has not earned a place yet, and a screen layout read from a file is what would make me "
 "add it\" than from a fifth pattern that is doing nothing. A pattern without a move behind it is decoration.", 10),

("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is one line per letter. The part worth keeping is this: SOLID is a check you run <i>after</i> the design, not a list you "
 "design towards. Every row points back at a move, and a letter with no move behind it means you recited it rather than did it. The "
 "one that does the most work here is D. The show is handed its clock and the service is handed its rules. That single habit is "
 "the only reason a test can jump five minutes into the future, hand in a gateway that always declines, and count the charges.", 11),

("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The picture is the answer sheet: match the twist to one of the five, say out loud which one it is, then type. Two are worth "
 "rehearsing. A new invariant across seats (three of them must be next to each other) is not a search problem; it is a locking "
 "problem. Choose and take inside the SAME locked section, or another family takes the middle seat between your picking it and "
 "your getting it. State that must outlive the process moves behind a repository (an interface that loads and saves, so the "
 "database can change without the show changing). The hold then becomes a conditional update: set the row to HELD where it is "
 "still AVAILABLE; zero rows updated means somebody else won. That is the database's compare-and-set, the same idea as the "
 "lock: one atomic step (nothing can run in the middle of it) decides the winner. For all five, the order hold, pay, sell never "
 "changes: a twist adds a class, a listener, a state or a step inside the lock. That is the test that the derivation was right; "
 "page 05 has the working code for each.", 12),
]
MOVES = [(t, MV[k], txt) for (t, txt, k) in MOVES]

HOW_TO_READ = (
    '<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed list of values). '
    'Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = implements. Filled '
    'diamond = owns: the service owns the shows, a show owns one ShowSeat per chair and owns its bookings, a screen owns its '
    'seats. Plain arrow = references: a ShowSeat points at the chair whose status it is holding, a Booking points at its show seats. '
    'Dashed green = handed in and never built here: pricing and seat choice through <code>configure()</code>, the clock through the '
    'constructor, the gateway as an argument to <code>confirm()</code>. Dotted blue = notifies, and it happens after the lock is '
    'released. Bottom centre-right are the three exceptions the flow throws. SeatUnavailable and PaymentDeclined are thrown '
    'before anything is written. HoldLapsed is thrown after the dead hold\'s seats are handed back, so the caller only has to '
    'refund. <b>Where state lives:</b> the left column and the bottom-left are the catalog, and they never change while anybody '
    'books. Every field that changes during a booking is on a ShowSeat, a Booking or the Show itself (its bookings map and free '
    'counts), and every write to one of them happens inside the show\'s lock. The service holds no seat state at all: it sequences '
    'hold, pay and commit, and it is the only class that talks to the gateway.')

# ============================================================ page 4: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each class '
              'and method says what it does and what it guarantees; read only those first for the shape, then the bodies for the '
              'mechanics. Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java (the reference '
              'code for every follow-up) and FailureTests.java (sixteen claims, 53 checks; '
              '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 5: follow-ups
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3><button class="timer" data-min="60">start 60:00</button></div>'
             '<div class="cb"><div class="prompt">' + PROMPT + '</div>Before typing, write your six to eight clarifying questions; then type in the order '
             'of Main.java: the enums (SeatClass, SeatStatus, BookingStatus), the catalog (Seat with no status, Screen, Theatre), ShowSeat and Booking, the '
             'three small exceptions, Clock, the four small interfaces with one implementation each, the Show with its map of seats, its lock and the '
             'hold / commit / release / cancel order, the BookingService that puts payment between the two locked halves, and a main with the fifty-thread '
             'race. If the clock runs out, the part that must exist is <code>Show.hold</code> and <code>Show.commit</code> under one lock, and a '
             '<code>confirm</code> that charges between them with the booking id as the key. The seat policy, cancel, the listeners and surge '
             'pricing come after.</div></div>')

FU = [
("Weekend surge, one and a half times, without touching Show or BookingService.", "functional", 10,
 "Price is already an interface, so surge is one new class that wraps the flat rule. It asks the flat rule for the price, looks at "
 "the day the <i>show</i> starts in the theatre's time zone, and charges 150 per cent on a Saturday or a Sunday. The percentage is "
 "an integer and the result is rounded down to the paisa, so no double ever touches money. Nothing else changes; the only edit is the "
 "<code>configure</code> line that hands the rule in. It reads the show's start time, not the wall clock, so a Tuesday booking for "
 "a Saturday show still pays the weekend price, and a test needs no clock. Demand pricing and coupons stack the same way, each "
 "wrapping the one below it.",
 sect(SRC, "class WeekendSurgePricing", "interface SeatPolicy") + "\n" + X("dynamic pricing", "persistence")),

("Two phones tap seat B4 in the same millisecond. Prove only one of them gets it.", "non-functional", 10,
 "The race lives in the gap between reading \"B4 is AVAILABLE\" and writing \"B4 is HELD\". <code>hold</code> does both inside one "
 "lock on the show, in two passes. Pass one checks every requested seat and touches nothing; pass two writes them all. No other "
 "phone can run in that gap, and a seat that fails in pass one means nothing was written. The proof: fifty threads wait behind "
 "one latch, the latch opens, all fifty ask for seat C1, and the test counts the bookings that came back. Exactly one; the other "
 "forty-nine get SeatUnavailable.",
 sect(SRC, "    Booking hold(String userId", "    Booking holdBest(String userId") + "\n" + cut(TST, "        // 1. fifty phones", "        // 2. the card is declined")),

("One lock per show. Does that scale, or have you serialised the whole cinema?", "non-functional", 5,
 "Yes, holds on one show go one at a time; whether that matters is arithmetic, not opinion. The locked part of a three-seat hold "
 "is three map lookups, three status reads, three price lookups and nine field writes: about two microseconds. At two hundred hold "
 "attempts a second on a hot show, the lock is busy four hundred microseconds in every million, and two shows never share a lock. "
 "What would break it is the gateway: one and a half seconds inside the lock would drop the show to 0.67 bookings a second. The "
 "code below is the next rung: each seat is claimed by compare-and-set, always in seat-id order, and a refusal hands back the "
 "seats already taken. Without that fixed order, two groups asking for C1+C2 and C2+C1 can each take one seat and both give up.",
 X("per-seat compare-and-set", "ExtDemo")),

("The card is declined. What is the state of the system, and show me the code.", "functional", 10,
 "Nothing is half done and nothing is released. <code>confirm</code> charges with no lock held; when the gateway returns null it "
 "throws, and the booking is still PENDING with its seats still HELD. The user can try another card against the same booking for "
 "the rest of the five minutes. If they walk away instead, nobody cleans up: the next person who asks for that seat finds a dead "
 "hold, reclaims it, marks the booking EXPIRED and takes the seat. The test declines a card and checks the seat is still HELD. "
 "Then it moves the clock: one millisecond before five minutes the seat is still held, and at five minutes exactly it is free.",
 sect(SRC, "    Booking confirm(String bookingId", "    void release(String bookingId)") + "\n" + cut(TST, "        // 2. the card is declined", "        // 3. the gateway is slower")),

("The gateway takes four minutes and your hold is five. Then the webhook fires three times.", "non-functional", 10,
 "These are the two ways confirm could sell a seat twice or take the money twice, and both are closed. The status check before "
 "charging only refuses a booking that is already over; it proves nothing about the hold, which can lapse while the gateway is "
 "thinking. So <code>commit</code> re-checks under the lock, just before marking anything SOLD: every seat must still be HELD, "
 "still stamped with <i>this</i> booking id, and still in time. If not, the seats are given back, the booking is EXPIRED and the "
 "caller refunds the charge; that is the most important line in the class. The webhook charges nothing: it commits with the "
 "payment reference it reports, so the second and third calls find the booking CONFIRMED with that same reference and do nothing. "
 "Two taps on Pay at the same instant send the same idempotency key, the booking id, so the gateway takes the money once.",
 sect(SRC, "    boolean commit(Booking b", "    boolean release(Booking b)") + "\n" + X("the payment webhook", "a gateway that times out")
 + "\n" + cut(TST, "        Booking t2 = svc.hold(\"PAY\"", "        // 14. a late release")),

("The gateway takes the money and then times out. You do not know whether the card was charged.", "non-functional", 10,
 "A timeout is a third answer, and the mistake is treating it as a no. The charge runs with no lock held and nothing is committed "
 "until it returns, so when it throws instead, the booking is still PENDING and its seats are still HELD. The gateway was given "
 "the booking id as the idempotency key, so the user can simply press Pay again: the same key is never charged twice. If the user "
 "has gone, <code>settle</code> asks the gateway about that key instead of charging. No reference means the charge never "
 "happened, and the hold lapses by itself. A reference means the money moved: settle commits with that same reference, or refunds "
 "it if the hold died meanwhile. The tests run all three endings.",
 X("a gateway that times out", "a refund policy") + "\n" + cut(TST, "        // 10. the gateway times out", "        // 11. cancelling")
 + "\n" + cut(TST, "        // 12. the booking id is the idempotency key", "        Booking t2 = svc.hold(\"PAY\"")),

("The seat map is read ten thousand times a second. Keep it fast, and keep it off the booking lock.", "non-functional", 5,
 "No new structure. \"How many gold seats are left\" is a counter on the show, moved by one at every hold, release and cancel: one "
 "map lookup, never a count. \"Is B4 free\" is one lookup in the show's seat map, and a hold whose time has passed is drawn as free, "
 "so an abandoned cart never shows as taken. Each holds the show's lock for tens of nanoseconds. The whole map of a 300-seat screen "
 "is a walk of about three microseconds, so ten thousand reads a second keep the lock about 3% busy, which is still fine. When it "
 "stops being fine, the seat fields are already volatile, so the read path can walk the map with no lock at all and draw a "
 "snapshot. It is a snapshot, not a promise; only a hold promises.",
 cut(SRC, "    /**\n     * How many seats of a class", "    /** Hand back every hold")),

("A city has forty theatres and three hundred shows tonight. List the cinemas showing Dune, without slowing booking down.", "twist", 5,
 "Browsing is a read path, and the one rule is that it never takes a booking lock. Beside the shows sits an index: city, then "
 "movie, then that movie's shows in a map sorted by start time (a ConcurrentSkipListMap, Java's thread-safe sorted map). Tonight's "
 "Dune in Bengaluru is two map hops and a range read over tonight's part of that map, so next week's shows are never touched. "
 "\"List the cinemas showing Dune\", the call a machine-coding version asks for, is the same range read collecting theatre ids. None "
 "of it touches a show's lock, so a million people browsing cannot make one hold wait. What is being checked is that you did not "
 "keep one list of all shows and scan it: three hundred shows scan fine, three hundred thousand across the country do not.",
 X("many theatres", "a waitlist")),

("Three seats together, or none at all.", "twist", 10,
 "The policy is handed in, so \"together\" is one new class. Given the free seats of a class in screen order, it looks for three "
 "in the same row with consecutive numbers, and returns them or nothing. The important part is not the search, it is where it "
 "runs. <code>holdBest</code> builds the candidate list, calls the policy and takes the seats <i>in the same locked section</i>, so "
 "another family cannot take the middle seat between the choosing and the taking. If no run exists, the method throws and not one "
 "seat was touched: the test checks the free count is unchanged and that all four scattered free seats are still AVAILABLE. Say "
 "the word atomic: nothing can run in the middle of it.",
 sect(SRC, "    Booking holdBest(String userId", "    boolean commit(Booking b") + "\n" + sect(SRC, "class AdjacentSeats", "/**\n * How money moves")),

("Do you need a background job to expire holds?", "design", 5,
 "For correctness, no. A hold is a lease: a claim that expires by itself. Every place a stale hold could block treats a "
 "lapsed one as free: the check inside <code>hold</code>, the candidate list inside <code>holdBest</code>, and the seat map. The "
 "first person who wants that seat reclaims it, marks the dead booking EXPIRED and takes it, so an abandoned cart can never keep a "
 "seat off sale. A sweeper is still worth having for the free count: until something reclaims a lapsed hold, the count reads one "
 "lower than the truth. That is the safe direction to be wrong in, but it makes the show look fuller than it is. A scheduled pass, "
 "or a DelayQueue (Java's queue that hands out each item only when its time comes) keyed on the expiry, does the job; neither is "
 "needed for correctness.",
 X("a background sweeper", "many theatres")),

("The show is sold out. Who gets the next seat that comes back, and what stops one script holding the whole house?", "twist", 10,
 "Two different mechanisms, and both are about seats nobody can buy. A waitlist is one queue per show and seat class. Whoever "
 "sees a seat come back calls <code>offer</code>: a listener on CANCELLED, or the sweeper for a lapsed hold. The person at the head "
 "then gets that seat HELD in their name for five minutes, not an email telling them to race for it; if somebody faster took it, "
 "they keep their place. The script is the other problem: a cap of, say, ten seats per user per show. The trap is checking the cap "
 "and then holding: two of the script's threads both read \"nine of ten used\" and both hold. So one user's requests queue on a "
 "small per-user lock. And the count is only of seats they hold or bought right now, so a lapsed hold, a release or a cancel gives "
 "the quota back by itself.",
 X("a waitlist", "dynamic pricing") + "\n" + X("a cap per user", "per-seat compare-and-set")),

("The user cancels forty-five minutes before the show. How much money goes back, and what puts the seat back?", "functional", 5,
 "Two separate decisions, and the interviewer is watching whether you notice that they are separate. The seat always comes back: "
 "<code>cancel</code> puts every seat of the booking to AVAILABLE under the show's lock and moves the free counter, whatever happens "
 "to the money. How much money goes back is a rule that will change, so it is another one-method interface: full up to two hours "
 "before, half up to twenty minutes, nothing after. It is decided from the booking's frozen amount and the show's start time, before "
 "anything moves. The refund is sent after the lock is released, so a slow refund never holds a seat hostage. Money is integer "
 "paise, so half of 25,000 is exactly 12,500. Half of an odd amount rounds down in the house's favour: say that decision out loud "
 "rather than letting a double make it for you.",
 X("a refund policy", "a cap per user") + "\n" + cut(TST, "        // 11. cancelling", "        // 12. the booking id is the idempotency key")),

("Persist it, then run it on four app servers. Which tables, and what stops two servers selling one seat?", "twist", 10,
 "One JVM's lock guards nothing once there are four JVMs, so the race moves into the database. The tables are the classes, and only "
 "one of them sees the race: show_seat, one row per seat per show. A group hold is one transaction with one conditional UPDATE: set "
 "the rows to HELD where they are still AVAILABLE or their hold has lapsed. If fewer rows changed than seats were asked for, roll "
 "back: somebody else won one. The transaction gives the two ACID promises that matter here: all the rows change or none do "
 "(atomic), and no other booking sees them half-changed (isolated). This is optimistic locking: write only if nothing changed, "
 "and zero rows means you lost. The pessimistic version, <code>SELECT ... FOR UPDATE</code>, locks the rows first and then writes. "
 "Never hold a database lock across the payment: the hold is a status plus an expiry time on the row, its time to live (TTL). In "
 "Redis the same hold is <code>SET seatKey bookingId NX PX 300000</code> (only if absent, gone in five minutes), released by a "
 "compare-and-delete (delete only if the value is still this booking's id).",
 X("persistence", "the payment webhook")),

("Where does time come from, and how do you test a hold expiring without sleeping?", "design", 5,
 "The show is handed a <code>Clock</code>, a one-method interface, and it reads it inside the lock so two callers can never disagree "
 "about whether a hold has lapsed. Nothing else in the design reads the wall clock. A test hands in a lambda over a one-element "
 "array and moves it: hold a seat, move the clock to five minutes, and the seat is free; one millisecond earlier it was still held. "
 "The nastiest test in the file is the same trick in a costume: a payment processor whose <code>charge</code> pushes the clock past "
 "the hold before returning success. That is exactly a gateway that took longer than your window. Confirm must then refuse and "
 "refund, and the assertions check the card was charged once and refunded once.",
 sect(SRC, "interface Clock", "// \"they'll want weekend") + "\n" + cut(TST, "        now[0] += HOLD - 1;", "        Booking b2b")
 + "\n" + cut(TST, "        // 3. the gateway is slower", "        // 4. a second confirm")),

("Which pattern is where, and why did each one earn its place?", "design", 5,
 "Four patterns are in the file, and each one is a line you can put your finger on. <b>Strategy</b>: "
 "<code>interface PricingRule { long pricePaise(Show, Seat); }</code> and <code>configure(pricing, policy)</code> -- the service is "
 "handed its rules and never builds one. <b>Decorator</b>: <code>WeekendSurgePricing</code> holds a <code>base</code> and multiplies "
 "whatever the base returned, so the flat rule is never opened and coupons and demand pricing stack on top of it the same way. "
 "<b>Observer</b>: <code>publish</code> runs after <code>lock.unlock()</code> and wraps each listener in a catch, which is why a dead "
 "SMS gateway cannot kill a confirmed booking. <b>State</b>: two enums plus the order at the critical step, so the illegal "
 "transitions have nowhere to live. Two are absent on purpose. No Factory, because screens and seats arrive already built. No "
 "Singleton, because <code>main</code> builds one service and hands it out, which is exactly why every test in FailureTests can "
 "build its own.",
 cut(SRC, "// \"they'll want weekend", "// \"give me the best three together\"")
 + "\n" + cut(SRC, "    /** Tell every listener", "}\n\n/**\n * Proof it works")),

("Enum for the seat class, or a Seat subclass? And where would a Factory pay?", "design", 3,
 "Enum, until a class gains behaviour of its own. Three tiers that differ only in what they cost are data: one row in a rate table. "
 "A recliner that must be reclined, or a wheelchair space with its own booking rules, is behaviour, and that is when a subclass pays. "
 "The same answer applies to the statuses: SeatStatus and BookingStatus are enums because the transitions live in one place, in the "
 "order at the critical step, not inside each state. A Factory earns its place when a screen layout arrives as configuration. Then "
 "a registry from a string to a constructor makes a new seat kind one registration instead of one more case in a growing switch.",
 "// data, not classes: a tier is a row\nprivate static final Map<SeatClass, Long> RATE = new EnumMap<>(Map.of(\n"
 "    SeatClass.SILVER, 15_000L, SeatClass.GOLD, 25_000L, SeatClass.PLATINUM, 40_000L));\n\n"
 "// when a tier gains behaviour, a subclass pays -- and Seat stops being final\nclass ReclinerSeat extends Seat {\n"
 "    ReclinerSeat(String row, int number) { super(row, number, SeatClass.PLATINUM); }\n"
 "    void recline() { /* talks to the seat motor */ }\n}\n\n"
 "// a factory only once creation grows: a registry, so a new kind is one registration\nMap<String, BiFunction<String, Integer, Seat>> registry = Map.of(\n"
 "    \"RECLINER\", ReclinerSeat::new);\nSeat s = registry.get(kind).apply(row, number);\n"),
]

# ============================================================ build
spec = dict(
    slug="bookmyshow",
    title="Movie Ticket Booking",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 16 failure tests (53 checks) and a 50-thread race pass",
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
)
build(spec)
