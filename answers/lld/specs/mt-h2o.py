# H2O Barrier LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"mt-h2o/Main.java").read_text()
ext   = (H/"mt-h2o/Extensions.java").read_text()
tests = (H/"mt-h2o/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+220])
    j = next(m for m in marks if m > i and b in ext[m:m+220])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def M(a, b, s=None):
    """sect() for a slice that starts mid-class: put the member's own indentation back on line 1"""
    return "    " + sect(s if s is not None else src, a, b).lstrip()

RED = "#ff6b6b"

# ============================================================ page 01: the problem
# what the code must do: one hydrogen and one oxygen, each with its wait
pf = _D
rows = [("hydrogen()", 20, 104, [("a hydrogen thread arrives", "any thread, at any time"),
                                 ("take the lock", "interruptibly"),
                                 ("a free hydrogen seat?", "two seats, never three"),
                                 ("sit down: is it full now?", "the last atom wakes the others"),
                                 ("emit OUTSIDE the lock", "then count the emit")],
         "no seat, or not full yet: park &mdash; the lock is released"),
        ("oxygen()", 185, 269, [("an oxygen thread arrives", "any thread, at any time"),
                                ("take the lock", "interruptibly"),
                                ("is the oxygen seat free?", "one seat, never two"),
                                ("sit down: is it full now?", "the last atom wakes the others"),
                                ("emit OUTSIDE the lock", "then count the emit")],
         "no seat, or not full yet: park &mdash; the lock is released")]
for lab, y, wy, boxes, wait in rows:
    pf += _tx(88, y + 31, lab, "var(--acc)", 12.5)
    for k, b in enumerate(boxes):
        x = 150 + k*212
        pf += _bx(x, y, 190, 54, b[0], b[1], acc=(k == 2))
        if k < 4: pf += _ar("M%s %s H%s" % (x+190, y+27, x+212), True)
    pf += _ar("M660 %s V%s" % (y+54, wy), dash=True) + _bx(500, wy, 430, 34, wait, "", dash=True)
    pf += _ar("M810 %s V%s" % (wy, y+58), True)
    pf += _tx(652, wy-11, "not yet", "var(--muted)", 10, "end")
    pf += _tx(820, wy-11, "woken &rarr; look again", "var(--acc)", 10, "start")
pf += _tx(1010, 160, 'a wake means "look again",', "var(--muted)", 11)
pf += _tx(1010, 178, 'never "the molecule is yours"', "var(--muted)", 11)
pf += _tx(88, 335, "read", "var(--acc)", 12.5)
pf += _tx(150, 335, "at any moment, from any thread: how many molecules formed, how many seats taken right now, how many parks so far &mdash; each read under the lock", "var(--text)", 12, "start")
pf += _tx(615, 366, "every window of three released atoms is exactly two H and one O, in any order, forever &mdash; with twenty hydrogen threads and ten oxygen threads running flat out", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 380, pf)

# one run, replayed -- these are the numbers Main.java prints
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("t = 0 ms   thirty threads start", ["20 hydrogen threads, 10 oxygen", "one latch releases them together",
                                           "3,000 atoms waiting to be placed"], False),
      ("t = 0.01 ms   molecule one", ["H sits, H sits: both seats gone", "O sits and wakes the other two",
                                      "three emits, then seats reopen"], True),
      ("t = 0-26 ms   1,000 molecules", ["4,997 parks: five per molecule", "nothing ever spun on a CPU",
                                         "a third H could not sit down"], False),
      ("t = 26 ms   the count", ["3,000 atoms out, 0 malformed", "every window of three is H,H,O",
                                 "the listener heard 1,000"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li><code>hydrogen(release)</code> and <code>oxygen(release)</code> are called by any number of threads, in any order, repeatedly, on one instance.</li>
<li>No thread runs its release until a complete molecule &mdash; two hydrogen and one oxygen &mdash; has gathered; then all three go.</li>
<li>The same instance forms molecules forever: molecule 1,000 works exactly like molecule 1.</li>
<li>A surplus of one element simply waits for its partners; nothing is dropped and nothing is forced through.</li>
<li>A caller that is blocked can be cancelled, and cancelling it must not cost anybody else their molecule.</li>
<li>The stoichiometry is a parameter: 2:1 today, any recipe on request, with no change to the waiting.</li>
<li><code>moleculesFormed()</code> is a consistent snapshot, never a molecule that is still forming.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>No malformed molecule is possible under any interleaving: never H,H,H and never H,O,O.</li>
<li>Every window of three released atoms belongs to one molecule: molecule N finishes before N+1 begins.</li>
<li>No busy-waiting: a waiting atom parks and burns no CPU until somebody signals it.</li>
<li>O(1) synchronisation per atom &mdash; one seat check, one wait, one signal &mdash; and memory O(number of elements).</li>
<li>The caller's release callback runs outside the lock, and a slow or throwing one cannot wedge the barrier.</li>
<li>The recipe, the clock and the listeners swap without touching the lock or the wait loops.</li>
<li>One JVM, in memory, one process (say it; a follow-up crosses machines).</li></ul></div></div>
'''

PROMPT = ('"There are threads that represent hydrogen atoms and threads that represent oxygen atoms. Each one '
          'calls <code>hydrogen()</code> or <code>oxygen()</code> and hands you a release function. No thread may '
          'run its release until a full molecule &mdash; two hydrogen and one oxygen &mdash; has gathered, and '
          'then all three go together. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Two kinds of thread walk up to the same object, and '
 'the only rule is that nobody leaves alone: a group of exactly two hydrogen and one oxygen leaves together, and '
 'the next group cannot start until this one has gone. So the thing you are writing is not a water molecule; it '
 'is a turnstile that holds atoms back until a complete set has gathered, then lets exactly that set through. '
 'Atoms arrive in any order and any number &mdash; five hydrogen and no oxygen is a perfectly normal Tuesday &mdash; '
 'and the surplus simply waits. Nobody may sit in a loop asking "is it my turn yet", because that burns a whole CPU '
 'to wait, so a thread that cannot bond goes to sleep and somebody has to wake it at the right moment. The one '
 'thing that must always be true: read the released atoms in order and every window of three is exactly two H and '
 'one O &mdash; never H,H,H, never H,O,O, and never three atoms borrowed from two different molecules.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: a class that compiles and a '
 '<code>main</code> that starts a crowd of threads and proves the grouping. The interviewer is watching for, in '
 'this order: the questions you ask before typing (is it always 2:1, and are the callbacks allowed to block, are '
 'the first two); which types exist and who owns which state; one atom\'s path end to end, including the sleeping; '
 'the race you are actually defending against, said out loud &mdash; a barrier of three trips on three hydrogens; '
 'whether the waits are <code>while</code> loops and not <code>if</code>s; what is inside the lock and for how '
 'long; what happens to a blocked thread that is interrupted. Then the twists: any molecule, not just water; '
 'timeouts; shutdown; do it with semaphores; do it without <code>java.util.concurrent</code>; make it fair.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Always two hydrogen and one oxygen, or will the recipe change?</td><td>2:1 now, any recipe later</td><td>A one-method <code>Recipe</code> handed in, not an <code>if</code> (moves 3, 5)</td></tr>'
 '<tr><td>One molecule and stop, or the same instance forever?</td><td>Forever</td><td>Something that resets every generation: never a <code>CountDownLatch</code> (moves 6, 8)</td></tr>'
 '<tr><td>Do the release callbacks block, and must the three run in a fixed order?</td><td>They may be slow; any order inside the molecule</td><td>The release runs OUTSIDE the lock (moves 6, 7)</td></tr>'
 '<tr><td>Do callers guarantee a balanced supply of atoms?</td><td>Yes; a surplus just waits</td><td>No timeout, no rejection, and a documented assumption (move 12)</td></tr>'
 '<tr><td>Must a blocked caller be cancellable?</td><td>Yes, by interrupt</td><td><code>lockInterruptibly</code>, and giving the seat back on the way out (moves 6, 9)</td></tr>'
 '<tr><td>Fairness across long-waiting threads, or throughput?</td><td>Throughput; fairness is a flag</td><td>A non-fair lock by default, with the measured cost of the other choice (move 8)</td></tr>'
 '<tr><td>Does anything need to watch the barrier?</td><td>A count, maybe a dashboard</td><td>One observer interface, called after the unlock (move 3)</td></tr>'
 '<tr><td>One JVM, in memory?</td><td>Yes</td><td>No broker, no persistence yet; crossing machines is a follow-up (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One run, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> two hydrogen and one oxygen per molecule, but the ratio is a '
 'parameter; the same instance forms molecules forever; atoms arrive from any thread in any order and a surplus '
 'waits; the caller\'s release callback may be slow, so it runs outside the lock; a blocked caller is cancellable '
 'by interrupt and hands its seat back when it goes; throughput first, so the lock is not fair. Named as out of '
 'scope: timeouts, shutdown, fairness, other molecules, crossing machines &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes; and the four things a threading problem tempts you to make classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a HYDROGEN and an OXYGEN arrive at a BARRIER; a MOLECULE needs two H and one O; whoever cannot bond yet WAITS; when it is complete all three RELEASE", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 185, "H2OBarrier", "the lock, the counters", 1), (233, 165, "Element", "identity: an enum", 1),
                          (416, 175, "Recipe", "no state: an interface", 0), (609, 175, "Molecule", "not an object: a number", 0),
                          (802, 190, "Hydrogen / Oxygen", "threads, not classes", 0), (1010, 200, "the waiting rooms", "Conditions on the lock", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a thread, a rule, a counter, or a waiting room the lock already keeps", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("cap how many of one element may enter", "H2OBarrier  (owns the seat counts)", "while (seated[e] == want) await()"),
                                       ("hold everybody until the set is complete", "H2OBarrier  (owns the lock)", "full.await() / full.signalAll()"),
                                       ('say how many atoms a molecule takes', "Recipe  (owns nothing: pure)", "recipe.needed(e)"),
                                       ("let this atom out", "the caller  (owns the callback)", "release.run(), outside the lock"),
                                       ("close a molecule, open the next", "H2OBarrier  (owns the generation)", "closeMyEmit()")]):
    y = 24 + k*52
    m2 += _bx(30, y, 340, 42, verb, "the verb") + _ar("M370 %s H430" % (y+21), True)
    m2 += _bx(430, y, 380, 42, cls, "the class whose state it touches", acc=True) + _ar("M810 %s H870" % (y+21), True)
    m2 += _bx(870, y, 330, 42, meth, "the method")
m2 += _tx(615, 305, "only the barrier can see the seat counts AND the waiting rooms, so it is the orchestrator; a hydrogen atom is not a class, it is any thread that calls a method", "var(--muted)", 11)
m2 += _tx(615, 325, "and notice the verb that belongs to nobody here: deciding WHAT release means. The barrier owns WHEN an atom is let out; the caller hands in what that does", "var(--muted)", 11)
MV[2] = _mv(1230, 338, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 70, 230, 104, "H2OBarrier", "configure(clock), addObserver(o)", acc=True)
for k, (t, sub, impl, isub) in enumerate([("Recipe", "how many of each element", "Recipe.WATER / Recipe.PEROXIDE", "e -> e == HYDROGEN ? 2 : 1, a lambda"),
                                          ("Clock", "where a timestamp comes from", "System::currentTimeMillis, or a fake", "a test pins the instant it wants"),
                                          ("MoleculeObserver", "who wants to know", "MoleculeCounter, a dashboard, a log", "called after the unlock, in a try/catch"),
                                          ("MoleculeBarrier", "the whole build is a rule too", "H2OBarrier / SemaphoreBarrier / Phaser", "the tests run the same checks on both")]):
    y = 20 + k*60
    m3 += _ar("M260 122 H340 V%s H410" % (y+21), True, True) + _bx(410, y, 290, 42, t, sub, dash=True)
    m3 += _bx(770, y, 430, 42, impl, isub) + _ar("M770 %s H700" % (y+21))
m3 += _tx(615, 282, "dashed green = handed in. The barrier never builds a rule, so \"now make it CO2\" is a different lambda and nothing else moves", "var(--muted)", 11)
m3 += _tx(615, 302, "and one wrapper takes the whole interface instead: MeteredBarrier implements MoleculeBarrier and times any build, which never learns it is being measured", "var(--acc)", 11)
MV[3] = _mv(1230, 315, m3)

# move 4: threads and time -- the gap, and what a bare barrier of three actually ships
m4 = _D
for k, lab in enumerate(["H thread 1", "H thread 2", "H thread 3", "O thread"]):
    m4 += _tx(25, 52 + k*44, lab, "var(--acc)", 11.5, "start")
    m4 += '<rect x="130" y="%s" width="700" height="30" rx="4" fill="var(--bg2)" stroke="var(--line)"/>' % (32 + k*44)
m4 += _bx(140, 32, 150, 30, "arrives", "") + _bx(300, 76, 150, 30, "arrives", "") + _bx(460, 120, 150, 30, "arrives", "")
m4 += _bx(140, 164, 300, 30, "still walking over", "", dash=True)
m4 += '<path d="M636 22 V212" stroke="%s" stroke-width="1.3" stroke-dasharray="5 4"/>' % RED
m4 += _tx(636, 16, "a bare barrier of three trips here: it counted to three", RED, 11)
for k in range(3):
    m4 += _bx(650, 32 + k*44, 170, 30, "released: H", "", acc=True)
m4 += _tx(535, 184, "the oxygen is still not here", "var(--muted)", 10.5)
m4 += '<path d="M130 224 H830" stroke="var(--line)" stroke-width="1.5"/>'
for k, t in enumerate(["t1", "t2", "t3", "t4"]):
    m4 += '<path d="M%s 219 V229" stroke="var(--line)"/>' % (215 + k*160) + _tx(215 + k*160, 245, t, "var(--muted)", 11)
m4 += _tx(860, 228, "time &rarr;", "var(--muted)", 11)
m4 += _card(850, 22, 360, 172, "the fix: seats, not a headcount",
            ["two hydrogen seats and one oxygen seat", "a third hydrogen cannot even sit down",
             "so the set can only ever be H + H + O", "the seats, the counters and the waiting rooms",
             "are ONE object's state behind ONE lock:", "check and sit down are a single step"], acc=True)
m4 += _tx(615, 272, "H,H,H: three atoms released as a molecule that does not exist. The gap is between \"three have arrived\" and \"the right three have arrived\"", RED, 11)
m4 += _tx(615, 292, "Extensions.java has this bug as runnable code (NaiveBarrier): feed it three hydrogen threads and it really does print HHH", "var(--muted)", 11)
m4 += _tx(615, 320, "and the second thing one lock buys you, which interviewers ask about separately: not one field in H2OBarrier is volatile, and none needs to be", "var(--acc)", 11)
m4 += _tx(615, 338, "every read and every write of them happens with the lock held, and one thread's unlock happens-before the next thread's lock &mdash; so the next thread sees everything the last one wrote", "var(--muted)", 11)
m4 += _tx(615, 356, "that is also why moleculesFormed() and seatedCount() take the lock to return one int: a lock-free read here would be a read with no happens-before edge behind it", "var(--muted)", 11)
MV[4] = _mv(1230, 370, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("how many H seats are taken?", "int[] seated, indexed by Element.ordinal()", "O(1)"),
                                      ("how many does a molecule need?", "int[] needed, read once from the Recipe", "O(1)"),
                                      ("is the molecule complete?", "one int filled, compared with size", "O(1)"),
                                      ("who is waiting for a hydrogen seat?", "seatFree[H]: the lock's queue of parked threads", "O(1) park / wake"),
                                      ("who is waiting for it to fill?", "full: a second queue of parked threads", "O(1) park / wake"),
                                      ("which molecule am I in?", "a long generation, read under the lock", "O(1)")]):
    y = 20 + k*46
    m5 += _bx(30, y, 350, 38, q, "the question") + _ar("M380 %s H440" % (y+19), True)
    m5 += _bx(440, y, 540, 38, shape, "the shape", acc=True) + _ar("M980 %s H1030" % (y+19), True) + _bx(1030, y, 170, 38, cost, "")
m5 += _tx(615, 320, "nothing scans, nothing is allocated per atom, and there is no list of waiters of our own: each Condition already keeps its own queue of parked threads", "var(--muted)", 11)
m5 += _tx(615, 340, "an EnumMap holds the three Conditions and a plain int[] holds the counts, so every question above is an array index, not a lookup", "var(--muted)", 11)
MV[5] = _mv(1230, 352, m5)

# move 6: one atom's life on a time line, and the ORDER
m6 = _D
m6 += _tx(880, 16, 'not full yet &rarr; sleep again: this arrow is exactly why the check is a while, not an if', "var(--acc)", 11)
m6 += _ar("M1095 45 V28 H730 V45", True)
steps6 = [(150, 145, "hydrogen(emit)", "any thread"), (315, 135, "lock it", "interruptibly"),
          (470, 150, "take a seat", "H seats: 1 of 2"), (640, 175, "park on \"full\"", "the lock is RELEASED"),
          (835, 140, "woken", "the third atom came"), (995, 210, "check again", "under the lock: while, never if")]
for k, (x, w, t, sub) in enumerate(steps6):
    m6 += _bx(x, 45, w, 42, t, sub, acc=(k in (3, 5)))
    if k < 5: m6 += _ar("M%s 66 H%s" % (x+w, steps6[k+1][0]), True)
m6 += _tx(25, 68, "one atom", "var(--acc)", 11.5, "start") + _tx(25, 133, "the lock", "var(--acc)", 11.5, "start")
m6 += '<rect x="315" y="112" width="325" height="30" rx="4" fill="var(--bg3)" stroke="var(--acc)"/>' + _tx(477, 132, "held by this thread", "var(--text)", 10.5)
m6 += '<rect x="640" y="112" width="195" height="30" rx="4" fill="var(--bg3)" stroke="var(--line)" stroke-dasharray="5 3"/>' + _tx(737, 132, "held by NOBODY", "var(--muted)", 10.5)
m6 += '<rect x="835" y="112" width="365" height="30" rx="4" fill="var(--bg3)" stroke="var(--acc)"/>' + _tx(1017, 132, "held again: await() re-acquires before it returns", "var(--text)", 10.5)
steps6b = [(150, 265, "unlock, THEN run the release", "the caller's code, outside"), (450, 250, "count the emit, in a finally", "even if the release threw"),
           (730, 310, "the third emit reopens the seats", "signal 2 H and 1 O, not signalAll"), (1060, 140, "return", "molecule closed")]
for k, (x, w, t, sub) in enumerate(steps6b):
    m6 += _bx(x, 165, w, 42, t, sub, acc=(k == 2))
    if k < 3: m6 += _ar("M%s 186 H%s" % (x+w, steps6b[k+1][0]), True)
m6 += '<rect x="20" y="228" width="1190" height="220" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(615, 250, "the order inside one atom, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  lock.lockInterruptibly()          so an atom that ends up parked can still be cancelled",
                       "2  while (this element's seats are full) seatFree.await()          the cap that makes H,H,H impossible",
                       "3  seated[e]++, filled++, remember the generation          the check and the sit-down are one step",
                       "4  last seat taken? full.signalAll()   else   while (not complete) full.await()",
                       "5  unlock, and only then release.run()          the caller's callback may be slow or may throw: never hold the lock through it",
                       "6  count the emit in a finally; the third emit resets the seats and signals exactly two H and one O"]):
    m6 += _tx(35, 276 + k*22, l, "var(--text)", 11, "start")
m6 += _tx(35, 414, "anything that throws before step 3 leaves every counter exactly as it was; an atom cancelled at step 4 hands its seat back and signals a peer, so the seat is not lost;", "var(--muted)", 11, "start")
m6 += _tx(35, 432, "and because the seats reopen only after all THREE emits, molecule N is fully out of the door before any atom of N+1 can even sit down", "var(--muted)", 11, "start")
# the wait protocol itself: three rules used twice, and the two wakeup bugs they exist to kill
m6 += _tx(615, 482, "underneath it, one protocol used twice &mdash; and every wait you will ever write is these three rules", "var(--text)", 12)
for k, (rule, why) in enumerate([("1   test the condition with the lock HELD", "no reading state you will sleep on outside the lock"),
                                 ("2   sleep in a while loop, never an if", "a wake means &quot;look again&quot;, never &quot;it is yours&quot;"),
                                 ("3   signal only after the state changed", "still under the lock, so a wake cannot outrun it")]):
    m6 += _bx(20 + k*405, 496, 380, 46, rule, why, acc=(k == 1))
m6 += '<rect x="20" y="558" width="1190" height="116" rx="6" fill="var(--bg3)" stroke="%s"/>' % RED
m6 += _tx(615, 580, "the two bugs those rules exist to kill", RED, 12)
for k, l in enumerate(["LOST WAKEUP: the signal fires in the gap between &quot;I looked&quot; and &quot;I slept&quot;, so the sleeper never hears it. There is no such gap here:",
                       "await() releases the lock atomically as it parks, so nobody can change a counter between the test and the sleep. Rule 1 is the whole defence.",
                       "SPURIOUS WAKEUP: the JVM may wake a parked thread for no reason at all. Rule 2 is the whole defence &mdash; re-test, and go back to sleep.",
                       "The one wakeup this design could still lose is one spent on an atom that is then cancelled, which is why it passes it on before it throws."]):
    m6 += _tx(35, 602 + k*20, l, "var(--text)" if k != 1 else "var(--muted)", 11, "start")
MV[6] = _mv(1230, 686, m6)

# move 7: what is inside the lock, and six threads across two molecules
m7 = _D + _card(30, 20, 560, 152, "inside the lock: about four nanoseconds",
                ["one array read and two int updates", "one comparison against the molecule size",
                 "one signal onto a Condition's queue", "measured: 4 ns for the whole locked part",
                 "nothing in here can block. Ever."], acc=True)
m7 += _ar("M590 96 H650", True) + _tx(620, 86, "unlock", "var(--acc)", 10.5)
m7 += _card(650, 20, 550, 152, "outside the lock: microseconds",
            ["the caller's release callback: theirs, not ours", "a park and an unpark: about 2 microseconds",
             "a molecule needs four of them: about 9 us", "the listeners: after the unlock, in a try/catch"])
m7 += _tx(615, 196, "six threads, two molecules: exactly three atoms fill at each dashed line, and never a fourth", "var(--text)", 12)
lanes = [("H-1", 200, 420), ("H-2", 250, 420), ("O-1", 390, 420), ("H-3", 450, 770), ("H-4", 480, 770), ("O-2", 740, 770)]
for k, (lab, seat, rel) in enumerate(lanes):
    y = 212 + k*22
    m7 += _tx(25, y + 12, lab, "var(--muted)", 10.5, "start")
    m7 += '<rect x="150" y="%s" width="1050" height="16" rx="3" fill="var(--bg3)" stroke="var(--line)"/>' % y
    m7 += '<rect x="%s" y="%s" width="16" height="16" rx="3" fill="var(--bg)" stroke="var(--acc)"/>' % (seat, y)
    m7 += '<rect x="%s" y="%s" width="16" height="16" rx="3" fill="#12302a" stroke="var(--acc)" stroke-width="1.6"/>' % (rel, y)
    m7 += '<path d="M%s %s H%s" stroke="var(--muted)" stroke-width="1" stroke-dasharray="2 3"/>' % (seat+16, y+8, rel)
for x, lab in [(438, "molecule 1 leaves"), (788, "molecule 2 leaves")]:
    m7 += '<path d="M%s 206 V352" stroke="var(--acc)" stroke-width="1.2" stroke-dasharray="5 4"/>' % x
    m7 += _tx(x + 8, 366, lab, "var(--acc)", 10.5, "start")
m7 += _tx(1090, 366, "outlined = sat down    filled = released", "var(--muted)", 10.5)
m7 += _tx(615, 392, "H-3 and H-4 arrived during molecule 1 and could not sit down: both hydrogen seats were taken, which is the cap doing its job", "var(--muted)", 11)
m7 += _tx(615, 412, "measured: 1,000 molecules through twenty hydrogen and ten oxygen threads takes 26 milliseconds, and the threads parked 4,997 times &mdash; about five parks per molecule", "var(--muted)", 11)
MV[7] = _mv(1230, 425, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + _tx(300, 34, "5,000 molecules, twenty H threads and ten O threads, measured on this machine", "var(--text)", 12)
cols8 = [("the build", 12), ("us / molecule", 245), ("why", 355)]
rows8 = [[("one lock + three waiting rooms", "var(--text)"), ("12.2", None), ("the reference on page 04", None)],
         [("semaphores + CyclicBarrier", "var(--text)"), ("6.6", None), ("the library does the counting", None)],
         [("semaphores + Phaser", "var(--text)"), ("5.8", None), ("and survives a cancelled atom", None)],
         [("the same, with fair = true", "var(--text)"), ("10.3", None), ("never starves, but pays for it", None)],
         [("synchronized + notifyAll", "var(--err)"), ("48", None), ("one queue wakes every waiter", None)],
         [("the lock itself, uncontended", "var(--acc)"), ("0.004", None), ("4 ns: the lock is not the cost", None)]]
m8 += _table(20, 46, cols8, rows8, rowh=28, widths=560)
m8 += _tx(300, 256, "four park-and-unpark trips a molecule, ~2 us each: the parking is the bill", "var(--acc)", 11)
m8 += _tx(890, 34, "the ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1   signal exactly as many as the seats that opened", "two H and one O, not signalAll: free, and 69 ms becomes 13"),
                              ("2   semaphores + a CyclicBarrier of three", "the library counts and rendezvouses: 12.2 us becomes 6.6"),
                              ("3   semaphores + a Phaser", "5.8 us, and one cancelled atom no longer breaks the barrier for good")]):
    m8 += _bx(600, 50 + k*58, 600, 46, t, sub, acc=(k == 0))
m8 += _tx(900, 256, "no rung four: a lock-free barrier is a research paper, not an interview answer", "var(--muted)", 11)
# what the library already gives you -- and why not one class of it answers this problem alone
cols8b = [("what java.util.concurrent gives you", 12), ("what it does for you", 260), ("why it is not the whole answer on its own", 620)]
rows8b = [[("Semaphore(n)", "var(--text)"), ("a counting cap: at most n threads inside at once", None), ("caps hydrogen at two, but never makes anybody wait for the oxygen", None)],
          [("CountDownLatch(3)", "var(--text)"), ("wait until three things have happened", None), ("one-shot: it stays at zero, so molecule two is a lone atom walking through", "var(--err)")],
          [("CyclicBarrier(3)", "var(--text)"), ("a rendezvous that resets itself every generation", None), ("counts parties, not kinds: three hydrogen trip it. That is the H,H,H bug", "var(--err)")],
          [("Phaser", "var(--text)"), ("the same, with a party count that can change", None), ("same blindness to kind, but one cancelled party does not break it for good", None)],
          [("ReentrantLock + Condition", "var(--acc)"), ("one queue of sleepers per thing worth waiting for", None), ("you write the protocol yourself &mdash; which is exactly the build on page 04", None)],
          [("Exchanger, SynchronousQueue", "var(--text)"), ("a handoff between exactly two threads", None), ("a molecule is three threads, and they are not interchangeable", None)]]
m8 += _table(20, 300, cols8b, rows8b, rowh=26, widths=1190)
m8 += _tx(615, 494, "so the honest answer to &quot;could you just use X&quot; is that it takes two of them at once: a Semaphore per element for the cap, and a CyclicBarrier or Phaser for the rendezvous", "var(--acc)", 11)
MV[8] = _mv(1230, 510, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("a barrier of three with no per-element cap", "a semaphore or a seat count per element; test 1 &mdash; 1,000 molecules, every window checked"),
                                ("the seat freed before the emit, not after", "free it in the finally AFTER release.run(); test 1 &mdash; N+1 would leak into N's window"),
                                ("if instead of while around a wait", "re-test in a loop, always; tests 1 and 3 &mdash; a spare hydrogen must stay asleep"),
                                ("one monitor and notify()", "with one queue you must use notifyAll; the monitor build in Extensions.java shows why"),
                                ("an interrupted atom keeps its seat", "hand the seat back and signal a peer; test 4 &mdash; the next molecule must still form"),
                                ("a release callback throws", "count the emit in a finally; test 5 &mdash; twenty more molecules form afterwards"),
                                ("a CountDownLatch instead of a CyclicBarrier", "it is one-shot: after molecule 1 every lone atom walks straight through (ExtDemo)"),
                                ("a listener called inside the lock, or throwing", "publish after the unlock in a try/catch; test 9 &mdash; a listener that always throws"),
                                ("each caller thread supplies its own quota", "not a bug in the barrier at all; test 10 &mdash; one thread owning both H waits for itself forever")]):
    y = 18 + k*40
    m9 += _bx(30, y, 350, 36, bad, "") + _ar("M380 %s H400" % (y+18), True) + _bx(400, y, 800, 36, fix, "", acc=True)
m9 += _tx(615, 398, "twenty checks in FailureTests.java, every wait with a deadline, every thread a daemon and a 45-second watchdog behind all of it:", "var(--muted)", 11)
m9 += _tx(615, 418, "a barrier test that hangs has told you nothing, so this suite is built so that a bug shows up as a FAIL and never as a stuck build", "var(--muted)", 11)
MV[9] = _mv(1230, 432, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 190), ("the line in the code", 280), ("what it buys", 830)]
rows10 = [[("Monitor object", "var(--text)"), ("move 4", None), ("one ReentrantLock + three Conditions, all private", None), ("state is touched only through a method that locks", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface Recipe { int needed(Element e); }", None), ("2:1 is data; peroxide is a lambda", None)],
          [("Strategy again", "var(--text)"), ("move 3", None), ("interface MoleculeBarrier: H2OBarrier, SemaphoreBarrier", None), ("the whole build swaps behind one name", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("MeteredBarrier implements MoleculeBarrier, wraps one", None), ("measurement without opening the barrier", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(index, atMs) after the unlock, in a try/catch", None), ("a dashboard can never stall an atom", None)],
          [("Command", "var(--text)"), ("move 2", None), ("the release Runnable, handed in by the caller", None), ("we own WHEN; the caller owns WHAT", None)],
          [("State", "var(--text)"), ("move 6", None), ("the two while loops ARE the atom's state machine", None), ("a wake goes back to the check, never to the emit", None)],
          [("Barrier / rendezvous", "var(--text)"), ("every move", None), ("hold N parties, release them as one, then reset", None), ("the thing this object IS; say the name", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the barrier is handed to both sides; no getInstance()", "var(--muted)"), ("a test builds a fresh one per case", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("new H2OBarrier(Recipe.WATER) is one line", "var(--muted)"), ("it earns the name when recipes come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("one constructor argument, and it has a default", "var(--muted)"), ("a builder here would be pure ceremony", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 402, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 418, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 430), ("the line that shows it", 530)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("H2OBarrier synchronises. Recipe says how many. MoleculeCounter counts. Element is identity.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("Recipe.PEROXIDE is a lambda; the lock and both wait loops are untouched", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("FailureTests runs the same window check on H2OBarrier and on SemaphoreBarrier", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Recipe, Clock, MoleculeObserver &mdash; a lambda implements each of them", None)],
          [("D", "var(--acc)"), ("depend on interfaces; be handed the rest", None), ("moves 3, 9", None), ("configure(() -&gt; 1_700_000_000_000L) and a listener that throws on purpose", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "CO2, NH3, any stoichiometry", "a different Recipe lambda; the lock and both wait loops are untouched", "", "move 3"),
        ("someone new wants to know", "a dashboard, a formation log", "one more observer, called after the unlock in a try/catch", "", "move 3"),
        ("a new step in a life", "give up on a deadline; shut down", "a deadline in the wait loops and a closed flag they already read", "", "move 6"),
        ("a new invariant across parties", "at most N inside, never mixed", "the same lock, a different predicate: that is the unisex bathroom", "", "move 4"),
        ("state that must outlive the process", "atoms arriving from two machines", "the seats become a broker's consumer group and the rendezvous becomes", "a transaction that commits all three offsets or none: the same order, one layer down", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the seat counts, the two wait loops and the order at the emit are untouched; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class &mdash; and on a threading problem, notice what does not.",
 "Reading the sentence again: a <b>hydrogen</b> and an <b>oxygen</b> arrive at a <b>barrier</b>; a <b>molecule</b> "
 "needs two H and one O; whoever cannot bond yet <b>waits</b>; when the set is complete all three <b>release</b>. "
 "The barrier holds the lock, the seat counts, the waiting rooms and the count of molecules so far: a class, and "
 "the only one the callers ever touch. An element is identity and nothing else &mdash; no fields that move &mdash; "
 "so it is an enum, and every per-element array in the design is indexed by its ordinal. Then the four that a "
 "threading problem tempts you to make classes and must not. The recipe has no state, only an answer, so it is a "
 "one-method interface. A <i>molecule</i> is not an object at all: it is a generation number, because nothing is "
 "ever asked about a molecule after it has left. A hydrogen atom is not an object either &mdash; it is a thread "
 "that calls a method and hands in a callback. And the waiting rooms are not lists you keep: they are queues of "
 "parked threads the lock already maintains, reached only through <code>await</code> and <code>signal</code>. "
 "Writing an <code>Atom</code> class here is the classic wrong turn, and it drags a <code>Waiter</code> list along "
 "behind it.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Cap how many atoms of one element may enter\" touches the seat counts, so it belongs to the barrier: "
 "<code>while (seated[e] == needed[e]) seatFree.await()</code>. \"Hold everybody until the set is complete\" "
 "touches the lock and its waiting rooms, so it belongs to the barrier too. \"Say how many atoms a molecule takes\" "
 "touches nothing at all &mdash; it reads an element and returns a number &mdash; so it is a pure rule, "
 "<code>recipe.needed(e)</code>. \"Close a molecule and open the next\" touches the counters and every waiting "
 "room at once, so it is the barrier again, which is why the barrier is the orchestrator. And then the verb that "
 "belongs to nobody in this design: deciding what \"released\" actually <i>does</i>. Printing an H, appending to a "
 "list, sending a message &mdash; none of that is ours. We own <i>when</i> an atom is let out; the caller hands in "
 "a <code>Runnable</code> that owns <i>what</i> that means. That single split is what makes one barrier reusable "
 "for a puzzle, a test and a real pipeline.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind a one-method interface and is handed in.",
 "Four things will change here, and each becomes something the barrier is <i>given</i> rather than builds. The "
 "stoichiometry changes the moment they say \"now do CO2\", so it is <code>Recipe</code>, one method, and water is "
 "the lambda <code>e -&gt; e == HYDROGEN ? 2 : 1</code>. Where a timestamp comes from changes, because a test "
 "cannot wait for the wall clock &mdash; that is <code>Clock</code>. Who wants to know changes &mdash; that is "
 "<code>MoleculeObserver</code>, called after the unlock so a dashboard can never stall an atom. And the fourth is "
 "the interesting one on a threading problem: the <i>whole build</i> is a rule. <code>MoleculeBarrier</code> is the contract; "
 "<code>H2OBarrier</code> (one lock, three waiting rooms) and <code>SemaphoreBarrier</code> (semaphores plus a "
 "<code>CyclicBarrier</code>) are two implementations of it, and the failure tests run the same window check on "
 "both. This is where the patterns are born, not announced: a swappable rule behind an interface is "
 "<b>Strategy</b>; a wrapper that adds behaviour to the whole interface is <b>Decorator</b>, and here it is "
 "<code>MeteredBarrier</code>, which times any build without that build ever learning it is being measured; a "
 "barrier that says \"a molecule formed\" without knowing what a dashboard is, is <b>Observer</b>.", 3),
("Move 4: state that many threads change at the same time gets one owner and one lock.",
 "Here is the race, and it is not the one people expect. Three hydrogen threads walk up to a bare "
 "<code>CyclicBarrier(3)</code>. It counts to three, trips, and releases H, H, H: a molecule that does not exist. "
 "No lost update, no torn read &mdash; the barrier did exactly what it was told, and what it was told was wrong. "
 "The gap is between \"three parties have arrived\" and \"the <i>right</i> three have arrived\", so the fix is not "
 "a bigger barrier, it is a cap per element: two hydrogen seats and one oxygen seat, checked and taken as a single "
 "step. That means the seat counts, the molecule size, the generation number and the waiting rooms are all one "
 "object's state behind one lock &mdash; the shape with a name, the <b>monitor object</b>. The three waiting rooms "
 "hang off that same lock on purpose: an atom that is about to sleep tests its condition and goes to sleep "
 "<i>without</i> ever releasing the lock in between, which is what makes \"I looked, and then I slept\" atomic. "
 "Extensions.java carries the broken version as runnable code, because being able to demonstrate the bug is worth "
 "more in an interview than describing it. One last thing the lock buys, asked as a separate question often enough "
 "to prepare for: not a single field in <code>H2OBarrier</code> is <code>volatile</code>, and none needs to be, "
 "because one thread's unlock <i>happens-before</i> the next thread's lock and every field is touched only inside "
 "that. It is also why <code>moleculesFormed()</code> takes a lock to return an <code>int</code>: a lock-free read "
 "there would have no happens-before edge behind it and could legally return a stale number.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"How many hydrogen seats are taken?\" is one array read: <code>seated[e.ordinal()]</code>. \"How many does a "
 "molecule need?\" is another, filled once in the constructor from the recipe and never read from the recipe "
 "again, so no rule runs on a hot path. \"Is the molecule complete?\" is the one worth naming: you keep a single "
 "<code>filled</code> counter rather than summing the array every time, so completeness is a comparison and not a "
 "loop. \"Who is waiting for a hydrogen seat?\" needs no structure from us at all &mdash; a <code>Condition</code> "
 "keeps its own queue of parked threads, so parking is O(1) and waking exactly two of them is O(1). And \"which "
 "molecule am I in?\" is a <code>long</code> generation number read under the lock, which costs nothing and is "
 "what lets a woken atom tell \"my molecule filled\" from \"my molecule already came and went\". Nothing scans, "
 "nothing is allocated per atom, and the memory is one small array plus one <code>Condition</code> per element, "
 "forever.", 5),
("Move 6: one atom has a life cycle, and the order of the steps inside it is the design.",
 "Follow one hydrogen along the clock. It takes the lock &mdash; interruptibly, so an atom that ends up parked can "
 "still be cancelled. It finds both hydrogen seats taken and waits on that element's room; when a seat opens it "
 "sits down, and <i>then</i> asks whether the molecule is now complete. If it took the last seat it wakes the "
 "others; otherwise it calls <code>full.await()</code>, which does the thing that makes the whole design work: it "
 "releases the lock while the thread sleeps, and re-acquires it before returning. The band at the bottom of the "
 "picture is the part to memorise, because every wait you will ever write is those three rules, and each one kills "
 "a bug that has a name. A <b>lost wakeup</b> is a signal that fires in the gap between \"I looked\" and \"I "
 "slept\", leaving a thread asleep on a condition that is already true; there is no such gap here, because "
 "<code>await()</code> releases the lock in the same atomic step as parking. A <b>spurious wakeup</b> is the JVM "
 "waking a parked thread for no reason at all, which it is allowed to do; the <code>while</code> loop is the entire "
 "defence, and it is why the arrow from \"woken\" goes back to the check. The one wakeup this design could still "
 "lose is one spent on an atom that is cancelled a moment later, which is the whole job of the "
 "<code>seatFree.signal()</code> in the interrupt handler: pass on the wake you are not going to use. Then the part "
 "people get wrong: the atom <b>unlocks first</b> and only then runs the caller's release, because that callback is "
 "somebody else's code and may be slow or may throw, and holding the lock through it would stall every other atom "
 "in the process. The emit is counted in a <code>finally</code>, so a callback that throws still closes its "
 "molecule; and the seats reopen only after all three emits have returned, which is precisely what stops an atom of "
 "molecule N+1 from appearing inside molecule N's window of three. That closing step takes the lock "
 "<i>un</i>interruptibly on purpose: once the release has run, this atom is committed and must be counted whatever "
 "later happens to its thread.", 6),
("Move 7: yes, one lock means one at a time. Ask for how long, and what is inside it.",
 "Inside the lock there is one array read, two integer updates, a comparison and one signal: measured on this "
 "machine, the whole locked part costs about four nanoseconds. Everything expensive is outside it &mdash; the "
 "caller's release callback, the listeners, and the parking itself, because a park and an unpark is about two "
 "microseconds and a molecule needs four of them. So the honest arithmetic is that the lock is roughly a "
 "twenty-five-hundredth of what a molecule costs, and if you want this faster you do not attack the lock, you "
 "attack the parking. The measured run: a thousand molecules through twenty hydrogen threads and ten oxygen "
 "threads takes twenty-six milliseconds, about thirty-eight thousand molecules a second, and those threads parked "
 "4,997 times &mdash; five parks per molecule, which is the number to volunteer. The picture also shows the thing "
 "the cap buys you: two of the six threads arrive during molecule one and simply cannot sit down, because both "
 "hydrogen seats are taken, and that is the whole defence against H,H,H expressed as a queue rather than as a "
 "check.", 7),
("Move 8: say the arithmetic, name the ladder, and know what the library already gives you.",
 "Measure before you climb. The table is five thousand molecules through thirty threads, and its shape is the "
 "whole lesson: every build lands between five and twelve microseconds a molecule, the "
 "<code>synchronized</code>/<code>notifyAll</code> one lands at forty-eight because a monitor has a single queue "
 "and every wake wakes every waiter in the process, and the lock itself measures four nanoseconds. The lock is "
 "not the cost. The parking is, so the knobs are how many threads you wake and how often anybody sleeps at all. "
 "Rung one of the ladder is therefore free: wake exactly as many waiters as the seats that just opened &mdash; two "
 "hydrogen and one oxygen &mdash; instead of <code>signalAll</code>, which on this workload is the difference "
 "between five parks a molecule and thirty-one, and between thirteen milliseconds and sixty-nine for the same "
 "thousand. That is safe here for a reason worth saying out loud, because it is the follow-up: every thread parked "
 "on <code>seatFree[H]</code> wants the same thing, one hydrogen seat, so they are interchangeable and waking two "
 "of them fills two seats. Use <code>signal</code> on a queue whose sleepers want <i>different</i> things and you "
 "have written a bug &mdash; which is exactly what goes wrong in the single-monitor build. Rung two hands the "
 "counting to the library, and rung three swaps the barrier for a <code>Phaser</code>, which is a little faster "
 "and is not permanently broken by one cancelled party. There is no rung four; a lock-free barrier is a research "
 "paper, not an interview answer. The bottom table answers the question underneath all of this &mdash; \"could you "
 "not just use <i>X</i>?\" &mdash; and the answer is no, never one of them: the cap is per element and the "
 "rendezvous is per molecule, so it always takes two.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The table is the list; three things about it are worth saying rather than reading. First, the second row is the "
 "single most load-bearing line in the file: the seat is handed back <i>after</i> the emit, not before, and the "
 "other order lets an atom of molecule N+1 appear inside molecule N's window of three &mdash; a bug that no "
 "count-based test would catch, which is why the test checks the shape of the output instead. Second, the last row "
 "is not a bug in the barrier at all, and it catches people in real interviews: if every caller thread supplies a "
 "fixed quota of atoms, one thread that owns both hydrogen atoms of a molecule blocks on the first and can never "
 "hand over the second, so nothing completes. The barrier is correct and the way it was driven is not, and the "
 "answer is to feed it from a shared pool &mdash; which is exactly what the demo and the tests do. Third, how the "
 "suite is built: twenty checks, every wait with a deadline, every thread a daemon, a forty-five second watchdog "
 "behind all of it. A concurrency test that hangs has told you nothing, so this one is built so that a bug always "
 "shows up as a FAIL and never as a stuck build.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Read the table down the \"born in\" column rather than the \"pattern\" column: not one of these was chosen, each "
 "is what a move left behind, and that is the difference between naming patterns and reciting them. Two rows are "
 "worth a sentence out loud. The first is <b>monitor object</b>, which is the name of the whole shape &mdash; "
 "private state, one lock, and the only way in is a method that takes it &mdash; and most candidates build it "
 "without ever saying the words. The second is the last real row: this object <i>is</i> a <b>barrier</b>, a "
 "rendezvous that holds N parties and releases them as one, and its interesting variant is that its parties are "
 "<i>typed</i>, which is the entire difficulty of the problem in one sentence. Interviewers notice when you skip "
 "that. The three greyed rows matter too, because a candidate who names a pattern that earned nothing loses more "
 "than one who names none.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is not a list to recite; it is the check that the moves did their job, and the table is the whole answer. "
 "The two lines to say aloud are L and D, because both are provable rather than arguable here: L is the failure "
 "tests running the identical window check over <code>H2OBarrier</code> and <code>SemaphoreBarrier</code> without "
 "asking which one they got, and D is <code>configure()</code>, which is exactly why a test can hand the barrier a "
 "clock frozen at one instant and a listener that throws on purpose, and then assert that neither of them changed "
 "a molecule.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Four of the five rows leave the seat counts, both wait loops and the order at the emit completely untouched, and "
 "that is the test that the derivation was right: if a twist forces you back into the wait loops, a move was "
 "wrong. Row four is the one to recognise on sight &mdash; \"at most three in the bathroom and never two kinds at "
 "once\" is this same problem wearing a hat, one lock with a different predicate, and saying so is most of the "
 "answer. Row five is the only one that genuinely changes shape: once the atoms arrive from two machines the seats "
 "become a broker's consumer group and the rendezvous becomes a transaction that commits all three offsets or "
 "none. Even there the ordering rule survives word for word &mdash; commit only after the work succeeded. Page 05 "
 "has runnable code for each.", 12),
]
DERIVATION_LEAD = ("The same twelve moves as every other page in this folder, run on a problem with almost no data in it. "
 "That is what makes it a good rehearsal: there is nowhere to hide behind classes, so every move has to earn its place "
 "on the ordering of four lines of code. The invariant is not arithmetic here, it is a shape &mdash; read the released "
 "atoms in order and every window of three must be exactly two H and one O &mdash; and moves 4, 6 and 7 are where that "
 "shape is won or lost.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the decorator, the two kinds of caller, the listener and the clock
put("metered", 10, 20, 250, "MeteredBarrier", ["inner: MoleculeBarrier"],
    ["hydrogen / oxygen: times it,", "  then delegates"], "Extensions.java")
put("hthread", 10, 130, 250, "Hydrogen thread", [], ["barrier.hydrogen(emit)"])
put("othread", 10, 204, 250, "Oxygen thread", [], ["barrier.oxygen(emit)"])
put("obs", 10, 285, 250, "MoleculeObserver", [], ["onMolecule(index, atMs)"], "interface")
put("counter", 10, 365, 250, "MoleculeCounter", ["seen: AtomicLong"], ["counts, after the unlock"])
put("clock", 10, 465, 250, "Clock", [], ["nowMs(): long"], "interface")
# centre: the contract, then the aggregate root
put("iface", 310, 20, 370, "MoleculeBarrier", [],
    ["hydrogen(release)", "oxygen(release)", "moleculesFormed(): long"], "interface")
put("barrier", 310, 160, 370, "H2OBarrier",
    ["lock: ReentrantLock", "seatFree: EnumMap&lt;Element, Condition&gt;", "full: Condition",
     "needed[] / seated[]: int", "size / filled / emitted: int", "molecules: long  (the generation)",
     "clock: Clock", "observers: List&lt;MoleculeObserver&gt;"],
    ["hydrogen(r) / oxygen(r)", "atom(e, r)  the whole life", "sitDown(e)  [takes the lock]",
     "closeMyEmit()  [takes the lock]", "publish(i, ms)  [after unlock]", "configure(clock) / addObserver(o)",
     "moleculesFormed() / seatedCount(e)", "waitCount(): long", "&nbsp;"])
# third column: the rules and the alternative build
put("recipe", 720, 20, 250, "Recipe", [], ["needed(e): int", "WATER, PEROXIDE"], "interface")
put("element", 720, 120, 250, "Element", ["HYDROGEN(\"H\"), OXYGEN(\"O\")"], [], "enum")
put("sem", 720, 200, 250, "SemaphoreBarrier",
    ["seats: EnumMap&lt;Element, Semaphore&gt;", "bond: CyclicBarrier(3)"],
    ["acquire, await, emit, release", "  the permit AFTER the emit"])
# far right: the other builds, all behind the same contract, all from Extensions.java
put("phaser", 990, 190, 240, "PhaserBarrier", [], ["arrive + awaitAdvance", "page 05: ladder rung 3"], "Extensions.java")
put("monitor", 990, 300, 240, "MonitorBarrier", [], ["synchronized + notifyAll", "page 05: no locks package"], "Extensions.java")

def raw(x, y, w, h, title, sub, chips):
    """the three waiting rooms: not classes, so they are drawn as what they are -- queues of parked threads"""
    g = '<g transform="translate(%s %s)"><rect width="%s" height="%s" rx="6" fill="var(--bg3)" stroke="var(--acc)" stroke-dasharray="5 3"/>' % (x, y, w, h)
    g += '<text x="%s" y="22" text-anchor="middle" font-size="12.5" fill="var(--acc)">%s</text>' % (w/2, title)
    for k, c in enumerate(chips):
        g += '<rect x="%s" y="34" width="46" height="22" rx="11" fill="#12302a" stroke="var(--acc)"/>' % (16 + k*54)
        g += '<text x="%s" y="49" text-anchor="middle" font-size="11" fill="var(--text)">%s</text>' % (39 + k*54, c)
    g += '<text x="%s" y="49" font-size="10.5" fill="var(--muted)">%s</text>' % (16 + len(chips)*54 + 8, sub)
    return g + '</g>'

def stub(x1, y, x2):
    return '<path d="M%s %s H%s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y, x2)

EDGES = [
 # the reference build implements the contract
 ln(B["barrier"]["t"], B["iface"]["b"], "inherit"),
 # every other build joins one bus and implements the same contract
 stub(970, 253, 975), stub(990, 225, 975), stub(990, 335, 975),
 ln((975, 335), (680, 63), "inherit", "", [(975, 103), (692, 103), (692, 63)]),
 _tx(985, 96, "three more builds, one contract", "var(--acc)", 10.5, "start"),
 # and the two types that deliberately stay OUTSIDE it, because they change the contract itself
 _card(925, 400, 300, 128, "deliberately NOT behind it",
       ["TimedBarrier: its calls can return", "false, so the contract changes",
        "MoleculeAssembler: keyed by symbol,", "not by a two-value enum",
        "both in Extensions.java, page 05"], dash=True),
 # the decorator implements it and wraps one
 ln(B["metered"]["r"], B["iface"]["l"], "inherit"),
 ln((260, 95), (310, 210), "assoc", "", [(274, 95), (274, 210)]),
 _tx(288, 124, "wraps one", "var(--muted)", 10.5),
 # the rules are handed in
 ln(B["recipe"]["l"], (680, 195), "inject", "", [(702, 55), (702, 195)]),
 _tx(695, 148, "the recipe: constructor", "var(--acc)", 10.5, "end"),
 ln(B["clock"]["r"], (310, 425), "inject", "", [(282, 492), (282, 425)]),
 # the barrier references the enum, and notifies the listeners
 ln((680, 245), B["element"]["l"], "assoc", "", [(710, 245), (710, 145)]),
 ln((310, 370), B["obs"]["r"], "notify", "", [(290, 370), (290, 312)]),
 ln(B["counter"]["t"], B["obs"]["b"], "inherit"),
 # the callers
 ln(B["hthread"]["r"], (310, 260), "assoc", "", [(298, 157), (298, 260)]),
 ln(B["othread"]["r"], (310, 290), "assoc", "", [(266, 231), (266, 290)]),
 # the three waiting rooms, all owned by the same lock
 raw(310, 560, 290, 74, "seatFree[H]", "2 seats", ["H5", "H9"]),
 raw(620, 560, 270, 74, "seatFree[O]", "1 seat", ["O3"]),
 raw(910, 560, 300, 74, "full &mdash; seated, waiting", "signalAll", ["H1", "H2"]),
 ln((400, 474), (420, 560), "compose", "", [(400, 538), (420, 538)]),
 ln((495, 474), (755, 560), "compose", "", [(495, 538), (755, 538)]),
 ln((590, 474), (1060, 560), "compose", "", [(590, 538), (1060, 538)]),
 _tx(615, 654, "these three are not classes: they are the queues of parked threads that the lock keeps for each Condition, reached only through await() and signal()", "var(--muted)", 11),
]
UMLSVG = uml_svg(1230, 700, EDGES, legend_y=680)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the type name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods; <code>[takes the lock]</code> marks '
 'the two private steps that do the locking, and <code>[after unlock]</code> marks the one that must never run '
 'inside it. A &laquo;Extensions.java&raquo; tag on a box means it lives in the second file, the one that holds the '
 'answer to a follow-up; everything untagged is in Main.java. <b>The arrows.</b> Hollow triangle = implements: four '
 'builds and one decorator satisfy the one contract the '
 'callers depend on, which is why the failure tests can run the same window check over two of them. Filled diamond '
 '= owns: the barrier owns its lock and all three waiting rooms, and they die with it. Dashed green = handed in '
 '&mdash; the recipe through the constructor, because it decides how many waiting rooms exist, and the clock through '
 '<code>configure()</code>. Dotted blue = notifies. <b>Where state lives:</b> every mutable field in this design is '
 'inside <code>H2OBarrier</code>, and every one of them is read and written only under the one lock &mdash; that is '
 'the entire safety argument, and it is why the caller\'s callback is deliberately run <i>outside</i> that lock. '
 'Notice what is <i>not</i> a class: a hydrogen atom is a thread, a molecule is the <code>molecules</code> counter, '
 'and the three waiting rooms at the bottom are queues of parked threads the lock maintains for each '
 '<code>Condition</code>. The dashed card on the right names the two types that deliberately stay <i>outside</i> '
 'the interface, because they change the contract rather than the implementation. And notice what is not on this '
 'diagram either: there is no <code>FairBarrier</code>, because fairness turned out to be a constructor flag on '
 'the two builds that are already here.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies &mdash; and on this problem '
 'read <code>sitDown</code> and <code>closeMyEmit</code> together, because the correctness lives in the order between '
 'them. Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s '
 'reference code, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (twenty claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (is the ratio fixed, and may the callbacks block, are '
 'the first two); then type in the order of Main.java: the Element enum, the Clock and Recipe interfaces with '
 '<code>Recipe.WATER</code>, the MoleculeObserver, the MoleculeBarrier contract, then H2OBarrier &mdash; its fields, '
 'its constructor from the recipe, <code>sitDown</code> with its two while loops, <code>closeMyEmit</code>, and '
 '<code>atom</code> which puts them either side of the caller\'s release; then the SemaphoreBarrier for contrast; then '
 'a main with thirty threads and a latch that checks every window of three.</div></div>')

FU = [
("Now it is CO2. Then NH3. Then any molecule at all.", "twist", 10,
 "The stoichiometry is already an interface, so for anything the <code>Element</code> enum can name this is a "
 "different lambda and nothing else: <code>new H2OBarrier(e -&gt; 2)</code> is hydrogen peroxide, and "
 "the failure tests check that it releases clean groups of two H and two O. The constructor reads the recipe once, "
 "sums it into the molecule size and builds one waiting room per element, so no rule is ever consulted on a hot "
 "path. When the elements outgrow a two-value enum, the same body keyed by symbol is <code>MoleculeAssembler</code>: "
 "a map from symbol to seat count, a map from symbol to <code>Condition</code>, and the identical protocol. The "
 "thing to point at is what did <i>not</i> change &mdash; the lock, both wait loops, and the rule that the seats "
 "reopen only after the last emit.",
 X("any molecule", "ladder rung three")),
("Two hydrogen and one oxygen arrive from three different threads at the same instant. Prove you cannot ship HHH.", "non-functional", 10,
 "The cap is what makes a malformed molecule impossible, not the rendezvous: a third hydrogen cannot take a seat "
 "while two are taken, so the set that completes can only ever be two H and one O. The proof is a shape rather than "
 "a count. Twenty hydrogen threads and ten oxygen threads pull atoms from a shared pool behind one latch, every "
 "release appends its letter to one buffer, and the test then walks that buffer three characters at a time and "
 "demands exactly two H and one O in every window. That catches both failures at once: a bad set inside a window, "
 "and a good set that leaked across a window boundary because a seat was freed too early. A thousand molecules, "
 "three thousand atoms, and the listener must have been told exactly a thousand times.",
 T("        // 1. the race", "        // 2. nobody leaves early")),
("One lock for the whole barrier. Have you serialised it? And is every read really O(1)?", "non-functional", 5,
 "Yes, one at a time &mdash; for four nanoseconds. That is the whole locked part: one array read, two integer "
 "updates, a comparison and one signal, with nothing in it that can block. Every read on the object is a field "
 "read under that same lock, so the molecule count, the seats taken and the wait count are each O(1) with no scan "
 "anywhere; they take the lock not for speed but for visibility, since a lock-free read here would have no "
 "happens-before edge behind it. The cost of a molecule is the sleeping, not the locking: a park and an unpark is "
 "about two microseconds and a molecule needs four of them, so a molecule costs 12.2 microseconds and the lock "
 "inside it costs 0.004 &mdash; which is why the ladder in move 8 attacks the parking and never the lock.",
 M("private long closeMyEmit()", "private void publish")
 + "\n" + M("public long moleculesFormed() { lock.lock()", "final class SemaphoreBarrier")),
("A release callback throws. What is the state of the barrier?", "functional", 5,
 "Exactly what it would have been. The callback runs outside the lock, and the emit is counted in a "
 "<code>finally</code>, so the molecule still closes, the seats still reopen and the exception travels up to the "
 "thread that supplied the bad callback &mdash; which is the right place for it, because it is their code. Nothing "
 "half-done is possible either side of that: before the emit, an atom that throws has not changed a counter; after "
 "it, the counter has been changed by the <code>finally</code> regardless. The failure test proves both halves &mdash; "
 "the throwing caller sees its own exception, its molecule still counts as formed, and twenty more molecules form "
 "on the same barrier afterwards. The same rule covers listeners: they are called after the unlock inside a "
 "try/catch, so a dashboard that is down cannot take a molecule with it.",
 M("void atom(Element e, Runnable release)", "private void sitDown")),
("An atom is cancelled while it waits. What happens to its seat?", "functional", 10,
 "It gives it back before it goes, and the two places a thread can be parked are not the same case. Waiting for a "
 "<i>seat</i> it has changed nothing, so it just rethrows &mdash; but it signals that element's room on the way "
 "out, because the wakeup it was given must not die with it. Waiting for the <i>molecule</i> it is already seated, "
 "so it decrements the seat, decrements the filled count and signals somebody who wanted that seat. The subtlety "
 "worth saying out loud: if the molecule completed while the interrupt was being delivered, backing out would be "
 "wrong, so it checks, and if it is committed it re-sets the interrupt flag and finishes its emit. The test proves "
 "it the only honest way: cancel a lonely hydrogen, then feed two hydrogen and one oxygen and require a molecule. "
 "If the seat had not come back, that molecule could never complete and the test would time out.",
 T("        // 4. an interrupted atom", "        // 5. a release callback")),
("Do it with java.util.concurrent instead. Which classes, and why is a CountDownLatch wrong?", "design", 10,
 "Not one class in the package does both jobs, because the cap is per element and the rendezvous is per molecule "
 "(the table at the bottom of move 8 goes through them one at a time). It takes two of them. A counting semaphore "
 "per element is exactly the "
 "cap &mdash; two permits for hydrogen, one for oxygen &mdash; and a <code>CyclicBarrier</code> of three is the "
 "rendezvous. The load-bearing line is the <code>finally</code> below &mdash; the whole class is "
 "<code>SemaphoreBarrier</code> on page 04 and the four lines that matter are here: the permit goes back "
 "<i>after</i> the release has "
 "run, not before the rendezvous, so all three permits of molecule N return only once N is fully emitted and N+1 "
 "cannot trip early. It is faster than the hand-written version (6.6 microseconds a molecule against 12.2) because "
 "the library does the waking. A <code>CountDownLatch</code> is wrong because it is one-shot: it counts down to "
 "zero and stays there, so molecule one is correct and every atom after it walks straight through alone &mdash; the "
 "demo shows a lone oxygen released with no hydrogen near it, which is worse than hanging because it looks like it "
 "works. <code>CyclicBarrier</code> resets itself each generation; its own weakness is that one cancelled party "
 "breaks it permanently, which is the argument for the <code>PhaserBarrier</code> on page 04 &mdash; same shape, "
 "one line different.",
 M("Semaphore seat = seats.get(e);", "public long moleculesFormed() { return molecules.get(); }")
 + "\n" + X("why a CountDownLatch", "the naive barrier")),
("Make every wait time out, and let me shut the thing down.", "twist", 10,
 "Both are the same move: something the wait loops already read. Every <code>await</code> becomes an "
 "<code>awaitNanos</code> against one deadline computed at entry, so the whole call has a budget rather than each "
 "wait having its own; when the budget runs out the atom hands its seat back, returns <code>false</code>, and its "
 "release never runs, so the caller can retry or give up with nothing half-done. Shutdown is a <code>closed</code> "
 "flag checked at the top of both loops plus a <code>signalAll</code> on every room, so nobody is left parked: a "
 "seated atom backs out of its seat and leaves with an exception. The rule that holds both together is the one from "
 "move 6 &mdash; an atom that leaves early must undo its seat first, or the next molecule waits forever for a "
 "thread that has gone. Only the changed half is below; the fields, the constructor and the closing step are byte "
 "for byte the reference build's, and you read them on page 04.",
 M("boolean atom(Element e, Runnable release, long timeoutMs)", "private void closeMyEmit()", ext)),
("Take java.util.concurrent.locks away. Do it with synchronized.", "twist", 10,
 "The four steps do not change: <code>synchronized (this)</code> replaces the lock, <code>wait()</code> replaces "
 "<code>await()</code>, and <code>notifyAll()</code> replaces <code>signal()</code>. What changes is the cost and "
 "one hard rule. A monitor has exactly one queue, so <code>notify()</code> is a bug here rather than an "
 "optimisation: it can hand the single wakeup to an atom that is waiting for a <i>seat</i> when the atom waiting "
 "for the <i>molecule</i> needed it, and that thread then goes straight back to sleep with the wakeup spent. "
 "<code>notifyAll</code> is correct and it is also why this version measures forty-eight microseconds a molecule "
 "against 12.2 &mdash; every wake wakes every waiter in the process. That is the whole argument for "
 "<code>Condition</code>: three queues instead of one, so you can wake exactly the two hydrogen and one oxygen that "
 "can actually proceed.",
 X("the synchronized", "the unisex bathroom")),
("Is any thread ever starved here? Make it fair.", "non-functional", 5,
 "Yes, and the measurement is uncomfortable, which is why it is worth running. Over fifteen hundred molecules with "
 "thirty threads, the busiest thread handled 276 atoms and the quietest handled one: a non-fair lock hands the "
 "next seat to whichever thread happens to be running, so a hot thread barges past a queue of sleepers. "
 "Correctness never suffers &mdash; every atom is placed, every molecule is well formed &mdash; but an unlucky "
 "caller's latency does. Notice what the fix is <i>not</i>: it is not another class. Both builds take a "
 "<code>fair</code> flag in the constructor, which becomes <code>new ReentrantLock(true)</code> on the reference "
 "build and <code>new Semaphore(n, true)</code> on the semaphore one, and the seat then goes to the longest "
 "waiter. The same run then reads 149 to 155 atoms per thread instead of 1 to 276, and costs about thirty-five per "
 "cent of the throughput (10.3 microseconds a molecule against 6.6) because every handoff becomes a context "
 "switch. Say the number, then let them choose.",
 M("H2OBarrier(Recipe recipe, boolean fair)", "void configure(Clock clock)")
 + "\n" + M("SemaphoreBarrier(Recipe recipe, boolean fair)", "public void hydrogen(Runnable releaseHydrogen) throws InterruptedException {")
 + "\n" + T("        // 7. nobody is left behind", "        // 8. the 2:1 rule")),
("Measure it without touching it.", "design", 5,
 "Both sides already depend on an interface, so the measurement goes in a class that implements that interface and "
 "wraps another one. <code>MeteredBarrier</code> times each call from entry to release, keeps a running total and a "
 "worst case in atomics, and delegates the molecule count upward; the barrier it wraps is not edited, not "
 "subclassed and never learns it is being watched, and the only change at the call site is one <code>new</code>. "
 "That is Decorator earning its place from move 3 rather than being announced. It is also how you answer \"how do "
 "you know the barrier is the bottleneck\": wrapped around the reference build under thirty threads, an atom waits "
 "about 150 microseconds on average, which is mostly the backlog of other atoms rather than the barrier itself.",
 X("measure without touching", "Runs every extension")),
("Same idea, different rule: at most three people in the bathroom, and never two kinds at once.", "twist", 10,
 "It is this problem wearing a hat, and saying so is most of the answer. The H2O barrier says \"nobody leaves until "
 "the set is complete\"; the bathroom says \"nobody enters unless the room already matches\". One lock, one "
 "condition, and a predicate: wait while the room is neither empty nor already your kind with room left. Leaving "
 "decrements, and the last one out clears the kind &mdash; the only moment the other kind can get in, which is why "
 "the signal on the way out is <code>signalAll</code>: the room changed kind, so everybody must look again. The "
 "demo runs sixty people through a room of three and counts how many times two kinds were inside together, which "
 "must be zero. The honest caveat is the usual one: this version can starve one kind under a steady stream of the "
 "other, and the fix is the same fairness flag.",
 X("the unisex bathroom", "measure without touching")),
("Where does time come from, and how do you test what a molecule was stamped with?", "design", 3,
 "The barrier has a <code>Clock</code> it was handed and stamps each completed molecule with it when it tells the "
 "listeners; nothing else in the design reads the wall clock. A test hands in a clock that returns a fixed instant, "
 "runs fifty molecules and asserts the exact timestamp the listener saw, which takes microseconds instead of "
 "waiting for real time to pass. The same seam is what makes the timed variant testable: its deadline is computed "
 "from a clock rather than discovered from one.",
 "/** Where time comes from. Injected, so a test decides what \"now\" is instead of waiting for it. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the barrier: handed in, defaulted, never read from the wall clock inside a method\n"
 "private Clock clock = System::currentTimeMillis;\n"
 "void configure(Clock clock) { this.clock = Objects.requireNonNull(clock, \"clock\"); }\n\n"
 "// and the only place it is read: after the lock is released, when the listeners are told\n"
 "long done = closeMyEmit();\n"
 "if (done > 0) publish(done, clock.nowMs());\n\n"
 "// in a test: pin the instant, then assert what the listener was told\n"
 "told.configure(() -> 1_700_000_000_000L);\n"
 "race(told, new StringBuffer(), 50, 4, 2);\n"
 "check(good.lastAtMs() == 1_700_000_000_000L, \"stamped with the injected clock, not the wall clock\");\n"),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "None of them was chosen up front; each is what a move produced, and the code below is the one line that proves "
 "each claim. The full tables are moves 10 and 11 &mdash; what matters when you are asked this out loud is the "
 "order you say it in: name the move, then the pattern, never the other way round. The two most people miss are "
 "the two that have no <code>new</code> anywhere: the object as a whole is a <b>monitor object</b>, and it "
 "<i>is</i> a <b>barrier</b> whose parties are typed. And be ready for the negative half of the question, which is "
 "where the marks are: Singleton earned nothing here, Factory earns its place only the day recipes arrive as "
 "configuration strings, and Builder never will &mdash; there is one constructor argument and it has a default.",
 "// Strategy: the ratio is data, handed in, never built by the barrier\n"
 "interface Recipe { int needed(Element e); Recipe WATER = e -> e == Element.HYDROGEN ? 2 : 1; }\n\n"
 "// Strategy again: the whole build is swappable, and the tests prove it by running over both\n"
 "for (MoleculeBarrier barrier : List.of(new H2OBarrier(), new SemaphoreBarrier())) { /* same checks */ }\n\n"
 "// Decorator: measure any build without opening it\n"
 "MoleculeBarrier metered = new MeteredBarrier(new H2OBarrier());\n\n"
 "// Observer: the barrier announces; it does not know what a dashboard is\n"
 "private void publish(long index, long atMs) {\n"
 "    for (MoleculeObserver o : observers) { try { o.onMolecule(index, atMs); } catch (RuntimeException ignored) { } }\n"
 "}\n\n"
 "// Command: we own WHEN an atom leaves; the caller owns WHAT leaving means\n"
 "barrier.hydrogen(() -> out.append(\"H\"));\n\n"
 "// State: the while loop IS the state machine, and the loop is the arrow from woken back to check\n"
 "while (molecules == mine && filled < size) { waits++; full.await(); }\n\n"
 "// Factory: not yet. One line, with a default; it earns the name when recipes come from config strings\n"
 "Map<String, Recipe> byName = Map.of(\"WATER\", Recipe.WATER, \"PEROXIDE\", Recipe.PEROXIDE);\n"),
]

build(dict(
    slug="mt-h2o", title="H2O Barrier",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 20 failure tests and a 1000-molecule race pass",
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
