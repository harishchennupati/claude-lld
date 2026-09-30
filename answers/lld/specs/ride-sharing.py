# Ride Sharing LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"ride-sharing/Main.java").read_text()
ext   = (H/"ride-sharing/Extensions.java").read_text()
tests = (H/"ride-sharing/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def rail(d):
    """a plain line with no arrow head, for merging several arrows onto one track"""
    return '<path d="%s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % d

RED = "#ff6b6b"

# ============================================================ page 01: the problem
# what the code must do: request a ride, finish a ride, and the reads as a line
pf = _D
# row 1: the claim, in five steps -- and two of the five are claims
pf += _tx(88, 57, "request a ride", "var(--acc)", 13)
for k, (t, sub, acc) in enumerate([("a rider taps", "a place, a drop, a tier", 0),
                                   ("claim the RIDER", "one live ride each", 1),
                                   ("who is near? nine cells", "never a fleet scan", 0),
                                   ("CLAIM the car: one CAS", "exactly one rider wins", 1),
                                   ("a trip, ASSIGNED", "both phones are told", 0)]):
    x = 175 + k*205
    pf += _bx(x, 26, 190, 54, t, sub, acc=bool(acc))
    if k < 4: pf += _ar("M%s 53 H%s" % (x+190, x+205), True)
pf += _ar("M885 80 V92", dash=True) + _bx(730, 92, 310, 38, "lost that car: take the next-nearest", "", dash=True)
pf += _ar("M475 80 V92", dash=True) + _bx(330, 92, 290, 38, "no car, or a throw: slot handed back", "", dash=True)
# row 2: the ride runs, and the branch that leaves it before the meter starts
pf += _tx(88, 189, "the ride runs", "var(--acc)", 13)
for k, (t, sub, acc) in enumerate([("the car drives over", "the rider watches it move", 0),
                                   ("ARRIVED: at the kerb", "driverArrived(tripId)", 0),
                                   ("the rider gets in", "startTrip: the meter starts", 1)]):
    x = 175 + k*260
    pf += _bx(x, 158, 240, 54, t, sub, acc=bool(acc))
    if k < 2: pf += _ar("M%s 185 H%s" % (x+240, x+260), True)
pf += _tx(1065, 180, "the ETA the rider watches is", "var(--muted)", 10.5) + _tx(1065, 198, "answered on read, never stored", "var(--muted)", 10.5)
pf += _ar("M685 185 V224", dash=True) + _bx(530, 224, 320, 42, "called off, any time before this", "free early, 30.00 once he set off", dash=True)
# row 3: the end, where the order is the other way round
pf += _tx(88, 319, "finish the ride", "var(--acc)", 13)
for k, (t, sub) in enumerate([("the car stops", "the meter has the minutes"),
                              ("price it: base + km + min", "then x surge, a wrapper"),
                              ("record COMPLETED_UNPAID", "car and rider both freed"),
                              ("charge the card", "then, and only then, COMPLETED")]):
    x = 175 + k*260
    pf += _bx(x, 288, 240, 54, t, sub, acc=(k == 2))
    if k < 3: pf += _ar("M%s 315 H%s" % (x+240, x+260), True)
pf += _tx(88, 372, "drivers", "var(--acc)", 13) + _tx(175, 372, "sign on, ping every few seconds, sign off: 15,000 pings a second, one field write each, and the index is touched only on a cell crossing", "var(--text)", 12, "start")
pf += _tx(88, 398, "read", "var(--acc)", 13) + _tx(175, 398, "at any moment, without scanning the fleet: the 5 nearest free cars for the map?  what is trip T7 doing?  is this rider on a ride?", "var(--text)", 12, "start")
pf += _tx(615, 432, "hundreds of riders tap in the same second: one car is never promised to two riders, one rider never collects two cars, and no trip is left half-ended", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 448, pf)

# one evening, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("18:42  Meera taps for a GO", ["her rider slot is claimed first", "9 cells hold 3 free cars; Chen is a",
                                      "PREMIER, so he is never offered", "CAS AVAILABLE -> RESERVED: Bilal"], True),
      ("18:42  Ravi taps, same second", ["he reaches for Bilal too", "compare-and-set gives him false",
                                         "no queue: Asha is next-nearest", "Meera taps again: refused, T7 is live"], False),
      ("19:09  the ride ends, 8.0 km", ["24 minutes by the injected clock", "40 + 12x8 + 1.50x24 = 172.00",
                                        "x1.5 surge = 258.00", "Bilal is free before the card"], False),
      ("19:09  the card declines", ["the trip sits at COMPLETED_UNPAID", "Bilal is AVAILABLE regardless",
                                    "the retry charges exactly once:", "the trip id is the idempotency key"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>A rider asks for a car of a chosen tier (auto, GO, premier or XL) at a place, and gets one or is told there is none.</li>
<li>A rider has at most one live ride: tapping again while one is running is refused, not duplicated.</li>
<li>The car sent is the nearest free car of that tier in the nine grid cells around the pickup, found through a spatial index (a map from each patch of the city to the cars in it), never a scan. Before he books, the map shows him the five nearest.</li>
<li>The trip walks a fixed life: requested, assigned, arrived, started, completed &mdash; or cancelled before it starts.</li>
<li>Drivers stream their location continuously; going online and offline is instant, but never mid-ride.</li>
<li>Cancelling is free until the driver is really on his way, and costs a fee after that.</li>
<li>The fare is base + per kilometre + per minute for the tier, times whatever surge is running, and is charged when the ride ends.</li>
<li>The moment the car stops, the car and the rider are both free again &mdash; whatever the card says.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Two riders reaching for one car, or one rider tapping twenty times: one ride comes out of each, and nobody is made to wait.</li>
<li>"Who is near this pickup?" touches a handful of grid cells, never the whole fleet.</li>
<li>A location ping is a field write, not an index rebuild: pings outnumber rides thirty to one.</li>
<li>An out-of-order call (end a ride that never started) or bad input (a negative distance) throws before it writes anything.</li>
<li>Matching, pricing and the cancellation rule swap without opening the service.</li>
<li>Nothing half-done: a declined card leaves a finished ride recorded and retryable and never strands a driver; a request that fails half-way hands back the rider's slot and any car it claimed.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design the back end of Uber. A rider asks for a car, we find a nearby driver and send him, the ride runs, '
          'and at the end we charge for it. Two riders must never be given the same car. I want working code, not a '
          'diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A rider opens the app at a place and asks for a car of a '
 'certain kind. The system has to answer "who is near here" out of tens of thousands of moving cars, pick one of '
 'them, and then <i>claim</i> that car so nobody else can be given it. The claim is a compare-and-set (CAS): change '
 'his status from free to taken only if it still reads free, as one atomic step (a step no other thread can see '
 'half-done). The ride then runs through a fixed sequence '
 '&mdash; the driver is assigned, he arrives, the rider gets in, the car stops &mdash; and each of those steps is '
 'only legal from the step before it. At the end the fare comes from how far and how long the car drove, times '
 'whatever surge (a multiplier on the fare when riders outnumber cars) is running, and the rider is charged. Cancelling is allowed, but only before the meter starts, and '
 'after the driver has really set off it costs something. Two things must always be true: a car is promised to '
 'exactly one rider, and a rider is on at most one ride. Thousands of riders tap at the same instant; two of them '
 'will sometimes reach for the same car in the same microsecond, and one of them will tap twice because the screen '
 'did not change fast enough.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with '
 'a <code>main</code> that sends a car, runs the ride, prints the fare, and then fires many threads at one car to '
 'show that only one of them gets it. The interviewer is watching for, in this order: the questions you ask before '
 'typing (how big is the fleet, and is straight-line distance good enough, are the first two); which classes exist '
 'and which one owns a driver\'s status; one ride end to end; what happens when two riders reach for the same car, '
 'and when one rider taps twice; '
 'where the rules that will change &mdash; who to send, what to charge &mdash; live, so a new one is a new class and '
 'not an edit; and what the system looks like when the card declines <i>after</i> the ride is over. Then the twists: '
 'the driver who ignores the request, persistence with a schema, the car-pool version, the five nearest cars on the '
 'map, ratings, a denser city.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>One city or the world, and how many cars online?</td><td>One city, tens of thousands of cars</td><td>A flat grid in one process rather than a location service split across machines (moves 5, 8)</td></tr>'
 '<tr><td>Is straight-line distance good enough, or must it be a real route?</td><td>Straight line for matching, the driven distance for the fare</td><td>Haversine (the straight-line distance over the Earth\'s curve) now; a routing service plugs in later behind an interface (moves 3, 5)</td></tr>'
 '<tr><td>Match each request as it arrives (greedy), or batch a few seconds of requests and pair them all at once?</td><td>Greedy, nearest free car</td><td>A one-method matching rule, swappable for a batch matcher later (move 3)</td></tr>'
 '<tr><td>Can the driver decline, or does the assignment stick?</td><td>It sticks for now</td><td>Whether the claim becomes an offer with a deadline (moves 6, 12)</td></tr>'
 '<tr><td>Are surge, coupons and tolls in scope?</td><td>Surge yes, the rest named</td><td>Pricing as a rule that can be wrapped, not a formula with flags (move 3)</td></tr>'
 '<tr><td>What happens if the card declines after the ride?</td><td>The ride still happened; the gateway sits behind an interface, so a test can hand in one that declines</td><td>A COMPLETED_UNPAID state, and the order at the end (moves 6, 9)</td></tr>'
 '<tr><td>Can one rider have two rides running at once?</td><td>No: one live ride each, however often he taps</td><td>A second atomic claim, on the rider and not just the car (moves 4, 5)</td></tr>'
 '<tr><td>One process and in memory, or a database and many servers?</td><td>One process, in memory</td><td>No repository (the class that saves and loads trips) yet; the compare-and-set becomes SQL later (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One evening, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> one city, tens of thousands of cars, one process, in memory; straight-line '
 'distance decides who is near, the driven distance decides the fare; money is whole paise (hundredths of a rupee); the only two cells threads '
 'fight over are a driver\'s status and a rider\'s live-ride slot, so both are single atomic steps and neither is a lock; '
 'a ride cannot be un-driven, so the ride is committed before the card is charged. Named as out of scope: the '
 'driver\'s accept window, pooling and the car-pool version, ratings, a real routing service, persistence &mdash; each '
 'is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a RIDER asks for a CAR at a PLACE; a DRIVER has a STATUS and a LOCATION; a TRIP has a LIFE and a FARE; a RULE picks the car", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 170, "Rider", "an id and a name", 0), (228, 190, "Driver", "status + location, both move", 1),
                          (446, 180, "Trip", "a life, and a fare", 1), (656, 170, "Location", "two numbers, frozen", 0),
                          (856, 170, "Matching rule", "no state: an interface", 0), (1056, 150, "ETA", "a question, not state", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: an id, a frozen value, an interface, or a question", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("say who is near this place", "DriverIndex  (owns the grid)", "index.nearby(pickup)"),
                                       ("claim one car", "Driver  (owns his own status)", "driver.reserve()   // one CAS"),
                                       ("claim this rider", "RideService  (owns the slot map)", "activeTrip.putIfAbsent(id)"),
                                       ("run a ride's life", "Trip  (owns status + the table)", "trip.transitionTo(ARRIVED)"),
                                       ("order the whole thing", "RideService  (owns the flow)", "svc.requestRide(rider, ...)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 311, "a verb whose state is spread over two classes goes to the class that sees both: that class becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 330, "and notice what is NOT a verb on the service: \"set the driver's status\". Only the driver may do that, and only with a compare-and-set", "var(--muted)", 11)
MV[2] = _mv(1230, 345, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 120, 220, 90, "RideService", "handed all of them, builds none", acc=True)
for k, (t, sub, impl, cfg) in enumerate([("MatchingStrategy", "which car gets the ride", "NearestDriver / LongestIdle / EtaMatching", 1),
                                         ("PricingStrategy", "what the ride costs", "NormalPricing, and Surge WRAPPING it", 1),
                                         ("CancellationPolicy", "what calling it off costs", "StandardCancellation, or free always", 1),
                                         ("PaymentProcessor", "who moves the money", "CardPayment, or a card that always declines", 1),
                                         ("TripObserver", "who hears that a trip moved", "PushNotifier, RatingBook, analytics", 0)]):
    y = 24 + k*56
    m3 += _ar("M250 165 H330 V%s H400" % (y+22), bool(cfg), True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(140, 232, "configure(m, p, c, pay)", "var(--acc)", 11) + _tx(140, 250, "addObserver(o), any number", "var(--muted)", 11)
m3 += _tx(615, 310, "dashed = handed in. The service never builds a rule, so a new way of matching is a new class and one changed line where it is built", "var(--muted)", 11)
m3 += _tx(615, 329, "and one rule WRAPS another: SurgePricing(base) multiplies whatever the base charged, so coupons and tolls stack instead of becoming flags", "var(--acc)", 11)
MV[3] = _mv(1230, 342, m3)

# move 4: the gap, and one owner -- here one CELL, settled by a compare-and-set
m4 = _D + _bx(30, 30, 190, 44, "Meera's phone", "reads Bilal: AVAILABLE") + _bx(30, 110, 190, 44, "Ravi's phone", "reads Bilal: AVAILABLE")
m4 += _bx(350, 70, 190, 44, "Bilal.status", "AVAILABLE", acc=True)
m4 += _ar("M220 52 H350 V70") + _ar("M220 132 H350 V114") + _tx(285, 40, "read", "var(--muted)", 10.5) + _tx(285, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="20" width="290" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(725, 45, "the gap", RED, 12) + _tx(725, 70, "both read AVAILABLE, both write", RED, 11) + _tx(725, 90, "one car, two riders, two trips", RED, 11)
m4 += _tx(725, 130, "fix: read and write as ONE step", "var(--text)", 11)
m4 += _bx(900, 40, 300, 100, "AtomicReference&lt;DriverStatus&gt;", "compareAndSet(AVAILABLE, RESERVED)", acc=True)
m4 += _tx(1050, 165, "one cell, one owner: the driver", "var(--muted)", 10.5)
m4 += _tx(1050, 185, "no lock: one instruction decides", "var(--muted)", 10.5)
m4 += _tx(615, 205, "the loser is not queued and does not fail: he drops that car and reaches for the next-nearest one, microseconds later", "var(--muted)", 11)
m4 += _tx(615, 240, "the same move, applied to the other end of the same request", "var(--text)", 12)
m4 += _bx(30, 256, 200, 44, "Meera taps twice", "two threads, one rider")
m4 += _ar("M230 278 H350", True) + _bx(350, 256, 330, 44, "activeTrip.putIfAbsent(R1)", "null back = the slot is yours", acc=True)
m4 += _ar("M680 278 H740", True) + _bx(740, 256, 460, 44, "the second tap is refused and told T7 is live", "no second trip, and no second car claimed")
m4 += _tx(615, 326, "only two cells in the whole system are fought over: a driver's status and a rider's live-ride slot. Each is settled in one instruction; neither is a lock", "var(--muted)", 11)
MV[4] = _mv(1230, 340, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("who is free near this pickup?", "Map&lt;cell, Set&lt;Driver&gt;&gt;, nine cells read", "O(9 + c)"),
                                      ("is this rider already on a ride?", "Map&lt;riderId, tripId&gt;, claimed with putIfAbsent", "O(1)"),
                                      ("where is driver D1 right now?", "a volatile Location field on the Driver", "O(1)"),
                                      ("what is trip T7 doing?", "Map&lt;tripId, Trip&gt;", "O(1)"),
                                      ("is this move of the trip legal?", "EnumMap&lt;TripStatus, EnumSet&lt;TripStatus&gt;&gt;", "O(1)"),
                                      ("what does a GO cost per km?", "EnumMap&lt;VehicleType, long[3]&gt;", "O(1)")]):
    y = 20 + k*50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 340, "nothing here scans the fleet and nothing recomputes a state from history: every question above is one hash lookup, or nine of them", "var(--muted)", 11)
MV[5] = _mv(1230, 355, m5)

# move 6: the state machine and the TWO critical orders
m6 = _D
st = [("REQUESTED", "no car yet"), ("ASSIGNED", "a car is held"), ("ARRIVED", "at the kerb"),
      ("IN_PROGRESS", "the meter runs"), ("COMPLETED_UNPAID", "the ride is a fact"), ("COMPLETED", "the money moved")]
for k, (t, sub) in enumerate(st):
    x = 20 + k*200
    m6 += _bx(x, 20, 175, 44, t, sub, acc=(k in (2, 4)))
    if k < 5: m6 += _ar("M%s 42 H%s" % (x+175, x+200), True)
for cx in (107, 307, 507):
    m6 += rail("M%s 64 V95 H520" % cx)
m6 += _ar("M520 95 V120", True) + _bx(420, 120, 200, 44, "CANCELLED", "only from the first three", acc=True)
m6 += _tx(660, 148, "and never once the meter is running: you cannot un-drive a ride", "var(--muted)", 11, "start")
m6 += _card(20, 190, 590, 152, "the order when a car is claimed",
            ["1 CLAIM the rider: putIfAbsent on his one slot", "2 ask the index: nine cells, no lock at all",
             "3 the rule picks a car: it only proposes", "4 CLAIM it: compareAndSet(AVAILABLE, RESERVED)",
             "5 only now make the trip and tell the phones", "no car, or a throw: slot and car handed back"], acc=True)
m6 += _card(620, 190, 590, 152, "the order when the ride ends -- the other way round",
            ["1 check the km, price it: it writes nothing, may throw", "2 one locked step: COMPLETED_UNPAID + free the car",
             "3 free the rider's slot, before the money", "4 charge the card, outside every lock",
             "a decline leaves the trip unpaid and retryable", "and strands nobody while it is unpaid"], acc=True)
m6 += _tx(615, 362, "two critical steps, two shapes: claim before you write when the thing can be undone, commit before you charge when it cannot", "var(--muted)", 11)
MV[6] = _mv(1230, 377, m6)

# move 7: what is actually serialised, and four hundred riders at the same instant
m7 = _D + _card(30, 20, 540, 150, "where two threads can collide: two single steps",
                ["compareAndSet on a driver's status: tens of ns", "putIfAbsent on a rider's slot: tens of ns",
                 "neither is a lock, and no thread ever blocks", "the ONE lock: a trip's own monitor, under 1 us,",
                 "wanted by that trip's rider and its driver"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "no lock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "everything else runs fully in parallel",
            ["the nine-cell read: ~900 cars handed over, ~4 us", "the min-scan over them: about 5 us",
             "the card payment: about 500 ms, no lock held", "the push notifications: ~50 ms, afterwards",
             "the person choosing a destination: seconds"])
m7 += _tx(615, 200, "four hundred riders tap in the same second", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "rider %d" % (k+1), "0 retries" if k < 9 else "1 retry, ~5 us", acc=(k == 9))
m7 += _tx(615, 283, "nobody queues. The one rider who reached for a car another rider had already won is the only one who does extra work,", "var(--muted)", 11)
m7 += _tx(615, 301, "and that work is one failed instruction and a second scan of his own candidate list: about five microseconds", "var(--muted)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "the scan, not the claim, is what this costs", "var(--text)", 12)
for k, l in enumerate(["60,000 cars over a 700 km2 city: about 85 per km2",
                       "nine 1.1 km cells = 11 km2, so a read hands over ~900 cars",
                       "measured on a laptop: read 4 us + scan 5 us; a request ~20 us",
                       "400 requests a second x 20 us = 8 ms: under 1% of one core",
                       "pings: 15,000 a second, of which ~400 cross a cell",
                       "the two claims cost tens of ns each, once per ride"]):
    m8 += _tx(35, 62 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 keep the card and the push outside everything", "already done: the money runs with no lock held"),
                              ("2 finer cells where the city is dense", "downtown a read hands over 4,000 cars: quadtree, geohash, S2"),
                              ("3 shard by zone, across processes", "UPDATE driver SET status='RESERVED' WHERE id=? AND status='AVAILABLE'")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two riders, one car", "compare-and-set; test 1: 200 riders, 40 cars, exactly 40 trips"),
                                ("one rider, two taps", "putIfAbsent on his slot; test 9: 20 taps, exactly 1 ride"),
                                ("a rule or the clock throws mid-request", "a finally block hands back slot and car; test 10: he books again"),
                                ("end a ride not started, or at -10 km", "legal-edge table + input check; tests 3, 12: nothing written"),
                                ("the card declines, or times out", "COMPLETED_UNPAID + the same key; test 6: the money moves once"),
                                ("a payment retry while the ride runs", "refused before the gateway; test 11: the real fare is charged"),
                                ("a cancelled ride strands the car", "every exit frees the driver; test 4: AVAILABLE again"),
                                ("the push gateway is down", "publish after the move, in a try/catch; test 7: the trip completes"),
                                ("a driver moves, logs off, pings race", "one step per driver in the grid; tests 8, 14: one cell only"),
                                ("two objects under one driver id", "the second is refused; test 13: no ghost is ever matched")]):
    y = 16 + k*36
    m9 += _bx(30, y, 330, 32, bad, "") + _ar("M360 %s H400" % (y+16), True) + _bx(400, y, 800, 32, fix, "", acc=True)
m9 += _tx(615, 394, "every claim this design makes has a failure test: FailureTests.java runs eighteen blocks and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 406, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("MatchingStrategy, PricingStrategy, CancellationPolicy: one method each", None), ("a new rule is a new class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new SurgePricing(base, surge)  --  and a coupon wraps that", None), ("surge, coupons and tolls stack, not flags", None)],
          [("Observer", "var(--text)"), ("moves 3, 4", None), ("publish(trip, from, to) after the move, inside a try/catch", None), ("the phones hear; the ride never waits", None)],
          [("State (as a table)", "var(--text)"), ("move 6", None), ("EnumMap&lt;TripStatus, EnumSet&gt;, checked before any write", None), ("an illegal move cannot happen", None)],
          [("Facade", "var(--text)"), ("move 2", None), ("RideService: request, arrive, start, end, cancel, and nothing else", None), ("the order of operations lives in one place", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the service is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh RideService", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("VehicleType is an enum and the rate table is already the registry", "var(--muted)"), ("it earns the name when tiers come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a Trip has six required fields and not one optional one", "var(--muted)"), ("a pattern without a move is decoration", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Index: where cars are. Trip: the life. Service: the order. A rule: one rule.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("LongestIdleMatching is a new file plus one line where the service is built", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("SurgePricing IS a PricingStrategy and HOLDS one, so it slots in anywhere", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Matching, Pricing, Cancellation, Payment, Observer, Clock: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("svc.configure(matching, pricing, cancellation, payments);  svc.setClock(...)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "shortest ETA, batched dispatch", "a new class behind MatchingStrategy plus one line", "", "move 3"),
        ("someone new wants to know", "ratings, analytics, receipts", "one more observer; the trip and the CAS do not change", "", "move 4"),
        ("a new step in a life", "the driver declines, a no-show", "the claim becomes an offer: PENDING, then accepted, declined or expired", "", "move 6"),
        ("a new invariant across things", "one car, several riders: pool", "the same claim, then a fare divided so the shares sum to it", "", "moves 4 + 6"),
        ("state that must outlive it", "persist it; two servers", "the compare-and-set becomes a conditional UPDATE:", "UPDATE driver SET status='RESERVED' WHERE id=? AND status='AVAILABLE'", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the service, the trip machine and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>rider</b> asks for a <b>car</b> at a <b>place</b>; a <b>driver</b> has a "
 "<b>status</b> and a <b>location</b>; a <b>trip</b> has a <b>life</b> and a <b>fare</b>; a <b>rule</b> picks the "
 "car. A driver has two fields that move on their own &mdash; where he is, and whether he is free &mdash; so he is a "
 "class, and the most interesting one here. A trip has a status, a fare and a set of timestamps: a class. A rider "
 "has an id and a name and nothing that moves, so it is a record (a Java class that is only its fields, fixed when it "
 "is made), and only the id ever reaches a payment. A location "
 "is two numbers that never change once taken: a record with one method on it, the distance to another location. A "
 "matching rule has no state at all &mdash; it is a decision &mdash; so it is an interface. And an ETA (the minutes until the car arrives) is not a "
 "field to keep up to date: it is a question you answer when somebody asks, from a location that is already there.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Say who is near this place\" touches the grid of cars, so it belongs to the thing that owns the grid: "
 "<code>index.nearby(pickup)</code>. \"Claim one car\" touches exactly one field on exactly one driver, so it belongs "
 "to the driver: <code>driver.reserve()</code>. \"Claim this rider\" &mdash; the check that he is not already on a "
 "ride &mdash; touches a map no single rider owns, so it belongs to the class that holds the map, the service. "
 "\"Run a ride's life\" touches the trip's status and the table of legal moves, so it belongs to the trip: "
 "<code>trip.transitionTo(ARRIVED)</code>. \"Order the whole thing\" touches all of them at once, and only one class "
 "sees all of them, so <code>RideService</code> is the orchestrator (the class that calls the others in the right "
 "order and decides none of the rules itself). Notice what is deliberately <i>not</i> a method "
 "on the service: setting a driver's status. If the service could write that field, two service calls could write it "
 "in the same microsecond and both think they won. Only the driver may change his own status, and only through a "
 "compare-and-set.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Which car to send will change: nearest today, shortest ETA when routing arrives, longest-idle when the ops team "
 "complains about starvation (a driver who is never picked), a batch matcher when somebody reads a paper. What to charge will change every week. "
 "What a cancellation costs will change the first time a city regulator calls. Who gets told will grow: the rider's "
 "phone, the driver's app, ratings, analytics. Each becomes a one-method interface the service is <i>given</i> and "
 "never builds: four of them arrive through <code>configure(matching, pricing, cancellation, payments)</code>, and "
 "listeners through <code>addObserver</code>, because there can be any number of those. This is where the patterns "
 "come from, not the other way round: a "
 "swappable rule behind an interface is <b>Strategy</b>; a rule that wraps another rule and adds to it is "
 "<b>Decorator</b> &mdash; and here it is the one that matters, because <code>SurgePricing</code> holds a "
 "<code>PricingStrategy</code> and multiplies whatever it charged, so a coupon wraps the surge and a toll wraps the "
 "coupon, and nobody ever adds a fifth flag to one fare method. A service that announces \"a trip moved\" without "
 "knowing what a phone is, is <b>Observer</b>. The spatial index is in the same family but is not a rule: it is a "
 "helper the service calls through an interface, so a grid today and a finer index next year is one line where the service is "
 "built.", 3),
("Move 4: state that many callers change at the same time gets one owner and one atomic step.",
 "Two riders tap at the same instant and the index hands both of them the same nearest car. Both read his status as "
 "AVAILABLE, both decide he is theirs, and both write: one car, two riders, two trips, and a very angry driver. So "
 "reading the status and writing it must be a single step. The usual answer is a lock, and here the usual answer is "
 "wrong in an interesting way: the shared thing is not a big structure, it is <i>one field on one driver</i>. So the "
 "field becomes an <code>AtomicReference</code> (a holder of one value that supports compare-and-set) and the claim "
 "becomes <code>compareAndSet(AVAILABLE, RESERVED)</code> &mdash; one hardware instruction, tens of nanoseconds, and "
 "exactly one thread gets <code>true</code>. A global matching lock would make every rider in the city wait in one "
 "line to prevent a collision between two of them; the compare-and-set involves only the two who collided. And the loser "
 "is not punished: he gets <code>false</code>, drops that car from his own list, and takes the next-nearest one. "
 "Anything that only listens &mdash; the push notification, the rating prompt &mdash; is called after the state has "
 "already moved, never before. Now apply the same move to the other end of the same request. A rider who taps twice "
 "because the screen did not change fast enough is two threads reaching for one rider, and the shared thing is again "
 "one cell: whether he is on a ride. So the service keeps a map from rider to live trip id and claims the slot with "
 "<code>putIfAbsent</code> (store a value for the key only if it has none yet, in one atomic step): the same move, "
 "a different instruction. A rider left holding a slot can never book again, so it goes back on every way out that made no trip: no car found, or a rule that threw half-way. A <code>finally</code> block does that, and also hands back any car the request had already claimed. The slot also goes back with the car when the ride ends or is cancelled.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Who is free near this pickup?\" is the one that decides the design. Sixty thousand cars in a list is a scan, so "
 "location gets an index: round the latitude and longitude to a cell about a kilometre across and keep a set of cars "
 "per cell. A read is the pickup's cell plus its eight neighbours &mdash; nine bucket lookups, whatever the fleet "
 "size. Those nine cells hold every car within one cell width (about 1.1 km) of the pickup. So the nearest car found there is the true nearest whenever it is that close; one found further out may have a nearer rival just outside the nine, and the widening search on page 05 settles that. The map's five nearest free cars are the same read plus a "
 "heap (a structure that always hands out its largest item first) holding the five nearest so far: a nearer car "
 "pushes out the farthest. \"Where is driver D1?\" is a volatile field on the driver (every thread sees its newest "
 "value, without a lock), written by the ping path and read by matching. \"What is trip T7 doing?\" is a map from id "
 "to trip. \"Is this move legal?\" is an <code>EnumMap</code> (a map keyed by an enum, stored as a plain array) from "
 "status to the statuses it may go to: the whole lifecycle in six lines. \"Is this rider already on a ride?\" is a "
 "map from rider id to trip id, because <code>putIfAbsent</code> on a <code>ConcurrentHashMap</code> is exactly the "
 "atomic claim that cell needs. \"What does a GO cost per kilometre?\" is an <code>EnumMap</code> from tier to three "
 "rates, instead of an if-chain that grows a branch per tier. The one subtlety: the index is only rewritten when a "
 "car crosses a cell boundary, about once every two and a half minutes at city speed, so the fifteen thousand pings a "
 "second cost one volatile write each. Nine lookups is not nine cars, though: move 8 counts them.", 5),
("Move 6: anything with a life cycle is a state machine, and the ORDER of operations is part of the design.",
 "A trip is REQUESTED, then ASSIGNED, then ARRIVED, then IN_PROGRESS, then COMPLETED_UNPAID, then COMPLETED; "
 "CANCELLED is reachable from the first three and never after the meter starts, because you cannot un-drive a ride. "
 "Every legal move is one row in one table and <code>transitionTo</code> is the only writer, and it checks the table "
 "<i>before</i> it touches a field, so ending a ride that never started throws and leaves the trip exactly as it "
 "was. Writing the states down forces the two order questions, and they have opposite answers. Starting a ride: claim "
 "the rider, ask the index, let the rule pick, and <i>claim</i> the car before anything is written, because a claim "
 "that fails must leave no trace. If no car turns up, or anything throws, the slot and any claimed car go straight back. Ending a ride: the ride is already a fact, so record it and free the car in one locked step, then free the rider's slot. Only then call the card, outside every lock, with the trip id as the idempotency "
 "key (an id sent with the charge, so the gateway applies a repeat of it only once). A declined card leaves the trip "
 "at COMPLETED_UNPAID with the driver back in the pool and the rider free to book again, and <code>retryPayment</code> "
 "finishes the money later. It refuses any trip that is not COMPLETED_UNPAID <i>before</i> it calls the gateway: a "
 "retry on a running ride would otherwise spend the trip's key on a fare of zero. COMPLETED_UNPAID is not a fudge: "
 "it is the honest name for \"the ride happened and the money has not\". The rule underneath both orders is the "
 "same one: whatever you take out of a pool, put back on every path out of the method, including the ones that "
 "throw.", 6),
("Move 7: yes, two riders reaching for one car are settled one at a time. Ask for how long, and what else is.",
 "The question you will be asked, and should ask yourself: have you now made dispatch one-at-a-time? No, and this is "
 "the part worth being precise about. There is no lock anywhere in the matching path. The nine-cell read, the scan "
 "over the nine hundred cars it returns, the choice, the trip object, the notifications &mdash; all of it runs fully "
 "in parallel across every rider in the city. The only places two riders can collide are two atomic steps of tens "
 "of nanoseconds each: the compare-and-set on a driver's status, which involves only the riders who reached for the "
 "same car, and the <code>putIfAbsent</code> on a rider's slot, which involves only that one rider's own taps. The "
 "one real lock in the system is a trip's own monitor (the lock every Java object carries, taken with "
 "<code>synchronized</code>), wanted by exactly two people, that trip's rider and that trip's driver. "
 "<code>transitionTo</code> holds it, and so do start, end and cancel, so that a trip and its car always change in one step. Each holds it for well under a microsecond. Cancelling needs "
 "it most: it reads the state the trip is in, prices the fee from it and then cancels, and those three have to be "
 "one step. Split them and a rider who cancels at the exact moment the driver reaches the kerb is priced as if "
 "nobody had come. Everything slow is outside every one of them: the card at around five hundred milliseconds, the "
 "push at fifty. When four hundred riders tap in the same second, none waits for another.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Sixty thousand cars online and four hundred ride requests a second at peak. Be careful with the number everybody "
 "gets wrong here: nine cell lookups is not nine cars. Sixty thousand cars over a seven-hundred-square-kilometre city "
 "is about eighty-five per square kilometre, and nine cells of 1.1 km is eleven square kilometres, so a read hands "
 "matching roughly nine hundred cars (930 in a simulated city). Each of those costs one haversine, about fifteen "
 "nanoseconds on a laptop. Measured: the read takes about 4 microseconds, the scan about 5, and a whole request, "
 "trip and all, about 20. Four hundred a second is 8 milliseconds of CPU in every second, under one per cent of one "
 "core, with no lock held for any of it. The two atomic claims are noise beside that: tens of nanoseconds per ride. "
 "The write path is the bigger count and the cheaper cost. Sixty thousand cars pinging every four seconds is "
 "fifteen thousand pings a second, but a car at city speed takes about two and a half minutes to cross a 1.1 km cell, so only about four hundred of those fifteen thousand touch the grid; the rest are one field write each. The "
 "ladder is beside this, in the order you would climb it, and only the middle rung needs a sentence. Downtown, that same read hands over four thousand cars and a request takes about a tenth of a millisecond, so you go finer <i>there</i>: a new class and one changed line, because the index is an interface. The names you will hear "
 "for it: a quadtree (cells that split into four wherever cars crowd), a geohash or Google's S2 (cells named by a "
 "string or a number, where a longer name is a smaller cell). The top rung is worth saying out loud too: "
 "<code>UPDATE driver SET status='RESERVED' WHERE id=? AND status='AVAILABLE'</code> is not a new idea, it is this "
 "page's compare-and-set performed by the database.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Two riders reaching for one car (exactly one trip, and the loser gets another car). One rider tapping twenty times "
 "(one ride, nineteen refusals, exactly one car out of the pool). A matching rule or the clock throwing half-way "
 "through a request (the slot and any claimed car come back, so he can book again). An out-of-order call or bad "
 "input, such as ending a ride that never started, or ending one at minus ten kilometres (it throws, and the trip is "
 "untouched). The card declining or timing out after the ride (the trip is recorded, the driver is free, and the "
 "retry with the same key moves the money exactly once). A payment retry while the ride is still running (refused "
 "before the gateway, so the real fare is charged at the end). A cancelled ride that forgets to give the car back "
 "(every exit releases the driver, or the fleet quietly drains over a day). The push gateway down (publish after "
 "the state has moved, inside a try/catch). A driver who drives across the city, logs off, or whose pings are "
 "handled on two threads at once (one step per driver in the grid, so he is only ever in one cell). Two driver "
 "objects under one id (the second is refused, so no ghost copy stays matchable). Each of these is a few lines in "
 "FailureTests.java; a design that cannot show its tests is a claim. Five of the eighteen blocks are races (the "
 "car, the double tap, the pings, the offers, the car-pool seats), and each is proved by counting rather than by "
 "reading a log.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer. Facade is simply the name for <code>RideService</code>'s shape: one class in front of the "
 "index, the trips and the rules, and the only one callers talk to. Two rows are worth defending out loud, because "
 "an interviewer pushes on both. State is "
 "move 6 but as a <i>table</i>, not a class per state: a trip's states carry no behaviour of their own, so a class "
 "each would buy nothing you cannot already read in six lines. The day a state does carry behaviour &mdash; a pooled "
 "leg that knows how to take on another rider &mdash; is the day you split them, and saying that is the difference "
 "between a decision and a shortcut. Decorator, not a flag, is the other: <code>SurgePricing</code> is a "
 "<code>PricingStrategy</code> that <i>holds</i> a <code>PricingStrategy</code>, which is exactly what lets a coupon "
 "wrap the surge and a toll wrap the coupon with nobody reopening the fare method. And the three grey rows matter as "
 "much as the five above them: naming Singleton, Factory or Builder here would be naming a pattern no move produced.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The thing to say out loud is that not one of the five was aimed at: each is what a move already produced, which is "
 "why every row has a line of code beside it instead of a definition. Two get probed. L, because "
 "<code>SurgePricing</code> is the sharp case &mdash; it <i>is</i> a pricing rule and <i>holds</i> one, so it can "
 "wrap the base, a coupon, or another surge, and the service never asks which it got. And I, because one method per "
 "interface is what makes the failure tests short: the gateway that always declines is three lines, and the clock "
 "that says the ride took twenty-four minutes is a lambda.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Three of the five deserve a sentence more than the table gives them. A new step in a life is rarely only an edge: "
 "the driver who never taps accept turns the claim into an <i>offer</i> with a deadline. The car is held while his phone rings for fifteen seconds, one compare-and-set decides between his tap and the timer, and a "
 "decline or silence sends the ride to the next car, never back to him. A new invariant (a rule that must always hold) across things is the pooled "
 "ride, and its hard part is not the car, it is the arithmetic: "
 "three shares that must add up to the fare to the last paisa, so the final leg absorbs the rounding. And state that "
 "must outlive the process only looks like a rewrite: <code>UPDATE driver SET status='RESERVED' WHERE id=? AND "
 "status='AVAILABLE'</code> is the compare-and-set performed by the database, and the rider's one-ride slot becomes a "
 "unique index (the database refuses a second open trip for the same rider). For all five the service, the trip "
 "machine and the tests are untouched; that is the "
 "test that the derivation was right. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, BookMyShow) and the class diagram, the concurrency, the "
 "tests, the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing "
 "is named before the move that produced it. On this problem move 4 is the one that pays: the only shared cells are a "
 "single field on a single driver and a single slot per rider, so the honest answer to both is one atomic instruction "
 "rather than a lock, and the whole of dispatch stays parallel.")

# ============================================================ page 03: the class diagram
uml_reset()
# column 1: the things handed in from the outside, and the plain values
put("obs",   10,  20, 230, "TripObserver", [], ["onTrip(trip, from, to)"], "interface")
put("push",  10,  90, 230, "PushNotifier", [], ["onTrip(...) &rarr; a phone"])
put("clock", 10, 160, 230, "Clock", [], ["nowMs(): long"], "interface")
put("pay",   10, 230, 230, "PaymentProcessor", [], ["charge(rider, paise, key)", "  : String,  or declines"], "interface")
put("card",  10, 316, 230, "CardPayment", ["byKey: Map&lt;key, ref&gt;"], ["charge(...): idempotent"])
put("rider", 10, 406, 230, "Rider", ["id: String", "name: String"], [])
put("money", 10, 488, 230, "Money", [], ["rupees(\"172.00\"): long", "fmt(paise): String"])
put("decl",  10, 578, 230, "PaymentDeclined", ["extends RuntimeException"], [])
# column 2: the aggregate root and the two classes that own the state that moves
put("svc", 300, 20, 330, "RideService",
    ["index: DriverIndex", "riders / drivers / trips: Map", "activeTrip: Map&lt;riderId, tripId&gt;",
     "matching: MatchingStrategy", "pricing: PricingStrategy", "cancellation: CancellationPolicy",
     "payments: PaymentProcessor", "clock, observers, seq"],
    ["configure(m, p, c, pay)", "goOnline(d, at) / goOffline(id)", "ping(driverId, where)",
     "requestRide(rider, src, dst, type)", "nearestFree(pickup, type, k)", "driverArrived(id) / startTrip(id)",
     "endTrip(id, km) / retryPayment(id)", "cancelTrip(id) / activeTripOf(rider)", "trip(id) / driver(id) / rider(id)"])
put("trip", 300, 362, 330, "Trip",
    ["LEGAL: EnumMap&lt;status, Set&gt;", "id / rider / driver", "pickup / drop: Location",
     "status: volatile TripStatus", "distanceKm / minutes", "farePaise / feePaise: long", "paymentRef: String"],
    ["transitionTo(to)  &larr; the guard", "assigned / arrived / started", "ended(km, mins, fare, at)",
     "paid(ref) / cancelled(fee)"])
put("driver", 300, 600, 330, "Driver",
    ["id / name / vehicle", "location: volatile Location", "status: AtomicReference&lt;...&gt;"],
    ["reserve(): CAS AVAILABLE&rarr;RESERVED", "board() / release()", "goOnline() / goOffline()", "moveTo(where)"])
# column 3: the enums, the frozen values, and the index
put("vtype",   700,  20, 230, "VehicleType", ["AUTO, GO, PREMIER, XL"], [], "enum")
put("dstatus", 700,  86, 230, "DriverStatus", ["OFFLINE, AVAILABLE,", "RESERVED, ON_TRIP"], [], "enum")
put("tstatus", 700, 168, 230, "TripStatus", ["REQUESTED, ASSIGNED,", "ARRIVED, IN_PROGRESS,", "COMPLETED_UNPAID,", "COMPLETED, CANCELLED"], [], "enum")
put("loc",     700, 282, 230, "Location", ["lat, lng: double"], ["distanceKm(o): double"])
put("veh",     700, 372, 230, "Vehicle", ["plate: String", "type: VehicleType"], [])
put("basis",   700, 454, 230, "FareBasis", ["type, distanceKm,", "minutes, pickup, atMs"], [])
put("index",   700, 536, 230, "DriverIndex", [], ["update(d, where)", "remove(d)", "nearby(pickup): List"], "interface")
put("grid",    700, 638, 230, "GridIndex", ["cells: Map&lt;cell, Set&gt;"], ["nine buckets, never a scan"])
# column 4: the rules that are handed in
put("match",   960,  20, 250, "MatchingStrategy", [], ["select(pickup, type,", "  candidates): Driver?"], "interface")
put("nearest", 960, 106, 250, "NearestDriver", [], ["the closest AVAILABLE", "car of the right tier"])
put("price",   960, 192, 250, "PricingStrategy", [], ["price(FareBasis): long"], "interface")
put("normal",  960, 262, 250, "NormalPricing", ["RATE: EnumMap by tier"], ["base + perKm + perMin"])
put("surge",   960, 352, 250, "SurgePricing", ["base: PricingStrategy", "surge: SurgeSource"], ["price = base x bp / 10000"])
put("cancel",  960, 470, 250, "CancellationPolicy", [], ["feePaise(status, waited)"], "interface")
put("std",     960, 540, 250, "StandardCancellation", [], ["free for 2 min, then 30"])
put("ssrc",    960, 610, 250, "SurgeSource", [], ["basisPoints(basis): int"], "interface")

EDGES = [
 # implementations
 ln(B["push"]["t"], B["obs"]["b"], "inherit"),
 ln(B["card"]["t"], B["pay"]["b"], "inherit"),
 ln(B["nearest"]["t"], B["match"]["b"], "inherit"),
 ln(B["normal"]["t"], B["price"]["b"], "inherit"),
 ln(B["std"]["t"], B["cancel"]["b"], "inherit"),
 ln(B["grid"]["t"], B["index"]["b"], "inherit"),
 # surge IS a pricing rule and HOLDS one: the two edges that make the decorator readable
 ln((960, 380), (960, 210), "inherit", "", [(944, 380), (944, 210)]),
 ln((960, 410), (960, 228), "assoc", "", [(930, 410), (930, 228)]),
 _tx(1085, 456, "IS a pricing rule and HOLDS one", "var(--acc)", 10.5),
 ln(B["ssrc"]["r"], B["surge"]["r"], "inject", "", [(1226, 637), (1226, 397)]),
 # the service owns the trips, the drivers and the index
 ln(B["svc"]["b"], B["trip"]["t"], "compose", "every trip"),
 ln((300, 200), (300, 667), "compose", "", [(284, 200), (284, 667)]),
 ln(B["trip"]["b"], B["driver"]["t"], "assoc", "rides with"),
 ln((630, 250), (700, 579), "compose", "owns", [(694, 250), (694, 579)]),
 # the trip and the driver point at their enums and their frozen values
 ln((630, 380), (700, 217), "assoc", "", [(652, 380), (652, 217)]),
 ln((630, 420), (700, 319), "assoc", "", [(664, 420), (664, 319)]),
 ln((630, 620), (700, 119), "assoc", "", [(680, 620), (680, 119)]),
 ln((630, 650), (700, 405), "assoc", "", [(672, 650), (672, 405)]),
 # the rules, handed in through configure()
 ln((630, 78), (960, 55), "inject", "", [(944, 78), (944, 55)]),
 ln((630, 160), (960, 219), "inject", "", [(950, 160), (950, 219)]),
 ln((630, 274), (960, 497), "inject", "", [(956, 274), (956, 497)]),
 _tx(945, 12, "the rules, handed in", "var(--acc)", 10.5),
 # the gateway, the clock, the listeners and the values
 ln(B["pay"]["r"], (300, 150), "inject", "", [(270, 265), (270, 150)]),
 ln(B["clock"]["r"], (300, 175), "inject", "", [(262, 187), (262, 175)]),
 ln((300, 80), (240, 47), "notify", "", [(254, 80), (254, 47)]),
 ln((300, 430), (240, 439), "assoc", "", [(266, 430), (266, 439)]),
 ln((300, 520), (240, 523), "assoc", "", [(252, 520), (252, 523)]),
 ln(B["decl"]["r"], B["pay"]["r"], "assoc", "", [(258, 601), (258, 272)]),
 _tx(12, 646, "thrown by charge(): the ride still", "var(--muted)", 10, "start"),
 _tx(12, 660, "happened, only the money has not", "var(--muted)", 10, "start"),
]
UMLSVG = uml_svg(1230, 800, EDGES, legend_y=777)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the service owns every trip, every driver and the index. Plain arrow = references: '
 'a trip points at its status, its two locations and the driver it is riding with. Dashed green = handed in through '
 '<code>configure()</code> or <code>setClock()</code>. Dotted blue = notifies. <b>Where state lives:</b> the driver has '
 'the two fields that move on their own: a volatile location written by the ping path, and an '
 '<code>AtomicReference</code> status, one of the only two cells threads fight over. The trip has its own status plus the '
 'table of legal moves, and is the only class allowed to write it. The index has the grid and nothing else. The service '
 'has the maps, the handed-in rules and the order of operations, and the other cell threads fight over: <code>activeTrip</code>, the rider-to-trip map that is claimed with <code>putIfAbsent</code> so a double tap cannot become two rides. The service holds no lock of its own. Notice what is <i>not</i> '
 'here: no Dispatcher class, because dispatch is a short loop inside <code>requestRide</code>; no state classes, because '
 'a trip\'s states carry no behaviour; and no ETA field anywhere, because an ETA is a question, not a thing to keep up '
 'to date.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (eighteen blocks of claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (fleet size and straight-line-versus-routed distance '
 'first); then type in the order of Main.java: the three enums, the Money helpers, the Clock, the Location record with '
 'haversine, Rider and Vehicle, then Driver with its AtomicReference and <code>reserve()</code>, then DriverIndex and the '
 'GridIndex, then the matching and pricing interfaces with one implementation each plus the surge wrapper, then the '
 'cancellation rule, the payment gateway and the observer, then Trip with its legal-edge table, then RideService with '
 'its two claims (the rider\'s slot, then the car) and its two orders (claim-then-write at the start, commit-then-charge '
 'at the end), then a main with the race. If the hour runs short, the must-write core is the enums, Driver with '
 '<code>reserve()</code>, Trip with its table, NearestDriver, NormalPricing, and RideService\'s request, start, end and '
 'cancel, with the race in main. Scan a plain list of drivers instead of the grid, and say the grid out loud. The grid, '
 'the surge wrapper, the cancellation rule and the observer come next, in that order.</div></div>')

FU = [
("Two riders tap for the same car in the same millisecond. Prove that only one of them gets it.", "non-functional", 10,
 "The race lives between reading a driver's status and writing it back. There is no lock: the status is an "
 "<code>AtomicReference</code> and the claim is <code>compareAndSet(AVAILABLE, RESERVED)</code>, so exactly one thread "
 "can get <code>true</code> for a given car, whatever the hardware does with the others. The proof is a count, not a "
 "log: fifty threads wait on one latch (a gate that opens for all of them at once) and all fifty request a ride "
 "against a fleet of one car, and the test asserts that exactly one trip exists. Then the same test runs with two "
 "hundred riders and forty cars and asserts forty trips and forty <i>distinct</i> drivers, which is the property that "
 "actually matters: no car was handed to two people, and no car was left idle while somebody was refused.",
 T("        // 1. the race", "        // 2. matching:")),
("The driver ignores the request for fifteen seconds, or declines it. And can one driver be offered two rides at once?", "twist", 10,
 "The claim becomes an offer with a deadline. <code>offer()</code> takes the nearest free car out of the pool with "
 "the same <code>reserve()</code> compare-and-set as <code>requestRide</code>, so a driver is never offered two rides at once. Thirty riders dispatched at the same instant against three cars get exactly three offers. Each offer has "
 "one outcome, decided once by a compare-and-set away from PENDING: his accept, his decline, or the timer that expires "
 "it after fifteen seconds, whichever lands first. A decline or an expiry puts the car back, and the rider's next "
 "offer skips every driver who already saw his request. The offer object is also the ticket, so his tap on an old, "
 "expired offer is refused even when his status reads RESERVED again for a newer ride. Every offer stays in his "
 "history: that is the \"requests I accepted and declined\" screen.",
 X("the driver declines", "fairness") + "\n" + T("        // 16. offers", "        // 17. the car-pool")),
("The rider taps Book twice because the screen did not change fast enough. What does he get?", "functional", 6,
 "One ride, and a message naming it. The rider's live-ride slot is a second claim, made before the index is even "
 "asked: <code>activeTrip.putIfAbsent(riderId, \"(matching)\")</code> returns null for exactly one caller, and any "
 "tap that finds a value already there is refused and told which trip is running. It is move 4 applied to the other "
 "end of the request, with <code>putIfAbsent</code> standing in for <code>compareAndSet</code> because the cell lives "
 "in a map rather than on an object. The slot goes back on every way out that makes no trip: no car found, or a rule or the clock throwing half-way, which a <code>finally</code> block covers along with any car already claimed. It also goes back with the car when the ride ends or is cancelled, even when the card declines. The tests fire twenty simultaneous "
 "taps at a fleet of five and count one ride and one car out of the pool, then make the rule and the clock throw and "
 "check that he can still book.",
 sect(src, "private final Map<String, String> activeTrip", "private final List<TripObserver> observers")
 + "\n" + T("        // 9. one rider", "        // 11. a payment retry")),
("The card declines after the ride is over, or the gateway times out. What is the state of the system?", "functional", 10,
 "Recorded, consistent, and retryable. A ride cannot be un-driven, so the order at the end is the opposite of the order at the start. Check the distance and price it (which writes nothing); record that the ride ended and free the car in one locked step; free the rider's slot; only then call the gateway, outside every lock, with the trip "
 "id as the idempotency key. A decline leaves the trip at COMPLETED_UNPAID with its fare stored and the driver already "
 "AVAILABLE, and <code>retryPayment</code> finishes it later. A timeout is the harder case, because the money may "
 "have moved: the retry sends the same key, so the gateway hands back the first charge instead of taking it twice, "
 "and the failure test fakes exactly that. <code>retryPayment</code> also refuses any trip that is not "
 "COMPLETED_UNPAID <i>before</i> it calls the gateway. An early retry on a running ride would otherwise spend the key "
 "on a fare of zero, and the real fare would never be charged.",
 sect(src, "Trip endTrip(", "Trip cancelTrip(")),
("Cancellation. Who pays, and how do you know the fleet is not quietly draining?", "functional", 8,
 "The fee is a rule, not an if-chain: the policy is handed the state the trip is being cancelled in and how long the rider has waited, and returns paise. It is free while nobody has been sent, free for two more minutes because the driver has only just set off, and thirty rupees once he is really coming. The order is the usual one: work out the fee, "
 "run the guarded transition (it throws, changing nothing, if the meter is already running) and free the car in the "
 "same locked step, then charge the fee outside any lock. Reading the state and cancelling in it must be one step, "
 "inside the trip's own monitor. Split them and a rider who cancels in the same instant the driver reaches the kerb "
 "is priced as ASSIGNED, free, on a trip that has already become ARRIVED. Draining is the failure nobody tests for: "
 "every path that takes a car out of the pool has a matching <code>release()</code> in the same method, and the tests "
 "check the driver is AVAILABLE again after each one. A declined fee is only logged here; a real app adds it to the "
 "rider's next ride.",
 sect(src, "class StandardCancellation", "class PaymentDeclined") + "\n" + sect(src, "Trip cancelTrip(", "/** One trip by id")),
("The airport is busy: charge 1.8x there between six and nine. Do it without opening the fare formula.", "twist", 8,
 "Surge is not a flag inside <code>NormalPricing</code>; it is a second pricing rule that holds the first one and "
 "multiplies whatever it charged. So a time-and-place surge is a <code>SurgeSource</code> &mdash; one method that "
 "returns basis points, reading the pickup and the timestamp it was handed &mdash; and the fare rule itself is not "
 "touched. Basis points are ten-thousandths: 10,000 means 1.0x and 18,000 means 1.8x, so the multiplier is a whole "
 "number and the arithmetic stays exact. Because the wrapper is itself a <code>PricingStrategy</code>, a coupon wraps "
 "the surge and a toll wraps the coupon, and the order of the stack is visible where it is built. The zone version in "
 "Extensions.java divides the requests of the last five minutes by the free cars, both counted over the same nine "
 "cells.",
 sect(src, "class SurgePricing", "// \"do we charge for a cancellation") + "\n" + X("real surge", "pooling")),
("Persist it: the tables first, then two servers.", "twist", 8,
 "Start with the tables, one fact in one place: rider, vehicle, driver (with its status), trip, offer and payment. "
 "The offer table answers \"which requests did this driver accept and decline\" with one query, and the payment table "
 "carries the idempotency key under a unique constraint. The service's code does not change, only what it is "
 "handed. The interesting half is the claim: a JVM's <code>AtomicReference</code> cannot arbitrate between two "
 "processes, so it becomes <code>UPDATE driver SET status='RESERVED' WHERE id=? AND status='AVAILABLE'</code> "
 "&mdash; one row updated means you won, zero means somebody else did, which is compare-and-set done by the database. "
 "The rider's slot becomes a unique index over open trips (the database refuses a second open trip for the same rider). The guarded transition becomes an UPDATE with the old status in the WHERE clause, so two settlement "
 "workers cannot both complete one ride.",
 X("persistence", "the upfront fare")),
("The car-pool version (Swiggy, MakeMyTrip): users offer seats from Bangalore to Mysore, and a passenger picks one by preference.", "twist", 10,
 "The same name, a different prompt, and no map at all. A ride is offered with a vehicle, seats, origin, "
 "destination, start and duration; the route is the key of a map, so finding the rides on it is one lookup. Each "
 "preference (earliest ending, shortest, most vacant) is an enum constant that carries its own comparator, so a new "
 "preference is one more constant, and a preferred vehicle is a filter before the sort. Two rules carry the round, "
 "and both are move 4 again: a vehicle has "
 "one open ride (<code>putIfAbsent</code> on the vehicle), and a seat is never sold twice (a compare-and-set loop on the seats left). Twenty passengers racing for three seats seat exactly three. The sort reads a copy of the seat "
 "counts taken at search time, because sorting on numbers that change mid-sort can make Java's sort throw; if the "
 "chosen ride fills up meanwhile, the next one is tried. Ending a ride frees the vehicle for its next offer, and two "
 "maps answer \"the rides this user offered and took\".",
 X("the car-pool version", "ratings") + "\n" + T("        // 17. the car-pool", "        // 18. the map")),
("Nykaa's version: show the rider the five nearest cars, give out rides first come first served, and keep the exact route of every trip.", "functional", 8,
 "The five nearest are <code>nearestFree(pickup, type, 5)</code> on the service: the same nine-cell read as "
 "matching, then a heap that keeps the five nearest, so O(c log 5) for c cars nearby, and it changes nothing. First "
 "come, first served is how claims already settle: requests are never batched or reordered, and whichever "
 "compare-and-set lands first gets the car. A strict line by tap time, for when every car is busy, is a queue per "
 "area that a freed car serves before any newcomer; the food-delivery page builds that kind of line for orders waiting for a rider. The route is <code>RouteLog</code>, a wrapper around the index (it is a "
 "<code>DriverIndex</code> and holds one), so every ping passes through it. A ping from a driver on a trip is appended "
 "to that trip's list, and a trip observer opens and closes the list. The route also gives the fare a distance "
 "measured by the server, from the pings, instead of a number typed in by the driver's app.",
 sect(src, "List<Driver> nearestFree", "/** The car is at the kerb") + "\n" + X("the route each trip took", "a denser city")),
("Nearest-first starves the car at the hotspot's edge, a river is in the way, and the rider wants minutes by vehicle type.", "twist", 10,
 "Each is a new rule behind an interface, and none touches the service. Starvation: among the cars within five "
 "kilometres, send the one idle longest; distance stays the first filter, because fairness across a whole city is a "
 "rider waiting twenty minutes. The river: the rule asks an injected <code>RouteProvider</code> for travel time and "
 "sends the car that will <i>arrive</i> first, often not the nearest. Minutes by vehicle (Paytm's version of the "
 "question): <code>EtaByVehicle</code> keeps one <code>RouteProvider</code> per tier in an <code>EnumMap</code>, so an "
 "auto and a GO on the same spot two kilometres out get 540 and 405 seconds. \"Three minutes away\" is never stored: "
 "it is worked out when the screen asks, from the driver's last ping and the trip's status (to the kerb before the "
 "rider is in, to the destination after). A stored ETA would need fifteen thousand pings a second copied out "
 "to every open app.",
 X("fairness", "minutes, not kilometres") + "\n" + X("minutes, not kilometres", "coupons and tolls")),
("Ratings and receipts want to hear about a finished trip, and one of them throws. Then: nearest car first, rating breaks near-ties.", "twist", 8,
 "They are observers, and they hear about it <i>after</i> the state has already moved. The rating book listens for "
 "a trip reaching COMPLETED and accepts exactly one star rating for it later; the service never learns that ratings "
 "exist. The throwing listener is the part worth proving: <code>publish</code> calls each observer inside a "
 "try/catch, and the failure test registers one that throws on every call and still sees the trip complete with the "
 "right fare and the car back in the pool. \"Nearest, then rating\" is one more matching rule, "
 "<code>RatedNearest</code>: every free car within 300 metres of the nearest counts as equally near, and among those the best-rated wins. An optional floor, such as 4.5 stars for a premium tier, filters first.",
 X("ratings", "the route each trip took") + "\n" + T("        // 7. a listener that throws", "        // 8. the ping path:")),
("You used a compare-and-set rather than a lock. Does dispatch actually run in parallel, or have you fooled yourself?", "non-functional", 6,
 "It runs in parallel, and the code counts rather than claims. Nothing in the matching path takes a lock: the "
 "nine-cell read, the scan over the roughly nine hundred cars it returns, the choice and the trip object all run "
 "concurrently for every rider in the city. The only collisions are two atomic instructions of tens of nanoseconds, "
 "and each involves only the callers who actually collided. The service keeps a <code>lostRaces</code> counter for "
 "exactly this question: in the two-hundred-rider, forty-car test it reads anywhere from a few dozen to about two "
 "hundred, depending on how the threads interleave. It is that high because all forty cars stand on one spot and "
 "every rider reaches for the same nearest car first, the worst case (a stadium exit). Every run still ends with "
 "exactly forty trips and forty different drivers, with nobody queued. Notice where the cost really is: about ten microseconds of reading and scanning against tens of nanoseconds of claiming, which is why the first upgrade is a "
 "finer index and not a cleverer lock.",
 sect(src, "Optional<Trip> requestRide", "List<Driver> nearestFree")),
("Two hundred thousand cars are online, four thousand of them are in one downtown cell, and the suburb has none.", "non-functional", 9,
 "The volume is already answered: \"who is near here\" is nine bucket lookups whatever the fleet size, and a ping "
 "only touches the grid when the car crosses a cell. The downtown cell is the known weakness of a uniform grid, "
 "density skew (far more cars in some cells than in others), and the fix is resolution: smaller cells and a wider "
 "ring where the city is dense. Because <code>DriverIndex</code> is an interface, that is a new class and one line "
 "where the service is built; a quadtree, a geohash prefix or S2 cells is the same idea with the size chosen per area. "
 "The suburb is the problem upside down: <code>nearbyWidening</code> widens the ring until a <i>free</i> car of the "
 "tier appears (a busy one does not count). It trusts that car only once it is closer than the ring's edge, because only then can nobody outside be nearer. It stops at a cap either way: a car twenty minutes away is a worse answer than "
 "\"no cars right now\", and it strips the next suburb of its own car.",
 X("a denser city", "persistence")),
("The rider was quoted 230.56 before he tapped, and surge doubled while he was in the car. What does he pay?", "twist", 8,
 "230.56, the quote. The quote is the <i>same</i> pricing rule run on an estimate &mdash; the straight line stretched "
 "by a road factor of 1.35, minutes at an assumed 22 km/h &mdash; so a quote and a meter can never disagree about how "
 "a fare is built. The price and its 1.5x are locked when he books, so surge rising during the ride changes nothing: "
 "the real 8.0 km, 24-minute ride is within 15% of the 7.1 km estimate, and the bill is the quote. Only a ride that changes a lot, over 15% longer or shorter than the estimate (a new destination, a long detour), is re-priced from the meter, and even then at the <i>locked</i> 1.5x: 11 km comes to 330.00, never the new surge. An unknown quote id is refused rather than billed "
 "at 1.0x, and in Main.java the whole change is one field: the trip remembers its quote id.",
 X("the upfront fare", "Runs every extension")),
("UberPool: one car, three riders, picked up and dropped along the way.", "twist", 8,
 "Not a new state machine. A pooled ride is a trip with several riders and one fare to divide, so two things change "
 "and nothing else. Matching scores the <i>detour</i> a new rider would add to the live route instead of the distance "
 "to the pickup, which is another <code>MatchingStrategy</code>. The fare is divided in proportion to the kilometres "
 "each rider was actually in the car, and it has the exact problem a Splitwise split has: the shares must add up to "
 "the fare to the paise, so the last leg absorbs the rounding. The trip's status, the claim, the cancellation rule and "
 "the payment path are all unchanged, which is why this is an eight-minute answer rather than a redesign.",
 X("pooling", "the car-pool version")),
("Where does time come from, and how do you test a twenty-four-minute ride?", "design", 3,
 "The service has a <code>Clock</code> it was handed, and nothing else in the system reads the wall clock: the trip's "
 "timestamps, the duration the fare is built from and the wait a cancellation fee depends on all come through it. A "
 "test hands in a clock backed by a single variable, starts a ride, moves the variable forward by twenty-four minutes "
 "and ends it, and can then assert the fare to the paise rather than asserting that it is roughly right. The same injected clock "
 "makes the cancellation grace period and the fifteen-second offer window testable, because both are deadlines "
 "measured against an injected now rather than a found one.",
 "/** Where time comes from. Injected, so a test can decide that a ride took exactly twenty-four minutes. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the service: handed in, defaulted, never read from the wall clock inside a method\n"
 "private Clock clock = System::currentTimeMillis;\n"
 "void setClock(Clock c) { clock = c; }\n\n"
 "// in a test: pick the instant, then move it\n"
 "long[] now = { 1_700_000_000_000L };\n"
 "svc.setClock(() -> now[0]);\n\n" + T("        // 5. the fare comes from", "        // 6. the card declines AFTER")),
("Which pattern is where, which SOLID letter is where, and where would a Factory or the State pattern earn its place?", "design", 8,
 "Answer this backwards, because that is how the page was built: name the move, then the pattern it produced. "
 "Strategy came out of move 3, Decorator out of the same move's wrapper, Observer out of moves 3 and 4, State-as-a-table out "
 "of move 6, Facade out of move 2 &mdash; the code lines are in the table there. The half interviewers actually "
 "listen for is the half about patterns you did <i>not</i> use. Singleton earned nothing: the service is handed to "
 "its callers, which is exactly why a test can build a fresh one with a declining card. Factory is \"not yet\", and "
 "this is the enum-versus-subclass question in disguise: a vehicle tier carries no behaviour of its own, only three "
 "numbers, so it is an enum and the tier-to-rate <code>EnumMap</code> is already the lookup table a factory would keep. "
 "Give a tier behaviour &mdash; XL needing a seat check, PREMIER a driver-rating floor &mdash; or let tiers arrive as "
 "strings from configuration, and the enum becomes a class and the map becomes a factory, on that day and not "
 "before. Builder never earns it here: a trip has six required fields and no optional ones, which is a constructor.",
 "// Strategy: three rules behind three one-method interfaces, handed in, never built by the service\n"
 "interface MatchingStrategy   { Optional<Driver> select(Location pickup, VehicleType type, List<Driver> candidates); }\n"
 "interface PricingStrategy    { long price(FareBasis basis); }\n"
 "interface CancellationPolicy { long feePaise(TripStatus cancelledIn, long waitedMs); }\n"
 "void configure(MatchingStrategy m, PricingStrategy p, CancellationPolicy c, PaymentProcessor pay) { ... }\n\n"
 "// Decorator: a pricing rule that HOLDS a pricing rule, so wrappers stack in the order the call site declares\n"
 "PricingStrategy fare = new SurchargePricing(new CouponPricing(new SurgePricing(new NormalPricing(), zone), 2000, cap), toll);\n\n"
 "// Observer: the service announces; it does not know what a phone or a rating is\n"
 "private void publish(Trip t, TripStatus from, TripStatus to) {\n"
 "    for (TripObserver o : observers) try { o.onTrip(t, from, to); } catch (RuntimeException e) { /* log */ }\n"
 "}\n\n"
 "// State, as a TABLE: the whole lifecycle in six lines, checked before any field is written\n"
 "m.put(TripStatus.IN_PROGRESS, EnumSet.of(TripStatus.COMPLETED_UNPAID));   // and never CANCELLED\n"
 "if (!LEGAL.get(status).contains(to)) throw new IllegalStateException(id + \": \" + status + \" -> \" + to);\n\n"
 "// Factory: not yet. The registry is already here; it earns the name when tiers come from config strings\n"
 "Map<String, long[]> byName = Map.of(\"GO\", new long[]{4000, 1200, 150}, \"XL\", new long[]{8000, 2000, 250});\n\n"
 "// Builder: never, here. Six required fields is a constructor; a trip has no optional ones\n"
 "new Trip(id, rider, driver, pickup, drop, type, clock.nowMs());\n"),
]

build(dict(
    slug="ride-sharing", title="Ride Sharing",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 18 failure-test blocks, a 200-rider and a 20-tap race",
    problem_body=PROBLEM_BODY,
    derivation_lead=DERIVATION_LEAD,
    moves=[(t, MV[k], txt) for (t, txt, k) in MOVES],
    uml_svg=UMLSVG, how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", src), ("Extensions.java", ext), ("FailureTests.java", tests)],
    test_class="FailureTests",
    implement_card_html=IMPLEMENT_CARD,
    followups=FU,
))
