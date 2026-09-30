# Dining Philosophers LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re, math
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"mt-dining/Main.java").read_text()
ext   = (H/"mt-dining/Extensions.java").read_text()
tests = (H/"mt-dining/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.rfind("/**", 0, ext.index("Runs every extension"))]
    i = next(m for m in marks if a in ext[m:m+220])
    j = next(m for m in marks if m > i and b in ext[m:m+220])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def M(a, b=None):
    """slice Main.java from one declaration to the next"""
    return sect(src, a, b)

RED  = "#ff6b6b"
BLUE = "var(--acc2)"

# ============================================================ page 01: the problem
pf = _D
# row 1: one meal, the happy path
pf += _tx(88, 57, "one meal", "var(--acc)", 13)
meal = [("think", "holding nothing at all"), ("take BOTH forks", "the policy decides how"),
        ("eat", "both forks in hand, 3 ms"), ("put both back", "in a finally, always")]
for k, (t, sub) in enumerate(meal):
    x = 175 + k*260
    pf += _bx(x, 30, 240, 54, t, sub, acc=(k == 1))
    if k < 3: pf += _ar("M%s 57 H%s" % (x+240, x+260), True)
pf += _ar("M555 84 V97", dash=True) + _bx(380, 97, 420, 40, "interrupted, or gave up: put back what you hold", "nothing is ever left half-held", dash=True)
# row 2: the protocol that must never happen
pf += _tx(88, 182, "the trap", RED, 13)
trap = [("take the fork on your left", "everyone can, at once"), ("reach for the right-hand one", "your neighbour has it"),
        ("all five hold one fork", "and all five are waiting"), ("nobody ever moves again", "no error, no crash, no log")]
for k, (t, sub) in enumerate(trap):
    x = 175 + k*260
    pf += _bx(x, 155, 240, 54, t, sub, acc=(k == 1), dash=(k >= 2))
    if k < 3: pf += _ar("M%s 182 H%s" % (x+240, x+260))
# the run line: the three methods the table itself has to offer
pf += _tx(88, 245, "run", "var(--acc)", 13)
pf += _tx(175, 245, "start() releases all five in the same instant &middot; awaitFinish(ms) waits with a deadline &middot; interruptAll() rescues a table that is stuck",
          "var(--text)", 12, "start")
# the read line
pf += _tx(88, 275, "read", "var(--acc)", 13)
pf += _tx(175, 275, "at any moment, without stopping anybody: who is eating, how many meals has each had, is anyone waiting in a ring?",
          "var(--text)", 12, "start")
pf += _tx(615, 315, "five threads reach in the same instant: a fork is in exactly one hand, and no set of philosophers may end up waiting on each other in a ring",
          "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 330, pf)

# one dinner, replayed
pe = _D + '<path d="M60 40 H930" stroke="var(--line)" stroke-width="1.5"/>' + _tx(1055, 30, "a second run, from the start", "var(--muted)", 10.5)
ev = [("00.000  five sit down", ["one latch opens and five threads", "reach in the same instant",
                                "forks 0 to 4 are all on the table"], False, "var(--text)"),
      ("00.000  left fork first", ["all five take a left fork:", "p0 has 0, p1 has 1 ... p4 has 4",
                                   "p0 waits for 1 ... p4 waits for 0"], True, RED),
      ("00.400  the grace runs out", ["the first to give up drops its left fork", "and the ring unravels behind it:",
                                      "0 meals in those 400 ms, the ring named"], False, "var(--text)"),
      ("next run  one line changed", ["lower fork id first: 10,000 meals", "2,000 each, two eating at once,",
                                      "8 ms, no fork ever in two hands"], True, "var(--acc)")]
for k, (t, lines, acc, tcol) in enumerate(ev):
    x = 60 + k*290
    fill = "none" if k == 3 else ("var(--acc)" if k != 1 else RED)
    pe += '<circle cx="%s" cy="40" r="5" fill="%s" stroke="var(--acc)"/>' % (x+125, fill) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc, tcol=tcol)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>N philosophers around one table, N forks, one between each pair; philosopher i uses forks i and (i+1) mod N.</li>
<li>A philosopher thinks, takes both of its forks, eats, and puts both back &mdash; for a set number of rounds.</li>
<li>Two philosophers who do not share a fork must be able to eat at the same time.</li>
<li>The rule for taking both forks is swappable: ordering, a waiter, try-and-back-off, one per class.</li>
<li>The broken protocol must be demonstrable on purpose, and the circular wait reported, not guessed at.</li>
<li>A supervisor can stop a run: cleanly between meals, or by force if somebody is stuck.</li>
<li>Read, at any moment: meals per philosopher, who is hungry, how many are eating.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>A fork is held by exactly one philosopher at a time &mdash; measured, not assumed.</li>
<li>No deadlock: the run always ends, and the reason is structural, not a timeout.</li>
<li>No fork is ever left held: every failure path returns everything it took.</li>
<li>Taking and returning a fork is O(1); finding a ring is O(N) over an array, off the hot path.</li>
<li>The fix must keep the parallelism: floor(N/2) philosophers still eat at once.</li>
<li>Every philosopher keeps getting meals in a bounded run (fairness is a knob, and its limits are stated).</li>
<li>In memory, one JVM, threads and ReentrantLocks (say it; leases across processes are a follow-up).</li></ul></div></div>
'''

PROMPT = ('"Five philosophers sit around a table. Between each pair there is one fork, and a philosopher needs the two '
          'forks beside it to eat. Write it so they all keep eating and no philosopher waits forever. I want working '
          'code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Five philosophers sit in a circle. There is one fork between '
 'each pair, so five forks for five people, and eating needs two: the one on your left and the one on your right. Each '
 'philosopher spends its life thinking, getting hungry, eating, and putting the forks back. A fork can only be in one '
 'hand at a time, so a philosopher who wants to eat may have to wait for a neighbour to finish. That is the whole '
 'story, and it is a trap: write the obvious thing &mdash; take the left fork, then the right &mdash; and if all five '
 'reach at the same instant, every one of them ends up holding one fork and waiting for a neighbour who is waiting for '
 'them. Nothing crashes, nothing is logged, no thread wakes up: the program simply stops for ever. The thing that must '
 'always be true is two-sided: a fork is in exactly one hand, and the set of philosophers waiting on each other must '
 'never close into a ring.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Working code with a <code>main</code> that runs '
 'threads, not a picture of a table. The interviewer is watching for, in this order: the questions you ask before '
 'typing (how many, block or time out, must the deadlock be shown); which classes exist and what a fork actually is '
 '(a lock, not a boolean); one meal end to end; the race &mdash; can you make the deadlock happen on purpose and say '
 'which of the four conditions each fix removes; where the acquisition rule lives, so a new fix is a new class rather '
 'than an edit; what happens when a philosopher is interrupted or throws mid-meal; and only then the twists: '
 'starvation, metrics, a graceful stop, and where the same problem shows up in production code.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>How many philosophers, and is N fixed at construction?</td><td>Five, fixed</td><td>An array of forks; left = i, right = (i+1) mod N (moves 1, 5)</td></tr>'
 '<tr><td>Is a fork a flag I guard, or a lock in its own right?</td><td>A lock</td><td><code>Fork</code> wraps a <code>ReentrantLock</code> (move 1). The other shape &mdash; one lock over a state array, one condition per seat &mdash; is on page 05</td></tr>'
 '<tr><td>Deadlock-freedom only, or no starvation either?</td><td>No deadlock first; fairness as a knob</td><td>Which fix you pick and what the tests can honestly claim (moves 4, 9)</td></tr>'
 '<tr><td>Does a hungry philosopher block for ever, or give up?</td><td>Block; a timeout policy is one of the options</td><td>Whether <code>acquireBoth</code> may throw, and what the caller does (moves 3, 6)</td></tr>'
 '<tr><td>Do you want the deadlock shown, or only avoided?</td><td>Shown &mdash; on purpose and safely</td><td>A naive policy with a grace timeout, plus a detector (moves 3, 9)</td></tr>'
 '<tr><td>Fixed rounds, or run until somebody stops it?</td><td>Fixed rounds; a stop flag is a follow-up</td><td>How the demo ends and how a supervisor stops a live run (moves 6, 12)</td></tr>'
 '<tr><td>Do we need live metrics: meals each, who is waiting?</td><td>Yes, and reading them must cost nothing</td><td>Volatile counters per philosopher plus an observer (moves 5, 3)</td></tr>'
 '<tr><td>One JVM, or forks shared across processes?</td><td>One JVM, threads and locks</td><td>No leases and no fencing tokens yet; a follow-up (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One dinner, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> a fork is a lock, not a boolean; five philosophers, fixed, each with '
 'forks i and (i+1) mod 5; a philosopher blocks rather than polls, and the lock is interruptible so a supervisor can '
 'rescue it; the acquisition rule is the one thing that changes, so it goes behind an interface; I will show the '
 'deadlock on purpose, with a grace timeout so nothing hangs, and then delete it. Named as out of scope: starvation '
 'proofs, forks across processes, Chandy-Misra &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a PHILOSOPHER takes two FORKS, EATS and puts them back; a TABLE seats them in a ring; a POLICY decides how to take both",
          "var(--text)", 12.5)
for x, w, t, sub, solid in [(30, 175, "Fork", "who holds it: a lock", 1), (225, 185, "Philosopher", "state, meals: a thread", 1),
                            (430, 185, "DiningTable", "the ring, the seats", 1), (635, 180, "ForkPolicy", "no state: an interface", 0),
                            (835, 180, "PhilosopherState", "a fixed list: an enum", 0), (1035, 175, "deadlock", "not a class: a shape", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(solid), dash=not solid) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: an interface, a fixed list of values, or a property of the whole graph", "var(--muted)", 11)
m1 += _tx(615, 210, "a fork is the one worth arguing about: \"held by exactly one philosopher at a time\" IS mutual exclusion, so it is a lock, not a boolean that would then need its own lock", "var(--acc)", 11)
MV[1] = _mv(1230, 225, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("take one fork, put it back", "Fork  (owns the lock and the owner)", "fork.pickUp(id) / putDown(id)"),
                                       ("get BOTH forks, or neither", "ForkPolicy  (owns the rule, no state)", "policy.acquireBoth(p)"),
                                       ("think, eat, count the meal", "Philosopher  (owns its own counters)", "philosopher.run()"),
                                       ("seat N in a ring, start them together", "DiningTable  (owns forks and seats)", "table.start()"),
                                       ("who holds what, who waits for what", "WaitGraph  (owns nothing: a read)", "WaitGraph.find(forks, seats)")]):
    y = 22 + k*54
    m2 += _bx(30, y, 340, 42, verb, "the verb") + _ar("M370 %s H430" % (y+21), True)
    m2 += _bx(430, y, 420, 42, cls, "the class whose state it touches", acc=True) + _ar("M850 %s H900" % (y+21), True)
    m2 += _bx(900, y, 300, 42, meth, "the method")
m2 += _tx(615, 310, "\"get both forks\" is the one verb whose owner is not obvious: it touches two forks and belongs to neither, so it becomes a thing of its own", "var(--muted)", 11)
MV[2] = _mv(1230, 325, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 95, 220, 90, "DiningTable", "configure(think, eat)", acc=True)
for k, (t, sub, impl) in enumerate([("ForkPolicy", "how to get both forks", "Naive | Ordered | Arbitrator | Backoff | Asymmetric | Monitor"),
                                    ("Work", "what thinking and eating mean", "instant | sleep 3 ms | one that throws"),
                                    ("DiningObserver", "who wants to be told", "a tracer | FairnessMetrics | a dashboard"),
                                    ("Clock", "where time comes from", "System::currentTimeMillis | a test's number")]):
    y = 22 + k*56
    m3 += _ar("M250 140 H330 V%s H400" % (y+21), True, True) + _bx(400, y, 300, 42, t, sub, dash=True)
    m3 += _bx(725, y, 475, 42, impl, "the classes that can be handed in") + _ar("M725 %s H700" % (y+21))
m3 += _tx(615, 268, "dashed green = handed in. Neither the table nor the philosopher ever builds one of these, so a new deadlock fix is a new class and one changed line at the call site", "var(--muted)", 11)
m3 += _tx(615, 288, "this is where Strategy is born, and nowhere else: every idea in the literature &mdash; ordering, a waiter, timeouts, asymmetry &mdash; is one implementation of the same two methods", "var(--acc)", 11)
MV[3] = _mv(1230, 302, m3)

# move 4: the shared state, the lock, and the ring (threads on lanes, then the cycle)
m4 = _D + _tx(300, 28, "five philosophers, released in the same instant", "var(--text)", 12.5)
m4 += _tx(205, 50, "t = 0", "var(--muted)", 10.5) + _tx(440, 50, "t = 0 plus a few nanoseconds", "var(--muted)", 10.5)
for k in range(5):
    y = 62 + k*38
    m4 += _tx(40, y+19, "p%d" % k, "var(--acc)", 12, "start")
    m4 += _bx(90, y, 210, 28, "takes fork %d" % k, "", acc=True)
    m4 += _ar("M300 %s H330" % (y+14))
    m4 += _bx(330, y, 270, 28, "waits for fork %d" % ((k+1) % 5), "", dash=True)
m4 += _tx(300, 272, "nobody is doing anything wrong; every one of them is one step from eating", RED, 11)
# the ring
CX, CY, R = 900, 185, 148
pts = []
for k in range(5):
    a = math.radians(-90 + 72*k)
    pts.append((CX + R*math.cos(a), CY + R*math.sin(a)))
for k in range(5):
    (x1, y1), (x2, y2) = pts[k], pts[(k+1) % 5]
    dx, dy = x2-x1, y2-y1
    L = math.hypot(dx, dy); ux, uy = dx/L, dy/L
    sx, sy = x1 + ux*56, y1 + uy*56
    ex, ey = x2 - ux*56, y2 - uy*56
    m4 += '<path d="M%.0f %.0f L%.0f %.0f" fill="none" stroke="%s" stroke-width="1.4" stroke-dasharray="5 4" marker-end="url(#uArr)" color="%s"/>' % (sx, sy, ex, ey, RED, RED)
    mx, my = (x1+x2)/2, (y1+y2)/2                      # push the label outward, off the arrow
    nx, ny = mx-CX, my-CY; nl = math.hypot(nx, ny)
    m4 += _tx(mx + nx/nl*30, my + ny/nl*30 + 4, "wants fork %d" % ((k+1) % 5), RED, 10)
for k, (x, y) in enumerate(pts):
    m4 += _bx(x-50, y-19, 100, 38, "p%d" % k, "holds fork %d" % k, acc=True)
m4 += _tx(CX, CY-10, "a circular wait", RED, 12.5) + _tx(CX, CY+8, "every arrow points at", "var(--muted)", 10.5) + _tx(CX, CY+23, "somebody who is also waiting", "var(--muted)", 10.5)
m4 += _card(30, 292, 570, 68, "the same five, one line changed", ["take the LOWER-NUMBERED fork first: p4 reaches for fork 0", "before fork 4, so it never holds 4 while waiting for 0"], acc=True)
m4 += _tx(615, 374, "the shared state is the fork and its owner is itself: one lock per fork, never one lock for the table. The failure is a shape, not a lost update.", "var(--muted)", 11)
m4 += _tx(615, 394, "four things must be true at once for that ring: exclusive forks, hold-one-and-wait, no taking a fork back by force, and a cycle. Delete ONE and it cannot form.", "var(--acc)", 11)
MV[4] = _mv(1230, 408, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("which two forks are mine?", "forks[i] and forks[(i+1) % n], an array", "O(1), no map"),
                                      ("who is holding fork 3 right now?", "a volatile int owner on the fork", "O(1) read"),
                                      ("what is p2 waiting for?", "a volatile int waitingFor on the philosopher", "O(1) read"),
                                      ("is there a ring anywhere?", "walk the n edges those two fields make", "O(n), off the path"),
                                      ("how many meals has p4 had?", "a long written only by p4's own thread", "O(1), no contention"),
                                      ("may I even sit down? (the waiter)", "Semaphore(n - 1)", "O(1)")]):
    y = 18 + k*44
    m5 += _bx(30, y, 360, 36, q, "the question") + _ar("M390 %s H450" % (y+18), True)
    m5 += _bx(450, y, 520, 36, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+18), True) + _bx(1030, y, 170, 36, cost, "")
m5 += _tx(615, 296, "nothing here is a map, because nothing here is looked up by a key: a ring of n is an array, and the neighbour of i is arithmetic", "var(--muted)", 11)
m5 += _tx(615, 316, "meals are counted in a field owned by one thread and read after join(), which is a happens-before edge: a shared counter would add contention to measure contention", "var(--acc)", 11)
MV[5] = _mv(1230, 330, m5)

# move 6: the life cycle and the ORDER of one round
m6 = _D
for k, (t, sub, acc) in enumerate([("THINKING", "holds nothing", 0), ("HUNGRY", "reaching, holds 0 or 1", 0), ("EATING", "holds both", 1)]):
    m6 += _bx(30 + k*185, 46, 165, 46, t, sub, acc=bool(acc))
    if k < 2: m6 += _ar("M%s 69 H%s" % (195 + k*185, 215 + k*185), True)
m6 += _ar("M482 46 V22 H112 V46", True) + _tx(297, 16, "put both back, and round again", "var(--muted)", 10.5)
m6 += _bx(400, 150, 180, 46, "DONE", "rounds are over") + _ar("M490 92 V150")
m6 += '<rect x="620" y="20" width="590" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(915, 44, "the order inside one round, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 think, then say HUNGRY -- holding nothing, so nobody is blocked by you",
                       "2 ask the POLICY for both forks: it returns with both, or with none",
                       "3 only now say EATING and eat: the meal is counted after it happened",
                       "4 a finally puts both forks back, whatever happened while eating",
                       "5 say THINKING, then tell the observers -- forks already on the table",
                       "an interrupt, a timeout or an exception cannot leave a fork held,",
                       "which is why the table is never poisoned by one bad philosopher"]):
    m6 += _tx(635, 68 + k*21, l, "var(--muted)" if k > 4 else "var(--text)", 11, "start")
# the lanes of one round: what is held, over time
m6 += _tx(615, 240, "one round of p0 on a clock, and what is in its hands", "var(--text)", 12.5)
segs = [(30, 150, "think", "holds 0", 0), (180, 110, "HUNGRY", "holds 0", 0), (290, 170, "takes fork 0", "holds 1", 0),
        (460, 170, "takes fork 1", "holds 2", 1), (630, 330, "eat, 3 ms", "holds 2", 1), (960, 240, "puts both back", "holds 0", 0)]
for x, w, t, sub, acc in segs:
    m6 += _bx(x, 258, w, 44, t, sub, acc=bool(acc))
m6 += _ar("M430 320 V306", dash=True) + _tx(430, 336, "interrupted here: fork 0 goes back, nothing eaten", RED, 10.5)
m6 += _ar("M790 320 V306", dash=True) + _tx(830, 336, "it throws here: the finally still returns both forks", RED, 10.5)
m6 += _tx(615, 362, "the state is a field on the philosopher, not a shared map: it is written by one thread and read by the detector and the metrics, which is all a volatile int is for", "var(--muted)", 11)
MV[6] = _mv(1230, 376, m6)

# move 7: what is inside the lock, and how many eat at once
m7 = _D + _tx(615, 26, "fifteen milliseconds at the table: five philosophers, a 3 ms meal, resource ordering", "var(--text)", 12.5)
X0, PX = 150, 1030/15.0
for t in range(0, 16, 3):
    m7 += '<path d="M%.0f 44 V235" stroke="var(--line)" stroke-dasharray="3 4"/>' % (X0 + t*PX) + _tx(X0 + t*PX, 38, "%d ms" % t, "var(--muted)", 10)
sched = {0: [(0, 3), (9, 12)], 1: [(3, 6), (12, 15)], 2: [(0, 3), (6, 9)], 3: [(3, 6), (9, 12)], 4: [(6, 9), (12, 15)]}
for k in range(5):
    y = 52 + k*36
    m7 += _tx(40, y+18, "p%d" % k, "var(--acc)", 12, "start") + _tx(75, y+18, "forks %d,%d" % (k, (k+1) % 5), "var(--muted)", 10, "start")
    for (a, b) in sched[k]:
        m7 += _bx(X0 + a*PX, y, (b-a)*PX, 28, "eat", "", acc=True)
m7 += _tx(615, 256, "two eat in every slot and never three: with five philosophers the ceiling is floor(5 / 2) = 2, and that is the problem's ceiling, not the code's", RED, 11)
m7 += _card(30, 276, 570, 120, "what a fork's lock actually costs",
            ["two tryLocks, two unlocks and a little bookkeeping per meal", "measured: 10,000 meals with no eating at all in ~15 ms",
             "so about 1.5 microseconds of locking per meal", "a real 3 ms meal is two thousand times that"], acc=True)
m7 += _card(630, 276, 570, 120, "so what is the queue for?",
            ["not the lock's internals: the fork itself", "the fork is held for the WHOLE meal, on purpose",
             "this is the rare case where the critical section IS the work", "shortening it means eating faster, nothing else"])
m7 += _tx(615, 414, "every other design says \"hold the lock for microseconds\". Here you cannot: a philosopher holds both forks for as long as it eats, so the ORDER of taking them is the design.", "var(--muted)", 11)
MV[7] = _mv(1230, 428, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "is this fast? do the arithmetic before you optimise", "var(--text)", 12)
for k, l in enumerate(["10,000 meals with instant meals: ~15 ms, so ~1.5 us of forks per meal",
                       "a real meal of 3 ms is 2,000 times the cost of the two locks",
                       "five philosophers, two eating at once: floor(n / 2) is the ceiling",
                       "think = eat means 2.5 want to eat and 2 can, so ~20% of life is waiting",
                       "the waiter costs one more counter: 10,000 meals in ~40 ms",
                       "drop-and-retry drops ~180 forks: the same 10,000 in ~400 ms"]):
    m8 += _tx(35, 68 + k*25, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, cheapest first", "var(--text)", 12)
for k, (t, sub) in enumerate([("1  resource ordering: lower fork id first", "one comparison, nothing else -- but you must own the numbering"),
                              ("2  a waiter: Semaphore(n - 1) seats", "no numbering needed; one shared counter, fair queue"),
                              ("3  tryLock with random backoff", "no order, no waiter; pays in dropped forks, livelocks without the randomness")]):
    m8 += _bx(600, 58 + k*54, 600, 46, t, sub, acc=(k == 0))
m8 += _tx(615, 236, "beyond the ladder: Chandy-Misra, where forks are clean or dirty tokens passed between neighbours &mdash; no order, no waiter, starvation-free. Named, not built.", "var(--acc)", 11)
MV[8] = _mv(1230, 250, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("all five take a left fork at once", "the ring, on purpose; test 1: a wedge latch, a grace timeout, and a detector that names 5 philosophers"),
                                ("a philosopher waits for ever", "ordering deletes the cycle; test 2: 10,000 meals finish with no deadlock, 2,000 each"),
                                ("the interviewer bans renumbering", "a waiter with n-1 seats; test 3: 5,000 meals, and every seat comes back"),
                                ("eating throws half way through", "a finally around the meal; test 6: p2 throws 200 times, every fork still ends free"),
                                ("a wedged run has to be broken", "lockInterruptibly; test 7: an interrupt unwinds 5-second meals at once"),
                                ("the \"fix\" is one lock for the table", "measure it; test 5: peak eaters falls from 2 to 1 and the same 150 meals take ~650 ms instead of ~380"),
                                ("a detector that cries wolf", "test 11: 40 samples of a healthy run, and no ring confirmed -- one sample is only a suspicion"),
                                ("the wait/notify version sleeps for ever", "one condition per seat, signalled after the change; test 15: one condition + signal() loses the wakeup")]):
    y = 16 + k*40
    m9 += _bx(30, y, 310, 36, bad, "") + _ar("M340 %s H380" % (y+18), True) + _bx(380, y, 820, 36, fix, "", acc=True)
m9 += _tx(615, 354, "every claim on this page has a test: FailureTests.java runs thirty-seven of them in about three seconds and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 368, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 830)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface ForkPolicy { acquireBoth(p); releaseBoth(p); }", None), ("every deadlock fix is a class, not an edit", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(id, state) after the forks are back, in a try/catch", None), ("metrics that cannot slow a meal down", None)],
          [("State", "var(--text)"), ("move 6", None), ("THINKING &rarr; HUNGRY &rarr; EATING, one field, one writer", None), ("the detector and the metrics read one int", None)],
          [("Decorator", "var(--text)"), ("move 12", None), ("stoppable(work): wraps any Work and adds the stop check", None), ("a graceful stop without touching the loop", None)],
          [("Monitor object", "var(--text)"), ("move 1", None), ("Fork = the data plus the lock that guards it, in one class", None), ("nobody can touch a fork without the lock", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the table is handed to its caller; nothing calls getInstance()", "var(--muted)"), ("a test builds four tables in four lines", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("new OrderedPolicy() at the call site is the whole construction", "var(--muted)"), ("it earns the name when policies come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a table is n, a policy and a round count", "var(--muted)"), ("three required fields is a constructor", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "and the watchdog is not a pattern at all: a detector is a monitor, and naming it a \"pattern\" is how people end up shipping the naive protocol with an alarm on it", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Fork: mutual exclusion. Philosopher: the loop. Table: the wiring. A policy: one rule.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("AsymmetricPolicy is a new file; Philosopher and DiningTable never change", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("policy.acquireBoth(this);  never \"is this the ordered one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one job each", None), ("move 3", None), ("ForkPolicy is two halves of one rule; Work, DiningObserver and Clock have one method", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("new DiningTable(5, new ArbitratorPolicy(5), 1000).configure(think, eat)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "asymmetric seats, Chandy-Misra", "a new class behind ForkPolicy plus one line at the call site", "", "move 3"),
        ("someone new wants to know", "fairness, a dashboard, tracing", "one more observer, called after the forks are back", "", "move 3"),
        ("a new step in a life", "a graceful stop, a paused seat", "one more state and one more checked transition", "", "move 6"),
        ("a new invariant across threads", "a philosopher who needs a knife too", "the SAME order over all three resources, everywhere", "", "move 4"),
        ("state that must outlive the process", "forks shared by two machines", "the lock becomes a lease in a store, and every write carries", "a fencing token, because a lease can expire while its holder still thinks it is eating", "moves 5 + 12")]):
    y = 22 + k*54
    m12 += _bx(30, y, 340, 42, t, sub) + _ar("M370 %s H420" % (y+21), True) + _bx(420, y, 660, 42, fix, sub2, acc=True) + _tx(1145, y+25, mv, "var(--muted)", 11)
m12 += _tx(615, 306, "for the first four the philosopher, the fork and the table do not change at all; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 320, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class &mdash; and one of them is a lock.",
 "Reading the paragraph again: a <b>philosopher</b> takes two <b>forks</b>, <b>eats</b>, and puts them back; a "
 "<b>table</b> seats five of them in a ring; a <b>rule</b> decides how a philosopher takes both. A philosopher has "
 "state that moves &mdash; what it is doing, how many meals it has had &mdash; and it has its own thread, so it is a "
 "class. A fork has the only state that matters: who is holding it. And that sentence, \"held by exactly one "
 "philosopher at a time\", is the definition of mutual exclusion, so a fork <i>is</i> a lock rather than a boolean "
 "you would then have to guard with a lock. The table holds the ring and the wiring. The acquisition rule has no "
 "state at all, so it is an interface. What is <i>not</i> a class is the deadlock: it is not a thing anybody owns, it "
 "is a shape the whole graph can fall into, which is exactly why nobody notices it until everything stops.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Take a fork and put it back\" touches one fork, so <code>fork.pickUp(id)</code> and <code>fork.putDown(id)</code> "
 "live on the fork &mdash; and putDown checks that you are the holder, so a clumsy caller cannot free somebody else's "
 "fork. \"Think, eat, count the meal\" touches only the philosopher's own fields, so it is <code>run()</code>. \"Seat "
 "five in a ring and start them in the same instant\" touches every fork and every seat, so it is the table. \"Who "
 "holds what and who is waiting\" touches nothing at all &mdash; it only reads &mdash; so it is a static method over "
 "an array. That leaves the interesting one: \"get both forks\". It touches two forks and belongs to neither of them, "
 "and it is the only line in the whole program that decides whether this deadlocks, so it becomes a thing of its own.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Four things will change. How a philosopher takes both forks &mdash; that is the entire literature of this problem: "
 "take the lower-numbered fork first, post a waiter who seats only four, try and give up, make the odd seats reach "
 "the other way, or drop the two-fork dance entirely and wait on a condition until both are free. What thinking and eating <i>mean</i>: a sleep in the demo, nothing at all in the race test, and "
 "something that throws in the failure test. Who wants to be told: a tracer, a fairness report, a dashboard. And "
 "where time comes from. Each is a small interface the table is <i>given</i> and never builds, which is where "
 "<b>Strategy</b> is born on this problem, and nowhere else: <code>ForkPolicy</code> with "
 "<code>acquireBoth</code> and <code>releaseBoth</code>. The payoff is the interview itself &mdash; when they say "
 "\"you may not renumber the forks\", the answer is a new class and one changed argument, with the philosopher and "
 "the table untouched.", 3),
("Move 4: the state many threads change at once is the fork &mdash; and the failure is not a lost update, it is a ring.",
 "On every other design the danger is two threads reading the same number and both writing it back. Here the fork is "
 "already a lock, so nothing can be lost; the danger is the opposite shape. Release five philosophers in the same "
 "instant with the obvious protocol and each one takes the fork on its left, which always succeeds, because there are "
 "five forks for five people. Then each reaches right, and every right-hand fork is in a neighbour's hand. Nobody is "
 "doing anything wrong, nobody can be blamed, and nobody ever moves again. Four conditions make that ring: forks are "
 "exclusive, a philosopher holds one while waiting for the next, nothing can take a fork back by force, and the "
 "waiting closes into a cycle. The first and the third are the problem statement &mdash; a fork really is exclusive, "
 "and you really cannot snatch one out of a hand &mdash; so there are exactly two answers, and every fix on this page "
 "is one of them. Delete the cycle: put a global order on the forks, or post a waiter so all five can never reach at "
 "once. Or delete hold-and-wait: never keep one fork while you wait for the other, which drop-and-retry does by "
 "handing the first one back and the wait/notify version on page 05 does by reserving both under a single lock. "
 "Saying which of the four your fix deletes is what makes an answer sound worked out rather than remembered.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "There is not a single map in this design, because nothing is looked up by a key. \"Which forks are mine?\" is "
 "arithmetic: fork <i>i</i> and fork <i>(i+1) mod n</i> out of an array. \"Who is holding fork 3?\" is a volatile int "
 "on the fork, written the instant it is acquired. \"What is p2 waiting for?\" is a volatile int on the philosopher, "
 "written just before it blocks. Those two fields are the entire input to the detector: n edges, so finding a ring is "
 "one pass over an array, and it happens on a watchdog thread rather than in anybody's way. Meals are a plain "
 "<code>long</code> written only by its own thread and read after <code>join()</code>, which is a happens-before edge "
 "and needs no lock &mdash; a shared counter would have added contention to the very thing we are measuring.", 5),
("Move 6: the life cycle is four states, and the order inside one round is what keeps a fork from being stranded.",
 "THINKING holds nothing. HUNGRY is reaching, and may be holding one fork for a moment. EATING means both forks are "
 "in hand. DONE is the end of the rounds. The order inside a round is the design: think, say HUNGRY while holding "
 "nothing, ask the policy for both forks &mdash; and the policy's contract is all-or-nothing, so it returns with two "
 "or with none &mdash; then and only then say EATING and eat, count the meal after it actually happened, and put both "
 "forks back inside a <code>finally</code>. That finally is load-bearing: a philosopher that is interrupted mid-reach "
 "hands back the fork it already took, and a philosopher whose meal throws still returns both. There is no state in "
 "which a fork is held by somebody who has stopped running, which is the concurrency equivalent of \"nothing is ever "
 "half-written\".", 6),
("Move 7: yes, a fork is held for the whole meal. That is the one design here where the critical section IS the work.",
 "The usual advice &mdash; hold the lock for microseconds, do the slow thing outside it &mdash; cannot be followed "
 "here: eating <i>is</i> holding both forks. So measure both halves. The locking itself is nothing: ten thousand "
 "meals with instant meals run in about fifteen milliseconds, one and a half microseconds of lock traffic per meal. A "
 "real meal of three milliseconds is two thousand times that. So the queue is never for the lock's internals, it is for the fork "
 "itself, and the only lever is the order in which forks are taken. The second number is the ceiling: five "
 "philosophers share five forks and each meal needs two, so at most two can eat at once &mdash; floor(n/2) &mdash; "
 "and a schedule that reaches it rotates cleanly, with every philosopher eating twice in fifteen milliseconds. When "
 "somebody proposes one lock for the whole table, this is the number that answers them: the peak falls from two to "
 "one and the same hundred and fifty meals take about 650 ms instead of about 380.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Ordering costs one integer comparison per meal and buys structural freedom from deadlock; measured, ten thousand "
 "meals in about fifteen milliseconds. The waiter costs a fair semaphore acquire as well, roughly three times the lock "
 "traffic, and buys the same guarantee <i>without</i> needing to own the numbering of the forks &mdash; which is the "
 "rung you climb to when the interviewer forbids a global order. Drop-and-retry costs far more: the same ten thousand "
 "meals took around four hundred milliseconds and threw away about a hundred and eighty half-acquisitions, because every failed attempt "
 "throws away work, and without a randomised backoff it does not deadlock but livelocks, which is worse, because it "
 "looks busy. Beyond the ladder is Chandy-Misra, where each fork is clean or dirty and neighbours pass them on "
 "request: no global order, no central waiter, and starvation-freedom as well. Name it; do not build it in an hour.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "All five reaching at once (show it on purpose: a latch makes every philosopher hold a left fork, and a grace "
 "timeout on the second fork means the demonstration ends in 400 ms instead of hanging the JVM). A philosopher "
 "waiting for ever (ordering; ten thousand meals finish). A ban on renumbering (the waiter; five thousand meals and "
 "every seat handed back). A meal that throws (the finally; every fork still free at the end, and the neighbours "
 "never blocked). A wedged run that must be broken (interruptible locks; an interrupt unwinds five-second meals "
 "immediately). The plausible bad fix (one lock for the table; the peak eaters number falls to one and the clock "
 "says so). A detector that cries wolf (forty samples of a healthy run, and no ring ever confirmed: our detector "
 "reads two fields that move while it is reading them, so a single sample really can compose a ring on a healthy "
 "table, and the rule is the same ring twice before you believe it). And, if you write the "
 "wait/notify version instead, the failure that replaces the ring: a wakeup delivered to the wrong thread, which the "
 "test reproduces on purpose by putting two waiters on one condition and calling signal() once. Each of those is a "
 "few lines in FailureTests.java, which runs thirty-seven checks in about three seconds.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Strategy is move 3 and it is the spine of this design: the acquisition rule behind <code>ForkPolicy</code>, so "
 "ordering, the waiter, backoff, asymmetry and the wait/notify version are five files and no edits. Observer is move 3 as well &mdash; the "
 "table announces a state change after the forks are back, inside a try/catch, so a metrics collector or a broken "
 "listener can never stretch a meal. State is move 6, four values in one field with one writer, which is what makes "
 "the detector's read cheap. Decorator turns up in the shutdown twist: <code>stoppable(work)</code> wraps any Work "
 "and adds the flag check, so a graceful stop needs no change to the philosopher's loop. And the Fork is the textbook "
 "<b>monitor object</b> &mdash; the data and the lock that guards it in one class &mdash; which is worth naming "
 "because it is the reason a boolean-plus-a-lock design is wrong rather than merely clumsy. Singleton earned nothing: "
 "the table is handed to its caller. Factory earns its name the day policies arrive from configuration. Builder never "
 "does: a table is three required fields.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "S: the fork does mutual exclusion, the philosopher runs the loop, the table does the wiring, a policy holds one "
 "rule &mdash; and nobody does two of those, which is why the deadlock fix is never tangled with the meal. O: "
 "asymmetric seating arrived as a new file in Extensions.java and nothing in Main.java moved. L: the philosopher "
 "calls <code>policy.acquireBoth(this)</code> and never asks which policy it got, which is why the same failure test "
 "runs against every one of them. I: <code>ForkPolicy</code> is two halves of a single rule, and Work, DiningObserver and "
 "Clock have one method each, so a fake is a lambda. D: the table is constructed with its policy and configured with "
 "its work, so a test can hand in a meal that throws, a clock that lies, and a policy designed to deadlock.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (asymmetric seats, Chandy-Misra, a priority for the hungriest) is a new class behind "
 "<code>ForkPolicy</code> and one changed argument. Somebody new who wants to know (fairness numbers, a dashboard, "
 "tracing) is one more observer, called after the forks are back. A new step in a life (a graceful stop, a seat that "
 "can be paused) is one more state and one more checked transition. A new invariant across threads (a philosopher "
 "who needs a knife as well as two forks) is the same move 4 answer generalised: sort <i>all</i> the resources by id "
 "and take them in that order, everywhere, which is also the fix for the two-account bank transfer that deadlocks in "
 "production. And state that must outlive the process (two machines sharing forks) turns the lock into a lease in a "
 "shared store, with the honest caveat that a lease can expire while its holder still believes it is eating, so "
 "every write it makes has to carry a fencing token. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("The same moves as every other design on this site, with one difference: on a parking lot the moves "
 "protect a number from two writers, and here they protect the whole program from a shape. Move 4 is where this problem "
 "lives &mdash; draw the ring, name the four conditions, delete one &mdash; and moves 6 and 7 are where the answer is "
 "made honest: what is held at every instant, and how long it is held for.")

# ============================================================ page 03: the class diagram
uml_reset()
EXT = ' <tspan font-size="10" fill="var(--acc2)">ext</tspan>'   # lives in Extensions.java, not in the hour
# left column: what is handed in, and what reads the table
put("work", 10, 20, 235, "Work", [], ["perform(philosopherId)", "sleepMs(ms) / none()"], "interface")
put("obs", 10, 130, 235, "DiningObserver", [], ["onState(id, state, atMs)"], "interface")
put("metrics", 10, 215, 235, "FairnessMetrics" + EXT, ["hungrySince, meals: long[]"], ["onState(...): the waits"])
put("clock", 10, 320, 235, "Clock", [], ["nowMs(): long"], "interface")
put("state", 10, 405, 235, "PhilosopherState", ["THINKING, HUNGRY,", "EATING, DONE"], [], "enum")
put("monitor", 10, 520, 235, "TableMonitor" + EXT, ["table: DiningTable"], ["line(): the read-only view"])
# centre column: the table, the philosopher, the fork
put("table", 300, 20, 340, "DiningTable",
    ["n: int", "forks: Fork[]", "seats: Philosopher[]", "threads: Thread[]", "policy: ForkPolicy", "gate: CountDownLatch",
     "observers, clock, think, eat", "eating / peakEating: AtomicInteger"],
    ["configure(think, eat)", "start() / awaitFinish(ms)", "interruptAll()", "enterMeal() / exitMeal()",
     "publish(id, state)", "findCycle(): Cycle", "snapshot(): Snapshot"])
put("phil", 300, 330, 340, "Philosopher &laquo;Runnable&raquo;",
    ["id: int,  left / right: Fork", "policy: ForkPolicy", "state: volatile PhilosopherState", "waitingFor: volatile int",
     "meals / errors / abandoned: long"],
    ["run(): think, both, eat, back", "markWaiting(forkId)", "left() / right() / id()"])
put("fork", 300, 580, 340, "Fork",
    ["id: int", "lock: ReentrantLock", "owner: volatile int", "hands: AtomicInteger"],
    ["pickUp(by) / tryPickUp(by, ms)", "putDown(by)  -- only the holder", "owner() / isFree() / violated()"])
# third column: the values and the detector
put("snap", 690, 20, 250, "Snapshot",
    ["meals: long[]", "states: PhilosopherState[]", "totalMeals, peakEating", "allForksFree: boolean"], [], "record")
put("cycle", 690, 140, 250, "Cycle", ["philosophers: List", "forks: List"], ["size(): int"], "record")
put("graph", 690, 255, 250, "WaitGraph", [], ["find(forks, seats): Cycle"], "")
put("dog", 690, 335, 250, "DeadlockWatchdog" + EXT, ["jvm: ThreadMXBean"], ["run(): find, name, interrupt"])
put("stop", 690, 440, 250, "GracefulShutdown" + EXT, ["running: volatile boolean"], ["stoppable(work): Work", "stop(graceMs)"])
put("lease", 690, 560, 250, "LeasedFork" + EXT, ["key, store, leaseMs"], ["pickUp(by, waitMs)", "putDown(by)"])
# fourth column: the rules that are handed in
put("wd", 690, 665, 250, "WouldDeadlock", ["philosopherId, forkId: int"], ["thrown by NaivePolicy"], "exception")
put("policy", 975, 20, 245, "ForkPolicy", [], ["acquireBoth(p)", "releaseBoth(p)"], "interface")
put("naive", 975, 130, 245, "NaivePolicy", ["graceMs, wedge latch"], ["left, then right, then give up"])
put("ordered", 975, 225, 245, "OrderedPolicy", [], ["lower fork id first"])
put("arb", 975, 305, 245, "ArbitratorPolicy", ["seats: Semaphore(n-1)"], ["a seat, then both forks"])
put("backoff", 975, 400, 245, "TimeoutBackoffPolicy", ["tryMs, backoff"], ["drop and retry, randomly"])
put("asym", 975, 495, 245, "AsymmetricPolicy" + EXT, [], ["odd seats reach right first"])
put("glob", 975, 575, 245, "GlobalLockPolicy", ["table: ReentrantLock"], ["one lock: no parallelism"])
put("mon", 975, 660, 245, "MonitorPolicy" + EXT, ["mutex + one Condition a seat", "eating / hungry: boolean[]"],
    ["both forks, or wait in a loop"])

def line(d, col="var(--muted)", dash=""):
    return '<path d="%s" fill="none" stroke="%s" stroke-width="1.2"%s/>' % (d, col, ' stroke-dasharray="5 3"' if dash else '')

EDGES = [
 # the seven policies implement the interface, on one bus down the left of the column
 line("M955 105 V705"),
 line("M955 165 H975"), line("M955 253 H975"), line("M955 340 H975"),
 line("M955 435 H975"), line("M955 520 H975"), line("M955 605 H975"), line("M955 705 H975"),
 ln((955, 105), B["policy"]["b"], "inherit"),
 # the table owns the forks and the seats; the philosopher points at its two forks
 ln(B["table"]["b"], B["phil"]["t"], "compose", "seats, each handed the policy"),
 ln((300, 175), (300, 665), "compose", "", [(282, 175), (282, 665)]),
 ln(B["phil"]["b"], B["fork"]["t"], "assoc", "left, right"),
 # the rules are handed in
 ln((640, 32), B["policy"]["t"], "inject", "", [(662, 8), (1097, 8)]),
 # what the table hands out, and who reads it
 ln((640, 120), (690, 75), "assoc", "", [(668, 120), (668, 75)]),
 ln(B["graph"]["l"], (640, 200), "assoc", "reads"),
 ln(B["graph"]["t"], B["cycle"]["b"], "assoc", ""),
 ln(B["dog"]["l"], (640, 230), "assoc", "", [(672, 395), (672, 230)]),
 ln(B["stop"]["l"], (640, 245), "assoc", "", [(660, 500), (660, 245)]),
 # the callers and the injected pieces on the left
 ln((300, 60), (245, 55), "inject", ""),
 ln((300, 90), (245, 160), "notify", "", [(268, 90), (268, 160)]),
 ln((300, 150), (245, 355), "inject", "", [(258, 150), (258, 355)]),
 ln(B["metrics"]["t"], B["obs"]["b"], "inherit"),
 ln(B["monitor"]["r"], (300, 250), "assoc", "", [(272, 592), (272, 250)]),
 ln((300, 420), (245, 440), "assoc", ""),
]
UMLSVG = uml_svg(1230, 800, EDGES, legend_y=772)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values; &laquo;record&raquo; = a value with no behaviour; &laquo;exception&raquo; = what a policy throws '
 'when it refuses to keep waiting). A small blue <b>ext</b> after a name means that class lives in Extensions.java: '
 'it is a follow-up\'s answer, not something you type in the hour. Everything without it is in Main.java. '
 'Middle: its fields, the state it holds. Bottom: '
 'its methods. <b>The arrows.</b> Hollow triangle = implements: seven policies, one interface, which is the whole design '
 'in one picture. Filled diamond = owns: the table creates the forks and the philosophers and their lifetime is its '
 'own. Plain arrow = references: a philosopher points at the two forks it shares with its neighbours, and those are '
 'the same two objects its neighbours point at. Dashed green = handed in at construction. Dotted blue = notifies. '
 '<b>Where state lives:</b> all of it is in the fork and the philosopher. A fork has the lock, the current owner and a '
 'count of hands on it; a philosopher has what it is doing, what it is reaching for, and how many meals it has had. '
 'The table owns no lock of its own &mdash; the forks are the locks &mdash; and the policy owns no state at all except '
 'the waiter\'s seat counter. Notice what is missing: there is no Deadlock class and no central book of who holds '
 'what, because the two volatile ints on the fork and the philosopher already are that book, and WaitGraph just reads '
 'them.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it, including a real deadlock broken by a watchdog) and FailureTests.java '
 '(thirty-seven checks in about three seconds; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java '
 'FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (is a fork a lock, and do you want the deadlock shown, '
 'are the first two); then type in the order of Main.java: the Clock and Work interfaces, the PhilosopherState enum, '
 'Fork with its lock and its guarded putDown, the ForkPolicy interface, the naive policy with its grace timeout, the '
 'ordered policy, the arbitrator, Philosopher with its try/finally, WaitGraph, then DiningTable with the start latch, '
 'and a main that wedges the naive run, names the ring and then runs ten thousand meals with ordering.</div></div>')

FU = [
("You may not renumber the forks. No global order is allowed. Now fix the deadlock.", "twist", 10,
 "A cycle needs all five philosophers reaching at the same time, so stop the fifth from sitting down: a waiter with "
 "four seats for five philosophers. A philosopher takes a seat before it touches a fork and gives the seat back with "
 "the forks, so at any instant at most four are reaching and at least one of them has both its forks free on one "
 "side. The semaphore is fair, so the queue for a seat is first-come-first-served. Philosopher and DiningTable do not "
 "change at all: this is a new ForkPolicy and one changed constructor argument, which is the whole point of move 3. "
 "It costs one extra counter on the hot path -- measured, ten thousand meals in about 40 ms against about 15 ms for ordering.",
 M("final class ArbitratorPolicy", "final class TimeoutBackoffPolicy")),
("Forget taking two forks one after the other. Do it with wait and notify.", "twist", 10,
 "One ReentrantLock over the whole table, two small arrays -- who is hungry, who is eating -- and one Condition per "
 "seat. A hungry philosopher marks itself hungry under that lock and tries to grant itself a meal: if neither "
 "neighbour is eating it sets eating[i] = true and signals its own condition, and if it cannot, it waits in a while "
 "loop until a neighbour finishes and grants it. The forks are only picked up after the grant, so nobody ever holds "
 "one fork while waiting for the other -- this deletes hold-and-wait, where ordering and the waiter both delete the "
 "cycle instead, and unlike drop-and-retry it throws no work away. Releasing runs in the order that matters: both forks "
 "down first, then the lock, then eating[i] = false, then a grant attempt for each neighbour, so a philosopher is "
 "only ever woken for forks that are already on the table. The interrupt path is the fiddly part and it has its own "
 "test, because there are two ways to be left holding a grant you can no longer use: signalled and interrupted in "
 "the same breath, or interrupted in "
 "the gap between the grant and the fork pick-up, where lockInterruptibly throws even though the fork is sitting "
 "free -- and both have to hand the grant on rather than drop it and strand two neighbours. Measured: 5,000 meals, no deadlock, peak two eating at "
 "once -- the same parallelism as ordering -- and both arrays empty at the end, with the honest caveat that this is "
 "deadlock-free but not starvation-free: two neighbours taking turns can keep a philosopher hungry for ever.",
 X("the wait protocol", "signal vs signalAll")),
("Why notifyAll and not notify? And why is the wait always in a while loop?", "design", 5,
 "Because a Condition has one queue, and signal() moves whichever thread happens to be at the head of it. If several "
 "threads wait on the same condition for different things, that thread may be waiting for something else entirely: "
 "it re-tests, finds its own test still false, goes back to sleep -- and takes the only wakeup with it. The thread "
 "the change was actually for is never told, and the program stalls with nobody holding anything. The test builds "
 "exactly that, deterministically: two waiters on one condition, the first parked before the second is even started "
 "so the queue order is a fact and not luck, then one signal() -- and the thread the change was for is still asleep "
 "300 ms later, while signalAll() gets it through. The while loop is the other half of the rule: a wakeup only ever "
 "means \"go and look again\", both because await() can return without anybody signalling and because a third thread "
 "can take what you were woken for before you get the lock back. MonitorPolicy above escapes the choice altogether "
 "by giving every philosopher its own condition, so signal() wakes exactly one thread, the right one, and there is "
 "no thundering herd to pay for.",
 X("signal vs signalAll", "the same trick anywhere two locks")),
("What does java.util.concurrent already give you here, and why ReentrantLock rather than synchronized?", "design", 5,
 "Nearly every piece except the one that matters. ReentrantLock gives three things synchronized cannot: "
 "lockInterruptibly, which is the only reason a wedged run can be rescued at all; tryLock with a timeout, which is "
 "the whole of the backoff policy and the grace timeout in the naive demonstration; and newCondition, so one lock "
 "can have a separate wait queue per philosopher instead of one queue for everybody. Semaphore(n - 1, true) is the "
 "waiter, fair queueing included. CountDownLatch is the start gate that makes five threads reach in the same "
 "instant, and ThreadMXBean.findDeadlockedThreads() is the production detector. What the JDK does not give you is "
 "the answer: there is no dining-philosophers class, because the acquisition rule IS the design and it is the one "
 "thing you have to write. synchronized is still the right default when you need none of the three -- it is shorter, "
 "it cannot be left unlocked, and the JVM optimises it -- but it blocks uninterruptibly, so a table built on it can "
 "be stopped only by killing the process.",
 "// 1. lockInterruptibly: the rescue path. synchronized has no equivalent, at all.\n"
 "void pickUp(int by) throws InterruptedException { lock.lockInterruptibly(); claim(by); }\n"
 "void interruptAll() { for (Thread t : threads) if (t != null) t.interrupt(); }\n\n"
 "// 2. tryLock with a deadline: the grace timeout that turns a hang into evidence, and the backoff policy\n"
 "boolean tryPickUp(int by, long ms) throws InterruptedException {\n"
 "    if (!lock.tryLock(ms, TimeUnit.MILLISECONDS)) return false;\n"
 "    claim(by);\n"
 "    return true;\n"
 "}\n\n"
 "// 3. newCondition: one wait queue PER philosopher, so signal() wakes exactly the right thread\n"
 "for (int i = 0; i < n; i++) mayEat[i] = mutex.newCondition();\n\n"
 "// the waiter is a fair semaphore, and nothing else\n"
 "this.seats = new Semaphore(n - 1, true);\n\n"
 "// the race itself is a latch: five threads, one instant\n"
 "private final CountDownLatch gate = new CountDownLatch(1);\n"
 "void awaitStart() throws InterruptedException { gate.await(); }\n\n"
 "// and the detector the JVM hands you for free, which is what jstack prints\n"
 "long[] ids = ManagementFactory.getThreadMXBean().findDeadlockedThreads();\n"),
("Don't describe the deadlock. Reproduce it, on purpose, in a test that does not hang.", "non-functional", 10,
 "Two pieces. A wedge latch inside the naive policy: every philosopher takes its left fork, counts down, and waits "
 "until all five have done so, which turns a rare interleaving into a certainty. And a grace timeout on the second "
 "fork: instead of blocking for ever the philosopher waits 400 ms, hands its first fork back and reports the "
 "circular wait. Meanwhile a detector thread samples the two volatile ints -- who owns each fork, what each "
 "philosopher is reaching for -- and walks the five edges looking for a ring. The test asserts the ring has five "
 "philosophers, that nobody ate during the whole grace window, and that every fork was back on the table afterwards. "
 "Every philosopher thread is a daemon, so even a broken version of this cannot wedge the JVM.",
 T("        // 1. the naive protocol", "        // 2. resource ordering")),
("It is three in the morning and the service has stopped. How would you know it is a deadlock?", "design", 5,
 "Two detectors, and neither of them is a fix. The JVM already knows who owns which ReentrantLock, so "
 "ThreadMXBean.findDeadlockedThreads() reports a genuine cycle rather than guessing from a timeout, and getThreadInfo "
 "names the threads and the lock each is blocked on -- that is exactly what jstack prints in a thread dump. The "
 "watchdog here polls it, prints the ring, and then interrupts everybody, which only works because every fork is "
 "taken with lockInterruptibly: a wedged philosopher throws, drops the fork it holds and unwinds. The second detector "
 "is the application's own: the wait-for graph built from two volatile ints, which also works for locks the JVM "
 "cannot see, such as a lease in Redis -- but it samples a moving picture, so it must see the SAME ring twice "
 "before it reports one, or it will cry wolf on a healthy table about once in forty runs. A test checks that "
 "direction too: forty samples of a healthy run, and nothing ever confirmed, because a detector that cries wolf "
 "gets switched off.",
 X("the real deadlock", "fairness, measured")),
("Does your fix cost you concurrency? Prove it, don't assert it.", "non-functional", 5,
 "It does not, and the number is the peak count of philosophers eating at the same instant. The table increments a "
 "counter when a meal starts and decrements it when the meal ends, keeping the maximum, so any run reports what it "
 "actually achieved. With resource ordering and a three-millisecond meal the peak is two, which is the ceiling of the "
 "problem itself: five philosophers sharing five forks, two forks per meal, so floor(5/2) = 2. The same run with one "
 "big lock around the whole meal -- the fix somebody always proposes -- reports a peak of one and takes about 650 ms "
 "instead of about 380 ms for the same hundred and fifty meals. That comparison is the answer to \"why not just "
 "synchronize the table\", and it takes ten lines of test.",
 T("        // 5. the fix must keep", "        // 6. a meal that throws")),
("Prove that no philosopher starves.", "non-functional", 10,
 "Be careful here, because the honest answer is that deadlock-freedom and starvation-freedom are different "
 "properties and ordering only gives you the first. What you can do is make starvation unlikely and then measure it. "
 "Fair locks (new ReentrantLock(true)) hand a fork to the longest waiter instead of whoever happens to be running, "
 "and the arbitrator's semaphore is fair too, so the queue for a seat is in order. The measurement is an observer: "
 "it timestamps HUNGRY and EATING for each philosopher and reports meals, worst wait and total wait per seat, plus "
 "the min/max ratio of meals. The failure test runs the bounded version of the claim -- five philosophers, four "
 "hundred meals each, fair forks, all of them finished -- and the extension prints the spread over five hundred "
 "meals each with a one-millisecond meal.",
 X("fairness, measured", "the asymmetric fix")),
("A philosopher throws up in the middle of a meal. What is the state of the table?", "functional", 5,
 "Exactly what it was, minus one meal. The meal happens inside a try whose finally returns both forks through the "
 "policy, so an exception, an interrupt or a timeout all leave the forks on the table and the neighbours free to "
 "eat. The counter is incremented after the meal returns normally, never before, so a failed meal is not counted as "
 "eaten -- it is counted as an error on that philosopher. The test makes p2 throw on all two hundred of its rounds "
 "and then checks three things: every fork is free at the end, p2 has two hundred errors and zero meals, and its two "
 "neighbours still ate two hundred times each, which is the part that proves one broken philosopher cannot poison "
 "the table.",
 M("    @Override public void run() {", "    /** Change state and tell")),
("Stop the dinner cleanly. Interrupting everybody is not a shutdown protocol.", "twist", 5,
 "The philosopher's loop checks a flag once per round, and because thinking is already handed in, the flag lives in "
 "the work rather than in the actor: stoppable(work) wraps any Work and throws when the flag is cleared, which ends "
 "that philosopher's loop between meals instead of in the middle of one. Stop then waits for everybody with a "
 "deadline and only escalates to interruptAll if somebody has not come back, which is the difference between a "
 "protocol and a hammer. Nothing in Philosopher or DiningTable changes; the wrapper is a Decorator, and it is the "
 "same trick as the timeout policy -- add behaviour to a rule that was already an interface.",
 X("a graceful stop", "forks in another process")),
("Give up instead of blocking: try for the forks and come back later.", "twist", 5,
 "tryLock with a timeout on each fork, and if the second one does not come, put the first back and retry after a "
 "pause. It cannot deadlock, because nobody ever holds a fork while waiting for ever -- but it can livelock: five "
 "philosophers dropping and grabbing in perfect step, busy and making no progress, which is why the pause is random "
 "rather than fixed. The price is real and worth quoting: the same ten thousand meals took around four hundred "
 "milliseconds and threw away about a hundred and eighty half-acquisitions, against about fifteen milliseconds for "
 "ordering. Use it when you "
 "cannot order the resources and cannot afford a central waiter.",
 M("final class TimeoutBackoffPolicy", "final class GlobalLockPolicy")),
("This is a toy. Where does this actually bite in production code?", "twist", 8,
 "Anywhere a thread takes two locks. The classic is a transfer between two accounts: lock the payer, lock the payee, "
 "move the money -- and two opposite transfers at the same instant are the philosophers' ring with n = 2. The fix is "
 "the same move: take the locks in a global order, here the account id, with a tie-break lock for the rare case of "
 "equal ids (which happens for real when the order is System.identityHashCode). The demo runs a hundred thousand "
 "opposing transfers and never wedges. The same helper generalises to k resources: sort them by id, take them in "
 "that order, release in reverse -- that is the answer when a philosopher needs a fork, a knife and a plate.",
 X("the same trick anywhere two locks", "a graceful stop")),
("Now the forks live in Redis and the philosophers are on different machines.", "twist", 5,
 "The protocol survives the move and the guarantee does not. A fork becomes a key with a lease: SET key owner NX PX "
 "leaseMs, released with a compare-and-delete so you can only free your own. Philosopher and the policies take an "
 "interface with pickUp and putDown, so neither changes. What breaks is the assumption underneath everything on this "
 "page: a ReentrantLock is held until you release it, but a lease expires on its own -- the demo shows p2 taking a "
 "fork that p1 still believes it is holding. That is why a distributed lock is only safe when every write it guards "
 "carries a fencing token that the storage rejects if a newer holder has appeared.",
 X("forks in another process", "the read-only view")),
("Show me who is eating and how many meals each has had, without slowing anybody down.", "functional", 3,
 "Every number is already a field: the philosopher's state and meal count are volatile, written by its own thread, "
 "and the fork's owner is volatile too. So the monitor is a read of n fields, takes no lock, blocks nobody and "
 "cannot take a fork; a snapshot is an O(n) copy. That is the whole reason the state lives in a field rather than in "
 "a map the table would have to guard: a supervisor asking \"who is hungry?\" a thousand times a second must not be "
 "able to slow a meal down by even a microsecond.",
 X("the read-only view", "ExtDemo")),
("Where does time come from, and how do you test a five-second meal inside a three-second test suite?", "design", 3,
 "Nothing in the system reads the wall clock by itself. Observers are stamped with an injected Clock, so a test can "
 "hand in a counter and control every timestamp -- that is how the leased-fork demo expires a lease without sleeping "
 "for a hundred milliseconds. Meals and thinking are injected too, as Work, so a test picks instant meals when it "
 "wants raw lock traffic, a three-millisecond meal when it wants to measure parallelism, and a five-second meal when "
 "it wants somebody stuck. The five-second test finishes in milliseconds because it does not wait for the meal: it "
 "interrupts the table and asserts that everybody unwound and every fork went back.",
 "/** Where time comes from. Injected, so a test can stamp events with any instant it likes. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the table: handed in, defaulted, never read from the wall clock inside a method\n"
 "private Clock clock = System::currentTimeMillis;\n"
 "DiningTable setClock(Clock c) { clock = c; return this; }\n\n"
 "// in a test: pick the instant, then move it -- no sleeping\n"
 "long[] now = { 1_700_000_000_000L };\n"
 "FakeRedis redis = new FakeRedis(() -> now[0]);\n"
 "LeasedFork remote = new LeasedFork(2, redis, 100);\n"
 "remote.pickUp(1, 50);                                  // p1 holds the lease\n"
 "now[0] += 101;                                         // the lease expires, without waiting for it\n"
 "remote.pickUp(2, 30);                                  // p2 takes a fork p1 still thinks it holds\n\n"
 "// and a five-second meal, tested in milliseconds\n"
 "DiningTable slow = new DiningTable(5, new OrderedPolicy(), 50).configure(Work.none(), Work.sleepMs(5_000));\n"
 "slow.start(); Thread.sleep(50); slow.interruptAll();\n"
 "check(slow.awaitFinish(3_000) && slow.allForksFree(), \"interrupt unwound it and every fork went back\");\n"),
("Which pattern is where, and what did NOT earn a place?", "design", 5,
 "Moves 10 and 11 have the full tables; what matters in the room is that you can say none of it was chosen up front. "
 "Strategy came out of move 3 and is the spine: seven deadlock answers, seven files, no edits to Philosopher or "
 "DiningTable. Fork is the textbook monitor object -- the data and the lock that guards it in one class -- and that "
 "is the reason \"a boolean plus a lock\" is the wrong shape rather than merely a clumsy one. The interesting half is "
 "the refusals: Singleton earned nothing, because the table is handed to its caller and a test builds four of them in "
 "four lines; Factory earns its name the day policies arrive from configuration and not before; and Builder never "
 "does, because a table is three required fields. Saying \"not yet\" and \"never\" about a pattern is what separates "
 "somebody who has used them from somebody who has read the book.",
 "// Strategy: the one rule that decides whether this program deadlocks, behind an interface\n"
 "interface ForkPolicy { void acquireBoth(Philosopher p) throws InterruptedException; void releaseBoth(Philosopher p); }\n"
 "new DiningTable(5, new ArbitratorPolicy(5), 1_000).configure(Work.none(), Work.sleepMs(3));\n\n"
 "// Monitor object: the fork IS its lock, so nothing can touch it without holding it\n"
 "final class Fork { private final ReentrantLock lock; private volatile int owner = -1; }\n\n"
 "// Observer: announced after the forks are back, and a broken listener cannot break dinner\n"
 "for (DiningObserver o : observers) { try { o.onState(id, s, at); } catch (RuntimeException ignored) { } }\n\n"
 "// Decorator: add the stop check to any Work without touching the philosopher's loop\n"
 "Work stoppable(Work base) { return id -> { if (!running) throw new InterruptedException(\"dinner is over\"); base.perform(id); }; }\n\n"
 "// Singleton: nothing. Factory: not yet -- one line at the call site is the whole construction.\n"
 "// Builder: never -- a table is three required fields.\n"
 "ForkPolicy p = new OrderedPolicy();\n"
 "DiningTable t = new DiningTable(5, p, 2_000);\n"),
]

build(dict(
    slug="mt-dining", title="Dining Philosophers",
    subtitle="LLD &middot; multithreading &middot; Java &middot; OpenJDK 21: demo, a safe deadlock, 37 failure checks",
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
