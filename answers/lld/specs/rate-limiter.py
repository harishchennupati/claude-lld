# Rate limiter LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"rate-limiter/Main.java").read_text()
ext   = (H/"rate-limiter/Extensions.java").read_text()
tests = (H/"rate-limiter/FailureTests.java").read_text()

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
# what the code must do: allow, refund, and the reads as a line
pf = _D
rows = [("allow",  30, [("a call arrives with a key", "acme, cost 1 permit"),
                        ("the rule for that key", "PRO: 600 a minute, burst 100"),
                        ("refill, then charge", "under this key's lock only"),
                        ("admitted", "X-RateLimit-Remaining: 99")]),
        ("refund", 165, [("a permit was charged", "and then the call never happened"),
                         ("give exactly that back", "same key, same lock"),
                         ("never above the burst", "a refund may not mint"),
                         ("the budget is honest again", "remaining 5 of 100")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 2 and lab == "allow") or (k == 1 and lab == "refund"))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M815 84 V95", dash=True) + _bx(660, 95, 310, 40, "refused: 429, Retry-After 100ms", "", dash=True)
pf += _tx(88, 262, "read", "var(--acc)", 13) + _tx(175, 262, "at any moment, charging nothing: how many permits are left for this key?  how many calls were allowed and refused?", "var(--text)", 12, "start")
pf += _tx(88, 292, "sweep", "var(--acc)", 13) + _tx(175, 292, "on a schedule, never on the request path: forget every key nobody has asked about for a whole window", "var(--text)", 12, "start")
pf += _tx(615, 332, "thousands of keys at once, a hundred threads on one key: never one permit more than the rule allows", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 348, pf)

# one afternoon, replayed: the numbers are the ones Main.java prints
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("12:00:00.000  first call",   ["PRO plan: 600 a minute, burst 100", "a key nobody has seen: full burst", "allowed, remaining 99", "one map entry now exists"], True),
      ("12:00:00.400  120 calls",    ["99 left + 4 minted, capped at 100", "100 allowed, 20 refused", "each refusal: Retry-After 100ms", "remaining 0"], False),
      ("12:00:02.400  the retries",  ["the client honoured Retry-After", "1 permit at +100ms, 19 more by +2s", "all 20 retries allowed", "nobody was dropped, only delayed"], True),
      ("12:01:32  the sweeper runs", ["idle 90s; one window is 60s", "it had refilled to 100 anyway", "the key is deleted: ~340 bytes back", "a fresh key is the same key"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 110, t, lines, acc=acc)
P_EX = _mv(1230, 185, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li><code>allow(key)</code> answers in microseconds: yes or no, how many permits are left, and when to come back.</li>
<li>At most <i>permits</i> per <i>window</i> for a key, and at most <i>burst</i> of them at one instant.</li>
<li>A rule per key, resolved at call time and changeable while the process runs (a plan upgrade, a sale).</li>
<li>Four algorithms behind one interface. Token bucket: a bucket of permits that refills at a steady rate. Fixed window: a counter that resets every window. Sliding window counter: this window's count plus a fading share of the last one. Sliding window log: one timestamp per call.</li>
<li>A heavy request may cost several permits. One that costs more than the whole bucket is refused for good, not told to wait.</li>
<li>Permits can be given back for a call that was admitted and then never made.</li>
<li>Counters of what was allowed and what was refused.</li>
<li>Keys nobody uses any more are forgotten.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Never admit more than the rule allows, whatever the thread count. That is the invariant: the one rule that must hold at every instant.</li>
<li>O(1) time and memory per decision (the exact log excepted); no scan, and no timer or background thread per key.</li>
<li>Keys never wait for each other: one lock per key, not one lock for the limiter.</li>
<li>The algorithm and the limits are swappable without opening the limiter.</li>
<li>One source of truth per key: the permits, and the instant they were measured at, changed together.</li>
<li>Time is handed in, so every test is instant and repeatable.</li>
<li>In memory, one process (say it); bounded memory as keys come and go.</li></ul></div></div>
'''

ASK_HTML = '''<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>
<tr><td>Per process, or one budget for the whole fleet?</td><td>One JVM, the guard in front of one service</td><td>A map in memory now; Redis behind the same interface later (moves 1, 12)</td></tr>
<tr><td>What is the key &mdash; tenant, user, API key, IP? How many at peak?</td><td>API key, about five thousand at peak</td><td>The map, and whether idle keys must be evicted (moves 5, 9)</td></tr>
<tr><td>On a refusal, does the caller fail or wait?</td><td>Fail fast, and be told when to come back</td><td>The return type is a Decision, not a boolean; waiting is a follow-up (move 2)</td></tr>
<tr><td>Are bursts allowed, or must the rate be smooth?</td><td>Bursts up to the limit are fine</td><td>Token bucket with a burst knob, not a leaky bucket (move 3)</td></tr>
<tr><td>Same limit for everyone?</td><td>No: a rule per tier, changeable live</td><td>The rules are handed in and read once per call (moves 3, 6)</td></tr>
<tr><td>Exact at the window edge, or is approximate acceptable?</td><td>Approximate at the front door, exact on login</td><td>Four algorithms behind one interface (moves 3, 5)</td></tr>
<tr><td>Does every request cost one permit?</td><td>No: a search costs more than a ping</td><td>A cost argument on allow() from the first line (move 2)</td></tr>
<tr><td>Does a refused call count against the limit?</td><td>No: a refused call is charged nothing</td><td>Charge only on yes, inside the lock (moves 4, 6)</td></tr></table></div>'''

PROMPT = ('"Build me a rate limiter. It sits in front of our API. Given a key (a tenant, an API key), it says whether this call may '
          'go through right now. And it has to be right when a hundred threads ask about the same key at the same instant. '
          'I want working code, not a diagram. Go."')

PROBLEM_BODY = ('<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A service wants to stop one noisy client from eating everybody else\'s capacity. In front of every request sits one call: <code>allow(key)</code>. It must answer in microseconds with three things: yes or no; how many permits (one call\'s worth of budget each) the key has left; and, on a no, how long to wait before trying again. The budget is a rule: so many permits per window, with a burst (how many may be spent at one instant). Different keys are on different plans. Hundreds of threads serve requests for the same key at the same moment, so the one thing that must never happen is admitting more calls than the rule allows. Everything else in this design exists to make that one sentence true cheaply.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a <code>main</code> that spends a burst, gets refused, waits, and is allowed again. The interviewer watches for these, in order. First, the questions you ask before typing: per process or per fleet, what the key is, fail or wait. Then which classes exist and which one owns which state, and <code>allow</code> working end to end. Then a hundred threads on one key at its limit. Then where the rules that will change live (the algorithm, the limit per tier, where time comes from), so a change is a new class and not an edit. Last, what happens when the answer was yes but the call never happened. Then the twists: the fixed-window boundary, twelve pods sharing one budget, ten million keys, unused permits saved as credits.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>' + ASK_HTML +
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One afternoon, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> one process, in memory; the key is an API key, about five thousand at peak; a refusal is immediate and carries a retry-after; bursts up to the limit are allowed; time is handed in. Named as out of scope: a shared budget across pods, waiting instead of failing, per-endpoint keys, warm-up, credits; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
# move 1: nouns -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(615, 47, "a CALLER asks: may this KEY spend a COST of PERMITS right now? apply the RULE, keep a BUCKET per key, answer with a DECISION", "var(--text)", 12.5)
for k, (t, sub, acc) in enumerate([("Caller", "a filter: no state", 0), ("Key", "a String: the map key", 0), ("Rule", "permits, window, burst", 1),
                                   ("Bucket = KeyState", "tokens + when measured", 1), ("Decision", "yes, left, retry-after", 1),
                                   ("Algorithm", "a rule: an interface", 0), ("Remaining", "a question: a method", 0)]):
    x = 30 + k*172
    m1 += _bx(x, 110, 155, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x+77))
m1 += _tx(615, 190, "solid = has its own state, so it becomes a class.   dashed = no state of its own: a caller, an interface, or a method", "var(--muted)", 11)

# move 2: verbs -> the class that owns the state
m2 = _D
for k, (verb, cls, meth, msub) in enumerate([("may this key spend one permit?", "KeyState  (owns tokens and the instant)", "algo.tryAcquire(s, rule, cost, now)", "the sums, handed the state (move 3)"),
                                             ("how many permits are left?", "KeyState  (same state, nothing charged)", "algo.remaining(s, rule, now)", "the sums, handed the state"),
                                             ("find this key, lock it, decide", "RateLimiter  (owns the map and the clock)", "limiter.allow(key, cost)", "the method")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True) + _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True) + _bx(900, y, 300, 44, meth, msub)
m2 += _tx(615, 215, "the state is per key, so the class that owns it is per key too: one KeyState each, and one RateLimiter over all of them", "var(--muted)", 11)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 80, 220, 110, "RateLimiter", "configure(algo, rules, clock)", acc=True)
for k, (t, sub, impls) in enumerate([("RateLimitAlgorithm", "a bucket today, a window tomorrow", "TokenBucket | FixedWindow | SlidingWindow x2"),
                                     ("RuleResolver", "flat today, a rule per tier tomorrow", "FlatRules | TierRules | WarmUpRules"),
                                     ("Clock", "the machine's, or a test's", "SystemClock | ManualClock"),
                                     ("LimiterObserver", "who wants to know what was decided", "MetricsCounter | a 429 audit log")]):
    y = 24 + k*60
    m3 += _ar("M250 135 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impls, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 275, "dashed = handed in. The limiter never builds these, so a new algorithm is a new class and one changed line", "var(--muted)", 11)

# move 4: the gap, and the lock that closes it
m4 = _D + _bx(30, 30, 190, 44, "thread 1", "reads: 1 token left") + _bx(30, 110, 190, 44, "thread 2", "reads: 1 token left") + _bx(350, 70, 200, 44, "acme's bucket", "tokens = 1", acc=True)
m4 += _ar("M220 52 H350 V70") + _ar("M220 132 H350 V114") + _tx(285, 42, "read", "var(--muted)", 10.5) + _tx(285, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="20" width="270" height="140" rx="6" fill="none" stroke="#f38ba8" stroke-dasharray="4 3"/>' + _tx(715, 45, "the gap", "#f38ba8", 12) + _tx(715, 72, "both saw 1, both deduct:", "#f38ba8", 11) + _tx(715, 94, "two calls on a budget of one", "#f38ba8", 11) + _tx(715, 132, "fix: all three as ONE step", "var(--text)", 11)
m4 += _bx(880, 40, 320, 100, "KeyState.lock", "one lock per KEY, not one per limiter", acc=True)
m4 += _tx(615, 182, "the lock lives on the state it protects, so two keys never wait for each other", "var(--muted)", 11)
m4 += _tx(615, 202, "the metrics listener is called after the unlock, never inside it", "var(--muted)", 11)

# move 5: each collection, its question, the O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("the state for this key?", "ConcurrentHashMap&lt;String, KeyState&gt;", "O(1), no global lock"),
                                      ("how many permits right now?", "two numbers: tokens + the instant measured", "O(1), no list"),
                                      ("how many in the last minute, exactly?", "ArrayDeque&lt;Long&gt;: a timestamp per permit", "O(k), ~17 KB a key"),
                                      ("which rule for this key?", "map key&rarr;Tier, then EnumMap&lt;Tier, Rule&gt;", "O(1)"),
                                      ("which keys are idle?", "lastSeenMs on each state, one pass", "O(n), off the hot path")]):
    y = 20 + k*50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True) + _bx(450, y, 490, 40, shape, "the shape", acc=True) + _ar("M940 %s H1000" % (y+20), True) + _bx(1000, y, 200, 40, cost, "")
m5 += _tx(615, 295, "the only shape here that is not O(1) is the exact one, and its price is memory: one timestamp for every permit", "var(--muted)", 11)

# move 6: the life of a key, and the order inside allow()
m6 = _D
m6 += _bx(30, 40, 190, 44, "FRESH", "full burst, on first sight")
m6 += _bx(260, 40, 190, 44, "SPENDING", "tokens going down", acc=True)
m6 += _bx(490, 40, 190, 44, "THROTTLED", "0 left; Retry-After", acc=True)
m6 += _bx(260, 120, 190, 44, "IDLE", "untouched: swept")
m6 += _ar("M220 62 H260") + _ar("M450 62 H490")
m6 += _ar("M585 40 V16 H355 V40", True) + _tx(470, 32, "time refills it", "var(--acc)", 10.5)
m6 += _ar("M355 84 V120") + _tx(372, 106, "nobody calls for a window", "var(--muted)", 10.5, "start")
m6 += _card(720, 20, 490, 150, "the order inside allow(), and why it is this order",
            ["1 read the rule once, read the clock once",
             "2 lock THIS key; refill from elapsed time",
             "3 charge, and only then admit",
             "4 unlock, then tell the listeners",
             "a permit spent can be refunded; a request admitted cannot be recalled"], acc=True)
m6 += _tx(615, 205, "charge before you admit is this system's 'take the money before you commit'. The refund is the compensating step when the call never happened.", "var(--muted)", 11)

# move 7: what is inside the lock, and a hundred threads at one instant (numbers measured: JDK 21, 10-core laptop)
m7 = _D + _card(30, 20, 540, 150, "inside the lock: tens of nanoseconds",
                ["one subtraction: now, minus the last measurement",
                 "one multiply and a min: the refill",
                 "one compare and one subtract: the charge",
                 "two field writes: the tokens, and the instant",
                 "nothing slow: no I/O, no logging, no waiting"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside the lock: everything else",
            ["reading the rule and the clock: before the lock is taken",
             "the metrics listener: after the unlock, in a try/catch",
             "the request this call gates: about 2 milliseconds",
             "one whole uncontended allow(), measured: 11 nanoseconds"])
m7 += _tx(615, 205, "a hundred threads press on ONE key at the same instant (measured, 35 runs)", "var(--text)", 12)
for k, (t, sub, acc) in enumerate([("the work inside the lock", "tens of nanoseconds", False),
                                   ("waking the next waiting thread", "a few microseconds each", False),
                                   ("the slowest of the 100 threads", "~15 us; ~100 us in the worst run", True),
                                   ("the request it was gating", "~2,000 us", False)]):
    x = 30 + k*298
    m7 += _bx(x, 222, 270, 44, t, sub, acc=acc)
    if k < 3: m7 += _ar("M%s 244 H%s" % (x+270, x+298))
m7 += _tx(615, 292, "one by one is true: what the queue costs is the hand-offs, and the slowest thread waits under 1% of its own request", "var(--muted)", 11)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "a lock per key: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["20,000 requests a second, spread over 5,000 API keys",
                       "the hottest key: 500 a second, ~20 ns of lock each",
                       "that key's lock is busy 10 us in every 1,000,000 us",
                       "keys never share a lock, so the other 4,999 never wait",
                       "memory: ~340 bytes a key: 5,000 = 1.7 MB, 10 million = 3.4 GB"]):
    m8 += _tx(35, 66+k*24, l, RED if k == 4 else "var(--muted)", 11, "start")
m8 += _tx(880, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 compare-and-set instead of the lock", "the bucket is one immutable value; a loser recomputes"),
                              ("2 split one hot key into eight stripes", "each stripe gets an eighth of the limit: cheap, approximate"),
                              ("3 move the budget out of the process", "one Redis script, or a lease of 100 permits per pod")]):
    m8 += _bx(600, 58+k*50, 600, 42, t, sub, acc=(k == 0))

# move 9: what can go wrong -> a test for each
m9 = _D
for k, (t, sub, fix) in enumerate([("two threads read '1 left'", "both admit: one permit, two calls", "refill and charge inside one per-key lock; test: 100 threads, exactly 50 admitted"),
                                   ("a burst either side of the edge", "twice the limit in 100 ms", "the sliding counter weights the previous window; test: 10 through vs 5 through"),
                                   ("NTP drags the clock back 5 s", "five seconds of free permits", "elapsed of zero or less mints nothing; test: the clock goes back, then forward"),
                                   ("a call costs more than the bucket", "told to wait; retries forever", "refuse it for good: Retry-After never; test: a call of 6 on a burst of 5"),
                                   ("ten million keys, nothing evicted", "3.4 GB, then out of memory", "sweepIdle drops keys idle for a window; test: idle dropped, live kept"),
                                   ("the sweeper deletes a key mid-call", "a permit spent and then lost", "mark it removed under the lock, fetch again; test: hold the lock, sweep, check")]):
    y = 20 + k*44
    m9 += _bx(30, y, 290, 38, t, sub) + _ar("M320 %s H380" % (y+19), True) + _bx(380, y, 820, 38, fix, "", acc=True)
m9 += _tx(615, 296, "every claim this derivation makes has a test: FailureTests.java runs 17 blocks of checks and must print ALL PASS", "var(--muted)", 11)

# move 10: patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 800)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface RateLimitAlgorithm { Decision tryAcquire(...); }  via configure()", None), ("swap the algorithm without opening the limiter", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("ShadowLimiter(Limiter delegate);  WarmUpRules(RuleResolver base)", None), ("add a dry run or a ramp without copying a rule", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(key, d) after the unlock; MetricsCounter implements it", None), ("metrics without knowing what a metric is", None)],
          [("Value object", "var(--text)"), ("move 1", None), ("record Rule(permits, windowMs, burst);  record Decision(...)", None), ("one Rule shared by a whole tier; nothing to lock", None)],
          [("State", "var(--muted)"), ("not earned", None), ("a key's states are just its numbers: no status field, no state classes", "var(--muted)"), ("the life is drawn in move 6, not coded", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("earns it when algorithms arrive as config strings: Map&lt;String, Supplier&gt;", "var(--muted)"), ("say 'not yet, and here is what would make me'", "var(--muted)")],
          [("Singleton, Builder", "var(--muted)"), ("never", None), ("one limiter per process is a wiring fact, not a class", "var(--muted)"), ("a getInstance would make every test share state", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 275, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)

# move 11: SOLID as a check
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("TokenBucket does token arithmetic; RateLimiter owns keys and locks; TierRules owns policy", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("shadow mode, layered limits and credits are new classes; nothing was reopened", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("Gcra replaces TokenBucket and admits the same calls; wrappers take any Limiter", None)],
          [("I", "var(--acc)"), ("small interfaces, so a fake is a lambda", None), ("move 3", None), ("limiter.configure(new TokenBucket(), rules, () -&gt; 1_000L) in a test", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("the tests hand in a ManualClock and a listener that always throws", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)

# move 12: every twist is one of five moves
m12 = _D
tw = [("a new rule", "a leaky bucket, credits, a plan per customer", "a new class behind RateLimitAlgorithm plus one configure line", "", "move 3"),
      ("someone new wants to know", "a 429 audit log, a per-tenant dashboard", "one more observer; the limiter and the lock do not change", "", "move 3"),
      ("a new step in a life", "warm-up: a new key starts at a tenth", "a resolver that wraps the rules and scales them by the key's age", "", "move 6"),
      ("a new invariant across keys", "this tenant AND the whole service", "charge both layers; refund the first when the second refuses", "", "move 4"),
      ("state that must outlive the process", "twelve pods, one budget", "one Redis script does refill-and-deduct: the fleet's compare-and-set", "EVAL bucket.lua 1 acme 100 0.01 1  -- one round trip, one step, Redis's own clock", "move 5 + this one")]
for k, (t, sub, fix, fixsub, mv) in enumerate(tw):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, fixsub, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 310, "for all five the limiter and its tests do not change; that is the test that the derivation was right", "var(--muted)", 11)

MV = {1: _mv(1230, 205, m1), 2: _mv(1230, 230, m2), 3: _mv(1230, 290, m3), 4: _mv(1230, 218, m4),
      5: _mv(1230, 310, m5), 6: _mv(1230, 220, m6), 7: _mv(1230, 305, m7), 8: _mv(1230, 220, m8),
      9: _mv(1230, 310, m9), 10: _mv(1230, 290, m10), 11: _mv(1230, 265, m11), 12: _mv(1230, 325, m12)}

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: a <b>caller</b> asks whether this <b>key</b> may spend a <b>cost</b> of <b>permits</b> right now; apply the <b>rule</b>; keep a <b>bucket</b> per key; answer with a <b>decision</b>. A rule has three numbers (permits, window, burst) that travel together, so it is a class: a record. A bucket has permits and the instant they were measured at, and neither number means anything without the other, so it is a class. It ends up holding the window counters and the lock as well, so the code calls it <code>KeyState</code>: everything one key owns. A decision has four fields a caller needs, so it is a class too, not a bare boolean. The caller keeps nothing of its own, so it is a thin caller, not a model. The key is a String. The algorithm has no state of its own; it only works on somebody else's bucket, which is exactly what an interface is. \"How many are left\" is a question I answer, so it is a method.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"May this key spend one permit\" changes the tokens and the instant they were measured at. Both live on the bucket, so their owner is KeyState, and by this move's rule the method would be <code>keyState.tryAcquire(...)</code>. Move 3 adds one twist: the sums are the part that will change, so they go to an algorithm object that is handed the state, <code>algo.tryAcquire(s, rule, cost, now)</code>. The state still has one owner; only the arithmetic is swappable. \"How many are left\" reads the same two fields and charges nothing, so it sits beside it. \"Find this key's state, lock it, decide, then tell the listeners\" touches the map, the clock, the rules and the listeners at once. Only the limiter sees all four, so that is <code>limiter.allow(key, cost)</code>. The pattern worth saying aloud: the state here is <i>per key</i>, so the class that owns it is per key too. One KeyState each, and one RateLimiter over all of them.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Four things will change. The algorithm: token bucket today, and they will ask for a sliding window the moment you mention the boundary. The limits: flat today, a rule per tier tomorrow, raised live during a sale. Where time comes from: the machine's clock in production, a clock the test sets in a test. And who wants to know what was decided: metrics today, a 429 audit log tomorrow. Each becomes an interface the limiter is <i>given</i> in <code>configure()</code> and never builds. This is where the patterns are born, not announced. A swappable rule behind an interface is <b>Strategy</b>. A wrapper that adds to an existing rule instead of replacing it is <b>Decorator</b>: shadow mode over a real limiter, or a warm-up over a rule source. A limiter that announces every decision without knowing what a metric is, is <b>Observer</b>.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two threads serving the same tenant both read \"one token left\", both decide yes, both write zero: one permit, two calls. That gap between the read and the write is the whole bug, and it is the one the interviewer is really asking about. So refill, check and charge must be one step under one lock. The important choice is <i>where that lock lives</i>: on the key's state, not on the limiter. A lock on the limiter would make five thousand unrelated tenants queue behind each other for no reason. A lock per key means two keys never wait for each other at all. The map that hands out the states is a ConcurrentHashMap, which is safe to share without a lock around it: reads take no lock, and a write locks only its own slot. Anything that only listens (metrics, an audit log) is called after the unlock, never inside it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"The state for this key\": a ConcurrentHashMap from key to KeyState, one lookup, no global lock. \"How many permits right now\": two numbers on that state, the tokens and the instant they were measured. The answer is computed from elapsed time, which is why there is no timer and no thread topping buckets up. \"How many calls in the last minute, exactly\": a deque (a double-ended queue: add at the back, drop from the front) holding one timestamp per permit. That is the only shape here that is not O(1), and its price is memory. Each timestamp is a boxed Long, an object of about 30 bytes, so a key on 600 a minute holds about 17 KB. Say that out loud, and say when you would pay it: a login endpoint at five a minute, never the public API. \"Which rule for this key\": a map to the tier, then an EnumMap of tier to rule. \"Which keys are idle\": a lastSeen stamp on each state and one pass over the map, run by a scheduled task, never on the request path.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A key's life is short and worth drawing. It is FRESH, with a full burst, the first time it is seen; SPENDING as tokens go down; THROTTLED at zero, with a retry-after; back to SPENDING as time refills it. It is IDLE when nobody has asked for a whole window, and then the sweeper deletes it. None of these states is stored: each is just what the numbers say, so there is no status field to keep in step. Writing the life down forces the order inside <code>allow</code>. Read the rule once and the clock once, so one decision sees one policy and one instant. Then take this key's lock, refill from elapsed time, charge, unlock, and only then tell the listeners. The rule that matters is <b>charge before you admit</b>. It mirrors taking the money before committing a booking, because here the irreversible thing is letting the request through. A permit spent can be given back; a request admitted cannot be recalled. That is what <code>refund</code> is: the compensating step (an action that undoes an earlier one) for a call that was allowed and then never made.", 6),
("Move 7: yes, one key's calls happen one at a time. Ask for how long, and what is inside the lock.",
 "Inside the lock: a subtraction, a multiply and a min, a compare, a subtract, and two field writes. That is tens of nanoseconds; a whole uncontended <code>allow()</code>, lookup and lock included, measured 11 nanoseconds on a laptop with JDK 21. The rule and the clock are read before the lock, the listeners are told after it, and the request being gated takes about 2 milliseconds. So what does a queue of 100 threads on one key cost? Mostly hand-offs, not work: waking a thread that went to sleep waiting for the lock takes a few microseconds. Measured, the slowest of 100 threads spent about 15 microseconds inside <code>allow()</code>, and about 100 in the worst of 35 runs. Against a 2-millisecond request, nobody can see it. It only breaks if something slow gets inside the lock, such as a log line or a network hop, which is why the listeners are told after the unlock.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "20,000 requests a second across 5,000 API keys. The hottest key sees 500 a second at about 20 nanoseconds of lock each, so its lock is busy 10 microseconds in every second: one part in a hundred thousand. The other 4,999 keys never touch it. Time is not the problem here; memory is. A key costs about 340 bytes (measured: the map entry, the KeyState, its lock and its empty deque), so 1.7 MB at 5,000 keys and 3.4 GB at 10 million. That number is the whole reason the sweeper exists. Then the ladder, cheapest first. One: hold the bucket as one immutable value and swap it with compare-and-set (write the new value only if the old one is still there). There is no lock, and a thread that loses simply recomputes. Two: split one hot key into eight stripes, each with an eighth of the limit; cheap, and a few percent approximate. Three: only then move the budget out of the process, into one Redis script, or hand each pod a lease of 100 permits to spend locally. Do the arithmetic before you climb; without it, two of those rungs are complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "This table is the answer to \"what would you test?\", and every row of it is a few lines in <code>FailureTests.java</code>, not a promise. Three rows are worth rehearsing. The race, because a limiter that is wrong under load is not a limiter: 100 threads, a frozen clock, exactly 50 admitted. The clock, because anyone who reached for the wall clock has this bug. When NTP (the service that keeps the machine's clock in sync) drags it back five seconds, elapsed time of zero or less must mint nothing. Nothing may be minted for the stretch the clock travels twice, either. And the last row, the one almost nobody finds: the sweeper deleting a key between another thread's lookup and its lock, which would silently swallow a spent permit. The fix is three lines: mark the state removed under the lock, and make the caller fetch again. The test holds the key's lock on purpose, so the caller stops at it, and then sweeps from the same thread. That works because the lock is re-entrant: a thread that already holds it may take it again.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Every pattern here came out of a move, which is why each can be defended in one sentence. Strategy is move 3: the algorithm sits behind a one-call interface, so a sliding window is a new class and one changed line. Decorator is the same move used twice: shadow mode wraps a whole limiter and swallows the refusals, and the warm-up rule wraps a rule source and scales its numbers by the key's age. Neither copies the thing it changes. Observer is move 3 as well, kept outside the lock by move 4: the limiter announces each decision after the unlock and does not know what a metric is. The records are value objects (immutable data, compared by what it contains), so one Rule can be shared by a whole tier and nothing about it needs locking. State is worth naming as <i>not</i> earned. The life in move 6 is real, but a key's state is just its numbers, so there is no status field and no class per state. Factory has not earned a place yet; it earns one the day algorithms arrive as strings from configuration and a registry maps \"token_bucket\" to a constructor. Singleton earns nothing at all: one limiter per process is a fact about wiring, and a static getInstance would make every test share a bucket.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "S: each class has one reason to change. TokenBucket changes when token arithmetic changes, RateLimiter when the key lifecycle does, TierRules when the plans do, MetricsCounter when counting does, and nobody does two of those. O: the late requirements (shadow mode, a second global budget, credits) each arrived as a new class and one wiring line; no existing class was opened for them. L: an implementation drops in and nobody checks which. Gcra takes TokenBucket's place and FailureTests shows it admitting the very same calls, and ShadowLimiter or WaitingLimiter wrap any Limiter without an <code>instanceof</code>. I: Clock, RuleResolver and LimiterObserver have one method each, so a fake in a test is a lambda. D: the limiter depends on interfaces and is handed the implementations. That is exactly why a test can hand it a clock that jumps 200 milliseconds and a listener that always throws.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Say which of the five it is before you type; that sentence is most of the answer, and the table above has the other half. Only two of them need real thought here. The first is a new invariant across keys: this tenant <i>and</i> the whole service. Both budgets are charged in order, and the first must be refunded when the second refuses; otherwise a tenant loses permits for a request nobody served. The second is state that must outlive the process: twelve pods, one budget. The bucket moves into Redis, and one script does refill-and-deduct on the server. Redis runs commands one at a time on a single thread, so that thread is the fleet's version of this key's lock: the same idea, one layer out. For all five, the limiter and its tests do not change; that is the test that the derivation was right. Page 05 has the code for each.", 12),
]

DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, BookMyShow). The class diagram, the lock, the tests, the patterns, SOLID "
 "and the answer to every twist fall out in that order. Nothing is chosen up front, and nothing is named before the move that "
 "produced it. On this problem two moves carry extra weight. Move 4, because the lock goes on the key and not on the limiter. "
 "And move 6, because the order is charge-then-admit, and a permit is the only thing that can be given back.")

# ============================================================ page 03: the class diagram
uml_reset()
put("filter", 10, 20, 220, "ApiFilter", ["limiter: Limiter"], ["handle(key, cost): int", "headers(d): String"])
put("limiter", 10, 140, 220, "Limiter", [], ["allow(key, cost): Decision", "allow(key): Decision"], "interface")
put("clock", 10, 250, 220, "Clock", [], ["nowMs(): long"], "interface")
put("clocks", 10, 334, 220, "SystemClock | ManualClock", [], ["nowMs(): long", "advance(ms)  -- test only"])
put("obs", 10, 444, 220, "LimiterObserver", [], ["onDecision(key, d)"], "interface")
put("metrics", 10, 528, 220, "MetricsCounter", ["allowed / refused: AtomicLong"], ["onDecision(key, d)", "allowed(): long", "refused(): long"])
put("lim", 300, 20, 300, "RateLimiter", ["keys: Map&lt;String, KeyState&gt;", "algo: RateLimitAlgorithm", "rules: RuleResolver", "clock: Clock", "observers: List&lt;LimiterObserver&gt;"],
    ["configure(algo, rules, clock)", "addObserver(o)", "allow(key, cost): Decision", "refund(key, cost)", "remaining(key): long", "sweepIdle(idleMs): int"])
put("ks", 300, 280, 300, "KeyState", ["key: String", "lock: ReentrantLock", "tokens: double", "lastRefillMs: long", "windowStartMs: long", "currentCount / previousCount", "log: ArrayDeque&lt;Long&gt;", "lastSeenMs / removed"], [])
put("rule", 300, 490, 300, "Rule", ["permits: long", "windowMs: long", "burst: long"], ["perMs(): double", "perSecond(n) / perMinute(n, b)"])
put("dec", 620, 280, 220, "Decision", ["allowed: boolean", "remaining: long", "retryAfterMs: long", "reason: String"], [], "record")
put("tier", 620, 420, 220, "Tier", ["FREE, PRO, ENTERPRISE"], [], "enum")
put("algo", 930, 20, 290, "RateLimitAlgorithm", [], ["tryAcquire(s, rule, cost, now)", "refund(s, rule, cost, now)", "remaining(s, rule, now): long", "capacity(rule): long", "name(): String"], "interface")
put("tb", 930, 162, 290, "TokenBucket", [], ["refill by elapsed, then charge", "O(1) time and memory"])
put("fw", 930, 272, 290, "FixedWindow | SlidingCounter", [], ["a counter per window on a grid", "the counter weights the last one"])
put("swl", 930, 382, 290, "SlidingWindowLog", [], ["a timestamp per permit: exact", "O(k) time, ~30 bytes a permit"])
put("resolver", 930, 530, 290, "RuleResolver", [], ["ruleFor(key): Rule"], "interface")
put("flat", 930, 614, 290, "FlatRules", [], ["one rule for everybody"])
put("tiers", 930, 698, 290, "TierRules", ["tierOf: Map&lt;String, Tier&gt;", "rules: EnumMap&lt;Tier, Rule&gt;"], ["assign(key, tier)", "setRule(tier, rule)  -- live", "ruleFor(key): Rule"])
edges = [
    ln(B["filter"]["b"], B["limiter"]["t"], "assoc", "calls"),
    ln(B["lim"]["l"], B["limiter"]["r"], "inherit"),
    ln(B["clocks"]["t"], B["clock"]["b"], "inherit"),
    ln(B["metrics"]["t"], B["obs"]["b"], "inherit"),
    ln(B["lim"]["b"], B["ks"]["t"], "compose", "one per key"),
    ln((600, 180), (730, 280), "assoc", "returns", [(730, 180)]),
    ln((300, 160), (230, 277), "inject", "", [(270, 160), (270, 277)]),
    ln((300, 210), (230, 471), "notify", "", [(255, 210), (255, 471)]),
    ln((600, 60), (930, 60), "inject", "injected"),
    ln((600, 129), (1075, 530), "inject", "", [(875, 129), (875, 500), (1075, 500)]),
    ln((930, 122), (600, 404), "assoc", "", [(855, 122), (855, 404)]),
    _tx(727, 397, "the algorithm reads and writes it", "var(--muted)", 10.5),
    _tx(150, 662, "notified after the unlock", "var(--muted)", 10.5),
    ln(B["tb"]["t"], B["algo"]["b"], "inherit"),
    ln((930, 307), (930, 80), "inherit", "", [(905, 307), (905, 80)]),
    ln((930, 417), (930, 100), "inherit", "", [(892, 417), (892, 100)]),
    ln(B["flat"]["t"], B["resolver"]["b"], "inherit"),
    ln((930, 759), (930, 570), "inherit", "", [(905, 759), (905, 570)]),
    ln(B["resolver"]["l"], B["rule"]["r"], "assoc", "returns"),
    ln(B["tiers"]["l"], B["tier"]["b"], "assoc", "", [(915, 759), (915, 670), (730, 670)]),
]

# the follow-up code, drawn where it plugs in. Dashed grey frame = Extensions.java, not Main.java.
_ext = ('<rect x="10" y="684" width="880" height="166" rx="8" fill="none" stroke="var(--muted)" stroke-dasharray="6 5" opacity="0.7"/>'
        + _tx(450, 708, "Extensions.java: page 05's code. The boxes plug into the three dashed interfaces above; none of them opens RateLimiter.", "var(--muted)", 11.5))
for _k, (_t, _s) in enumerate([("ShadowLimiter", "a Limiter: runs it, admits all"),
                               ("LayeredLimiter", "a Limiter: tenant AND global"),
                               ("RedisTokenBucket", "a Limiter: 12 pods, 1 budget"),
                               ("WaitingLimiter", "wraps a Limiter: waits"),
                               ("Gcra", "an Algorithm: the leaky bucket"),
                               ("CreditWindow", "an Algorithm: saved credits"),
                               ("WarmUpRules", "a RuleResolver: a ramp up")]):
    _ext += _bx(22 + (_k % 4)*218, 718 + (_k // 4)*56, 206, 46, _t, _s, dash=True)
_ext += _tx(450, 842, "also here: UnsafeLimiter (the bug), CasBucket (no lock at all), Endpoints, HitCounter (LeetCode 362)", "var(--muted)", 11)
edges.append(_ext)

UMLSVG = uml_svg(1230, 900, edges, legend_y=872)

HOW_TO_READ = ("<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;record&raquo; = a small immutable "
 "value; &laquo;enum&raquo; = a fixed list). Middle: its fields, the state it holds. Bottom: its methods. Everything outside the "
 "grey dashed frame at the bottom is <code>Main.java</code>. The seven boxes inside it are <code>Extensions.java</code>, drawn to "
 "show that page 05's code hangs off three interfaces. <b>The arrows.</b> "
 "Hollow triangle = implements. Filled diamond = owns: the limiter owns one KeyState per key and is the only thing that "
 "deletes one. Plain arrow = references or returns. Dashed green = handed in through <code>configure()</code>. Dotted blue "
 "= notifies, after the unlock. <b>Where state lives:</b> everything mutable is in KeyState: the tokens, the instant "
 "they were measured at, the window counters, the log, and the lock that guards all of them. The RateLimiter holds only the "
 "map of those states plus the three things it was handed. Rule and Decision are immutable, so they are shared freely and "
 "never locked. The algorithms hold no state at all. They are handed a KeyState and a Rule and do arithmetic on them, which "
 "is why one instance serves every key in the process.")

# ============================================================ page 04: the code
CODE_INTRO = ("Read the green comments above each class and method first. They say what the thing is for and what it "
 "guarantees, which is the whole shape of the system in two minutes; then read the bodies for the mechanics. Each copy "
 "button copies that whole file. <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> "
 "must print ALL PASS, and <code>java Main</code> runs the demo and the hundred-thread race.")

# ============================================================ page 05: follow-ups and practice
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3><button class="timer" data-min="60">start 60:00</button></div>'
 '<div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six clarifying questions. Then type in this order. The Clock interface, with a manual one for tests. '
 'The Rule and Decision records. KeyState with its own lock, holding just the tokens and the instant they were measured. '
 'The RateLimitAlgorithm interface, and TokenBucket behind it. RuleResolver with a flat implementation. RateLimiter: its map, '
 'the find-and-lock helper, and the charge-then-admit order in <code>allow</code>. The filter that turns a Decision into a 429. '
 'And a main that fires a hundred threads at one key on a frozen clock. That is the must-write core. The rest of Main.java '
 '(three window algorithms, tiers, observers, refund, the sweeper) is follow-up material: write it when they ask.</div></div>')

FU = [
("Ops doubles a tenant's limit during a sale, and a new tenant must ramp up instead of starting at full speed. No restart.", "functional", 5,
 "The limits already live behind <code>RuleResolver</code>, so neither change opens the limiter. TierRules keeps each tier's rule in an AtomicReference (a holder whose value is swapped in one step), so <code>setRule</code> takes effect on the next decision and never in the middle of one. That is why <code>allow</code> reads the rule exactly once, into a local. The subtlety is lowering a limit: a bucket may hold more tokens than the new burst allows. So the refill caps the tokens at the current burst every time, before any charge; otherwise you would grant permits the new policy says do not exist. The ramp is a wrapper round the same interface. WarmUpRules remembers when it first saw a key and scales the rule's numbers from a tenth up to the whole limit over 30 seconds, leaving the tier rules underneath untouched.",
 sect(src, "class TierRules", "interface Limiter {") + "\n" +
 "// in allow(): the rule is read ONCE into a local, so one decision never sees two rules\n"
 "Rule rule = rules.ruleFor(key);\n\n"
 "// in TokenBucket: the cap is applied on every refill, so a lowered burst bites at once\n" +
 sect(src, "    private void refill", "    public String name() { return \"token bucket\"; }") + "\n" +
 X("warm-up", "the leaky bucket")),

("A hundred threads hit one key at its limit at the same instant. Prove that exactly the limit gets through.", "non-functional", 10,
 "The race lives between reading \"one token left\" and writing \"zero\". In this design the refill, the check and the charge happen inside one lock, on the key's own state, so no other thread can run in the gap. The proof: 100 threads wait on one latch (a gate that opens for every waiting thread at once), with the clock frozen so no permit can be minted mid-race. The latch opens, every thread calls allow for the same key, and the test counts the admissions. Exactly 50 on a limit of 50, and the bucket ends at zero, not below it. The clock must be frozen for the count to be exact: with a live clock the answer is 50 or a few more, and the test proves nothing.",
 T("        // 3. a hundred threads", "        // 4. a key nobody has seen")),

("One lock per key. Does that scale, or have you just moved the bottleneck? What about a single hot key?", "non-functional", 10,
 "It scales, and the answer is arithmetic, not opinion. Move 8 has the sums: the hottest of 5,000 keys holds its lock for about 10 microseconds in every second, and no other key touches that lock. The bottleneck did not move to the map either, because a ConcurrentHashMap needs no lock around it. The interesting half of the question is one genuinely hot key: one tenant carrying all the traffic. Even there, measured with 100 threads arriving together, the slowest waited about 15 microseconds in front of 2 milliseconds of work it was gating. That never shows up in a latency graph (a chart of how long requests take). If it ever did, rung one of the ladder removes the lock rather than splitting it. Hold the whole bucket as one immutable value and swap it with compare-and-set, so a thread that loses recomputes against the winner's value instead of sleeping. ExtDemo prints the real cost of that: 200 threads, exactly 50 admitted, and how many swaps were lost and redone. OpenAI's 2026 version hands you a limiter with the read-check-write bug and asks you to fix it, then make it faster. The lock is the fix; compare-and-set is the speed-up.",
 sect(src, "    public Decision allow(String key, long cost)", "    void refund(String key") + "\n" + X("rung one of the ladder", "shadow mode")),

("The limiter said yes, and then the call never happened — the downstream service threw, or a later check refused it. What happens to the permit?", "functional", 5,
 "It is given back. The order inside allow is charge first, then admit, because admitting is the irreversible half; that leaves exactly one thing to undo, and <code>refund</code> is it. A refund refills from elapsed time first, then adds the permits back, capped at the burst, so it can never mint budget that was not earned. An unknown key is ignored rather than created. Call it once, straight after the failed call: two refunds give back twice, and a late one returns a permit that time has already returned. The place this really shows up is layered limits: a tenant budget and a global budget, charged in order. When the global one refuses, the tenant is refunded at once; otherwise the tenant loses permits for a request nobody served. The demo checks that exact number: 3 admitted through a global budget of 3, and the tenant still holding 7 of its 10.",
 sect(src, "    void refund(String key", "    long remaining(String key)") + "\n" + X("layered limits", "back-pressure")),

("A dashboard asks \"how many permits are left\" a thousand times a second, and there are ten million keys. Show me both.", "non-functional", 5,
 "The read is O(1) and needs no new structure: the bucket already holds the tokens and when they were measured, so the answer is a refill and a floor, under the key's lock. A read that refills is still a write, which is why it takes the lock. An unknown key answers what a new key would have and is deliberately not created, so a monitoring sweep cannot fill the map. Memory is the real question: about 340 bytes a key, 3.4 GB at 10 million. So a scheduled task calls sweepIdle, which drops keys nobody has asked about for a while. Saying why that loses nothing is the senior move. A key idle long enough to be full again is the same as a fresh key, and that takes one window when the burst is no bigger than the window's permits. Two traps come with it. Deleting a key while another thread is deciding on it would swallow a spent permit, so the state is marked removed under the lock and that caller fetches again. And a client that never repeats a key can fill the map faster than the sweeper drains it. So the map also gets a hard maximum, past which an unknown key is refused: a limiter that runs out of memory is worse than one that is strict.",
 sect(src, "    long remaining(String key)", "    int sweepIdle(long idleMs)") + "\n" +
 sect(src, "    int sweepIdle(long idleMs)", "    int size()") + "\n" +
 sect(src, "    private KeyState lockState(String key", "    private void publish(String key")),

("Which rate-limiting algorithms do you know, and which one would you actually ship?", "design", 10,
 "Five names, three real ideas. The token bucket, which this code ships, holds permits that refill with elapsed time. It is O(1) in time and memory, and it lets a client burst up to a stored depth, which is how API plans are sold: 600 a minute, burst 100. The leaky bucket is not a different answer. As a <i>meter</i> (water drains at the steady rate, each call pours in its cost, overflow is refused) it is the same arithmetic upside down. GCRA keeps it as one moment per key, and block 9 of FailureTests shows it admitting the identical calls, even at 3 a second. The <i>queue</i> reading of \"leaky bucket\" behaves differently: it delays calls instead of refusing them, which is shaping, not limiting. The window family is about accuracy at the edge. The fixed window is one counter and can pass twice the limit in an instant at the boundary. The sliding counter adds one more counter and is close on real traffic, and the log is exact at the price of one timestamp per permit. So pick by endpoint, not by fashion: token bucket at the front door, sliding window log on login, where five a minute has to mean five.",
 "// the menu, and what each one costs. P permits per window W, burst B.\n"
 "//\n"
 "//  algorithm                state per key          time    burst?  exact?  where it belongs\n"
 "//  ----------------------------------------------------------------------------------------------\n"
 "//  token bucket             2 numbers              O(1)    yes     yes     the default: public APIs\n"
 "//  leaky bucket (meter)     1 moment  -- Gcra      O(1)    yes     yes     same admissions, whole-number sums\n"
 "//  leaky bucket (queue)     a queue of callers     O(1)    no      yes     shaping, not limiting\n"
 "//  fixed window             1 counter + a stamp    O(1)    yes     NO      never alone: 2x at the boundary\n"
 "//  sliding window counter   2 counters + a stamp   O(1)    yes     almost  Cloudflare's edge: 0.003% wrong\n"
 "//  sliding window log       P timestamps           O(k)    yes     yes     login, OTP: 5 a minute means 5\n"
 "//\n"
 "// Ship the token bucket, and say why in one line: O(1) in time AND memory, and its worst instant is a burst\n"
 "// you chose, never a whole extra window. Burst is a knob separate from rate: the shape a plan is sold in.\n\n"
 + T("        // 9. the leaky bucket", "        // 10. a call bigger")),

("Someone spends their whole minute at 11:59:59 and their whole next minute at 12:00:00. Show me the bug and the fix.", "design", 10,
 "A fixed window is a counter plus the window it belongs to. Windows sit on an absolute grid (they reset on the second, the minute, the hour), so a client that knows the boundary can spend twice the limit across it. The test proves it: 10 calls through in 100 milliseconds on a limit of 5 a second. The O(1) answer is the sliding window counter: count this window exactly, and add a share of the previous window, weighted by how much of it is still inside the last 60 seconds. Just after the boundary the previous window counts almost in full, so the same burst is refused. It assumes the previous window's calls were spread evenly. On real traffic that is close: Cloudflare, which runs it at its edge, measured 0.003% of requests decided wrongly. A client that packs its calls into the end of a window can still get near twice the limit over a sliding minute. When that matters, use the exact answer, a timestamp per permit in a deque; it costs memory in proportion to the limit, so keep it for a login endpoint. The token bucket has no grid, so no boundary: the most it lets through in one instant is the burst, a number you chose.",
 sect(src, "class SlidingWindowCounter", "class SlidingWindowLog") + "\n" + T("        // 2. the fixed window", "        // 3. a hundred threads")),

("Atlassian's version: each customer may make X requests per Y seconds, and a customer who does not use all of them keeps the rest as credits, up to a maximum. Add it, and keep it thread-safe.", "twist", 10,
 "It is a new algorithm behind the same interface, so nothing else opens. It runs under the same per-key lock as every other algorithm, so it is thread-safe for free. CreditWindow is a fixed window of <i>permits</i> per window plus a bank of saved credits. At each new window, whatever the ended windows left unused goes into the bank, capped at burst minus permits; a quiet window saves all of it. A call that finds this window full spends a credit instead of being refused. So Rule(5, 1 second, 8) means 5 a second plus up to 3 saved. The test runs three seconds. 8 get through in the first, because a new key starts with a full bank, as a new bucket starts full. Then 5 in a busy second after a busy one, and 8 again after a quiet second. Say the link out loud: this is the token bucket's burst, earned one whole window at a time instead of continuously.",
 X("credits", "the hit counter") + "\n" + T("        // 16. credits", "        // 17. the hit counter")),

("LeetCode 362: hit(timestamp) records a hit, getHits(timestamp) returns the hits in the past 5 minutes. Then: what if there are millions of hits a second, from many threads?", "twist", 10,
 "The first answer is the sliding window log from Main.java: a queue of timestamps; drop the old ones, count what is left. The follow-up breaks it, because a million hits a second means a million timestamps a second in memory. The fix keeps 300 slots, one per second of the window. Each slot remembers which second it is counting and how many hits it saw, and a newer second that lands on the slot resets it. Memory is 300 slots whatever the traffic, and getHits is one pass over them. For many threads, one lock around both methods is enough, because each holds it for a few field writes. If that lock ever shows up, each slot becomes one small value swapped with compare-and-set, so a reset and a hit on the same slot cannot interleave. The test fires 100,000 hits from 4 threads, gets all of them back, and gets 0 three hundred seconds later. Databricks asks the same shape as load metrics on a key-value store: average puts and gets per second over the last 5 minutes. LeetCode 359, the Logger Rate Limiter, is the smallest case: a map from each message to the second it may next be printed.",
 X("the hit counter", "Runs every extension") + "\n" + T("        // 17. the hit counter", "        System.out.println(failures")),

("We run twelve pods. Right now each one grants the full limit, so the tenant gets twelve times what they pay for. Fix it.", "twist", 10,
 "The interface survives; only an implementation is added. A Redis-backed limiter runs the same refill-and-deduct as one Lua script (a small program Redis runs as one step). Redis runs commands one at a time on a single thread, so the script is the fleet's version of the per-key lock. The read and the write both happen on the server, so twelve pods have no gap to race in. The script also reads the time from Redis itself, so pods whose clocks disagree still share one clock. The reference code models Redis with a map behind one lock, with the real script in the comment above it. The demo runs two pods against one budget of 50 and admits 50, not 100. Three more things to say out loud. Keep a local bucket in front as a cheap first filter, so most refusals never leave the pod. The key's TTL (time to live: Redis deletes the key by itself when it runs out) is the sweeper, so eviction comes free. And decide now whether a Redis outage fails open (let every call through) or fails closed (refuse every call), or it will be decided for you at three in the morning.",
 X("twelve pods", "a limit per endpoint") + "\n" + T("        // 15. twelve pods", "        // 16. credits")),

("Different limits per endpoint, and a search costs more than a ping.", "twist", 5,
 "Both are smaller than they look. \"A limit per endpoint\" is a different key: tenant plus route. The map grows by the number of routes, and not one class changes. Per user <i>and</i> per endpoint at once is two layers in LayeredLimiter, keyed by user and by user plus route. \"A search costs more\" is the cost argument that has been on <code>allow</code> since the first line, read from a small table of route to permits. A refusal for a cost of five waits long enough to have earned five, not one. And a call that costs more than the whole bucket is refused for good (Retry-After: never), because no wait would ever make room: the client must split it. Cloudflare (2025) and Cursor (2026) ask the composed version: several rules at once, such as global, per path, per user plus path, and even a byte budget. A request counts against no rule unless every rule admits it. That is LayeredLimiter with one layer per rule. A byte budget is the cost argument with the body size as the cost, and the refund on a refusal makes the rules all-or-nothing. The thing worth flagging is the number of keys: tenants times routes is what the sweeper now has to keep up with.",
 X("a limit per endpoint", "warm-up") + "\n" + T("        // 10. a call bigger", "        // 11. an unknown key")),

("Before we switch this on for a live tenant, ops wants a week of evidence that it will not break them. Give them that without refusing one request.", "twist", 5,
 "Shadow mode, and it is a wrapper, not a change. <code>ShadowLimiter</code> takes any Limiter, runs the real algorithm and charges the real permits. Then it throws the refusal away and admits everything, while counting what it would have blocked. A week of that count on a dashboard answers \"what will this break?\" with evidence instead of a guess. Switching it on for real is one wiring line, <code>new ShadowLimiter(limiter)</code> becoming <code>limiter</code>, and no class is opened to do it. The detail worth saying: it charges the permits for real, so the number it reports is the number you will get. It is not an estimate from a parallel bucket that has drifted away from the live one.",
 X("shadow mode", "layered limits")),

("A nightly batch job would rather wait for a permit than fail. Give it that, and tell me where you would refuse to offer it.", "twist", 5,
 "The decision already carries the answer: <code>retryAfterMs</code> is the shortest wait after which the call fits, if nobody else spends first. So waiting is a loop around the same call and needs no new state anywhere. <code>WaitingLimiter</code> takes a timeout the caller chose, asks, and on a refusal sleeps exactly the retry-after the limiter reported, instead of polling on a fixed interval. At the deadline it returns false rather than waiting forever, which is the half people forget, and it gives up at once on a call that can never fit. This is back-pressure: the caller is slowed down instead of failed. Plaid's version also bounds how many may wait: put a Semaphore (a counter of free slots) of N in front, and a caller that cannot get a slot is refused at once. Where I would refuse to offer it is a web request. A thread held under load is how a service falls over: the queue in front of the limiter becomes the outage. So this is for batch jobs and queue consumers, and the web tier keeps failing fast with a 429.",
 X("back-pressure", "twelve pods")),

("Where does time come from, and how do you test a refill without a Thread.sleep?", "design", 5,
 "Time is handed in as a one-method interface. In production it is System.nanoTime, not the wall clock: only elapsed time matters here, and nanoTime cannot jump backwards when NTP corrects the machine. In tests it is a clock the test sets, so \"200 milliseconds later\" is one line that runs instantly; the whole suite has no sleep in it. That is also what makes the nasty cases testable. When the clock goes backwards nothing may be minted, and nothing may be minted for the stretch it travels twice either. The refill still keeps its own guard: elapsed time of zero or less mints nothing. A monotonic clock (one that never goes backwards) is a promise about production, not about whatever a caller injects.",
 sect(src, "interface Clock", "enum Tier") + "\n" + T("        // 1. burst then refill", "        // 2. the fixed window")),

("Which pattern is where, and why did each one earn its place?", "design", 5,
 "Nothing here was chosen up front, which is why each name has a one-sentence defence. Strategy is move 3: the algorithm is a one-call interface handed in through <code>configure</code>. Decorator appears twice, and both times it wraps instead of copying: ShadowLimiter wraps a whole limiter, WarmUpRules wraps a rule source. Observer is move 3 too, kept outside the lock by move 4. Three are worth naming as <i>not</i> earned. State: a key's life is real, but its state is just its numbers, so there is no status field and no class per state. Factory: not until algorithms arrive as strings from a config file. Singleton: never, because a static getInstance would make every test share a bucket.",
 "// Strategy: the rule that decides, behind an interface, handed in\n"
 "interface RateLimitAlgorithm { Decision tryAcquire(KeyState s, Rule rule, long cost, long nowMs); }\n"
 "void configure(RateLimitAlgorithm algo, RuleResolver rules, Clock clock) { ... }\n\n"
 "// Decorator: wrap the thing, do not copy it\n"
 "class ShadowLimiter implements Limiter { private final Limiter delegate; /* run it, then allow anyway */ }\n"
 "class WarmUpRules implements RuleResolver { private final RuleResolver base; /* scale its numbers by age */ }\n\n"
 "// Observer: announced after the unlock, each listener in its own try/catch\n"
 "private void publish(String key, Decision d) {\n"
 "    for (LimiterObserver o : observers) { try { o.onDecision(key, d); } catch (RuntimeException ignored) { } }\n"
 "}\n\n"
 "// State: NOT earned. The life is drawn in move 6, but a key's state is just its numbers:\n"
 "// tokens left means SPENDING, none left means THROTTLED. No status field, no class per state.\n\n"
 "// Factory: not yet. It earns its place the day this line is needed:\n"
 "Map<String, Supplier<RateLimitAlgorithm>> registry = Map.of(\"token_bucket\", TokenBucket::new, \"sliding_log\", SlidingWindowLog::new);\n"
 "RateLimitAlgorithm algo = registry.get(config.get(\"algorithm\")).get();\n"),

("Which SOLID letter is where in this code?", "design", 5,
 "The honest answer is short, because SOLID here is a check on the moves, not a goal anyone designed for. S: TokenBucket changes when token arithmetic changes, RateLimiter when the key lifecycle does, TierRules when the plans do. O: shadow mode, the second global budget and credits each arrived as a new class plus one wiring line. L: Gcra takes TokenBucket's place and FailureTests shows the same calls admitted; WaitingLimiter wraps any Limiter without an <code>instanceof</code>. I and D are one fact seen from two sides. Clock, RuleResolver and LimiterObserver have one method each and are handed in. That is what lets a test give the limiter a clock that jumps and a listener that always throws.",
 "// S: one reason to change each\n"
 "class TokenBucket { /* token arithmetic */ }   class RateLimiter { /* keys, locks, order */ }   class TierRules { /* policy */ }\n\n"
 "// O: new behaviour is a new class plus one wiring line; nothing was opened\n"
 "Limiter live = new ShadowLimiter(limiter);                 // day 1: measure\n"
 "Limiter live = limiter;                                    // day 8: enforce\n\n"
 "// L: one drops in for another, and nobody checks which\n"
 "limiter.configure(new Gcra(), rules, clock);               // admits exactly what TokenBucket did\n"
 "new WaitingLimiter(new RedisTokenBucket(redis, rule));     // any Limiter will do\n\n"
 "// I: one method each, so a fake is a lambda\n"
 "interface Clock { long nowMs(); }   interface RuleResolver { Rule ruleFor(String key); }\n\n"
 "// D: handed in, which is what makes the nasty tests possible\n"
 "limiter.configure(new TokenBucket(), new FlatRules(Rule.perSecond(5)), manualClock);\n"
 "limiter.addObserver((k, d) -> { throw new RuntimeException(\"the metrics sidecar is down\"); });\n"),

("An enum for the algorithm with a switch, or an interface? And where would a Factory actually pay here?", "design", 3,
 "Split it by whether the thing is data or behaviour. A tier is data: FREE, PRO and ENTERPRISE differ only in three numbers. So it is an enum with a rule per constant, and adding a plan is one constant and one row. An algorithm is behaviour, with its own fields and its own arithmetic. An enum with a switch inside <code>tryAcquire</code> would put four unrelated implementations in one method and reopen it for every new one. That is an interface, and the sliding window proved it by arriving as a class, not a case. A Factory pays the moment creation stops being a constructor call: algorithms named in a YAML file, and a registry from name to constructor. Then a new algorithm is a registration, not a growing switch. Until then it is one <code>new</code> in the wiring code, and a factory would only hide it.",
 "// data: a tier is three numbers, so it is an enum plus a table\n"
 "enum Tier { FREE, PRO, ENTERPRISE }\n"
 "rules.setRule(Tier.PRO, Rule.perMinute(600, 100));\n\n"
 "// behaviour: an algorithm has its own state and its own arithmetic, so it is a class behind an interface\n"
 "class SlidingWindowCounter implements RateLimitAlgorithm { /* arrived without reopening anything */ }\n\n"
 "// NOT this: one method that must be reopened for every new algorithm\n"
 "enum Algo { TOKEN_BUCKET, FIXED_WINDOW;\n"
 "    Decision tryAcquire(...) { switch (this) { case TOKEN_BUCKET: ...; case FIXED_WINDOW: ...; } } }\n\n"
 "// the Factory earns its place when the name comes from configuration\n"
 "Map<String, Supplier<RateLimitAlgorithm>> registry = Map.of(\"token_bucket\", TokenBucket::new, \"gcra\", Gcra::new);\n"),
]

build(dict(
    slug="rate-limiter",
    title="Rate Limiter",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: the demo, 17 failure-test blocks and a 100-thread race pass",
    problem_body=PROBLEM_BODY,
    derivation_lead=DERIVATION_LEAD,
    moves=[(t, MV[k], txt) for (t, txt, k) in MOVES],
    uml_svg=UMLSVG,
    how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", src), ("Extensions.java", ext), ("FailureTests.java", tests)],
    test_class="FailureTests",
    implement_card_html=IMPLEMENT,
    followups=FU,
))
