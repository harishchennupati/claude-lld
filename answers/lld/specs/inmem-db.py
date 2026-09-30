# In-memory Database LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"inmem-db/Main.java").read_text()
ext   = (H/"inmem-db/Extensions.java").read_text()
tests = (H/"inmem-db/FailureTests.java").read_text()

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
pf += _tx(88, 61, "insert", "var(--acc)", 13)
for k, b in enumerate([("a row, typed, from a client", "four values in column order"),
                       ("check what needs no table", "types, NOT NULL, CHECK: no lock yet"),
                       ("take the table, check the key", "is this primary key still free?"),
                       ("write the row AND every index", "one apply(), so they cannot drift")]):
    x = 155 + k*260
    pf += _bx(x, 30, 245, 54, b[0], b[1], acc=(k == 2))
    if k < 3: pf += _ar("M%s 57 H%s" % (x+245, x+260), True)
pf += _ar("M797 84 V95", dash=True) + _bx(642, 95, 310, 40, "refused: nothing written, no lock taken", "", dash=True)

pf += _tx(88, 176, "commit", "var(--acc)", 13)
pf += _bx(155, 148, 300, 48, "log the batch, then unlock", "tables held until the log has it", acc=True) + _ar("M455 172 H475", True)
pf += _bx(475, 148, 345, 48, "then tell the triggers, one batch", "an audit line, a count")
pf += _tx(845, 166, "the indexes were told long before, inside apply():", "var(--muted)", 11, "start")
pf += _tx(845, 184, "an index is state, a trigger is an announcement", "var(--muted)", 11, "start")

pf += _tx(88, 238, "rollback", "var(--acc)", 13)
pf += _bx(155, 210, 300, 48, "replay the undo log backwards", "apply(after, before), newest first", acc=True) + _ar("M455 234 H475", True)
pf += _bx(475, 210, 345, 48, "then unlock every table", "rows and indexes exactly as before")
pf += _tx(845, 228, "the triggers hear nothing at all: they are only", "var(--muted)", 11, "start")
pf += _tx(845, 246, "ever told about rows that committed", "var(--muted)", 11, "start")

pf += _tx(88, 292, "query", "var(--acc)", 13) + _tx(155, 292, "the row with id 41?  everyone in Pune?  everyone aged 30 to 40?  and which of those was a scan?", "var(--text)", 12, "start")
pf += _tx(615, 326, "many clients at once: one primary key names exactly one row, ever, and no index may ever disagree with the rows", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 342, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("14:02  insert user 41", ["one hash put, two index inserts", "about 0.3 microseconds of lock",
                                "the trigger hears after the unlock"], True),
      ("14:05  two clients, id 41", ["both check, one writes", "the other: duplicate primary key",
                                     "one row, not two, and no lost row"], True),
      ("14:06  orders 14:00 to 14:05", ["a range read on the placed_at index", "6 rows examined of 100,000",
                                        "the same query on total: a scan"], False),
      ("14:07  a client disappears", ["3 orders deleted in a transaction", "rollback puts all three back,",
                                      "and their index entries with them"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+137) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+137)
    pe += _card(x, 60, 275, 110, t, lines, acc=acc)
P_EX = _mv(1230, 185, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Create and drop a table: typed columns, one primary key, NOT NULL, and a CHECK (a rule every row must pass) the caller hands in.</li>
<li>Insert, update, delete and read rows, with the where-clause (the filter: which rows?) as an object rather than a string.</li>
<li>Secondary indexes for equality and for ranges, buildable at any time over rows that already exist.</li>
<li>Transactions: BEGIN, COMMIT, ROLLBACK, SAVEPOINT; a single statement runs in its own transaction.</li>
<li>A write is refused by a duplicate key, a wrong type, a null, a broken CHECK or a foreign key.</li>
<li>Triggers (code the database calls after a commit) hear about every committed change once, as one batch per transaction.</li>
<li>Say which access path (key lookup, index or scan) a query used, so "is this a scan?" has an answer.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many clients at once: one primary key names exactly one row, and no index may disagree with the rows.</li>
<li>By primary key O(1); by an indexed value O(log n) plus one step per hit; a scan called a scan.</li>
<li>Rules, triggers and the locking policy swappable without opening the table or the transaction.</li>
<li>One source of truth: rows and indexes move together, through one method, or not at all.</li>
<li>Nothing half-done: a refused statement (even one that already changed a row) and an abandoned transaction leave the database exactly as it was.</li>
<li>Rollback costs what the transaction touched, never what the table holds.</li>
<li>In memory, one process, no durability (say it; a write-ahead log is a follow-up).</li></ul></div></div>
'''

PROMPT = ('"Build me a small in-memory database. Tables with typed columns and a primary key, indexes so lookups '
          'and range queries are fast, constraints, and transactions that can be rolled back &mdash; and several '
          'clients hitting it at once. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A database here is a box of tables. A table has a fixed '
 'shape &mdash; a list of columns, each with a type &mdash; and a pile of rows. One column is the primary key: its '
 'value names exactly one row. Clients insert rows, change them, delete them and ask for them back. The asking is the interesting part: by primary key ("give me row 41"), by another column ("everyone in Pune"), or by a range '
 '("everyone aged thirty to forty"). None of those may turn into reading every row, so the table keeps indexes, '
 'which are just other maps pointing at the same rows. Writes can be grouped into a transaction that either all '
 'happens or none of it does, so there has to be a way to put things back. And several clients do all this at the '
 'same moment. That is where the two invariants live (rules that must be true at every instant): a primary key '
 'names exactly one row, ever; and no index may point at a row that is not there, or miss one that is.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that creates a table, inserts, queries three ways and rolls a transaction back. The '
 'interviewer is watching for, in this order: the questions you ask before typing (what makes a row valid, and '
 'what two clients are promised, are the first two); which classes exist and which one owns the rows; an insert '
 'end to end; what happens when two clients insert the same key at the same instant; where the rules that will '
 'change live &mdash; a new constraint, a new index, a new listener &mdash; so each is a new class and not an edit; '
 'and what the database looks like after a write is refused half way. Then the twists. A foreign key: a column '
 'that must name a row in another table. A savepoint: a mark inside a transaction you can roll back to. A query '
 'planner: the code that picks how to answer a query. Joins across two tables. MVCC: old versions kept so that '
 'readers never wait. A write-ahead log: every commit written to disk, and replayed after a restart. Sharding: the '
 'rows split across several databases.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Key-value, or tables with typed columns and a primary key?</td><td>Tables, fixed schema, one primary key</td><td>A Schema, a type check, and a row as cells in column order (moves 1, 5)</td></tr>'
 '<tr><td>Which reads must be fast: by key, by a column, by range?</td><td>All three</td><td>A hash map on the key; secondary indexes in TreeMaps, maps kept sorted by key (move 5)</td></tr>'
 '<tr><td>Transactions? Savepoints? Or one statement at a time?</td><td>Transactions with savepoints; a lone statement auto-commits</td><td>An undo log (the old version of every row the transaction changed) per transaction, and the order at the write (move 6)</td></tr>'
 '<tr><td>What do two clients at the same instant get to assume?</td><td>Serialisable (as if the transactions ran one after another), by locking, and say what it costs</td><td>Strict two-phase locking (take each table at first touch, give all back at the end), one lock per table (moves 4, 7)</td></tr>'
 '<tr><td>Lock the table or the row?</td><td>The table first; row locks are the named upgrade</td><td>One lock per table, held first touch to end (moves 4, 8)</td></tr>'
 '<tr><td>When do indexes and listeners learn about a change?</td><td>Indexes with the row; listeners only after a commit</td><td>Index maintenance inside apply(); triggers after the unlock (move 6)</td></tr>'
 '<tr><td>Does it have to survive a restart?</td><td>No: in memory, one process</td><td>No log yet; the follow-up writes one at COMMIT, before the unlock (move 12)</td></tr>'
 '<tr><td>Joins, a planner, MVCC, sharding?</td><td>Out of scope, named</td><td>Each is one of the five twist moves (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One afternoon, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> tables have a fixed schema and one primary key; values are long, '
 'String and boolean, and a wrong type is refused before anything is locked; reads are by key, by an indexed '
 'value or by range, and anything else is a scan I will admit to. One lock per table, taken at the first touch '
 'and held to the end of the transaction. That makes it serialisable: no dirty reads, no non-repeatable reads, no '
 'phantoms (no value that is later rolled back, no row that changes, no row that appears, between two reads). It '
 'also makes deadlock possible: two transactions each waiting for a table the other holds. In memory, one '
 'process. Named as out of scope: durability, MVCC, joins, a cost-based planner, sharding &mdash; each is a '
 'follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a DATABASE holds TABLES; a TABLE has a SCHEMA of COLUMNS, ROWS and INDEXES; a TRANSACTION collects UNDO ENTRIES; a RULE checks; a TRIGGER is told", "var(--text)", 12.5)
for x, w, t, sub, acc in [(25, 150, "Database", "tables, triggers", 1), (190, 150, "Table", "rows, indexes, lock", 1),
                          (355, 145, "Schema", "columns, the key", 1), (515, 120, "Row", "the cells", 1),
                          (650, 130, "Index", "value to keys", 1), (795, 155, "Transaction", "undo log, locks", 1),
                          (965, 115, "Rule", "no state", 0), (1095, 115, "Predicate", "a question", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a check, a question, a lambda", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("is this row allowed?", "RowRule (before the lock) / TableRule (in it)", "rule.check(...): throws or returns"),
                                       ("find the rows that match", "Table  (owns the rows and the indexes)", "table.select(predicate)"),
                                       ("write the row and its indexes", "Table  (the one door for every write)", "table.apply(before, after)"),
                                       ("remember how to undo it", "Txn  (owns the undo log and the locks)", "txn.insert / update / delete"),
                                       ("tell whoever is listening", "Database  (owns the triggers)", "db.publish(batch)")]):
    y = 20 + k*52
    m2 += _bx(25, y, 320, 42, verb, "the verb") + _ar("M345 %s H415" % (y+21), True)
    m2 += _bx(415, y, 420, 42, cls, "the class whose state it touches", acc=True) + _ar("M835 %s H905" % (y+21), True)
    m2 += _bx(905, y, 300, 42, meth, "the method")
m2 += _tx(615, 300, "a verb that touches two classes goes to the one that owns both: the transaction owns the undo log and the locks, so it runs the steps", "var(--muted)", 11)
m2 += _tx(615, 319, "and a delete is not a special verb: it is apply(row, null), which is why an undo is apply(after, before) and nothing else", "var(--muted)", 11)
MV[2] = _mv(1230, 332, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(25, 95, 250, 90, "Database / Table", "configure, addRule, addTrigger", acc=True)
for k, (t, sub, impl) in enumerate([("RowRule", "judged from the row alone", "TypeRule / NotNullRule / CheckRule"),
                                    ("TableRule", "has to read a table", "PrimaryKeyRule / ForeignKeyRule"),
                                    ("Trigger / CommitLog", "who is told; what must survive", "AuditTrigger / CityCount;  WalLog (page 05)"),
                                    ("LockPolicy", "who may touch a table", "StrictTableLocking / NoLocking"),
                                    ("Clock", "where time comes from", "System::currentTimeMillis / a test's long[]")]):
    y = 16 + k*52
    m3 += _ar("M275 140 H330 V%s H390" % (y+21), True, True) + _bx(390, y, 290, 42, t, sub, dash=True)
    m3 += _bx(740, y, 465, 42, impl, "the classes that can be handed in") + _ar("M740 %s H680" % (y+21))
m3 += _tx(615, 300, "dashed green = handed in. The table never builds a rule, so a foreign key is a new class and one addRule line", "var(--muted)", 11)
m3 += _tx(615, 319, "and one wrapper sits over the others: SafeTrigger(t) wraps EVERY trigger, so a listener written next year cannot break a commit", "var(--acc)", 11)
MV[3] = _mv(1230, 332, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(25, 30, 200, 44, "client A: INSERT id 41", "id 41 free? yes") + _bx(25, 112, 200, 44, "client B: INSERT id 41", "id 41 free? yes")
m4 += _bx(350, 71, 190, 44, "users.byPk", "no row 41 yet", acc=True)
m4 += _ar("M225 52 H350 V71") + _ar("M225 134 H350 V115") + _tx(288, 42, "read", "var(--muted)", 10.5) + _tx(288, 162, "read", "var(--muted)", 10.5)
m4 += '<rect x="575" y="20" width="300" height="145" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(725, 45, "the gap", RED, 12) + _tx(725, 70, "both were told the key was free", RED, 11) + _tx(725, 90, "both write: one row is silently lost,", RED, 11) + _tx(725, 110, "and two clients were told they wrote it", RED, 11)
m4 += _tx(725, 145, "fix: check and write as ONE step", "var(--text)", 11)
m4 += _bx(905, 45, 300, 95, "Table.lock", "check the key, write the row and every index", acc=True)
m4 += _tx(1055, 178, "the lock lives where the shared state lives:", "var(--muted)", 10.5)
m4 += _tx(1055, 196, "one lock per TABLE, so two tables never wait", "var(--muted)", 10.5)
MV[4] = _mv(1230, 212, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("give me row 41", "HashMap&lt;pk, Row&gt;", "O(1)"),
                                      ("everyone in Pune", "TreeMap&lt;value, LinkedHashSet&lt;pk&gt;&gt;", "O(log n) + 1 per hit"),
                                      ("everyone aged 30 to 40", "the same TreeMap, subMap(lo, hi)", "O(log n) + 1 per hit"),
                                      ("how do I put this transaction back?", "ArrayList&lt;UndoEntry&gt;, appended", "O(1) add, O(k) undo"),
                                      ("what must the triggers be told?", "ArrayList&lt;Change&gt;, one per row change", "O(1) append"),
                                      ("which table is called users?", "ConcurrentHashMap&lt;name, Table&gt;", "O(1)")]):
    y = 18 + k*44
    m5 += _bx(25, y, 350, 36, q, "the question") + _ar("M375 %s H430" % (y+18), True)
    m5 += _bx(430, y, 470, 36, shape, "the shape", acc=True) + _ar("M900 %s H955" % (y+18), True) + _bx(955, y, 250, 36, cost, "")
m5 += _tx(615, 300, "the index holds primary keys, not rows, so a row moves without the index having to be rebuilt: one map is the truth, the rest are pointers", "var(--muted)", 11)
m5 += _tx(615, 319, "and a row with null in an indexed column is simply not in that index, so a query for it falls back to a scan -- say that out loud", "var(--muted)", 11)
MV[5] = _mv(1230, 332, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(25, 30, 190, 44, "ACTIVE", "holding its tables", acc=True)
m6 += _bx(300, 20, 190, 40, "COMMITTED", "log, unlock, publish") + _bx(300, 88, 190, 40, "ROLLED_BACK", "undo, then unlock")
m6 += _ar("M215 45 H300", True) + _ar("M215 62 H300 V88", True)
m6 += _tx(258, 148, "any operation after the end throws", "var(--muted)", 10.5)
m6 += '<rect x="545" y="14" width="665" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(877, 38, "the order at an insert, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 build the row and check types, NOT NULL, CHECK -- no lock held, nothing written",
                       "2 take the table's lock, and keep it until the transaction ends",
                       "3 now the checks that must READ the table: is this primary key free? does the parent row exist?",
                       "4 only now apply: the row and every index, in one method that cannot fail half way",
                       "5 keep the before-image; at commit: the log, then unlock, then the triggers",
                       "a refused write leaves every row and every index exactly as they were;",
                       "an abandoned transaction is put back from its own undo log, newest change first"]):
    m6 += _tx(560, 62 + k*22, l, "var(--muted)" if k > 4 else "var(--text)", 11, "start")
m6 += _tx(615, 234, "an update or delete of many rows checks them one by one inside the lock; if row 3 is refused, rows 1 and 2 are undone too", "var(--muted)", 11)
MV[6] = _mv(1230, 248, m6)

# move 7: what is inside the lock, and ten clients at the same instant
m7 = _D + _card(25, 20, 555, 150, "inside the lock: about 0.3 microseconds a statement",
                ["one hash lookup: is this primary key taken?", "one hash put: the row",
                 "two TreeMap inserts, about 17 compares each", "a five-statement transaction: about 3 microseconds",
                 "measured on a laptop; held from the first touch to COMMIT"], acc=True)
m7 += _ar("M580 95 H650", True) + _tx(615, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(650, 20, 555, 150, "outside the lock: milliseconds",
            ["building and type-checking the row: before the lock", "the trigger that refreshes a search index: 5 ms, after",
             "the client thinking between two statements: seconds", "-- which is the only reason the lock is ever hot",
             "(a log on disk must flush before the unlock: card 11)"])
m7 += _tx(615, 200, "ten clients commit a five-statement transaction on the same table at the same instant", "var(--text)", 12)
for k in range(10):
    x = 25 + k*119
    m7 += _bx(x, 215, 107, 40, "client %d" % (k+1), "waits %d us" % (k*3), acc=(k == 9))
m7 += _tx(615, 283, "the tenth client waits about 27 microseconds for the table; its triggers then run after the unlock, on its own time:", "var(--muted)", 11)
m7 += _tx(615, 301, "one at a time is true, and nobody can tell, as long as nothing slow is allowed inside the lock -- so never hold a transaction open across a network round trip", "var(--muted)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="232" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per table: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a statement holds the lock about 0.3 us; a five-statement transaction, 3 us",
                       "measured, ten clients: about 300,000 transactions a second on one table",
                       "a chatty client that keeps a transaction open across two round trips",
                       "holds it 200 us instead, and the same table drops to 5,000 a second",
                       "reads take the lock too, so a read-heavy table is what hurts first",
                       "and the second budget, because this is memory: measured, a row is",
                       "about 200 bytes, each index 50 more -- 1 GB holds about 3 million rows"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 keep the lock short, hold nothing slow", "already done: validate before it, publish after it"),
                              ("2 one lock per row, taken in sorted order", "two writers on different rows never meet -- but phantoms come back"),
                              ("3 versions per row (MVCC): readers never block", "a reader takes a snapshot; the price: old versions to clean up")]):
    m8 += _bx(600, 58 + k*50, 605, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 266, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two clients insert the same primary key", "the key check and the write inside one lock; test 1: 50 threads, one winner"),
                                ("a wrong type, a null, a CHECK that fails", "refuse before the lock is taken; test 3: four refusals, nothing written"),
                                ("an update changes an indexed column", "one door removes the old key and adds the new; test 4: the old key finds nothing"),
                                ("a client disappears mid-transaction", "replay the undo log backwards; test 7: every row and index as before"),
                                ("the search-index listener is down", "every trigger is wrapped, and it runs after the commit; test 8"),
                                ("two transactions, two tables, opposite orders", "tryLock with a timeout; the loser rolls back; test 9: nobody hangs"),
                                ("the same query twice inside one transaction", "the table is held to the end, not per statement; test 10: no phantom either"),
                                ("an UPDATE of two rows is refused on row 2", "undo back to where the statement began; test 11: row 1 is put back")]):
    y = 18 + k*42
    m9 += _bx(25, y, 375, 38, bad, "") + _ar("M400 %s H445" % (y+19), True) + _bx(445, y, 760, 38, fix, "", acc=True)
m9 += _tx(615, 376, "every claim this design makes has a test: FailureTests.java runs fourteen of them, sixty-one checks, and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 389, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface LockPolicy / RowRule / TableRule / CommitLog, handed in", None), ("a new constraint is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("addTrigger wraps EVERY trigger in SafeTrigger", None), ("no listener can break a commit", None)],
          [("Observer", "var(--text)"), ("move 6", None), ("db.publish(batch) after the unlock, at commit only", None), ("a rolled-back row reaches nobody", None)],
          [("Memento", "var(--text)"), ("move 6", None), ("the old Row object IS the before-image; undo = apply(after, before)", None), ("rollback costs nothing to prepare", None)],
          [("Command", "var(--text)"), ("move 6", None), ("an UndoEntry is one reversible change; a WAL line is the same thing as text", None), ("undo, and replay after a restart, are one idea", None)],
          [("Interpreter", "var(--text)"), ("move 5", None), ("Eq / Between / And as objects the planner can READ", None), ("a where-clause can choose an index", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the Database is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh database", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("ColType's EnumMap is already the registry of types", "var(--muted)"), ("it earns the name when schemas arrive as DDL text", "var(--muted)")],
          [("Builder", "var(--muted)"), ("not yet", None), ("createTable(name, pk, columns...) is three required things", "var(--muted)"), ("it earns a place when columns gain defaults", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 335, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 350, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 430), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Index answers one question. Table owns rows and the lock. Txn owns the undo log.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("ForeignKeyRule is a new file plus one addRule line", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("the same race runs against StrictTableLocking and NoLocking, byte for byte", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("six interfaces have one method; LockPolicy has two: a lock is given back", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 12", None), ("db.configure(policy, timeout);  db.setClock(() -&gt; now[0]);  db.setLog(wal)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "a foreign key, a CHECK, unique", "a new class behind RowRule or TableRule plus one addRule line", "", "move 3"),
        ("someone new wants to know", "an audit, a count, a cache", "one more trigger; the table and the lock do not change", "", "move 6"),
        ("a new step in a life", "PREPARED, for two-phase commit", "one more transaction state and one more checked transition", "", "move 6"),
        ("a new invariant across rows", "a foreign key, a balance floor", "the check and the writes inside the SAME lock: all or nothing", "", "move 4"),
        ("state that must outlive the process", "persist it; two servers", "a CommitLog appends each batch before the unlock; the row update becomes", "UPDATE users SET city = ?, version = version + 1 WHERE id = ? AND version = ?", "moves 3 + 12")]):
    y = 24 + k*54
    m12 += _bx(25, y, 330, 44, t, sub) + _ar("M355 %s H415" % (y+22), True) + _bx(415, y, 665, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the table, the transaction and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>database</b> holds <b>tables</b>; a table has a <b>schema</b> of "
 "<b>columns</b>, a pile of <b>rows</b> and some <b>indexes</b>; a <b>transaction</b> groups writes and collects "
 "<b>undo entries</b>; a <b>rule</b> decides whether a row is allowed; a <b>trigger</b> is told what changed. A "
 "table has rows, indexes and a lock, all of which change: a class. A row is cells that never change once "
 "written &mdash; an update builds a new row rather than editing one, and that single decision is what makes "
 "undo free later. A schema is fixed at create time, so one instance is shared by every row of the table. An "
 "index has its own map: a class. A transaction has an undo log and a set of held tables: a class. A rule and a "
 "where-clause have no state at all &mdash; they are questions &mdash; so they are interfaces, and a lambda is a "
 "valid implementation of either.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Is this row allowed?\" touches nothing: it reads a row and either throws or returns, so it belongs to a pure "
 "rule. \"Find the rows that match\" touches the rows and the indexes, so it belongs to the table: "
 "<code>table.select(predicate)</code>. \"Write the row and its indexes\" touches the same state, so it is the table again. It is deliberately one method, <code>table.apply(before, after)</code>, so there is exactly one place in the system where a row and its indexes can get out of step. \"Remember how to undo it\" "
 "touches the undo log and the locks, which the transaction owns, so the transaction runs the steps. \"Tell "
 "whoever is listening\" touches the trigger list, which the database owns. Notice what is not a separate verb: "
 "a delete is <code>apply(row, null)</code> and an undo is <code>apply(after, before)</code> &mdash; the same "
 "door, with the arguments swapped.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "What makes a row valid will change: a CHECK today, a foreign key in five minutes, a unique second column after "
 "that. Who is told will change: an audit log today, a materialised count (a total kept up to date as rows change) "
 "tomorrow. What must survive a restart will change: nothing today, a log on disk later. How clients are kept out "
 "of each other's way will change: a table lock today, row locks or MVCC later. Each becomes a small interface the "
 "table or the database is <i>given</i> and never builds. There are two rule interfaces, not one, and the split is "
 "the interesting part. A <code>RowRule</code> can be judged by looking at the row alone, so it runs before any lock "
 "is taken. A <code>TableRule</code> has to read a table (is this key free? does the parent row exist?), so it can "
 "only run inside the lock. This is where the patterns come from: a "
 "swappable rule behind an interface is <b>Strategy</b>; something that announces a change without knowing who is "
 "listening is <b>Observer</b>; and the wrapper the database puts around every trigger it is handed, so a broken "
 "listener cannot break a commit, is <b>Decorator</b>. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two clients insert the same primary key at the same instant. Both ask \"is 41 free?\", both are told yes, both "
 "write, and one row is simply gone &mdash; while both clients were told their insert succeeded, which is worse "
 "than an error. So the check and the write have to be one step, in the class that owns the rows: the table. The "
 "same gap eats an update: two clients read a counter as 100, both write 101, and one increment vanishes. The lock "
 "is per <i>table</i>, not per database, which is the whole trick &mdash; a thousand tables take writes in "
 "parallel and never wait for each other. And it is held from the first touch until the transaction ends, not just "
 "for one statement. That is what makes the undo log safe: nobody else can change a row between the moment this "
 "transaction saved its before-image (the row as it was before the change) and the moment it puts it back.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Give me row 41\" is a hash map from primary key to row: one lookup at any table size. \"Everyone in Pune\" is a secondary index: a map from a column value to the primary keys that hold it. It is a TreeMap rather than a HashMap for one reason: \"everyone aged thirty to forty\" is then a <code>subMap</code> (the slice "
 "of the sorted map between two keys) instead of a scan. The index holds keys, not rows, so a row can be replaced without the index being rebuilt. \"How do I put "
 "this transaction back?\" is a list of before-images, appended, replayed backwards. \"What must the triggers be "
 "told?\" is a second list, one entry per row change, published only if the transaction commits. The where-clause "
 "is a shape too: <code>Eq</code>, <code>Between</code> and <code>And</code> are objects rather than lambdas "
 "precisely so the planner can <i>read</i> them and reach for an index. A lambda predicate is always a scan, and the code says so.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A transaction is ACTIVE, then COMMITTED or ROLLED_BACK, and anything asked of it afterwards throws rather than "
 "quietly doing nothing. Writing that down forces the question the interviewer will ask &mdash; what is the state "
 "of the database when a write is refused half way? &mdash; and the answer is the five-step order in the box. Each "
 "step is there for a reason you should be able to give. The cheap checks come first so that most refusals never "
 "reach the table at all. The checks that must read the table come after the lock because reading and writing have "
 "to be one step. Apply is one method so a row and its indexes cannot move separately. An UPDATE of many rows adds "
 "one case: row 3 can be refused after rows 1 and 2 were written. So a statement notes where the undo log stood "
 "when it began, and a refusal undoes back to that mark; the transaction stays open, and a later COMMIT saves "
 "nothing half done. At COMMIT the batch goes to the log first, while the tables are still held, so a log sees "
 "commits in the order they happened. Only after the unlock are the triggers told: a listener must never run while "
 "a table is held, and must never hear about a row that was later rolled back. That is why an index (state, rolled "
 "back with the row) and a trigger (an announcement about committed rows only) are told at different moments.", 6),
("Move 7: yes, the lock makes one table's transactions happen one at a time. Ask for how long, and what is inside it.",
 "Inside the lock, one statement does a hash lookup, a hash put and one tree insert per secondary index. Measured "
 "on a laptop, that is about 0.3 microseconds. A five-statement transaction holds the table for about 3, counting "
 "the hand-over of the lock from one thread to the next. Everything expensive is outside. The row is built and type-checked before the lock is taken, and the triggers (an audit line, a search-index refresh) run after the "
 "commit released it, each wrapped so it cannot throw into the caller. Ten clients committing on the same table at "
 "the same instant means the tenth waits about 27 microseconds, which nobody notices. One line in that picture is not an "
 "optimisation detail: reads take the lock too, and hold it to the end of the transaction. That looks like waste until you name what it buys: two identical queries inside one transaction see the same database. That is what the word <i>isolation</i> means, and card 5 on page 05 shows what each cheaper promise lets back in.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A third of a microsecond a statement and about three for a five-statement transaction: measured with ten clients, "
 "one table takes about 300,000 such transactions a second, and tables do not wait for each other. A chatty client "
 "that holds the transaction open across two network round trips turns three microseconds into two hundred. The "
 "same table then drops to five thousand a second, which is why the first rung of the ladder is not a data "
 "structure at all. Rungs two and three are in the picture, and each has an honest cost written next to it. Row "
 "locks let phantoms back in (a new row appearing in a range you already read) unless the range itself is locked. "
 "Versions per row need a garbage collector for the old versions, and give up serialisability for snapshot "
 "isolation (each transaction reads the database as it was when it began). There is a second budget in an "
 "in-memory database, and it is the one that ends the conversation: memory. Measured, a four-column row costs about "
 "two hundred bytes of Java objects and each secondary index about fifty more. With two indexes that is three "
 "hundred bytes a row, so a gigabyte holds about three million rows. Past that you are not tuning a lock: you are "
 "buying RAM, or sharding. Say both numbers before you climb: a rung nobody costed is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The table above pairs each one with the test that proves it, and three of them are worth a sentence more. The refusals (a wrong type, a null in a NOT NULL column, a failed CHECK, the wrong number of values) all happen before the lock is even taken. So the test checks not only that no row was added, but that the table was not left locked either: the bug people actually ship. Then the quiet one: a report that runs the "
 "same query twice inside one transaction and gets two different answers. That cannot happen here, because the table is held to the end of the transaction rather than released after each statement. Test 10 runs the scenario twice, once with the lock and once without, and asserts both outcomes. The last row is the "
 "one most designs miss: an UPDATE of two rows whose second row breaks a CHECK. Test 11 commits after the refusal "
 "and finds the first row exactly as it was. A design that cannot show its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table above is the answer; these are the three that need a sentence of defence. Memento is the one this "
 "problem really earns: the before-image is the old <code>Row</code> object itself, so a rollback costs nothing "
 "to prepare &mdash; free precisely because rows are immutable and an update builds a new one. Command sits next to it: every change is an object holding its before and after. Undoing it is applying it backwards, and the commit batch can be written to a log as text and replayed after a restart. Interpreter is move 5: the where-clause is a little tree the planner can read "
 "rather than a lambda it cannot see into, which is the only reason a query can reach for an index at all. The three greyed rows matter as much as the six above them. Singleton earned nothing here, and Factory and Builder each have a specific day they would: schemas arriving as DDL text (CREATE TABLE statements), and a column gaining defaults. A "
 "pattern without a move behind it is decoration, and an interviewer can tell.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "S: each class has one reason to change, which move 2 gave you &mdash; an index changes when the answer to one "
 "question changes, the table when storage does, the transaction when transaction rules do, and nobody does two of "
 "those. O: a foreign key is a new file and one <code>addRule</code> line; nothing in Table or Txn is opened. L: "
 "the same fifty-thread race runs byte-identically against <code>StrictTableLocking</code> and "
 "<code>NoLocking</code> and nothing asks which policy it got &mdash; which is how the demo can print the lost "
 "update appearing and then not appearing. I: seven interfaces, six of them one method, so a fake in a test is a "
 "lambda; <code>LockPolicy</code> has two because a lock has to be given back. D: the database is handed its lock "
 "policy, its clock, its log and its triggers. That is exactly why a test can hand it a clock that says last "
 "Tuesday, a log that fails, and a trigger that throws on purpose.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The first four are read off the table above. The useful habit is saying which one a twist is before you start typing: for a new rule, which of the two rule interfaces it is <i>tells you</i> whether it runs "
 "before the lock or inside it. The fifth is the one that goes furthest: state that must outlive the process. At "
 "COMMIT, before the locks are released, the batch is appended to a log on disk, and a failed append fails the "
 "commit. Replaying the log against an empty database rebuilds exactly the committed state, and the same log is "
 "what you ship to a replica (a copy of the database on another machine). On a real database the in-memory "
 "read-modify-write then becomes <code>UPDATE users SET city = ?, version = version + 1 WHERE id = ? AND version "
 "= ?</code>. Zero rows updated means somebody got there first: the database took the same all-at-once step our "
 "lock did. For all five the table, the transaction and the tests do not change; that is the test "
 "that the derivation was right. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, BookMyShow) and the class diagram, the lock, the "
 "tests, the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and "
 "nothing is named before the move that produced it. On this problem two moves carry most of the weight: move 5, "
 "because a database is nothing but the right collection behind each question, and move 6, because the order of "
 "operations is what a transaction actually is.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the transaction, what it records, and the policies handed in
put("txn", 25, 20, 245, "Txn",
    ["db: Database", "id: long", "undo: List&lt;UndoEntry&gt;", "pending: List&lt;Change&gt;",
     "held: LinkedHashSet&lt;Table&gt;", "state: TxnState"],
    ["insert(table, values...)", "update(table, where, set)", "delete(table, where)", "select(table, where) / table(t)",
     "savepoint() / rollbackTo(n)", "commit() / rollback()", "explain(table, where)"])
put("undo", 25, 322, 245, "UndoEntry", ["table: Table", "before: Row", "after: Row"], [])
put("change", 25, 424, 245, "Change", ["table: String", "schema: Schema", "kind: ChangeKind", "before / after: Row"], [])
put("plan", 25, 550, 245, "Plan", ["how: String", "candidates: List&lt;Row&gt;"], [])
put("lockp", 25, 640, 245, "LockPolicy", [], ["acquire(table, timeoutMs)", "release(table)"], "interface")
put("locki", 25, 734, 245, "StrictTableLocking", [], ["tryLock(table, timeout)", "NoLocking: does nothing"])
put("clock", 25, 818, 245, "Clock", [], ["nowMs(): long"], "interface")
# centre column: the root and what it owns
put("db", 320, 20, 340, "Database",
    ["tables: Map&lt;name, Table&gt;", "triggers: List&lt;SafeTrigger&gt;", "locks: LockPolicy / lockTimeoutMs",
     "clock: Clock", "log: CommitLog"],
    ["createTable(...) / dropTable(name)", "configure(policy, timeoutMs)", "addTrigger / setLog / setClock",
     "begin(): Txn", "insert / update / delete / select", "publish(batch)"])
put("table", 320, 268, 340, "Table",
    ["name: String", "schema: Schema", "byPk: Map&lt;pk, Row&gt;", "indexes: Map&lt;col, Index&gt;",
     "rowRules / tableRules", "lock: ReentrantLock"],
    ["createIndex(column): Index", "checkRow(row) / checkTable(...)", "apply(before, after)",
     "plan(where): Plan", "select(where): List&lt;Row&gt;", "row(pk) / allRows()"])
put("exc", 320, 730, 340, "ConstraintViolation | LockTimeout",
    [], ["thrown when a statement is refused;", "nothing of it stays: fix it, or retry"])
put("index", 320, 560, 340, "Index",
    ["column: String", "tree: TreeMap&lt;value, Set&lt;pk&gt;&gt;"],
    ["add(row, pk) / remove(row, pk)", "eq(value): Set&lt;pk&gt;", "range(lo, hi): List&lt;pk&gt;", "keyCount(): int"])
# third column: the data types and the enums
put("schema", 700, 20, 230, "Schema", ["cols: List&lt;Column&gt;", "pos: Map&lt;name, int&gt;", "pk: int"],
    ["pos(name): int", "pkIndex() / pkName()", "col(i): Column"])
put("column", 700, 200, 230, "Column", ["name: String", "type: ColType", "notNull: boolean"], [])
put("row", 700, 308, 230, "Row", ["cells: Object[]", "version: long", "atMs: long"],
    ["get(schema, col)", "pk(schema): Object", "with(schema, set, ...)", "show(schema): String"])
put("coltype", 700, 488, 230, "ColType", ["INT, TEXT, BOOL"], ["accepts(v): boolean", "Values.norm: int to long"], "enum")
put("ckind", 700, 588, 230, "ChangeKind", ["INSERT, UPDATE, DELETE"], [], "enum")
put("tstate", 700, 664, 230, "TxnState", ["ACTIVE, COMMITTED,", "ROLLED_BACK"], [], "enum")
put("clog", 700, 748, 230, "CommitLog", [], ["append(batch): before unlock"], "interface")
# fourth column: the rules and the listeners, handed in
put("pred", 950, 20, 250, "Predicate", [], ["test(schema, row): boolean"], "interface")
put("predi", 950, 94, 250, "Eq | Between | And | All", [], ["test(...), read by the planner", "made by Where.eq / between / and"])
put("rowrule", 950, 194, 250, "RowRule", [], ["check(schema, row)"], "interface")
put("rowrulei", 950, 268, 250, "TypeRule | NotNullRule", [], ["CheckRule too, all handed in", "throws ConstraintViolation"])
put("tablerule", 950, 348, 250, "TableRule", [], ["check(txn, table, b, a)"], "interface")
put("tablerulei", 950, 422, 250, "PrimaryKeyRule", [], ["reads the table, inside the lock"])
put("trigger", 950, 502, 250, "Trigger", [], ["afterCommit(batch)"], "interface")
put("safet", 950, 576, 250, "SafeTrigger", ["inner: Trigger (wrapped)", "failures: AtomicInteger"], ["afterCommit in try/catch"])
put("trigi", 950, 690, 250, "AuditTrigger | CityCount", [], ["afterCommit(batch)"])
put("extra", 950, 764, 250, "ForeignKeyRule | WalLog", ["+ RestrictDeleteRule; they sit", "behind TableRule / CommitLog"], [], "Extensions.java")

EDGES = [
 # the root owns the tables, a table owns its indexes
 ln(B["db"]["b"], B["table"]["t"], "compose", "tables"),
 ln(B["table"]["b"], B["index"]["t"], "compose", "indexes"),
 # the transaction: what it records, and what it locks
 ln(B["txn"]["b"], B["undo"]["t"], "compose", "undo log"),
 ln((25, 200), (25, 466), "compose", "", [(12, 200), (12, 466)]),
 ln(B["txn"]["r"], (320, 380), "assoc", "locks, reads, writes"),
 ln((270, 600), (320, 470), "assoc", "returns"),
 ln(B["locki"]["t"], B["lockp"]["b"], "inherit"),
 # the rules and the listeners are handed in
 ln((660, 430), (950, 219), "inject", "", [(940, 430), (940, 219)]),
 ln((660, 450), (950, 373), "inject", "", [(932, 450), (932, 373)]),
 ln((660, 120), (950, 527), "notify", "", [(924, 120), (924, 527)]),
 ln((320, 140), (270, 665), "inject", "", [(290, 140), (290, 665)]),
 ln((320, 170), (270, 845), "inject", "", [(282, 170), (282, 845)]),
 ln((660, 226), (700, 775), "inject", "", [(692, 226), (692, 775)]),
 # the table reads the predicate to plan
 ln((660, 350), (950, 47), "assoc", "", [(916, 350), (916, 47)]),
 # the implementations
 ln(B["predi"]["t"], B["pred"]["b"], "inherit"),
 ln(B["rowrulei"]["t"], B["rowrule"]["b"], "inherit"),
 ln(B["tablerulei"]["t"], B["tablerule"]["b"], "inherit"),
 ln(B["safet"]["t"], B["trigger"]["b"], "inherit"),
 ln(B["trigi"]["t"], (1215, 560), "inherit", "", [(1075, 672), (1215, 672), (1215, 560)]),
 # the data types
 ln(B["schema"]["b"], B["column"]["t"], "compose", "columns"),
 ln((930, 241), (930, 512), "assoc", "", [(942, 241), (942, 512)]),
 ln(B["table"]["r"], (700, 90), "assoc", ""),
 ln((660, 300), (700, 350), "assoc", ""),
 ln((660, 640), (700, 400), "assoc", "", [(680, 640), (680, 400)]),
 _tx(645, 852, "the index points at primary keys, never at rows, so a row is replaced without the index being rebuilt", "var(--muted)", 11),
 _tx(645, 874, "everything in the fourth column is handed in: nothing here builds a rule, a trigger or a lock policy", "var(--muted)", 11),
 ln(B["table"]["l"], B["exc"]["l"], "assoc", "", [(296, 385), (296, 765)]),
]
UMLSVG = uml_svg(1230, 930, EDGES, legend_y=908)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a '
 'fixed list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow '
 'triangle = implements. Filled diamond = owns: the database owns the tables, a table owns its indexes, a '
 'transaction owns its undo log. Plain arrow = references. Dashed green = handed in and never built here: the '
 'rules, the lock policy, the clock, the log. Dotted blue = notifies. <b>Where state lives:</b> the table has the rows, the '
 'indexes, the rules and the one lock &mdash; everything that can change. The schema and every row are immutable, '
 'which is why one schema is shared by a million rows, and why the old row object can be kept as the undo image for '
 'free. The transaction has the undo log, the tables it is holding and the batch it will publish if it commits. '
 'The database has the tables, the triggers, the log, the lock policy and the clock, and no row state at all, which is '
 'exactly why a table can be locked without locking the database. <b>One box is not from Main.java:</b> the '
 '&laquo;Extensions.java&raquo; box at the bottom right is page 05\'s code, drawn so you can see that a foreign '
 'key and a write-ahead log are new classes behind interfaces that already exist. Notice what is <i>not</i> here: '
 'no Query class, because a query is a predicate plus a table; and no Transaction Manager, because a transaction '
 'manages itself.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it does; read only those first for the shape, then the bodies for the mechanics. '
 'Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s '
 'reference code, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (fourteen claims, sixty-one checks; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> '
 'prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (what makes a row valid, and what two clients are '
 'promised, come first). Main.java is far more than an hour of typing, so know the must-write core: about 250 lines. In typing order: ColType and Column, Schema, an immutable Row, Eq and Between, one TreeMap Index, Table (its key map, its one apply() and a three-if planner), the primary-key check inside the lock, Txn (the order at insert, the undo log, commit and rollback), Database with begin(), and a main with fifty threads on one primary key. Only if time is left: the rule interfaces, triggers with SafeTrigger, savepoints, EXPLAIN, and the '
 'LockPolicy and CommitLog seams &mdash; which is what the follow-ups below ask for.</div></div>')

FU = [
("Mid-round: \"a row in orders must name a real user, and a user with orders cannot be deleted.\"", "functional", 8,
 "A foreign key is a new class behind the TableRule interface plus one addRule line; nothing in Table or Txn is "
 "opened. It is a TableRule and not a RowRule because it has to read another table, which is also why it runs "
 "inside the lock rather than before it. The rule is handed the transaction rather than the database, so its read of the parent table takes that table's lock, like any other read, and holds it to the end. So a parent row cannot be deleted out from under a child insert. The other direction is a second rule on the parent that counts "
 "the children before allowing a delete. Both refusals leave the database exactly as it was: the refused row is never written, and a DELETE of many rows refused half way is undone.",
 X("a foreign key", "an index added at run time")),
("Two clients insert the same primary key at the same instant. Prove you cannot end up with two rows, or none.", "non-functional", 10,
 "The race lives between \"is this key free?\" and the write. Both checks happen inside the table's lock, held by "
 "the transaction from the first touch, so no other writer can run in that gap. The proof is a count rather than "
 "an argument: fifty threads wait on one latch and all insert the same key, and exactly one is told it succeeded "
 "while exactly one row exists. Fifty more threads insert fifty distinct keys at the same moment, and all fifty "
 "land &mdash; so the lock is not hiding a lost write. The last check is the one people forget: every secondary "
 "index must hold exactly those fifty keys, because a row and its index entries move together in one method or "
 "the database is quietly corrupt.",
 T("        // 1. fifty threads insert the SAME primary key", "        // 2. a duplicate primary key is refused")),
("One lock per table. Have you serialised the database? And how big can this thing get?", "non-functional", 8,
 "Per table, not per database, so a thousand tables take writes in parallel. Inside the lock one statement is a "
 "hash lookup, a hash put and one tree insert per index: about 0.3 microseconds, measured. A five-statement "
 "transaction holds the table for about 3, so one table takes about 300,000 of them a second. The number that "
 "hurts is the client that runs BEGIN and then waits for two network round trips before COMMIT. That holds the "
 "table for two hundred microseconds and drops it to five thousand a second, which is why rung one is keeping the "
 "lock short rather than any data structure. Rung two is the code below, a lock per row taken in sorted order. Its "
 "honest cost: a table lock also stopped rows from <i>appearing</i>, so phantoms come back unless the range itself "
 "is locked; rung three is the next card. The other ceiling is memory, because that is all there is here: measured, "
 "about 200 bytes a row plus 50 per index, so a gigabyte holds about three million rows with two indexes. Past that "
 "the answer is not a lock but sharding by primary key: each database owns a slice of the keys. A transaction that "
 "spans two shards then needs two-phase commit (every shard first promises it can commit, then all of them do), so "
 "COMMIT can now fail.",
 X("row-level locks", "sharding by primary key")),
("My reporting queries are queueing behind every writer. Give me readers that never wait.", "twist", 8,
 "Stop making readers take a lock at all: that is MVCC, and it is what every real database ended up doing. Every "
 "key keeps a chain of versions stamped with the commit number that wrote it, and a writer appends a new version "
 "instead of overwriting, so nothing a reader is looking at is ever changed under it. A reader takes a snapshot "
 "&mdash; the commit number at the moment it starts &mdash; and reads the newest version at or before it, so it never waits for a writer and never sees a half-finished transaction. A delete is a version too, a tombstone (a marker saying the row is gone from this commit on), which is how an older snapshot still sees a dropped row. Name the two costs before the interviewer does. First, dead versions pile up until something collects them, which is what <code>vacuum</code> is for (an LSM store, built from append-only sorted files, deletes with the same tombstones and calls its vacuum compaction). Second, two transactions can each commit against "
 "the same snapshot, so snapshot isolation is not serialisable. The example for that last one is write skew &mdash; "
 "two transactions read the same two rows, each changes a different one, and together they break an invariant "
 "neither broke alone.",
 X("MVCC", "row-level locks")),
("What isolation level is this? Show me a dirty read, a non-repeatable read and a phantom.", "non-functional", 8,
 "It is SERIALIZABLE, and it gets there the crude way. A transaction takes a whole table the first time it touches "
 "it and holds it to the end, so nobody can change a row it read or add a row to a range it scanned. The three "
 "anomalies are three things one transaction can see: a <b>dirty read</b> is a value written by a transaction that "
 "later rolls back; a <b>non-repeatable read</b> is the same row read twice with two different values; a "
 "<b>phantom</b> is the same range read twice with a row in it that was not there before. <code>Isolation.run</code> "
 "plays each one out with two threads &mdash; a reader counts the rows in Pune, a writer is let loose, the reader "
 "counts again &mdash; under both lock policies. With <code>StrictTableLocking</code> the counts are 1 then 1 all "
 "three times; with <code>NoLocking</code> they are 1 then 2, 1 then 0 and 1 then 2; test 10 asserts both. Every "
 "weaker level keeps the tables it WROTE locked to the end and differs only in its reads. READ UNCOMMITTED takes no "
 "read locks, so it allows dirty reads. READ COMMITTED releases a table it only READ at the end of each statement, "
 "which lets non-repeatable reads back in. REPEATABLE READ keeps read locks to the end but on rows, not the table, "
 "which is exactly why phantoms come back. <code>NoLocking</code> is worse than all four: it drops the write locks "
 "too, which is how the demo loses most of its fifty updates.",
 X("isolation levels", "TTL rows")),
("A constraint fails half way through a write. What is the state of the database?", "functional", 8,
 "Exactly what it was. The row is built and checked against the type, NOT NULL and CHECK rules before the lock is "
 "taken and before anything is written, so most refusals never reach the table at all. The checks that must read "
 "the table (is the key free? does the parent exist?) happen inside the lock but still before any write. What follows them is a single method that puts the row and every index entry in together. An UPDATE or DELETE of many "
 "rows is the one place a refusal can come after a write: row 2 fails after row 1 changed. So the statement notes "
 "where the undo log stood when it began and undoes back to there; the transaction stays open, and test 11 commits "
 "after the refusal and finds nothing half done. The machine-coding versions of this prompt ask for a string of at "
 "most 20 characters, an int between -1024 and 1024, a required column: each is one CheckRule or NOT NULL.",
 sect(src, "Row insert(String table, Object... values)", "/** Delete every row matching")
 + "\n" + sect(src, "private void undoStatement", "/** The table, locked")),
("\"Give me everyone aged thirty to forty\" over a hundred thousand rows, without a scan.", "functional", 5,
 "The secondary index is a TreeMap from column value to the primary keys that hold it, so a range is a subMap: one "
 "descent to find the start, then one step per row you actually return. Equality on an indexed column is a single "
 "tree lookup, and equality on the primary key is a hash lookup that never touches an index at all. The planner is "
 "three ifs over the where-clause: the primary key first, then an index probe, then an index range, and only then a scan. It names the path it took, so \"is this a scan?\" is a question the code answers rather than a guess. That is the payoff for making Eq and Between objects instead of lambdas: a lambda cannot be read, so a "
 "lambda predicate is always a full scan.",
 sect(src, "Plan plan(Predicate p)", "List<Row> select(Predicate p)") + "\n"
 + sect(src, "final class Index", "record Plan")),
("API version: select(columns, where, orderBy). Sort by city, then oldest first; names only.", "functional", 8,
 "This is how the prompt is often asked: create a table, insert, then select(columns, where, order_by), built level "
 "by level. The rows come from the same planner as before (key, index or scan); only the k matched rows are then "
 "sorted, O(k log k), never the whole table. Each sort key is a column and a direction (\"age DESC\"), and the keys "
 "chain with <code>thenComparing</code>, so two users in the same city are ordered by age. A range read through a "
 "TreeMap index already returns rows in that column's order, and Java's sort notices a sorted list and makes one "
 "pass. The column list is the last step: each row is cut down to the columns asked for. Test 14 checks both orders.",
 X("ORDER BY", "joins")),
("An update changes a column that is indexed. What has to happen, and what usually goes wrong?", "twist", 8,
 "The old index entry has to go and a new one has to arrive, and the usual bug is that some code path writes the "
 "row without doing it. That is why there is exactly one method that ever changes a row: apply(before, after) "
 "removes the before-image from every index, writes the row, then adds the after-image to every index. An insert "
 "is apply(null, row), a delete is apply(row, null), and an undo is apply(after, before) &mdash; the same door in "
 "reverse. With one door there is exactly one place a row and its indexes could get out of step, and the tests "
 "check the old value finds nothing afterwards while the new one finds the row.",
 sect(src, "void apply(Row before, Row after)", "Row build(Database db")),
("The client ran three statements and disappeared. And: I want SAVEPOINT.", "twist", 10,
 "Every write appends a before-image to the transaction's undo log, so a rollback is that log replayed backwards "
 "through the same apply() &mdash; rows and index entries land back exactly where they were. It costs what the "
 "transaction touched, never what the table holds, and it is free to prepare because rows are immutable: the old "
 "row object IS the before-image, so nothing is copied. A savepoint is then almost nothing: the length of the undo log at that moment. ROLLBACK TO undoes entries back to that mark and stops. The transaction stays open and, importantly, keeps its locks: releasing them early is what would reopen the lost update. The pending batch for the triggers is trimmed the same way, so a rolled-back statement is never "
 "published. Who calls rollback when a client vanishes? Whoever holds the transaction: here the caller's "
 "try/catch, the same shape as the autocommit methods; a server does it when the connection drops.",
 sect(src, "int savepoint()", "void commit()") + "\n" + sect(src, "void commit()", "private void releaseAll()")),
("Two transactions, two tables, opposite order. Show me the deadlock and what you do about it.", "non-functional", 8,
 "Strict two-phase locking makes deadlock possible by construction: T1 holds users and wants orders while T2 holds "
 "orders and wants users, and neither will ever let go. The code does not pretend otherwise: every acquisition is a tryLock with a timeout. The transaction that runs out of patience rolls back, which releases everything it held, and throws a LockTimeout the client can retry. The alternative is a "
 "waits-for graph: who waits for whom, where a cycle is a deadlock and one transaction in it (the victim) is "
 "aborted. It catches the cycle at once and never aborts a transaction that was merely slow, at the cost of "
 "bookkeeping on every acquisition; a timeout is the honest one-line answer, and you say which you chose and why. "
 "The test proves both halves: somebody gave up, and every row still present belongs to a transaction that committed.",
 T("        // 9. a deadlock", "        // 10. the isolation")),
("Make it survive a restart.", "twist", 8,
 "Durability is the database's CommitLog slot. At COMMIT the batch is appended "
 "to the log while the transaction still holds its tables, and only then are the locks released. So the log's "
 "order is the commit order, and replaying it against an empty database rebuilds exactly the committed state; test "
 "12 slows the first committer's disk and still finds the insert before the update. The log is not wrapped like a "
 "trigger: if the append throws (disk full), the commit fails and is rolled back, so no client is told "
 "\"committed\" for a change the log does not have. The price is the fsync (the call that forces bytes onto the "
 "disk, about a millisecond) inside the lock, which caps one table near a thousand commits a second. Group commit "
 "(one fsync for every transaction waiting at that moment) buys it back, or Redis's default: one fsync a second, "
 "at the risk of losing that second. A real log also writes each batch's length and a checksum, so replay stops cleanly at a batch a crash cut in half; a snapshot every so often lets the old log be deleted. The SQL version, a conditional UPDATE, is in the code below.",
 X("persistence", "MVCC")),
("Join users to orders. Which algorithm, and when does the other one win?", "twist", 8,
 "Nested loop walks the left table and probes the right table's index once per row. It is cheap when the left side is small and the right side is indexed, and terrible when neither is true. Hash "
 "join builds a map from the smaller table, then streams the larger one past it: one pass over each, no index "
 "needed, but the build side has to fit in memory. So the rule of thumb is: an index on the join column and a "
 "small left side means nested loop; two big unindexed tables mean hash join; already-sorted inputs mean a merge "
 "join (walk the two sorted lists side by side), the third one worth naming. Both read the two tables inside one "
 "transaction, so the join sees one consistent database while others write. Both return the same rows, which the "
 "demo asserts &mdash; a join is a choice of algorithm, never a choice of answer.",
 X("joins", "persistence")),
("Which index did that query use, and what if two are usable? And add an index at run time.", "design", 8,
 "Main's planner takes the first usable path in a fixed order: primary key, index probe, index range, scan. The "
 "cost-based version prices every usable path by how many rows it would examine and takes the cheapest. So city = 'Pune' AND name = 'Bela' examines one row through the name index instead of two through the city index; test 13 counts them. It can price exactly because probing an index is cheap at this size. A real planner keeps histograms (counts of rows per range of values), because probing millions of rows to plan a query would cost "
 "more than running it. Adding an index later is one call: it is filled from the rows already there, so it is "
 "complete the moment it exists, and from then on the table's single apply() maintains it like any other. Do it "
 "while nothing else is running: creating an index is not transactional here, and saying so is better than pretending.",
 X("EXPLAIN", "ORDER BY") + "\n" + X("an index added at run time", "EXPLAIN")),
("Where does time come from, and how do you test something that expires?", "design", 3,
 "The database is handed a Clock, and it stamps every row it writes; nothing else reads the wall clock. So a sweeper "
 "for a TTL (time to live: how old a row may get) is a few lines: everything stamped longer ago than the TTL is deleted. The deletes are ordinary transactions, so the indexes, the undo log and the triggers all behave exactly as they do for a hand-typed DELETE. A test moves the clock instead of sleeping: insert a row, advance the long by a minute, "
 "insert another, sweep with a thirty-second TTL, and exactly one row goes.",
 X("TTL rows", "Runs every extension")),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "None of the patterns was chosen up front; each is what a move produced, and the code below is the one line "
 "behind each name. The two worth defending out loud are Memento and Interpreter. The before-image is the old <code>Row</code> object itself, free because rows are immutable. The where-clause is a little tree the planner can <i>read</i>, which is the only reason a query can reach for an index: hand it a lambda and it is a full scan every time. For SOLID: S is move 2, O is the foreign key (a new file and one <code>addRule</code> "
 "line), L is the same fifty-thread race running byte-identically against two lock policies, I is seven interfaces "
 "with six of them one method, and D is <code>configure()</code>, <code>setClock()</code> and <code>setLog()</code>. Factory earns its "
 "place the day schemas arrive as DDL text (CREATE TABLE statements), because the column-type map is already the registry. A new column type, which the machine-coding versions ask for, is one enum constant and one line in that map. Builder earns its "
 "place the day a column gains a default value and other options &mdash; today <code>createTable</code> takes a name, a key "
 "and the columns, and all three are required.",
 "// Strategy: what makes a row valid, who may touch a table, where commits are kept -- all handed in\n"
 "interface RowRule   { void check(Schema s, Row row); }                 // judged from the row alone: before the lock\n"
 "interface TableRule { void check(Txn txn, Table t, Row before, Row after); }  // has to read a table: inside the lock\n"
 "interface LockPolicy { boolean acquire(Table t, long timeoutMs); void release(Table t); }\n"
 "interface CommitLog { void append(List<Change> batch); }             // at COMMIT, before the unlock; never wrapped\n\n"
 "// Decorator: every trigger handed in gets the same guarantee, written once\n"
 "SafeTrigger addTrigger(Trigger t) { SafeTrigger s = new SafeTrigger(t); triggers.add(s); return s; }\n\n"
 "// Observer: committed batches only, after every lock is released\n"
 "void commit() { db.log().append(batch); state = COMMITTED; releaseAll(); db.publish(batch); }\n\n"
 "// Memento + Command: the old row IS the before-image, and undo is the same door in reverse\n"
 "record UndoEntry(Table table, Row before, Row after) {}\n"
 "e.table().apply(e.after(), e.before());                 // rollback, newest change first\n\n"
 "// Interpreter: a where-clause the planner can READ (a lambda would always be a scan)\n"
 "record Eq(String col, Object val) implements Predicate { ... }\n"
 "if (q instanceof Eq e && e.col().equals(schema.pkName())) return new Plan(\"primary key lookup\", ...);\n\n"
 "// Factory: not yet. ColType's EnumMap is already the registry; DDL text would make it a factory\n"
 "static { JAVA.put(INT, Long.class); JAVA.put(TEXT, String.class); JAVA.put(BOOL, Boolean.class); }\n\n"
 "// Builder: not yet. Three required things; defaults and collations per column would change that\n"
 "db.createTable(\"users\", \"id\", Column.intCol(\"id\", true), Column.text(\"name\", true));\n"),
]

build(dict(
    slug="inmem-db", title="In-memory Database",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 14 failure tests and a 50-thread race pass",
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
