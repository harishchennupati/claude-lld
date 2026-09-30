# Bounded Blocking Queue LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"mt-blocking-queue/Main.java").read_text()
ext   = (H/"mt-blocking-queue/Extensions.java").read_text()
tests = (H/"mt-blocking-queue/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+220])
    j = next(m for m in marks if m > i and b in ext[m:m+220])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
# what the code must do: put and take, each with its wait
pf = _D
rows = [("put", 20, 104, [("an item arrives", "from any producer thread"),
                         ("take the lock", "interruptibly"),
                         ("is there room?", "count &lt; capacity"),
                         ("copy it in, count + 1", "then signal ONE consumer"),
                         ("unlock, then listeners", "never inside the lock")],
         "full: park on notFull &mdash; the lock is released"),
        ("take", 185, 269, [("a consumer asks", "from any consumer thread"),
                            ("take the lock", "interruptibly"),
                            ("is there an item?", "count &gt; 0"),
                            ("take the head, count - 1", "then signal ONE producer"),
                            ("unlock, return it", "listeners after")],
         "empty: park on notEmpty &mdash; the lock is released")]
for lab, y, wy, boxes, wait in rows:
    pf += _tx(88, y + 31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k*220
        pf += _bx(x, y, 195, 54, b[0], b[1], acc=(k == 2))
        if k < 4: pf += _ar("M%s %s H%s" % (x+195, y+27, x+220), True)
    pf += _ar("M640 %s V%s" % (y+54, wy), dash=True) + _bx(560, wy, 350, 34, wait, "", dash=True)
    pf += _ar("M760 %s V%s" % (wy, y+58), True)
    pf += _tx(632, wy-11, "full" if lab == "put" else "empty", "var(--muted)", 10, "end")
    pf += _tx(770, wy-11, "woken &rarr; check again", "var(--acc)", 10, "start")
pf += _tx(735, 160, 'a wake only means "look again", never "the slot is yours" &mdash; so the check is a while loop, not an if', "var(--muted)", 11)
pf += _tx(88, 335, "read", "var(--acc)", 13)
pf += _tx(150, 335, "at any moment, from any thread: how many items are in it, and how much room is left &mdash; one lock, one consistent number", "var(--text)", 12, "start")
pf += _tx(615, 365, "0 &le; count &le; capacity at every instant, FIFO order, every item delivered exactly once &mdash; with ten producers and ten consumers running flat out", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 380, pf)

# one run, replayed -- the numbers are the ones Main.java prints
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("t = 0 ms   eight threads start", ["4 producers, 4 consumers, cap 64", "one latch releases them together",
                                          "the ring is empty: consumers park"], False),
      ("t = 0-42 ms   100,000 items", ["the ring never holds more than 64", "about 1 handoff in 10 parked a thread",
                                       "the other nine in ten never blocked"], True),
      ("t = 42 ms   producers done", ["close(): signalAll, both sides", "every parked consumer re-checks",
                                      "they drain, then see null"], False),
      ("t = 42 ms   the count", ["delivered 100,000, lost 0", "duplicates 0, final size 0",
                                 "peak size 64 of 64: the bound held"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li><code>put(item)</code> appends at the tail and blocks while the queue is full; <code>take()</code> removes from the head and blocks while it is empty.</li>
<li>Timed <code>offer</code> and <code>poll</code> wait only up to a deadline, then give up with <code>false</code> / <code>null</code>.</li>
<li>Capacity is fixed at construction. Items are never null, so a <code>null</code> answer unambiguously means "nothing".</li>
<li>What "full" means is itself a rule: block by default, or drop the oldest, or refuse loudly.</li>
<li><code>size()</code> and <code>remainingCapacity()</code> are consistent snapshots; <code>drainTo</code> moves a batch in one go.</li>
<li><code>close()</code> stops new work, wakes everybody parked, and lets consumers drain before end-of-stream.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Every item delivered exactly once, in FIFO order, with any number of threads on either side.</li>
<li>0 &le; size &le; capacity at every instant: never an overwrite, never a read of an empty slot.</li>
<li>No busy-waiting: a waiting thread parks and burns no CPU until somebody signals it.</li>
<li>put, take, offer, poll and size are O(1); memory is exactly capacity slots and never grows.</li>
<li>A blocked caller can be cancelled, and a failure anywhere leaves the queue exactly as it was.</li>
<li>The rules &mdash; what full means, how items are stored, where time comes from, who is told &mdash; swap without touching the lock.</li>
<li>One JVM, in memory, not durable (say it; a follow-up adds the log).</li></ul></div></div>
'''

PROMPT = ('"Write me a bounded blocking queue. Fixed capacity, many producer threads, many consumer threads. '
          '<code>put</code> blocks when it is full, <code>take</code> blocks when it is empty, nothing is lost and '
          'nothing is delivered twice. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>One thread makes work, another thread does it, and a '
 'box in the middle holds what has been made but not yet done. The box has a fixed size, and that is the whole '
 'problem: a producer that arrives at a full box cannot just carry on, and a consumer that arrives at an empty '
 'box has nothing to do. Neither may sit in a loop asking "is it my turn yet" &mdash; that burns a whole CPU to '
 'wait &mdash; so the thread has to go to sleep and somebody has to wake it at the right moment. Any number of '
 'threads may be on either side at the same instant, so the check ("is there room?") and the act ("put it in") '
 'have to happen as one indivisible step, or two producers both see the last free slot and one item is silently '
 'overwritten. The one thing that must always be true: the number of items is between zero and the capacity, they '
 'come out in the order they went in, and every item is delivered exactly once &mdash; never lost, never twice.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: a class that compiles and a '
 '<code>main</code> that starts a crowd of threads and proves the counts. The interviewer is watching for, in '
 'this order: the questions you ask before typing (what happens on full, and how many threads on each side, are '
 'the first two); which types exist and who owns which state; <code>put</code> and <code>take</code> end to end, '
 'including the waiting; the race you are actually defending against, named out loud; whether the wait is a '
 '<code>while</code> and not an <code>if</code>, and why there are two conditions and not one; what is inside the '
 'lock and for how long; what happens when a blocked thread is interrupted; and, near the end, why you would write any '
 'of this when <code>ArrayBlockingQueue</code> already exists. Then the twists: never block, drop instead; priority '
 'instead of FIFO; bound it by bytes; shut it down cleanly; make it faster than one lock.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Fixed capacity, or can it grow?</td><td>Fixed at construction</td><td>An array ring buffer, and a bound that is real (moves 1, 5)</td></tr>'
 '<tr><td>On full: block, wait a while, drop something, or throw?</td><td>Block; the rest are a policy</td><td>One-method <code>OverflowPolicy</code> handed in (move 3)</td></tr>'
 '<tr><td>Many producers and many consumers, or one of each?</td><td>Many of both</td><td>A lock and two conditions, not a lock-free single-producer ring (moves 4, 8)</td></tr>'
 '<tr><td>Do callers need a deadline, and must a blocked caller be cancellable?</td><td>Yes to both</td><td>Timed <code>offer</code>/<code>poll</code>, and <code>lockInterruptibly</code> (moves 6, 9)</td></tr>'
 '<tr><td>FIFO, or is priority in scope?</td><td>FIFO</td><td>Storage behind its own interface, so a heap is a new class (moves 3, 12)</td></tr>'
 '<tr><td>Does anything need to stop cleanly?</td><td>Yes: drain, then end-of-stream</td><td>A closed flag read inside the same wait loops (move 6)</td></tr>'
 '<tr><td>Bulk operations, or one item at a time?</td><td><code>drainTo</code> for the consumer</td><td>One lock acquire per batch: rung one of the ladder (move 8)</td></tr>'
 '<tr><td>One JVM and in memory?</td><td>Yes</td><td>No durability yet; the log version is a follow-up (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One run, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> capacity is fixed at construction; many producers and many '
 'consumers; blocking is the default on full and on empty, and the timed variants give up on a deadline; items '
 'are never null so null can mean "nothing"; a blocked caller is cancellable by interrupt; FIFO. Named as out of '
 'scope: priority ordering, byte-based bounds, durability, distribution &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes; and the three things that are deliberately NOT classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a PRODUCER puts an ITEM into a QUEUE of fixed CAPACITY; a CONSUMER takes one out; when it is FULL, somebody WAITS", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 170, "BoundedBlockingQueue", "the lock, the conditions", 1), (228, 180, "RingBuffer", "slots, head, tail, count", 1),
                          (436, 180, "OverflowPolicy", "no state: an interface", 0), (644, 170, "Item", "the payload, not ours", 0),
                          (842, 170, "Producer / Consumer", "threads, not classes", 0), (1040, 160, "notFull / notEmpty", "waiting rooms", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a thread, a payload, an interface, or a waiting room that belongs to the lock", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("hold the items, in order", "RingBuffer  (owns the array + cursors)", "ring.add(item) / ring.poll()"),
                                       ("wait until there is room", "BoundedBlockingQueue  (owns the lock)", "notFull.await() / signal()"),
                                       ('decide what "full" means', "OverflowPolicy  (owns nothing: pure)", "policy.onFull(queue, item)"),
                                       ("hand an item across threads", "BoundedBlockingQueue  (owns all three)", "q.put(item) / q.take()")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 268, "only the queue can see the store AND the two conditions, so the queue is the orchestrator; a producer is not a class here, it is any thread that calls put", "var(--muted)", 11)
m2 += _tx(615, 288, "and notice the verb with no class at all: waiting. It is two queues of parked threads owned by the lock, and await / signal are the only way to touch them", "var(--muted)", 11)
MV[2] = _mv(1230, 300, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 70, 220, 100, "BoundedBlockingQueue", "configure(policy, clock)", acc=True)
for k, (t, sub, impl, isub) in enumerate([("OverflowPolicy", 'what "full" means', "BlockUntilRoom / DropOldest / RejectWhenFull", "and DropNewest, written next year"),
                                          ("Store", "how the items are held", "RingBuffer / HeapStore / ByteBoundedStore", "FIFO, priority, bounded by bytes"),
                                          ("Clock", "where a deadline comes from", "System::nanoTime, or a test's fake", "a lambda is a valid implementation"),
                                          ("QueueObserver", "who wants to know", "PeakMeter, a dashboard, a log line", "called after the unlock, never inside")]):
    y = 20 + k*58
    m3 += _ar("M250 120 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, isub) + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 268, "dashed green = handed in. The queue never builds a rule, so \"never block, throw the stalest reading away\" is a new class and one line at construction", "var(--muted)", 11)
m3 += _tx(615, 288, "and one wrapper takes the whole interface instead: MeteredBuffer wraps ANY BlockingBuffer to time it, and the queue never learns it is being measured", "var(--acc)", 11)
MV[3] = _mv(1230, 300, m3)

# move 4: threads and time -- the gap between check and act
m4 = _D
m4 += _tx(25, 62, "producer A", "var(--acc)", 12, "start") + _tx(25, 132, "producer B", "var(--acc)", 12, "start") + _tx(25, 202, "the ring", "var(--acc)", 12, "start")
cols = [150, 330, 510, 690]
m4 += _bx(cols[0], 40, 165, 44, "reads count = 63", "one free slot")
m4 += _bx(cols[2], 40, 165, 44, "writes slot 63", "count = 64", acc=True)
m4 += _bx(cols[1], 110, 165, 44, "reads count = 63", "one free slot")
m4 += _bx(cols[3], 110, 165, 44, "writes slot 63 too", "count = 65", acc=True)
for k, v in enumerate(["63", "63", "64", "65"]):
    m4 += _bx(cols[k]+40, 180, 85, 34, v, "", acc=(k == 3))
m4 += '<rect x="140" y="28" width="730" height="70" rx="6" fill="none" stroke="%s" stroke-dasharray="5 4"/>' % RED
m4 += _tx(1000, 24, "the gap: A read it, then B read the same number", RED, 11)
m4 += '<path d="M140 235 H880" stroke="var(--line)" stroke-width="1.5"/>'
for k, t in enumerate(["t1", "t2", "t3", "t4"]):
    m4 += '<path d="M%s 230 V240" stroke="var(--line)"/>' % (cols[k]+82) + _tx(cols[k]+82, 256, t, "var(--muted)", 11)
m4 += _tx(905, 240, "time &rarr;", "var(--muted)", 11)
m4 += _bx(900, 60, 300, 100, "one lock", "the check and the write are ONE step", acc=True)
m4 += _tx(1050, 180, "the two waiting rooms hang off that same lock,", "var(--muted)", 10.5)
m4 += _tx(1050, 198, "so nobody can wait on a number that is moving", "var(--muted)", 10.5)
m4 += _tx(615, 285, "count is now 65 in a ring of 64 slots: A's item was overwritten by B and vanished, and the count is a lie that never repairs itself", RED, 11)
MV[4] = _mv(1230, 300, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what comes out next?", "slots[head] &mdash; one array read", "O(1)"),
                                      ("where does the next item go?", "slots[tail], tail = (tail+1) % n", "O(1)"),
                                      ("is it full? is it empty?", "an int count (head == tail cannot tell)", "O(1)"),
                                      ("who is waiting for room?", "notFull: the lock's queue of parked threads", "O(1) park / wake"),
                                      ("how many items right now?", "count, read under the lock", "O(1)")]):
    y = 20 + k*50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 292, "no scanning, no allocation per item, and no list of waiters of our own: each Condition already keeps its own queue of parked threads", "var(--muted)", 11)
MV[5] = _mv(1230, 305, m5)

# move 6: the life of one put, on a time line, and the ORDER
m6 = _D
m6 += _tx(745, 16, 'still full &rarr; sleep again: this arrow is exactly why the check is a while, not an if', "var(--acc)", 11)
m6 += _ar("M920 55 V30 H570 V55", True)
steps6 = [(160, 150, "put(item)", "any thread"), (320, 150, "take the lock", "interruptibly"),
          (480, 180, "park on notFull", "the lock is RELEASED"), (680, 140, "woken", "by a take"),
          (830, 180, "check AGAIN", "under the lock"), (1030, 170, "add, signal, unlock", "in that order")]
for k, (x, w, t, sub) in enumerate(steps6):
    m6 += _bx(x, 55, w, 42, t, sub, acc=(k in (2, 4)))
    if k < 5: m6 += _ar("M%s 76 H%s" % (x+w, steps6[k+1][0]), True)
m6 += _tx(25, 80, "one put", "var(--acc)", 12, "start") + _tx(25, 140, "the lock", "var(--acc)", 12, "start")
m6 += '<rect x="320" y="122" width="160" height="32" rx="4" fill="var(--bg3)" stroke="var(--acc)"/>' + _tx(400, 143, "held by us", "var(--text)", 10.5)
m6 += '<rect x="480" y="122" width="330" height="32" rx="4" fill="var(--bg3)" stroke="var(--line)" stroke-dasharray="5 3"/>' + _tx(645, 143, "held by NOBODY &mdash; await() gave it up while we slept", "var(--muted)", 10.5)
m6 += '<rect x="830" y="122" width="370" height="32" rx="4" fill="var(--bg3)" stroke="var(--acc)"/>' + _tx(1015, 143, "held by us again, re-acquired before await returns", "var(--text)", 10.5)
m6 += '<rect x="20" y="180" width="1190" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(615, 202, "the order inside put, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  lock.lockInterruptibly()   so a caller that ends up parked can still be cancelled",
                       "2  while (full) notFull.await()   in awaitRoom(), which the blocking policy calls: while, not if, because a wake only means \"look again\"",
                       "3  store.add(item)   the state changes FIRST, and it cannot fail half way",
                       "4  notEmpty.signal()   then exactly one consumer is woken, still under the lock",
                       "5  unlock in a finally   an exception must never leave the lock held",
                       "6  then the listeners, outside the lock, in a try/catch"]):
    m6 += _tx(35, 226 + k*20, l, "var(--text)", 11, "start")
m6 += _tx(35, 352, "steps 2 and 3 are under the SAME lock a consumer needs to free a slot, so no signal can land between the check and the sleep: that gap is the real lost wakeup", "var(--muted)", 11, "start")
m6 += _tx(35, 370, "anything that throws before step 3 leaves the count as it was; an interrupt landing after a signal was spent on us signals a peer before it throws", "var(--muted)", 11, "start")
MV[6] = _mv(1230, 395, m6)

# move 7: what is inside the lock, and eight threads at the same instant
m7 = _D + _card(30, 20, 560, 152, "inside the lock: about ten nanoseconds",
                ["one array write, two int updates, one modulo", "one signal onto the other condition's queue",
                 "an uncontended lock acquire and release", "measured: put + take on one thread = 10 ns",
                 "nothing in here can block. Ever."], acc=True)
m7 += _ar("M590 96 H650", True) + _tx(620, 86, "unlock", "var(--acc)", 10.5)
m7 += _card(650, 20, 550, 152, "outside the lock: microseconds to milliseconds",
            ["the consumer's actual work: milliseconds", "a park and an unpark: about 2 microseconds",
             "the listeners: after the unlock, in a try/catch", "the producer making its next item"])
m7 += _tx(615, 196, "eight threads at the same instant: the lock is a baton, not a queue", "var(--text)", 12)
for k in range(8):
    y = 212 + k*18
    lab = ("producer %d" % (k+1)) if k < 4 else ("consumer %d" % (k-3))
    m7 += _tx(25, y + 11, lab, "var(--muted)", 10, "start")
    m7 += '<rect x="150" y="%s" width="1050" height="14" rx="3" fill="var(--bg3)" stroke="var(--line)"/>' % y
    m7 += '<rect x="%s" y="%s" width="14" height="14" rx="3" fill="#12302a" stroke="var(--acc)"/>' % (180 + k*130, y)
m7 += _tx(615, 372, "the grey bar is the thread doing its own work, all at once; the green block is the ten nanoseconds it holds the lock", "var(--muted)", 11)
m7 += _tx(615, 392, "measured: 100,000 items through a capacity-64 queue with these eight threads is about 40 ms, and about one handoff in ten had to park anybody", "var(--muted)", 11)
MV[7] = _mv(1230, 405, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + _tx(300, 34, "one producer, one consumer, 200,000 items (CapacityScan, Extensions.java)", "var(--text)", 12)
cols8 = [("capacity", 12), ("nanoseconds per item", 175), ("how often a thread parked", 340)]
rows8 = [[("1", "var(--text)"), ("about 3,800", None), ("two parks for every single item", None)],
         [("8", "var(--text)"), ("about 520", None), ("one item in four", None)],
         [("64", "var(--text)"), ("about 65", None), ("one item in thirty", None)],
         [("1024", "var(--text)"), ("about 65", None), ("one item in a thousand", None)],
         [("one thread, alone", "var(--acc)"), ("12 for put AND take", None), ("never", None)]]
m8 += _table(20, 46, cols8, rows8, rowh=28, widths=560)
m8 += _tx(300, 240, "the lock is not the cost. The parking is: capacity is the first knob, not cleverness.", "var(--acc)", 11)
m8 += _tx(890, 34, "the ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1   batch: drainTo(sink, 64)", "one lock acquire per batch instead of per item; costs nothing to add"),
                              ("2   two locks: putLock + takeLock + an atomic count", "producers and consumers stop meeting; 50,000 items in about 13 ms"),
                              ("3   a lock-free ring: two volatile cursors, one thread each side", "50,000 items in 2 ms &mdash; and back-pressure becomes the caller's problem")]):
    m8 += _bx(600, 50 + k*58, 600, 46, t, sub, acc=(k == 0))
m8 += _tx(915, 240, "rung 3 gives up the one thing the queue was for: blocking", "var(--muted)", 11)
MV[8] = _mv(1230, 255, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("if instead of while around await", "re-test in a loop, always; test 6 &mdash; 200 rounds of four threads over a capacity-1 queue"),
                                ("checking the flag outside the lock", "check and wait under the SAME lock, so no signal can land in the gap; test 9"),
                                ("notify() on one monitor, or no signal", "two conditions, and signal the matching one after every change; tests 1, 3 and 6"),
                                ("unlock outside a finally", "unlock in a finally, always; test 4 &mdash; after an interrupt the queue still works"),
                                ("an interrupt eats a signal meant for a peer", "re-signal that condition before rethrowing; test 4"),
                                ("the dashboard is called inside the lock", "publish after the unlock, in a try/catch; test 7"),
                                ("a shutdown leaves threads parked forever", "close() sets a flag the wait loops already read, then signalAll on both; test 8")]):
    y = 18 + k*42
    m9 += _bx(30, y, 330, 38, bad, "") + _ar("M360 %s H380" % (y+19), True) + _bx(380, y, 820, 38, fix, "", acc=True)
m9 += _tx(615, 338, "twenty-three checks in FailureTests.java, every wait with a deadline and a fifty-second watchdog: a queue test that hangs is a failed queue test", "var(--muted)", 11)
MV[9] = _mv(1230, 352, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 830)]
rows10 = [[("Monitor object", "var(--text)"), ("move 4", None), ("one ReentrantLock + two Conditions, private to the queue", None), ("state can only be touched through a method that locks", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface OverflowPolicy { boolean onFull(q, item); }", None), ("block / drop / reject is a class, not a branch", None)],
          [("Strategy again", "var(--text)"), ("move 3", None), ("interface Store { add / poll / isFull / size }", None), ("FIFO &rarr; priority &rarr; bytes, lock untouched", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("MeteredBuffer implements BlockingBuffer, wraps one", None), ("measurement without opening the queue", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(...) after the unlock, inside a try/catch", None), ("a dashboard can never slow a handoff", None)],
          [("State", "var(--text)"), ("move 6", None), ("the while loop IS the state machine of a put", None), ("a wake goes back to the check, never to the write", None)],
          [("Producer-Consumer", "var(--text)"), ("every move", None), ("put / take across threads, with a bound", None), ("the pattern this object IS; say the name", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the queue is handed to both sides; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh queue per case", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("new BoundedBlockingQueue&lt;&gt;(64) is one line", "var(--muted)"), ("it earns the name when they come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a capacity and a store: two arguments", "var(--muted)"), ("a builder here would be pure ceremony", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 372, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 388, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 430), ("the line that shows it", 530)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("RingBuffer stores. The queue synchronises. A policy decides what full means.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("DropNewest is a new file plus one line at construction", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("policy.onFull(this, item);  store.add(item);  never \"which one is it?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("OverflowPolicy, Clock, QueueObserver, Weigher &mdash; a lambda implements each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; be handed the rest", None), ("moves 3, 6", None), ("configure(policy, clock): a test hands in a clock already past the deadline", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "never block: drop, or refuse", "a new class behind OverflowPolicy plus one line at construction", "", "move 3"),
        ("someone new wants to know", "queue depth on a dashboard", "one more observer, called after the unlock in a try/catch", "", "move 4"),
        ("a new step in a life", "shut down cleanly", "a closed flag the wait loops already read, then signalAll on both", "", "move 6"),
        ("a new invariant across items", "bound by bytes, not by count", "a new Store whose isFull() counts bytes; the lock does not change", "", "moves 3 + 5"),
        ("state that must outlive the process", "survive a restart", "the array becomes an append-only log; head becomes a committed offset", "commit the offset only AFTER the work succeeded: at-least-once, idempotent consumers", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the lock, the two conditions and the wait loops are untouched; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class &mdash; and on a threading problem, notice what does not.",
 "Reading the sentence again: a <b>producer</b> puts an <b>item</b> into a <b>queue</b> of fixed <b>capacity</b>; a "
 "<b>consumer</b> takes one out; when it is <b>full</b>, somebody <b>waits</b>. The queue holds the lock, the two "
 "conditions and the rules: a class, and the only one the callers touch. The storage has an array, a head, a tail and "
 "a count, all of which move: a class of its own, so it can be tested on one thread with no threading at all. What "
 "\"full\" means has no state, so it is an interface. And then the three that a threading problem tempts you to make "
 "classes and must not: the item is the caller's payload, not ours; a producer is not an object, it is any thread that "
 "calls <code>put</code>; and the waiting parties are not a list you keep &mdash; they are two queues of parked threads "
 "that the lock already maintains, reached only through <code>await</code> and <code>signal</code>. Inventing a "
 "<code>Waiter</code> class here is the classic wrong turn.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Hold the items in order\" touches the array and the two cursors, so it belongs to the ring buffer: "
 "<code>ring.add(item)</code> and <code>ring.poll()</code>. \"Wait until there is room\" touches the lock and the "
 "not-full condition, so it belongs to the thing that owns them: the queue. \"Decide what full means\" touches nothing "
 "at all &mdash; it is a decision, given the queue and the item &mdash; so it is a pure rule. And \"hand an item across "
 "threads\" touches all three at once; only the queue can see the store <i>and</i> the conditions, so "
 "<code>put</code> and <code>take</code> live there and the queue is the orchestrator. That is also the answer to a "
 "question interviewers like: why is there no <code>Producer</code> class? Because a producer owns no state that the "
 "queue cares about. It is a thread, and its only relationship with the design is that it calls a method.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind a one-method interface and is handed in.",
 "Four things will change, and each becomes an interface the queue is <i>given</i> rather than builds. What happens on "
 "full will change: block today, drop the stalest reading tomorrow, refuse loudly the day after &mdash; that is "
 "<code>OverflowPolicy</code>, and it is the seam the interviewer reaches for first. How the items are held will change: "
 "a ring today, a bounded heap when somebody says \"urgent jobs first\", a byte budget when somebody says \"these "
 "messages are two megabytes each\" &mdash; that is <code>Store</code>. Where a deadline comes from will change, because "
 "a test cannot afford to wait for one &mdash; that is <code>Clock</code>. And who wants to know will change &mdash; "
 "that is <code>QueueObserver</code>. This is where the patterns are born, not announced: a swappable rule behind an "
 "interface is <b>Strategy</b>; a wrapper that adds behaviour to the whole interface is <b>Decorator</b>, and here it is "
 "<code>MeteredBuffer</code>, which times any buffer without the queue ever knowing; a queue that says \"an item landed\" "
 "without knowing what a dashboard is, is <b>Observer</b>.", 3),
("Move 4: state that many threads change at the same time gets one owner and one lock.",
 "Two producers arrive at a queue with one free slot. Both read <code>count = 63</code> against a capacity of 64, both "
 "conclude there is room, and both write into slot 63: one item is silently overwritten, the count says 65 in a ring of "
 "64, and nothing ever repairs itself. The gap is between the check and the act, and the only fix is to make them one "
 "step. So the array, both cursors, the count and the two conditions all belong to one object, and every path in and out "
 "goes through its lock &mdash; that shape has a name, the <b>monitor object</b>. The two waiting rooms hang off the same "
 "lock on purpose: a thread that is about to sleep tests the condition and goes to sleep <i>without</i> ever releasing "
 "the lock in between, which is what makes \"I checked and then I slept\" atomic. Anything that only listens is called "
 "after the unlock, never inside it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What comes out next?\" is one array read at <code>head</code>. \"Where does the next item go?\" is one array write at "
 "<code>tail</code>, then <code>tail = (tail + 1) % n</code> to wrap. \"Is it full? is it empty?\" is the one that "
 "catches people: <code>head == tail</code> is true in both cases, so you keep an <code>int count</code> and those two "
 "questions become comparisons. \"Who is waiting?\" needs no structure from us at all &mdash; each <code>Condition</code> "
 "keeps its own queue of parked threads, so parking is O(1) and waking exactly one is O(1). Nothing here scans, nothing "
 "allocates per item, and the memory is exactly capacity slots forever, which is the other half of what \"bounded\" "
 "buys you: a fixed, known ceiling on how much work can be in flight.", 5),
("Move 6: a put has a life cycle, and the order of the steps inside it is the design.",
 "Follow one <code>put</code> along the clock. It takes the lock &mdash; interruptibly, so a caller that ends up parked "
 "can still be cancelled. It finds the queue full and calls <code>notFull.await()</code>, which does the thing that "
 "makes the whole design work: it releases the lock while the thread sleeps, and re-acquires it before returning. A "
 "consumer takes an item and signals; this thread wakes up, but a wake only means \"look again\", so it re-tests the "
 "condition &mdash; another producer may have taken the slot in between, which is called a signal steal, and the "
 "hardware is also allowed to wake a thread for no reason at all, which is a spurious wakeup. That is why the wait is a "
 "<code>while</code> and never an <code>if</code>; the arrow from \"woken\" goes back to the check, not forward to the "
 "write. Only when it sees room does it change the store, then signal one consumer, then unlock in a <code>finally</code>, "
 "then tell the listeners. Anything that throws before the store changes leaves the count exactly as it was; and an "
 "interrupt that lands after a signal was already spent on this thread signals a peer before it throws, so the wakeup "
 "does not die with it.", 6),
("Move 7: yes, one lock means one at a time. Ask for how long, and what is inside it.",
 "Inside the lock there is one array write, two integer updates, a modulo and one signal: on this machine a "
 "<code>put</code> and a <code>take</code> together measure about ten nanoseconds when nothing blocks. Everything "
 "expensive is outside it &mdash; the work the consumer actually does, the listeners, the producer making its next item "
 "&mdash; because nothing that can block is allowed inside. So eight threads hitting the queue at the same instant pass "
 "the lock around like a baton rather than queueing behind it: the measured run of 100,000 items through a capacity-64 "
 "queue with four producers and four consumers takes about 40 milliseconds, and what those threads spent their time on "
 "was each other, not the lock. The honest number to volunteer is the other one: about one handoff in ten &mdash; ten "
 "thousand of the hundred thousand &mdash; actually had to put a thread to sleep and wake it again, and that is where "
 "the milliseconds went.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Measure before you climb. One producer and one consumer moving 200,000 items: at capacity 1, about 3,800 nanoseconds per "
 "item and two parks for every single item; at capacity 8, about 520 nanoseconds and one item in four parks; at capacity "
 "64, about 65 nanoseconds and one in thirty; at capacity 1024, about the same again and one in a thousand. Those "
 "absolute numbers move ten or twenty per cent from run to run &mdash; the ratios between the rows do not. "
 "The shape of that table is the whole lesson &mdash; the lock costs tens of nanoseconds, a park and an unpark costs "
 "about two microseconds, so the first knob is capacity, not cleverness, and a queue that is sized so it is rarely "
 "empty and rarely full barely blocks at all. Then the ladder, cheapest first. One: batch, with "
 "<code>drainTo(sink, 64)</code>, which is one lock acquire per batch instead of per item and costs nothing to add. Two: "
 "two locks &mdash; a linked list has two ends, so producers take a put lock, consumers take a take lock, and the only "
 "shared word is an atomic count; that is what <code>LinkedBlockingQueue</code> does, and it moved 50,000 items in about "
 "13 milliseconds here. Three: a lock-free ring with two volatile cursors, 50,000 items in 2 milliseconds &mdash; and it "
 "gives up the one thing you were asked for, because a full ring now returns false and back-pressure becomes the "
 "caller's problem.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "An <code>if</code> instead of a <code>while</code> around the wait, so a stolen or spurious wakeup lets a thread act on "
 "a condition that is no longer true. One monitor with <code>notify()</code>, which hands the wakeup to whichever crowd "
 "it likes and can spend it on a thread that cannot use it. A signal forgotten after a change, or sent to the wrong "
 "condition, which leaves a thread asleep forever. An unlock outside a <code>finally</code>, so one exception wedges "
 "every thread in the process. An interrupt landing on a thread that had already been signalled, quietly swallowing that "
 "signal. A listener called inside the lock, or throwing. And a shutdown that never wakes the parked. Each of those is a "
 "few lines in FailureTests.java, and every wait in that file has a deadline with a watchdog behind it, because a "
 "concurrency test that hangs has told you nothing.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Read the table, then say the two things it cannot. First, name the shape of the whole object out loud: private state, "
 "one lock, and the only way in is a method that takes it, is a <b>monitor object</b> &mdash; and the object itself "
 "<i>is</i> <b>Producer-Consumer</b>, which interviewers notice when you skip it. Second, be willing to say a pattern is "
 "not here: Singleton earned nothing, Factory earns its name the day capacity, policy and store arrive as strings from "
 "configuration, and Builder never does with two constructor arguments. Every other row is a move that already happened, "
 "which is why none of them was chosen before the code existed.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is the answer; here is what it is for. On a threading problem the S line is the one that pays: because "
 "storage, synchronisation and the full-policy are three types and not one, the ring buffer can be unit-tested on a "
 "single thread with no threading at all, and only the queue needs the awkward multi-thread tests. And the D line is "
 "what makes the timed calls testable: the clock is handed in through <code>configure</code>, so a test can supply one "
 "whose deadline has already passed and watch <code>poll</code> give up without waiting a single millisecond.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (\"never block, this feeds a live panel\") is a new class behind <code>OverflowPolicy</code> plus one line. "
 "Someone new who wants to know (queue depth on a dashboard, a log line per drop) is one more observer, called after the "
 "unlock. A new step in a life (shut it down; drain, then end-of-stream) is a flag the wait loops already read plus "
 "<code>signalAll</code> on both conditions, because that is the one change that concerns every waiter at once. A new "
 "invariant across items (bound it by bytes, not by count) is a new <code>Store</code> whose <code>isFull</code> counts "
 "bytes; the lock and the conditions do not move. And state that must outlive the process is the same two cursors with "
 "the array replaced by an append-only log: <code>head</code> becomes a committed offset, and the order becomes append "
 "first, hand the item over second, commit the offset only after the work succeeded &mdash; which is at-least-once "
 "delivery and is why the consumer must be idempotent. That last one is not a trick: it is what a message broker is. For "
 "all five, the lock, the two conditions and the wait loops are untouched.", 12),
]
DERIVATION_LEAD = ("The same twelve moves as every other page here, with the threading ones doing the work: the shared "
 "state and its one lock (move 4), the wait protocol &mdash; check under the lock, wait in a loop, signal after the "
 "change (move 6), what is inside the lock and what happens when N threads arrive at once (move 7), and the ladder from "
 "one lock and two conditions to two locks to no locks at all (move 8). Nothing is chosen up front, and no pattern is "
 "named before the move that produced it.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the decorator, the two kinds of caller, and the injected bits
put("metered", 10, 20, 250, "MeteredBuffer", ["in Extensions.java", "inner: BlockingBuffer&lt;T&gt;"], ["put / take: times, delegates"])
put("prod", 10, 120, 250, "Producer thread", [], ["q.put(item)", "q.offer(item, 50, MILLIS)"])
put("cons", 10, 210, 250, "Consumer thread", [], ["q.take()", "q.poll(50, MILLIS)"])
put("obs", 10, 310, 250, "QueueObserver", [], ["onEvent(what, size)"], "interface")
put("meter", 10, 394, 250, "PeakMeter", ["peak: AtomicInteger"], ["onEvent: keeps the maximum"])
put("clock", 10, 498, 250, "Clock", [], ["nanoTime(): long"], "interface")
# centre: the contract, then the aggregate root
put("iface", 310, 20, 360, "BlockingBuffer&lt;T&gt;", [],
    ["put(item)", "take(): T", "offer(item, timeout, unit)", "poll(timeout, unit): T", "size(): int", "capacity(): int"], "interface")
put("queue", 310, 190, 360, "BoundedBlockingQueue&lt;T&gt;",
    ["store: Store&lt;T&gt;", "lock: ReentrantLock", "notFull: Condition", "notEmpty: Condition",
     "onFull: OverflowPolicy&lt;T&gt;", "clock: Clock", "observers: List&lt;QueueObserver&gt;", "closed: boolean"],
    ["put(item) / take()", "offer(...) / poll(...)", "drainTo(sink, max): int", "close() / isClosed()",
     "size() / capacity() / remainingCapacity()", "parkCount(): long", "configure(policy, clock)", "addObserver(o)",
     "awaitRoom()  [lock held]", "evictOldest()  [lock held]", "publish(what, size)  [after unlock]"])
# right column: what "full" means, and how items are held
put("policy", 720, 20, 250, "OverflowPolicy&lt;T&gt;", [], ["onFull(queue, item): boolean"], "interface")
put("block", 720, 110, 250, "BlockUntilRoom", [], ["awaits notFull, then enqueue"])
put("drop", 720, 195, 250, "DropOldest", [], ["evicts the head, then enqueue"])
put("reject", 720, 280, 250, "RejectWhenFull", [], ["throws IllegalStateException"])
put("store", 720, 390, 250, "Store&lt;T&gt;", [], ["add(item) / poll(): T", "isFull() / isEmpty()", "size() / capacity()"], "interface")
put("ring", 720, 520, 250, "RingBuffer", ["slots: Object[]", "head, tail, count: int"], ["O(1), nothing allocated"])
# far right: the alternatives that the two seams make cheap
put("twolock", 990, 110, 240, "TwoLockQueue", ["in Extensions.java", "putLock / takeLock", "count: AtomicInteger"], ["page 05: ladder rung 2"])
put("heap", 990, 390, 240, "HeapStore", ["in Extensions.java"], ["a bounded binary heap", "priority instead of FIFO"])
put("bytes", 990, 500, 240, "ByteBoundedStore", ["in Extensions.java", "weigher: Weigher&lt;T&gt;"], ["full = the byte budget"])

def raw(x, y, w, h, title, sub, chips):
    """the two waiting rooms: not classes, so they are drawn as what they are -- queues of parked threads"""
    g = '<g transform="translate(%s %s)"><rect width="%s" height="%s" rx="6" fill="var(--bg3)" stroke="var(--acc)" stroke-dasharray="5 3"/>' % (x, y, w, h)
    g += '<text x="%s" y="22" text-anchor="middle" font-size="12.5" fill="var(--acc)">%s</text>' % (w/2, title)
    for k, c in enumerate(chips):
        g += '<rect x="%s" y="34" width="46" height="22" rx="11" fill="#12302a" stroke="var(--acc)"/>' % (18 + k*56)
        g += '<text x="%s" y="49" text-anchor="middle" font-size="11" fill="var(--text)">%s</text>' % (41 + k*56, c)
    g += '<text x="%s" y="49" font-size="10.5" fill="var(--muted)">%s</text>' % (18 + len(chips)*56 + 10, sub)
    return g + '</g>'

def bus(x, y1, y2):
    return '<path d="M%s %s V%s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x, y1, y2)

EDGES = [
 # the three policies hang off one bus into the interface
 bus(700, 307, 90), '<path d="M720 137 H700" stroke="var(--muted)" stroke-width="1.3"/>',
 '<path d="M720 222 H700" stroke="var(--muted)" stroke-width="1.3"/>', '<path d="M720 307 H700" stroke="var(--muted)" stroke-width="1.3"/>',
 ln((700, 90), (845, 74), "inherit", "", [(845, 90)]),
 # the stores
 ln(B["ring"]["t"], B["store"]["b"], "inherit"),
 ln(B["heap"]["l"], B["store"]["r"], "inherit"),
 ln(B["bytes"]["l"], B["store"]["r"], "inherit", "", [(975, 537), (975, 445)]),
 # the queue implements the contract and owns the store
 ln(B["queue"]["t"], B["iface"]["b"], "inherit"),
 ln(B["metered"]["r"], B["iface"]["l"], "inherit"),
 ln((1110, 110), (670, 87), "inherit", "", [(1110, 92), (690, 92)]),
 ln((670, 355), (720, 433), "compose", "", [(695, 355), (695, 433)]),
 # the rules are handed in
 ln((720, 47), (670, 230), "inject", "", [(690, 47), (690, 230)]),
 _tx(845, 12, "handed in through configure()", "var(--acc)", 10.5),
 ln(B["clock"]["r"], (310, 430), "inject", "", [(280, 525), (280, 430)]),
 ln((310, 330), B["obs"]["r"], "notify", "", [(285, 330), (285, 337)]),
 ln(B["meter"]["t"], B["obs"]["b"], "inherit"),
 # the callers
 ln(B["prod"]["r"], (310, 250), "assoc", "", [(292, 155), (292, 250)]),
 ln(B["cons"]["r"], (310, 290), "assoc", "", [(300, 245), (300, 290)]),
 # the two waiting rooms, owned by the same lock
 raw(310, 640, 360, 74, "notFull &mdash; producers asleep", "await() gave the lock back", ["P2", "P5"]),
 raw(700, 640, 360, 74, "notEmpty &mdash; consumers asleep", "signal() wakes one", ["C1", "C3", "C4"]),
 ln((490, 536), (490, 640), "compose"),
 ln((600, 536), (880, 640), "compose", "", [(600, 625), (880, 625)]),
 _tx(615, 730, "these two are not classes: they are the queues of parked threads that the lock itself keeps, reached only through await() and signal()", "var(--muted)", 11),
 _tx(615, 748, "every box tagged \"in Extensions.java\" is follow-up code, not part of the hour: MeteredBuffer, TwoLockQueue, HeapStore, ByteBoundedStore. Everything else is Main.java", "var(--muted)", 11),
]
UMLSVG = uml_svg(1230, 806, EDGES, legend_y=780)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the type name (dashed border = interface). Middle: its fields, the state '
 'it holds; a box whose first line reads <i>in Extensions.java</i> is follow-up code, not something you type in the '
 'hour. Bottom: its methods; <code>[lock held]</code> marks the two package-private hooks a policy is allowed to '
 'call, and <code>[after unlock]</code> marks the one that must not run inside it. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the queue owns its store, its lock and both conditions, and they die with it. '
 'Dashed green = handed in through <code>configure()</code> or the constructor. Dotted blue = notifies. '
 '<b>Where state lives:</b> every mutable field in this design is inside <code>BoundedBlockingQueue</code> or inside the '
 '<code>Store</code> it owns, and both are reachable only under the one lock &mdash; that is the whole safety argument, '
 'and it is why a policy is handed the queue rather than the array. Notice what is <i>not</i> a class: the producer and '
 'the consumer are threads, not objects; and the two waiting rooms at the bottom are queues of parked threads that the '
 'lock maintains for each <code>Condition</code>, which is why "who is waiting?" needs no data structure of ours.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does and what it guarantees; read only those first for the shape, then the bodies. Each '
 'copy button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, '
 'with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (twenty-three checks, every wait on a '
 'deadline; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six clarifying questions (what happens on full, and how many threads per side, first); then '
 'type in the order of Main.java: the <code>Clock</code> and <code>BlockingBuffer</code> interfaces, the '
 '<code>Store</code> interface and <code>RingBuffer</code> with no locks in it at all, <code>OverflowPolicy</code> with '
 'the blocking implementation, the observer, then <code>BoundedBlockingQueue</code> &mdash; the lock, the two '
 'conditions, and <code>put</code> with its order &mdash; then <code>take</code> as its mirror, then the timed pair, '
 'then <code>drainTo</code> and <code>close</code>, then a main that starts eight threads on one latch and counts what '
 'came out.</div></div>')

FU = [
("Mid-round: this queue feeds a live metrics panel, so a producer must never stall. If it is full, throw away the stalest reading.", "twist", 8,
 "Nothing in the queue changes. What happens on full was already a rule handed in, so this is one new class whose "
 "<code>onFull</code> evicts the head and returns true, plus one line at construction. It never waits, so a producer is "
 "never parked: the demo puts seven items into a capacity-3 queue and the park counter stays at zero while the queue "
 "holds the last three. The family is open &mdash; drop the newest instead, or refuse loudly with an exception &mdash; "
 "and each is another small class rather than another branch inside <code>put</code>. The one thing to say out loud is "
 "that the policy runs with the lock already held, so it may evict, but it may only wait on the queue's own condition.",
 sect(src, "final class DropOldest", "final class RejectWhenFull") + "\n" + X("drop the NEWEST", "measure without touching")),
("Ten producers and ten consumers, a hundred thousand items. Prove nothing is lost and nothing is delivered twice.", "non-functional", 10,
 "The race lives between reading the count and acting on it, and the fix is that the whole read-modify-write happens "
 "under one lock. The proof is a count, not an argument: twenty threads wait on one latch, ten of them put ten thousand "
 "distinct integers each, ten of them take until the queue is closed and drained, and the test then marks every integer "
 "it saw. A lost item leaves a hole, a doubled item trips the duplicate counter, and an overfilled queue shows up in the "
 "observer's peak, which is checked against the capacity. All three are asserted, and every join has a thirty-second "
 "deadline so a deadlock fails the test instead of hanging the build.",
 T("        // 2. the race", "        // 3. full means")),
("Why is the wait a while loop and not an if? Show me what breaks.", "design", 5,
 "Because a wakeup is not a promise. Two things can happen between the signal and this thread actually running: another "
 "producer can take the slot that was just freed (a signal steal), and the JVM is allowed to return from "
 "<code>await</code> for no reason at all (a spurious wakeup). With an <code>if</code>, the thread carries on and writes "
 "into a full ring, which either overwrites an item or throws. With a <code>while</code>, it re-tests and goes back to "
 "sleep, which costs one extra check. The state machine on page 02 move 6 is the picture of it: the arrow from \"woken\" "
 "goes back to \"check\", never forward to \"write\". The test that catches the <code>if</code> version is the stress "
 "loop: two hundred rounds of four threads over a capacity-1 queue, where any stale check corrupts the count and any "
 "lost wakeup hangs the round past its deadline.",
 sect(src, "public T take()", "public boolean offer(") + "\n" + T("        // 6. capacity 1", "        // 7. a listener")),
("Why two conditions and not one? And why signal rather than signalAll?", "design", 8,
 "With one condition there is one waiting crowd, so a wakeup cannot be aimed: a put that frees nothing for producers can "
 "still wake a producer, that producer re-checks, finds the queue full and goes back to sleep, and the wakeup is spent. "
 "With one monitor you are forced into <code>notifyAll</code>, which wakes everybody so that the one thread that can "
 "make progress is definitely among them &mdash; correct, and a thundering herd. Two conditions let a put wake a "
 "consumer and a take wake a producer, so <code>signal</code> is enough: each operation changes availability by exactly "
 "one, so exactly one waiter can use it. The two places that still need <code>signalAll</code> are the ones where the "
 "change concerns everyone: <code>close()</code>, and <code>drainTo</code>, which frees many slots at once and therefore "
 "signals once per slot freed.",
 sect(src, "public int drainTo(", "public void close()") + "\n" + X("synchronized / wait / notify", "shutdown without a flag")),
("You keep saying \"lost wakeup\". What exactly is lost, and why can it not happen here?", "design", 5,
 "Two different bugs go by that name. The first is the one in the monitor version above: the signal is spent on a thread "
 "that cannot use it, and everyone goes back to sleep. The second is the real one, and it is what the wait protocol is "
 "for. A signal is not stored anywhere: <code>signal</code> wakes whoever is waiting at that instant, and if nobody is "
 "waiting it does nothing at all. So if you check the condition, release the lock, and only then go and wait, the state "
 "can change in that gap and the signal can be sent while you are not yet waiting &mdash; and it is gone. This design "
 "cannot do that, because the check and the <code>await</code> are both inside the lock, and the thread that would "
 "change the state needs that same lock to change it. The reference code has both halves so you can read the diff, and "
 "test 9 measures them: the version that checks outside the lock sleeps the whole 300 ms, the version that checks inside "
 "wakes in 0 ms.",
 X("the lost wakeup proper", "two semaphores") + "\n" + T("        // 9. the lost wakeup", "        // 10. the two alternatives")),
("Where is volatile in all this? Why is the closed flag a plain boolean?", "design", 5,
 "Because a lock does two jobs, and people only remember one. It keeps threads out of each other's way, and it also "
 "publishes memory: everything a thread wrote before it released the lock is visible to the next thread that acquires "
 "it. <code>closed</code>, the array, the head, the tail and the count are only ever written and read with the lock "
 "held, so they need nothing else &mdash; adding <code>volatile</code> to them would be noise, not safety. Two fields "
 "are different and show the rule by contrast. <code>parks</code> is an <code>AtomicLong</code> because "
 "<code>parkCount()</code> deliberately reads it without taking the lock, so a test can look while threads are running. "
 "And in the lock-free ring on page 05 there is no lock at all, so the two cursors have to be <code>volatile</code>: "
 "writing the cursor is what publishes the slot the producer just filled, and reading it is what makes that write "
 "visible. The rule to say out loud: either the state is under one lock, or every field it is reached through is "
 "volatile or atomic. Never half of each.",
 sect(src, "private final Store<T> store;", "/** A queue of this many items") + "\n"
 + sect(src, "public void close()", "void awaitRoom()") + "\n" + sect(src, "public int size() { lock.lock();", "private void publish")
 + "\n" + sect(ext, "final class SpscRing", "/** Called by the one producer thread")),
("A consumer is blocked on an empty queue and the service is shutting down. How does the caller cancel it?", "functional", 5,
 "By interrupting the thread. Both <code>put</code> and <code>take</code> acquire the lock with "
 "<code>lockInterruptibly</code> and wait with <code>await</code>, so a parked thread wakes with an "
 "<code>InterruptedException</code> rather than sitting there forever. Three details make it safe rather than merely "
 "possible. The unlock is in a <code>finally</code>, so the lock is released on the way out and the queue is still usable "
 "&mdash; the test interrupts a parked consumer and then does a normal put and poll to prove it. The catch signals "
 "the same condition before rethrowing, because this thread may have been the one a signal was spent on; without that "
 "line the wakeup dies with the cancelled thread and a peer sleeps forever. And the queue throws the exception rather "
 "than handling it, which is the right half of the rule; the other half is for the caller, and interviewers ask it: a "
 "catch block either rethrows, or it restores the flag with <code>Thread.currentThread().interrupt()</code> before it "
 "returns, because the flag was cleared when the exception was thrown and the next blocking call up the stack needs to "
 "see it. Swallowing it silently is the bug &mdash; every consumer loop in <code>main</code> restores it. If a caller "
 "genuinely must not be cancellable, the opposite pair exists: plain <code>lock()</code> and "
 "<code>awaitUninterruptibly()</code>, which is almost never what you want in a queue.",
 sect(src, "void awaitRoom()", "void evictOldest()") + "\n" + T("        // 4. empty means", "        // 5. the timed calls")),
("Timed offer and poll: where does the deadline come from, and how do you test one without waiting for it?", "design", 5,
 "The deadline is computed once, from an injected clock, and the remaining budget is recomputed on every wake: "
 "<code>awaitNanos</code> is given what is left, so a spurious wakeup shortens the wait instead of restarting it. That is "
 "the bug the naive version has &mdash; passing the full timeout again each time round the loop, so a thread woken ten "
 "times waits ten timeouts. Because the clock is handed in, a test can supply one whose every reading is a second later "
 "than the last: the deadline is already in the past on the first check, and <code>poll</code> returns null in under a "
 "millisecond, which is asserted. The real parking still uses the operating system's timer, so what the fake clock "
 "proves is the arithmetic, not the sleep.",
 sect(src, "public T poll(long timeout", "public int drainTo(") + "\n" + T("        // 5. the timed calls", "        // 6. capacity 1")),
("One lock for everything. Have you serialised the whole pipeline? And what is above this if I need more?", "non-functional", 10,
 "Measure first. The locked part is one array write, two int updates and a signal: a put and a take together measure "
 "about twelve nanoseconds on one thread. Under load the lock is not what threads wait for &mdash; they wait for each "
 "other's items. The number that matters is how often a thread actually parks, and that is a function of capacity, which "
 "is what the table in move 8 measures: raise the capacity and the parking falls away. So the first fix is sizing, not "
 "architecture. Only then the ladder: batch with <code>drainTo</code>, which is one lock acquire per batch instead of "
 "per item; then two locks, a put lock and a take lock over a linked list with an atomic count, which is what "
 "<code>LinkedBlockingQueue</code> does and which moved 50,000 items in about 13 ms here; then a lock-free ring with two "
 "volatile cursors, 50,000 items in 2 ms, which is single-producer single-consumer only and hands back-pressure back to "
 "the caller, giving up the very thing a blocking queue was for.",
 X("two locks", "ladder rung 3") + "\n" + X("ladder rung 3", "the synchronized / wait / notify")),
("In real code you would not write this yourself. What does java.util.concurrent already give you, and which one would you pick?", "design", 8,
 "Say it before they do: <code>ArrayBlockingQueue</code> <i>is</i> this class &mdash; one lock, two conditions, a fixed "
 "array, a fairness flag in the constructor &mdash; and in production that is what you use. The exercise is to show you "
 "know what is inside it. The family is the same shape with one knob moved: <code>LinkedBlockingQueue</code> is rung two "
 "of the ladder (a put lock and a take lock); <code>SynchronousQueue</code> is capacity zero, a hand-off rather than a "
 "buffer, and is what a cached thread pool uses; <code>PriorityBlockingQueue</code> is the heap store; "
 "<code>DelayQueue</code> hands an item over only once its own time has come; <code>LinkedTransferQueue.transfer</code> "
 "waits until a consumer has actually taken the item. Two of them have a trap worth naming: "
 "<code>new LinkedBlockingQueue&lt;&gt;()</code> with no argument is unbounded, and <code>PriorityBlockingQueue</code> "
 "is always unbounded, so both quietly undo the back-pressure you were asked for. And the piece people miss: a "
 "<code>ThreadPoolExecutor</code> is a bounded queue plus a <code>RejectedExecutionHandler</code>, which is exactly our "
 "<code>OverflowPolicy</code> &mdash; <code>DiscardOldestPolicy</code> is drop-oldest, <code>AbortPolicy</code> is "
 "reject, and <code>CallerRunsPolicy</code> is the nearest thing to blocking, because the thread that submitted the work "
 "has to run it itself and therefore stops submitting. If they ask for a second way to write it by hand, the short one is "
 "two semaphores and a mutex: the permit count <i>is</i> the predicate, so there is no condition and no "
 "<code>while</code> loop &mdash; and no way to run a policy that wants to look inside a full queue, which is why the "
 "lock-and-two-conditions version is the one to type first. Test 10 runs ours, the semaphore one and "
 "<code>ArrayBlockingQueue</code> side by side and checks they answer identically.",
 X("what java.util.concurrent", "the capacity table") + "\n" + X("two semaphores", "what java.util.concurrent")),
("The service is shutting down. Stop the queue cleanly: no work lost, nobody left asleep.", "twist", 8,
 "<code>close()</code> sets a flag under the lock and then calls <code>signalAll</code> on both conditions, because this "
 "is the one change that concerns every waiter at once. The flag is read inside the same wait loops, so a parked thread "
 "wakes, re-checks, and sees it; a closing signal cannot be lost because the flag and the signal are set under the same "
 "lock. After close, a put is refused with an exception so nothing is silently dropped, while a take keeps handing out "
 "what is already in the queue and only then returns null as end-of-stream &mdash; which is exactly what the consumer "
 "loops in <code>main</code> use to exit. The portable alternative, for a queue you do not own, is one poison pill per "
 "consumer: a sentinel that travels in FIFO order behind the real work.",
 sect(src, "public void close()", "void awaitRoom()") + "\n" + X("shutdown without a flag", "fairness and starvation")),
("Urgent jobs must jump the queue. Priority instead of FIFO.", "twist", 5,
 "Storage was already a separate job behind its own interface, so this is a new <code>Store</code> and nothing else: a "
 "bounded binary heap with the same add / poll / isFull / size surface. The lock, both conditions, the wait loops and "
 "every policy are untouched, and the queue is constructed with the new store instead of a ring. Two honest caveats to "
 "volunteer: add and poll become O(log n) instead of O(1), and FIFO is gone, so a low-priority item can starve &mdash; "
 "the usual fix is a priority plus an arrival sequence number as a tie-break, or ageing. Also note that drop-oldest on a "
 "heap drops the <i>highest</i>-priority item, so pair a heap with drop-newest.",
 X("priority instead of FIFO", "bound by bytes")),
("These messages are two megabytes each. Bound it by bytes, not by item count.", "twist", 5,
 "Same seam again: a store whose <code>isFull</code> compares a running byte total against a budget, with the size of an "
 "item supplied by a one-method <code>Weigher</code> handed in, because the queue must not guess how big anything is. "
 "The queue does not change at all. The one imprecision worth saying out loud before they say it: fullness is tested "
 "before the incoming item is weighed, so the bound can overshoot by at most one item; the exact fix is a "
 "<code>hasRoomFor(item)</code> on the store interface, which <code>put</code> would call instead of "
 "<code>isFull()</code>. An item larger than the whole budget is rejected rather than deadlocking the producer forever.",
 X("bound by bytes", "bulk transfer")),
("One of my producers is being starved. What can you do about it, and what does it cost?", "non-functional", 5,
 "The lock is non-fair by default: a thread arriving at the very moment the lock is released can barge past threads that "
 "have been queued for a while. That is what makes it fast &mdash; the thread that just released the lock is still on a "
 "CPU and can simply take it again, with no park, no unpark and no context switch &mdash; and it is also how one caller "
 "can be passed over again and again, which is starvation. <code>new ReentrantLock(true)</code> hands the lock out in "
 "arrival order instead. Quote the price, because it is bigger than people expect: with six threads sharing nothing but "
 "the lock, the barging lock does about eleven million round-trips through it in 200 ms and the fair lock about forty "
 "thousand. That is two to three orders of magnitude, and it is all park and unpark. The second half of the answer is "
 "the one that gets the nod: on that same run the barging lock did not actually starve anybody &mdash; the busiest and "
 "quietest threads were within 1.1x of each other. Fairness buys a guarantee that no waiter is passed over indefinitely; "
 "it does not buy a better average. So measure first, and if one producer really is losing, the usual fix is a separate "
 "queue for it or a bigger capacity, not the flag.",
 X("fairness and starvation", "why bound at all")),
("Now it has to survive a restart. And why did we bound it in the first place?", "twist", 8,
 "Bounding is the answer to the second question: an unbounded queue does not remove the mismatch between a fast producer "
 "and a slow consumer, it hides it in the heap until the process dies &mdash; 200 items a second of surplus is 720,000 "
 "items an hour. A bound converts that into the producer waiting, which is the system telling the truth, and the "
 "capacity you pick is a latency budget: depth divided by drain rate. Durability is the same two cursors with the array "
 "replaced by an append-only file. Put appends and returns only once the write is durable; take reads at the committed "
 "offset; and the offset is committed only <i>after</i> the consumer's work succeeded. That order is the design: a crash "
 "in between replays the last item, so delivery is at-least-once and consumers must be idempotent, and exactly-once "
 "needs the work and the offset in one transaction. At that point you have described a message broker, which is the "
 "right thing to say next.",
 X("surviving a restart", "Runs every extension")),
("Which pattern is where, which SOLID letter is where, and why is OverflowPolicy not just an enum?", "design", 5,
 "The tables on page 02 moves 10 and 11 are the answer; the snippet below is the sixty-second spoken version, one line "
 "per name. Two things are worth adding. The first is the question interviewers use to see whether you actually "
 "understand Strategy: why is what-happens-on-full not an <code>enum {BLOCK, DROP_OLDEST, REJECT}</code> with a "
 "<code>switch</code> inside <code>put</code>? Because each of those is behaviour, not a label &mdash; blocking has to "
 "call <code>awaitRoom</code>, drop-oldest has to evict, and the next one somebody asks for will want state of its own, "
 "like a count of how many it dropped. An enum puts all of that inside the queue and makes every new rule an edit to "
 "<code>put</code>; a one-method interface makes it a new file. Use an enum when the values really are just names, like "
 "an event type. The second is Factory and Builder: Factory earns its place the day capacity, policy and store arrive as "
 "strings from configuration; Builder never does here, because the constructor takes two arguments.",
 "// Monitor object: private state, one lock, and every path in takes it\n"
 "private final ReentrantLock lock;\n"
 "private final Condition notFull, notEmpty;      // two crowds, so a signal can be aimed\n\n"
 "// Strategy, twice: what \"full\" means, and how items are held\n"
 "interface OverflowPolicy<T> { boolean onFull(BoundedBlockingQueue<T> queue, T item) throws InterruptedException; }\n"
 "interface Store<T> { void add(T item); T poll(); boolean isFull(); boolean isEmpty(); int size(); int capacity(); }\n"
 "void configure(OverflowPolicy<T> policy, Clock clock) { this.onFull = policy; this.clock = clock; }\n\n"
 "// Decorator: the same interface, wrapped, so measurement never opens the queue\n"
 "final class MeteredBuffer<T> implements BlockingBuffer<T> { private final BlockingBuffer<T> inner; }\n\n"
 "// Observer: announced after the unlock, and a broken listener cannot break a handoff\n"
 "private void publish(String what, int size) {\n"
 "    for (QueueObserver o : observers) try { o.onEvent(what, size); } catch (RuntimeException ignored) { }\n"
 "}\n\n"
 "// State: the while loop IS the state machine -- a wake goes back to the check, never to the write\n"
 "while (store.isFull() && !closed) { parks.incrementAndGet(); notFull.await(); }\n\n"
 "// Factory: not yet. It earns the name the day this line comes from configuration\n"
 "new BoundedBlockingQueue<>(new RingBuffer<>(64), false);\n"),
]

build(dict(
    slug="mt-blocking-queue", title="Bounded Blocking Queue",
    subtitle="LLD &middot; multi-threading &middot; Java &middot; OpenJDK 21: demo, 23 failure tests and a 100,000-item race pass",
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
