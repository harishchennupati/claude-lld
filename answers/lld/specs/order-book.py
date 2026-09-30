# Order Book / Matching Engine LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"order-book/Main.java").read_text()
ext   = (H/"order-book/Extensions.java").read_text()
tests = (H/"order-book/FailureTests.java").read_text()

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
rows = [("submit",  30, [("an order arrives", "side, price in ticks, quantity"),
                         ("match while it crosses", "best price, then arrival order"),
                         ("print at the maker's price", "shrink it, drop it, prune the level"),
                         ("rest the rest, or kill it", "GTC rests; IOC, FOK, market do not")]),
        ("cancel", 165, [("cancel by id", "a member changes their mind"),
                         ("find it in one hop", "the index says which level"),
                         ("pull it out of its queue", "and prune the level if it empties"),
                         ("tell the tape and the feed", "after the lock, never inside it")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V95", dash=True) + _bx(370, 95, 370, 40, "rejected or killed: the book is byte-identical", "", dash=True)
pf += _tx(88, 266, "read", "var(--acc)", 13)
pf += _tx(175, 266, "at any moment, without walking the orders: what is the best bid and ask?  how deep is the book?  is order X still resting?", "var(--text)", 12, "start")
pf += _tx(615, 305, "many members submit at the same instant: no resting order may ever fill more than it offered, and every lot bought is a lot sold", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 320, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:15:00.000  the book builds", ["ANA rests 200 to buy at 1499.95", "BEN rests 300 behind her, same price",
                                         "DEV offers 400 at 1500.05", "ESH offers 600 at 1500.10",
                                         "quote: 500 @ 1499.95 | 1500.05 @ 400"], False),
      ("09:15:00.412  FIR buys 900", ["a limit buy at 1500.10 sweeps both", "asks: 400 at 1500.05, then 500 of ESH",
                                      "each at the RESTING order's price", "FIR keeps the price improvement",
                                      "ESH still rests 100 at 1500.10"], True),
      ("09:15:01.006  GIR sells 300", ["both bids sit at 1499.95: time decides", "ANA's 200 fills first, she was first",
                                       "then 100 of BEN's 300", "BEN's remaining 200 stays in front",
                                       "two makers, so the tape prints two lines"], True),
      ("09:15:02.310  HAR: all-or-nothing", ["fill-or-kill for 5,000 lots", "a dry run says only 700 are there",
                                             "so it fills nothing at all", "the book is identical, level for level",
                                             "and the reject says why: only 700"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*288
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+137) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+137)
    pe += _card(x, 60, 275, 130, t, lines, acc=acc)
P_EX = _mv(1230, 205, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Take an order: a side, a price in whole ticks, a quantity, a type (limit or market) and a time-in-force.</li>
<li>Match it against the opposite side while the prices cross: best price first, arrival order inside a price.</li>
<li>Print a trade at the <i>resting</i> order's price; shrink the maker, remove it when exhausted, prune an emptied level.</li>
<li>Rest the remainder (good-till-cancelled) or throw it away (immediate-or-cancel, fill-or-kill, market).</li>
<li>Fill-or-kill fills completely or does nothing at all.</li>
<li>Cancel any resting order by id; a cancel that races a fill answers "no", it does not blow up.</li>
<li>Publish every event &mdash; accepted, traded, rested, cancelled, rejected &mdash; to the tape, market data and risk.</li>
<li>Answer the best bid and ask, and the depth of the top few levels, at any moment.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many members submitting at once: no resting order ever fills more than it offered, and every lot bought is a lot sold.</li>
<li>Prices are integer ticks, so comparison is exact: no <code>double</code> anywhere near the matching loop.</li>
<li>Best price is a bounded walk of the ladder (about eight hops on a two-hundred-level book); cancel by id is O(1).</li>
<li>The allocation rulebook is swappable per contract without touching the matching loop.</li>
<li>One source of truth: the book, behind one lock; nothing else may touch a price level.</li>
<li>Nothing half-done: a rejected or killed order leaves the book byte-identical and the member can retry.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds the journal).</li></ul></div></div>
'''

PROMPT = ('"Design the order book and matching engine for one instrument on an exchange. Members send limit and market '
          'orders; the engine matches whatever crosses, prints the trades, and lets a member cancel what has not filled. '
          'I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>An exchange keeps, for each instrument, a list of the orders '
 'nobody has traded with yet: people willing to buy at a price, people willing to sell at a price. That list is the '
 '<b>book</b>. A new order arrives; if it is willing to pay at least what somebody is asking &mdash; the prices '
 '<b>cross</b> &mdash; a trade happens immediately, and what is left of the new order joins the book and waits. Which '
 'resting order gets the trade is not a detail: it is the promise the exchange sells. The promise here is '
 '<b>price-time priority</b>: the best price wins, and among orders at the same price the one that arrived first wins. '
 'A member can cancel anything that has not filled. Everything that happens is published &mdash; to the tape that '
 'prints trades, to the market-data feed that shows the top of the book, to risk. The one thing that must always be '
 'true is arithmetic: a resting order can never give up more lots than it offered, and every lot somebody bought is a '
 'lot somebody else sold.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a '
 '<code>main</code> that rests a few orders, sends a taker through them and prints the trades. The interviewer is '
 'watching for, in this order: the questions you ask before typing (how a price is represented, and whether it is '
 'price-time or pro-rata, are the first two); which classes exist and which one owns the book; an order matching end '
 'to end; what happens when two takers hit the same resting order at the same instant; where the rule that will change '
 '(who gets filled inside a price level) lives, so a pro-rata contract is a new class and not an edit; and what the '
 'book looks like after an order is refused. Then the twists: iceberg orders, stop orders, self-trade prevention, '
 'cancel-replace, surviving a crash, ten thousand symbols.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>One instrument or many?</td><td>One book per symbol, with a thin router in front</td><td>Where the lock lives, and the whole scaling story (moves 4, 8)</td></tr>'
 '<tr><td>How is a price represented?</td><td>Whole ticks in a <code>long</code>: 1500.05 is 150005</td><td>Exact comparison, cheap map keys, no rounding drift (moves 1, 5)</td></tr>'
 '<tr><td>Price-time priority, or pro-rata?</td><td>Price-time now; pro-rata is coming</td><td>The allocation rule behind a one-method interface (move 3)</td></tr>'
 '<tr><td>At a cross, whose price prints &mdash; resting or incoming?</td><td>The resting order\'s</td><td>The aggressor keeps the price improvement; the tape is reproducible (moves 2, 9)</td></tr>'
 '<tr><td>Limit only, or market orders and time-in-force?</td><td>Limit and market; GTC, IOC and FOK</td><td>What happens to the remainder, and the all-or-nothing pre-check (moves 6, 9)</td></tr>'
 '<tr><td>Concurrent submits, or one sequenced stream?</td><td>Concurrent</td><td>One lock per book, and the race is worth showing (moves 4, 7)</td></tr>'
 '<tr><td>Self-trade prevention, iceberg, stop orders?</td><td>Out of scope, named</td><td>Each is one of the five twist moves (move 12)</td></tr>'
 '<tr><td>One process and in memory, or persisted?</td><td>One process, in memory</td><td>No journal yet; a follow-up adds one (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning at the open, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> prices are integer ticks and never a double; priority is price first, then '
 'arrival, and the trade prints at the resting order\'s price; one book and one lock per symbol, in memory, one process; '
 'the sequence number that decides arrival order is stamped by the engine inside the lock, not read from a wall clock. '
 'Named as out of scope: self-trade prevention, iceberg and stop orders, cancel-replace, persistence and replay, '
 'sharding across cores &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "an ORDER arrives and rests at a PRICE LEVEL; the levels make a BOOK; a match prints a TRADE; an ALLOCATOR decides who fills", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 190, "Order", "side, price, qty, remaining", 1), (238, 185, "PriceLevel", "one price, one FIFO queue", 1),
                          (441, 190, "OrderBook", "two ladders + an id index", 1), (649, 200, "MatchingEngine", "the lock, the rules, the seq", 1),
                          (867, 150, "Trade", "a fact, never changes", 0), (1035, 175, "Allocator", "no state: an interface", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state that changes, so it becomes a class.   dashed = a fact that never changes, or a rule with no state at all", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("take an order and match it", "MatchingEngine  (owns the book and the lock)", "engine.submit(order)"),
                                       ("share out one price level", "Allocator  (owns nothing at all: pure)", "allocator.allocate(taker, level)"),
                                       ("pull a resting order out", "OrderBook  (owns the ladders and the index)", "book.cancel(orderId)"),
                                       ("shrink a maker, drop it when done", "PriceLevel  (owns the queue at one price)", "level.reduce(maker, qty)")]):
    y = 20 + k*54
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 254, "a verb whose state is spread over several classes goes to the one that owns all of them: that class becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 273, "and notice what is NOT a verb: a market order is not a third flow, it is a limit order with no price and no right to rest", "var(--muted)", 11)
MV[2] = _mv(1230, 288, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 60, 220, 90, "MatchingEngine", "configure(...) / addListener(...)", acc=True)
for k, (t, sub, impl, isub) in enumerate([("Allocator", "who gets filled inside a level", "PriceTimeAllocator / ProRataAllocator / SelfTradeGuard", "the rulebook of the contract"),
                                          ("BookListener", "who is told, and what about", "ConsoleTape / TopOfBook / RiskMonitor / Journal", "everything downstream of a fill"),
                                          ("Clock", "what instant a trade carries", "System::currentTimeMillis, or a fixed instant", "so a test can assert on it")]):
    y = 24 + k*60
    m3 += _ar("M250 105 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 440, 44, impl, isub) + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 212, "dashed green = handed in. The engine never builds a rulebook, so a pro-rata contract is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 232, "and one rule wraps every other rule: CheckedAllocator(rule) refuses any plan that hands out more lots than exist, including next year's rulebook", "var(--acc)", 11)
MV[3] = _mv(1230, 245, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 200, 44, "taker A", "reads a1: 100 lots left") + _bx(30, 110, 200, 44, "taker B", "reads a1: 100 lots left")
m4 += _bx(360, 70, 180, 44, "a1 resting", "100 lots", acc=True)
m4 += _ar("M230 52 H360 V70") + _ar("M230 132 H360 V114") + _tx(295, 40, "read", "var(--muted)", 10.5) + _tx(295, 160, "read", "var(--muted)", 10.5)
m4 += '<rect x="580" y="20" width="300" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(730, 45, "the gap", RED, 12) + _tx(730, 70, "both read 100, both take 100", RED, 11) + _tx(730, 90, "the venue just sold 200 lots", RED, 11) + _tx(730, 108, "of a 100-lot order", RED, 11)
m4 += _tx(730, 138, "fix: read, decide and write as ONE step", "var(--text)", 11)
m4 += _bx(910, 40, 290, 100, "MatchingEngine.lock", "the plan and the writes: one step", acc=True)
m4 += _tx(1055, 165, "the lock lives where the shared state lives", "var(--muted)", 10.5)
m4 += _tx(1055, 185, "one lock per SYMBOL: INFY and TCS never wait", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is the best bid, the best ask?", "TreeMap&lt;price, PriceLevel&gt;, bids reversed", "O(log P), ~8 hops"),
                                      ("who is next in line at this price?", "LinkedHashMap&lt;orderId, Order&gt;", "O(1), arrival order"),
                                      ("where is order X, so I can cancel it?", "HashMap&lt;orderId, Order&gt; + its level", "O(1)"),
                                      ("how many lots rest at this price?", "a totalQty kept on every add and fill", "O(1), never counted"),
                                      ("how deep is the book, top five?", "the first five entries of the ladder", "O(5)")]):
    y = 20 + k*46
    m5 += _bx(30, y, 360, 38, q, "the question") + _ar("M390 %s H450" % (y+19), True)
    m5 += _bx(450, y, 500, 38, shape, "the shape", acc=True) + _ar("M950 %s H1010" % (y+19), True) + _bx(1010, y, 190, 38, cost, "")
m5 += _tx(615, 268, "the two priorities are two different structures: a SORTED map for price, an INSERTION-ORDERED map for time. Mixing them into one list is the junior answer", "var(--muted)", 11)
MV[5] = _mv(1230, 282, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(30, 30, 110, 38, "NEW", "", acc=True) + _bx(190, 30, 140, 38, "ACCEPTED", "")
m6 += _bx(190, 105, 140, 38, "PARTIALLY", "FILLED") + _bx(400, 30, 120, 38, "FILLED", "") + _bx(400, 105, 120, 38, "CANCELLED", "")
m6 += _bx(30, 105, 110, 38, "REJECTED", "")
m6 += _ar("M140 49 H190", True) + _ar("M85 68 V105", dash=True) + _ar("M260 68 V105", True)
m6 += _ar("M330 42 H400", True) + _ar("M330 124 H400", True) + _ar("M330 118 H350 V58 H400", True)
m6 += _ar("M230 68 V88 H160 V162 H460 V143", True)
m6 += _tx(275, 186, "moveTo() refuses any move that is not drawn here", "var(--muted)", 10.5)
m6 += _tx(275, 204, "a fill that leaves lots over just repeats PARTIALLY_FILLED", "var(--muted)", 10.5)
m6 += '<rect x="600" y="16" width="610" height="196" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(905, 40, "the order of operations when an order arrives, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 take the lock, then validate: symbol, id, quantity, price on the tick -- nothing written",
                       "2 stamp the arrival sequence: one counter, inside the lock, and it IS the book's order",
                       "3 fill-or-kill only: dry-run the same walk against a COPY of the order",
                       "4 match: the allocator decides a plan, the engine applies it, inside one lock",
                       "5 rest the remainder or throw it away, unlock, and only then tell the tape",
                       "a rejected or killed order leaves the book byte-identical and can be retried;",
                       "nothing is published until the book is consistent: the tape can never lead it"]):
    m6 += _tx(615, 64 + k*22, l, "var(--muted)" if k > 4 else "var(--text)", 11, "start")
MV[6] = _mv(1230, 215, m6)

# move 7: what is inside the lock, and ten gateways at the same instant
m7 = _D + _card(30, 20, 545, 150, "inside the lock: about three microseconds",
                ["walk the ladder to the best price: ~8 pointer hops", "ask the allocator for a plan: 1 to 5 resting orders",
                 "shrink each maker, drop the ones that are done", "prune an emptied level: one tree delete",
                 "about forty map and tree operations in all"], acc=True)
m7 += _ar("M575 95 H645", True) + _tx(610, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(645, 20, 555, 150, "outside the lock: microseconds to seconds",
            ["the gateway's decode and pre-trade risk: before submit()", "the tape socket and the market-data fan-out: ~50 us",
             "the journal write: ~5 ms, handed to a queue, never done here", "the member deciding what to send: seconds"])
m7 += _tx(615, 200, "ten gateway threads press submit at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 215, 106, 40, "gateway %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%d" % (k*3)), acc=(k == 9))
m7 += _tx(615, 283, "the tenth waits twenty-seven microseconds for the lock and then fifty for its own tape line: one at a time is true,", "var(--muted)", 11)
m7 += _tx(615, 301, "and nobody can tell, because nothing slow is allowed inside the critical section", "var(--muted)", 11)
MV[7] = _mv(1230, 315, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per book: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of a marketable order: ~40 operations, about 3 us",
                       "a hot NSE symbol at the open: about 2,000 orders a second",
                       "2,000 x 3 us = 6 ms of lock in every second: 0.6% busy",
                       "at 100,000 orders a second into ONE symbol it is 30% busy: climb",
                       "and the lock is per SYMBOL, so 1,200 books never meet at all"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 nothing slow inside the lock", "already done: every listener fires after the unlock"),
                              ("2 shard by symbol", "Exchange already does it: one engine, one lock, per book"),
                              ("3 one writer thread per shard", "orders off a queue: no lock at all, and the stream replays")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("a later order fills before an earlier one", "one queue per price, in arrival order; test 1: early fills, then late"),
                                ("two takers hit the same resting order", "one lock per book; test 7: fifty threads, lots bought == lots sold"),
                                ("an order fills more than it offered", "Order.take() refuses it; test 7: filled + remaining == quantity, always"),
                                ("a fill-or-kill that cannot fill in full", "dry-run the walk first; test 4: the book is identical, level for level"),
                                ("a rulebook that hands out too much", "CheckedAllocator throws before any write; test 8: nothing moved"),
                                ("the tape socket is down", "listeners fire after the unlock, in a try/catch; test 8"),
                                ("a price off the tick, a reused order id", "validated before a single write; test 9: the book is untouched"),
                                ("an amend-down looks like a fill to risk", "shrinkTo lowers the order too; test 6: filled() stays 0")]):
    y = 18 + k*42
    m9 += _bx(30, y, 320, 38, bad, "") + _ar("M350 %s H400" % (y+19), True) + _bx(400, y, 800, 38, fix, "", acc=True)
m9 += _tx(615, 376, "every claim this design makes has a test: FailureTests.java runs nine blocks of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 390, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 850)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface Allocator { List&lt;Allocation&gt; allocate(taker, level); }", None), ("a pro-rata contract is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("configure() wraps every rulebook in new CheckedAllocator(a)", None), ("no rulebook can overfill, ever", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("fire(events) AFTER the unlock, each listener in a try/catch", None), ("a dead tape cannot stall matching", None)],
          [("State", "var(--text)"), ("move 6", None), ("moveTo(next) refuses any edge the state machine does not have", None), ("an illegal move throws, not corrupts", None)],
          [("Command", "var(--text)"), ("move 6", None), ("the Allocation plan is decided in full before a lot moves", None), ("the journal replays it exactly", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("Exchange is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh book in a line", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("engines.computeIfAbsent(symbol, ...) IS the registry", "var(--muted)"), ("it earns the name when contracts differ", "var(--muted)")],
          [("Builder", "var(--muted)"), ("not yet", None), ("six required fields, plus Order.limit() and Order.market()", "var(--muted)"), ("iceberg and stop fields would change that", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("PriceLevel: one queue. OrderBook: sorted lookup. MatchingEngine: the flow and the lock.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("ProRataAllocator is a new file plus one configure() line", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("allocator.allocate(taker, level);  never \"is this the pro-rata one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: every listener method defaults to a no-op", None), ("move 3", None), ("ConsoleTape implements onTrade and nothing else", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("engine.configure(new ProRataAllocator(1));  engine.setClock(() -&gt; t)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "pro-rata, self-trade prevention", "a new class behind Allocator plus one configure line", "", "move 3"),
        ("someone new wants to know", "risk, market data, surveillance", "one more listener; the book and the lock do not change", "", "move 4"),
        ("a new step in a life", "stop orders, parked until triggered", "a trigger table and one more transition; the book is untouched", "", "move 6"),
        ("a new invariant across orders", "iceberg: shown and hidden lots", "both writes inside the SAME lock: all of it, or none of it", "", "move 4"),
        ("state that must outlive the process", "survive a crash; two servers", "journal every command with its sequence number, then replay it", "a fresh engine fed the same commands prints the same tape, trade for trade", "moves 6 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the engine's matching loop, the lock and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: an <b>order</b> arrives and rests at a <b>price level</b>; the levels stacked up make a "
 "<b>book</b>; when two orders cross, a <b>trade</b> prints; an <b>allocator</b> decides which resting order gets it. An "
 "order has a side, a price, a quantity and a remaining quantity, and that last field is the only thing matching ever "
 "changes: a class. A price level is the queue of orders sitting at one price, and it shrinks and empties: a class. The "
 "book is two ladders of those levels plus an index to find an order by id: a class. A trade is a fact &mdash; it "
 "happened, at a price, for a quantity &mdash; and nothing about it ever changes again, so it is a record. And the "
 "allocator has no state at all; it is a calculation, so it is an interface. Notice what is <i>not</i> a class: a "
 "\"market order\" is not a second kind of thing, it is an order with no price and no right to rest.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Share out one price level\" touches nothing: it reads a queue and a quantity and returns a plan, so it belongs to a "
 "pure rule, <code>allocator.allocate(taker, level)</code>. \"Shrink a maker and drop it when it is done\" touches the "
 "queue at one price, so it belongs to the level: <code>level.reduce(maker, qty)</code>. \"Pull a resting order out\" "
 "touches the ladder and the id index, which only the book sees: <code>book.cancel(orderId)</code>. And \"take an order "
 "and match it\" touches all of them at once, plus the sequence number and the listeners, so it belongs to the one class "
 "that owns everything: <code>engine.submit(order)</code> is the orchestrator. That is also the class that will own the "
 "lock, which is not a coincidence &mdash; the orchestrator and the lock owner are the same class for the same reason.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Who gets filled inside a price level will change: equities are first-come-first-served, but plenty of futures and "
 "options contracts hand every resting order a slice proportional to its size, and the interviewer will say so in the "
 "fiftieth minute. Who is told about a fill will change: a tape today, market data and risk and a journal tomorrow. What "
 "instant a trade carries will change the moment you try to test it. Each becomes a one-method (or all-default) "
 "interface the engine is <i>given</i> and never builds. This is where the patterns come from, not the other way round: a "
 "swappable rulebook behind an interface is <b>Strategy</b>; a rule that wraps another rule and adds a guarantee is "
 "<b>Decorator</b>, and here it is the one that matters &mdash; <code>CheckedAllocator</code> wraps every rulebook the "
 "engine is handed and throws if a plan gives a resting order more lots than it is offering, so a pro-rata class written "
 "next year cannot sell stock that does not exist. An engine that announces \"a trade printed\" without knowing what a "
 "tape is, is <b>Observer</b>. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two members hit the same resting order at the same instant. Both read that it has a hundred lots left, both decide to "
 "take a hundred, both write. The order's remaining quantity goes to minus a hundred, or to zero twice over, and the "
 "exchange has just printed two hundred lots of trade against a hundred-lot order: it sold stock that never existed, and "
 "the tape and the book now disagree forever. So reading the level, deciding the plan and writing the result must be one "
 "step, in the class that owns all of it: the engine. Note what a compare-and-swap cannot do here. A CAS makes one word "
 "atomic, and there is no single word in this invariant &mdash; one match mutates a maker, a level's queue and its "
 "cached total, the ladder, the id index and the taker. A lock, or a single writer thread, is the honest answer at this "
 "size. The lock is per <i>symbol</i>, which is the whole scaling story: INFY and TCS never wait for each other.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers fast.",
 "There are two priorities here and they want two different structures, which is the whole trick. Price priority: \"what "
 "is the best bid?\" is a sorted map from price to level, with the bid map's comparator reversed so both ladders are "
 "read front to back; <code>firstEntry()</code> is a walk to the leftmost node, so about eight pointer hops on a "
 "two-hundred-level book, and you can cache the head if you ever need it to be free. Time priority: \"who is next in "
 "line at this price?\" is a <code>LinkedHashMap</code> keyed by order id &mdash; iteration stays arrival order, and "
 "removing from the middle is O(1), which matters because the thing a live book does most is cancel. \"Where is order "
 "X?\" is a hash map from id to order, so a cancel never scans. \"How many lots rest at this price?\" is a running "
 "total kept on the level, so a quote and a depth ladder never add a queue up. Keeping one flat list and scanning it for the best price is the junior "
 "answer, and it is O(n) on the hottest path in the building.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An order is NEW until the engine looks at it, then either REJECTED (a price off the tick, a reused id) or ACCEPTED. "
 "From there it is PARTIALLY_FILLED while it still has lots left, FILLED when it has none, or CANCELLED &mdash; by the "
 "member, or because its own time-in-force threw the remainder away. <code>moveTo()</code> refuses any move that "
 "diagram does not have, so a bug shows up as an exception rather than as a corrupt book. Writing the states down forces the question "
 "the interviewer will ask: what if the order cannot be filled? The answer is an order of operations. Take the lock, "
 "then validate, writing nothing: the reused-id check reads a set another thread can write, so it has to be inside, "
 "though the cheap field checks could run in the gateway first. Stamp an arrival sequence &mdash; one counter, incremented inside the lock, so "
 "it is both the order's place in the queue and the tape's line number. For a fill-or-kill, dry-run the same walk "
 "against a <i>copy</i> of the order, so all-or-nothing stays honest even after somebody swaps the rulebook. Then match: "
 "the allocator decides a plan, the engine applies it. Then the remainder, the unlock, and only then the tape. A "
 "rejected or killed order leaves the book byte-identical.", 6),
("Move 7: yes, the lock makes one symbol's orders happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every order takes the book's lock, is the exchange now a "
 "queue? It is, for about three microseconds, and only for that one symbol. Inside the lock there is a walk down the "
 "ladder to the best price (about eight pointer hops), one call to the allocator producing a plan of one to five lines, "
 "a shrink of each maker with the exhausted ones dropped, and a tree delete if a level emptied: roughly forty map and "
 "tree operations. Everything slow is outside it. The gateway's protocol decode and pre-trade risk happen before "
 "<code>submit</code> is called at all. The tape socket, the market-data fan-out and the journal all happen after the "
 "unlock, each listener inside a try/catch, so a dead socket cannot stall matching. So when ten gateway threads press "
 "submit at the same instant, the tenth waits about twenty-seven microseconds for the lock and then fifty for its own "
 "tape line.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Say the number before you name the ladder. Two thousand orders a second against a lock held three microseconds is "
 "six milliseconds of lock in every second: the book is busy six tenths of one per cent, and two writers collide "
 "roughly never. A hundred thousand orders a second into <i>one</i> symbol makes it thirty per cent busy, and thirty "
 "per cent is where waiting stops being free &mdash; that is the number that says climb, and you should say it out "
 "loud before you climb anything. The three rungs in the picture are in cost order, and the first two are already "
 "built: nothing slow is inside the critical section, and <code>Exchange</code> gives one lock per symbol for free, so "
 "twelve hundred books across forty cores never contend. The third rung is what real venues run &mdash; one writer "
 "thread per shard, taking orders off a ring buffer &mdash; and it deletes the lock entirely while making the stream "
 "deterministic for replay. Only who calls <code>submit</code> changes.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The table is the row-by-row version. Three of the rows are worth a sentence more. The first is the bug that gets a "
 "venue into the newspapers: a member who queued first watches a later order fill. It is not a crash, it is a silently "
 "wrong answer, which is why test 1 rests two orders at the same price and then asserts on the order id inside each "
 "printed trade. The rulebook row is the one people forget: <code>CheckedAllocator</code> throws before the first lot "
 "moves, and the test hands the engine a deliberately broken allocator to show the book came out untouched. And the "
 "amend row is the one this page got wrong on its first pass &mdash; shrinking a resting order used to leave "
 "<code>filled()</code> claiming lots that never traded, which risk and the journal would both have believed. Each of "
 "these is a few lines in FailureTests.java; a design that cannot show its tests is a claim.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the defence, one line each. Two rows are worth more than a line. <b>Decorator</b> appears twice on the "
 "same seam: <code>CheckedAllocator</code> adds an invariant every rulebook must obey, and the self-trade guard in "
 "Extensions.java adds a business rule to the same interface &mdash; two different kinds of thing wrapping cleanly is "
 "the evidence the seam was cut in the right place. <b>Command</b> is hiding inside move 6: the allocator returns a "
 "<i>plan</i> that is decided in full before a single lot moves, and that is exactly what lets the journal replay it. "
 "The three grey rows carry as much weight as the five: Singleton earned nothing, and Factory and Builder are honest "
 "\"not yets\" with the condition stated. A pattern without a move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is not a list to recite; it is the check that the moves did their job, and the table is the whole check. Two "
 "rows are worth saying out loud in the room. I, because it is the one most designs fail: the listener interface has "
 "six methods and every one defaults to a no-op, so the tape implements exactly one of them and a bare lambda is a "
 "legal listener. And D, because it is the one you can prove: the engine is handed its allocator and its clock rather "
 "than building them, which is exactly why a test can give it a clock that says last Tuesday and a rulebook that "
 "deliberately over-allocates.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The picture is the whole answer; what it does not show is the cost, so say that. Four of the five twists cost one "
 "class and not one character of the matching loop. The stop order is the one people get wrong in the room: it is not "
 "in the book at all, so it changes nothing about matching &mdash; it is a side table plus a listener on trades, and "
 "the parked order touches the book only on the tick it fires. Persistence is the only twist that reaches into the "
 "flow, and even then what is written down is the <i>commands</i> and not the book, which is replayable only because "
 "nothing in matching reads a wall clock or a random number. Page 05 has the working code for all five.", 12),
]
DERIVATION_LEAD = ("Twelve moves in this order, and the class diagram, the lock, the tests, the patterns and the answer "
 "to every twist fall out of them; nothing is named before the move that produced it. On this problem move 4 is the one "
 "that decides whether you pass, because the race here is not a lost update &mdash; it is an exchange printing trades "
 "against stock that was never there.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the callers, the listeners, the value helpers
put("exch", 10, 20, 240, "Exchange", ["engines: Map&lt;symbol, Engine&gt;", "tickSize / lotSize: long"],
    ["book(symbol): MatchingEngine", "addDefaultListener(l)"])
put("listener", 10, 150, 240, "BookListener", [], ["onAccepted(o) / onTrade(t)", "onRested(o, q) / onCancelled(..)", "onRejected(id, why) / onQuote(q)"], "interface")
put("tape", 10, 250, 240, "ConsoleTape", [], ["onTrade(t): keeps the tape", "printed(): List&lt;Trade&gt;"])
put("l1", 10, 340, 240, "TopOfBook", [], ["onQuote(q): keeps the last", "last(): Quote"])
put("clock", 10, 430, 240, "Clock", [], ["nowMs(): long"], "interface")
put("ticks", 10, 505, 240, "Ticks", [], ["of(\"1500.05\"): long", "fmt(150005): String"])
# centre column: the aggregate root and what it owns
put("engine", 300, 20, 340, "MatchingEngine",
    ["symbol: String,  book: OrderBook", "lock: ReentrantLock", "listeners: List&lt;BookListener&gt;",
     "usedIds: Set&lt;String&gt;", "allocator: Allocator,  clock: Clock", "tickSize / lotSize: long",
     "seq: long   (guarded by the lock)"],
    ["configure(allocator) / setClock(c)", "addListener(l)", "submit(order): SubmitResult", "cancel(orderId): boolean",
     "amendDown(orderId, newQty)", "quote() / depth(side, n)", "resting(id) / restingQty(side)"])
put("book", 300, 320, 340, "OrderBook",
    ["symbol: String", "bids: TreeMap&lt;price, Level&gt;  desc", "asks: TreeMap&lt;price, Level&gt;  asc", "byId: Map&lt;orderId, Order&gt;"],
    ["ladder(side) / best(side)", "rest(o) / cancel(id) / forget(id)", "crosses(taker, price): boolean",
     "pruneIfEmpty(side, price)", "quote() / depth(side, n)", "totalQty(side): long"])
put("level", 300, 560, 340, "PriceLevel",
    ["priceTicks: long", "fifo: LinkedHashMap&lt;id, Order&gt;", "totalQty: long   (kept, not counted)"],
    ["add(o) / remove(id) / find(id)", "reduce(maker, qty) / shrink(o, q)", "queue(): List&lt;Order&gt;  arrival order",
     "totalQty() / orderCount() / isEmpty()"])
# third column: the order and the value records
put("order", 690, 20, 250, "Order",
    ["id / symbol / memberId", "side / type / tif", "limitTicks / qty: long", "remaining: long  (mutable)",
     "seq: long", "status: OrderStatus"],
    ["limit(...) / market(...)", "take(qty) / shrinkTo(q)", "moveTo(status)", "filled(): long", "stamp(seq)"])
put("trade", 690, 270, 250, "Trade",
    ["seq / priceTicks / qty", "buyOrderId / sellOrderId", "takerSide: Side", "atMs: long"], ["text(): String"])
put("alloc", 690, 420, 250, "Allocation", ["makerOrderId: String", "qty: long"], [])
put("result", 690, 500, 250, "SubmitResult",
    ["orderId / status", "filledQty / restingQty", "trades: List&lt;Trade&gt;", "rejectReason: String"], [])
put("quote", 690, 600, 250, "Quote", ["bidTicks / bidQty: long", "askTicks / askQty: long"], [])
put("rung",  690, 682, 250, "Rung",  ["priceTicks / qty / orders"], [])
# fourth column: the enums, then the rulebook interface and its implementations
put("side", 960, 20, 260, "Side", ["BUY, SELL  |  opposite()"], [], "enum")
put("otype", 960, 90, 260, "OrderType", ["LIMIT, MARKET"], [], "enum")
put("tif", 960, 160, 260, "TimeInForce", ["GTC, IOC, FOK"], [], "enum")
put("status", 960, 230, 260, "OrderStatus",
    ["NEW, ACCEPTED,", "PARTIALLY_FILLED, FILLED,", "CANCELLED, REJECTED"], ["canMoveTo(next): boolean"], "enum")
put("allocator", 960, 380, 260, "Allocator", [], ["allocate(taker, level)", "  : List&lt;Allocation&gt;"], "interface")
put("pt", 960, 480, 260, "PriceTimeAllocator", [], ["walk the queue in", "arrival order until full"])
put("checked", 960, 570, 260, "CheckedAllocator", ["base: Allocator (wrapped)"], ["allocate(...): refuses", "a plan that overfills"])

def stub(x, y1, y2):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x, y1, x, y2)

EDGES = [
 # the two allocators implement the interface; the checked one wraps whatever it was given
 ln(B["pt"]["t"], B["allocator"]["b"], "inherit"),
 ln((960, 610), (950, 435), "inherit", "", [(945, 610), (945, 435)]),
 ln((1220, 595), (1220, 435), "assoc", "", [(1238, 595), (1238, 435)]),
 _tx(1240, 762, "CheckedAllocator wraps whatever rulebook it was handed", "var(--muted)", 10.5, "end"),
 # the listeners implement the interface
 ln(B["tape"]["t"], B["listener"]["b"], "inherit"),
 stub(130, 340, 320),
 # the engine owns the book, the book owns the levels, a level queues orders
 ln(B["engine"]["b"], B["book"]["t"], "compose", "owns the book"),
 ln(B["book"]["b"], B["level"]["t"], "compose", "one per price"),
 ln(B["level"]["r"], (690, 190), "assoc", "", [(665, 640), (665, 190)]),
 # the exchange owns one engine per symbol; the engine is handed its rules and tells its listeners
 ln(B["exch"]["r"], (300, 60), "compose", ""),
 ln((300, 100), (250, 200), "notify", "", [(272, 100), (272, 200)]),
 ln((300, 130), (250, 455), "inject", "", [(262, 130), (262, 455)]),
 ln((640, 250), (960, 405), "inject", "", [(952, 250), (952, 405)]),
 _tx(946, 264, "the rulebook, handed in", "var(--acc)", 10.5, "end"),
 # the engine's inputs and outputs
 ln((640, 90), B["order"]["l"], "assoc", ""),
 ln((640, 120), (690, 300), "assoc", "", [(672, 120), (672, 300)]),
 ln((640, 150), (690, 545), "assoc", "", [(680, 150), (680, 545)]),
 ln((640, 240), (690, 633), "assoc", "", [(686, 240), (686, 633)]),
 ln((640, 500), (690, 707), "assoc", "", [(676, 500), (676, 707)]),
 # an order points at its enums
 ln((940, 60), B["side"]["l"], "assoc"),
 ln((940, 90), (960, 115), "assoc", "", [(950, 90), (950, 115)]),
 ln((940, 120), (960, 185), "assoc", "", [(948, 120), (948, 185)]),
 ln((940, 150), (960, 285), "assoc", "", [(946, 150), (946, 285)]),
 # a plan is a list of allocations
 ln(B["allocator"]["l"], (940, 445), "assoc", ""),
 _tx(950, 408, "a plan", "var(--muted)", 10.5, "end"),
]
UMLSVG = uml_svg(1260, 820, EDGES, legend_y=792)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed list '
 'of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the exchange owns one engine per symbol, the engine owns the order book, the book owns '
 'its price levels. Plain arrow = references. Dashed green = handed in through <code>configure()</code> or '
 '<code>setClock()</code>. Dotted blue = notifies. <b>Where state lives:</b> a price level owns the queue at one price '
 'and the running total of what is resting there; the order book owns the two ladders and the id index and nothing else; '
 'the matching engine owns the book, the one lock, the sequence counter, the handed-in rulebook and the listeners, and it '
 'is the only class that writes anything; an order owns its own remaining quantity and its status, and the allocator owns '
 'nothing at all, which is why one instance can serve every book on the exchange. Notice what is <i>not</i> here: no '
 'Trade store, because a trade is published and gone, and no BestBid field, because the best bid is a question the ladder '
 'already answers.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (nine blocks of claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (how a price is represented, and price-time versus '
 'pro-rata, come first); then type in the order of Main.java: the four enums, the Ticks helpers, Order with its '
 '<code>take</code> and <code>moveTo</code>, the records (Trade, Allocation, SubmitResult, Quote), PriceLevel, '
 'OrderBook, the Allocator interface with price-time and the checked wrapper, the BookListener interface with the tape, '
 'then MatchingEngine with its lock and the order of operations at submit, then the Exchange router, then a main that '
 'rests a ladder, sweeps it and finishes with fifty threads.</div></div>')

FU = [
("Walk me through matching one order, level by level. A 250-lot sell arrives; the book has 100 lots bid at 100.05 "
 "and two 100-lot bids at 100.00, the first of which queued earlier.", "functional", 8,
 "The loop takes the best price on the opposite ladder, checks it still crosses, asks the allocator who at that price "
 "gets filled, applies that plan, and then steps to the next price. Here: the best bid is 100.05 and the sell at "
 "100.00 crosses it, so the single order there gives up 100 lots, the level empties and the book prunes it. The next "
 "price is 100.00, which still crosses; the allocator walks that level's queue in arrival order and returns 100 lots "
 "to the order that queued first and 50 to the one behind it. The taker now has nothing left, the loop ends, and three "
 "trades print &mdash; at 100.05, 100.00 and 100.00, always the <i>resting</i> order's price. Two details are the "
 "whole answer: each price is visited exactly once, because the next step is <code>higherEntry</code> of the price "
 "just looked at, so the loop cannot spin on a level the allocator declined to fill; and deciding the plan and "
 "applying it happen inside the same lock, so nothing can slip in between the decision and the write.",
 sect(src, "private List<Trade> match", "private long fillable")),
("Mid-round: \"this contract allocates pro-rata, so a 500-lot taker splits across resting size, not arrival time.\"", "twist", 10,
 "The allocation rule is already an interface, so this is one new class and one line: <code>engine.configure(new "
 "ProRataAllocator(1))</code>. It gives each resting order a slice proportional to its size, floors the slice because "
 "lots are whole numbers, drops slices below a minimum lot, and hands the dust that flooring left down the queue in "
 "arrival order &mdash; so time priority survives as the tie-break. Against 100 and 900 lots resting, a 500-lot taker "
 "fills 100 then 400 under price-time and 50 then 450 under pro-rata. The engine's matching loop does not change one "
 "character, and that is only cheap because <code>allocate()</code> is pure: it decides a plan and mutates nothing, so "
 "the engine can check the plan before applying it.",
 X("pro-rata", "self-trade prevention")),
("Two takers hit the same resting order at the same instant. Prove you cannot sell stock that is not there.", "non-functional", 10,
 "The race lives between reading a resting order's remaining quantity and writing the new one. Everything from the "
 "validation through the allocator's plan to the last lot applied happens inside one lock held by the engine, so no "
 "other writer can run in that gap; <code>Order.take()</code> is the second line of defence, refusing any fill larger "
 "than what is left. The proof is arithmetic, not a count: fifty threads wait on one latch, all fifty submit crossing "
 "orders into one book, and the test then adds up the lots bought and the lots sold. They must be equal, because every "
 "trade adds the same quantity to both. It also checks that filled + remaining equals the original quantity for every "
 "order, that the tape printed exactly those lots and no more, and that the id index and the price ladders still agree "
 "&mdash; which is what catches a cached level total that drifted.",
 T("        // 7. the race:", "        // 8. a listener")),
("One lock per book. Does that scale, or have you serialised the exchange?", "non-functional", 5,
 "It scales, and the way to answer is to name what breaks first. The lock holds about forty map and tree operations, "
 "roughly three microseconds, so one book is six tenths of one per cent busy at two thousand orders a second and "
 "thirty per cent busy at a hundred thousand &mdash; and no single symbol sees a hundred thousand. What breaks first "
 "is not the lock, it is the fan-out after it: <code>fire()</code> calls every listener one at a time on the "
 "submitting thread, so one slow consumer adds its own latency to every order on that book. The fix for that is a "
 "queue per listener, not a bigger lock. For many symbols the router is the answer &mdash; one engine and one lock "
 "each, so twelve hundred books never contend &mdash; but do not give each book a thread: twelve hundred threads on "
 "forty cores is a context-switch bill. Run a small pool of writer threads with each symbol pinned to exactly one, "
 "which is the third rung of move 8 and also gives replay the deterministic stream it needs. That rung is where "
 "back-pressure becomes a real answer too: the writer's inbox is a bounded queue, and a full inbox rejects the order "
 "and tells the gateway to slow down &mdash; a far better failure than an unbounded queue quietly growing until the "
 "process dies.",
 X("the single writer", "the race")),
("A fill-or-kill arrives that the book cannot fill. What is the state of the book afterwards?", "functional", 10,
 "Exactly what it was, level for level and lot for lot. The all-or-nothing decision happens before a single lot moves: "
 "<code>fillable()</code> runs the same walk down the same ladder with the same allocator, but against a <i>copy</i> of "
 "the order, so it mutates nothing. If the copy could not have been filled completely, the real order is cancelled with "
 "a reason and the book is untouched. Doing it as a dry run of the real walk &mdash; rather than adding up level totals "
 "&mdash; is what keeps it honest when somebody swaps in pro-rata or a self-trade guard that would have skipped half "
 "the level. Everything else in submit follows the same rule: every check runs before the first write, and what comes "
 "after the checks is arithmetic that cannot fail half way. (The checks are inside the lock, because the reused-id "
 "check reads a set another thread can write; only the cheap field checks could move out to the gateway.) The "
 "alternative &mdash; match first, roll back after &mdash; is machinery you should refuse out loud.",
 sect(src, "private SubmitResult submitLocked", "private SubmitResult settle")),
("The hot path is best bid, best ask, and cancel by id. Make them fast, and say the cost of each.", "non-functional", 5,
 "Best bid is <code>firstEntry()</code> on a <code>TreeMap</code>: O(log P), about eight pointer hops on a "
 "two-hundred-level book, and cacheable if you ever need it free. Cancel is two O(1) lookups &mdash; the id index "
 "gives the order, the order's own price gives the level, and a <code>LinkedHashMap</code> removes from the middle "
 "without shifting anything &mdash; plus O(log P) to drop the level if that emptied it. That middle removal is the "
 "reason for the LinkedHashMap rather than an ArrayDeque, because cancels are the most common thing a live book does: "
 "on a real venue most orders are cancelled, not traded. Put it together and one <code>submit</code> costs O(log P) to "
 "find the first price, one step per level it eats, and one line per maker it consumes &mdash; two or three makers in "
 "practice, never the size of the book. Nothing here ever walks the orders to answer a question.",
 sect(src, "final class PriceLevel", "interface Allocator {")),
("\"Add iceberg orders: show a hundred lots of ten thousand at a time.\"", "twist", 10,
 "An iceberg is not a new kind of order in the book. It is a small child order that keeps coming back: a listener "
 "watches the tape, and when the visible slice is gone it submits the next slice at the same price. The new slice joins "
 "the <i>back</i> of the queue, which is the price a hidden order pays for hiding, and it is the behaviour real venues "
 "have. In the demo a thousand lots shown a hundred at a time takes a 250-lot buy and comes back showing fifty with "
 "seven hundred still hidden. The reference version lives entirely on top of the public API, which is the point worth "
 "making; a production engine does the refresh inside the lock instead, so that no other order can slip in between the "
 "slice emptying and the next one arriving.",
 X("iceberg", "stop orders")),
("\"Support stop and stop-limit orders.\"", "twist", 5,
 "A stop order is not in the book at all; it is parked in a side table until the tape prints through its trigger price, "
 "and only then is it submitted as an ordinary market or limit order. The table is two sorted maps &mdash; buy stops "
 "fire when the last price rises to the trigger, sell stops when it falls to it &mdash; so finding everything that just "
 "fired costs the number that fired, not the number parked. The trigger is driven by a <code>BookListener</code> on "
 "trades, so it runs after the unlock and cannot recurse into a book that is mid-match. Two things to say out loud: a "
 "stop cascade can move the price further and fire more stops, which is why venues add price bands; and because stops "
 "are invisible, they are not liquidity, however much the table looks like a book.",
 X("stop orders", "cancel-replace")),
("\"A member must never trade against their own resting order.\"", "twist", 5,
 "Self-trade prevention is a rule about who may fill, so it is another allocator that wraps one &mdash; the same "
 "Decorator seam the checked wrapper uses. It takes the plan the real rulebook produced, drops the lines whose maker "
 "belongs to the same member as the taker, and hands the freed lots to the next orders in the queue, counting what it "
 "skipped for surveillance. That is the SKIP policy, which is the common venue default. CANCEL_NEWEST and CANCEL_OLDEST "
 "cannot live in a pure allocator, because they remove an order from the book; they belong in the engine, consulted at "
 "the same point. The interaction worth naming: because fill-or-kill dry-runs through the same allocator, a member "
 "whose own orders make up the level gets the right answer for free.",
 X("self-trade prevention", "iceberg")),
("A member wants to change a resting order. Do they keep their place in the queue?", "twist", 5,
 "Only if they are giving something up. Shrinking the quantity keeps queue place, because the order object never leaves "
 "its queue: <code>amendDown</code> lowers the remaining quantity and the level's running total in place, under the "
 "lock. Raising the quantity or moving the price is a cancel and a new order, and the new order joins the back &mdash; "
 "otherwise you could buy priority by queueing a small order early and growing it, which is exactly what the rule "
 "exists to stop. One trap worth saying out loud: shrinking must lower the order&#39;s <i>quantity</i> too, not just "
 "what is left of it, or <code>filled()</code> starts reporting lots that never traded and risk and the journal both "
 "believe it &mdash; block 6 of FailureTests asserts <code>filled() == 0</code> after an amend. The reference code "
 "returns which of the two things happened in the words a trader would use, and the demo shows the order that raised "
 "its quantity losing the next fill to the one behind it.",
 X("cancel-replace", "the journal") + "\n" + sect(src, "boolean amendDown", "private void fire")),
("\"The book must survive a crash.\"", "twist", 10,
 "Write down the commands, not the book. Every accepted order and every cancel is journalled with the sequence number "
 "the engine gave it, and a replay feeds those commands into a fresh engine and gets the same trades, in the same "
 "order, because nothing in matching reads a wall clock or a random number &mdash; the clock is injected and only "
 "stamps a trade's timestamp, never a decision. The demo proves it: the live tape and the replayed tape are identical, "
 "trade for trade. Two things to say. The journal write must not be inside the lock, so it is a hand-off to a queue and "
 "a slow disk stalls nothing. And for the log to be replayable the commands must be recorded in the same order the "
 "engine applied them, which a single writer thread gives you for free and is the third rung of the ladder from move 8.",
 X("the journal", "risk")),
("Somebody new wants to know: risk, market data, surveillance. What does it cost?", "twist", 5,
 "One class each, and nothing else moves. The listener interface has six methods and all of them default to a no-op, so "
 "a consumer implements only what it cares about: the tape takes onTrade, the level-1 feed takes onQuote, the risk "
 "monitor takes onAccepted to learn who owns which order and onTrade to move their position. They are called after the "
 "unlock, one at a time, each inside a try/catch, so a dead socket cannot stall matching &mdash; the failure test "
 "installs a listener that throws on every event and shows the trade still happening. The honest caveat: a listener "
 "sees events after the fact, so it can alarm but it cannot stop a trade. Real pre-trade risk sits in front of the "
 "engine, in the gateway, where it can still say no. The same seam is where the numbers you will be asked for come "
 "from: time waited for the lock, time held, orders and trades a second, and how long each listener took &mdash; a "
 "listener is the only place a matching engine can be measured without slowing it down.",
 X("risk", "the single writer")),
("Where do the timestamp and the sequence number come from, and how do you test them?", "design", 3,
 "They come from two different places on purpose. The sequence number is the engine's own counter, incremented inside "
 "the lock, so it is both an order's place in the arrival queue and the tape's line number, and it is the reason a "
 "replay can be ordered exactly. The timestamp comes from an injected <code>Clock</code>, and nothing else in the "
 "system reads the wall clock, so a test hands in an instant and asserts on the trade that comes out. That separation "
 "is what makes time priority immune to clock skew: two orders a nanosecond apart are ordered by a counter, not by two "
 "machines' opinions of the time.",
 "/** Where time comes from. Injected, so a test can stamp a trade with any instant it likes. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the engine: handed in, defaulted, never read from the wall clock inside a method\n"
 "private volatile Clock clock = System::currentTimeMillis;\n"
 "void setClock(Clock c) { clock = c; }\n\n"
 "// the arrival stamp is NOT the clock: it is a counter incremented inside the lock\n"
 "private long seq;                                      // guarded by lock\n"
 "taker.stamp(++seq);                                    // the order's place in the queue\n"
 "Trade t = new Trade(++seq, symbol, level.priceTicks(), q, buyId, sellId, taker.side(), clock.nowMs());\n\n"
 "// in a test: pick the instant, then assert on the trade\n"
 "engine.setClock(() -> 1_700_000_000_000L);\n"
 "SubmitResult r = engine.submit(Order.limit(\"clocked\", \"INFY\", \"DEV\", Side.BUY, Ticks.of(\"100.00\"), 100));\n"
 "assert r.trades().get(0).atMs() == 1_700_000_000_000L;\n"),
("Market orders, immediate-or-cancel, and whose price prints. Walk me through the remainder.", "functional", 5,
 "What did not fill is decided in one small method. If the order has nothing left it is FILLED. If it is a market order, "
 "or its time-in-force is not good-till-cancelled, the remainder is thrown away and the order ends CANCELLED with its "
 "fills reported &mdash; a market order never rests, which is why a market order into an empty book fills nothing and "
 "leaves nothing behind. Otherwise the remainder joins the back of its price queue and the order is PARTIALLY_FILLED if "
 "anything traded. The price question is separate and is the one juniors get wrong: every trade prints at the "
 "<i>resting</i> order's price, so a buyer willing to pay 1500.10 who finds an offer at 1500.05 pays 1500.05. The "
 "aggressor earns the improvement, it is the rule on every lit venue, and it makes the tape reproducible from the "
 "commands.",
 sect(src, "private SubmitResult settle", "private String validate")),
("Name the patterns you used. And why is the order type an enum rather than a subclass of Order, when a class per "
 "type would look cleaner?", "design", 8,
 "The patterns are on page 02, move 10, each named against the move that produced it: Strategy and Decorator on the "
 "<code>Allocator</code> seam, Observer on <code>BookListener</code>, State inside <code>moveTo</code>, Command in the "
 "plan the allocator hands back. The enum question is the better one, and the answer is to count the differences. A "
 "limit order and a market order differ in exactly two behaviours &mdash; whether a price can stop them crossing, and "
 "whether the remainder is allowed to rest &mdash; and both are one line, in <code>crosses()</code> and in "
 "<code>settle()</code>. A subclass per type would spread those two lines across two files and then push every other "
 "class into asking which subclass it is holding; the enum keeps the difference where the difference is used, and a "
 "third type is one more arm of a switch. The rule for when that flips: the day a type needs its own <i>state</i> "
 "&mdash; a stop price, a display quantity, a peg offset &mdash; the enum stops paying and a subclass earns it. "
 "Factory and Builder pass the same test and fail it today: <code>computeIfAbsent</code> is already the registry, so "
 "Factory earns the name when each contract carries its own rulebook from configuration, and six required fields with "
 "two named static methods are enough until those extra fields arrive.",
 sect(src, "static boolean crosses", "void rest(Order o)") +
 "\n// ...and the only other place the type is read, in settle(): whether the remainder may rest\n"
 "if (taker.type() == OrderType.MARKET || taker.tif() != TimeInForce.GTC) {\n"
 "    long killed = taker.remaining();\n"
 "    taker.moveTo(OrderStatus.CANCELLED);                 // a market order never rests\n"
 "    events.add(l -> l.onCancelled(taker, killed));\n"
 "    return new SubmitResult(taker.id(), OrderStatus.CANCELLED, filled, 0, List.copyOf(trades), null);\n"
 "}\n\n"
 "// two lines of difference, so the difference is an enum, not a hierarchy\n"
 "enum OrderType { LIMIT, MARKET }\n\n"
 "// Factory: not yet. The registry is already here; it earns the name when contracts carry their own rulebook\n"
 "return engines.computeIfAbsent(symbol, s -> {\n"
 "    MatchingEngine e = new MatchingEngine(s, tickSize, lotSize);\n"
 "    for (BookListener l : defaults) e.addListener(l);\n"
 "    return e;\n"
 "});\n\n"
 "// Builder: not yet. Six required fields is a constructor plus two named static factory methods\n"
 "Order.limit(\"b1\", \"INFY\", \"ANA\", Side.BUY, Ticks.of(\"1499.95\"), 200);\n"
 "Order.market(\"t6\", \"INFY\", \"LAL\", Side.BUY, 400);\n"),

]

build(dict(
    slug="order-book", title="Order Book",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 9 blocks of failure tests and a 50-thread race pass",
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
