# Library management LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"library/Main.java").read_text()
ext   = (H/"library/Extensions.java").read_text()
tests = (H/"library/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+80])
    j = next(m for m in marks if m > i and b in ext[m:m+80])
    return ext[i:j].rstrip() + "\n"
def S(a, b=None):
    """sect() from Main.java, with the first line's indentation restored when the slice starts at a Javadoc"""
    s = sect(src, a, b)
    first = s.split("\n", 2)
    p = src.find(first[0] + "\n" + first[1]) if len(first) > 1 else -1
    if p > 0:
        ind = src[src.rfind("\n", 0, p) + 1:p]
        if ind.strip() == "": s = ind + s
    return s
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("borrow", 30, 1, [("a member asks for a title", "member id and ISBN"),
                           ("check his rules", "3 books, one of each title, dues"),
                           ("his held copy, else the shelf", "the head of the shelf queue"),
                           ("a loan, due in 14 days", "the slip shows the due date")]),
        ("return", 165, 2, [("a copy is scanned", "its barcode"),
                            ("fine: Rs 20 a day late", "never more than Rs 500"),
                            ("first member waiting?", "held 3 days for him; else the shelf"),
                            ("notices go out", "after the lock: SMS, e-mail")])]
for lab, y, acc, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k*270
        pf += _bx(x, y, 250, 54, b[0], b[1], acc=(k == acc))
        if k < 3: pf += _ar("M%s %s H%s" % (x+250, y+27, x+270), True)
pf += _ar("M815 84 V97", dash=True) + _bx(640, 97, 350, 38, "no copy free: he joins the FIFO queue", "", dash=True)
pf += _tx(88, 262, "read", "var(--acc)", 13) + _tx(150, 262, "at any moment, without a scan: is a copy on the shelf?  who has it?  what does he have?  what is overdue?  titles starting 'clea'?", "var(--text)", 12, "start")
pf += _tx(88, 292, "also", "var(--acc)", 13) + _tx(150, 292, "renew (never while others wait), cancel a hold, report a lost copy, pay a fine, register and unregister members", "var(--text)", 12, "start")
pf += _tx(615, 326, "desks, kiosks and the app act at the same instant: a copy is lent to one member at a time, and never sits on the shelf while someone waits for it", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 342, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("1 Sep 10:00  the last copy", ["asha has had CC-1 since 29 Aug", "ravi takes CC-2, due 15 Sep", "Clean Code: 0 of 2 on the shelf"], True),
      ("1 Sep 10:05  two more ask", ["no copy free: meera is 1st in line", "kabir is 2nd", "ravi asks to renew: refused,", "because two people are waiting"], False),
      ("14 Sep  asha returns CC-1", ["due 12 Sep: 2 days late, fine Rs 40", "CC-1 skips the shelf: it is held", "for meera until 17 Sep", "SMS to meera, after the lock"], True),
      ("18 Sep  meera never came", ["her pickup date has passed", "CC-1 is now held for kabir,", "until 21 Sep; he collects it", "nobody jumped the queue"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 40 + k*295
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+135) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+135)
    pe += _card(x, 60, 270, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Add titles and their copies; register and unregister members.</li>
<li>Borrow a copy of a title for 14 days: at most 3 books at a time, and one copy of a title per member.</li>
<li>When no copy is free, join a first-come-first-served queue (a hold). A returned copy is set aside for the first member in line for 3 days, then passes to the next.</li>
<li>Return: close the loan, charge Rs 20 for every day late (never more than Rs 500), and give the copy to the queue before the shelf.</li>
<li>Renew twice, but never while someone waits; report a lost copy (its price plus the fine so far); pay fines.</li>
<li>Search by a word of the title or the author; list a member's books, a title's borrowers and the overdue loans.</li>
<li>Tell the next member when his copy is ready, and a member when he is fined.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Desks, kiosks and the app at the same instant: a copy is lent to one member at a time, and nobody waits while a copy sits on the shelf.</li>
<li>Every question is a lookup or one range of a sorted map, never a scan of the whole library: O(1) or O(log n).</li>
<li>The limit and the fine are rules, swappable without touching the library.</li>
<li>One source of truth for where every copy is: the library, behind one lock.</li>
<li>Nothing half-done: a refusal, or a fine rule that fails, leaves every loan, queue and account as it was.</li>
<li>A broken SMS gateway cannot break a return, and a slow one never makes the other desks wait.</li>
<li>In memory, one process, one branch (say it; follow-ups add a database and branches).</li></ul></div></div>
'''

PROMPT = ('"Design a library management system. Books with several copies, members who borrow and return them, a limit '
          'on how many they can hold, a waitlist when every copy is out, and a fine for late returns. I want working '
          'code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A library has titles (a <b>book</b>: an ISBN, which is the '
 'book\'s international number, a title and an author) and, for each title, one or more physical <b>copies</b>, each with '
 'its own barcode. A member borrows a copy for 14 days and may have three at a time. When every copy of a title is out, '
 'he joins a first-come-first-served (FIFO) queue for it, called a hold. When a copy comes back it does not go back on the '
 'shelf: it is set aside for the first person in the queue, who has three days to collect it before it passes to the '
 'next. A late return costs Rs 20 a day, never more than Rs 500, and a member who owes more than Rs 100 cannot borrow. '
 'Desks, self-service kiosks and the app all act at the same time, so the invariant (the rule that must always hold) '
 'is: a copy is lent to one member at a time, and a copy never sits on the shelf while someone is waiting for its '
 'title.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a '
 '<code>main</code> that lends, queues, returns and fines. The interviewer is watching for, in this order: the '
 'questions you ask before typing (book versus copy, and what happens when every copy is out, come first); which '
 'classes exist and which one owns the shelf, the queue and the loans; borrowing and returning working end to end; '
 'what happens when two members want the last copy, and when a return crosses a new request; where the rules that '
 'change (the limit, the fine) live, so a change is a new class and not an edit; and what state the library is in '
 'when the fine rule fails halfway through a return. Then the twists: member tiers, renewals, lost books, the database '
 'schema and the overdue query, racks, reminders, several branches.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Can one title have several copies, each with its own barcode?</td><td>Yes: a book (ISBN) has copies (barcodes)</td><td>Book and BookCopy, two classes (move 1)</td></tr>'
 '<tr><td>How many books may a member have, and for how long?</td><td>3 at a time, 14 days, 2 renewals</td><td>LoanRules, handed in; tiers later (move 3)</td></tr>'
 '<tr><td>What happens when every copy is out?</td><td>He joins a FIFO queue; a returned copy is set aside for the first in line for 3 days</td><td>Hold, the pickup date, placeCopy (moves 5, 6)</td></tr>'
 '<tr><td>How are late returns charged?</td><td>Rs 20 a day after the due date, never more than Rs 500; owing more than Rs 100 blocks borrowing</td><td>FinePolicy, and a cap that wraps it (move 3)</td></tr>'
 '<tr><td>Do desks, kiosks and the app act at the same time?</td><td>Yes</td><td>One lock in the library; the desk is a thin caller (moves 4, 7)</td></tr>'
 '<tr><td>Search by what?</td><td>A word of the title or of the author, as a prefix; the first 20 hits</td><td>A sorted word index (move 5)</td></tr>'
 '<tr><td>Who must be told what?</td><td>The next member when his copy is ready; a member when he is fined</td><td>Listeners, called after the lock (moves 3, 4)</td></tr>'
 '<tr><td>One branch, in memory?</td><td>Yes; branches, a database and reminders are follow-ups</td><td>No repository yet (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>Three weeks at one branch, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> one branch, in memory, one process; a book is a title and a copy is the '
 'thing with a barcode; three books for fourteen days, one copy of a title each; Rs 20 a day late, never more than '
 'Rs 500, and no borrowing while owing more than Rs 100; a returned copy goes to the first member waiting, for three '
 'days, before it goes to the shelf; one lock in the library. Named as out of scope: member tiers, reminders before the '
 'due date, several branches, e-books, the database; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a MEMBER borrows a COPY of a BOOK at a DESK; the LOAN is due in 14 days; a HOLD waits its turn; a late return costs a FINE; SEARCH by title", "var(--text)", 12.5)
for k, (t, sub, acc) in enumerate([("Member", "loans, holds, dues", 1), ("Desk", "no state: a caller", 0),
                                   ("Book", "copies, shelf, queue", 1), ("BookCopy", "barcode, status", 1),
                                   ("Loan", "copy, due, renewals", 1), ("Hold", "queue place, pickup", 1),
                                   ("Fine", "a rule's result", 0), ("Search", "a question: a method", 0)]):
    x = 20 + k*150
    m1 += _bx(x, 110, 140, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x+70))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state of its own: a caller, a rule's result, or a method", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("take the next copy off the shelf", "Book  (owns its shelf and its queue)", "book.takeFromShelf()"),
                                       ("at his limit? has this title?", "Member  (owns his loans, by ISBN)", "one lookup in member.loans"),
                                       ("lend a copy", "Library  (owns titles, members, loans, lock)", "library.checkout(member, isbn)"),
                                       ("give a returned copy to the next", "Library  (the loan, two members, the queue)", "library.returnCopy(barcode)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 270, "a verb whose state is spread over several classes goes to the class that owns them all: that class becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 289, "\"compute the fine\" touches no state at all, so it is not a method on a model: it is a rule, and rules can be swapped (move 3)", "var(--muted)", 11)
MV[2] = _mv(1230, 302, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 90, 220, 100, "Library", "configure, setClock, addListener", acc=True)
for k, (t, sub, impl) in enumerate([("LoanRules", "3 books, 14 days, 2 renewals", "StandardTerms / TieredTerms"),
                                    ("FinePolicy", "Rs 20 a day, capped", "PerDayFine / CappedFine (wraps)"),
                                    ("LibraryListener", "SMS, e-mail, the hold shelf", "NoticePrinter / SmsOutbox"),
                                    ("Clock", "which day it is", "the system clock / a test's own day")]):
    y = 20 + k*58
    m3 += _ar("M250 140 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 440, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 275, "dashed green = handed in. The library never builds a rule, so a new fine is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 295, "and one fine rule WRAPS another: new CappedFine(new PerDayFine(2_000), 50_000). That wrapping is Decorator, born right here.", "var(--acc)", 11)
MV[3] = _mv(1230, 310, m3)

# move 4: two gaps, one owner, one lock
m4 = _D
m4 += _bx(30, 20, 250, 44, "desk", "reads: CC-2 is on the shelf") + _bx(30, 76, 250, 44, "kiosk", "reads: CC-2 is on the shelf")
m4 += _ar("M280 42 H305 V58 H330") + _ar("M280 98 H305 V82 H330")
m4 += '<rect x="330" y="20" width="520" height="100" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(590, 50, "gap 1: both saw CC-2 on the shelf, both lend it", RED, 12) + _tx(590, 74, "one copy, on two members' cards", RED, 11)
m4 += _tx(590, 102, "fix: check and take as ONE step", "var(--text)", 11)
m4 += _bx(30, 150, 250, 44, "a return", "reads: nobody is waiting") + _bx(30, 206, 250, 44, "the app", "reads: no copy on the shelf")
m4 += _ar("M280 172 H305 V188 H330") + _ar("M280 228 H305 V212 H330")
m4 += '<rect x="330" y="150" width="520" height="100" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(590, 180, "gap 2: the copy goes to the shelf, the member to the queue", RED, 12)
m4 += _tx(590, 204, "he waits while his book sits on the shelf, and a walk-in takes it", RED, 11)
m4 += _tx(590, 232, "fix: decide both under the same lock", "var(--text)", 11)
m4 += _ar("M850 70 H875 V112 H900", True) + _ar("M850 200 H875 V158 H900", True)
m4 += _bx(900, 85, 300, 100, "Library.lock", "check + act = one step", acc=True)
m4 += _tx(1050, 212, "the lock lives where the shelf, the", "var(--muted)", 10.5) + _tx(1050, 228, "queue and the loans live", "var(--muted)", 10.5)
m4 += _tx(1050, 252, "the SMS hears AFTER the unlock", "var(--muted)", 10.5)
MV[4] = _mv(1230, 270, m4)

# move 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("next copy to lend of this title?", "Book.shelf: ArrayDeque, head = the answer", "O(1)"),
                                      ("who is next in line for it?", "Book.waiting: ArrayDeque, FIFO; cancelled ones skipped", "O(1) average"),
                                      ("the loan behind this barcode?", "Map&lt;barcode, Loan&gt; onLoan", "O(1)"),
                                      ("at his limit? has this title already?", "Member.loans: Map&lt;isbn, Loan&gt;", "O(1)"),
                                      ("which loans are overdue?", "TreeMap&lt;LocalDate, Set&lt;Loan&gt;&gt;: headMap(today)", "O(log n + k)"),
                                      ("whose pickup date has passed?", "PriorityQueue&lt;Hold&gt; by pickup date: peek the head", "O(1) to check"),
                                      ("titles with a word starting 'clea'?", "TreeMap&lt;word, Set&lt;isbn&gt;&gt;: one subMap range", "O(log n + k)")]):
    y = 16 + k*46
    m5 += _bx(30, y, 360, 38, q, "the question") + _ar("M390 %s H450" % (y+19), True)
    m5 += _bx(450, y, 520, 38, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+19), True) + _bx(1030, y, 170, 38, cost, "")
m5 += _tx(615, 350, "k = the number of answers. Not one of these is a scan of the library, and a scan is what would have been inside the lock", "var(--muted)", 11)
MV[5] = _mv(1230, 365, m5)

# move 6: two life cycles and the ORDER inside returnCopy
m6 = _D + _tx(30, 22, "a copy", "var(--acc)", 11.5, "start")
m6 += _bx(30, 40, 150, 44, "AVAILABLE", "on the shelf") + _bx(240, 40, 150, 44, "LOANED", "due in 14 days", acc=True)
m6 += _bx(440, 40, 150, 44, "ON_HOLD", "for one member", acc=True)
m6 += _ar("M180 62 H240", True) + _tx(210, 56, "lend", "var(--acc)", 10)
m6 += _ar("M390 62 H440", True) + _tx(415, 56, "return", "var(--acc)", 10)
m6 += _ar("M515 40 V28 H315 V40", True) + _tx(415, 24, "he collects it", "var(--acc)", 10)
m6 += _ar("M280 84 V100 H105 V84", True) + _tx(192, 114, "return, nobody waits", "var(--acc)", 10)
m6 += _ar("M350 84 V135") + _bx(240, 135, 150, 36, "LOST", "price + fine so far", dash=True)
m6 += _tx(515, 104, "not collected in 3 days:", "var(--muted)", 10) + _tx(515, 118, "the next member in line,", "var(--muted)", 10) + _tx(515, 132, "else back on the shelf", "var(--muted)", 10)
m6 += _tx(30, 197, "a hold", "var(--acc)", 11.5, "start")
m6 += _bx(30, 208, 130, 36, "WAITING", "") + _bx(200, 208, 130, 36, "READY", "", acc=True) + _bx(370, 208, 130, 36, "COLLECTED", "")
m6 += _ar("M160 226 H200", True) + _ar("M330 226 H370", True)
m6 += _tx(30, 264, "WAITING in the queue; READY when a copy is set aside, 3 days to collect;", "var(--muted)", 10.5, "start")
m6 += _tx(30, 280, "else EXPIRED or CANCELLED, and the copy goes through placeCopy again", "var(--muted)", 10.5, "start")
m6 += '<rect x="620" y="20" width="590" height="252" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(915, 44, "the order inside returnCopy, and why", "var(--text)", 12)
for k, l in enumerate(["1 find the active loan by barcode; do not remove it",
                       "2 ask the fine rule: handed-in code, it may throw",
                       "  ... and if it does, nothing has been written yet",
                       "3 commit: close the loan, free his slot, add the fine",
                       "4 placeCopy: the first member waiting, else the shelf",
                       "5 unlock, then tell the listeners: hold ready, fine",
                       "a second scan of the same barcode finds no loan: refused,",
                       "so nobody is fined twice and no copy goes to two members"]):
    m6 += _tx(635, 72 + k*24, l, "var(--muted)" if k in (2, 6, 7) else "var(--text)", 11, "start")
m6 += _tx(615, 302, "a copy frees up in five ways (a return, a new copy, an expired hold, a cancelled hold, a member leaving): all five go through placeCopy", "var(--muted)", 11)
MV[6] = _mv(1230, 318, m6)

# move 7: what is inside the lock, and five counters at the same instant
m7 = _D + _card(30, 20, 540, 150, "inside the lock: about 2 microseconds",
                ["look up the member and the title: two maps", "ask the rules: one call", "take the head of the shelf: a deque poll",
                 "record the loan: two map puts, one due-index insert", "first of all, peek at the pickup-date heap"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside the lock: seconds",
            ["scanning the barcode and the security tag: ~1 s", "printing the due-date slip: ~2 s",
             "the SMS 'your hold is ready': ~300 ms, after the unlock", "the member putting the book in his bag: seconds"])
m7 += _tx(615, 205, "five counters press at the same instant", "var(--text)", 12)
for k in range(5):
    x = 30 + k*236
    m7 += _bx(x, 220, 222, 40, "counter %d" % (k+1), "waits %d us for the lock" % (k*2), acc=(k == 4))
m7 += _tx(615, 290, "the fifth counter waits 8 microseconds for the lock, then 2 seconds for its printer: one by one is true, and nobody can tell", "var(--muted)", 11)
m7 += _tx(615, 309, "the one read that could hold the lock for long is a search for 'a': so every search takes a limit (20 on the app)", "var(--muted)", 11)
MV[7] = _mv(1230, 322, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a loan or a return: ~2 us of lock; a search (limit 20): ~10 us",
                       "evening peak: 5 counters, a scan every 10 s each: ~1 us a second",
                       "the app: 50 searches a second: ~500 us of lock a second",
                       "busy 0.05% of the time; a call waits about once in 2,000",
                       "the reads are 99% of the lock's time: move search first"]):
    m8 += _tx(35, 66 + k*24, l, RED if k == 4 else "var(--muted)", 11, "start")
m8 += _tx(900, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 search off the lock", "a copy-on-write index: rebuilt on a new title, read with no lock"),
                              ("2 a lock per title", "different books never wait; the limit becomes an atomic counter"),
                              ("3 the database decides", "UPDATE copy SET status='LOANED' WHERE barcode=? AND status='AVAILABLE'")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two members, one copy", "check and take under one lock; test 1: 50 threads, one latch, exactly one loan"),
                                ("a return crosses a new request", "both decided under the same lock; test 2: 3 returns vs 20 requests, 30 rounds, shelf 0"),
                                ("the fine rule throws mid-return", "ask the rule before the first write; test 8: the book stays on his card, the retry fines once"),
                                ("the same barcode scanned twice", "the second finds no active loan and is refused; test 8: no second fine"),
                                ("he never collects his hold", "a pickup date in a heap, checked on every call; test 5: on the 18th the copy moves on"),
                                ("the SMS gateway throws", "listeners after the unlock, each in a try/catch; test 9: the return still completes"),
                                ("a renewal moves the due date", "out of the due index, change it, back in; test 6: not overdue the day after")]):
    y = 18 + k*42
    m9 += _bx(30, y, 320, 38, bad, "") + _ar("M350 %s H400" % (y+19), True) + _bx(400, y, 800, 38, fix, "", acc=True)
m9 += _tx(615, 330, "every claim this page makes has a failure test: FailureTests.java runs fourteen of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 345, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 850)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface FinePolicy { long fine(Loan loan, LocalDate returnedOn); }", None), ("a new fine rule is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new CappedFine(new PerDayFine(2_000), 50_000)", None), ("a cap without copying the rate", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(events) after the unlock; NoticePrinter implements LibraryListener", None), ("the SMS hears; lending never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("CopyStatus + HoldStatus, and every free copy through placeCopy()", None), ("nobody waits while a copy is on the shelf", None)],
          [("Dependency injection", "var(--text)"), ("move 3", None), ("configure(rules, fines), setClock(c): handed in, never built", None), ("a test sets the date and breaks the rule", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("desks are HANDED the library; nothing calls getInstance()", "var(--muted)"), ("every test builds a fresh library", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("CatalogImport, once items arrive as rows of a file", "var(--muted)"), ("today titles arrive already typed", "var(--muted)")],
          [("Command, Builder", "var(--muted)"), ("never", None), ("no desk action is queued or undone; a book has 4 required fields", "var(--muted)"), ("a pattern without a move is decoration", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Book: its shelf and queue. Member: his loans and dues. Library: the flow and the lock.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("a grace period is new GraceDays(...) plus one configure() line", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("long fine = fines.fine(loan, today);  never \"is it the capped one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("LoanRules, FinePolicy, LibraryListener, Clock: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("lib.configure(rules, (loan, d) -&gt; { throw ... });  lib.setClock(() -&gt; day18)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "tiers, a grace period, a student rate", "a new class behind LoanRules or FinePolicy + one configure line", "", "move 3"),
        ("someone new wants to know", "due-soon reminders, an SMS outbox", "one more listener; lending does not change at all", "", "move 4"),
        ("a new step in a life", "IN_TRANSIT between branches", "a new status + one more hop inside placeCopy", "", "move 6"),
        ("a new invariant across items", "one copy of a title each; 5 holds at most", "checked inside the same lock, before the first write", "", "move 4"),
        ("state that must outlive the process", "a database; twenty branches on it", "the maps behind a repository; the claim becomes",
         "UPDATE copy SET status='LOANED' WHERE barcode=? AND status='AVAILABLE'", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the book, the copy and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: a <b>member</b> borrows a <b>copy</b> of a <b>book</b> at a <b>desk</b>; the <b>loan</b> is "
 "due in fourteen days; a <b>hold</b> waits its turn; a late return costs a <b>fine</b>; members <b>search</b>. Book is "
 "the title: an ISBN, a title, an author and a price, plus its copies, its shelf and its queue: a class. BookCopy is the "
 "physical thing with a barcode and a place (on the shelf, lent, on the hold shelf, lost): a class. Keeping it apart from "
 "Book is the first thing the interviewer checks, because five copies of one title are five things that can be in five "
 "places. Member has his loans, his holds and what he owes: a class. Loan has a copy, a member, a due date and a count of "
 "renewals: a class. Hold has a member, a title, a place in the queue and, once a copy is set aside, a pickup date: a "
 "class. The library holds all of it: a class, and the only one with a lock. The desk remembers nothing, so it is a thin "
 "caller. The fine is a number that a rule computes, and search is a question, so neither is a class.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Take the next copy off the shelf\" changes the book's shelf, so <code>book.takeFromShelf()</code>. \"Is he at his "
 "limit, does he already have this title?\" reads the member's loans, and because they are kept by ISBN each answer is "
 "one lookup in <code>member.loans</code>. \"Lend a copy\" touches the book's shelf, the member's loans and the library's "
 "map of loans at once; only the library sees all three, so <code>library.checkout(memberId, isbn)</code>. \"Give a "
 "returned copy to the next person\" touches the loan, two members, the copy and the book's queue, so it belongs to the "
 "library too: <code>library.returnCopy(barcode)</code>. When a verb's state is spread over several classes it goes to "
 "the class that owns them all, and that class becomes the orchestrator (the one class that runs the flow and calls the "
 "others). Note what did not become a method on a model: \"compute the fine\" touches no state at all, which is exactly "
 "why it can be a swappable rule.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "The limit will change (three books today; two for students and ten for faculty tomorrow). The fine will change (Rs 20 "
 "a day today; a grace period and a cap tomorrow). Somebody will want to be told things (an SMS when a hold is ready). And "
 "the date must be something a test can set. Each becomes a one-method interface the library is <i>given</i>, never "
 "builds itself: <code>LoanRules</code> and <code>FinePolicy</code> through <code>configure()</code>, "
 "<code>LibraryListener</code> through <code>addListener()</code>, <code>Clock</code> through <code>setClock()</code>. "
 "Hand each rule the whole object, not a number. The fine rule gets the whole <code>Loan</code>, so a cap at the book's "
 "price reads the book and a student rate reads the member, with no new interface. This is where the patterns come from, "
 "not the other way round. A swappable rule behind an interface is <b>Strategy</b>. A rule that wraps another instead of "
 "replacing it, <code>new CappedFine(new PerDayFine(2_000), 50_000)</code>, is <b>Decorator</b>. A library that announces "
 "\"CC-1 is ready for meera\" without knowing whether an SMS or an e-mail is listening is <b>Observer</b>. Do them; do "
 "not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two gaps, one fix. The first is the obvious one: a desk and a kiosk both read \"CC-2 is on the shelf\", and both lend "
 "it. The second is the one that shows you thought about the queue. A return reads \"nobody is waiting\" and puts the "
 "copy on the shelf, while at the same instant the app reads \"no copy on the shelf\" and puts a member in the queue. Now "
 "a copy sits on the shelf and a member waits for it, and a walk-in will take it first. Both gaps are a check and an act "
 "done as two steps. So every check and its act run as one step, under one lock, in the class that owns the shelf, the "
 "queue and the loans: the library. Anything that only listens (the SMS) is called after the lock is released, inside a "
 "try/catch: a gateway that throws cannot break a return, and a slow one never holds the lock while other desks wait.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"The next copy to lend\": a deque per title (a double-ended queue: take from the front, add at the back), and the head "
 "is the answer. \"Who is next in line\": another deque per title, first in, first out. A cancelled hold is only marked; "
 "it is dropped when it reaches the front, so a cancel costs O(1) and nobody walks the queue. \"The loan behind this "
 "barcode\": a map. \"Is he at his limit, does he have this title\": his loans in a map keyed by ISBN, one lookup each. "
 "Two questions are about time, and a hash map cannot answer \"everything before a date\". \"Which loans are overdue\" is "
 "a TreeMap (a map kept sorted by its keys) from due date to loans, and <code>headMap(today)</code> is exactly the "
 "overdue ones, found in O(log n) plus one step per answer. \"Whose pickup date has passed\" is a heap (a priority "
 "queue whose head is always the smallest), ordered by pickup date, so checking costs one peek. Search is the same trick "
 "on words: a sorted map from each word to its ISBNs, where every word starting with \"clea\" is one range. Every scan "
 "avoided here is a scan that is not inside the lock.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A copy is AVAILABLE on the shelf, LOANED to a member, ON_HOLD on the hold shelf for one member, or LOST. A hold is "
 "WAITING in the queue, READY when a copy is set aside with a pickup date three days away, and then COLLECTED, EXPIRED "
 "or CANCELLED. Writing the states down forces the question the interviewer will ask: what exactly happens at a return? "
 "The answer is an order. Find the active loan by barcode, without removing it. Ask the fine rule, which is handed-in "
 "code and may throw; nothing has changed yet, so a failure leaves the book on his card and the queue untouched. Only "
 "then commit: close the loan, free his slot, add the fine to what he owes. Then decide where the copy goes: the first "
 "member still waiting, else the shelf. Tell the listeners after the unlock. A second scan of the same barcode finds no "
 "active loan and is refused, so nobody is fined twice. The last rule is the one that makes the invariant safe. A copy "
 "frees up in five ways (a return, a new copy, an expired hold, a cancelled hold, a member leaving), and all five go "
 "through one method, <code>placeCopy</code>. There is no sixth path that could forget the queue.", 6),
("Move 7: yes, the lock makes lending happen one at a time. Ask for how long, and what is inside it.",
 "Inside the lock there are two map lookups (the member, the title), one call to the rules, a deque poll, two map "
 "writes, one insert into the due index, and a peek at the pickup-date heap: about two microseconds. Everything slow is "
 "outside it: scanning the barcode, the security tag, printing the slip, sending the SMS, and the member putting the book "
 "in his bag. So when five counters press at the same instant, the fifth waits about eight microseconds for the lock and "
 "then two seconds for its printer. One by one is true, and nobody can tell. The one read that could hold the lock for "
 "long is a search: a one-letter query matches most of the catalogue. That is why every search takes a limit (the app "
 "asks for twenty), and its walk stops there.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A busy branch at the evening peak has five counters, each scanning a book every ten seconds: half a scan a second, "
 "about one microsecond of lock a second. The app adds fifty searches a second at about ten microseconds each: half a "
 "millisecond of lock a second. So the lock is busy 0.05% of the time, and the reads, not the loans, are nearly all of "
 "it. A call finds the lock taken about once in two thousand tries, and then waits a few microseconds. Nothing needs "
 "building yet. Then the ladder, in the order you would climb it. Rung one moves search off the lock: the catalogue "
 "changes a few times a day, so each change builds a new index and publishes it with one write, and searches read it "
 "with no lock at all. Rung two is a lock per title, so members borrowing different books never wait for each other; the "
 "limit, which spans titles, becomes an atomic counter per member (a number that many threads can change safely without "
 "a lock). Rung three is the database: the claim becomes "
 "<code>UPDATE copy SET status='LOANED' WHERE barcode=? AND status='AVAILABLE'</code>, and returns and holds for one "
 "title lock that title's row first. Say the arithmetic first: climbing the ladder without it is complexity nobody asked "
 "for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Each row of that table is a few lines in FailureTests.java, which runs fourteen tests and prints ALL PASS or exits "
 "non-zero. The race is the one to write in front of the interviewer: fifty threads wait on one latch (a gate that opens "
 "for all of them at once), and exactly one loan comes out. The second race is the one that proves you understood the "
 "queue. Three returns and twenty requests start together, thirty rounds in a row, and every round ends with three "
 "members served, seventeen waiting and nothing on the shelf. The row candidates forget is the fifth: a member who never "
 "collects his hold. Without a pickup date the copy would sit on the hold shelf for ever, and the whole queue behind him "
 "with it. Time comes from an injected clock, so the test moves the date on instead of sleeping.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; each name has one sentence behind it because a move produced it. The bottom rows are the "
 "absences, and Walmart's round asked about exactly these, so say them out loud. Singleton did not earn a place: desks "
 "are handed the library, which is why every test builds a fresh one and nothing global has to be reset. Factory has not "
 "earned one yet, because titles arrive already typed; it earns one when the catalogue is imported from a file, one row "
 "per item. Command (an action wrapped as an object, so it can be queued or undone) would earn one if a desk had to work "
 "offline and replay its scans later; it does not. Builder never will: a book has four fields and every one is required. "
 "A pattern without a move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is the answer; the thing to say with it is that not one of these was aimed at. Each letter is a line that "
 "already existed because a move produced it, so the honest reply to \"which SOLID principles did you apply?\" is \"move "
 "2 gave me S, move 3 gave me O, L, I and D\", not five definitions. The one worth showing rather than claiming is D. "
 "Because the fine rule is handed in, a test hands in one that throws, and that one lambda is how FailureTests proves "
 "that a failing rule leaves the book on the member's card.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Two of the five need more than the picture gives them. A new step in a life: with several branches, a copy returned "
 "at the wrong branch is IN_TRANSIT before it is READY. That is one more status and one more hop inside "
 "<code>placeCopy</code>, the single place where a free copy's next stop is decided. And when the state has to outlive "
 "the process, the maps go behind a repository (an interface with load and save), the claim becomes a conditional "
 "UPDATE, and returns and holds for one title first lock that title's row with <code>SELECT ... FOR UPDATE</code>. That "
 "row lock is move 4 again, one layer down. For all five the book, the copy and the tests do not change; that is the "
 "test that the derivation was right. Page 05 has the code for each.", 12),
]

# ============================================================ page 03: the class diagram
uml_reset()
put("desk", 10, 20, 250, "Desk", ["lib: Library"], ["borrow(member, isbn): String", "giveBack(barcode): String"])
put("listener", 10, 150, 250, "LibraryListener", [], ["onEvent(e: LibraryEvent)"], "interface")
put("printer", 10, 236, 250, "NoticePrinter", [], ["onEvent(e) &rarr; an SMS line"])
put("clock", 10, 322, 250, "Clock", [], ["nowMs(): long"], "interface")
put("event", 10, 408, 250, "LibraryEvent", ["kind: EventKind", "memberId, isbn, barcode", "date: LocalDate, paise: long"], [], "record")
put("refused", 10, 530, 250, "Refused", ["why: Refusal"], ["thrown before any write"])
put("catalog", 10, 632, 250, "Catalog", ["byIsbn: Map&lt;isbn, Book&gt;", "titleWords, authorWords"], ["byTitle / byAuthor(q, limit)"])
put("tokens", 10, 752, 250, "TokenIndex", ["index: TreeMap&lt;word, Set&lt;isbn&gt;&gt;"], ["add(text, isbn)", "find(prefix, keep, limit)"])
put("lib", 300, 20, 340, "Library",
    ["catalog: Catalog", "copies: Map&lt;barcode, BookCopy&gt;", "members: Map&lt;id, Member&gt;", "onLoan: Map&lt;barcode, Loan&gt;",
     "byDue: TreeMap&lt;date, Set&lt;Loan&gt;&gt;", "readyByDeadline: PriorityQueue&lt;Hold&gt;", "lock: ReentrantLock",
     "rules, fines, clock, listeners"],
    ["configure(rules, fines) / setClock(c)", "addBook / addCopy / register / unregister", "checkout(member, isbn): Slip",
     "placeHold(member, isbn): HoldSlip", "cancelHold(member, isbn)", "returnCopy(barcode): Receipt", "renew(barcode): Slip",
     "reportLost(barcode) / payFine(m, paise)", "expireHolds()", "searchTitle / searchAuthor(q, limit)",
     "onShelf / position / holdOf / dues / status", "loansOf / borrowersOf / overdue / dueBetween",
     "private: locked / placeCopy / setAside / sweep"])
put("book", 300, 440, 340, "Book",
    ["isbn, title, author, pricePaise", "copies: List&lt;BookCopy&gt;", "shelf: Deque&lt;BookCopy&gt;  (AVAILABLE)", "waiting: Deque&lt;Hold&gt;  (FIFO)"],
    ["peekShelf / takeFromShelf / shelve", "enqueue / firstWaiting / nextInLine", "position(m) / onShelf()"])
put("copy", 300, 640, 160, "BookCopy", ["barcode", "book: Book", "status: CopyStatus"], [])
put("hold", 480, 640, 160, "Hold", ["member, book", "status: HoldStatus", "copy, pickupBy"], [])
put("member", 680, 20, 240, "Member", ["id, name, tier: Tier", "loans: Map&lt;isbn, Loan&gt;", "holds: Map&lt;isbn, Hold&gt;", "duesPaise: long"], [])
put("loan", 680, 150, 240, "Loan", ["id, copy, member", "borrowedOn, due: LocalDate", "renewals, status: LoanStatus", "closedOn, chargedPaise"], [])
put("slips", 680, 280, 240, "Slip | HoldSlip", ["Slip: barcode, title, due", "HoldSlip: status, position"], [], "record")
put("receipts", 680, 372, 240, "Receipt | Found", ["Receipt: fine, heldFor", "Found: title, onShelf"], [], "record")
put("cstat", 680, 470, 240, "CopyStatus", ["AVAILABLE, LOANED,", "ON_HOLD, LOST"], [], "enum")
put("hstat", 680, 562, 240, "HoldStatus", ["WAITING, READY, COLLECTED,", "EXPIRED, CANCELLED"], [], "enum")
put("lstat", 680, 654, 240, "LoanStatus | Tier", ["ACTIVE, RETURNED, LOST", "REGULAR, STUDENT, FACULTY"], [], "enum")
put("rules", 950, 20, 260, "LoanRules", [], ["termsFor(m: Member): Terms"], "interface")
put("std", 950, 100, 260, "StandardTerms", [], ["termsFor: 3 books, 14 days,", "  2 renewals, owes at most Rs 100"])
put("terms", 950, 196, 260, "Terms", ["maxLoans, loanDays,", "maxRenewals, maxDuesPaise"], [], "record")
put("fine", 950, 320, 260, "FinePolicy", [], ["fine(loan, returnedOn): long"], "interface")
put("perday", 950, 400, 260, "PerDayFine", ["perDayPaise: long"], ["fine: days late x rate"])
put("capped", 950, 498, 260, "CappedFine", ["base: FinePolicy, capPaise"], ["fine: min(base.fine, cap)"])
put("kinds", 950, 610, 260, "EventKind", ["HOLD_READY, HOLD_EXPIRED,", "FINE_CHARGED, DUE_SOON"], [], "enum")
put("refusal", 950, 702, 260, "Refusal", ["NOT_AVAILABLE, LIMIT_REACHED,", "OWES_FINES, ALREADY_HAS_TITLE,", "OTHERS_WAITING, ... (14 in all)"], [], "enum")

edges = [
 ln(B["desk"]["r"], (300, B["desk"]["r"][1]), "assoc", "calls"),
 ln(B["printer"]["t"], B["listener"]["b"], "inherit"),
 ln((300, B["listener"]["r"][1]), B["listener"]["r"], "notify"),
 ln((300, B["clock"]["r"][1]), B["clock"]["r"], "inject"),
 ln((300, 382), B["catalog"]["t"], "compose", "", [(280, 382), (280, 618), (B["catalog"]["t"][0], 618)]),
 ln(B["catalog"]["b"], B["tokens"]["t"], "compose", "2"),
 ln(B["lib"]["b"], B["book"]["t"], "compose", "1..*"),
 ln((380, B["book"]["b"][1]), (380, 640), "compose", "copies"),
 ln((560, B["book"]["b"][1]), (560, 640), "compose", "queue"),
 ln((640, B["member"]["l"][1]), B["member"]["l"], "compose"),
 ln((640, B["loan"]["l"][1]), B["loan"]["l"], "compose"),
 ln((640, B["slips"]["l"][1]), B["slips"]["l"], "assoc"),
 ln((640, 136), B["rules"]["l"], "inject", "", [(935, 136), (935, B["rules"]["l"][1])]),
 ln((640, 266), B["fine"]["l"], "inject", "", [(935, 266), (935, B["fine"]["l"][1])]),
 ln(B["std"]["t"], B["rules"]["b"], "inherit"),
 ln(B["std"]["b"], B["terms"]["t"], "assoc"),
 ln(B["perday"]["t"], B["fine"]["b"], "inherit"),
 ln((B["capped"]["t"][0]-70, B["capped"]["t"][1]), (B["fine"]["b"][0]-70, B["fine"]["b"][1]), "inherit"),
 ln(B["capped"]["r"], (B["fine"]["r"][0], B["fine"]["r"][1]+8), "assoc", "", [(1222, B["capped"]["r"][1]), (1222, B["fine"]["r"][1]+8)]),
]
UMLSVG = uml_svg(1230, 890, edges, legend_y=868)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed list '
 'of values; &laquo;record&raquo; = an immutable value). Middle: its fields, the state it holds. Bottom: its methods. '
 '<b>The arrows.</b> Hollow triangle = implements. Filled diamond = owns: the library owns the catalogue, the titles, '
 'the members and the active loans; a book owns its copies and its queue of holds; the catalogue owns its two word '
 'indexes. Plain arrow = references: the desk calls the library, the library hands back slips, and the arrow from '
 'CappedFine back to FinePolicy is one fine rule wrapping another. Dashed green = handed in through '
 '<code>configure()</code> or <code>setClock()</code>. Dotted blue = notifies: the one call the library makes after it '
 'has released the lock. <b>Where state lives:</b> a book has its shelf and its queue; a copy its status; a member his '
 'loans and holds by ISBN, and his dues; a loan its due date; a hold its place and its pickup date. The library has all '
 'of them plus the due index, the pickup-date heap and the one lock, and it is the only class that writes to more than '
 'one of them. The records on the right of the library are what it hands back: copies, safe to read after the lock. '
 'Everything in the right-hand column is handed in and could be replaced without opening the library.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does and what it guarantees. Read only those first for the shape, then the bodies; start '
 'with <code>Library.returnCopy</code> and <code>placeCopy</code>, the forty lines that are the whole interview. Each '
 'copy button copies that whole file. Below Main.java: Extensions.java (every follow-up\'s reference code, with an '
 '<code>ExtDemo</code> main that runs all of it) and FailureTests.java (fourteen claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT +
 '</div>Before typing, write your six to eight clarifying questions; then type in the order of Main.java: the enums (the '
 'copy\'s, the hold\'s and the loan\'s statuses, and the refusal reasons), the five small classes (Book with its shelf and '
 'its queue, BookCopy, Member, Loan, Hold), the two rules with one implementation each (LoanRules, FinePolicy) and the '
 'listener, the library with its one lock, <code>locked()</code>, the order inside <code>returnCopy</code> and '
 '<code>placeCopy</code>, the desk, and a main with the race. If the clock runs out, the one thing that must exist is '
 'checkout and return under one lock, with a returned copy going to the first member waiting before it goes to the '
 'shelf.</div></div>')

FU = [
("New rules: students borrow two books, faculty ten for sixty days; fines get a grace period, a student rate, a cap. Where does each go?", "functional", 10,
 "Both rules are already interfaces, so every change is a new class and the library never opens. Tiers are a table: "
 "<code>TieredTerms</code> maps each tier to its terms (books at once, days, renewals, the most he may owe), and the "
 "library asks it about the member in front of it. The fine changes are three wrappers, each asking the rule inside it "
 "first. <code>GraceDays</code> returns zero when the book is at most two days late and otherwise defers. "
 "<code>StudentRate</code> halves a student's fine, rounded down to a whole rupee. <code>CapAtPrice</code> returns the smaller "
 "of the fine and the book's price. The question the interviewer is really asking is the order of the wrapping, and it "
 "has one answer. The grace goes innermost, because a book two days late is free whoever you are; the cap goes "
 "outermost, because nobody pays more than a new copy costs; the student rate sits between them. None of this needed a "
 "new interface, because the rule is handed the whole loan, and the loan knows its book and its member.",
 X("rules that change", "ladder rung 1")
 + "\n// the one line that changes in the library's setup:\nlib.configure(new TieredTerms(), new CapAtPrice(new StudentRate(new GraceDays(new PerDayFine(2_000), 2))));\n"),

("One copy, two members at the same instant; and a return racing a new request. Prove both are safe, with a test.", "non-functional", 10,
 "The first race lives between reading \"PP-1 is on the shelf\" and taking it. <code>checkout</code> checks and takes "
 "inside one lock, so no other counter can run in that gap. The proof is a test: fifty threads wait on one latch, the "
 "latch opens, and all fifty ask for the only copy of The Pragmatic Programmer. Exactly one loan comes back, forty-nine "
 "hear NOT_AVAILABLE, and the copy is LOANED, not lost. The second race shows you understood the queue. A return that "
 "finds nobody waiting shelves the copy, and a request that finds no copy joins the queue. Both decisions happen under "
 "the same lock, and a new hold takes a copy straight off the shelf if one is there, so either order ends well. The test "
 "runs three returns against twenty requests, thirty rounds, and every round ends with three members served, seventeen "
 "waiting, nobody served twice and nothing on the shelf.",
 T("        // 1. the last copy", "        // 3. the limit")),

("One lock for the whole library. Does that scale, or is every desk now waiting in one line?", "non-functional", 5,
 "Every call does wait in one line, for about two microseconds. Inside the lock are two lookups, one rule call, a deque "
 "poll, a few map writes and one insert into the due index; the scanning, the printing and the SMS are all outside it. At "
 "an evening peak of five counters and fifty app searches a second, the lock is busy 0.05% of the time, and 99% of that "
 "is search. So the ladder starts with the reads. Rung one: the catalogue changes a few times a day, so each change builds "
 "a new index and publishes it with one volatile write (a write every other thread is guaranteed to see; this is copy-on-write: copy, "
 "change the copy, swap it in), and searches "
 "read it with no lock at all. Rung two: a lock per title, so members borrowing different books never wait for each "
 "other. The limit spans titles, so it moves out of the title lock into an atomic counter per member. He claims a slot "
 "with compare-and-set (write the new count only if it still holds the value you read), takes a copy under the title's "
 "lock, and gives the slot back if none was free. Each call holds one lock at a time, so there is no lock order to get "
 "wrong. The price is a rare false \"limit reached\" while a failed claim is being given back, never a false yes. Rung "
 "three is the database, in card 8.",
 X("ladder rung 1", "ladder rung 2") + "\n" + X("ladder rung 2", "several branches")),

("The fine rule throws mid-return, the SMS gateway is down, and a book is scanned twice. What state is the library in?", "functional", 10,
 "Nothing is half done, because of the order inside <code>returnCopy</code>. It finds the active loan without removing "
 "it, then asks the fine rule, the only handed-in code on the path. If the rule throws (say its holiday calendar is "
 "down), nothing has been written yet: the book is still on the member's card, the copy is still LOANED, and the member "
 "first in line is still first. The desk retries once the rule is fixed, and the retry charges once. The SMS is a "
 "listener, and <code>locked()</code> calls the listeners only after it has released the lock, each in its own "
 "try/catch, so a gateway that throws cannot undo the return or stop the next listener. A second scan of the same "
 "barcode finds no active loan and is refused with NOT_ON_LOAN, so nobody is fined twice and no copy is handed to two "
 "members. FailureTests 8 and 9 prove all three.",
 S("    Receipt returnCopy(String barcode)", "    Slip renew(String barcode)") + "\n"
 + S("    private <T> T locked(", "    private String placeCopy(") + "\n" + S("    private long fineFor(", "    private void publish(")),

("Every copy is out and three people want it. What happens when a copy comes back, and when the first never collects it?", "functional", 10,
 "A hold joins the back of its title's queue, a deque, and gets a position. When a copy comes back, "
 "<code>placeCopy</code> takes the first hold still WAITING and sets the copy aside for that member: status ON_HOLD, a "
 "pickup date three days away, and a HOLD_READY notice after the unlock. The copy never touches the shelf, so a walk-in "
 "cannot take it, and neither can the second person in line. If the member never comes, nothing has to wake up to "
 "notice. The READY holds sit in a heap ordered by pickup date, and every call first peeks at its head. Once that date "
 "has passed, the hold becomes EXPIRED and the copy goes through <code>placeCopy</code> again: to the next member or, "
 "with nobody waiting, back to the shelf. The test moves the injected clock from the 17th to the 18th and watches the "
 "copy pass from meera to kabir, with no timer thread and no sleep. This is Flipkart's 2025 prompt almost word for word: "
 "\"When the book is returned to the library, it will not be marked as available and will be available only to the "
 "first user under the FIFO queue.\"",
 S("    private String placeCopy(", "    private void cancel(") + "\n"
 + S("    private void sweep(", "    private void publish(")),

("Flipkart's version: ids like ROW1234 from the author's name, one copy per member, unregister, and who has which book.", "twist", 10,
 "Three of the four are already in the core. One copy of a title per member is the first check in "
 "<code>checkout</code> and <code>placeHold</code>: his loans and holds are kept by ISBN, so it is one lookup, and the "
 "answer is ALREADY_HAS_TITLE. The two audit questions are reads: <code>borrowersOf(isbn)</code> walks that title's few "
 "copies, and <code>loansOf(memberId)</code> reads his map. Unregister is refused while he has a book out or owes money. "
 "Otherwise his holds are cancelled, and a copy set aside for him goes to the next member through "
 "<code>placeCopy</code>. The id is the new part. <code>BookIdGenerator</code> takes the first three letters of the "
 "author's last name and adds a number from a counter for that prefix. The counter is created and advanced atomically, "
 "so two librarians adding Rowling books at the same instant get ROW1001 and ROW1002, never the same id twice. The test "
 "adds a thousand at once and counts a thousand different ids.",
 X("flipkart ids", "racks") + "\n" + S("    void unregister(String memberId)", "    // ---------------- lending") + "\n"
 + S("    List<Slip> loansOf(String memberId)", "    List<Slip> overdue()")),

("On the shelf? Who has it? What does he have? What is overdue? Titles starting 'clea'? The app asks all day: make each cheap.", "non-functional", 5,
 "No new structure is needed: each question already has its own shape, and each is read under the lock, so it never "
 "sees half a loan. On the shelf: the size of the title's shelf deque, O(1). Who has it: a walk over that title's copies, "
 "a handful, each looked up in the map of active loans. What he has: his loans, kept in a map by ISBN. What is overdue: "
 "the due-date TreeMap's <code>headMap(today)</code>, which costs O(log n) to find and one step per overdue loan, never a "
 "scan of every loan. Search: the sorted word index, where \"clea\" is the range from clea up to clea followed by the "
 "largest character, walked until the limit. The one honest exception is a member's place in the queue: a walk over that "
 "title's holds. A queue is a few dozen long, so it stays a walk.",
 S("    List<Found> searchTitle(", "    // ---------------- the private helpers")),

("Walmart: the database schema. Bloomberg: the SQL for overdue books. And what stops two app servers lending one copy?", "twist", 10,
 "The tables follow the classes: book, copy, member, loan and hold. The loan keeps the ISBN too, so the database itself "
 "can enforce one copy of a title per member, as a unique index over the loans still open. The overdue report joins the "
 "open loans with the member and the book where the due date is before today, oldest first. A partial index (an index "
 "over only the rows that match a condition) on the due date of open loans makes it the same range read the TreeMap does "
 "in memory. Two servers cannot both lend one copy because the claim is one conditional update: <code>UPDATE copy SET "
 "status='LOANED' WHERE barcode=? AND status='AVAILABLE'</code>. One row changed means he got it; zero means someone else "
 "did. That is the database's compare-and-set, the same idea as the lock. Returns and holds for one title first lock "
 "that title's row with <code>SELECT ... FOR UPDATE</code>, which is move 4 one layer down. And the in-memory maps go "
 "behind a repository interface, so the services above do not change.",
 X("persistence", "the copy's life as a table")),

("The workat.tech version: numbered racks, one copy of a book per rack, first free rack on return, lowest rack on borrow.", "twist", 10,
 "This changes one thing: the order in which the shelf hands copies out. In the core a title's shelf is a deque and any "
 "copy will do. Here the rule is \"the lowest rack\", so each book gets a TreeMap from rack number to copy, whose first "
 "entry is the lowest, and a BitSet of the racks already holding a copy of it. <code>nextClearBit(1)</code> finds the "
 "first free rack for that book in one call. Adding copies is all or nothing, and it counts the copies that are out as "
 "well as those on racks: each borrowed copy must find a rack when it comes back, so a book may own at most one copy per "
 "rack. If the new copies would break that, nothing is placed and the answer is \"Rack not available\". Borrowing a named "
 "copy takes it off its rack, and a return goes back to the first free rack, which is often the one it left. It is the parking lot's idea again: the "
 "order in which free things are handed out is a rule of its own.",
 X("racks", "reminders and a slow sms gateway")),

("He wants two more weeks. Or he has lost the book. What happens to the due date, the queue and his account?", "functional", 5,
 "Renewal adds one loan period to the due date, and says no in three cases: the book is already overdue (return it and "
 "pay), he has used his two renewals, or someone is waiting for the title. That last check reads the first live hold in "
 "the queue, so a cancelled hold does not block him. There is one trap. The due date is the key the loan is filed under "
 "in the due index; change it in place and the loan stays filed under the old date, and the overdue report lists a "
 "renewed book. So the loan leaves the index, the date changes, and it goes back in. Test 6 checks the report the day "
 "after the old date. A lost book is charged its price plus the fine so far. The copy becomes LOST and leaves "
 "circulation, and his slot is free again. Members waiting for the title keep their places, and a replacement copy, "
 "added later, goes straight to the first of them.",
 S("    Slip renew(String barcode)", "    void payFine(String memberId")),

("Due-date reminders and hold-ready SMS, through a gateway that takes a second per message. Nobody at a desk may wait.", "non-functional", 5,
 "The hold-ready notice already exists: the library builds it under the lock and delivers it after the unlock. The "
 "reminder is a nightly job. It asks the library for the loans due between today and two days from now, one range of "
 "the due index, and sends a DUE_SOON notice for each. One problem is left: listeners run on the caller's thread, so a "
 "gateway that takes a second per message would still slow the desk whose return triggered it. So the SMS sender "
 "becomes an outbox. Its <code>onEvent</code> only puts the notice in a queue, which takes microseconds, and a worker "
 "thread sends at the gateway's pace. A message the gateway refuses goes back in the queue, not in the bin. The test "
 "takes the gateway down, sees the message stay queued, brings it back and sees it sent once. One more thing to say: "
 "each call's notices keep their order, but two calls at the same instant may deliver theirs in either order. That is "
 "harmless here, because each notice is a separate fact about one member.",
 X("reminders and a slow sms gateway", "persistence")),

("There are twenty branches now. A member can return a book at any branch and collect his hold at his own.", "twist", 10,
 "Each branch keeps its own shelves, but a title's queue is shared, because a member waiting for Clean Code does not "
 "care whose copy he gets. So the queue has one owner and one lock, and a returned copy follows the core's rule: the "
 "first member waiting, else the shelf. The new part is where he collects. A hold names a pickup branch, and a copy "
 "that comes back at another branch cannot go on that branch's hold shelf. It goes IN_TRANSIT to his branch, and only "
 "when the van delivers it is it READY, with his three days starting then. That is one new status and one more hop in "
 "the place that decides a free copy's next stop. With nobody waiting, the copy stays on the shelf of the branch it came "
 "back to.",
 X("several branches", "flipkart ids")),

("Where does 'today' come from, and how do you test a fine on day fifteen, or a hold that expires in three days?", "design", 5,
 "The library is handed a <code>Clock</code>, a one-method interface, and turns its milliseconds into a date in the "
 "library's time zone. Each call reads it once, at the start of <code>locked()</code>, and every part of that call uses "
 "the same day, so a return at one second to midnight cannot price the fine on one day and close the loan on the next. A "
 "test hands in a clock that reads a variable. It lends a book on the 1st, sets the variable to the 15th and expects no "
 "fine. Then it lends again, moves to the 30th (one day past the new due date) and expects Rs 20. The pickup date works "
 "the same way: the test moves the variable from the 17th to the 18th, and the next call passes the copy on. Nothing "
 "sleeps, nothing is flaky, and nothing calls the system clock except the default the library starts with.",
 T("        // 7. fines", "        // 8. the fine rule throws")),

("Which pattern is where, and why did each one earn its place? Walmart's round named Singleton, Factory, Observer and Command.", "design", 5,
 "Each one is what a move produced, so name the move, then the line. Strategy is move 3: the loan terms and the fine are "
 "rules that change, so each sits behind a one-method interface the library is handed in <code>configure</code>. "
 "Decorator is the fine stack: a cap, a grace period and a student rate each wrap the rule inside them. Observer is "
 "move 4's rule that the SMS must never run inside the lock: the library announces and never learns who listens. State "
 "is move 6: the copy's and the hold's statuses, and one method, <code>placeCopy</code>, that decides where a free copy "
 "goes. The absences are worth saying without being asked. No Singleton: desks are handed the library, so every test "
 "builds its own. No Factory until the catalogue is imported from a file. No Command, because nothing queues or undoes a "
 "desk action. No Builder, because a book has four required fields.",
 S("interface FinePolicy", "interface LibraryListener") + "\n" + S("interface LibraryListener", "final class NoticePrinter")
 + "\n" + S("    private void publish(", "    private Member member(")),

("Which SOLID letter is where in this code?", "design", 5,
 "Not one of them was aimed at; each is a line some move already produced, which is the only convincing way to answer. "
 "S is the class list: a book owns its shelf and its queue, a member his loans and dues, a copy its status, the library "
 "the flow and the lock. O: the grace period, the student rate and the tiers were new classes and one changed "
 "<code>configure</code> line; the library never opened. L: the library calls <code>fines.fine(loan, today)</code> and "
 "never asks which rule it got. I: every interface has one method, so a fake is a lambda, and <code>(loan, d) -&gt; { "
 "throw ... }</code> is a broken fine rule in one line. D: the library depends on the interfaces it is handed, which is "
 "exactly why a test can hand it a clock that says the 18th and a fine rule that throws.",
 S("    void configure(LoanRules r", "    LocalDate today()") + "\n" + S("interface LoanRules", "final class StandardTerms")),

("Enum statuses or a State class per status? Subclasses for a DVD, a magazine, an e-book? And where would a Factory pay?", "design", 5,
 "Enums, until a status grows behaviour of its own. The copy's four statuses differ only in what may happen next, and "
 "that is data: a table from each status to the statuses it may move to, where every move not in the table throws. The "
 "same goes for tiers: a row of terms, not a Member subclass. A DVD lent for seven days and a reference book that is "
 "never lent are data too: one more column in the terms. An e-book is the counter-example: no barcode, no shelf, a "
 "number of licences, and loans that end by themselves on the due date, so it can never be late. That is different "
 "behaviour, so it earns its own class, not a BookCopy subclass that would inherit a shelf it never uses. A Factory pays "
 "when items stop arriving typed in code and start arriving as rows of a file: one maker registered per kind of row, "
 "instead of a growing switch.",
 X("the copy's life as a table", "e-books") + "\n" + X("e-books", "items from a file") + "\n" + X("items from a file", "Runs every extension")),
]

build(dict(
    slug="library", title="Library Management",
    subtitle="LLD &middot; Java &middot; OpenJDK 21 &middot; demo, 14 failure tests, a 50-thread race and a returns-versus-holds race pass",
    problem_body=PROBLEM_BODY,
    derivation_lead=("Run these on any LLD (parking lot, elevator, BookMyShow) and the class diagram, the lock, the tests, "
                     "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, "
                     "and nothing is named before the move that produced it."),
    moves=[(t, MV[k], txt) for (t, txt, k) in MOVES],
    uml_svg=UMLSVG, how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", src), ("Extensions.java", ext), ("FailureTests.java", tests)],
    test_class="FailureTests",
    implement_card_html=IMPLEMENT,
    followups=FU,
))
