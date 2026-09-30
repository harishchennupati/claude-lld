# Payment Gateway LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"payment-gateway/Main.java").read_text()
ext   = (H/"payment-gateway/Extensions.java").read_text()
tests = (H/"payment-gateway/FailureTests.java").read_text()

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
# four write flows, each a row; the accented box in every one of them is the claim -- the step that decides
rows = [("pay", 24, 240, 260, 1, [("claim the key", "one putIfAbsent: one attempt"),
                                  ("claim the payment", "CREATED to PENDING, under its lock"),
                                  ("call the acquirer", "outside the lock, with a timeout"),
                                  ("record what it said", "AUTHORIZED / CAPTURED / UNKNOWN")]),
        ("capture", 140, 330, 350, 0, [("claim it again", "AUTHORIZED to PENDING, the same lock"),
                                       ("call the acquirer", "outside the lock, with a timeout"),
                                       ("CAPTURED, or the claim back", "a refused capture keeps the hold")]),
        ("refund", 204, 240, 260, 1, [("what is left to refund?", "captured - refunded - reserved"),
                                      ("reserve it", "the check and the write, one step"),
                                      ("call the acquirer", "outside the lock, again"),
                                      ("turn it into a fact", "PARTIALLY_REFUNDED or REFUNDED")]),
        ("late news", 268, 330, 350, 1, [("a webhook, or the status query", "about the exact key we sent"),
                                         ("is it legal, and is it news?", "the transition table, then the rank"),
                                         ("apply it once, or drop it", "a duplicate changes nothing")])]
for lab, y, w, step, accat, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*step
        pf += _bx(x, y, w, 54, b[0], b[1], acc=(k == accat))
        if k < len(boxes)-1: pf += _ar("M%s %s H%s" % (x+w, y+27, x+step), True)
pf += _ar("M555 78 V88", dash=True) + _bx(355, 88, 450, 38, "declined or unknown: nothing is recorded as captured", "", dash=True)
pf += _tx(88, 352, "read", "var(--acc)", 13)
pf += _tx(175, 352, "at any moment: what is payment pay_1?   what did this merchant take today?   whose outcome do we still not know?",
          "var(--text)", 12, "start")
pf += _tx(615, 384, "fifty retries of the same request land at once: the acquirer must be called exactly once, and nothing may be written as captured before it answers",
          "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 400, pf)

# one morning, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:12  card, Rs.1,000", ["ord-1001 claims the key", "HDFC authorizes: AUTHORIZED",
                                 "fee 20.00 = 18.00 at 180 bp + 2.00", "no money has moved yet"], True),
      ("09:12  the phone retries", ["the same key, 50 ms later", "putIfAbsent loses: no second call",
                                    "the very same payment comes back"], False),
      ("11:30  UPI, Rs.99", ["NPCI takes it, then times out", "state UNKNOWN, not FAILED",
                             "one row on the job's list"], False),
      ("11:31  the job asks NPCI", ["statusOf(pay_5) says: captured", "the payment settles CAPTURED",
                                    "asking is not a second charge"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Take a payment: a merchant, an amount, a method and the merchant's idempotency key.</li>
<li>Route it to an acquirer that supports the method and the currency, with a failover list behind it.</li>
<li>Authorize, then capture &mdash; and collapse the two on rails that have no split (UPI).</li>
<li>Refund a captured payment, in full or in slices, never more than was captured.</li>
<li>Accept the acquirer's webhooks, which arrive late, twice and out of order.</li>
<li>Resolve a payment whose outcome is unknown, by asking the acquirer about the exact request we sent.</li>
<li>Tell the merchant what happened, and tell them again if their server was down.</li>
<li>Read a payment by our id or by their key, and a merchant's settlement for the day.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Fifty retries of one request must produce exactly one charge at the acquirer.</li>
<li>No lock is ever held across a network call, so a slow acquirer cannot queue the gateway.</li>
<li>Money is exact: integer paise with a currency, never a double.</li>
<li>Lookup by payment id and by idempotency key are O(1); nothing scans every payment.</li>
<li>Routing, fees, retry and risk rules are swappable without editing the flow.</li>
<li>Nothing half-done: a refusal or a timeout leaves the payment exactly as it was, and the caller can retry.</li>
<li>In memory, one process, no database (say it; every guard here has an obvious SQL twin).</li></ul></div></div>
'''

PROMPT = ('"Design a payment gateway. A merchant server sends us an amount, a payment method and an idempotency key; '
          'we pick an acquirer, authorize, capture, and later refund. Retries, timeouts and out-of-order callbacks are '
          'the normal case, not the edge case. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A shopper taps Pay. The merchant\'s server calls us with '
 'an amount, a card or a UPI handle, and a key of their own choosing so they can call us again safely. We pick an '
 'acquirer &mdash; the bank or switch that actually moves the money &mdash; and ask it to authorize, which only '
 'reserves the money; a later capture is what moves it. Afterwards the merchant may refund some or all of what was '
 'captured. Everything interesting happens because the acquirer is a computer somewhere else: it takes a quarter of '
 'a second to answer, it sometimes answers twice, it sometimes answers through a webhook an hour later, and it '
 'sometimes takes the money and never answers at all. The one thing that must always be true is that a customer is '
 'charged exactly once per request and never refunded more than was taken; and the one state nobody wants to write '
 'down &mdash; "I called them and I do not know what happened" &mdash; is the state that makes that possible.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with '
 'a <code>main</code> that pays, captures, refunds and then runs a retry storm. The interviewer is watching for, in '
 'this order: the questions you ask before typing (the money type and auth-versus-capture are the first two); which '
 'classes exist and which one owns a payment\'s state; a payment end to end; what happens when fifty retries of one '
 'request arrive at the same instant; where the rules that will change (routing, fees, retries, risk) live, so a new '
 'acquirer is a new class and not an edit; what happens when the acquirer never answers &mdash; that single question '
 'separates this round from every other LLD. Then the twists: 3-D Secure, partial capture, chargebacks, settlement, '
 'tokenisation, persistence.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Am I the gateway routing to acquirers, or the acquirer itself?</td><td>The gateway; acquirers are outbound</td><td><code>PaymentProcessor</code> is a port with adapters, not the thing I build (moves 1, 3)</td></tr>'
 '<tr><td>How is money represented, and one currency or many?</td><td>Integer paise plus a currency; one per payment</td><td><code>long</code>, never <code>double</code>; no currency ever mixes (move 1)</td></tr>'
 '<tr><td>Auth then capture, or one shot? Partial captures?</td><td>Auth then capture; full capture for now</td><td>Two states rather than one boolean, and a claim before each call (moves 6, 12)</td></tr>'
 '<tr><td>Who supplies the idempotency key, and what does a repeat mean?</td><td>The merchant; a repeat returns the first answer</td><td>One <code>putIfAbsent</code> is the whole retry story (moves 4, 5)</td></tr>'
 '<tr><td>When the acquirer times out, may I call it again?</td><td>No &mdash; ask its status API instead</td><td>An UNKNOWN state and a reconciliation job (moves 6, 9)</td></tr>'
 '<tr><td>Do acquirers call us back, and can callbacks arrive out of order?</td><td>Yes, at least once, out of order</td><td>A rank on every outcome, checked before every write (moves 6, 5)</td></tr>'
 '<tr><td>Refunds: partial, many of them, and who caps them?</td><td>Many partials, capped at what was captured</td><td>Reserve-then-settle rather than one counter (moves 4, 9)</td></tr>'
 '<tr><td>One process and in memory, or a database and many servers?</td><td>One process, in memory</td><td>No repository yet; every guard has a SQL twin (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> money is integer paise with a currency, never a double; the merchant\'s '
 'idempotency key decides everything, and a repeat of it returns the first answer whatever that answer was; authorize '
 'and capture are separate because card rails are; a timeout is not a failure, it is an unknown, and it is resolved by '
 'asking rather than by calling again; one process, in memory. Named as out of scope: 3-D Secure, partial capture, '
 'chargebacks, settlement files, tokenisation, persistence &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a MERCHANT takes a PAYMENT with a PAYMENT METHOD; an ACQUIRER moves the money; a REFUND sends some back; a WEBHOOK reports it late",
          "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 170, "Payment", "amount, state, refunds", 1), (228, 180, "Refund", "its own amount and state", 1),
                          (436, 210, "PaymentService", "the registries and the flow", 1), (676, 160, "Merchant", "an id and a URL", 0),
                          (866, 170, "Acquirer", "no state: an interface", 0), (1056, 155, "Method", "a token: a record", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state that changes, so it becomes a class.   dashed = an id, a value, an interface, or a question answered by a method", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("take a payment", "PaymentService (owns the registries)", "pay(key, merchant, amount, ...)"),
                                       ("claim the right to call", "Payment (owns its state and its lock)", "claim(CREATED, PENDING)"),
                                       ("move the money", "PaymentProcessor (owns the wire)", "authorize / capture / refund"),
                                       ("send money back", "Payment (owns the two counters)", "reserveRefund / settleRefund")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 268, "the flow touches state in two classes at once, so it goes to the one that owns both registries: PaymentService is the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 287, "and notice what is NOT a new verb: a capture. It is the same claim, the same call, the same record, one state further along", "var(--muted)", 11)
MV[2] = _mv(1230, 300, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 100, 220, 90, "PaymentService", "configure(...) hands them all in", acc=True)
for k, (t, sub, impl) in enumerate([("RoutingPolicy", "who to call, and in what order", "PreferredRouting / LeastCostRouting"),
                                    ("FeePolicy", "what the merchant is charged", "BpsFee: a flat paise plus basis points"),
                                    ("RetryPolicy", "when a failed call may be retried", "RetrySafeFailuresOnly: never a timeout"),
                                    ("RiskRule", "refuse before anything is tried", "AmountCapRule / CardTestingRule"),
                                    ("PaymentListener", "who is told a payment moved", "MerchantWebhook / AuditLog / the ledger")]):
    y = 24 + k*54
    m3 += _ar("M250 145 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 308, "the green dashed arrows = handed in. The gateway never builds a rule, so a new acquirer or a new price is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 328, "and one wrapper is not a rule at all: CircuitBreaker(acquirer) IS a PaymentProcessor holding a PaymentProcessor &mdash; that is where Decorator is born", "var(--acc)", 11)
MV[3] = _mv(1230, 345, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 190, 44, "retry #1", "reads state = CREATED") + _bx(30, 110, 190, 44, "retry #2", "reads state = CREATED")
m4 += _bx(350, 70, 190, 44, "pay_1.state", "CREATED", acc=True)
m4 += _ar("M220 52 H350 V70") + _ar("M220 132 H350 V114") + _tx(285, 40, "read", "var(--muted)", 10.5) + _tx(285, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="20" width="300" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(730, 45, "the gap", RED, 12) + _tx(730, 70, "both read CREATED, both call", RED, 11) + _tx(730, 90, "the customer is charged twice", RED, 11)
m4 += _tx(730, 130, "fix: read and write as ONE step", "var(--text)", 11)
m4 += _bx(910, 40, 290, 100, "Payment.lock", "claim, then call, then record", acc=True)
m4 += _tx(1055, 165, "the lock is per PAYMENT, not per gateway:", "var(--muted)", 10.5)
m4 += _tx(1055, 185, "two payments never wait for each other", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("have I seen this idempotency key?", "Map&lt;key, Payment&gt;.putIfAbsent", "O(1)"),
                                      ("what is payment pay_1?", "Map&lt;id, Payment&gt;", "O(1)"),
                                      ("what did this merchant take today?", "Map&lt;merchantId, List&lt;Payment&gt;&gt;", "O(1) + O(k)"),
                                      ("whose outcome do we not know?", "a Set&lt;id&gt;, written as it happens", "O(u), no scan"),
                                      ("have I seen this refund key?", "Map&lt;key, Refund&gt;", "O(1)"),
                                      ("is this move legal, and is it news?", "an EnumMap of edges, plus a rank", "O(1)")]):
    y = 20 + k*44
    m5 += _bx(30, y, 400, 40, q, "the question") + _ar("M430 %s H460" % (y+20), True)
    m5 += _bx(460, y, 540, 40, shape, "the shape", acc=True) + _ar("M1000 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 300, "nothing here ever re-reads the payments to answer a question, which is the mistake that makes a real gateway slow exactly when a sale starts", "var(--muted)", 11)
MV[5] = _mv(1230, 315, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D
top = [(20, 130, "CREATED", "nothing claimed"), (185, 130, "PENDING", "a call is out"), (350, 150, "AUTHORIZED", "money reserved"),
       (535, 140, "CAPTURED", "money moved"), (710, 200, "PARTIALLY_REFUNDED", "some sent back"), (945, 140, "REFUNDED", "all sent back")]
for x, w, t, sub in top: m6 += _bx(x, 60, w, 40, t, sub, acc=(t in ("CAPTURED", "PENDING")))
for a, b in [(150, 185), (315, 350), (500, 535), (675, 710), (910, 945)]: m6 += _ar("M%s 80 H%s" % (a, b), True)
m6 += _bx(185, 140, 130, 40, "UNKNOWN", "no answer", acc=True) + _bx(350, 140, 150, 40, "FAILED", "declined, or voided")
m6 += _ar("M250 100 V140") + _ar("M425 100 V140") + _ar("M315 160 H350")
# the two edges that run BACKWARDS, and they are the ones juniors leave out
m6 += _ar("M425 60 V34 H250 V60", acc=True) + _tx(355, 26, "a capture claims it back to PENDING", "var(--acc)", 10.5)
m6 += _ar("M215 60 V46 H85 V60") + _tx(128, 40, "un-claimed: the call never left", "var(--muted)", 10.5)
m6 += _ar("M810 60 V38 H880 V60", acc=True) + _tx(845, 32, "another partial", "var(--acc)", 10.5)
# the only ways out of UNKNOWN: ask, and apply whatever the answer is
m6 += _ar("M250 180 V205 H605 V100", acc=True) + _ar("M515 205 V120 H500", acc=True)
m6 += _tx(430, 226, "statusOf(the key we sent) settles it: CAPTURED, AUTHORIZED, or FAILED if the acquirer never saw it", "var(--acc)", 11)
m6 += '<rect x="20" y="242" width="1190" height="212" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(615, 266, "the order when a payment is taken, and why it is exactly this order", "var(--text)", 12)
for k, l in enumerate(["1  claim the idempotency key with one putIfAbsent -- nothing charged, and no retry can get past here",
                       "2  risk rules, routing and pricing: pure, no lock, no network, nothing written",
                       "3  take the payment's lock, move CREATED to PENDING, release it -- that is the claim",
                       "4  call the acquirer OUTSIDE the lock, with a timeout: this is the irreversible step",
                       "5  take the lock again and write what it said: AUTHORIZED, CAPTURED, FAILED -- or UNKNOWN if it never answered",
                       "6  release, then tell the merchant, in a try/catch, so a broken webhook cannot break a payment",
                       "a timeout leaves a payment that says \"ask again\", never one that says \"paid\"; the status query and the job close it",
                       "a refusal writes nothing at all, and the merchant's key is still theirs to retry with"]):
    m6 += _tx(35, 290 + k*22, l, "var(--muted)" if k > 5 else "var(--text)", 11, "start")
MV[6] = _mv(1230, 468, m6)

# move 7: what is inside the lock, and fifty retries at the same instant
m7 = _D + _card(30, 20, 540, 132, "inside the lock: about half a microsecond",
                ["one EnumSet check: is this move legal?", "one rank compare: is this news, or old news?",
                 "one enum write and three long writes", "roughly five field operations, and that is all",
                 "the lock is per PAYMENT, never per gateway"], acc=True)
m7 += _ar("M570 86 H640", True) + _tx(605, 76, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 132, "outside the lock: milliseconds to seconds",
            ["the card authorize: about 250 ms", "the UPI collect: about 120 ms",
             "the merchant webhook: about 40 ms, after unlock", "the shopper typing an OTP: 20 seconds",
             "the database write: about 5 ms (a follow-up)"])
m7 += _tx(615, 176, "fifty retries of one idempotency key at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 190, 106, 40, "retry %d" % (k+1), "wins the key" if k == 0 else "no socket", acc=(k == 0))
m7 += _tx(615, 258, "ten of the fifty drawn: the winner spends 250 ms on the network, the other forty-nine lose the putIfAbsent in about a hundred nanoseconds and open no socket at all", "var(--muted)", 11)
m7 += _tx(615, 276, "one at a time is true, and it lasts half a microsecond, because nothing slow is ever allowed inside the lock", "var(--muted)", 11)
MV[7] = _mv(1230, 290, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one lock per payment: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of a payment: ~5 field operations, about 0.4 us",
                       "a payment takes it twice: the claim and the record, 0.8 us in all",
                       "a busy Indian gateway: 2,000 payments a second at a sale peak",
                       "no two payments share a lock, so that is 2,000 separate locks",
                       "contention is per payment: 50 retries of ONE key, ~20 us total"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1  keep the acquirer call outside the lock", "already done: no lock ever spans the wire"),
                              ("2  swap the lock for one AtomicReference CAS", "the same claim; the losers fail in nanoseconds"),
                              ("3  beyond one process: the row is the lock", "UPDATE ... WHERE state = ?, plus a unique index on the key")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
m8 += _tx(615, 222, "the design that fails is the one that holds a lock AROUND the 250 ms call: that caps the whole gateway at four payments a second", RED, 11)
MV[8] = _mv(1230, 240, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("the same request arrives fifty times", "one putIfAbsent on the key; test 1: fifty threads, one charge"),
                                ("the acquirer never answers", "UNKNOWN, no retry, no failover; test 2: one call, nothing captured"),
                                ("and nobody ever closes that payment", "statusOf on the exact key we sent; test 3: it resolves both ways"),
                                ("a refund larger than the capture", "reserve under the lock; test 4: refused, and it reserves nothing"),
                                ("two refunds decided from one read", "reserve-then-settle; test 5: twenty threads, exactly ten win"),
                                ("a webhook arrives late, and twice", "the rank and the legality table; test 6: both are dropped"),
                                ("the primary acquirer is unreachable", "fail over, but never after a timeout; test 7: the backup takes it"),
                                ("the merchant's endpoint is down", "publish after the unlock, in a try/catch; test 8: it still captures")]):
    y = 18 + k*42
    m9 += _bx(30, y, 340, 38, bad, "") + _ar("M370 %s H400" % (y+19), True) + _bx(400, y, 800, 38, fix, "", acc=True)
m9 += _tx(615, 372, "every claim this design makes has a failure test: FailureTests.java runs eight of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 385, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface RoutingPolicy { List&lt;PaymentProcessor&gt; route(...); }", None), ("a cost-based route is a class, not an edit", None)],
          [("Adapter", "var(--text)"), ("move 3", None), ("class CardAcquirer implements PaymentProcessor", None), ("one vendor's dialect, translated in one file", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new CircuitBreaker(acquirer, 3, 30_000, clock)", None), ("a vendor written next year gets breaking free", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(p) after the unlock, inside a try/catch", None), ("the merchant hears; the payment never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("PaymentState.canGoTo(next)  +  outcomeRank()", None), ("a late webhook cannot rewind a payment", None)],
          [("Template Method", "var(--muted)"), ("not here", None), ("the flow is one method; the rules are handed in", "var(--muted)"), ("subclassing the gateway is how it rots", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("the gateway is handed to its callers", "var(--muted)"), ("a test builds a fresh PaymentService", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("the method-to-acquirer list IS the registry", "var(--muted)"), ("it earns the name when acquirers come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a payment has five fields and all five are required", "var(--muted)"), ("it would be ceremony, not a design", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 340, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 355, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Payment guards its own state; the service sequences; an acquirer class translates one vendor", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("LeastCostRouting is a new file plus one line in configure(); pay() is untouched", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody asks which", None), ("move 3", None), ("the UPI switch captures on authorize and the flow never notices: it asks capturesOnAuthorize()", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("seven one-method interfaces: routing, fees, retries, risk, listener, webhook endpoint, clock", None)],
          [("D", "var(--acc)"), ("depend on interfaces; the implementations are handed in", None), ("moves 3, 9", None), ("configure(...) and setClock(): a test hands in an acquirer that always times out", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "cost-based routing, a new price", "a new class behind the interface plus one configure line", "", "move 3"),
        ("someone new wants to know", "the ledger, the fraud desk, payouts", "one more listener; the flow and the lock do not change", "", "move 3"),
        ("a new step in a life", "3-D Secure: an OTP in the middle", "one more state and two rows in the transition table", "", "move 6"),
        ("a new invariant across items", "a merchant's daily refund cap", "the check and the writes inside the SAME lock: all or nothing", "", "move 4"),
        ("state that must outlive the process", "persist it; two servers", "the claim becomes a conditional UPDATE, the key a unique index", "UPDATE payments SET state = 'PENDING' WHERE id = ? AND state = 'CREATED'", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the Payment class, its lock and the eight tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>merchant</b> takes a <b>payment</b> from a shopper with a <b>payment method</b>; "
 "an <b>acquirer</b> moves the money; a <b>refund</b> sends some of it back; a <b>webhook</b> reports what happened, "
 "late. A payment has an amount, a state, an acquirer, a fee and two refund counters, all of which change: a class, "
 "and the most important one on the page. A refund has its own amount and its own life, so it is a class too, not a "
 "number on the payment &mdash; you cannot audit a number. The service has the registries and the flow: a class. A "
 "merchant is an id, a name and a URL that never move, so it is a record. A payment method is a token and a display "
 "string, which is the whole of PCI scope: there is no card number anywhere in the code. And an acquirer has no state "
 "of ours at all &mdash; it is a connection to somebody else &mdash; so it is an interface with one adapter per "
 "vendor. Notice what is <i>not</i> a class: a fee. It is a number a rule computes, stored on the payment.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Take a payment\" touches the idempotency map, the payment registry and the merchant index, and only the service "
 "sees all three, so <code>pay(...)</code> is the orchestrator. \"Claim the right to call the acquirer\" touches "
 "exactly one payment's state, so it belongs to the payment: <code>claim(CREATED, PENDING)</code>. \"Move the money\" "
 "touches nothing of ours at all &mdash; it is somebody else's computer &mdash; so it belongs to the acquirer port: "
 "<code>authorize</code>, <code>capture</code>, <code>refund</code>. \"Send money back\" touches the payment's two "
 "refund counters, so <code>reserveRefund</code> and <code>settleRefund</code> live there. And notice what is not a "
 "new verb: a capture. It is the same claim, the same call and the same record, one state further along, which is why "
 "the code for it is nine lines and why a UPI payment that has no capture step does not need a special case.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Four things will change, and you can name them before they are asked. <i>Who to call</i>: today by relationship, "
 "tomorrow by cost, and during an incident by whoever is still up. <i>What we charge</i>: a flat fee plus basis "
 "points today, something else next quarter. <i>When a failed call may be tried again</i>: and getting this one wrong "
 "is how customers get charged twice. <i>What to refuse before we try at all</i>: an amount cap today, a card-testing "
 "rule the Monday after a bad weekend. Each becomes a one-method interface the gateway is <i>given</i> in "
 "<code>configure()</code> and never builds, which is <b>Strategy</b>. A gateway that announces \"this payment moved\" "
 "without knowing what a merchant's server is, is <b>Observer</b>. Each acquirer class translating one vendor's "
 "dialect into ours is <b>Adapter</b>. And the one that earns its place loudest here is <b>Decorator</b>: "
 "<code>CircuitBreaker</code> <i>is</i> a <code>PaymentProcessor</code> that <i>holds</i> a "
 "<code>PaymentProcessor</code>, so \"stop sending traffic to a flapping acquirer\" is a wrapper, not an edit in "
 "every vendor class. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "A shopper's phone loses signal and retries. The merchant's queue redelivers. Their HTTP client times out at two "
 "seconds and fires again. Three threads read the payment as CREATED, all three believe they may call the acquirer, "
 "and the customer is charged three times &mdash; the single most common production incident in payments. So reading "
 "the state and writing it must be one step, in the class that owns it: the payment. There are two claims in front of "
 "two different gaps: <code>putIfAbsent</code> on the merchant's idempotency key decides which request is the request "
 "at all, and <code>claim(CREATED, PENDING)</code> decides which thread may open a socket. The lock is per "
 "<i>payment</i>, which is the whole trick: two payments never wait for each other, and the retries of one payment "
 "that do reach the lock are serialised for half a microsecond each. The same move covers refunds &mdash; the check \"is there "
 "enough left?\" and the write \"reserve it\" happen under one lock, before the acquirer is called.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "Three of those six rows are ordinary maps. Three are worth saying out loud. The idempotency key is not a lookup "
 "followed by a put &mdash; it is a single <code>putIfAbsent</code>, because a lookup followed by a put is the very "
 "race it was there to prevent. \"Whose outcome do we not know?\" is a set of ids written the moment a call times "
 "out, not a query run later: the moment you catch yourself planning to scan for unknown payments, the round is "
 "already lost, and this way the reconciliation job reads a handful of rows instead of every payment ever taken. And "
 "the two questions asked on every single write &mdash; is this move legal, and is this news or old news? &mdash; are "
 "an <code>EnumMap</code> of allowed edges and one integer rank per state: two array lookups and a comparison, with "
 "no branching and nothing to keep in sync.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is the design.",
 "A payment is CREATED when the key is claimed, PENDING while a call is out, AUTHORIZED when the money is reserved, "
 "CAPTURED when it moves, PARTIALLY_REFUNDED and then REFUNDED as it goes back, FAILED if it was refused &mdash; and "
 "UNKNOWN when we called and got nothing back. That last one is the state juniors leave out and the state the whole "
 "round is about. Two of the arrows point backwards, and they are the other two everyone forgets: a capture takes an "
 "AUTHORIZED payment back to PENDING while its call is out, and a call that provably never left the building hands "
 "the claim back to exactly where it started. That is why the rank is a second number and not the state itself "
 "&mdash; the state is allowed to move backwards, the rank never is, so a stale webhook still cannot rewind a "
 "payment that has moved on. Writing the machine down forces the order, and the order is this: claim the merchant's key with one "
 "<code>putIfAbsent</code>; run the risk rules and pick the route, which are pure and touch no lock; take the "
 "payment's lock just long enough to move CREATED to PENDING and let go; call the acquirer <i>outside</i> the lock "
 "with a timeout, because that is the irreversible step; take the lock again and write down what it said; release, "
 "then tell the merchant inside a try/catch. Nothing is ever recorded as captured before the acquirer says captured. "
 "A timeout therefore leaves a payment that says \"ask again\", which <code>statusOf(the key we sent)</code> can "
 "answer in either direction: it took the money, or it never saw the request.", 6),
("Move 7: yes, the lock makes one payment's calls happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every payment takes a lock, is the gateway now a queue? "
 "It is, for about half a microsecond, and only for the retries of that one payment. Inside the lock there is one "
 "<code>EnumSet</code> membership check, one integer comparison against the rank reached, one enum write and three "
 "long writes: roughly five field operations. Everything slow is outside it, deliberately &mdash; the card authorize "
 "at about two hundred and fifty milliseconds, the UPI collect at a hundred and twenty, the merchant's webhook at "
 "forty, the shopper typing an OTP for twenty seconds. The lock is private to <code>Payment</code> and every method "
 "on that class takes it and gives it back before returning, which is not tidiness: it makes it <i>impossible</i> for "
 "the flow to hold a lock across the wire, because the flow is never handed one. So when fifty retries arrive at the "
 "same instant, one wins the key in about a hundred nanoseconds and forty-nine lose in about the same, having opened "
 "no socket at all.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A busy Indian gateway at a sale peak takes two thousand payments a second. Each takes its own payment's lock twice "
 "&mdash; once to claim, once to record &mdash; for about four hundred nanoseconds a time, and no two payments share "
 "a lock, so that is two thousand independent locks each busy for under a microsecond. The only contention that "
 "exists is the retry storm on one payment: fifty threads, twenty microseconds in all, and forty-nine of them never "
 "reach the lock because they lost the idempotency key first. Now say the number that matters most, by contrast: a "
 "lock held <i>around</i> the two-hundred-and-fifty-millisecond acquirer call would cap the entire gateway at four "
 "payments a second, and preventing exactly that is why this move exists. The ladder is in the picture; the rung "
 "worth explaining is the last one, where the row itself becomes the lock &mdash; <code>UPDATE payments SET state = "
 "'PENDING' WHERE id = ? AND state = 'CREATED'</code> updates one row or none, which is the same compare-and-set, "
 "and a unique index on the idempotency key does what <code>putIfAbsent</code> does today.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The picture is the list, and a design that cannot show its tests is only a claim. Three of the eight rows are "
 "where candidates are actually lost. A refund larger than "
 "what was captured must be refused <i>and</i> must reserve nothing, or the next honest refund is refused for a "
 "ghost. Two refunds decided from the same read must not both win: twenty threads refunding a hundred each against a "
 "thousand, and exactly ten may succeed. And the acquirer that never answers must be neither retried nor failed over, "
 "because either one is how a customer pays twice &mdash; the test asserts that exactly one call was made and that "
 "nothing was recorded as captured. Each row is a few lines in FailureTests.java, and the page you are reading "
 "refuses to build unless all eight of them pass.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; the paragraph is for the rows that get argued with. Decorator is the loudest name on this "
 "problem and the one to say first: <code>CircuitBreaker</code> is a processor that <i>holds</i> a processor, so "
 "\"stop sending traffic to a flapping acquirer\" reaches vendors written next year without touching one of them, and "
 "because the wrapper reports the wrapped acquirer's own <code>name()</code>, routing and the stored acquirer name "
 "never learn it exists. The four grey rows earn their place as much as the five white ones: naming a pattern you "
 "did <i>not</i> use is how you show you were choosing rather than decorating. Template Method earned nothing here "
 "because the flow is one method with its rules handed in, and subclassing a gateway to change routing is how "
 "gateways rot; Factory is \"not yet\" rather than \"no\", because the method-to-acquirer map is already the registry "
 "and it earns the name the day acquirers arrive as strings from configuration. Say them in the order the moves "
 "produced them, never as a list you memorised.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is not a list to recite; it is the check that the moves did their job, and the table is the whole answer. "
 "Two letters are worth defending out loud on this problem. I says keep interfaces small: seven of the eight here "
 "have exactly one method, so a fake for a test is a lambda &mdash; and the eighth, <code>PaymentProcessor</code>, "
 "has eight methods because a vendor is wide, which is worth saying rather than pretending otherwise. D says depend "
 "on interfaces and be handed the implementations, and the reason to care is not tidiness: it is that a test can "
 "hand this gateway an acquirer that takes the money and then times out, which is the one scenario you cannot "
 "produce any other way.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (route by cost, a new price, a new risk check) is a new class behind an existing interface plus one "
 "line in configure. Someone new who wants to know (a double-entry ledger, a fraud desk, the payouts job) is one "
 "more listener, and the flow and the lock do not change. A new step in a life (3-D Secure, an OTP page between the "
 "request and the authorize) is one more state and two rows in the transition table. A new invariant across items (a "
 "merchant's daily refund cap) is the check and the writes inside the <i>same</i> lock, all or nothing. State that "
 "must outlive the process is the claim becoming a conditional <code>UPDATE</code>, the idempotency key becoming a "
 "unique index, and the merchant webhook becoming an outbox row written in the same transaction as the payment. For "
 "all five, the Payment class, its lock and the eight failure tests do not change &mdash; which is the test that the "
 "derivation was right. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, Splitwise, BookMyShow) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On this problem moves 4 and 6 carry the round, because the irreversible step "
 "is somebody else's computer: everything here is about what you write down before you call it, and what you write "
 "down when it does not answer.")

# ============================================================ page 03: the class diagram
uml_reset()
# column 1: everything the gateway is handed -- listeners, the risk rule, the retry rule, the clock, the money helper
put("listener", 10, 20, 225, "PaymentListener", [], ["onEvent(e)"], "interface")
put("hook", 10, 95, 225, "MerchantWebhook", ["urls, maxAttempts"], ["onEvent(e): POST, retries"])
put("audit", 10, 190, 225, "AuditLog", [], ["onEvent(e): append"])
put("risk", 10, 270, 225, "RiskRule", [], ["check(merchant, paise, m)"], "interface")
put("cap", 10, 345, 225, "AmountCapRule", ["caps: EnumMap"], ["check(): may throw"])
put("retryi", 10, 440, 225, "RetryPolicy", [], ["retry(attempts, failure)"], "interface")
put("retry", 10, 515, 225, "RetrySafeFailuresOnly", [], ["only a call that never left", "never after a timeout"])
put("clock", 10, 610, 225, "Clock", [], ["nowMs(): long"], "interface")
put("money", 10, 685, 225, "Money", [], ["rupees(\"12.50\"): long", "fmt(paise) / bps(p, bp)"])
put("currency", 10, 775, 225, "Currency", ["INR, USD"], [], "enum")

# column 2: the aggregate root and what it owns
put("svc", 285, 20, 345, "PaymentService",
    ["merchants / byId / byKey: Map", "byMerchant: Map&lt;id, List&gt;", "refundsById / refundsByKey: Map",
     "unresolved: Set&lt;String&gt;", "processors: List&lt;Processor&gt;", "listeners: List&lt;Listener&gt;",
     "routing / fees / retries / risk", "clock: Clock"],
    ["configure(routing, fees, ...)", "pay(key, merchant, paise, m)", "capture(paymentId)",
     "refund(key, paymentId, paise)", "handleWebhook(id, state, ref)", "resolveUnknown(id)",
     "reconcile(staleMs)", "paymentsOf(m) / settlementOf(m)"])
put("pay", 285, 340, 345, "Payment",
    ["id / idemKey / merchantId", "paise: long,  currency", "method: PaymentMethod", "state: PaymentState",
     "rankReached: int", "acquirer / acquirerRef / inFlightKey", "feePaise / capturedPaise",
     "refundedPaise / refundReserved", "lock: ReentrantLock (private)"],
    ["claim(from, to, acq, fee, key)", "settle(outcome, ref, why, now)", "markUnknown(why, now)",
     "revertClaim(why, now)", "reserveRefund(paise): boolean", "releaseRefund / settleRefund",
     "refundablePaise(): long"])
put("refund", 285, 660, 345, "Refund",
    ["id / idemKey / paymentId", "paise: long", "state: RefundState", "acquirerRef / failureReason"],
    ["succeed(ref) / fail(why)", "unknown(why)"])

# column 3: the enums and the value records
put("pstate", 665, 20, 255, "PaymentState",
    ["CREATED, PENDING, AUTHORIZED", "CAPTURED, PARTIALLY_REFUNDED", "REFUNDED, FAILED, UNKNOWN"],
    ["canGoTo(next): boolean", "outcomeRank(): int"], "enum")
put("rstate", 665, 165, 255, "RefundState", ["PENDING, SUCCEEDED", "FAILED, UNKNOWN"], [], "enum")
put("mtype", 665, 252, 255, "PaymentMethodType", ["CARD, UPI, NETBANKING"], [], "enum")
put("outcome", 665, 323, 255, "Outcome", ["AUTHORIZED, CAPTURED, DECLINED", "REFUNDED, NOT_FOUND"], [], "enum")
put("method", 665, 410, 255, "PaymentMethod", ["type: PaymentMethodType", "token / display: String"], [])
put("merchant", 665, 497, 255, "Merchant", ["id / name / webhookUrl"], [])
put("event", 665, 568, 255, "PaymentEvent", ["paymentId / merchantId", "state / paise / captured", "refunded / acquirer / reason"], [])
put("result", 665, 671, 255, "ProcessorResult", ["outcome: Outcome", "ref / reason: String"], [])
put("vmode", 665, 757, 255, "VendorMode", ["HEALTHY, DECLINE,", "DOWN, TIMEOUT_CHARGED"], [], "enum")

# column 4: the acquirers behind one port, and the rules about them
put("proc", 955, 20, 265, "PaymentProcessor", [],
    ["name() / feeBps()", "supports(type, currency)", "capturesOnAuthorize()", "authorize(key, paise, cur, m)",
     "capture / refund(key, ref, p)", "statusOf(key): Result"], "interface")
put("card", 955, 175, 265, "CardAcquirer", ["byKey: the vendor's own"], ["authorize: AUTHORIZED", "capture: CAPTURED"])
put("upi", 955, 286, 265, "UpiSwitch", [], ["authorize: CAPTURED", "capturesOnAuthorize = true"])
put("breaker", 955, 377, 265, "CircuitBreaker", ["inner: PaymentProcessor"], ["trips after n failures", "then ProcessorUnavailable"])
put("routei", 955, 490, 265, "RoutingPolicy", [], ["route(type, cur, paise, all)", "  : List&lt;PaymentProcessor&gt;"], "interface")
put("route", 955, 581, 265, "PreferredRouting", [], ["a preferred acquirer per method", "the rest are the failover tail"])
put("feei", 955, 672, 265, "FeePolicy", [], ["feeFor(paise, type, acq)"], "interface")
put("fee", 955, 747, 265, "BpsFee", [], ["flat + the acquirer's bps"])

# the bottom band: the three ways a call can end badly, and the seam the merchant's server sits behind
put("exRej", 10, 862, 225, "PaymentRejected", ["a rule said no:", "nothing was tried"], [])
put("exTo", 285, 862, 345, "ProcessorTimeout", ["no answer: the money MAY have moved", "-> UNKNOWN, no retry, no failover"], [])
put("exUn", 665, 862, 255, "ProcessorUnavailable", ["it never left the building", "-> un-claim, try the next one"], [])
put("hookep", 955, 862, 265, "WebhookEndpoint", [], ["post(url, e): boolean  (a seam)"], "interface")

def hstub(x1, x2, y):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y, x2, y)

EDGES = [
 # implementations, up their own column
 ln(B["hook"]["t"], B["listener"]["b"], "inherit"),
 ln((10, 217), (10, 47), "inherit", "", [(3, 217), (3, 47)]),      # AuditLog: up the outside, so it crosses no box
 ln(B["cap"]["t"], B["risk"]["b"], "inherit"),
 ln(B["retry"]["t"], B["retryi"]["b"], "inherit"),
 ln(B["route"]["t"], B["routei"]["b"], "inherit"),
 ln(B["fee"]["t"], B["feei"]["b"], "inherit"),
 # the three acquirer classes share one spine up into the port they implement
 ln((940, 422), (955, 87), "inherit", "", [(940, 87)]),
 hstub(955, 940, 220), hstub(955, 940, 321), hstub(955, 940, 422),
 # the decorator IS what it holds: one bracket up the outside
 ln((1220, 410), (1220, 120), "assoc", "", [(1227, 410), (1227, 120)]),
 _tx(1213, 371, "wraps one", "var(--muted)", 10.5, "end"),
 # the service owns the payments and the refunds; a payment owns nothing but its own numbers
 ln(B["svc"]["b"], B["pay"]["t"], "compose", "every payment"),
 ln((285, 200), (285, 700), "compose", "", [(268, 200), (268, 700)]),
 _tx(280, 678, "owns every refund", "var(--muted)", 10.5, "end"),
 # a payment points at its state and its method; a refund at its state; the service at its merchants
 ln((630, 430), (665, 443), "assoc", "", [(659, 430), (659, 443)]),
 ln((630, 400), (665, 95), "assoc", "", [(653, 400), (653, 95)]),
 ln((630, 700), (665, 198), "assoc", "", [(641, 700), (641, 198)]),
 ln((630, 120), (665, 522), "assoc", "", [(647, 120), (647, 522)]),
 # the service calls whichever acquirers the route named
 ln((630, 160), (1087, 154), "assoc", "", [(645, 160), (1087, 160)]),
 _tx(790, 153, "calls the route", "var(--muted)", 10.5),
 # the rules and the clock, handed in through configure(); the listeners are notified
 ln((630, 311), (955, 525), "inject", "", [(925, 311), (925, 525)]),
 ln((630, 318), (955, 699), "inject", "", [(931, 318), (931, 699)]),
 ln((285, 80), (235, 47), "notify", "", [(258, 80), (258, 47)]),
 ln((285, 110), (235, 297), "inject", "", [(250, 110), (250, 297)]),
 ln((285, 140), (235, 467), "inject", "", [(244, 140), (244, 467)]),
 ln((285, 170), (235, 637), "inject", "", [(238, 170), (238, 637)]),
 _tx(615, 846, "the bottom row: what a call can throw, and which of the two it is decides whether the payment may be tried again",
     "var(--muted)", 11),
]
UMLSVG = uml_svg(1230, 985, EDGES, legend_y=958)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the service owns every payment and every refund. Plain arrow = references. '
 'Dashed green = handed in through <code>configure()</code> or <code>setClock()</code>. Dotted blue = notifies. '
 '<b>The columns.</b> Left: everything the gateway is <i>given</i> &mdash; listeners, the risk rule, the retry rule, '
 'the clock. Centre: the aggregate root and what it owns. Right of centre: the enums and the value records, which '
 'hold no behaviour. Far right: the acquirers behind one port, plus the two rules that are about acquirers. '
 '<b>The bottom row</b> has no arrows because nobody owns it: three exceptions, which are how a call ends when it '
 'does not return a result, and the one seam the merchant\'s server sits behind. <code>ProcessorTimeout</code> and '
 '<code>ProcessorUnavailable</code> are the two most important types on this page &mdash; one means "the money may '
 'have moved", the other means "it never left" &mdash; and telling them apart is what stops a retry from charging '
 'twice. <code>VendorMode</code> is the only box that is not production code: it is the knob the two fake acquirers '
 'expose so a test can make one decline, go down, or take the money and then time out. '
 '<b>Where state lives:</b> <code>Payment</code> owns its state, its rank, its fee, its captured amount, its two '
 'refund counters and its own private lock &mdash; and it is the only class in the system that may change any of '
 'them. <code>PaymentService</code> owns the registries and the order of operations and nothing else; it holds no '
 'lock at all, which is why it cannot hold one across a network call. An acquirer holds no state of ours. Notice what '
 'is <i>not</i> here: no card number anywhere, because <code>PaymentMethod</code> carries a token; and no Fee class, '
 'because a fee is a number a rule computes and the payment stores.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does and what it guarantees; read only those first for the shape, then the bodies for '
 'the mechanics &mdash; and read <code>Payment.claim</code> and <code>Payment.settle</code> twice, because everything '
 'else on this page is arrangement. Each copy button copies that whole file for your IDE. Below Main.java: '
 'Extensions.java (every follow-up\'s reference code, with an <code>ExtDemo</code> main that runs all of it) and '
 'FailureTests.java (eight claims proven; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java '
 'FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (the money type and auth-versus-capture first); then '
 'type in the order of Main.java: Currency and Money, PaymentMethodType and the PaymentMethod record, PaymentState '
 'with its transition table and its ranks, the Clock and the three exceptions (a rule\'s refusal, and the two an '
 'acquirer can throw), ProcessorResult and the '
 'PaymentProcessor interface with one acquirer behind it, the four rule interfaces with one implementation each, the '
 'listener and its two implementations, Refund, then Payment with its private lock and its claim / settle pair, then '
 'PaymentService with the order at pay(), then a main with fifty threads on one idempotency key.</div></div>')

FU = [
("Cards over five thousand rupees now need 3-D Secure: an OTP page in the middle of the payment.", "twist", 10,
 "This is a new step in a life, which is move 6. The honest version inside the machine is one more constant, "
 "PENDING_AUTH, and two rows in the transition table: CREATED goes to PENDING_AUTH, and PENDING_AUTH goes to "
 "AUTHORIZED or FAILED; <code>pay()</code> returns before the acquirer is called and a new <code>resume(id, "
 "token)</code> re-enters the ordinary flow. The reference code puts the challenge in front of the gateway instead, "
 "so the enum on page 03 stays exactly as it is drawn: a big card payment comes back as a challenge rather than a "
 "payment, nothing has been claimed, nothing has been charged, and the merchant's idempotency key is still free. A "
 "wrong or expired OTP refuses and leaves the key free to try again; a right one calls <code>pay()</code> with that "
 "same key, so idempotency, routing and the claim are all untouched.",
 X("3-D Secure", "partial capture")),
("Fifty retries of the same request hit us at the same instant. Prove the customer is charged once, with a test.", "non-functional", 10,
 "There are two races, and the test kills both. The first is which request is the request at all: the merchant's "
 "idempotency key goes into the map with one <code>putIfAbsent</code>, so exactly one thread creates the payment and "
 "the other forty-nine get that same object back. Under a true simultaneous storm the losers do build an object and "
 "take an id number first &mdash; ids are cheap and are never shown to the merchant &mdash; but only one of those "
 "objects is ever in the map, and only that one thread goes on. The second race is which thread may open a socket: "
 "<code>claim(CREATED, PENDING)</code> is a compare-and-set under the payment's own lock, so even if two threads "
 "somehow reached it only one proceeds. The proof is not a count of successes but a count at the vendor: the fake "
 "acquirer counts every request that reaches it, fifty threads wait on one latch, and afterwards the test asserts one "
 "distinct payment id and exactly one call.",
 sect(src, "    Payment pay(", "    private void authorizeAlong") + "\n"
 + T("        // 1. fifty threads", "        // 2. the acquirer takes")),
("The acquirer takes the money and then the socket dies. What is the state of the system, and what do you do next?", "functional", 10,
 "Not FAILED, and not captured: UNKNOWN. That is the only honest answer, because the money may or may not have moved "
 "and nothing in the response tells you which. Three things follow, and they are the whole difference between a "
 "gateway and a double-charging machine. The payment is not retried, because retrying a call that may already have "
 "charged is how a customer pays twice. It is not failed over to the next acquirer, for the same reason &mdash; note "
 "the code distinguishes a timeout from a refused connection, which provably never reached the vendor and IS safe to "
 "fail over. And the payment's id goes into a set the reconciliation job reads, so nobody has to scan. The job asks "
 "<code>statusOf</code> about the exact key we sent and settles it in whichever direction the vendor says, including "
 "\"I never saw that request\".",
 sect(src, "    private void authorizeAlong", "    Payment capture(")),
("One lock per payment. Does that scale, or have you serialised the gateway?", "non-functional", 5,
 "It scales, and the answer is arithmetic: the locked part is about five field operations, roughly four hundred "
 "nanoseconds, taken twice per payment, and no two payments share a lock. Two thousand payments a second is "
 "therefore two thousand independent locks each busy for under a microsecond, and the only real contention is a "
 "retry storm on one payment &mdash; fifty threads, twenty microseconds in total. The contrast is the sentence to "
 "say out loud: a lock held <i>around</i> the two-hundred-and-fifty-millisecond acquirer call would cap the whole "
 "gateway at four payments a second. What makes that impossible here is structural rather than careful: the lock is "
 "private to <code>Payment</code>, and every method on that class takes it and gives it back before returning, so "
 "the flow is never handed a lock it could hold across the wire.",
 sect(src, "    boolean claim(", "    boolean markUnknown(")),
("The merchant refunds three hundred, then eight hundred, on a thousand-rupee payment, from two tabs at once.", "functional", 10,
 "One of them is refused, and the refused one leaves nothing behind. The trap is a single counter written after the "
 "acquirer answers: both tabs read \"a thousand refundable\", both call the vendor, and the merchant has refunded "
 "eleven hundred of a thousand. So the amount is reserved <i>before</i> the call: under the payment's lock the code "
 "checks captured minus refunded minus already-reserved and adds to the reservation in the same step, which is why "
 "the second tab is refused on the read the first tab has already changed. When the vendor says yes the reservation "
 "becomes a settled refund and the payment moves to PARTIALLY_REFUNDED or REFUNDED; when it says no, or the call "
 "never left, the reservation is handed straight back. A refund whose call timed out is the one case where the "
 "reservation is deliberately kept, because the money may be on its way.",
 sect(src, "    boolean reserveRefund(", "    @Override public String toString")),
("The acquirer's webhook arrives an hour late, out of order, and then arrives again.", "twist", 5,
 "None of that needs new code, because the webhook path and the response path are the same method. Every outcome "
 "carries a rank &mdash; authorized and failed rank one, captured two, partially refunded three, refunded four "
 "&mdash; and the payment remembers the highest rank it has ever reached. A report is applied only if its rank beats "
 "that number and the move is legal in the transition table, so a duplicate loses on equality, an \"authorized\" "
 "arriving after a capture loses on rank, and a \"captured\" arriving after a partial refund loses on both. The "
 "rank is deliberately separate from the state, which is what lets a claim move the state backwards (AUTHORIZED to "
 "PENDING for a capture) without opening a hole for a stale callback. And when the news IS new, it lands: a webhook "
 "that beats the status query closes an UNKNOWN payment and takes it off the reconciliation list.",
 sect(src, "    boolean settle(", "    boolean markUnknown(") + "\n"
 + sect(src, "    boolean handleWebhook(", "    boolean resolveUnknown(")),
("Our primary acquirer is flapping. Route around it, during the incident, without a deploy.", "twist", 10,
 "Two pieces, and neither touches the flow. The routing policy is an interface that returns a <i>list</i>, best "
 "first, and the tail of that list is the failover plan; swapping PreferredRouting for LeastCostRouting is a new "
 "class and one line in configure, and the field is volatile so it can be swapped live. The circuit breaker is the "
 "other half: it is a PaymentProcessor that holds a PaymentProcessor, counts consecutive failures, and after the "
 "threshold fails every call instantly as ProcessorUnavailable &mdash; which the router already reads as \"try the "
 "next one\" &mdash; then half-opens after the cool-off. Because it reports the wrapped acquirer's own name, routing "
 "and the stored acquirer name never learn it exists.",
 sect(src, "class CircuitBreaker", "interface RoutingPolicy") + "\n" + X("least-cost routing", "the card-testing rule")),
("Support partial capture: ship half the order today and the rest on Friday.", "twist", 5,
 "It is the exact mirror of the refund pair that already exists, which is the point of the answer. Payment grows two "
 "more long fields, a reserved and a settled capture amount, moved under the same lock with the acquirer call between "
 "them, plus a PARTIALLY_CAPTURED self-loop in the transition table; refunds then check against the settled capture "
 "instead of the full amount. The two rules are the same two rules: the captures can never add up past what was "
 "authorized, and nothing is written until the acquirer says yes. The reference code keeps that book beside the "
 "payment so Main stays as page 03 draws it.",
 X("partial capture", "least-cost routing")),
("Card testing hit us over the weekend: hundreds of tiny payments on stolen cards. Block a token after three declines in a minute, by Monday.", "twist", 5,
 "It looks like three changes &mdash; the risk check, the failure path and the wiring &mdash; and it is one class. The "
 "risk chain already asks every rule the same question before anything is claimed, and the listener bus already "
 "announces every payment that failed, so <code>CardTestingRule</code> implements both interfaces and is registered "
 "twice: once in <code>configure()</code> as a rule, once with <code>addListener</code>. The rule half counts that "
 "token's declines inside a sixty-second window and throws <code>PaymentRejected</code>, which <code>pay()</code> "
 "turns into a FAILED payment with no acquirer name on it and no socket opened. The listener half adds a timestamp "
 "only for payments an <i>acquirer</i> declined &mdash; it checks that the event carries an acquirer name &mdash; "
 "which is how the rule avoids counting its own refusals and locking a card out forever. The window is pruned on "
 "read, so there is no timer and no cleanup job, and the timestamps come from the injected clock, so the test moves "
 "time instead of sleeping for a minute.",
 X("the card-testing rule", "tokenisation")),
("Show me this merchant's settlement for the day, and every payment whose outcome we still do not know.", "non-functional", 5,
 "No new structure, only indexes maintained as payments land. Payments are in a map keyed by merchant, so a "
 "merchant's day is O(1) to find and O(k) to add up over their own payments, never a scan of the gateway; the "
 "settlement is captured minus refunded minus our fee, and note that a fully refunded payment still leaves the fee "
 "behind, which is what a real gateway does. The unknown payments are a set written the moment a call times out and "
 "cleared the moment one is resolved, so the reconciliation job reads a handful of rows rather than every payment "
 "ever taken. The query an interviewer usually adds next is \"show me authorizations older than seven days\", and it "
 "is the same move &mdash; one more index at the one choke point where state changes &mdash; but what you do with "
 "them is the interesting half. An expired hold has to be voided locally, and <code>settle()</code> will refuse to "
 "do it: FAILED and AUTHORIZED have the same rank, which is exactly what stops a late \"declined\" webhook from "
 "cancelling a good authorization. So a void is its own four-line method beside <code>markUnknown</code>, using the "
 "AUTHORIZED-to-FAILED edge the table already has; the acquirer stays the source of truth, so a capture that really "
 "did happen can still arrive afterwards and win on rank.",
 sect(src, "    long settlementOf(", "    private void publish(") + "\n" + X("settlement", "the double-entry ledger")),
("Finance says the numbers must add up on their own. Where are the books, and what is one payment's double entry?", "functional", 5,
 "Every movement is written twice, once positive and once negative, so the sum of every line ever written is zero; if "
 "it is not zero, somebody wrote one side of a movement. A capture of a thousand rupees writes +1000.00 to "
 "<code>acquirer_receivable</code> (money the acquirer now owes us) and &minus;1000.00 to "
 "<code>merchant_payable</code> (money we now owe the merchant), and a refund writes the mirror of that. The class is "
 "a <code>PaymentListener</code> and nothing else changed: accounting arrived after the design and cost one class and "
 "one <code>addListener</code> line, and because it is fed events rather than payments it cannot change a payment "
 "even by accident. The one trap is that an event carries running totals rather than the movement, so the ledger "
 "posts the <i>difference</i> between the total in the event and the total already on its books: a replayed event "
 "posts zero, an event that arrives out of order carries an older and smaller total and posts nothing, and a third "
 "partial refund posts only its own hundred rupees. <code>ExtDemo</code> proves it &mdash; six lines for one capture "
 "and two partial refunds, nothing for the replayed event, and an imbalance of zero.",
 X("the double-entry ledger", "persistence")),
("Persist it. And now there are two servers.", "twist", 5,
 "Every guard in the in-memory version has a one-line database twin, which is why the shape does not change. The "
 "idempotency map becomes a unique index on the key with INSERT ... ON CONFLICT DO NOTHING. The claim becomes UPDATE "
 "payments SET state = 'PENDING' WHERE id = ? AND state = 'CREATED', and \"zero rows updated\" is exactly what "
 "<code>claim()</code> returning false means today. The rank guard becomes another WHERE clause, rank_reached &lt; ?. "
 "And the merchant webhook, which today runs after the unlock, becomes an outbox row written inside the same "
 "transaction as the payment and drained by a worker: no payment without a row, no row without a payment, and a "
 "double delivery is the at-least-once problem merchants already handle.",
 X("persistence", "ExtDemo")),
("A chargeback lands forty days later. And compliance asks where the card number is stored.", "twist", 5,
 "A chargeback is not a refund: the money is already gone when the issuer tells us, so there is nothing to call the "
 "acquirer about. It is a fact to record against the payment and subtract from what the merchant is owed, which makes "
 "it a second book the settlement job reads &mdash; and it is refused if it exceeds what is still held, and refused "
 "twice on the same payment, because an issuer pulls the money back once. The card number question is already "
 "answered: nowhere. PaymentMethod carries a token and a display string, the vault is the only class whose methods "
 "ever take a PAN, and so nothing downstream &mdash; the payment, the audit log, the merchant webhook, the future "
 "database &mdash; needs a redaction rule, because it never had the number to redact.",
 X("chargebacks", "settlement") + "\n" + X("tokenisation", "chargebacks")),
("Where does time come from, and how do you test a rule about the last sixty seconds?", "design", 3,
 "The gateway has a Clock it was handed and stamps every state change with it; nothing in the system reads the wall "
 "clock inside a method. A test hands in a clock that returns a fixed instant, makes a payment time out, moves the "
 "instant forward by a minute and runs the reconciliation job, and can then assert that the job's staleness rule "
 "fired exactly when it should have. The same seam is what makes the circuit breaker's cool-off and the card-testing "
 "rule's sixty-second window testable without a single sleep: both are given a now, never asked to find one.",
 "/** Where time comes from. Injected, so a test can put the clock anywhere it likes and move it. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the gateway: handed in, defaulted, never read from the wall clock inside a method\n"
 "private volatile Clock clock = System::currentTimeMillis;\n"
 "void setClock(Clock c) { clock = c; }\n\n"
 "// in a test: pick the instant, then move it\n"
 "long[] now = { 1_700_000_000_000L };\n"
 "gw.setClock(() -> now[0]);\n"
 "acquirer.mode(VendorMode.TIMEOUT_CHARGED);\n"
 "Payment p = gw.pay(\"ord-2\", \"m1\", Money.rupees(\"700.00\"), Currency.INR, CARD);   // UNKNOWN\n"
 "acquirer.mode(VendorMode.HEALTHY);\n"
 "now[0] += 60_000;                                      // a minute later\n"
 "gw.reconcile(30_000);                                  // only now is it stale enough to chase\n"),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "Moves 10 and 11 named them; this is the version that survives being argued with, which is what the question is "
 "really for. <b>Strategy</b>: routing, fees, retries and risk are one-method interfaces the gateway is handed, so a "
 "cost-based route is a new file and one line in <code>configure()</code>. <i>\"Then why is PaymentProcessor not a "
 "Strategy as well?\"</i> Because it is a port to somebody else's computer rather than a rule of ours, and each "
 "implementation behind it is an <b>Adapter</b> for one vendor's dialect. <i>\"Why is CircuitBreaker a Decorator and "
 "not a subclass of each acquirer?\"</i> Because a subclass has to be written once per vendor and again for every "
 "vendor added later, while the wrapper reports the wrapped acquirer's own <code>name()</code>, so routing and the "
 "stored acquirer name never learn it exists. <b>Observer</b> is what keeps a merchant's slow server outside the "
 "lock; <b>State</b> is the transition table plus the rank. <b>Factory</b> earns its place the day acquirers arrive "
 "as strings from configuration &mdash; the map is already the registry &mdash; and <b>Builder</b> never does here: "
 "five fields, all of them required. SOLID in one line each: S is move 2, O is <code>LeastCostRouting</code>, L is "
 "that the flow asks <code>capturesOnAuthorize()</code> and never which vendor it got, I is the one-method "
 "interfaces with <code>PaymentProcessor</code> as the honest exception because a vendor is wide, and D is "
 "<code>configure()</code> and <code>setClock()</code> &mdash; which is exactly why a test can hand in an acquirer "
 "that takes the money and then times out.",
 "// Strategy: a rule behind an interface, handed in, never built by the gateway\n"
 "interface RoutingPolicy { List<PaymentProcessor> route(PaymentMethodType t, Currency c, long paise, List<PaymentProcessor> all); }\n"
 "void configure(RoutingPolicy routing, FeePolicy fees, RetryPolicy retries, List<RiskRule> riskRules) { ... }\n\n"
 "// Adapter: one class per vendor dialect; the gateway never learns a vendor's names\n"
 "class CardAcquirer implements PaymentProcessor { ... }      // auth then capture\n"
 "class UpiSwitch    implements PaymentProcessor { ... }      // capturesOnAuthorize() == true\n\n"
 "// Decorator: a processor that HOLDS a processor, so the behaviour applies to vendors written next year\n"
 "gw.addProcessor(new CircuitBreaker(hdfc, 3, 30_000, clock));\n"
 "public String name() { return inner.name(); }               // routing never learns the wrapper exists\n\n"
 "// Observer: the gateway announces; it does not know what a merchant's server is\n"
 "interface PaymentListener { void onEvent(PaymentEvent e); }\n"
 "for (PaymentListener l : listeners) try { l.onEvent(e); } catch (RuntimeException ex) { /* log */ }\n\n"
 "// State: the life as data -- the legality table and the rank, checked on every single write\n"
 "if (outcome.outcomeRank() <= rankReached) return false;     // a report of an older truth\n"
 "if (!state.canGoTo(outcome)) return false;                  // an edge that does not exist\n\n"
 "// Factory: not yet. The registry is already here; it earns the name when acquirers come from config strings\n"
 "Map<String, PaymentProcessor> byAcquirer = new ConcurrentHashMap<>();\n\n"
 "// Builder: never here. Five required fields is a constructor\n"
 "new Payment(id, idemKey, merchantId, paise, currency, method, createdMs);\n"),
]

build(dict(
    slug="payment-gateway", title="Payment Gateway",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 8 failure tests and a 50-thread idempotency race pass",
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
