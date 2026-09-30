# Pub/Sub LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"pubsub/Main.java").read_text()
ext   = (H/"pubsub/Extensions.java").read_text()
tests = (H/"pubsub/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def nc(s):
    """drop a class's closing brace when a sect() ran to the end of that class"""
    lines = s.rstrip().split("\n")
    while lines and lines[-1] == "}": lines.pop()
    return "\n".join(lines) + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
# what the code must do: publish, deliver, and the reads as a line
pf = _D
rows = [("publish", 30, [("a thread calls publish", "topic, key, payload"),
                         ("take the topic's lock", "offset = tail"),
                         ("store in the ring, signal", "one step: nobody else is inside"),
                         ("unlock, then tell listeners", "a slow listener stalls nobody")]),
        ("deliver", 165, [("one thread per subscriber", "reads at its own cursor"),
                          ("run the handler, no lock held", "it is allowed to throw"),
                          ("retry, then park if hopeless", "the policy decides, not the broker"),
                          ("only now: cursor + 1", "commit AFTER the handler")])]
for lab, y, boxes in rows:
    pf += _tx(78, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 165 + k*262
        pf += _bx(x, y, 242, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+242, y+27, x+262), True)
for x0, y0, w0, txt in [(430, 95, 340, "a publish never waits for a subscriber"),
                        (395, 230, 440, "still failing: parked, and the cursor moves on")]:
    pf += _ar("M%s %s V%s" % (x0 + w0/2, y0-11, y0), dash=True) + _bx(x0, y0, w0, 40, txt, "", dash=True)
pf += _tx(78, 300, "read", "var(--acc)", 13) + _tx(165, 300, "at any moment, without touching a message: how far behind is this subscriber?   what is at offset 91,204?   who listens to orders?", "var(--text)", 12, "start")
pf += _tx(78, 332, "stop", "var(--acc)", 13) + _tx(165, 332, "unsubscribe(id): interrupt the thread wherever it is parked, commit nothing that was in flight, let a replacement read it again", "var(--text)", 12, "start")
pf += _tx(615, 366, "fifty publishers at the same instant: every offset is handed out exactly once, and no cursor skips a message that was never given to its handler", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 382, pf)

# one morning, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:00:00.000  the burst", ["50 threads publish 2,000 orders", "offsets 0 .. 1999, none issued twice",
                                   "tail = 2000; the ring holds all 2,000", "no publisher waited for a subscriber"], True),
      ("09:00:00.004  three readers", ["audit at 2000, email at 2000", "fraud at 1412: it is 588 behind",
                                       "one log, three cursors", "not three copies of anything"], False),
      ("09:03:11  fraud's handler throws", ["waits 10 ms, 20 ms, 40 ms, gives up", "orders@1584 parked, with the reason",
                                            "cursor moves to 1585 anyway", "giving up must not stall a reader"], True),
      ("09:40:00  fraud restarts", ["resumes at the offset it committed", "the ring overwrote 400 under it",
                                    "skips ahead, and 400 is COUNTED", "a loss you can see, not a silent one"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 258, 128, t, lines, acc=acc)
P_EX = _mv(1230, 200, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>A broker holds named topics; anybody can publish to one without knowing who is listening.</li>
<li>Many subscribers per topic, and every one of them gets every message: fan-out.</li>
<li>Each subscriber keeps its own read position (its cursor), so a slow one falls behind instead of blocking anyone.</li>
<li>A late subscriber can start at the end, or replay whatever history the topic still holds.</li>
<li>A handler is allowed to fail: retry it by a rule, and park what can never work.</li>
<li>Pause, resume, seek, unsubscribe, and report how far behind each subscriber is.</li>
<li>A subscription can carry a filter, so it sees a slice of the topic and skips the rest.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many publishers at once: no offset duplicated, none skipped, and each publisher's own order kept.</li>
<li>Publish is O(1) and read-by-offset is O(1); lag is one subtraction, never a scan.</li>
<li>Per-subscriber order: a subscriber sees a topic's messages in the order they were published.</li>
<li>One slow or throwing handler stalls no publisher and no other subscriber.</li>
<li>Bounded memory per topic: a ring of fixed size, and what it overwrites is counted, not hidden.</li>
<li>Retry rule, dead-letter destination and time are all swappable without touching the log.</li>
<li>In memory, one process, nothing survives a restart (say it; a follow-up adds a store).</li></ul></div></div>
'''

PROMPT = ('"Design an in-process pub/sub system. Publishers post messages to named topics and subscribers get '
          'them without the two ever knowing about each other &mdash; many publishers, many subscribers, and a '
          'handler that is allowed to fail. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>One part of a program wants to announce that something '
 'happened: an order was placed, a file arrived. Other parts want to hear about it, and the announcer must not need to '
 'know who they are or how long they take. Messages go to a named <b>topic</b>; anybody can subscribe to a topic '
 'and is then handed every message published to it, in order. A subscriber can be slow, can start an hour late, can '
 'crash and come back, and can fail on one particular message. None of that may hurt the publisher or any other '
 'subscriber. The thing that must always be true is about <b>offsets</b>. Every message gets a position, its offset, '
 'in its topic\'s log: the list of messages that is only ever appended to. Offsets are handed out one at a time, with '
 'no duplicate and no gap. A subscriber\'s cursor (its read position) never moves past a message its handler was not '
 'given. Everything else hangs off that one decision: retries, dead letters (messages given up on and parked), '
 'replay, and lag (how far behind a subscriber is).</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that publishes, fans out to several subscribers and survives a handler that throws. The '
 'interviewer is watching for, in this order: the questions you ask before typing; which classes exist and which one '
 'owns the log; a publish and a delivery end to end; what happens when two threads publish at the same instant; where '
 'the rule that will change (how to retry) lives, so a new one is a class and not an edit; and what the cursor does '
 'when a handler fails. The first three questions are fan-out (every subscriber gets every message) or competing '
 'consumers (each message goes to one worker), push or pull, and at-most-once or at-least-once. At-most-once means a '
 'message is never handled twice, but can be lost. At-least-once means it is never lost, but can be handled twice, so '
 'the handler must be idempotent: handling a message twice has the same effect as handling it once. Then the twists: '
 'consumer groups (workers that share one stream of messages), consumers that pull, a consumer that is down for an '
 'hour, dead-letter topics, back-pressure (making publishers wait when readers fall behind), persistence, and "so how '
 'is this different from Kafka?"</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Fan-out, or competing consumers: does everyone get every message, or does each message go to one worker?</td><td>Fan-out; groups are a follow-up</td><td>A cursor per subscriber, not a queue per subscriber (moves 1, 5)</td></tr>'
 '<tr><td>Push or pull: do we call each subscriber\'s handler, or does the subscriber call consume() and then ack()?</td><td>Push, one thread per subscriber; pull is follow-up 10 (Razorpay\'s version)</td><td>Who runs the read loop: Subscription.run(), or the consumer itself (moves 2, 6)</td></tr>'
 '<tr><td>At-most-once or at-least-once? It is one line, so let us pick it on purpose.</td><td>At-least-once; handlers are idempotent</td><td>Where <code>cursor + 1</code> sits relative to the handler call (move 6)</td></tr>'
 '<tr><td>Does a late subscriber see history? May a message be dropped before a slow subscriber has read it?</td><td>Yes, what the ring still holds; a drop is counted (Razorpay says never drop: follow-up 7)</td><td>A ring per topic (a fixed array used in a circle: the newest message overwrites the oldest), not delete-on-read (moves 5, 6)</td></tr>'
 '<tr><td>Must a subscriber see one topic\'s messages in order?</td><td>Yes, per topic per subscriber</td><td>One dispatcher thread (the thread that reads for one subscriber) per subscription (moves 4, 7)</td></tr>'
 '<tr><td>What happens to a message that can never be processed: drop, block, or park?</td><td>Retry a few times, then park it</td><td>A retry rule and a dead-letter sink, both handed in (move 3)</td></tr>'
 '<tr><td>How many publishers at once, and how many subscribers per topic?</td><td>Tens of threads, tens of subscribers</td><td>One lock per topic is enough; the ladder is named, not climbed (moves 4, 8)</td></tr>'
 '<tr><td>Does anything survive a restart?</td><td>No: one process, in memory</td><td>No store yet; a follow-up slots one in behind an interface (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> push, fan-out, at-least-once, so handlers must be idempotent. One log '
 'per topic, a ring of fixed size, with a cursor per subscriber rather than a queue per subscriber; what the ring '
 'overwrites is counted. One thread per subscription, so each subscriber gets the topic\'s order for free. In memory, '
 'one process. Named as out of scope: consumer groups, consumers that pull, a guarantee for a consumer that is down, persistence, '
 'exactly-once &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a PUBLISHER puts a MESSAGE on a TOPIC; a SUBSCRIPTION reads it at its own OFFSET and hands it to a HANDLER; a RETRY RULE decides what happens when it fails", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 175, "Message", "immutable: a record", 1), (220, 185, "Topic", "log, offsets, one lock", 1),
                          (420, 200, "Subscription", "cursor, thread, state", 1), (635, 165, "Broker", "the maps, the threads", 1),
                          (815, 150, "Handler", "no state: an interface", 0), (980, 105, "Publisher", "a caller", 0),
                          (1100, 110, "Lag", "a question", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a caller, an interface, or a number a method computes", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("give a message its position", "Topic  (owns the log and the offsets)", "topic.append(key, payload, ...)"),
                                       ("remember how far I have read", "Subscription  (owns one cursor)", "cursor.incrementAndGet()"),
                                       ("hand it over and survive a throw", "Subscription  (owns the thread too)", "deliver(m): boolean"),
                                       ("find the topic, start the thread", "Broker  (owns the maps)", "broker.publish / subscribe")]):
    y = 22 + k*54
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 258, "and notice the verb that is NOT here: \"send it to everybody\". There is no fan-out loop and no copying:", "var(--muted)", 11)
m2 += _tx(615, 277, "fan-out is three subscriptions reading one log at three positions; a fourth adds a cursor and a thread, never a copy", "var(--acc)", 11)
MV[2] = _mv(1230, 290, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(24, 76, 250, 90, "Broker / Subscription", "configure(...), SubscribeOptions", acc=True)
for k, (t, sub, impl) in enumerate([("Handler", "the subscriber's own code", "any lambda:  m -> charge(m.payload())"),
                                    ("RetryPolicy", "again, and how long?", "FixedDelayRetry / ExponentialBackoff / NoRetryFor"),
                                    ("DeadLetterSink", "where a hopeless message goes", "InMemoryDeadLetters, or a .dlq topic"),
                                    ("Filter / BrokerListener / Clock", "who sees what, who is told, the time", "a lambda each: they have one method")]):
    y = 20 + k*58
    m3 += _ar("M274 121 H330 V%s H390" % (y+22), True, True) + _bx(390, y, 300, 44, t, sub, dash=True)
    m3 += _bx(750, y, 450, 44, impl, "handed in, never built inside") + _ar("M750 %s H690" % (y+22))
m3 += _tx(615, 268, "dashed = handed in. The broker never writes new on a rule, so a new backoff is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 288, "and one rule wraps the others: BoundedRetry(policy) forces EVERY policy, including next year's, to give up eventually", "var(--acc)", 11)
MV[3] = _mv(1230, 300, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 26, 190, 44, "thread A", "reads tail = 7") + _bx(30, 106, 190, 44, "thread B", "reads tail = 7")
m4 += _bx(350, 66, 190, 44, "the ring", "tail = 7", acc=True)
m4 += _ar("M220 48 H350 V66") + _ar("M220 128 H350 V110") + _tx(285, 36, "read", "var(--muted)", 10.5) + _tx(285, 156, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="16" width="300" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(730, 42, "the gap", RED, 12) + _tx(730, 66, "both write slot 7: one message", RED, 11) + _tx(730, 86, "is lost, and nothing reports it:", RED, 11) + _tx(730, 106, "offset 7 was handed out twice", RED, 11)
m4 += _tx(730, 136, "fix: assign AND store as ONE step", "var(--text)", 11)
m4 += _bx(910, 40, 290, 96, "Topic.lock", "assign, store, signal", acc=True)
m4 += _tx(615, 186, "the second shared thing is the WAIT: a dispatcher that checks \"anything at offset 7?\", sees nothing and then sleeps can miss a", "var(--muted)", 11)
m4 += _tx(615, 205, "publish that lands in between. So the check and the wait sit inside the SAME lock the publisher signals under, in a while loop.", "var(--muted)", 11)
m4 += _tx(615, 228, "one lock per TOPIC, not per broker: ten thousand topics never wait for each other, and a handler is never inside it", "var(--acc)", 11)
MV[4] = _mv(1230, 242, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is at offset 91,204?", "a ring: Message[],  slot = offset % size", "O(1)"),
                                      ("how far behind is this subscriber?", "AtomicLong cursor, volatile tail;  lag = tail - cursor", "O(1), no lock"),
                                      ("which subscription / which topic?", "ConcurrentHashMap by id", "O(1)"),
                                      ("what did we give up on?", "an append-only list in the sink", "O(1) append")]):
    y = 18 + k*48
    m5 += _bx(30, y, 350, 40, q, "the question") + _ar("M380 %s H430" % (y+20), True)
    m5 += _bx(430, y, 560, 40, shape, "the shape", acc=True) + _ar("M990 %s H1040" % (y+20), True) + _bx(1040, y, 160, 40, cost, "")
m5 += _tx(615, 232, "and the shape that is WRONG here: a queue per subscriber. It copies every message N times, deletes on read, and with that", "var(--muted)", 11)
m5 += _tx(615, 251, "one choice you have thrown away replay, late joiners and any lag number. Cursor, not queue &mdash; everything else hangs off it.", "var(--acc)", 11)
MV[5] = _mv(1230, 264, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D
for x, y, w, t, sub, acc in [(24, 24, 178, "FETCHED", "read under the lock", 0),
                             (242, 24, 178, "DELIVERING", "lock released, handler runs", 1),
                             (24, 112, 178, "ACKED", "the handler returned", 0),
                             (242, 112, 178, "RETRY WAIT", "sleep the backoff", 0),
                             (242, 200, 178, "DEAD-LETTERED", "the policy gave up", 0)]:
    m6 += _bx(x, y, w, 44, t, sub, acc=bool(acc))
m6 += _ar("M202 46 H242", True)                       # FETCHED -> DELIVERING
m6 += _ar("M260 68 V134 H202")                        # DELIVERING -> ACKED
m6 += _ar("M380 68 V112")                             # DELIVERING -> RETRY WAIT
m6 += _ar("M420 134 H444 V46 H424", dash=True)        # RETRY WAIT -> DELIVERING, attempt + 1
m6 += _ar("M331 156 V200")                            # RETRY WAIT -> DEAD-LETTERED
m6 += _tx(222, 272, "ACKED and DEAD-LETTERED both lead to cursor + 1", "var(--acc)", 11)
m6 += '<rect x="460" y="16" width="750" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(835, 40, "the order at delivery, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 read the message at the cursor -- the topic's lock is held only for this",
                       "2 release the lock; run the handler; it may take two seconds and it may throw",
                       "3 on a throw: ask the policy, wait, try again, or park it in the sink",
                       "4 only now: cursor + 1.  The commit is the LAST statement",
                       "a stop in the middle hands the message out again: at-least-once;",
                       "move the increment ABOVE the handler and it is at-most-once. That is the whole difference."]):
    m6 += _tx(475, 64 + k*22, l, "var(--muted)" if k > 3 else "var(--text)", 11, "start")
m6 += _tx(835, 200, "and the subscription has a life too: ACTIVE &harr; PAUSED &rarr; STOPPED, and STOPPED is final", "var(--acc)", 11)
m6 += _tx(615, 294, "publishing has its own order: assign and store before signalling, and tell the listeners only after the unlock", "var(--muted)", 11)
MV[6] = _mv(1230, 308, m6)

# move 7: what is inside the lock, and ten publishers at the same instant (measured: 20 subscribers, laptop, JDK 21)
m7 = _D + _card(30, 20, 545, 152, "inside the topic's lock: about 0.3 microseconds",
                ["read tail, build the message, store it in its slot", "a full ring: that store overwrote the oldest; head + 1",
                 "republish tail and earliest", "signalAll: each waiting subscriber is queued to wake",
                 "no loop over the log and no copy: the same cost at any size"], acc=True)
m7 += _ar("M575 96 H645", True) + _tx(610, 86, "unlock", "var(--acc)", 10.5)
m7 += _card(645, 20, 555, 152, "outside it: microseconds to seconds",
            ["the handler: 50 us in process, up to 2 s over HTTP", "the retry backoff: 10 ms to a minute",
             "the listeners: after the unlock, in a try/catch", "the dead-letter write: a list today, a topic later",
             "none of these can make a publisher wait"])
m7 += _tx(615, 200, "ten threads publish to the same topic at the same instant (20 subscribers; measured, median of 3,000 runs)", "var(--text)", 12)
for k, us in enumerate(["0.2", "0.2", "0.2", "0.3", "0.3", "0.3", "0.3", "0.4", "0.5", "1.0"]):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "thread %d" % (k+1), "done: %s us" % us, acc=(k == 9))
m7 += _tx(615, 283, "the tenth usually finishes in about one microsecond. About one time in ten it had to sleep and be woken, which costs about 0.1 ms.", "var(--muted)", 11)
m7 += _tx(615, 301, "It never waits for a subscriber: no handler, no retry and no listener is ever inside the lock. One at a time is true, and nobody can tell.", "var(--muted)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per topic: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a publish holds the lock ~0.3 us (20 subscribers, measured)",
                       "an order service: 2,000 publishes a second into one topic",
                       "that is 0.7 ms of lock in every second: 0.07% busy",
                       "even a 40,000/s burst is 13 ms a second: 1.3%",
                       "20 subscribers add 20 cursors and 20 threads, not 20 copies"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 partitions: N rings, N locks, key &rarr; partition", "per-key order kept; total order across the topic is the price"),
                              ("2 claim the slot with compare-and-set", "the LMAX Disruptor shape: no lock at all, for millions a second"),
                              ("3 move the log out of the process", "Kafka or Pulsar: when one machine's memory is not enough")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
m8 += _tx(615, 222, "and a second ladder for the readers: one thread per subscription is fine to a few hundred; past that, a fixed pool of threads", "var(--muted)", 11)
m8 += _tx(615, 241, "that still runs each subscription's messages one at a time &mdash; and Subscription does not change: it was always a Runnable with a cursor", "var(--muted)", 11)
MV[8] = _mv(1230, 254, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two threads publish at the same instant", "assign and store as one locked step; test 1: 50 threads, 2,000 distinct offsets"),
                                ("a dispatcher sleeps through a publish", "check and wait under the SAME lock, in a while; test 11: the publish woke it, not the timeout"),
                                ("a handler or its filter throws", "retry by the policy, park it, move the cursor on; tests 5, 14: the cursor still reaches the end"),
                                ("a retry rule never gives up, or throws", "BoundedRetry wraps every policy; test 9: stopped at 20 attempts, or parked at once"),
                                ("the ring outruns a slow reader", "counted (test 6: 11 + 39 = 50), or back-pressure makes the publisher wait (test 17: 0 missed)"),
                                ("one handler takes two seconds", "it runs outside the lock, on its own thread; test 7: six publishes in 0 ms"),
                                ("stop or seek mid-delivery", "commit nothing; apply a seek before the next read; tests 12, 13: cursor still 0, replay from 0"),
                                ("an interrupt that is not a stop()", "an interrupt always means stop; test 15: the thread ends instead of spinning forever")]):
    y = 16 + k*40
    m9 += _bx(30, y, 320, 36, bad, "") + _ar("M350 %s H396" % (y+18), True) + _bx(396, y, 804, 36, fix, "", acc=True)
m9 += _tx(615, 356, "every claim this design makes has a failure test: FailureTests.java runs seventy-five checks and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 370, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 830)]
rows10 = [[("Observer", "var(--text)"), ("move 3", None), ("broker.subscribe(id, topic, handler) -- publish names no subscriber", None), ("the whole point: neither side knows the other", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface RetryPolicy { long backoffMs(attempt, failure); }", None), ("a new retry rule is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new BoundedRetry(policy, 20, 60_000) wraps EVERY policy", None), ("no rule, present or future, retries forever", None)],
          [("Iterator", "var(--text)"), ("move 5", None), ("the cursor: one AtomicLong per subscription over one log", None), ("a fourth subscriber adds a cursor, not a copy", None)],
          [("State", "var(--text)"), ("move 6", None), ("SubState, and the delivery order: read, deliver, THEN commit", None), ("at-least-once is one visible line", None)],
          [("Builder", "var(--text)"), ("move 3", None), ("opts().fromEarliest().retry(p).filter(f) -- five optional knobs", None), ("the rare LLD where it truly earns its place", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the broker is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh broker per case", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("topics appear via topics.computeIfAbsent(name, ...), one line", "var(--muted)"), ("it earns the name when a topic needs a config", "var(--muted)")],
          [("Command", "var(--muted)"), ("never", None), ("no move produced one: a message is data, not an instruction", "var(--muted)"), ("a pattern without a move is decoration", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 335, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 350, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 430), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Topic: the log. Subscription: one cursor, one handler. RetryPolicy: again or not.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("ExponentialBackoff, NoRetryFor, a .dlq sink, a FileStore: each one a new class", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("retry.backoffMs(attempt, e);  a negative answer means give up, from any policy", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Handler, Filter, DeadLetterSink, BrokerListener, RetryPolicy: each can be a lambda", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("opts().retry(...).deadLetters(...).filter(...);  broker.setClock(() -&gt; t)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "backoff, a filter, a different sink", "a new class behind the interface, plus one line at subscribe", "", "move 3"),
        ("someone new wants to know", "metrics, a lag alarm, tracing", "one more BrokerListener; the log and the cursors do not move", "", "move 3"),
        ("a new step in a life", "paused, draining, quarantined", "one more SubState and one more checked transition", "", "move 6"),
        ("a new invariant across readers", "each message handled by exactly one worker", "the same log, one filter per group member: consumer groups", "", "moves 3 + 5"),
        ("state that must outlive the process", "persist it; then two processes", "the log behind a MessageStore and the cursor behind an OffsetStore;", "append becomes a write to a file on disk; commit becomes an offset commit", "moves 5 + 12")]):
    y = 22 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 308, "for all five the Topic, the cursor and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 322, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>publisher</b> puts a <b>message</b> on a <b>topic</b>; a <b>subscription</b> "
 "reads it at its own <b>offset</b> and hands it to a <b>handler</b>; a <b>retry rule</b> decides what happens when "
 "the handler fails. A topic has a log, a next offset and a lock, all of which change: a class, and the one that "
 "matters. A subscription has a cursor, a thread and a state: a class. A message never changes once published, so it "
 "is a record. It must be immutable for a real reason, not for tidiness: one object sits in the log and is handed to "
 "twenty handlers on twenty threads at once. A broker has the map of topics and the map of subscriptions: a class. A "
 "handler has no state at all, so it is an interface. A publisher is not a class here; it is whoever calls "
 "<code>publish</code>. And an offset is not a class either: it is a long, on the message and on the cursor.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "The table is mechanical once the question is put the right way round: a verb goes to whoever owns the state it "
 "touches. Giving a message its position touches the log and the next offset, so it is the topic's. Remembering how "
 "far I have read touches one cursor, so it is the subscription's, and so is <code>deliver</code>, because whether "
 "that cursor moves is the whole question. What matters here is the verb that is <i>not</i> in the list: \"send it to "
 "everybody\". There is no fan-out loop anywhere in this design, and nothing is ever copied. Fan-out is three "
 "subscriptions reading one log at three different positions. A fourth subscriber adds one cursor and one thread, "
 "never another copy of the messages.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "How to retry will change. Twenty minutes in they will say: \"a flat twenty milliseconds hammers a struggling "
 "downstream; back off exponentially, and never retry a message that can never work\". Where a hopeless message goes "
 "will change: a list today, a dead-letter topic tomorrow. Who is told will change: metrics, a lag alarm, a trace, "
 "each one a listener. "
 "What a subscriber sees will change: a filter. Each becomes a one-method interface that the subscription is "
 "<i>given</i> and never builds. This is where the patterns come from, not the other way round. A swappable rule "
 "behind an interface is <b>Strategy</b>. A rule that wraps another rule and adds to it is <b>Decorator</b>. The one "
 "that matters here is <code>BoundedRetry</code>, which the broker wraps around every policy it is handed. So a rule "
 "written next year cannot retry a poison message (one that fails every time) forever. A broker that announces \"a "
 "message landed\" without knowing what a metrics system is, is <b>Observer</b>, and in this system Observer is the "
 "product itself. The names come later, in move 10; what matters here is that every rule is a separate object you "
 "can swap.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two threads publish at the same instant. Assigning an offset and storing at it are two operations: both read "
 "<code>tail</code> as 7, both write slot 7, and one message is simply gone. So the two operations happen as one step, "
 "inside a lock owned by the class that owns the log: the topic. The second shared thing is less obvious, and it is "
 "the one that separates a good answer from a great one: the <i>waiting</i>. A dispatcher asks \"is there anything at "
 "offset 7?\", sees nothing, and goes to sleep. A publish that lands between the question and the sleep is missed: a "
 "lost wakeup. So the check and the wait sit inside the same lock the publisher signals under, in a <code>while</code> "
 "loop. The loop also makes a spurious wakeup (a wake-up with no signal, which Java allows) harmless. The lock is per "
 "<i>topic</i>, and no handler, no retry and no listener is ever inside it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What is at offset 91,204?\" is a ring: a fixed array used in a circle. Offset o sits in slot o % size (the "
 "remainder after dividing by the size), so finding a message is one step, O(1). A new message on a full ring simply "
 "overwrites the oldest one: no copying, ever. \"How far behind is this subscriber?\" is one AtomicLong per "
 "subscription, and lag is tail minus cursor: O(1), never a scan of anything. The tail needs one extra line of care. "
 "The topic keeps it in a <code>volatile long</code> (a field every thread reads fresh, without a lock) that "
 "<code>append</code> rewrites inside the lock. So a dashboard asking a thousand subscribers for their lag reads a "
 "field and never queues behind a publisher. \"Which subscription, which topic?\" are concurrent hash maps by id. "
 "\"What did we give up on?\" is an append-only list in the sink. But the shape worth arguing about is the one you do "
 "<i>not</i> pick: a queue per subscriber. It copies every message once per subscriber and deletes on read, and with "
 "that one choice you have thrown away replay, late joiners and any lag number for a dashboard. One log, N cursors: "
 "every other decision hangs off that one. The price is stated honestly: the ring has a fixed size, so a subscriber "
 "that falls too far behind loses messages, and the loss is counted.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "One message's trip through one subscription starts FETCHED, under the topic's lock, and becomes DELIVERING once the "
 "lock is released. Then it is ACKED if the handler returns, or goes to RETRY WAIT and back to DELIVERING, or ends "
 "DEAD-LETTERED when the policy gives up. "
 "ACKED and DEAD-LETTERED both lead to the same place, <code>cursor + 1</code>. Giving up must never stall a "
 "subscription: a reader stuck forever on one bad message is the commonest bug in a hand-written bus. That gives the "
 "order. Read at the cursor, with the lock held only for the read. Release it. Run the handler, which may take two "
 "seconds and may throw. Retry or park. Only then move the cursor: that is the commit. The commit is the last "
 "statement, and that is the delivery guarantee written down. A stop in the middle hands the message out again, so "
 "this is at-least-once, and handlers must be idempotent. Move the increment above the handler call and you have at-most-once, which is the "
 "right choice for a metrics ping. One line, the whole difference: say which one you picked before you write the "
 "loop. The subscription has a life of its own too: ACTIVE to PAUSED and back, then STOPPED, which is final. Each "
 "change happens under the subscription's own small lock, so a late pause() cannot bring a stopped subscription back.", 6),
("Move 7: yes, the lock makes one topic's publishes happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every publish takes the topic's lock, is this a queue "
 "with extra steps? It is, for about a third of a microsecond. The left-hand card is everything that happens in "
 "there, and none of it is slow. There is no loop over the log and no copying, so the cost is the same at ten "
 "messages or ten million. The only part that grows is <code>signalAll</code>, which touches each waiting subscriber "
 "once. Everything slow is on the other side of the unlock: the handler, the backoff, the listeners. Measured with "
 "twenty subscribers, the tenth of ten simultaneous publishers usually finishes in about one microsecond. About one "
 "time in ten it has to sleep and be woken by the operating system, which costs about a tenth of a millisecond. It "
 "never waits for a subscriber at all, and that is the property publishers actually care about.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Say the number before you say the design. With twenty subscribers a publish holds the topic's lock for about a "
 "third of a microsecond (measured on a laptop). An order service publishing two thousand messages a second into "
 "one topic holds that lock for 0.7 milliseconds in every second: busy 0.07% of the time. Even a burst of forty "
 "thousand a second is 1.3%. The lock is per topic, so the number of topics does not matter. Memory is the other "
 "number to say out loud: ten thousand retained messages at about two hundred bytes is two megabytes per topic. "
 "Twenty subscribers add twenty cursors and twenty threads, not twenty copies. Only then the ladder, and notice how "
 "little each rung disturbs. Partitions (N rings behind one topic name, the message key picking the ring) change only "
 "which ring a key lands in. Per-key order is kept and total order across the topic is given up, which is exactly "
 "the trade Kafka makes. Claiming slots with compare-and-set (one CPU instruction that writes only if the value is "
 "still the one you read) drops the lock. It is worth it only at millions a second. Moving the log out of the process is the last rung, and that is Kafka. The readers have their "
 "own rung: a fixed pool of threads that still runs each subscription's messages one at a time. Subscription does not "
 "change for it, because it was always a Runnable with a cursor. Climbing either ladder without the arithmetic is "
 "complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Two threads publishing at the same instant: fifty of them, and every offset must be distinct. A dispatcher sleeping "
 "through a publish, the lost wakeup. Its test is the sharp one, because a weak test cannot tell the fix from the bug. "
 "Park a reader on an empty topic with a five-second budget and publish sixty milliseconds later: it must come back "
 "in about sixty milliseconds. If it comes back after five seconds, the signal was lost and only the timeout saved "
 "you. A handler or a filter that throws, and a retry rule that never gives up or throws itself: retry, park, and the "
 "cursor must still reach the end. The ring outrunning a slow subscriber: eleven delivered plus thirty-nine missed "
 "must be exactly fifty, and with back-pressure nothing may be missed at all. One handler that takes two seconds, and "
 "a metrics listener that throws: neither may cost a publisher anything. A stop or a seek while a message is in the "
 "handler: the stop commits nothing, and the replay starts exactly where it was asked to. An interrupt that nobody "
 "meant as a stop still ends the thread, instead of leaving it spinning. Each is a few lines in FailureTests.java, "
 "which runs seventy-five checks; a design that cannot show its tests is only making claims.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; what it cannot show is the order things happened in. Every name in it was earned by a move "
 "and written down afterwards, which is why each has a line of code beside it instead of a paragraph of defence. Two "
 "are worth saying out loud in the room. Observer is not a pattern this design uses; it is what the design "
 "<i>is</i>: <code>publish</code> names a topic and has never heard of a subscriber. And Builder, which is decoration "
 "in most LLDs, earns its place here: <code>SubscribeOptions</code> has five settings and all five are optional, "
 "which is exactly what a five-argument constructor handles badly. The bottom three rows are worth as much as the top "
 "six. Naming a pattern no move produced is decoration, and \"not yet, and here is what would change my mind\" is a "
 "stronger answer than a name.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is a check, not a recitation. Every letter has to point at a move and at a line of this code. A letter "
 "that cannot point at one is telling you something about the design, not about the acronym. The row to say out loud "
 "is D, because it is what makes the tests possible at all. The subscription is handed its policy, its sink, its "
 "filter and its clock, and never writes <code>new</code> on any of them. That is why a test can hand it a clock that "
 "runs a five-minute backoff schedule in no time, and a policy that never gives up.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Four of the five are small. A new rule is a new class behind an existing interface, plus one line at the subscribe "
 "call. Someone new who wants to know is one more listener, and the log and the cursors do not move. A new step in a "
 "life is one more state and one more checked transition. A new invariant across readers (a rule that must always "
 "hold; here, each message handled by exactly one worker instead of all of them) is consumer groups. It needs no new "
 "broker code, because it is the same log with one filter per member. The fifth sounds big and is not. The log goes "
 "behind a <code>MessageStore</code> and the cursor behind an <code>OffsetStore</code>. The append becomes a write to "
 "a file on disk, the commit becomes an offset commit, and every class keeps its name. That is why \"explain "
 "Kafka\" and \"explain this file\" turn out to be the same explanation at two sizes. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, BookMyShow) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On this problem one decision carries everything: one append-only log per topic "
 "with a cursor per subscriber, instead of a queue per subscriber. Get that in move 5 and replay, late joiners, lag and "
 "cheap fan-out are all free; get it wrong and no amount of later cleverness buys them back.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the caller and the one-method interfaces it supplies
put("caller", 10, 20, 235, "your code", ["a publisher thread", "a subscriber's handler"],
    ["broker.publish(topic, key, body)", "broker.subscribe(id, topic, h)"])
put("handler", 10, 160, 235, "Handler", [], ["onMessage(m) throws Exception"], "interface")
put("filter", 10, 240, 235, "Filter", [], ["accepts(m): boolean", "static all()"], "interface")
put("clock", 10, 335, 235, "Clock", [], ["nowMs(): long", "sleepMs(ms)   (default)"], "interface")
put("listener", 10, 430, 235, "BrokerListener", [], ["onEvent(Event e)"], "interface")
# centre column: the owner, the aggregate root, and the reader
put("broker", 310, 20, 330, "Broker",
    ["topics: Map&lt;String, Topic&gt;", "subs: Map&lt;String, Subscription&gt;", "dispatchers: ExecutorService",
     "listeners: List&lt;BrokerListener&gt;", "defaultRetry / defaultSink / clock"],
    ["configure(retry, sink)", "publish(topic, key, payload): long", "subscribe(id, topic, handler, opts)",
     "unsubscribe(id) / close()", "lag(id) / lagReport() / subscribersOf(t)", "topic(name) / slowestCursor(t)"])
put("topic", 310, 275, 330, "Topic",
    ["name: String", "ring: Message[]   slot = offset % size", "head: long   (oldest still held)",
     "lastAtMs: long   (time never goes back)", "tail / earliest: volatile long", "lock: ReentrantLock", "appended: Condition"],
    ["append(key, payload, hdrs, atMs)", "readAt(offset) / clamp(offset)", "awaitAt(offset, timeoutMs)",
     "tailOffset() / earliestOffset()", "capacity() / droppedCount() / retained()"])
put("sub", 310, 530, 330, "Subscription   (Runnable)",
    ["id: String,  topic: Topic", "handler: Handler", "cursor / seekTo: AtomicLong", "state (volatile),  gate: lock",
     "retry / sink / filter / clock", "delivered / deadLettered / missed"],
    ["run()  -- the dispatch loop", "deliver(m): boolean", "pause() / resume() / stop()", "lag() / seek(off) / offset() / running()"])
# third column: the values and the enums
put("event", 690, 20, 225, "Event", ["type: EventType", "topic / subscriptionId", "offset: long,  attempts: int"], [])
put("etype", 690, 135, 225, "EventType", ["PUBLISHED, DELIVERED,", "RETRIED, DEAD_LETTERED,", "SKIPPED, FAST_FORWARDED"], [], "enum")
put("msg", 690, 250, 225, "Message", ["offset: long", "topic / key / payload", "headers: Map&lt;String,String&gt;", "atMs: long"], [])
put("dead", 690, 385, 225, "Dead", ["message: Message", "subscriptionId: String", "attempts: int,  reason: String", "atMs: long"], [])
put("substate", 690, 520, 225, "SubState", ["ACTIVE, PAUSED, STOPPED"], [], "enum")
# fourth column: the rules that are handed in
put("rp", 960, 20, 255, "RetryPolicy", [], ["backoffMs(attempt, failure)", "  : long   (&lt; 0 = give up)"], "interface")
put("bounded", 960, 115, 255, "BoundedRetry", ["base: RetryPolicy (wrapped)"], ["wraps ANY policy and", "caps attempts + backoff"])
put("fixed", 960, 215, 255, "FixedDelayRetry", [], ["the same wait, n times"])
put("expo", 960, 290, 255, "ExponentialBackoff", [], ["base &lt;&lt; (attempt-1), capped"])
put("dls", 960, 380, 255, "DeadLetterSink", [], ["park(Dead d)"], "interface")
put("imdl", 960, 455, 255, "InMemoryDeadLetters", [], ["park(d) &rarr; a list", "all() / size()"])
put("opts", 960, 560, 255, "SubscribeOptions", ["retry / sink / filter", "startAt: long,  earliest: boolean"],
    ["opts()  -- a fresh set", "retry(r) / deadLetters(s) / filter(f)", "fromEarliest() / fromOffset(n)"])

EDGES = [
 # the caller reaches the broker
 ln(B["caller"]["r"], (310, 129), "assoc", ""),
 # the broker owns its topics, its subscriptions and its threads
 ln(B["broker"]["b"], B["topic"]["t"], "compose", "owns, by name"),
 ln((310, 180), (310, 631), "compose", "", [(300, 180), (300, 631)]),
 ln((310, 129), (245, 457), "notify", "", [(290, 129), (290, 457)]),
 # the subscription is handed its handler, its filter and its clock
 ln((310, 631), (245, 187), "inject", "", [(258, 631), (258, 187)]),
 ln((310, 660), (245, 275), "inject", "", [(270, 660), (270, 275)]),
 ln((310, 690), (245, 370), "inject", "", [(282, 690), (282, 370)]),
 # a subscription reads a topic it does not own; the topic owns the log
 ln((640, 631), (640, 392), "assoc", "", [(655, 631), (655, 392)]),
 _tx(662, 500, "reads by offset;", "var(--muted)", 10.5, "start"),
 _tx(662, 516, "many share one", "var(--muted)", 10.5, "start"),
 ln(B["topic"]["r"], B["msg"]["l"], "compose", "", [(670, 392), (670, 299)]),
 ln((640, 570), (690, 545), "assoc", ""),
 # the values
 ln(B["etype"]["t"], B["event"]["b"], "assoc"),
 ln(B["dead"]["t"], B["msg"]["b"], "assoc", "carries"),
 ln(B["broker"]["r"], B["event"]["l"], "assoc", "", [(668, 129), (668, 61)]),
 # the rules are handed in
 ln((640, 700), B["dls"]["l"], "inject", "", [(930, 700), (930, 407)]),
 ln((640, 715), B["rp"]["l"], "inject", "", [(945, 715), (945, 55)]),
 ln(B["opts"]["b"], B["sub"]["b"], "inject", "", [(1087, 748), (475, 748)]),
 _tx(925, 690, "the rules, handed in", "var(--acc)", 10.5, "end"),
 _tx(700, 742, "the options a caller builds, read once at subscribe", "var(--acc)", 10.5, "start"),
 # the policies and the sink
 ln(B["bounded"]["t"], B["rp"]["b"], "inherit"),
 ln((960, 152), (960, 55), "assoc", "", [(950, 152), (950, 55)]),
 ln(B["fixed"]["l"], B["rp"]["l"], "inherit", "", [(938, 242), (938, 55)]),
 ln(B["expo"]["l"], B["rp"]["l"], "inherit", "", [(928, 317), (928, 55)]),
 ln(B["imdl"]["t"], B["dls"]["b"], "inherit"),
 ln(B["dls"]["l"], B["dead"]["r"], "assoc", "", [(940, 407), (940, 434)]),
]
UMLSVG = uml_svg(1230, 800, EDGES, legend_y=778)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the broker owns its topics and its subscriptions, and a topic owns its ring of '
 'messages. Plain arrow = references: a subscription points at a topic it does <i>not</i> own, because many '
 'subscriptions share one topic and stopping one must not close it. Dashed green = handed in. Dotted blue = '
 'notifies. <b>Where state lives:</b> the topic has the ring, the head and tail offsets and the one lock, and nothing '
 'else in the system writes an offset. A subscription has one cursor, plus a seek waiting to be applied, its thread, '
 'its state and its counters. The broker has the two maps and the thread pool, and no lock at all. A retry policy and '
 'a filter have no state, which is why one instance can serve every subscription. Notice what is <i>not</i> here: no '
 'queue anywhere, and no list of subscribers on the topic. A topic does not know who is reading it; the cursors do all '
 'the work, which is the whole design in one sentence.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does: read only those first for the shape, then the bodies for the mechanics. When you '
 'get to <code>Subscription.run()</code>, read the last two statements of the loop slowly, because they are the delivery '
 'guarantee. Each copy button copies that whole file for your IDE. Below Main.java, Extensions.java holds every '
 'follow-up\'s reference code, with an <code>ExtDemo</code> main that runs all of it. FailureTests.java holds seventy-five '
 'checks proving the claims of move 9; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> '
 'prints ALL PASS.')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (fan-out or competing consumers, push or pull, and '
 'at-most-once or at-least-once come first). The must-write core is about 150 lines: Message, Handler, Topic with its '
 'lock, append and awaitAt, Subscription with its dispatch loop and the commit as the last statement, a thin Broker with '
 'publish, subscribe and unsubscribe, and a main with fifty publishing threads. Amazon\'s 30-minute version (event '
 'types, subscribe, unsubscribe, every subscriber receives) is that core alone. Then add what the interviewer asks for, '
 'in the order of Main.java: the retry policies and the BoundedRetry wrapper, the dead-letter sink, the filter, pause '
 'and seek, the listeners, and SubscribeOptions. If the statement says subscribers call consume() and ack() '
 '(Razorpay\'s version), keep the log and the cursors and write follow-up 10 instead of the thread.</div></div>')

FU = [
("Twenty minutes in: \"back off exponentially instead of a flat 20 ms, and never retry a message that can never work.\"", "twist", 10,
 "Two changes, both new classes, and nothing inside Topic, Subscription or Broker moves. ExponentialBackoff starts at "
 "the base, doubles the wait after each failure up to a cap, and gives up after n attempts: with a base of 10 ms and "
 "four attempts, it waits 10 ms, 20 ms and 40 ms, then stops. \"Never retry a message that can never work\" is a wrapper rather than a new policy. NoRetryFor "
 "holds any policy and answers &minus;1 (give up) the moment the failure is of a type you declared permanent, so it "
 "composes with the backoff instead of replacing it. The call site is one line: "
 "<code>opts().retry(new NoRetryFor(new ExponentialBackoff(6, 10, 1000), PermanentFailure.class))</code>. It was cheap "
 "because the failure is passed to the policy, so telling a timeout from a malformed payload never needed a new "
 "signature. Where the given-up message goes is the other interface. DeadLetterTopic publishes it to "
 "<code>orders.dlq</code> with the reason in its headers, so the repair tool is just another subscriber and a replay is "
 "just another publish.",
 sect(src, "final class ExponentialBackoff", "final class BoundedRetry") + "\n" + X("never retry a message that can never work", "exactly-once for the handler")),
("Fifty threads publish to one topic at the same instant. Prove you cannot duplicate or lose an offset, with a test.", "non-functional", 10,
 "The race lives between reading the tail and storing at it: two threads both read 7, both write slot 7, and one "
 "message disappears. append does both inside the topic's lock, so no other publisher can run in that gap. The proof "
 "is not a count but a set. Fifty threads wait on one latch, each publishes forty messages, and each collects the "
 "offsets it was handed. The test then checks four things: the two thousand offsets are two thousand distinct "
 "values; the tail is exactly 2000; every offset from 0 to 1999 reads back (no gap); and each publisher's own "
 "offsets increased. A subscriber counting in the background must also have seen all two thousand. Then state the "
 "ordering promise precisely, because they will push on it. Offsets come out in the order the lock handed them out, "
 "so every subscriber sees one topic's messages in exactly that order. Nothing is promised about two independent "
 "publishers: if their order matters, they must be one publisher, or share one key.",
 T("        // 1. fifty threads publish into ONE topic", "        // 2. fan-out")),
("Your dispatch loop says \"if there is nothing at my cursor, wait\". Walk me through what breaks.", "non-functional", 8,
 "Two different bugs, and this design closes both in one method. The first is the <b>lost wakeup</b>. Between the "
 "check that finds nothing and the call that goes to sleep, a publisher can append and signal. The sleeper never "
 "hears it: it waits out its whole timeout, or forever without one. <code>awaitAt</code> closes that gap by doing the "
 "check and the wait inside the topic's own lock, the same lock <code>append</code> signals under, so a publisher "
 "cannot run in between. The second is the <b>spurious wakeup</b>: <code>await</code> may return with nothing having "
 "changed. That is why the check is a <code>while</code> and not an <code>if</code>. On any wakeup it looks at the "
 "ring again, and goes back to sleep if the message is still not there. The fifty-millisecond timeout is not a patch "
 "for either bug. It makes an idle dispatcher look at its own state (paused? a seek waiting?) at least every fifty "
 "milliseconds; stop() does not need it, because stop() interrupts. Test 11 catches a broken version: a reader parked "
 "with a five-second budget must come back about sixty milliseconds after the publish, not after five seconds.",
 nc(sect(src, "    Message awaitAt(", "// \"the knobs are about to multiply\""))
 + "\n" + T("        // 11. the lost wakeup", "        // 12. shutting down")),
("One lock per topic. Have you just serialised the whole broker?", "non-functional", 5,
 "No, and the answer is arithmetic. For one topic, yes: publishes take turns, which is what serialised means. But "
 "each turn is short: read the tail, build the message, store it in its slot, signal the waiting subscribers. With "
 "twenty subscribers that measured about 0.3 microseconds, so two thousand publishes a second hold the lock 0.07% of "
 "the time. The lock is per topic, so ten thousand topics never meet. The ring has no slow case: no trim and no copy, "
 "the same cost at any size. If they push, name the ladder from move 8: partitions, then compare-and-set, then the log "
 "leaves the process. The lock is the unfair kind on purpose. A fair one hands every acquire through a queue, which "
 "costs more than the work inside it. Nothing here is held long enough for a publisher to starve (wait forever while "
 "others cut in). The readers have their own ceiling: one thread per subscription is fine into the low hundreds. Past "
 "that, use a fixed pool that still runs each subscription's messages one at a time; Subscription does not change.",
 sect(src, "final class Topic", "// \"the knobs are about to multiply\"")),
("A handler throws. Where is the cursor afterwards, and what guarantee have you just implemented?", "functional", 10,
 "The cursor has not moved: the increment is the last statement of the loop, and it runs only when deliver returns "
 "true. deliver calls the handler with no lock held. On an exception it asks the policy how long to wait, sleeps, and "
 "tries again. When the policy answers a negative number, it parks the message in the dead-letter sink and returns "
 "true anyway. Giving up must move the cursor, or the subscription is stuck forever on one bad message. A filter that "
 "throws takes the same path. A stop in the middle returns false, so that message is handed out again. That is "
 "at-least-once, and it is one line: move the increment above the handler call and you have at-most-once, which is "
 "right for a metrics ping. The price of at-least-once is duplicates, so handlers must be idempotent. When the "
 "business code is not, IdempotentHandler remembers the ids it has handled and skips a repeat. In production those ids "
 "live in the database, written in the same transaction as the business change.",
 sect(src, "    private boolean deliver(", "    void pause()") + "\n" + X("exactly-once for the handler", "pull instead of push")),
("Someone calls unsubscribe while a delivery is in flight. What happens to the thread, and to that message?", "functional", 8,
 "<code>stop</code> does three things, and the third is the one people forget. It sets the state to STOPPED, wakes a "
 "thread parked on the pause condition, and interrupts the dispatcher thread. The interrupt matters because that "
 "thread is almost never somewhere it can see a flag. It is waiting in <code>awaitNanos</code> for the next message, or asleep in a "
 "sixty-second backoff between retries. In the wait, awaitAt passes the <code>InterruptedException</code> up and the "
 "loop ends. In the backoff, deliver catches it, sets the interrupt flag again and returns <i>false</i>, the one path "
 "that does not commit. Either way the cursor stays where it was, and nothing is parked in the dead-letter sink. A "
 "replacement subscription started at that offset is handed the same message: at-least-once, proven by test 12. The "
 "interrupt is sent under the subscription's gate lock, and run() clears its thread under the same lock. So a stop "
 "that arrives late can never hit a pooled thread that has already moved on to another subscription. Say the limit "
 "out loud too: an interrupt is only a request. A handler that swallows it, or is blocked on a socket with no read "
 "timeout, cannot be stopped by anyone, so the timeout belongs on whatever the handler calls.",
 sect(src, "    void stop()", "    private void awaitResume")
 + "\n" + T("        // 12. shutting down", "        // 13. seek while")),
("A subscriber was down for an hour. What does it see when it is back, and what if no message may be lost (Razorpay)?", "functional", 10,
 "Whatever it had not finished, and nothing twice. Its cursor is the offset it will read next, committed only after a "
 "handler returned. So a restart from that number repeats nothing it acknowledged and skips nothing it did not. "
 "Subscribing with fromOffset does that in one line; fromEarliest replays everything the ring still holds. The hard "
 "case is a ring that filled up while it was down. By default the ring overwrites the oldest messages, and the "
 "subscriber skips ahead and adds the gap to its missed counter: a loss you can see, which is Kafka's choice. "
 "Razorpay's statement forbids that loss. Then a publish must never overwrite a message someone has not read. "
 "BackPressure lets a publish through only while the slowest cursor is less than a full ring behind, and refuses a "
 "publisher that has waited too long. Publishers of that topic take turns at the check, so two can never take the "
 "last free slot (test 17: eight publishers, 200 messages, none missed). For an outage longer than memory allows, "
 "spill the oldest messages to a file and read them back when the consumer returns; Razorpay lists that as a plus "
 "point.",
 T("        // 3. a subscriber restarts", "        // 4. the handler throws") + "\n" + X("guaranteed delivery", "lag metrics and an alarm")),
("One subscriber takes two seconds per message. What happens to the publisher, and to the other subscribers?", "non-functional", 5,
 "Nothing happens to either. The publisher's call ends when the message is in the ring, which takes under a "
 "microsecond, and it never looks at a subscriber. The slow handler runs on its own dispatcher thread with no lock "
 "held, so the only thing that grows is that subscription's own lag. The test publishes six messages, checks the "
 "publish loop took no measurable time, checks the fast subscriber received all six, and checks the slow one is "
 "still behind. The junior version of this design calls every handler inside publish, which makes one slow "
 "subscriber an outage for everyone and one throwing subscriber a fan-out that stops halfway. The good version has a "
 "real cost worth saying: a stuck handler stalls its own subscription forever, so production puts a timeout on "
 "whatever the handler calls.",
 T("        // 7. one slow subscriber", "        // 8. a handler that always throws")),
("Now make it competing consumers: a group of three workers, each message handled by exactly one of them, and per-key order kept.", "twist", 10,
 "It needs no new broker code at all, which is the sign that move 5 was right. A group member is a normal "
 "subscription with a filter that accepts only its own slice of the keys. So the three read the same log at three "
 "cursors, and each handles one message in three. Messages with the same key hash to the same member, so "
 "per-key order survives; a message with no key falls back to its offset, which spreads them in turn. The honest "
 "price is that each member walks the whole log and skips two thirds of it. That is fine at these volumes, and it is "
 "exactly what real Kafka fixes by giving each member its own partition log instead. That is the partitions "
 "extension below: the same idea one level down, and the reason consumer groups hand out partitions, not keys.",
 X("consumer groups", "never retry a message that can never work") + "\n" + X("partitions", "persistence")),
("Razorpay's version: subscribers pull. consume() returns their next messages and ack() confirms them. What changes?", "twist", 10,
 "The log and the cursors stay; only who runs the read loop changes. PullConsumers keeps one cursor per topic and "
 "consumer, which subscribe starts at the end of the log or at the oldest message. consume reads up to max messages "
 "from that cursor, leaves out the ones the consumer's filter rejects, and moves nothing. It returns a Batch: the "
 "messages, plus the offset to acknowledge. ack(next) commits the whole batch in one step and never moves backwards, "
 "so a consumer that crashes before ack is handed the same batch again: at-least-once. In the practice-site version "
 "(codezym), consume moves the cursor at once; that is consume and ack in one call, which is at-most-once. A consumer "
 "that is down just stops calling, and its cursor waits. With waitMs above zero, consume waits in awaitAt until a "
 "publish wakes it: a long poll, which is also Uber's \"notify the consumer when a message arrives\". Kafka itself "
 "works this way: a consumer calls poll() and then commits. A push-style listener, such as Spring's @KafkaListener, "
 "is a poll loop the library runs for you, just like Subscription.run().",
 X("pull instead of push", "guaranteed delivery")),
("The dashboard asks every subscriber's lag a thousand times a second. Make it O(1).", "non-functional", 5,
 "It already is. Lag is the topic's tail offset minus the subscription's cursor: two volatile reads and a "
 "subtraction, and nothing is scanned, counted or re-read. The tail is a volatile long that <code>append</code> "
 "rewrites inside the lock precisely so this read stays outside it. A metrics thread asking a thousand times a second "
 "must never queue behind a publisher, and a number that is one message stale is harmless. That shape follows "
 "directly from one log with a cursor per subscriber. With a queue per subscriber you would be asking for the size of "
 "a concurrent queue, which is at best approximate and at worst a walk over the whole queue. The broker's lagReport "
 "walks the subscription map once and does that subtraction per subscriber, so the whole dashboard is O(number of "
 "subscriptions). The alarm on top is a listener plus a filter over the report, and it needs no new state anywhere.",
 sect(src, "    Message readAt(long offset)", "    int capacity()")
 + "\n" + X("lag metrics and an alarm", "partitions")),
("Persist it: messages must survive a restart. And then there are two processes.", "twist", 5,
 "The log goes behind a MessageStore and the cursors behind an OffsetStore, and no other class changes. The topic's "
 "ring becomes a cache of the newest part of the file. Each line carries its offset, and key and payload are "
 "Base64-encoded (turned into plain letters and digits), so a tab or a newline inside a payload cannot break a line. A restart reads the file back in offset "
 "order and puts each message back at its own offset and time. It goes straight into the topic rather than through "
 "publish, so no listener stores it a second time (test 19). A subscriber resumes with one line, because its cursor was always "
 "just a number. Two processes is where an in-process broker stops being the right tool, and you should say so. The "
 "log moves out to Kafka, Pulsar or a table with an increasing id. The topic's lock becomes the partition leader's, "
 "and the cursor becomes a committed offset in the broker's own store. Every class here keeps its name, which is why "
 "the mapping table is the same explanation at two sizes.",
 X("persistence", "replay from a point in time") + "\n" + X("the Kafka mapping", "Runs every extension")),
("Where does time come from, and how do you test a five-minute backoff schedule without waiting five minutes?", "design", 3,
 "One injected interface does both jobs: Clock answers what time it is and also does the waiting, with a default "
 "method so the production clock is still a lambda. Nothing else in the system reads the wall clock or calls "
 "Thread.sleep. A test hands in a clock that records every requested wait and returns at once. So the backoff "
 "schedule can be checked exactly (10, 20, 40), and the whole suite runs in about a second. The same seam stamps each "
 "message's time, and append never lets a timestamp go below the one before it. So a wall clock stepped back by six "
 "seconds cannot break seek-by-time (test 16).",
 sect(src, "interface Clock", "// \"a handler will fail") + "\n"
 "// in a test: the clock records what it was asked to wait for, and never actually waits\n"
 "static final class TestClock implements Clock {\n"
 "    volatile long now = 1_700_000_000_000L;\n"
 "    final List<Long> sleeps = new CopyOnWriteArrayList<>();\n"
 "    public long nowMs() { return now; }\n"
 "    @Override public void sleepMs(long ms) { sleeps.add(ms); now += ms; }\n"
 "}\n"
 "broker.setClock(clock);\n"
 "// ... a handler that throws three times ...\n"
 "check(clock.sleeps.equals(List.of(10L, 20L, 40L)), \"the waits before giving up were 10, 20 and 40 ms\");\n"),
("Which pattern is where, and why did each one earn its place?", "design", 8,
 "None was chosen up front; each is what a move produced. Observer is not a pattern this design uses; it is what the "
 "design <i>is</i>: publish names a topic and never a subscriber. Strategy, Decorator and Builder all come out of "
 "move 3. Retry, sink, filter and clock are rules handed in. BoundedRetry wraps whatever policy it is given, so no "
 "rule, present or future, can retry forever. SubscribeOptions has five settings and every one is optional: the rare "
 "case where a builder beats a constructor. Iterator is move 5: the cursor is an iterator over a shared log, which is "
 "why a fourth subscriber adds a cursor, not a copy of everything. State is move 6, twice over: the delivery life "
 "cycle and the subscription's own. Singleton earned nothing: the broker is handed to its callers, so each test "
 "builds a fresh one.",
 "// Observer: the whole product. publish names a topic; it has never heard of a subscriber\n"
 "long publish(String topicName, String key, String payload) { ... }\n"
 "Subscription subscribe(String subId, String topicName, Handler h, SubscribeOptions o) { ... }\n\n"
 "// Strategy: a rule behind a one-method interface, handed in, never built by the broker\n"
 "interface RetryPolicy { long backoffMs(int attempt, Exception failure); }\n\n"
 "// Decorator: add the invariant to every policy, present and future, instead of trusting each one\n"
 "new BoundedRetry(o.retry == null ? defaultRetry : o.retry, MAX_ATTEMPTS, MAX_BACKOFF_MS)\n\n"
 "// Iterator: one log, N cursors. This line is the entire fan-out mechanism\n"
 "private final AtomicLong cursor;           // the next offset to read; written only by the dispatcher\n\n"
 "// State: the delivery life cycle, and the subscription's own\n"
 "enum SubState { ACTIVE, PAUSED, STOPPED }\n"
 "if (!deliver(m)) break;                    // stopped mid-delivery: nothing is committed\n"
 "cursor.incrementAndGet();                  // handled, skipped or parked: commit\n\n"
 "// Builder: five optional knobs, which is exactly the case a long constructor handles badly\n"
 "SubscribeOptions.opts().fromEarliest().retry(new ExponentialBackoff(5, 10, 1000)).filter(m -> \"IN\".equals(m.key()))\n"),
("Which SOLID letter is where in this code, and where would a Factory earn its place?", "design", 5,
 "S: the topic stores and hands back by offset; the subscription drives one cursor and one handler; a policy answers "
 "\"again, and how long\"; the broker wires them together. So changing the retry rule cannot break the log. O and "
 "L together: exponential backoff, never-retry-this, a dead-letter topic and a file store were each a new class behind "
 "an existing interface. No caller ever asks which one it got, because the whole contract is \"a negative answer "
 "means give up\". I and D together: five interfaces with one method each, all handed in, which is why every fake in "
 "the tests is a lambda. Factory is the interesting one, because it has <i>not</i> earned its place: topics appear "
 "through a single computeIfAbsent, which is a registry, not a factory. It earns the name the day a topic needs a "
 "configuration of its own (its own retention, its own partition count), because then construction stops being one "
 "line. Razorpay's statement lists \"a separate component that creates and lists topics\" as a plus point. That is "
 "this registry moved into its own class, and the natural home for that factory.",
 "// S: four classes, four reasons to change\n"
 "final class Topic { /* the log and the offsets */ }\n"
 "final class Subscription { /* one cursor, one handler, one thread */ }\n"
 "interface RetryPolicy { long backoffMs(int attempt, Exception failure); }\n\n"
 "// D + I: handed in, one method each, so a test fake is a lambda\n"
 "cap.configure((attempt, failure) -> 0, parked);       // \"always retry, immediately\" -- and BoundedRetry stops it\n"
 "broker.setClock(() -> fixedInstant);\n\n"
 "// Factory: not yet. This one line is the registry; it earns the name when a topic needs a config\n"
 "Topic topic(String name) { return topics.computeIfAbsent(name, n -> new Topic(n, retention)); }\n"
 "// the day it becomes:  topics.computeIfAbsent(name, n -> topicFactory.create(n, configFor(n)));\n"),
]

build(dict(
    slug="pubsub", title="Pub/Sub System",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 75 failure checks and a 50-thread publish race pass",
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
