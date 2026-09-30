# ATM LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"atm/Main.java").read_text()
ext   = (H/"atm/Extensions.java").read_text()
tests = (H/"atm/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def M(a, b):
    """slice a run of lines out of Main.java's main()"""
    return src[src.index(a):src.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("withdraw", 30, [("card in, PIN right", "three wrong on the card: kept"),
                          ("reserve the notes", "an exact combination, or refuse"),
                          ("ask the bank to debit", "one key, one debit, ever"),
                          ("push the notes", "a jam is credited back")]),
        ("deposit",  165, [("card in, PIN right", "the same visit"),
                           ("count the notes", "the reader counts; nobody types"),
                           ("ask the bank to credit", "its own key, one credit"),
                           ("receipt, audit log", "after the lock, never inside")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 2))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V95", dash=True) + _bx(380, 95, 350, 40, "no combination of notes: refused here", "", dash=True)
pf += _tx(88, 256, "read", "var(--acc)", 13) + _tx(175, 256, "at any moment, without touching the cassettes: what is the balance?  which rows did the bank never answer?", "var(--text)", 12, "start")
pf += _tx(88, 284, "give up", "var(--acc)", 13) + _tx(175, 284, "nobody has touched the screen for forty-five seconds: take the card back, without ever cutting into a withdrawal", "var(--text)", 12, "start")
pf += _tx(615, 322, "the accent box is the step that decides: it is the only one that cannot be undone, so everything reversible happens before it", "var(--muted)", 11.5)
pf += _tx(615, 342, "many machines share one account: the balance may never go below zero, and the drawer must always agree with what was debited", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 358, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:10  ACC-1 asks for 2,700", ["balance 10,000", "drawer 2000x2 500x4 200x3 100x5", "reserved 2000 + 500 + 200 = 3 notes",
                                        "debit ok, only then pushed", "balance 7,300, drawer down 3 notes"], True),
      ("09:20  the same card asks 2,750", ["not a multiple of 100", "refused before anything moved",
                                           "balance still 7,300"], False),
      ("11:40  drawer is 500x1, 200x3", ["600 asked; greed dead-ends on the 500", "backs off and pays 200 x 3 = 600",
                                         "the machine pays what it can pay"], False),
      ("16:05  the link to the bank dies", ["debit sent, no answer at all", "nothing dispensed; row = UNKNOWN",
                                            "reconciled at 18:00, balance intact"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 130, t, lines, acc=acc)
P_EX = _mv(1230, 205, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Take a card and check the PIN; after three wrong PINs in a row on that card, on any machine, keep the card.</li>
<li>Withdraw cash: an exact combination of the notes actually in the cassettes, or a refusal.</li>
<li>Show the balance; take cash in and credit exactly what the note reader counted.</li>
<li>Every withdrawal attempt is one row in a journal (the machine's own record), written <i>before</i> the bank is asked and never deleted.</li>
<li>A withdrawal that fails after the money left the account is credited back automatically.</li>
<li>A withdrawal the bank never answered dispenses nothing and is reconciled later: the bank is asked to reverse it, which gives the money back only if the debit landed.</li>
<li>If nobody touches the screen for forty-five seconds, the machine takes the card back by itself.</li>
<li>Give the card back, reset, and be ready for the next customer.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many machines share one account: the balance may never go below zero and no debit may be lost.</li>
<li>The cash that left the drawer must always equal the money that left the account.</li>
<li>Whole rupees, never a <code>double</code>: a rounding error in a dispenser is a real cash difference.</li>
<li>"How many 500s are left?" and "has this key been applied?" are O(1). The key is an idempotency key: the bank applies each key at most once, so a retry cannot take the money twice.</li>
<li>The note rule, the amount rule and the listeners are swappable without touching the machine.</li>
<li>Nothing half-done: a refusal leaves the cassette and the balance exactly as they were.</li>
<li>In memory, one process per machine, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design an ATM. A customer puts in a card, types a PIN, and takes cash out; the machine holds the notes '
          'and the bank holds the money. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A box on a wall with money in it: a customer puts a card '
 'in, types a PIN and asks for an amount. The machine must then find an exact combination of the notes in its '
 'cassettes (the locked trays of notes inside it), get the bank to take that money off the account, and push the '
 'notes out. Two owners hold the two halves. The <b>bank</b> owns the balance: the machine can neither see it nor '
 'lock it, and a phone may be spending the same account at the same moment. The <b>machine</b> owns the notes. The '
 'one thing that must always be true is that those two stories agree: never hand out money that was not debited, '
 'and never debit money that cannot be handed out. Every way this goes wrong &mdash; an empty cassette, a declined '
 'card, a jammed note path, a bank that simply does not answer, a customer who walks off mid-visit &mdash; has to '
 'end with the customer no worse off than before.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with '
 'a <code>main</code> that withdraws cash and shows what happens when it cannot. The interviewer is watching for, in '
 'this order: the questions you ask before typing (who owns the balance is the first one); which classes exist and '
 'which one owns which state; a withdrawal end to end; what happens when two terminals hit the same account at the '
 'same instant; where the rules that will change (which notes, what limit, who is told) live, so a change is a new '
 'class and not an edit; and the order of operations at the moment money moves, because that order is the whole '
 'answer. Then the twists: a daily cap, a lopsided drawer, a jam, a bank timeout, a customer who walks away, '
 'deposits, persistence.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>One machine, or the whole network of them?</td><td>One machine, many of them, one bank behind</td><td>The machine owns the cash and the session; the bank owns the balance (moves 1, 4)</td></tr>'
 '<tr><td>Which notes, and must the amount come out exactly?</td><td>2000 / 500 / 200 / 100; exact or nothing</td><td>An <code>EnumMap</code> cassette and a note rule that backs off (moves 3, 5)</td></tr>'
 '<tr><td>How many wrong PINs, and then what?</td><td>Three in a row on the same card, then the machine keeps it</td><td>The bank counts per card, so taking the card out buys no fresh tries (moves 2, 6)</td></tr>'
 '<tr><td>What if the notes jam after the bank has debited?</td><td>Credit it back, automatically</td><td>Reserve before debit, and a reversal: one credit that undoes the debit (move 6)</td></tr>'
 '<tr><td>What if the bank does not answer at all?</td><td>Dispense nothing; settle it later</td><td>A third answer, TIMEOUT, an UNKNOWN row, and a reversal sent later (moves 6, 9)</td></tr>'
 '<tr><td>Daily limits, fees, more than one currency?</td><td>A per-transaction rule now, a daily cap as a follow-up</td><td>The rule behind an interface; the cap wraps the bank (moves 3, 12)</td></tr>'
 '<tr><td>Deposits: does the machine count the cash?</td><td>Yes: its note reader counts it; an envelope machine is a follow-up</td><td>The credit is what was counted, never a typed number (moves 2, 12)</td></tr>'
 '<tr><td>How long before the machine gives up on a customer who walks away?</td><td>Forty-five quiet seconds, then it takes the card back</td><td>A watchdog thread that waits on the machine\'s own lock (moves 7, 8)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> the bank owns the balance and the machine owns the notes, so the one '
 'step that checks the balance and takes the money belongs to the bank, and the machine never reads a balance and then '
 'writes it; the bank also counts wrong PINs, per card; whole rupees, never a double; an amount is paid exactly or '
 'refused; a withdrawal reserves the notes before it asks for the money; one process, in memory, one machine per '
 'object. Named as out of scope: more than one currency, transfers, PIN change. Envelope deposits and persistence are '
 'follow-ups on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a CARD starts a SESSION; the BANK owns the BALANCE; the CASSETTES hold NOTES; a WITHDRAWAL is one attempt; a RULE picks the notes", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 165, "Card", "a number, an account", 0), (215, 175, "Session", "where the visit has got to", 1),
                          (410, 185, "Withdrawal", "amount, notes, state, key", 1), (615, 175, "CashDispenser", "the note counts", 1),
                          (810, 180, "BankService", "the balance: not ours", 0), (1010, 190, "Note rule", "no state: an interface", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state here: a value, an interface, or somebody else's data", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("pick the notes for an amount", "NoteSelection  (owns nothing: pure)", "rule.select(stock, amount)"),
                                       ("take money off an account", "BankService  (owns the balance)", "bank.debit(acct, amt, key)"),
                                       ("count the wrong PINs", "BankService  (owns the card's record)", "bank.authenticate(card, pin)"),
                                       ("run one withdrawal end to end", "ATM  (owns the session, journal, lock)", "atm.withdraw(amount)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 269, "a verb whose state is spread over two owners goes to the one that can see both: the machine calls the others in order, and stores no money", "var(--muted)", 11)
m2 += _tx(615, 288, "and \"deposit\" is not a second machine: the note reader counts the cash, and the bank credits what was counted", "var(--muted)", 11)
MV[2] = _mv(1230, 301, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 60, 220, 90, "ATM", "configure(policy, selection)", acc=True)
for k, (t, sub, impl) in enumerate([("NoteSelection", "fewest notes, ration the 2000s", "FewestNotes / RationBigNotes"),
                                    ("WithdrawalPolicy", "a minimum, a ceiling, a multiple", "AmountRules / a daily rule"),
                                    ("AtmObserver", "receipt, audit, low cash, fraud", "ReceiptPrinter / AuditLog")]):
    y = 24 + k*60
    m3 += _ar("M250 105 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 212, "dashed green = handed in. The machine never builds a rule, so a new note rule is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 232, "and one rule wraps a collaborator instead of a rule: DailyCap wraps the BankService, so \"cap it at 20,000 a day\" touches no ATM code at all", "var(--acc)", 11)
MV[3] = _mv(1230, 245, m3)

# move 4: the gap, and the owner of the number does the atomic step
m4 = _D + _bx(30, 30, 200, 44, "the machine in the mall", "reads balance 500") + _bx(30, 110, 200, 44, "the netbanking app", "reads balance 500")
m4 += _bx(360, 70, 190, 44, "ACC-9 balance", "500", acc=True)
m4 += _ar("M230 52 H360 V70") + _ar("M230 132 H360 V114") + _tx(295, 40, "read", "var(--muted)", 10.5) + _tx(295, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="590" y="20" width="290" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(735, 45, "the gap", RED, 12) + _tx(735, 70, "both read 500, both subtract 500", RED, 11) + _tx(735, 90, "the account ends at minus 500", RED, 11)
m4 += _tx(735, 130, "fix: read and subtract as ONE step", "var(--text)", 11)
m4 += _bx(910, 40, 290, 100, "bank.debit(acct, amt, key)", "compare-and-set, or read again", acc=True)
m4 += _tx(1055, 165, "the machine cannot lock a balance it does not own", "var(--muted)", 10.5)
m4 += _tx(1055, 185, "so the owner of the number does the atomic step", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is this account's balance?", "Map&lt;account, AtomicLong&gt;", "O(1)"),
                                      ("how many 500s are left?", "EnumMap&lt;Note, Integer&gt;", "O(1)"),
                                      ("has this key already been applied?", "Map&lt;key, BankReply&gt;", "O(1)"),
                                      ("which rows did the bank not answer?", "List&lt;Withdrawal&gt;, append only", "O(all rows)")]):
    y = 20 + k*50
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 240, "nothing re-reads the day's transactions to answer a balance: the balance IS the number, and the key map is what makes a retry safe", "var(--muted)", 11)
MV[5] = _mv(1230, 255, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(30, 30, 170, 44, "PENDING", "nothing asked yet", acc=True)
m6 += _bx(240, 30, 170, 44, "DEBITED", "the money left", acc=True) + _bx(450, 30, 170, 44, "DISPENSED", "the customer has it", acc=True)
m6 += _bx(30, 120, 170, 44, "REFUSED", "nothing moved") + _bx(240, 120, 170, 44, "REVERSED", "jammed, credited back")
m6 += _bx(450, 120, 170, 44, "UNKNOWN", "no answer; reconcile")
m6 += _ar("M200 52 H240", True) + _ar("M410 52 H450", True) + _ar("M115 74 V120") + _ar("M325 74 V120") + _ar("M200 63 H222 V186 H535 V168")
m6 += '<rect x="660" y="20" width="550" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(935, 44, "the order at the moment money moves, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 write the row, then check the amount rule: nothing reserved yet",
                       "2 RESERVE the notes: choose a combination and take it out of the cassette",
                       "3 ask the bank to debit, with this row's key",
                       "4 only now push the notes; a jam is credited back under a second key",
                       "a refusal at 1 or 2 has moved no money at all: the customer can ask for less;",
                       "a bank that never answers dispenses nothing; the row is reversed later"]):
    m6 += _tx(675, 68 + k*23, l, "var(--muted)" if k > 3 else "var(--text)", 11, "start")
m6 += _tx(615, 232, "six states and one rule: reserve what is reversible first, and do the irreversible thing last. The journal row is written before the bank is asked.", "var(--muted)", 11)
MV[6] = _mv(1230, 245, m6)

# move 7: what is inside the lock, and ten terminals on one account
m7 = _D + _card(30, 20, 540, 150, "inside the machine's lock: about three seconds",
                ["the journal row and the amount rule: about a microsecond", "reserve the notes: the dispenser's own lock, ~2 us",
                 "the bank round trip over the network: about a second", "pushing the notes into the slot: about two seconds",
                 "so nearly all of it is waiting for the bank and the motor"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside it: the rest of the visit",
            ["the customer reading the screen: about 20 seconds", "typing the PIN and the amount: about 10 seconds",
             "the receipt printer: about 300 ms, after the unlock", "one whole visit: about 45 seconds"])
m7 += _tx(615, 200, "ten terminals hit ONE account at the same instant: the bank is the only thing they share", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "terminal %d" % (k+1), "wins on try %d" % (k+1), acc=(k == 9))
m7 += _tx(615, 283, "at worst the tenth loses the compare-and-set nine times, reading the fresh balance each time: microseconds in all, and nobody waits for a lock", "var(--muted)", 11)
m7 += _tx(615, 301, "inside one machine there is no queue at all, because a machine serves one customer, which is what a machine is", "var(--muted)", 11)
m7 += _tx(615, 325, "the one thread that is NOT a customer is the watchdog: it calls ejectCard(), which wants the same lock, so it waits out those three seconds", "var(--acc)", 11)
m7 += _tx(615, 343, "instead of taking the card back between the debit and the push -- safe, but it is the reason rung 1 of the next move exists", "var(--acc)", 11)
MV[7] = _mv(1230, 357, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per machine: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a visit is about 45 seconds; a busy machine does ~80 a day",
                       "the lock is held ~3 s a withdrawal, 80 times: 240 seconds",
                       "240 s out of 86,400 s: the lock is busy 0.3% of the day",
                       "and there is only ever one customer standing at one machine",
                       "the bank: ~900 debits a second nationwide, one compare-and-set each"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 the bank call and the push outside the lock", "a state guards the gap, so the watchdog never waits on the bank or the motor"),
                              ("2 one balance per account, which it already is", "the compare-and-set scales with accounts, not machines; only hot accounts meet"),
                              ("3 beyond one process: the row becomes the lock", "UPDATE account SET balance = balance - ? WHERE id = ? AND balance &gt;= ?")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("wrong PINs on one card", "the bank counts per card; tests 1 and 13: out and back in buys no fresh tries"),
                                ("the drawer cannot make the amount", "refused BEFORE the bank is asked; test 2: the bank saw zero calls"),
                                ("the bank declines after reserving", "every reserved note goes back; test 3: the cassette counts are identical"),
                                ("the note path jams after the debit", "reversed under a second key; tests 4 and 15: even when the credit-back fails"),
                                ("the bank never answers, or throws", "dispense nothing, row = UNKNOWN; tests 5 and 14: reversed later, never re-debited"),
                                ("two machines want the same last 500", "the bank's compare-and-set is the only writer; test 9: twenty of forty paid"),
                                ("the customer walks away mid-withdrawal", "the watchdog waits for the machine's lock; test 11: it cannot cut in"),
                                ("a deposit of nothing, or of -500", "the credit is what the reader counted; test 16: refused, balance unmoved")]):
    y = 18 + k*42
    m9 += _bx(30, y, 300, 38, bad, "") + _ar("M330 %s H380" % (y+19), True) + _bx(380, y, 820, 38, fix, "", acc=True)
m9 += _tx(615, 376, "and the rest: a printer that throws (test 7), one key charged once (8), a cap asked the same key twice (10), a low-cash floor (12),", "var(--muted)", 11)
m9 += _tx(615, 394, "note rules (6), local midnight and a jam against the cap (17), the state-object sketch (18). FailureTests.java runs 53 checks and must print ALL PASS.", "var(--muted)", 11)
MV[9] = _mv(1230, 408, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 830)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface NoteSelection { select(stock, amount): plan }", None), ("a new note rule is a class, not an edit", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface WithdrawalPolicy { refuse(acct, amt, now): String }", None), ("limits and fees become configuration", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("class DailyCap implements BankService { base.debit(...) }", None), ("\"cap it at 20,000 a day\" touches no ATM code", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(e) AFTER the unlock, each listener in a try/catch", None), ("the receipt hears; the money flow never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("Transitions.ALLOWED: SessionState &rarr; the moves it may make", None), ("an illegal action is refused by a table lookup", None)],
          [("Command", "var(--text)"), ("move 6", None), ("the Withdrawal row: its amount, its notes and its key", None), ("the reversal is that row with the sign flipped", None)],
          [("Chain of Responsibility", "var(--muted)"), ("not earned", None), ("the back-off walks Note.values() in order, in one method", "var(--muted)"), ("it earns links when a link carries its own policy", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("the machine is HANDED its bank and its dispenser", "var(--muted)"), ("a test builds forty fresh ATMs in a loop", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("Note.values() is already the registry of denominations", "var(--muted)"), ("it earns the name when notes come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a withdrawal has one field the customer chose: the amount", "var(--muted)"), ("there is nothing to build", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 374, "name a pattern only after the move that produced it; then every name has a one-sentence defence, and the empty rows are as useful as the full ones", "var(--muted)", 11)
MV[10] = _mv(1230, 388, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("CashDispenser: the notes. ATM: the flow and the lock. The bank: the balance.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("DailyCap is a new file plus one wiring line; the ATM never opened", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("rule.select(stock, amount);  never \"is this the rationing one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("NoteSelection, WithdrawalPolicy, AtmObserver, NoteFeeder, Clock", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("new ATM(id, bank, dispenser);  atm.setClock(() -&gt; fixedMs)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "ration the 2000s, a fee, a limit", "a new class behind NoteSelection or WithdrawalPolicy, one wiring line", "", "move 3"),
        ("someone new wants to know", "mini-statement, low-cash alert, fraud", "one more observer; the order at the critical step does not change", "", "move 4"),
        ("a new step in a life", "an envelope waiting to be counted", "one more state and one more row in the ALLOWED table", "", "move 6"),
        ("a new invariant across owners", "cash and balance must always agree", "reserve, then debit, then reverse on a jam: one order, all or nothing", "", "move 6"),
        ("state that must outlive the process", "the machine rebooted mid-withdrawal", "the journal behind a repository; claiming a key becomes an INSERT", "UPDATE account SET balance = balance - ? WHERE id = ? AND balance &gt;= ?", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the ATM, the dispenser and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>card</b> starts a <b>session</b>; the <b>bank</b> owns the <b>balance</b>; the "
 "<b>cassettes</b> hold <b>notes</b>; a <b>withdrawal</b> is one attempt at moving money; a <b>rule</b> decides which "
 "notes come out. A session has a card and a place in the visit, which changes: a class. A withdrawal has an amount, "
 "the notes reserved for it, a status and an idempotency key: a class, and the row an operator reconciles from. The "
 "cassettes have counts that change: a class with its own lock. A card is a number and an account id and nothing that "
 "moves, so it is a value. And the balance is the one that matters: it is not ours. The machine never holds a "
 "balance, so the class that appears is <code>BankService</code>, an interface, because the thing behind it is "
 "somebody else's process. The count of wrong PINs is not ours either: it belongs to the card, and the card is the "
 "bank's.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Pick the notes for an amount\" touches no state at all &mdash; it reads a stock map and an amount and returns a "
 "plan &mdash; so it belongs to a pure rule, <code>rule.select(stock, amount)</code>. \"Take money off an account\" "
 "touches the balance, which lives at the bank, so it belongs to the bank: <code>bank.debit(acct, amount, key)</code>. "
 "\"Count the wrong PINs\" touches the card's record, which is the bank's too, so the bank counts: if the visit "
 "counted, a thief could take the card out after two wrong tries and put it back for three fresh ones. \"Run one "
 "withdrawal end to end\" touches the session, the journal, the cassettes and the bank; only the machine can see all "
 "four, so <code>atm.withdraw(amount)</code> is the orchestrator (the one that calls the others, in order), and it "
 "stores not a single rupee. A deposit is not a second machine either: the note reader counts the cash, and the bank "
 "credits what was counted, under the deposit's own key.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Which notes come out will change: fewest today, \"stop giving out 2000s before noon\" tomorrow. What is allowed will "
 "change: a minimum, a ceiling, a multiple, a fee, a daily cap. Who is told will change: a receipt today, an audit "
 "log and a fraud feed later. Each becomes a one-method interface the machine is <i>given</i> in "
 "<code>configure()</code> and never builds. This is where the patterns come from, not the other way round: a "
 "swappable rule behind an interface is <b>Strategy</b>; a machine that announces \"a withdrawal happened\" without "
 "knowing what a printer is, is <b>Observer</b>. And the <b>Decorator</b> here is the one worth remembering, because "
 "it wraps a collaborator rather than a rule: <code>DailyCap</code> implements <code>BankService</code>, holds a real "
 "bank inside it, counts what an account has taken today and returns DECLINED over the cap. \"Cap withdrawals at "
 "twenty thousand a day\" is then a new file and one wiring line, and the machine does not learn a new word.", 3),
("Move 4: state that many callers change at the same time gets one owner and one atomic step.",
 "A machine in a mall and a netbanking session both read the balance as five hundred, both subtract five hundred, and "
 "both write: the account ends at minus five hundred and the bank is short. The fix is the same as always &mdash; the "
 "read and the write have to be one step &mdash; but the twist on this problem is that the machine <i>cannot</i> do "
 "it. It does not own the balance; it cannot lock a number in another process. So the atomic step (one step that "
 "nobody can cut into) is pushed to the owner: <code>bank.debit(...)</code> runs a compare-and-set loop on the "
 "account's balance. Compare-and-set means: read the number, decide, and write it back only if nobody changed it in "
 "between. A debit that loses the race reads the fresh number and decides again, instead of overwriting somebody. "
 "What the machine <i>does</i> own "
 "&mdash; the cassette counts, the session, the journal &mdash; gets a lock of its own, and anything that only listens "
 "(the receipt, the audit log) is called after that lock is released, never inside it.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What is this account's balance?\" is a map from account to a single <code>AtomicLong</code>: one number, one "
 "writer, no history to walk. \"How many 500s are left?\" is an <code>EnumMap</code> from note to count, which is an "
 "array behind the scenes, so a count is an array index and the whole cassette is four entries. \"Has this key already "
 "been applied?\" is a map from idempotency key to the answer that was given, and it is what makes a retried request "
 "safe rather than a second debit. \"Which rows did the bank never answer?\" is a scan of the journal, which keeps "
 "every attempt and is never pruned: O(n) over all rows, about 30,000 after a year at eighty a day. That is well "
 "under a millisecond, for a question an operator asks a few times a day, so it earns no index of its own.", 5),
("Move 6: anything with a life cycle is a state machine, and the ORDER of operations is the design.",
 "There are two life cycles. The visit is IDLE &rarr; CARD_INSERTED &rarr; AUTHENTICATED &rarr; TRANSACTION &rarr; "
 "DISPENSING and back, held in a table of allowed moves so an action in the wrong place is refused by a lookup rather "
 "than by a wall of if-statements. The money has its own: PENDING, then REFUSED (nothing moved), DEBITED (the money "
 "left the account), DISPENSED (the customer is holding it), REVERSED (it jammed and we credited it back) or UNKNOWN "
 "(nobody knows yet whether money moved). Writing them down forces the order, and the order is the whole answer. Write "
 "the journal row first, then check the amount rule: a refused amount leaves a REFUSED row and touches nothing else. "
 "Then <i>reserve</i> the notes &mdash; choose a combination and take it out of the cassette in one step &mdash; "
 "because a reservation is reversible and a debit is not, and because an empty cassette must be discovered before an "
 "account is touched. Then ask the bank, with this row's key. Only then push the notes; if the hardware jams, reverse "
 "the debit (one credit, under the row's key plus \"-rev\") and mark the row REVERSED. And if the bank does not "
 "answer, or the call throws, dispense nothing and leave the row UNKNOWN: a timeout is not a no, it is \"nobody knows "
 "yet\", and handing out cash on a guess is how a machine loses real money.", 6),
("Move 7: yes, the machine's lock makes its customers go one at a time. Ask for how long, and what is inside it.",
 "Inside the machine's lock there is the journal row, the amount rule and a reserve on the dispenser's own lock, "
 "about two microseconds in all &mdash; and two slow things: the bank round trip, about a second, and the notes being "
 "pushed into the slot, about two seconds. So the lock is held for about three seconds, and nearly all of it is "
 "waiting for the bank and the motor. That sounds bad until you notice what a machine is: one customer, standing "
 "there, for about forty-five seconds. Nobody else is in the queue. The screen, the typing and the receipt are outside "
 "the lock anyway. The place where things really do arrive at the same instant is the bank, and there the answer is "
 "the compare-and-set: ten terminals hitting one account need microseconds between them, because each loser simply "
 "reads the fresh balance and tries again. One thread in this system is not a customer: the watchdog that takes the "
 "card back when somebody walks away. It calls <code>ejectCard()</code>, which wants the same lock, so if a "
 "withdrawal is in flight the watchdog waits for it rather than ejecting a card in the gap between the debit and the "
 "notes. That is the right answer, and it costs the watchdog about three seconds of waiting; when the bank is slow, "
 "it waits as long as the bank does. That is why the next move has a rung 1.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A busy machine does about eighty withdrawals a day. At about three seconds of lock each, that is 240 seconds of a "
 "day: the lock is busy less than three tenths of one per cent of the time, and only ever against one customer who is "
 "not there twice. At the bank the number that matters is different: forty thousand machines busy at peak, each "
 "finishing a visit every forty-five seconds, is roughly nine hundred debits a second. Each one is a compare-and-set "
 "on its own account's number, which is tens of nanoseconds of work. Then the ladder, cheapest first. One: move the "
 "bank call and the push out of the machine's lock, holding it only for the reservation and the state writes, with a "
 "state that says a withdrawal is in flight. You do not need this for throughput (withdrawals per second); you need "
 "it because of the watchdog in move 7, which cannot take a card back while the bank is thinking. Two: nothing, because the "
 "balances are already one atomic number per account, so the cost grows with hot accounts and not with machines. "
 "Three: when the balance stops being an <code>AtomicLong</code> and becomes a row, the compare-and-set becomes "
 "<code>UPDATE account SET balance = balance - ? WHERE id = ? AND balance &gt;= ?</code>: one row updated means paid, "
 "zero rows means declined. Say the arithmetic first; climbing the ladder without it is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Three wrong PINs (the card is captured and the visit ends; because the bank counts per card, taking it out and "
 "putting it back buys no fresh tries). A drawer that cannot make the amount (refused before the bank is asked, which "
 "the test proves by counting the calls the bank received: zero). A decline after the notes were reserved (every note "
 "goes back, and the cassette counts afterwards are identical). A jam after the debit (a reversal under a second key; "
 "the notes are counted into the retract bin, a sealed box inside the machine, rather than pretended back into the "
 "cassette, so the cash in the machine still adds up; and if even the credit-back fails, the row says UNKNOWN, never "
 "settled). A bank that never answers, or a call that throws (nothing dispensed, the row left UNKNOWN; later a "
 "reconciler sends a reversal for the <i>same</i> key, which gives the money back if the debit landed and makes sure "
 "it can never land if it did not). The race: forty machines, one account with ten thousand in it, everybody asking for five hundred &mdash; "
 "exactly twenty are paid, the balance lands on zero, and the cash that left the drawers equals the money that left "
 "the account. Two more only a running program finds. A customer who walks away while the bank is thinking: the "
 "watchdog waits for the lock, so the card comes out after the notes and never instead of them. A daily cap asked "
 "the same idempotency key twice: a retry is not a second withdrawal, so it must be let straight through, or the "
 "machine is told no about money that really left. A design that cannot show its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; what it cannot show is why four names are missing. Chain of Responsibility is the "
 "interesting refusal, because it is the classic ATM answer: one handler per denomination, each passing the remainder "
 "down the chain. The textbook chain is pure greed: each link takes all it can and passes the rest on, so it refuses "
 "the 600 on page 05. This code walks <code>Note.values()</code> in one method and can step back: four fewer classes "
 "and a right answer. The chain earns its links the day a link carries a policy of its own. Singleton earned nothing: "
 "the machine is handed its bank and its dispenser, which is exactly how a test builds forty of them in a loop, and a "
 "static instance would make that impossible. Factory not yet: <code>Note</code> is already the registry of "
 "denominations, and a factory earns its place the day they arrive from a config file. Builder never: the customer "
 "chooses one field, the amount. Saying why a pattern is absent is worth more in the room than naming one that is "
 "there, because it shows the names are conclusions and not decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "Read the table as five questions with a yes already written in. The one that actually pays here is D: the machine "
 "is handed a <code>BankService</code> and a <code>Clock</code>, both interfaces, and its dispenser is handed a "
 "<code>NoteFeeder</code>. That is the only reason the failure tests can give it a bank that times out on demand, a "
 "feeder that jams once and a clock stuck on a Tuesday. If a letter has no line in the code next to it, the move that should have produced it "
 "did not happen &mdash; that is what this table is for, not recital.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The value of the table is the sentence you say before you type: \"that is a new rule, so it is a new class behind "
 "<code>NoteSelection</code> and one wiring line\". Two rows are worth spelling out. The last one is the real change "
 "of shape: once the journal must outlive the process it goes behind a repository, claiming a key becomes an "
 "<code>INSERT</code> that a duplicate key rejects, and the debit becomes <code>UPDATE account SET balance = balance "
 "- ? WHERE id = ? AND balance &gt;= ?</code> &mdash; the database doing exactly the atomic step the compare-and-set "
 "did in memory. The fourth is the one people skip: an invariant that spans two owners is not a new class at all, it "
 "is the order, and the order is already reserve, debit, reverse. For all five, the ATM, the dispenser and the "
 "tests do not change; that is the test that the derivation was right. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, Splitwise) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On this problem the moves earn their keep in move 4 and move 6, because the "
 "invariant (the rule that must always hold) spans two owners: the money is the bank's and the notes are the "
 "machine's, and they must always tell the same story.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the values and the two life cycles
put("session",    10,  50, 270, "Session", ["id: String", "card: Card", "state: SessionState", "startedMs: long"], [])
put("sstate",     10, 195, 270, "SessionState", ["IDLE, CARD_INSERTED,", "AUTHENTICATED, TRANSACTION,", "DISPENSING, EJECTED"], [], "enum")
put("withdrawal", 10, 315, 270, "Withdrawal", ["id: int / key: String", "accountId: String", "amount: long", "notes: EnumMap&lt;Note,int&gt;", "state: TxnState", "note: String"], ["refuse(why): Withdrawal", "noteCount(): int"])
put("tstate",     10, 515, 270, "TxnState", ["PENDING, REFUSED, DEBITED,", "DISPENSED, REVERSED, UNKNOWN"], [], "enum")
put("card",       10, 620, 270, "Card", ["number: String", "accountId: String"], [])
put("event",      10, 715, 270, "AtmEvent", ["atmId / kind: String", "accountId: String", "amount / atMs: long", "txn: Withdrawal"], [])
# centre: the aggregate root and what it owns
put("atm",       320,  50, 340, "ATM", ["id: String", "bank: BankService", "dispenser: CashDispenser", "lock: ReentrantLock", "policy: WithdrawalPolicy", "clock: Clock", "session: Session", "journal: List&lt;Withdrawal&gt;", "observers: List&lt;AtmObserver&gt;"],
                                        ["configure(policy, selection)", "setClock(clock) / addObserver(o)", "insertCard(card) / enterPin(pin)", "balance(): long", "withdraw(amount): Withdrawal", "deposit(counted notes): long", "ejectCard()", "state() / journal() / unresolved()"])
put("dispenser", 320, 410, 340, "CashDispenser", ["stock: EnumMap&lt;Note,int&gt;", "lock: ReentrantLock", "selection: NoteSelection", "feeder: NoteFeeder", "retracted: int"],
                                                 ["reserve(amount): plan | null", "release(plan)", "push(plan) throws HardwareFault", "refill(note, n) / count(note)"])
put("note",      320, 630, 340, "Note", ["N2000, N500, N200, N100", "(largest first: the picking order)"], [], "enum")
# right column: the seams, each handed in
put("bank",      690,  50, 290, "BankService", [], ["authenticate(cardNo, pin): PinCheck", "balance(acct): long", "debit(acct, amt, key): BankReply", "credit(acct, amt, key)", "reverse(acct, amt, key): boolean"], "interface")
put("inmem",     690, 180, 290, "InMemoryBank", ["balances: Map&lt;acct, AtomicLong&gt;", "applied: Map&lt;key, BankReply&gt;", "wrongPins: Map&lt;card, int&gt;"], ["authenticate: count per card", "debit: computeIfAbsent(key)", "cas: compare-and-set loop", "reverse: mark key dead, give back"])
put("clock",     690, 350, 290, "Clock", [], ["nowMs(): long"], "interface")
put("policy",    690, 420, 290, "WithdrawalPolicy", [], ["refuse(acct, amt, now): String"], "interface")
put("amount",    690, 490, 290, "AmountRules", ["min / max / step: long"], ["refuse: bounds + a modulo"])
put("select",    690, 585, 290, "NoteSelection", [], ["select(stock, amount): plan"], "interface")
put("fewest",    690, 670, 290, "FewestNotes", [], ["select: greedy, then back off", "(600 from 500x1 + 200x3)"])
put("feeder",    690, 765, 290, "NoteFeeder", [], ["feed(notes)"], "interface")
put("feeders",   690, 838, 290, "WorkingFeeder", [], ["feed(notes): always works", "JammingFeeder *: throws once"])
# far right: the listeners, the failures, the table
put("obs",       995,  50, 230, "AtmObserver", [], ["onEvent(e: AtmEvent)"], "interface")
put("listeners", 995, 140, 230, "ReceiptPrinter | AuditLog", [], ["onEvent -&gt; print / keep"])
put("failed",    995, 220, 230, "WithdrawalFailed", ["w: Withdrawal"], [])
put("errors",    995, 300, 230, "the other failures", ["CardRetained: the card is kept", "HardwareFault: the notes jammed"], [])
put("reply",     995, 405, 230, "BankReply", ["OK, DECLINED, TIMEOUT"], [], "enum")
put("trans",     995, 490, 230, "Transitions", ["ALLOWED: SessionState &rarr;", "  the moves it may make"], [])
put("pin",       995, 580, 230, "PinCheck", ["OK, WRONG, BLOCKED"], [], "enum")

edges = [
    ln(B["atm"]["l"], B["session"]["r"], "compose", ""),
    ln(B["atm"]["l"], B["withdrawal"]["r"], "compose", ""),
    ln(B["atm"]["b"], B["dispenser"]["t"], "compose", "the cassettes"),
    ln(B["session"]["b"], B["sstate"]["t"], "assoc", "state"),
    ln(B["withdrawal"]["b"], B["tstate"]["t"], "assoc", "state"),
    ln(B["dispenser"]["b"], B["note"]["t"], "assoc", "counted per"),
    ln(B["atm"]["r"], B["bank"]["l"], "inject", ""),
    ln(B["atm"]["r"], B["clock"]["l"], "inject", ""),
    ln(B["atm"]["r"], B["policy"]["l"], "inject", ""),
    ln(B["dispenser"]["r"], B["select"]["l"], "inject", ""),
    ln(B["dispenser"]["r"], B["feeder"]["l"], "inject", ""),
    ln(B["inmem"]["t"], B["bank"]["b"], "inherit", ""),
    ln(B["amount"]["t"], B["policy"]["b"], "inherit", ""),
    ln(B["fewest"]["t"], B["select"]["b"], "inherit", ""),
    ln(B["feeders"]["t"], B["feeder"]["b"], "inherit", ""),
    ln(B["listeners"]["t"], B["obs"]["b"], "inherit", ""),
    ln(B["bank"]["r"], B["reply"]["l"], "assoc", "", via=[(987, B["bank"]["r"][1]), (987, B["reply"]["l"][1])]),
    ln(B["bank"]["r"], B["pin"]["l"], "assoc", "", via=[(987, B["bank"]["r"][1]), (987, B["pin"]["l"][1])]),
    ln(B["atm"]["t"], B["obs"]["t"], "notify", "", via=[(490, 20), (1110, 20)]),
    '<text x="800" y="15" text-anchor="middle" font-size="10.5" fill="var(--acc2)">notifies, always after the unlock</text>',
    _tx(20, 958, "* JammingFeeder is the only box here that is not in Main.java: it is a test double, from Extensions.java", "var(--muted)", 10.5, "start"),
]
UMLSVG = uml_svg(1230, 972, edges, legend_y=932)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the machine owns the visit, the journal and the cassettes. Plain arrow = '
 'references. Dashed green = handed in and never built here. Dotted blue = notifies, and it leaves the ATM from the '
 'top to say what it means: the listeners are called after the lock is released. <b>Where state lives:</b> the '
 '<i>bank</i> has the balances, the applied-keys map and the wrong-PIN count per card, and it is the only writer of a '
 'balance; the <i>CashDispenser</i> has the note counts, the retract bin and its own lock; the <i>ATM</i> has one '
 'visit, one lock and an append-only journal, and it owns no money at all. The two enums on the left are the two life '
 'cycles &mdash; one for the visit, one for the money &mdash; and the Transitions box on the right is the table that '
 'says which move may follow which. BankReply and PinCheck, on the right, are the two kinds of answer the bank gives. Card and AtmEvent have no arrows because they are values: they are passed around and never '
 'changed. <b>What is here and what is not.</b> Every class in Main.java is on this page, so this is the whole list '
 'of what you type in the hour; the one exception is marked with an asterisk, because JammingFeeder is a test double '
 'from Extensions.java and is drawn only to show that the feeder really is a seam. Everything else in Extensions.java '
 '&mdash; DailyCap, RationBigNotes, GreedyOnly, MiniStatement, LowCashAlert, the Reconciler, the repository, the watchdog &mdash; '
 'is an answer to a follow-up on page 05, and every one of them plugs into a box that is already on this diagram '
 'without changing it.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it is for and what it guarantees; read only those first for the shape, then the '
 'bodies for the mechanics, and read <code>doWithdraw</code> last and slowly, because its order is the design. Each '
 'copy button copies that whole file. Below Main.java: Extensions.java (every follow-up\'s reference code, plus an '
 '<code>ExtDemo</code> main that runs them) and FailureTests.java (fifty-three claims proven across eighteen scenarios; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT +
 '</div>Before typing, write your six to eight clarifying questions; then type in the order of Main.java: the enums '
 '(Note largest first, the two life cycles, BankReply, PinCheck), Card and Session, the Withdrawal row with its key, '
 'the BankService interface with its compare-and-set implementation, NoteSelection with the backing-off picker, the '
 'CashDispenser with its own lock, the ATM with its lock and the reserve &rarr; debit &rarr; push order, and a main '
 'with the forty-machine race. If the hour runs short, the core that must be typed is the debit with its key, the '
 'reserve &rarr; debit &rarr; push order with its three failure branches, and the race; the listeners, the deposit '
 'and the Javadoc can be one line each, or said aloud. Some rounds hand you the interfaces and the model classes and '
 'ask only for the driver (Uber, 2025): that is the ATM class and its main, and the order inside '
 '<code>doWithdraw</code> is what gets graded.</div></div>')

FU = [
("Now cap withdrawals at 20,000 a day. Do it without touching the ATM.", "twist", 10,
 "The machine was never handed an <code>InMemoryBank</code>; it was handed a <code>BankService</code>. So the cap is a "
 "new class that implements the same interface, holds the real bank inside it, and counts what each account has taken "
 "today before delegating. Over the cap it returns DECLINED, which is a path the machine already knows: it puts every "
 "reserved note back and tells the customer. The check and the debit happen under that account's own lock, so two "
 "machines cannot both squeeze past the limit, and other accounts never wait. \"Today\" is the bank's local day, read "
 "from the injected clock in the bank's time zone: a UTC day would roll over at half past five in the morning in "
 "Mumbai. A reversal gives its amount back to the day, so a jam does not eat the customer's limit. Now the line that "
 "is easy to miss and that an interviewer will go looking for: <b>a decorator on a money path must not break "
 "idempotency</b>. If the same key arrives twice it is a retry of a withdrawal that already happened, not a new one, "
 "so it goes straight through to the bank, which answers with what it did the first time. Without that line the retry "
 "is measured against the cap again, comes back DECLINED, and the machine is told no about money that really left the "
 "account. Tests 10 and 17 prove the retry, the local midnight and the jam.",
 X("cap withdrawals", "a second note rule") + "\n" +
 T("        // 10. a decorator must not break", "        // 11. the watchdog") + "\n" +
 T("        // 17. the daily cap counts", "        // 18. the state-object")),
("Two terminals, one account, five hundred rupees left in it. Prove they cannot both get it.", "non-functional", 10,
 "The machine cannot fix this, because it does not own the balance and cannot lock a number in another process. The "
 "fix lives at the bank: <code>debit</code> reads the balance, refuses if it is too small, and only writes with a "
 "compare-and-set; if somebody else got in between the read and the write, the compare-and-set fails and the loop "
 "reads the fresh balance and decides again. The proof is the race in <code>main</code>: forty machines, one account "
 "with ten thousand, everybody asking for five hundred at one latch. Exactly twenty are paid, the balance lands on "
 "zero and never goes below it, and the cash that left the drawers equals the money that left the account. Say the "
 "general version out loud, because it is the point of the whole question: <b>reading a number and then acting on it "
 "is not a check</b>. <code>balance()</code> is a courtesy for the screen: it is already stale by the time the "
 "customer has read it. The only thing that decides whether there is enough money is the debit itself, which "
 "compares and subtracts in one step. That is why the code never asks the bank \"is there 500 in there?\" "
 "before asking it to take 500.",
 sect(src, "class InMemoryBank", "interface NoteSelection")),
("Every withdrawal takes the machine's lock, and holds it across a bank call. Is that a bottleneck?", "non-functional", 5,
 "It is held for about three seconds: about one for the bank round trip and two for pushing the notes out. That "
 "sounds alarming until you say what a machine is: one customer, standing in front of it, for about forty-five "
 "seconds. Eighty withdrawals a day is 240 seconds of lock in 86,400 &mdash; less than three tenths of one per cent "
 "&mdash; and there is never a second customer to block. The place where things really do arrive together is the "
 "bank, and nobody there waits for a lock: one compare-and-set per account. The one caller that does get blocked is "
 "not a customer at all but the watchdog, and that is rung 1 of the ladder: move the bank call and the push outside "
 "the machine's lock, so a card can be taken back while they run. Rung 2 is nothing, because the balances are already one atomic number per account; rung 3 is past "
 "one process, where the row becomes the lock: <code>UPDATE ... WHERE balance &gt;= ?</code>.",
 M("        // the race: forty machines", "        System.out.println(\"audit rows")),
("The notes jam after the bank has already debited. What is the state of the system, and show me the code.", "functional", 10,
 "The money has left the account and the customer has nothing, which is the only genuinely dangerous state in an ATM, "
 "so it is handled rather than hoped about. <code>push</code> throws a <code>HardwareFault</code>; the machine "
 "reverses the debit &mdash; the bank credits the amount back once, under the row's key plus \"-rev\" &mdash; marks "
 "the row REVERSED and reports it. If that credit-back cannot reach the bank either, the row is marked UNKNOWN "
 "instead of being left looking settled, and the reconciler reverses it later under the same key, so it can never be "
 "paid back twice (test 15). The reserved notes are <i>not</i> pretended back into the cassette &mdash; they are "
 "physically stuck, so they are counted into the retract bin, and the cash in the machine still adds up. The row "
 "stays in the journal forever, which is what the operator reads in the morning.",
 sect(src, "    Withdrawal withdraw(long amount) {", "    void ejectCard() {") + "\n" +
 T("        // 4. the dispenser jams", "        // 5. the bank never answers") + "\n" +
 T("        // 15. the notes jam AND", "        // 16. a deposit is")),
("The bank does not answer at all. The link is down. What do you do?", "functional", 10,
 "A timeout is not a no. Nobody knows whether the debit landed, so the machine dispenses nothing, puts the reserved "
 "notes back, and marks the row UNKNOWN rather than guessing; a bank call that throws is treated the same way (test "
 "14). Later a reconciler sends a <b>reversal</b> for that row's key. If the debit landed, the bank gives the money "
 "back once; if it never landed, the bank marks the key as dead, so the lost request cannot land if it turns up late. "
 "What the reconciler must never do is \"ask\" by debiting again: if the first debit never landed, that question takes "
 "the money now. The key is written into the journal row before the bank is asked, so the row always carries what the "
 "reversal needs. In India this is a rule, not a nicety: the RBI gives a bank five days after a failed withdrawal to "
 "put the money back, then &#8377;100 a day in compensation to the customer. <b>Reconciliation</b> means matching "
 "the machine's journal against the bank's ledger (its own record of every debit and credit). Neither is edited to "
 "match the other: settling a row adds a new fact, a reversal, and never rewrites an old one.",
 X("reconciling the rows", "the same life cycle") + "\n" +
 sect(src, "    public boolean reverse(String accountId", "    private BankReply cas(") + "\n" +
 T("        // 5. the bank never answers", "        // 6. note selection is exact") + "\n" +
 T("        // 14. the link dies", "        // 15. the notes jam AND")),
("Three wrong PINs. And what if the thief takes the card out after two and puts it back?", "functional", 5,
 "The count lives at the bank, per card, not on the visit. If the visit counted, a thief could take the card out after "
 "two wrong tries and put it back for three fresh ones, as often as he liked. So <code>authenticate</code> answers OK, "
 "WRONG or BLOCKED, and the bank keeps the count in one atomic step per card: <code>compute</code> on a concurrent map "
 "runs one caller at a time for the same key. A right PIN resets the count; a blocked card is refused even with the "
 "right PIN, on every machine. On BLOCKED the machine moves the visit to EJECTED and then IDLE without giving the card "
 "back: it is in the capture bin. Everything after that is refused by the state check, which names the state it "
 "happened in. Test 13 takes the card out after two wrong PINs, puts it back, and proves the third wrong one still "
 "keeps it.",
 sect(src, "    void enterPin(String pin) {", "    long balance() {") + "\n" +
 sect(src, "    public PinCheck authenticate(", "    public long balance(String accountId)") + "\n" +
 T("        // 13. wrong PINs are counted", "        // 14. the link dies")),
("Someone asks for 600 and the drawer has one 500 and three 200s. What happens?", "twist", 10,
 "Pure greed takes the 500, is left needing 100, has no 100s, and refuses a withdrawal the machine could actually "
 "pay. So the picker tries the greediest count of each denomination first and then steps down: zero 500s, three 200s, "
 "exactly 600. It walks the denominations largest first, which is the enum's own declaration order, so on 2000 / 500 "
 "/ 200 / 100 the first answer it finds is also the fewest-note one. Being exhaustive, it finds a combination "
 "whenever one exists, and it refuses rather than approximating when none does. The search stays small: each count "
 "is capped by the cassette and by the amount, and an amount bigger than the whole drawer is refused before "
 "searching, so even a bad drawer is a few thousand steps: microseconds. Know the opposite variant too: <b>LeetCode "
 "2241</b> (Design an ATM Machine) specifies pure greed, largest first and never step back, so there the same 600 "
 "must be refused. If that is the prompt, it is the spec: one more <code>NoteSelection</code>, "
 "<code>GreedyOnly</code>, and nothing else moves. The honest caveat: on a denomination set where greed-first is not "
 "optimal, the first answer stops being the fewest, and the body becomes a bounded coin-change table. Same interface, "
 "same callers.",
 sect(src, "class FewestNotes", "interface NoteFeeder") + "\n" +
 X("LeetCode 2241", "reconciling the rows") + "\n" +
 T("        // 6. note selection is exact", "        // 7. a receipt printer")),
("The monitoring system asks \"how many 500s are left?\" a thousand times a second.", "non-functional", 3,
 "No new structure. The cassette is an <code>EnumMap</code> from note to count, which is an array indexed by the "
 "note's position in the enum, so a count is an array read and the whole drawer is four entries. The read takes the "
 "dispenser's lock so it never sees a withdrawal half-done, and that costs tens of nanoseconds. "
 "The same is true of the total cash in the machine: four multiplications, not a walk over anything.",
 sect(src, "class CashDispenser", "interface WithdrawalPolicy")),
("The customer types a PIN and walks away. Who takes the card back, and what stops that thread cutting into a withdrawal?", "twist", 10,
 "A watchdog thread, armed when the card goes in and restarted by every customer action, calls "
 "<code>atm.ejectCard()</code> after a quiet period. The whole answer is in what <code>ejectCard</code> does: it "
 "takes the machine's own lock, the same lock a withdrawal holds. So if a withdrawal is in flight the watchdog "
 "<i>waits</i> for it and ejects afterwards; it can never take the card back in the gap between the debit and the "
 "notes, which is the one moment when doing so would cost the customer real money. The price is that the watchdog can "
 "be stuck for the bank round trip and the push, about three seconds (longer when the bank is slow), which is the "
 "whole reason rung 1 of the ladder in move 8 exists. "
 "Two details matter. <code>touch()</code> is synchronized but the firing method is not, so restarting the "
 "countdown never blocks behind a withdrawal. And notes a customer never picks up would go where jammed notes go: "
 "into the retract bin, never back into a cassette. Test 11 sets the bank to take 400 ms and the watchdog to "
 "50 ms, and proves the withdrawal still finishes whole and the card comes out only afterwards.",
 X("the customer walked away", "Runs every extension") + "\n" +
 T("        // 11. the watchdog", "        // 12. the drawer runs low")),
("Add a mini-statement, and page the operator when the drawer is running dry. How much of the ATM changes?", "twist", 5,
 "Nothing changes. Both are listeners: they implement <code>AtmObserver</code>, they are added with "
 "<code>addObserver</code>, and the machine announces what happened without knowing that either exists. The "
 "mini-statement keeps the last few money events per account, newest first, and drops the oldest past its limit. "
 "The low-cash alert is handed the "
 "dispenser it is watching and a floor, and it reads <code>dispenser.cash()</code> when an event arrives. It pages on "
 "the <i>crossing</i>, not on every event, so an empty drawer is one page rather than a page per withdrawal, and a "
 "refill that lifts the cash back over the floor arms it again. Both run after the lock is released, inside a "
 "try/catch, so a slow or broken listener cannot delay or break a withdrawal. The receipt printer lives by the same "
 "rule, which is why a fraud feed next week will not reopen the money path. Test 12 is the alert's claim: nothing above the floor, one page on the crossing, nothing again "
 "after that.",
 X("mini-statement", "a deposit the machine cannot count")),
("Add deposits. The machine cannot count what is in the envelope.", "twist", 5,
 "<code>ATM.deposit</code> in Main.java is the machine that can count: its note reader counts the notes, and the bank "
 "credits exactly what was counted, under the deposit's own key. The customer never types an amount, because a "
 "machine that credits a typed amount pays out for an empty tray; a negative count or an empty tray is refused (test "
 "16). An envelope is the machine that cannot count. The customer types an amount and posts it, and the balance does "
 "<i>not</i> move, because the machine has no idea what is inside. The envelope gets its own small life cycle: "
 "ACCEPTED when it goes into the bin, then VERIFIED or REJECTED when a human counts it the next morning, and the "
 "credit happens then, for what was actually in it rather than what was typed. The credit carries the envelope's own "
 "key, so a morning job that is run twice pays once.",
 sect(src, "    long deposit(EnumMap", "    Withdrawal withdraw(long amount) {") + "\n" +
 X("a deposit the machine cannot count", "state that must outlive")),
("Persist it. The machine reboots in the middle of a withdrawal.", "twist", 5,
 "The journal moves behind a repository interface, and the in-memory map is one implementation. The interesting method "
 "is <code>claim</code>: it must refuse a key that already exists, which is what makes a restart safe &mdash; on boot "
 "the machine reads its own unresolved rows and reconciles them before it lets anybody in. The counter inside the key "
 "must come from the store as well: a counter that starts again at 1 after a reboot would reuse old keys, and the "
 "bank would answer a new withdrawal with an old OK. In SQL the two steps are "
 "an <code>INSERT</code> on the key, where a duplicate-key error means \"this attempt already exists\", and "
 "<code>UPDATE account SET balance = balance - ? WHERE id = ? AND balance &gt;= ?</code>, where one row updated means "
 "paid and zero rows means declined. That is the database doing exactly what the compare-and-set did.",
 X("state that must outlive", "the customer walked away")),
("Where does time come from, and how do you test a daily cap on a Tuesday?", "design", 5,
 "The machine has a <code>Clock</code> it was handed &mdash; one method, <code>nowMs()</code> &mdash; and it stamps "
 "the journal rows and is read by any rule that cares what day it is. Nothing calls "
 "<code>System.currentTimeMillis()</code> in the middle of a flow. A test hands in a lambda that returns a fixed "
 "millisecond, so \"today\" is whatever the test says, and the daily cap can be pushed over its limit and then rolled "
 "into tomorrow without anybody waiting. \"Today\" also needs a time zone: the cap's day is the bank's local day, so "
 "it is handed a <code>ZoneId</code> too (test 17). The failure tests use exactly that, together with a bank that "
 "times out on demand and a feeder that jams once.",
 "// one method, so a test is a lambda\ninterface Clock { long nowMs(); }\n\n// production wiring\nATM atm = new ATM(\"ATM-01\", bank, dispenser);   // clock defaults to System::currentTimeMillis\n\n// a test decides what \"today\" is\nstatic final Clock CLOCK = () -> 1_757_000_000_000L;\natm.setClock(CLOCK);\nDailyCap capped = new DailyCap(core, 20_000, CLOCK, ZoneId.of(\"Asia/Kolkata\"));   // the same clock, in the bank's time zone\n"),
("A table of allowed moves, or one class per state? Which did you use and why?", "design", 5,
 "The machine here uses a table: an <code>EnumMap</code> from a state to the states it may move to, checked on every "
 "transition, which makes an illegal action a lookup rather than a wall of if-statements and keeps the whole life "
 "cycle visible in six lines. The alternative is one class per situation with every action defaulting to \"illegal in "
 "this state\", so a concrete state writes only the moves it allows and everything else is refused by construction. "
 "Same guarantee. The table wins while the states differ only in which moves they allow; the objects win the moment a "
 "state carries real work of its own, because then the table's <code>switch</code> comes back. Extensions.java has "
 "both, so you can show either.",
 X("the same life cycle", "mini-statement")),
("Which pattern is where, which SOLID letter is where, and where would a Factory earn its place?", "design", 5,
 "Strategy: the note rule and the amount rule, because those are what the interviewer changes. Decorator: the daily "
 "cap, which wraps the bank rather than a rule. Observer: the receipt, the audit log and the low-cash alert, all "
 "called after the unlock. State: the table of allowed moves. Command: the withdrawal row carries its own amount, "
 "notes and key, so the reversal is that row with the sign flipped. Chain of Responsibility is the famous ATM answer "
 "and it is deliberately not here: one handler per denomination is four more classes, and the textbook chain is pure "
 "greed, which refuses the 600 in question 7. It earns its links only when a link carries a policy of its own. For "
 "SOLID, one letter is worth more than the recital: D. The machine is handed its bank and its clock as interfaces, and "
 "that is the only reason the tests can give it a bank that times out, a feeder that jams and a Tuesday that never "
 "ends. A Factory earns its place the day "
 "denominations arrive from configuration rather than from an enum.",
 "// Strategy: the rules that change, each behind one method, handed in\ninterface NoteSelection    { EnumMap<Note, Integer> select(EnumMap<Note, Integer> stock, long amount); }\ninterface WithdrawalPolicy { String refuse(String accountId, long amount, long nowMs); }\nvoid configure(WithdrawalPolicy policy, NoteSelection selection) { this.policy = policy; dispenser.setSelection(selection); }\n\n// Decorator: wrap the collaborator, not the rule\nclass DailyCap implements BankService { private final BankService base; /* ... base.debit(...) under the cap */ }\n\n// Observer: the machine announces; it does not know what a printer is\nprivate void publish(AtmEvent e) { for (AtmObserver o : observers) { try { o.onEvent(e); } catch (RuntimeException ignored) { } } }\n\n// State: the life cycle as a table; an illegal move is a lookup that fails\nstatic final Map<SessionState, Set<SessionState>> ALLOWED = new EnumMap<>(Map.of(/* ... */));\n\n// Factory: only once notes stop being an enum\nMap<String, Note> fromConfig = Map.of(\"2000\", Note.N2000, \"500\", Note.N500);   // one registration per denomination\n"),
]

# ============================================================ build
build(dict(
    slug="atm",
    title="ATM",
    subtitle="LLD &middot; Java &middot; OpenJDK 21 &middot; 18 failure scenarios, 53 checks, a 40-machine race &middot; reserve, debit, push",
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
