# Splitwise LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"splitwise/Main.java").read_text()
ext   = (H/"splitwise/Extensions.java").read_text()
tests = (H/"splitwise/FailureTests.java").read_text()

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
# what the code must do: add an expense, settle up, and the reads as a line
pf = _D
rows = [("add an expense", 30, [("someone paid a bill", "who paid, how much, who shares"),
                                ("the rule makes the shares", "sums to the bill, to the paise"),
                                ("apply them under the lock", "all of it, or none of it"),
                                ("tell the participants", "after the lock, never inside it")]),
        ("settle up",     160, [("bob hands alice money", "all of the debt, or part of it"),
                                ("an expense of a special kind", "payer bob, one share: alice"),
                                ("same rule, same lock", "the ledger moves the other way"),
                                ("that pair reads zero", "and drops out of the map")]),
        ("edit or delete", 234, [("last week's bill was wrong", "or it never happened at all"),
                                ("reverse the STORED shares", "the same numbers, sign flipped"),
                                ("both halves in one lock", "a reverse, then the new version"),
                                ("the row is kept, not erased", "marked EDITED or DELETED")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V95", dash=True) + _bx(400, 95, 310, 40, "rejected: nothing is written", "", dash=True)
pf += _tx(88, 324, "read", "var(--acc)", 13) + _tx(175, 324, "at any moment, without re-reading the expenses: what is my net?  what does bob owe alice?  which few payments would clear us?", "var(--text)", 12, "start")
pf += _tx(88, 350, "members", "var(--acc)", 13) + _tx(175, 350, "join at any time; leave only when their net is zero, and then no debt may name them", "var(--text)", 12, "start")
pf += _tx(615, 385, "many people post at the same time: every balance must always sum to exactly zero, and nothing is ever half-applied", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 400, pf)

# one evening, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("20:10  dinner, Alice pays", ["3000.00 split equally across three", "shares 1000.00 / 1000.00 / 1000.00",
                                    "alice +2000.00", "bob -1000.00, carol -1000.00"], True),
      ("20:40  chai, Bob pays 1.00", ["100 paise across three: 34 / 33 / 33", "the odd paise goes to the payer, Bob",
                                      "nothing is lost: they sum to 100"], False),
      ("21:00  Carol's exact split", ["a 500.00 bill, shares add up to 400.00", "rejected before a single write",
                                      "every balance is exactly as it was"], False),
      ("21:30  Bob settles with Alice", ["bob owes alice 1000.00 minus 0.33", "a settle-up of 999.67",
                                         "the pair reads zero and is dropped"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Add an expense: one member paid, a set of members share it.</li>
<li>Three ways to split: equally, by exact amounts, by percentage &mdash; and a fourth on request.</li>
<li>Every split resolves to per-person shares that add up to the bill to the paise.</li>
<li>Read a person's net (what they are owed overall, minus what they owe) and any pair's "A owes B".</li>
<li>Settle up: a payment, in full or in part, that moves the pair toward zero.</li>
<li>Edit and delete an expense, keeping what was there before.</li>
<li>Suggest payments that would clear the whole group: at most one fewer than the people with a balance.</li>
<li>Let a member leave, but only once their net is exactly zero; no debt may name them afterwards.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many people posting at once: no update may be lost, and every balance must sum to exactly zero.</li>
<li>Money is exact: integer paise, never a double, never a lost paise.</li>
<li>"What is my net?" and "what does A owe B?" are O(1), never a re-read of the expenses.</li>
<li>Split rules swappable without touching the group or the ledger.</li>
<li>One source of truth for the balances: the group's ledger, behind one lock.</li>
<li>Nothing half-done: a rejected expense leaves every balance exactly as it was.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design Splitwise. People in a group log shared expenses &mdash; one person pays, the cost is split '
          'among some of them, equally or by exact amounts or by percentage &mdash; and the app tracks who owes '
          'whom and lets them settle up. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A group of people share costs. Somebody pays for '
 'something &mdash; a hotel, a cab, dinner &mdash; and the cost is divided among the people who were there. The '
 'division can be equal, or exact amounts per person, or percentages. Every division has to come out to the bill '
 'exactly: if three people split a hundred paise, the shares are 34, 33 and 33, and the extra paise has to go '
 'somewhere rather than vanish. Each division moves a running record of who owes whom (the ledger), so anybody can ask '
 '"what am I owed?" or "what do I owe Bob?" without the app re-reading a year of expenses. When somebody pays a friend back, '
 'that is recorded too, and the pair moves toward zero. Several people in the same group add expenses at the same '
 'moment. The one thing that must always be true is that the balances sum to exactly zero: every paise somebody '
 'owes is a paise somebody else is owed.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that adds a few expenses and prints the balances. The interviewer is watching for, in '
 'this order: the questions you ask before typing (the money type and the leftover paise are the first two); which '
 'classes exist and which one owns the balances; adding an expense end to end; what happens when two people post '
 'at the same instant; where the rule that will change (how to split) lives, so a fourth way is a new class and not '
 'an edit; what happens when the numbers do not add up. Then the twists: simplify the debts and the true minimum, '
 'settle up, edit and delete, one user across many groups, somebody leaving with a debt open, multi-currency, and the '
 'tables once it is persisted.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>How is money represented, and what happens to the leftover paise?</td><td>Integer paise; the leftover goes to the payer</td><td><code>long</code>, never <code>double</code>; a remainder rule that always gives the same answer (moves 5, 9)</td></tr>'
 '<tr><td>Which ways of splitting, and will there be more?</td><td>Equal, exact, percent; yes, more later</td><td>The split rule behind a one-method interface (move 3)</td></tr>'
 '<tr><td>Balances pairwise ("A owes B") or one net figure per person?</td><td>Both, kept in step; each pair netted to one number</td><td>Two maps written by one method (move 5)</td></tr>'
 '<tr><td>Can several people post to one group at the same time?</td><td>Yes</td><td>One lock per group; the app object only finds the group and calls it (moves 4, 7)</td></tr>'
 '<tr><td>Can an expense be edited or deleted, and is there an audit trail (every old version kept)?</td><td>Yes, and nothing is erased</td><td>A status on the expense and stored shares as the undo (move 6)</td></tr>'
 '<tr><td>Is a settle-up always the exact amount owed?</td><td>No, any amount</td><td>A settle-up is just an expense of a special kind (move 2)</td></tr>'
 '<tr><td>One process and in memory, or a database and many servers?</td><td>One process, in memory</td><td>No repository yet; a follow-up adds one (move 12)</td></tr>'
 '<tr><td>Multi-currency, recurring bills, a simplify-debts toggle?</td><td>Out of scope, named</td><td>Each is one of the five twist moves (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One evening, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> money is integer paise and never a double; the leftover paise from an '
 'uneven split goes to the payer, the same way every time; balances are kept both as a net per person and as a '
 'who-owes-whom pair, written by one method so they cannot drift; one group, one lock, in memory, one process. Named '
 'as out of scope: multi-currency, recurring expenses, persistence, auto-simplify, one user\'s total across groups; each '
 'is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a USER pays an EXPENSE; a GROUP holds MEMBERS and BALANCES; a SPLIT RULE makes SHARES; a SETTLE-UP clears a pair", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 170, "User", "an id, nothing that moves", 0), (228, 180, "Group", "members, ledger, expenses", 1),
                          (436, 200, "Expense", "payer, total, shares, status", 1), (664, 150, "Share", "one person's paise", 1),
                          (842, 170, "Split rule", "no state: an interface", 0), (1040, 160, "Balance", "a question: a method", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it holds state that moves, so it becomes a class.   dashed = nothing that moves: an id, a calculation, or a question", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("turn a bill into shares", "SplitStrategy  (owns no state: pure)", "rule.split(total, payer, parts)"),
                                       ("move who owes whom", "Ledger  (owns the two maps)", "ledger.apply(payer, shares, +1)"),
                                       ("record an expense", "Group  (owns the ledger, the log, the lock)", "group.addExpense(...)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 213, "a verb whose state is spread over two classes goes to the class that owns both: that class becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 232, "and a settle-up is not a new verb: it is an expense paid by the debtor with one participant, the creditor", "var(--muted)", 11)
MV[2] = _mv(1230, 245, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 92, 220, 90, "Group", "configure(...) and setClock(...)", acc=True)
for k, (t, sub, impl, isub) in enumerate([("SplitStrategy", "equal, exact, percent, weights", "EqualSplit / ExactSplit / PercentSplit / SharesSplit", "the classes that can be handed in"),
                                    ("SimplifyStrategy", "greedy, the exact minimum, or none", "MinCashFlow, or FewestPayments for small groups", "the classes that can be handed in"),
                                    ("ExpenseObserver", "push, email, analytics", "PushNotifier, an email digest, a lambda", "the classes that can be handed in"),
                                    ("Clock", "where \"now\" comes from", "System::currentTimeMillis, or () -&gt; fixedInstant", "the real clock, or a test's frozen one")]):
    y = 24 + k*60
    m3 += _ar("M250 137 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, isub) + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 292, "dashed green = handed in. The group never builds one of these, so a fourth way to split is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 312, "and one rule wraps the others: CheckedSplit(rule) enforces \"the shares add up to the bill\" for every rule, including the ones written next year", "var(--acc)", 11)
MV[3] = _mv(1230, 325, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 190, 44, "Ravi's phone", "reads alice = -500.00") + _bx(30, 110, 190, 44, "Meera's phone", "reads alice = -500.00")
m4 += _bx(350, 70, 190, 44, "alice's net", "-500.00", acc=True)
m4 += _ar("M220 52 H350 V70") + _ar("M220 132 H350 V114") + _tx(285, 40, "read", "var(--muted)", 10.5) + _tx(285, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="20" width="290" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(725, 45, "the gap", RED, 12) + _tx(725, 70, "both read -500, both write", RED, 11) + _tx(725, 90, "one expense simply vanishes", RED, 11)
m4 += _tx(725, 130, "fix: read and write as ONE step", "var(--text)", 11)
m4 += _bx(900, 40, 300, 100, "Group.lock", "compute, check, apply = one step", acc=True)
m4 += _tx(1050, 165, "the lock lives where the shared state lives", "var(--muted)", 10.5)
m4 += _tx(1050, 185, "one lock per GROUP: two groups never wait", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is my net?", "Map&lt;user, long paise&gt;", "O(1)"),
                                      ("what does bob owe alice?", "Map&lt;user, Map&lt;user, long paise&gt;&gt;", "O(1)"),
                                      ("have I applied this expense already?", "Map&lt;expenseId, Expense&gt;", "O(1)"),
                                      ("what changed, and when?", "List&lt;Expense&gt;, append only", "O(1) append")]):
    y = 20 + k*50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 240, "the two maps are written by ONE method, from one signed number, so \"A owes B\" and \"B owes A\" can never drift apart", "var(--muted)", 11)
MV[5] = _mv(1230, 255, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(30, 30, 200, 44, "RECORDED", "live, and in the balances", acc=True)
m6 += _bx(300, 30, 200, 44, "EDITED", "a newer version replaced it") + _bx(30, 120, 200, 44, "DELETED", "reversed, the row kept")
m6 += _ar("M230 52 H300", True) + _ar("M130 74 V120", True)
m6 += '<rect x="560" y="20" width="650" height="180" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(885, 44, "the order when an expense is added, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 compute the shares and check them -- the lock is not taken, nothing is written",
                       "2 take the lock; check the id has not been used and everyone is a member",
                       "3 only now apply the changes: map arithmetic that cannot fail half way",
                       "4 append to the log, release the lock, then tell the phones",
                       "a rejected expense leaves every balance exactly as it was and the client can retry;",
                       "the same expense id posted twice is applied once and returns the first one"]):
    m6 += _tx(575, 68 + k*22, l, "var(--muted)" if k > 3 else "var(--text)", 11, "start")
m6 += _tx(615, 220, "three states and one rule: nothing is written until everything has been checked. A delete reverses the STORED shares, so it is exact.", "var(--muted)", 11)
MV[6] = _mv(1230, 235, m6)

# move 7: what is inside the lock, and ten people at the same instant
m7 = _D + _card(30, 20, 540, 150, "inside the lock: about 2 microseconds",
                ["check the expense id in a map", "check every participant is a member",
                 "per person in the split: two net updates, one pair update", "put the expense in a map and a list",
                 "about a dozen map operations per person: ~40 for four"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside the lock: milliseconds to seconds",
            ["the split arithmetic: done BEFORE the lock is taken", "the push notification: about 50 ms, after unlock",
             "the database write: about 5 ms (a follow-up)", "the person typing the amount: seconds"])
m7 += _tx(615, 200, "ten flatmates press add at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "phone %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%d" % (k*2)), acc=(k == 9))
m7 += _tx(615, 283, "the tenth phone waits eighteen microseconds for the lock and then fifty milliseconds for its own push notification:", "var(--muted)", 11)
m7 += _tx(615, 301, "one at a time is true, and nobody can tell, because nothing slow is allowed inside the lock", "var(--muted)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per group: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of a four-person expense: ~40 map operations, about 2 us",
                       "a busy trip group: 40 expenses a day, one every 36 minutes",
                       "even at 100 expenses a second into ONE group: 200 us of lock a second",
                       "that is 0.02% busy; two writers in one group collide about never",
                       "the lock is per GROUP, so ten million groups never meet at all"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 notify and persist outside the lock", "already done: the phones hear after the unlock"),
                              ("2 one atomic merge per pair", "a group of thousands: a concurrent map keyed by the pair"),
                              ("3 the database takes over the lock", "one transaction per expense: lock the group's row, then paise = paise + ?")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("exact shares do not add up to the bill", "reject before any write; test 2: every balance is identical afterwards"),
                                ("1.00 split three ways", "34 / 33 / 33, the odd paise to the payer; test 3: they sum to 100"),
                                ("money kept in a double", "integer paise everywhere; test 10: the same 1000 splits in a double drift"),
                                ("two phones post at the same instant", "one lock per group; test 1: 50 threads, sums to zero, matches one thread"),
                                ("the same expense id posted twice", "the id is the idempotency key; test 9: applied once, the first one returned"),
                                ("an expense was wrong, or never happened", "reverse the STORED shares; test 4: back to the old numbers exactly"),
                                ("somebody leaves while they owe money", "refused until the net is zero; then their debts pass through them; test 11"),
                                ("a rule written next year loses a paise", "CheckedSplit wraps every rule; test 8: nothing at all was written")]):
    y = 18 + k*42
    m9 += _bx(30, y, 300, 38, bad, "") + _ar("M330 %s H380" % (y+19), True) + _bx(380, y, 820, 38, fix, "", acc=True)
m9 += _tx(615, 376, "also in the file: settle-ups (5), simplify (6), push gateway down (7), ladder rung 2 (12), one group per id (13), true minimum (14), many groups (15)", "var(--muted)", 11)
m9 += _tx(615, 396, "fifteen scenarios, fifty-nine checks: FailureTests.java must print ALL PASS or the page does not build", "var(--acc)", 11)
MV[9] = _mv(1230, 410, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface SplitStrategy { List&lt;Share&gt; split(total, payer, parts); }", None), ("a fourth way to split is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new CheckedSplit(rule) wraps EVERY rule inside configure()", None), ("no rule can ever lose a paise", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(e) after the unlock, inside a try/catch", None), ("the phones hear; the ledger never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("RECORDED &rarr; EDITED / DELETED, checked before every write", None), ("an illegal move cannot happen", None)],
          [("Command", "var(--text)"), ("move 6", None), ("the Expense IS the command: its stored shares are its undo", None), ("delete and edit are exact reversals", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the app object is handed to the callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh Splitwise", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("the SplitType &rarr; rule map IS the registry, one line per type", "var(--muted)"), ("it earns the name when types come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("not yet", None), ("every argument is required, and only the group builds an Expense", "var(--muted)"), ("it earns a place when receipts and tags arrive", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Ledger: the two maps. Group: the flow and the lock. A rule: the arithmetic.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("SharesSplit is a new class plus one line in configure()", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("rule.split(total, payer, parts);  never \"is this the percent one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("SplitStrategy, SimplifyStrategy, ExpenseObserver, Clock: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("move 3", None), ("group.configure(rules, new MinCashFlow());  group.setClock(() -&gt; t)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "split by weights, by adjustment", "a new class behind SplitStrategy plus one configure line", "", "move 3"),
        ("someone new wants to know", "an email digest, analytics, fraud", "one more observer; the ledger and the lock do not change", "", "move 4"),
        ("a new step in a life", "pending approval, disputed", "one more status and one more checked transition", "", "move 6"),
        ("a new invariant across people", "nobody leaves owing or owed money", "the check and the write inside the SAME lock: all or nothing", "", "move 4"),
        ("state that must outlive the process", "persist it; two servers", "the two maps behind a repository; each expense is one transaction", "lock the group's row, insert the expense once by its id, then paise = paise + ?", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five, nothing already written is rewritten; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>user</b> pays an <b>expense</b>; a <b>group</b> holds <b>members</b> and their "
 "<b>balances</b>; a <b>split rule</b> turns the bill into <b>shares</b>; a <b>settle-up</b> clears a pair. A "
 "group has members, a ledger and a list of expenses, all of which change: a class. An expense has a payer, a "
 "total, the shares it was split into and a status: a class. A share is two fields that never change once "
 "computed: a record (Java's one-line class for fixed values). A user has an id and a name and nothing that moves, "
 "so the ledger stores the id and a rename can never move money. A split rule has no state at all (it is a "
 "calculation), so it is an interface, not a class with fields. And a balance is not a thing to store twice: it is "
 "a question the group answers from the ledger it already has.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Turn a bill into shares\" touches nothing at all: it reads an amount and a list and returns a list, so it "
 "belongs to a pure rule, <code>rule.split(total, payer, parts)</code>. \"Move who owes whom\" touches the two "
 "balance maps, so it belongs to the thing that owns them: <code>ledger.apply(payer, shares, +1)</code>. \"Record "
 "an expense\" touches the ledger, the expense log and the lock at once. Only the group sees all three, so "
 "<code>group.addExpense(...)</code> is the orchestrator (the one method that calls the others in the right "
 "order). And notice what is <i>not</i> a new verb: a settle-up. Bob handing Alice five hundred rupees is an "
 "expense paid by Bob with exactly one participant, Alice, owing all of it. Same method, same lock, same reversal, "
 "which is why a mistaken settle-up can be deleted like any other expense.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "How a bill is divided will change: equal today, by weights tomorrow, by adjustments the day after. How debts are "
 "simplified will change: greedy today (the biggest debtor pays the biggest creditor, again and again), or no "
 "simplifying at all if the group does not trust it. Who is told will change: a push today, an email digest and "
 "analytics later. And where \"now\" comes from changes the moment you write a test, so the clock is handed in too; "
 "that is the fourth. Each becomes a one-method interface the group is <i>given</i> and never builds. This is "
 "where the patterns come from, not the other way round: a swappable rule behind an interface is <b>Strategy</b>, "
 "and a rule that wraps another rule and adds to it is <b>Decorator</b>. Here Decorator is the one that matters: "
 "<code>CheckedSplit</code> wraps every rule the group is handed and refuses any result whose shares do not add up "
 "to the bill. So a rule written next year cannot put a lost paise into the ledger. A group that announces \"an "
 "expense landed\" without knowing what a phone is, is <b>Observer</b>. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two flatmates add an expense at the same instant. Both read Alice's net as minus five hundred, both add their "
 "own amount to it, and both write it back. One of the two expenses simply disappears from the balances, and "
 "nobody notices, because the balances still look plausible. So reading the ledger and writing it must be one "
 "atomic step (one that no other thread can see half done), in the class that owns both maps: the group. The lock "
 "is per <i>group</i>, not per application, which is the whole trick. Ten million groups post expenses in parallel "
 "and never wait for each other; the five people inside one group take turns, each holding the lock for about two "
 "microseconds. Anything that only listens (the push notification) is called after the lock is released, never "
 "inside it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What is my net?\" is a map from user to signed paise: positive means the group owes you. \"What does Bob owe "
 "Alice?\" is a map from user to a map from user to paise. \"Have I applied this expense already?\" is a map from "
 "expense id to expense, which is what makes a retried request safe. \"What changed and when?\" is an append-only "
 "list (rows are only ever added at the end). Nothing here re-reads the expense history to answer a balance; that "
 "re-reading is what makes a clone slow exactly when a group gets busy. The one subtlety: the pairwise map is "
 "written by a single method from a single signed number, so \"A owes B\" and \"B owes A\" are two views of one value "
 "and cannot drift. A pair that reaches zero is deleted, so a settled group costs no memory. This is double-entry "
 "book-keeping under another name: every paise added to one person is taken from another in the same step. It is "
 "why the nets always sum to zero, and why the race test can check that sum.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An expense is RECORDED when it lands, EDITED when a newer version replaces it (the old row is kept), and DELETED "
 "when it is reversed (the row is kept too). Nothing is ever erased, which is what an audit trail means. Writing "
 "the states down forces the question the interviewer will ask: what if the numbers do not add up? The answer is "
 "an order. First compute the shares and check them, with the lock not yet taken and nothing written. Then take "
 "the lock, hand back the earlier expense if this id was already applied, and check that every participant is a "
 "member. Only then apply the changes to the balances: map arithmetic that cannot fail half way. A rejected "
 "expense leaves every balance exactly as it was, and a retried expense id is applied once. And because the shares "
 "are <i>stored</i> on the expense rather than recomputed, a delete is the same arithmetic with the sign flipped: "
 "an exact reversal, to the paise.", 6),
("Move 7: yes, the lock makes one group's expenses happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every expense takes the group's lock, is Splitwise "
 "now a queue? It is, for about two microseconds, and only for the people in that one group. Inside the lock there "
 "is a map lookup for the id and a membership check per person. Then come two net updates and one pair update per "
 "person in the split, and two collection writes: about a dozen map operations per person, some forty for a "
 "four-person dinner. Everything slow is outside it. The split arithmetic happens before the lock is taken, on "
 "purpose: it is the part that can throw, so it must not be able to leave the ledger half-written. The push "
 "notification, about fifty milliseconds, happens after the unlock, inside a try/catch. So when ten flatmates "
 "press add at the same instant, the tenth waits about eighteen microseconds for the lock, then fifty milliseconds "
 "for its own notification.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A busy trip group logs forty expenses in a day, which is one every thirty-six minutes, against a lock held for "
 "two microseconds. Even if you invented a group posting a hundred expenses a second, that is two hundred "
 "microseconds of lock in every second: busy two hundredths of one per cent of the time. And the lock is per "
 "group, so the number of groups is irrelevant. Then the ladder, in the order you would climb it. First, keep the "
 "notification and the persistence outside the lock, which this code already does. Second, for a group with "
 "thousands of members, replace the single lock with one atomic merge per pair on a concurrent map (a "
 "ConcurrentHashMap, safe for many threads with no lock of ours). The map is keyed by the two ids in sorted order, "
 "so unrelated pairs never wait; that rung is written out on page 05, and what it costs you is that an expense is "
 "no longer one step. Third, beyond one process, use one database transaction per expense. It locks the group's "
 "row first (<code>SELECT ... FOR UPDATE</code>, a lock held until the commit), inserts the expense once, and adds "
 "each share with <code>SET paise = paise + ?</code>. The expense id is the idempotency key (a unique id per "
 "request, so a retry that arrives twice is applied once). That is the database doing what the lock did. Say the "
 "arithmetic first: climbing the ladder without it is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The table is the list; this is what it is for. Every row above is a claim this design makes, and a claim with no "
 "test behind it is just a sentence you said confidently. So each row names the test that proves it. Each test is "
 "small enough to write in the last ten minutes of the hour: post fifty expenses from fifty threads and add up the "
 "balances; hand the group a rule that deliberately loses a paise and check that nothing was written; delete the "
 "same expense twice. Notice the shape of the good ones: they check <i>arithmetic</i>, not counts. A lost update "
 "is invisible in a count of expenses, but it shows in the sum of the balances and in a comparison with the same "
 "fifty expenses posted by one thread. When the interviewer asks \"how do you know?\", the answer should be a line "
 "number.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table names them; these are the three you would otherwise get wrong. Decorator here is not the usual wrapper "
 "around a service: <code>CheckedSplit</code> adds one invariant, that the shares add up to the bill, to every "
 "rule the group is handed, including rules nobody has written yet. Command is hiding in plain sight: an expense "
 "stores the shares it was applied with, so the expense <i>is</i> its own undo log. That is why a delete or an "
 "edit is exact, rather than a recomputation that might round differently. And the \"not yet\"s matter more than the "
 "yeses in a round like this. Factory earns its name the day split types arrive as configuration strings, and "
 "Builder the day an expense grows optional fields. Saying so is what separates a design from a pattern shopping "
 "list.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is the answer; the rule is that a letter with no line of code beside it has not been earned. The one "
 "worth pausing on is D: the group is <i>handed</i> its split rules, its simplifier and its clock, and builds none "
 "of them. That is exactly why a test can give it a clock that says last Tuesday and a split rule that "
 "deliberately loses a paise. It is not a diagram property: it is the difference between a design you can test in "
 "the last ten minutes and one you cannot.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (weights, or adjustments like \"Bob pays 50 more, the rest equal\") is a new class behind "
 "<code>SplitStrategy</code> plus one line in configure. Someone new who wants to know (an email digest, "
 "analytics, a fraud check) is one more observer. A new step in a life (pending approval, disputed, or a settle-up "
 "waiting for a real payment to confirm) is one more status and one more checked transition. A new invariant "
 "across people (nobody may walk out of a group owing or owed money) is the check and the write inside the "
 "<i>same</i> lock, all or nothing: that is <code>removeMember</code>. State that must outlive the process "
 "(persist it; two servers) is the two maps behind a repository interface. Each expense becomes one transaction: "
 "lock the group's row, insert the expense once by its id, then add each share with <code>paise = paise + "
 "?</code>. That is the database's version of the same lock and the same all-or-nothing step. For all five, "
 "nothing already written is rewritten; that is the test that the derivation was right.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, BookMyShow) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On this problem the moves are load-bearing in a way they are not on a parking "
 "lot, because the invariant (the one rule that must always hold) is arithmetic: every balance must sum to exactly "
 "zero, forever.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the callers, the listeners, the value types
put("app", 10, 20, 230, "Splitwise", ["groups: Map&lt;id, Group&gt;", "users: Map&lt;id, User&gt;"],
    ["newGroup(id, members): Group", "groupOrCreate(id, members)", "group(id): Group"])
put("obs", 10, 165, 230, "ExpenseObserver", [], ["onExpense(groupId, e)"], "interface")
put("push", 10, 250, 230, "PushNotifier", [], ["onExpense(...) &rarr; a phone"])
put("clock", 10, 335, 230, "Clock", [], ["nowMs(): long"], "interface")
put("user", 10, 420, 230, "User", ["id: String", "name: String"], [])
put("money", 10, 520, 230, "Money", [], ["rupees(\"12.50\"): long", "fmt(paise): String"])
# centre column: the aggregate root and what it owns
put("group", 300, 20, 320, "Group",
    ["id: String", "members: Set&lt;String&gt;", "ledger: Ledger", "live: Map&lt;id, Expense&gt;",
     "log: List&lt;Expense&gt;", "lock: ReentrantLock", "splits: Map&lt;SplitType, SplitStrategy&gt;",
     "simplifier / clock / observers"],
    ["configure(splits, simplifier)", "addExpense(id, payer, total, type, parts)", "settleUp(id, from, to, paise)",
     "edit(...) / delete(id)", "addMember(u) / removeMember(u)", "netOf(u) / owes(a, b) / balances()",
     "simplify() / history()"])
put("expense", 300, 335, 320, "Expense",
    ["id / groupId / payerId: String", "kind: ExpenseKind", "totalPaise: long", "shares: List&lt;Share&gt;",
     "version: int", "status: ExpenseStatus", "atMs: long,  note: String"], ["markStatus(s)"])
put("ledger", 300, 540, 285, "Ledger",
    ["net: Map&lt;user, paise&gt;", "owes: Map&lt;user, Map&lt;user, paise&gt;&gt;"],
    ["apply(payer, shares, +1 | -1)", "netOf(u) / owed(a, b)", "passThrough(u): when u leaves",
     "netSnapshot() / owesSnapshot()"])
# third column: the enums and the value records
put("stype", 660, 20, 250, "SplitType", ["EQUAL, EXACT, PERCENT"], [], "enum")
put("kind", 660, 110, 250, "ExpenseKind", ["BILL, SETTLEMENT"], [], "enum")
put("status", 660, 200, 250, "ExpenseStatus", ["RECORDED, EDITED, DELETED"], [], "enum")
put("part", 660, 300, 250, "Participant", ["userId: String", "rawValue: long (paise | bp)"], [])
put("share", 660, 410, 250, "Share", ["userId: String", "paise: long"], [])
put("transfer", 660, 520, 250, "Transfer", ["from / to: String", "paise: long"], [])
# fourth column: the rules that are handed in
put("split", 950, 20, 260, "SplitStrategy", [], ["split(total, payer, parts)", "  : List&lt;Share&gt;"], "interface")
put("checked", 950, 130, 260, "CheckedSplit", ["base: SplitStrategy (wrapped)"], ["split(...): asserts the sum"])
put("simp", 950, 250, 260, "SimplifyStrategy", [], ["simplify(net): List&lt;Transfer&gt;"], "interface")
put("mcf", 950, 340, 260, "MinCashFlow", [], ["two heaps: the biggest debtor", "pays the biggest creditor"])
put("rem", 950, 450, 260, "Remainder", [], ["payerFirst(payer, parts)", "spread(parts, order, base, extra)"])
# the bottom row: the three concrete split rules, on one inheritance bus
put("equal", 600, 620, 190, "EqualSplit", [], ["base = total / n", "extra paise to the payer"])
put("exact", 800, 620, 195, "ExactSplit", [], ["each declares paise", "must add up to the bill"])
put("percent", 1005, 620, 225, "PercentSplit", [], ["basis points: 3333 = 33.33%", "must add up to 10000"])

def stub(x, y1, y2):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x, y1, x, y2)

EDGES = [
 # the three split rules implement the interface, on one bus around the right edge
 ln(B["equal"]["t"], (1210, 55), "inherit", "", [(695, 600), (1222, 600), (1222, 55)]),
 stub(897, 620, 600), stub(1117, 620, 600),
 ln(B["checked"]["t"], B["split"]["b"], "inherit"),
 ln((950, 167), (950, 45), "assoc", "", [(925, 167), (925, 45)]),
 ln(B["mcf"]["t"], B["simp"]["b"], "inherit"),
 ln(B["push"]["t"], B["obs"]["b"], "inherit"),
 # the group owns the expenses and the ledger
 ln(B["group"]["b"], B["expense"]["t"], "compose", "every version"),
 ln((300, 161), (300, 601), "compose", "", [(284, 161), (284, 601)]),
 # the expense points at its enums and its shares
 ln((620, 480), (660, 443), "assoc", "", [(630, 480), (630, 443)]),
 ln((620, 440), (660, 225), "assoc", "", [(641, 440), (641, 225)]),
 ln((620, 410), (660, 135), "assoc", "", [(652, 410), (652, 135)]),
 # the rules are handed in through configure()
 ln((620, 272), (950, 62), "inject", "", [(944, 272), (944, 62)]),
 ln((620, 286), (950, 272), "inject", "", [(936, 286), (936, 272)]),
 _tx(905, 266, "the rules, handed in", "var(--acc)", 10.5, "end"),
 ln((300, 100), (240, 192), "notify", "", [(262, 100), (262, 192)]),
 ln((300, 140), (240, 362), "inject", "", [(272, 140), (272, 362)]),
 # the callers and the values
 ln(B["app"]["r"], (300, 77), "assoc", ""),
 ln((240, 120), (240, 453), "assoc", "", [(248, 120), (248, 453)]),
 ln((950, 290), (910, 553), "assoc", "", [(920, 290), (920, 553)]),
 ln((950, 45), (910, 333), "assoc", "", [(930, 45), (930, 333)]),
]
UMLSVG = uml_svg(1230, 745, EDGES, legend_y=715)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the group owns every version of every expense and owns the ledger. Plain arrow = '
 'references: an expense points at its status, its kind and its shares. Dashed green = handed in &mdash; the split '
 'rules and the simplifier through <code>configure()</code>, the clock through <code>setClock()</code>. Dotted blue = '
 'notifies. <b>Where state lives:</b> the ledger has the two balance maps and '
 'nothing else. The group has the members, the ledger, every expense version, the handed-in rules and the one lock. An '
 'expense keeps the shares it was split into, which is what makes a delete an exact reversal. A split rule has no '
 'state at all, which is why one instance can serve every group. Notice what is <i>not</i> here: no Balance class, because a '
 'balance is a question the ledger answers, and no Settlement class, because a settle-up is an expense with one '
 'participant.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (fifteen scenarios, fifty-nine checks; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (money type and leftover paise first); then type in the '
 'order of Main.java: the three enums, the Money helpers, the records (User, Participant, Share, Transfer), the Clock, '
 'the SplitStrategy interface with its three rules and the CheckedSplit wrapper, the SimplifyStrategy with min cash '
 'flow, the observer, Expense, Ledger, then Group with its lock and the order at addExpense, then the thin Splitwise '
 'caller, then a main with fifty threads. If the clock runs out, the one thing that must exist is addExpense: the three '
 'split rules checked to the paise, then the net map and the pair map updated under the group\'s lock. Settle-up, edit, '
 'delete, leaving and simplify come after.</div></div>')

FU = [
("Product wants a fourth way to split: by shares, 2:1:1, so a couple pays double a single.", "functional", 10,
 "The split rule is already an interface, so this is one new class and one line. It adds up the weights and gives "
 "each participant total &times; weight / units, rounded down. The last participant gets whatever paise are left "
 "over, so the shares still come out to the bill. Nothing else moves: the group, the ledger, the lock and the "
 "tests are untouched, and CheckedSplit polices the new rule exactly as it polices the old ones. The one seam that "
 "is not free is that SplitType is an enum, so a brand-new constant is the single extra edit; key the registry "
 "(the map from split type to rule) by String and even that disappears.",
 X("a fourth way to split", "fairness")),
("Two people add an expense to the same group at the same instant. Prove you cannot lose one, with a test.", "non-functional", 10,
 "The race lives between reading a balance and writing it back. addExpense does that whole read-modify-write "
 "inside one lock held by the group (the id check, the membership check, every net and pair update), so no other "
 "writer can run in that gap. The proof is arithmetic rather than a count: fifty threads wait on one latch (a gate "
 "that opens for all of them at once), all fifty post an expense to the same five-person group, and the test adds "
 "up every balance. If a single update had been lost, the total would be non-zero, because a lost credit has no "
 "matching lost debit. The test also checks that the two maps agree for every member, and that every number equals "
 "the same fifty expenses posted by one thread.",
 T("        // 1. fifty people post an expense", "        // 2. an exact split")),
("One lock per group. Does that scale, or have you serialised Splitwise?", "non-functional", 5,
 "It scales, and the answer is arithmetic rather than opinion. The locked part is about a dozen map operations per "
 "person in the split, some forty for a four-person dinner: call it two microseconds. A busy trip group posts "
 "forty expenses a day; even an invented group posting a hundred a second holds the lock two hundred microseconds "
 "in every second, two hundredths of one per cent. And the lock is per group, so ten million groups never meet. If "
 "one group really did get hot, rung two of the ladder is the code below: no group lock at all, every pair its own "
 "key in a concurrent map, and a debt moved with one atomic merge, so unrelated pairs never wait. What you pay is "
 "the thing the lock was buying: an expense is no longer one step, so a reader can catch a five-way split half "
 "applied.",
 X("one atomic merge per pair", "persistence")),
("The exact amounts they typed do not add up to the bill. What is the state of the system?", "functional", 10,
 "Exactly what it was, and the reason is the order, not a rollback. <code>record</code> splits and checks the "
 "shares before the lock is taken and before anything is written. So a bill of five hundred with shares adding up "
 "to four hundred throws out of the split rule and never reaches the ledger. Under the lock come the remaining "
 "checks (has this expense id been used, is every participant a member), and only after them the changes to the "
 "balances, which are map arithmetic that cannot fail half way. So there is no partial expense and nothing to "
 "undo: the client fixes the numbers and retries with the same id. The check itself lives in CheckedSplit, which "
 "wraps every rule the group is handed, so it also polices rules that do not exist yet; test 8 registers a "
 "deliberately broken one and proves nothing was written.",
 sect(src, "private Expense record(", "Expense edit(") + "\n" + sect(src, "class CheckedSplit", "// \"settle with the fewest")),
("Three people split a bill of one rupee. Where does the last paise go, and how do you know it is not lost?", "functional", 5,
 "A hundred paise over three is 33 each with one left over, so the shares are 34, 33 and 33. The extra paise goes "
 "to the payer, the person who fronted the money: a rule you can say out loud and repeat. The order is fixed "
 "(payer first, then everyone else in the order the client sent), so the same expense always splits the same way, "
 "which matters the moment you replay a log. Some statements fix the rule for you: workat.tech's gives the extra "
 "paise to the first person listed, which is one line in Remainder. The proof that nothing is lost is not the "
 "splitting code. It is the wrapper, which adds the shares up and refuses anything that is not exactly the bill, "
 "plus a failure test that checks the shares sum to 100 and the balances to zero. If the interviewer says \"that is "
 "unfair to the payer\", the fairness variant that rotates who absorbs the odd paise is a new class and nothing "
 "else.",
 sect(src, "final class Remainder", "class ExactSplit") + "\n" + X("fairness", "multi-currency")),
("Why is money a long of paise? Talk me out of double, and out of BigDecimal.", "design", 5,
 "A rupee amount in a double is not the number anybody typed. One rupee split three ways and added back a thousand "
 "times comes to 999.9999999999955, which test 10 prints; the same thousand splits in paise sum to exactly zero. "
 "It breaks valid input too: 47.72% + 38.54% + 13.74% adds up to 99.99999999999999 in double, so a check for 100 "
 "refuses it, while in basis points it is exactly 10000. So the system counts in the smallest unit, a "
 "<code>long</code> of paise, and there is no double anywhere in Main.java. BigDecimal is exact too, and it is the "
 "right answer in a general ledger. But every operation carries a scale and a rounding mode you then have to argue "
 "about, and it is an object per amount; with paise the arithmetic is plain integer addition. The boundary is two "
 "methods: <code>Money.rupees</code> parses \"1234.50\" through BigDecimal once, at the edge, and "
 "<code>Money.fmt</code> prints it back. A long holds about ninety-two thousand trillion rupees, so overflow is "
 "not a real worry; what would make me switch is maths that needs fractions of a paise, like interest or exchange "
 "rates.",
 sect(src, "final class Money", "record User(") + "\n" + T("        // 10. money is exact", "        // 11. nobody walks away")),
("Somebody edited last week's expense. Then deleted another one. What happens to the balances?", "twist", 10,
 "Both are reversals, and both are exact, because each expense stores the shares it was applied with instead of "
 "recomputing them. A delete applies those stored shares with the sign flipped and marks the row DELETED; the row "
 "stays in the log, and a second delete is refused rather than double-reversed. An edit is the same reversal "
 "followed at once by the new version, both inside one lock, so nobody can read a group where the old expense is "
 "gone and the new one has not arrived. The old row is marked EDITED and version n+1 is appended. As with adding, "
 "the new shares are computed before the lock, so an edit that does not add up changes nothing at all. One refusal "
 "to know: an expense that names someone who has left cannot be edited or deleted (follow-up 12). \"Who changed "
 "what?\" and a user's passbook (every expense they were part of) need no new storage: the audit view below filters "
 "the log the group already keeps.",
 sect(src, "Expense edit(", "void addMember(") + "\n" + X("the audit view", "one atomic merge per pair")),
("Bob pays Alice back. Part of it, all of it, more than he owes — and what if the payment never confirms?", "twist", 5,
 "A settle-up is not a new model. It is an expense of a special kind: paid by the person handing over the money, "
 "with exactly one participant owing the whole amount, so it takes the same method, the same lock and the same "
 "reversal. That is what makes the edge cases free. Pay twenty of the fifty you owe and thirty is left; pay a "
 "hundred against thirty and the pair simply flips, so Alice now owes Bob seventy. The same settle-up id posted "
 "twice lands once, and a settle-up sent in error is deleted like any other expense. The one thing this version "
 "does not model is real money moving: a UPI transfer can come back yes, no, or with no answer at all. Then the "
 "settle-up becomes two steps. Record it as PENDING, and let only a confirmation apply it to the ledger: the "
 "gateway's answer, or the bank's next-morning file of payments that really happened (the reconciliation file). "
 "That is move 6's \"a new step in a life\": one more status, not a new class.",
 sect(src, "Expense settleUp(", "private Expense record(") + "\n"
 + T("        // 5. a settle-up brings the pair to zero", "        // 6. simplify is a suggestion")),
("Show me the fewest payments that would clear the whole group.", "twist", 10,
 "Take a snapshot of the nets (a copy made under the lock at one instant) and run greedy min cash flow over two "
 "heaps (priority queues that hand back the biggest amount first). The biggest debtor pays the biggest creditor as "
 "much as clears one of them, again and again. Each payment zeroes at least one person, so there are at most n-1 "
 "payments for n people with a balance, and the ids break ties so the same group always gets the same plan. It is "
 "a suggestion and touches nothing: test 6 checks that every net is identical afterwards and that paying the plan "
 "leaves everybody at zero. Say the caveat before the interviewer does: greedy is short, but not always the "
 "shortest. When a owes 400 and b owes 300, and c, d and e are owed 200, 200 and 300, greedy makes four payments "
 "where three would do; the next card finds the true minimum. With Splitwise's \"simplify debts\" switched on, the "
 "group shows the view below instead of its pairwise map, recomputed after every expense: same nets, far fewer "
 "pairs, and the expense log untouched.",
 sect(src, "class MinCashFlow", "// \"the others must be told\"") + "\n"
 + X("the simplification is a suggestion", "the true minimum")),
("The interviewer says your greedy plan is not the minimum. Find the true fewest payments.", "twist", 10,
 "They are right, and some interviewers mark greedy down for exactly this; it is LeetCode 465, Optimal Account "
 "Balancing. People whose balances sum to zero can settle among themselves in one payment fewer than their number. "
 "So the fewest payments equal the people with a balance minus the most zero-sum groups they can be split into: in "
 "the four-versus-three example, {a, c, d} and {b, e} give 5 - 2 = 3. FewestPayments finds that most-groups count "
 "for every subset of people, written as a bitmask (one bit per person) and built up from smaller subsets; then it "
 "walks back to cut the groups out and runs greedy inside each. It is O(n &times; 2^n): instant for fifteen people "
 "with a balance, too slow past about twenty, so greedy stays the default and this one is handed in through "
 "configure() for small groups. Test 14 checks the example and 300 random groups.",
 X("the true minimum", "many groups")),
("The app asks \"what do I owe Bob?\" a thousand times a second. Make it O(1).", "non-functional", 5,
 "No new structure. The ledger already keeps a net per person and a pairwise map, updated as each expense lands, "
 "so both questions are one hash lookup; nothing ever re-reads the expense log to compute a balance. The two maps "
 "are written by one method from one signed number, which is why A-owes-B and B-owes-A cannot disagree, and a pair "
 "that reaches zero is deleted. The size to watch is not the expenses but the live pairs. A hundred people who "
 "never settle can reach a few thousand entries: trivial for memory, but the real reason the simplify toggle "
 "exists. \"Who owes the most?\" is one pass over the nets, which is fine at any real group size. The reads take the "
 "group's lock so a number is never read half-written, which costs tens of nanoseconds; if that ever mattered, you "
 "would keep the nets in a concurrent map and drop the lock on reads.",
 sect(src, "class Ledger", "class Group {")),
("Carol wants to leave the group. She still owes a hundred.", "twist", 5,
 "She cannot yet: <code>removeMember</code> throws unless her net is exactly zero, because a debt to someone who "
 "is gone could never be settled. A zero net can still hide a loop: bob owes her 150 and she owes alice 150. So on "
 "the way out her debts pass through her: bob now owes alice 150, nobody's net moves, and no pair names carol "
 "afterwards. The check, the pass-through and the removal happen inside the <i>same</i> lock, so nobody can post "
 "an expense into the gap; that is move 12's fourth twist. Leaving is not erasing: her rows stay in the log. A new "
 "expense naming her is refused, and so is editing or deleting an old one, because reversing it would reopen her "
 "balance. Test 11 checks all of it.",
 sect(src, "void removeMember(", "long netOf(String userId)") + "\n" + sect(src, "void passThrough(", "Map<String, Long> netSnapshot()") + "\n"
 + T("        // 11. nobody walks away", "        // 12. the ladder's second rung")),
("Bob is in five groups. Show what he owes and is owed across all of them, and let a friend join a group.", "functional", 10,
 "Nothing about the money changes: each group keeps its own ledger and lock, and Bob's overall balance is the sum "
 "of his nets in the groups he is in. The directory below keeps an index from user to group ids, updated on every "
 "create, join and leave that goes through it, so the sum reads only Bob's five groups, not all ten million. \"What "
 "does Bob owe Alice everywhere?\" is the same sum over the groups they share, netted to one number. Joining is "
 "<code>addMember</code>: one line under the group's lock, and it moves no money. Each group is read under its own "
 "lock, so every number is exact but the total is not one frozen instant, which is fine for a screen. Test 15 "
 "checks the sums and the join.",
 sect(src, "void addMember(", "void removeMember(") + "\n" + X("many groups", "Runs every extension")),
("The group is in Goa but two people paid in euros.", "twist", 5,
 "Money grows a currency, and the ledger becomes one ledger per currency, so a euro debt is never silently added "
 "to a rupee debt. Each expense is split inside a single currency, which keeps the shares exact. Conversion "
 "happens at exactly one moment: when somebody settles, or when a screen asks for one number. It goes through an "
 "injected rate provider, so yesterday's balances are never re-priced when the rate moves. The group, the lock and "
 "the split rules do not change: this is move 5 (a new key on the collection) plus an injected rule.",
 X("multi-currency", "an expense between two friends")),
("Rent every month, automatically. And an expense between two friends who are not in any group.", "twist", 5,
 "Neither needs a new model. A pair is a group of two whose id is built from the two user ids in sorted order, so "
 "alice-bob and bob-alice are the same group, with the same lock and the same ledger. It is created on first use "
 "in one atomic step (<code>computeIfAbsent</code>). A look-up followed by a create would let both friends make a "
 "group at the same moment, and one expense would vanish with the losing group (test 13). Recurring is a schedule "
 "that posts real expenses, and the interesting part is the id. It contains the period number, so running the job "
 "twice posts each month exactly once, because addExpense is idempotent by id.",
 sect(src, "Group newGroup(", "private static Group wired(") + "\n" + X("an expense between two friends", "the audit view")),
("Persist it: which tables? And now there are two servers.", "twist", 5,
 "The ledger's two maps become rows behind a repository interface. The group is handed one instead of building its "
 "own Ledger, and its order (split, check, apply, publish) stays the same. The tables are the maps and the log: "
 "balance and pair rows for the two maps, expense and share rows for every version, plus grp and member. Each "
 "expense becomes one transaction that first locks the group's row (<code>SELECT ... FOR UPDATE</code>): the "
 "ReentrantLock moved into the database, so two servers take turns per group and the membership check and \"may "
 "carol leave?\" stay safe. The expense insert carries <code>ON CONFLICT DO NOTHING</code>, so a retry, or a "
 "message delivered twice, applies once. Each share is an upsert (insert the row, or add to it if it is already "
 "there) with <code>paise = paise + ?</code>; a bare UPDATE would silently skip a brand-new member. That is move "
 "12's fifth twist, and it is why the expense id is a parameter and not generated inside.",
 X("persistence", "the simplification is a suggestion")),
("Where does time come from, and how do you test what an expense was stamped with?", "design", 3,
 "The group has a Clock it was handed, and it stamps every expense version with it; nothing else in the system "
 "reads the wall clock. A test hands in a clock that returns a fixed instant, posts an expense, moves the instant "
 "forward and edits it. It can then assert the exact timestamps on version one and version two. The same seam "
 "makes the recurring-expense extension testable: the job is given a now, not asked to find one.",
 "/** Where time comes from. Injected, so a test can stamp an expense with any instant it likes. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the group: handed in, defaulted, never read from the wall clock inside a method\n"
 "private volatile Clock clock = System::currentTimeMillis;   // volatile: a test sets it, other threads read it\n"
 "void setClock(Clock c) { clock = c; }\n\n"
 "// in a test: pick the instant, then move it\n"
 "long[] now = { 1_700_000_000_000L };\n"
 "group.setClock(() -> now[0]);\n"
 "group.addExpense(\"e1\", \"alice\", 30000, SplitType.EQUAL, parts, \"dinner\");\n"
 "now[0] += 7L * 24 * 3600 * 1000;                       // a week later\n"
 "group.edit(\"e1\", \"alice\", 25000, SplitType.EQUAL, parts, \"dinner, corrected\");\n"),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "None of them was chosen up front; each is what a move produced, which is why each has a one-sentence defence. "
 "Strategy is move 3: how to split, how to simplify and where time comes from, each a one-method interface the "
 "group is handed. Decorator is the same move's wrapper, CheckedSplit, which adds the sum-to-the-bill check to "
 "every rule instead of copying it into each. Observer is move 4's rule that a phone must never be inside the "
 "lock. State and Command are both move 6: an expense's life is a fixed set of moves, and its stored shares are "
 "its own undo. For SOLID: S is move 2, O is the weights rule, L is that the group calls rule.split and never asks "
 "which rule it got, I is four interfaces with one method each, and D is configure() and setClock(), which is "
 "exactly why a test can hand in a broken rule. Factory earns its place the day split types arrive as "
 "configuration strings, because the SplitType-to-rule map is already the registry. Builder earns it the day an "
 "expense gains optional fields, because today every argument is required.",
 "// Strategy: a rule behind an interface, handed in, never built by the group\n"
 "interface SplitStrategy { List<Share> split(long totalPaise, String payerId, List<Participant> parts); }\n"
 "void configure(Map<SplitType, SplitStrategy> rules, SimplifyStrategy simplifier) { /* wraps each rule */ }\n\n"
 "// Decorator: add the invariant to every rule, present and future, instead of copying the check\n"
 "rules.forEach((type, rule) -> checked.put(type, new CheckedSplit(rule)));\n\n"
 "// Observer: the group announces; it does not know what a phone is\n"
 "interface ExpenseObserver { void onExpense(String groupId, Expense e); }\n"
 "private void publish(Expense e) { for (ExpenseObserver o : observers) try { o.onExpense(id, e); } catch (RuntimeException ex) { /* log */ } }\n\n"
 "// State + Command: the life is a fixed set of moves, and the expense carries its own undo\n"
 "enum ExpenseStatus { RECORDED, EDITED, DELETED }\n"
 "ledger.apply(gone.payerId(), gone.shares(), -1);        // the stored shares ARE the undo log\n\n"
 "// Factory: not yet. The registry is already here; it earns the name when types come from config strings\n"
 "Map<String, SplitStrategy> byName = Map.of(\"EQUAL\", new EqualSplit(), \"SHARES\", new SharesSplit());\n\n"
 "// Builder: not yet. Every field is required and only the group calls this; receipts, categories and tags would change that\n"
 "new Expense(id, groupId, kind, payerId, totalPaise, shares, version, atMs, note);\n"),
]

build(dict(
    slug="splitwise", title="Splitwise",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 15 failure scenarios and a 50-thread race pass",
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
