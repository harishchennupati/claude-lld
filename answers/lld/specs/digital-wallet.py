# Digital Wallet LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"digital-wallet/Main.java").read_text()
ext   = (H/"digital-wallet/Extensions.java").read_text()
tests = (H/"digital-wallet/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def S(a, b):
    """slice Main.java between two exact anchors"""
    return src[src.index(a):src.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("pay",       24, [("a request with a key", "who pays whom, how much"),
                           ("claim the key, once", "a retry never pays twice"),
                           ("lock every account, by id", "sender, receiver, fee"),
                           ("append the legs, then balances", "all of it, or none of it")]),
        ("top up",   146, [("money in from the bank rail", "or back out to it"),
                           ("the same posting", "the bank account is the other side"),
                           ("same locks, same key", "not a new verb"),
                           ("the books still sum to zero", "every paise came from somewhere")]),
        ("undo",     218, [("the payment was a mistake", "a shop that never served"),
                           ("the opposite posting", "nothing is ever edited"),
                           ("same locks, same key", "the amount and the fee come back"),
                           ("the original is REVERSED", "both lines stay in the journal")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M815 78 V90", dash=True) + _bx(660, 90, 310, 38, "refused: nothing is written", "", dash=True)
pf += _tx(88, 306, "read", "var(--acc)", 13) + _tx(175, 306, "at any moment, without folding the journal: what is my balance?  what did transaction T do?  my last ten lines?", "var(--text)", 12, "start")
pf += _tx(615, 344, "many people pay at the same instant, and Ann pays Ben while Ben pays Ann: no balance goes negative, the total never changes, nothing deadlocks", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 358, pf)

# one afternoon, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("13:02  Ann tops up 1,000.00", ["bank -1,000.00, ann +1,000.00", "two legs, signed sum exactly zero",
                                       "the float we now hold is 1,000.00"], True),
      ("13:14  Ann pays the chai stall", ["120.00 to the shop, 2.00 to the house", "three legs: ann is debited 122.00",
                                          "the posting still sums to zero"], False),
      ("13:14  the phone retries it", ["the same idempotency key arrives again", "putIfAbsent loses: the first txn wins",
                                       "no second line, no second 122.00"], True),
      ("13:40  9,000.00 she does not have", ["refused before a line is appended", "Ben pays her at once: both lock by id",
                                             "no balance moved, no deadlock"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 270, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Open accounts for people, for merchants, and for the house (the bank rail, the fee account).</li>
<li>Top up from a bank rail and withdraw back to it.</li>
<li>Send money to another person or to a merchant, with a fee the product can change.</li>
<li>Every write carries an idempotency key: a retry returns the first outcome, it does not move money again.</li>
<li>A double-entry journal: every movement is written as entries whose signed sum is exactly zero.</li>
<li>Undo a completed payment by writing the opposite posting; never edit an entry.</li>
<li>Read a balance, a statement, and what one transaction did.</li>
<li>Freeze, unfreeze and close an account.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many callers at once: no balance may go negative and no posting may be half-written.</li>
<li>Ann pays Ben while Ben pays Ann: that must not deadlock.</li>
<li>Money is exact: integer paise, never a double, never a lost paise.</li>
<li>Balance and "what did this transaction do" are O(1); a statement is O(n) in the lines asked for.</li>
<li>Fees, limits and fraud checks swappable without touching the money path.</li>
<li>One source of truth: the journal. The balance is a cache the journal can prove and re-derive.</li>
<li>Nothing half-done: a refused transfer leaves every balance and the journal exactly as they were.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design a digital wallet. People keep a balance with us, top it up from their bank, send money to each '
          'other and pay merchants, and every payment has to be auditable and safe to retry. I want working code, '
          'not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>People keep money with us. It arrives from a bank, it '
 'moves between people and to merchants, and it leaves again. Every movement has to be written down in a way that '
 'answers "why is this account forty rupees short" a year later, so a movement is not two numbers being edited: it '
 'is a pair of journal lines, money out of one account and into another, whose signed sum is exactly zero. The '
 'phone that asked for the payment is on a train, so the same request will arrive two or three times, and it must '
 'move the money once. Two people will pay each other at the same instant. The one thing that must always be true '
 'is that no balance goes negative and the total in the system never changes on its own: every paise in somebody\'s '
 'wallet is a paise out of the account it came from.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that tops up, pays, retries, refuses, reverses and then runs a race. The interviewer is '
 'watching for, in this order: the questions you ask before typing (how money is represented, and whether every '
 'write has an idempotency key, are the first two); which classes exist and which one owns the balance; a transfer '
 'end to end; what happens when two threads move money between the same two accounts in opposite directions; where '
 'the rules that will change (the fee, the daily cap, the fraud check) live, so a new one is a new class and not an '
 'edit; what the wallet looks like when a step in the middle fails. Then the twists: a card top-up that times out, '
 'holds, multi-currency, persistence, settlement.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>How is money represented?</td><td>Integer paise, one currency in v1</td><td><code>long</code>, never <code>double</code>; FX becomes a follow-up, not a patch (moves 1, 12)</td></tr>'
 '<tr><td>A real ledger, or just a balance field on each account?</td><td>A ledger; balances are a cache of it</td><td>Double-entry entries, and a reconcile job that proves the cache (moves 1, 5)</td></tr>'
 '<tr><td>Does every write carry an idempotency key?</td><td>Yes, the client sends one</td><td>One <code>putIfAbsent</code> claims it; a retry can never pay twice (moves 5, 6)</td></tr>'
 '<tr><td>Closed loop, or a pass-through to bank rails?</td><td>Closed loop, with a bank settlement account as the ramp</td><td>Top-up and withdrawal are ordinary transfers, not new code (move 2)</td></tr>'
 '<tr><td>Can two people move money between the same accounts at once, in both directions?</td><td>Yes</td><td>A lock per account, taken in id order (moves 4, 7)</td></tr>'
 '<tr><td>Fees, daily limits, fraud checks &mdash; and will they change?</td><td>A merchant fee, a daily cap, a velocity check; all will change</td><td>Each behind a one-method interface, handed in (move 3)</td></tr>'
 '<tr><td>Can a payment be undone?</td><td>Yes, by an opposite posting; nothing is ever edited</td><td>REVERSED as a state, not an UPDATE on a row (move 6)</td></tr>'
 '<tr><td>One process and in memory, or a database and many servers?</td><td>One process, in memory</td><td>No repository yet; a follow-up adds one (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One afternoon, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> money is integer paise and never a double; every write carries an '
 'idempotency key and the key is claimed with one <code>putIfAbsent</code>; the journal is the source of truth and '
 'a balance is a cache the journal can prove; the lock lives on the account, and a transfer takes every account it '
 'touches sorted by id, which is why Ann-pays-Ben and Ben-pays-Ann cannot deadlock; the outside world is modelled '
 'as accounts too, so no money appears from nowhere. Named as out of scope: multi-currency and FX, holds, '
 'persistence, settlement with a bank &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a USER sends MONEY between ACCOUNTS; every movement is a pair of LEDGER ENTRIES; one TRANSFER is one TRANSACTION with an IDEMPOTENCY KEY", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 175, "Account", "balance, status, lock", 1), (225, 165, "Ledger", "the journal + an index", 1),
                          (410, 190, "LedgerEntry", "immutable: one line", 1), (620, 185, "Transaction", "one request, its outcome", 1),
                          (825, 175, "Money", "no state: two helpers", 0), (1020, 180, "Rules, fees, listeners", "no state: interfaces", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a value, an interface, or a number the journal can prove", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("hold the money", "Account  (balance, status, its own lock)", "account.applyDelta(-paise)"),
                                       ("record the movement", "Ledger  (the journal and its index)", "ledger.post(legs)"),
                                       ("move money, end to end", "WalletService  (it can see all three)", "wallet.transfer(key, a, b, paise)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 213, "a verb whose state is spread over two classes goes to the class that can see both: that class becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 232, "and top-up, withdrawal and reversal are not new verbs: the same posting, a different counterparty or the opposite sign", "var(--muted)", 11)
MV[2] = _mv(1230, 245, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 60, 220, 90, "WalletService", "configure(rules, feePolicy)", acc=True)
for k, (t, sub, impl) in enumerate([("FeePolicy", "free, flat per merchant, 0.5% capped", "NoFee / MerchantFlatFee / CappedPercentFee"),
                                    ("TransferRule", "daily cap, velocity, currency, sanctions", "DailyLimitRule / VelocityRule / SameCurrencyRule"),
                                    ("TxnListener", "receipt, fraud desk, cashback, analytics", "ReceiptPrinter / FraudMonitor / Cashback")]):
    y = 24 + k*60
    m3 += _ar("M250 105 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 212, "dashed green = handed in. The wallet never builds a rule, so a new fee or a new limit is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 232, "and notice what is NOT a rule: \"he must have the money\", \"the account must be ACTIVE\", \"the legs must sum to zero\".", "var(--acc)", 11)
m3 += _tx(615, 251, "those are invariants, not policy: they are never handed in and can never be switched off", "var(--acc)", 11)
MV[3] = _mv(1230, 264, m3)

# move 4: the gap, one lock per account, and the ORDER the locks are taken in
m4 = _D + _bx(30, 30, 190, 44, "Ravi's phone", "reads ann = 600.00") + _bx(30, 110, 190, 44, "the shop's till", "reads ann = 600.00")
m4 += _bx(350, 70, 190, 44, "ann's balance", "600.00", acc=True)
m4 += _ar("M220 52 H350 V70") + _ar("M220 132 H350 V114") + _tx(285, 40, "read", "var(--muted)", 10.5) + _tx(285, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="20" width="290" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(725, 45, "the gap", RED, 12) + _tx(725, 70, "both see 600, both pay 500", RED, 11) + _tx(725, 90, "the balance ends at minus 400", RED, 11)
m4 += _tx(725, 130, "fix: check and debit as ONE step", "var(--text)", 11)
m4 += _card(900, 26, 300, 132, "the lock lives on the ACCOUNT",
            ["not on the wallet, so two unrelated", "payments never wait for each other", "",
             "and the ledger's own monitor is always", "taken after them, never before"], acc=True)
m4 += _tx(615, 188, "but one lock per account means a transfer takes TWO, and two locks is where deadlocks live", "var(--text)", 12)
m4 += _card(20, 200, 580, 110, "lock the sender, then the receiver",
            ["Ann pays Ben: lock ann, then wait for ben", "Ben pays Ann: lock ben, then wait for ann",
             "each holds what the other needs: forever"], dash=True, tcol=RED)
m4 += _card(630, 200, 580, 110, "lock every account SORTED BY ID",
            ["Ann pays Ben: lock ann, then ben", "Ben pays Ann: lock ann, then ben",
             "one order for everybody, so there is no cycle"], acc=True)
MV[4] = _mv(1230, 325, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what does this account hold?", "a long on the Account (a cache of the fold)", "O(1)"),
                                      ("have I seen this request before?", "Map&lt;idemKey, Transaction&gt; + putIfAbsent", "O(1)"),
                                      ("what did transaction T do?", "Map&lt;txnId, Transaction&gt;", "O(1)"),
                                      ("my last ten lines?", "Map&lt;accountId, List&lt;LedgerEntry&gt;&gt;", "O(n) lines"),
                                      ("which account do I lock?", "Map&lt;accountId, Account&gt;", "O(1)"),
                                      ("is that balance honest?", "fold this account's entries", "a job, not a request")]):
    y = 16 + k*45
    m5 += _bx(30, y, 360, 40, q, "the question") + _ar("M390 %s H450" % (y+20), True)
    m5 += _bx(450, y, 520, 40, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+20), True) + _bx(1030, y, 170, 40, cost, "")
m5 += _tx(615, 300, "the journal is the truth and the balance is a cache of it: the cache answers in O(1), and reconcile() is what makes it safe to trust", "var(--muted)", 11)
MV[5] = _mv(1230, 315, m5)

# move 6: two state machines and the ORDER at the critical step
m6 = _D + _tx(300, 18, "a transaction's life", "var(--text)", 12)
m6 += _bx(30, 26, 150, 42, "PENDING", "the key is claimed", acc=True)
m6 += _bx(230, 26, 150, 42, "COMPLETED", "both legs written") + _bx(430, 26, 150, 42, "REVERSED", "an opposite posting")
m6 += _bx(230, 106, 150, 42, "FAILED", "nothing was written")
m6 += _ar("M180 47 H230", True) + _ar("M380 47 H430", True) + _ar("M105 68 V127 H230", True, True)
m6 += _tx(300, 180, "an account's life", "var(--text)", 12)
m6 += _bx(30, 190, 150, 42, "ACTIVE", "sends, receives", acc=True) + _bx(230, 190, 150, 42, "FROZEN", "neither way")
m6 += _bx(430, 190, 150, 42, "CLOSED", "only at zero")
m6 += _ar("M180 203 H230") + _ar("M230 222 H180") + _ar("M380 211 H430", True)
m6 += _tx(300, 262, "an illegal move throws; it cannot happen quietly", "var(--muted)", 11)
m6 += '<rect x="620" y="20" width="590" height="270" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m6 += _tx(915, 44, "the order at a transfer, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  claim the idempotency key: ONE putIfAbsent decides it",
                       "2  compute the fee -- pure, no lock held, and it may throw",
                       "3  lock every account the posting touches, sorted by id",
                       "4  check statuses, run the rules, check the balance",
                       "5  append both legs to the journal -- the irreversible write",
                       "6  only then move the cached balances and mark COMPLETED",
                       "7  unlock, then tell the listeners inside a try/catch",
                       "a refusal at step 4 leaves the journal and every balance untouched;",
                       "a crash between 5 and 6 loses nothing: the journal is the truth, and",
                       "rebuildFromJournal() folds it again to repair the cached balance"]):
    m6 += _tx(636, 70 + k*22, l, "var(--muted)" if k > 6 else "var(--text)", 11, "start")
MV[6] = _mv(1230, 305, m6)

# move 7: what is inside the lock, and ten people at the same instant
m7 = _D + _card(30, 20, 540, 150, "inside the locks: about 2 microseconds",
                ["two status checks and the rule checks", "compare the balance against amount + fee",
                 "build two or three entries and append them", "write two or three balance fields",
                 "about twenty operations in all"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside the locks: milliseconds to seconds",
            ["the fee arithmetic: done before the locks are taken", "the receipt or push: about 50 ms, after the unlock",
             "the database write: about 5 ms (a follow-up)", "the person typing the amount: seconds"])
m7 += _tx(615, 200, "ten people pay the same chai stall at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "phone %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%d" % (k*2)), acc=(k == 9))
m7 += _tx(615, 283, "the tenth phone waits eighteen microseconds for the shop's lock and then fifty milliseconds for its own receipt;", "var(--muted)", 11)
m7 += _tx(615, 301, "and two payments that share no account never wait for each other at all, which is most of them", "var(--muted)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per account: where would it bite? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["an account's lock is held about 2 us per posting",
                       "so ONE account can serve about 500,000 postings a second",
                       "a person: twenty payments a day. contention: none, ever",
                       "a busy chai stall on a festival day: 500 a second = 0.1% busy",
                       "the two hot spots are the HOUSE account (every top-up locks it)",
                       "and the JOURNAL's one monitor (every posting, about 1 us each)"]):
    m8 += _tx(35, 62 + k*23, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 listeners and persistence outside the locks", "already done: the receipt goes out after the unlock"),
                              ("2 shard the two hot spots: the house account and the journal", "bank#0 .. bank#15 by a hash of the user; one journal per shard"),
                              ("3 a row per account in the database", "UPDATE account SET balance = balance + ? WHERE id = ?, the key UNIQUE")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two threads spend the same balance", "check and debit inside one lock; test 1: 50 threads both ways, the total is conserved"),
                                ("Ann pays Ben while Ben pays Ann", "lock every account sorted by id; test 1 finishes at all -- a deadlock would time out"),
                                ("the phone retries on a bad network", "putIfAbsent on the key; test 3: the same txn comes back, and one journal line, not two"),
                                ("no money, frozen, or over the cap", "refuse before the append; tests 2, 4, 5: no balance moved and no journal line"),
                                ("the payment was a mistake", "an opposite posting, never an edit; test 6: the original entry is exactly what it was"),
                                ("the cached balance drifts", "reconcile() catches it, rebuildFromJournal() folds the journal again; tests 7 and 9"),
                                ("the card charge times out", "credit nothing, ask the gateway again later; test 10: the job cannot double-credit"),
                                ("the push gateway is down", "listeners after the unlock in a try/catch; test 8: a listener that throws changes nothing")]):
    y = 16 + k*40
    m9 += _bx(30, y, 300, 36, bad, "") + _ar("M330 %s H380" % (y+18), True) + _bx(380, y, 820, 36, fix, "", acc=True)
m9 += _tx(615, 348, "every claim this design makes has a failure test: FailureTests.java runs ten blocks and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 362, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface FeePolicy / interface TransferRule: one method each", None), ("a new fee or limit is a class, not an edit", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publish(t) after the unlock, inside a try/catch", None), ("the fraud desk hears; the money never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("PENDING &rarr; COMPLETED / FAILED &rarr; REVERSED, checked before every write", None), ("reversing twice is impossible", None)],
          [("Event log", "var(--text)"), ("move 5", None), ("the journal IS the log; a balance is fold(journal)", None), ("any balance can be re-derived and proved", None)],
          [("Guard, not Decorator", "var(--text)"), ("move 3", None), ("Ledger.post refuses legs whose signed sum is not zero", None), ("one gate every movement goes through", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the wallet is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh WalletService", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("the rules arrive as a List in configure(); that IS the registry", "var(--muted)"), ("it earns the name when rules come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("not yet", None), ("a transfer has four required arguments and nothing optional", "var(--muted)"), ("earns a place when a transfer grows optional fields", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Account: a balance. Ledger: movements. A rule: one policy. WalletService: the flow.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("CappedPercentFee is a new file plus one line in configure()", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("feePolicy.feeFor(...) and rule.check(...); never \"is this the merchant one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("FeePolicy, TransferRule, TxnListener, Clock: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("wallet.configure(rules, fee);  wallet.setClock(() -&gt; t);  wallet.addListener(...)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "a cap on new payees, a sanctions list", "a new class behind TransferRule plus one configure line", "", "move 3"),
        ("someone new wants to know", "cashback, analytics, the fraud desk", "one more listener; the money path does not change", "", "move 3"),
        ("a new step in a life", "authorise then capture; an UNKNOWN top-up", "one more state and one more checked transition", "", "move 6"),
        ("a new invariant across accounts", "FX: three legs, two currencies", "every account in the SAME sorted lock set: all of it or none", "", "move 4"),
        ("state that must outlive the process", "persist it; two servers", "the account row behind a repository; the write becomes", "UPDATE account SET balance = ?, version = version + 1 WHERE id = ? AND version = ?", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the Account, the Ledger and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>user</b> sends <b>money</b> between <b>accounts</b>; every movement is written "
 "as <b>ledger entries</b>; one <b>transfer</b> is one <b>transaction</b> carrying an <b>idempotency key</b>; "
 "<b>rules</b> can refuse it and <b>listeners</b> are told about it. An account has a balance, a status and a lock, "
 "all of which change: a class. The ledger has a journal and an index, both of which grow: a class. A ledger entry "
 "never changes once written, which is the point of it: a record. A transaction has a status that moves and a "
 "reason it failed: a class. Money has no state at all &mdash; it is a <code>long</code> of paise plus two helpers "
 "at the edges &mdash; so it is not a thing to instantiate, and a <code>double</code> here is the single fastest way "
 "to fail this interview. And the balance is not a class either: it is a number cached on the account that the "
 "journal can prove at any time.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Hold the money\" touches a balance, a status and a lock, and all three live on one account, so it is "
 "<code>account.applyDelta(-paise)</code> and <code>account.canCover(paise)</code>. \"Record the movement\" touches "
 "the journal and its per-account index, so it is <code>ledger.post(legs)</code>. \"Move money end to end\" touches "
 "two accounts, the journal and the idempotency map at once, and only the wallet can see all of them, so "
 "<code>wallet.transfer(key, from, to, paise)</code> is the orchestrator. Then notice what are <i>not</i> new verbs. "
 "A top-up is a transfer from the bank settlement account. A withdrawal is a transfer to it. A reversal is a "
 "transfer the other way with the same amounts. Because the outside world is modelled as accounts too, money never "
 "appears from nowhere, and one code path carries all four cases.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "What it costs to send money will change: free today, two rupees to merchants tomorrow, half a percent capped at a "
 "hundred on Friday afternoon. What is allowed will change: a daily cap, a velocity check, a sanctions list, a limit "
 "on brand-new payees. Who is told will change: a receipt today, a fraud desk and a cashback engine later. Each "
 "becomes a one-method interface the wallet is <i>given</i> in <code>configure()</code> and never builds &mdash; "
 "that is <b>Strategy</b> for the fee and the rules, and <b>Observer</b> for the listeners, born here rather than "
 "announced somewhere. The line worth saying out loud is the other one: an <i>invariant</i> is not a rule. \"He must "
 "have the money\", \"the account must be ACTIVE\", \"the legs must sum to zero\" are not handed in and cannot be "
 "switched off, because they are not negotiable. Confusing the two is how a wallet ends up with a configuration flag "
 "that allows negative balances.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock &mdash; and then an order.",
 "Ravi's phone and the shop's till both read Ann's balance as six hundred, both decide she can afford five hundred, "
 "and both debit: she ends at minus four hundred and the wallet has invented money. So the check and the debit must "
 "be one step, under a lock held by whoever owns the balance &mdash; the account, not the wallet, because Ann paying "
 "Ben must not block Carol paying Dan. But a transfer touches two accounts, and two locks is exactly where deadlocks "
 "live: if each thread locks the sender and then the receiver, Ann-pays-Ben and Ben-pays-Ann grab one each and wait "
 "for the other forever. The fix is one line and it is the whole answer: collect every account the posting touches "
 "&mdash; sender, receiver, and the fee account if there is a fee &mdash; sort them by id, and lock them in that "
 "order. One order for everybody means there is no cycle to wait in. There is a second lock hiding here and a good "
 "interviewer will find it: the ledger has a monitor of its own, because two postings must not interleave inside the "
 "journal. Two lock levels can deadlock as easily as two accounts, and the reason this pair cannot is that there is "
 "exactly one direction &mdash; accounts first, ledger second, never the other way round. Say \"two lock levels, one "
 "order\" out loud before you are asked.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What does this account hold?\" is a <code>long</code> on the account, so a balance screen never folds a year of "
 "history. \"Have I seen this request before?\" is a map from idempotency key to transaction, and the operation on "
 "it is <code>putIfAbsent</code>, which is a compare-and-set: the thread that puts the value in owns the payment and "
 "everyone else gets the existing one. \"What did transaction T do?\" is a map from transaction id. \"My last ten "
 "lines?\" is a per-account list of entries the ledger maintains as it appends, so a statement is O(n) in the lines "
 "you asked for and never a scan of the journal. The one to say deliberately: the journal is the truth and the "
 "balance is a cache of it. That is a choice with a cost &mdash; two writes per movement, and a job that folds the "
 "journal and compares &mdash; and it buys you an audit trail, refunds that are postings rather than guesses, and a "
 "balance you can prove.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A transaction is PENDING when its key is claimed, COMPLETED when both legs are in the journal, FAILED when a rule "
 "or an invariant refused it, REVERSED when a later opposite posting undid it; an account is ACTIVE, FROZEN or "
 "CLOSED, and closing one that still holds money is refused. Writing the states down forces the question that "
 "decides this interview, and the panel beside them is the answer: in what order do the steps happen? Two of those "
 "seven steps are the ones to defend. The key is claimed <i>first</i>, with one <code>putIfAbsent</code> and before "
 "a single account is locked, so a duplicate request never reaches the money at all. And the journal append is the "
 "irreversible write, so everything that can refuse &mdash; the statuses, the rules, the balance &mdash; runs "
 "before it, and the cached balances move only after it has succeeded. A refusal therefore leaves the journal and "
 "every balance exactly as they were. And a crash "
 "between the append and the balance write loses nothing either: the journal is the truth, "
 "<code>reconcile()</code> finds the account whose cached balance no longer matches it, and "
 "<code>rebuildFromJournal()</code> folds the entries again to repair it.", 6),
("Move 7: yes, the locks make one account's payments happen one at a time. Ask for how long, and what is inside them.",
 "The question you will be asked: if every payment takes two or three locks, is the wallet now a queue? It is, for "
 "about two microseconds, and only for the accounts involved. Inside the locks there are two status checks, the rule "
 "checks (a map read for the daily counter and a short walk down the tail of the account's entry list for the "
 "velocity check), one comparison of the balance against amount plus fee, two or three entry objects appended to the "
 "journal and its index, and two or three field writes: roughly twenty operations. Everything slow is outside. The "
 "fee arithmetic happens before the locks are taken, deliberately, because it is the part that can throw. The "
 "receipt, about fifty milliseconds, happens after the unlock inside a try/catch, so a dead push gateway cannot hold "
 "a lock. Ten people paying the same chai stall at the same instant: the tenth waits about eighteen microseconds.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "The picture has the arithmetic; here is what it means. No user's account ever contends with itself &mdash; twenty "
 "payments a day against a lock that could take five hundred thousand is not a queue. The two places that do "
 "contend are both shared: the house account, because every top-up in the system locks the one bank settlement "
 "account, and the journal, because <code>Ledger.post</code> is synchronised on the whole ledger so every posting "
 "passes through a single monitor. Those two, not a user's lock, are the wallet's ceiling: at around fifty thousand "
 "top-ups a second the bank account is ten per cent busy, and the journal's monitor tops out near a million "
 "postings a second. That is what the ladder fixes, cheapest rung first: listeners and persistence stay outside the "
 "locks, which this code already does; the house account splits into bank#0 to bank#15 by a hash of the user id "
 "(free, because a house account never needs a balance check) and the journal splits the same way, one per shard; "
 "and past one process each account becomes a database row whose write is <code>UPDATE account SET balance = "
 "balance + ?</code>, with the journal an INSERT into an append-only table where the monitor problem disappears "
 "entirely.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Two threads spending the same balance, and Ann paying Ben while Ben pays Ann: one locked step, every account in "
 "id order, and the test proves the second one by <i>finishing</i> &mdash; a deadlock shows up as a timeout, not as "
 "a wrong number. A phone retrying on a bad network. Three refusals that must all leave the wallet exactly as it "
 "was: not enough money, a frozen account, the daily cap (that one needs the injected clock). A payment that was a "
 "mistake. A cached balance that has drifted, which <code>reconcile()</code> catches and "
 "<code>rebuildFromJournal()</code> repairs. A card charge that times out. A dead push gateway. That is ten blocks "
 "in FailureTests.java, and the last two are what separates a wallet from a bank-account exercise: a design that "
 "cannot show its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; what is worth saying out loud is the bottom half of it. Decorator did not earn a place "
 "here, and people expect it to: there is nothing to wrap, because the invariant that every posting sums to zero "
 "already sits in one gate, <code>Ledger.post</code>, that every movement goes through. Singleton earned nothing "
 "either &mdash; the wallet is handed to its callers, which is exactly why a test can build a fresh one per case. "
 "Factory and Builder are \"not yet\" rather than \"never\": the list of rules handed to <code>configure()</code> is "
 "already the registry, so Factory earns the name the day rules arrive as strings from a config file, and Builder "
 "earns its place the day a transfer grows optional fields &mdash; a note, tags, a device id. A pattern without a "
 "move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "Read the table, then say the one sentence that matters: every letter here is something a move already did, not "
 "something added to satisfy a checklist. The one to point at under pressure is D. The wallet depends on interfaces "
 "and is handed the implementations, and that is not an ideal &mdash; it is the only reason a test can hand it a "
 "clock that says next Tuesday and prove the daily cap resets, or hand it a listener that throws and prove the "
 "money still moves.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The picture maps five shapes of twist onto five moves. What to add out loud is the trap inside each. The listener "
 "one: a cashback posting must not trigger another cashback, or the promo account drains one per cent at a time "
 "until the rounding stops it. The new-invariant one: a cross-currency payment must put every account it touches "
 "into the <i>same</i> sorted lock set, or you have re-invented the deadlock you designed out in move 4. The "
 "persistence one: the conditional UPDATE <i>is</i> the lock, so a caller that ignores its \"zero rows changed\" "
 "answer has quietly lost a payment. For all five the Account, the Ledger and the failure tests do not change, and "
 "that is the real test that the derivation was right. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD and the class diagram, the lock, the tests, the patterns, SOLID and the answer "
 "to every twist fall out in that order; nothing is chosen up front, and nothing is named before the move that produced "
 "it. On a wallet two of the moves carry more weight than usual: move 4, because a transfer needs two locks and two "
 "locks is where deadlocks live, and move 6, because the order of the steps is the difference between a refused "
 "payment and a wallet that has lost somebody's money.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the listeners, the injected clock, the value types
put("lst", 10, 20, 250, "TxnListener", [], ["onTxn(t)"], "interface")
put("impl", 10, 110, 250, "ReceiptPrinter | FraudMonitor", [], ["onTxn(t): a phone, a desk"])
put("clock", 10, 200, 250, "Clock", [], ["nowMs(): long"], "interface")
put("money", 10, 290, 250, "Money", [], ["rupees(\"120.50\"): long", "fmt(paise): String"])
put("entry", 10, 400, 250, "LedgerEntry",
    ["entryId / txnId: String", "accountId: String", "dir: Direction", "paise: long", "atMs: long,  memo: String"],
    ["signed(): long"])
put("dir", 10, 560, 250, "Direction", ["DEBIT, CREDIT"], [], "enum")
# centre column: the root and what it owns
put("wallet", 300, 20, 340, "WalletService",
    ["accounts: Map&lt;id, Account&gt;", "byKey: Map&lt;idemKey, Transaction&gt;", "byId: Map&lt;id, Transaction&gt;",
     "ledger: Ledger", "rules / feePolicy / clock", "listeners: List&lt;TxnListener&gt;"],
    ["configure(rules, feePolicy)", "open(id, type, currency)", "transfer(key, from, to, paise, memo)",
     "topUp(key, to, paise) / withdraw(...)", "reverse(key, txnId)", "balanceOf(id) / statement(id, n)",
     "txn(id) / byKey(key)", "reconcile() / rebuildFromJournal()"])
put("acct", 300, 310, 340, "Account",
    ["id: String", "type: AccountType", "currency: Currency", "balancePaise: long", "status: AccountStatus",
     "spentTodayPaise / dayNumber", "lock: ReentrantLock"],
    ["canCover(paise): boolean", "applyDelta(delta) / resetBalance(v)", "balance() / status()", "spentToday(nowMs) / addSpent(...)",
     "setStatus(s)"])
put("ledger", 300, 570, 340, "Ledger",
    ["journal: List&lt;LedgerEntry&gt;", "byAccount: Map&lt;id, List&lt;...&gt;&gt;", "nextId: AtomicLong"],
    ["post(legs) -- signed sum must be 0", "statement(id, n) / entriesFor(id)", "replay(id): long",
     "journal() / accountsSeen()"])
# third column: the transaction and the enums
put("txn", 670, 20, 255, "Transaction",
    ["id / idemKey: String", "fromId / toId: String", "amountPaise / feePaise: long", "status: TxnStatus",
     "failureReason: String", "entryIds: List&lt;String&gt;"],
    ["complete(ids) / fail(reason)", "markReversed(byTxnId)"])
put("tstat", 670, 220, 255, "TxnStatus", ["PENDING, COMPLETED,", "FAILED, REVERSED"], [], "enum")
put("astat", 670, 315, 255, "AccountStatus", ["ACTIVE, FROZEN, CLOSED"], [], "enum")
put("atype", 670, 395, 255, "AccountType", ["USER, MERCHANT,", "BANK_SETTLEMENT, FEE_REVENUE"], [], "enum")
put("ccy", 670, 490, 255, "Currency", ["INR, USD"], [], "enum")
put("rej", 670, 570, 255, "TransferRejected", [], ["a rule or an invariant said no"])
# fourth column: the rules that are handed in
put("fee", 950, 20, 265, "FeePolicy", [], ["feeFor(paise, from, to)"], "interface")
put("fees", 950, 100, 265, "NoFee | MerchantFlatFee", [], ["feeFor(...): 0 | a flat fee", "+ CappedPercentFee (Extensions)"])
put("rule", 950, 195, 265, "TransferRule", [], ["check(t, from, to, nowMs)", "  throws TransferRejected"], "interface")
put("r1", 950, 290, 265, "SameCurrencyRule", [], ["both sides, one currency"])
put("r2", 950, 365, 265, "DailyLimitRule", [], ["spentToday + amount &lt;= cap"])
put("r3", 950, 440, 265, "VelocityRule", ["ledger, maxDebits, windowMs"], ["n debits in the last 60s"])
put("inv", 950, 545, 265, "the invariants", ["not rules: never handed in"],
    ["balance &gt;= amount + fee", "status == ACTIVE", "the legs must sum to zero"])

def hstub(y, x1, x2):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y, x2, y)

EDGES = [
 # implementations
 ln(B["impl"]["t"], B["lst"]["b"], "inherit"),
 ln(B["fees"]["t"], B["fee"]["b"], "inherit"),
 ln((950, 477), (950, 230), "inherit", "", [(944, 477), (944, 230)]),
 hstub(317, 950, 944), hstub(392, 950, 944),
 # the wallet owns the accounts, the ledger and the transactions
 ln(B["wallet"]["b"], B["acct"]["t"], "compose", "id &rarr; account"),
 ln((300, 150), (300, 600), "compose", "", [(290, 150), (290, 600)]),
 ln(B["wallet"]["r"], B["txn"]["l"], "compose"),
 ln((300, 647), (260, 469), "compose", "", [(266, 647), (266, 469)]),
 # the entry points at its direction; the transaction and the account at their enums
 ln(B["entry"]["b"], B["dir"]["t"], "assoc"),
 ln(B["txn"]["b"], B["tstat"]["t"], "assoc"),
 ln((640, 380), (670, 340), "assoc", "", [(658, 380), (658, 340)]),
 ln((640, 430), (670, 428), "assoc"),
 ln((640, 480), (670, 515), "assoc", "", [(652, 480), (652, 515)]),
 # the rules and the fee policy are handed in through configure()
 ln((640, 200), (950, 47), "inject", "", [(934, 200), (934, 47)]),
 ln((640, 212), (950, 230), "inject", "", [(928, 212), (928, 230)]),
 _tx(1082, 690, "all handed in through configure()", "var(--acc)", 10.5),
 # the velocity rule reads the ledger's per-account index
 ln((950, 477), (640, 650), "assoc", "", [(916, 477), (916, 650)]),
 _tx(910, 668, "reads the per-account index", "var(--muted)", 10.5, "end"),
 # the callers and the injected pieces
 ln((300, 60), (260, 47), "notify", "", [(274, 60), (274, 47)]),
 ln((300, 90), (260, 227), "inject", "", [(282, 90), (282, 227)]),
]
UMLSVG = uml_svg(1230, 780, EDGES, legend_y=755)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the wallet owns the accounts, the ledger and every transaction; the ledger owns '
 'every entry. Plain arrow = references: an entry points at its direction, an account at its status, its type and its '
 'currency. Dashed green = handed in through <code>configure()</code> and <code>setClock()</code>. Dotted blue = '
 'notifies. <b>Where state lives:</b> the account has the balance, the status, today\'s spend and <i>the lock</i> '
 '&mdash; there is no lock on the wallet at all, which is why two unrelated payments never meet; the ledger has the '
 'journal, the per-account index and one monitor of its own, which is always taken after the account locks and '
 'never before; a transaction has its status and the ids of the lines it '
 'wrote; a rule and a fee policy have no state worth the name, so one instance serves every payment. Notice what is '
 '<i>not</i> here: no Balance class, because a balance is a <code>long</code> the journal can prove, and no TopUp or '
 'Withdrawal class, because both are transfers with a house account on the other side.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (ten blocks, one per claim on page 02; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (integer paise and an idempotency key on every write are '
 'the first two); then type in the order of Main.java: the five enums, the Money helpers, the LedgerEntry record, the '
 'Clock, the Ledger with its balanced post(), the Account with its balance and its own lock, TransferRejected and the '
 'Transaction, the FeePolicy and TransferRule interfaces with one implementation each, the listeners, then '
 'WalletService with sorted-by-id locking and the order at transfer(), then a main with fifty threads paying in both '
 'directions.</div></div>')

FU = [
("From today: half a percent on every transfer over ten thousand, capped at a hundred.", "functional", 8,
 "The fee is already an interface, so this is one new class and one line where the wallet is configured. It returns "
 "zero below the threshold, otherwise the amount times fifty basis points, and takes the smaller of that and the cap "
 "&mdash; all integer arithmetic on paise, so there is no rounding to argue about. Nothing in WalletService, Ledger, "
 "Account or Transaction moves. The one line worth pointing at is the first: the house does not charge itself, so a "
 "top-up from the bank settlement account is still free.",
 X("the mid-round pricing change", "top-up through a payment gateway")),
("Ann pays Ben while Ben pays Ann, fifty threads at once. Prove nothing is lost and nothing hangs.", "non-functional", 10,
 "Two different failures hide in that sentence and the test has to catch both. Money lost is caught by arithmetic: "
 "the balances of the two accounts are added up before and after, and if any check-then-debit had raced the total "
 "would have moved. A deadlock is caught by <i>time</i>: every future is collected with a five-second timeout, so a "
 "cycle of two threads each holding one lock shows up as a timeout rather than as a wrong number. The reason it does "
 "not happen is one line in the transfer: every account the posting touches is sorted by id before any lock is "
 "taken, so both directions take ann first, then ben. The test also re-runs reconcile, which folds the journal and "
 "compares it with every cached balance.",
 T("        // 1. fifty threads", "        // 2. not enough money")),
("One lock per account, two locks per transfer. Does that scale, or have you serialised the wallet?", "non-functional", 5,
 "It scales, and the answer is arithmetic rather than opinion. A lock is held about two microseconds, so one "
 "account could serve roughly half a million postings a second, and a person sends twenty payments a day; a user's "
 "own lock is never the problem. The locks everybody shares are the two to name before the interviewer does: the "
 "house account, which every top-up in the system locks, and the ledger's own monitor, because "
 "<code>post()</code> is synchronised on the whole journal so every posting in the wallet passes through it. Then "
 "give the ladder: listeners and persistence stay outside the locks, which this code already does; the house "
 "account and the journal both shard by a hash of the user id; and past one process each account becomes a row "
 "whose write is <code>UPDATE account SET balance = balance + ?</code> while the journal becomes an INSERT into an "
 "append-only table, which contends with nothing at all.",
 S("    /** Sorting by id is the whole deadlock story", "    private static void requireUsable")
 + "\n    " + sect(src, "    synchronized void post(", "    /** The last n entries")),
("The balance check passed and then a step failed. What is the state of the wallet?", "functional", 10,
 "Exactly what it was. Look at the order in transfer(): the fee is computed before any lock, because that is the "
 "part that can throw; under the locks come the status checks, the rules and the balance check, and all of them run "
 "before a single line is written; then the journal append, which is the irreversible write; and only then the "
 "cached balances and the COMPLETED mark. A refusal at any of the checks throws TransferRejected, the transaction is "
 "marked FAILED with its reason, and neither balance nor the journal moved &mdash; the failure test asserts both, "
 "including that the journal has not grown by a line. The honest edge case is a crash between the append and the "
 "balance write, and even that loses nothing: the journal is the truth, so <code>reconcile()</code> finds the "
 "account whose cached balance no longer matches it and <code>rebuildFromJournal()</code> folds the entries again "
 "to repair it &mdash; failure test 9 breaks a balance on purpose and watches both happen.",
 S("    /**\n     * Move money from one account to another.", "    /**\n     * Money in from the outside world")),
("The phone was on a train and retried the same payment three times.", "functional", 5,
 "It is paid once. The idempotency key is claimed with a single putIfAbsent before any account is locked: the thread "
 "that inserts its transaction owns the payment, every other caller gets the one already there. A retry of a "
 "completed payment returns the very same Transaction object, and the test checks that the receiver has exactly one "
 "journal line rather than two. A retry of a payment that was <i>refused</i> is refused again with the stored "
 "reason, which is the part people get wrong: a key names one attempt, not one intention, so a genuine second try "
 "needs a new key. That is also why the wallet takes the key as a parameter and never generates it. And if the "
 "duplicate arrives while the first attempt is still inside the locks, it gets that same Transaction while it is "
 "still PENDING, so the caller must read the status: PENDING means \"in progress, ask again\", which is a 202 over "
 "HTTP and not a receipt.",
 T("        // 3. a retried request", "        // 4. a frozen account")),
("That payment was a mistake. Undo it.", "twist", 8,
 "Nothing is edited and no balance is set by hand. A reversal is an ordinary posting that points the other way: the "
 "receiver is debited, the sender is credited the amount plus the fee he paid, the fee account gives the fee back, "
 "and the original transaction is marked REVERSED. Both the mistake and the correction stay in the journal, which is "
 "what makes the history worth keeping. Two things are checked first: only a COMPLETED transaction can be reversed, "
 "so calling it twice throws instead of paying the money back twice, and the receiver must still have the money "
 "&mdash; if he has spent it, the reversal is refused and this becomes a dispute, not a silent negative balance.",
 S("    /**\n     * Undo a completed transaction", "    /**\n     * The check that makes the cached balances")),
("How do you know the balances are right? Prove it.", "design", 5,
 "By folding the journal. <code>reconcile()</code> walks every account the journal has ever touched, adds up the "
 "signed value of its entries, compares that with the number the wallet serves, and then adds every balance "
 "together, which must come to exactly zero. It can be zero at all only because of the move on page 02: the outside "
 "world is modelled as accounts, so a top-up is not money appearing, it is the bank settlement account going "
 "negative by the float we now hold. Two guards keep that true &mdash; <code>Ledger.post</code> refuses any posting "
 "whose legs do not sum to zero, and a balance moves only through <code>applyDelta</code>, immediately after an "
 "append that succeeded. Finding a mismatch is half the job, so <code>rebuildFromJournal()</code> folds the entries "
 "again and overwrites the cache; the journal is the truth, which is what makes the cache disposable. The last "
 "thing to say is that <code>reconcile()</code> is a job and not a request: it takes each account's lock one at a "
 "time, so on a live wallet it can read account A after a transfer and account B before the same one and report a "
 "difference that is not real &mdash; run it when the wallet is quiet, or fold only up to a fixed journal position "
 "and compare against balances read at that same point.",
 S("    /**\n     * The check that makes the cached balances", "    /** Sorting by id is the whole deadlock story")),
("Top up from a card, and the gateway times out. Now what?", "twist", 10,
 "The order is everything: charge the card first, credit the wallet second. On SUCCESS the wallet is credited under "
 "the same key the gateway was given. On FAILED nothing happens. On UNKNOWN &mdash; which is the real answer to "
 "\"what if it times out\" &mdash; the money may or may not have left the bank, so the wallet is credited with "
 "nothing and the key is parked. A reconciliation job asks the gateway again later and finishes the job, and because "
 "the wallet's top-up is idempotent on that same key, the job can run as often as it likes without ever "
 "double-crediting. Crediting first and charging afterwards is how wallets give money away.",
 X("top-up through a payment gateway", "multi-currency")),
("Show me my balance and my last ten transactions, a thousand times a second.", "non-functional", 3,
 "No new structure. The balance is a long on the account, read under its lock, so it is one field read. The "
 "statement comes off the per-account index the ledger maintains as it appends, so the last ten lines are a sublist "
 "and cost ten, not the size of the journal. \"What did transaction T do?\" is a map lookup by id, and the "
 "transaction carries the ids of the lines it wrote. Nothing anywhere re-reads the journal to answer a request; the "
 "only thing that folds it is <code>reconcile()</code>, which is a job, not a screen. The one honest cost to admit: "
 "<code>statement()</code> is synchronised on the ledger, the same monitor the money path takes, and "
 "<code>List.copyOf</code> copies the slice before returning it, so a thousand statement reads a second really do "
 "contend with payments &mdash; at that volume the statement stops being a read of the write model and becomes its "
 "own read model, fed from the journal.",
 S("/**\n * The journal: every movement", "/**\n * Where money sits.")),
("Authorise five hundred at the pump, capture three hundred and eighty.", "twist", 8,
 "A hold moves no money: it is a promise, so the only new idea is available() = balance minus holds, and every rule "
 "that asks \"can he cover it\" asks available() rather than balance(). The capture releases the hold and then does "
 "an ordinary transfer, so the ledger never learns a new shape and the money path is untouched; a release with no "
 "capture is just a subtraction. In a system with real books the hold itself becomes a leg into a per-user holds "
 "account so the balance sheet still adds up, and the hold grows its own small state machine &mdash; which is move "
 "6's twist, a new step in a life.",
 X("holds", "cashback")),
("Ann keeps rupees and Dana keeps dollars. Ann pays Dana.", "twist", 8,
 "Never one posting in two currencies: legs in different currencies cannot sum to zero, so "
 "<code>Ledger.post</code> would refuse the whole thing, which is the guard doing exactly its job. It is two "
 "ordinary postings instead, each balanced inside one currency &mdash; Ann's rupees into the INR house account, "
 "Dana's dollars out of the USD house account &mdash; and each leg carries its own key derived from the caller's "
 "one key, so a retry is exactly-once on both. The rate is read once, at the moment of the transfer, and written "
 "into the memo of both legs, so nobody has to guess a year later what it was that afternoon. The two house "
 "accounts are then left holding a position, long rupees and short dollars, which the treasury desk squares in the "
 "real market: that is the honest answer to \"who carries the FX risk\". Say the weakness before you are asked "
 "&mdash; two postings are two atomic steps, so a crash between them leaves the rupee leg written and the dollar "
 "leg not; here the caller retries with the same keys and the second leg completes, while a real system gives the "
 "pair its own state machine with a pending leg that a job finishes.",
 X("multi-currency", "holds")),
("Marketing wants one per cent cashback on person-to-person payments, live tomorrow.", "twist", 5,
 "Nothing in <code>transfer()</code> changes: cashback is one more listener, handed in with "
 "<code>addListener</code>. It runs after the locks are released, which is what makes it safe for it to call the "
 "wallet again &mdash; a listener that moved money while the account locks were still held would re-enter a "
 "<code>ReentrantLock</code> it already owns, which succeeds quietly and stretches the critical section instead "
 "of failing loudly. The money comes out of a promo house account, so the books still sum to zero and "
 "marketing's spend is a balance anyone can read. The trap is the loop: a cashback payment is itself a completed "
 "transaction, so the listener hears its own posting; the guard is the memo check on the first line, and without "
 "it the promo account drains one per cent at a time until the rounding stops it. The second trap is already "
 "handled &mdash; <code>publish()</code> wraps every listener in a try/catch, so a cashback bug cannot fail a "
 "payment that has already been written.",
 X("cashback", "persistence")),
("Persist it. And now there are two servers.", "twist", 8,
 "The account's balance becomes a row behind a repository and the wallet's code does not change, only what it was "
 "handed. The read-modify-write that a lock protects today becomes a conditional UPDATE that names the version it "
 "read: it either changes one row or changes none, and changing none means somebody else got there first, so the "
 "caller re-reads and retries. The idempotency map becomes a unique index on the key with INSERT ... ON CONFLICT DO "
 "NOTHING, which is the same compare-and-set putIfAbsent does in memory. The journal is the easy part: it is "
 "append-only, so it is an INSERT with no contention at all.",
 X("persistence", "standing instructions")),
("Rent on the first of every month, and a nightly settlement sweep. The job crashes and re-runs. Prove it does not pay twice.", "twist", 5,
 "Neither one is new machinery; both are the idempotency key doing the work, which is the point. A standing "
 "instruction pays every period due by now, and its key is the instruction id plus the period number, so a "
 "second run &mdash; or a second server running the same job at the same time &mdash; pays each period exactly "
 "once and reports zero paid. The nightly settlement sweeps each merchant's balance out to the bank as an "
 "ordinary withdrawal, with the day in the key, so re-running the batch settles nothing again. Two things worth "
 "saying: a period that was <i>refused</i> keeps that refusal under its key, so retrying it needs an attempt "
 "number in the key, and whether to retry at all is a product decision rather than a technical one. And the "
 "sweep reads balances without holding anything across accounts, so a merchant paid while the batch is running "
 "is simply settled tomorrow &mdash; the journal, not the sweep, is the record.",
 X("standing instructions", "settlement") + "\n" + X("settlement", "the audit view")),
("Where does time come from, and how do you test a daily cap?", "design", 3,
 "The wallet has a Clock it was handed, and it stamps every entry and every transaction with it; nothing else in the "
 "system reads the wall clock. That is what makes the cap testable: the test hands in a clock returning a fixed "
 "instant, sends up to the cap, checks that the next paise is refused and that nothing moved, then adds a day to the "
 "instant and sends again. The same seam is what makes the velocity rule testable, and what makes a standing "
 "instruction a pure function of \"now\" rather than something that has to be waited for.",
 T("        // 5. the daily cap", "        // 6. a reversal")),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "None of them was chosen up front; each is what a move produced, and that is the whole answer. Strategy and "
 "Observer are move 3 &mdash; the fee and the rules are the things that change, so each is a one-method interface "
 "the wallet is handed, and listeners run after the unlock inside a try/catch so a dead push gateway cannot hold a "
 "lock. State is move 6, which is why reversing the same payment twice throws, and the journal is an event log in "
 "the small, so any balance is a fold and can be proved. Two absences are worth a sentence: Decorator, because the "
 "sum-to-zero invariant already has one gate in <code>Ledger.post</code> and there is nothing to wrap; and "
 "Singleton, because the wallet is handed to its callers, which is what lets every failure test build a fresh one. "
 "For SOLID, point at a line rather than a letter: <code>configure()</code> and <code>setClock()</code> are D, and "
 "they are the reason a test can prove the daily cap resets on Tuesday. Factory earns its name the day rules "
 "arrive as strings from a config file, and Builder the day a transfer grows optional fields &mdash; today it has "
 "four required arguments, so a builder would be ceremony.",
 "// Strategy: the rules that change, behind interfaces, handed in, never built by the wallet\n"
 "interface FeePolicy   { long feeFor(long amountPaise, Account from, Account to); }\n"
 "interface TransferRule { void check(Transaction t, Account from, Account to, long nowMs); }\n"
 "void configure(List<TransferRule> rules, FeePolicy feePolicy) { /* the wallet is GIVEN its policy */ }\n\n"
 "// Observer: the wallet announces; it does not know what a phone or a fraud desk is\n"
 "interface TxnListener { void onTxn(Transaction t); }\n"
 "private void publish(Transaction t) {\n"
 "    for (TxnListener l : listeners)                       // after the locks are released, always\n"
 "        try { l.onTxn(t); } catch (RuntimeException ex) { /* log */ }\n"
 "}\n\n"
 "// State: the life is a fixed set of moves, checked before every write\n"
 "enum TxnStatus { PENDING, COMPLETED, FAILED, REVERSED }\n"
 "if (orig.status() != TxnStatus.COMPLETED) throw new TransferRejected(\"...is \" + orig.status());\n\n"
 "// Event log: the journal is the truth, a balance is the fold of it\n"
 "long replayed = ledger.replay(accountId);                 // == account.balance(), always\n\n"
 "// NOT Decorator: the invariant has one gate already, so there is nothing to wrap\n"
 "void post(List<LedgerEntry> legs) { if (signedSum(legs) != 0) throw new IllegalStateException(...); }\n\n"
 "// Factory: not yet. configure() already takes the registry; it earns the name when rules come from config\n"
 "List<TransferRule> rules = List.of(new SameCurrencyRule(), new DailyLimitRule(cap));\n\n"
 "// Builder: not yet. Four required arguments is a method call; a note, tags and a device id would change that\n"
 "wallet.transfer(idemKey, fromId, toId, paise, memo);\n"),
]

build(dict(
    slug="digital-wallet", title="Digital Wallet",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 10 failure tests and a 50-thread two-way race pass",
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
