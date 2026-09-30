# Cache with eviction policies LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
# The angle of this page is the POLICY SEAM: one cache, many rules behind one interface. The pointer surgery inside
# an LRU list and the frequency buckets inside LFU are derived move by move on the LRU page; here they are details.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"cache-eviction/Main.java").read_text()
ext   = (H/"cache-eviction/Extensions.java").read_text()
tests = (H/"cache-eviction/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def tail(a, b):
    """slice Main.java between two literal anchors, dropping a trailing class-closing brace"""
    out = src[src.index(a):src.index(b)].rstrip()
    return (out[:-2].rstrip() if out.endswith("\n}") else out) + "\n"

RED = "#ff6b6b"
LRU_PAGE = '<a href="lru-workbench.html">the LRU cache page</a>'
TTL_PAGE = '<a href="mt-ttl-cache-workbench.html">the TTL cache page</a>'

# ============================================================ page 01: the problem
pf = _D
rows = [("get", 30, [("key K: is it in the table?", "one hash lookup, no walk"),
                     ("is it past its deadline?", "a dead entry is a miss"),
                     ("tell the policy it was read", "LRU moves it, FIFO does not"),
                     ("return the value", "nothing is allocated")]),
        ("put", 175, [("key K, value V, a deadline", "worked out before the lock"),
                      ("full? ask the policy who goes", "evict first, admit second"),
                      ("write it, tell the policy", "table and policy, one step"),
                      ("tell the listener, and why", "after the unlock, never inside")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V100", dash=True)
pf += _bx(330, 100, 560, 44, "already dead: dropped right here, reported EXPIRED",
          "expiry is the clock's decision, and it always applies", dash=True)
pf += _tx(88, 272, "read", "var(--acc)", 13)
pf += _tx(175, 272, "the value for a key (one hash lookup);  how many entries are resident;  hits, misses, evictions and expirations",
          "var(--text)", 12, "start")
pf += _tx(88, 298, "drop", "var(--acc)", 13)
pf += _tx(175, 298, "remove(key) takes it out and reports EXPLICIT;  cleanUp() sweeps every dead entry in one pass, reporting EXPIRED",
          "var(--text)", 12, "start")
pf += _tx(615, 332, "fifty threads call get and put at the same instant: the table and the policy must never name different keys, "
          "and the count must never go one over the capacity", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 348, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:00:00  put A, B, C, D", ["a cache of four, now full", "A and C have long TTLs", "D's fuse is five seconds"], False),
      ("09:00:02  get B, then get A", ["B and A have two uses each", "C and D still have one", "and A is the freshest read"], False),
      ("09:00:06  put E into a full cache", ["FIFO gives up A, the oldest arrival", "LRU gives up B, the coldest read",
                                             "LFU gives up C, the fewest uses"], True),
      ("09:00:10  the same put, 4s later", ["D died at 09:00:09", "ExpiryFirst(LRU) takes D, not B",
                                            "cause EXPIRED, not CAPACITY"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 45 + k*292
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+136) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+136)
    pe += _card(x, 60, 272, 110, t, lines, acc=acc)
P_EX = _mv(1230, 185, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>getIfPresent(key): the value, or nothing &mdash; and a read past the deadline is a miss, not a stale value.</li>
<li>put(key, value) and put(key, value, ttl): insert a new entry or overwrite one in place.</li>
<li>A fixed capacity: a put that would go over it removes exactly one entry, chosen by the policy, <i>before</i> the new one is admitted.</li>
<li>The rule is chosen at construction and swappable while the cache is running: LRU, LFU, FIFO, shortest-fuse-first, or anything written next year.</li>
<li>TTL on top of any rule: an entry past its deadline is never returned, and is preferred as a victim.</li>
<li>Tell somebody when an entry leaves, with the cause: EXPLICIT, REPLACED, EXPIRED or CAPACITY.</li>
<li>Hit, miss, eviction and expiration counts, and the hit rate.</li>
<li>remove(key), size(), capacity(), and cleanUp() to sweep the dead on demand.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many threads at once: the table and the policy must never be seen naming different keys.</li>
<li>The count must never exceed the capacity, not even for an instant in the middle of a put.</li>
<li>get and put O(1) under LRU, LFU and FIFO; O(log n) under the deadline-ordered rule &mdash; and say which.</li>
<li>A new rule is a new class: the cache is never opened, and no caller changes.</li>
<li>No caller code runs while the lock is held: not the loader, not the listener.</li>
<li>Time comes from an injected clock, so a 24-hour TTL is provable in zero milliseconds.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds invalidation across two servers).</li></ul></div></div>
'''

PROMPT = ('"Design a cache with a fixed capacity and a pluggable eviction policy. Least-recently-used to start, but I '
          'am going to ask for least-frequently-used and FIFO before we are done, some entries carry a time-to-live, '
          'and something has to be told when an entry is dropped and why. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A box that holds a fixed number of answers so the slow thing '
 'behind it &mdash; a database, an API, a computation &mdash; is asked as rarely as possible. The part that makes this '
 'problem different from "write an LRU cache" is the word <i>pluggable</i>: the interviewer is going to change the '
 'rule while you are typing, and the design is graded on whether that costs you a new file or a rewrite. Underneath, '
 'two questions get mashed together by almost everybody, and keeping them apart is the decision the whole design rests '
 'on. <b>The cache is full, who goes?</b> is a ranking question whose answer depends on the traffic: least recently '
 'used, least frequently used, oldest arrival, shortest remaining fuse. <b>May I still return this entry?</b> is a '
 'validity question whose answer depends on the clock alone, and it applies in a cache that is two per cent full. The '
 'first is swappable and lives behind an interface. The second is never optional and lives in the cache. Many threads '
 'hammer one cache, so the thing that must always be true is that the table and the ranking name exactly the same set '
 'of keys, and the count never goes one over the capacity.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a '
 '<code>main</code> that pushes one access trace through several rules and shows a different key leaving each time. The '
 'interviewer is watching for, in this order: the questions you ask before typing (is the bound entries or bytes, and '
 'is TTL a rule or a validity check, are the first two); which classes exist and which one owns the table; get and put '
 'end to end, and the <i>order</i> inside put; what happens when fifty threads put into a full cache at once; where the '
 'rule that will change lives, so "now make it LFU" is a new class and one line; and what a caller is told when an '
 'entry vanishes. Then the twists: TTL over any rule, swapping the rule at runtime, writes that have to reach the '
 'database, bounding by bytes, sampling the way Redis does, a nightly scan that destroys the hit rate, and two '
 'servers.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>One cache in this process, or shared across machines?</td><td>One process, in memory</td><td>No serialisation and no network; invalidation is a follow-up (move 12)</td></tr>'
 '<tr><td>Is the bound a count of entries, or a budget in bytes?</td><td>A count of entries</td><td>One check before an insert instead of a loop of evictions (moves 5, 12)</td></tr>'
 '<tr><td>Which rules, and will more arrive mid-round?</td><td>LRU now; LFU, FIFO and TTL before the hour is out</td><td>The rule is an interface handed in, never a flag or an <code>if</code> (move 3)</td></tr>'
 '<tr><td>Is TTL a rule for who leaves, or a rule for what may be returned?</td><td>Both, and they are different questions</td><td>Expiry lives in the cache; shortest-fuse-first is one more policy (moves 3, 6)</td></tr>'
 '<tr><td>Does anybody need to know when an entry left, and why?</td><td>Yes, with the cause</td><td>A listener told an enum cause, called after the unlock (moves 3, 4)</td></tr>'
 '<tr><td>On a miss: return nothing, or go and fetch it?</td><td>Return nothing; a loader can be wrapped on</td><td>Read-through is a wrapper, not a field on the cache (move 12)</td></tr>'
 '<tr><td>Read-heavy or write-heavy, and how many threads?</td><td>Read-heavy, tens of threads</td><td>One lock now, with striping named as the next rung (moves 4, 7, 8)</td></tr>'
 '<tr><td>Exact LRU, or is a good approximation acceptable?</td><td>Exact now; approximate on request</td><td>Sampling is a policy, so it is a class and not a rewrite (moves 3, 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> the capacity is a fixed count of entries; the rule for who leaves is a '
 'whole object handed in, not a flag; expiry is a different question from eviction and lives in the cache, so it '
 'applies whatever rule is in force; null is how a miss is reported, so neither keys nor values may be null; time is '
 'injected; one process, in memory. Named as out of scope: bounding by bytes, striping, reads and writes that reach a '
 'database, a background '
 'sweeper, two servers &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a CACHE of fixed CAPACITY holds ENTRIES; a POLICY ranks the KEYS; a DEADLINE decides validity; "
          "a LISTENER is told the CAUSE", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 175, "PolicyCache", "table, lock, clock, policy", 1),
                          (220, 175, "CacheEntry", "a value and two stamps", 1),
                          (410, 185, "EvictionPolicy", "no storage: an interface", 0),
                          (610, 185, "the four rules", "LRU LFU FIFO shortest-fuse", 1),
                          (810, 175, "RemovalCause", "why it left: an enum", 1),
                          (1000, 175, "Key / Value", "the caller's own objects", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 192, "solid = it owns state, so it becomes a class.   dashed = no state of its own: an interface, or an object the caller already has",
          "var(--muted)", 11)
MV[1] = _mv(1230, 208, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("find the value for a key", "PolicyCache  (owns the table)", "cache.getIfPresent(k)"),
                                       ("say this key was just used", "EvictionPolicy  (owns the ranking)", "policy.onGet(k, now)"),
                                       ("name who should go", "EvictionPolicy  (owns the ranking)", "policy.selectVictim(now)"),
                                       ("evict, admit and announce", "PolicyCache  (owns table + lock)", "cache.put(k, v, ttl)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 270, "the policy never touches the table: it advises, the cache executes, so exactly one object ever mutates the entries",
          "var(--muted)", 11)
m2 += _tx(615, 289, "and notice what this move exposes: getIfPresent is a verb that WRITES. A read changes the ranking, so there are no pure readers here",
          "var(--acc)", 11)
MV[2] = _mv(1230, 302, m2)

# move 3: rules that change -> interfaces handed in
m3 = _D + _bx(30, 70, 220, 90, "PolicyCache", "is handed all four; builds none", acc=True)
for k, (t, sub, impl) in enumerate([("EvictionPolicy", "who goes when the cache is full", "LruPolicy / LfuPolicy / FifoPolicy / TtlPolicy"),
                                    ("RemovalListener", "who is told, and why", "a metric, a write-back store, a log line"),
                                    ("Clock", "where time comes from", "SystemClock  |  ManualClock for tests"),
                                    ("CacheLoader", "where a miss goes", "a database read, wrapped in single flight")]):
    y = 24 + k*60
    m3 += _ar("M250 115 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 440, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 285, "dashed green = handed in. The cache never names a policy class, so a fifth rule is a new file and one builder line",
          "var(--muted)", 11)
m3 += _tx(615, 304, "and one rule wraps the others: ExpiryFirst(rule) makes \"whatever is already dead\" the first answer for ANY rule, including next year's",
          "var(--acc)", 11)
MV[3] = _mv(1230, 318, m3)

# move 4: the gap, and one lock over BOTH structures
m4 = _D + _bx(30, 30, 230, 44, "thread A: put X", "the cache is full: who goes?")
m4 += _bx(30, 110, 230, 44, "thread B: put Y", "writing, policy not told yet")
m4 += _bx(360, 70, 200, 44, "the ranking", "already out of date", acc=True)
m4 += _ar("M260 52 H310 V82 H360") + _ar("M260 132 H310 V102 H360")
m4 += '<rect x="590" y="20" width="350" height="150" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(765, 44, "the gap", RED, 12)
m4 += _tx(765, 68, "A evicts using a ranking B has already changed,", RED, 11)
m4 += _tx(765, 88, "or drops a key from the table and not the policy", RED, 11)
m4 += _tx(765, 112, "then the policy names a key that is not there,", RED, 11)
m4 += _tx(765, 132, "nothing goes, and the cache grows past its bound", RED, 11)
m4 += _tx(765, 158, "fix: the table AND the policy under ONE lock", "var(--text)", 11)
m4 += _bx(945, 45, 265, 100, "one ReentrantLock", "the whole operation, not one each", acc=True)
m4 += _tx(615, 190, "a ConcurrentHashMap beside an unsynchronised policy is fast and wrong: the bound holds only some of the time",
          "var(--muted)", 11)
MV[4] = _mv(1230, 205, m4)

# move 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("where is the value for key K?", "Map&lt;K, CacheEntry&lt;V&gt;&gt;", "O(1)"),
                                      ("who has gone longest without a read?", "linked key list + key &rarr; node map", "O(1)"),
                                      ("who has been used fewest times?", "count &rarr; LinkedHashSet buckets, plus minCount", "O(1)"),
                                      ("who arrived first?", "the SAME list, with onGet doing nothing", "O(1)"),
                                      ("whose deadline is soonest?", "TreeSet of (deadline, seq, key)", "O(log n)"),
                                      ("how many hits and misses?", "AtomicLong, incremented outside the lock", "O(1)")]):
    y = 20 + k*48
    m5 += _bx(30, y, 370, 38, q, "the question") + _ar("M400 %s H450" % (y+19), True)
    m5 += _bx(450, y, 570, 38, shape, "the shape", acc=True) + _ar("M1020 %s H1060" % (y+19), True) + _bx(1060, y, 140, 38, cost, "")
m5 += _tx(615, 330, "six questions, six shapes &mdash; and exactly one of them is not O(1), which is worth saying out loud "
          "rather than letting the interviewer find it", "var(--muted)", 11)
MV[5] = _mv(1230, 344, m5)

# move 6: the life of an entry and the ORDER inside put
m6 = _D + _bx(30, 30, 190, 44, "ABSENT", "not in the table")
m6 += _bx(280, 30, 190, 44, "LIVE", "in the table, still fresh", acc=True)
m6 += _bx(30, 120, 190, 44, "EXPIRED", "the clock decided")
m6 += _bx(280, 120, 190, 44, "EVICTED", "the policy decided")
m6 += _ar("M220 52 H280", True) + _ar("M420 74 V120", True) + _ar("M330 74 V97 H125 V120", True)
m6 += _tx(250, 186, "a read finds it dead and drops it there;  a full cache asks the policy", "var(--muted)", 10.5)
m6 += '<rect x="520" y="20" width="690" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(865, 44, "the order inside put, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 work out the deadline -- the lock is not taken and nothing is written",
                       "2 take the lock; a key already here is a rewrite, and a rewrite never grows the count",
                       "3 while full: ask the policy, then drop the key from the table AND the policy",
                       "4 only now write the entry and tell the policy about it",
                       "5 unlock, then hand the departures to the listeners",
                       "evict BEFORE admitting: under LFU a newcomer sits at one use, is the coldest key,",
                       "and an insert-then-evict cache would have it evict itself and do nothing at all"]):
    m6 += _tx(535, 68 + k*21, l, "var(--muted)" if k > 4 else "var(--text)", 11, "start")
MV[6] = _mv(1230, 222, m6)

# move 7: what is inside the lock, and ten threads at once
m7 = _D + _card(30, 20, 560, 150, "inside the lock: about a hundred nanoseconds",
                ["one hash lookup in the table", "the policy's bookkeeping: six pointer writes (LRU)",
                 "or two set operations (LFU), or one TreeSet insert (TTL, ~1 us at a million keys)",
                 "an uncontended lock and unlock: about twenty nanoseconds",
                 "no allocation on a hit, and nothing that can throw"], acc=True)
m7 += _ar("M590 95 H650", True) + _tx(620, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(650, 20, 550, 150, "outside the lock: microseconds to milliseconds",
            ["the deadline arithmetic: done before the lock is taken", "the loader on a miss: one to five milliseconds of database",
             "the removal listener: a metric, a socket, a log line", "the caller's own work: everything else"])
m7 += _tx(615, 200, "ten threads call get at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "thread %d" % (k+1), "waits %s ns" % (k*100), acc=(k == 9))
m7 += _tx(615, 283, "the tenth thread waits about nine hundred nanoseconds, which nobody can measure. But unlike most designs, "
          "this lock really can saturate,", "var(--muted)", 11)
m7 += _tx(615, 301, "and \"does one lock scale?\" deserves a number rather than a shrug: move 8 works out at which traffic it bites",
          "var(--acc)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="205" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one lock over the table and the policy: when does it bite?", "var(--text)", 12)
for k, l in enumerate(["one get under the lock: about 100 ns with LRU or LFU",
                       "a permissions cache at 100k gets a second: 10 ms of lock a second",
                       "that is 1% busy, and the queue never forms",
                       "the same cache at 1 million a second: 0.1 s of lock per second, 10% busy",
                       "at 10 million a second one lock IS the bottleneck -- say so before they do",
                       "and note: TTL ordering costs ~1 us, so it saturates ten times sooner"]):
    m8 += _tx(35, 66 + k*26, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 nothing slow inside the lock", "already done: the loader and the listener run outside it"),
                              ("2 stripe into sixteen segments", "spread hash; ~16x throughput, the bound is now per stripe"),
                              ("3 buffer the reads, replay under tryLock", "a hit becomes a lookup plus an array write -- Caffeine's design"),
                              ("4 out of process: Redis", "sampled eviction, approximate on purpose")]):
    m8 += _bx(600, 58 + k*42, 600, 36, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 240, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("insert first, evict second", "under LFU the newcomer evicts itself; test 2: d is resident and c is gone"),
                                ("the table drops a key, the policy does not", "every removal path calls onRemove; test 3: both track the same count"),
                                ("an expired entry is still handed back", "check the deadline on every read, and inject the clock; test 4: 24 hours in zero ms"),
                                ("a listener throws, or calls back in", "drain after the unlock in a try/catch; test 8: both are harmless"),
                                ("the listener is told only the key", "a cause on every removal; tests 5 and 10: four causes, and write-back flushes two"),
                                ("swapping the rule empties the cache", "re-index the live keys under the same lock; test 7: all three survive")]):
    y = 18 + k*42
    m9 += _bx(30, y, 340, 38, bad, "") + _ar("M370 %s H410" % (y+19), True) + _bx(410, y, 790, 38, fix, "", acc=True)
m9 += _tx(615, 292, "every claim this design makes has a failure test: FailureTests.java runs ten of them, "
          "forty checks, and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 306, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 810)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface EvictionPolicy&lt;K&gt; { ... K selectVictim(long nowMs); }", None), ("a fifth rule is a new file, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new ExpiryFirst&lt;&gt;(new LruPolicy&lt;&gt;())", None), ("TTL on top of ANY rule, present or future", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("fire(pending) after the unlock, each call in a try/catch", None), ("a metric hears; the cache never waits for it", None)],
          [("State", "var(--text)"), ("move 6", None), ("RemovalCause: EXPLICIT / REPLACED / EXPIRED / CAPACITY", None), ("\"why did my session go?\" has an answer", None)],
          [("Builder", "var(--text)"), ("move 3", None), ("newBuilder().capacity(4).policy(p).clock(c).listener(l)", None), ("six optional knobs, no constructor full of nulls", None)],
          [("Template Method", "var(--muted)"), ("not here", None), ("the cache calls four policy methods; it owns none of their bodies", "var(--muted)"), ("Strategy already did that job", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("a cache is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh one per check", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("the builder's single default (LRU) IS the whole registry", "var(--muted)"), ("it earns the name when rules arrive as config strings", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 415), ("the line that shows it", 525)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("PolicyCache stores and bounds; a policy ranks; CacheStats counts; a listener notifies", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("SegmentedLruPolicy is a new file; PolicyCache was never opened to add it", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("policy.selectVictim(now);  never \"is this the LFU one?\" -- even the approximate one substitutes", None)],
          [("I", "var(--acc)"), ("small interfaces, so a fake is a lambda", None), ("move 3", None), ("Clock, RemovalListener, CacheLoader: one method each; EvictionPolicy has four, the one blemish", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("new PolicyCache&lt;&gt;(cap, policy, clock, ttl) -- the string \"LruPolicy\" appears nowhere inside it", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 252, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 266, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "LFU, FIFO, segmented, sampled", "a new class behind EvictionPolicy plus one builder line", "", "move 3"),
        ("someone new wants to know", "a metric, a write-back store", "one more removal listener; the lock and the table do not move", "", "move 4"),
        ("a new step in an entry's life", "loading, refreshing, invalidated", "one more cause and one more checked transition", "", "move 6"),
        ("a new invariant across entries", "a budget in bytes, not a count", "the check AND the evictions inside the SAME lock, all or nothing",
         "and the single if becomes a loop: one big value pushes out several small ones", "move 4"),
        ("state that must outlive the process", "Redis, or a second server", "the far store becomes the loader; a write publishes an invalidation",
         "which node owns which key is consistent hashing, named and left out of scope", "moves 3 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 340, 44, t, sub) + _ar("M370 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five, PolicyCache, KeyList and the failure tests do not change; that is the test that the derivation was right",
           "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: a <b>cache</b> of fixed <b>capacity</b> holds <b>entries</b>; a <b>policy</b> ranks the "
 "<b>keys</b>; a <b>deadline</b> decides whether a value may still be returned; a <b>listener</b> is told the "
 "<b>cause</b>. The cache holds the table, the capacity, the lock and the clock, all of which change: a class. An "
 "entry is a value plus two stamps &mdash; when it was written and when it dies &mdash; so it is a small class, and "
 "writing it down first is what gives every rule a shared vocabulary. The policy has state of its own (an order, or "
 "counts, or a heap of deadlines) but it stores no values, so it is an <i>interface</i> with several implementations "
 "rather than a field on the cache. A cause is a fixed list of four things, so it is an enum, and the fact that it is "
 "four and not one is the whole point of telling anybody. A key and a value are the caller's objects and the cache "
 "never looks inside either.",
 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Find the value for a key\" touches the table, so it is <code>cache.getIfPresent(k)</code>. \"Say this key was just "
 "used\" touches the ranking, so it belongs to whatever owns the ranking: <code>policy.onGet(k, now)</code>. \"Name who "
 "should go\" is the policy's own question: <code>policy.selectVictim(now)</code>. \"Evict, admit and announce\" touches "
 "the table, the policy and the lock at once; only the cache sees all three, so <code>cache.put(k, v, ttl)</code> is "
 "the orchestrator. The split that matters falls straight out of this move: the policy never touches the table. It is "
 "told what happened and it names a key; the cache does the removing. One object mutates the entries, which is why one "
 "lock is enough. And notice the thing this problem exposes that most do not &mdash; <code>getIfPresent</code> is a "
 "verb that <i>writes</i>. A read moves a node or bumps a count, so there is no such thing as a pure reader here, and "
 "a read-write lock would buy exactly nothing.",
 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Four rules will change on this problem and one of them is the problem. Who leaves when the cache is full will change "
 "&mdash; LRU now, LFU in ten minutes, FIFO after that, and something nobody has written yet next year. Who is told "
 "when an entry leaves will change: a metric today, a write-back store tomorrow. Where time comes from must change, or "
 "you cannot test a day-long TTL. Where a miss goes may change: nothing today, a database read later. So each becomes "
 "an interface the cache is <i>given</i> and never builds: <code>EvictionPolicy</code>, <code>RemovalListener</code>, "
 "<code>Clock</code>, <code>CacheLoader</code>. This is where the patterns come from, not the other way round. A "
 "swappable rule behind an interface is <b>Strategy</b>. A cache that announces a departure without knowing what a "
 "metrics counter is, is <b>Observer</b>. And the one that carries this page: a rule that wraps another rule and adds "
 "to it is <b>Decorator</b> &mdash; <code>ExpiryFirst(policy)</code> makes \"whatever is already dead\" the first "
 "answer for any rule at all, so TTL is not a fifth thing you pick <i>instead of</i> LRU. Be honest about the cost of "
 "this seam: <code>EvictionPolicy</code> has four methods, not one, because a rule that ranks keys has to see every "
 "event that changes the ranking.",
 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two threads put into a full cache at the same instant. Thread A asks the policy who should go; thread B is in the "
 "middle of inserting and the policy has not been told yet, so A evicts using a ranking that is already stale. Worse: "
 "if a removal drops a key from the table but not from the policy, the policy will later name a key that is not there, "
 "the cache removes nothing, and the size bound quietly fails &mdash; the cache grows forever and looks fine. So the "
 "table and the policy are one piece of state with one owner and <i>one</i> lock covering the whole operation, not one "
 "lock each. This is the line to say out loud: a <code>ConcurrentHashMap</code> with an unsynchronised policy bolted "
 "beside it is fast and wrong, because no lock-free scheme keeps a hash table and a linked list agreeing across a "
 "four-step eviction. Anything that is not part of that agreement goes outside: the loader, and every listener.",
 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Where is the value for key K?\" is a hash map from key to entry. The next two questions are answered by an index "
 "that lives inside a policy and not in the cache: a doubly-linked list of keys plus a key-to-node map for recency, "
 "and a use-count-to-bucket map plus the smallest non-empty count for frequency. Both are O(1), and both are taken "
 "apart pointer by pointer on " + LRU_PAGE + "; here each is a detail inside one class. What belongs to this page is "
 "the row after them: \"who arrived first?\" is the "
 "<i>same</i> list as LRU with the read hook doing nothing &mdash; one empty method is the entire difference between "
 "LRU and FIFO, which is the clearest evidence that the rule and not the cache is what changes. \"Whose deadline is "
 "soonest?\" is a <code>TreeSet</code> of (deadline, sequence, key), and that one is O(log n), not O(1). Say it: log n "
 "is about seventeen comparisons at a million entries, dwarfed by the hash lookup, and a timing wheel would be O(1) "
 "with bucket-granularity error and far more code. A design that claims O(1) everywhere without noticing this is a "
 "design that has not read its own data structures.",
 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An entry is ABSENT, then LIVE, and it leaves in one of two ways that are genuinely different: EXPIRED, which the "
 "clock decides and which can hit an entry in a cache that is two per cent full, and EVICTED, which the policy decides "
 "and which can hit an entry written a second ago. That is why the listener is told a cause. Writing the life down "
 "forces the order inside <code>put</code>, and the order is the design. Work out the deadline before the lock is "
 "taken. Take the lock. A key already in the table is a rewrite, which never grows the count and therefore never "
 "evicts. Otherwise, while the cache is full, ask the policy for a victim and drop it from the table <i>and</i> the "
 "policy. Only then write the new entry and tell the policy about it. Unlock, and only then hand the departures to the "
 "listeners. The one step people get wrong is the order of those last two: evict <i>before</i> admitting. Under LRU "
 "both orders look identical, which is exactly why the bug survives. Under LFU the newcomer arrives at one use, is "
 "instantly the coldest key in the cache, and an insert-then-evict cache has it evict itself &mdash; the put silently "
 "does nothing, and you never find out until the second policy is plugged in.",
 6),
("Move 7: yes, every get takes the lock. Ask for how long, and what is inside it.",
 "Inside the lock there is one hash lookup and the policy's bookkeeping: six pointer writes for LRU, two set "
 "operations for LFU, one <code>TreeSet</code> insert for the deadline-ordered rule. Add an uncontended lock and "
 "unlock, about twenty nanoseconds, and the whole critical section is around a hundred nanoseconds &mdash; with no "
 "allocation and nothing that can throw. Everything slow is outside: the deadline arithmetic happens before the lock "
 "is taken, the loader on a miss is one to five milliseconds of database, and the removal listener is caller code that "
 "might write to a socket. Ten threads calling get at the same instant means the tenth waits about nine hundred "
 "nanoseconds, which nobody can measure. But be honest: this is the one design on this shelf where a single lock "
 "genuinely can saturate, so \"does one lock scale\" deserves arithmetic rather than reassurance. Move 8 does it.",
 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A permissions cache doing a hundred thousand gets a second holds the lock for ten milliseconds in every second: one "
 "per cent busy, and no queue ever forms. The same cache at a million a second is ten per cent busy, which is fine but "
 "visible in a profiler. At ten million a second &mdash; a hot in-process cache in front of a database in a big "
 "service &mdash; one lock <i>is</i> the bottleneck, and the deadline-ordered policy, at about a microsecond an "
 "operation, saturates ten times sooner than the others. Then the ladder, in the order you would climb it. First, keep "
 "everything slow outside the lock, which this code already does. Second, stripe: sixteen independent caches behind "
 "one <code>Cache</code>, chosen by a spread hash of the key, for roughly sixteen times the throughput &mdash; the "
 "price is that the bound and the recency order are now per stripe, so eviction becomes approximate across the whole "
 "cache. Third, stop touching the policy on every read: append the key to a ring buffer and replay the buffer under "
 "<code>tryLock</code>, so a hit is a map lookup and an array write; that is what Caffeine actually ships. Fourth, "
 "leave the process: Redis, which keeps no perfect LRU list at all and samples instead. Say the arithmetic first &mdash; "
 "climbing this ladder at a hundred thousand gets a second is complexity nobody asked for.",
 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Inserting before evicting (invisible under LRU, and under LFU the newcomer evicts itself). A removal that drops a "
 "key from the table but not from the policy (the policy then names a ghost, nothing is evicted, and the bound fails "
 "silently). An expired entry handed back because only a sweeper ever checked the deadline, so the read path must "
 "check it too and drop it there &mdash; and that test is written against an injected clock, because "
 "<code>Thread.sleep(1100)</code> is slow, flaky, and cannot test a twenty-four-hour TTL at all. A listener "
 "that throws, does I/O, or calls straight back into the cache (all three are safe only because listeners run after "
 "the unlock). A listener told only the key, so nobody can tell a capacity bug from an expiry bug &mdash; and a "
 "write-back store hung on that same hook would then flush the wrong things. And swapping the "
 "policy at runtime throwing away the entries, when it should only throw away the ranking. Each of these is a few "
 "lines in FailureTests.java: ten numbered blocks, forty checks, and it must print ALL PASS.",
 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Strategy is move 3, and on this problem it is the whole point rather than a flourish: the rule is not a flag on the "
 "cache, it is an object the cache is handed, so \"now make it LFU\" is a new file and one builder line. Decorator is "
 "the same move twice over &mdash; <code>ExpiryFirst</code> wraps a policy and adds \"the dead go first\" to any rule "
 "at all, and <code>LoadingCache</code>, <code>StripedCache</code> and the byte-bounded cache all wrap a "
 "<code>Cache</code> rather than editing one. Observer is move 4's rule that caller code must not run inside the lock. "
 "State is move 6: an entry's life written down, which is what makes the cause on the callback four values instead of "
 "a boolean. Builder earns its place here for the same reason it does in Guava and Caffeine &mdash; capacity, policy, "
 "clock, TTL and listeners are six optional knobs, and a six-argument constructor full of nulls is worse than a chain "
 "of named calls. Template Method did not earn one: the cache calls four policy methods but owns none of their bodies, "
 "and Strategy already did that job. Singleton earned nothing: a cache is handed to its callers, so every test builds "
 "a fresh one. Factory is \"not yet\": the builder's single default is the entire registry today, and it grows a name "
 "the day policies arrive as strings from configuration.",
 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "S: a class has one reason to change, which move 2 gave you &mdash; the cache stores and bounds, a policy ranks, "
 "<code>CacheStats</code> counts, a listener notifies, and nobody does two of those. O: a new behaviour is a new class "
 "and one changed line; <code>SegmentedLruPolicy</code> exists and <code>PolicyCache</code> was never opened to add "
 "it. L: any implementation drops in and nothing asks which one it got, and the interesting case is the approximate "
 "one &mdash; sampled LRU is substitutable because the contract is \"name a victim\", not \"name the mathematically "
 "coldest key\". I: <code>Clock</code>, <code>RemovalListener</code>, <code>CacheLoader</code> and "
 "<code>Weigher</code> have one method each, so a fake is a lambda; <code>EvictionPolicy</code> has four, and it "
 "carries a deadline that LRU and LFU throw away, which is the one honest blemish on this design &mdash; cheaper than "
 "splitting the interface, and worth naming before the interviewer does. D: the cache depends on interfaces it is "
 "handed, which is exactly why a test can give it a clock that says last Tuesday and a listener that throws.",
 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (LFU, FIFO, segmented, sampled, TinyLFU) is a new class behind <code>EvictionPolicy</code> plus one "
 "builder line. Someone new who wants to know (a metric, a write-back store that flushes on evict) is one more "
 "listener; the table and the lock do not move. A new step in an entry's life (loading, refreshing, invalidated) is "
 "one more cause and one more checked transition. A new invariant across entries (a budget in bytes rather than a "
 "count) is the check <i>and</i> the evictions inside the same lock, all or nothing, with the single <code>if</code> "
 "becoming a loop because one heavy value can push out several small ones. And state that must outlive "
 "the process (Redis in front of the database, or simply a second server) is the far store becoming the loader, and "
 "every write publishing an invalidation rather than a value, so two nodes can never disagree about which value is "
 "newest &mdash; they both go and read it again. For all five, <code>PolicyCache</code>, <code>KeyList</code> and the "
 "failure tests do not change; that is the test that the derivation was right. Page 05 has the code and the traps "
 "for each.",
 12),
]

DERIVATION_LEAD = ("Run these on any LLD and the class diagram, the lock, the tests, the patterns, SOLID and the answer "
 "to every twist fall out in that order; nothing is chosen up front, and nothing is named before the move that produced "
 "it. On this problem move 3 is the one that is load-bearing, because the interviewer is going to change the eviction "
 "rule while you are typing and the whole grade is whether that costs you a new file or a rewrite. The internals of a "
 "single LRU or LFU cache &mdash; the sentinels, the relinking, the frequency buckets &mdash; are derived on " + LRU_PAGE +
 "; this page is about the seam they hang from.")

# ============================================================ page 03: the class diagram
uml_reset()
# column A: the things that are handed in, and the value types
put("clock", 10, 20, 240, "Clock", [], ["nowMs(): long"], "interface")
put("sysclock", 10, 94, 240, "SystemClock", [], ["nowMs() &rarr; the wall clock"])
put("manclock", 10, 168, 240, "ManualClock", ["now: long"], ["advance(ms) / setTo(ms)"])
put("listener", 10, 262, 240, "RemovalListener", [], ["onRemoval(key, value, cause)"], "interface")
put("cause", 10, 336, 240, "RemovalCause", ["EXPLICIT, REPLACED,", "EXPIRED, CAPACITY"], [], "enum")
put("stats", 10, 422, 240, "CacheStats", ["hits / misses: long", "evictions / expirations: long"], ["hitRate(): double"])
put("loaderif", 10, 532, 240, "CacheLoader", [], ["load(key): V  (no lock held)"], "interface")
put("weigher", 10, 606, 240, "Weigher", [], ["weigh(key, value): int"], "interface")
# column B: the contract, the cache, the builder, and the other implementations
put("cacheif", 290, 20, 350, "Cache", [], ["getIfPresent(key): V", "put(key, value [, ttlMs])", "remove(key): V",
                                           "size() / capacity(): int", "cleanUp()", "stats(): CacheStats"], "interface")
put("cache", 290, 180, 350, "PolicyCache",
    ["capacity: int", "table: LinkedHashMap&lt;K, CacheEntry&gt;", "policy: EvictionPolicy&lt;K&gt;",
     "lock: ReentrantLock", "clock: Clock", "listeners: List&lt;RemovalListener&gt;",
     "hits / misses / evictions: AtomicLong"],
    ["getIfPresent(k) / put(k, v, ttl) / remove(k)", "setPolicy(p): swap while running",
     "setClock(c) / cleanUp() / stats()", "consistent(): table and policy agree", "fire(pending) -- after the unlock"])
put("builder", 290, 440, 350, "CacheBuilder", ["capacity / policy / clock", "ttlMs / listeners"],
    ["capacity(n).policy(p).clock(c)", "ttlMs(ms).listener(l)", "build(): PolicyCache"])
put("striped", 290, 600, 350, "StripedCache", ["segments: List&lt;PolicyCache&gt;"],
    ["segmentFor(key): spread hash", "sixteen locks instead of one"])
put("loading", 290, 716, 350, "LoadingCache", ["inner: Cache&lt;K, V&gt;", "inFlight: Map&lt;K, Future&lt;V&gt;&gt;"],
    ["get(key): loads on a miss", "putIfAbsent elects ONE loader"])
put("bytes", 290, 848, 350, "ByteBoundedCache", ["maxWeight / totalWeight: long", "weigher: Weigher&lt;K, V&gt;"],
    ["put: a LOOP of evictions", "refuses one value over budget"])
# column C: the entry and the shapes the policies are built on
put("entry", 680, 20, 240, "CacheEntry", ["value: V", "writtenAtMs / lastAccessMs", "expiresAtMs: long"],
    ["expired(nowMs): boolean"])
put("keylist", 680, 146, 240, "KeyList", ["head, tail: sentinels", "index: Map&lt;K, Node&gt;"],
    ["touchFirst(key) / remove(key)", "last(): the next victim", "oldestFirst(): List&lt;K&gt;"])
put("fuse", 680, 288, 240, "Fuse", ["deadlineMs: long", "seq: long", "key: K"], [])
put("dlindex", 680, 390, 240, "DeadlineIndex", ["fuses: TreeSet&lt;Fuse&gt;", "byKey: Map&lt;K, Fuse&gt;"],
    ["put(key, deadlineMs)", "earliest(): K", "earliestIfDue(now): K"])
put("expfirst", 680, 532, 240, "ExpiryFirst", ["inner: EvictionPolicy&lt;K&gt;", "deadlines: DeadlineIndex&lt;K&gt;"],
    ["a corpse first, then", "inner.selectVictim(now)"])
put("removal", 680, 690, 240, "Removal", ["key: K,  value: V", "cause: RemovalCause"], [], "record")
# column D: the seam and its implementations
put("policy", 965, 20, 250, "EvictionPolicy", [], ["onPut(k, now, expiresAt)", "onGet(k, now)", "onRemove(k)",
                                                   "selectVictim(now): K", "trackedKeys(): int"], "interface")
put("lru", 965, 158, 250, "LruPolicy", ["order: KeyList&lt;K&gt;"], ["onGet &rarr; touchFirst(key)", "victim = order.last()"])
put("fifo", 965, 268, 250, "FifoPolicy", ["arrival: KeyList&lt;K&gt;"], ["onGet &rarr; { }  -- the whole diff", "victim = arrival.last()"])
put("lfu", 965, 378, 250, "LfuPolicy", ["useCount: Map&lt;K, Integer&gt;", "buckets: count &rarr; LinkedHashSet", "minCount: int"],
    ["onGet &rarr; bump(key)", "victim = coldest bucket"])
put("ttlp", 965, 520, 250, "TtlPolicy", ["deadlines: DeadlineIndex&lt;K&gt;"], ["victim = earliest()", "O(log n), and says so"])
put("sampled", 965, 630, 250, "SampledLruPolicy", ["keys: dense array + slots"], ["coldest of five at random", "Redis's trade"])
put("segmented", 965, 740, 250, "SegmentedLruPolicy", ["probation / protected"], ["a second read promotes", "scans die in probation"])

def hstub(x1, x2, y):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y, x2, y)

EDGES = [
 # the cache implements the contract, and so do the three wrappers, on one bus down the left
 ln(B["cache"]["t"], B["cacheif"]["b"], "inherit"),
 ln(B["bytes"]["l"], B["cacheif"]["l"], "inherit", "", [(276, 901), (276, 87)]),
 hstub(290, 276, 645), hstub(290, 276, 769),
 # the five rules implement the policy interface, on one bus round the right edge
 ln(B["segmented"]["r"], B["policy"]["r"], "inherit", "", [(1224, 785), (1224, 79)]),
 hstub(1215, 1224, 203), hstub(1215, 1224, 313), hstub(1215, 1224, 439), hstub(1215, 1224, 565), hstub(1215, 1224, 675),
 # the decorator is a policy too, and it wraps one
 ln(B["expfirst"]["r"], B["policy"]["l"], "inherit", "", [(932, 585), (932, 79)]),
 # the rule, the clock and the listener are handed to the cache
 ln((640, 410), B["policy"]["t"], "inject", "", [(652, 410), (652, 8), (1090, 8)]),
 ln(B["cache"]["l"], B["clock"]["r"], "inject", "", [(268, 297), (268, 47)]),
 ln((290, 337), B["listener"]["r"], "notify", "", [(262, 337), (262, 289)]),
 ln(B["listener"]["b"], B["cause"]["t"], "assoc", "the cause"),
 # what the cache owns, and what the policies are built on
 ln((640, 200), B["entry"]["l"], "compose", "", [(666, 200), (666, 73)]),
 ln(B["lru"]["l"], B["keylist"]["r"], "compose", ""),
 ln(B["fifo"]["l"], (920, 240), "compose", "", [(946, 313), (946, 240)]),
 ln(B["expfirst"]["t"], B["dlindex"]["b"], "compose", "one index"),
 ln(B["dlindex"]["t"], B["fuse"]["b"], "compose", ""),
 # the builder assembles, and the wrappers hold what they wrap
 ln(B["cache"]["r"], B["removal"]["l"], "assoc", "", [(666, 297), (666, 723)]),
 ln(B["builder"]["t"], B["cache"]["b"], "assoc", "build()"),
 ln(B["striped"]["r"], (640, 400), "compose", "", [(660, 645), (660, 400)]),
 ln(B["loading"]["l"], B["loaderif"]["r"], "inject", "", [(258, 769), (258, 559)]),
 ln(B["bytes"]["l"], B["weigher"]["r"], "inject", "", [(252, 875), (252, 633)]),
]
def extmark(x, y, w):
    """a small 'ext' tag in a box's top-right corner: this class lives in Extensions.java, not Main.java"""
    return _tx(x + w - 7, y + 13, "ext", "var(--acc2)", 9.5, "end")

# notes and tags that must sit ON TOP of the boxes, so they are appended after the parts
NOTES = ("".join([_tx(1090, 152, "handed in, never built here", "var(--acc)", 10.5),
                  _tx(1090, 621, "TtlPolicy owns one of these too", "var(--muted)", 10),
                  _tx(800, 654, "ExpiryFirst IS a policy, and WRAPS one", "var(--acc)", 10.5),
                  _tx(800, 776, "filled inside the lock, emptied after it", "var(--muted)", 10),
                  _tx(1000, 994, "ext = in Extensions.java", "var(--acc2)", 11, "start")]
                 + [extmark(x, y, w) for (x, y, w) in [(10, 532, 240), (10, 606, 240), (290, 600, 350),
                                                       (290, 716, 350), (290, 848, 350),
                                                       (965, 630, 250), (965, 740, 250)]]))
UMLSVG = uml_svg(1230, 1020, EDGES, legend_y=990).replace("</svg>", NOTES + "</svg>")

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements &mdash; note the two buses, one down the left where three wrappers implement <code>Cache</code>, and one '
 'round the right where five rules implement <code>EvictionPolicy</code>. Filled diamond = owns: the cache owns every '
 'entry, and each rule owns whatever index it ranks with. Plain arrow = references. Dashed green = handed in. '
 'Dotted blue = notifies. <b>Where state lives:</b> the cache has the table, the lock, the clock, the listeners and '
 'the counters, and it is the only object that removes an entry; a policy has an index of keys and no values at all, '
 'which is why one lock covers both and why a policy needs no synchronisation of its own. Notice the two things that '
 'are <i>not</i> here. There is no LruCache and no LfuCache class &mdash; there is one cache and five rules, which is '
 'the whole difference between this page and ' + LRU_PAGE + '. And there is no TtlCache: expiry lives on '
 '<code>CacheEntry</code> and is checked by the cache on every read, while <code>ExpiryFirst</code> is a rule that '
 'wraps another rule, which is why the same wrapper works over LRU, LFU and FIFO alike. <code>Removal</code>, the '
 'small record on the right, is what makes the listener safe: the cache fills a list of them <i>inside</i> the lock '
 'and empties it after, so a listener may be slow, may throw, or may call back in. Boxes tagged <code>ext</code> live '
 'in Extensions.java rather than Main.java; they are drawn because they are the proof that the two seams hold &mdash; '
 'each one is a new file and nothing else moved. Extensions.java holds a few more that are not drawn, for the same '
 'reason: the loader, the write-through wrapper, the invalidation bus.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does and what it guarantees; read only those first for the shape, then the bodies. Main.java '
 'is the whole system and its <code>main</code> runs one access trace through four rules, then the decorator, then a '
 'runtime policy swap, then a fifty-thread race. Each copy button copies that whole file for your IDE. Below it: '
 'Extensions.java (every follow-up\'s reference code, with an <code>ExtDemo</code> main that runs all of it) and '
 'FailureTests.java (ten claims, forty checks; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; '
 'java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (entries or bytes, and whether TTL is a rule or a validity '
 'check, come first); then type in the order of Main.java: the RemovalCause enum, Clock with its two implementations, '
 'RemovalListener and CacheEntry, the Cache interface, then the EvictionPolicy interface &mdash; write that one before any '
 'rule, because it is the decision being graded &mdash; then KeyList, then LruPolicy and FifoPolicy off the same list, then '
 'LfuPolicy, then PolicyCache with its lock and the order inside put, then the builder, then a main that pushes one trace '
 'through two rules and prints two different victims. TtlPolicy, ExpiryFirst and the DeadlineIndex are the second pass, or '
 'the moment they say "and some entries have a TTL".</div></div>')

FU = [
("Now make it least-frequently-used. How much of your code changes?", "functional", 5,
 "One new class and one builder line; <code>PolicyCache</code> is never opened. The class keeps a use count per key and "
 "a bucket of keys per count, remembers the smallest non-empty count, and hands back the first key of that bucket, so an "
 "eviction is a lookup and never a scan for a minimum; the bucket bookkeeping is taken apart line by line on " + LRU_PAGE +
 ". What to say out loud here is the seam rather than the buckets. The same access trace through <code>FifoPolicy</code>, "
 "<code>LruPolicy</code>, <code>LfuPolicy</code> and <code>TtlPolicy</code> gives up A, B, C and D &mdash; four rules, "
 "four victims, identical calls &mdash; and <code>Main</code> prints exactly that. Test 1 asserts that all four answers "
 "differ, which is the only way to prove the rule is really pluggable and not decoration.",
 sect(src, "final class LfuPolicy", "final class TtlPolicy")),
("I want a TTL, but on top of whatever policy I already chose, not instead of it.", "twist", 10,
 "That is a Decorator over the policy, not a fifth policy. ExpiryFirst wraps any rule and keeps its own index of "
 "deadlines; when it is asked for a victim it hands back a key that is already dead if there is one, and otherwise "
 "delegates to the wrapped rule, so ExpiryFirst(LRU), ExpiryFirst(LFU) and ExpiryFirst(FIFO) all exist and behave "
 "exactly like the rule they wrap while everything is alive. Entries with no deadline are not indexed at all, so "
 "wrapping a cache that uses no TTLs costs nothing. Keep this separate from expiry itself: expiry is the question \"may "
 "I return this?\", it is never optional, and it lives in the cache on the read path.",
 sect(src, "final class ExpiryFirst", "final class PolicyCache")),
("Swap the eviction policy while the cache is serving traffic.", "twist", 10,
 "Under the same lock, every live key is handed to the new policy as a fresh insert, then the field is swapped. No entry "
 "is lost and no reader ever sees a cache without a rule. What does not survive is the ranking: the new policy starts "
 "with no history, so recency counts and use counts are gone and the first eviction after a swap follows the order the "
 "keys were re-indexed in. That is why the table is a LinkedHashMap &mdash; not to make it an LRU cache, but so the "
 "re-index order is deterministic and the behaviour is testable. Say the trade out loud rather than pretending the "
 "history carries across; the test asserts exactly this.",
 sect(src, "EvictionPolicy<K> setPolicy", "EvictionPolicy<K> policy() {")),
("Under LRU I cannot see any difference between evicting first and inserting first. Why is the order a decision?",
 "design", 5,
 "Under LRU there is no difference, which is exactly why this bug ships. Under LFU there is: a newcomer arrives at a use "
 "count of one, which makes it the coldest key in the cache the instant it is written, so an insert-then-evict cache "
 "picks the key it has just inserted and takes it straight back out. The put silently does nothing, the cache never "
 "fills, and nobody finds out until the second policy is plugged in. So the order is: evict while the table is at "
 "capacity, and only then write &mdash; which also means the count never goes one over the bound, not even for an "
 "instant in the middle of a put. It is a <code>while</code> and not an <code>if</code> for two reasons: one heavy value "
 "in a byte-bounded cache has to push out several small ones, and a policy that names a key the table never had has that "
 "key dropped from the policy as well and the loop tries again, so drift can never wedge a put. Test 2 is the proof "
 "under LFU: three keys, two of them read twice, a fourth put in, and d is resident while c is gone.",
 sect(src, "public void put(K key, V value, long ttlMs)", "public V remove(K key)")
 + "\n" + T("        // 2. evict BEFORE admitting", "        // 3. fifty threads")),
("Fifty threads put into a full cache at the same instant. Prove the bound holds, with a test.", "non-functional", 10,
 "The race lives in the gap between asking the policy who should go and actually removing that key. The sequence in the "
 "card above &mdash; the rewrite check, the eviction loop, the write and the policy update &mdash; runs inside one lock, "
 "so no other writer can ever be in that gap. The proof is two assertions rather than a count: fifty threads wait on one latch, "
 "run twenty thousand mixed operations against a cache of a hundred, and the test checks the size was never observed "
 "above the capacity and that afterwards the policy is tracking exactly as many keys as the table holds. That second "
 "check is the one that catches the real bug, because a policy that leaks keys still looks fine from outside until the "
 "day it names a key that is not there and nothing gets evicted at all.",
 T("        // 3. fifty threads", "        // 4. a twenty-four-hour")),
("One lock over the table AND the policy. Have you just serialised the cache?", "non-functional", 8,
 "For a while, yes, and this is the one design here where the honest answer is arithmetic rather than reassurance. The "
 "critical section is a hash lookup plus the policy's bookkeeping, about a hundred nanoseconds. A permissions cache at a "
 "hundred thousand gets a second spends one per cent of each second inside it; at a million a second it is ten per cent; "
 "at ten million a second one lock is the bottleneck, and the deadline-ordered policy at about a microsecond an "
 "operation gets there ten times sooner. A read-write lock buys nothing, because a read mutates the ranking. The ladder: "
 "keep the loader and the listener outside the lock, which this code already does; stripe into sixteen segments by "
 "spread hash for roughly sixteen times the throughput, at the price of a per-stripe bound and an approximate order; "
 "then buffer read events in a ring and replay them under tryLock, which is what Caffeine ships; then leave the process.",
 X("striping", "two servers")),
("Somebody's removal listener throws. Another one calls straight back into the cache.", "non-functional", 5,
 "Neither can hurt the cache, because no listener runs while the lock is held. Departures are collected into a small "
 "local list inside the critical section and delivered after the unlock, each call wrapped in its own try/catch, so a "
 "listener that throws does not stop the put that caused it and does not stop the next listener either. A listener that "
 "calls back into the cache simply takes the lock again on its own, with no risk of mutating the table midway through "
 "an eviction. The same rule is why a listener may do I/O: closing a pooled connection on evict is the normal use of "
 "this hook, and it would freeze every other thread from inside the lock.",
 tail("    // A listener is caller code", "/**\n * The one place the pieces are assembled")),
("A user asks why their session disappeared. What can you tell them?", "functional", 5,
 "Exactly which of four things happened, because every removal carries a cause. EXPLICIT means somebody called remove. "
 "REPLACED means a new value was written over the same key, and the listener gets the old value, which is what a "
 "write-back store needs. EXPIRED means the clock passed the deadline, and that can happen in a cache that is two per "
 "cent full. CAPACITY means the cache was full and the policy chose this key, which can happen to an entry written a "
 "second ago. Those are four different bugs: a flood of CAPACITY says the cache is too small, a flood of EXPIRED says "
 "the TTL is too short, and a listener told only the key cannot tell them apart.",
 T("        // 5. \"why did my session", "        // 6. TTL as a DECORATOR")),
("Reads come out of the cache. Do writes go through it to the database?", "twist", 8,
 "Two answers, and <code>PolicyCache</code> changes in neither. Write-through is a wrapper that writes the store first "
 "and the cache second, so a store that throws never leaves behind a cached value nobody persisted &mdash; the same "
 "ordering rule as move 6 &mdash; and the price is that every put pays the database's millisecond on the caller's "
 "thread. Write-back is a <code>RemovalListener</code> and nothing else: no new field, no new lock, and the <i>cause</i> "
 "is the whole logic. CAPACITY and EXPIRED carry the newest value out of memory, so not writing it loses the write; "
 "REPLACED hands back a value that a newer one has already superseded, so writing it is pure waste; EXPLICIT is the "
 "caller saying forget this. Name the cost before they do: the flush runs after the unlock, so a crash in that window "
 "loses the write, which is why real write-back caches also flush everything still dirty on a timer. On the read side "
 "<code>LoadingCache</code> in Extensions.java loads on a miss and elects one loader per key, so six threads missing the "
 "same key do not become six queries; that stampede is derived in full on " + TTL_PAGE + ".",
 X("writes", "striping")),
("Capacity in bytes, not entries. A 2 MB value and a 2 KB value are not the same thing.", "twist", 8,
 "A one-method Weigher is handed in, the cache tracks a running total, and the single \"is it full?\" check becomes a "
 "loop, because one heavy value can push out several small ones. The policies are untouched: weight is a bound, not a "
 "ranking, and nothing about who-goes-next changes. The trap worth naming is the entry heavier than the whole budget: "
 "without an explicit refusal the loop evicts everything, still does not fit, and the cache ends up empty and useless. "
 "In production the weigher is where the bugs live, because measuring a Java object's real size is guesswork and an "
 "under-count means the budget quietly does not hold.",
 X("capacity in bytes", "read-through")),
("A nightly report scans every row and wrecks your hit rate. And Redis keeps no linked list at all, it samples.",
 "twist", 8,
 "Both answers are the same shape, which is the whole point: a new policy class, and nothing in the cache moves. Scan "
 "resistance is <code>SegmentedLruPolicy</code> &mdash; a probation list and a protected list, a second read promotes a "
 "key into protected, and victims come from probation first, so a one-pass scan walks in and straight back out. The "
 "demo replays the identical trace through both rules: plain LRU loses all eight hot keys to a two-hundred-key scan, "
 "segmented LRU keeps all eight. Sampling is the other class, <code>SampledLruPolicy</code>: a dense array of keys and "
 "a tick per key, look at five at random and evict the coldest you saw, with removal swapping the last key into the "
 "hole so it stays O(1). It is deliberately wrong some of the time &mdash; Redis's trade &mdash; and how often is "
 "worked out on " + LRU_PAGE + ". TinyLFU puts an admission filter in front of the same idea, a count-min sketch that "
 "refuses one-hit wonders; that is what Caffeine ships, and naming it is the senior answer here.",
 X("scan resistance", "capacity in bytes")),
("Now there are two servers, and a write on one must not leave a stale copy on the other.", "twist", 5,
 "Publish invalidations, not values. A write updates the local copy and tells every other node to drop that key, so the "
 "next read there reloads it; two nodes can then never disagree about which value is newest, because at most one of "
 "them has a value at all. A cache fill after a read publishes nothing &mdash; nobody else's copy became wrong &mdash; "
 "and a node that broadcasts every time it warms itself turns a cache into a message storm. Which node owns which key "
 "is consistent hashing, so adding a node moves one Nth of the keys rather than all of them; name it and leave it out "
 "of scope. In production this deserves a fifth cause, INVALIDATED, because today the drop is reported as EXPLICIT.",
 X("two servers", "Runs every extension")),
("Where does time come from, and how do you test a twenty-four-hour TTL?", "design", 3,
 "The cache is handed a Clock and nothing in it ever reads the wall directly. A test hands in a clock it drives by "
 "hand: write an entry with a day-long TTL, advance twenty-three hours and it still reads; advance two more and the "
 "read is a miss, the entry is dropped by the read that found it, and the listener is told EXPIRED. That test takes a "
 "microsecond and cannot flake. The alternative &mdash; Thread.sleep(1100) &mdash; is slow, flaky, and cannot test a "
 "day-long TTL at all, which is why the injected clock is worth the one interface.",
 T("        // 4. a twenty-four-hour", "        // 5. \"why did my session")),
("Which pattern is where, which SOLID letter is where, and where would a Factory earn its place?", "design", 8,
 "None was chosen up front; each is what a move produced. Strategy is move 3 and it is the point of the problem: the "
 "rule is an object handed in, so LFU is a new file. Decorator is the same move twice &mdash; ExpiryFirst wraps a "
 "policy, and LoadingCache, StripedCache, WriteThroughCache and the byte-bounded cache wrap a Cache. Observer is move 4's rule that "
 "caller code never runs inside the lock. State is move 6, the entry's life, which is why the cause has four values. "
 "Builder earns its place because six of seven knobs are optional, exactly as in Guava and Caffeine. For SOLID: S is "
 "move 2 (the cache stores, a policy ranks, stats count); O is SegmentedLruPolicy, a new file with PolicyCache "
 "untouched; L is that sampled LRU substitutes even though it is approximate, because the contract is \"name a "
 "victim\"; I is a row of one-method interfaces &mdash; clock, listener, loader, weigher, store &mdash; with EvictionPolicy's four methods named as the honest blemish; D is the "
 "constructor taking a policy and a clock. Factory earns its name the day policies arrive as strings from "
 "configuration &mdash; the builder's single default is already the registry. Template Method did not earn a place at "
 "all: Strategy did that job first.",
 "// Strategy: the rule is an OBJECT the cache is handed, never a flag and never an if-chain\n"
 "interface EvictionPolicy<K> { void onPut(K k, long now, long exp); void onGet(K k, long now);\n"
 "                              void onRemove(K k); K selectVictim(long now); int trackedKeys(); }\n"
 "CacheBuilder.<String,String>newBuilder().capacity(4).policy(new LfuPolicy<>()).build();\n\n"
 "// Decorator, twice: one wraps a POLICY (adds \"the dead go first\"), one wraps a CACHE (adds loading)\n"
 "new ExpiryFirst<>(new LruPolicy<>());                  // works over LRU, LFU, FIFO, anything\n"
 "new LoadingCache<>(new StripedCache<>(16, 1600, LruPolicy::new, clock), loader, true);\n\n"
 "// Observer: the cache announces a departure and does not know what a metrics counter is\n"
 "interface RemovalListener<K, V> { void onRemoval(K key, V value, RemovalCause cause); }\n"
 "for (Removal<K, V> r : pending) for (RemovalListener<K, V> l : listeners)\n"
 "    try { l.onRemoval(r.key(), r.value(), r.cause()); } catch (RuntimeException ignored) { }\n\n"
 "// State: four ways out, four causes -- a boolean here would hide two different bugs\n"
 "enum RemovalCause { EXPLICIT, REPLACED, EXPIRED, CAPACITY }\n\n"
 "// Factory: not yet. The builder's one default IS the registry; config strings would earn the name\n"
 "Map<String, Supplier<EvictionPolicy<String>>> byName =\n"
 "    Map.of(\"lru\", LruPolicy::new, \"lfu\", LfuPolicy::new, \"fifo\", FifoPolicy::new);\n"),
]

build(dict(
    slug="cache-eviction", title="Cache with Eviction Policies",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 10 failure tests and a 50-thread race pass",
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
