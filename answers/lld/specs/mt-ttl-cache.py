# TTL Cache (thread-safe) LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
# The angle of this page is TIME and CONTENTION: expiry that is never observable, a sweeper that never removes a
# live entry, and a loader that runs once per key under a stampede. LRU/LFU internals live on lru-workbench.html
# and the eviction seam lives on cache-eviction-workbench.html; neither is repeated here.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H / "mt-ttl-cache/Main.java").read_text()
ext   = (H / "mt-ttl-cache/Extensions.java").read_text()
tests = (H / "mt-ttl-cache/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m + 200])
    j = next(m for m in marks if m > i and b in ext[m:m + 200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def nobrace(s):
    """drop a trailing class-closing brace picked up by a slice that runs to the end of a file"""
    lines = s.rstrip().split("\n")
    while lines and lines[-1].strip() == "}" and not lines[-1].startswith(" "): lines.pop()
    return "\n".join(lines).rstrip() + "\n"

RED = "#ff6b6b"
LRU_PAGE   = '<a href="lru-workbench.html">the LRU page</a>'
EVICT_PAGE = '<a href="cache-eviction-workbench.html">the cache-eviction page</a>' 

# ============================================================ page 01: the problem
# what the code must do: the read, the read-or-load, and the two background lines
pf = _D
rows = [("write", 20, [("put(key, value)", "the caller never passes a TTL"),
                       ("ask the rule how long", "ttl.ttlMsFor(key)"),
                       ("stamp an absolute deadline", "now + ttl, onto the entry"),
                       ("map.put, then announce", "the replaced value, after the write")]),
        ("read", 120, [("get(key)", "one hash, no lock at all"),
                       ("compare with the clock", "the entry knows its own deadline"),
                       ("live: hand back the value", "a hit"),
                       ("dead: reclaim it, say miss", "map.remove(key, THIS entry)")]),
        ("read or load", 220, [("getOrLoad(key, loader)", "only after a miss"),
                               ("claim the key", "putIfAbsent(key, future)"),
                               ("the winner calls the loader", "20 ms, with nothing held"),
                               ("store it, then wake the rest", "the losers read what was stored")])]
for lab, y, boxes in rows:
    pf += _tx(100, y + 31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k * 260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x + 240, y + 27, x + 260), True)
pf += _ar("M815 274 V287", dash=True) + _bx(580, 287, 470, 40, "the loader threw: nothing stored, the claim freed", "", dash=True)
pf += _tx(100, 352, "remove", "var(--acc)", 13) + _tx(175, 352, "invalidate(key) drops it now and the listener hears EXPLICIT;  a TTL of zero means do not cache at all", "var(--text)", 12, "start")
pf += _tx(100, 378, "sweep", "var(--acc)", 13) + _tx(175, 378, "once a second a daemon thread walks what is left and removes only the entries whose deadline has passed", "var(--text)", 12, "start")
pf += _tx(100, 404, "ask", "var(--acc)", 13) + _tx(175, 404, "at any instant, without a lock: is this key here?  how many entries are held?  what is the hit rate?", "var(--text)", 12, "start")
pf += _tx(615, 436, "fifty threads at the same instant: no value is ever served after its deadline, and one cold key costs one call to the loader, not fifty", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 450, pf)

# one minute, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("10:00:00.000  cold start", ["40 threads ask for user:42 at once", "one wins the claim, 39 wait on it",
                                    "1 database call, not 40", "deadline set to 10:01:00.000"], True),
      ("10:00:31.240  a refresh", ["a writer refreshes user:42", "its deadline moves to 10:01:31",
                                   "the sweeper holds the OLD entry", "remove(key, old) deletes nothing"], False),
      ("10:01:31.000  the deadline", ["a reader compares it with the clock", "dead: reclaimed on that very read",
                                      "the caller is told miss"], False),
      ("10:01:31.002  and again", ["2,000 reads a second, all missing", "one claim, one load, 39 riders",
                                   "1,440 loads that day, not 57,600"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k * 290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x + 125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x + 125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li><code>put(key, value)</code> stores a value with a time to live; <code>get(key)</code> reads it back.</li>
<li><code>getOrLoad(key, loader)</code> fetches the value on a miss and stores it.</li>
<li>An entry whose deadline has passed reads as a miss, and is reclaimed by the read that found it.</li>
<li>A background sweeper reclaims entries that nobody will ever read again.</li>
<li><code>invalidate(key)</code> removes a key; a replacement is announced too.</li>
<li>A listener hears every removal with its reason: expired, swept, replaced, explicit.</li>
<li>The rule for how long a key lives is swappable: one number today, per key tomorrow, with jitter.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Under many threads: a value is never served after its deadline, and a refreshed value is never deleted.</li>
<li>One cold key costs one call to the loader, however many threads miss it at the same instant.</li>
<li><code>get</code> and <code>put</code> are O(1) and take no lock of ours; a slow load blocks only its own key.</li>
<li>The rules that change &mdash; how long a key lives, where time comes from, who hears about a removal &mdash; are handed in and never built inside, which is what lets a one-hour TTL be tested in a millisecond.</li>
<li>A thread waiting on somebody else\u2019s load can hand in a deadline and can be interrupted; the thread running the loader is never cut off by either.</li>
<li>Nothing half-done: a loader that throws stores nothing and leaves the key loadable by the next caller.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds Redis).</li></ul></div></div>
'''

PROMPT = ('"Build me a thread-safe cache with a time to live. <code>put</code>, <code>get</code>, and a '
          '<code>getOrLoad</code> that takes a loader for a miss. Entries expire, expired entries must never be '
          'served, and they must not pile up forever. Many threads will hammer it at once. I want working code, '
          'not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A service reads the same few thousand rows over and '
 'over, and each read costs a database round trip of about twenty milliseconds. A cache keeps those rows in '
 'memory so the second reader pays nothing. What makes it a cache and not a map is one extra fact per entry: '
 'the instant it goes stale. Once the clock passes that instant the value must never be handed to anybody again '
 '&mdash; not once, not to the thread that got there a microsecond late. Fifty request threads use the cache at '
 'the same time, so two things go wrong on their own. The first is that a key goes stale and forty threads all '
 'miss it inside the twenty milliseconds the loader takes, and all forty ask the database the same question. '
 'The second is subtler: something has to reclaim entries nobody reads again, and that something is walking the '
 'map while other threads are writing to it, so it can very easily delete a value that was refreshed a '
 'microsecond ago. The invariant is one sentence: <b>no expired value is ever returned, no live value is ever '
 'deleted, and one cold key costs one load.</b></p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: a file that compiles, with a '
 '<code>main</code> that runs a demo and then a fifty-thread race that prints the counts. The interviewer is '
 'watching for, in this order: the questions you ask before typing (where time comes from is the first one); '
 'which classes exist and who owns the map; the read and the read-or-load end to end; the two races, named out '
 'loud &mdash; the stampede and the sweep-versus-refresh; how the threads that are <i>not</i> loading wait, and '
 'whether a wakeup can go missing; where the rule that will change (how long a key lives) lives, so a per-key TTL '
 'is a new class and not an edit; what the cache holds after a loader throws. Then the twists: refresh-ahead, '
 'jitter, negative caching, a deadline on the wait, two servers.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Where does time come from, and can I control it in a test?</td><td>An injected clock</td><td>A one-method <code>Clock</code> interface; every TTL test runs in a millisecond (moves 3, 9)</td></tr>'
 '<tr><td>Is the TTL one number or per key, and counted from the write or the last read?</td><td>One number to start, per key behind an interface; from the write</td><td>A <code>TtlPolicy</code> handed in, and an absolute deadline on the entry (moves 1, 3)</td></tr>'
 '<tr><td>Many threads miss the same cold key at once. What should happen?</td><td>The loader runs once and the rest share its result</td><td>A claim per key: a future, not a lock (moves 4, 6)</td></tr>'
 '<tr><td>Is dropping an expired entry when somebody reads it enough?</td><td>No: also sweep in the background</td><td>One daemon thread, and the compare-and-remove that protects a refresh (moves 6, 9)</td></tr>'
 '<tr><td>Can the loader be slow, and can it fail?</td><td>Yes to both: about 20 ms, and it can throw</td><td>The order at the critical step, and what is left behind after a failure (move 6)</td></tr>'
 '<tr><td>If one thread&rsquo;s load is slow, may the others wait for it forever?</td><td>No: a caller may hand in a deadline, and an interrupt is honoured</td><td>Two forms of <code>getOrLoad</code>, and the rule that a deadline bounds the wait and never somebody&rsquo;s own load (moves 4, 6)</td></tr>'
 '<tr><td>Does <code>size()</code> have to be exact?</td><td>No, an estimate is fine</td><td>No global counter and therefore no global lock (moves 5, 8)</td></tr>'
 '<tr><td>One process, or a cache shared by many servers?</td><td>One process, in memory</td><td>No Redis yet; a follow-up adds it (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One minute, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> time comes from an injected clock, so every TTL test runs in a '
 'millisecond. The deadline is absolute and lives on the entry, so checking it is one comparison. Entries are '
 'reclaimed twice over &mdash; lazily on a read, and by one daemon sweeper &mdash; and both reclaim by entry '
 'identity, never by key. A miss claims the key with a compare-and-set, so the loader runs once; the threads '
 'that lose that claim wait on a result rather than on a lock, which is why no wakeup here can be lost. And '
 'there is no lock of my own anywhere. Named as out of scope: a size bound and which key to evict, '
 'refresh-ahead, negative caching, and anything distributed &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with their own state -> classes; and the waiting parties, which are not one
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a CALLER asks the CACHE for a KEY; an ENTRY holds a VALUE and its DEADLINE; a LOADER fetches a miss; a SWEEPER reclaims; a CLOCK says when", "var(--text)", 12.5)
for k, (t, sub, solid) in enumerate([("TtlCache", "the map + the claims", 1), ("CacheEntry", "value + deadline", 1),
                                     ("the sweeper", "a thread + its period", 1), ("the waiters", "no class: a future each", 0),
                                     ("Loader", "no state: handed in", 0), ("TtlPolicy", "no state: a rule", 0),
                                     ("Clock", "no state: an interface", 0)]):
    x = 18 + k * 172
    m1 += _bx(x, 110, 158, 46, t, sub, acc=bool(solid), dash=not solid) + _ar("M%s 64 V110" % (x + 79))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a rule, an interface, or a thread that is only waiting", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("read a key", "TtlCache  (owns the map)", "cache.get(k)"),
                                       ("read it, or fetch it once", "TtlCache  (owns the map AND the claims)", "cache.getOrLoad(k, loader)"),
                                       ("fetch the value", "Loader  (owns nothing: slow, can fail)", "loader.load(k)"),
                                       ("say how long this key lives", "TtlPolicy  (owns nothing: a rule)", "ttl.ttlMsFor(k)"),
                                       ("reclaim what died", "TtlCache  (owns the map)", "cache.sweepOnce()")]):
    y = 24 + k * 54
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y + 22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y + 22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 322, "the one verb that is slow and can fail -- fetch the value -- belongs to a collaborator, which is what lets the cache call it with nothing held", "var(--muted)", 11)
m2 += _tx(615, 341, "and \"reclaim what died\" has the same owner as \"read a key\": whoever owns the map is the only one allowed to decide what leaves it", "var(--muted)", 11)
MV[2] = _mv(1230, 354, m2)

# move 3: the rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 78, 220, 90, "TtlCache", "configure(ttl, clock)", acc=True)
for k, (t, sub, impl) in enumerate([("TtlPolicy", "60s today, per key tomorrow", "FixedTtl / TtlRules / JitteredTtl"),
                                    ("Clock", "the real one, or a test's", "SystemClock / ManualClock"),
                                    ("RemovalListener", "metrics, a log line, close a socket", "CacheMetrics / a lambda / none"),
                                    ("Loader", "handed in per call, not per cache", "a database read, an HTTP call")]):
    y = 20 + k * 58
    m3 += _ar("M250 123 H330 V%s H400" % (y + 22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y + 22))
m3 += _tx(615, 272, "dashed green = handed in. The cache never builds one of these, so a per-key TTL is a new class plus one changed line", "var(--muted)", 11)
m3 += _tx(615, 292, "and one rule wraps another: new JitteredTtl(base, 20) shortens every TTL by a random slice, so a million keys written together do not all die in the same millisecond", "var(--acc)", 11)
MV[3] = _mv(1230, 305, m3)

# move 4: the state many callers change at once -- drawn as threads on a time axis
def _axis(m, x0, pxPerMs, y, marks, unit="ms"):
    m += '<path d="M%s %s H%s" stroke="var(--line)" stroke-width="1.2"/>' % (x0 - 6, y, x0 + marks[-1] * pxPerMs + 20)
    for v in marks:
        x = x0 + v * pxPerMs
        m += '<path d="M%s %s V%s" stroke="var(--line)"/>' % (x, y - 4, y + 4)
        m += _tx(x, y - 10, ("%g " % v) + unit if v in (marks[0], marks[-1]) else "%g" % v, "var(--muted)", 10)
    return m

m4 = _D + _tx(615, 20, "one cold key, three threads, and a database call that takes twenty milliseconds", "var(--text)", 12.5)
m4 = _axis(m4, 180, 42, 46, [0, 5, 10, 15, 20])
for k in range(3):
    y = 56 + k * 30
    m4 += _tx(170, y + 16, "thread %d" % (k + 1), "var(--acc)", 11.5, "end")
    m4 += _bx(180, y, 66, 24, "miss", "")
    m4 += _bx(250, y, 770, 24, "the loader: one database call, 20 ms", "")
m4 += '<rect x="1040" y="56" width="172" height="84" rx="6" fill="var(--bg3)" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(1126, 80, "3 threads", RED, 12) + _tx(1126, 102, "3 database calls", RED, 11) + _tx(1126, 122, "and 3x the bill", RED, 11)
m4 += _tx(615, 172, "with one claim per key: loading.putIfAbsent(key, future) -- a compare-and-set, not a lock", "var(--acc)", 12.5)
for k, (t, acc, dash) in enumerate([("the loader: one database call, 20 ms", True, False),
                                    ("waits on thread 1's future: no lock held", False, True),
                                    ("waits on thread 1's future: no lock held", False, True)]):
    y = 190 + k * 30
    m4 += _tx(170, y + 16, "thread %d" % (k + 1), "var(--acc)", 11.5, "end")
    m4 += _bx(180, y, 66, 24, "miss", "", acc=(k == 0))
    m4 += _bx(250, y, 770, 24, t, "", acc=acc, dash=dash)
m4 += '<rect x="1040" y="190" width="172" height="84" rx="6" fill="var(--bg3)" stroke="var(--acc)"/>'
m4 += _tx(1126, 214, "3 threads", "var(--acc)", 12) + _tx(1126, 236, "1 database call", "var(--acc)", 11) + _tx(1126, 256, "2 rode the result", "var(--acc)", 11)
m4 += _tx(615, 300, "the gap is everything between \"I saw a miss\" and \"I stored a value\"; every thread that arrives inside those 20 milliseconds also sees a miss", "var(--muted)", 11)
m4 += _tx(615, 320, "one CompletableFuture per key closes it: the winner loads, the losers hold a handle on its result, and not one of them holds a lock", "var(--muted)", 11)
m4 += _tx(615, 358, "and now the question a multi-threading round always reaches: how do the losers wait?", "var(--text)", 12.5)
m4 += _card(30, 372, 570, 128, "a future: what the code on page 04 does",
            ["the winner: map.put(entry) first, then future.complete(entry)",
             "a loser: future.join() -- a completed future is a latch, not a bell",
             "a thread that arrives after complete() returns at once, no wait",
             "nobody waiting holds a lock, so nothing else is blocked"], acc=True)
m4 += _card(630, 372, 570, 128, "wait/notify: the same job by hand, and its two holes",
            ["synchronized (slot) { while (!slot.done) slot.wait(); }",
             "take the lock, test the flag UNDER it, and wait in a LOOP",
             "no flag: a notify sent before the wait is gone -- LOST WAKEUP",
             "if instead of while: a wakeup nobody sent -- SPURIOUS WAKEUP"])
m4 += _tx(615, 524, "both give one load for fifty threads, and FailureTests proves it for each; the future is the one to write, because there is no flag to forget", "var(--muted)", 11)
MV[4] = _mv(1230, 538, m4)

# move 5: each collection, the question asked of it, the shape that answers in O(1)
m5 = _D
for k, (q, shape, cost) in enumerate([("is this key here, and still alive?", "ConcurrentHashMap&lt;K, CacheEntry&lt;V&gt;&gt;", "O(1), no lock"),
                                      ("is somebody already loading it?", "ConcurrentHashMap&lt;K, CompletableFuture&gt;", "O(1), one CAS"),
                                      ("how long may this key live?", "TtlPolicy: a method, not a map", "O(1)"),
                                      ("what has died since the last pass?", "today: walk every entry", "O(n) per pass"),
                                      ("how many entries are alive?", "size() counts the dead too; liveSize() walks", "O(1) / O(n)")]):
    y = 20 + k * 50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y + 20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y + 20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 292, "the only O(n) thing in the whole design is the sweep, and move 8 is where that gets fixed. Everything a caller touches is one hash.", "var(--muted)", 11)
MV[5] = _mv(1230, 305, m5)

# move 6: the life cycle, and the ORDER at the critical step drawn as two threads over time
m6 = _D
m6 += _bx(30, 45, 180, 44, "ABSENT", "nothing stored")
m6 += _bx(290, 45, 190, 44, "LOADING", "one thread owns it", acc=True)
m6 += _bx(560, 45, 180, 44, "LIVE", "inside its deadline", acc=True)
m6 += _bx(820, 45, 200, 44, "EXPIRED", "dead, not yet reclaimed")
m6 += _ar("M210 67 H290", True) + _tx(250, 36, "a miss wins", "var(--muted)", 10)
m6 += _ar("M480 67 H560", True) + _tx(520, 36, "loader returned", "var(--muted)", 10)
m6 += _ar("M740 67 H820", True) + _tx(780, 36, "clock passed it", "var(--muted)", 10)
m6 += _ar("M385 45 V22 H120 V43", dash=True) + _tx(250, 17, "the loader threw: nothing stored, the claim freed", "var(--muted)", 10.5)
m6 += _ar("M920 89 V122 H120 V91", True) + _tx(520, 138, "a read or a sweep compare-and-removes: only THIS entry, never a value somebody refreshed in between", "var(--muted)", 11)
m6 += _tx(615, 176, "the order at the critical step, on the two threads that meet there", "var(--text)", 12.5)
for k, (t, sub) in enumerate([("1  claim the key", "putIfAbsent: one CAS"), ("2  call the loader", "20 ms, nothing held"),
                              ("3  map.put(entry)", "publish it first"), ("4  complete the future", "then wake the waiters"),
                              ("5  release the claim", "in a finally block")]):
    x = 180 + k * 202
    m6 += _bx(x, 196, 186, 46, t, sub, acc=True)
    if k < 4: m6 += _ar("M%s 219 H%s" % (x + 186, x + 200), True)
m6 += _tx(170, 222, "the winner", "var(--acc)", 11.5, "end")
m6 += _tx(170, 288, "a loser", "var(--acc)", 11.5, "end")
m6 += _bx(180, 264, 186, 46, "sees the claim taken", "putIfAbsent returns it")
m6 += _ar("M366 287 H380", True)
m6 += _bx(380, 264, 388, 46, "waits on the winner's future", "holds no lock; wakes when it completes", dash=True)
m6 += _ar("M768 287 H782", True)
m6 += _bx(782, 264, 388, 46, "gets the value that was stored", "never a value the map does not have")
m6 += _tx(615, 336, "if the loader throws, steps 3 and 4 never happen: nothing is written, every waiter is told the same failure, and step 5 still runs, so the next caller starts clean", "var(--muted)", 11)
MV[6] = _mv(1230, 350, m6)

# move 7: what is inside a lock, for how long, and eight callers at the same instant
m7 = _D + _card(30, 20, 540, 155, "inside a lock: about 100 nanoseconds",
                ["there is no lock of our own in the whole class",
                 "a get takes none at all: one volatile array read",
                 "a put takes one bin's lock out of about 16,000",
                 "what is held: one hash, a short list walk, one write",
                 "the listener fires after the map call has returned"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 86, "no lock", "var(--acc)", 10)
m7 += _card(640, 20, 560, 155, "outside every lock: milliseconds",
            ["the loader: a database round trip, about 20 ms",
             "which is 200,000 times longer than the bin lock",
             "the removal listener: a metric, a log line",
             "a sweep pass over 10,000 entries: about 0.2 ms",
             "the caller's own network hop: tens of milliseconds"])
m7 += _tx(615, 192, "eight threads touch the same key at the same instant", "var(--text)", 12.5)
m7 = _axis(m7, 140, 2.5, 230, [0, 100, 200, 300, 400], "ns")
for k, note in enumerate(["returns at about 40 ns -- it took no lock, so it waited for nobody",
                          "the same instant, the same 40 ns, and still no waiting",
                          "and four more exactly like them: a reader never queues behind anything"]):
    y = 240 + k * 19
    m7 += _tx(130, y + 12, "reader 1" if k == 0 else ("reader 2" if k == 1 else "readers 3-6"), "var(--muted)", 10.5, "end")
    m7 += '<rect x="140" y="%s" width="100" height="15" rx="3" fill="var(--bg3)" stroke="var(--line)"/>' % y
    m7 += _tx(250, y + 12, note, "var(--muted)", 10.5, "start")
m7 += _tx(130, 311, "writer 1", "var(--acc)", 10.5, "end")
m7 += '<rect x="140" y="299" width="250" height="15" rx="3" fill="var(--bg3)" stroke="var(--acc)"/>'
m7 += _tx(400, 311, "holds one bin for about 100 ns", "var(--acc)", 10.5, "start")
m7 += _tx(130, 330, "writer 2", "var(--acc)", 10.5, "end")
m7 += '<rect x="390" y="318" width="250" height="15" rx="3" fill="var(--bg3)" stroke="var(--acc)" stroke-dasharray="4 3"/>'
m7 += _tx(650, 330, "only if its key lands in the SAME bin: waits 100 ns, then takes its own 100 ns", "var(--acc)", 10.5, "start")
m7 += _tx(615, 357, "so \"is everything one by one now?\" -- no. Readers take no lock at all. Two writers only meet when their keys land in the same bin, which with", "var(--muted)", 11)
m7 += _tx(615, 376, "16,384 bins is about one put in sixteen thousand, for a hundred nanoseconds -- while the twenty-millisecond loader runs with nothing held at all", "var(--muted)", 11)
m7 += _tx(615, 402, "and the honest half of the answer: none of this is fair. The claim goes to whoever wins one compare-and-set -- no queue, no ticket, no order --", "var(--acc)", 11)
m7 += _tx(615, 421, "so a thread can lose twice running. Nobody starves, because losing means riding somebody else\u2019s result, which is finished work, not another wait.", "var(--acc)", 11)
MV[7] = _mv(1230, 435, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="205" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one hot key: is the stampede real? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a product page: 2,000 reads a second of one key",
                       "TTL 60 s, and the loader is a 20 ms database call",
                       "every 60 s it dies; in those 20 ms, 40 threads miss it",
                       "without a claim: 40 queries a window, 57,600 a day",
                       "with a claim: 1 query a window, 1,440 a day -- 40x less",
                       "a get itself costs ~40 ns: 50,000 a second is 0.2% of a core"]):
    m8 += _tx(35, 66 + k * 26, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1  lazy expiry plus one claim per key", "this file: no timer, no thread, the loader outside every lock"),
                              ("2  a deadline queue for the sweeper", "a pass pops only the keys that died: O(k log n), not O(n)"),
                              ("3  shard by hash, or amortise onto reads", "N maps and N sweepers; Caffeine drains a ring buffer and needs no thread")]):
    m8 += _bx(600, 58 + k * 54, 600, 46, t, sub, acc=(k == 0))
m8 += _tx(615, 245, "say the arithmetic before you climb: at 2,000 reads a second the cache is not the problem and the database is, which is why rung 1 is a claim and not a faster map", "var(--muted)", 11)
MV[8] = _mv(1230, 258, m8)

# move 9: what can go wrong -> the test for each
m9 = _D
for k, (bad, fix) in enumerate([("a value is served after it died", "compare with the clock on every read; an injected clock steps over the deadline (test 1)"),
                                ("the sweeper deletes a fresh value", "map.remove(key, entry): the entry, not the key; a refresh mid-sweep survives (test 3)"),
                                ("fifty threads miss one cold key", "one claim per key, putIfAbsent on a future; 50 threads, exactly 1 loader call (test 4)"),
                                ("the loader throws, or wedges forever", "nothing written, the claim freed in a finally; a waiter may set a deadline (tests 6, 10)"),
                                ("a waiter is cancelled, or wakes too late", "the bounded wait answers the interrupt, and the retry loop always ends (tests 11, 12)"),
                                ("a listener throws, or a load is slow", "both are called with nothing held, each listener in its own try/catch (tests 7, 8)")]):
    y = 18 + k * 42
    m9 += _bx(30, y, 320, 38, bad, "") + _ar("M350 %s H400" % (y + 19), True) + _bx(400, y, 800, 38, fix, "", acc=True)
m9 += _tx(615, 292, "every claim this page makes has a test: FailureTests.java runs thirteen of them, fifty-seven checks, finishes in under a second, and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 305, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface TtlPolicy&lt;K&gt; { long ttlMsFor(K key); }, handed in by configure()", None), ("a per-key TTL is a new class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new JitteredTtl&lt;&gt;(base, 20) wraps any TTL rule, present or future", None), ("a million keys stop dying in the same millisecond", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("fire(key, value, cause) after the map write, each one in a try/catch", None), ("metrics without the cache knowing what a metric is", None)],
          [("State", "var(--text)"), ("move 6", None), ("ABSENT &rarr; LOADING &rarr; LIVE &rarr; EXPIRED, and the CAS that owns LOADING", None), ("only one thread can be in LOADING for a key", None)],
          [("Future (Promise)", "var(--text)"), ("move 4", None), ("loading.putIfAbsent(key, new CompletableFuture&lt;&gt;()): the wait protocol", None), ("a completed future is a latch: no wakeup is lost", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the cache is built and handed to its callers; no getInstance()", "var(--muted)"), ("a test builds a fresh cache per claim", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("TtlRules.parse(\"user:=300000, =60000\") in Extensions.java", "var(--muted)"), ("it earns the name the day TTLs come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("not yet", None), ("three collaborators, all required, one configure(ttl, clock) call", "var(--muted)"), ("Caffeine.newBuilder() is this, at ten knobs", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence and none of them is decoration", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("CacheEntry holds a deadline. TtlPolicy answers one question. TtlCache owns the map.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("TtlRules and JitteredTtl are new files; not one line of TtlCache changed", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("clock.nowMs() and ttl.ttlMsFor(k); never \"is this the test clock?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Clock, TtlPolicy, Loader, RemovalListener: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("configure(new FixedTtl&lt;&gt;(100), manualClock) is the entire test seam", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "refresh-ahead, jitter, negative caching", "a new TtlPolicy, or a wrapper round the loader", "the cache itself does not change", "move 3"),
        ("someone new wants to know", "hit rate, load latency, a leak alarm", "one more RemovalListener, plus the counters already there", "fired after the write, in a try/catch", "move 3"),
        ("a new step in a life", "serve stale while a reload runs", "one more state, REFRESHING, and one more transition", "a soft deadline in front of the hard one", "move 6"),
        ("a new invariant across keys", "the cache must fit in two gigabytes", "a bound goes ON the cache, with whatever state the victim rule needs", "soft: a hard bound needs one global counter", "move 4"),
        ("state that must outlive the process", "two servers, and a restart", "the entries in Redis: SET key val PX 60000, and the claim becomes", "SET lock:key owner NX PX 5000, with PUBLISH to invalidate the other copy", "moves 5 + 12")]):
    y = 24 + k * 54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y + 22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y + 27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the read path, the claim and the tests do not change; that is the check that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: a <b>caller</b> asks the <b>cache</b> for a <b>key</b>; an <b>entry</b> holds a "
 "<b>value</b> and its <b>deadline</b>; a <b>loader</b> fetches a miss; a <b>sweeper</b> reclaims; a <b>clock</b> "
 "says when. The cache owns the map of entries and the set of keys currently being loaded, both of which change: "
 "a class. An entry holds a value and the instant it dies, and never changes afterwards: a small immutable class. "
 "Its three fields are <code>final</code>, and on a multi-threading problem that is not decoration &mdash; final "
 "fields are frozen when the constructor returns, so a thread that finds the entry in the map can never see a "
 "half-built one. The name for that is <i>safe publication</i>, and it is why reading an entry needs no lock. "
 "The sweeper owns a thread and a period: a field "
 "on the cache, not a class of its own. The loader, the TTL rule and the clock have no state at all &mdash; they "
 "are calculations somebody hands in &mdash; so each is a one-method interface. And the interesting one: the "
 "<i>waiting parties</i>, the forty-nine threads that miss a cold key while the fiftieth is loading it, are not a "
 "class either. On a multi-threading problem the first thing to name out loud is who waits, and here they wait on "
 "a handle to a result, not in a queue and not on a lock.", 1),

("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Read a key\" touches the map, so it belongs to the thing that owns the map: <code>cache.get(k)</code>. \"Read "
 "it, or fetch it once\" touches the map <i>and</i> the set of claims, and only the cache sees both, so it is "
 "<code>cache.getOrLoad(k, loader)</code> and nothing else can own it. \"Fetch the value\" touches nothing of "
 "ours at all &mdash; it is a database call that takes twenty milliseconds and may throw &mdash; so it goes to a "
 "collaborator, <code>loader.load(k)</code>, and that is not bookkeeping: it is what lets the cache call it with "
 "nothing held. \"Say how long this key lives\" is a pure calculation, <code>ttl.ttlMsFor(k)</code>. \"Reclaim "
 "what died\" touches the map again, so it has the same owner as the read: <code>cache.sweepOnce()</code>. That "
 "is the rule that matters here &mdash; whoever owns the map is the only one allowed to decide what leaves it, "
 "which is why the sweeper is a method on the cache and not a class walking somebody else's data.", 2),

("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Four things will change. How long a key lives (sixty seconds today; per key tomorrow; with jitter the day a "
 "million keys are written together) becomes <code>TtlPolicy</code>. Where time comes from becomes "
 "<code>Clock</code>, and that one is not a nicety: without it a one-hour TTL is tested by sleeping for an hour. "
 "Who wants to hear that an entry left becomes <code>RemovalListener</code>. How to fetch a missing value becomes "
 "<code>Loader</code>, handed in per call rather than per cache, because two callers of the same cache legitimately "
 "load from different places. Each is one method. The cache is <i>given</i> them in <code>configure(...)</code> and "
 "never builds one, which is why a test can hand in a clock it drives by hand. This is also where the patterns are "
 "born, and nowhere else: a swappable rule behind an interface is <b>Strategy</b>; a rule that wraps another rule "
 "and adds to it &mdash; <code>new JitteredTtl(base, 20)</code>, which shortens every TTL by a random slice so a "
 "million keys do not all die in the same millisecond &mdash; is <b>Decorator</b>; something that announces \"this "
 "entry left\" without knowing what a metric is, is <b>Observer</b>. Name them on page 02, move 10, not now.", 3),

("Move 4: state that many callers change at the same time gets one owner and one lock -- and here the answer is no lock at all.",
 "The shared state is the map, and the map is a <code>ConcurrentHashMap</code>, which already has one lock per bin "
 "and takes none at all on a read. So the usual move &mdash; one owner, one lock &mdash; is already done by the "
 "structure, and the real race is somewhere else. Look at the picture: three threads miss the same cold key, and "
 "each one calls a loader that takes twenty milliseconds. The gap is everything between \"I saw a miss\" and \"I "
 "stored a value\", and it is twenty milliseconds wide, so every thread that arrives inside it also sees a miss. "
 "At two thousand reads a second that is forty threads asking the database the same question. The fix is not a "
 "lock around the load &mdash; a lock would make the other forty-nine threads sleep in a queue, and would still "
 "have to be released before the slow call to avoid pinning everything. The fix is a <i>claim</i>: one extra map "
 "from key to a <code>CompletableFuture</code>, and <code>putIfAbsent</code> on it is a single compare-and-set. "
 "Exactly one thread gets null back and becomes the loader; everybody else gets the winner's future and waits on a "
 "result. Waiting on a result is not the same as waiting on a lock: nothing is held, nothing else is blocked, and "
 "a thread that arrives after the value is stored never waits at all. That last clause is the whole <i>wait "
 "protocol</i>, in the words the interviewer is listening for: change the state first, signal second, and let a "
 "late arriver test the state instead of listening for the signal. A completed future does all of that for free, "
 "because it is a latch and not a bell &mdash; joining one that has already completed returns at once &mdash; so "
 "no wakeup here can go missing. It carries the memory guarantee too, which is the half of this question people "
 "forget: everything the winner did before <code>complete</code> is visible to every thread that returns from "
 "<code>join</code>, exactly as everything done before a <code>map.put</code> is visible to whoever later gets "
 "that key. Those two guarantees are why the values this cache hands between threads need no lock and no "
 "<code>volatile</code> of their own. The right-hand card is the same protocol written by hand with a monitor, and the "
 "two ways it goes wrong have names worth knowing: drop the <code>done</code> flag and a <code>notifyAll</code> "
 "sent a microsecond too early is gone for good, which is a <b>lost wakeup</b>; use an <code>if</code> where a "
 "<code>while</code> belongs and a wakeup nobody sent hands the caller a half-built answer, which is a "
 "<b>spurious wakeup</b>. Extensions.java carries that version and test 13 proves it: one load for thirty "
 "threads, and a lost wakeup reproduced on demand. So the reason to write the future is not speed &mdash; it is "
 "that there is no flag to forget.", 4),

("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Is this key here, and still alive?\" is one hash into a <code>ConcurrentHashMap</code> and one comparison "
 "against the clock: O(1), and a read takes no lock. \"Is somebody already loading it?\" is a second map, keyed "
 "the same way, holding one future per load in flight; the question is answered by the <code>putIfAbsent</code> "
 "that asks it, so asking and claiming are the same operation. \"How long may this key live?\" is not a map at "
 "all, it is a method call on the rule that was handed in. Two answers are deliberately not O(1), and saying so "
 "out loud is the point of this move. \"What has died since the last pass?\" is a full walk of the map today, "
 "O(n) per pass, and move 8 replaces it with a deadline queue. And <code>size()</code> counts entries that have "
 "expired but not yet been reclaimed, so it is an estimate that runs high between sweeps; an exact live count "
 "would need one shared counter on every write, which is the single global bottleneck this design exists to "
 "avoid.", 5),

("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An entry is ABSENT, then LOADING while one thread owns the claim, then LIVE until the clock passes its deadline, "
 "then EXPIRED, and then ABSENT again when a read or a sweep reclaims it. Writing the states down forces the two "
 "questions an interviewer will ask. First: what if the loader throws? Then LOADING goes straight back to ABSENT "
 "and nothing is stored &mdash; the key is not poisoned with a bad value and the next caller starts a clean load. "
 "Second: who removes an EXPIRED entry, and what if somebody refreshed it a microsecond ago? That is the whole "
 "reason the removal is <code>map.remove(key, entry)</code> and not <code>map.remove(key)</code>: it deletes that "
 "exact object or nothing at all. Then the order at the critical step, which is the same rule as \"take the money "
 "before you commit\": <b>1</b> claim the key with a compare-and-set; <b>2</b> call the loader, holding nothing, "
 "for twenty milliseconds; <b>3</b> put the entry in the map; <b>4</b> only now complete the future; <b>5</b> "
 "release the claim in a <code>finally</code>. Publishing to the map before completing the future is what makes "
 "the losers' answer safe: a waiter can never be handed a value the map does not already have. It is also move "
 "4's rule with this system's nouns in it &mdash; change the state, then signal, never the other way round. And "
 "if step 2 throws, steps 3 and 4 never happen, every waiter is told the same failure, and step 5 still runs. "
 "One last thing about the loop around all of this: it is not there for spurious wakeups, which a future does "
 "not have. It is there for the one case where the winner's value had already died by the time a waiter was "
 "woken, which needs a TTL shorter than a load, and each extra round either hands back a live value or makes "
 "that thread the next loader. Page 05 has the proof that it always ends.", 6),

("Move 7: yes, there is contention. Ask where it actually is, for how long, and what is inside it.",
 "The honest answer for this design is that there is no lock of our own anywhere in the class, so the question "
 "becomes: what does <code>ConcurrentHashMap</code> hold, and for how long? A <code>get</code> holds nothing &mdash; "
 "it is a volatile read of one array slot, about forty nanoseconds &mdash; so the eight readers in the picture all "
 "return at once and none of them waits for another. A <code>put</code> takes the lock of one bin, for about a "
 "hundred nanoseconds, long enough to hash the key, walk a very short list and write one field. Two writers only "
 "meet if their keys land in the same bin, and with sixteen thousand bins that is about one put in sixteen "
 "thousand. Everything expensive is outside: the loader at twenty milliseconds, which is two hundred thousand "
 "times the bin lock; the removal listener, fired after the map call has returned and wrapped in a try/catch; the "
 "sweep pass. So when the interviewer asks \"have you not just serialised the whole cache?\", those are the two "
 "numbers to give, and the reason they stay that small is that the only slow thing in the system is never allowed "
 "inside them. Two more things belong in that answer, because they are what the next question is made of. First, "
 "none of this is <i>fair</i>: the claim goes to whichever thread wins one compare-and-set, there is no queue and "
 "no ticket and no order, and a thread can lose twice running. Nobody starves, though, and the reason is worth "
 "having ready &mdash; losing is not another wait, it is riding a result somebody is already fetching. Second, a "
 "waiter is not hostage to the winner: the three-argument <code>getOrLoad</code> takes a deadline in milliseconds "
 "and answers an interrupt, while the winner's own load is never cut off by somebody else's impatience, because "
 "that bound belongs on the loader and not in the cache.", 7),

("Move 8: say the arithmetic, then name the ladder.",
 "Take a product page: two thousand reads a second of one key, a TTL of sixty seconds, a loader that is a "
 "twenty-millisecond database call. Every sixty seconds the key dies, and in the twenty milliseconds the reload "
 "takes, two thousand times 0.02 &mdash; forty threads &mdash; miss it. Without a claim that is forty identical "
 "queries per window and 57,600 a day; with a claim it is one per window and 1,440 a day, forty times less, which "
 "is the entire argument for the extra map. The cache itself is not the cost, as the card's last line says. Then "
 "the ladder, cheapest first. Rung one is what is in the file, and it needs no timer and no thread. Rung two "
 "attacks the one O(n) thing there is: keep the deadlines in a priority queue so a pass pops only the keys that "
 "actually died, O(k log n) instead of walking ten thousand entries to find three. Rung three is sharding, N "
 "sub-caches by hash with a sweeper each. Say the arithmetic before you climb: at two thousand reads a second "
 "the cache was never the problem, the database was, which is why rung one is a claim and not a faster map.", 8),

("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The six failures are in the picture, each beside the line that stops it. What is worth saying out loud is how "
 "two of them are <i>tested</i>, because they are races, and a race you cannot reproduce is not a test. Both are "
 "made deterministic by the seam move 3 already gave us: the injected clock. The sweeper reads the clock "
 "between picking an entry up and removing it, so a test clock that performs the refresh inside that read "
 "reproduces the interleaving exactly, every single run. The stampede tests use the same idea from the other "
 "side: the loader does not return until all forty-nine losers are provably waiting, so the count is one on a "
 "fast laptop and one on a loaded build box. The last three are the ones a multi-threading interviewer reaches "
 "for: a waiter stuck behind a wedged load (it hands in a deadline, and giving up starts no second load); a "
 "waiter that is cancelled (the bounded wait throws <code>InterruptedException</code> instead of swallowing it, "
 "and the thread that was loading carries on undisturbed); and the retry loop with a TTL shorter than a load, "
 "forced by a clock that jumps five milliseconds a read. FailureTests.java runs thirteen of these, fifty-seven "
 "checks, in under a second.", 9),

("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table has the four that any LLD round produces &mdash; Strategy, Decorator, Observer, State &mdash; each "
 "with the move that produced it and the line that shows it. Two more rows need a sentence the table cannot "
 "hold. The first is the one specific to a "
 "multi-threading round: the <b>Future</b>, sometimes called a Promise, <i>is</i> the wait protocol. On a "
 "blocking queue the waiters sit on a condition variable and somebody has to remember to signal them after the "
 "change; here they hold a handle on somebody else's result, which is strictly better because it blocks nothing "
 "and because a result that has already arrived cannot be missed. The second is why two famous names are marked "
 "\"not yet\" rather than used. Factory earns its name the day the rules stop being written in Java and arrive as "
 "text, which is <code>TtlRules.parse(\"user:=300000, =60000\")</code> in Extensions.java. Builder earns its "
 "place at about the sixth optional collaborator; three that are all required is a <code>configure</code> call, "
 "and ten optional ones is <code>Caffeine.newBuilder()</code>, which is exactly this pattern in a real library.", 10),

("Move 11: run SOLID as a check on the moves, one line each.",
 "S: each class has one reason to change &mdash; an entry holds a value and a deadline, a TTL rule answers one "
 "question, a clock tells the time, the cache owns the map. O: a per-key TTL and a jittered TTL are new files, and "
 "not one line of <code>TtlCache</code> changed to add them. L: the cache calls <code>clock.nowMs()</code> and "
 "<code>ttl.ttlMsFor(k)</code> and never asks which implementation it got, which is precisely why a test clock "
 "with a side effect can be dropped in to reproduce a race. I: four interfaces with one method each, so a caller "
 "depends only on the slice it uses. D: <code>configure(new FixedTtl&lt;&gt;(100), manualClock)</code> is the "
 "whole test seam &mdash; the cache depends on the abstractions and is handed the implementations, which is the "
 "difference between testing a one-hour TTL in a millisecond and not testing it at all.", 11),

("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The first three rows of the picture are twists you can answer in one sentence each, and the code for all of "
 "them is on page 05. Two need more than a sentence. A new invariant across keys &mdash; \"the cache must fit in "
 "two gigabytes\" &mdash; is a size bound, and the point that earns marks is that it goes <i>on</i> this cache "
 "and not inside it: a TTL cache records nothing about reads, so the rule that picks a victim has to bring its "
 "own state with it. The bound is also deliberately soft, because a hard one needs a global counter on every "
 "write, which is the thing this design refuses. Which key to throw away &mdash; LRU, LFU, and the O(1) "
 "structures behind them &mdash; belongs to " + LRU_PAGE + " and " + EVICT_PAGE + ", not here. State that must "
 "outlive the process (two servers, a restart) hands the deadline to Redis instead of tracking it here, and turns "
 "the claim into a lease with a TTL of its own, so a server that dies mid-load does not block the key forever. "
 "For all five the read path, the claim and the tests are untouched, and that is the check that the derivation "
 "was right.", 12),
]

DERIVATION_LEAD = ("Run these on any LLD and the class diagram, the tests, the patterns, SOLID and the answer to "
 "every twist fall out in that order; nothing is chosen up front, and nothing is named before the move that "
 "produced it. On a multi-threading problem three of the moves change shape: move 1 also names <i>who waits</i>, "
 "move 4 asks what the gap between reading and writing is <i>wide enough</i> to let in and then how the threads "
 "that lose the race are made to wait, and move 6 becomes the order of operations across two threads instead of "
 "one. Here the gap is twenty milliseconds wide, which is why "
 "it is the whole problem.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the callers, the small role interfaces, and the two clocks
put("loader", 10, 95, 250, "Loader", [], ["load(key): V", "a database read; may throw"], "interface")
put("rl", 10, 190, 250, "RemovalListener", [], ["onRemoval(key, value, cause)", "CacheMetrics, or a lambda"], "interface")
put("cause", 10, 285, 250, "RemovalCause", ["EXPIRED, SWEPT,", "REPLACED, EXPLICIT"], [], "enum")
put("clock", 10, 375, 250, "Clock", [], ["nowMs(): long"], "interface")
put("sys", 10, 460, 120, "SystemClock", [], ["nanoTime()/1e6"])
put("man", 140, 460, 120, "ManualClock", [], ["advance(ms)"])
# centre column: the contract, the aggregate root, and the thing it owns
put("cache", 310, 10, 350, "Cache", [],
    ["put(key, value)", "get(key): V", "getOrLoad(key, loader): V", "getOrLoad(key, loader, timeoutMs): V",
     "invalidate(key): boolean", "size(): int"], "interface")
put("ttlcache", 310, 160, 350, "TtlCache",
    ["map: ConcurrentHashMap&lt;K, CacheEntry&gt;", "loading: ConcurrentHashMap&lt;K,",
     "     CompletableFuture&lt;CacheEntry&gt;&gt;", "listeners: CopyOnWriteArrayList",
     "ttl: TtlPolicy    clock: Clock", "sweeper: ScheduledExecutorService",
     "7 LongAdder counters (hits, misses, ...)"],
    ["configure(ttl, clock) / addListener(l)", "put / get / invalidate",
     "getOrLoad(k, loader [, timeoutMs])", "startSweeper(everyMs) / sweepOnce() / close()",
     "size() / liveSize() / stats()"])
put("entry", 310, 445, 350, "CacheEntry",
    ["value: V", "loadedAtMs / expiresAtMs: long", "all final: safe publication"],
    ["isLive(nowMs): boolean", "equals = identity, on purpose"])
# third column: the JDK machinery, which is where the waiting happens
put("fut", 710, 160, 250, "CompletableFuture", ["one per key being loaded"],
    ["complete(entry)", "join(): the losers wait here"], "jdk")
put("sched", 710, 285, 250, "ScheduledExecutorService", ["one daemon thread", "named ttl-sweeper"],
    ["scheduleWithFixedDelay(...)"], "jdk")
# fourth column: the rules that are handed in
put("ttlp", 1000, 10, 230, "TtlPolicy", [], ["ttlMsFor(key): long"], "interface")
put("fixed", 1000, 95, 230, "FixedTtl", ["ttlMs: long"], ["one number for every key"])
put("jit", 1000, 200, 230, "JitteredTtl", ["base: TtlPolicy (wrapped)", "percent: int"], ["shortens by a random slice"])
put("rules", 1000, 320, 230, "TtlRules", ["byPrefix: Map&lt;String, Long&gt;"], ["parse(config): TtlRules", "longest prefix wins"], "Extensions.java")

def note(x, y, w, h, title, lines, col="var(--muted)"):
    g = '<rect x="%s" y="%s" width="%s" height="%s" rx="6" fill="var(--bg2)" stroke="%s" stroke-dasharray="5 3"/>' % (x, y, w, h, col)
    g += _tx(x + w / 2, y + 20, title, col, 12)
    for k, l in enumerate(lines): g += _tx(x + w / 2, y + 40 + k * 17, l, "var(--muted)", 10.5)
    return g

EDGES = [
 note(10, 10, 250, 62, "50 caller threads", ["no class of their own:", "they bind to the interface"], "var(--acc2)"),
 note(710, 422, 250, 110, "the waiting parties", ["n-1 threads per key,", "each holding a handle on", "the winner's result:",
                                                  "no lock, no queue, no class"], "var(--acc2)"),
 ln((260, 41), (310, 69), "assoc", "", [(285, 41)]),
 ln(B["ttlcache"]["t"], B["cache"]["b"], "inherit"),
 ln(B["ttlcache"]["b"], B["entry"]["t"], "compose", "one per key"),
 ln((660, 200), (710, 200), "compose"),
 ln((660, 330), (710, 330), "compose"),
 ln((660, 267), (1000, 37), "inject", "", [(975, 267), (975, 37)]),
 _tx(945, 92, "the rules, handed in", "var(--acc)", 10.5, "end"),
 ln((310, 230), (260, 402), "inject", "", [(285, 230), (285, 402)]),
 ln((310, 185), (260, 130), "assoc", "", [(296, 185), (296, 130)]),
 ln((310, 280), (260, 225), "notify", "", [(273, 280), (273, 225)]),
 ln(B["rl"]["b"], B["cause"]["t"], "assoc"),
 ln(B["sys"]["t"], B["clock"]["b"], "inherit"),
 ln(B["man"]["t"], B["clock"]["b"], "inherit"),
 ln(B["fixed"]["t"], B["ttlp"]["b"], "inherit"),
 ln(B["jit"]["l"], B["ttlp"]["l"], "inherit", "", [(985, 245), (985, 37)]),
 ln(B["rules"]["l"], B["ttlp"]["l"], "inherit", "", [(972, 365), (972, 30)]),
 ln(B["jit"]["t"], B["fixed"]["b"], "assoc", "wraps"),
]
UMLSVG = uml_svg(1230, 620, EDGES, legend_y=590)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a '
 'fixed list of values; &laquo;jdk&raquo; = a class from the standard library that is part of the design; '
 '&laquo;Extensions.java&raquo; = a class that lives in the second file, so everything unmarked is Main.java). Middle: '
 'its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = implements. Filled '
 'diamond = owns: the cache owns every entry, every claim in flight, and the sweeper thread, and all three die '
 'with it. Plain arrow = references. Dashed green = handed in through <code>configure()</code>. Dotted blue = '
 'notifies. <b>Where state lives:</b> everything mutable is in <code>TtlCache</code> &mdash; two concurrent maps, '
 'a list of listeners and seven counters &mdash; and nothing else in the diagram has a field that changes. '
 '<code>CacheEntry</code> is written once and never touched again, which is what makes it safe to hand across '
 'threads without a lock, and its identity is load-bearing: <code>map.remove(key, entry)</code> means <i>this '
 'object</i>. <b>What is not here:</b> no lock class, because there is no lock of our own; no Sweeper class, '
 'because whoever owns the map decides what leaves it; and no class for the forty-nine threads waiting on a cold '
 'key, because they hold a future and wait on a result rather than queueing on anything. The two forms of '
 '<code>getOrLoad</code> on the contract are the whole waiting story: the short one waits as long as the load '
 'takes, the long one gives this caller a deadline and answers an interrupt.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it is for and what it guarantees; read only those first for the shape, then the '
 'bodies. Each copy button copies that whole file. Below Main.java: Extensions.java (the reference code for every '
 'follow-up, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (thirteen claims and '
 'fifty-seven checks; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS in '
 'under a second).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (where time comes from is the first one); then type '
 'in the order of Main.java: the RemovalCause enum, the Clock interface with its two implementations, the '
 'TtlPolicy interface with FixedTtl and the JitteredTtl wrapper, the RemovalListener and Loader interfaces, the '
 'immutable CacheEntry, the Cache interface, then TtlCache &mdash; the two maps, get with its compare-and-remove, '
 'getOrLoad with the claim and the five-step order, then the bounded form of the wait, sweepOnce and the daemon '
 'sweeper &mdash; and finally a main with a manual clock and a fifty-thread race.</div></div>')

FU = [
("A million keys were written in the same minute. At the end of that minute they all expire together and a million "
 "loads hit the database at once. Fix it without touching TtlCache.", "twist", 8,
 "The TTL is already a rule behind an interface, so this is one new class that wraps the old one. JitteredTtl asks "
 "the rule it wraps for a TTL and then subtracts a random slice of it, up to twenty percent, so a million keys "
 "written in the same millisecond get a million different deadlines spread over a twelve-second window. It only "
 "ever shortens, never lengthens, so it cannot cause a stale value to be served. Nothing else moves: the cache, "
 "the tests and the read path are untouched, and it wraps any rule, including the per-prefix one in "
 "Extensions.java and any rule written next year. That is Decorator, and it was born in move 3 as a rule that "
 "wraps a rule &mdash; not chosen because the pattern is nice.",
 sect(src, "final class JitteredTtl", "interface RemovalListener")),

("Fifty threads miss the same cold key at the same instant. Prove, with a test, that the loader ran exactly once.",
 "non-functional", 10,
 "The test starts fifty threads on a latch so they all miss together, and counts the calls to the loader. The "
 "trick that makes it deterministic rather than flaky is that the loader does not return until all forty-nine "
 "losers have provably joined: it waits on the cache's own joins counter, with a fifteen-second ceiling so a "
 "broken design fails the test instead of hanging it. Without that, a slow machine could let the winner finish "
 "before a straggler arrives, and the straggler would get a cache hit instead of joining, and the counts would "
 "wobble. Four things are asserted: exactly one call to the loader, all fifty threads got the same value, "
 "exactly forty-nine of them rode the winner's result, and exactly one entry was stored.",
 T("        // 4. fifty threads miss one cold key", "        // 5. the claim is per key")),

("You have told me there is no lock of your own anywhere. So what actually serialises here, and when does this "
 "stop scaling?", "non-functional", 6,
 "Three things, and only the third is a real limit. A read serialises on nothing at all: one volatile read of an "
 "array slot, about forty nanoseconds. A write takes one bin of the ConcurrentHashMap for about a hundred "
 "nanoseconds, and two writers only collide when their keys land in the same bin, which with sixteen thousand "
 "bins is about one put in sixteen thousand &mdash; while the loader, the only slow thing in the system, is "
 "called with nothing held. What eventually bites is the sweeper, whose pass is O(n) over the whole map, and the "
 "counters, which is why they are LongAdder and not AtomicLong: fifty thousand increments a second on one "
 "AtomicLong is itself a contention point. The ladder from there is a deadline queue, then sharding.",
 sect(src, "    public V get(K key)", "    /**\n     * The value, loading it on a miss")),

("The forty-nine threads that did not win the claim -- how exactly do they wait, and can one of them miss the "
 "wakeup?", "design", 6,
 "They hold the winner\'s CompletableFuture and call <code>join</code> on it, which parks the thread and holds "
 "nothing at all. No wakeup can go missing, and the sentence to have ready is that a completed future is a latch, "
 "not a bell: the winner calls <code>complete</code> once, and every thread that joins afterwards returns "
 "immediately with the same value. That is the wait protocol &mdash; change the state first, signal second, and "
 "let a late arriver test the state instead of listening for the signal. The code below writes the same protocol "
 "by hand, and all three lines are load-bearing: take the lock, test the <code>done</code> flag <i>under</i> the "
 "lock, and wait in a <i>loop</i>. Delete the flag and a <code>notifyAll</code> sent a microsecond too early is "
 "gone for good, which is the <b>lost wakeup</b> that <code>lostWakeup()</code> reproduces on demand, with a "
 "timed wait so it reports the bug instead of hanging; use an <code>if</code> where a <code>while</code> belongs "
 "and a wakeup nobody sent hands the caller a half-built answer, which is the <b>spurious wakeup</b>. Both "
 "versions load once for thirty threads, so the future wins on there being no flag to forget, not on speed.",
 X("the monitor version", "two processes")),
("The loader throws halfway through, or never returns at all. What is in the cache afterwards, and what does the "
 "next caller see?", "functional", 8,
 "Nothing is in the cache. The order is deliberate: the loader is called first, and the map is only written after "
 "it returns, so a failure means there was never anything to undo. The future is completed exceptionally, so all "
 "nineteen waiters are told the same failure rather than hanging, and the claim is released in a finally block, "
 "so the very next caller starts a clean load rather than finding a poisoned key. The test proves all three: "
 "twenty callers fail, the loader was called once, the cache is empty, and the next call succeeds. A loader that "
 "never returns is a different problem, and it is fixed on the loader rather than inside the cache: BoundedLoader "
 "wraps any loader and runs it with a deadline, which turns a hang into an exception the cache already knows how "
 "to handle.",
 sect(src, "    private V loadAndPublish", "    /** Waiting on the winner")
 + "\n" + X("a loader that never returns", "a deadline queue")),

("A request thread cannot sit behind somebody else\'s twenty-second load. Give it a deadline -- and tell me what "
 "happens if that thread is cancelled.", "functional", 8,
 "The three-argument <code>getOrLoad</code> is this answer. It waits with <code>get(timeout)</code> instead of "
 "<code>join</code>, so it throws <code>TimeoutException</code> when the deadline passes and "
 "<code>InterruptedException</code> if the thread is interrupted, both checked on purpose: a caller that asked "
 "for a deadline has to decide what to do when it arrives. The deadline bounds the <i>wait</i> and nothing else "
 "&mdash; the thread running the loader is never cut off by somebody else\'s impatience, and a load that hangs is "
 "bounded by wrapping the loader in <code>BoundedLoader</code> instead. Giving up starts no second load either, "
 "because the claim is still the winner\'s, so an impatient caller costs the database nothing. The interrupt is "
 "rethrown rather than swallowed, which is the rule to say out loud: the thread that was asked to stop is the "
 "thread that decides how. Tests 10 and 11 prove all of it, including that the loading thread finishes normally "
 "after a waiter beside it was interrupted.",
 sect(src, "    public V getOrLoad(K key, Loader<K, V> loader) {", "    /**\n     * The winner\'s path")
 + "\n" + sect(src, "    private static <T> T awaitUntil", "    /** A loader that returns null is a bug")
 + "\n" + T("        // 11. a waiter that is cancelled", "        // 12. the retry loop terminates")),
("Set the TTL to one millisecond and let the loader take thirty. A waiter now wakes to a value that is already "
 "dead. Does anybody starve in that loop?", "non-functional", 5,
 "No, and the reason is worth saying precisely rather than waving at. <code>getOrLoad</code> loops, and a second "
 "round only happens when the winner\'s value had already expired by the time the waiter was woken, which needs "
 "a TTL shorter than a load. Each extra round then does one of exactly two things: it finds a live value and "
 "returns, or it makes this thread the next winner, which means it runs the loader itself and returns its own "
 "value however briefly that value lives. So the number of rounds is bounded by the number of threads and not by "
 "time, and nobody spins without doing work &mdash; which is freedom from starvation, not fairness, and the "
 "difference is worth naming before the interviewer does. Test 12 makes it deterministic with a clock that jumps "
 "five milliseconds every time it is read: ten callers, ten loads, all ten return. The <code>staleJoins</code> "
 "counter exists so that in production this is something you can see rather than guess at.",
 T("        // 12. the retry loop terminates", "        // 13. the same wait protocol")),
("The sweeper is walking the map when another thread refreshes the very key it is holding. Show me the line that "
 "stops the fresh value being deleted, and the test for it.", "twist", 6,
 "The line is <code>map.remove(key, e)</code> instead of <code>map.remove(key)</code>. The two-argument form is a "
 "compare-and-remove: it deletes the mapping only if the value there is still the exact object the sweeper picked "
 "up, and CacheEntry deliberately does not override equals, so that comparison is object identity. If a refresh "
 "landed in between, the map holds a different object and the remove does nothing. The same line is in the read "
 "path, for the same reason. The test makes the interleaving deterministic with the seam move 3 already gave us: "
 "the sweeper reads the clock between picking the entry up and removing it, so a test clock that performs the "
 "refresh inside that read reproduces the race exactly, every run.",
 sect(src, "    int sweepOnce()", "    /**\n     * Start the background sweeper")
 + "\n" + T("        // 3. the identity check", "        // the same race on the read path")),

("Where does time come from, and how do you test a one-hour TTL without waiting an hour?", "design", 5,
 "Time comes from a one-method interface that is handed in, never from a call to System.nanoTime inside the "
 "cache. Production passes SystemClock, which uses nanoTime rather than currentTimeMillis so that an NTP "
 "correction cannot make a TTL run backwards. A test passes ManualClock and jumps it forward by an hour in one "
 "statement, so every TTL assertion is exact and instant &mdash; the whole failure-test file runs in under a "
 "second. It also buys the thing you cannot get any other way: because the clock is a collaborator, a test can "
 "hand in a clock with a side effect and reproduce a two-thread interleaving deterministically, which is how the "
 "sweeper race above is tested.",
 sect(src, "interface Clock", "/** How long a key is allowed to live")
 + "\n" + T("        // 1. an expired value is never handed back", "        // a TTL of zero means do not cache")),

("A hot key expires and every request for it now waits twenty milliseconds for the reload. Serve the old value "
 "instead, and refresh it behind the caller.", "twist", 10,
 "Give the entry a soft deadline in front of its hard one. A read past the soft deadline returns the value it "
 "already has, immediately, and kicks off exactly one background reload; a read past the hard deadline still "
 "blocks on a normal load, so a value can never be served indefinitely. The single-flight idea appears a second "
 "time here, for the reload: a putIfAbsent on a refreshing map means only one background thread is ever reloading "
 "a key. It is built on the public API only &mdash; get, getOrLoad and put &mdash; so TtlCache itself does not "
 "change. In the state machine it is one new state, REFRESHING, which is why move 12 calls this \"a new step in a "
 "life\".",
 X("refresh-ahead", "negative caching")),

("A scraper is asking for a million ids that do not exist. Every one of them is a miss and every one of them "
 "reaches the database.", "twist", 6,
 "Remember the absence as well as the value. A second cache, with a much shorter TTL, holds a tombstone for keys "
 "the loader said were not there, so a repeated lookup of a missing id is answered from memory for the tombstone "
 "window instead of becoming a query. The two TTLs are deliberately different: sixty seconds for a real value, "
 "five for a tombstone, because being wrong about an absence is cheap to fix and you do not want a row that "
 "appears a second later to stay invisible for a minute. The one thing it changes in the core is a rule that was "
 "already there: a loader returning null is an error in TtlCache, so negative caching is an explicit feature "
 "rather than a silent default.",
 X("negative caching", "a size bound")),

("This cache is unbounded. It has to fit in memory. Add a size bound.", "functional", 6,
 "The half of this answer that earns marks is why the bound cannot go <i>inside</i> TtlCache. The cache records "
 "nothing about reads &mdash; <code>get</code> touches no ordering at all, which is exactly why it takes no lock "
 "&mdash; so there is nothing in it to rank keys by. A bound therefore goes <i>on</i> it, as a wrapper that "
 "brings whatever state the victim rule needs. The one below keeps the cheapest such state, the order keys were "
 "written in, and evicts the oldest write: that is FIFO, not LRU, and calling it by its right name is the point. "
 "The bound is soft on purpose, because the size is read and then a victim is evicted, so a burst between those "
 "two steps overshoots by a handful of entries; Caffeine makes the same trade. Which key to throw away, and the "
 "O(1) structures that answer it in one step instead of a scan, belong to " + LRU_PAGE + " and " + EVICT_PAGE + ".",
 X("a size bound", "metrics")),

("Why not just use computeIfAbsent? It is one line and the JDK already does single-flight for you.", "design", 6,
 "Because computeIfAbsent holds the bin's lock for the whole mapping function. For a fast function that is "
 "perfect; for a loader that takes twenty milliseconds it means every other key that hashes to that bin is "
 "blocked behind a database round trip, and the bin is one of several thousand keys' homes, not just this one's. "
 "There is a second, harder failure: a loader that touches the same map &mdash; a cache that looks something else "
 "up, a listener that writes back &mdash; is refused outright, and the JDK reports it as \"Recursive update\", "
 "which the probe below reproduces deterministically by forcing two keys into one bin. A future in a separate map "
 "costs one extra map and gives the loader the freedom to be slow, to fail, and to touch anything it likes.",
 X("why not computeIfAbsent", "the monitor version")),

("size() is O(1) but it lies. What is the O(1) question this cache can actually answer, and what does the "
 "dashboard get?", "non-functional", 5,
 "size() returns the number of entries in the map, which includes entries that are past their deadline but have "
 "not been read or swept yet, so it is an estimate that runs high between sweeps. Saying that out loud is the "
 "answer the interviewer wants, because the alternative &mdash; an exact live count &mdash; needs a shared "
 "counter updated on every write and every expiry, which is exactly the one global bottleneck the design avoids. "
 "liveSize() gives the exact number and is O(n), which is fine for a test or a once-a-minute metric and wrong for "
 "a hot path. What the dashboard actually wants is not a size but a hit rate, and that is O(1): seven LongAdders, "
 "summed on demand, which is also why they are LongAdders and not AtomicLongs.",
 sect(src, "    public int size()", "    /**\n     * One sweep")
 + "\n" + nobrace(sect(src, "    /** The counters an interviewer asks for", "/**\n * A demo of the three things"))),

("Two servers now. A write on one leaves the other one stale, and a restart empties both.", "twist", 8,
 "Three moves, in the order you would make them. The entries go into Redis with the deadline handed to the store "
 "rather than tracked in the process, so expiry is the store's job and a restart loses nothing. The in-process "
 "cache stays, in front of it, with a much shorter TTL, because a network hop to Redis is still a hundred "
 "microseconds and a local hit is forty nanoseconds. And the claim becomes a lease: SET lock:key owner NX PX "
 "5000, which is the same compare-and-set one layer out, with a TTL on the claim itself so a server that dies "
 "mid-load does not block the key forever. Invalidation travels by PUBLISH, and each process drops its own copy "
 "when it hears. The thing that does not change is the shape: the same claim, the same identity check, the same "
 "order at the critical step.",
 X("two processes", "Runs every extension")),

("Caffeine does all of this in one builder call. What did the JDK actually give you here, what did you have to "
 "write yourself, and when would you just use the library?", "design", 5,
 "Four things came free from <code>java.util.concurrent</code>, and each replaced something that is easy to write "
 "badly: <code>ConcurrentHashMap</code> is the per-bin locking and the lock-free read; "
 "<code>CompletableFuture</code> is the wait protocol, with no flag to forget and no monitor to hold; "
 "<code>ScheduledExecutorService</code> is the one daemon sweeper, on a fixed delay so passes cannot queue up "
 "behind each other; <code>LongAdder</code> is the counter that does not itself become the contention point. "
 "What the JDK did not give you is the design: the deadline on the entry, the compare-and-remove that protects a "
 "refresh, the claim map that turns a stampede into one load, and the order &mdash; publish, then complete, then "
 "release. In real code you use Caffeine, and saying so is a senior answer rather than a cop-out: it does all of "
 "the above plus admission control, a size bound, refresh-ahead and cleanup with no dedicated thread, in one "
 "dependency. Write it by hand when you need behaviour it does not have, or when an interviewer asks you to.",
 "// what the JDK already did for you, and the line of this design that uses it\n"
 "ConcurrentHashMap<K, CacheEntry<V>> map;       // per-bin locks; a get takes none at all\n"
 "ConcurrentHashMap<K, CompletableFuture<...>> loading;  // the claim: one CAS, no lock\n"
 "CompletableFuture.complete(entry) / join();    // the wait protocol, latch not bell\n"
 "Executors.newSingleThreadScheduledExecutor();  // one daemon sweeper, fixed delay\n"
 "new LongAdder();                               // counters that do not serialise the hot path\n\n"
 "// what you still had to design, and what an interviewer is actually grading\n"
 "new CacheEntry<>(value, now, now + ttlMsFor(key));  // an absolute deadline, on the entry\n"
 "map.remove(key, e);                                 // identity, so a refresh survives a sweep\n"
 "map.put(key, fresh); mine.complete(fresh);          // publish, THEN signal -- never the reverse\n\n"
 "// and what you would actually run in production\n"
 "// LoadingCache<String,Row> c = Caffeine.newBuilder()\n"
 "//     .expireAfterWrite(Duration.ofSeconds(60)).maximumSize(10_000)\n"
 "//     .refreshAfterWrite(Duration.ofSeconds(30)).build(this::loadRow);\n"),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?",
 "design", 8,
 "None of the patterns was chosen up front, and the code below is each one as a single line: Strategy is move 3, "
 "because how long a key lives is a rule that changes, so it is a one-method interface the cache is handed; "
 "Decorator is the same move's wrapper, JitteredTtl; Observer is the fourth rule handed in there, and move 4 is "
 "only where it was decided that it fires <i>after</i> the write; State is move 6, the entry's life; and the "
 "multi-threading one is the Future, which here is a handle on somebody's result rather than a condition "
 "variable. SOLID is the table in move 11, and the letter to defend under pressure is D: <code>configure()</code> "
 "is the whole test seam, which is the difference between testing a one-hour TTL in a millisecond and not testing "
 "it at all. Factory earns its name the day the rules arrive as text rather than as Java, which is "
 "<code>TtlRules.parse</code>; Builder at about the sixth optional collaborator, which is "
 "<code>Caffeine.newBuilder()</code>. And the part people fumble, enum against subclass: the TTL rule is "
 "deliberately not an enum, because an enum of TTLs has to be edited for every new key prefix, whereas a rule "
 "handed in is a new class and no edit at all.",
 "// Strategy: a rule behind a one-method interface, handed in, never built by the cache\n"
 "interface TtlPolicy<K> { long ttlMsFor(K key); }\n"
 "void configure(TtlPolicy<K> ttl, Clock clock) { this.ttl = ttl; this.clock = clock; }\n\n"
 "// Decorator: add jitter to every rule, present and future, instead of copying the arithmetic\n"
 "new JitteredTtl<>(new FixedTtl<>(60_000), 20);\n\n"
 "// Observer: the cache announces; it does not know what a metric is, and a broken one cannot break a put\n"
 "for (RemovalListener<K, V> l : listeners) try { l.onRemoval(key, value, cause); } catch (RuntimeException ignored) { }\n\n"
 "// State: the entry's life, and the compare-and-set that owns the LOADING slot for one key\n"
 "// ABSENT -> LOADING -> LIVE -> EXPIRED -> ABSENT\n"
 "CompletableFuture<CacheEntry<V>> running = loading.putIfAbsent(key, mine);\n\n"
 "// Future: the wait protocol. A loser holds a handle on a result; it does not hold a lock.\n"
 "CacheEntry<V> e = await(running);\n\n"
 "// Factory: not yet -- it earns the name the day the rules arrive as text\n"
 "TtlRules.parse(\"user:=300000, price:=2000, =60000\");\n\n"
 "// Builder: not yet -- three required collaborators is a constructor; ten optional ones is Caffeine.newBuilder()\n"
 "TtlCache<String, String> cache = new TtlCache<>(60_000);\n"
 "cache.configure(new FixedTtl<>(60_000), new SystemClock());\n"),
]

build(dict(
    slug="mt-ttl-cache", title="TTL Cache",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: multi-threading round &mdash; demo, 13 failure tests and a 50-thread stampede",
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
