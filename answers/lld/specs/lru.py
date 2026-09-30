# LRU / LFU cache LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"lru/Main.java").read_text()
ext   = (H/"lru/Extensions.java").read_text()
tests = (H/"lru/FailureTests.java").read_text()

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
rows = [("get", 30, [("key K: is it here?", "one hash lookup, no walk"),
                     ("present, and still fresh?", "an expired entry is a miss"),
                     ("move it to the front", "a read counts as a use"),
                     ("return the value", "nothing is allocated")]),
        ("put", 175, [("key K, value V", "insert, or overwrite in place"),
                      ("full? the oldest leaves FIRST", "never one over capacity"),
                      ("link it at the front", "map and list, in one step"),
                      ("tell the listener", "after the unlock, never inside")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V100", dash=True)
pf += _bx(360, 100, 500, 44, "a miss: the loader runs with no lock held", "its value is written only if no put or remove came meanwhile", dash=True)
pf += _tx(88, 272, "read", "var(--acc)", 13)
pf += _tx(175, 272, "the value for this key (one hash lookup);  which entry would leave next (the tail of the list);  how many are resident (a count)", "var(--text)", 12, "start")
pf += _tx(88, 302, "remove", "var(--acc)", 13)
pf += _tx(175, 302, "unlink from the list and delete the map row in the same step, then tell the listener the cause was REMOVED", "var(--text)", 12, "start")
pf += _tx(615, 340, "fifty threads call get and put at the same instant: the map and the list must always name exactly the same keys, and the count must never exceed the capacity", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 354, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:00:00  put A, B, C", ["a cache of three, now full", "newest first: C  B  A", "A is the next to go"], False),
      ("09:00:01  get A -- a hit", ["A moves to the front", "newest first: A  C  B", "B is the next to go now"], True),
      ("09:00:02  put D", ["full, so B is unlinked first", "then D is linked at the front", "the count is 3 the whole time"], True),
      ("09:01:03  get B -- a miss", ["B left a minute ago", "the loader reads Postgres: 5 ms", "no lock held, then B is written"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 110, t, lines, acc=acc)
P_EX = _mv(1230, 185, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>get(key): the value, or nothing if it is not there &mdash; and a read counts as a use.</li>
<li>put(key, value): insert a new entry, or overwrite an existing one in place.</li>
<li>A fixed capacity: a put that would go over it evicts the entry that has gone longest without use.</li>
<li>remove(key), size(), capacity(), and the order in which entries would be given up.</li>
<li>Tell somebody when an entry leaves, and why: full, expired, overwritten, or removed.</li>
<li>On a miss, optionally fetch the value from wherever it really lives and keep it (read-through).</li>
<li>Optionally expire an entry a fixed time after it was written, or after it was last used.</li>
<li>Swap the rule for who leaves: least-recently-used today, least-frequently-used on request.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>get, put and remove are O(1): one hash lookup and a fixed number of pointer writes, never a scan.</li>
<li>Many threads at once: the map and the order must never be seen disagreeing.</li>
<li>The count must never exceed the capacity, not even for an instant inside a put.</li>
<li>Memory bounded by the capacity and nothing else; no allocation on a hit.</li>
<li>The eviction policy swappable without editing a single caller.</li>
<li>Nothing slow inside the lock: a database read is milliseconds, the lock is nanoseconds.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design an LRU cache. Fixed capacity, generic key and value, and both get and put have to be O(1). '
          'When it is full the least-recently-used entry goes. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A box that remembers a fixed number of answers, so '
 'that the slow thing behind it (a database, an API, a computation) is asked as rarely as possible. A caller '
 'asks for a key: if the box has it, hand back the value; if not, say so. A caller writes a key and a value: '
 'store it, and if the box is already full, throw out the entry that has gone longest without being used. The '
 'catch is the word <i>both</i> in "both get and put are O(1)". A hash map finds a value instantly but has no '
 'idea which entry is stalest; a list knows the order but cannot find a key without walking it. Neither is '
 'enough alone, so the answer is both at once, over the same objects. A read is a use, so even get changes the '
 'order. That is what makes the concurrency question interesting: there is no pure reader here (a caller that '
 'only looks and changes nothing). Many threads hammer one cache. The invariant (the one thing that must always '
 'be true) is this: the map and the order hold exactly the same keys, and the count never goes above the '
 'capacity.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that fills a small cache, reads one entry, and shows the right key being evicted. The '
 'interviewer watches for these, in order: the questions you ask before typing (thread safety and what happens '
 'on a miss come first); which classes exist, and which one owns the two indexes; and get and put end to end, '
 'with the key stored <i>inside</i> the node. Then what happens when two threads put into a full cache at the '
 'same instant. Then where the rules that will change live (the policy, the loader, the listener), so that "now '
 'make it LFU" (least frequently used) is a new class and not an edit. And what happens when the database behind '
 'the loader is down. Then the twists: LFU; a policy picked when the cache is built; TTL; several cache levels; '
 'hit-rate stats; surviving a crash; striping; why one nightly scan can empty the whole cache; and what Caffeine '
 'actually ships. TTL is time to live: an entry expires a set time after it is written, or after it was last '
 'used. Striping splits one cache into parts, each with its own lock. Caffeine is the standard Java cache '
 'library.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Is the capacity a count of entries, or a budget in bytes?</td><td>A count of entries, fixed at construction</td><td>One <code>if</code> before an insert, not a loop of evictions (moves 5, 12)</td></tr>'
 '<tr><td>Will several threads share one cache?</td><td>Yes</td><td>One lock inside the cache, and no pure readers (moves 4, 7)</td></tr>'
 '<tr><td>On a miss: return nothing, or fetch it?</td><td>Return nothing by default; a loader can be handed in</td><td>A one-method loader, called outside the lock (moves 3, 6)</td></tr>'
 '<tr><td>Is it only capacity that evicts, or do entries also expire?</td><td>Capacity by default; a TTL can be switched on, counted from the last write or the last use</td><td>An expiry stamp on the node and an injected clock (moves 1, 6)</td></tr>'
 '<tr><td>Does anybody need to be told when an entry leaves?</td><td>Yes: a write-back store (it saves each leaving value to the database) and a metric</td><td>A listener, called after the unlock (moves 3, 4)</td></tr>'
 '<tr><td>Will the policy change &mdash; LFU, FIFO (first in, first out), weighted?</td><td>Yes, LFU before the hour is out</td><td>The <code>Cache</code> interface is the seam (the point where one class swaps for another), not a flag (move 3)</td></tr>'
 '<tr><td>Null keys and null values?</td><td>Neither; null is how a miss is reported</td><td>Two null checks and no ambiguity at the boundary (move 9)</td></tr>'
 '<tr><td>One process, in memory?</td><td>Yes</td><td>No shared store yet; a follow-up adds one (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> capacity is a fixed count of entries; a read counts as a use; the '
 'cache is shared by many threads, so it holds its own lock; null is how a miss is reported, so neither keys nor '
 'values may be null; and the eviction policy is a whole implementation of one interface, not a flag. Named as '
 'out of scope: bounding by bytes, striping, persistence, a background sweeper &mdash; each is a follow-up on '
 'page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: the nouns with state
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a CACHE of a fixed CAPACITY holds ENTRIES; a KEY finds a VALUE; the ORDER OF USE decides the VICTIM", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 180, "Cache", "map, order, capacity", 1), (228, 180, "Entry / Node", "key, value, two links", 1),
                          (426, 190, "Order", "which end is oldest", 1), (634, 150, "Key", "no state: a lookup", 0),
                          (802, 180, "Value", "the caller's object", 0), (1000, 200, "Victim", "a question: a method", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a lookup, the caller's object, or a question", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("find the value for a key", "the map  (owns key -&gt; node)", "index.get(key)"),
                                       ("say \"this was just used\"", "RecencyList  (owns the links)", "order.moveToFirst(n)"),
                                       ("choose who leaves", "the policy: LruCache or LfuCache", "order.last()"),
                                       ("insert, evict, tell somebody", "LruCache  (map + order + lock)", "cache.put(k, v)")]):
    y = 20 + k*52
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 245, "a verb whose state is spread over two indexes goes to the class that owns both: that class becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 265, "and notice that \"get\" is a verb that WRITES: it changes the order. There are no pure readers here, which decides move 4.", "var(--acc)", 11)
MV[2] = _mv(1230, 278, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 55, 230, 100, "LruCache / LfuCache", "configure(loader, listener)", acc=True)
for k, (t, sub, impl) in enumerate([("CacheLoader", "where a miss goes", "a database read, an HTTP call, a lambda"),
                                    ("EvictionListener", "write-back, stats, metrics", "WriteBackListener, WriteBehind, a lambda"),
                                    ("Clock", "now, in milliseconds", "System::currentTimeMillis, a test's instant")]):
    y = 20 + k*58
    m3 += _ar("M260 105 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 205, "dashed green = handed in. The cache never builds a rule, which is why a test can hand it a loader that throws.", "var(--muted)", 11)
m3 += _tx(615, 227, "and the biggest seam is Cache itself: \"now evict the least-FREQUENTLY used\" is a whole new class and one constructor line -- Strategy.", "var(--acc)", 11)
m3 += _tx(615, 249, "a wrapper that ADDS to a cache instead of replacing it (hit-rate stats, locking, a de-duplicating loader) is Decorator.", "var(--muted)", 11)
MV[3] = _mv(1230, 262, m3)

# move 4: the gap, one owner, one lock
m4 = _D + _bx(30, 30, 190, 44, "thread 1", "sees 100 of 100") + _bx(30, 110, 190, 44, "thread 2", "sees 100 of 100")
m4 += _bx(350, 70, 190, 44, "the tail node", "the oldest entry", acc=True)
m4 += _ar("M220 52 H350 V70") + _ar("M220 132 H350 V114") + _tx(285, 40, "read", "var(--muted)", 10.5) + _tx(285, 162, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="20" width="290" height="150" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(725, 45, "the gap", RED, 12) + _tx(725, 70, "both unlink the same node", RED, 11) + _tx(725, 90, "one prev pointer is written twice", RED, 11)
m4 += _tx(725, 110, "the list loops; the map leaks a row", RED, 11)
m4 += _tx(725, 148, "fix: look, evict and insert as ONE step", "var(--text)", 11)
m4 += _bx(900, 45, 300, 100, "LruCache.lock", "find + evict + insert = one step", acc=True)
m4 += _tx(1050, 168, "the lock lives where the two indexes live", "var(--muted)", 10.5)
m4 += _tx(1050, 188, "the loader and the listener stay outside it", "var(--muted)", 10.5)
MV[4] = _mv(1230, 202, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("the value for this key?", "Map&lt;K, Node&gt;", "O(1)"),
                                      ("which entry leaves next?", "a doubly linked list, tail = oldest", "O(1)"),
                                      ("unlink this node, from the middle", "prev / next on the node + sentinels", "O(1), no walk"),
                                      ("which map row does the victim own?", "the KEY rides inside the node", "O(1) delete"),
                                      ("the least-FREQUENTLY used?", "Map&lt;count, list&gt; + the smallest count", "O(1)")]):
    y = 20 + k*50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 288, "a hash map has lookup without order; a list has order without lookup; the whole trick is that both point at the SAME node object", "var(--muted)", 11)
MV[5] = _mv(1230, 302, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(30, 30, 200, 44, "ABSENT", "not in the cache")
m6 += _bx(300, 30, 200, 44, "RESIDENT", "in the map and the list", acc=True)
m6 += _bx(300, 125, 200, 44, "EXPIRED", "its time ran out")
m6 += _bx(30, 125, 200, 44, "EVICTED", "full, or a caller removed it")
m6 += _ar("M230 52 H300", True) + _tx(265, 44, "put", "var(--acc)", 10.5)
m6 += _ar("M400 74 V125", True) + _tx(470, 103, "the ttl passes", "var(--muted)", 10.5)
m6 += _ar("M300 147 H230", True) + _tx(265, 186, "the read that finds it unlinks it", "var(--muted)", 10.5)
m6 += _ar("M130 125 V74", True) + _tx(70, 103, "gone", "var(--muted)", 10.5)
m6 += _ar("M330 74 L240 121", True) + _tx(300, 108, "full", "var(--muted)", 10.5)
m6 += _card(560, 20, 650, 165, "the order inside put, and why it is this order",
            ["1 take the lock; already here? then it is ONE node: overwrite and move it up",
             "2 not here and full: unlink the oldest AND delete its map row, in one step",
             "3 only now link the newcomer and put it in the map: the count is never capacity + 1",
             "4 release the lock, and only then tell the listener, inside a try/catch",
             "a miss takes a TICKET, then loads with no lock held; it writes only if the ticket",
             "survived: a database that is down, or a put or remove meanwhile, changes nothing"], acc=True)
m6 += _tx(615, 208, "four states and one rule: nothing is linked until the entry it replaces is gone; look, decide and change are one step", "var(--muted)", 11)
MV[6] = _mv(1230, 222, m6)

# move 7: inside the lock, and sixty-four callers at the same instant
m7 = _D + _card(30, 20, 540, 155, "inside the lock: about 80 nanoseconds",
                ["one hash lookup on the key", "four pointer writes to unlink a node",
                 "four more to link it at the front", "one map put, and on an eviction one map remove",
                 "a dozen machine-level steps, and no allocation"], acc=True)
m7 += _ar("M570 97 H640", True) + _tx(605, 87, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 155, "outside the lock: microseconds to milliseconds",
            ["the loader on a miss: about 5 ms to Postgres", "the write-back listener: about 2 ms to the store",
             "serialising the value for the wire: about 10 us", "the caller doing something with the value"])
m7 += _tx(615, 202, "sixty-four threads call get at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "thread %d" % (k+1), "waits %d ns" % (k*80), acc=(k == 9))
m7 += _tx(615, 283, "the tenth waits 720 nanoseconds and the sixty-fourth about five microseconds, against the five milliseconds it would", "var(--muted)", 11)
m7 += _tx(615, 301, "have spent on a miss anyway. One at a time is true, and nobody can tell -- unless the loader gets inside the lock.", "var(--muted)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="196" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one lock on a hot cache: do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of a get: about 80 nanoseconds",
                       "a product cache: 200,000 gets a second, 64 threads",
                       "200,000 x 80 ns = 16 ms of lock in every second",
                       "1.6% busy: a thread almost never finds it taken",
                       "at 5 million ops a second it is 40% busy: now they queue"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(35, 196, "one 5 ms load inside the lock would undo every bit of this", RED, 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 keep the loader and the listener outside the lock", "already done: 5 milliseconds must never sit inside 80 nanoseconds"),
                              ("2 stripe into 16 segments by key hash", "16 locks, capacity/16 each: approximate LRU, which is what Guava ships"),
                              ("3 buffer the reads, and put a door on the cache", "reads go to a buffer, replayed later; a sketch keeps one-off keys out: Caffeine")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 230, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("a read does not count as a use", "move to the front on a read; test 1: the key just read is the one that survives"),
                                ("insert first, evict afterwards", "evict first; test 5: the count is never seen above capacity, in 20,000 puts"),
                                ("the map and the list drift apart", "both written in one step; test 5: the list walk equals the map's key set"),
                                ("an overwrite makes a second node", "overwrite in place; test 2: three puts of one key leave one entry"),
                                ("the loader fails, or races a put", "load outside the lock with a ticket; tests 4, 11, 12: nothing stale is written"),
                                ("the write-back listener throws", "notify after the unlock, in a try/catch; test 6: the put still stands"),
                                ("a stale value is served for ever", "lazy expiry on the read; test 7: an injected clock, then a miss"),
                                ("LFU evicts the newest of a tie", "each frequency bucket is itself an LRU list; test 8: the older one leaves"),
                                ("a scan evicts the working set", "a door: the newcomer must beat the victim; test 10: all 40 hot keys survive")]):
    y = 18 + k*40
    m9 += _bx(30, y, 320, 36, bad, "") + _ar("M350 %s H380" % (y+18), True) + _bx(380, y, 820, 36, fix, "", acc=True)
m9 += _tx(615, 398, "every claim this design makes has a failure test: FailureTests.java runs twenty-one blocks, sixty checks, and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 412, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 860)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("new LfuCache&lt;&gt;(1000) / new AdmissionLruCache&lt;&gt;(1000): the policy IS the class", None), ("swap the rule without opening a caller", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new StatsCache&lt;&gt;(cache);  new SingleFlightLoader&lt;&gt;(loader)", None), ("stats and de-duplication, cache untouched", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("fire(key, value, CAPACITY) after the unlock, in a try/catch", None), ("the store hears; the cache never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("EvictionCause, and the ABSENT / RESIDENT / EXPIRED order", None), ("an entry cannot be half-evicted", None)],
          [("Builder", "var(--acc)"), ("move 3", None), ("CacheBuilder.newBuilder().maximumSize(1000).expireAfterWrite(60s)", None), ("six optional knobs: here it EARNS its place", None)],
          [("Template Method", "var(--muted)"), ("not earned", None), ("LockedCache holds state and helpers; it does not own get or put", "var(--muted)"), ("either cache can be read on its own", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("a cache is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh one", "var(--muted)")],
          [("Factory", "var(--muted)"), ("in build()", None), ("lfu ? new LfuCache&lt;&gt;(n) : new LruCache&lt;&gt;(n) -- one line", "var(--muted)"), ("it grows a name when policies come from config", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Node holds links. RecencyList splices. LruCache owns the policy and the lock.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("LfuCache, StatsCache and AdmissionLruCache all exist; LruCache was never opened", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("cache.get(key);  never \"is this the LFU one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Clock, CacheLoader, EvictionListener: one method, so a fake is a lambda", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("cache.configure(loader, listener);  cache.setClock(() -&gt; now[0])", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "LFU, weighted by bytes, a door on the front", "a new class behind Cache; not one caller changes", "", "move 3"),
        ("someone new wants to know", "hit rate, write-back, metrics", "one more listener, or one more wrapper around Cache", "", "move 4"),
        ("a new step in a life", "expired, dirty, in flight", "one more cause and one more checked transition", "", "move 6"),
        ("a new invariant across entries", "a budget in bytes, not entries", "the check AND the loop of evictions inside the SAME lock", "", "move 4"),
        ("state that must outlive the process", "a crash; Redis in front of the database", "a log replayed on restart, or the far store as the loader", "and a conditional UPDATE by version, plus an invalidation message", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five, Node, RecencyList and the failure tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: a <b>cache</b> of a fixed <b>capacity</b> holds <b>entries</b>; a <b>key</b> finds a "
 "<b>value</b>; the <b>order of use</b> decides the <b>victim</b>. The cache holds the capacity, the map and the "
 "order, all of which change: a class. An entry has a key, a value and a place in the order. That place is not "
 "a number but two pointers, so the entry <i>is</i> the list node. The order has its own state (which end is "
 "newest, which node follows which), so it is a class too. A key is something you look up, and a value is the "
 "caller's object that the cache never opens. A victim is not a thing to store at all: it is a question the "
 "order answers, so it is a method. Two decisions fall out here, and both cost you later if you miss them. "
 "First, the key goes <i>inside</i> the node. Eviction starts at the order and then has to delete that entry "
 "from the map, and without the key in hand that delete is a scan. Second, if there is a TTL, the expiry stamp "
 "goes on the node too, because it belongs to the entry and to nothing else.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Find the value for a key\" touches the map, so it is <code>index.get(key)</code>. \"Say this was just used\" "
 "touches the two pointers, so it belongs to the thing that owns them: <code>order.moveToFirst(n)</code>. "
 "\"Choose who leaves\" is the policy's own question: for LRU it is the tail of the list, for LFU the tail of the "
 "least-used bucket. \"Insert, evict and tell somebody\" touches the map, the order and the lock at once. Only the "
 "cache sees all three, so <code>cache.put(k, v)</code> is the orchestrator (the method that runs the whole "
 "flow). Now notice what this move exposes, which no other problem on this list has: <code>get</code> is a verb "
 "that <i>writes</i>. A read moves a node to the front, so there is no such thing as a pure reader here. That "
 "single fact decides move 4. A read-write lock (one that lets many readers in together, but a writer only "
 "alone) would buy nothing, because there is nobody to let in together.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Three small rules will change, and one big one. Where a miss goes will change: nowhere today, a database read "
 "tomorrow. That is <code>CacheLoader</code>, one method. Who is told when an entry leaves will change: nobody "
 "today, a write-back store and a metrics counter tomorrow. That is <code>EvictionListener</code>. Where "
 "<i>now</i> comes from will change the moment somebody asks for a TTL and you have to test it: that is "
 "<code>Clock</code>. All three are handed in through <code>configure()</code> and <code>setClock()</code>. The "
 "cache never builds them, which is exactly why a test can hand it a loader that throws. The big one has a "
 "different shape. Here the eviction policy is not a rule you plug into a cache: it <i>is</i> the cache, because "
 "LFU needs its own layout of the entries. So the seam is the <code>Cache</code> interface itself. LFU is a whole "
 "new class that nothing else has to notice. When a prompt says users pick the policy as they build the cache, use the other shape, question 2 on "
 "page 05. This is where the patterns come from, not the other way round. A swappable rule behind an interface "
 "is <b>Strategy</b>. A wrapper that adds to a cache instead of replacing it is <b>Decorator</b>. A cache that "
 "announces \"this left\" without knowing what a store is, is <b>Observer</b>. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two threads put a new key into a full cache at the same instant. Both read the count as one hundred of one "
 "hundred, both take the tail, and both unlink the same node. One thread writes <code>prev.next</code> after the "
 "other has already moved it. The list ends up pointing at a node that is no longer in it, and the map keeps a "
 "row for a key the order has forgotten. Nobody notices until the cache quietly stops evicting. So the lookup, "
 "the eviction and the insert must be one step, in the class that owns both indexes: the cache. The lock goes "
 "<i>inside</i> the cache, not in a wrapper around it, and the reason is worth saying out loud. Only the owner "
 "of a lock can release it and <i>then</i> call the listener. A wrapper whose methods are all "
 "<code>synchronized</code> is correct and five lines long. But it drags the loader and the write-back into the "
 "critical section (the code that runs while the lock is held). "
 "Extensions.java has that wrapper, with the cost written on it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"The value for this key\" is a hash map. \"Which entry leaves next\" is the tail of a list. \"Unlink this node "
 "from the middle\" is why the list is <i>doubly</i> linked. With only forward pointers you would have to walk "
 "to find the node before it, and the O(1) claim collapses. Two sentinel nodes (dummy nodes that always sit at "
 "the two ends) remove every empty-list and one-element check. So both splices (the few pointer writes that "
 "unlink or link a node) are straight-line code. \"Which map row does the victim own\" is answered by keeping the "
 "key inside the node. And \"the least-frequently used\" is a map from use-count to a list, plus the smallest "
 "count in use. That makes LFU O(1), where a heap (a tree that keeps the smallest item on top) would be "
 "O(log n). The whole trick, in one sentence: a hash map has lookup without order, a list has order without "
 "lookup, and both point at the same node object.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An entry is ABSENT, then RESIDENT when a put links it. It becomes EVICTED when the capacity or a caller pushes "
 "it out, or EXPIRED when its time runs out and the next read unlinks it. Writing the states down forces the "
 "questions the interviewer will ask, and each answer is an <i>order</i> of steps, not a mechanism. What if the "
 "database behind the loader is down? The load runs outside the lock, before anything is written, so the "
 "exception reaches the caller and the cache is exactly what it was: nothing half-filled, and a retry just "
 "works. What if a put or a remove of the same key lands while the load is running? Before it loads, a miss "
 "takes a ticket; a put or remove of that key tears the ticket up; and the load writes only if its ticket is "
 "still there. Without it, a slow load could overwrite a newer put, or bring back a row that was just removed. "
 "(Facebook's memcache paper calls this ticket a lease.) What if the cache is full? Unlink the oldest node and "
 "delete its map row as one step, and only then link the newcomer, so the count is never capacity plus one. An "
 "existing key is a third case and a common bug: it is one node overwritten in place, never a second node.", 6),
("Move 7: yes, the lock makes reads happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every get takes the lock, has the cache become a "
 "queue? It has, for about eighty nanoseconds. That is one hash lookup and eight pointer writes: four to unlink "
 "the node, four to link it at the front. An insert adds one map put and maybe one map remove, and nothing is "
 "allocated. Everything slow is outside it. The loader is five milliseconds against Postgres and runs before "
 "anything is written; the write-back listener is two milliseconds and runs after the unlock. So when sixty-four "
 "threads call get at the same instant, the sixty-fourth waits about five microseconds, against the five "
 "milliseconds a miss would have cost it anyway. One at a time is true, and nobody can tell. Put the loader "
 "inside the lock and that same thread waits three hundred milliseconds, which is how a cache becomes the "
 "slowest part of the system.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Two hundred thousand gets a second across sixty-four threads, at eighty nanoseconds of lock each, is sixteen "
 "milliseconds of lock in every second: 1.6 per cent busy. A thread almost never finds the lock taken, so the "
 "honest answer to \"does one lock scale\" is yes, for this traffic. Unlike a car park, though, a cache really "
 "can get hot. At five million operations a second the same lock is forty per cent busy, and threads queue. "
 "Rung one is already built, and it is worth more than the other two together: five milliseconds of loader "
 "inside the critical section would undo all of that arithmetic. Rung two is striping, and it costs you the thing "
 "the design is named for. Sixteen segments have sixteen recency orders, so there is no global one any more: "
 "this is approximate LRU, which is exactly what Guava (Google's core Java library) ships. Rung three is what Caffeine does, and it is two "
 "ideas. A hit records itself in a small buffer (one of a few, picked by the thread) instead of splicing the "
 "shared list, and one thread replays the buffer later under the lock. And a frequency sketch (a small table of "
 "counters that estimates how often each key is asked for) decides what is allowed <i>in</i>, so a one-off scan "
 "cannot flush the cache. Say the arithmetic before you climb; a ladder without it is complexity nobody asked "
 "for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "A read that does not count as a use (the cache then evicts exactly the keys it is busiest with). Inserting "
 "before evicting (the count goes one over capacity: the easiest bug here to spot if the interviewer watches the "
 "size). The map and the list drifting apart (unlink from both in one step, or a row leaks for ever). An "
 "overwrite creating a second node. The database behind the loader being down, or a put racing the load (the "
 "ticket: nothing stale is written, and the retry works). A write-back listener that throws (it runs after the "
 "unlock, in a try/catch). A stale value served for ever (expiry is checked on the read that finds it). And LFU "
 "breaking a tie by the wrong rule (each frequency bucket is itself a recency list, so of two entries used once, "
 "the one used longer ago leaves). The last row is not a bug at all, and it is the one that actually costs "
 "money. A nightly report reads a million rows, and each one is the most recently used entry the moment it "
 "arrives. By morning the working set (the keys real users keep asking for) is gone. No eviction rule fixes that; an "
 "<i>admission</i> rule does, and it is question 11 on page 05. FailureTests.java runs twenty-one blocks and "
 "sixty checks; a design that cannot show its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Strategy is move 3, and here it is unusually clean. The policy is not a field on the cache; it is the whole "
 "implementation, so LRU, LFU and the admission cache are three classes behind one interface. Decorator is the "
 "same move's wrapper, and this problem has three. <code>StatsCache</code> counts hits from outside; "
 "<code>SynchronizedCache</code> adds a lock; and <code>SingleFlightLoader</code> wraps one loader in another, so "
 "that a thousand simultaneous misses on one key make one database call. Observer is move 4's rule that a slow "
 "listener runs after the unlock; State is move 6. And here is the one that differs from every other problem in "
 "this set: <b>Builder earns its place</b>. Capacity, TTL, policy, loader, listener, clock and stats are seven "
 "knobs, and six are optional. A seven-argument constructor full of nulls is worse than a chain of named calls, "
 "which is exactly why Guava ships <code>CacheBuilder</code> and Caffeine ships <code>Caffeine.newBuilder()</code>. "
 "The rule has not changed; the optional fields have.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is the answer. What is worth saying out loud is that only one letter has a real trap on this "
 "problem. L says any implementation can stand in for another, and nothing asks which one it got. But a "
 "decorator that forgets to delegate <code>size()</code>, or a policy that quietly stops moving a key to the "
 "front on a read, breaks that promise <i>while still compiling</i>. Neither mistake fails to build and neither "
 "throws; the cache just gets slowly worse, which is the kind of failure that survives code review. That is "
 "what the failure tests are for. Test 1 catches a policy that stopped moving keys on a read; a wrapper that "
 "under-reports the size shows up the first time the dashboard disagrees with the cache.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (LFU, weighted by bytes, an admission door) is a new class behind <code>Cache</code>, and not one "
 "caller changes. Someone new who wants to know is one more listener or one more wrapper. A new step in an "
 "entry's life is one more cause and one more checked transition. A new invariant across entries (a budget in "
 "bytes instead of a count) is the check <i>and</i> a loop of evictions, inside the same lock. It is a loop "
 "because one big value can push out several small ones. And state that must outlive the process is a log or a "
 "shared store. Either the cache appends every change to a file before making it, and replays the file on "
 "restart. Or the far store becomes the loader, and its write becomes a conditional update (write only if my "
 "version is newer than the stored one). An invalidation message then tells the other servers to drop their copy. For all five, "
 "<code>Node</code>, <code>RecencyList</code> and the failure tests do not change; that is the test that the "
 "derivation was right. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, Splitwise) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order. Nothing is chosen up front, and nothing is "
 "named before the move that produced it. On this problem two moves do the heavy lifting: move 5, because the data "
 "structures ARE the design, and move 2, because it is where you notice that a read writes.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the rules handed in, their implementations, and the two decorators
put("clock", 10, 20, 250, "Clock", [], ["nowMs(): long"], "interface")
put("loader", 10, 100, 250, "CacheLoader", [], ["load(key): V"], "interface")
put("listener", 10, 180, 250, "EvictionListener", [], ["onEvict(key, value, cause)"], "interface")
put("wb", 10, 265, 250, "WriteBackListener", [], ["onEvict(...): store.put(k, v)", "log(): what it saw"])
put("stats", 10, 390, 250, "StatsCache", ["inner: Cache", "hits / misses: AtomicLong"], ["get / put / remove: delegate", "hitRate(): double", "summary(): String"], stereo="Extensions.java")
put("striped", 10, 545, 250, "StripedCache", ["segments: LruCache[16]", "-- approximate LRU"], ["segmentFor(key)", "get / put / remove: delegate"], stereo="Extensions.java")
put("admit", 10, 690, 250, "AdmissionLruCache", ["index, order: as LruCache", "sketch: FrequencySketch"],
    ["get(key) / put(key, value)", "-- the newcomer must beat", "   the victim to get in"], stereo="Extensions.java")
# centre: the contract, the shared plumbing, and the two policies
put("cache", 430, 20, 350, "Cache", [], ["get(key): V", "put(key, value): V", "remove(key): V", "size() / capacity(): int", "evictionOrder(): List&lt;K&gt;"], "interface")
put("locked", 430, 200, 350, "LockedCache", ["lock: ReentrantLock", "loader, listener: handed in", "clock: Clock", "ttlMs, restartOnRead", "loading: key -&gt; ticket"],
    ["configure(loader, listener)", "setClock(c) / setTtlMs(ms, onRead)", "stamp() / expired(n) / touched(n)", "start / finish / cancelLoad(key)", "fire(k, v, cause) -- after unlock"], abstract=True)
put("lru", 300, 450, 320, "LruCache", ["capacity: int", "index: Map&lt;K, Node&gt;", "order: RecencyList"],
    ["get(key) / put(key, value)", "write(key, value, ticket)", "remove(key) / evictionOrder()", "sweepExpired() / expireIfDue(k)", "consistent(): boolean"])
put("lfu", 650, 450, 340, "LfuCache", ["capacity: int", "index: Map&lt;K, Node&gt;", "buckets: Map&lt;count, list&gt;", "minFreq: int"],
    ["get(key) / put(key, value)", "write(key, value, ticket)", "remove(key) / evictionOrder()", "bump(node): one more use", "frequencyOf(key): int"])
# right column: the enum and the entry
put("cause", 1030, 20, 200, "EvictionCause", ["CAPACITY, EXPIRED,", "REPLACED, REMOVED"], [], "enum")
put("node", 1030, 130, 200, "Node", ["key: K  (final)", "value: V", "prev, next: Node", "freq: int", "expireAtMs: long"], [])
# bottom: the order list both policies are built on
put("order", 420, 690, 350, "RecencyList", ["head, tail: sentinel nodes", "size: int"],
    ["addFirst(n) / moveToFirst(n)", "unlink(n)", "last(): the next victim", "keysOldestFirst(): List&lt;K&gt;"])

EDGES = [
 ln((605, 200), (605, 154), "inherit"),
 ln((460, 450), (540, 402), "inherit", "", [(460, 428), (540, 428)]),
 ln((820, 450), (690, 402), "inherit", "", [(820, 428), (690, 428)]),
 ln((260, 451), (430, 87), "inherit", "", [(285, 451), (285, 87)]),
 ln((260, 598), (430, 112), "inherit", "", [(285, 598), (285, 112)]),
 ln((260, 751), (430, 301), "inherit", "", [(285, 751), (285, 301)]),
 ln((135, 265), (135, 234), "inherit"),
 ln((430, 240), (260, 47), "inject", "", [(402, 240), (402, 47)]),
 ln((430, 268), (260, 127), "inject", "", [(386, 268), (386, 127)]),
 ln((430, 300), (260, 207), "notify", "", [(370, 300), (370, 207)]),
 ln((780, 230), (1030, 45), "assoc", "the cause", [(870, 230), (870, 45)]),
 ln((460, 620), (560, 690), "compose", "one list"),
 ln((760, 636), (690, 690), "compose", "one list per use-count"),
 ln((600, 620), (1090, 260), "assoc", "the map", [(600, 680), (1090, 680)]),
 ln((770, 759), (1130, 260), "compose", "the list owns the nodes", [(1130, 759)]),
 _tx(950, 858, "two indexes, one object: the map and the list point at the SAME node", "var(--acc)", 10.5),
]
UMLSVG = uml_svg(1230, 930, EDGES, legend_y=900)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (<i>italic</i> = abstract, never <code>new</code>-ed; '
 'dashed border = interface; &laquo;enum&raquo; = a fixed list of values; &laquo;Extensions.java&raquo; = a follow-up\'s class rather than part of the hour). Middle: its fields, the state it holds. '
 'Bottom: its methods. <b>The arrows.</b> Hollow triangle = extends or implements. Filled diamond = owns: each cache '
 'owns its order &mdash; one list for LRU, one list per use-count for LFU &mdash; and the list owns the nodes. Plain '
 'arrow = references. Dashed green = handed in through <code>configure()</code>. Dotted blue = notifies. '
 '<b>Where state lives:</b> a <code>Node</code> holds the key, the value, its two links, its use-count and its expiry; '
 'it is the only object with per-entry state. <code>RecencyList</code> holds nothing but two sentinels and a count, '
 'and does nothing but splice. <code>LockedCache</code> holds the one lock, the three handed-in rules and the tickets of '
 'the loads in flight. Each cache holds its capacity, its map and its order. Follow the two arrows into <code>Node</code>: '
 'the map points at it and the list points at it, and that is the entire design, two indexes over one object. Notice '
 'what is <i>not</i> here. There is no Entry class separate from the node: they are the same thing, which is what makes '
 'eviction O(1). And there is no policy field on the cache, because the policy <i>is</i> the class. That is why '
 '<code>AdmissionLruCache</code>, the one with a frequency sketch on its door, sits beside the other two, not inside them.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does and what it guarantees; read only those first for the shape, then the bodies for the '
 'pointer surgery. Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java (every '
 'follow-up\'s reference code, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (twenty-one '
 'claims, sixty checks; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints '
 'ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your five to eight clarifying questions (thread safety and what happens on a miss first). The '
 'must-write core is small, about sixty lines: <code>Node</code>, <code>RecencyList</code> with its two sentinels, and '
 '<code>LruCache</code> with a HashMap, one lock, get and put, and the evict-first order inside put. That is LeetCode 146 '
 'made thread-safe, and it is what most rounds grade. Type it first, then a main that fills a cache of three, reads one '
 'entry and shows the right key leaving. Only then add what the interviewer asks for, in the order asked: the '
 '<code>Cache</code> interface and LFU, the loader with its tickets, the listener, TTL. <code>LockedCache</code> is what you '
 'factor out the moment the interviewer says "now do LFU".</div></div>')

TICKETS = src[src.index("    // Tickets. A miss takes"):src.index("\n}\n", src.index("    // Tickets. A miss takes")) + 1]

FU = [
("The interviewer changes the policy mid-round: evict the least-FREQUENTLY used instead. How much of your code moves?", "twist", 10,
 "One new class, and nothing else. Callers hold a <code>Cache</code>, so the constructor line is the only edit at the "
 "call site. Inside, the single recency list becomes one recency list per use-count, plus the smallest count in use "
 "(<code>minFreq</code>). A get unlinks the node from its bucket, adds one to its count, and links it at the front of "
 "the next bucket up. If that emptied the smallest bucket, <code>minFreq</code> moves up by one. An eviction takes the "
 "tail of the smallest bucket, so a tie between two entries used equally often is broken by recency. That tie-break "
 "is what the interviewer is checking for, and it is free, because each bucket is itself a recency list. Remove and "
 "expiry are O(1) too, because they never repair <code>minFreq</code>. They do not need to. It is only read when the "
 "cache is full, and a cache that just lost an entry fills up again only through an insert, which resets it to 1. Test 9 checks "
 "the whole cache against a brute-force LFU over 20,000 random operations.",
 sect(src, "final class LfuCache", "class WriteBackListener")),
("The prompt says users pick the eviction policy (LRU or FIFO today, LFU later) and the store when they create the cache. Show that shape.", "twist", 8,
 "Split the cache in two. A store (any <code>Map</code>) holds the values; an <code>EvictionPolicy</code> only hears "
 "which keys were used and answers which key should leave next. <code>PolicyCache</code> holds both under one lock. A "
 "put of a new key into a full store asks the policy for its victim, removes it from both, then stores the value and "
 "reports the use. LRU and FIFO are one class, <code>ListPolicy</code>. LRU moves a key to the front on every use; "
 "FIFO places it only when it first arrives. Test 17 shows the two losing different keys. The cost is a second index, "
 "because the policy keeps its own key-to-node map; the gain is one cache class for every policy. LFU plugs in the "
 "same way (<code>LfuCache</code>'s buckets without the values), and so does a policy that evicts the lowest rank "
 "some other service reports, with LRU breaking ties. Switching the policy of a live cache means building the new "
 "one from the keys already stored; their history is lost, so say so.",
 X("pluggable policy", "multi-level")),
("Fifty threads hammering one cache of a hundred. Prove nothing is lost and the count never goes over capacity, with a test.", "non-functional", 10,
 "The race lives between reading the count and writing the two indexes. Every operation does the whole "
 "read-modify-write inside one lock held by the cache: the lookup, the unlink of the victim from the list and the "
 "map, and the link of the newcomer. So no other writer can run in that gap. The proof is arithmetic, not a count. "
 "Fifty threads wait on one latch, then insert four hundred distinct keys each. Afterwards, the number the listener "
 "reported as evicted plus the number still resident must be exactly twenty thousand: a lost update leaves it short, "
 "a double count leaves it over. The test also checks the size after every put, and walks the list against the "
 "map's keys. Two things to say while you write it. A <code>ReadWriteLock</code> buys nothing, because a get moves a "
 "node, so there are no pure readers to let in together. And two thread-safe collections do not make a thread-safe "
 "cache. A <code>ConcurrentHashMap</code> next to a <code>ConcurrentLinkedDeque</code> (a double-ended queue) still "
 "has a gap between the two updates, and <code>deque.remove(key)</code> walks the whole deque, so it is O(n) as well.",
 T("        // 5. fifty threads", "        // 6. an eviction listener")),
("One lock on a cache doing two hundred thousand gets a second. Have you serialised the whole system?", "non-functional", 5,
 "No. The locked part of a get is about eighty nanoseconds, so two hundred thousand of them are sixteen "
 "milliseconds of lock in every second: 1.6 per cent busy. A thread almost never finds it taken. The number "
 "that matters is what you keep out of the lock: one five-millisecond loader inside it would push that 1.6 per cent "
 "past a hundred. When traffic really does outgrow one lock, the next rung is the striped cache below. The key's "
 "hash picks one of sixteen segments, each a whole little cache with its own lock, map and order. Say its three "
 "costs out loud. There is no global recency order any more: a key can be evicted from a busy segment while an "
 "older key survives in a quiet one. That is approximate LRU, which is exactly what Guava ships. <code>size()</code> is a "
 "sum of sixteen snapshots taken at sixteen different instants, so it is a number to log, not one to branch on. "
 "And the capacity divides: a cache of a hundred in sixteen stripes is sixteen caches of six. A hot segment keeps "
 "evicting keys it still needs while a quiet one sits empty. Stripe only when capacity over stripes is still in the hundreds.",
 X("striping", "the stampede")),
("The database behind your loader is down. What is the state of the cache? And what if a put lands while a load is still running?", "functional", 10,
 "Exactly what it was. A miss leaves the lock first and only then calls the loader. So an exception reaches the "
 "caller with nothing written (no placeholder, no null entry, no half-linked node), and the next call retries "
 "cleanly. A loader that returns null is the same story: a miss stays a miss. This is the cache's version of paying "
 "before committing: the slow, fallible, outside step happens before any change, so there is nothing to roll back. "
 "The second danger is a writer arriving mid-load. Before it loads, a miss takes a ticket. A put or remove of that "
 "key tears the ticket up. A load whose ticket is gone hands its value to its caller, but does not write it. "
 "Without the ticket, a slow load could overwrite a newer put (test 11) or bring back a row that was just removed "
 "(test 12). Keeping the loader outside the lock has one more cost: a cold key hit by a thousand threads at once "
 "makes a thousand database calls, which is the next question but one.",
 sect(src, "    public V get(K key) {", "    public V remove(K key) {") + "\n" + TICKETS),
("Why is this actually O(1)? Walk me through the eviction, pointer by pointer.", "non-functional", 5,
 "Three separate reasons, and an interviewer wants all three. First, the map answers \"the value for this key\" in "
 "one hash lookup. Second, the list is <i>doubly</i> linked, so unlinking a node found through the map is four "
 "pointer writes with no walk to find the node before it. With a singly linked list it would be O(n). Third, the "
 "key is stored inside the node, so when eviction takes the tail it already has the key it needs to delete the map "
 "row. Otherwise you would be searching the map by value. The two sentinels are a fourth, smaller reason: they "
 "remove every empty-list and one-element special case, so the splices are straight-line code and much harder to "
 "get wrong. Space is O(capacity): one map entry and one node per key, and an LRU hit allocates nothing at all.",
 sect(src, "final class Node", "abstract class LockedCache")),
("A thousand threads miss the same cold key at the same instant. What happens to your database?", "non-functional", 5,
 "A thousand reads, unless you do something, because the loader deliberately runs outside the lock (this pile-up "
 "is called a cache stampede). The fix is not to put the loader back inside the lock: that would make every miss in "
 "the cache wait behind one slow key. It is to wrap the loader in another loader that collapses duplicate work. The "
 "first caller for a key puts a task in a concurrent map and runs it. Everybody else finds the task already there "
 "and waits for its result. The first caller clears the slot when it is done. A thousand callers, one database "
 "read, and the same Decorator seam one level down: a <code>CacheLoader</code> wrapping a <code>CacheLoader</code>. "
 "The small race that remains is worth admitting: a caller who arrives after the slot is cleared but before the "
 "value lands in the cache starts a second load.",
 X("the stampede", "the sweeper")),
("Expire entries sixty seconds after the write, then after the last use. How do you test that without sleeping?", "twist", 10,
 "Expiry is a second reason to leave, so it goes on the entry: each node carries the instant it stops being valid, "
 "stamped from an injected clock. The check is lazy: a read that finds an expired node treats it as a miss, unlinks "
 "it there and then, and tells the listener EXPIRED. That costs one comparison on every get. \"After last use\" "
 "(expire-after-access) is one more line: every hit stamps the node again. Lazy expiry never frees a key that nobody "
 "asks for again, so the proactive version needs the entries in expiry order. With expire-after-access that order "
 "already exists: the least recently used entry is always the first to expire, so <code>sweepExpired</code> pops "
 "expired nodes off the tail and stops at the first fresh one. When entries can have different deadlines, keep a heap "
 "of notes (key, due time) and let a background tick drain it. A key written twice has two notes, so the sweep drops "
 "a key only if the node's own deadline has passed (test 13). The tests never sleep. They hand the cache a clock that "
 "returns a number the test controls, then check a hit one millisecond before the minute is up and a miss one "
 "millisecond after.",
 sect(src, "    int sweepExpired() {", "    public List<K> evictionOrder() {") + "\n" + X("the sweeper", "write-behind")),
("Every value expires a fixed time after it was written. Give put, get and getAverage() of the values still alive, all O(1).", "twist", 8,
 "With one fixed lifetime, entries expire in the order they were written. So the order this page already has is "
 "enough: the same <code>RecencyList</code>, except that only a write moves a node. A read moves nothing. A running "
 "sum sits beside it. Every call first pops expired nodes off the old end and subtracts them, then does its "
 "own work, so <code>average()</code> is the sum divided by the count. Each entry is popped at most once in its "
 "life, so the cleanup is O(1) amortized (averaged over all the calls), not a scan per call. An overwrite takes the "
 "old value out of the sum and moves the node to the front, which restarts its lifetime; test 19 walks the clock "
 "through 2, 10 and 12 seconds. Counting instead of averaging (how many live entries does this key have?) is the "
 "same list with a count per key. The assumption to say out loud: time only goes forward. If writes can arrive with "
 "older timestamps, the list is no longer in expiry order, and you need a heap.",
 X("write-order expiry", "memo + log")),
("Bound it by memory instead of by entry count: values are between one kilobyte and one megabyte.", "twist", 5,
 "The capacity becomes a budget, and every value declares a weight through a function handed in at construction. "
 "Two things change, and both matter. The eviction becomes a <i>loop</i> instead of an if, because one large value "
 "can push out several small ones. And the new invariant (the sum of the weights never exceeds the budget) is "
 "checked and restored inside the same lock. When the lock is released, either the budget holds or nothing was "
 "written. A value heavier than the whole budget, or with a negative weight, is refused up front, instead of "
 "emptying the cache for something that still will not fit. Everything else is untouched: same node, same list, "
 "same listener, same tests.",
 X("bound by bytes", "striping")),
("A nightly report reads a million rows through this cache. The next morning the hit rate is zero. Why, and what do the real caches do about it?", "twist", 8,
 "Because plain LRU has no defence against a scan. Each of those million rows is, the moment it arrives, the most "
 "recently used entry in the cache, so each one throws out a real key and then leaves itself. By morning the cache "
 "is full of rows nobody will ask for again. No eviction rule fixes this, because by the time a scan row is the "
 "victim, the damage is done. The fix is an <i>admission</i> rule: a door on the front. The cache below keeps a "
 "frequency sketch: a fixed array of small counters that stop at fifteen, four per key. A key's estimate is the "
 "smallest of its four, because a collision can only push a count up. Every request bumps them, hit or miss. On a full "
 "cache the newcomer is compared with the entry it would push out, and gets in only if its count is higher; ties go "
 "to the resident. Test 10 runs the same five-hundred-row scan through two caches: the forty-key working set "
 "survives in one and is wiped out in the other. Two details to volunteer. The counters are halved every so often, "
 "so the count is recent, not lifelong. And a genuinely new hot key is also seen once, so it is also refused, which "
 "is why Caffeine's <b>W-TinyLFU</b> puts every newcomer in a small LRU window first. A cheaper answer that "
 "interviewers also accept is segmented LRU. A new key enters a probation part, and only a second hit moves it to "
 "the protected part, so a one-pass scan churns probation and never touches protected.",
 X("admission", "pluggable policy")),
("Ops want the hit rate on a dashboard by Friday. Do not touch either cache class.", "functional", 5,
 "Another <code>Cache</code> that delegates and counts. Every method forwards to the one it wraps; get adds one to "
 "hits or misses on the way back, and hitRate is a division. It composes with anything, because the seam it plugs "
 "into is the interface, not a class, so the same wrapper works over LRU, LFU, the weighted cache and the striped "
 "one. The honest caveat to say out loud: with a read-through loader, a miss that the loader answers comes back "
 "non-null, so the wrapper records it as a hit. When that matters, count the loader's calls instead, which is what "
 "the demo does.",
 X("stats", "the locking decorator")),
("The cache sits in front of a slow function as a memo (one answer kept per distinct call). It must survive a crash, order included.", "functional", 8,
 "Two parts. The key: equal calls must build equal keys, and a Java array's own <code>equals</code> only asks "
 "\"same object?\", so <code>CallKey</code> compares arguments with <code>Arrays.deepEquals</code> and sorts named "
 "arguments by name (test 20). The crash: every change is appended to a log file before the cache changes (a "
 "write-ahead log). A restart replays it through the same LRU rules, which rebuilds the entries and their order, "
 "because hits are logged too. Puts are forced to disk with an fsync; hits are not, since losing the last few only "
 "makes the order slightly stale. Each line ends in a checksum (a number computed from its bytes), so a line torn by "
 "the crash does not match and is cut off. <code>compact()</code> rewrites the log through a temp file and one rename "
 "that happens all at once or not at all (test 21).",
 X("memo + log", "Runs every extension")),
("Now there are two servers, and they share one store (Redis or a table).", "twist", 5,
 "Memory goes in front of the shared store, and the seams are already there. The store becomes the loader, so a "
 "local miss falls through to Redis or a table without the cache knowing what it is talking to. A write goes to the "
 "store first; then this server drops its own copy instead of updating it, so the next read loads whichever write "
 "won in the store. The store's write is a conditional update (write only if this version is newer than the stored "
 "one), which is the database doing what the lock does in one process. The versions must come from one place every "
 "server shares, such as a database sequence or Redis <code>INCR</code>. With a counter per server, a quiet server's "
 "newer write would lose to a busy server's older one (test 15). Then the hard part of every distributed cache: the "
 "other server's copy is now wrong, so a write publishes an invalidation message and every server drops that key. "
 "The ticket from question 5 stops a load already running from putting the old row back. Say out loud that this is "
 "eventually consistent (the servers agree in the end, not at every instant), and that the window is the message's "
 "delivery time. Three write policies are worth naming. Write-through writes the store on every put: this class, "
 "which then drops its copy instead of updating it. Write-back writes the store only when a value leaves the cache "
 "(<code>WriteBackListener</code>). Write-behind hands that write to a queue that one thread drains "
 "(<code>WriteBehindListener</code>).",
 X("two tiers", "the builder")),
("Levels L1 to Ln, each with a capacity, a read time and a write time; print usage and average times.", "functional", 10,
 "Each level is a whole <code>LruCache</code> plus two numbers, its read cost and its write cost, and "
 "<code>MultiLevelCache</code> holds the list, fastest first. A read walks down until a level has the key, then "
 "copies the value into every faster level above it; the time charged is every read tried plus every copy written. "
 "A write goes down from L1, reading each level first and stopping at the first one that already holds the same "
 "value, which is the prompt's rule. <code>stats()</code> prints each level's filled and total size, and the "
 "average read and write time over the last five calls, kept in two small queues. One lock covers all the levels, "
 "because a read also writes, and nobody may see a value half-copied. The levels' own locks are always taken "
 "inside it, in the same order, so nothing can deadlock. Test 18 checks the arithmetic: a write of 78 ms, a deep "
 "read of 38 ms, and a repeat write that stops at L1 in 1 ms.",
 X("multi-level", "write-order expiry")),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "None of them was chosen up front; each is what a move produced. The short answer is four names and one argument. "
 "Strategy: the eviction policy is the whole implementation, so LRU, LFU and the admission cache are three classes "
 "behind one interface. Question 2 shows the classic form: a policy handed to <code>PolicyCache</code>. Decorator: "
 "three of them, namely stats, the locking wrapper, and a loader wrapped in a loader to collapse a stampede. "
 "Observer: the eviction listener, called after the unlock. State: the entry's life and the cause on the callback. "
 "The argument is the Builder. This is the one problem in the set where it earns its place: seven knobs, six of "
 "them optional, is exactly the case a builder is for. That is why Guava ships CacheBuilder and Caffeine ships "
 "Caffeine.newBuilder. Factory is the one ternary inside <code>build()</code>; Template Method was declined, and "
 "Singleton earned nothing. For SOLID, the letter worth talking about is L: nothing asks which policy it got. The "
 "trap is a decorator that forgets to delegate a method, which breaks that promise while still compiling.",
 X("the builder", "the five-line version")),
("Should I have just used LinkedHashMap?", "design", 5,
 "Often, yes, and saying so is a senior signal, not a cop-out. A <code>LinkedHashMap</code> built in access order is "
 "exactly this design: a hash map whose entries already sit in a doubly linked list, with "
 "<code>removeEldestEntry</code> as the eviction hook. Five lines, in the JDK since 1.4, and the right answer for a "
 "single-threaded cache with no TTL and no plan to change the policy. Four things push you back to writing the nodes "
 "out. There is no per-entry expiry. The only victim it can offer is the eldest, so LFU is out. It is not "
 "thread-safe, and in access order even <code>get</code> rearranges the list, so every read needs the exclusive lock "
 "too. And the hook is handed the victim but runs inside <code>put</code>, so a listener called from it runs inside "
 "your lock. So: name it, say when it is enough, and say which of those four made you hand-roll.",
 X("the five-line version", "admission")),
]

build(dict(
    slug="lru", title="LRU / LFU Cache",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 21 failure tests and a 50-thread race pass",
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
