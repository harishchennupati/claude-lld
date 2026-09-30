# Banking system LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"banking/Main.java").read_text()
ext   = (H/"banking/Extensions.java").read_text()
tests = (H/"banking/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.rindex("/**", 0, ext.index("class ExtDemo"))]
    i = next(m for m in marks if a in ext[m:m+220])
    j = next(m for m in marks if m > i and b in ext[m:m+220])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("post", 26, [("cash in, or cash out", "an account, an amount"),
                      ("every rule must agree", "floor, ceiling, daily cap"),
                      ("row and balance together", "one lock hold, or neither"),
                      ("tell the SMS and the audit", "after the unlock, never inside")]),
        ("transfer", 150, [("pay B out of A", "with a transfer id"),
                           ("lock both, lower id first", "so a cycle cannot form"),
                           ("ask B, debit A, credit B", "the fee is asked first, too"),
                           ("one receipt per id", "a retried request pays once")]),
        ("end of period", 214, [("interest for the period", "by account kind"),
                                ("on the daily closing balances", "read off the ledger"),
                                ("charges, as FEE rows", "below the floor, overdrawn"),
                                ("180 days idle: DORMANT", "a customer posting wakes it")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 80 V90", dash=True) + _bx(360, 90, 390, 40, "a rule says no: no row, no paise", "", dash=True)
pf += _tx(88, 300, "read", "var(--acc)", 13) + _tx(175, 300, "at any moment, without re-adding the history: what is my balance?  what did March look like?  what does the bank hold?", "var(--text)", 12, "start")
pf += _tx(615, 334, "tellers, ATMs and the app all at once: no posting may be lost, a transfer may not create or destroy a rupee, and two customers paying each other must never deadlock", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 350, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("10:05  Asha at an ATM", ["SB-1001 holds 1,00,000.00", "floor 1,000.00; she asks for 99,500",
                                 "refused: not a row, not a paise", "the balance reads 1,00,000.00"], False),
      ("11:20  the shop pays a supplier", ["CA-2001 holds 20,000.00", "it pays out 60,000.00",
                                           "allowed to -40,000.00", "current account, ceiling 50,000"], True),
      ("14:00  rent, SB-1001 to CA-2001", ["25,000.00, transfer id T-1", "locks: CA-2001 then SB-1001",
                                           "the app retried T-1 at 14:00:01", "same receipt, no second pair of rows"], True),
      ("31st, 23:00  the month closes", ["she held 75,000 for 17 of 31 days", "paid on each day's closing balance",
                                         "the shop pays 18% on its red days", "each its own row: INTEREST or FEE"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Open savings and current accounts for a customer, each with an opening balance.</li>
<li>Deposit and withdraw; every balance change writes one row to the account's ledger (its history, never edited), and the row carries the balance after it.</li>
<li>Savings keeps a minimum balance; current may run negative, down to an overdraft ceiling.</li>
<li>Transfer between two accounts: nobody may ever see the debit without the credit, and a caller-supplied key makes a retried request move the money once.</li>
<li>Interest accrues for a period, by account kind, on the closing balance of each day, driven by an injected clock.</li>
<li>The bank charges as well as pays: a penalty under the minimum balance, interest on the days a current account spent overdrawn.</li>
<li>An account is ACTIVE, DORMANT (idle for months), FROZEN or CLOSED; closing is refused unless the balance is exactly zero.</li>
<li>A statement for any window, and alerts to whoever subscribed (a large withdrawal, an audit feed).</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many tellers and ATMs at once: no lost update, and no transfer creates or destroys a rupee.</li>
<li>Two customers paying each other must never deadlock: the lock order is decided, not hoped for.</li>
<li>Money is exact: integer paise inside a value type, never a double, and INR never adds to USD.</li>
<li>Balance, account lookup and "which accounts does she own" are O(1); a statement is a binary search.</li>
<li>Withdrawal rules, interest, fees and alerts swappable without editing Account or Bank.</li>
<li>Nothing half-done: a refused withdrawal or transfer leaves no row, no paise and no alert behind it.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design the core of a bank. Customers with savings and current accounts; deposits, withdrawals and '
          'transfers between two accounts; a statement at the end of the month. Savings keeps a minimum balance '
          'and earns interest, current may go overdrawn. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A bank holds accounts. Each account belongs to a '
 'customer, holds a balance, and keeps a full history of every rupee that moved, because the statement <i>is</i> '
 'the product. Money goes in and money comes out. The two account types disagree about one thing: how far the '
 'balance may fall. A savings account must stay above a floor (its minimum balance); a current account may sink '
 'below zero, down to its overdraft limit. They also differ in what the bank pays or charges at the end of a '
 'month. There the real question is not the rate but the <i>basis</i>: which balance the rate is applied to. '
 'A savings account is paid on the closing balance of every day, so money that arrived on the 28th '
 'earns three days, not a month. Money also moves between two accounts, and nobody may ever see the debit without '
 'the credit. Tellers, ATMs and the phone app all post (write a row to an account) at the same moment. So two '
 'things must always be true: no posting may be lost, and a transfer never creates or destroys a rupee (whatever '
 'the bank held before it, it holds after it). Interest, charges, dormancy (an idle account being marked inactive) '
 'and statements all depend on the date, so the date is something the code is given, not something it looks up.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that opens two accounts, moves money and prints the balances. The interviewer is '
 'watching for, in this order: the questions you ask before typing (how money is represented, and what actually '
 'differs between savings and current, are the first two); which classes exist and which one owns the balance; a '
 'deposit, a withdrawal and a transfer end to end; what happens when two ATMs hit one account at the same instant; '
 'where the rule that will change lives, so a daily cap is a new class and not an edit; what the account looks like '
 'when a rule says no. Then the twists: interest and what it is paid on, a charge instead of a refusal, dormancy, '
 'joint accounts, standing instructions, loans, KYC, persistence.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>How is money represented?</td><td>Integer paise inside a value type that carries its currency</td><td><code>long</code>, never <code>double</code>; INR plus USD throws (moves 1, 5)</td></tr>'
 '<tr><td>What really differs between savings and current?</td><td>Only how far below zero the balance may go</td><td>The difference is a rule object, not an overridden method (move 3)</td></tr>'
 '<tr><td>Is the balance a stored field, or the sum of the ledger?</td><td>Stored, and written with its row while the lock is held</td><td>O(1) reads now; persisted, this flips (move 5)</td></tr>'
 '<tr><td>Two callers on one account at the same instant &mdash; and two customers paying each other?</td><td>Both happen, and a request may be retried</td><td>One lock per account, both taken in id order, and the transfer id decides a repeat (moves 4, 6)</td></tr>'
 '<tr><td>What is interest paid on?</td><td>The closing balance of each day in the period</td><td>The rule is handed the account, not a number, and reads the ledger (moves 3, 5)</td></tr>'
 '<tr><td>Who drives interest, charges and dormancy?</td><td>An injected clock, and a month-end batch over every account (a sweep) that the caller runs</td><td><code>Clock</code> as an interface; a test moves a year in one line (moves 3, 9)</td></tr>'
 '<tr><td>One process in memory, or a database and many branches?</td><td>One process, in memory</td><td>No repository yet; a follow-up adds one (move 12)</td></tr>'
 '<tr><td>Joint accounts, loans, KYC, scheduled payments?</td><td>Out of scope, named</td><td>Each is one of the five twist moves (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One afternoon, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> money is integer paise in a value type that carries its currency and '
 'refuses mixed arithmetic; the balance is a stored field, written together with its ledger row while the account\'s '
 'lock is held; savings and current differ only in the rule objects they are opened with; interest is paid on the '
 'daily closing balance, so the rule is handed the account and reads the ledger; a transfer takes both account locks '
 'in id order, and is idempotent by a caller-supplied key (a retry with the same key moves no more money); the date '
 'is injected. Named as out of scope: joint accounts, standing '
 'instructions, loans, KYC, persistence &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a CUSTOMER holds ACCOUNTS; an ACCOUNT has a BALANCE and a LEDGER of ROWS; a RULE vetoes a WITHDRAWAL; a TRANSFER moves money between two accounts", "var(--text)", 12.5)
for x, w, t, sub, solid in [(30, 150, "Customer", "an id; nothing moves", 1), (200, 180, "Account", "balance, ledger, lock", 2),
                            (400, 150, "Txn", "one immutable row", 1), (570, 150, "Money", "paise + currency", 1),
                            (740, 160, "Bank", "accounts, transfer ids", 2), (920, 140, "Rule", "an interface", 0),
                            (1080, 150, "Balance", "a field, not a class", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=(solid == 2), dash=(solid == 0)) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a field, an interface, or a method", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("put money in, take money out", "Account  (owns the balance, the ledger, the lock)", "account.deposit / withdraw(amount)"),
                                       ("say no to a withdrawal", "WithdrawalRule  (owns only its own memory)", "rule.check(account, amount, now)"),
                                       ("move money between two accounts", "Bank  (owns both accounts, so it owns the order)", "bank.transfer(id, from, to, amt)"),
                                       ("what did March look like?", "Account  (owns the rows)", "account.statement(from, to)")]):
    y = 20 + k*54
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 255, "a verb whose state sits in TWO classes belongs to neither: it goes up to the class that owns both. That is why transfer lives on the Bank", "var(--muted)", 11)
m2 += _tx(615, 274, "and a statement is not a new class reaching into the ledger: the account owns the rows, so the account prints them", "var(--muted)", 11)
MV[2] = _mv(1230, 288, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 142, 220, 90, "Bank / Account", "configure(...) / addRule(...)", acc=True)
for k, (t, sub, impl) in enumerate([("WithdrawalRule", "floor, overdraft, daily cap, KYC", "MinBalanceRule / OverdraftRule / DailyLimitRule"),
                                    ("InterestRule", "a rate, a bonus, and the BASIS", "SimpleInterest, DailyBalanceInterest, PromoInterest"),
                                    ("MonthlyCharge", "below the floor, days overdrawn", "MinBalancePenalty, OverdraftInterest"),
                                    ("FeePolicy", "free, or flat above a threshold", "FlatFeeAboveThreshold, or a lambda"),
                                    ("AccountListener", "SMS, audit, fraud, analytics", "AuditLog, LargeWithdrawalAlert, a lambda"),
                                    ("Clock", "what today's date is", "System::currentTimeMillis, or a test's lambda")]):
    y = 20 + k*58
    m3 += _ar("M250 187 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 420, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 384, "dashed = handed in. Nothing here builds a rule, so a daily cap is a new class and one line &mdash; and one rule WRAPS another:", "var(--muted)", 11)
m3 += _tx(615, 403, "PromoInterest(SimpleInterest(400), 50) adds a festival bonus to a rate nobody edited. That is Decorator, and it was born here", "var(--acc)", 11)
m3 += _tx(615, 426, "InterestRule is handed the ACCOUNT, not a number, so \"which balance do we pay on?\" is the rule's answer too, read off the ledger", "var(--acc)", 11)
m3 += _tx(615, 449, "the tempting design is to override withdraw() in SavingsAccount and CurrentAccount. Then the first daily cap needs an instanceof: vetoes stack up, overrides do not", "var(--muted)", 11)
MV[3] = _mv(1230, 464, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 210, 44, "an ATM in Kolkata", "reads 5,000.00") + _bx(30, 110, 210, 44, "her phone, same instant", "reads 5,000.00")
m4 += _bx(360, 70, 190, 44, "the balance", "INR 5,000.00", acc=True)
m4 += _ar("M240 52 H360 V70") + _ar("M240 132 H360 V114") + _tx(300, 40, "read", "var(--muted)", 10.5) + _tx(300, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="590" y="20" width="300" height="148" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(740, 45, "the gap", RED, 12) + _tx(740, 70, "both were told \"you have enough\"", RED, 11) + _tx(740, 90, "8,000.00 leaves a 5,000.00 account", RED, 11)
m4 += _tx(740, 110, "and the 1,000.00 floor is broken", RED, 11)
m4 += _tx(740, 145, "fix: check and write as ONE step", "var(--text)", 11)
m4 += _bx(920, 40, 280, 100, "Account.lock", "rules + row + balance, one hold", acc=True)
m4 += _tx(1060, 165, "the lock lives where the balance lives", "var(--muted)", 10.5)
m4 += _tx(1060, 185, "one lock per ACCOUNT: two customers never wait", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is my balance?", "a Money field, written with the row", "O(1)"),
                                      ("the account numbered CA-2001?", "Map&lt;String, Account&gt;", "O(1)"),
                                      ("which accounts does she own?", "Map&lt;customerId, List&lt;String&gt;&gt;", "O(1)"),
                                      ("what happened in March?", "List&lt;Txn&gt;, appended in time order", "O(log n + k)"),
                                      ("which interest rule does savings use?", "EnumMap&lt;AccountKind, InterestRule&gt;", "O(1)"),
                                      ("have I already done this transfer?", "ConcurrentHashMap&lt;txId, Receipt&gt;", "O(1)"),
                                      ("what did she hold on each day of March?", "one copy of the ledger, one binary search a day", "O(n + 31 log n)")]):
    y = 20 + k*46
    m5 += _bx(30, y, 360, 38, q, "the question") + _ar("M390 %s H450" % (y+19), True)
    m5 += _bx(450, y, 520, 38, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+19), True) + _bx(1030, y, 170, 38, cost, "")
m5 += _tx(615, 364, "the balance is a STORED field, not re-added from the ledger: the row and the field are written in the same lock hold, so they cannot disagree", "var(--muted)", 11)
m5 += _tx(615, 383, "and the ledger answers the last question for free, which is what makes interest on the daily closing balance a rule and not a new store", "var(--muted)", 11)
MV[5] = _mv(1230, 396, m5)

# move 6: the state machine, the ORDER at the critical step, and the deadlock
m6 = _D + _bx(60, 30, 180, 44, "ACTIVE", "takes postings", acc=True) + _bx(330, 30, 190, 44, "FROZEN", "refuses everything")
m6 += _bx(60, 125, 180, 44, "DORMANT", "180 days untouched") + _bx(330, 125, 190, 44, "CLOSED", "final; never reopens")
m6 += _ar("M240 45 H330", True) + _tx(285, 37, "freeze", "var(--muted)", 9.5)
m6 += _ar("M330 62 H240") + _tx(285, 79, "unfreeze", "var(--muted)", 9.5)
m6 += _ar("M120 74 V125", True) + _tx(112, 104, "180 days idle", "var(--muted)", 9.5, "end")
m6 += _ar("M180 125 V74") + _tx(190, 104, "customer posts", "var(--muted)", 9.5, "start")
m6 += _ar("M228 74 L336 125", True)
m6 += _ar("M240 147 H330", True) + _tx(285, 141, "at zero", "var(--muted)", 9.5)
m6 += _tx(285, 195, "ACTIVE or DORMANT to CLOSED, only at exactly zero", "var(--muted)", 10.5)
m6 += _tx(285, 213, "FROZEN cannot close: a freeze is a legal hold", "var(--muted)", 10.5)
m6 += '<rect x="560" y="20" width="650" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(885, 44, "the order inside a transfer, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  the transfer id: if it already has a receipt, return it and post nothing",
                       "2  take BOTH locks, lower account id first -- always, by id",
                       "3  ask all that could refuse: the destination, and the fee policy",
                       "4  debit the source: its rules see amount + fee, in the same hold",
                       "5  credit the destination: it cannot fail, because step 3 already asked",
                       "6  write the fee row, already approved in step 4, in the same hold",
                       "7  write the receipt, release both locks, and only then tell the listeners",
                       "anything that throws before step 4 leaves both accounts exactly as they were, and the",
                       "id is not claimed, so the caller may retry it once the reason has been fixed"]):
    m6 += _tx(575, 66 + k*18, l, "var(--muted)" if k > 6 else "var(--text)", 11, "start")
m6 += _bx(30, 255, 250, 44, "thread 1:  A pays B", "holds A, wants B") + _bx(330, 255, 250, 44, "thread 2:  B pays A", "holds B, wants A")
m6 += _ar("M280 267 H330", True) + _ar("M330 289 H280", True)
m6 += '<rect x="20" y="245" width="570" height="64" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m6 += _tx(305, 325, "a deadlock: each holds one lock and waits for the other, forever", RED, 11)
m6 += _bx(640, 255, 570, 44, "the fix is not more locks, it is an ORDER", "sort the two ids and take the LOWER one first: a cycle cannot form", acc=True)
m6 += _tx(925, 325, "every thread takes the lower id first, so none can hold what another waits for", "var(--muted)", 11)
MV[6] = _mv(1230, 345, m6)

# move 7: what is inside the lock, and ten callers at the same instant
m7 = _D + _card(30, 20, 540, 155, "inside the lock: about 1.5 microseconds",
                ["is the status ACTIVE or DORMANT?", "one to three rule checks, each reading the balance",
                 "one Money subtract, overflow-checked", "append one row; write balance, seq and the stamp",
                 "about twelve operations in all"], acc=True)
m7 += _ar("M570 97 H640", True) + _tx(605, 87, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 155, "outside the lock: milliseconds to seconds",
            ["the SMS to the customer: about 50 ms, after unlock", "the audit file: about 1 ms, after unlock",
             "the database write: about 5 ms (a follow-up)", "the customer at the ATM: seconds",
             "a transfer holds TWO locks, for about 3 us"])
m7 += _tx(615, 205, "ten ATMs hit one salary account at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 220, 106, 40, "atm %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%.1f" % (k*1.5)), acc=(k == 9))
m7 += _tx(615, 288, "the tenth ATM waits 13.5 microseconds for the lock and then fifty milliseconds for its own SMS:", "var(--muted)", 11)
m7 += _tx(615, 306, "one at a time is true, and nobody can tell, because nothing slow is allowed inside the lock", "var(--muted)", 11)
MV[7] = _mv(1230, 320, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per account: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of a posting: ~12 operations, about 1.5 us",
                       "a salary account: about 30 postings a month, one a day",
                       "a busy merchant current account: 5 a second = 7.5 us a second",
                       "even 1,000 postings a second into ONE account is 1.5 ms: 0.15% busy",
                       "and the lock is per ACCOUNT: fifty million accounts never meet"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 nothing slow inside the lock", "the SMS, the audit file, the database: all after the unlock"),
                              ("2 shrink the hold, or split one very hot account", "k sub-balances, each with its own lock, summed on read"),
                              ("3 the balance becomes a database row", "UPDATE ... SET paise = paise - ? WHERE id = ? AND paise - ? &gt;= floor")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("sixteen ATMs on one account at once", "check and write in ONE lock hold; test 6: 192 tries, exactly 90 get paid"),
                                ("A pays B while B pays A", "both locks in account-id order; test 7: all 64 finish, total assets unchanged"),
                                ("the destination is frozen", "ask the destination BEFORE the debit; test 12: the source still has one row"),
                                ("a savings account is drained past its floor", "every rule inside the same hold; tests 1 and 2: balance and ledger identical"),
                                ("the same transfer request arrives twice", "the transfer id is the key; test 10: two rows each, not four"),
                                ("a month's interest on 3-day-old money", "the rule reads the daily closing balances; test 4: INR 65.75, not INR 361.64"),
                                ("the balance and the ledger disagree", "one writer, both written in one hold; test 24: 277 rows replay to the balances")]):
    y = 18 + k*42
    m9 += _bx(30, y, 340, 38, bad, "") + _ar("M370 %s H410" % (y+19), True) + _bx(410, y, 790, 38, fix, "", acc=True)
m9 += _tx(615, 334, "every claim this design makes has a failure test: FailureTests.java runs fifty-eight of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 347, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 190), ("the line in the code", 280), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface WithdrawalRule { void check(account, amount, now); }", None), ("a daily cap is a class plus one addRule line", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new PromoInterest(new SimpleInterest(400), 50)", None), ("a festival bonus without editing the rate", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(t) after the unlock, inside a try/catch", None), ("the SMS hears; the balance never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("ACTIVE / DORMANT / FROZEN / CLOSED, checked before every post", None), ("an illegal posting cannot happen", None)],
          [("Ordered locking", "var(--text)"), ("move 6", None), ("first = fromId.compareTo(toId) &lt; 0 ? from : to;", None), ("deadlock is impossible, not rare", None)],
          [("Template Method", "var(--muted)"), ("rejected", None), ("withdraw() fixed in Account, canWithdraw() overridden per subclass", "var(--muted)"), ("a second veto would need an instanceof", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("the Bank is handed to its callers; no getInstance()", "var(--muted)"), ("a test builds a fresh Bank", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("openSavings / openCurrent are the two constructors", "var(--muted)"), ("it earns the name when kinds come from config", "var(--muted)")],
          [("Builder", "var(--muted)"), ("not yet", None), ("an account has five fields and every one is required", "var(--muted)"), ("it earns a place when an application form arrives", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=29, widths=1190)
m10 += _tx(615, 330, "name a pattern only after the move that produced it; then every name has a one-sentence defence, and \"rejected\" is an answer too", "var(--muted)", 11)
MV[10] = _mv(1230, 345, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 430), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Money does arithmetic, Txn is one row, Account guards one balance, Bank owns the transfer", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("DailyLimitRule is a new file plus asha.addRule(...); Account and Bank are untouched", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("deposit / withdraw are final, so no subclass can skip a rule or post outside the lock", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("WithdrawalRule, InterestRule, FeePolicy, AccountListener, Clock: one method to implement each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("bank.configure(rules, clock);  account.addRule(rule);  bank.setFeePolicy(p)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "a daily cap, KYC, a charge not a veto", "a new class behind the matching interface, plus one line", "", "move 3"),
        ("someone new wants to know", "SMS, a fraud engine, a regulator", "one more listener; Account and Bank do not change", "", "move 4"),
        ("a new step in a life", "pending closure, blocked by a court", "one more status and one more checked transition", "", "move 6"),
        ("a new invariant across accounts", "a fee, a sweep across three accounts", "every leg inside the SAME ordered locks: all of it or none", "", "moves 4, 6"),
        ("state that must outlive the process", "persist it; two branches", "the balance becomes a row; the debit becomes", "UPDATE ... WHERE id = ? AND paise - ? &gt;= floor, plus a unique index on the transfer id", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 340, 44, t, sub) + _ar("M370 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the Account, the Bank and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>customer</b> holds <b>accounts</b>; an account has a <b>balance</b> and a "
 "<b>ledger</b> of <b>rows</b>; a <b>rule</b> vetoes a <b>withdrawal</b>; a <b>transfer</b> moves money between two "
 "accounts. An account has a balance, a status, a history and a lock, all of which change: a class, and the one the "
 "whole design turns on. A ledger row has a type, an amount and the balance after it, and never changes again: a "
 "record. Money is two values that never change once made, paise and a currency, so it is a value type (an object "
 "that is nothing but its values). Making it a type rather than a bare <code>long</code> is what stops somebody "
 "adding rupees to dollars. A "
 "customer has an id and a name and nothing that moves, so the account stores the id and a rename can never move "
 "money. A rule answers one question, so it is an interface; the rare rule that must remember something, such as a "
 "daily cap, keeps that memory inside its own class. And a balance is not a separate thing to store twice: "
 "it is one field on the account, written in the same breath as the row that explains it.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Put money in, take money out\" touches the balance, the ledger and the lock, and only the account owns all three, "
 "so <code>account.deposit(...)</code> and <code>account.withdraw(...)</code>. \"Say no to a withdrawal\" touches "
 "nothing but the amount and the balance it is given, so it belongs to a rule: <code>rule.check(account, amount, "
 "now)</code>. \"What did March look like?\" touches the rows, and the account owns the rows, so "
 "<code>account.statement(from, to)</code> &mdash; a statement is not a new class reaching into somebody else's list. "
 "Then the interesting one. \"Move money between two accounts\" touches two balances, and a verb whose state sits in "
 "two classes belongs to neither: it goes up to the class that owns both. That is the bank. It is not an extra "
 "layer: it is the only place allowed to hold two account locks, and that rule is what stops one account reaching "
 "into another and two threads waiting for each other forever.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "How far the balance may fall will change: a floor today, an overdraft for current accounts, a daily cap on ATMs "
 "before the hour is out. The interest rate will change, and so will a festival bonus on top of it. What the bank "
 "takes will change twice over: what a transfer costs, and what it charges at the end of a month &mdash; a penalty "
 "under the minimum balance, interest on the days a current account spent overdrawn. Who is told will change: an SMS "
 "today, a fraud engine and a regulator feed later. Each becomes a "
 "one-method interface that is handed in through <code>configure()</code> or <code>addRule()</code> and never built "
 "inside. One of them hides a question most candidates miss. <code>InterestRule</code> is handed the <i>account</i>, "
 "not a balance, so the rule also decides the <b>basis</b>. It can pay on the balance as it stands, or on the "
 "closing balance of every day in the month. The second is what a real savings account is paid on, and it stops a "
 "deposit made on the 28th earning a full month. Reading those daily balances needs the ledger, and the account "
 "already has it. "
 "This is where the patterns come from, not the other way round: a swappable rule behind an interface is "
 "<b>Strategy</b>; a rule that wraps another and adds to it is <b>Decorator</b>; a bank that announces \"a row was "
 "written\" without knowing what an SMS is, is <b>Observer</b>. And notice the design this replaces. The tempting move "
 "is to override <code>withdraw()</code> in SavingsAccount and CurrentAccount, since that is the one sentence they "
 "disagree about. Do that and the first extra check &mdash; a daily cap, a fraud hold &mdash; means editing both "
 "subclasses or writing an <code>instanceof</code>. An override can express one difference. Vetoes have to stack up "
 "(every one of them must agree), and a list of rule objects stacks; overrides do not. The subclasses shrink to what "
 "is genuinely is-a: savings earns interest, current has a ceiling.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "An ATM in Kolkata and her phone hit the same account at the same instant, both asking for four thousand out of a "
 "balance of five thousand with a floor of one thousand. Both read five thousand, both are told \"you have enough\", "
 "both write: eight thousand leaves an account that held five, and the floor everyone was so careful about is broken. "
 "So checking and writing must be one step, in the class that owns the balance and the ledger: the account. Both "
 "happen in one <i>hold</i> of its lock (the lock is taken once and not released in between). The lock is per "
 "<i>account</i>, not per bank, and that is the whole trick. Fifty million accounts post in parallel and never wait "
 "for each other; the two tellers touching one account take turns, for about a microsecond and a half each. "
 "Anything that only listens (the SMS, the audit file) is called after the lock is released, never inside it, "
 "because a gateway that hangs for thirty seconds must not be able to hold a balance hostage.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What is my balance?\" is a field on the account, written in the same lock hold as the row that changed it, so the "
 "two can never disagree. It is not re-added from the ledger on every read: adding up a year of history on every "
 "balance screen is the mistake that makes a real bank slow. \"The account numbered CA-2001?\" is a map by id. \"Which "
 "accounts does she own?\" is a map from customer id to a list of account ids. \"What happened in March?\" is the "
 "ledger, appended in time order, so both ends of a window are a binary search: O(log n + k), never a scan. That "
 "order is guaranteed: <code>post()</code> never stamps a row earlier than the row before it, even if the server's "
 "clock steps back. \"Which interest rule does a savings account use?\" is an <code>EnumMap</code> keyed by the account "
 "kind, which is what the kind enum is <i>for</i>. \"Have I already done this transfer?\" is a map from the caller's "
 "transfer id to its receipt, and that one map is what makes a retried request free. Then the question the ledger "
 "answers for free: \"what did she hold on each day of March?\" is one copy of the rows and thirty-one binary searches "
 "over it. That is why interest on the daily closing balance is a rule that reads the ledger, not a second store of "
 "daily balances. One honest note: the day this is saved to a database, the ledger becomes the record, and the "
 "stored balance becomes a copy (a cache) you can always rebuild by replaying the rows. The last failure test does "
 "exactly that.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An account is ACTIVE when it is working. It becomes DORMANT after 180 days in which no customer touched it (this "
 "code's number; for an Indian \"inoperative\" account the RBI's number is two years). It is FROZEN when the bank or "
 "a court says so, and a frozen account cannot be closed until it is unfrozen. It is CLOSED only when the balance is "
 "exactly zero, so money can never be stranded in an account nobody can reach; CLOSED is final. Any customer posting "
 "wakes a dormant account, but the bank's own interest row does not, which is a small rule worth saying out loud. "
 "Writing the states down forces the question the interviewer will ask: what if something fails halfway through a "
 "transfer? The answer is an order (the digital wallet page derives it in full). One: check the transfer id, and "
 "return the old receipt if it has one. Two: take <i>both</i> locks, lower account id first. Three: before a single "
 "paise moves, ask everything that could refuse: the destination (frozen, closed, wrong currency) and the fee "
 "policy. Four: debit the source, with its rules checking the amount plus the fee in the same hold. Five: credit "
 "the destination, which now cannot fail. Six: write the fee row. Seven: write the receipt, release both locks, "
 "then tell the listeners. Anything that throws before the debit leaves both accounts exactly as they were, and the "
 "id is not claimed, so the caller can retry it. The one line worth memorising is the lock <i>order</i>. Every "
 "thread takes the lower account id first, so no thread can hold one account while waiting for a thread that holds "
 "the other: A-pays-B while B-pays-A cannot deadlock. That is impossible, not merely unlikely.", 6),
("Move 7: yes, the lock makes one account's postings happen one at a time. Ask for how long, and what is inside it.",
 "If every posting takes the account's lock, is the bank a queue? It is, for about a microsecond and a half, and only "
 "for the people touching that one account. Inside the lock: a status check, one to three rule checks, one "
 "overflow-checked subtraction, one row appended, three field writes; about twelve operations. Each rule check reads "
 "the balance, which takes the same lock again; that works because the lock is reentrant (the thread that holds it "
 "may take it again). Everything slow is outside: the SMS at fifty milliseconds, the audit file, a later version's "
 "database write, and the customer standing at the machine. So when ten ATMs hit one salary account at the same "
 "instant, the tenth waits about 13.5 microseconds for the lock and then fifty milliseconds for its own SMS. The one "
 "banking-specific note: interest and the month-end charges hold one account's lock at a time, for microseconds, to "
 "read that account's balances and write its row. So a batch over fifty million accounts never makes a customer at "
 "an ATM wait longer than that.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A salary account sees about thirty postings a month. A busy merchant's current account might see five a second, "
 "which is seven and a half microseconds of lock in every second. Invent a thousand postings a second into one "
 "account and it is one and a half milliseconds a second: busy fifteen hundredths of one per cent of the time. The "
 "lock is per account, so the number of accounts is irrelevant; only the two accounts in a transfer ever share. Then "
 "the ladder, in the order you would climb it. First, keep everything slow outside the lock, which this code already "
 "does. Second, if one account really is hot (a settlement account where a big merchant's card payments land, a "
 "million credits a day), split its balance into k sub-balances, each with its own lock, summed on read. Third, "
 "beyond one process, make the balance a database row and the debit one conditional <code>UPDATE ... WHERE paise - ? "
 "&gt;= floor</code>, with a unique index on the transfer id (the database refuses a second row with the same id). "
 "Say the arithmetic first: climbing the ladder without it is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Sixteen ATMs on one account at the same instant: the check and the write happen in one hold, so the arithmetic is "
 "exact. INR 9,000 above the floor, taken INR 100 at a time, is exactly 90 successful withdrawals out of 192 "
 "attempts, whatever order the threads ran in. Two customers paying each other at the same instant: both locks in "
 "account-id order, all 64 transfers finish, and the bank's total assets are unchanged to the paise. The destination "
 "frozen: asked before the debit, so the source still has exactly one row. A savings account drained past its "
 "floor: every rule inside the same hold, and a refusal leaves no row and no paise. The same transfer request "
 "arriving twice: the id is the key, two rows each and not four. A fee policy that throws, or a fee that would break "
 "the overdraft limit: the fee is asked before any money moves, so nothing is written. A month of interest paid on "
 "money that arrived three days ago: the daily-closing-balance rule pays INR 65.75 where the naive one pays INR "
 "361.64. The balance and the ledger drifting apart: every row of every account in every test bank is replayed from "
 "zero and must land on the stored balance. And the SMS gateway throwing: listeners run after the unlock, each in a "
 "try/catch, and the deposit still lands. Each of these is a few lines in FailureTests.java; a design that cannot "
 "show its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Every pattern here came out of a move, which is why each can be defended in one sentence. Strategy is move 3: how "
 "far a balance may fall, what interest it earns and what a transfer costs are rules that will change, so each sits "
 "behind a one-method interface that is handed in. Decorator is the same move's wrapper: <code>PromoInterest</code> "
 "adds a festival bonus to whatever rule an account kind already has, instead of editing the rate. Observer is move "
 "4's rule that an SMS gateway must never be inside the lock. State is move 6: the account's life written down, so a "
 "posting to a closed account throws instead of quietly working. The ordered two-lock acquisition in a transfer has "
 "no fancy name and is the most valuable line on the page. Then the honest negatives. Template Method (a fixed "
 "<code>withdraw()</code> in Account that calls one step each subclass overrides, such as <code>canWithdraw()</code>) "
 "is the design most people reach for here. It is rejected on purpose: it expresses exactly one difference, and the "
 "second veto costs an <code>instanceof</code>. "
 "Singleton earned nothing: the bank is handed to its callers, so a test builds a fresh one. Factory earns the name "
 "the day account kinds arrive as strings from configuration, and Builder the day a real application form arrives "
 "with a dozen optional fields. A pattern without a move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is not a list to recite; it is the check that the moves did their job. S: a class has one reason to change, "
 "which move 2 gave you &mdash; Money does arithmetic, a Txn is one immutable row, an Account guards one balance and "
 "its history, a rule answers one question, and the Bank owns the one invariant that spans two accounts. O: a daily "
 "cap is a new file and one <code>addRule</code> call, and Account, Bank, Money, Txn and both subclasses are never "
 "opened. L: <code>deposit</code>, <code>withdraw</code> and both halves of a transfer are <code>final</code>, so no "
 "subclass can skip a rule or write a row outside the lock &mdash; the substitution is safe because there is nothing "
 "left to override. I: five interfaces, one method to implement each, so a fake for a test is a lambda. D: the bank "
 "depends on "
 "interfaces and is handed the implementations, which is exactly why a test can hand it a clock that says next March "
 "and a rule that refuses everything.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (a daily cap, KYC, a fraud hold, two-person approval) is a new class behind <code>WithdrawalRule</code> "
 "plus one <code>addRule</code> line, and a charge at the end of a month is the same move behind "
 "<code>MonthlyCharge</code>. Someone new who wants to know (an SMS, a fraud engine, a regulator feed) is one "
 "more listener; the account and the bank do not change. A new step in a life (pending closure, blocked by a court "
 "order) is one more status and one more checked transition. A new invariant across accounts (a fee charged with the "
 "transfer, a sweep across three accounts) is every leg inside the <i>same</i> ordered locks, all of it or none of "
 "it. State that must outlive the process is the balance behind a repository (an interface that loads and saves "
 "accounts), where the debit becomes <code>UPDATE ... WHERE id = ? AND paise - ? &gt;= floor</code>: the database "
 "doing the same compare-and-set (change the row only if it still passes the check, in one step). For "
 "all five the Account, the Bank and the tests do not change; that is the test that the derivation was right. Page "
 "05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, Splitwise) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On a bank two of the moves do more work than usual. Move 3, because the "
 "obvious design (override withdraw() per account type) is the wrong one. Move 5, because the ledger has to answer "
 "\"what did she hold on each day of March?\" as well as \"what is my balance?\". The two-account transfer (ordered "
 "locks, one receipt per id, a debit and a credit that land together) is worked through in full on the digital wallet "
 "page. Here it is stated once, and the hour goes on the things only a bank has.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the callers, the listeners, the value types
put("cust",  10, 20, 240, "Customer", ["id: String", "name: String"], [])
put("lsnr",  10, 105, 240, "AccountListener", [], ["onPosted(account, txn)"], "interface")
put("audit", 10, 180, 240, "AuditLog", [], ["onPosted(...) &rarr; a file, an SMS"])
put("alert", 10, 245, 240, "LargeWithdrawalAlert", ["threshold: Money"], ["onPosted(...) &rarr; an alert"])
put("clock", 10, 340, 240, "Clock", [], ["nowMs(): long"], "interface")
put("money", 10, 420, 240, "Money", ["paise: long", "currency: String"],
    ["plus / minus / lessThan", "inr(\"1000.50\"): Money"])
put("rcpt",  10, 550, 240, "TransferReceipt", ["transferId: String", "fromId / toId: String", "amount: Money"], [])
put("errs",  10, 650, 240, "BankingException", ["RuleViolation", "AccountNotActive", "NoSuchAccount", "CurrencyMismatch"], [])
# centre column: the aggregate roots and what they own
put("bank", 300, 20, 340, "Bank",
    ["accounts: Map&lt;id, Account&gt;", "customers: Map&lt;id, Customer&gt;", "transfers: Map&lt;txId, Receipt&gt;",
     "interestRules: EnumMap&lt;Kind, Rule&gt;", "listeners / fees / clock"],
    ["configure(rules, clock)", "openSavings(...) / openCurrent(...)", "account(id) / accountsOf(customer)",
     "transfer(txId, from, to, amount)", "accrueInterest(days)", "markDormant() / close(id)",
     "totalAssets(currency)"])
put("acct", 300, 270, 340, "Account",
    ["id / customerId: String", "kind: AccountKind", "balance: Money", "status: AccountStatus",
     "ledger: List&lt;Txn&gt;", "lock: ReentrantLock", "rules: List&lt;WithdrawalRule&gt;", "seq / lastActivityMs: long"],
    ["deposit(amount, note): Txn", "withdraw(amount, note): Txn", "debitForTransfer / creditForTransfer",
     "checkCanReceive(amount)", "statement(from, to): Statement", "balance() / status()", "addRule(rule)",
     "post(...)  -- the one writer"], abstract=True)
put("txn",  300, 600, 340, "Txn",
    ["seq: long,  type: TxnType", "amount / balanceAfter: Money", "atMs: long,  ref: String", "note: String"], [])
# third column: the enums, the value records and the two subclasses
put("status", 680, 20, 240, "AccountStatus", ["ACTIVE, DORMANT,", "FROZEN, CLOSED"], [], "enum")
put("kind",   680, 105, 240, "AccountKind", ["SAVINGS, CURRENT"], [], "enum")
put("ttype",  680, 175, 240, "TxnType", ["OPENING, DEPOSIT, WITHDRAW,", "TRANSFER_IN / TRANSFER_OUT,", "INTEREST, FEE, REVERSAL"], [], "enum")
put("stmt",   680, 275, 240, "Statement", ["opening / closing: Money", "rows: List&lt;Txn&gt;"], ["print(): String"])
put("sav",    680, 380, 240, "SavingsAccount", ["minBalance: Money"], ["wires a MinBalanceRule"])
put("cur",    680, 480, 240, "CurrentAccount", ["overdraftLimit: Money"], ["wires an OverdraftRule"])
# fourth column: the rules that are handed in
put("wrule", 960, 20, 225, "WithdrawalRule", [], ["check(account, amount, now)", "onWithdrawn(account, amount)"], "interface")
put("irule", 960, 130, 225, "InterestRule", [], ["interest(account, days, now)"], "interface")
put("simple", 960, 210, 225, "SimpleInterest", [], ["the balance as it stands", "x bps x days / 365"])
put("promo", 960, 306, 225, "PromoInterest", ["base: InterestRule (wrapped)"], ["+ a festival bonus"])
put("fee",   960, 400, 225, "FeePolicy", [], ["feeFor(from, to, amount)"], "interface")
# the bottom row: the three withdrawal rules, on one inheritance bus
put("minbal", 680, 648, 165, "MinBalanceRule", [], ["no lower than a floor"])
put("over",   860, 648, 165, "OverdraftRule", [], ["no lower than -ceiling"])
put("daily", 1040, 648, 165, "DailyLimitRule", [], ["a cap with a memory", "(Extensions.java)"])

def stub(x, y1, y2):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x, y1, x, y2)

EDGES = [
 # the three withdrawal rules implement the interface, on one bus around the right edge
 ln(B["minbal"]["t"], (1185, 55), "inherit", "", [(762, 620), (1212, 620), (1212, 55)]),
 stub(942, 648, 620), stub(1122, 648, 620),
 # the interest rules
 ln(B["simple"]["t"], B["irule"]["b"], "inherit"),
 ln(B["promo"]["r"], (1185, 150), "inherit", "", [(1196, 343), (1196, 150)]),
 _tx(1072, 394, "WRAPS another rule: Decorator", "var(--acc)", 10.5),
 _tx(1072, 486, "+ DailyBalanceInterest, in Extensions", "var(--muted)", 10.5),
 # the two listeners, on one bus
 ln(B["audit"]["t"], B["lsnr"]["b"], "inherit"),
 stub(130, 245, 234),
 _tx(150, 762, "all unchecked: any rule may throw", "var(--muted)", 10.5),
 # the two account types
 ln(B["sav"]["l"], (640, 350), "inherit", "", [(668, 417), (668, 350)]),
 ln(B["cur"]["l"], (640, 400), "inherit", "", [(660, 517), (660, 400)]),
 # the bank owns the accounts, the account owns its rows
 ln(B["bank"]["b"], B["acct"]["t"], "compose", "owns every account"),
 ln(B["acct"]["b"], B["txn"]["t"], "compose", "append only, immutable"),
 # the account points at its enums and hands out a statement
 ln((640, 300), B["stmt"]["l"], "assoc", "", [(672, 300), (672, 291)]),
 ln((640, 285), (680, 45), "assoc", "", [(676, 285), (676, 45)]),
 ln((640, 330), (680, 130), "assoc", "", [(650, 330), (650, 130)]),
 ln(B["txn"]["r"], (680, 216), "assoc", "", [(646, 657), (646, 216)]),
 # the rules are handed in
 ln((640, 480), B["wrule"]["l"], "inject", "", [(940, 480), (940, 55)]),
 ln((640, 100), B["irule"]["l"], "inject", "", [(932, 100), (932, 157)]),
 ln((640, 160), B["fee"]["l"], "inject", "", [(948, 160), (948, 427)]),
 _tx(1072, 520, "the rules, handed in", "var(--acc)", 10.5),
 _tx(1072, 553, "+ MonthlyCharge, in Extensions", "var(--muted)", 10.5),
 # the callers, the listeners and the values
 ln((300, 320), B["lsnr"]["r"], "notify", "", [(275, 320), (275, 132)]),
 ln(B["bank"]["l"], B["clock"]["r"], "inject", "", [(268, 129), (268, 367)]),
 ln(B["acct"]["l"], B["money"]["r"], "assoc", ""),
 ln((300, 200), B["rcpt"]["r"], "assoc", "", [(288, 200), (288, 591)]),
 _tx(130, 542, "one receipt per transfer id", "var(--muted)", 10.5),
 ln(B["cust"]["r"], (300, 50), "assoc", ""),
]
UMLSVG = uml_svg(1230, 800, EDGES, legend_y=782)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (italic = abstract, dashed border = interface, '
 '&laquo;enum&raquo; = a fixed list of values). Middle: its fields, the state it holds. Bottom: its methods. '
 '<b>The arrows.</b> Hollow triangle = extends or implements. Filled diamond = owns: the bank owns every account, '
 'an account owns every row of its ledger. Plain arrow = references: an account points at its status and its kind, a '
 'row at its type. Dashed green = handed in through <code>configure()</code>, <code>addRule()</code> or '
 '<code>setFeePolicy()</code>. Dotted blue = notifies. <b>Where state lives:</b> the account has the balance, the '
 'status, the ledger, its rules and the one lock, and its private <code>post()</code> is the only thing in the system '
 'that writes a row; the bank has the accounts, the transfer receipts, the interest rules, the clock and no balance '
 'of its own; a row never changes after it is written; <code>Money</code> is immutable, so a number in a ledger row '
 'cannot be edited behind the account\'s back. Down the left column are the things that only listen or only carry a '
 'value: the two listeners on one bus, the clock, Money, a receipt, and the one exception family every refusal is '
 'thrown as. A box marked <code>(Extensions.java)</code> is not part of the hour\'s code &mdash; it is a follow-up\'s '
 'class, drawn here to show where it would plug in. Notice what is <i>not</i> here: no Balance class, because a '
 'balance is a field the account writes with the row that explains it; no Transfer class, because a transfer is a '
 'method on the bank plus a receipt; and almost nothing in SavingsAccount and CurrentAccount, because the sentence '
 'they disagree about became a rule object instead of an overridden method.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code &mdash; '
 'the daily cap, the daily-closing-balance interest, the month-end charges, the joint account, the schedules &mdash; with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (fifty-eight claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (how money is represented, and what actually differs '
 'between savings and current, come first); then type in the order of Main.java: the three enums, the exception family, '
 'the Money value type, the Txn and Statement records, the Clock, the WithdrawalRule interface with MinBalanceRule and '
 'OverdraftRule, the InterestRule with SimpleInterest and the PromoInterest wrapper, the listener interface, then '
 'Account with its one lock and its single <code>post()</code>, then the two thin subclasses, then Bank with the '
 'ordered locks and the seven-step transfer, then a main with the race. If the hour runs short, the must-write core '
 'is Money, Txn, the WithdrawalRule with its two rules, Account with its lock and <code>post()</code>, and '
 '<code>Bank.transfer</code>; interest, dormancy, statements and listeners come after it. The smallest version of '
 'this prompt is LeetCode 2043, Simple Bank System (reported at Capital One, PayPal, Okta and OpenAI): balances in a '
 '<code>long[]</code> by account number, and every call returns false instead of throwing.</div></div>')

FU = [
("The bank announces a festival bonus: half a per cent on top of the savings rate, for one month only.", "twist", 5,
 "Nothing is edited. PromoInterest holds the rule it decorates (wraps) and a second rule for the bonus, and returns "
 "the sum of what both say. So the base rate and the promotion stay separate objects, and the promotion comes off "
 "again by dropping one wrapper. The bank is handed <code>new PromoInterest(new SimpleInterest(400), 50)</code> for "
 "SAVINGS; rates are in basis points, hundredths of a per cent, so 400 is 4.00% a year and 50 is 0.50%. Nothing else "
 "changes: not Account, not Bank, not the tests. The alternative, an <code>if (festivalMonth)</code> inside "
 "SimpleInterest, is the same feature and a permanent edit to a class that had one job. Because the bonus is a rule "
 "and not a number, handing in <code>new PromoInterest(dailyBalanceRule, dailyBalanceBonus)</code> keeps both halves "
 "on the same basis.",
 sect(src, "final class PromoInterest", "interface FeePolicy")),
("Her salary lands on the 28th. How much interest does she earn for that month?", "functional", 8,
 "The rate is not the interesting part; the <b>basis</b> is. SimpleInterest pays on the balance as it stands when the "
 "batch runs, so INR 1,00,000 that arrived on the 28th earns a whole month: INR 361.64 in the test. A real savings "
 "account is paid on the closing balance of <i>every day</i> (the RBI's rule for Indian banks since April 2010). The "
 "same account then earns INR 65.75, because the money was there for three days. DailyBalanceInterest gets "
 "those daily balances from the ledger, which is exactly why InterestRule is handed the account and not a number. It "
 "needs one binary search per day, since every row already carries the balance after it. Watch the boundary: a "
 "day's closing balance counts only the rows strictly before midnight, so a deposit stamped at exactly 00:00 on the "
 "28th belongs to the 28th, not the 27th. The rule sums the days first and divides once at the end, so the month is "
 "rounded down one time instead of thirty; the fraction of a paisa stays with the bank. Compounding is the same rule "
 "run more often: credit the INTEREST row monthly and the next month\'s daily balances already include it.",
 X("interest on the daily closing balance", "a charge instead of a veto")),
("She fell below the minimum balance. Do not refuse her, charge her. And the shop has sat overdrawn all month.", "twist", 8,
 "A veto and a charge are two different objects, which is why the veto never became an overridden method. "
 "MinBalancePenalty is a MonthlyCharge: at the end of the period it averages the daily closing balances and, if the "
 "average is under the line, charges a share of the shortfall (4% in the test). Two RBI rules shape that number: the "
 "charge must be in proportion to the shortfall, and it may never take a savings balance below zero, so the penalty "
 "caps itself at what the account holds. OverdraftInterest charges its rate on the negative part of each day\'s "
 "closing balance, so a day that ends in the red costs one day\'s interest, not a month\'s. Each charge is a FEE row "
 "that deliberately does <i>not</i> run the withdrawal rules: this is the bank taking its own money, so the penalty "
 "may push the balance further below the minimum. The test shows the same account still refusing a customer\'s "
 "one-rupee withdrawal a moment later. The sweep computes each charge and writes its row in one hold of the "
 "account\'s lock, so a withdrawal cannot slip in between the cap and the row. A transfer fee is different, because "
 "the customer started the transfer: FeePolicy is asked before any money moves, and the source\'s rules must agree "
 "to the amount plus the fee.",
 X("a charge instead of a veto", "a joint account") + "\n"
 "// and the transfer fee, for comparison: asked before any money moves; the rules see amount + fee\n"
 "//     bank.setFeePolicy(new FlatFeeAboveThreshold(Money.inr(\"100000.00\"), Money.inr(\"25.00\")));\n"),
("Sixteen ATMs on one account, and two customers paying each other, all at the same instant. Prove the floor holds and nothing hangs.", "non-functional", 8,
 "The mechanism is the digital wallet page\'s, in one line: the rule checks, the row and the balance all happen inside "
 "one hold of the account\'s lock, and a transfer takes both locks in account-id order, so no two threads can each "
 "hold the lock the other wants. What is worth your time here is the assertion. For one account the arithmetic is "
 "exact: INR 9,000 above the floor, taken INR 100 at a time, is exactly 90 successful withdrawals out of 192 "
 "attempts, whatever order the threads ran in. A single lost update (two threads both writing from the same old "
 "balance) would make it 91. For the transfers the check is that money is conserved: 64 threads fire transfers in "
 "both directions, and the bank\'s total assets must be unchanged to the paise, because a lost credit has no matching "
 "lost debit. The deadlock proof is the timeout on <code>Future.get</code>: a deadlock makes the test hang rather "
 "than fail, so the timeout <i>is</i> the assertion. If asked for another way out of the deadlock: "
 "<code>tryLock</code> with a timeout, then release both, wait a random moment and retry. It works, but under load "
 "the retries can repeat, so the fixed order is the better first answer.",
 T("        // 6. sixteen ATMs on ONE account", "        // 7. sixty-four threads")),
("One lock per account, and two locks for a transfer. Does that scale, or have you serialised the bank?", "non-functional", 4,
 "It scales, and the answer is arithmetic rather than opinion. Inside the lock there are about twelve operations "
 "(move 7 lists them), roughly a microsecond and a half; a transfer is that twice, under two locks. A busy merchant at five postings a second holds "
 "its lock seven and a half microseconds in each second, and even an invented thousand a second is 0.15% busy. The "
 "lock is per account, so the number of accounts is irrelevant. The ladder (slow work outside the lock, then split a "
 "genuinely hot account into k sub-balances, then a conditional UPDATE in a database) is the wallet page\'s, step for "
 "step. The banking-specific note is the batch: interest and the month-end charges hold one account\'s lock at a "
 "time, for microseconds, so end-of-month over fifty million accounts never makes a customer wait longer than that.",
 sect(src, "    final Txn withdraw(Money amount", "    final void checkCanReceive")),
("The destination account is frozen, and you only find out halfway. What is the state of both accounts?", "functional", 8,
 "Exactly what it was, because you never find out halfway: the destination is asked everything that could refuse a "
 "credit &mdash; frozen, closed, wrong currency &mdash; before a single paise leaves the source. The order is the "
 "design, not a detail. If that check throws, no row has been written anywhere, the transfer id is <i>not</i> claimed, "
 "and the caller may retry the same id once the account is unfrozen. A rule saying no has the same shape: the source\'s "
 "rules run inside its own hold before its row is written, so a refusal leaves no row, no paise and no alert. The one "
 "case left is a credit that throws after the debit, which cannot happen here. The code still posts a REVERSAL row "
 "rather than leaving money in mid-air: you undo a ledger by writing the opposite row, never by editing one.",
 T("        // 12. a frozen destination is discovered BEFORE the source is debited", "        // 13. rules compose")),
("The app asks for a balance a thousand times a second, and then wants March\'s statement.", "non-functional", 5,
 "The balance is a stored field written in the same lock hold as the row that changed it, so a read is one field read: "
 "O(1), and it can never disagree with the ledger because the two move together. The statement is the interesting one: "
 "rows are appended in time order and never reordered, so both ends of a window are a binary search and the answer is "
 "a sublist &mdash; O(log n + k), never a scan of a lifetime of history. Opening and closing balances come free, "
 "because every row carries the balance after it. At twenty years of history you stop keeping every row in memory: the "
 "old ones go to cold storage and each month\'s statement is anchored by its opening balance, which is the same "
 "binary-search boundary you already compute. Reads take the lock, which guarantees the reader sees the latest write "
 "(without it, another thread may see an old balance). The day that lock costs anything, make the field "
 "<code>volatile</code>: Money is immutable, so a volatile read always returns a whole, current value, with no lock.",
 sect(src, "    final Statement statement(long fromMs", "    /** A copy of the whole ledger")),
("Mid-round: \"cap ATM withdrawals at INR 3,000 a day.\" And while you are there, KYC.", "functional", 8,
 "One new class and one line, for both. A daily cap is stateful: it has to remember what today already cost, and "
 "that memory has nowhere clean to live if the veto is an overridden method. As a rule object it is a private "
 "counter, updated through the <code>onWithdrawn</code> hook, which only fires after the row is written, so a "
 "refused withdrawal never counts against the cap. It stacks with the minimum balance, because every rule on the "
 "account must agree. Rules see every debit, transfers included; to cap only cash, pass the channel (ATM or "
 "transfer) to <code>check()</code>. A cap over the last 24 hours instead of the calendar day keeps a queue of "
 "(time, amount) and drops the old entries before each check. KYC (the bank\'s identity check) is the same move: a "
 "status on the rule, a cap while the papers are not in order, and nothing in Account or Bank changes. The cap\'s "
 "counter is only touched inside the account\'s lock, so it needs no lock of its own. The KYC status is set by the "
 "back office from outside that lock, so it is <code>volatile</code>: every thread sees the latest value.",
 X("a daily cap on cash", "interest on the daily closing balance") + "\n" + X("KYC --", "a fee on a transfer")),
("A joint account: two owners, and anything over INR 50,000 needs the second signature.", "twist", 10,
 "The only genuinely new state is the set of owners; everything that makes it a joint account is a rule. Below the "
 "threshold a withdrawal simply goes through. Above it, the rule refuses until a second, <i>different</i> owner has "
 "signed for that exact amount: the first owner\'s call parks the request and returns null, and the second owner\'s "
 "call performs the withdrawal. Any other refusal, such as the minimum balance, is thrown, never mistaken for "
 "\"waiting\". The signature is spent through the same <code>onWithdrawn</code> hook the daily cap uses, so one "
 "approval can never pay for two withdrawals. The rule\'s memory of who signed lives under the account\'s lock, like "
 "the balance, so two owners signing at the same instant still give exactly one withdrawal (a test signs 1,000 "
 "amounts from two threads at once). The balance, the ledger, the lock and the posting path are the ones every other "
 "account uses. That is the point of the whole page: a twist that needs a big block of code means the derivation "
 "went wrong.",
 X("a joint account", "a standing instruction")),
("Rent on the first of every month. And then: model a loan.", "twist", 8,
 "Both are schedules that post ordinary transfers, and the interesting part of both is the transfer id. A standing "
 "instruction (a repeating payment the customer set up once) builds its id out of its own name and the period "
 "number. So running the job twice, or on two threads at the same moment, pays each period exactly once, because a "
 "transfer is idempotent by that id. On two servers the ids need one shared store: the unique index in the next "
 "follow-up. A loan is not a new kind of money either: it is an amount owed plus a schedule of instalments, each one "
 "a transfer from the borrower into the loan account with the same id trick. The loan also counts the instalments it "
 "has paid, so a job that runs twice changes neither the money nor the amount still owed. This version uses equal "
 "principal plus interest on the reducing outstanding, so every number stays exact integer paise and the last "
 "instalment absorbs the rounding, closing the loan at exactly zero.",
 X("a standing instruction", "a loan as a schedule") + "\n" + X("a loan as a schedule", "KYC")),
("Persist it. And now there are two branches, on two servers.", "twist", 6,
 "The mechanism is the wallet page\'s. The balance becomes a row behind a repository, and the debit becomes one "
 "conditional <code>UPDATE ... SET paise = paise - ? WHERE id = ? AND paise - ? &gt;= floor</code>, so the database "
 "does the check and the write in one step, as the lock did. The other two standard answers are "
 "<code>SELECT ... FOR UPDATE</code> (lock the row, then check and write) and a version column (write only if the "
 "version is still the one you read). A unique index on the transfer id gives you the same idempotency the receipt "
 "map gives you in memory. The claim of the id, the debit and the credit are one database transaction. If the "
 "debit\'s condition fails, the claim is rolled back with it, so the same id can be retried later "
 "(<code>releaseTransfer</code> stands for that rollback here). Two consequences are specific to a bank. "
 "First, the stored balance stops being the truth: the ledger is, and the balance is a cache you can rebuild by "
 "replaying the rows. Interviewers who say \"ledger\" often mean double entry: every movement is written twice, a "
 "debit on one account and a credit on another, so the whole book always sums to zero. Transfers here already do "
 "that; interest and fees would need the bank\'s own income and expense accounts as their other side. Second, the "
 "month-end batch becomes the hard part rather than the transfer: interest must be computed from each day\'s "
 "closing balances as they stood at a fixed cut-off time, not from rows that are still changing.",
 X("persistence and a second server", "Runs every extension")),
("Where does time come from, and how do you test interest, charges and dormancy without waiting six months?", "design", 3,
 "The bank is handed a Clock and hands it to every account it opens; nothing in the system reads the wall clock inside "
 "a method. A test therefore owns the date: it keeps a one-element array, hands in a lambda that reads it, moves it "
 "forward by a year and asserts that INR 1,00,000 at four per cent earned exactly INR 4,000.00. The amounts are "
 "integer paise, so the assertion is an equality, not a tolerance. If the real clock steps back (a time-server "
 "correction), <code>post()</code> stamps the row with the previous row\'s time instead, so the ledger stays in "
 "order; test 17 moves the clock back an hour to prove it. The same seam drives the interest basis (move the clock "
 "twenty-seven days, deposit, move three more, and the two rules give different answers), dormancy, the month-end "
 "charges, the daily cap and the statement window. It is also why <code>configure</code> refuses to run once an "
 "account exists: every account must hold the same clock.",
 "/** Where time comes from. Injected everywhere, so a test can say \"six months later\" without sleeping. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the bank: handed in with the rules, then given to every account it opens\n"
 "void configure(Map<AccountKind, InterestRule> rules, Clock clock) {\n"
 "    if (!accounts.isEmpty()) throw new IllegalStateException(\"configure before opening accounts\");\n"
 "    interestRules.clear(); interestRules.putAll(rules); this.clock = clock;\n"
 "}\n\n"
 "// in a test: pick the instant, then move it\n"
 "long[] now = { 1_700_000_000_000L };\n"
 "bank.configure(Map.of(AccountKind.SAVINGS, new SimpleInterest(400)), () -> now[0]);\n"
 "SavingsAccount a = bank.openSavings(\"SB-3\", \"c1\", Money.inr(\"100000.00\"), Money.inr(\"0.00\"));\n"
 "now[0] += 365L * 24 * 3600 * 1000;                       // a year later\n"
 "bank.accrueInterest(365);                                // -> exactly INR 4000.00 of interest\n"
 "now[0] += 200L * 24 * 3600 * 1000;                       // and two hundred days of silence\n"
 "bank.markDormant();                                      // -> DORMANT, until the next customer posting\n"),
("Which pattern is where, which SOLID letter is where, and why are Savings and Current subclasses at all?", "design", 8,
 "Each pattern is what a move produced: Strategy is move 3 (the veto, the interest rule, the fee policy), Decorator "
 "is PromoInterest, Observer is the listeners called after the unlock, State is move 6, and the ordered two-lock "
 "acquisition has no pattern name and is the most valuable line in the file. The SOLID letters are the five rows of "
 "move 11. The subclasses survive because earning interest and having an overdraft ceiling are genuinely is-a "
 "differences, but notice how little is left in each: a constructor that wires one rule. The veto itself is "
 "deliberately not an overridden method, because an override expresses one difference and cannot stack with the "
 "second and third. AccountKind stays an enum because it is only a key into the interest rules; a Factory earns its "
 "place the day account kinds arrive as strings from configuration.",
 sect(src, "final class SavingsAccount", "/**\n * The bank: it owns the customers") + "\n"
 "// Strategy: the veto is an object, so vetoes COMPOSE -- which an overridden method cannot do\n"
 "asha.addRule(new MinBalanceRule(Money.inr(\"1000.00\")));\n"
 "asha.addRule(new DailyLimitRule(Money.inr(\"3000.00\")));   // both must agree, at run time\n\n"
 "// Decorator: a bonus on top of a rate nobody edited\n"
 "bank.configure(Map.of(AccountKind.SAVINGS, new PromoInterest(new SimpleInterest(400), 50)), clock);\n\n"
 "// Observer: the account announces; it does not know what an SMS is\n"
 "interface AccountListener { void onPosted(Account account, Txn txn); }\n\n"
 "// State: the life is a fixed set of moves, checked before every write\n"
 "enum AccountStatus { ACTIVE, DORMANT, FROZEN, CLOSED }\n\n"
 "// the line with no pattern name, and the one that matters most\n"
 "Account first = fromId.compareTo(toId) < 0 ? from : to;   // a total order over the ids\n"),
]

build(dict(
    slug="banking", title="Banking System",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 58 failure checks and three thread races pass",
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
