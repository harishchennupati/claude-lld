# Striped Concurrent Map LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"mt-striped-map/Main.java").read_text()
ext   = (H/"mt-striped-map/Extensions.java").read_text()
tests = (H/"mt-striped-map/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+240])
    j = next(m for m in marks if m > i and b in ext[m:m+240])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
# what the code must do: the three shapes of write, the read, and where the decision is
pf = _D
rows = [("put", 18, [("a key and a value", "from any thread"),
                     ("spread the hash once", "multiply, then fold"),
                     ("pick the stripe", "the HIGH bits, masked"),
                     ("lock THAT stripe", "not the map"),
                     ("write, raise the count", "then unlock")]),
        ("merge", 92, [("key, value, a function", "count + 1, say"),
                       ("same spread, same stripe", "a key never moves"),
                       ("ONE hold of the lock", "read, apply, write"),
                       ("nothing can interleave", "no update is lost"),
                       ("unlock, then listeners", "never inside")]),
        ("size", 166, [("nobody asks a lock", "no stripe is touched"),
                       ("read 16 volatile ints", "one per stripe"),
                       ("add them up", "a weak, cheap answer"),
                       ("exactSize: all 16 locks", "in index order, budgeted"),
                       ("that one is O(n)", "say it out loud")])]
for lab, y, boxes in rows:
    pf += _tx(88, y + 28, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k*212
        pf += _bx(x, y, 190, 50, b[0], b[1], acc=(k == 2 and lab != "size"))
        if k < 4: pf += _ar("M%s %s H%s" % (x+190, y+25, x+212), True)
pf += _ar("M150 43 H122 V240 H146", dash=True)
pf += _bx(150, 224, 250, 32, "a null key or value: refused", "before any lock is taken", dash=True)
pf += _tx(88, 292, "read", "var(--acc)", 13)
pf += _tx(150, 292, "at any instant, from any thread: the value under a key &mdash; one stripe lock, a walk of one short chain, back out", "var(--text)", 12, "start")
pf += _tx(615, 322, "a key lives in exactly ONE stripe, and every read-modify-write on it happens inside ONE hold of that stripe's lock:", "var(--muted)", 11.5)
pf += _tx(615, 341, "no update is ever lost, and no reader ever walks a chain that is being relinked", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 355, pf)

# one run, replayed -- the numbers are the ones Main.java prints
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("50 threads start together", ["one latch releases all of them", "100,000 distinct keys to write",
                                     "16 stripes, 16 locks"], False),
      ("30 ms later: all written", ["exact size 100,000, none missing", "stripes hold 6,239..6,267 each",
                                    "6,500 met another thread"], True),
      ("then 8 threads, ONE key", ["merge: 400,000, to the increment", "get-then-put: about 100,000",
                                   "three of every four vanished"], True),
      ("the same load, 1 stripe", ["with 1.8 us inside the lock:", "256 ms against 51 ms",
                                   "five times, for one argument"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li><code>get</code>, <code>put</code>, <code>remove</code> on a key, with the map safe for any number of threads on either side.</li>
<li><code>merge</code> and <code>compute</code>: read-modify-write on one key as a single indivisible step, so counters work.</li>
<li><code>putIfAbsent</code> and <code>replace(key, expected, updated)</code>: check-then-act, also indivisible.</li>
<li><code>computeIfAbsent</code> runs its loader at most once per key, however many threads miss it at the same instant.</li>
<li>A cheap <code>size()</code> for monitoring, and an exact one for when you really need it &mdash; two methods, not one.</li>
<li>Iteration that never throws while somebody is writing, and a true snapshot when you ask for one.</li>
<li>Null keys and null values are refused, so a <code>null</code> answer means "absent" and nothing else.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>No lost updates and no torn reads with fifty threads writing flat out: exactly one stripe owns a key, and one lock guards that stripe.</li>
<li><code>get</code>, <code>put</code>, <code>remove</code> and <code>merge</code> are O(1) on average; only the all-stripe operations are not.</li>
<li>Threads working on different keys must not wait for each other &mdash; that is the entire point of the exercise.</li>
<li>No caller waits forever: any wait not measured in nanoseconds carries a deadline and is allowed to give up.</li>
<li>Nothing half-done: a function the caller supplied that throws leaves the map exactly as it was.</li>
<li>How the hash is spread, where time comes from and who is told are all swappable without touching a lock.</li>
<li>One JVM, in memory, not durable (say it; a follow-up adds the log).</li></ul></div></div>
'''

PROMPT = ('"Write me a thread-safe hash map. Many threads reading, many threads writing, and wrapping a HashMap in '
          'one <code>synchronized</code> is not an answer. Show me that two threads incrementing the same counter '
          'never lose an update. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A hash map is an array of buckets; a key\'s hash picks '
 'the bucket, and keys that land in the same bucket hang off it in a chain. On one thread that is a first-year '
 'exercise. The moment two threads write at the same time it stops being one: two writers can relink the same '
 'chain and lose a node, and a reader can walk a chain while a resize is rebuilding it. The obvious fix is one lock '
 'around the whole map, and it works &mdash; it also means that a thread writing key <code>alice</code> waits for '
 'a thread writing key <code>zoe</code>, which is a purely invented reason to wait. So you cut the table into N '
 'independent pieces, called <b>stripes</b> or segments, and give each piece its own lock. A key\'s hash chooses '
 'its stripe, so unrelated keys usually land on different locks and never meet. The one thing that must always be '
 'true: a key lives in exactly one stripe, and everything that reads and then writes that key happens inside one '
 'hold of that stripe\'s lock &mdash; otherwise two threads both read 41, both write 42, and one increment is '
 'gone forever.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: a class that compiles and a '
 '<code>main</code> that starts a crowd of threads and prints numbers that prove it. The interviewer is watching '
 'for, in this order: the questions you ask before typing (how many stripes, and which operations have to be '
 'atomic, are the first two); which types exist and who owns which state &mdash; and specifically that the lock '
 'lives on the <i>stripe</i> and not on the map; the path of a <code>get</code> and a <code>put</code> end to end, '
 'including which bits pick the stripe and which pick the bucket; the race, named out loud and then demonstrated by '
 'running it; the order of the writes inside the lock and what a resize does; what <code>size()</code> can honestly '
 'mean; and what happens when one operation needs two stripes. Then the twists: a hasher that puts every key in one '
 'stripe, loading a key exactly once, bounding the map, making it durable, and why '
 '<code>ConcurrentHashMap</code> does not look like this at all.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Which operations have to be atomic: just get and put, or compound ones too?</td><td>Compound too: merge, putIfAbsent, replace, computeIfAbsent</td><td>Whether a lock is needed at all, or a single volatile would do (moves 4, 6)</td></tr>'
 '<tr><td>How many stripes, and can that number change at runtime?</td><td>Fixed at construction, a power of two; buckets inside a stripe still grow</td><td>A mask instead of a modulo, and per-stripe resize (moves 5, 6)</td></tr>'
 '<tr><td>Read-heavy or write-heavy?</td><td>Mixed; and if reads really dominate, do not reach for a read/write lock</td><td>Whether reads take a lock at all, which decides how resize works (moves 6, 8)</td></tr>'
 '<tr><td>Does <code>size()</code> have to be exact?</td><td>No: a weak sum for monitoring, and a separate exact call</td><td>A volatile count per stripe, and an ordered all-lock path (moves 5, 7)</td></tr>'
 '<tr><td>Null keys or values?</td><td>Neither. A concurrent map forbids both</td><td>A <code>null</code> answer means absent, with no second call to check (move 9)</td></tr>'
 '<tr><td>Is iteration required, and must it be a frozen snapshot?</td><td>Weakly consistent is fine; a true snapshot is a separate, expensive call</td><td>One stripe locked at a time, versus all of them (moves 5, 12)</td></tr>'
 '<tr><td>Will one operation ever need two keys at once?</td><td>Yes &mdash; and that is where the deadlock lives</td><td>A fixed global lock order by stripe index (moves 9, 12)</td></tr>'
 '<tr><td>One JVM and in memory?</td><td>Yes</td><td>No durability yet; the log and the version column are a follow-up (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One run, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> a fixed, power-of-two number of stripes, each with its own lock and '
 'its own bucket array that grows on its own; compound operations are atomic per key; null keys and values are '
 'refused; <code>size()</code> is weakly consistent and there is a separate exact call; iteration is weakly '
 'consistent. Named as out of scope: rehashing across a different stripe count, eviction, durability, distribution '
 '&mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes; and the ones a threading problem tempts you to invent
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a KEY maps to a VALUE; the TABLE is cut into STRIPES; each stripe owns its BUCKETS and its LOCK; a spread HASH picks which stripe", "var(--text)", 12.5)
for x, w, t, sub, acc in [(24, 178, "StripedMap", "the stripe array, the rules", 1), (216, 178, "Segment", "buckets, count, its lock", 1),
                          (408, 178, "Entry", "key, hash, value, next", 1), (600, 178, "Hasher", "no state: an interface", 0),
                          (792, 190, "Key / Value", "the caller's, not ours", 0), (994, 216, "Bucket / Thread / Lock", "not classes: see below", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 186, "solid = it has state of its own, so it becomes a class.   dashed = no state: a pure rule, the caller's payload, or something the JDK already gives you", "var(--muted)", 11)
m1 += _tx(615, 212, "a bucket is one slot in an array holding the head of a chain, not an object; a &quot;writer&quot; is any thread that calls put; and the lock is java.util.concurrent's, not yours", "var(--muted)", 11)
MV[1] = _mv(1230, 228, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("hold the entries of one stripe", "Segment  (owns the buckets + the lock)", "seg.put(key, hash, value)"),
                                       ("decide which stripe a key is in", "StripedMap  (owns the stripe array)", "stripeIndex(hash)"),
                                       ("spread a hashCode into bits", "Hasher  (owns nothing: pure)", "hasher.spread(key.hashCode())"),
                                       ("add one to a counter under a key", "Segment  (owns the value AND the lock)", "seg.merge(k, h, 1, sum)"),
                                       ("count the whole map", "StripedMap  (the only one seeing all)", "size() / exactSize(ms)")]):
    y = 20 + k*54
    m2 += _bx(28, y, 330, 44, verb, "the verb") + _ar("M358 %s H424" % (y+22), True)
    m2 += _bx(424, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M824 %s H890" % (y+22), True)
    m2 += _bx(890, y, 312, 44, meth, "the method")
m2 += _tx(615, 302, "the verb that decides the whole design is &quot;add one to a counter&quot;: it touches a value AND the lock that guards it, and only the Segment sees both &mdash; so it is one method there,", "var(--muted)", 11)
m2 += _tx(615, 321, "never a get and a put from outside. Notice too that the map itself owns no entry and no lock: it routes, and everything else belongs to a stripe.", "var(--muted)", 11)
MV[2] = _mv(1230, 334, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(28, 76, 230, 104, "StripedMap", "configure(hasher, clock)", acc=True)
for k, (t, sub, impl, isub) in enumerate([("Hasher", "how a hashCode is spread", "SpreadHasher / FoldOnlyHasher / OneStripeHasher", "the seam they reach for first"),
                                          ("MapObserver", "who wants to know about a write", "metrics, an audit line, a cache invalidator", "called after the unlock, in a try/catch"),
                                          ("Clock", "where a deadline comes from", "System::currentTimeMillis, or a test's fake", "a lambda is a valid implementation"),
                                          ("KeyValueStore", "the contract itself", "MeteredMap wraps ANY implementation", "that one is a Decorator, not a Strategy")]):
    y = 20 + k*58
    m3 += _ar("M258 128 H330 V%s H396" % (y+22), True, True) + _bx(396, y, 290, 44, t, sub, dash=True)
    m3 += _bx(750, y, 452, 44, impl, isub) + _ar("M750 %s H686" % (y+22))
m3 += _tx(615, 268, "dashed green = handed in. The map never builds a rule, so &quot;our keys are sequential ids and they all pile into one stripe&quot; is a new class and one changed line at construction", "var(--muted)", 11)
m3 += _tx(615, 288, "and the last row is the odd one out: MeteredMap implements the same interface and holds one, so it counts hits and misses and the map never learns it is being measured", "var(--acc)", 11)
MV[3] = _mv(1230, 300, m3)

# move 4: THREADS AND TIME -- the gap between the read and the write, then the fix, then the cut
m4 = _D
m4 += _tx(24, 58, "thread A", "var(--acc)", 12, "start") + _tx(24, 116, "thread B", "var(--acc)", 12, "start") + _tx(24, 176, 'key "hits"', "var(--acc)", 12, "start")
cols = [128, 300, 472, 644]
m4 += _bx(cols[0], 36, 160, 42, "get(hits) &rarr; 41", "hold one, released")
m4 += _bx(cols[2], 36, 160, 42, "put(hits, 42)", "hold two", acc=True)
m4 += _bx(cols[1], 94, 160, 42, "get(hits) &rarr; 41", "the same 41")
m4 += _bx(cols[3], 94, 160, 42, "put(hits, 42)", "overwrites A", acc=True)
for k, v in enumerate(["41", "41", "42", "42"]):
    m4 += _bx(cols[k]+38, 156, 84, 32, v, "", acc=(k == 3))
m4 += '<rect x="118" y="26" width="516" height="62" rx="6" fill="none" stroke="%s" stroke-dasharray="5 4"/>' % RED
m4 += _tx(376, 18, "the gap: A read it, released the lock, and B read the same number", RED, 11)
m4 += '<path d="M118 208 H820" stroke="var(--line)" stroke-width="1.5"/>'
for k, t in enumerate(["t1", "t2", "t3", "t4"]):
    m4 += '<path d="M%s 203 V213" stroke="var(--line)"/>' % (cols[k]+80) + _tx(cols[k]+80, 229, t, "var(--muted)", 11)
m4 += _tx(848, 213, "time &rarr;", "var(--muted)", 11)
m4 += _card(840, 30, 362, 118, "the fix: one hold, not two",
            ["merge(key, 1, Integer::sum)", "read, apply, write &mdash; inside one lock hold",
             "nothing can interleave, so nothing is lost", "measured: 400,000 exact, against about 100,000"], acc=True)
m4 += _tx(615, 258, "and now the second half of the move: WHOSE lock? One lock over the whole map would fix this too,", "var(--text)", 11.5)
m4 += _tx(615, 277, "and would make alice wait for zoe. So cut the state first, then lock each piece.", "var(--text)", 11.5)
for k in range(8):
    x = 130 + k*136
    m4 += _bx(x, 294, 118, 52, "stripe %d" % k, "its own lock", acc=(k in (2, 5)))
m4 += _tx(189, 364, "alice", "var(--acc)", 10.5) + _tx(597, 364, "zoe", "var(--acc)", 10.5)
m4 += _tx(615, 390, "two writers, two locks, no waiting (eight of the sixteen drawn). The lock did not move to the map; the state was cut into sixteen pieces and each piece kept its own.", "var(--muted)", 11)
MV[4] = _mv(1230, 404, m4)

# move 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("which stripe holds this key?", "segments[(h &gt;&gt;&gt; shift) &amp; mask] &mdash; the HIGH bits", "O(1), no modulo"),
                                      ("which bucket inside the stripe?", "table[h &amp; (table.length - 1)] &mdash; the LOW bits", "O(1), no modulo"),
                                      ("is this node the key I want?", "compare the cached int hash, then equals", "~1 equals per bucket"),
                                      ("is this stripe getting full?", "count &gt; threshold, kept and never counted", "O(1)"),
                                      ("how many entries are there?", "16 volatile ints, summed, with no lock", "O(stripes) = 16"),
                                      ("everything, as one frozen moment?", "all 16 locks, in index order, budgeted", "O(n), not O(1)")]):
    y = 18 + k*48
    m5 += _bx(28, y, 344, 40, q, "the question") + _ar("M372 %s H432" % (y+20), True)
    m5 += _bx(432, y, 530, 40, shape, "the shape", acc=True) + _ar("M962 %s H1016" % (y+20), True) + _bx(1016, y, 186, 40, cost, "")
m5 += _tx(615, 328, "the two bit ranges are the whole trick: the stripe comes from the top bits and the bucket from the bottom ones, so two keys in the same stripe are not also in the same bucket", "var(--muted)", 11)
m5 += _tx(615, 348, "and both are masks rather than modulos, which is why the stripe count and the bucket count are always rounded up to a power of two", "var(--muted)", 11)
MV[5] = _mv(1230, 362, m5)

# move 6: the life of a stripe, the order inside a write, and who waits -- on a time line
m6 = _D
m6 += _tx(24, 54, "the writer", "var(--acc)", 12, "start") + _tx(24, 118, "stripe 5's lock", "var(--acc)", 12, "start")
m6 += _tx(24, 158, "a reader of stripe 5", "var(--acc)", 12, "start") + _tx(24, 198, "a reader of stripe 9", "var(--acc)", 12, "start")
m6 += _tx(24, 238, "size()", "var(--acc)", 12, "start")
st6 = [(166, 128, "put(k, v)", "any thread"), (306, 122, "lock stripe 5", "only stripe 5"),
       (450, 140, "walk the bucket", "cached hash first"), (612, 152, "publish the node", "one reference write"),
       (786, 140, "raise the count", "volatile, LAST"), (948, 148, "rehash + swap", "over the load factor"),
       (1108, 96, "unlock", "then listeners")]
for k, (x, w, t, sub) in enumerate(st6):
    m6 += _bx(x, 32, w, 42, t, sub, acc=(k in (3, 4, 5)))
    if k < 6: m6 += _ar("M%s 53 H%s" % (x+w, st6[k+1][0]), True)
m6 += '<rect x="306" y="104" width="898" height="28" rx="4" fill="var(--bg3)" stroke="var(--acc)"/>' + _tx(755, 123, "held by us, start to finish &mdash; the rehash included", "var(--text)", 10.5)
m6 += '<rect x="306" y="144" width="898" height="28" rx="4" fill="var(--bg3)" stroke="var(--line)" stroke-dasharray="5 3"/>' + _tx(755, 163, "waits here, then walks the NEW table: it can never see a half-moved chain", "var(--muted)", 10.5)
m6 += '<rect x="212" y="184" width="992" height="28" rx="4" fill="#12302a" stroke="var(--acc)"/>' + _tx(708, 203, "never waits at all: a different lock, and 15 of the 16 stripes are in this position", "var(--text)", 10.5)
m6 += '<rect x="212" y="224" width="992" height="28" rx="4" fill="#12302a" stroke="var(--acc)"/>' + _tx(708, 243, "never waits either: it reads sixteen volatile counters and takes no lock at all", "var(--text)", 10.5)
m6 += '<rect x="20" y="268" width="700" height="196" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(370, 290, "the order inside a write, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  take the stripe's lock &mdash; nothing before it reads or writes shared state",
                       "2  walk the chain, cached int hash first &mdash; an equals that throws has changed nothing",
                       "3  the caller's function runs HERE &mdash; merge / compute, still inside the one hold",
                       "4  link the new node, then publish it &mdash; one write; the chain is never half-built",
                       "5  only NOW raise the volatile count &mdash; a lock-free size() never counts a node it cannot find",
                       "6  over the load factor? rehash and swap &mdash; all of it under this same lock",
                       "7  anybody parked waiting for this key? signal them HERE, lock still held",
                       "8  unlock in a finally, then the listeners &mdash; outside, in a try/catch"]):
    m6 += _tx(34, 314 + k*18, l, "var(--text)", 11, "start")
m6 += _bx(752, 300, 168, 48, "Serving", "readers and writers", acc=True)
m6 += _bx(1034, 300, 168, 48, "Growing", "the writer rehashes")
m6 += _ar("M920 314 H1030", True) + _tx(976, 292, "count &gt; threshold", "var(--muted)", 9.5)
m6 += _ar("M1034 336 H924", True) + _tx(976, 362, "the new table is swapped in", "var(--muted)", 9.5)
m6 += _tx(977, 394, "the same thread does both, holding the same lock the whole time,", "var(--muted)", 10.5)
m6 += _tx(977, 412, "so &quot;what does a reader see mid-resize?&quot; has a one-word answer: nothing.", "var(--muted)", 10.5)
m6 += _tx(977, 434, "It is waiting.", "var(--acc)", 10.5)
MV[6] = _mv(1230, 478, m6)

# move 7: what is inside the lock, and eight threads at the same instant
m7 = _D + _card(24, 18, 570, 150, "inside the lock: 15 ns for a put, 10 ns for a get",
                ["one shift and one mask to find the bucket", "a walk of a chain that is almost always one node long",
                  "two int comparisons, one field write", "sometimes: a doubled array and a rehash",
                  "nothing in here can block, and nothing calls out"], acc=True)
m7 += _ar("M594 93 H652", True) + _tx(623, 83, "unlock", "var(--acc)", 10.5)
m7 += _card(652, 18, 550, 150, "outside the lock: everything that could take a while",
            ["the listeners, in a try/catch, after the unlock", "the caller's own work between calls",
             "a loader, when you use a future instead", "a durable append &mdash; unless you put it in on purpose",
             "the boxing, the string building, the garbage"])
m7 += _tx(615, 192, "eight threads at the same instant, sixteen stripes: the green block is the fifteen nanoseconds a thread holds one stripe", "var(--text)", 12)
busy = [90, 640, 260, 900, 420, 640, 1060, 180]
for k in range(8):
    y = 208 + k*22
    m7 += _tx(24, y + 13, "thread %d" % (k+1), "var(--muted)", 10, "start")
    m7 += '<rect x="110" y="%s" width="1092" height="16" rx="3" fill="var(--bg3)" stroke="var(--line)"/>' % y
    clash = (k in (1, 5))
    m7 += '<rect x="%s" y="%s" width="16" height="16" rx="3" fill="%s" stroke="%s"/>' % (
        110 + busy[k], y, "#3a1f22" if clash else "#12302a", RED if clash else "var(--acc)")
m7 += '<rect x="742" y="230" width="24" height="112" rx="4" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m7 += _tx(615, 400, "threads 2 and 6 both hashed into stripe 11: one of them waits fifteen nanoseconds. That is the only waiting on this whole picture.", RED, 11)
m7 += _tx(615, 422, "measured: 50 threads writing 100,000 distinct keys finished in 30 ms, and a thread found its stripe already held about 6,500 times in 100,000 writes &mdash; under seven per cent", "var(--muted)", 11)
m7 += _tx(615, 442, "so the honest answer to &quot;is everything one by one now?&quot; is: per stripe yes, for fifteen nanoseconds; across the map, sixteen things happen at once", "var(--muted)", 11)
MV[7] = _mv(1230, 456, m7)

# move 8: the arithmetic, then the ladder
cols8 = [("stripes", 12), ("8 threads, 1.6 M writes", 110), ("ns per write", 285), ("with 1.8 us inside the lock", 400)]
rows8 = [[("1", "var(--text)"), ("62 ms", None), ("38", None), ("256 ms   (everything queues)", None)],
         [("2", "var(--text)"), ("54 ms", None), ("33", None), ("&mdash;", None)],
         [("4", "var(--text)"), ("41 ms", None), ("25", None), ("119 ms   2.2x", None)],
         [("16", "var(--acc)"), ("25 ms", None), ("15", None), ("78 ms   3.3x", None)],
         [("64", "var(--text)"), ("20 ms", None), ("12", None), ("51 ms   5.0x", None)],
         [("one thread", "var(--muted)"), ("nobody to wait for", None), ("15 put, 10 get", None), ("that IS the critical section", "var(--muted)")]]
m8 = _D + _tx(300, 32, "measured on this machine, by Main.java", "var(--text)", 12)
m8 += _table(20, 44, cols8, rows8, rowh=28, widths=596)
m8 += _tx(911, 32, "the ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1   more stripes", "one constructor argument: 1 &rarr; 64 took 62 ms to 20 ms. Try this first, always"),
                              ("2   get the slow thing out of the lock", "a future per key instead of a loader inside it: 32 misses, one 200 ms load"),
                              ("3   no lock on the read path at all", "CHM's shape: volatile bins, CAS an empty one, synchronize on the head. 14 ns a get")]):
    m8 += _bx(624, 48 + k*62, 578, 50, t, sub, acc=(k == 0))
m8 += _tx(615, 264, "striping buys you exactly as much as the time spent inside the lock: at 15 ns inside, 64 stripes is 3x; at 1.8 us inside, 5x and still climbing", "var(--acc)", 11)
m8 += _tx(615, 288, "and the rung that is NOT on this ladder: a read/write lock per stripe. On a 95% read workload it measured 33 ms with plain locks,", RED, 11)
m8 += _tx(615, 306, "75 ms with RW locks and 12 ms with no read lock at all &mdash; the obvious rung is the slowest of the three. Measure before you climb.", RED, 11)
MV[8] = _mv(1230, 320, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("get, then put, for a counter", "one hold: merge / compute / replace; test 2 runs the racy loop and loses most of 200,000 increments"),
                                ("a spreader with no multiply in it", "the stripe comes from the HIGH bits: fold-only sends every sequential key to stripe 0; test 1"),
                                ("the count raised before the node is visible", "publish the node, THEN write the volatile count; tests 1 and 4"),
                                ("a resize a reader can walk into", "the whole rehash under the stripe's lock; test 4 forces 20,000 keys into one stripe, 7 readers"),
                                ("two stripes taken in whatever order", "always the lower index first; test 6 moves a value both ways 20,000 times and finishes"),
                                ("an exact size() that fights every writer", "a budget from the injected clock, then give up and say so; test 7"),
                                ("a waiter that looks before it takes the lock", "look for the key UNDER the lock, or it arrives in the gap and the signal is lost; test 11"),
                                ("await() in an if, or a wait with no deadline", "a while loop beats a spurious wake-up; awaitNanos returns the budget LEFT; test 12 stops at 200 ms"),
                                ("lock() where the wait can be long", "lockInterruptibly / tryLock on the all-stripe path, so a cancelled caller is not stuck; test 13"),
                                ("a listener called inside the lock", "publish after the unlock, in a try/catch; test 8 proves it from another thread"),
                                ("a stripe count that is not a power of two", "round up at construction: 17 becomes 32; test 7")]):
    y = 14 + k*40
    m9 += _bx(24, y, 372, 36, bad, "") + _ar("M396 %s H416" % (y+18), True) + _bx(416, y, 786, 36, fix, "", acc=True)
m9 += _tx(615, 476, "twenty-nine checks in FailureTests.java, every join with a deadline and a forty-five-second watchdog behind the lot: a concurrency test that hangs has told you nothing", "var(--muted)", 11)
MV[9] = _mv(1230, 490, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 176), ("the line in the code", 262), ("what it buys", 800)]
rows10 = [[("Monitor object", "var(--text)"), ("move 4", None), ("Segment: private fields, one ReentrantLock, every path takes it", None), ("one answer to &quot;who guards this?&quot;", None)],
          [("Lock striping", "var(--text)"), ("move 4", None), ("Segment[] segments, chosen by the top bits of the hash", None), ("sixteen writers instead of one", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface Hasher { int spread(int hashCode); }", None), ("a new spreader is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("MeteredMap implements KeyValueStore, holds one", None), ("hit rates without opening the map", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(op, key, stripe) after the unlock, in a try/catch", None), ("a broken listener cannot hold a stripe", None)],
          [("State", "var(--text)"), ("move 6", None), ("Serving &rarr; Growing &rarr; Serving, all under one lock hold", None), ("&quot;what is seen mid-resize?&quot; &mdash; nothing", None)],
          [("Iterator", "var(--text)"), ("move 5", None), ("StripeIterator: one stripe copied at a time", None), ("iteration that cannot throw", None)],
          [("Adapter", "var(--muted)"), ("if asked", None), ("a ConcurrentHashMap behind the same KeyValueStore", "var(--muted)"), ("swap the whole engine, keep the callers", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("the map is handed to whoever needs it; no getInstance()", "var(--muted)"), ("every test builds a fresh map", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("new StripedMap&lt;&gt;(16) is one line", "var(--muted)"), ("it earns the name when 16 comes from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("three constructor arguments, two with defaults", "var(--muted)"), ("a builder here is pure ceremony", "var(--muted)")]]
m10 = _D + _table(20, 18, cols10, rows10, rowh=29, widths=1190)
m10 += _tx(615, 388, "name a pattern only after the move that produced it; then every name comes with a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 402, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 48), ("from", 430), ("the line that shows it", 526)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Segment stores and locks. StripedMap routes. Hasher spreads. Entry links.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("FoldOnlyHasher is a new file and one changed line at construction", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("hasher.spread(key.hashCode()) &mdash; the map never asks which spreader it got", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Hasher, Clock and MapObserver are one method each; a lambda implements all three", None)],
          [("D", "var(--acc)"), ("depend on interfaces; be handed the rest", None), ("moves 3, 6", None), ("configure(hasher, clock): a test hands in a clock already past the deadline", None)]]
m11 = _D + _table(20, 18, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 246, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 260, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "a different way to spread a hash", "a new class behind Hasher plus one line at construction", "", "move 3"),
        ("someone new wants to know", "hit rate, write rate, per-stripe load", "an observer after the unlock, or a Decorator over the interface", "", "moves 3 + 4"),
        ("a new step in a life", "bound it, and evict when it is full", "the eviction runs inside the same write hold, so the bound is never exceeded", "", "move 6"),
        ("a new invariant across items", "move a value between two keys, atomically", "both stripe locks, always in index order; that ordering IS the invariant", "", "moves 4 + 9"),
        ("state that must outlive the process", "survive a restart", "append to the log inside the same hold, then commit; a version refuses a stale writer", "and that is the one slow thing you put inside a lock on purpose &mdash; stripes are what keep it cheap", "moves 6 + 8")]):
    y = 20 + k*56
    m12 += _bx(28, y, 300, 46, t, sub) + _ar("M328 %s H388" % (y+23), True) + _bx(388, y, 700, 46, fix, sub2, acc=True) + _tx(1150, y+28, mv, "var(--muted)", 11)
m12 += _tx(615, 322, "for all five the striping, the lock per stripe and the order inside a write are untouched; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 336, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class &mdash; and on a threading problem, notice hard what does not.",
 "Reading the sentence again: a <b>key</b> maps to a <b>value</b>; the <b>table</b> is cut into <b>stripes</b>; each "
 "stripe owns its <b>buckets</b> and its <b>lock</b>; a spread <b>hash</b> picks which stripe. The map owns the array "
 "of stripes and the handed-in rules, so it is a class &mdash; and it is the only one the callers touch. A stripe owns "
 "a bucket array, a count and a lock, all of which change: a class, and the important one, because that is where the "
 "lock ends up living. An entry owns a key, a cached hash, a value and a next pointer: a class, deliberately tiny. How "
 "to spread a hash has no state at all, so it is an interface. Then the three a threading problem tempts you to invent "
 "and must not. A <code>Bucket</code> is not a class: it is one slot in an array holding the head of a chain, and "
 "wrapping it costs an object per slot for nothing. A <code>Writer</code> or <code>Reader</code> is not a class: it is "
 "any thread that calls a method. And the lock is not yours to write &mdash; <code>ReentrantLock</code> already exists, "
 "and the entire design question is <i>how many of them and where</i>, not how one works.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Hold the entries of one stripe\" touches a bucket array and a count, so it belongs to the stripe: "
 "<code>seg.put(key, hash, value)</code>. \"Decide which stripe a key is in\" touches the array of stripes, which only "
 "the map has: <code>stripeIndex(hash)</code>. \"Spread a hashCode\" touches nothing at all &mdash; it is arithmetic on "
 "an int &mdash; so it is a pure rule. \"Count the whole map\" touches every stripe's counter, and again only the map "
 "sees all of them. The verb that decides the design is the fourth one: \"add one to a counter under a key\" touches a "
 "value <i>and</i> the lock that guards it, and the only object that can see both is the stripe. So it is one method "
 "there, <code>merge</code>, and never a <code>get</code> followed by a <code>put</code> from outside &mdash; because "
 "outside, those are two separate holds of the lock with a gap in the middle. Notice also what the map itself does not "
 "own: not a single entry, and not a single lock. It routes. Everything else belongs to a stripe, and that is exactly "
 "why the stripes can work in parallel.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind a one-method interface and is handed in.",
 "Three things will change, and each becomes an interface the map is <i>given</i> rather than builds. How a hashCode "
 "becomes bits will change, because it depends entirely on what the keys look like &mdash; that is <code>Hasher</code>, "
 "and it is the seam the interviewer reaches for first, usually with \"our keys are sequential ids\". Who wants to know "
 "about a write will change &mdash; metrics today, an audit log tomorrow, a cache invalidator the day after &mdash; that "
 "is <code>MapObserver</code>, and the rule that comes with it is that it is called after the unlock. Where a deadline "
 "comes from will change, because a test cannot afford to wait for one &mdash; that is <code>Clock</code>. This is where "
 "the patterns are born, not announced: a swappable rule behind an interface is <b>Strategy</b>; a map that says \"a "
 "write happened\" without knowing what a dashboard is, is <b>Observer</b>. And one more, which is the odd one out: "
 "<code>MeteredMap</code> implements the same <code>KeyValueStore</code> interface and holds one, so it counts hits and "
 "misses around any implementation at all and the map never learns it is being measured. Wrapping the whole interface "
 "rather than plugging into a slot is <b>Decorator</b>.", 3),
("Move 4: state that many threads change at once gets one owner and one lock &mdash; so cut the state until one lock is many.",
 "Two threads increment the same counter. A reads 41 and releases the lock; B reads 41; A writes 42; B writes 42. One "
 "increment is gone, and nothing ever repairs it &mdash; measured on this machine, 400,000 increments written that way "
 "land somewhere near 100,000 &mdash; a different number every run &mdash; so three of every four vanish. The gap is "
 "between the read and the write, and the only fix "
 "is to make them one hold of one lock: that is <code>merge(key, 1, Integer::sum)</code>, with the caller's function "
 "running <i>inside</i> the critical section. So far this is the same move as every other page. The part that is "
 "special here is the second half: <i>whose</i> lock? One lock around the whole map would also fix it, and would make a "
 "thread writing <code>alice</code> wait for a thread writing <code>zoe</code> for no reason anybody can name. So you "
 "cut the state first &mdash; sixteen independent bucket arrays, each with its own count &mdash; and then give each "
 "piece its own lock. The lock did not move up to the map; the state was divided, and every piece kept its own "
 "guard. That pattern has a name worth saying: <b>lock striping</b>, and the object it produces is a "
 "<b>monitor</b> &mdash; private fields, one lock, and the only way in is a method that takes it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Which stripe holds this key?\" is <code>(h &gt;&gt;&gt; shift) &amp; mask</code>: a shift, an AND and one array "
 "read. \"Which bucket inside it?\" is <code>h &amp; (table.length - 1)</code>. Both are masks rather than modulos, "
 "which is why the stripe count and the bucket count are always rounded up to a power of two &mdash; asking for "
 "seventeen stripes gives you thirty-two. And the two use different halves of the same integer on purpose: the stripe "
 "comes from the top bits, the bucket from the bottom ones, so two keys that share a stripe are not thereby forced to "
 "share a bucket. \"Is this the key?\" compares the cached int hash first and only calls <code>equals</code> when it "
 "matches, which is why every node stores its hash. \"Is this stripe filling up?\" is a comparison against a kept "
 "threshold, never a count. \"How many entries?\" is sixteen volatile ints added up with no lock at all. And one "
 "question is deliberately not O(1): a frozen snapshot needs every lock at once, which is O(n) and fights the whole "
 "map &mdash; so it is a separate method with a budget, and you say that out loud rather than pretending.", 5),
("Move 6: a stripe has a life cycle, and the order of the steps inside a write is the design.",
 "A stripe is <b>Serving</b> almost always, and <b>Growing</b> for the few microseconds when a writer that just pushed "
 "it past its load factor rehashes it &mdash; same thread, same lock hold, straight back to Serving. Now follow one "
 "<code>put</code> along the clock. Take the stripe's lock. Walk the bucket, comparing the cached hash before "
 "<code>equals</code>. If the caller handed in a function &mdash; <code>merge</code>, <code>compute</code>, "
 "<code>computeIfAbsent</code> &mdash; it runs <i>here</i>, inside the one hold, which is the whole reason none of "
 "those can lose an update. Then link the new node to the current head and publish it with one reference write, so the "
 "chain is never half-built. Only <i>then</i> raise the volatile count, so a <code>size()</code> running with no lock "
 "can never count an entry it could not have found. If that pushed the stripe over its threshold, rehash into a "
 "doubled array and swap the table in one more reference write &mdash; all of it still under the same lock, which is "
 "the complete answer to \"what does a reader see mid-resize?\": nothing, it is waiting. If anything is parked "
 "waiting for this key to appear, signal it <i>here</i>, with the lock still held: a signal only moves threads from "
 "the waiting queue to the lock queue, so it costs two pointer moves, and doing it before the unlock is what stops a "
 "wake-up going missing. Then unlock in a <code>finally</code>, and only then tell the listeners, which are "
 "arbitrary code somebody else wrote. One line to remember: <b>signal inside the lock, call listeners outside it</b> "
 "&mdash; the wait protocol on page 05 is built on it. Anything that throws before the publish &mdash; a bad "
 "<code>equals</code>, a remap function that blows up &mdash; leaves the map exactly as it was, and the caller can "
 "simply retry.", 6),
("Move 7: yes, a stripe is one at a time. Ask for how long, and what is inside it.",
 "Inside the lock there is a shift, a mask, a walk of a chain that is almost always one node long, two int comparisons "
 "and a field write: measured on one thread with nobody to contend with, fifteen nanoseconds for a "
 "<code>put</code> and ten for a <code>get</code>. Everything slow is outside &mdash; the listeners, the caller's own "
 "work, the boxing and the garbage. So when eight threads arrive at the same instant they are almost never on the same "
 "stripe: fifty threads writing a hundred thousand distinct keys finished in thirty milliseconds, and a thread found "
 "its stripe already held about six and a half thousand times out of a hundred thousand writes. Under seven per cent. "
 "That is the "
 "number to volunteer, because it is the honest answer to \"is everything one by one now?\" &mdash; per stripe yes, for "
 "fifteen nanoseconds; across the map, sixteen things are happening at once. The one case where striping cannot help "
 "at all is worth saying in the same breath: every thread hammering the <i>same</i> key is every thread on one lock, "
 "and no amount of striping changes that. It is also the case in the lost-update demo, which is why that demo is "
 "honest about the cost as well as the correctness.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Measure before you climb. Eight threads, 1.6 million writes over 65,536 keys: one stripe takes 62 ms (38 ns a write), "
 "two 54 ms, four 41 ms, sixteen 25 ms, sixty-four 20 ms (12 ns). Three times, for a constructor argument. Then run the "
 "same thing with 1.8 microseconds of real work inside the lock &mdash; a loader, a big value, a durable append &mdash; "
 "and the table changes shape: one stripe 256 ms, four 119 ms, sixteen 78 ms, sixty-four 51 ms, which is 5x and still "
 "climbing. That is the whole lesson in one sentence: <i>striping buys you exactly as much as the time spent inside the "
 "lock</i>. Now the ladder, cheapest first. One: more stripes, which is one argument and always worth trying first. "
 "Two: get the slow thing out of the lock &mdash; a future per key instead of a loader inside the critical section, so "
 "thirty-two threads missing the same key cost one 200 ms load instead of thirty-two. Three: no lock on the read path "
 "at all, which is what <code>ConcurrentHashMap</code> actually does &mdash; volatile bins, a compare-and-set into an "
 "empty one, <code>synchronized</code> on the head node otherwise &mdash; and measures 14 ns a get here. And one rung "
 "that is deliberately <i>not</i> on this ladder, because it is the one everybody reaches for: a read/write lock per "
 "stripe. The same 95 per cent read workload measured 33 ms on plain locks, 75 ms on read/write locks and 12 ms with no "
 "read lock at all. The RW version is <i>slower</i>, and the reason is worth one sentence: taking a read lock is itself "
 "a compare-and-set on one shared counter, so ten readers of the same stripe still hammer the same cache line &mdash; "
 "they simply do not block while they do it. An RW lock pays only when the critical section is long enough that the "
 "exclusion itself was the cost; here it is fifteen nanoseconds. Have the number before you claim the rung.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "A counter done as a <code>get</code> then a <code>put</code>, which is two holds with a gap. A spreader with no "
 "multiply in it, which is fine for <code>HashMap</code> because that only uses the low bits, and a disaster here "
 "because the stripe comes from the high bits &mdash; the fold-only version puts all twenty thousand sequential keys in "
 "stripe zero, and the thirty-second way to catch it is to print the per-stripe histogram. A count raised before the "
 "node is published, so a lock-free <code>size()</code> counts something nobody can find. A resize a reader can walk "
 "into. Two stripes taken in whatever order they happened to come in, which is the classic deadlock. An exact "
 "<code>size()</code> that fights every writer with no budget. A listener called inside the lock. A stripe count that "
 "is not a power of two, so the mask silently drops keys into a subset of the stripes. Then the three that only appear "
 "once a thread has to <i>wait</i> for something rather than just take its turn, and they are the ones that hang "
 "rather than slow down. A waiter that looks for the key <i>before</i> it takes the lock: the value can arrive in the "
 "gap, taking the announcement with it, and the waiter then sleeps for an announcement that has already been made "
 "&mdash; a <b>lost wakeup</b>. An <code>await</code> inside an <code>if</code> instead of a <code>while</code>: "
 "<code>await</code> is allowed to return with nobody having signalled at all (a <b>spurious wakeup</b>), and even "
 "after a real signal another waiter may have taken the value first, so the condition has to be re-checked rather "
 "than assumed. And a wait with no deadline, which is a hang wearing a different hat. Each of those is a few lines in "
 "FailureTests.java &mdash; twenty-nine checks, every join with a deadline and a forty-five-second watchdog behind the "
 "lot, because a concurrency test that hangs has told you nothing.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "<b>Monitor object</b> is move 4: <code>Segment</code> has private fields, one lock, and the only way in is a method "
 "that takes it. <b>Lock striping</b> is the second half of the same move, and it is worth naming out loud because it "
 "is the name of the whole exercise: divide the state into independent pieces and give each its own guard. "
 "<b>Strategy</b> is move 3, for the hasher. <b>Decorator</b> is the same move's wrapper, <code>MeteredMap</code>, "
 "which implements <code>KeyValueStore</code> and holds one. <b>Observer</b> is move 4's rule that a listener runs "
 "after the unlock. <b>State</b> is move 6: Serving to Growing and back, inside one lock hold. <b>Iterator</b> is move "
 "5's <code>StripeIterator</code>, which copies one stripe at a time and therefore cannot throw. If they ask how you "
 "would swap the engine, that is <b>Adapter</b>: a <code>ConcurrentHashMap</code> behind the same interface, and not "
 "one call site changes. Singleton earned nothing &mdash; the map is handed to whoever needs it, so every test builds a "
 "fresh one. Factory is not yet: <code>new StripedMap&lt;&gt;(16)</code> is one line, and it earns the name the day "
 "the sixteen comes from a config file. Builder is never: three constructor arguments, two of them with defaults.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "S: the stripe stores and locks, the map routes, the hasher spreads, the entry links &mdash; four reasons to change, "
 "four types, and that split is why the entry and the spreader can be tested with no threads at all. O: a different way "
 "of spreading a hash is a new file and one changed line at construction, never an edit to anything that holds a lock. "
 "L: the map calls <code>hasher.spread(key.hashCode())</code> and never asks which implementation it got, which is why "
 "the test can hand it one that sends every key to stripe zero and watch the map stay correct. I: "
 "<code>Hasher</code>, <code>Clock</code> and <code>MapObserver</code> have one method each, so a fake for a test is a "
 "lambda. D: the map depends on those interfaces and is handed the implementations through <code>configure</code>, "
 "which is exactly how a test hands it a clock whose every reading is ten seconds later than the last and watches "
 "<code>exactSize</code> give up in under a millisecond instead of fighting fifty writers.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (\"our keys are sequential ids\") is a new <code>Hasher</code> plus one line. Someone new who wants to "
 "know (hit rate, per-stripe load) is an observer after the unlock, or a decorator around the whole interface. A new "
 "step in a life (\"bound it at ten thousand entries\") is an eviction that runs inside the same write hold that caused "
 "it, so the bound is never exceeded even for an instant &mdash; and the honest caveat is that the bound is per stripe, "
 "so a skewed key set evicts one stripe early. A new invariant across items (\"move a value between two keys "
 "atomically\") is the one that is genuinely hard: it needs both stripe locks, and taking them in whatever order they "
 "arrive is a deadlock within seconds, so the rule is always the lower stripe index first. The ordering <i>is</i> the "
 "invariant. And state that must outlive the process is the append-only log: the append happens inside the same stripe "
 "hold as the in-memory write, so a failed append leaves the map exactly as it was, and a version column refuses a "
 "writer holding a stale version. That last one is also the only time you deliberately put something slow inside a "
 "lock &mdash; and the stripes are precisely what stops it from serialising the whole map. Then say the honest "
 "exception, because on a threading problem they will find it: there is a sixth shape, and it is \"a caller must now "
 "<i>wait</i> for something rather than take its turn\" &mdash; \"block until this key appears\". That is not a new "
 "rule and not a new state; it is a <code>Condition</code> grown on the stripe, and it brings four rules of its own. "
 "They are the first follow-up card on page 05 that has nothing to do with hashing.", 12),
]
DERIVATION_LEAD = ("The same twelve moves as every other page here, with the threading ones doing the work: the shared "
 "state and how it is cut up before it is locked (move 4), the order of the writes inside one hold and what a reader "
 "sees during a resize (move 6), what is inside the lock and what happens when eight threads arrive at once (move 7), "
 "and the ladder from one lock to sixteen to none at all (move 8). Nothing is chosen up front, and no pattern is named "
 "before the move that produced it.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the callers, the decorator, and the two rules that are handed in
put("writer", 10, 20, 246, "Writer thread", [], ["map.put(k, v)", "map.merge(k, 1, sum)"])
put("reader", 10, 100, 246, "Reader thread", [], ["map.get(k)", "map.size()"])
put("metered", 10, 180, 246, "MeteredMap&lt;K,V&gt;", ["inner: KeyValueStore&lt;K,V&gt;", "hits / misses: LongAdder"], ["delegates, then counts", "report(): String"], "Extensions.java")
put("obs", 10, 312, 246, "MapObserver", [], ["onWrite(op, key, stripe, atMs)"], "interface")
put("clock", 10, 392, 246, "Clock", [], ["nowMs(): long"], "interface")
# centre: the contract, then the aggregate root
put("iface", 296, 20, 372, "KeyValueStore&lt;K,V&gt;", [],
    ["get / put / remove (key)", "putIfAbsent(k, v)", "replace(k, expected, updated)", "merge(k, v, remap)",
     "compute(k, remap)", "computeIfAbsent(k, loader)", "size(): int"], "interface")
put("map", 296, 210, 372, "StripedMap&lt;K,V&gt;",
    ["segments: Segment&lt;K,V&gt;[]", "segMask, segShift: int", "hasher: Hasher", "clock: Clock",
     "observers: List&lt;MapObserver&gt;"],
    ["stripeIndex(hash): int", "the whole KeyValueStore surface", "exactSize(budgetMs): int", "snapshot(budgetMs): Map",
     "weakSnapshot() / stripeSnapshot(i)", "moveValue(from, to): boolean", "clear(budgetMs) / configure(...)",
     "lockAll(budgetMs)  [all, in order]", "publish(op, key, stripe)  [after unlock]"])
# right of centre: the stripe and its nodes
put("seg", 706, 210, 300, "Segment&lt;K,V&gt;",
    ["lock: ReentrantLock", "table: Entry&lt;K,V&gt;[]", "count: volatile int", "threshold: int", "waits: LongAdder"],
    ["get / put / remove / merge", "compute / computeIfAbsent", "putIfAbsent / replace", "findLocked(k, h)  [lock held]",
     "putLocked / removeLocked  [held]", "copyInto(sink)  [lock held]", "resize()  [lock held]"])
put("entry", 706, 470, 300, "Entry&lt;K,V&gt;", ["key: final K", "hash: final int", "value: V", "next: Entry&lt;K,V&gt;"], [])
# right column: the rule that changes, and the two rungs above this design
put("hasher", 1042, 20, 178, "Hasher", [], ["spread(hashCode): int"], "interface")
put("spread", 1042, 96, 178, "SpreadHasher", [], ["multiply, then fold"])
put("fold", 1042, 158, 178, "FoldOnlyHasher", [], ["fold only: the trap"], "Extensions.java")
put("onestripe", 1042, 238, 178, "OneStripeHasher", [], ["always 0: the worst case"], "Extensions.java")
put("rw", 1042, 336, 178, "RwStripedMap", ["RW lock per stripe"], ["page 05: measured slower"], "Extensions.java")
put("cas", 1042, 424, 178, "CasMap", ["bins: AtomicRefArray"], ["page 05: one lock/bin"], "Extensions.java")
put("wait", 1042, 512, 178, "WaitableMap", ["changed: Condition"], ["page 05: wait protocol"], "Extensions.java")

def stripebox(x, y, w, h, title, cells, acc=False, note=""):
    """one stripe drawn as what it is: a padlocked box holding a few buckets, each a chain head"""
    st = "var(--acc)" if acc else "var(--line)"
    g = '<g transform="translate(%s %s)"><rect width="%s" height="%s" rx="6" fill="var(--bg3)" stroke="%s" stroke-width="1.3"/>' % (x, y, w, h, st)
    g += '<text x="%s" y="18" text-anchor="middle" font-size="11.5" fill="%s">%s</text>' % (w/2, "var(--acc)" if acc else "var(--muted)", title)
    for k, c in enumerate(cells):
        g += '<rect x="8" y="%s" width="%s" height="17" rx="3" fill="var(--bg2)" stroke="var(--line)"/>' % (26 + k*21, w-16)
        g += '<text x="%s" y="%s" text-anchor="middle" font-size="9.5" fill="var(--muted)">%s</text>' % (w/2, 38 + k*21, c)
    if note: g += '<text x="%s" y="%s" text-anchor="middle" font-size="9.5" fill="var(--acc)">%s</text>' % (w/2, h-6, note)
    return g + '</g>'

EDGES = [
 # the three hashers hang off one bus into the interface
 '<path d="M1032 268 V60" stroke="var(--muted)" stroke-width="1.3"/>',
 '<path d="M1042 124 H1032" stroke="var(--muted)" stroke-width="1.3"/>',
 '<path d="M1042 192 H1032" stroke="var(--muted)" stroke-width="1.3"/>',
 '<path d="M1042 268 H1032" stroke="var(--muted)" stroke-width="1.3"/>',
 ln((1032, 60), (1120, 74), "inherit", "", [(1120, 60)]),
 # the map implements the contract, owns its stripes, is handed its rules
 ln(B["map"]["t"], B["iface"]["b"], "inherit"),
 ln(B["metered"]["r"], (296, 100), "inherit", "", [(276, 232), (276, 100)]),
 ln(B["map"]["r"], B["seg"]["l"], "compose", "1..N stripes"),
 ln(B["seg"]["b"], B["entry"]["t"], "compose", "buckets"),
 ln((1000, 506), (1006, 534), "assoc", "", [(1024, 506), (1024, 534)]),
 _tx(1024, 496, "next", "var(--muted)", 10),
 ln((1042, 44), (668, 300), "inject", "", [(700, 44), (700, 300)]),
 _tx(852, 14, "handed in through configure()", "var(--acc)", 10.5),
 ln(B["clock"]["r"], (296, 340), "inject", "", [(274, 419), (274, 340)]),
 ln((296, 380), B["obs"]["r"], "notify", "", [(270, 380), (270, 339)]),
 ln(B["writer"]["r"], (296, 250), "assoc", "", [(278, 60), (278, 250)]),
 ln(B["reader"]["r"], (296, 280), "assoc", "", [(284, 140), (284, 280)]),
 _tx(1131, 322, "three shapes this design is not", "var(--muted)", 10.5),
 # the stripe array, drawn as what it is
 _tx(615, 596, "the sixteen stripes, drawn as what they actually are", "var(--text)", 12),
]
cells = [["k: alice &rarr; 7", "k: nia &rarr; 3", "(empty)"], ["k: zoe &rarr; 1", "(empty)", "(empty)"],
         ["k: raj &rarr; 9", "k: ann &rarr; 2", "k: sam &rarr; 4"], ["(empty)", "(empty)", "(empty)"]]
for k in range(8):
    x = 18 + k*152
    acc = k in (0, 5)
    lab = "stripe %d &#128274;" % k if k < 7 else "... stripe 15 &#128274;"
    EDGES.append(stripebox(x, 612, 140, 116, lab, cells[k % 4], acc=acc,
                           note=("count = 6,247" if k == 0 else ("count = 6,239" if k == 5 else ""))))
EDGES += [
 _tx(615, 748, "each box is a Segment: one ReentrantLock, one bucket array that grows on its own, one volatile count. A key is in exactly one of them, chosen by the top bits of its spread hash.", "var(--muted)", 11),
 _tx(615, 768, "the green two are being written right now, by two different threads, at the same instant, waiting for nothing. That picture is the entire design.", "var(--acc)", 11),
]
UMLSVG = uml_svg(1230, 810, EDGES, legend_y=790)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the type name (dashed border = interface). Middle: its fields, the state '
 'it holds. Bottom: its methods; <code>[lock held]</code> marks the ones that assume the caller already took the '
 'stripe lock &mdash; they exist so the map can do a two-stripe or all-stripe operation without taking the same lock '
 'twice &mdash; and <code>[after unlock]</code> marks the one that must never run inside it. A box stamped <i>&laquo;Extensions.java&raquo;</i> is not part of the system you type in the hour: it is a follow-up\'s answer, living in the second file. Everything without that stamp is in Main.java. <b>The arrows.</b> Hollow '
 'triangle = implements. Filled diamond = owns: the map owns its stripes, a stripe owns its bucket array and its '
 'lock, and they die with it. Plain arrow = references: one entry points at the next in its chain. Dashed green = '
 'handed in through <code>configure()</code>. Dotted blue = notifies. <b>Where state lives:</b> every mutable field in '
 'this design is inside a <code>Segment</code> or inside the <code>Entry</code> chain it owns, and every one of them '
 'is reachable only under that stripe\'s lock &mdash; with exactly one exception, the volatile <code>count</code>, '
 'which is written under the lock and read without it so that <code>size()</code> costs nothing. '
 '<code>StripedMap</code> itself holds no entry and no lock: it routes. The row of padlocked boxes at the bottom is '
 'the same information as the <code>Segment</code> class, drawn sixteen times, because that is the picture worth '
 'having in your head when you type.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it does and what it guarantees; read only those first for the shape, then the '
 'bodies. Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s '
 'reference code, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (twenty-nine checks, '
 'every join on a deadline; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> '
 'prints ALL PASS in about five seconds).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six clarifying questions (which operations must be atomic, and how many stripes, first); '
 'then type in the order of Main.java: the <code>Clock</code> and <code>Hasher</code> interfaces, '
 '<code>SpreadHasher</code> with its multiply, the <code>KeyValueStore</code> contract, <code>Entry</code>, then '
 '<code>Segment</code> &mdash; its lock, its bucket array, its volatile count, and <code>putLocked</code> with the '
 'publish-then-count order &mdash; then <code>resize</code>, then <code>merge</code> and '
 '<code>computeIfAbsent</code> with the caller\'s function inside the hold, then <code>StripedMap</code> as the router '
 '(the two bit ranges, <code>tableSizeFor</code>, <code>lockAll</code> in index order), then a main that starts eight '
 'threads on one latch and prints the counter both ways.</div></div>')

FU = [
("Mid-round: our keys are sequential ids, and every single one of them is landing in stripe 0. Fix it.", "twist", 8,
 "Nothing in the map changes. How a hashCode becomes bits was already a rule handed in at construction, so this is one "
 "new class and one changed line. The bug is worth naming precisely, because it is the trap in this design: the stripe "
 "is chosen from the HIGH bits of the spread hash, and the classic spreader &mdash; <code>h ^ (h &gt;&gt;&gt; 16)</code>, "
 "which is exactly what <code>java.util.HashMap</code> uses &mdash; only folds the high bits down onto the low ones and "
 "leaves the high ones untouched. Sequential integers have all-zero high bits, so every key gets stripe 0. The fix is a "
 "multiply by the 32-bit golden ratio before the fold, which makes every output bit depend on every input bit. The "
 "evidence is a histogram, not an argument: with the fold-only spreader, 16 stripes hold 0..20,000 entries and 15 of "
 "them are empty; with the multiply, 1,248..1,252 each and none empty.",
 sect(src, "final class SpreadHasher", "/**\n * Whoever wants to know") + "\n" + X("the naive spreader", "force every key into one stripe")),
("Eight threads, one counter key, fifty thousand increments each. Prove nothing is lost.", "non-functional", 10,
 "The race lives between reading a value and writing it back, and the fix is that the whole read-modify-write happens "
 "inside one hold of that key's stripe lock: that is what <code>merge</code> is, with the caller's function running "
 "<i>inside</i> the critical section. The proof is a number, not an argument. Eight threads released by one latch each "
 "call <code>merge(&quot;hits&quot;, 1, Integer::sum)</code> fifty thousand times, and the counter reads exactly "
 "400,000. The same loop written as a <code>get</code> and then a <code>put</code> &mdash; two holds with a gap &mdash; "
 "lands on about 100,000, so three of every four increments are silently gone. Both versions are in "
 "<code>main</code>, which is the point: the race is demonstrated by running it, not asserted. The honest cost to "
 "volunteer in the same breath is that this is the one case striping cannot help, because every thread is on the same "
 "key and therefore the same lock.",
 T("        // 2. the race", "        // 3. computeIfAbsent")),
("One lock per stripe. Does that actually scale, and what is above it?", "non-functional", 10,
 "Measure first. Eight threads doing 1.6 million writes: one stripe takes 62 ms (38 ns a write), sixteen takes 25 ms, "
 "sixty-four takes 20 ms (12 ns) &mdash; about three times, for one constructor argument. Now run the same thing with "
 "1.8 microseconds of real work inside the lock and the shape changes: 256 ms on one stripe against 51 ms on "
 "sixty-four, five times and still climbing. That is the rule in one sentence: striping buys you exactly as much as "
 "the time spent inside the lock. The ladder, cheapest first: more stripes; then get the slow thing out of the lock (a "
 "future per key rather than a loader inside the critical section); then no lock on the read path at all, which is "
 "what <code>ConcurrentHashMap</code> does. The code below is the rung deliberately left <i>off</i> the ladder, "
 "because it is the one everybody suggests: a read/write lock per stripe. On a 95 per cent read workload it measured "
 "33 ms with plain locks, 75 ms with read/write locks and 12 ms with no read lock at all. The RW version is slower, "
 "and the reason is one sentence: taking a read lock is itself a compare-and-set on one shared counter, so ten readers "
 "of the same stripe still fight over the same cache line &mdash; they just do not block while they do it. It pays "
 "only when the critical section is long enough that the exclusion itself was the cost, and fifteen nanoseconds is "
 "not that.",
 X("the rung that is NOT on the ladder", "reads with no lock at all")),
("The function I pass to merge throws halfway through. What is the state of the map?", "functional", 5,
 "Exactly what it was. The order inside the critical section is what guarantees it: the chain is walked, the caller's "
 "function is applied, and only when it <i>returns</i> is anything written &mdash; the value field for an existing key, "
 "or a brand-new node linked and published for an absent one. A function that throws propagates out through the "
 "<code>finally</code> that releases the lock, so the lock is never left held either, and the caller can retry. The "
 "same reasoning covers a <code>hashCode</code> or <code>equals</code> that throws while the chain is being walked. The "
 "one ordering rule underneath all of it is the general one: never commit anything before the step that can fail has "
 "succeeded. The test asserts both halves &mdash; the exception comes out, and the value and the count are unchanged.",
 sect(src, "    V merge(K key, int hash, V value", "    /**\n     * The general form of merge") + "\n" + T("        boolean threw = false;", "        // 6. two stripes")),
("size() while fifty threads are writing: exact or approximate? And how do I iterate?", "design", 8,
 "Two different questions, so two different methods, and saying that out loud is most of the answer. "
 "<code>size()</code> sums sixteen volatile counters with no lock at all: it is O(number of stripes), it costs nothing, "
 "and it is <i>weakly consistent</i> &mdash; a write can land between two of the reads. That is right for monitoring "
 "and wrong for an assertion. <code>exactSize(budgetMs)</code> takes every stripe lock in index order, sums, and "
 "releases in reverse; it is exact and it fights the whole map, so it carries a budget and returns -1 rather than "
 "blocking forever. Iteration is the same trade: <code>StripeIterator</code> copies one stripe at a time under that "
 "one lock, so it reflects writes that land while it runs and can never throw "
 "<code>ConcurrentModificationException</code>, while <code>snapshot(budgetMs)</code> takes every lock and gives you a "
 "frozen moment. The ordering &mdash; stripe 0, 1, 2, always &mdash; is what makes the all-lock path deadlock-free.",
 sect(src, "    int exactSize(long budgetMs)", "    /** A copy of ONE stripe") + "\n" + X("iteration that never copies", "surviving a restart")),
("Move a value from one key to another, atomically, when the two keys are in different stripes.", "twist", 10,
 "Two stripes means two locks, and that is where the deadlock lives: one thread moving A to B holds stripe 4 and wants "
 "stripe 10, while another moving B to A holds 10 and wants 4, and both sit there forever. The fix is one line of "
 "policy, and it is the thing to say before you write any code: always acquire in a fixed global order &mdash; here, "
 "the lower stripe index first &mdash; and release in reverse. Two threads then ask for the same lock first, so one of "
 "them simply waits. The demonstration is safe rather than theoretical: the unordered version is run with "
 "<code>tryLock</code> and a 20 ms deadline, so each would-be deadlock shows up as a counted back-off (about 1,700 "
 "of them in 2,000 rounds) instead of a hung build, while the ordered version records zero. The test then moves a value "
 "back and forth twenty thousand times from both directions and checks that exactly one key holds it at the end.",
 sect(src, "    boolean moveValue(K from, K to)", "    /** Every stripe lock, in index order") + "\n" + X("two stripes at once", "load once per key")),
("Fifty threads miss the same key at once and the loader is a 200 ms database call. Call it once — without holding the stripe.", "twist", 10,
 "<code>computeIfAbsent</code> as written runs the loader inside the stripe lock, which is exactly what makes it "
 "exactly-once: the second caller blocks and finds the entry already there when it gets in. The test proves it &mdash; "
 "32 threads, one loader call. The cost is equally real: a 200 ms load holds up every other key in that stripe for "
 "200 ms. The fix is to store a promise instead of a value. The first caller wins a <code>putIfAbsent</code> of an "
 "empty <code>CompletableFuture</code>, which is one very short lock hold, and then does the slow work holding nothing "
 "at all; the losers get the winner's future back and wait on that. A loader that throws removes the slot so the next "
 "caller retries rather than caching a failure forever. Measured: 32 threads, the loader ran once, total wall time "
 "210 ms rather than 32 x 200 ms.",
 X("load once per key", "waiting for a key to appear") + "\n" + T("        // 3. computeIfAbsent", "        // 4. a stripe that resizes")),
("Now get(key) has to BLOCK until somebody puts it \u2014 up to 200 ms. Write it.", "twist", 10,
 "This is the one place a map needs a thread to <i>wait</i> rather than just take its turn, and it is where "
 "multi-threading rounds are actually won or lost. The stripe grows one <code>Condition</code>, which is a queue of "
 "threads parked on that stripe, and four rules come with it. <b>One: check under the lock.</b> Look for the key while "
 "holding the stripe, never before taking it \u2014 check outside and the value can arrive in the gap between your look "
 "and your <code>await</code>, taking the announcement with it, and you then sleep waiting for something that has "
 "already happened. That is a <b>lost wakeup</b>, and it is a hang, not a slowdown. <b>Two: wait in a "
 "<code>while</code> loop, never an <code>if</code>.</b> <code>await</code> is allowed to return with nobody having "
 "signalled at all \u2014 a <b>spurious wakeup</b> \u2014 and even after a real signal another waiter may have taken the "
 "value first, so the loop re-checks the thing you actually care about. <b>Three: signal after the change and before "
 "the unlock.</b> <code>signalAll</code> only moves threads from the condition queue to the lock queue, so it is two "
 "pointer moves and Java requires the lock to be held for it \u2014 note the contrast with the observer in "
 "<code>StripedMap</code>, which is somebody else's code and must be called <i>after</i> the unlock. <b>Four: carry "
 "a deadline, not a fresh timeout.</b> <code>awaitNanos</code> returns how much of the budget is left, and feeding "
 "that back into the loop is what stops a thread waiting forever in a series of short naps. The door is "
 "<code>lockInterruptibly</code>, so a cancelled request is not stuck waiting for permission to start waiting. The "
 "tests hold it to both halves: eight threads park, one <code>signalAll</code> after the write wakes all eight, and a "
 "wait for a key that never arrives returns <code>null</code> after about 200 ms rather than never.",
 X("waiting for a key to appear", "a thread stuck on a busy stripe") + "\n"
 + T("        // 11. the wait protocol", "        // 13. cancelling a thread")),
("A thread is blocked on a stripe somebody else is holding. Can I cancel it? Can it starve?", "non-functional", 8,
 "Two separate questions, and both have a one-line answer plus a number. <b>Cancel:</b> not if you wrote "
 "<code>lock()</code>. <code>ReentrantLock.lock()</code> is uninterruptible \u2014 interrupting a thread parked inside it "
 "only sets a flag the thread notices much later, once it has the lock anyway, which the test shows directly. "
 "<code>lockInterruptibly()</code> and <code>tryLock(timeout)</code> both give up on demand, and the price is that "
 "every method built on them must be allowed to fail. That is exactly the split in Main.java: plain <code>lock()</code> "
 "on the single-key path, where the wait is nanoseconds and failing would be absurd, and <code>tryLock</code> with a "
 "deadline on the all-stripe path, where the wait is unbounded. <b>Starve:</b> <code>new ReentrantLock()</code> is "
 "<i>unfair</i> \u2014 a thread arriving at a just-released lock may barge in front of threads already queued, and that "
 "barging is most of why it is fast. <code>new ReentrantLock(true)</code> hands the lock out in strict arrival order "
 "and pays a context switch per handover. Measured here on four threads hammering one lock for 250 ms: barging did "
 "about 30 million acquisitions with the unluckiest thread on 6.9 million and the luckiest on 9.0 million; fair did "
 "about 134,000, and every thread got within a whisker of 33,500 \u2014 dead even, and two hundred times less total "
 "work done. So: on a stripe "
 "held for fifteen nanoseconds nothing starves in practice, and you keep the default. What <i>can</i> starve is an "
 "operation that needs every stripe at once, which is precisely why <code>exactSize</code> carries a budget and "
 "returns -1 instead of promising an answer.",
 X("a thread stuck on a busy stripe", "bound the map") + "\n"
 + T("        // 13. cancelling a thread", "        System.out.println(failures == 0")),
("Bound it: at most ten thousand entries, evicting the least recently used.", "twist", 8,
 "Per stripe, and the eviction runs inside the same write hold that caused it, so the bound is never exceeded even for "
 "an instant. You do not write the recency list yourself: a <code>LinkedHashMap</code> constructed in access order with "
 "<code>removeEldestEntry</code> overridden is the whole mechanism, and it is called by the map after the insert while "
 "your lock is still held. One caveat to volunteer before they raise it: the bound is per stripe, total divided by N "
 "each, so a skewed key set evicts one stripe early while others sit half empty. A truly global bound needs one shared "
 "counter, which is precisely the contention the whole design exists to remove &mdash; so the usual answer in real "
 "systems is per-shard bounds plus a little slack, and the named implementation to reach for is Caffeine.",
 X("bound the map", "iteration that never copies")),
("Add metrics — hit rate, write rate — without touching StripedMap.", "design", 5,
 "A decorator, because both sides already depend on the <code>KeyValueStore</code> interface rather than on the class. "
 "<code>MeteredMap</code> implements that interface and holds one: every method delegates, and <code>get</code> "
 "additionally counts a hit or a miss on the way back. The map never learns it is being measured, and the same wrapper "
 "works unchanged over a <code>ConcurrentHashMap</code> adapter if the engine is swapped later. The counters are "
 "<code>LongAdder</code> rather than <code>AtomicLong</code>, which is worth a sentence because it is the same idea as "
 "the whole page: an adder keeps one cell per contending thread and sums them on read, so writers stop fighting over a "
 "single cache line. If the requirement is per-write notification rather than counting &mdash; an audit line, a cache "
 "invalidation &mdash; that is the observer instead, and the rule there is that it is called after the unlock inside a "
 "try/catch.",
 X("measure without touching the map", "the rung that is NOT on the ladder")),
("Where does time come from in this design, and how do you test a budget without waiting for it?", "design", 5,
 "Time enters through a one-method <code>Clock</code> handed in at <code>configure</code>, and it is used in exactly "
 "one place that matters: the all-stripe operations. <code>lockAll</code> computes a deadline once, then takes each "
 "stripe's lock with a <code>tryLock</code> given whatever budget is left, and on running out it releases what it holds "
 "in reverse order and reports failure rather than sitting on half the map. Because the clock is injected, a test hands "
 "in one whose every reading is ten seconds later than the last: the deadline is already in the past at the first "
 "check, so <code>exactSize</code> returns -1 in under a millisecond and the test asserts both the answer and the "
 "elapsed time. The honest limit, worth saying out loud, is that the actual blocking still uses the operating "
 "system's timer &mdash; what the fake clock proves is the arithmetic, not the sleep.",
 sect(src, "    private boolean lockAll(long budgetMs)", "    /** Release the first `held` stripe locks") + "\n" + T("        long[] tick = { 0 };", "        // 8. listeners are called")),
("Now it has to survive a restart.", "twist", 8,
 "The map becomes a cache over an append-only log, and the whole answer is an order. The append &mdash; the "
 "irreversible thing &mdash; happens inside the same stripe hold as the in-memory write, using the general "
 "<code>compute</code> seam, so an append that throws leaves the map exactly as it was and the caller retries. For a "
 "real store the same shape is a version column: <code>UPDATE rows SET value=?, version=version+1 WHERE key=? AND "
 "version=?</code>, where zero rows updated means somebody else got there first, which is exactly what the demo's "
 "stale writer sees. Recovery is replaying the log in order, last writer per key winning. And this is the one place "
 "you deliberately allow something slow inside a lock &mdash; which is precisely why the arithmetic on page 02 has a "
 "second column: at 1.8 microseconds inside the critical section, sixty-four stripes is 5.4 times one lock, and that "
 "is what makes a durable write per key affordable at all.",
 X("surviving a restart", "Runs every extension")),
("Why does java.util.concurrent.ConcurrentHashMap not look like this? And what else in java.util.concurrent should I have used?", "design", 8,
 "Because Java 8 threw the segments away. The lock granularity is now one <i>bucket</i>, not one stripe: a read takes "
 "nothing at all &mdash; a volatile array read, a chain walk, a volatile value read &mdash; a write into an empty "
 "bucket is a single compare-and-set, and a write into an occupied one synchronizes on the node that is already the "
 "head. A bucket that gets long turns into a red-black tree, and the resize is incremental, with writers helping to "
 "transfer bins. The consequence worth naming is that because a reader holds nothing, a node can never be relinked "
 "underneath one &mdash; which is exactly what this design's resize does, and exactly why its <code>get</code> takes "
 "the lock. Then the rest of the shelf, because the interviewer is really asking whether you would ever write this at "
 "work. <code>ConcurrentHashMap</code> is the default, and its <code>merge</code> and <code>computeIfAbsent</code> are "
 "atomic per key, which is most of what this page is about. <code>Collections.synchronizedMap</code> is the one lock "
 "around everything you were told at the start not to write. <code>LongAdder</code> beats <code>AtomicLong</code> for "
 "a contended counter, because it keeps one cell per contending thread and only sums them on read &mdash; the same "
 "divide-the-state idea as striping, applied to a single number. <code>ConcurrentSkipListMap</code> is the one to "
 "reach for when you need keys in order. <code>StampedLock</code> gives an optimistic read that takes no lock and is "
 "validated afterwards, which is the read/write lock done properly, at the cost of an API that is easy to misuse. So: "
 "in production, use <code>ConcurrentHashMap</code>. You build this in an interview to show you know what is under it, "
 "and the one real reason to build your own is a compound operation across several keys, which no single map API "
 "gives you.",
 X("one lock per BIN", "two stripes at once"))
]

build(dict(
    slug="mt-striped-map", title="Striped Concurrent Map",
    subtitle="LLD &middot; multi-threading &middot; Java &middot; OpenJDK 21: demo, 29 failure tests and a 400,000-increment race pass",
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
