# Notification Service LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"notification-lld/Main.java").read_text()
ext   = (H/"notification-lld/Extensions.java").read_text()
tests = (H/"notification-lld/FailureTests.java").read_text()

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
rows = [("submit", 30, [("a caller hands one over", "who, channel, urgency, template"),
                        ("render it, take their gate", "no quota spent, no key claimed"),
                        ("walk the reasons not to send", "muted, capped, 3am, already sent"),
                        ("record it and enqueue", "urgent first, then arrival")]),
        ("deliver", 165, [("a worker takes the top", "CRITICAL before LOW"),
                          ("past its deadline? drop it", "the gateway is never called"),
                          ("call the gateway, no lock", "yes / no / no answer"),
                          ("record the outcome by rank", "sent, retry, or dead letter")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 2))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M740 84 V95", dash=True) + _bx(590, 95, 300, 40, "refused: a reason, never a send", "", dash=True)
pf += _ar("M905 84 V115 H922", dash=True) + _bx(922, 95, 296, 40, "3am: parked, judged again at 08:00", "", dash=True)
pf += _tx(88, 256, "read", "var(--acc)", 13) + _tx(175, 256, "without scanning anything: where is n-8, and why?  what was user u1 sent?  what is in the dead-letter list?", "var(--text)", 12, "start")
pf += _tx(88, 282, "change", "var(--acc)", 13) + _tx(175, 282, "a receipt the provider posts back later: onReceipt(id, attempt, DELIVERED).   the caller's cancel(id): never while a send is in flight", "var(--text)", 12, "start")
pf += _tx(615, 312, "fifty callers can submit the same key in the same millisecond: exactly one message may reach the human", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 325, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("03:00  a promo", ["quiet hours: 21:00-08:00 local", "DEFERRED, not dropped",
                         "at 08:00 every guard runs again", "then it goes out"], False),
      ("09:14:02  an OTP, CRITICAL", ["queued behind 40,000 promos", "taken first: CRITICAL sorts first",
                                     "the gateway times out: UNKNOWN", "retried in 100 ms, same key"], True),
      ("09:14:02  the client retries", ["its HTTP call had timed out", "same key: login-77",
                                        "the claim fails: a duplicate"], False),
      ("09:14:03  attempt 2 accepted", ["sms/991a3cc7, state SENT", "the provider drops the repeat",
                                        "one text message, not two"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Submit: who it is for, which channel, how urgent, which template and its parameters.</li>
<li>Run every reason it might not go out, and record which one stopped it. A message held until 08:00 is judged again at 08:00.</li>
<li>Deliver urgent first: an OTP submitted last still beats a marketing blast queued first.</li>
<li>Retry a &ldquo;try again later&rdquo;, with a growing wait and a budget; never retry a malformed address.</li>
<li>Drop a message whose deadline passed before it reached a gateway.</li>
<li>Answer &ldquo;where is this notification, and why&rdquo; and &ldquo;what was this user sent&rdquo; at any moment.</li>
<li>Accept a delivery receipt that arrives later, possibly out of order.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Two callers submitting the same key in the same millisecond produce exactly one message.</li>
<li>Status lookups and preference lookups are O(1); admission into the queue is O(log n).</li>
<li>Every rule &mdash; channel, reason, retry, template &mdash; swappable without touching the engine.</li>
<li>One source of truth per notification: the record, and only higher-ranked moves change it.</li>
<li>Nothing half-done: a refused message never reaches a gateway and never eats a quota.</li>
<li>A slow or broken provider must not park the worker pool or stop the other channels.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design the notification service. Other teams hand it a message &mdash; who it is for, email or SMS or '
          'push, how urgent &mdash; and it gets it out: templates, opt-outs, rate caps, retries when the gateway '
          'is down. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Every other service in the company wants to tell a '
 'human something: your payment failed, here is your code, forty per cent off today. They hand that sentence to '
 'you and walk away. You turn it into words from a template, find the person\'s address, and decide whether it '
 'should go out at all. They may have unsubscribed. They may have had twenty already today. It may be three in '
 'the morning where they live. The same message may have gone out thirty seconds ago, because the caller\'s HTTP '
 'call timed out and their client sent it again. If it does go out, you hand it to a gateway (the provider\'s '
 'server: an SMS company, Apple\'s or Google\'s push service) that you do not control. It will sometimes say '
 'yes, sometimes no, and sometimes nothing at all. Two things must always be true: a human never gets the same '
 'message twice because of something <i>we</i> did, and no message we accepted is ever silently lost.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that submits a few messages and prints what happened to each. The interviewer is '
 'watching for, in this order: the questions you ask before typing, where idempotency (a request that arrives '
 'twice is carried out once) and the delivery guarantee (when unsure, do we risk sending twice or risk never '
 'sending?) come first; which classes exist and which one owns the state; a submit and a delivery end to end; '
 'what happens when two threads submit the same key at the same instant; where the rules that will change live, '
 'so a new reason not to send is a new class and not an edit; what the record says when the gateway times out. '
 'Then the twists these companies actually use: a new channel with its own templates, order events to the right '
 'people, a daily limit per user, a provider\'s rate limit, receipts, persistence.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>If a caller\'s request times out and they retry, may the human get two?</td><td>No: the caller sends an idempotency key (a unique id for this request), and we remember it for a de-dup window (say one minute)</td><td>A claim that is ONE atomic step (no other thread can get in between its read and its write), not check-then-put (moves 4, 5)</td></tr>'
 '<tr><td>At-least-once or at-most-once? What is the retry budget?</td><td>At-least-once (never lost, sometimes twice) rather than at-most-once (never twice, sometimes lost); four attempts, doubling waits</td><td>Three outcomes from a send, and a retry policy handed in (moves 3, 6)</td></tr>'
 '<tr><td>Does a provider tell us it was delivered, or is &ldquo;accepted&rdquo; the end?</td><td>Receipts arrive later, and out of order</td><td>SENT is not final; every update is ranked (move 6)</td></tr>'
 '<tr><td>Are there priority classes? Does an OTP (a one-time password) jump a marketing blast?</td><td>Four classes, urgent first, ties by arrival</td><td>A heap (it always hands out the smallest first) keyed on class, then arrival; not a list (move 5)</td></tr>'
 '<tr><td>Which reasons can stop a message, and who adds new ones?</td><td>Muted, capped, quiet hours, duplicate: from four teams</td><td>One class per reason, walked in order (move 3)</td></tr>'
 '<tr><td>One request, one channel? Or does one request fan out (become push and SMS and email)?</td><td>One channel; fan-out is a policy on top</td><td>One record per send, so status still means something (move 12, follow-ups 2 and 16)</td></tr>'
 '<tr><td>An in-process library, or a service behind a queue?</td><td>In-process; the queue boundary gets named</td><td>Whether submit is a method or an HTTP handler (moves 2, 12)</td></tr>'
 '<tr><td>One process and in memory, or ten instances?</td><td>One process, in memory</td><td>No repository yet; a follow-up adds one (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> the caller sends an idempotency key, and claiming it is one atomic '
 'step. Delivery is at-least-once, and every attempt carries the same key, so the provider can drop a repeat. A '
 'send has three outcomes, not two: a timeout is neither yes nor no. One record per notification, and an update '
 'lands only if it outranks what is already there. Named as out of scope: order events and fan-out across '
 'channels, persistence, ten instances, batching; each is a follow-up on page 05.</div>')
print("page 1 built")

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a CALLER submits a NOTIFICATION for a RECIPIENT; TEMPLATES render it, GUARDS judge it, a SENDER hands it over, a RECORD remembers", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 185, "Notification", "every field final: a value", 0), (245, 185, "Recipient", "addresses + timezone", 0),
                          (460, 205, "DeliveryRecord", "attempt, state, why: it moves", 1), (695, 215, "NotificationService", "queue, ledger, gates, workers", 1),
                          (940, 130, "Guard", "a rule: no state", 0), (1090, 120, "Sender", "one call: no state", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = state of its own that changes, so it becomes a class.   dashed = a value or a rule: a record, or an interface", "var(--muted)", 11)
m1 += _tx(615, 210, "the one that surprises people: a notification never changes. Only the RECORD of what happened to it does, and that is where the hard questions live", "var(--muted)", 11)
MV[1] = _mv(1230, 225, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("turn a template into words", "TemplateEngine  (owns the registry)", "templates.render(id, channel, params)"),
                                       ("decide whether it goes out at all", "DeliveryGuard  (owns one reason)", "guard.check(n, recipient, now)"),
                                       ("hand it to a provider", "Sender  (owns one provider)", "sender.send(to, words, key)"),
                                       ("remember where it got to", "DeliveryRecord  (owns the progress)", "record.moveTo(attempt, state, why)"),
                                       ("sequence all of that, and only that", "NotificationService  (queue, ledger, gates)", "service.submit(n)")]):
    y = 20 + k*52
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 295, "a verb whose state is spread over several classes goes to the one that owns them all: that class is the engine, and it does nothing else", "var(--muted)", 11)
m2 += _tx(615, 315, "and notice what is NOT a verb here: \"retry\". A retry is the same send, one attempt later -- which is why it is a state, not a method", "var(--muted)", 11)
MV[2] = _mv(1230, 330, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 110, 220, 100, "NotificationService", "configure(...) hands these in", acc=True)
for k, (t, sub, impl, note) in enumerate([("Sender", "one call per provider", "EmailSender / FlakySmsSender / PushSender", "one class per provider; WhatsApp is a fourth"),
                                    ("DeliveryGuard", "one reason not to send", "Preference / QuietHours / DailyCap / Dedupe", "one class per reason, walked in order"),
                                    ("RetryPolicy", "how long, and how many times", "ExponentialBackoff, JitteredBackoff(policy)", "the arithmetic, and nothing else"),
                                    ("DeliveryListener", "who else wants to know", "ConsoleAudit, Metrics, ReceiptWebhook", "told after the change, never inside the gate"),
                                    ("Clock and Scheduler", "where now and later come from", "a timer thread, or one that runs inline", "the seam that lets a test stand at 03:00")]):
    y = 20 + k*54
    m3 += _ar("M250 160 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 440, 44, impl, note) + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 300, "dashed green = handed in. The engine builds none of them, so \"nothing between 9pm and 8am, except OTPs\" is one new class and one line in a list", "var(--muted)", 11)
m3 += _tx(615, 320, "and two of them wrap another of their own kind: CircuitBreakerSender(sms) is still a Sender, JitteredBackoff(policy) is still a RetryPolicy. That is Decorator, born here", "var(--acc)", 11)
MV[3] = _mv(1230, 335, m3)

# move 4: the gap, and one owner with one gate
m4 = _D + _bx(30, 30, 210, 44, "the first HTTP call", "key login-77: unclaimed") + _bx(30, 110, 210, 44, "the retry, 80 ms later", "key login-77: unclaimed")
m4 += _bx(370, 70, 200, 44, "the de-dup map", "\"login-77 is not there\"", acc=True)
m4 += _ar("M240 52 H370 V70") + _ar("M240 132 H370 V114") + _tx(305, 40, "read", "var(--muted)", 10.5) + _tx(305, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="610" y="20" width="300" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(760, 45, "the gap", RED, 12) + _tx(760, 70, "both see \"nobody claimed it\"", RED, 11) + _tx(760, 90, "both enqueue; the human gets", RED, 11) + _tx(760, 108, "two OTPs and logs into neither", RED, 11)
m4 += _tx(760, 138, "fix: decide and claim as ONE step", "var(--text)", 11)
m4 += _bx(940, 40, 270, 100, "one claim, one step", "putIfAbsent, inside the user's gate", acc=True)
m4 += _tx(615, 190, "the gate is per RECIPIENT, so two different users never wait for each other, and the reserve-and-check arithmetic of the daily cap is safe inside it", "var(--muted)", 11)
m4 += _tx(615, 210, "the claim itself is one atomic map operation and needs no gate at all, which is exactly why it survives being moved to Redis SET NX unchanged", "var(--muted)", 11)
MV[4] = _mv(1230, 225, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D + _tx(220, 16, "the question asked of it", "var(--muted)", 11) + _tx(730, 16, "the shape that answers it", "var(--muted)", 11) + _tx(1115, 16, "the cost", "var(--muted)", 11)
for k, (q, shape, cost) in enumerate([("where is notification n-8?", "Map&lt;id, DeliveryRecord&gt;", "O(1)"),
                                      ("which message goes out next?", "PriorityBlockingQueue by (class, arrival)", "O(log n)"),
                                      ("has this key already been claimed?", "ConcurrentHashMap&lt;key, expiry&gt; + putIfAbsent", "O(1)"),
                                      ("which sender for this channel?", "EnumMap&lt;Channel, Sender&gt;", "O(1)"),
                                      ("how many has this user had today?", "Map&lt;user, long[their day, used]&gt;", "O(1)"),
                                      ("what was user u1 sent?", "Map&lt;user, queue of records&gt;, added at submit", "O(their records)"),
                                      ("what is in the dead-letter list?", "a scan of the ledger, on purpose", "O(n)")]):
    y = 28 + k*42
    m5 += _bx(30, y, 380, 36, q, "") + _ar("M410 %s H450" % (y+18), True)
    m5 += _bx(450, y, 560, 36, shape, "", acc=True) + _ar("M1010 %s H1030" % (y+18), True) + _bx(1030, y, 170, 36, cost, "")
m5 += _tx(615, 342, "one shape is deliberately NOT O(1): the dead-letter scan, because a human reads it twice a day and a second index would be one more thing to keep true", "var(--muted)", 11)
m5 += _tx(615, 360, "and the queue is a heap, not a list: ties are broken by arrival sequence, so the same input always comes out in the same order", "var(--muted)", 11)
MV[5] = _mv(1230, 372, m5)
print("moves 1-5 built")

# move 6: the state machine, the rank rule, and the ORDER at the critical step
m6 = _D
for t, x, y, sub, acc in [("SUPPRESSED", 20, 30, "finished", 0), ("EXPIRED", 175, 30, "finished", 0),
                          ("CREATED", 20, 120, "rank 0", 0), ("QUEUED", 175, 120, "rank 10", 0), ("SENDING", 330, 120, "rank 20", 1),
                          ("SENT", 485, 120, "rank 50", 0), ("DELIVERED", 640, 120, "finished + 1", 0),
                          ("DEFERRED", 20, 210, "rank 5, re-judged", 0), ("RETRY_SCHEDULED", 175, 210, "rank 40, attempt + 1", 0),
                          ("UNKNOWN", 330, 210, "rank 30", 0), ("FAILED_FINAL", 485, 210, "finished", 0)]:
    m6 += _bx(x, y, 140, 44, t, sub, acc=bool(acc))
for d, acc in [("M160 142 H175", True), ("M315 142 H330", True), ("M470 142 H485", True), ("M625 142 H640", True),
               ("M90 120 V74", False), ("M245 120 V74", False), ("M60 164 V210", False), ("M150 210 V190 H200 V164", False),
               ("M245 210 V164", False), ("M345 164 L300 210", False), ("M400 164 V210", False), ("M455 164 L500 210", False),
               ("M330 232 H315", False), ("M470 232 H485", False), ("M625 232 H710 V164", False)]:
    m6 += _ar(d, acc)
m6 += _tx(97, 100, "a guard said no", "var(--muted)", 10, "start") + _tx(252, 100, "deadline passed", "var(--muted)", 10, "start")
m6 += _tx(67, 192, "quiet hours", "var(--muted)", 10, "start") + _tx(305, 186, "503", "var(--muted)", 10, "end")
m6 += _tx(407, 190, "no answer", "var(--muted)", 10, "start") + _tx(505, 190, "permanent", "var(--muted)", 10, "start")
m6 += _tx(322, 272, "tries left", "var(--muted)", 10) + _tx(478, 272, "none left", "var(--muted)", 10)
m6 += _tx(717, 200, "a late receipt", "var(--muted)", 10, "start")
m6 += _card(920, 30, 290, 250, "the order at the critical step",
            ["1  render and resolve: nothing written", "2  take the gate, walk the guards in order",
             "3  leave the gate, THEN queue or park it", "4  a parked one is judged again at 08:00",
             "5  a worker checks the deadline first", "6  move to SENDING: it takes ownership",
             "7  call the gateway with NO lock held", "8  only then write SENT", "",
             "a crash at 7 leaves the record saying", "SENDING -- which is the truth --", "and the retry carries the same key"], acc=True)
m6 += _tx(615, 302, "every move is one compare-and-set on one AtomicReference, and lands only if its rank is HIGHER: attempt x 100 + the number in the box", "var(--muted)", 11)
m6 += _tx(615, 320, "finished states share one rank above every attempt, so none replaces another; only DELIVERED ranks higher. cancel(): anything not yet SENDING becomes SUPPRESSED", "var(--muted)", 11)
MV[6] = _mv(1230, 332, m6)

# move 7: what is inside the gate, and ten callers at the same instant
m7 = _D + _card(30, 20, 540, 130, "inside one user's gate: about 1.2 microseconds",
                ["is this category muted for them? one set lookup", "is it quiet hours where they are? one zone lookup",
                 "have they had twenty today? one array read and write", "claim the idempotency key: one putIfAbsent",
                 "about six hash operations, and nothing that can block"], acc=True)
m7 += _ar("M570 85 H640", True) + _tx(605, 75, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 130, "outside it: milliseconds, sometimes seconds",
            ["rendering the template: before the gate is taken", "the gateway call: 40 to 200 ms, no lock held at all",
             "the wait before a retry: on a timer, not on a worker", "the audit and the metrics: after, in a try/catch",
             "the person typing their phone number: seconds"])
m7 += _tx(615, 178, "ten threads submit for the SAME user at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 193, 106, 40, "caller %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%.1f" % (k*1.2)), acc=(k == 9))
m7 += _tx(615, 261, "the tenth waits about eleven microseconds for the gate, and then up to two hundred milliseconds for its own gateway call:", "var(--muted)", 11)
m7 += _tx(615, 279, "one at a time is true, and nobody can tell, because nothing slow is allowed inside the gate -- and two different users never meet at all", "var(--muted)", 11)
MV[7] = _mv(1230, 293, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one gate per user: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the gated part of a submit: about six map operations, 1.2 us",
                       "a flash sale: 2,000 submits a second over two million users",
                       "that is one per user every 17 minutes on average; even a user",
                       "who gets 5 a second holds the gate 6 us a second: 0.0006% busy",
                       "so the gate is not the bottleneck. The gateway is:",
                       "8 workers x 50 ms per send = 160 sends a second, not 2,000"]):
    m8 += _tx(35, 66 + k*23, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 size each pool by rate x latency", "Little's law: 500 SMS/s x 80 ms = 40 threads, one pool per channel"),
                              ("2 stop parking threads on sockets", "non-blocking provider clients: 8 threads can hold 10,000 calls open"),
                              ("3 a broker, and many instances", "a topic per priority class, Redis SET NX for the claim, a row per record")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("the client retried a timed-out call", "claim the key with putIfAbsent; test 1: fifty threads, one claim, one gateway call"),
                                ("the gateway timed out: did it send?", "record UNKNOWN and retry with the SAME key; test 2: three attempts, ends SENT"),
                                ("the address is malformed", "permanent means no retry at all; test 3: one call, then the dead-letter list"),
                                ("it sat in the queue past its deadline", "check the deadline before the send; test 4: EXPIRED, the gateway never called"),
                                ("a receipt for an old attempt arrives", "a move must raise the rank or do nothing; test 5: the stale receipt changes nothing"),
                                ("3am where the recipient lives", "defer to 08:00 local, do not drop; test 6: held until 08:00 sharp, OTPs walk through"),
                                ("a duplicate eats the daily quota", "a guard undoes whatever it reserved; test 7: still one slot used, not two"),
                                ("the provider SDK or a listener throws", "one try/catch each, UNKNOWN for the adapter; test 8: the message still goes out"),
                                ("the queue is full in a flash sale", "refuse at the door and undo every reservation; test 9: the slot and the key come back"),
                                ("push failed: fall back to SMS?", "only a FAILURE climbs, a mute is a decision; test 10: a suppression climbs nothing"),
                                ("parked at 3am, retried, muted at 7", "judge it again when it wakes; test 11: one buzz at 08:00, and the mute holds"),
                                ("cancelled, then its deadline passes", "finished states share one rank; test 12: it stays cancelled, no SMS goes out")]):
    y = 14 + k*38
    m9 += _bx(30, y, 320, 34, bad, "") + _ar("M350 %s H380" % (y+17), True) + _bx(380, y, 820, 34, fix, "", acc=True)
m9 += _tx(615, 485, "every claim this design makes has a failure test: FailureTests.java runs sixteen blocks (13 to 16 prove the follow-ups) and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 500, m9)
print("moves 6-9 built")

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 860)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface Sender { SendResult send(to, words, idempotencyKey); }", None), ("a new channel is a class, not an edit", None)],
          [("Chain of Responsibility", "var(--text)"), ("move 3", None), ("for (DeliveryGuard g : guards) if (g.check(...) != ALLOW) break;", None), ("a fifth reason is a class and one list entry", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new CircuitBreakerSender(sms, 2, 60_000, clock) -- still a Sender", None), ("a dead provider stops costing you workers", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("fire(from, to, why) after the change, one try/catch each", None), ("audit, metrics and receipts, none in the way", None)],
          [("State", "var(--text)"), ("move 6", None), ("moveTo(attempt, state, why): a higher rank, or nothing at all", None), ("an out-of-order webhook is harmless", None)],
          [("Builder", "var(--text)"), ("move 1", None), ("Notification.to(u, SMS, \"otp\").priority(CRITICAL).dedupeKey(k)", None), ("seven fields, four optional: earned here", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the service is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("each test builds a fresh one", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("the Channel -&gt; Sender map IS the registry, one line each", "var(--muted)"), ("earns the name when channels are config strings", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence, and Builder is the one this problem actually earns", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 470), ("the line that shows it", 570)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("a guard knows one rule; a sender one provider; the record the life cycle", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("QuietHoursGuard is a new file plus one entry in the list handed to configure()", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("sender.send(to, words, key);  never \"is this the SMS one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one or two methods each", None), ("move 3", None), ("Clock, Scheduler, listener: one method, a lambda fakes it; Sender, guard: two, a tiny class", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("configure(templates, directory, policy, guards, senders, clock, scheduler)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "quiet hours, hold till tomorrow, a fraud hold", "a new class behind DeliveryGuard, plus one entry in the list", "", "move 3"),
        ("someone new wants to know", "receipts, metrics, a data warehouse", "one more listener; the queue and the gate do not move", "", "move 4"),
        ("a new step in a life", "BOUNCED, SCHEDULED, CANCELLED", "one more state with a rank, and the edges it may come from", "", "move 6"),
        ("a new invariant across messages", "at most one OTP a minute per user", "the check and the reserve inside the SAME gate: all or nothing", "", "move 4"),
        ("state that must outlive the process", "persist it; ten instances", "the ledger behind a repository, and moveTo becomes", "UPDATE ... SET state = ?, rank = ? WHERE id = ? AND rank &lt; ?", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the engine, the queue and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)
print("moves 10-12 built")

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>caller</b> submits a <b>notification</b> for a <b>recipient</b>; a "
 "<b>template</b> turns it into words; <b>guards</b> decide whether it goes out; a <b>sender</b> hands it to a "
 "provider; something has to <b>remember</b> what happened. Now sort them by whether they hold state that "
 "changes. A notification does not: every field is final, because the request a caller made is a fact and facts "
 "do not move. A recipient is addresses plus a timezone: a value. A template is text. A guard and a sender have "
 "no fields at all worth the name &mdash; they are rules and calls &mdash; so they are interfaces. What is left "
 "is the pair that carries everything: the <code>DeliveryRecord</code>, which holds which attempt we are on, "
 "what state it reached and why; and the <code>NotificationService</code>, which holds the queue, the ledger (a "
 "map from notification id to its record), one lock per user (move 4 calls it the user's gate) and the workers. "
 "That split is the whole design in one line: the message never changes, and the record of what happened to it "
 "is the only thing that does.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Turn a template into words\" touches the template registry, so <code>templates.render(id, channel, params)</code>. "
 "\"Decide whether it goes out\" touches one rule's own data &mdash; the mute set, the day's counter, the claimed "
 "keys &mdash; so each reason gets its own class and one method, <code>guard.check(n, recipient, now)</code>. "
 "\"Hand it to a provider\" touches a connection, so <code>sender.send(to, words, key)</code>. \"Remember where "
 "it got to\" touches the progress, so <code>record.moveTo(attempt, state, why)</code>. What is left touches all "
 "of them at once &mdash; the queue, the ledger, the gates, the workers &mdash; and only the service sees all of "
 "those, so the service sequences and does nothing else. And notice what is <i>not</i> a verb: \"retry\". A retry "
 "is the same send one attempt later, which is why it turns up in move 6 as a state rather than here as a method.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Which providers exist will change: email today, WhatsApp next quarter. Which reasons can stop a message will "
 "change, and they arrive from four different teams on four different days: muted, too many today, three in the "
 "morning, already sent. How long you wait before trying again will change. Who wants to hear about it will "
 "change. So each becomes a small interface (one or two methods) that the service is <i>given</i> in "
 "<code>configure(...)</code> and never builds. This is where the patterns come from, not the other way round: a swappable rule behind an "
 "interface is <b>Strategy</b>; an ordered list of independent reasons, each able to stop the walk, is <b>Chain "
 "of Responsibility</b>; a service that announces what happened without knowing what an audit log is, is "
 "<b>Observer</b>; and a class that implements the same interface it wraps &mdash; "
 "<code>CircuitBreakerSender(sms)</code> is still a <code>Sender</code>, <code>JitteredBackoff(policy)</code> is "
 "still a <code>RetryPolicy</code> &mdash; is <b>Decorator</b>. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "A caller's HTTP call times out, their client retries eighty milliseconds later, and both requests land on "
 "different threads of your service. Both ask \"has key login-77 been claimed?\", both are told no, both enqueue, "
 "and the human gets two one-time passwords and logs in with neither. The gap is between the read and the write, "
 "so the read and the write must be one step. There are two such steps here, answered differently on purpose. "
 "The claim is one atomic map operation: <code>putIfAbsent</code> (put the key only if it is absent, and return "
 "what was there) lets exactly one of fifty threads see null. Being one operation, it needs no lock, which is why "
 "it moves to Redis unchanged, as <code>SET key NX PX</code> (Redis's own put-if-absent, with an expiry). The "
 "daily cap is not one operation: it reads a counter, compares it and writes it back, so it needs a lock. The "
 "lock is per <i>recipient</i>, so two different users never wait for each other; call it the user's gate. "
 "Everything the guards do happens inside that gate, nothing slow is allowed in, and the listeners are called "
 "after it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Where is notification n-8?\" is a map from id to record, which is what makes a support screen instant. "
 "\"Which message goes out next?\" is a heap ordered by priority class and then by arrival sequence, so an OTP "
 "submitted last still beats a marketing blast queued first, and ties never reorder &mdash; the same input always "
 "comes out in the same order, which is what makes a bug reproducible. \"Has this key been claimed?\" is a "
 "concurrent map from key to expiry. \"Which sender for this channel?\" is an <code>EnumMap</code>, an array "
 "behind a friendly name. \"How many has this user had today?\" is a map from user to a two-slot array: the day, "
 "on the user's own calendar, and the count. A new day resets the count on first use, with no clean-up job. "
 "\"What was user u1 sent?\" is one more map, from user to that user's records, added to at submit. One shape is "
 "deliberately <i>not</i> O(1): the "
 "dead-letter list (messages that will never be retried, kept for a human) is a scan of the ledger, because a "
 "human reads it twice a day and a second index would be one "
 "more thing that can disagree with the first.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A boolean <code>sent</code> flag is a lie the moment retries exist. It cannot tell \"failed once, will try "
 "again\" from \"dead\", and it cannot tell either from \"the gateway never answered\". So write the life down: "
 "created; then queued, deferred (parked until a time) or suppressed; sending; then sent, unknown, waiting for "
 "another attempt, expired, or failed for good; and later, from a webhook (an HTTP call the provider makes back to "
 "us), delivered. Give every state a rank. Every move is a compare-and-set (write the new value only if the old "
 "one is still there, in one step) that lands only if it <i>raises</i> the rank. A live state's rank is "
 "<code>attempt &times; 100 + the state's number</code>. The finished states all share one rank above every "
 "attempt, so none can replace another, and DELIVERED alone sits one higher. That one rule pays four times: a "
 "receipt for attempt 1 that arrives while attempt 2 is in flight changes nothing; a timer that fires after a "
 "cancel changes nothing; the same webhook twice changes nothing the second time; and only a DELIVERED receipt "
 "can overrule \"we gave up\", because if the handset got it, it got it. The order is the other half. Render and "
 "resolve before the gate, so a missing template throws with nothing reserved. Take the gate, run the guards, "
 "leave the gate, then queue the message or park it. A message parked until 08:00 goes through every guard again "
 "at 08:00. In the worker: check the deadline, take ownership by moving to SENDING, and only then call the "
 "gateway, with no lock held, because it is the one slow thing here. Write SENT only after the gateway has said "
 "yes. A crash in between leaves the record saying SENDING, which is the truth, and the retry carries the same "
 "idempotency key so the provider can drop the repeat.", 6),
("Move 7: yes, one user's submits happen one at a time. Ask for how long, and what is inside the gate.",
 "The question you will be asked: if every submit takes a lock, have you serialised the notification service "
 "(made it one at a time)? For one user, for about 1.2 microseconds, yes. Inside the gate there is a set lookup "
 "for the mute, one time-zone lookup for the local hour, one array read and write for the daily count, and one "
 "<code>putIfAbsent</code> for the key: roughly six hash operations, none of which can block. Everything slow is "
 "outside it. The template is rendered before the gate is taken, on purpose: that is the part that can throw, and "
 "it must not leave a quota half-spent. The gateway call, forty to two hundred milliseconds, happens on a worker "
 "with no lock held at all. The wait before a retry happens on a shared timer, not by sleeping a worker. That is "
 "the difference between a slow provider costing you nothing and a slow provider taking down every channel. So "
 "when ten threads submit for the same user at the same instant, the tenth waits about eleven microseconds for "
 "the gate, then waits on its own gateway call like everybody else.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A flash sale is two thousand submits a second, spread across two million users. That is one submit per user "
 "every seventeen minutes on average. Even a user who gets five a second holds their gate for six microseconds a "
 "second: 0.0006 per cent busy. The gate is not the bottleneck, and saying so out loud is half the answer. The "
 "gateway is: eight workers each blocked for fifty milliseconds per send make a hundred and sixty sends a second, "
 "not two thousand, and that is the number to fix. The ladder, in the order you would climb it. First, size each "
 "pool by rate times latency (how long each call takes); that is Little's law, and it says five hundred SMS a "
 "second at eighty milliseconds each needs forty threads. Give each channel its own pool, so a slow SMS provider "
 "cannot take email with it. Second, stop parking threads on sockets: non-blocking provider clients (they do not "
 "hold a thread while waiting for the reply) let eight threads keep ten thousand calls open. Third, and only then, "
 "leave the process: a message broker (a queue outside the process, like Kafka or SQS) with a topic per priority "
 "class, the claim in Redis, a row per record in a database. Say the arithmetic first; climbing the ladder "
 "without it is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "A client retrying a timed-out call (claim the key atomically; fifty threads, one gateway call). A gateway that "
 "times out so you do not know whether it sent (record UNKNOWN and retry with the <i>same</i> key). A malformed "
 "address (permanent: no retry at all, straight to the dead-letter list). A message that sat in the queue past "
 "its deadline (checked before the send, so the gateway is never called). A receipt for an attempt you have "
 "already moved past (a move must raise the rank or do nothing). Three in the morning where the recipient lives "
 "(defer to eight, do not drop &mdash; and an OTP walks through). A duplicate quietly eating the user's daily "
 "quota (a guard undoes whatever it reserved when a later guard refuses). A provider SDK (its client library) or a metrics "
 "listener that throws (one try/catch each; a broken listener is not allowed to stop a notification, and a broken adapter "
 "becomes an UNKNOWN rather than a lost worker). A flash sale that fills the bounded queue (refuse at the door, "
 "and undo every reservation the guards made, so the slot and the key both come back). And a fallback to another "
 "channel that climbs past an opt-out (only a FAILURE climbs; a suppression is a decision somebody made). A "
 "message parked at 3am, sent twice by the client and muted at 7am (judge it again when it wakes: one message at "
 "08:00, and the mute holds). A cancelled message whose deadline then passes (it stays cancelled, so it cannot "
 "turn into a failure and climb to SMS). Each of these is a few lines in FailureTests.java; a design that cannot "
 "show its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The second column is the defence: every name in the table arrived because a move produced it, so each can be "
 "defended in a sentence, and none of them is there because a book said so. One row needs more "
 "than a line, because it is the pattern people mis-name: a <b>Decorator</b> implements the same interface it "
 "wraps. <code>CircuitBreakerSender</code> holds a <code>Sender</code> and <i>is</i> a <code>Sender</code>; "
 "<code>JitteredBackoff</code> holds a <code>RetryPolicy</code> and <i>is</i> a <code>RetryPolicy</code>. The "
 "engine cannot tell the difference, which is why every channel gets the behaviour without an edit anywhere. And "
 "the two grey rows matter as much as the six above them: an interviewer learns more from a pattern you refused "
 "than from one you used, and page 05 has the argument for each.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "Read the table as a check, not a recital: every letter should point at a line of your own code, and if one "
 "points at nothing you named the principle rather than followed it. The letter carrying the most weight here is "
 "I, small interfaces. Clock, Scheduler and DeliveryListener have one method each, so a test fake is a lambda: "
 "<code>() -&gt; threeAm</code> is a clock standing at three in the morning. Sender, DeliveryGuard and RetryPolicy "
 "have two, so a fake is a ten-line class, like the gateway that times out twice on purpose. That is how the "
 "failure suite hands in a clock, a scheduler that runs every retry at once and a broken gateway, and still "
 "finishes in a fraction of a second.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (quiet hours, hold it for tomorrow, a fraud hold) is a new class behind <code>DeliveryGuard</code> plus one "
 "entry in the list handed to configure. Someone new who wants to know (delivery receipts, metrics, a data "
 "warehouse) is one more listener; the queue and the gate do not move. A new step in a life (BOUNCED, "
 "SCHEDULED) is one more state with a rank and the edges it may come from. A new invariant across messages "
 "(a rule that must always hold, such as at most one OTP a minute per user) is the check and the reserve inside the <i>same</i> gate, all or nothing. "
 "State that must outlive the process (persist it; ten instances) is the ledger behind a repository interface, "
 "and <code>moveTo</code> becomes <code>UPDATE ... SET state = ?, rank = ? WHERE id = ? AND rank &lt; ?</code> "
 "&mdash; the database refusing the stale write exactly as the compare-and-set does, with the row count as the "
 "boolean. For all five the engine, the queue and the tests do not change; that is the test that the derivation "
 "was right. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, Splitwise) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On this problem move 6 carries the most weight. The hard part of a "
 "notification service is not sending; it is what you write down when the gateway does not answer.")
print("move text built")

# ============================================================ page 03: the class diagram
uml_reset()
# column 1: the caller, the values it hands in, and the two time seams
put("caller", 10, 20, 290, "any caller", [], ["service.submit(n)", "service.statusOf(id)"])
put("notif", 10, 110, 290, "Notification",
    ["id / seq: String, long", "userId / templateId / category", "channel: Channel", "priority: Priority",
     "params: Map&lt;String, String&gt;", "dedupeKey: String  (optional)", "deadlineMs: long"],
    ["to(user, channel, tpl): Builder", "idempotencyKey(): String"])
put("recip", 10, 316, 290, "Recipient", ["userId / email / phone", "deviceToken: String", "zone: ZoneId"],
    ["addressFor(channel): String"])
put("rendered", 10, 442, 290, "RenderedMessage", ["title: String", "body: String"], [])
put("clock", 10, 528, 290, "Clock", [], ["nowMs(): long"], "interface")
put("sched", 10, 602, 290, "Scheduler", [], ["schedule(task, delayMs)"], "interface")
# column 2: the aggregate root and what it owns
put("svc", 320, 20, 330, "NotificationService",
    ["queue: PriorityBlockingQueue", "depth / outstanding: AtomicInteger", "ledger: Map&lt;id, DeliveryRecord&gt;",
     "byUser: Map&lt;userId, records&gt;", "gates: Map&lt;userId, UserGate&gt;", "guards: List&lt;DeliveryGuard&gt;",
     "senders: EnumMap&lt;Channel, Sender&gt;", "listeners: List&lt;DeliveryListener&gt;"],
    ["configure(templates, directory,", "  policy, guards, senders, clock, sched)", "addListener(l)",
     "submit(n): DeliveryRecord", "start() / shutdown()", "statusOf / recordOf / historyOf",
     "onReceipt(id, attempt, state, why)", "cancel(id) / deadLetters()"])
put("rec", 320, 336, 330, "DeliveryRecord",
    ["notification: Notification", "message: RenderedMessage", "progress: AtomicReference&lt;Progress&gt;",
     "listeners: List&lt;DeliveryListener&gt;"],
    ["moveTo(attempt, state, why): boolean", "cancelIfNotStarted(): boolean", "state() / attempt() / detail()"])
put("prog", 320, 506, 330, "Progress", ["attempt: int", "state: DeliveryState", "detail: String"],
    ["rank(): long", "rankOf(attempt, state): long"])
put("gate", 320, 638, 330, "UserGate", ["lock: ReentrantLock", "lastUsedMs: long"], [])
# column 3: the enums and the value types
put("chan", 670, 20, 240, "Channel", ["EMAIL, SMS, PUSH,", "IN_APP"], [], "enum")
put("prio", 670, 106, 240, "Priority", ["CRITICAL, HIGH,", "NORMAL, LOW"], [], "enum")
put("outcome", 670, 192, 240, "SendOutcome", ["SENT, TRANSIENT,", "PERMANENT, UNKNOWN"], [], "enum")
put("state", 670, 278, 240, "DeliveryState",
    ["CREATED, DEFERRED, QUEUED,", "SENDING, UNKNOWN,", "RETRY_SCHEDULED, SENT,", "SUPPRESSED, EXPIRED,",
     "FAILED_FINAL, DELIVERED"], ["rank(): int", "terminal(): boolean"], "enum")
put("sendres", 670, 452, 240, "SendResult", ["outcome: SendOutcome", "detail: String"],
    ["sent / transientFailure", "permanentFailure / unknown"])
put("verdict", 670, 578, 240, "Verdict", ["kind: ALLOW | SUPPRESS", "      | DEFER", "reason / untilMs"], [])
# column 4: the interfaces handed in
put("sender", 930, 20, 270, "Sender", [], ["channel(): Channel", "send(to, words, key): SendResult"], "interface")
put("guard", 930, 110, 270, "DeliveryGuard", [], ["name(): String", "check(n, r, now): Verdict", "undo(n, r)   (default: nothing)"], "interface")
put("policy", 930, 216, 270, "RetryPolicy", [], ["shouldRetry(attempts): boolean", "backoffMs(attempts): long"], "interface")
put("listener", 930, 306, 270, "DeliveryListener", [], ["onTransition(rec, from, to, why)"], "interface")
put("tpl", 930, 380, 270, "TemplateEngine", [], ["render(id, channel, params)"], "interface")
put("dir", 930, 454, 270, "RecipientDirectory", [], ["lookup(userId): Recipient"], "interface")
put("prefstore", 930, 528, 270, "PreferenceStore", [], ["enabled(user, channel, cat)"], "interface")
put("dedupestore", 930, 602, 270, "DedupeStore", [], ["claim(key, now, ttl): boolean", "release(key)"], "interface")
# the bottom row: the concrete classes, on three buses
for k, (name, note) in enumerate([("EmailSender", "SMTP"), ("FlakySmsSender", "times out twice"),
                                  ("PushSender", "APNs / FCM"), ("PreferenceGuard", "muted?"),
                                  ("QuietHoursGuard", "3am -&gt; defer"), ("DailyCapGuard", "reserves + undoes"),
                                  ("DedupeGuard", "claims the key"), ("ExponentialBackoff", "100, 200, 400")]):
    put("i%d" % k, 6 + k*149, 716, 146, name, [], [note])
put("standins", 10, 822, 1190, "the stand-ins that main and the tests hand in, and Main itself",
    ["InMemoryTemplates (holds MessageTemplate) is a TemplateEngine;   InMemoryDirectory is a RecipientDirectory;   InMemoryPreferences is a PreferenceStore",
     "InMemoryDedupeStore is a DedupeStore;   TimerScheduler is a Scheduler;   ConsoleAudit and Metrics are DeliveryListeners;   Main runs the demo"], [])

def stub(x, y1, y2):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x, y1, x, y2)
def bar(x1, x2, y):
    return '<path d="M%s %s H%s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y, x2)

EDGES = [
 # who calls what, and who owns what
 ln((300, 55), (320, 161), "assoc", "", [(310, 55), (310, 161)]),
 ln(B["svc"]["b"], B["rec"]["t"], "compose", ""),
 ln(B["rec"]["b"], B["prog"]["t"], "compose", ""),
 ln((320, 270), (320, 671), "compose", "", [(304, 270), (304, 671)]),
 _tx(296, 690, "one gate per recipient", "var(--muted)", 10.5, "end"),
 ln((320, 400), (300, 203), "assoc", "", [(310, 400), (310, 203)]),
 ln((320, 440), (300, 475), "assoc", "", [(312, 440), (312, 475)]),
 ln((650, 557), (670, 355), "assoc", "", [(660, 557), (660, 355)]),
 # the rules, handed in through configure()
 ln((650, 96), (930, 55), "inject", "", [(916, 96), (916, 55)]),
 ln((650, 180), (930, 153), "inject", "", [(908, 180), (908, 153)]),
 ln((650, 268), (930, 251), "inject", "", [(900, 268), (900, 251)]),
 ln((650, 440), (930, 333), "notify", "", [(892, 440), (892, 333)]),
 _tx(1200, 700, "the template engine, the directory and the two stores come in the same way", "var(--acc)", 10.5, "end"),
 # the three implementation buses
 stub(1122, 770, 791), ln((1122, 791), (1200, 251), "inherit", "", [(1222, 791), (1222, 251)]),
 stub(526, 770, 799), stub(675, 770, 799), stub(824, 770, 799), bar(526, 973, 799),
 ln((973, 799), (1200, 153), "inherit", "", [(1214, 799), (1214, 153)]),
 stub(79, 770, 807), stub(228, 770, 807), bar(79, 377, 807),
 ln((377, 807), (1200, 55), "inherit", "", [(1206, 807), (1206, 55)]),
]
UMLSVG = uml_svg(1230, 935, EDGES, legend_y=915)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements, and the three buses along the bottom say it once for each family: three senders, four guards, one retry '
 'policy. Filled diamond = owns: the service owns one record per notification and one gate per recipient, and a record '
 'owns its progress. Plain arrow = references. Dashed green = handed in through <code>configure(...)</code>; the '
 'template engine, the directory and the two stores come in the same way, and are left unlabelled only to keep the '
 'picture readable. Dotted blue = notifies. <b>Where state lives:</b> a notification holds nothing that moves &mdash; '
 'every field is final &mdash; and neither does a recipient, a rendered message, a guard or a sender. Everything that '
 'changes is in two places: the <code>Progress</code> inside a record, swapped as one object by compare-and-set, and '
 'the service\'s own queue, ledger, per-user log and gates. Notice what is <i>not</i> here: no Message class separate '
 'from Notification, because the words are rendered once at submit and stored on the record; no Retry class, because a '
 'retry is a state plus a scheduled re-queue; and no Boolean anywhere near the word "sent". The strip at the bottom '
 'names the eight small classes that main and the tests hand in, each with the interface it implements, and Main, which '
 'runs the demo.')
print("uml built")

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (sixteen blocks of claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (idempotency and the delivery guarantee first). '
 'Main.java is the complete answer, far more than anyone types in an hour. The must-write core is about 300 lines: '
 'Channel, Priority and DeliveryState with its ranks; the Notification with its builder; the Sender interface with '
 'one implementation; the DeliveryGuard interface with the de-dup guard; Progress and DeliveryRecord with moveTo; '
 'NotificationService with submit, the worker loop and deliver with its retry; and a main with a fifty-thread race '
 'on one de-dup key. Then, if time is left, in this order: the other guards (preference, daily cap, quiet hours), '
 'the templates, receipts and cancel, back-pressure. Know which version you were asked: Kotak wanted only template '
 'registration and a send API (follow-up 1); Cleartrip wanted order events sent to the right people (follow-up 2).'
 '</div></div>')

FU = [
("Add WhatsApp, and let product own the words: one template per message and per channel.", "functional", 5,
 "Three companies asked a version of this. Kotak (2026) wanted only two APIs: register a template for each "
 "channel, and send with it. Amazon (2025) asked for &ldquo;building message content for different channels&rdquo;, "
 "and Adobe (2025) named WhatsApp next to SMS and push. The registry is keyed by template id AND channel, because "
 "an SMS is not an email. Rendering happens once, at submit, and the words are stored on the record. A new provider "
 "is one class implementing Sender, one line in the map handed to <code>configure</code>, and one template per "
 "message; the queue, the guards, the retry policy and the state machine do not know how many channels exist. One "
 "cost is not free: Channel is an enum, so a real WhatsApp needs a constant, and the switch in "
 "<code>Recipient.addressFor</code> refuses to compile until you say which address it uses. That is the compiler "
 "doing your code review.",
 sect(src, "interface TemplateEngine", "interface RecipientDirectory") + "\n" + X("a new channel", "a flaky provider")),
("Order events: the customer hears every status, the seller only 'placed', logistics only 'shipped'.", "functional", 10,
 "This is Cleartrip's machine-coding question (2025, and again in 2026), and it sits above the engine. "
 "<code>OrderNotifier</code> keeps two tables. One says who is on each order: role to user id. The other says which "
 "channels each person wants for each event; a missing entry means the role's default. <code>publish(order, "
 "event)</code> turns one event into one ordinary notification per person and channel, so guards, retries and "
 "records all still apply, and the order system never waits. Each carries the de-dup key order|event|role, so the "
 "same event published twice sends nothing new. A replay (their bonus part) uses a fresh key on purpose, and goes "
 "to the channels the person has today. Changing a channel uses <code>ConcurrentHashMap.compute</code>, which makes the "
 "read-change-write one atomic step per key. The 2026 panel turned down a Kafka design: they wanted it working in "
 "90 minutes. Test 15 proves the routing.",
 X("order events to the people on the order", "Order Placed")),
("Persist it. And now there are ten instances behind a load balancer.", "twist", 8,
 "Ola (2024) and Blinkit (2026) spent most of the round here: the tables, the indexes, and Kafka against a plain "
 "API. Two tables and two shared stores, and the engine does not change, only what it is handed. The rank rule "
 "maps straight onto SQL: <code>moveTo</code> becomes <code>UPDATE ... SET state = ?, rank = ? WHERE id = ? AND "
 "rank &lt; ?</code>, and the row count is the boolean. The de-dup claim is an INSERT into a table with a UNIQUE "
 "index on the idempotency key (user, channel, the caller's key), or Redis <code>SET key NX PX ttl</code>. It must "
 "be that key, never our own id, because a client's retry arrives with a new id. The queue becomes a broker with a "
 "topic per priority class. The hand-off from submit to the queue becomes an outbox row (a note in the same "
 "database saying &ldquo;queue this&rdquo;), written in the same transaction as the record, so a crash between "
 "&ldquo;accepted&rdquo; and &ldquo;queued&rdquo; is recovered. One thing does change with ten instances: the id. "
 "&ldquo;n-&rdquo; plus one process's counter repeats across machines, so it becomes a UUID (a random 128-bit id "
 "that is unique without asking anyone).",
 X("persistence and the outbox", "exactly once is impossible") + "\n" + X("ten instances behind", "over the daily limit")),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "Adobe (2025) and PhonePe (2026) both asked which patterns you used and why. Moves 10 and 11 put every pattern and "
 "every SOLID letter next to the move that produced it, so this card is the exhibit: one line of real code each, "
 "to point at in the room. Three judgements are worth arguing out loud. Builder is earned: a notification has "
 "seven fields, four of them optional, and a seven-argument constructor with three nulls in it is how a promotion "
 "goes out on somebody's OTP template. Singleton is not earned: the service is handed to its callers, which is why "
 "the failure suite builds a fresh one for every test. Factory is not earned yet: the channel-to-sender map "
 "already <i>is</i> the registry, and it earns the name the day channels arrive as strings from a config file. Of "
 "the five SOLID letters, the one an interviewer tests is O, by changing a rule mid-round: quiet hours cost one new "
 "file and one entry in a list.",
 "// Strategy: the one line that differs per provider, behind an interface, handed in and never built here\n"
 "interface Sender { Channel channel(); SendResult send(Recipient to, RenderedMessage m, String idempotencyKey); }\n\n"
 "// Chain of Responsibility: independent reasons, in order, and the first one that does not say ALLOW stops the walk\n"
 "for (DeliveryGuard g : guards) { Verdict v = g.check(n, to, now); if (v.kind() != ALLOW) { verdict = v; break; } reserved.add(g); }\n"
 "if (verdict.kind() != ALLOW) for (int i = reserved.size() - 1; i >= 0; i--) reserved.get(i).undo(n, to);   // refused or parked: keep nothing\n\n"
 "// Decorator: a Sender that holds a Sender, and a guard that holds a guard, so the engine cannot tell the difference\n"
 "Map.of(Channel.SMS, new CircuitBreakerSender(new RateLimitedSender(sms, 50, 10, clock), 2, 60_000, clock));\n"
 "List.of(new HoldForTomorrowGuard(new DailyCapGuard(2)));\n\n"
 "// Observer: announced after the change is committed, one try/catch each\n"
 "for (DeliveryListener l : listeners) try { l.onTransition(this, from, to, detail); } catch (RuntimeException ignored) {}\n\n"
 "// State: one compare-and-set, and only if the rank goes UP\n"
 "if (want <= current.rank()) return false;\n\n"
 "// Builder: seven fields, four optional -- this is where a builder stops being ceremony\n"
 "Notification.to(\"u1\", Channel.SMS, \"otp\").priority(Priority.CRITICAL).dedupeKey(\"login-77\")\n"
 "            .category(\"otp\").params(Map.of(\"code\", \"4821\")).deadlineMs(now + 60_000).build();\n\n"
 "// Factory: not yet. The registry is already here; it earns the name when channels come from config strings\n"
 "Map<String, Sender> byName = Map.of(\"EMAIL\", new EmailSender(), \"WHATSAPP\", new WhatsAppSender());\n"),
("Each user may get at most two a day. Over the limit, do not drop the message: deliver it tomorrow.", "twist", 8,
 "This was Microsoft's LLD round (2024): jobs finish, each notifies its user by email or SMS, two a day at most, "
 "and the rest wait for the next day. The count is <code>DailyCapGuard</code>. It RESERVES a slot under the "
 "user's gate, so two threads cannot both take the last one, and if a later guard refuses the message, "
 "<code>undo</code> gives the slot back. The day is the user's own calendar day. Holding for tomorrow is one new "
 "class, <code>HoldForTomorrowGuard</code>: it wraps the cap and turns its &ldquo;no&rdquo; into &ldquo;park until "
 "the user's midnight&rdquo;. That is a Decorator on a guard. The engine needs no change, because a parked message "
 "is judged again, by every guard, when it wakes. At midnight it meets tomorrow's cap like any new message, and "
 "quiet hours, if it is in the list, moves it on to 08:00. Test 14 proves it: the third message is parked, goes "
 "out at midnight, and counts against the new day.",
 X("over the daily limit", "order events to the people") + "\n" + sect(src, "final class DailyCapGuard", "final class DedupeGuard")),
("The SMS gateway times out. Did the message go out or not? What do you write down?", "functional", 10,
 "You do not know, and the design says so. A send has three outcomes, not two: yes (SENT), no (PERMANENT, or "
 "TRANSIENT: try later), and no answer (UNKNOWN), which is what a timeout is. The record moves to SENDING before "
 "the call and to SENT only after the gateway has answered. A crash in between leaves it saying SENDING, which is "
 "the truth, instead of a boolean that is wrong either way. A timeout or a 503 (the provider's &ldquo;busy, try "
 "later&rdquo;) is retried with exponential backoff "
 "(each wait twice the one before) and with the SAME idempotency key, because the only place a duplicate can be "
 "removed is the provider. Exactly-once does not exist across a network you do not control. You pick "
 "at-least-once plus an idempotent receiver (a provider that treats a repeated key as one message), which is "
 "effectively-once. If the budget runs out while still UNKNOWN, do not guess: ask the provider by the key. "
 "Amazon's 2026 round put this as &ldquo;resend notifications if sending failed&rdquo;.",
 sect(src, "private void deliver(DeliveryRecord record)", "private void later") + "\n"
 + X("exactly once is impossible", "jittered backoff")),
("The SMS provider allows 5,000 a minute, it is throttling us, and every worker is parked on a socket to a gateway that is down.", "twist", 8,
 "The first two answers have the same shape: a class that implements Sender and holds a Sender, so the engine "
 "cannot tell the difference. The circuit breaker counts failures in a row. Past a threshold it answers TRANSIENT without "
 "a network call for the next minute, so a dead gateway costs nothing, and one success closes it again. The rate "
 "limiter is a token bucket (a counter that refills at a fixed rate; each send spends one token), per user by "
 "default. Amazon's 2026 version is the provider's own limit, 5,000 a minute: the same bucket keyed by channel, "
 "with capacity 5,000 and a refill of 83 a second. The bucket is one immutable value inside an AtomicReference, "
 "so &ldquo;refill, then spend one&rdquo; is one compare-and-set, and two threads cannot both spend the last "
 "token. Being refused is a TRANSIENT failure, so the engine's own backoff waits on the timer, not on a worker. "
 "The third failure is the one interviewers name: when the gateway comes back, ten thousand parked retries are "
 "all due in the same millisecond. <code>JitteredBackoff</code> is the same trick on the retry policy (it holds "
 "one and is one) and adds jitter (a random spread to each wait): three waits of 2,000 ms become 1,730, 1,749 and "
 "1,348.",
 X("a flaky provider", "the provider caps us") + "\n" + X("the provider caps us", "delivery receipts")
 + "\n" + X("jittered backoff", "one message, several channels")),
("Support asks \"what happened to notification n-8, and why did my user get nothing?\" a thousand times a second, and wants the log of everything user u1 was sent.", "non-functional", 5,
 "One hash lookup for the first question. The ledger maps id to record, and the record carries the answer as one "
 "immutable triple: which attempt, which state, and the reason in plain words, such as &ldquo;preference: opted "
 "out of marketing on PUSH&rdquo; or &ldquo;daily-cap: already had 20 today&rdquo;. A refused message still gets "
 "a record, because &ldquo;why did my user get nothing&rdquo; is the most common support question there is. The "
 "per-user log is Amazon's 2026 requirement: a second map, user id to that user's records, added to at submit, "
 "and <code>historyOf</code> returns a copy, oldest first. Neither read takes a lock: the progress lives in an "
 "AtomicReference, so a reader sees the old triple or the new one, never a mixture.",
 sect(src, "DeliveryState statusOf(String", "boolean onReceipt(String")),
("Providers now post delivery receipts, late and out of order. And product wants to know who opened and who clicked.", "twist", 5,
 "Nothing structural changes, because the rank rule was built for this. Every state carries a number, every move "
 "is a compare-and-set that lands only if it raises the rank, and a live state's rank is <code>attempt &times; "
 "100 + its number</code>. So a receipt for attempt 1 that arrives while attempt 2 is in flight is dropped. The "
 "finished states share one rank, and DELIVERED alone sits above them, on purpose: if the handset acknowledged "
 "it, it arrived, whatever we wrote after giving up. The webhook is a listener that remembers which provider "
 "reference belongs to which record, so the HTTP handler is three lines. Opened and clicked (Adobe, 2025) are not "
 "states: keep them as events with a time, next to the record. A click does not change whether the message was "
 "delivered, and it can arrive twice.",
 sect(src, "record Progress(int attempt", "final class DeliveryRecord") + "\n"
 + X("delivery receipts", "priority lanes")),
("\"Order Placed\" must reach the customer before \"Item Dispatched\". Your queue is asynchronous and it retries. How do you keep them in order?", "twist", 8,
 "Ajio asked this (2023) right after an asynchronous design. Two workers, or one retry, can reorder two messages: "
 "PLACED gets a 503, waits 200 ms for its retry, and SHIPPED overtakes it. <code>InOrderDispatcher</code> keeps "
 "one message in flight per ordering key, here the order id. The next message for that key is submitted only "
 "when the one before it is SENT or finished; until then it waits in a small queue for that key. It is a listener "
 "above the engine, so the engine does not change. SENT is the strongest order we control, because the provider "
 "can still reorder two texts; for &ldquo;the phone shows them in order&rdquo;, wait for DELIVERED and accept the "
 "delay. Test 16 shows both halves: without it SHIPPED arrives first, with it PLACED does.",
 X("Order Placed", "Runs every extension")),
("Two threads submit the same idempotency key at the same instant. Prove the human gets one message, with a test.", "non-functional", 10,
 "The race lives between &ldquo;has this key been claimed?&rdquo; and &ldquo;claim it&rdquo;. "
 "<code>putIfAbsent</code> is one operation: it returns the previous value, so exactly one of fifty threads sees "
 "null and wins, and the other forty-nine get a verdict with a reason on it. The claim is taken LAST, after every "
 "other guard has said yes, so a message we were going to refuse anyway does not burn the key. The proof is not a "
 "count of records; it is a count of gateway calls. Fifty threads wait on one latch (a start gun they all wait "
 "for), all fifty submit the same key, and the test then asks the fake push provider how many times it was "
 "called. One. It also checks that exactly one key is held in the store, not fifty, which is what catches a "
 "leaked reservation.",
 T("        // 1. fifty threads", "        // 2. the gateway times out")),
("One gate per user. Does that scale, or have you serialised the notification service?", "non-functional", 5,
 "It scales, and move 8 has the arithmetic: 1.2 microseconds inside the gate, against a gate that even a busy user "
 "touches a few times a second. This card adds the shape of the code that makes that number true, and the one "
 "case where it is not. The message is rendered BEFORE the gate is taken, so the part that can throw cannot leave "
 "a quota half-spent. The gate is released BEFORE anything is queued, and nothing inside it can block. The case "
 "where it is not true is one hot user id, say an alerting bot hammering one service account. The gate then "
 "serialises that account at about eight hundred thousand admissions a second, still far more than any gateway "
 "behind it can take. What actually pushes back is the queue. When it is full, submit gives back every "
 "reservation and returns a record saying <code>back-pressure: queue full</code>; back-pressure means refusing "
 "at the door so the caller slows down (test 9).",
 sect(src, "DeliveryRecord submit(Notification n)", "DeliveryState statusOf(String")),
("Minute 35. Compliance says no notifications between 9pm and 8am local time, except OTPs.", "twist", 10,
 "This is the rule-change twist, and the answer is a new file. Quiet hours has nothing in common with the rules "
 "already there: it needs the recipient's time zone, it only applies to channels that buzz a phone, and CRITICAL "
 "overrides it. In an if-ladder version it would be a fourth clause bolted into <code>submit</code>. Here it is "
 "one class implementing DeliveryGuard and one entry in the list handed to <code>configure</code>. It DEFERS "
 "rather than refuses, because a receipt the user wanted at 3am is still wanted at 8am; the wait runs on the "
 "scheduler the retries already use. Two details decide whether it is right. The hour is the recipient's zone "
 "(India is UTC+5:30), and the message wakes at 08:00 sharp, not &ldquo;five hours later&rdquo;. And at 08:00 it "
 "goes through every guard again: the user may have muted it overnight, the daily cap belongs to the day it is "
 "sent, and a client's retry of the same key must still meet the claim (test 11).",
 sect(src, "final class QuietHoursGuard", "final class DailyCapGuard")),
("A flood of CRITICAL alerts means marketing never goes out at all. Fix the starvation.", "twist", 5,
 "Say the trade first: a single priority queue really does have this failure. Ordering strictly by class means a "
 "steady flood of the top class starves the bottom one for ever. Two answers. The cheap one is ageing: a "
 "message's effective class improves the longer it waits, so nothing waits for ever, at the cost of an order that "
 "is no longer purely by class. The real one is a lane per class, each with its own workers and its own bound, so "
 "every class is guaranteed a share. The engine does not change; only the routing in front of it does. One trap: "
 "each lane is a whole service with its own gates, so two lanes must never share a DailyCapGuard, whose count is "
 "safe only behind one gate per user. Give each lane its own, or admit in one place and split only the delivery "
 "queues.",
 X("priority lanes", "batching for email")),
("Twenty alerts in a minute should be one email. And a million-message campaign must not become one spike.", "twist", 5,
 "Both live above the engine, not inside it. Batching cannot be a Sender: a Sender that buffered would have to "
 "answer SENT before the provider had seen anything, and that lie is what the three-way SendResult exists to "
 "prevent. So a collector holds lines for a window or until it is full, then submits ONE notification whose "
 "parameters are the joined lines; every guard, retry and receipt then applies to the digest. It submits outside "
 "its own lock, and with no de-dup key: a key built from the clock would make two batches closed in the same "
 "millisecond look like one, and the second would be dropped (test 13). Pacing is the same idea in time: the "
 "campaign is cut into chunks, and each chunk is handed to the Scheduler the retries use, so a million messages "
 "spread across an hour. Each chunk is a copy, because the timer reads it later and the caller may reuse its list.",
 X("batching for email", "campaign pacing") + "\n" + X("campaign pacing", "persistence and the outbox")),
("Push failed, so send it by SMS. And if the user turned push off, what then?", "twist", 8,
 "A ladder of channels, and like batching it lives above the engine. <code>ChannelLadder</code> is a listener: it "
 "remembers which rung each record it started is on, and when one ends in FAILED_FINAL or EXPIRED it submits the "
 "same message on the next channel. Every rung is a real notification with its own record, guards and retries, "
 "so &ldquo;where is n-8&rdquo; keeps one answer per send. The second half of the question separates a good "
 "answer from a careless one: only a FAILURE climbs. A SUPPRESSED does not, because a mute, a daily cap, a "
 "duplicate or a cancel is a decision somebody made. Texting a user because they turned push off is a compliance "
 "incident, not a fallback. A cancelled rung cannot climb later either: finished states share one rank, so it "
 "never becomes EXPIRED (test 12). The listener runs after the change is committed, with no lock held, which is "
 "why it may call submit. Test 10 proves both halves: a missing device token climbs exactly one rung; a muted "
 "push climbs none.",
 X("one message, several channels", "ten instances behind") + "\n"
 + T("        PushSender pushB = new PushSender();", "        // 11. a parked message")),
("Where does time come from, and how do you test quiet hours and backoff without sleeping?", "design", 3,
 "Two seams (places where a test swaps in its own version), both one-method interfaces, both handed in through "
 "configure. <code>Clock</code> answers &ldquo;what "
 "time is it&rdquo;, so a test stands at 03:00 in India by handing in a lambda. <code>Scheduler</code> answers "
 "&ldquo;run this later&rdquo;: production hands in one shared timer thread, never a sleeping worker, and a test "
 "hands in one that runs the task at once. One catch: a parked message is judged again when it wakes, so a test "
 "scheduler that runs it at once must also move the clock forward, or the message wakes at 03:00 and parks again. "
 "That is why the whole failure suite finishes in a fraction of a second with no fixed sleeps, while the backoff "
 "arithmetic is asserted on its own.",
 "/** Where time comes from, and where \"later\" comes from. Both injected, both one method. */\n"
 "interface Clock     { long nowMs(); }\n"
 "interface Scheduler { void schedule(Runnable task, long delayMs); }\n\n"
 "// production: one shared timer thread, so ten thousand pending retries cost ten thousand small objects\n"
 "service.configure(templates, people, policy, guards, senders, System::currentTimeMillis, new TimerScheduler());\n\n"
 "// a test: stand at 03:00 in India (Asia/Kolkata, UTC+5:30); when something must wait, jump the clock and run it now\n"
 "AtomicLong clock = new AtomicLong(atIndia(3, 0));\n"
 "Scheduler wakeOnTime = (task, delayMs) -> { clock.addAndGet(delayMs); task.run(); };\n"
 "service.configure(templates, people, policy, List.of(quiet), senders, clock::get, wakeOnTime);\n\n"
 "// and assert the arithmetic on its own, with no engine involved at all\n"
 "RetryPolicy backoff = new ExponentialBackoff(4, 100, 10_000);\n"
 "assert backoff.backoffMs(1) == 100 && backoff.backoffMs(2) == 200 && backoff.backoffMs(3) == 400;\n"
 "assert backoff.backoffMs(20) == 10_000;                 // capped, not overflowed to a year\n"),
]

build(dict(
    slug="notification-lld", title="Notification Service",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 16 failure blocks and a 50-thread de-dup race pass",
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
