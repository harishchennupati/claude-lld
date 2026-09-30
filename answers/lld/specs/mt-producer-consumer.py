# Producer-Consumer LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"mt-producer-consumer/Main.java").read_text()
ext   = (H/"mt-producer-consumer/Extensions.java").read_text()
tests = (H/"mt-producer-consumer/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("produce",  26, [("a producer thread makes a task", "on its own thread, at its own speed"),
                          ("ask the overflow policy", "block, shed, or give up"),
                          ("hand it over under the lock", "in the buffer before it is counted"),
                          ("count it admitted", "exactly once, and never before")]),
        ("consume", 150, [("take: sleep while empty", "no spinning, no burnt core"),
                          ("do the slow work", "milliseconds, outside every lock"),
                          ("count it consumed", "only after the work returned"),
                          ("it threw? park it", "a dead-letter, never a loss")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 2))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M815 80 V92", dash=True) + _bx(560, 92, 510, 40, "buffer full: the producer parks, or the item is shed", "", dash=True)
pf += _tx(88, 232, "stop", "var(--acc)", 13) + _tx(175, 232, "shutdown(ms): producers stop and are joined, then one pill per consumer goes in behind every real task; each consumer drains and ends", "var(--text)", 12, "start")
pf += _tx(88, 258, "stop now", "var(--acc)", 13) + _tx(175, 258, "shutdownNow(ms): every thread is interrupted, and whatever is still in the buffer is handed BACK to the caller as a list", "var(--text)", 12, "start")
pf += _tx(88, 284, "read", "var(--acc)", 13) + _tx(175, 284, "stats(), at any moment, without stopping anything: how deep is the buffer? how many produced, admitted, consumed, dropped, parked?", "var(--text)", 12, "start")
pf += _tx(615, 322, "many producers and many consumers on one buffer: every item is consumed exactly once, and the buffer never holds more than its capacity", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 338, pf)

# one run, replayed -- the numbers are from the demo in Main.java
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("t = 0 ms   the gate opens", ["3 producers, 2 consumers, capacity 4", "both consumers asleep on notEmpty",
                                    "one latch releases all five at once"], True),
      ("t = 6 ms   the buffer is full", ["producer-2 parks holding task#44", "about 50 park events in 60 items",
                                         "memory stops growing"], False),
      ("t = 112 ms   producers done", ["4 items still in the buffer", "producers joined, then 2 pills in",
                                       "RUNNING -> DRAINING"], False),
      ("t = 120 ms   TERMINATED", ["produced 60, admitted 60, done 60", "depth 0, pills 2, threads alive 0",
                                   "the ledger balances"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 105, t, lines, acc=acc)
P_EX = _mv(1230, 180, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Many producer threads make items; many consumer threads process them; one bounded buffer sits between.</li>
<li>A consumer with nothing to do sleeps until work arrives, and wakes the instant it does.</li>
<li>When the buffer is full the producer waits &mdash; that wait is back-pressure, and it is a feature.</li>
<li>The full-buffer decision is swappable: block, drop the newest, evict the oldest, or give up after a deadline.</li>
<li>Two shutdowns: the drained one (everything queued is still processed) and the stop-now one, which interrupts the threads and hands the unprocessed work back to the caller.</li>
<li>Work that throws does not vanish: it is parked in a dead-letter queue and counted.</li>
<li>Counters an operator can read: produced, admitted, dropped, consumed, depth, park events, blocked time.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Every item produced is consumed exactly once: none lost, none done twice.</li>
<li>The buffer never holds more than its capacity, for a single instant, under any number of threads.</li>
<li>Memory is O(capacity) whatever the arrival rate &mdash; an unbounded queue is an out-of-memory crash on a delay.</li>
<li>put and take are O(1), nothing slow runs inside the lock, and a waiting thread costs no CPU: it sleeps, it does not spin.</li>
<li>No producer and no consumer is starved: every thread that waits is eventually served, and the page says what that costs.</li>
<li>Shutdown is bounded: it returns with an answer, it never hangs.</li>
<li>In memory, one JVM, no durability (say it; a crash loses the buffer &mdash; a follow-up adds the seam).</li></ul></div></div>
'''

PROMPT = ('"Build a producer-consumer pipeline. Several threads produce work, several threads consume it, and a '
          'fixed-size buffer sits between them. When the consumers fall behind, the producers must feel it; when the '
          'run is over, nothing may be left in the buffer and no thread may be left alive. I want working code, not a '
          'diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>One side of the program makes work &mdash; rows off a '
 'socket, images to resize, events to index &mdash; and the other side does it, and the two sides run at different '
 'speeds on different threads. Between them sits a buffer with a fixed number of slots. If the makers are faster, the '
 'buffer fills, and something has to happen: the makers wait, or work gets thrown away. That choice is the whole '
 'design, and the wrong answer is an unbounded queue, which does not remove the problem but converts a slow consumer '
 'into an out-of-memory crash an hour later. The second half of the problem is stopping: when the source is exhausted, '
 'every item already in the buffer still has to be processed, and every thread has to actually end &mdash; not be '
 'killed, not be left parked forever. The one thing that must always be true is arithmetic: every item produced is '
 'consumed exactly once, never twice, never zero times.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile, and a '
 '<code>main</code> that starts ten producers and ten consumers and prints counts that add up. The interviewer is '
 'watching for, in this order: the questions you ask before typing (what happens when it is full, and must shutdown '
 'drain, are the first two); which classes exist and which one owns the buffer; the hand-off end to end; the race, '
 'written as a wait protocol rather than a lock sprinkled on top &mdash; check under the lock, wait in a '
 '<code>while</code> loop, signal after the change; where the rule that will change (what a full buffer means) lives; '
 'and the shutdown &mdash; both of them &mdash; which is where most candidates lose the round. Then the twists: '
 'per-key order, batching, many stages, a pool instead of threads, and what changes the day this crosses a process '
 'boundary.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>When the buffer is full, do producers wait, or do we drop? Is any loss acceptable?</td><td>Producers wait; loss is a policy you can switch on</td><td>The full-buffer rule behind a one-method interface (move 3)</td></tr>'
 '<tr><td>What capacity, and how much faster are the producers?</td><td>A small capacity, producers faster &mdash; so it fills</td><td>Whether back-pressure is visible at all; the numbers in move 8</td></tr>'
 '<tr><td>On shutdown, must queued work be finished, or must we stop this second?</td><td>Both: a drained stop, and a stop-now that hands the backlog back</td><td>Poison pills and the order of the protocol, plus shutdownNow (move 6)</td></tr>'
 '<tr><td>Do we need strict global order, or only order within a key?</td><td>FIFO in the buffer; no promise across producers</td><td>One queue, or one lane per key (moves 5, 12)</td></tr>'
 '<tr><td>How many producers and consumers, and are they threads or a pool?</td><td>A thread each for now; a pool is a follow-up</td><td>Whether the code reads plainly; who owns the threads (move 2)</td></tr>'
 '<tr><td>What happens when processing a task throws?</td><td>Park it in a dead-letter queue and keep going</td><td>A failure rule handed in, not a try/catch buried in the consumer (moves 3, 9)</td></tr>'
 '<tr><td>Am I allowed to use <code>java.util.concurrent</code>, or do you want it hand-built?</td><td>Hand-built buffer, then say what the JDK already gives you</td><td>Whether you write the wait protocol or call <code>ThreadPoolExecutor</code> (moves 8, 12)</td></tr>'
 '<tr><td>One JVM, or is this a real queue between processes?</td><td>One JVM, in memory</td><td>No durability yet; a crash loses the buffer (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One run, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> the buffer is bounded and a full buffer parks the producer, because the '
 'bound is the safety property; the full-buffer rule is handed in, so "never stall" is a one-line change; shutdown '
 'drains &mdash; producers are joined first, then one poison pill per consumer &mdash; and the stop-now variant hands the '
 'backlog back instead of dropping it; every wait is a <code>while</code> loop under the lock, and nothing slow runs '
 'inside it; counters are atomic, not lock-protected. Named as out of scope: durability across a crash, per-key '
 'ordering, batching, a consumer pool &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "PRODUCERS make TASKS; a bounded BUFFER holds them; CONSUMERS take them and do WORK; a PIPELINE starts and stops it all; COUNTERS say it added up", "var(--text)", 12.5)
for x, w, t, sub, acc in [(24, 158, "Task", "id and payload", 0), (196, 176, "Producer", "its own id range", 0),
                          (386, 200, "Handoff (buffer)", "the meeting point", 1), (600, 176, "Consumer", "what it holds now", 0),
                          (790, 176, "Pipeline", "threads, state", 1), (980, 110, "Work rule", "no state", 0),
                          (1104, 106, "POISON", "one value", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a rule, or a single reserved value", "var(--muted)", 11)
m1 += _tx(615, 210, "one noun is not like the others: the buffer is the only place two threads touch the same memory, so it is the only object that needs a lock", "var(--acc)", 11)
MV[1] = _mv(1230, 225, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("make a task", "Producer  (owns its id range and nothing shared)", "new Task(baseId + i, ...)"),
                                       ("decide what a full buffer means", "OverflowPolicy  (owns no state: pure)", "policy.submit(h, t, m, out)"),
                                       ("put it in / take it out", "Handoff  (owns the slots, the lock, the waits)", "h.put(t)  /  h.take()"),
                                       ("start, drain, stop, stop NOW", "Pipeline  (owns the threads and the life cycle)", "start / shutdown / shutdownNow")]):
    y = 20 + k*54
    m2 += _bx(24, y, 300, 44, verb, "the verb") + _ar("M324 %s H384" % (y+22), True)
    m2 += _bx(384, y, 470, 44, cls, "the class whose state it touches", acc=True) + _ar("M854 %s H914" % (y+22), True)
    m2 += _bx(914, y, 292, 44, meth, "the method")
m2 += _tx(615, 254, "the test for a threading problem: a verb that touches memory two threads can see goes to the ONE class that owns that memory", "var(--muted)", 11)
m2 += _tx(615, 274, "everything else -- making a task, doing the work, counting -- stays ordinary single-threaded code, which is why it stays readable", "var(--muted)", 11)
MV[2] = _mv(1230, 288, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(24, 70, 244, 90, "Pipeline", "configure(policy, work, onFailure)", acc=True)
for k, (t, sub, impl) in enumerate([("OverflowPolicy", "what a FULL buffer means", "BlockUntilRoom / DropNewest / DropOldest / TimedBlock"),
                                    ("Work", "what a consumer actually does", "any lambda: resize, index, charge a card"),
                                    ("FailurePolicy", "what a THROWN task means", "DeadLetterSink / BoundedDeadLetters / retry-then-park"),
                                    ("PipelineListener", "who is told, after the fact", "a log line, a metric, a dashboard, a lambda")]):
    y = 16 + k*54
    m3 += _ar("M268 115 H312 V%s H360" % (y+22), True, True) + _bx(360, y, 300, 44, t, sub, dash=True)
    m3 += _bx(720, y, 486, 44, impl, "the classes that can be handed in") + _ar("M720 %s H660" % (y+22))
m3 += _tx(615, 250, "dashed green = handed in. The pipeline never builds a rule, so \"the feed must never stall\" is one new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 270, "and one rule wraps the others: AccountedWork(work) does the exactly-once counting for EVERY work function, including the ones written next year", "var(--acc)", 11)
MV[3] = _mv(1230, 285, m3)

# move 4: the gap, drawn as threads on a time axis
m4 = _D + _tx(24, 32, "two producer threads, one buffer of 8 holding 7, no lock", "var(--text)", 12, "start")
for lab, y in [("producer-1", 56), ("producer-2", 104)]:
    m4 += _tx(24, y+22, lab, "var(--acc)", 11, "start")
    m4 += '<path d="M104 %s H700" stroke="var(--line)" stroke-width="1" stroke-dasharray="2 4"/>' % (y+17)
m4 += _bx(120, 56, 130, 34, "reads count = 7", "")
m4 += _bx(260, 104, 130, 34, "reads count = 7", "")
m4 += _bx(400, 56, 130, 34, "writes slot 7", "count = 8")
m4 += '<g><rect x="540" y="104" width="130" height="34" rx="6" fill="var(--bg3)" stroke="%s" stroke-width="1.4"/><text x="605" y="120" text-anchor="middle" font-size="12.5" fill="%s">writes slot 7</text><text x="605" y="133" text-anchor="middle" font-size="10.5" fill="%s">count = 9</text></g>' % (RED, RED, RED)
m4 += '<path d="M104 158 H700" stroke="var(--line)"/>'
for k, tk in enumerate(["t1", "t2", "t3", "t4"]):
    x = 185 + k*140
    m4 += '<path d="M%s 154 V162" stroke="var(--muted)"/>' % x + _tx(x, 176, tk, "var(--muted)", 10.5)
m4 += '<rect x="104" y="192" width="596" height="66" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(402, 214, "the gap: both threads saw room, so both wrote the same slot.", RED, 11.5)
m4 += _tx(402, 236, "one item is gone for good, and count now says 9 in a buffer of 8.", RED, 11.5)
m4 += _card(730, 40, 480, 170, "the fix: one owner, one lock, two waiting rooms",
            ["the check and the write are ONE step, inside the lock",
             "no room? sleep on notFull -- do not spin, do not retry",
             "a take frees a slot and signals notFull: one producer wakes",
             "an add signals notEmpty: one consumer wakes",
             "the wait is a while loop, because the slot can be gone again",
             "counters stay outside: single increments, so AtomicLong"], acc=True)
m4 += _tx(970, 240, "the lock lives where the shared state lives: inside the hand-off.", "var(--muted)", 11)
m4 += _tx(970, 260, "the pipeline has its own lock, and it guards the life cycle only.", "var(--muted)", 11)
m4 += _tx(24, 306, "the second gap, and the one only threading has: the signal arrives BEFORE the wait", "var(--text)", 12.5, "start")
lw = [("consumer reads: empty", "no lock held, so the answer is stale", 0),
      ("producer adds + signals", "nobody is waiting: the signal is dropped", 1),
      ("consumer calls wait()", "the item is already in the buffer", 0)]
for k, (t, sub, acc) in enumerate(lw):
    x = 24 + k*288
    m4 += _bx(x, 318, 268, 44, t, sub, acc=bool(acc)) + _ar("M%s 340 H%s" % (x+268, x+288), True)
m4 += '<g><rect x="888" y="318" width="268" height="44" rx="6" fill="var(--bg3)" stroke="%s" stroke-width="1.4"/><text x="1022" y="336" text-anchor="middle" font-size="12.5" fill="%s">asleep, with work waiting</text><text x="1022" y="351" text-anchor="middle" font-size="10.5" fill="%s">400 ms burnt; a plain wait() = forever</text></g>' % (RED, RED, RED)
m4 += _tx(615, 382, "that is a LOST WAKEUP. The fix is one line: read the guard and wait while holding the same lock the signaller holds --", "var(--muted)", 11)
m4 += _tx(615, 400, "await() releases the lock and re-takes it as ONE step, so no signal can slip into the gap. Test 11 forces it and measures it.", "var(--acc)", 11)
MV[4] = _mv(1230, 414, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is the next item, oldest first?", "Task[] ring + head, tail, count", "O(1)"),
                                      ("is there room? is there anything?", "one int, count, under the same lock", "O(1)"),
                                      ("who is waiting for a slot, or for work?", "two Conditions: notFull, notEmpty", "O(1) wake, one thread"),
                                      ("how many produced, consumed, dropped?", "one AtomicLong each, no lock at all", "O(1) CAS"),
                                      ("which ids were processed? (the proof)", "AtomicIntegerArray indexed by task id", "O(1)")]):
    y = 18 + k*46
    m5 += _bx(24, y, 350, 38, q, "the question") + _ar("M374 %s H430" % (y+19), True)
    m5 += _bx(430, y, 480, 38, shape, "the shape", acc=True) + _ar("M910 %s H966" % (y+19), True) + _bx(966, y, 240, 38, cost, "")
m5 += _tx(615, 268, "the array IS the bound: a fixed ring never grows and never allocates, so \"bounded memory\" is a property of the shape, not of a check", "var(--muted)", 11)
m5 += _tx(615, 288, "and the two Conditions are a collection too -- each is a queue of sleeping threads, which is why signalling the right one wakes only a thread that can move", "var(--muted)", 11)
MV[5] = _mv(1230, 302, m5)

# move 6: the life cycle, and the shutdown protocol drawn over time
m6 = _D
for k, (t, sub, acc) in enumerate([("NEW", "threads not made", 0), ("RUNNING", "hand-off cycling", 1),
                                   ("DRAINING", "the backlog has not", 1), ("TERMINATED", "buffer empty, threads dead", 0)]):
    x = 24 + k*216
    m6 += _bx(x, 16, 192, 44, t, sub, acc=bool(acc))
    if k < 3: m6 += _ar("M%s 38 H%s" % (x+192, x+216), True)
m6 += _tx(886, 32, "DRAINING is the state people forget.", "var(--muted)", 11, "start")
m6 += _tx(886, 52, "Stopping is not the same as draining.", "var(--muted)", 11, "start")
COLS = ["1  stop flag set", "2  producers JOINED", "3  one pill per consumer", "4  backlog drained", "5  pills taken"]
for k, c in enumerate(COLS):
    m6 += _tx(145 + k*206 + 100, 92, c, "var(--acc)", 11)
grid = [("producer", ["stops making items", "DEAD", "--", "--", "--"], [0, 1, 0, 0, 0]),
        ("buffer", ["4 items", "4 items", "4 items + 2 pills", "2 pills", "empty"], [0, 0, 1, 0, 1]),
        ("consumer-1", ["working", "working", "working", "takes its pill", "ended"], [0, 0, 0, 1, 0]),
        ("consumer-2", ["working", "working", "working", "takes its pill", "ended"], [0, 0, 0, 1, 0])]
for r, (lab, cells, accs) in enumerate(grid):
    y = 106 + r*46
    m6 += _tx(24, y+24, lab, "var(--acc)", 11, "start")
    for k, cell in enumerate(cells):
        m6 += _bx(145 + k*206, y, 200, 38, cell, "", acc=bool(accs[k]))
m6 += _tx(615, 318, "joining the producers BEFORE the pills go in is the whole protocol: that is what makes \"the pill sits behind every real task\" true.", "var(--muted)", 11)
m6 += _tx(615, 338, "swap those two lines and a consumer can stop while work is still arriving. FIFO does the rest: no consumer can reach a pill early.", "var(--muted)", 11)
m6 += _tx(24, 378, "and the other one, shutdownNow(ms), for the caller who cannot wait for the backlog:", "var(--text)", 12.5, "start")
for k, (t, sub) in enumerate([("interrupt every thread", "a parked put or take wakes and ends"),
                              ("join, with the same deadline", "it returns an answer, it never hangs"),
                              ("drain the ring into a list", "one poll(0) at a time until it is empty"),
                              ("hand it back, count discarded", "so the ledger still balances")]):
    x = 24 + k*296
    m6 += _bx(x, 392, 276, 44, t, sub, acc=(k == 3))
    if k < 3: m6 += _ar("M%s 414 H%s" % (x+276, x+296), True)
m6 += _tx(615, 456, "the difference in one line: shutdown(ms) finishes the backlog, shutdownNow(ms) gives it back. Neither one drops it on the floor.", "var(--acc)", 11)
MV[6] = _mv(1230, 470, m6)

# move 7: what is inside the lock, and twenty threads at the same instant
m7 = _D + _card(24, 16, 580, 120, "inside the lock: about 5 nanoseconds",
                ["ring[tail] = t;  tail = (tail + 1) % cap;  count++",
                 "notEmpty.signal()  --  a queue push, not a wake-up",
                 "one put + one take, uncontended: 9-10 ns (the HandoffCost probe)",
                 "no allocation, no logging, no work, no listener, no I/O"], acc=True)
m7 += _ar("M604 76 H660", True) + _tx(632, 66, "unlock", "var(--acc)", 10.5)
m7 += _card(660, 16, 546, 120, "outside the lock: where the time actually goes",
            ["the consumer's work: 1 to 2 milliseconds in the demo",
             "the park / unpark handshake: about 350 ns when it happens",
             "building the Task and tallying the counters",
             "every listener call: after the unlock, inside a try/catch"])
m7 += _tx(615, 164, "twenty threads hit the same hand-off at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 178, 106, 40, "producer %d" % (k+1), "waits %d ns" % (k*5), acc=(k == 9))
    m7 += _bx(x, 226, 106, 40, "consumer %d" % (k+1), "waits %d ns" % (50 + k*5), acc=(k == 9))
m7 += _tx(615, 292, "the twentieth thread waits ninety-five nanoseconds for the lock, and then one to two MILLISECONDS for its own work.", "var(--muted)", 11)
m7 += _tx(615, 312, "so yes, the hand-off is one at a time -- and no, that is not where the time goes. What costs is the park and the wake, not the lock.", "var(--muted)", 11)
m7 += _tx(24, 348, "and the follow-up question: who goes next, and can one producer be starved?", "var(--text)", 12.5, "start")
m7 += _card(24, 362, 580, 118, "who goes next is decided by the Condition, not the lock",
            ["a producer that finds no room parks on notFull",
             "a Condition's wait set is served first-in, first-out",
             "so the parked producers are woken in the order they slept",
             "barging only affects a thread that arrives at lock() itself"], acc=True)
m7 += _card(660, 362, 546, 118, "measured: 4 producers, buffer of 1, a 120 ms window",
            ["default lock: about 7,000 items each -- spread 1.00x, every run",
             "new ReentrantLock(true): 3x, then 31x, once 11,460x -- it SCATTERS",
             "and it pushes a fifth to a third fewer items through",
             "so fairness cost throughput and bought nothing the Condition had not"])
m7 += _tx(615, 500, "so the honest answer to \"is it fair?\" is a measurement, not a boolean: lock fairness governs threads queued at lock(), and these are", "var(--muted)", 11)
m7 += _tx(615, 518, "parked on a Condition -- which is why it bought nothing here and cost throughput. Test 13 asserts the even spread and the price of the fair lock.", "var(--muted)", 11)
MV[7] = _mv(1230, 532, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="16" width="580" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(310, 38, "is one lock a bottleneck? do the arithmetic first", "var(--text)", 12)
for k, l in enumerate(["one put + one take, uncontended: 9-10 ns measured, so ~5 ns per lock trip",
                       "a million items a second = 10 ms of lock in every second = 1% busy",
                       "the 10x10 run: 20,000 items in 31-46 ms = over 400,000 items a second",
                       "and ~1,400 of those puts had to park -- back-pressure, not contention",
                       "the lock is not the bottleneck. The park / unpark handshake is.",
                       "so the first rung of the ladder is not a better lock. It is a bigger buffer."]):
    m8 += _tx(34, 62 + k*26, l, "var(--muted)" if k < 4 else "var(--acc)", 11, "start")
m8 += _tx(905, 38, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1  raise the capacity, and measure",
                               "200k items, 1 producer 1 consumer: cap 1 = 780 ms, cap 16 = 50 ms, cap 1024 = 10 ms"),
                              ("2  batch the hand-off",
                               "drainTo(list, 64): one lock trip for sixty-four items instead of sixty-four trips"),
                              ("3  stop writing it: ThreadPoolExecutor + a bounded queue",
                               "the JDK's queue, pool and rejection handler; past that, two locks, then a lock-free ring")]):
    m8 += _bx(620, 56 + k*54, 586, 46, t, sub, acc=(k == 0))
m8 += _tx(615, 236, "say the arithmetic before you climb: a lock-free ring buffer that nobody measured is complexity somebody else will have to maintain", "var(--muted)", 11)
MV[8] = _mv(1230, 250, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("an item is lost, or done twice", "one lock, wait in a while loop; test 1: 10x10 threads, 20,000 items, each seen exactly once"),
                                ("a check outside the lock loses a wakeup", "read the guard under the lock you signal under; test 11: the broken take burns its whole 400 ms timeout"),
                                ("shutdown throws the backlog away", "join producers, then one pill each; test 3: 400 items, the buffer still full at stop, all 400 done"),
                                ("a stop-now drops what is queued", "hand it back and count it; test 12: 32 items returned, discarded == 32, the ledger balances"),
                                ("an interrupt eats the task in hand", "park it before the thread dies; test 6: the dead-letter holds task#77 and the ledger balances"),
                                ("work throws and the item disappears", "AccountedWork routes it; test 7: 86 done + 14 parked == 100 admitted")]):
    y = 14 + k*38
    m9 += _bx(24, y, 300, 34, bad, "") + _ar("M324 %s H374" % (y+17), True) + _bx(374, y, 832, 34, fix, "", acc=True)
m9 += _tx(615, 264, "four more blocks cover the rest: the bound holds on a capacity of ONE (test 2), a full buffer parks instead of spinning (test 5),", "var(--muted)", 11)
m9 += _tx(615, 282, "both builds of the hand-off pass the same exactly-once check (test 8), and fairness is measured rather than asserted (test 13).", "var(--muted)", 11)
m9 += _tx(615, 308, "thirteen blocks, 1.5 seconds, and it must print ALL PASS -- every wait in the file has a timeout, so a broken pipeline FAILS a check", "var(--acc)", 11)
m9 += _tx(615, 326, "instead of hanging the run. A threading test that can hang is not a test, it is a coin flip.", "var(--acc)", 11)
MV[9] = _mv(1230, 340, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 830)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface OverflowPolicy { boolean submit(h, t, m, out); }", None), ("\"never stall\" is a new class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new AccountedWork(work, metrics, onFailure) wraps EVERY work", None), ("no work function can break the count", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("fanout.onEvent(...) after the unlock, inside a try/catch", None), ("a broken listener is not an outage", None)],
          [("State", "var(--text)"), ("move 6", None), ("NEW -> RUNNING -> DRAINING -> TERMINATED, checked on entry", None), ("start() twice throws instead of forking threads", None)],
          [("Command / sentinel", "var(--text)"), ("move 6", None), ("Task.POISON: one reserved value, compared by ==", None), ("the stop signal queues like any other item", None)],
          [("Producer-Consumer", "var(--text)"), ("move 4", None), ("the whole page: it IS the pattern, and it is a concurrency one", None), ("two speeds, decoupled by one bounded buffer", None)],
          [("Factory", "var(--muted)"), ("not yet", None), ("new LockHandoff(16) at the call site: one line, chosen once", "var(--muted)"), ("it earns the name when the build comes from config", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("never here", None), ("every test builds its own Pipeline; nothing calls getInstance()", "var(--muted)"), ("shared mutable global state in a threaded design", "var(--muted)")]]
m10 = _D + _table(20, 16, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 300, "name a pattern only after the move that produced it; then every name has a one-sentence defence, and the ones you left out have one too", "var(--muted)", 11)
MV[10] = _mv(1230, 314, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 450), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Handoff guards the slots. Producer makes. Consumer does. Pipeline wires and stops.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("DropOldest is a new file; the buffer, producer, consumer and shutdown are untouched", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("moves 3, 8", None), ("the same failure tests pass on both builds of the Handoff; only the trade-off changes", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("OverflowPolicy, Work, FailurePolicy, PipelineListener, Clock: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("configure(policy, work, onFailure) -- which is how a test hands in work that throws", None)]]
m11 = _D + _table(20, 16, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 244, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 258, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "drop oldest, drop newest, a deadline", "a new class behind OverflowPolicy plus one configure line", "", "move 3"),
        ("someone new wants to know", "a dashboard, an alert, autoscaling", "one more listener, called after the unlock; the lock does not change", "", "move 4"),
        ("a new step in a life", "PAUSED, or a stage that stops alone", "one more state and one more checked transition", "", "move 6"),
        ("a new invariant across items", "same key, in order; N at a time", "one lane per key, or a semaphore beside the same lock", "", "moves 4 + 5"),
        ("state that must outlive the process", "a crash must not lose the buffer", "append before the hand-off, ack after the work; unacked items are redelivered,", "so delivery becomes at-least-once and the consumer dedupes by id", "moves 6 + 12")]):
    y = 18 + k*54
    m12 += _bx(24, y, 330, 44, t, sub) + _ar("M354 %s H414" % (y+22), True) + _bx(414, y, 660, 44, fix, sub2, acc=True) + _tx(1140, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 304, "for all five, the hand-off and its wait protocol do not change at all; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 318, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class — and one of them is where two threads meet.",
 "Reading the paragraph again: <b>producers</b> make <b>tasks</b>; a bounded <b>buffer</b> holds them; <b>consumers</b> "
 "take them and do <b>work</b>; a <b>pipeline</b> starts and stops the whole thing; <b>counters</b> say afterwards that "
 "it added up. A task has an id and a payload and never changes, so it is a small final class. A producer owns its own "
 "id range and its own loop; a consumer owns whatever it is holding right now; both hold state, so both are classes. "
 "The buffer holds the slots, how many are used, and the threads asleep waiting on it: a class. The work rule holds no "
 "state at all &mdash; it is a calculation &mdash; so it is an interface. One noun is genuinely different from the rest: "
 "the buffer is the only object two threads touch at the same time, so it is the only one that needs a lock. Writing "
 "that sentence down early is most of the design, because it tells you that everything else stays ordinary code.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Make a task\" touches nothing anyone else can see, so it belongs to the producer. \"Decide what a full buffer "
 "means\" touches no state either &mdash; it reads a situation and returns a decision &mdash; so it belongs to a pure "
 "rule, <code>policy.submit(h, t, m, out)</code>. \"Put it in\" and \"take it out\" touch the slots, the count and the "
 "sleeping threads, all of which live in one object, so they belong to the hand-off: <code>h.put(t)</code> and "
 "<code>h.take()</code>. \"Start, drain, stop\" touches the threads, the life-cycle state and the counters at once, and "
 "only the pipeline sees all three, so <code>shutdown(ms)</code> and <code>shutdownNow(ms)</code> are its methods. The "
 "test for a threading problem is the usual one with a clause added: a verb that touches memory two threads can see "
 "must go to the one class that owns that memory, and nowhere else. Do that and there is exactly one file where "
 "concurrency lives, and one class inside it.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "What a full buffer means will change; it is the first thing they change. What a consumer actually does will change. "
 "What a thrown task means will change. Who gets told will change. So each is a one-method interface the pipeline is "
 "<i>given</i> in <code>configure()</code> and never builds: <code>OverflowPolicy</code>, <code>Work</code>, "
 "<code>FailurePolicy</code>, <code>PipelineListener</code>. This is where the patterns come from, not the other way "
 "round. A swappable rule behind an interface is <b>Strategy</b>, and it is why \"the feed must never stall\" is one new "
 "class and one changed line rather than surgery on tested concurrency code. A rule that wraps another rule and adds to "
 "it is <b>Decorator</b>: <code>AccountedWork</code> wraps whatever work it is handed and does the counting itself, so "
 "an item counts as consumed only after the work returns, and work that throws goes to the failure policy instead of "
 "vanishing. A pipeline that announces \"a producer parked\" without knowing what a dashboard is, is <b>Observer</b>. I "
 "do them; I do not announce them.", 3),
("Move 4: state that many threads change at once gets one owner and one lock — then mind the two gaps.",
 "Two producers reach a buffer of eight that holds seven. Both read the count, both see room, both write slot seven: "
 "one item is gone for good, and the count now says nine in a buffer of eight. The bug is not the write; it is the gap "
 "between checking and acting, and the fix is to make those one step inside a lock held by the object that owns the "
 "slots. Now the part a parking lot never has. When there is genuinely no room, the producer must not spin and must not "
 "retry &mdash; it must sleep, and be woken by whoever makes room. That is a <code>Condition</code>: a queue of "
 "sleeping threads attached to the lock. Two of them, because there are two reasons to sleep: producers on "
 "<code>notFull</code>, consumers on <code>notEmpty</code>. And that opens the <i>second</i> gap, the one only "
 "threading has. If a thread decides \"it is empty\" and then goes to sleep, and the signal arrives in between, the "
 "signal is thrown away: a signal wakes whoever is in the wait set at that instant, and at that instant the wait set "
 "was empty. That is a <b>lost wakeup</b>, and the thread now sleeps on top of work that is already there. The rule "
 "that kills it is one line: read the guard, decide, and wait while holding the same lock the signaller holds &mdash; "
 "<code>await()</code> releases the lock and re-takes it as one step, so nothing can slip into the gap. And the wait is "
 "a <code>while</code> loop, never an <code>if</code>, for the other reason: between the signal and re-acquiring the "
 "lock, another thread can take the slot back, and the JVM is also permitted to wake a waiter for no reason at all (a "
 "<b>spurious wakeup</b>). Counters stay outside all of this: single independent increments, so <code>AtomicLong</code>.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What is the next item, oldest first?\" is a fixed array used as a ring, with a head, a tail and a count: enqueue "
 "and dequeue are three assignments each. \"Is there room? is there anything?\" is that same count, read under the same "
 "lock &mdash; one number, one owner, no second source of truth to drift. \"Who is waiting?\" is a collection too, and "
 "people forget it: each <code>Condition</code> is a queue of sleeping threads, which is exactly why signalling the "
 "right one wakes a thread that can actually move. \"How many produced, consumed, dropped?\" is one "
 "<code>AtomicLong</code> per counter and no lock at all, because each is an independent single increment. And the "
 "proof the design works is a collection as well: an <code>AtomicIntegerArray</code> indexed by task id, so a test can "
 "say every id was seen exactly once. The array is also the bound &mdash; a fixed ring cannot grow, so \"bounded "
 "memory\" is a property of the shape rather than of a check somebody might forget to write.", 5),
("Move 6: the life cycle is the pipeline's, and the order of operations is the whole of both shutdowns.",
 "The pipeline goes NEW, RUNNING, DRAINING, TERMINATED, and DRAINING is the one people forget: producers have stopped, "
 "the backlog has not. Three orders have to be right. First the wait protocol, on every hand-off: take the lock, check "
 "the condition in a <code>while</code> loop, sleep if it does not hold, make the change, signal the <i>other</i> "
 "condition, unlock. Second the drained shutdown, which is where rounds are lost. Set the stop flag, so no producer "
 "starts another item. <i>Join the producers</i> &mdash; after that line nothing can be added, and that is what makes "
 "the next step sound. Now put exactly one poison pill per consumer into the buffer: because the buffer is FIFO, every "
 "pill sits behind every real task, so no consumer can reach one early. Join the consumers; each drains the backlog, "
 "takes exactly one pill and ends. Flip to TERMINATED. Reverse the join and the pills and a consumer can stop while "
 "work is still arriving. Third, the shutdown the interviewer asks for next: stop <i>now</i>. Interrupt every thread, "
 "join them with the same deadline, drain whatever is left in the ring into a list, and hand that list back to the "
 "caller, counting each item <code>discarded</code>. The difference in one sentence: <code>shutdown</code> finishes the "
 "backlog, <code>shutdownNow</code> gives it back, and neither drops it. Every wait in both protocols takes a deadline, "
 "so a shutdown returns with an answer rather than hanging.", 6),
("Move 7: yes, the hand-off happens one at a time. Ask for how long, what is inside the lock, and who goes next.",
 "The question you will be asked, and should ask yourself first: if every item goes through one lock, have you "
 "serialised the whole pipeline? You have, for about five nanoseconds. Inside the lock there is one array write, one "
 "index update, one increment and one signal &mdash; and a signal is a queue push, not a wake-up, so it costs almost "
 "nothing. Measured on JDK 21, an uncontended put and take together are nine to ten nanoseconds; "
 "<code>HandoffCost</code> in <code>Extensions.java</code> is the loop that says so. Everything slow is outside: "
 "the consumer's work (one to two milliseconds in the demo), building the task, and every listener call, which happens "
 "after the unlock inside a try/catch so a broken dashboard cannot stall the pipeline. So when twenty threads arrive at "
 "the same instant, the twentieth waits about ninety-five nanoseconds for the lock &mdash; and then one to two "
 "milliseconds for its own work. Then the follow-up: <i>who goes next, and can a producer starve?</i> Not the lock's "
 "decision, as it turns out. A producer that finds no room parks on <code>notFull</code>, and a Condition's wait set is "
 "served first-in-first-out, so parked producers are woken in the order they fell asleep. Fairness on the lock "
 "(<code>new ReentrantLock(true)</code>) only stops a thread arriving at <code>lock()</code> from barging past a thread "
 "that was already woken. Measure it: four producers pushing through a buffer of one for 120 milliseconds. The "
 "default lock gave each of them about seven thousand items &mdash; a spread of 1.00, on every run. "
 "<code>new ReentrantLock(true)</code> <i>scattered</i> them instead: 3x on a good run, 31x on a bad one, and once "
 "11,460x, when one producer got a single item &mdash; while pushing a fifth to a third fewer items through, because "
 "every hand-over becomes a context switch. So the fair lock did not buy the even counts here. The Condition had "
 "already bought them, and fairness only added a bill. Turn it on when you can show a thread being overtaken at "
 "<code>lock()</code> itself, and say what it costs.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Five nanoseconds inside the lock means a million items a second spends ten milliseconds of every second holding it: "
 "one per cent busy. The ten-by-ten run pushes twenty thousand items through a single lock in thirty to forty-six "
 "milliseconds, and roughly fourteen hundred of those puts had to park &mdash; which tells you the truth straight away: "
 "this pipeline is limited by the park-and-wake handshake, not by the lock. So the first rung is not a cleverer lock. "
 "Raise the capacity and measure &mdash; <code>HandoffCost.ladderMs</code> does exactly this, and <code>ExtDemo</code> "
 "prints it: two hundred thousand items through one producer and one consumer take about 780 milliseconds at capacity "
 "one, 50 at capacity sixteen and 10 at capacity 1024, because a bigger buffer means the two sides "
 "rarely have to meet. Second rung, batch the hand-off: <code>drainTo(list, 64)</code> is one lock trip for sixty-four "
 "items instead of sixty-four trips. Third rung, stop writing it: a <code>ThreadPoolExecutor</code> with a bounded "
 "<code>ArrayBlockingQueue</code> is this entire page, maintained by somebody else. Past that there is "
 "<code>LinkedBlockingQueue</code>, which splits the lock into a put lock and a take lock so producers and consumers "
 "stop colliding, and then a lock-free ring with per-slot sequence numbers, which is what the LMAX Disruptor is. Say "
 "the arithmetic first: a lock-free ring nobody measured is complexity somebody else will have to maintain.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Six failures carry the design, and each has a block in <code>FailureTests.java</code> that would go red if the code "
 "regressed: an item lost or done twice, a wakeup lost because the guard was read outside the lock, a shutdown that "
 "throws the backlog away, a stop-now that drops it instead of handing it back, an interrupt that takes the task in "
 "hand to the grave, and work that throws. Four more blocks cover the bound on a capacity of one, a full buffer parking "
 "instead of spinning, the same exactly-once check on both builds of the hand-off, and fairness measured rather than "
 "asserted. Thirteen blocks, 1.5 seconds, and the page does not build unless they all pass. The rule that makes them "
 "usable: every wait in the file has a timeout. A threading test that can hang is not a test, it is a coin flip &mdash; "
 "so a broken pipeline fails a named check in a second instead of freezing your build for ten minutes.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Strategy is move 3: what a full buffer means is the rule that changes, so it sits behind a one-method interface the "
 "pipeline is handed. Decorator is the same move's wrapper, <code>AccountedWork</code>, which adds the exactly-once "
 "counting to any work function instead of trusting each one to count itself. Observer is move 4's rule that nothing "
 "slow may happen inside the lock, so listeners are called after the unlock and their exceptions are swallowed. State "
 "is move 6: four named states, checked on entry, so calling <code>start()</code> twice throws instead of quietly "
 "forking a second set of threads. The poison pill is a sentinel and, read another way, a Command: the stop instruction "
 "travels through the same queue as the work, which is the only reason it arrives in the right order. And the honest "
 "one: Producer-Consumer <i>is itself</i> a pattern &mdash; a concurrency pattern rather than a Gang-of-Four one &mdash; "
 "and the whole page is it. Factory did not earn a place: the hand-off is built once at a call site, and it earns the "
 "name the day that choice comes from configuration. Singleton earns nothing at all, because every test builds its own "
 "pipeline.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "S: one reason to change per class, which move 2 gave you &mdash; the hand-off guards the slots, the producer makes, "
 "the consumer does, the pipeline wires and stops, and nobody does two of those. O: a new overflow behaviour is a new "
 "file and one changed line, never an edit to tested concurrency code. L: the strongest evidence on this page is that "
 "the same failure tests pass on both builds of the hand-off &mdash; the lock with two Conditions in "
 "<code>Main.java</code> and the JDK's own queue in <code>Extensions.java</code> &mdash; "
 "so only the trade-off changes, never the correctness. I: five interfaces with one method each, so a fake for a test "
 "is a lambda. D: the pipeline depends on interfaces and is handed the implementations, which is precisely why a test "
 "can hand it work that throws on every seventh task and then check that not one of the hundred items disappeared.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (drop the newest, evict the oldest, give up after eighty milliseconds) is a new class behind "
 "<code>OverflowPolicy</code> plus one line in configure. Someone new who wants to know (a dashboard, an alert, an "
 "autoscaler reading the depth) is one more listener called after the unlock. A new step in a life (PAUSED, or a stage "
 "that stops on its own) is one more state and one more checked transition. A new invariant across items (same key in "
 "order, or at most N in flight) is one lane per key or a semaphore beside the same lock. And state that must outlive "
 "the process is the real one: append the item to a log <i>before</i> handing it over, ack it <i>after</i> the work "
 "succeeds, and redeliver whatever is unacked at restart &mdash; which makes delivery at-least-once rather than "
 "exactly-once, so the consumer has to dedupe by task id. That is the same idempotency key a payment system uses, and "
 "it is the honest answer to \"is this Kafka?\": no, and here is the seam where it would become one. For all five, the "
 "hand-off and its wait protocol do not change at all. Page 05 has the code for each.", 12),
]

DERIVATION_LEAD = ("The same twelve moves as every other page, but on a threading problem three of them carry the "
 "round: move 4 becomes a wait protocol rather than just a lock, move 6 becomes three orders &mdash; the order inside "
 "the hand-off and the order of each of the two shutdowns &mdash; and move 7 has to answer who goes next. The buffer "
 "itself gets one build here; the sibling page, Bounded Blocking Queue, is where it is built four ways. Nothing is "
 "chosen up front, and nothing is named before the move that produced it.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the values, the clock, the listener, the counters
put("task", 10, 16, 240, "Task", ["id: int", "payload: String", "POISON: Task  (the sentinel)"], [])
put("clock", 10, 120, 240, "Clock", [], ["nowMs(): long"], "interface")
put("listener", 10, 200, 240, "PipelineListener", [], ["onEvent(event, detail)"], "interface")
put("metrics", 10, 282, 240, "Metrics",
    ["produced / admitted / dropped", "evicted / abandoned / consumed", "failed / deadLettered",
     "discarded / backpressured", "blockedNanos / inFlight", "maxDepth / pillsTaken"],
    ["observeDepth(d)", "snapshot(depth)"])
put("snap", 10, 466, 240, "MetricsSnapshot", ["fourteen counters, one reading"], ["balanced(): boolean"])
# centre column: the aggregate root and the two roles
put("pipeline", 288, 16, 346, "Pipeline",
    ["handoff: Handoff", "metrics: Metrics", "lock: ReentrantLock (life cycle)", "state: PipelineState",
     "gate: CountDownLatch", "stopped: AtomicBoolean", "producerThreads / consumerThreads", "policy / work / onFailure / clock"],
    ["configure(policy, work, onFailure)", "addListener(l) / setClock(c)", "start(producers, each, consumers)",
     "awaitProducers(ms): boolean", "shutdown(ms): boolean", "shutdownNow(ms): List&lt;Task&gt;",
     "stats(): MetricsSnapshot", "state() / allThreadsDead()"])
put("producer", 288, 334, 346, "Producer", ["name / baseId / count", "policy, metrics, listener", "stopped, gate"],
    ["run(): make, submit, count"])
put("consumer", 288, 452, 346, "Consumer", ["handoff, work, metrics", "onFailure, gate", "inHand: Task"],
    ["run(): take, stop on POISON,", "  process, count, park on interrupt"])
put("accounted", 288, 600, 346, "AccountedWork", ["base: Work  (wrapped)"], ["process(t): count AFTER it returns"])
# third column: the hand-off and its two builds
put("handoff", 672, 16, 302, "Handoff", [],
    ["put(t)", "put(t, timeoutMs): boolean", "offer(t): boolean", "take(): Task", "poll(timeoutMs): Task",
     "putEvictingOldest(t): Task", "size() / capacity()", "name(): String"], "interface")
put("lockh", 672, 210, 302, "LockHandoff",
    ["ring: Task[]   (the bound)", "head / tail / count: int", "lock: ReentrantLock(fair?)", "notFull / notEmpty: Condition"],
    ["put: while full -> notFull.await()", "take: while empty -> notEmpty.await()", "then signal the OTHER condition"])
put("juc", 672, 396, 302, "JucHandoff", ["q: ArrayBlockingQueue"],
    ["the JDK's build of the same idea:", "  same ring, same lock,", "  same two Conditions"], "extension")
put("state", 672, 520, 302, "PipelineState", ["NEW, RUNNING,", "DRAINING, TERMINATED"], [], "enum")
# fourth column: the rules handed in
put("policy", 1002, 16, 218, "OverflowPolicy", [], ["submit(h, t, m, out)", "  : boolean"], "interface")
put("block", 1002, 112, 218, "BlockUntilRoom", [], ["offer, else park on notFull", "and count the park"])
put("drop", 1002, 208, 218, "DropNewest | DropOldest", [], ["shed on arrival, or", "evict the oldest"], "extension")
put("work", 1002, 306, 218, "Work", [], ["process(t)"], "interface")
put("fail", 1002, 388, 218, "FailurePolicy", [], ["onFailed(t, cause, m)"], "interface")
put("sink", 1002, 470, 218, "DeadLetterSink", ["parked: Queue&lt;Task&gt;"], ["park it, never lose it"])

EDGES = [
 # both builds implement the hand-off
 ln(B["lockh"]["t"], B["handoff"]["b"], "inherit"),
 ln((960, 396), (960, 194), "inherit", "", [(990, 396), (990, 194)]),
 # the policies and the rules
 ln(B["block"]["t"], B["policy"]["b"], "inherit"),
 ln((1002, 230), (1002, 62), "inherit", "", [(986, 230), (986, 62)]),
 ln(B["sink"]["t"], B["fail"]["b"], "inherit"),
 ln(B["accounted"]["r"], B["work"]["l"], "inherit", "", [(986, 637), (986, 333)]),
 # the pipeline owns the hand-off, the threads and the counters
 ln(B["pipeline"]["r"], B["handoff"]["l"], "compose"),
 ln(B["pipeline"]["b"], B["producer"]["t"], "compose"),
 _tx(474, 328, "runs", "var(--muted)", 10.5, "start"),
 ln((288, 200), (288, 474), "compose", "", [(272, 200), (272, 474)]),
 ln((634, 160), (672, 550), "assoc", "", [(650, 160), (650, 550)]),
 ln(B["pipeline"]["l"], (250, 340), "compose", "", [(268, 100), (268, 340)]),
 # the rules are handed in through configure()
 ln((634, 60), (1002, 40), "inject", "", [(994, 60), (994, 40)]),
 ln((634, 80), (1002, 330), "inject", "", [(982, 80), (982, 330)]),
 ln((634, 100), (1002, 412), "inject", "", [(970, 100), (970, 412)]),
 _tx(960, 126, "the rules, handed in", "var(--acc)", 10.5, "end"),
 ln((288, 60), (250, 224), "notify", "", [(266, 60), (266, 224)]),
 ln((288, 120), (250, 144), "inject", "", [(274, 120), (274, 144)]),
 # the roles talk to the hand-off and carry tasks
 ln(B["producer"]["r"], (672, 150), "assoc"),
 ln(B["consumer"]["r"], (672, 170), "assoc", "", [(654, 500), (654, 170)]),
 ln(B["consumer"]["l"], (250, 60), "assoc", "", [(270, 500), (270, 60)]),
 ln(B["accounted"]["l"], (250, 360), "assoc", "", [(262, 622), (262, 360)]),
]
# the waiting parties: who is asleep, and where
band = _tx(615, 712, "who is asleep, and where: two waiting rooms inside one lock", "var(--text)", 12)
for k in range(3):
    band += _bx(20 + k*108, 726, 100, 44, "producer-%d" % k, "")
band += _ar("M336 748 H366", True)
band += _bx(370, 726, 180, 44, "notFull", "asleep while full", dash=True, acc=True)
band += _ar("M550 748 H580", True)
band += _bx(580, 726, 200, 44, "the ring, one lock", "count / capacity", acc=True)
band += _ar("M780 748 H810", True)
band += _bx(810, 726, 180, 44, "notEmpty", "asleep while empty", dash=True, acc=True)
band += _ar("M990 748 H1020", True)
for k in range(2):
    band += _bx(1020 + k*102, 726, 95, 44, "consumer-%d" % k, "")
band += _tx(615, 792, "a producer that finds the buffer full does not spin: it sleeps on notFull. A take frees a slot and signals notFull, waking exactly one producer.", "var(--muted)", 11)
band += _tx(615, 810, "an add signals notEmpty and wakes exactly one consumer. Two rooms, so a wake-up never goes to a thread that cannot move.", "var(--muted)", 11)
EDGES.append(band)
UMLSVG = uml_svg(1230, 860, EDGES, legend_y=838)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values; &laquo;extension&raquo; = the class lives in Extensions.java, so it is the answer to a follow-up '
 'rather than part of the core file). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> '
 'Hollow triangle = implements, and there are two of them into <code>Handoff</code> because the hand-off is built '
 'twice: the lock with two Conditions here, and the JDK\'s own queue as a follow-up. Filled '
 'diamond = owns: the pipeline owns the buffer, the threads and the counters. Plain arrow = references: a producer '
 'calls <code>put</code>, a consumer calls <code>take</code>, and both carry Tasks. Dashed green = handed in through '
 '<code>configure()</code>. Dotted blue = notifies, after the unlock. <b>Where state lives:</b> all shared mutable '
 'state is in one class, <code>LockHandoff</code> &mdash; the array, the three integers and the two Conditions &mdash; '
 'and that is the only object with a lock on the hot path. The pipeline has a second lock, but it guards the life cycle '
 'only and is never taken while an item moves. The counters are atomic and take no lock at all, because each is an '
 'independent single increment. <b>The band at the bottom</b> is the part a class diagram normally hides: the two '
 'queues of sleeping threads. A producer that finds no room sleeps on <code>notFull</code>; a consumer that finds '
 'nothing sleeps on <code>notEmpty</code>; every change signals the <i>other</i> room, so a wake-up always goes to a '
 'thread that can actually make progress. Notice what is <i>not</i> here: no Scheduler, because the JVM is the '
 'scheduler, and no stop flag on the consumer, because the stop signal travels through the buffer as a Task.')

# ============================================================ page 04: the code
CODE_INTRO = ('The green comment above each class and method says what it does and what it guarantees; read only those '
 'first for the shape, then the bodies. Main.java is the whole system and compiles on its own; Extensions.java holds '
 'the reference code for every follow-up on page 05 (plus an <code>ExtDemo</code> main that runs all of it); '
 'it also prints the two timings quoted in moves 7 and 8, so the arithmetic on this page is something you can re-run. '
 'FailureTests.java proves thirteen claims in about 1.5 seconds, every wait in it bounded by a timeout. Each copy '
 'button copies that whole file. <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java '
 'FailureTests</code> prints ALL PASS.')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (what happens when it is full, and must a shutdown drain, '
 'are the first two); then type in the order of Main.java: Task with its POISON sentinel, the Clock / Work / '
 'FailurePolicy / PipelineListener interfaces, the Handoff interface, then LockHandoff with its ring, its lock and its '
 'two Conditions &mdash; get put and take right before anything else, and say the while-loop rule out loud as you write '
 'it. Then Metrics and the snapshot, OverflowPolicy with BlockUntilRoom, AccountedWork, DeadLetterSink, Producer, '
 'Consumer, PipelineState, and Pipeline with start, awaitProducers, the five-step shutdown and shutdownNow. Finish with '
 'a main that runs ten producers against ten consumers and prints that every id was seen exactly once.</div></div>')

FU = [
("Mid-round: the source is a live market feed and must never stall. Shed load instead of blocking.", "twist", 8,
 "The full-buffer decision is already one method behind an interface, so this is a new class and one changed line at "
 "the call site: the buffer, the producer, the consumer and both shutdowns are untouched. <code>DropNewest</code> "
 "throws the arriving item away and returns false, which the producer already counts as a drop. <code>DropOldest</code> "
 "keeps the freshest window instead, evicting the head and adding the newcomer as one step under the lock, so the bound "
 "is never exceeded even for an instant. <code>TimedBlock</code> is the middle answer: wait, but only for eighty "
 "milliseconds, using <code>awaitNanos</code> so a spurious wake-up cannot silently extend the deadline. Say one thing "
 "out loud: a dropped item and an evicted item are different losses, and the counters keep them apart, or the ledger "
 "stops adding up.",
 X("shed load instead of stalling", "a task that keeps failing")),
("Ten producers and ten consumers. Prove nothing is lost and nothing is done twice.", "non-functional", 10,
 "The proof is an array, not an eyeball. Twenty thousand tasks carry ids 0 to 19,999, the work increments "
 "<code>seen[id]</code> in an <code>AtomicIntegerArray</code>, and after a clean shutdown every entry must be exactly "
 "one &mdash; a zero is a lost item, a two is a double delivery, and the test reports both counts separately. The "
 "threads are released together: the pipeline holds all twenty on one <code>CountDownLatch</code> and opens it only "
 "once every thread exists, so the race is real on every run rather than a matter of scheduling luck. The second half "
 "of the proof is the ledger: produced equals admitted plus dropped plus abandoned, and admitted equals consumed plus "
 "dead-lettered plus evicted plus handed back by a stop-now plus what is still in the buffer plus what is still in a "
 "consumer's hand. There is no sixth place an item can be, so if both lines hold, nothing was lost. They are exact at "
 "rest, which is why the test asserts them after shutdown and not during.",
 T("// 1. ten producers and ten consumers", "// 2. the bound is the safety property")),
("How does it shut down? Show me that nothing is left in the buffer and no thread is left alive.", "functional", 10,
 "Five steps, and the order is the whole answer. Flip the state to DRAINING and set the stop flag so no producer starts "
 "another item. Join the producers &mdash; after that line nothing can be added, which is what makes the next step "
 "sound. Put exactly one poison pill per consumer into the buffer; because the buffer is FIFO, every pill sits behind "
 "every real task, so no consumer can reach one early. Join the consumers: each drains the backlog, takes exactly one "
 "pill and ends. Flip to TERMINATED. Every wait carries a deadline, so shutdown returns false rather than hanging. The "
 "test proves it with numbers: the buffer is still full when the drain starts, all four hundred items are "
 "processed, the depth is zero, both pills were taken, and no thread is alive.",
 sect(src, "boolean shutdown(long timeoutMs)", "    /**\n     * The other shutdown")),
("Now stop it this second — the caller cannot wait for the backlog. What happens to the queued work?", "functional", 8,
 "It is handed back, not dropped. <code>shutdownNow(ms)</code> starts the same way &mdash; DRAINING, stop flag &mdash; "
 "then interrupts every thread instead of queueing pills, joins them with the same deadline, drains whatever is left in "
 "the ring into a list, and returns that list to the caller. Each of those items is counted "
 "<code>discarded</code>, which is why the ledger still balances afterwards: they were not lost, they changed owner. An "
 "item a consumer was already holding is not in the list &mdash; the interrupt sends that one to the failure policy "
 "instead, so it is in the dead-letter queue. The test starts two producers on ten thousand items each, stops after "
 "forty milliseconds, and then checks the arithmetic on a run where every column is non-zero &mdash; one run printed "
 "62 admitted = 28 done + 2 dead-lettered + 32 handed back. The columns move every time you run it, which is the point: "
 "the test asserts the equation, never the numbers. This is exactly what <code>ExecutorService.shutdownNow()</code> "
 "does, and now you know why it returns a <code>List</code>.",
 sect(src, "List<Task> shutdownNow(long timeoutMs)", "    /** A reading of the counters")),
("Why a poison pill and not a volatile stop flag? Show me the difference.", "design", 8,
 "A pill travels in-band, so FIFO ordering does the reasoning for you: it sits behind every real task, and a consumer "
 "physically cannot see it until it has processed everything ahead of it. A flag is out of band, so a consumer can see "
 "it while items are still queued and simply walk away &mdash; the test measures exactly that, and the naive version "
 "strands all forty items. A flag can be made correct, and the draining version here is the honest one: the flag must "
 "mean \"every producer has been joined\", and a consumer exits only when the flag is set AND a timed poll comes back "
 "empty. That costs one poll timeout of latency on the way out and needs no pill counting, which is what you want when "
 "the consumer count is dynamic. Two costs of pills are worth saying before they are asked: you must know how many "
 "consumers there are, and a consumer that dies early leaves its pill sitting in the buffer. And FIFO is load-bearing "
 "&mdash; the day somebody swaps the ring for a priority queue, the pill must be forced to sort last or the consumers "
 "stop with work still queued behind them.",
 X("the other shutdown", "the lost wakeup")),
("A consumer is asleep and the buffer is not empty. How did that happen?", "design", 8,
 "Somebody read the guard outside the lock. A signal wakes whoever is in the wait set <i>at that instant</i>; if the "
 "thread has decided \"it is empty\" but has not yet called <code>wait()</code>, the wait set is empty, the signal is "
 "thrown away, and the thread then sleeps on top of an item that is already there. That is a lost wakeup: with a plain "
 "<code>wait()</code> it sleeps forever, and with <code>wait(400)</code> it burns the whole timeout &mdash; which is "
 "what the test measures, forcing the interleaving with two latches so the bug shows up on every run instead of at "
 "3 a.m. The fix is one line: read the guard, decide, and wait while holding the same lock the signaller holds, because "
 "<code>await()</code> releases the lock and re-takes it as a single step. Separately, the wait must be a "
 "<code>while</code> loop and never an <code>if</code>, for two reasons: another thread can take the slot back between "
 "the signal and your re-acquisition, and the JVM is allowed to wake a waiter for no reason at all &mdash; a spurious "
 "wakeup. The loop re-checks and goes back to sleep, so neither one can turn into a bug. One more sentence if they "
 "push: with <code>synchronized</code> there is a single wait set, so <code>notify()</code> can wake a producer when "
 "only a consumer could have moved &mdash; you must call <code>notifyAll()</code> and pay for the herd. Two Conditions "
 "exist so a signal can be aimed.",
 X("the lost wakeup", "what java.util.concurrent already gives you") + "\n"
 + T("// 11. the lost wakeup", "// 12. the OTHER shutdown")),
("One of my producers is never getting in. Is your lock fair?", "non-functional", 5,
 "Answer it with a measurement, not a boolean. Who goes next is decided by the <code>Condition</code>, not by the lock: "
 "a producer that finds no room parks on <code>notFull</code>, and a Condition's wait set is served first-in-first-out, "
 "so parked producers are woken in the order they fell asleep. Lock fairness only stops a thread arriving at "
 "<code>lock()</code> from barging past one that was already woken. The probe runs four producers through a buffer of "
 "one for 120 milliseconds. The default unfair lock gave each producer about seven thousand items, a spread of 1.00 on "
 "every run. Then the part worth saying out loud, because it is the opposite of the textbook answer: "
 "<code>new ReentrantLock(true)</code> made it <i>worse</i> &mdash; 3x on a good run, 31x on a bad one, once 11,460x "
 "when one producer got a single item &mdash; and pushed a fifth to a third fewer items through, because every "
 "hand-over becomes a context switch. The reason is the one above: these producers are parked on a Condition, not "
 "queued at <code>lock()</code>, so lock fairness never touches them. It buys neither the invariant nor, here, the "
 "spread. The starvation that does bite a pipeline is a different one: head-of-line blocking, where one slow key or "
 "one slow lane holds up everything behind it &mdash; and that is fixed with lanes, not with a fair lock.",
 X("fairness and starvation", "batching") + "\n" + T("// 13. fairness and starvation", '        System.out.println("elapsed')),
("A consumer throws on one task. Where does that task go, and do your numbers still add up?", "functional", 5,
 "Nowhere silently. The pipeline wraps whatever work it was handed in <code>AccountedWork</code>, which is the only "
 "place counting happens: the item counts as consumed only after the work returns, and a RuntimeException is caught and "
 "handed to the failure policy, which parks it in a dead-letter queue and counts it there. So consumed plus "
 "dead-lettered equals admitted, and the test proves it with work that throws on every seventh id: 86 done plus 14 "
 "parked equals 100. The same wrapper handles the nastier case &mdash; an interrupt arriving while a consumer holds a "
 "task &mdash; by parking what is in hand before the thread ends. Retrying is a decorator on top: "
 "<code>RetryingWork</code> tries N times and lets the last failure escape, so the dead-letter path stays the single "
 "exit.",
 sect(src, "final class AccountedWork", "/** The default failure policy") + "\n"
 + X("a task that keeps failing", "the other shutdown")),
("One lock for the whole hand-off. Does that scale, and would you ship this or use java.util.concurrent?", "non-functional", 10,
 "It scales, and the answer is arithmetic rather than opinion. Inside the lock there is one array write, one index "
 "update, one increment and one signal; an uncontended put and take together measure nine to ten nanoseconds on JDK 21 "
 "(the <code>HandoffCost</code> probe in Extensions.java is the loop), so the critical section is about five. A million items a second holds the lock ten milliseconds in every second: one per "
 "cent busy. The ten-by-ten run pushes twenty thousand items through in thirty to forty-six milliseconds and parks roughly "
 "fourteen hundred times, which is the real finding &mdash; the cost is the park-and-wake handshake, not the lock. So "
 "the ladder starts with capacity, not cleverness: two hundred thousand items through one producer and one consumer take "
 "about 780 ms at capacity one, 50 ms at sixteen and 10 ms at 1024. Then batching, one lock trip for sixty-four items. Then "
 "the honest answer to the second half of the question: no, I would not ship the hand-built one. A "
 "<code>ThreadPoolExecutor</code> with a bounded <code>ArrayBlockingQueue</code> is this entire page in fifteen lines "
 "&mdash; the queue is the hand-off, the pool threads are the consumers, and the <code>RejectedExecutionHandler</code> "
 "is the OverflowPolicy: <code>AbortPolicy</code> throws, <code>DiscardPolicy</code> is DropNewest, "
 "<code>DiscardOldestPolicy</code> is DropOldest, and <code>CallerRunsPolicy</code> is back-pressure, because the "
 "submitting thread has to run the task itself and stops producing while it does. <code>shutdown()</code> plus "
 "<code>awaitTermination()</code> is the drained stop and <code>shutdownNow()</code> is the stop-now. What the JDK does "
 "not give you is the ledger: no exactly-once counters, no dead-letter queue, no depth metric. That part you still "
 "write, and it is the part this page is about.",
 sect(ext, "final class JdkPipeline", "// ---- ext: fairness") + "\n" + X("batching", "order per key")),
("Tasks for the same account must be processed in order. And now there are three stages.", "twist", 8,
 "One buffer with many consumers gives no per-key ordering at all, so route by a hash of the key into N lanes with one "
 "consumer per lane: same key, same lane, same consumer, therefore same order, and no global lock. The price is "
 "head-of-line blocking, since one slow key stalls its whole lane. Stages are the other direction: a consumer of one "
 "buffer is the producer of the next, and the property that matters is that back-pressure composes &mdash; if the last "
 "buffer fills, its stage slows, which fills the buffer feeding it, which slows the stage before it, all the way back "
 "to the source. Every stage stays bounded with no coordination between them. The pill travels too: a stage that takes "
 "POISON passes one on before it exits, so one injection stops the whole chain in order.",
 X("order per key", "many stages") + "\n" + X("many stages", "scale the consumers")),
("Is it actually keeping up? Answer that in O(1), without stopping anything.", "non-functional", 5,
 "Back-pressure is invisible without numbers, so the counters are a product feature, not debug code. Depth, produced, "
 "admitted, consumed, dropped, park events and total blocked time are atomic longs read without a lock, and one "
 "immutable snapshot gives a monitor a consistent line to print. Two derived numbers earn their place: items per second "
 "since the last sample, and how much time producers spent parked &mdash; that second one is the honest measure of "
 "whether the consumers are behind. Sustained high depth says add consumers, sustained zero depth says you "
 "over-provisioned, and that is exactly the signal an autoscaler uses. It is also the same signal as Kafka consumer "
 "lag, which is a good sentence to say out loud: depth is lag, measured in one JVM.",
 X("the monitoring surface", "beyond one JVM") + "\n" + X("scale the consumers", "the monitoring surface")),
("Persist it. A crash must not lose the buffer, and now there are two processes.", "twist", 5,
 "Then it is not a bounded buffer any more, and the honest answer starts by saying so: everything on this page lives in "
 "one JVM and a crash loses whatever is in the ring. The smallest seam that fixes it is a decorator on the hand-off: "
 "append the item to a log <i>before</i> handing it over, ack it <i>after</i> the work has succeeded, and redeliver "
 "whatever is unacked at restart. That turns delivery into at-least-once rather than exactly-once, so the consumer has "
 "to record the ids it has finished and skip duplicates &mdash; the same idempotency key a payment system uses. Across "
 "two processes the lock and the Conditions become somebody else's problem: Kafka, SQS or RabbitMQ, where the buffer "
 "depth you have been measuring is called consumer lag and the back-pressure you built by blocking is called flow "
 "control.",
 X("beyond one JVM", "Runs every extension")),
("Where does time come from, what does an interrupt mean, and how do you test a wait without making the test flaky?", "design", 5,
 "Time comes from an injected <code>Clock</code>, and the pipeline uses it only for deadlines and stamps &mdash; which "
 "is the honest limit worth stating: you cannot fake the clock a wait actually sleeps on, because the parking is done "
 "by the JVM. An interrupt has one meaning here: you own whatever you are holding, so clean it up. A consumer "
 "interrupted with a task in hand parks that task in the dead-letter queue, restores the interrupt flag with "
 "<code>Thread.currentThread().interrupt()</code> and ends; a producer interrupted mid-put counts the item abandoned so "
 "the ledger still closes. Never swallow it, and never keep working after it. So threading tests are written with "
 "latches and bounded timeouts instead of sleeps: to prove a full buffer parks a producer, the test starts one, waits "
 "until its thread state is WAITING, then asserts a latch has NOT counted down within 200 ms; to prove one take "
 "releases it, the same latch must count down within three seconds. Every wait in the file has a bound, so a broken "
 "pipeline fails a check rather than hanging the run.",
 sect(src, "final class Consumer implements Runnable", "/** The pipeline's life.") + "\n"
 + T("// 5. back-pressure, measured", "// 6. an interrupt is not a shutdown protocol")),
("Which pattern is where, which SOLID letter is where, and what did NOT earn a place?", "design", 8,
 "None of them was chosen up front. Strategy is move 3: what a full buffer means is the rule that changes, so it sits "
 "behind a one-method interface handed in through configure. Decorator is the same move's wrapper, AccountedWork, which "
 "adds the exactly-once counting to any work function. Observer is move 4's rule that nothing slow runs inside the "
 "lock, so listeners are called after the unlock inside a try/catch. State is move 6, four named states checked on "
 "entry. The poison pill is a sentinel and, read another way, a Command. For SOLID: S is move 2, one owner per piece of "
 "state; O is DropOldest, a new file and one line; L is the strongest evidence on the page, because the same tests pass "
 "on both builds of the hand-off; I is five interfaces with one method each; D is configure(), which is why a test "
 "can hand in work that throws. Factory did not earn a place, and Singleton earns nothing at all: every test builds its "
 "own pipeline, which is exactly what a shared global would take away.",
 "// Strategy: the rule that changes, behind one method, handed in\n"
 "interface OverflowPolicy { boolean submit(Handoff h, Task t, Metrics m, PipelineListener out) throws InterruptedException; }\n"
 "pipeline.configure(new DropOldest(), work, new DeadLetterSink());   // \"never stall\" = one changed line\n\n"
 "// Decorator: the exactly-once count belongs to the pipeline, not to the work it was handed\n"
 "Work counted = new AccountedWork(work, metrics, onFailure);\n\n"
 "// Observer: announced after the unlock, and a broken listener is swallowed\n"
 "for (PipelineListener l : listeners) try { l.onEvent(event, detail); } catch (RuntimeException ignored) { }\n\n"
 "// State: four named states, checked on entry, so start() twice throws instead of forking more threads\n"
 "enum PipelineState { NEW, RUNNING, DRAINING, TERMINATED }\n\n"
 "// Sentinel / Command: the stop instruction travels through the same queue as the work\n"
 "static final Task POISON = new Task(-1, \"poison\");\n"
 "if (inHand == Task.POISON) { m.pillsTaken.incrementAndGet(); return; }   // identity, never equals\n\n"
 "// Factory: not yet. One line at the call site, chosen once\n"
 "Handoff h = new LockHandoff(16);   // or new LockHandoff(16, true) for a fair lock\n\n"
 "// Singleton: never. Every test builds its own pipeline, which is the point\n"
 "Pipeline p = new Pipeline(new LockHandoff(16));\n"),
]

build(dict(
    slug="mt-producer-consumer", title="Producer-Consumer",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 13 failure tests and a 10x10 exactly-once race pass",
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
