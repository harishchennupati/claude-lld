# In-memory File System LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"file-system/Main.java").read_text()
ext   = (H/"file-system/Extensions.java").read_text()
tests = (H/"file-system/FailureTests.java").read_text()

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
rows = [("write", 30, [("putFile / overwrite / append", "or addContent: create or append"),
                       ("hold the name still", "namespace read lock (create: write)"),
                       ("reserve, then ask the rule", "the guard sees the resulting size"),
                       ("publish the new array", "one reference: never half a file")]),
        ("rearrange", 165, [("mkdir(s) / move / delete", "the shape of the tree"),
                            ("one exclusive lock", "nobody sees a half-moved node"),
                            ("check every rule first", "exists? own subtree? empty? guard?"),
                            ("unlink, rename, link", "three pointer ops, any subtree")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 2))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M815 84 V95", dash=True) + _bx(660, 95, 310, 40, "refused: the old bytes, untouched", "", dash=True)
pf += _tx(88, 266, "read", "var(--acc)", 13)
pf += _tx(175, 266, "read / ls / du / find / open / exists / isDirectory / totalBytes -- they share the read lock, so readers never wait for each other", "var(--text)", 12, "start")
pf += _tx(615, 305, "many threads at once: two appends to one file never lose a byte, and a delete never lands in the middle of a write to that file", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 320, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:00  mkdir -p /home/h/notes", ["3 levels created, 0 already there", "the exclusive lock, held 0.3 us",
                                         "3 new folders under the root"], False),
      ("09:01  8 threads append", ["one file, one lock: 4000 bytes", "0 lost; about 0.6 us per write",
                                   "unlocked: 1,700-2,900 of them lost"], True),
      ("09:02  a 200-byte file, 64 cap", ["reserved 200, the rule said no", "the reservation was released",
                                          "no file was created to undo"], False),
      ("09:03  rm a file being read", ["the name leaves the tree", "the reader still gets its bytes",
                                       "freed when that handle closes"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li><code>mkdir -p</code>: create every missing level of a path, and say nothing if it is already there.</li>
<li>Create or replace a file, read the whole of it, and append to the end.</li>
<li>List a directory, in name order.</li>
<li>Move or rename anything, including a directory with ten thousand descendants.</li>
<li>Delete, with an explicit recursive flag, so <code>rm</code> on a non-empty directory fails loudly.</li>
<li>Paths are absolute and normalised once: <code>.</code> vanishes, <code>..</code> pops, <code>..</code> above the root clamps at the root.</li>
<li>Search on one traversal: by extension, by size, by modified time, and any combination of those.</li>
<li>One hook that every change asks (a write, mkdir, move or delete), so a quota or a read-only folder is a class and not an edit.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many threads at once: two appends to one file never lose a byte, and two creates in one directory never lose a file.</li>
<li>Writers to different files must not block each other, and a delete must never land in the middle of a write.</li>
<li>Resolving a path is O(depth &times; log children); a quota check is O(1), never a walk of the tree.</li>
<li>Moving a directory is three pointer operations whatever the subtree weighs.</li>
<li>The write rule, the search predicate and the clock are swappable without touching the core.</li>
<li>Nothing half-done: a refused write leaves the old bytes, the old counters and no new node.</li>
<li>In memory, one process, no durability (say it; a follow-up adds the journal).</li></ul></div></div>
'''

PROMPT = ('"Design an in-memory file system. <code>mkdir -p</code>, create and read a file, append to it, list a '
          'directory, move it, delete it &mdash; and it has to stay correct when several threads use it at once. '
          'I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Somebody types <code>/home/harish/notes/todo.txt</code> '
 'and expects bytes back. So there is a thing that holds bytes, a thing that holds other things, and a string that '
 'addresses both. A file and a folder are related: listing wants a name from both, and a folder\'s size is the sum of what is inside it. What is inside may be another folder, and that recursion is the shape of the problem. On top of '
 'the tree sit the operations people actually use: make a directory and its parents, write a file, read it, append to '
 'it, list, move, delete. Several threads do all of that at the same time, and there are two different things they can '
 'break: the bytes of one file, and the shape of the tree. The one rule that must hold is that no write is ever half done. Every byte a caller was told was written is readable, and a refused call leaves the file system exactly as it found it.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile, with a '
 '<code>main</code> that builds a tree, writes files and then runs threads at it. The interviewer is watching for, in '
 'this order: the questions you ask before typing (durability and threads are the first two); which classes exist and '
 'which one owns what a path means; a write and a move end to end; what happens when two threads touch the same file '
 'and when two threads touch the same directory; where the rule that will change mid-round lives, so a quota is a new '
 'class and not an edit; what the system looks like after a refused write. Then the twists: LeetCode 588\'s create-or-append, cd with relative paths, symlinks, hard links, permissions, a recoverable delete, files too big for one array, and surviving a restart.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>One process holding everything in RAM, or must it survive a restart?</td><td>In memory, one process</td><td>No journal in the core; a journal (a log of every change, replayed after a restart) is a follow-up (move 12)</td></tr>'
 '<tr><td>One thread at a time, or many? That answer changes half the code.</td><td>Many, and it is a requirement</td><td>Two things to protect, two locks, one stated lock order (moves 4, 7)</td></tr>'
 '<tr><td>Absolute paths only, or a working directory and relative paths? Case sensitive?</td><td>Absolute, case sensitive, normalised once on the way in (<code>.</code> and <code>..</code> resolved)</td><td>One immutable <code>FsPath</code> (fixed once built); no method ever sees a slash (move 1); <code>cd</code> is a follow-up</td></tr>'
 '<tr><td>A strict tree, or symlinks and hard links?</td><td>A strict tree: one parent per node</td><td>Whether the path walk can loop, and whether bytes need a count of the names pointing at them (move 12)</td></tr>'
 '<tr><td>Is a write whole-file plus append, or random access at a byte offset?</td><td>Whole file plus append</td><td>One <code>byte[]</code> behind one lock, or a chunk list (moves 5, 12)</td></tr>'
 '<tr><td>Is delete recoverable, and what happens to somebody mid-read when a file is unlinked?</td><td>Not recoverable; a reader finishes what it started</td><td>A life cycle with open handles (a reader\'s hold on a file), and where the bytes are freed (move 6)</td></tr>'
 '<tr><td>Are there quotas, permissions, read-only areas?</td><td>Not today, but they will ask for one</td><td>One hook that every change asks, instead of a thicket of ifs (move 3)</td></tr>'
 '<tr><td>How big does this get &mdash; a hundred files, or two hundred thousand?</td><td>Big enough that a full walk per call is wrong</td><td>Incremental byte accounting and a paged listing (move 5)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> in memory, one process, no durability; absolute case-sensitive paths, '
 'normalised once at the edge so no method below ever sees a slash; a strict tree, one parent per node; whole-file '
 'read and replace plus append, no byte offsets; many threads is a requirement, not an extension. Named as out of scope: a working directory with <code>cd</code>, symlinks, hard links, permissions, a recoverable delete, and persistence &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes, and the composite
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a PATH names a FILE or a DIRECTORY; both are NODES; the FILE SYSTEM owns the root, the locks and the count; a RULE allows a write; a WATCHER is told", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 170, "FsPath", "parsed once, then frozen", 0), (228, 180, "FileNode", "bytes, version, its lock", 1),
                          (436, 200, "DirNode", "children by name", 1), (664, 150, "FileSystem", "root, locks, counters", 1),
                          (842, 170, "WriteGuard", "no state: an interface", 0), (1040, 160, "FsWatcher", "no state: an interface", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _bx(400, 190, 460, 44, "FsNode  (abstract)", "name, times, isDirectory(), sizeBytes()")
m1 += _ar("M318 156 V172 H470 V190") + _ar("M536 156 V172 H700 V190")
m1 += _tx(615, 252, "solid = state of its own, so it becomes a class.   dashed = no state: a parsed value, or a one-method interface", "var(--muted)", 11)
m1 += _tx(615, 270, "a file and a folder answer the same two questions, so they share one base type &mdash; the composite. A folder's size is the sum of its children's, and a child may be a folder.", "var(--muted)", 11)
MV[1] = _mv(1230, 285, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("hold bytes, and grow them", "FileNode  (owns the array and its lock)", "f.setContentLocked(bytes, now)"),
                                       ("hold names", "DirNode  (owns the children map)", "dir.put(n) / dir.remove(name)"),
                                       ("say what a path means", "FileSystem  (owns the root)", "nodeAt(FsPath)"),
                                       ("rearrange the tree, count the bytes", "FileSystem  (owns the shape and the counters)", "mkdirs / move / delete / write")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 258, "a node never parses a path and never points back at the file system: that one rule is what keeps the locking story short", "var(--muted)", 11)
m2 += _tx(615, 277, "and the verb that touches two of them &mdash; a write &mdash; goes to the one class that can see both, which makes it the orchestrator", "var(--muted)", 11)
MV[2] = _mv(1230, 292, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 80, 220, 90, "FileSystem", "configure(guard), watch(prefix)", acc=True)
for k, (t, sub, impl) in enumerate([("WriteGuard", "quota, max size, a read-only folder", "CapacityGuard / ReadOnlySubtreeGuard / AuditGuard"),
                                    ("NodeFilter", "by extension, size, modified time, name", "Filters.extension(...).and(largerThan(...))"),
                                    ("FsWatcher", "an indexer, a log rotator, a backup", "a lambda, or AsyncWatcher(64, w)"),
                                    ("Clock", "the modified time stamped on every node", "Clock.SYSTEM, or a test's fixed instant")]):
    y = 24 + k*60
    m3 += _ar("M250 125 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 272, "dashed = handed in. A swappable rule behind a one-method interface is Strategy; a file system that announces without knowing who listens is Observer", "var(--muted)", 11)
m3 += _tx(615, 290, "a rule that wraps another rule and adds to it is Decorator: AuditGuard(inner) records every refusal, and neither rule knows it is there", "var(--acc)", 11)
MV[3] = _mv(1230, 305, m3)

# move 4: two invariants, two gaps, two locks
m4 = _D
m4 += _bx(30, 30, 190, 44, "thread A appends", "reads 3 bytes, builds 4")
m4 += _bx(30, 100, 190, 44, "thread B appends", "reads the same 3, builds 4")
m4 += _bx(330, 65, 180, 44, "todo.txt", "3 bytes", acc=True)
m4 += _ar("M220 52 H295 V87 H330") + _ar("M220 122 H295 V87 H330")
m4 += '<rect x="560" y="25" width="300" height="130" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(710, 52, "gap 1: the bytes", RED, 12) + _tx(710, 82, "both start from 3 and publish 4", RED, 11)
m4 += _tx(710, 104, "the file ends at 4 bytes, not 5", RED, 11) + _tx(710, 132, "nobody notices: it still looks like a file", "var(--muted)", 11)
m4 += _bx(900, 45, 300, 90, "the file's OWN lock", "read and publish as one step", acc=True)
m4 += _bx(30, 185, 190, 44, "thread C writes", "resolved /a/b/f.txt")
m4 += _bx(30, 250, 190, 44, "thread D deletes", "rm -r /a")
m4 += _bx(330, 217, 180, 44, "the tree", "/a/b/f.txt", acc=True)
m4 += _ar("M220 207 H295 V239 H330") + _ar("M220 272 H295 V239 H330")
m4 += '<rect x="560" y="180" width="300" height="118" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(710, 207, "gap 2: the shape", RED, 12) + _tx(710, 237, "C writes into a file that", RED, 11)
m4 += _tx(710, 259, "nothing can reach any more", RED, 11) + _tx(710, 285, "and the byte count still counts it", "var(--muted)", 11)
m4 += _bx(900, 194, 300, 90, "the namespace lock", "shape changes take the WRITE side", acc=True)
m4 += _tx(615, 322, "two different invariants, so two different locks &mdash; never the same one. A byte write takes only the READ side of the namespace lock, so writers to different files never wait.", "var(--muted)", 11)
m4 += _tx(615, 340, "lock order is a stated rule: namespace first, then a file, never the reverse, and never two file locks at once, so a deadlock cannot form.", "var(--muted)", 11)
MV[4] = _mv(1230, 355, m4)

# move 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is at this path?", "a walk of TreeMap&lt;name, FsNode&gt;", "O(d x log k)"),
                                      ("what is in this directory, in order?", "TreeMap: sorted, so a page starts at a cursor", "O(k); page log k + n"),
                                      ("am I over quota?", "two AtomicLongs, moved as writes land", "O(1)"),
                                      ("what are the bytes?", "one byte[], read under the file's lock", "O(size): a copy"),
                                      ("who is watching /var?", "a copy-on-write list of (prefix, watcher)", "O(watchers)")]):
    y = 20 + k*50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 288, "a hash map would resolve in O(1) but re-sort on every ls; a sorted map needs about ten comparisons at a thousand entries and hands ls the order for free", "var(--muted)", 11)
m5 += _tx(615, 306, "and the byte count is incremental on purpose: walking the tree to answer \"am I over quota?\" would make every single write O(n)", "var(--muted)", 11)
MV[5] = _mv(1230, 320, m5)

# move 6: the life cycle, and the ORDER on a write
m6 = _D + _bx(30, 30, 190, 44, "LIVE", "reachable by name", acc=True)
m6 += _bx(30, 130, 190, 44, "UNLINKED", "name gone, still being read")
m6 += _bx(320, 130, 190, 44, "FREED", "the last handle closed")
m6 += _ar("M125 74 V130", True) + _ar("M220 152 H320", True)
m6 += _ar("M220 52 H415 V130", True) + _tx(300, 44, "delete, and nobody had it open", "var(--muted)", 10.5, "start")
m6 += _tx(133, 106, "delete while open", "var(--muted)", 10.5, "start") + _tx(270, 144, "last close()", "var(--muted)", 10.5)
m6 += '<rect x="560" y="20" width="650" height="252" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(885, 44, "the order on a write, and why a refusal leaves nothing behind", "var(--text)", 12)
for k, l in enumerate(["1  parse the path -- no lock held, and nothing written",
                       "2  namespace READ lock (a create takes the WRITE side instead)",
                       "3  the file's own lock -- order is namespace, then file",
                       "4  work out the resulting sizes and RESERVE them",
                       "5  ask the guard; if it says no, release the reservation",
                       "6  publish the new array: one reference, cannot half-fail",
                       "7  unlock, then tell the watchers, inside a try/catch",
                       "a refused write leaves the old bytes, the old counters and no new node;",
                       "a create asks the guard BEFORE it links the node in, so there is nothing to undo"]):
    m6 += _tx(575, 70 + k*21, l, "var(--muted)" if k > 6 else "var(--text)", 11, "start")
m6 += _tx(615, 292, "a delete unlinks the name inside the lock and frees the bytes outside it, so a reader mid-read finishes: the states make that a rule and not an accident", "var(--muted)", 11)
MV[6] = _mv(1230, 305, m6)

# move 7: what is inside the lock, and eight threads at the same instant
m7 = _D + _card(30, 20, 540, 125, "inside a lock: a few microseconds at most",
                ["a shape change at depth 3: about 0.3 us", "a 4 KB overwrite: about 0.6 us, measured",
                 "a 64 KB overwrite: about 5 us", "the guard: a quick check on numbers and a path",
                 "nothing that waits on anything, ever"], acc=True)
m7 += _ar("M570 82 H640", True) + _tx(605, 72, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 125, "outside the lock: milliseconds",
            ["parsing the path: before any lock is taken", "the watchers: after the unlock, in a try/catch",
             "a slow subscriber: its own bounded queue", "freeing an unlinked file's bytes: at close",
             "a disk or a network call: never inside"])
m7 += _tx(615, 172, "eight threads appending to EIGHT different files: nobody waits", "var(--text)", 12)
for k in range(8):
    x = 30 + k*148
    m7 += _bx(x, 185, 136, 38, "file %d" % (k+1), "waits 0 us", acc=False)
m7 += _tx(615, 252, "eight threads appending to ONE file: one at a time", "var(--text)", 12)
for k in range(8):
    x = 30 + k*148
    m7 += _bx(x, 265, 136, 38, "thread %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%.1f" % (k*0.6)), acc=(k == 7))
m7 += _tx(615, 326, "the read side of the namespace lock is shared, so eight writers to eight files are genuinely parallel; only the eight sharing one file queue up", "var(--muted)", 11)
m7 += _tx(615, 344, "and the eighth of those waits four microseconds &mdash; one at a time is true, and nobody can tell, because nothing slow is allowed inside a lock", "var(--muted)", 11)
MV[7] = _mv(1230, 356, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="180" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one lock for the shape of the tree: is it a bottleneck?", "var(--text)", 12)
for k, l in enumerate(["a shape change holds the exclusive lock about 0.3 us",
                       "a busy build machine: 2,000 mkdir / mv / rm a second",
                       "that is 0.6 ms of lock in every second: 0.06% busy",
                       "invent 100,000 a second and it is still only 3% busy",
                       "byte writes take the READ side, so they never queue here"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1  keep everything slow out of the locks", "already done: parsing before them, watchers after them"),
                              ("2  a read-write lock per directory, root first", "shared on the way down, exclusive on the folder that changes"),
                              ("3  an immutable tree, root swapped by compare-and-set", "readers take no lock at all, and a backup snapshot is free")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("\"..\" walks above the root", "the path is normalised once and clamps at the root; test 2: /a/../../.. is /"),
                                ("mv a directory into its own subtree", "one prefix comparison on the segments refuses it; test 3: the tree is unchanged"),
                                ("rm on a directory that has children", "it throws unless recursive was asked for; test 4: nothing was freed"),
                                ("two threads append to one file", "the file's own lock; test 6: 8 x 500 appends leave exactly 4000 bytes"),
                                ("a write goes over the quota", "reserve, ask, release; test 5: no file, no bytes, no drifted counter"),
                                ("two threads create the same name", "one entry in the map and one increment; test 7: 51 files, not 52"),
                                ("a watcher throws", "called after the unlock in a try/catch; test 8: a second writer gets through"),
                                ("rm a file somebody is reading", "the name goes, the bytes wait for close; test 9: the reader still reads"),
                                ("a rename lands mid-write", "the mover needs the write side, so it waits; test 10: 2000 appends, none lost"),
                                ("a subscriber cannot keep up", "a bounded queue drops and counts; test 11: 195 dropped, 200 files still written")]):
    y = 16 + k*40
    m9 += _bx(30, y, 330, 36, bad, "") + _ar("M360 %s H410" % (y+18), True) + _bx(410, y, 790, 36, fix, "", acc=True)
m9 += _tx(615, 436, "every claim this page makes has a test: FailureTests.java runs fifty-eight of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 450, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 860)]
rows10 = [[("Composite", "var(--text)"), ("move 1", None), ("abstract class FsNode { boolean isDirectory(); long sizeBytes(); }", None), ("du and filters never ask which kind it is", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface WriteGuard { void check(WriteRequest r); }", None), ("a new rule is a new class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new AuditGuard(WriteGuard.allOf(new CapacityGuard(64, 1024)))", None), ("every refusal recorded; no rule knows", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(event) after every unlock, inside a try/catch", None), ("an indexer hears; the tree never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("LIVE &rarr; UNLINKED &rarr; FREED, checked on unlink and on close", None), ("a reader mid-read cannot be broken", None)],
          [("Null Object", "var(--text)"), ("move 3", None), ("WriteGuard UNLIMITED = r -&gt; {};   AccessPolicy.ALLOW_ALL", None), ("no \"if (guard != null)\" anywhere", None)],
          [("Specification", "var(--text)"), ("move 3", None), ("extension(\"txt\").and(largerThan(4096)) -- a filter made of filters", None), ("no findByExtensionAndSize, ever", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the file system is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh tree", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("two constructors: new FileNode(name, now) and new DirNode(name, now)", "var(--muted)"), ("it earns the name when kinds come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a node is a name, two timestamps and nothing optional", "var(--muted)"), ("there would be nothing to build", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=28, widths=1190)
m10 += _tx(615, 350, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 365, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("DirNode holds names. FileNode holds bytes. FileSystem holds what a path means.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("CapacityGuard is a new file plus fs.configure(...); FileSystem is never opened", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 1", None), ("du and every filter call sizeBytes() on FsNode; only the walk casts", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("WriteGuard, NodeFilter, FsWatcher, Clock &mdash; a test hands in a lambda", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("new FileSystem(clock);  fs.configure(guard);  the tree builds neither", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "a quota, a read-only /etc", "a new WriteGuard plus one configure line", "allOf composes it with the rules already there", "move 3"),
        ("someone new wants to know", "an indexer, a log rotator, a backup", "one more watcher, on its own bounded queue", "the tree, the locks and the tests do not change", "moves 3, 4"),
        ("a new step in a life", "trash, restore, purge", "one more state and one more checked move", "delete becomes a move into /.trash; restore is the move back", "move 6"),
        ("a new invariant across names", "hard links: two names, one set of bytes", "the count of names and the unlink under the SAME lock", "the bytes go when the last name goes, not the first", "move 4"),
        ("state that must outlive the process", "survive a restart; two machines", "a journal of every change that succeeded, written after it", "replay at boot; then the tree itself behind a repository", "moves 6 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 306, "for all five, the node classes, the path parser and the two locks do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 320, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: a <b>path</b> names a <b>file</b> or a <b>directory</b>; a <b>file system</b> holds the "
 "root and decides what a path means; a <b>rule</b> says whether a change may happen; a <b>watcher</b> wants to be "
 "told. A file has bytes, a version and the lock that guards them, so it is a class. A directory has its children by "
 "name, so it is a class. A path has segments that never change once parsed, so it is an immutable value (fixed once built). Parse it once at the edge and no method below ever sees a slash again, so <code>..</code> cannot mean two different things in two different methods. A write rule has no state at all, so it is a one-method interface, not a class with "
 "fields. And the important one: a file and a folder are related. Listing wants a name from both, <code>du</code> (disk usage: the bytes under a path) wants a size from both, and a folder's size is the sum of its children's, one of which may be another folder. That recursion is the shape of the problem, so they share an abstract <code>FsNode</code> and a "
 "folder holds a collection of it &mdash; the composite, forced by the feature rather than chosen.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Hold bytes and grow them\" touches one array and the lock over it, so it belongs to the file: "
 "<code>setContentLocked(bytes, now)</code>. \"Hold names\" touches the children map, so it belongs to the directory. "
 "\"Say what a path means\" touches the root, which only the file system has, so <code>nodeAt(FsPath)</code> lives "
 "there. \"Rearrange the tree\" and \"count the volume\" touch the shape and the counters, and again only the file system sees both. So <code>mkdirs</code>, <code>move</code>, <code>delete</code> and the write path are its methods, and it is the orchestrator (the one class that runs a flow across the others). Then resist the instinct that ruins this design: do not give a node a pointer back to "
 "the file system and do not let a node parse a path. A file guards its bytes, a directory holds names, and the object "
 "above owns what a path means and who may rearrange things. That split is what makes the concurrency answer short "
 "enough to say out loud.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind a one-method interface and is handed in.",
 "What will change? What is allowed to change &mdash; a quota today, a maximum file size next, a read-only "
 "<code>/etc</code> after that. Every change asks that rule: a byte write shows it the resulting sizes, and a "
 "<code>mkdir</code>, move or delete shows it the path. What people search for &mdash; by extension today, by size and modified "
 "time tomorrow, by a combination the day after. Who is told when something changes &mdash; nobody today, an indexer "
 "and a backup later. And what time it is, because a test needs to control it. So each is a one-method interface the "
 "file system is <i>given</i> and never builds: <code>WriteGuard</code>, <code>NodeFilter</code>, "
 "<code>FsWatcher</code>, <code>Clock</code>. This is where the patterns are born, not announced. A swappable rule behind an interface is <b>Strategy</b>. A rule that wraps another rule and adds to it is <b>Decorator</b>; <code>AuditGuard(inner)</code> is the real one here, recording every refusal without the rule or the file system knowing it is there. An object that announces something without knowing who listens is <b>Observer</b>. "
 "And <code>WriteGuard.allOf(a, b)</code> and <code>filter.and(other)</code> combine two rules without editing either.", 3),
("Move 4: name the invariants. Each one gets its own owner and its own lock, and the lock order is a rule you say out loud.",
 "There are two things threads can break here, and they are not the same. The first is a file's bytes. An append reads the current array, builds a bigger one and publishes it, so two threads that both read three bytes both publish four: the file ends at four bytes instead of five, and nobody notices. The second is the shape of the tree. One thread resolves <code>/a/b/f.txt</code> while another deletes <code>/a</code>. The first thread then writes into a file nothing can reach any more, and the volume's byte count still counts it. Two invariants, two locks. The content of a file sits under that file's own <code>ReentrantLock</code> (one holder at a time). The shape of the tree sits under one <code>ReentrantReadWriteLock</code> on the file system, the namespace lock: a shared READ side for many threads, and an exclusive WRITE side for one. The trick that makes "
 "this fast is the read side: a byte write only needs the name to stay resolved, so it takes the namespace "
 "<i>read</i> lock and the file's own lock. Writers to different files never wait for each other, while a delete or "
 "a move still waits for them to finish. The read side also keeps every walk safe, because a <code>TreeMap</code> "
 "must not be read while another thread changes it. And state the order before you write a single "
 "<code>lock()</code>: namespace first, then a file, never the reverse, and never two file locks at once. A shape change may take a file's lock (a delete reads each file's size), but always second. Every thread takes locks in the same order, so a cycle cannot form: deadlock is impossible by construction, not merely unobserved.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers it cheaply.",
 "The picture answers most rows on its own. The third is the one worth arguing about. A quota check sits on the write path, so it has to be O(1). That is why the volume's byte and file counts are two <code>AtomicLong</code>s (counters many threads can add to without a lock) that move as each write lands, not numbers computed on demand. Be honest about the other half: <code>du(\"/var\")</code> for one folder still walks that subtree, and making it O(1) moves the cost onto every write (follow-up 9). The second row has a big-directory answer too. <code>ls(dir, cursor, 50)</code> reads the fifty names after the cursor (the last name of the page before) straight off the sorted map, so a page of a two-hundred-thousand-name directory costs O(log k + 50), not a copy of every name. The last row is a copy-on-write list: adding a watcher copies the list, so a thread already walking it never sees it change. And notice the thing here that is <i>not</i> a collection: a flat map from full path to file. It would make a listing a prefix scan, and moving a directory with ten thousand descendants would become ten thousand key rewrites, where a real tree does it in three pointer operations.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations at the write is part of the design.",
 "A file is LIVE while a name points at it, UNLINKED when the name is deleted but somebody still has it open, and FREED "
 "when the last reader closes. Writing that down answers the question the interviewer will ask: what happens to a reader when somebody deletes the file underneath them? The rule: the name leaves the tree inside the lock, and the bytes are released later, when the reader's handle (its hold on the open file) closes. So the reader finishes what it started. Then the order on a write, the other half of this move, which the numbered list spells out. Hold the name still, lock the file, and <i>reserve</i> the resulting bytes on the counter (a number moves, no bytes do). Ask the guard; a refusal releases the reservation, so the old bytes and the counter are exactly as they were. Only then publish the new array in one reference assignment, which cannot fail half way. A create asks the guard <i>before</i> the node is linked in, so a refused create has nothing to roll back.", 6),
("Move 7: yes, the locks make some things happen one at a time. Say which things, and for how long.",
 "The two cards are the answer, so only three things need saying out loud. First, the numbers are that small because of what is <i>not</i> allowed inside. The guard is defined as a quick check on a few numbers and a path; a guard that made a network call would be the one thing that breaks this design. Second, everything slow is deliberately outside. The path is parsed before any lock is taken, and the watchers are called after the unlock in a "
 "<code>try</code>/<code>catch</code>, so a subscriber that sleeps for fifty milliseconds delays nobody but itself. "
 "Third, the answer to \"is everything one at a time now?\" is no. Eight threads appending to eight different files run "
 "genuinely in parallel, because they share the read side of the namespace lock and hold eight different file locks. "
 "Only the eight sharing one file queue up, and the eighth of those waits about four microseconds &mdash; one at a time "
 "is true, and nobody can tell.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "The one lock worth arguing about is the exclusive namespace lock, because every <code>mkdir</code>, <code>mv</code> "
 "and <code>rm</code> takes it, and holds it for three tenths of a microsecond. A busy build machine churning two "
 "thousand shape changes a second therefore holds it six tenths of a millisecond in every second: six hundredths of one "
 "per cent. Invent a machine doing a hundred thousand a second and it is still only three per cent busy, and byte "
 "writes never queue there at all because they take the read side. That arithmetic is the answer. The ladder is only what you would do if the arithmetic came out differently. Rung two is the one to be able to defend: a read-write "
 "lock per directory, taken from the root down. To change the names in one folder, take the read side of every folder "
 "above it and the write side of that folder only, so <code>mkdir /var/a/x</code> and <code>mkdir /var/b/y</code> run "
 "at the same time. Everyone locks from the root down, so no two threads can hold two locks in opposite orders; the "
 "hard case is a move between two folders, which needs two write sides. Rung three is an immutable tree: a change "
 "copies the nodes on its path and swaps in the new root with one compare-and-set (a single step that replaces the root only if nobody replaced it first). Readers then take no lock, and a snapshot (a frozen copy of the whole tree, "
 "for a backup) costs nothing. Say the arithmetic before you climb: this is where candidates invent complexity "
 "nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the hour is over.",
 "The list is the deliverable, not this paragraph: ten things that can go wrong, and beside each one the line of code "
 "that stops it and the numbered test that proves it. Two numbers are worth saying out loud in the room. Eight threads by five hundred appends must leave exactly four thousand bytes. The identical run through the unlocked path loses between 1,700 and 2,900 of them, run to run: that gap is what the file's lock buys, stated as a number rather than a belief. And a refused write must leave three things unchanged, not one: the old bytes, the running counter, "
 "and the absence of the file. Each row is a few lines in FailureTests.java; a design that cannot show its tests is a "
 "claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Read the table right to left: each shape came out of something the system had to do, which is why each name has a one-sentence defence. One entry "
 "is worth defending out loud: <code>AuditGuard</code> is the honest Decorator, because it adds \"remember what you "
 "refused\" to any rule &mdash; including rules written next year &mdash; instead of copying that line into each of "
 "them. Specification is the least-known name here: a yes/no rule object that combines with and, or and not, which "
 "is exactly what <code>NodeFilter</code> is. Then the negatives, which are what an interviewer is really testing. Singleton earned nothing: the file system "
 "is handed to its callers, so a test builds a fresh tree in one line. Factory is \"not yet\" &mdash; there are exactly "
 "two node constructors, and it earns the name the day node kinds arrive as strings, for example when a tree is "
 "rebuilt from a saved file. Builder is \"never\" on this problem: a node is a name and two timestamps, with nothing "
 "optional to build. A pattern without a move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is the check, so the paragraph only needs the payoff. S is what move 2 handed you, and the practical "
 "benefit is that the race lives in one class and the path bugs in another, so you always know which file to open. O is "
 "<code>CapacityGuard</code>: a new file plus one call to <code>configure</code>, and <code>FileSystem</code> is never "
 "opened. L is that <code>sizeBytes()</code> means \"bytes underneath you\" for both kinds of node &mdash; it simply "
 "recurses for one of them &mdash; so <code>du</code> and every filter work on <code>FsNode</code> without asking which "
 "kind. Only the path walk casts to <code>DirNode</code>, after asking <code>isDirectory()</code>, because only a "
 "directory has children. I and D are the same thing said twice: four interfaces with one method each, all handed in. That is exactly why a test can give this file system a clock that "
 "says last Tuesday and a rule that refuses everything.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The five rows are the script: before you type, say which of the five the twist is, and the interviewer knows you have seen it before. One row needs an extra sentence. A new invariant across names (hard links: two names for one set of bytes) is a count of names. The count and the unlink must happen under the <i>same</i> lock, so the bytes go when the last name goes, not the first. "
 "Symlinks are deliberately not on the list, because they are the one twist that does reach into the core. Even then only the path walk changes: it restarts from the link's target with a hop counter (so <code>/a</code> pointing at <code>/b</code> pointing at <code>/a</code> is an error, not a hang), and it takes over <code>..</code> from <code>FsPath</code>. Page 05 has the code for all of them.", 12),
]
DERIVATION_LEAD = ("Run these twelve on any LLD and the class diagram, the locks, the tests, the patterns, SOLID and the "
 "answer to every twist fall out in that order. Nothing is chosen up front, and nothing is named before the move that produced it. On this problem move 4 is the one that separates candidates. There are two invariants here, not one (an invariant is a rule that must hold at every moment), and the design is only as good as the sentence you can say about the lock order.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the value types, the injected interfaces, the open handle
put("path", 10, 20, 230, "FsPath", ["segs: List&lt;String&gt;  (frozen)"],
    ["of(raw): FsPath", "parent() / child(n) / name()", "startsWith(p): boolean"])
put("clock", 10, 150, 230, "Clock", [], ["nowMs(): long"], "interface")
put("watch", 10, 228, 230, "FsWatcher", [], ["onEvent(e: FsEvent)"], "interface")
put("ev", 10, 306, 230, "FsEvent", ["kind: EventKind", "path: String", "from: String (a move)", "atMs: long"], [])
put("handle", 10, 412, 230, "Handle", ["node: FileNode"], ["read(): byte[]", "close()"])
put("exc", 10, 530, 230, "FsException", ["NotFound / AlreadyExists", "NotADirectory / IsADirectory",
                                         "DirectoryNotEmpty", "QuotaExceeded / InvalidMove"], [], "7 subclasses")
# centre: the aggregate root, the abstract node, and the two shapes of node
put("fs", 300, 20, 340, "FileSystem",
    ["root: DirNode", "namespace: ReadWriteLock", "totalBytes / fileCount: AtomicLong", "guard: WriteGuard",
     "clock: Clock", "watchers: List&lt;prefix, FsWatcher&gt;"],
    ["configure(guard) / setClock / watch", "mkdirs / mkdir / move / delete", "putFile / addContent(path, text)",
     "overwrite / append(path, text)", "read / ls / du / find / open", "exists / isDirectory(path)", "totalBytes() / fileCount()"])
put("node", 300, 320, 340, "FsNode", ["name: String", "createdMs / modifiedMs: long"],
    ["isDirectory(): boolean", "sizeBytes(): long", "rename(n) / touch(now)"], abstract=True)
put("file", 300, 530, 300, "FileNode",
    ["content: byte[]", "lock: ReentrantLock", "version: AtomicLong", "openHandles: int", "state: FileState"],
    ["read(): byte[]", "setContentLocked(b, now)", "acquire() / release() / unlink()"])
put("dir", 640, 530, 290, "DirNode", ["children: TreeMap&lt;name, FsNode&gt;"],
    ["child(n) / put(n) / remove(n)", "names() / namesAfter(cursor, n)", "sizeBytes(): sum of children"])
# third column: the enums and the record the rule reads
put("wmode", 690, 20, 215, "WriteMode", ["OVERWRITE, APPEND,", "MKDIR, MOVE, DELETE"], [], "enum")
put("ekind", 690, 92, 215, "EventKind", ["CREATED, WRITTEN,", "DELETED, MOVED"], [], "enum")
put("fstate", 690, 180, 215, "FileState", ["LIVE, UNLINKED, FREED"], [], "enum")
put("req", 690, 300, 215, "WriteRequest",
    ["path: String", "mode: WriteMode", "resultingFileBytes", "resultingTotalBytes", "fileCount: long"], [])
# fourth column: the rules that are handed in
put("guard", 945, 20, 265, "WriteGuard", [], ["check(r: WriteRequest)", "allOf(g...): WriteGuard", "UNLIMITED"], "interface")
put("cap", 945, 140, 265, "CapacityGuard", ["maxFileBytes / maxTotalBytes"], ["check(r): throws over either"])
put("audit", 945, 240, 265, "AuditGuard", ["inner: WriteGuard  (wrapped)"], ["check(r): delegates, records"])
put("filter", 945, 340, 265, "NodeFilter", [], ["matches(path, node): boolean", "and / or / negate"], "interface")
put("filters", 945, 444, 265, "Filters", [], ["extension(ext) / largerThan(n)", "modifiedAfter(ms) / filesOnly()"])

EDGES = [
 # the two shapes of node share one base type
 ln(B["file"]["t"], (430, 442), "inherit", "", [(450, 490), (430, 490)]),
 ln(B["dir"]["t"], (520, 442), "inherit", "", [(785, 490), (520, 490)]),
 # the file system owns the root directory
 ln((600, 270), (700, 530), "compose", "", [(600, 308), (662, 308), (662, 478), (700, 478)]),
 _tx(710, 521, "owns the root", "var(--acc)", 10.5, "start"),
 # a handle holds the node, not the name
 ln((240, 457), (300, 615), "assoc", "", [(270, 457), (270, 615)]),
 # the file system parses a path once, is handed a clock, and announces to watchers
 ln((300, 60), (240, 73), "assoc", "", [(272, 60), (272, 73)]),
 ln((300, 120), (240, 177), "inject", "", [(280, 120), (280, 177)]),
 ln((300, 90), (240, 255), "notify", "", [(262, 90), (262, 255)]),
 ln(B["ev"]["t"], B["watch"]["b"], "assoc"),
 # the rules are handed in through configure()
 ln((640, 255), (945, 55), "inject", "", [(932, 255), (932, 55)]),
 ln((640, 265), (945, 370), "inject", "", [(922, 265), (922, 370)]),
 _tx(915, 248, "handed in ", "var(--acc)", 10.5, "end"),
 # the guard reads a request; the implementations implement the interface
 ln((945, 90), (905, 357), "assoc", "", [(912, 90), (912, 357)]),
 ln(B["cap"]["t"], B["guard"]["b"], "inherit"),
 ln((1210, 277), (1210, 67), "inherit", "", [(1228, 277), (1228, 67)]),
 ln(B["audit"]["t"], B["cap"]["b"], "assoc", "wraps"),
 ln(B["filters"]["t"], B["filter"]["b"], "assoc", "returns"),
]
UMLSVG = uml_svg(1230, 760, EDGES, legend_y=735)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (italic = abstract, never instantiated; dashed border = '
 'interface; &laquo;enum&raquo; = a fixed list of values). Middle: its fields, the state it holds. Bottom: its methods. '
 '<b>The arrows.</b> Hollow triangle = extends or implements: <code>FileNode</code> and <code>DirNode</code> are both '
 '<code>FsNode</code>, which is why <code>du</code> and every filter treat them identically without asking which kind; '
 'only the path walk casts, because only a directory has children. Filled diamond = owns: the file system owns the root, and the root owns everything under '
 'it. Plain arrow = references: a handle holds the node rather than the name, which is exactly why a reader survives a '
 'delete, and <code>AuditGuard</code> holds the rule it wraps. Dashed green = handed in through '
 '<code>configure()</code> or the constructor. Dotted blue = notifies. Bottom left is the failure family: every method '
 'throws one of seven subclasses of <code>FsException</code>, so a caller who does not care which catches the one base '
 'type. <b>Where state lives:</b> a file has its bytes, '
 'its version and the lock over them; a directory has its children by name and nothing else; the file system has the '
 'root, the two locks, the two counters and the handed-in rules. Notice what is <i>not</i> here: no path string inside '
 'a node, no pointer from a node back to the file system, and no <code>Size</code> class &mdash; a size is a question '
 'a node answers, and the volume total is a counter the write path moves.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it is for and what it guarantees; read only those first for the shape, then the '
 'bodies for the mechanics. Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java '
 '(every follow-up\'s reference code, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java '
 '(fifty-eight claims proven; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> '
 'prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (durability and threads first). Then type in the order of '
 'Main.java: the three enums and the Clock; the exception family; FsPath with its normalising parse; the abstract FsNode '
 'and then FileNode (bytes plus its own lock) and DirNode (a sorted map of children); the WriteRequest record and the '
 'WriteGuard interface with one implementation; NodeFilter and the watcher; the Handle; then FileSystem with its two '
 'locks, the write path in the order of move 6, and the shape operations; then a main that builds a tree and runs eight '
 'threads at one file and fifty at one directory. If the clock runs out, the one thing that must exist is FsPath, the two node classes, and FileSystem with mkdirs, putFile, append, read, ls, move and delete. Inside it: one read-write lock for the tree, one lock per file, and the guard asked before anything changes. The Handle, the watchers, find and the audit '
 'guard are the parts to describe out loud and add only if time is left.</div></div>')

FU = [
("Now no file may be over 64 bytes, and the whole volume caps at 1 KB.", "functional", 8,
 "One new class and one line. The rule reads numbers the write path has already computed: the resulting size of this file and of the whole volume are in the WriteRequest before anything changes. So the rule is a class that reads two fields and throws. Nothing in FileSystem changes, because all three byte writes "
 "(create, overwrite, append) funnel through one guarded step, and mkdirs, move and delete ask the same guard with "
 "their path. Rules stack without knowing about each other, which is what the second class below shows. <code>WriteGuard.allOf(new CapacityGuard(64, 1024), new "
 "ReadOnlySubtreeGuard(\"/etc\"))</code> refuses any change under <code>/etc</code> (a write, a mkdir, an mv or an rm) and a write over 64 bytes anywhere. Neither rule has heard of the other. The one thing a guard may not do is "
 "anything slow, because it runs inside a lock.",
 sect(src, "final class CapacityGuard", "final class AuditGuard") + "\n" + X("a read-only subtree", "symlinks")),
("Two threads append to the same file at the same instant. Prove you cannot lose a byte, with a test.", "non-functional", 10,
 "The race lives between reading the current array and publishing the bigger one. Append does the whole "
 "read-modify-write inside that file's own lock, so no other writer can run in the gap. The proof is a count, not an argument. Eight threads released together by a latch (a gate that opens for all of them at once) each append one byte five hundred times, and the file must be "
 "exactly four thousand bytes. Run the identical workload through the unsynchronised path in Main and it loses "
 "between 1,700 and 2,900 of them, depending on the run: that number is worth saying out loud. The test also checks that the running "
 "byte counter still equals a fresh walk of the tree, because a lock that protects the bytes but not the accounting is "
 "only half a lock.",
 T("        // 6. eight threads appending to ONE file", "        // 7. fifty threads creating files")),
("One lock for the whole tree. Have you serialised the file system?", "non-functional", 8,
 "No: there are two locks, and the busy one is not exclusive. The shape of the tree sits under a read-write lock on the file system, and the bytes of each file under that file's own lock. A byte write takes the <i>read</i> side of the namespace lock plus its own file's lock, so eight writers to eight files run in parallel, while a delete still waits for them. Only mkdir, mv, rm and create take the exclusive side, for about three tenths of a microsecond each: two thousand a second is six hundredths of one per cent busy. The ladder, cheapest first: keep slow work out of the locks (done); a read-write lock per directory, shared on the way down and exclusive only on the folder that changes (the second class below; test 15 shows <code>/var/a</code> and <code>/var/b</code> changing at once); an immutable tree with a compare-and-set on the root, so readers take no lock at all.",
 sect(src, "private void applyWrite", "// ------------------------------------------------ reads")
 + "\n" + X("one namespace lock is the bottleneck", "LeetCode 588")),
("One thread is appending to /a/b/f.txt while another renames /a/b. What happens, and can your two locks deadlock?",
 "non-functional", 8,
 "Nothing is lost and nothing is torn, because the two calls cannot overlap. An append holds the namespace <i>read</i> lock for its whole run and a rename needs the <i>write</i> side, so the rename finishes before the append resolves the path, or waits until the append has published its bytes. Either way the bytes are safe: a move changes a name in a parent's map and never touches a node's bytes. A caller that arrives after the rename gets <code>NotFoundException</code> for the old path, as on a real file system. Deadlock cannot happen: every thread takes the namespace lock before any file lock, and no thread holds two file locks at once. The test below runs four appending threads against a fifth that renames the folder back and forth; a thirty-second timeout turns a deadlock into a failed run instead of a hung one.",
 T("        // 10. a rename and a write at the same instant", "        // 11. a slow subscriber")),
("The quota refuses a write half way through. What is the state of the file system?", "functional", 8,
 "Exactly what it was. The order is the answer: resolve, take the locks, work out the resulting sizes, reserve them on "
 "the volume counter, ask the guard, and only then publish. A reservation is a number moving, not bytes, so a refusal "
 "releases it and the counter reads what it read before. The bytes are published by a single reference assignment, "
 "which cannot fail half way, and it happens after every step that can say no. On a create the guard is asked before the node is linked into the tree at all. So no empty file is left behind and no inflated file count poisons later quota decisions, which is strictly better than creating it and rolling back. The failure test checks the bytes, "
 "the counter and the absence of the file, all three.",
 sect(src, "void putFile(String path, String content)", "void move(String from, String to)")),
("mv /a into /a/b/c, and rm on a directory that still has children.", "functional", 8,
 "Both are refused, each in one line, because the path was parsed once. Moving a folder into its own subtree would leave it reachable only from itself, so the check asks: is the destination at or under the source? On strings, <code>dst.startsWith(src)</code> is wrong, because <code>/a/bc</code> starts with <code>/a/b</code>; on a list of segments it is exact. Removing a folder that has children throws unless the caller passed recursive. A move that does happen is three pointer operations inside one exclusive lock (unlink the old name, rename the node, link the new one), so nobody sees the node at neither name, and the cost is the same for three descendants or thirty thousand. A move onto a name that exists is refused (Unix <code>mv</code> would replace a file); say which you chose. Datadog turns rm -rf around: with only \"delete one file or one empty folder\", delete a tree children first, with an explicit stack so a deep tree cannot overflow the call stack.",
 sect(src, "void move(String from, String to)", "void delete(String path, boolean recursive)")),
("They hand you LeetCode 588: ls, mkdir, addContentToFile, readContentFromFile. Then Coinbase's stricter mkdir.", "functional", 6,
 "Three of the four calls already exist: <code>ls</code> is <code>ls</code> (a file path lists just its own name, as "
 "588 asks), <code>mkdir</code> is <code>mkdirs</code>, and <code>readContentFromFile</code> is <code>readString</code>. "
 "The fourth, <code>addContentToFile</code>, means create the file if it is missing and add to its end if it is not, "
 "and 588 also makes the missing folders. The adapter (a thin class that maps 588's names onto ours) makes the folders, then calls <code>addContent</code>, which "
 "creates or appends in one step under the write lock. The tempting version, append, catch \"not found\", then create, "
 "lets two first writers both miss, and the second create wipes the first one's text. Test 18 races two first writers fifty times, and both texts always survive. Coinbase and LeetCode 1166 want the strict <code>mkdir</code> instead: "
 "exactly one new level, and an error if the parent is missing or the name is taken. Adobe's follow-up, \"what if the "
 "content is not text?\", is already answered, because the core stores bytes.",
 X("LeetCode 588", "cd and pwd") + "\n// in FileSystem (Main.java)\n" + sect(src, "void mkdir(String path)", "void putFile(String path")
 + sect(src, "void addContent(String path", "private void createOrWrite(")),
("Add cd and pwd: a working directory, relative paths and ~. Then Uber's twist: a * inside cd.", "twist", 8,
 "The working directory belongs to a session, not to the file system, so a <code>Shell</code> owns it and turns every "
 "typed path into an absolute one before the file system sees it. A path that starts with <code>/</code> is absolute, "
 "<code>~</code> is the home folder, and anything else is glued onto the working directory. <code>FsPath</code> then folds <code>.</code> and <code>..</code> as before. <code>cd</code> checks that the target exists and is a folder, "
 "and only then moves, so a failed <code>cd</code> leaves <code>pwd</code> where it was. Say what <code>..</code> above "
 "the root does: this code stays at <code>/</code>, as Meta's reported example does, but some versions want an error, so ask. Uber lets a <code>*</code> segment stand for <code>.</code>, <code>..</code> or any child "
 "folder; <code>cdGlob</code> tries those choices in that order, depth first (one choice is followed to the end before the next is tried), and the first path that reaches a real "
 "folder wins. Symlinks inside <code>cd</code> are the symlink card's walk; test 19 covers the rest.",
 X("cd and pwd", "du in O(1)")),
("du /var must be O(1), and it must stay right while files change.", "non-functional", 8,
 "Keep the answer instead of computing it: every folder holds an <code>AtomicLong</code> of the bytes under it. A file "
 "that grows or shrinks by delta bytes adds delta to its folder and to every folder above it, so <code>du</code> is one "
 "read and a write costs O(depth) instead of nothing. In <code>FileSystem</code> that is a short loop in the write "
 "path, over the folders the walk from the root has just passed. A move takes the folder's bytes out of every old "
 "ancestor and adds them to every new one; a delete takes them out. The counters are atomic because writers to different files add to the same parent at once, and a move takes the write lock, so no write is half-counted. Google asks the same over a map of ids: keep sizes in a <code>long</code>, since "
 "gigabytes overflow an <code>int</code>, and keep a visited set if the input could contain a cycle. Test 20 checks "
 "<code>du</code> against a slow recount after eight threads write and a folder moves.",
 X("du in O(1)", "Runs every extension")),
("Find every .txt over 4 KB, and then the ten biggest files under /var.", "non-functional", 5,
 "The traversal is written once and what changes is a yes/no question about one node, so there is no findByExtension, "
 "then findBySize, then findByExtensionAndSize. The predicates compose: "
 "<code>Filters.extension(\"txt\").and(Filters.largerThan(4096))</code>, and the walk runs under the namespace read "
 "lock so the tree cannot change underneath it. \"The ten biggest\" is the same single walk feeding a heap of ten entries (a heap always knows its smallest entry, so an eleventh pushes the smallest out). That is O(n log 10) time and ten slots of memory, not a sort of everything. "
 "Two more for a big tree. <code>find</code> should return a lazy iterator (one that finds the next hit only when asked) rather than collect every hit. And a listing of two hundred thousand names comes a page at a time. The fifty names after a cursor are read straight off the sorted map in O(log k + 50), and test 16 pages through 100,000 names in about 20 ms.",
 X("millions of files", "one namespace lock is the bottleneck") + "\n// in DirNode (Main.java): the page is read off the sorted map\n"
 + sect(src, "List<String> namesAfter(", "Collection<FsNode> childNodes()")),
("Somebody deletes a file while I am reading it.", "twist", 8,
 "The reader finishes. Delete unlinks the name inside the exclusive lock: the entry leaves its parent's map, and the byte count drops at once, because the counters measure what is reachable by name. Then, outside the lock, each file that left the tree is told. A file nobody has open goes straight to FREED and releases its array. A file somebody has open goes to UNLINKED and keeps its bytes until that handle closes, at which point it "
 "goes to FREED. The handle holds the node rather than the path, which is the whole reason this works. Writing the three states down turns \"what about a reader mid-read?\" from an improvisation into a rule. The other defensible choice, refusing the delete while the file is open, is what Windows does, and it is one branch in the same "
 "place.",
 sect(src, "void acquire()", "\n}\n\n/**\n * A directory") + "\n    "
 + sect(src, "void delete(String path, boolean recursive)", "// ------------------------------------------------ content")),
("Support symlinks. Now make /a point at /b and /b point at /a. And hard links.", "twist", 10,
 "A symlink is a third kind of node holding a target path, and the path walk changes in two ways. At a link, the walk puts the target's segments in front of the ones still to walk and restarts, counting hops. After forty hops it gives up, so /a to /b to /a is an error, not a hang. And <code>..</code> moves into the walk: <code>/shortcut/..</code> is the parent of the folder the link points at, so FsPath's early clean-up of <code>..</code> is wrong once links exist (Java's <code>Path.normalize()</code> carries the same warning; test 17). Nothing else learns that links exist. Hard links are a different shape: split the bytes into an inode (the record that holds a file's bytes, apart from its names) with a count of names, and point two directory entries at it. Deleting a name lowers the count, only the last one frees the bytes, and <code>du</code> must count shared bytes once, by inode identity.",
 X("symlinks", "hard links") + "\n" + X("hard links", "users and permissions")),
("Users and permissions.", "twist", 5,
 "Permissions are a rule that changes, so they go behind a one-method interface exactly like the quota did. Who is "
 "asking is threaded through the API as a value rather than read from a thread local (a hidden per-thread variable), so a test can be any user. The "
 "policy here is owner plus two bits &mdash; may others read, may others write &mdash; and anything more elaborate "
 "(groups, access control lists, inherited permissions) is a different implementation of the same interface. The check sits in front of "
 "the call in a thin wrapper, so <code>FileSystem</code> does not change and never learns what a user is. A rule that "
 "needs no user, like a read-only folder, can live in <code>WriteGuard</code> instead; a per-user rule cannot, because a "
 "<code>WriteRequest</code> carries no user. The table is keyed by path to stay short; a real system keeps the owner "
 "and the bits on the node, so they move with a rename.",
 X("users and permissions", "trash and restore")),
("Make delete recoverable: trash, restore and purge.", "twist", 5,
 "\"Recoverable\" means the file has states rather than a boolean, which is move 6 again. Deleting becomes a move into "
 "a hidden <code>/.trash</code> under a generated id: the name leaves the visible tree, the bytes do not move at all, "
 "and the visible listing is already correct. Restoring is the same move backwards. Purging &mdash; explicitly, or by a "
 "sweeper that walks the trash on a timer under the write lock &mdash; is the only step that actually frees memory. "
 "Every one of those steps reuses a method that already exists, which is the point: a new step in a life costs a state "
 "and a transition, not new machinery. One order matters in restore: claim the record, move the file back, and put the record back if the move fails (the old path is taken again, or its folder is gone). A failed restore then loses nothing; test 14.",
 X("trash and restore", "random access and big files")),
("A ten-megabyte log appended a line at a time, and a write at a byte offset.", "non-functional", 8,
 "One array stops being the right shape at that size, for two reasons. Every append copies the whole file, so appending a line at a time is quadratic (the copying grows with the square of the file size). And a ten-megabyte file needs ten contiguous megabytes. Replace the array with a list of fixed chunks and both go away. Appending fills the tail chunk and adds another, so an append costs only the new bytes, never a copy of the file. A write at an offset touches one chunk instead of rebuilding the file. Read, size and version keep their meaning, "
 "so nothing above the file notices. The related upgrade is the lock. A file that is read far more often than it is written wants a read-write lock. A file edited by a human wants optimistic concurrency instead, because you cannot hold a lock across thirty seconds of typing. The caller reads a version, edits, and writes back only if "
 "nobody got there first.",
 X("random access and big files", "many readers, one writer") + "\n" + X("many readers, one writer", "persistence")),
("The indexer watching /var cannot keep up with the writes. What happens to its events?", "twist", 5,
 "Watchers are told after the unlock, so a slow one never holds a lock, but the writer's own thread still runs the subscriber's code. <code>AsyncWatcher</code> fixes that: each event goes on its own queue and one thread drains it, so the write returns at once. The queue is <i>bounded</i>, because an unbounded one turns a slow subscriber into an out-of-memory error under a write storm. Full means drop and count: the file system never blocks on a subscriber, and <code>dropped()</code> is the number to export. So the stream is at-most-once (each event arrives once or never), and a watcher that must not miss anything reads the journal instead. A watcher on <code>/var/log</code> also hears a file moved out of it (the event carries the old path) and the delete of <code>/var</code> above it; test 12. Test 11 writes two hundred files against a blocked subscriber: the writes take a few milliseconds, 195 events are dropped, and all two hundred files exist.",
 X("a slow watcher", "millions of files") + "\n"
 + T("        // 11. a slow subscriber", "        // 13. a refused call")),
("Survive a restart. And where does time come from in your modified times?", "twist", 8,
 "A journal: every change that succeeded is written as a line &mdash; what was done, to what, with what &mdash; under "
 "one lock, so the journal's order is the order things really happened. The order is apply, then write the line: a "
 "call that is refused (no such file, over quota) throws before its line exists, so it can never come back on replay. "
 "Redis's append-only file works the same way. The only loss is a crash between applying and writing, and that "
 "caller never got an answer. Replay the lines into a fresh file system at boot and you are where you were; test 13 "
 "replays a journal after two refused calls. Time is the smaller half of the same idea. The file system is handed a <code>Clock</code> and stamps every node with it, and nothing else reads the wall clock. So a test can pin an instant, write a file, move the instant a week forward and check the exact modified times.",
 X("persistence", "a slow watcher must not freeze the namespace") + "\n"
 "// where time comes from: handed in, defaulted, never read from the wall clock inside a method\n"
 "interface Clock { long nowMs(); Clock SYSTEM = System::currentTimeMillis; }\n\n"
 "// in a test: pick the instant, then move it\n"
 "long[] now = { 1_700_000_000_000L };\n"
 "FileSystem fs = new FileSystem(() -> now[0]);\n"
 "fs.putFile(\"/a.txt\", \"one\");\n"
 "now[0] += 7L * 24 * 3600 * 1000;                        // a week later\n"
 "fs.append(\"/a.txt\", \" two\");                             // mtime is now exactly a week on\n"),
("Which pattern is where, which SOLID letter is where, and when is a kind an enum rather than a subclass?", "design", 8,
 "None was chosen up front; each is what a move produced, which is the only defence that survives the next question. Composite is move 1: a folder's size is the sum of its children's, and a child may be a folder. Strategy, Decorator and Observer are move 3: the rule that changes sits behind one method, <code>AuditGuard</code> wraps any rule to record what it refused, and the file system announces without knowing who listens (move 4 is why it announces after the unlock). State is move 6. For SOLID the letter worth saying is O: <code>CapacityGuard</code> and <code>ReadOnlySubtreeGuard</code> are each a new file plus one line, and <code>FileSystem</code> is never opened. Factory earns its place the day node kinds arrive as strings, say when a tree is rebuilt from a saved file; Builder never does, because a node has nothing optional. <code>WriteMode</code> is an enum because a mode is data one method branches on; a node kind is a subclass because a file and a directory answer <code>sizeBytes()</code> with different code.",
 "// Composite: one base type, so du and every filter never ask which kind a node is\n"
 "abstract class FsNode { abstract boolean isDirectory(); abstract long sizeBytes(); }\n"
 "final class DirNode extends FsNode {\n"
 "    @Override long sizeBytes() { long s = 0; for (FsNode c : children.values()) s += c.sizeBytes(); return s; }\n"
 "}\n\n"
 "// Strategy: the rule that changes, behind one method, handed in and never built here\n"
 "interface WriteGuard { void check(WriteRequest r); }\n"
 "void configure(WriteGuard guard) { this.guard = guard; }\n\n"
 "// Decorator: add one behaviour to any rule, present or future, without editing it\n"
 "fs.configure(new AuditGuard(WriteGuard.allOf(new CapacityGuard(64, 1024))));\n\n"
 "// Observer: the file system announces; it does not know what an indexer is\n"
 "private void publish(FsEvent e) { /* after every unlock, in a try/catch */ }\n\n"
 "// Null Object: the default rule allows everything, so nothing anywhere tests for null\n"
 "WriteGuard UNLIMITED = r -> {};\n\n"
 "// State: the life of a file, written down instead of improvised\n"
 "enum FileState { LIVE, UNLINKED, FREED }\n\n"
 "// Factory: not yet. Two constructors today; it earns the name when node kinds come from config\n"
 "FsNode made = kind.equals(\"dir\") ? new DirNode(name, now) : new FileNode(name, now);\n\n"
 "// Builder: never, on this problem. A node is a name and two timestamps, nothing optional\n"
 "new FileNode(name, clock.nowMs());\n"),
]

build(dict(
    slug="file-system", title="In-memory File System",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 58 failure checks and three races pass",
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
