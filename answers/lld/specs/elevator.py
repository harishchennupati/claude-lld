# Elevator System LLD workbench: problem -> twelve moves -> class diagram -> the whole code -> follow-ups.
# Content only; the frame, the guard and the page come from lld_engine.build(spec).
import sys, pathlib
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

SRC = H / "elevator"
M = (SRC / "Main.java").read_text()
E = (SRC / "Extensions.java").read_text()
T = (SRC / "FailureTests.java").read_text()
def X(a, b=None):
    """slice a plain comment-delimited block out of Extensions.java"""
    i = E.index("// ---- ext: " + a)
    j = E.index("// ---- ext: " + b, i) if b else len(E)
    return E[i:j].rstrip() + "\n"
def XE(a):
    """slice from an ext marker to just before the ExtDemo runner"""
    return E[E.index("// ---- ext: " + a):E.index("/** Runs every extension")].rstrip() + "\n"
def block(src, a, b):
    return src[src.index(a):src.index(b)].rstrip() + "\n"
def lines_with(src, *needles):
    """the exact source lines containing each needle, so a quoted line stays in sync with the Java"""
    return "\n".join(next(l.strip() for l in src.split("\n") if n in l) for n in needles) + "\n"

RED = "#ff6b6b"

# ============================================================ problem page pictures
# what the code must do: a hall call, then the sweep, with the query as a line
pf = _D
rows = [("hall call", 30, [("a rider presses UP on 2", "a floor and a direction"),
                           ("score the cars in service", "floors of travel, sweep included"),
                           ("that car takes floor 2", "into its up leg; the bank records it"),
                           ("the panel updates", "where that car is now")]),
        ("the sweep", 165, [("one tick of the world", "one floor, or one door cycle"),
                            ("a stop on this leg?", "open; the call leaves the index"),
                            ("the rider presses 12 inside", "bound to this car only"),
                            ("nothing left ahead: turn", "the other leg is served next")]),
        ("a car stops", 300, [("car 3 is taken out", "a fault, or the engineer's key"),
                              ("it drops its stops, doors open", "the riders inside get out here"),
                              ("its calls go back on the queue", "nothing is lost"),
                              ("the next tick re-offers them", "another car takes them")])]
for lab, y, boxes in rows:
    pf += _tx(80, y + 31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k * 270
        pf += _bx(x, y, 250, 54, b[0], b[1], acc=(k in (1, 2) if y == 300 else k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x + 250, y + 27, x + 270), True)
pf += _ar("M545 84 V95", dash=True) + _bx(420, 95, 250, 40, "no car can take it: it waits", "", dash=True)
pf += _tx(150, 245, "inside the car there are two more buttons: OPEN holds the doors, CLOSE ends the wait, and neither may move a car", "var(--muted)", 11, "start")
pf += _tx(80, 400, "query", "var(--acc)", 13) + _tx(150, 400,
      "at any moment, without scanning anybody's stops: where is every car?  how long until one reaches floor 7?",
      "var(--text)", 12, "start")
pf += _tx(615, 440, "many riders press at the same instant: one hall call must be answered by exactly one car, and never half-assigned", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 455, pf)

# one morning, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("08:15:00.0  floor 2 presses UP", ["cars stand at 0, and 15 to 19", "estimates: 2 floors, or 13 and up", "car 0 is sent, and recorded", "car 0 up leg: {2}"], True),
      ("08:15:01.5  car 0 opens at 2", ["the call leaves the index", "waited 1500 ms by the clock", "the rider presses 12 inside", "car 0 up leg: {12}"], False),
      ("08:15:02.5  floor 6 presses UP", ["car 0 is at 2, owing 12: 4 floors", "the nearest other car: 9 floors", "car 0 takes it on the way", "car 0 up leg: {6, 12}"], False),
      ("08:15:03.5  a rider presses 1", ["car 0 is at 4: 1 joins the DOWN leg", "12 is still ahead, so no turn", "6, then 12, then down to 1", "trace: 3 4 5 6 6 6 .. 12 12 12 .. 1"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k * 290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x + 125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x + 125)
    pe += _card(x, 60, 250, 110, t, lines, acc=acc)
P_EX = _mv(1230, 185, pe)

# ============================================================ the twelve move pictures
MV = {}

# 1: the sentence, and which nouns have state
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(615, 47,
     "a RIDER presses a HALL BUTTON on a FLOOR; the BANK sends a CAR; the car works through its STOPS; the DOORS open; a PANEL shows where it is", "var(--text)", 12.5)
for (x, w, t, sub, acc) in [(30, 210, "ElevatorSystem", "the cars, the calls, the lock", 1),
                            (250, 200, "ElevatorCar", "floor, heading, doors", 1),
                            (470, 180, "StopSet", "two sorted sets", 1),
                            (670, 160, "HallCall", "floor + direction", 1),
                            (850, 170, "Hall button", "no state: a caller", 0),
                            (1040, 170, "Panel", "a listener, not a model", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w / 2))
m1 += _tx(615, 190, "solid = has its own state, becomes a class.   dashed = no state of its own: a caller or a listener", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([
        ("press UP on floor 7", "ElevatorSystem  (cars + the call index + lock)", "bank.requestHall(7, UP)"),
        ("press 12 inside car 0", "ElevatorCar  (owns its two stop sets)", "car.pressFloor(12)"),
        ("move a floor, or cycle the doors", "ElevatorCar  (floor, heading, doors)", "car.step(doorPolicy)"),
        ("decide which car answers", "nobody: it is a rule, not state", "strategy.pick(cars, call)")]):
    y = 24 + k * 56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y + 22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y + 22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 270, "a verb whose state is spread over two classes goes to the class that owns both: the bank owns the cars and the index, so dispatch is its method", "var(--muted)", 11)
MV[2] = _mv(1230, 285, m2)

# 3: rules the interviewer can change -> one-method interfaces, handed in
m3 = _D + _bx(30, 90, 220, 90, "ElevatorSystem", "configure(dispatch, doors)", acc=True)
for k, (t, sub, impls) in enumerate([
        ("DispatchStrategy", "nearest today, up-peak at nine", "NearestCarStrategy / UpPeakDispatch / ZonedDispatch"),
        ("DoorPolicy", "one tick now, three at the lobby", "FixedDwellPolicy / LobbyDwellPolicy"),
        ("ElevatorObserver", "who wants to know a car moved", "DisplayPanel / MaintenanceMonitor"),
        ("Clock", "the tick now, a real clock later", "the test's clock / System::currentTimeMillis")]):
    y = 24 + k * 60
    m3 += _ar("M250 135 H330 V%s H400" % (y + 22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 440, 44, impls, "the classes that can be handed in") + _ar("M760 %s H700" % (y + 22))
m3 += _tx(615, 285, "dashed green = handed in. the bank never builds these, so a new rule is a new class and one changed line", "var(--muted)", 11)
MV[3] = _mv(1230, 300, m3)

# 4: two riders, one button, the gap
m4 = _D + _bx(30, 30, 170, 44, "rider A", "presses 7 UP") + _bx(30, 110, 170, 44, "rider B", "presses 7 UP")
m4 += _bx(340, 70, 180, 44, "nobody owes 7 UP", "yet", acc=True)
m4 += _ar("M200 52 H340 V70") + _ar("M200 132 H340 V114") + _tx(270, 40, "reads", "var(--muted)", 10.5) + _tx(270, 160, "reads", "var(--muted)", 10.5)
m4 += '<rect x="550" y="20" width="300" height="145" rx="6" fill="none" stroke="#f38ba8" stroke-dasharray="4 3"/>'
m4 += _tx(700, 45, "the gap", "#f38ba8", 12) + _tx(700, 70, "both saw it unowed, both dispatch:", "#f38ba8", 11)
m4 += _tx(700, 90, "two cars sent to floor 7,", "#f38ba8", 11) + _tx(700, 110, "one arrives to an empty hallway", "#f38ba8", 11)
m4 += _tx(700, 145, "fix: look up, score, take, record: ONE step", "var(--text)", 11)
m4 += _bx(880, 40, 320, 100, "ElevatorSystem.lock", "check the index, score, accept, record", acc=True)
m4 += _tx(1040, 165, "the lock lives where the shared state lives", "var(--muted)", 10.5)
m4 += _tx(1040, 185, "panels are told after unlock, never inside it", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([
        ("is this floor a stop on my leg?", "NavigableSet&lt;Integer&gt; up  .contains(floor)", "O(log n)"),
        ("is anything still ahead of me?", "the same two sets  .higher / .lower", "O(log n), no scan"),
        ("the two legs, keyed by direction", "EnumMap&lt;Direction, NavigableSet&lt;Integer&gt;&gt;", "an array index"),
        ("who owes this hall call?", "Map&lt;HallCall, carId&gt;   a record is a key", "O(1)"),
        ("where is car 3 right now?", "car.snapshot(): one volatile field", "O(1), no lock")]):
    y = 20 + k * 50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y + 20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y + 20), True)
    m5 += _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 290, "pressing 5 three times is one stop because a set dedupes; every sweep question is a lookup, so nothing scans inside the lock", "var(--muted)", 11)
MV[5] = _mv(1230, 305, m5)

# 6: the state machine, and the order at the critical step
m6 = _D + _bx(30, 50, 150, 44, "IDLE", "no stops owed")
m6 += _bx(240, 50, 230, 44, "MOVING_UP / DOWN", "one floor per tick", acc=True)
m6 += _bx(540, 50, 180, 44, "DOORS_OPEN", "the car may not move", acc=True)
m6 += _ar("M180 72 H240", True) + _tx(210, 42, "a stop", "var(--muted)", 10)
m6 += _ar("M470 72 H540", True) + _tx(505, 42, "arrived", "var(--muted)", 10)
m6 += _ar("M630 94 Q 540 150 420 94") + _tx(525, 143, "doors close, stops remain", "var(--muted)", 10.5)
m6 += _ar("M700 94 C 700 195, 110 195, 105 94") + _tx(400, 192, "doors close, nothing owed", "var(--muted)", 10.5)
m6 += _ar("M300 50 Q 355 8 410 50") + _tx(355, 22, "nothing ahead: reverse the leg -- this is LOOK", "var(--acc)", 10.5)
m6 += _ar("M60 96 V210", dash=True) + _tx(68, 192, "emergency stop, any state", "var(--muted)", 10.5, "start")
m6 += _bx(30, 210, 690, 42, "MAINTENANCE", "an emergency stop halts the car here and hands its hall calls back to the bank's queue", dash=True)
m6 += '<rect x="760" y="20" width="450" height="232" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(985, 44, "the order inside requestHall, and why", "var(--text)", 12)
for k, l in enumerate(["1 reject a button this building has not got:", "   floor 99, or UP on the top floor",
                       "2 already lit? return the same car, do nothing else",
                       "3 score the cars that are in service", "4 the winner TAKES THE STOP (it may refuse)",
                       "5 only now: write down who owes the call", "a refusal leaves every set exactly as it was and",
                       "the call waits on the queue; the next tick offers it again"]):
    m6 += _tx(775, 66 + k * 21, l, "var(--muted)" if k > 5 else "var(--text)", 11, "start")
m6 += _tx(615, 275, "a car state plus one rule: nothing is written down until a car has actually taken the stop. An emergency stop is the same rule backwards.", "var(--muted)", 11)
MV[6] = _mv(1230, 290, m6)

# 7: what is inside the lock, and ten buttons at the same instant
m7 = _D + _card(30, 20, 540, 165, "inside the lock: under a microsecond (measured ~0.6)",
                ["look the call up in the index: is it already lit?", "score six cars from their snapshots: a few subtractions each",
                 "the winner inserts one floor into a TreeSet", "write who owes it; copy six snapshots",
                 "a tick: six cars stepped, then waiting calls re-offered"], acc=True)
m7 += _ar("M570 100 H640", True) + _tx(605, 90, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 165, "outside the lock: milliseconds to seconds",
            ["the panel above the doors: a serial write, ~5 ms", "the maintenance monitor: counting and a log line",
             "the door motor: 2 seconds", "the rider walking in: 10 seconds", "the next tick: 500 ms away"])
m7 += _tx(615, 205, "ten buttons pressed at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k * 118
    m7 += _bx(x, 220, 106, 40, "press %d" % (k + 1), "waits %d us" % k, acc=(k == 9))
m7 += _tx(615, 290, "call it 1 us each: the tenth rider waits about nine microseconds for the lock, then two seconds for a door. One at a time is true, and nobody can tell", "var(--muted)", 11)
MV[7] = _mv(1230, 305, m7)

# 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock for six cars: is it a bottleneck?", "var(--text)", 12)
for k, l in enumerate(["a hall call holds it under 1 us: one lookup, six scores, one insert",
                       "morning peak in a twenty-floor tower: ~3 presses a second",
                       "ticks: two a second, six cars, under 1 us each: ~2 us a second",
                       "~5 us of lock in every 1,000,000 us; two presses collide ~once a day",
                       "the weak spot: a tick re-scores every waiting call in the lock"]):
    m8 += _tx(35, 66 + k * 24, l, RED if k == 4 else "var(--muted)", 11, "start")
m8 += _tx(880, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 stop re-scoring waiting calls every tick", "offer them again only when a car frees up or comes back into service"),
                              ("2 a lock per car, taken after the index lock", "cars on different sweeps stop waiting for each other"),
                              ("3 one thread per car with a mailbox", "a press becomes a queued command; snapshots stay the only shared read")]):
    m8 += _bx(600, 58 + k * 50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# 9: what can go wrong, and the test for each
m9 = _D
for k, (t, sub, fix) in enumerate([
        ("two riders, one button", "two cars sent, one empty trip", "index + score + accept in one locked step; test: 40 threads, one latch, one car"),
        ("the up car puts out the down lamp", "the down crowd is left standing", "opening clears only the leg being served; test: the DOWN call on 6 is still owed"),
        ("the sweep turns early", "the top floor starves", "turn only when nothing is ahead; test: the floor trace never dips first"),
        ("the sweep runs to the top", "wasted travel: that is SCAN", "turn at the LAST STOP, not the last floor; test: the car never passes floor 8"),
        ("an emergency stop", "the queue is swallowed with the car", "hand the calls back; test: the call is pending, then another car owes it"),
        ("a panel throws, or hears late", "the tick dies, or a count grows", "publish after unlock, catch; version + odometer; test: a throwing panel, presses racing ticks")]):
    y = 24 + k * 46
    m9 += _bx(30, y, 290, 40, t, sub) + _ar("M320 %s H380" % (y + 20), True) + _bx(380, y, 820, 40, fix, "", acc=True)
m9 += _tx(615, 315, "every claim the design makes has a failure test: FailureTests.java runs thirteen of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 330, m9)

# 10: the patterns, named after the fact
cols = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 830)]
rows = [[("Strategy", "var(--text)"), ("move 3", None), ("interface DispatchStrategy { ElevatorCar pick(cars, call); }  via configure()", None), ("change which car answers without opening the bank", None)],
        [("Decorator", "var(--text)"), ("move 3", None), ("ZonedDispatch(base): filter the candidates, then base.pick(allowed, call)", None), ("add zoning on top of any scoring rule", None)],
        [("Observer", "var(--text)"), ("move 3", None), ("publish(snaps) after unlock; DisplayPanel and MaintenanceMonitor", None), ("panels hear; the bank never knows what a screen is", None)],
        [("State", "var(--text)"), ("move 6", None), ("enum CarState + step(): a door cycle OR a floor, never both", None), ("driving with the doors open cannot be written", None)],
        [("Command", "var(--muted)"), ("rung 3", None), ("the mailbox in move 8: a press becomes a queued object", "var(--muted)"), ("earned only when each car gets its own thread", "var(--muted)")],
        [("Singleton", "var(--muted)"), ("not here", None), ("the bank is constructed and handed in: one controller may run several banks", "var(--muted)"), ("a getInstance() would have been wrong here", "var(--muted)")],
        [("Factory, Builder, Visitor", "var(--muted)"), ("not yet", None), ("cars arrive built; a factory pays when a building is read from a config file", "var(--muted)"), ("say 'not yet, and here is what would make me'", "var(--muted)")]]
m10 = _D + _table(20, 20, cols, rows, rowh=30, widths=1190)
m10 += _tx(615, 275, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 290, m10)

# 11: SOLID as a check on the moves
cols = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows = [[("S", "var(--acc)"), ("one reason to change per class (each owns one state)", None), ("move 2", None), ("StopSet: the sweep. ElevatorCar: its own physics. ElevatorSystem: dispatch and the lock", None)],
        [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("up-peak = one new class + one changed configure() line", None)],
        [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("dispatch.pick(eligible, call);  never 'is it the zoned one?'", None)],
        [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("DispatchStrategy, DoorPolicy, ElevatorObserver, Clock: one method each", None)],
        [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("bank.setClock(() -&gt; now[0]);   bank.configure(new UpPeakDispatch(0, 19), doors)", None)]]
m11 = _D + _table(20, 20, cols, rows, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# 12: every twist is one of five moves
m12 = _D
tw = [("a new rule", "up-peak, energy, destination dispatch", "a new class behind DispatchStrategy + one configure line", "", "move 3"),
      ("someone new wants to know", "a lobby kiosk, analytics, the fire panel", "one more observer; no car and no sweep changes", "", "move 3"),
      ("a new step in a life", "out of service, fire recall", "a new state + the one place that checks it",
       "MAINTENANCE on the car; the recall mode on the bank, checked by dispatch and the car buttons", "move 6"),
      ("a new invariant across cars", "a zone must always keep one car free", "both claims inside the SAME locked step: all or nothing", "", "move 4"),
      ("state that must outlive the process", "forty buildings, one controller", "the index behind a repository interface; the claim becomes",
       "UPDATE hall_call SET car_id=? WHERE floor=? AND car_id IS NULL: the database's compare-and-set", "move 5 + this one")]
for k, (t, sub, fix, fsub, mv) in enumerate(tw):
    y = 24 + k * 54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y + 22), True) + _bx(420, y, 660, 44, fix, fsub, acc=True) + _tx(1150, y + 27, mv, "var(--muted)", 11)
m12 += _tx(615, 310, "for all five the cars and the sweep do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

# ============================================================ the class diagram
uml_reset()
put("hallp", 10, 20, 240, "HallPanelButtons", ["bank: ElevatorSystem", "floor: int"], ["up(): int   /   down(): int"])
put("carp", 10, 140, 240, "CarPanelButtons", ["bank: ElevatorSystem", "carId: int"],
    ["press(destination)", "holdDoor(n) / closeDoor()"])
put("obs", 10, 290, 240, "ElevatorObserver", [], ["onChange(s: CarSnapshot)"], "interface")
put("panel", 10, 390, 240, "DisplayPanel", ["watchedCar: int", "shownVersion: long"], ["onChange(s): newer only, print"])
put("mon", 10, 510, 240, "MaintenanceMonitor", ["travelled: Map&lt;carId, int&gt;"], ["onChange(s)  (synchronized)", "floorsTravelled(carId): int"])
put("sys", 300, 20, 310, "ElevatorSystem",
    ["cars: List&lt;ElevatorCar&gt;", "assigned: Map&lt;HallCall, carId&gt;", "pending: Set&lt;HallCall&gt;",
     "raisedAtMs: Map&lt;HallCall, long&gt;", "lock: ReentrantLock", "dispatch: DispatchStrategy",
     "doorPolicy: DoorPolicy", "clock: Clock", "recallFloor: Integer (fire recall)"],
    ["configure(dispatch, doors) / setClock(c)", "addObserver(o) / snapshots()", "requestHall(floor, dir): int",
     "requestCar(carId, floor) / tick()", "holdDoors(carId, n) / closeDoors(carId)",
     "takeOutOfService / returnToService(carId)", "recallAll(floor) / endRecall()", "estimateFloorsToServe(call): int"])
put("car", 300, 360, 310, "ElevatorCar",
    ["id, floor, bottomFloor, topFloor: int", "heading: Direction", "state: CarState", "doors: DoorState",
     "stops: StopSet", "held: Set&lt;HallCall&gt;", "version, floorsMoved: counters", "published: volatile CarSnapshot"],
    ["accept(call): boolean", "pressFloor(dest): boolean", "step(policy): List&lt;HallCall&gt;",
     "holdDoors(n) / closeDoorsNow()", "dropStops(): List&lt;HallCall&gt;",
     "goOutOfService(): List&lt;HallCall&gt;", "snapshot(): CarSnapshot"])
put("stops", 300, 670, 310, "StopSet", ["legs: EnumMap&lt;Direction, TreeSet&gt;"],
    ["add(leg, floor) / clear(leg, floor)", "servesOnLeg(floor, leg): boolean", "hasStopAhead(from, leg): boolean", "chooseDirection(from): Direction"])
put("disp", 680, 20, 250, "DispatchStrategy", [], ["pick(cars, call): ElevatorCar"], "interface")
put("near", 680, 110, 250, "NearestCarStrategy", ["bottom, top: int"], ["pick(): the lowest cost", "cost(snap, call, lo, hi): int"])
put("zoned", 680, 235, 250, "ZonedDispatch", ["base: DispatchStrategy", "zones: Map&lt;carId, int[]&gt;"], ["pick(): filter, then base"], "extension")
put("uppeak", 680, 355, 250, "UpPeakDispatch", ["+ LobbyParking, Capacity, Drain,", "&nbsp;&nbsp; Destination, StopBudget"], ["pick(): a different bias"], "extension")
put("dpol", 680, 460, 250, "DoorPolicy", [], ["dwellTicks(carId, floor): int"], "interface")
put("dwell", 680, 545, 250, "FixedDwellPolicy", ["+ LobbyDwellPolicy:", "&nbsp;&nbsp; 3 ticks at the lobby"], ["dwellTicks(): the same everywhere"])
put("clock", 680, 645, 250, "Clock", [], ["nowMs(): long"], "interface")
put("hc", 970, 20, 250, "HallCall", ["floor: int", "direction: Direction"], [], "record")
put("snap", 970, 120, 250, "CarSnapshot", ["carId, floor: int", "version: long (+1 per change)", "heading: Direction", "state: CarState", "doors: DoorState", "pendingStops, floorsMoved: int"], [], "record")
put("dir", 970, 270, 250, "Direction", ["UP, DOWN, IDLE"], ["opposite() / delta()"], "enum")
put("cst", 970, 380, 250, "CarState", ["IDLE, MOVING_UP, MOVING_DOWN,", "DOORS_OPEN, MAINTENANCE"], [], "enum")
put("dst", 970, 480, 250, "DoorState", ["OPEN, CLOSED"], [], "enum")

edges = [
    ln(B["hallp"]["r"], (B["sys"]["l"][0], B["hallp"]["r"][1]), "assoc", "presses"),
    ln(B["carp"]["r"], (B["sys"]["l"][0], B["carp"]["r"][1]), "assoc", "presses"),
    ln(B["sys"]["b"], B["car"]["t"], "compose", "cars 1..*"),
    ln(B["car"]["b"], B["stops"]["t"], "compose", "its two legs"),
    ln((610, 129), B["disp"]["l"], "inject", "", [(646, 129), (646, 47)]),
    _tx(640, 36, "configure", "var(--muted)", 10.5),
    ln((610, 149), B["dpol"]["l"], "inject", "", [(634, 149), (634, 487)]),
    ln((610, 169), B["clock"]["l"], "inject", "", [(622, 169), (622, 672)]),
    ln(B["near"]["t"], B["disp"]["b"], "inherit"),
    ln(B["zoned"]["l"], (B["disp"]["b"][0] - 50, B["disp"]["b"][1]), "inherit", "", [(658, 280), (658, 92)]),
    ln(B["uppeak"]["l"], (B["disp"]["b"][0] + 50, B["disp"]["b"][1]), "inherit", "", [(670, 400), (670, 100)]),
    ln(B["dwell"]["t"], B["dpol"]["b"], "inherit"),
    ln((610, 92), B["hc"]["b"], "assoc", "", [(1095, 92)]),
    _tx(1030, 107, "the index key", "var(--muted)", 10.5),
    ln(B["car"]["r"], B["snap"]["l"], "assoc", "", [(644, 501), (644, 217), (950, 217), (950, B["snap"]["l"][1])]),
    _tx(652, 348, "publishes", "var(--muted)", 10.5, "start"),
    ln(B["panel"]["t"], B["obs"]["b"], "inherit"),
    ln(B["mon"]["r"], (B["obs"]["r"][0], B["obs"]["r"][1] + 14), "inherit", "", [(275, 555), (275, 331)]),
    ln((B["sys"]["l"][0], B["obs"]["r"][1]), B["obs"]["r"], "notify", ""),
]
UMLSVG = uml_svg(1230, 840, edges, legend_y=815)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;record&raquo; = immutable data; '
 '&laquo;enum&raquo; = a fixed list of values; &laquo;extension&raquo; = it lives in Extensions.java on page 04, not in Main.java, '
 'and a "+" line names its siblings there). Middle: its fields, the state it holds. Bottom: its methods. '
 '<b>The arrows.</b> Hollow triangle = implements. Filled diamond = owns: the bank owns the cars, a car owns its stop set. '
 'Plain arrow = references: the bank keys its index by a hall call, a car publishes a snapshot. Dashed green = handed in '
 'through <code>configure()</code>. Dotted blue = notifies. <b>Where state lives:</b> the car has its floor, its heading, its '
 'doors and its two sorted legs, and nothing else in the system may write them. The bank has the cars, the index of who owes '
 'which call, the queue of calls with no car yet, the injected rules, the fire-recall mode and the one lock. A snapshot is a '
 'dead copy that anyone may read from any thread. Its version goes up by one on every change, so a listener can tell a late '
 'copy from a fresh one. The three enums on the right are named in the fields beside them. On the next step this diagram '
 'stays open in a second tab while you read the code.')

# ============================================================ page 1: the problem
PROMPT = ('"Design the lifts in an office tower. A handful of cars, twenty floors, buttons in the hallways and buttons inside '
          'each car. Riders should not wait long and a car should not bounce up and down. I want working code, not a diagram. Go."')
ASK_TABLE = '''<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>
<tr><td>How many cars and floors, and can every car reach every floor?</td><td>Six cars, twenty floors, every car everywhere</td><td>A floor range on the car, and the zoned twist (moves 1, 12)</td></tr>
<tr><td>How does a car pick its next stop: first come first served, or a sweep?</td><td>A sweep, and it turns only when nothing is left ahead</td><td>Two sorted sets per car and the one turn rule (moves 5, 6)</td></tr>
<tr><td>What are we optimising: waiting time, travel time or energy?</td><td>Waiting time, and say the estimate out loud</td><td>The cost function behind the dispatch interface (move 3)</td></tr>
<tr><td>Once a call is given to a car, is it stuck there?</td><td>Yes: the car that takes it keeps it. Moving it later is a follow-up</td><td>One index entry per call, written once (moves 4, 6)</td></tr>
<tr><td>Ticks or real time? Is a floor one step and a door another?</td><td>A tick: one floor, or one door cycle, never both</td><td>The state machine, the door buttons, tests with no sleeps (moves 6, 9)</td></tr>
<tr><td>Do buttons fire from many threads at the same instant?</td><td>Yes</td><td>One lock in the bank; the panels stay thin callers (moves 4, 7)</td></tr>
<tr><td>Capacity and weight, out of service, fire recall?</td><td>Out of scope, named</td><td>Each is one of the five twist moves (move 12)</td></tr>
<tr><td>One building, in memory, one process?</td><td>Yes</td><td>No repository yet (an interface a database can sit behind); a follow-up adds one (move 12)</td></tr></table></div>'''
REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>A hall call (a floor and a direction) goes to one car; a car call (a floor pressed inside) goes to that car only.</li>
<li>A car sweeps: it keeps going one way, opens at every stop it owes on that leg, and turns only when nothing is left ahead.</li>
<li>A car climbing past floor 6 serves the people there who want to go up; the DOWN lamp on 6 stays lit for the way back.</li>
<li>One tick moves each car one floor or cycles its doors, never both.</li>
<li>The OPEN and CLOSE buttons inside a car change how long the doors stay open, and can never move a car.</li>
<li>Which car answers is a rule that can be swapped mid-round; so is how long the doors stay open.</li>
<li>A car can be taken out of service, and the calls it owed must not be lost.</li>
<li>Panels and a maintenance monitor are told whenever a car changes.</li>
<li>Answer "where is every car?" and "how long until one reaches floor 7?" without scanning anybody's stops.</li>
<li>Reject a button the building does not have: floor 99, and UP on the top floor.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many riders press at the same instant: one hall call is answered by exactly one car.</li>
<li>No sweep question may scan: every one of them is a lookup on a sorted set, O(log n).</li>
<li>Once a car has a call, it opens its doors there within one sweep of the shaft: at most 38 floors here.</li>
<li>The dispatch rule and the door rule are swappable without touching a car.</li>
<li>One source of truth for who owes which call: the bank's index.</li>
<li>Nothing half-done: if no car takes a call it waits on a queue and is offered again on the next tick.</li>
<li>Time is handed in, so waits are replayable and no test sleeps.</li>
<li>In memory, one building, one process (say it; a follow-up adds persistence).</li></ul></div></div>
'''
PROBLEM_BODY = ('<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A tower with twenty floors and six lift cars sharing one lobby. A group of '
 'cars that share a lobby is called a <b>bank</b>, and one piece of software runs the whole bank. There are two different buttons, and '
 'telling them apart is most of the design. The UP or DOWN button in a hallway belongs to the bank, because any car may answer it. The '
 'floor button inside a car is bound to that one car and carries no direction at all. When a hallway button is pressed, the bank picks '
 'a car and gives it that stop. The car then drives itself, opening its doors at every floor it owes on the <b>leg</b> it is sweeping. '
 'A leg is one half of a round trip: the floors it will serve while climbing, or the floors it will serve while coming down. A car '
 'turns round only when nothing is left ahead of it. A display panel above each door shows where its car is, and a maintenance monitor '
 'counts the floors travelled. Many riders press at the same instant, so one hall call must be answered by exactly one car and never by '
 'two. A car taken out of service mid-sweep must hand back the calls it owed rather than swallow them.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a <code>main</code> '
 'that presses buttons, ticks a simulated clock and prints where each car went. The interviewer is watching for, in this order: the '
 'questions you ask before typing; which classes exist and which one owns which state; a hall call and a car call working end to end; '
 'how a car chooses its next stop, and why that is a sweep rather than first-come-first-served; what happens when two riders press the '
 'same button at the same instant; where the rules that will change (which car answers, how long the doors stay open) live, so a change '
 'is a new class and not an edit; what happens to the queue when a car dies mid-sweep. Then the twists: express zones (cars that serve '
 'only some floors), capacity and weight, and destination dispatch (riders type their floor in the lobby and are told which car to take). '
 'After those: a cap on the stops any one rider sits through, maintenance and fire recall, many buildings.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>' + ASK_TABLE +
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> one building, in memory, one process; a tick is one floor or one door cycle, never both; '
 'a car keeps the call it took; the two door buttons change the wait at a floor and nothing else; ties go to the lowest car id, so the '
 'same presses always send the same car. Named as out of scope: capacity and weight, express zones, destination dispatch, a stop limit '
 'per rider, maintenance and fire recall, moving a call to a different car, persistence; each is a follow-up on page 05.</div>')

# ============================================================ page 2: the twelve moves
MOVES_TEXT = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "A car has a floor, a direction, doors and the stops it owes: a class. Those stops are not a plain list, and the questions asked of them are the "
 "whole algorithm, so they get a class of their own: StopSet. A hall call is a floor plus a direction and nothing else, so it is a small immutable "
 "record (it never changes once made), which also makes it a free map key. The bank holds the cars, the index of who owes which call and the lock: "
 "a class, and the only writer. "
 "A hall button remembers nothing, so it is a thin caller, not a model, and a floor is just an integer. The panel holds no state the system owns, "
 "so it is a listener.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Press UP on floor 7\" touches the cars, the index and the lock at once, and only the bank sees all three, so it is "
 "<code>bank.requestHall(7, UP)</code>. \"Press 12 inside car 0\" touches one car's stop sets, so it is <code>car.pressFloor(12)</code>. "
 "\"Move a floor, or cycle the doors\" touches that car's floor, heading and doors, so it is <code>car.step(policy)</code>. Notice that there "
 "are two different decisions here, with two different owners. <b>Which car answers</b> a hall call is the bank's decision, and it is the "
 "one an interviewer keeps changing. <b>Where this car goes next</b> is the car's own, and it never changes. \"Decide which car answers\" "
 "touches no state at all: it only reads. That is the tell that it is a rule rather than a method, and move 3 takes it away into an interface. "
 "This is how a bank of small cars plus one orchestrator (the one class that coordinates the others) appears without anyone planning an "
 "architecture.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Four things in this system will change, and none of them is the sweep: which car answers, how long the doors stay open, who wants to know that a "
 "car moved, and where time comes from. Each becomes a one-method interface the bank is <i>given</i> in <code>configure()</code> and never builds. "
 "That is why swapping one is a new class and a changed line, not an edit inside the bank. This is also where the patterns come from, not the "
 "other way round. A swappable rule behind an interface is <b>Strategy</b>. A rule that filters the candidates and then defers to the old one "
 "(zoning over nearest) is <b>Decorator</b>. A bank that announces 'this car changed' to whoever subscribed, without knowing what a screen is, is "
 "<b>Observer</b>. I write them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two riders press UP on floor 7 in the same millisecond. Both look at the index, both see that nobody owes 7 UP, and both dispatch: two cars "
 "drive to floor 7 and one of them arrives to an empty hallway. The gap is between \"nobody owes it\" and \"this car owes it\". So the lookup, "
 "the scoring, the car taking the stop and the write into the index must be one step under one lock, in the class that owns all of it: the bank. "
 "The second press then finds the call already lit and is handed back the same car, which is what a real lift does. Anything that only listens, "
 "like the panel, is called after the lock is released and never inside it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers without scanning.",
 "The table above is the whole answer; four things in it are worth saying out loud. \"Is anything still ahead of me?\" decides when to turn "
 "round, so it must never be a loop over floors: on a sorted set it is <code>higher</code> or <code>lower</code>, O(log n). An "
 "<code>EnumMap</code> is an array indexed by the enum's position, so keying the two legs by direction costs no hashing at all. A "
 "<code>HallCall</code> record gets equals and hashCode for free, so it is a map key with no work. And the two-legs shape pays for itself twice "
 "over. Because the legs are separate, a car climbing to 6 opens its doors for the people going up and clears only the up leg. The DOWN lamp on "
 "6 stays lit, and that crowd is served on the way back down. The last row needs no lock at all: after every change a car puts a <b>snapshot</b> "
 "(an immutable copy of its floor, heading and doors) into a volatile field, which every thread reads fresh. Every scan avoided here is a scan "
 "that would otherwise have happened inside the lock.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A car is IDLE with nothing owed, MOVING_UP or MOVING_DOWN while it sweeps, DOORS_OPEN while people get in and out, and MAINTENANCE when it is "
 "pulled out of service. One rule ties the machine together: a tick is a door cycle or a floor, never both, so a car can never move with its doors "
 "open. The two door buttons are safe for the same reason: both refuse unless the doors are already open and the car is in service. The sweep "
 "turns round only when nothing is owed ahead on this leg, and that one condition is the whole algorithm. It has a name, <b>LOOK</b>: keep going "
 "the way you are pointing until your last stop on this leg, then reverse. A car that has just reversed asks the other leg about the floor it is "
 "already standing on, which is how the turning floor itself gets served instead of skipped. Then the order at the critical step, the one that "
 "decides which car owes a call. Reject a button that does not exist, return the same car if the button is already lit, score the cars in "
 "service, let the winner take the stop, and only then write down who owes it. If the car refuses, nothing has been written: the call goes on "
 "the waiting queue and the next tick offers it again. An emergency stop runs the same rule backwards: the car hands its calls back "
 "before it stops existing as far as the bank is concerned.", 6),
("Move 7: yes, the lock makes dispatch happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every press and every tick take the same lock, is the whole building now a queue? "
 "It is, for under a microsecond each (a new hall call measured about 0.6 on a laptop), and the two cards above say exactly what sits on each "
 "side of the line. The rule behind that split is the one to say out loud: inside the lock goes only work whose cost you can count in lookups. "
 "Anything that talks to hardware, to a screen or to a person goes outside it. So when ten buttons are pressed at the same instant, the tenth "
 "rider waits about nine microseconds for the lock and then two seconds for a door to finish opening. One at a time is true, and nobody in the "
 "building can tell. The one thing inside the lock that "
 "grows with the building is the tick re-scoring every waiting call, which is why it is the first rung of the ladder in the next move.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Morning peak in a twenty-floor tower is about three presses a second, and the tick runs twice a second over six cars. Call each hold one "
 "microsecond, which is generous: that is about five microseconds of lock in every million, busy one part in two hundred thousand. Two "
 "presses collide about once a day. A door cycle takes two seconds whatever the lock does, so the lock is not the thing riders feel. The "
 "ladder in the picture is written cheapest first. Rung two carries the rule that stops it going wrong: two locks are only safe if every "
 "thread takes them in the same order. So the car lock is always taken after the index lock, never before it. Rung three gives "
 "each car its own thread and a mailbox (a queue of commands only that thread reads), so nothing about a car is shared any more. Say the "
 "arithmetic before you climb any of it. A hundred cars and four hundred floors "
 "would change the answer; six cars and twenty floors do not, and climbing the ladder anyway is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The six above, and six more. A car sits in maintenance (it must never be fed a call, and with every car down the call must queue rather than "
 "vanish). Someone presses floor 99, or UP on the top floor where there is no UP button (both rejected before anything is touched). Pressing the "
 "same button three times is one stop and one door opening. The OPEN button holds the doors and the car does not move; CLOSE lets it go; neither "
 "does anything while the car is travelling. And one invariant (a rule that must hold after every step) is worth testing on every tick of a "
 "long run. Whenever the panel shows an arrow, the car really is moving that way with its doors shut; a panel that lies is a bug riders see. "
 "Waiting time comes from the injected clock, so a test can say a rider waited two thousand milliseconds without sleeping. The follow-ups "
 "that make a claim have checks too, such as: the car the bank sends really is the one that arrives first, a fire recall ignores the buttons inside, and a "
 "keypad rider's floor is pressed only once they are on board. Each of these is a few lines in FailureTests.java; a design that cannot show "
 "its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; this paragraph is only for the two names that are <i>not</i> in the code, because saying those out loud is worth as much "
 "as the four that are. Singleton did not earn a place: one controller may run several banks in several buildings. So the bank is constructed "
 "and handed to the panels; a <code>getInstance()</code> would have made a second building impossible to test. Factory has not earned one either: "
 "cars arrive built, and it pays the day a building is read from a config file and \"freight\" has to become a constructor. Command arrives only on "
 "the third rung of move 8's ladder, when a press becomes a queued object in a car's mailbox. A pattern without a move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "Read the table, not this paragraph; it is here for the one thing a table cannot show, which is where the letters pull against each other. S says "
 "split. Split far enough, and ElevatorSystem would become a dispatcher, an index and a clock keeper: three objects that all need the same "
 "lock, and would have to reach into one another to keep it honest. The invariant wins: everything one lock protects stays in one class, and S is "
 "satisfied by giving that class one job, which is owning the invariant. That trade is the answer when they ask why the bank holds so much.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Every twist an interviewer has ever added to this problem is one of the five rows above, so the useful skill is saying which one it is before you "
 "start typing. The last row is the only one that is not obvious. The index goes behind a repository (an interface a database can sit behind). "
 "Once two controllers share a bank, the claim that today is a put under a lock becomes a conditional update: set the car id on that call's "
 "row where it is still null. One row updated means you won it; zero means somebody else did. That is the database's compare-and-set, the same "
 "idea as the lock. For all five rows the cars and the sweep do not change, which is the test that the derivation was right; page 05 has "
 "working code for each.", 12),
]
MOVES = [(t, MV[k], txt) for (t, txt, k) in MOVES_TEXT]

# ============================================================ page 5: follow-ups
FU = [
("It is 9am. Up-calls from the lobby should win, and idle cars should go back to the lobby to wait. At night, save energy instead. Do it without touching the bank.", "twist", 10,
 "For the morning, two pieces, and neither is a change to the bank. Up-peak is the morning rush, when nearly every trip starts in the lobby and goes up. "
 "UpPeakDispatch scores each car with the same cost function the normal rule uses. Then it takes five floors off the score of any car "
 "standing still when the call is at the lobby. It adds three to any car already holding more than four stops, so the crowd spreads out. "
 "Where idle cars <i>wait</i> is not a scoring question at all, so it is not in the strategy. LobbyParking reads the published snapshots "
 "and, for every car idle away from the lobby, presses that car's own ground-floor button. It is a caller, like a "
 "rider, which is why it needs no new method anywhere. Hand the rule in with one configure line and run the parking on a timer. "
 "The night rule has the same shape: EnergySavingDispatch adds a penalty to every car standing still, because starting a motor costs more "
 "power than carrying on. So a car already climbing past takes the call, even when a parked car is a floor closer.",
 X("the 9am rule change", "express and zoned cars")),
("Two riders press UP on floor 7 in the same millisecond. Prove exactly one car is sent.", "non-functional", 10,
 "The race lives between reading \"nobody owes 7 UP\" and writing \"car 1 owes it\". requestHall does the lookup, the scoring, the car's accept and "
 "the index write inside one lock, so no other press can run in that gap. The proof: forty threads wait at one CountDownLatch (a gate that opens "
 "once, for everyone), the gate opens, and all forty press 7 UP. The test collects the car ids they were given: one distinct car, one entry in the "
 "index, and exactly one stop across the whole bank. The second part of the same test fires six different buttons at once and checks that seven calls produced seven stops, so nothing was "
 "dropped and nothing was dispatched twice.",
 block(T, "        // 1. forty riders press", "        // 2. a car in maintenance")),
("Which scheduling algorithm is this: first-come-first-served, SCAN, or LOOK? Why not the other two?", "design", 5,
 "LOOK, and the difference from the other two is one condition. Take a car at floor 5 heading up, with buttons pressed in the order 9, then 6, then "
 "2. First-come-first-served serves them in that order: it climbs past floor 6 without stopping, opens at 9, comes back down to 6, then carries on "
 "to 2. Everyone rides longer, and the rider on 6 watches a car go by. SCAN sweeps end to end, like the arm of an old hard disk: it opens at 6, then 9, then carries on to floor "
 "19 before reversing. No pass is wasted, but the car always runs the full height of the building. LOOK is SCAN that turns at its last stop "
 "instead of the last floor: 6, then 9, then straight back down to 2. In this code that turn is <code>hasStopAhead</code>: the car reverses "
 "only when neither leg owes anything beyond where it is standing. Because the stops are two sorted sets, that question is one "
 "<code>higher</code> or <code>lower</code> lookup, not a loop over floors. The failure test proves it: a car sent to floor 8 turns at 8 and "
 "never runs on to 19.",
 sect(M, "    boolean hasStopAhead(int from, Direction leg)", "    /** From a standstill") + "\n" +
 block(M, "        // LOOK: turn around only", "        floor += heading.delta();") +
 "\n// car at 5 heading up; buttons pressed in the order 9, then 6, then 2.  [n] = the doors open there\n"
 "//   FCFS  5 6 7 8 [9] 8 7 [6] 5 4 3 [2]     passes 6 without stopping, then has to come back for it\n"
 "//   SCAN  5 [6] 7 8 [9] 10 .. 19 .. [2]     no wasted pass, but always runs to the end of the shaft\n"
 "//   LOOK  5 [6] 7 8 [9] 8 7 6 .. [2]        SCAN that turns at its last stop: what this code does\n"),
("A car is climbing to floor 6 for someone who pressed UP. Somebody else on 6 pressed DOWN. Do its doors open, and what happens to the lamp?", "functional", 5,
 "The doors open, because the doors always open for whoever is on that floor; what must not happen is that the DOWN lamp goes out. The two are "
 "different calls, HallCall(6, UP) and HallCall(6, DOWN), so they are different keys in the bank's index and they sit on different legs of the "
 "car's stop set. When the car opens while climbing, it clears floor 6 from the <i>up</i> leg only and hands back only HallCall(6, UP). The DOWN "
 "call is still owed, still in the index, and still on the down leg. The car finishes its climb, turns, comes back to 6 and opens again for the "
 "people going down. That is the whole reason the stop set is two sets keyed by direction rather than one set of floors.",
 block(M, "    /** Open the doors and clear the floor", "    /**\n     * The OPEN button inside the car") + "\n" +
 block(T, "        // 9. a car climbing serves", "        // 10. the door buttons")),
("One lock for the whole bank. Does that scale, or have you serialised the building?", "non-functional", 5,
 "Serialised means every press waits its turn in one line, and yes, it does, for under a microsecond each. It scales here, and the answer is "
 "arithmetic: about five microseconds of lock in every million, two presses colliding about once a day, against a door cycle of two seconds. "
 "Move 8 has that sum. What matters in the round is the number that "
 "would change your mind, so give it unprompted. At a hundred cars a press scores a hundred snapshots instead of six, and the tick re-scores "
 "every waiting call against all hundred: the locked section grows with cars times waiting calls. That is the point at which you climb the "
 "ladder below. Say rung two's rule out loud: two locks are only safe if every thread takes them in the same order.",
 "// rung 1: the tick re-scores every waiting call inside the lock. Offer a waiting call again only when\n"
 "//         something changed: a car freed up, came back into service, or a new car joined the bank.\n\n"
 "// rung 2: a lock per car, always taken AFTER the index lock, so two locks can never be taken in two orders.\n"
 "//   indexLock.lock();  try { chosen = score(...); } finally { indexLock.unlock(); }\n"
 "//   chosen.lock.lock(); try { chosen.accept(call); }  finally { chosen.lock.unlock(); }\n\n"
 "// rung 3: one owning thread per car with a mailbox; a press becomes a queued command, snapshots stay the only shared read.\n"
 "//   BlockingQueue<Runnable> mailbox;  while (running) { mailbox.poll().run(); car.step(policy); }\n"),
("A car is stopped in the middle of a sweep. What happens to the calls it was holding? And if maintenance can wait until the trip is over?", "functional", 10,
 "Nothing is lost, because the car never owned the calls on its own: the bank's index owns them and the car holds a copy. goOutOfService drops the "
 "car's stops, opens its doors where it stands, and returns every hall call it still owed. takeOutOfService then removes each of those from the "
 "index and puts it back on the waiting queue, and the next tick offers them to the cars again, so another car picks them up. The riders inside get "
 "out at the current floor, which is what the doors opening means. The gentle version is what Microsoft calls maintenance mode: take no new "
 "calls, finish the trip. DrainForService leaves the car out of every dispatch while it serves the stops it already owes. Once its "
 "snapshot shows it idle with nothing owed, the same class calls takeOutOfService.",
 block(M, "    List<HallCall> goOutOfService()", "    /**\n     * Forget every stop") +
 "\n" + sect(M, "    void takeOutOfService(int carId)", "    void recallAll(int floor)") +
 "\n" + X("maintenance mode", "destination dispatch")),
("The fire alarm goes off. Every car must go to the ground floor and ignore every button until the fire service releases it.", "twist", 10,
 "Recall is a mode of the whole bank, so the bank owns it. recallAll(floor) switches it on, and under the same lock every car drops its stops and "
 "is sent to that floor. The hall calls the cars owed go back on the waiting queue. While the mode is on, the dispatcher gives no car to any hall "
 "call, so every press waits on that queue, and requestCar refuses the buttons inside the cars. endRecall() switches it off, and the next tick "
 "offers the waiting calls to the cars again, so nothing pressed during the fire is lost. FireService is the fire panel's side: engage, watch "
 "until every car in service stands at the recall floor, release.",
 sect(M, "    void recallAll(int floor)", "    boolean holdDoors(int carId, int extraTicks)") +
 "\n// the two places that check the mode: requestCar(), then choose() for every hall call\n" +
 lines_with(M, "if (recallFloor != null) throw", "if (recallFloor != null) return null") + "\n" +
 X("fire service", "the cheap query") + "\n" +
 block(T, "        // 12. two ways out of normal service", "        // ... and maintenance mode")),
("Somebody presses OPEN while the doors are closing, and somebody else stands in the doorway. What do those buttons do?", "functional", 5,
 "Both are the same thing: they add ticks to the wait at this floor. <code>holdDoors(n)</code> raises the number of ticks left before the doors "
 "shut, and <code>closeDoorsNow()</code> drops it to one so the next tick shuts them. Both refuse, changing nothing, unless the doors are already "
 "open and the car is in service. That is what stops a rider pressing OPEN in a moving car and freezing it. Nothing a panel shows changes, so neither one publishes. The "
 "door sensor that fires when someone stands in the way calls exactly the same method as the OPEN button, with a longer hold. The car does "
 "not need to know a finger from a shoulder.",
 block(M, "    /**\n     * The OPEN button inside the car", "    /**\n     * Emergency stop or maintenance") + "\n" +
 block(M, "    /**\n     * The OPEN button inside a car, and the door sensor", "    /** Put a car back on the bank") + "\n" +
 block(T, "        // 10. the door buttons", "        // 11. the bank sends")),
("A rider on floor 19 presses DOWN during the morning rush. Can they wait forever?", "non-functional", 5,
 "Once a car has taken the call, the wait is bounded: the sweep never skips a stop it owes and never turns while something is ahead. The "
 "doors open there within one trip to the end of the shaft and back, at most 38 floors of travel here, and the failure test measures it. A "
 "call no car could take waits in <code>pending</code>, a LinkedHashSet (a set that keeps the order things were added), and every tick "
 "offers those calls again, oldest first. What you must name yourself is an unfair wait, not an endless one. Assignment is sticky (a call "
 "stays with the car that took it), so a call can wait on a busy car while another car stands idle. Lifting that needs a count per floor "
 "instead of a set, because the hallway and a rider inside can both want one floor. That count is also how \"cancel my floor\" works: the "
 "stop goes only when nobody wants it any more.",
 block(M, "    /** Offer every waiting call to the cars again", "    /** Tell every observer") +
 "\n// the bound on an assigned call, proven in FailureTests test 4:\n"
 "// check(ticksToServeBoth <= 2 * 19, \"served inside one sweep of the shaft\");\n\n"
 "// lifting sticky assignment: a floor can be owed by BOTH the hallway and a rider inside, so a set is not enough\n"
 "//   Map<Direction, NavigableMap<Integer, Integer>> legs;   // floor -> how many callers still want it\n"
 "//   release(call) or cancel(floor): if (--count == 0) legs.get(leg).remove(floor);   // only then does the stop go\n"),
("The lobby board asks \"how long until a car reaches 7?\" a thousand times a second. Make it cheap.", "non-functional", 5,
 "No new structure and no lock. Every car republishes an immutable CarSnapshot into one volatile field after each change, so reading where all six "
 "cars are is six field reads. The board asks the bank's estimate. It skips the cars that could not take the call (out of service, or unable "
 "to reach that floor) and scores the rest with the nearest-car rule's own cost function. The board multiplies that by the time per floor. That is "
 "O(cars) with no scan of anybody's stops. At the moment of the press, the number shown is the cost of the car the nearest-car rule would send. "
 "With a different rule handed in, such as zoning, the board must ask that rule instead, or the two can disagree.",
 X("the cheap query", "persistence") + "\n" +
 block(M, "    /**\n     * Floors of travel before a car could answer", "    // ---- private")),
("Two twists at once: cars 1 to 3 serve the low rise and 4 to 6 the high rise, and a full car should stop answering hall calls.", "twist", 10,
 "Both are the same move, which is the point: the interviewer is adding a <i>filter</i>, and a filter is a decorator. ZonedDispatch is handed the "
 "normal rule and a map of car to floor range. It drops every candidate whose zone does not cover the call and hands what is left to the rule "
 "underneath. CapacityAwareDispatch is handed the normal rule and a CarLoad per car, which counts riders and kilos and refuses a boarding that would "
 "pass either limit. It drops the full cars and hands the rest down. Either one may end up with nobody left, and then it returns null, which the "
 "bank already understands: the call waits on the queue instead of being forced onto the wrong car. A full car keeps sweeping and keeps serving what "
 "it already owes; it just stops being offered more. Neither the bank nor the car nor the sweep changes a line, and the two decorators stack, so "
 "zoned <i>and</i> capacity-aware is <code>new ZonedDispatch(new CapacityAwareDispatch(nearest, load), zones)</code>.",
 X("express and zoned cars", "the door rule changes too")),
("Destination dispatch: riders type the floor they want on a keypad in the lobby.", "twist", 10,
 "The keypad knows more than a button does, so use it. DestinationDispatch.enter takes \"I am on 0, I want 12\", notes the 12, presses the "
 "ordinary hall button, and tells the rider which car to stand at. As the dispatch rule, it prefers a car already collecting riders for 12, and "
 "otherwise lets the normal rule decide. The 12 is pressed only at boarding: the same class listens to the cars and presses it when that car "
 "opens at the rider's floor, going their way. Pressed any earlier, a car that reached 12 first would open there for nobody and leave the rider "
 "with no stop. One limit to say out loud: the bank keeps one car per hall button, so riders on one floor going one way share the car already coming.",
 X("destination dispatch", "request feasibility") + "\n" +
 block(T, "        // 13. riders who type their floor", "        // ... and Microsoft's rule")),
("Microsoft's version: one lift, fifty floors, twenty people at a time, and no rider may sit through more than five stops. When may the lift take a new request?", "twist", 10,
 "Each request now carries both floors, so every rider's trip is known, and that is what makes the rule checkable. StopBudget keeps, for the "
 "sweep the car is on, a sorted set of the floors it stops at and the list of trips it has taken. A new trip adds at most two floors. For every "
 "rider, the newcomer included, the stops they sit through are the floors after the one they board at, up to and including their own: one "
 "<code>subSet(...).size()</code> each. The trip is taken only if nobody passes five and the car never holds more than twenty; checking and "
 "recording are one synchronized step, the bank's lock rule again. Stops already made stay in the set until the sweep ends, so a rider who has "
 "sat through three is never promised five more. A refused rider waits for the next sweep.",
 X("request feasibility", "fire service") + "\n" +
 block(T, "        // ... and Microsoft's rule", "        System.out.println(failures")),
("Persist it. Or: one controller for forty buildings.", "twist", 5,
 "The index of who owes which call goes behind a repository interface, and the in-memory map becomes one implementation. The services do not "
 "change. The claim, which today is a put under a lock, becomes a conditional update: set the car id on that call's row where it is still null. One "
 "row updated means this controller won it, zero rows means another controller did and it must pick again. That is the database's compare-and-set, "
 "the same idea as the lock: one indivisible step decides the winner, and it is what lets two controllers share one bank. The code stops at the "
 "repository, but it also answers \"resume safely after a power cut\", another Microsoft ask. The rows survive the restart, each car's floor is "
 "read back from the car itself, and a call whose car does not come back is released and offered again.",
 XE("persistence")),
("Where does time come from, and how do you prove a rider waited 2000 ms without sleeping?", "design", 5,
 "The bank has a Clock it was handed. It stamps the moment a hall button was first pressed and works out the wait when the doors open there. "
 "Nothing else reads the time: the wall clock is only the default Clock, and a test hands in its own. The tick is the other half: a tick is one floor or one door cycle, so a test drives the "
 "world forward by calling tick and asserting, with no sleeps and nothing flaky. The failure test below hands in a clock it moves by five hundred "
 "milliseconds per tick, presses floor 3, ticks four times and checks the recorded wait is exactly two thousand milliseconds. Say the second "
 "benefit out loud: because time is a parameter, a peak-hour simulation of ten thousand presses runs in a second.",
 "// the bank stamps the first press and closes the wait when the doors open, both from the injected clock\n"
 "raisedAtMs.putIfAbsent(call, clock.nowMs());              // in requestHall, under the lock\n"
 "Long raised = raisedAtMs.remove(served);                  // in tick(), when a car served it\n"
 "if (raised != null) { totalWaitMs += now - raised; servedCalls++; }\n\n"
 + block(T, "        // 8. waiting time is read", "        // 9. a car climbing serves")),
("Point at the line for each pattern you used, and for each SOLID letter. Which ones did you deliberately not use?", "design", 5,
 "Four patterns, each the output of a move, never chosen up front. Strategy: which car answers and how long the doors stay open both sit behind "
 "one-method interfaces the bank is handed. Decorator: zoning and capacity filter the candidates and then defer to the rule underneath instead of "
 "replacing it. Observer: the bank announces that a car changed, after the lock, and has no idea what a panel is. State: the car's life as an enum "
 "with one rule about what a tick may do. Not used, on purpose: Singleton, because one controller may run several banks; Factory, until cars are "
 "built from a config file. For SOLID the code is the argument, and the five lines below are where each letter lives.",
 "// Strategy (move 3): a rule behind an interface, handed in -- also SOLID's I, one method per interface\n"
 "interface DispatchStrategy { ElevatorCar pick(List<ElevatorCar> cars, HallCall call); }\n"
 "void configure(DispatchStrategy d, DoorPolicy p) { lock.lock(); try { this.dispatch = d; this.doorPolicy = p; } finally { lock.unlock(); } }\n\n"
 "// Decorator (move 3): filter the candidates, then defer to the rule underneath -- also SOLID's O, nothing opened\n"
 "class ZonedDispatch implements DispatchStrategy { private final DispatchStrategy base; /* ... base.pick(allowed, call) */ }\n"
 "bank.configure(new ZonedDispatch(new NearestCarStrategy(0, 19), zones), new LobbyDwellPolicy(0, 3, 1));\n\n"
 "// Observer (moves 3 and 4): the bank announces, after the lock; it does not know what a screen is\n"
 "interface ElevatorObserver { void onChange(CarSnapshot s); }\n"
 "for (CarSnapshot s : snaps) for (ElevatorObserver o : observers) try { o.onChange(s); } catch (RuntimeException e) { /* logged */ }\n\n"
 "// State (move 6): the car's life, and the rule that one tick is one thing\n"
 "enum CarState { IDLE, MOVING_UP, MOVING_DOWN, DOORS_OPEN, MAINTENANCE }\n"
 "if (doors == DoorState.OPEN) { /* the doors own this tick; the car does not move */ }\n\n"
 "// SOLID's S: one reason to change each\n"
 "class StopSet { /* the sweep questions */ }   class ElevatorCar { /* its own physics */ }   class ElevatorSystem { /* dispatch + the lock */ }\n"
 "// SOLID's L: any implementation drops in; the bank never checks the concrete type\n"
 "ElevatorCar chosen = dispatch.pick(eligible, call);\n"
 "// SOLID's D: depend on the interface, hand in the implementation; tests hand in fakes\n"
 "bank.setClock(() -> now[0]);   bank.addObserver(s -> { throw new RuntimeException(\"panel is down\"); });\n"),
("Enum states or ElevatorCar subclasses? Where would you use a Factory?", "design", 3,
 "Enum, until a state gains behaviour of its own. IDLE, MOVING_UP, DOORS_OPEN and MAINTENANCE differ only in what the next tick may do, which is "
 "data: a few branches in one method you can read end to end. A subclass pays when a kind of car really behaves differently, such as a freight car "
 "with its own door timing and a key switch. Even then, the cheap version is a different DoorPolicy, not a new class of car. Factory earns "
 "its place when cars and zones are built from a configuration file: a registry that maps \"freight\" to a constructor turns adding a kind into one "
 "registration instead of a growing switch.",
 "// data, not classes: the state only decides what the next tick may do\nenum CarState { IDLE, MOVING_UP, MOVING_DOWN, DOORS_OPEN, MAINTENANCE }\n"
 "if (doors == DoorState.OPEN) { /* close */ } else if (stops.servesOnLeg(floor, heading)) { /* open */ } else { floor += heading.delta(); }\n\n"
 "// the cheap version of a 'different kind of car' is a different rule, not a subclass\nbank.configure(dispatch, new LobbyDwellPolicy(0, 3, 1));\n\n"
 "// a factory only once cars are built from strings: a registry, so a new kind is one registration\n"
 "Map<String, Function<Integer, ElevatorCar>> registry = Map.of(\"freight\", id -> new ElevatorCar(id, 0, 5, 0));\n"
 "ElevatorCar c = registry.get(kind).apply(nextId);\n"),
]

IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your five to eight clarifying questions; then type in the order of Main.java: the three enums, the two records '
 '(HallCall and CarSnapshot), StopSet with its sweep questions (the one that matters is hasStopAhead), ElevatorCar with accept, pressFloor, step '
 'and the two door buttons, the two rule interfaces with one implementation each, the two observers, ElevatorSystem with its lock and the order '
 'inside requestHall, the thin panels, and a main that ticks the world and races forty threads at one button.</div></div>')

spec = dict(
    slug="elevator",
    title="Elevator System",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: a tick-by-tick demo, 13 failure tests and a 40-thread race pass",
    problem_body=PROBLEM_BODY,
    derivation_lead="Run these on any LLD (a lift bank, a parking lot, BookMyShow, Splitwise) and the class diagram, the lock, the tests, the "
                    "patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is named "
                    "before the move that produced it.",
    moves=MOVES,
    uml_svg=UMLSVG,
    how_to_read=HOW_TO_READ,
    code_intro="Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each class and method says "
               "what it does and what it guarantees; read only those first for the shape, then the bodies for the mechanics. Each copy button "
               "copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up's reference code, with an ExtDemo main "
               "that runs them all) and FailureTests.java (thirteen claims proven; "
               "<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).",
    files=[("Main.java", M), ("Extensions.java", E), ("FailureTests.java", T)],
    test_class="FailureTests",
    followups=FU,
    implement_card_html=IMPLEMENT_CARD,
)
build(spec)
