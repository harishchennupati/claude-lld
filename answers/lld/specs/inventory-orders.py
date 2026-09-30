# Inventory, Cart and Orders LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups.
# Evidence: research/inventory-orders.md (Meesho x3, PhonePe x3, Swiggy, Cars24, Harness, Amazon x2, Google, Licious, Walmart).
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"inventory-orders/Main.java").read_text()
ext   = (H/"inventory-orders/Extensions.java").read_text()
tests = (H/"inventory-orders/FailureTests.java").read_text()

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
MUT = "var(--muted)"

# ============================================================ page 01: the problem
pf = _D
rows = [("order", 30, [("a cart, or SKUs + quantities", "2 KURTI + 1 MUG, code SAVE10"),
                       ("check every line + the coupon", "touch nothing yet"),
                       ("block all, create the order", "PENDING_PAYMENT until +5 min"),
                       ("show the total to pay", "Rs 1,297 less Rs 100 = Rs 1,197")]),
        ("pay", 175, [("confirmOrder(order id)", "the buyer pays"),
                      ("charge the bank, no lock", "the order id is the key"),
                      ("still pending and in time?", "re-checked under the lock"),
                      ("reserved -&gt; sold, CONFIRMED", "then the SMS, after the unlock")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k*270
        acc = (k == 1) if lab == "order" else (k == 2)
        pf += _bx(x, y, 250, 54, b[0], b[1], acc=acc)
        if k < 3: pf += _ar("M%s %s H%s" % (x+250, y+27, x+270), True)
pf += _ar("M545 84 V100", dash=True) + _bx(315, 100, 460, 36, "a line short or the coupon used up: refuse, block nothing", "", dash=True)
pf += _ar("M815 229 V245", dash=True) + _bx(600, 245, 430, 36, "no: expired or cancelled meanwhile: refund", "", dash=True)
pf += _tx(88, 312, "stock", "var(--acc)", 13) + _tx(150, 312, "getInventory(PEN) at any moment, one lookup: how many can a new buyer still get?", "var(--text)", 12, "start")
pf += _tx(88, 342, "expiry", "var(--acc)", 13) + _tx(150, 342, "nobody pays within five minutes: the hold ends by itself and the units are for sale again", "var(--text)", 12, "start")
pf += _tx(615, 376, "a hundred buyers, ten pens, one instant: exactly ten orders. A unit is sold at most once, and stock never goes below zero", MUT, 11.5)
P_FLOWS = _mv(1230, 392, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("10:00  Asha checks out", ["2 KURTI + 1 MUG = Rs 1,297", "SAVE10: 10%, capped at Rs 100",
                                 "O1001 PENDING until 10:05", "KURTI: 1 available, 2 reserved"], True),
      ("10:01  she pays, twice", ["her app sends Pay two times", "key O1001: charged once",
                                 "Rs 1,197 taken; CONFIRMED", "KURTI: 2 reserved -&gt; 2 sold"], False),
      ("10:02  Ravi never pays", ["O1002 blocks the last KURTI", "10:07: nobody has paid",
                                 "EXPIRED; KURTI available 1", "a late payment is refunded"], False),
      ("10:10  100 buyers, 10 pens", ["each orders one PEN at once", "one lock decides the order",
                                     "10 orders, 90 OUT_OF_STOCK", "PEN: 0 available, 10 reserved"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Sellers add a product with a price and a count, and restock it or take back unsold units (<code>addProduct</code>, <code>updateInventory</code>).</li>
<li>Anyone can ask how many units a new buyer can still get (<code>getInventory</code>).</li>
<li>Buyers add and remove items in a cart and see the total, with a coupon if they have one.</li>
<li>Placing an order (<code>createOrder</code>, or <code>checkout</code> for the whole cart) blocks every line for five minutes, all or none, and returns the order and its total.</li>
<li><code>confirmOrder</code> takes the payment. Paid in time: the blocked units are sold. Declined: they stay blocked until the hold ends.</li>
<li>An unpaid order expires by itself after five minutes, and its units go back on sale.</li>
<li>Cancel before or after payment (units back, money back); mark as delivered only a confirmed order; show a buyer's order history.</li>
<li>Coupons: a percentage with a cap, or a flat amount above a minimum cart value; each with a limit per buyer and a limit in total.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>A hundred buyers at the same instant: a unit is sold at most once, and stock never goes below zero.</li>
<li>All or nothing: an order blocks every line or none, and a failed or late payment leaves stock and money consistent.</li>
<li>Safe to retry: the same order request twice makes one order; the same payment twice is charged once.</li>
<li>Stock and order lookups are O(1); ending the holds that are due costs O(log n) each, never a scan.</li>
<li>Pricing, the payment gateway, the hold time and the clock are handed in, so each can change without touching the store.</li>
<li>Listeners (the SMS, alerts) never run inside the lock, and a broken one cannot break an order.</li>
<li>In memory, one process, one store (say it; follow-ups add many machines).</li></ul></div></div>
'''

PROMPT = ('"Design the inventory and order service for an e-commerce site like Meesho: sellers add stock, buyers fill a '
          'cart and check out with a coupon, and placing an order blocks the stock for five minutes until the payment '
          'confirms it or the block runs out. Thousands of buyers at once, and it must never oversell. I want working '
          'code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>An online shop, like Meesho or Flipkart. Sellers add '
 'products, each with a SKU (stock keeping unit: the product\'s id), a price and a count, and restock them. Each '
 'product\'s count is split three ways: <i>available</i> (anyone may buy it), <i>reserved</i> (blocked for an order '
 'that is waiting to be paid; Meesho\'s word is "blocked") and <i>sold</i>. A buyer fills a cart, which is only a wish '
 'list and blocks nothing. When he places the order, the shop blocks every item at once for five minutes (a hold) '
 'and shows the price after any coupon. If the payment succeeds within those five minutes, the blocked units become '
 'sold; if not, the hold ends by itself and the units are for sale again. The one thing that must always be true (the '
 'invariant) is that a unit is sold at most once. Stock never goes below zero, and every unit is exactly one of '
 'available, reserved or sold, even when a hundred buyers press Buy in the same instant.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with '
 'a <code>main</code> that adds stock, places an order and pays for it. The interviewer is watching for, in this '
 'order: the questions you ask before typing (when stock is blocked, for how long, and what happens to a payment that '
 'arrives late are the first three); which classes exist, and which one owns the counts; placing an order and paying '
 'for it, end to end; what happens when a hundred buyers want the last ten units; where the rules that change live '
 '(pricing and coupons, the payment gateway, the hold time), so a change is a new class and not an edit; and what the '
 'stock and the money look like after a payment that fails or arrives too late. Then the twists: the same request '
 'arriving twice, a hold that ends with nobody around, several warehouses, an external seller, a flash sale, and '
 'running on many machines.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Does adding to the cart block stock, or only placing the order?</td><td>Only placing the order; the cart only checks</td><td>Stock has available and reserved; the cart blocks nothing (moves 1, 6)</td></tr>'
 '<tr><td>How long does an unpaid order block its stock, and who ends the block?</td><td>Five minutes; the store ends it by itself</td><td>A hold end per order, a queue ordered by it, swept on every call (moves 5, 6)</td></tr>'
 '<tr><td>Can one order have several products? All or nothing?</td><td>Yes; all or nothing</td><td>Check every line before blocking any, under one lock (moves 4, 6)</td></tr>'
 '<tr><td>Who takes the payment? Can it fail, time out, or answer late?</td><td>A gateway handed in; yes to all three</td><td>Charge outside the lock, re-check after it, refund when late (moves 3, 6)</td></tr>'
 '<tr><td>Can the same request arrive twice?</td><td>Yes: retries and double taps</td><td>An idempotency key per order request; the order id at the bank (moves 5, 9)</td></tr>'
 '<tr><td>Which coupons, and are they limited?</td><td>10% off with a cap, flat off above a minimum; once per buyer, N in total</td><td>Rules that wrap each other; uses claimed in the same step as the stock (moves 3, 5)</td></tr>'
 '<tr><td>How many buyers at once? One warehouse? Only our own stock?</td><td>Thousands at once; one warehouse; our own stock</td><td>One lock in the store; warehouses and sellers are follow-ups (moves 7, 8, 12)</td></tr>'
 '<tr><td>In memory, one process?</td><td>Yes</td><td>No database yet; the conditional UPDATE is a follow-up (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> money in paise (a long), never a double; each product\'s stock is three '
 'counts, available, reserved and sold, and every unit is in exactly one; the cart blocks nothing; placing an order '
 'blocks every line for five minutes, or none; the bank is called outside the lock, and nothing is sold before it says '
 'yes; the order id is the payment\'s idempotency key (a unique id per payment, so a retry is charged once); one store, '
 'one lock, in memory, one process. Named as out of scope: several warehouses, external sellers, back-in-stock alerts, '
 'a flash sale, many machines; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a BUYER fills a CART with PRODUCTS; each has STOCK; CHECKOUT makes an ORDER that blocks it 5 min; a COUPON cuts the price; PAYMENT confirms", "var(--text)", 12.5)
for k, (t, sub, acc) in enumerate([("Product", "sku, name, price", 1), ("Stock", "three counts", 1), ("Cart", "SKU -&gt; quantity", 1),
                                   ("Order", "lines + status", 1), ("Coupon", "code + 2 limits", 1), ("Store", "all of it + lock", 1),
                                   ("Buyer", "a caller: user id", 0), ("Checkout", "a verb: a method", 0), ("Payment", "an interface", 0)]):
    x = 20 + k*132
    m1 += _bx(x, 110, 124, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + 62))
m1 += _tx(615, 190, "solid = has state of its own, becomes a class.   dashed = no state here: a caller, a verb (a method), or something outside (an interface)", MUT, 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("block 2 kurtis", "Stock  (owns available, reserved)", "stock.reserve(2)"),
                                       ("add a mug to the cart", "Cart  (owns SKU -&gt; quantity)", "cart.add(\"MUG\", 1)"),
                                       ("count one use of SAVE10", "CouponBook  (owns the use counts)", "coupons.claim(code, user)"),
                                       ("place the order: lines + coupon", "Store  (owns all of them + the lock)", "store.createOrder(...)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 258, "a verb whose state is spread over several classes goes to the class that owns them all: the store runs the flow (the orchestrator)", MUT, 11)
MV[2] = _mv(1230, 272, m2)

# move 3: rules that change -> interfaces handed in
m3 = _D + _bx(30, 80, 230, 100, "Store", "configure(pricing, bank, hold)", acc=True)
for k, (t, sub, impl) in enumerate([("PricingRule", "list price, % off, flat off", "ListPrice / PercentOff / FlatOff"),
                                    ("PaymentGateway", "UPI, card; a fake that declines", "FakeGateway / a test's late bank"),
                                    ("Clock", "the wall, or a test's clock", "System::currentTimeMillis / () -&gt; now[0]"),
                                    ("StoreObserver", "SMS, back-in-stock alerts", "BuyerSms / BackInStockAlerts / SoldOutGate")]):
    y = 20 + k*58
    m3 += _ar("M260 130 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, sub, dash=True)
    m3 += _bx(760, y, 440, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 268, "dashed green = handed in. The store never builds a rule, so a new offer or a new bank is a new class and one changed line", MUT, 11)
m3 += _tx(615, 288, "and one price rule WRAPS another: new PercentOff(new ListPrice(), \"SAVE10\", 10, 100_00). That wrapping is Decorator, born here.", "var(--acc)", 11)
m3 += _tx(615, 308, "not an interface yet: which warehouse ships the order. There is one warehouse; follow-up 11 adds AllocationRule when there are two", MUT, 11)
MV[3] = _mv(1230, 322, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 210, 44, "buyer 1", "reads PEN: 1 left") + _bx(30, 110, 210, 44, "buyer 2", "reads PEN: 1 left")
m4 += _bx(360, 70, 190, 44, "PEN stock", "available = 1", acc=True)
m4 += _ar("M240 52 H360 V70") + _ar("M240 132 H360 V114") + _tx(300, 40, "read", MUT, 10.5) + _tx(300, 160, "read", MUT, 10.5)
m4 += '<rect x="590" y="20" width="290" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(735, 45, "the gap", RED, 12) + _tx(735, 70, "both saw 1, both block one:", RED, 11) + _tx(735, 90, "available -1, one pen sold twice", RED, 11)
m4 += _tx(735, 130, "fix: check + write = ONE step", "var(--text)", 11)
m4 += _bx(910, 40, 290, 100, "Store.lock", "check all, block all, create", acc=True)
m4 += _tx(1055, 165, "the lock lives where the counts live", MUT, 10.5)
m4 += _tx(1055, 185, "the bank and the SMS run OUTSIDE it", MUT, 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("how many PEN can a buyer get?", "Map&lt;sku, Stock&gt;: one lookup", "O(1)"),
                                      ("this order, by id?", "Map&lt;orderId, Order&gt;", "O(1)"),
                                      ("did this request already order?", "Map&lt;user, Map&lt;key, orderId&gt;&gt;", "O(1)"),
                                      ("which holds have run out?", "PriorityQueue by hold end: look at the top", "O(log n) each"),
                                      ("Asha's orders?", "Map&lt;user, List&lt;Order&gt;&gt;", "O(1) + copy"),
                                      ("is SAVE10 used up, for her?", "Map&lt;code, uses&gt; + Map&lt;code, Map&lt;user, uses&gt;&gt;", "O(1)"),
                                      ("the cart, in SKU order?", "TreeMap&lt;sku, qty&gt;", "O(log n)")]):
    y = 16 + k*44
    m5 += _bx(30, y, 360, 38, q, "the question") + _ar("M390 %s H450" % (y+19), True)
    m5 += _bx(450, y, 520, 38, shape, "the shape", acc=True) + _ar("M970 %s H1030" % (y+19), True) + _bx(1030, y, 170, 38, cost, "")
m5 += _tx(615, 340, "not one of these is a scan; a scan would sit inside the lock, and every buyer would wait for it", MUT, 11)
MV[5] = _mv(1230, 355, m5)

# move 6: the order's life, and the ORDER inside confirmOrder
m6 = _D + _bx(30, 30, 190, 44, "PENDING_PAYMENT", "the order blocked it", acc=True)
m6 += _bx(260, 30, 180, 44, "CONFIRMED", "paid in time", acc=True) + _bx(480, 30, 170, 44, "FULFILLED", "delivered")
m6 += _ar("M220 52 H260", True) + _ar("M440 52 H480", True)
m6 += _bx(30, 150, 190, 44, "EXPIRED", "5 min, nobody paid") + _bx(260, 150, 180, 44, "CANCELLED", "by the buyer")
m6 += _ar("M125 74 V150") + _tx(131, 118, "hold ends", MUT, 10.5, "start")
m6 += _ar("M200 74 V110 H300 V150") + _tx(250, 104, "release", MUT, 10.5)
m6 += _ar("M400 74 V150") + _tx(406, 118, "restock + refund", MUT, 10.5, "start")
m6 += '<rect x="680" y="20" width="530" height="200" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(945, 44, "the order inside confirmOrder, and why", "var(--text)", 12)
for k, l in enumerate(["1 lock: still PENDING? note which bank is charged",
                       "2 NO lock: charge the bank; the order id is the key",
                       "3 lock: still PENDING and before the hold's end?",
                       "yes: reserved -&gt; sold, CONFIRMED",
                       "no: it expired or was cancelled: refund by id",
                       "declined: nothing moves, the hold keeps running",
                       "timeout: UNKNOWN, still pending; a retry is safe"]):
    m6 += _tx(725 if k in (3, 4) else 695, 68 + k*21, l, MUT if k > 4 else "var(--text)", 11, "start")
m6 += _tx(615, 242, "checkout's order: price and check every line and the coupon, touching nothing; then block all, count the coupon, create the order", MUT, 11)
m6 += _tx(615, 260, "a move not in the table throws (deliver an unpaid order, cancel a delivered one); nothing is sold before the money moved", MUT, 11)
MV[6] = _mv(1230, 274, m6)

# move 7: what is inside the lock, and a hundred buyers at the same instant
m7 = _D + _card(30, 20, 540, 150, "inside the lock: a few microseconds",
                ["price 3 lines: 3 catalogue lookups", "check 3 counts, then write 6 of them",
                 "check and claim the coupon's two counts", "4 map writes and 1 heap push for the hold",
                 "about 5 us in all, measured, allocation included"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside the lock: milliseconds to seconds",
            ["the bank: 300 ms to 2 s, between two short sections", "the SMS and the alerts: after the unlock",
             "a refund call: after the unlock", "the buyer typing his OTP: 20 seconds"])
m7 += _tx(615, 200, "a hundred buyers press Buy for ten pens at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    n = k + 1 if k < 9 else 100
    m7 += _bx(x, 214, 106, 40, "buyer %d" % n, "waits %d us" % ((n - 1) * 5), acc=(k == 9))
m7 += _tx(615, 282, "the hundredth buyer waits half a millisecond for the lock, then seconds for his bank: one by one is true, and nobody can tell", MUT, 11)
MV[7] = _mv(1230, 297, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m8 += _tx(300, 42, "one lock for the store: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["one order: checkout ~5 us + two pay sections ~3 us",
                       "+ a few stock reads and cart edits: ~12 us of lock",
                       "Meesho: 1M orders a day = 12 a second; a sale day 100x",
                       "1,200 orders a second x 12 us = 1.4% busy",
                       "the real limit: one process will not serve 10M users"]):
    m8 += _tx(35, 66 + k*24, l, RED if k == 4 else MUT, 11, "start")
m8 += _tx(900, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 a lock per SKU", "taken in SKU order: buyers of different products never wait"),
                              ("2 a sold-out gate for a hot SKU", "a compare-and-set counter says 'sold out' without the lock"),
                              ("3 the database decides", "UPDATE stock ... WHERE sku = ? AND available &gt;= ?   1 row = yours")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("100 buyers, 10 pens, one instant", "one lock round check + write; test 1: 10 orders, 90 OUT_OF_STOCK, never below 0"),
                                ("one line of three is short", "check every line before writing any; test 2: PEN and MUG untouched"),
                                ("the buyer never pays", "a queue by hold end, swept on every call; test 3: held at 4:59.999, free at 5:00.000"),
                                ("the bank answers after the hold", "re-check under the lock after the charge, refund; test 4: money back, nothing sold"),
                                ("the app retries; Pay tapped twice", "a key per request, the order id at the bank; tests 6, 7: one order, one charge"),
                                ("50 buyers race for a 10-use coupon", "the use is claimed in the same step as the stock; test 8: exactly 10"),
                                ("the bank times out, nobody retries", "the order remembers the bank it charged: refund by id at its end; test 11"),
                                ("the SMS provider throws", "listeners after the unlock, in a try/catch; test 10: the order completes")]):
    y = 18 + k*40
    m9 += _bx(30, y, 320, 36, bad, "") + _ar("M350 %s H400" % (y+18), True) + _bx(400, y, 800, 36, fix, "", acc=True)
m9 += _tx(615, 352, "every claim on this page has a test: FailureTests.java runs fifteen groups of checks and must print ALL PASS", MUT, 11)
m9 += _tx(615, 370, "test 13 runs orders, payments, cancels and restocks on eight threads, then checks every unit and every paise", MUT, 11)
MV[9] = _mv(1230, 385, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 190), ("the line in the code", 280), ("what it buys", 840)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface PricingRule { Quote price(List&lt;Line&gt; lines); }  handed in", None), ("a new offer is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new PercentOff(new ListPrice(), \"SAVE10\", 10, 100_00)", None), ("add a discount without copying one", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("StoreObserver.onEvent(e), called after the unlock", None), ("the SMS hears; checkout never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("NEXT: PENDING_PAYMENT -&gt; CONFIRMED | CANCELLED | EXPIRED", None), ("an illegal move throws", None)],
          [("Idempotency key", "var(--text)"), ("move 5", None), ("byKey: user -&gt; key -&gt; order id;   bank.charge(orderId, paise)", None), ("a retry is the same order and charge", None)],
          [("Singleton", MUT), ("not here", None), ("a store per tenant; every test builds a fresh one", MUT), ("no global to reset between tests", MUT)],
          [("Factory", MUT), ("not yet", None), ("CouponFactory.fromConfig(\"SAVE10|PERCENT|10|10000|1|1000\")", MUT), ("when coupons come from an admin screen", MUT)],
          [("Builder", MUT), ("never", None), ("an order's fields are all required, set in one place", MUT), ("a pattern without a move is decoration", MUT)]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 310, "name a pattern only after the move that produced it; then every name has a one-sentence defence", MUT, 11)
MV[10] = _mv(1230, 325, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Stock: its counts. Cart: its items. CouponBook: its uses. Store: the flow + the lock.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("BuyXGetY and BestOf are new classes; Store was never opened", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("Quote plain = pricing.price(lines);   never \"is it the coupon one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces, one job each", None), ("move 3", None), ("PricingRule, Clock, StoreObserver: one method; PaymentGateway: charge + refund", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations handed in", None), ("moves 3, 9", None), ("store.configure(rule, lateBank, Store.HOLD_MS);   store.setClock(() -&gt; now[0])", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", MUT, 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "buy 2 get 1, nearest warehouse, longer hold", "a new class behind the existing interface + one configure line", "", "move 3"),
        ("someone new wants to know", "SMS, back in stock, a seller dashboard", "one more listener; checkout does not change", "", "move 4"),
        ("a new step in a life", "SHIPPED, RETURN_REQUESTED, cash on delivery", "one more state and a row in the table", "", "move 6"),
        ("a new invariant across items", "a combo: both SKUs or neither; 2 per buyer", "every check inside the SAME lock: all or nothing", "", "move 4"),
        ("state that must outlive the process", "a restart; many machines", "the stock behind a repository; the check-and-block becomes",
         "UPDATE stock SET available = available - ? WHERE sku = ? AND available &gt;= ?", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, MUT, 11)
m12 += _tx(615, 310, "for all five, Stock, Cart and the tests do not change; that is the test that the derivation was right", MUT, 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the prompt again: a <b>buyer</b> fills a <b>cart</b> with <b>products</b>; each product has <b>stock</b>; "
 "<b>checkout</b> makes an <b>order</b> that blocks the stock for five minutes; a <b>coupon</b> cuts the price; "
 "<b>payment</b> confirms it. A product has a SKU, a name and a price: a record (a small class that only holds values). "
 "Its stock has three counts, available, reserved and sold: a class, because the three change together and must never "
 "go below zero. A cart has SKUs and quantities: a class. An order has lines, a price, a status and the moment its hold "
 "ends: a class. A coupon has a code, a discount and two limits: a record, with a <code>CouponBook</code> that counts "
 "its uses. The store holds all of it plus the lock: a class. The buyer remembers nothing here, so he is a user id "
 "passed in. Checkout is a verb, so it is a method. The payment happens at a bank outside the process, so it becomes "
 "an interface the store is handed.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Block two kurtis\" changes the kurti's counts, so <code>stock.reserve(2)</code>, and Stock refuses by itself to go "
 "below zero. \"Add a mug to the cart\" changes the cart, so <code>cart.add(\"MUG\", 1)</code>. \"Count one use of "
 "SAVE10\" changes the coupon counts, so <code>coupons.claim(code, user)</code>. \"Place the order\" touches the stock of "
 "every line, the coupon counts, the orders and the queue of holds at once. Only the store sees all of them, so "
 "<code>store.createOrder(...)</code>. A verb whose state is spread over several classes goes to the class that owns "
 "them all. That class becomes the orchestrator (the one class that runs the flow and calls the others). The same "
 "test places the rest. \"Move an order to CONFIRMED\" changes its status, so <code>order.moveTo(CONFIRMED)</code>, and "
 "the order refuses a move its table does not allow. \"All or nothing across the lines\" needs every line's stock, so it "
 "is <code>inventory.reserveAll(lines)</code>.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Pricing will change: the list price today, 10% off tomorrow, buy two get one for Diwali. The bank will change: UPI, a "
 "card, a fake that declines in a test. Time must be controllable, or the five-minute hold cannot be tested without "
 "waiting five minutes. And people will want to hear about orders: an SMS, a back-in-stock alert, a seller's dashboard. "
 "Each becomes a small interface the store is <i>given</i> through <code>configure()</code>, <code>setClock()</code> "
 "and <code>addObserver()</code>, and never builds itself. The hold time is a number handed in the same way. This is "
 "where the patterns come from, not the other way round. A swappable rule behind an interface is <b>Strategy</b>. A rule "
 "that wraps another instead of replacing it (SAVE10 wraps the list price) is <b>Decorator</b>. A store that announces "
 "\"order confirmed\" without knowing who listens is <b>Observer</b>. Which warehouse ships an order is not an interface "
 "yet, because there is one warehouse; it becomes one the moment there are two (follow-up 11).", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "A hundred buyers can press Buy for the last pens in the same instant. Between \"I read that PEN has 1 left\" and \"I "
 "blocked it\", another buyer can block it too. That gap is where one pen is sold twice and the count goes to minus one. "
 "So the check and the write must be one step under one lock, in the class that owns the counts: the store. For an order "
 "of several lines, the step is the whole order: check every line, block every line, create the order. All of it runs "
 "under the same lock, so nobody can take a unit between the check and the write. Two things must NOT be inside that "
 "lock. The bank takes a second or two, so it is called between two short locked steps (move 6). The listeners (the SMS "
 "sender) can be slow or broken, so they run after the unlock.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"How many PEN can a buyer still get?\": a map from SKU to its stock, one lookup. \"This order, by id?\": a map. \"Did "
 "this exact request already make an order?\": a map from buyer and idempotency key to the order id. The key is a "
 "unique id the app sends with each order request, so a retry can be recognised. \"Which holds have run out?\": a priority queue (a "
 "heap: the item with the smallest key is always on top) ordered by the moment each hold ends. The sweep (ending every "
 "hold whose time is up) looks only at the top and stops at the first hold still running. A paid order stays in the "
 "queue until its time comes and is then skipped, which costs one pop, not a search. \"Asha's orders?\": a map from buyer "
 "to a list. \"Is SAVE10 used up, for her?\": two counters, one for everybody and one per buyer. \"The cart in SKU "
 "order?\": a sorted map. Every scan avoided here is time not spent inside the lock, where every other buyer would wait "
 "for it.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An order is PENDING_PAYMENT when it is placed, CONFIRMED when the money arrived in time, and FULFILLED when "
 "delivered. An unpaid order ends EXPIRED after five minutes, or CANCELLED by the buyer; a confirmed one can still be "
 "CANCELLED before it ships. The moves are a table, so a move that is not in it (delivering an unpaid order, cancelling "
 "a delivered one) throws. Writing the states down forces the question the interviewer will ask: what if the payment "
 "fails, or arrives late? The answer is the order inside <code>confirmOrder</code>. Under the lock, check the order is "
 "still pending and note that a charge is being tried. With no lock held, charge the bank, with the order id as the "
 "idempotency key. Under the lock again, commit only if the order is still pending and its hold has not ended: reserved "
 "becomes sold. If it expired or was cancelled while the bank was working, the money goes back. Nothing is sold before "
 "the money moved. A decline leaves everything as it was, and the hold keeps running, so the buyer can try another card.", 6),
("Move 7: yes, the lock makes orders happen one at a time. Ask for how long, and what is inside it.",
 "Inside the lock, an order of three lines does about twenty small things: three catalogue lookups, three count checks, "
 "six counter writes, two coupon counts, four map writes and one heap push. That is a few microseconds; measured on a "
 "busy laptop, allocation included, about five. Everything slow is outside: the bank (a second or two, between two "
 "short locked steps), the SMS (after the unlock), the buyer typing his OTP. So when a hundred buyers press Buy for the "
 "last ten pens in the same instant, they do go through one at a time. The hundredth waits about half a millisecond "
 "for the lock, then seconds for his bank like everybody else. One by one is true, and nobody can tell, as long "
 "as nothing slow gets inside.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Take Meesho's own numbers. A million orders a day is about twelve a second, and a sale day at a hundred times that is "
 "1,200 a second. One order costs about twelve microseconds of lock: the order itself, the two short steps of the "
 "payment, a few stock reads and cart edits. 1,200 orders a second is then about fifteen milliseconds of lock in every "
 "second: 1.4% busy. The lock is not the limit. The limit is that ten million users will never be served by one "
 "process. Then name the ladder, in the order you would climb it. Rung one: a lock per SKU, always taken in SKU order, so "
 "buyers of different products never wait for each other. Rung two is for one product everybody wants in a flash sale "
 "(a sale that opens at a set minute with few units). A counter in front of the store says \"sold out\" with a "
 "compare-and-set, without touching the lock. A compare-and-set writes the new count only if it still holds the value "
 "just read, as one hardware step. Rung three: the database decides, with one conditional UPDATE per line, which is how many machines "
 "share one stock. Say the arithmetic first: climbing the ladder without it is complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Each row of the table is a numbered group in FailureTests.java, which prints ALL PASS or exits non-zero. The race is "
 "the one worth writing in front of the interviewer. A hundred threads wait on one latch (a gate that opens for all of "
 "them at once). The test counts ten orders and ninety OUT_OF_STOCK, and checks the count never went below zero. Then "
 "all ten winners pay at once, and the bank holds exactly ten pens' money. The rows candidates forget are the money "
 "rows: a payment that lands after the hold ended, a reply that never came back, a refund call that fails. Test 13 then "
 "runs a random mix of orders, payments, cancels and restocks on eight threads with the clock moving. At the end it "
 "checks the two things that matter: every unit is available, reserved or sold, and the bank holds exactly what the "
 "confirmed orders cost.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; each name has one sentence behind it because a move produced it. Two rows need a word. The "
 "idempotency key is not in the Gang of Four book, but in an order system it is the most important pattern on the page. "
 "The key per request makes a retried order the same order, and the order id at the bank makes a retried payment the "
 "same charge. And the bottom three rows are the absences, worth saying out loud. There is no Singleton, because a "
 "store is handed to its callers and every test builds a fresh one. There is no Factory until coupons arrive as lines "
 "of config from an admin screen (that is <code>CouponFactory</code> in Extensions.java). There is no Builder, because "
 "an order's fields are all required and set in one place.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is not a list to recite; it is the check that the moves did their job. Every letter is a line that already "
 "exists because a move produced it. So the honest answer to \"which SOLID principles did you apply?\" is \"move 2 gave "
 "me S, move 3 gave me O, L, I and D\". The one worth showing instead of claiming is D. Because the store depends on "
 "interfaces it is handed, a test hands it a bank that answers six minutes late and a clock it can move. The late-payment "
 "refund is then tested in ten lines, without sleeping.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (buy two get one, which warehouse ships, a longer hold on sale days) is a new class behind an existing "
 "interface and one configure line. Several discounts at once are those classes wrapped round each other, and the order "
 "of wrapping is the answer. Someone new who wants to know (an SMS, a back-in-stock alert, a seller's dashboard) is one "
 "more listener; checkout does not change. A new step in a life (SHIPPED, RETURN_REQUESTED, cash on delivery) is a new "
 "state and a row in the table. A new invariant across items (a combo: both products or neither; at most two per buyer "
 "in a flash sale) is every check inside the same lock, all or nothing. And state that must outlive the process, or be "
 "shared by many machines, is the stock behind a repository (an interface with load and save). There the locked "
 "check-and-block becomes one conditional UPDATE: <code>UPDATE stock SET available = available - 2, reserved = reserved + 2 "
 "WHERE sku = 'PEN' AND available &gt;= 2</code>. One row updated means you got them; zero means someone else did. That "
 "is the database's compare-and-set, the same idea as the lock, one layer down. Page 05 has the code for each.", 12),
]

# ============================================================ page 03: the class diagram
uml_reset()
# callers, cart, coupons, listeners, refusals: left column
put("main", 10, 20, 220, "Main", [], ["stocked(): Store", "main: demo + 100-buyer race"])
put("cart", 10, 120, 220, "Cart", ["items: TreeMap&lt;sku, qty&gt;"], ["add / remove(sku, qty)", "qty / items / isEmpty"])
put("book", 10, 240, 220, "CouponBook", ["byCode: Map&lt;code, Coupon&gt;", "used, usedBy: use counts"], ["ruleFor(code, user, base)", "claim / giveBack(code, user)"])
put("obs", 10, 380, 220, "StoreObserver", [], ["onEvent(e: StoreEvent)"], "interface")
put("sms", 10, 460, 220, "BuyerSms", [], ["onEvent(e): text the buyer"])
put("event", 10, 540, 220, "StoreEvent", ["kind, orderId, userId", "lines, paise, seq"], [])
put("reason", 10, 630, 220, "Reason", ["UNKNOWN_PRODUCT, BAD_QUANTITY", "EMPTY_ORDER, OUT_OF_STOCK", "UNKNOWN_COUPON", "COUPON_USED_UP", "COUPON_NOT_APPLICABLE"], [], "enum")
put("refused", 10, 770, 220, "OrderRefused", ["reason: Reason"], [])
# the aggregate root and what it owns: centre
put("store", 290, 20, 320, "Store",
    ["inventory: Inventory", "carts: Map&lt;user, Cart&gt;", "orders: Map&lt;id, Order&gt;", "byKey: Map&lt;user, Map&lt;key, orderId&gt;&gt;",
     "history: Map&lt;user, List&lt;Order&gt;&gt;", "holds: PriorityQueue&lt;Order&gt; by hold end", "coupons: CouponBook",
     "lock: ReentrantLock, eventSeq: long", "pricing / gateway / holdMs / clock"],
    ["configure(pricing, gateway, holdMs)", "setClock(c) / addObserver(o) / addCoupon(c)", "addProduct(sku, name, price, qty)",
     "updateInventory(sku, delta): int", "getInventory(sku): int / stockOf(sku)", "addToCart / removeFromCart / viewCart",
     "cartTotal(user, code): Quote", "checkout(user, key, code): Order", "createOrder(user, key, wanted, code)",
     "confirmOrder(orderId): PayResult", "cancelOrder(id) / fulfilOrder(id)", "sweepExpired(): int", "order(id) / orderHistory(user)"])
put("inv", 290, 450, 320, "Inventory", ["catalog: Map&lt;sku, Product&gt;", "stock: Map&lt;sku, Stock&gt;"],
    ["price(wanted): List&lt;Line&gt;", "firstShort(lines): Line", "reserveAll / releaseAll(lines)", "commitAll / putBackAll(lines)"])
put("stock", 290, 620, 320, "Stock", ["available, reserved, sold: int"], ["reserve / release / commit(n)", "putBack(n) / restock(n)", "view(): StockView"])
put("view", 290, 760, 320, "StockView", ["available, reserved, sold"], [])
# the order and the values: centre right
put("order", 650, 20, 250, "Order", ["id, userId, couponCode", "lines: List&lt;Line&gt;", "quote: Quote", "holdUntilMs: long",
                                     "status: OrderStatus", "chargedVia: PaymentGateway"], ["status() / totalPaise()", "moveTo(next)"])
put("ostatus", 650, 215, 250, "OrderStatus", ["PENDING_PAYMENT, CONFIRMED", "FULFILLED, CANCELLED, EXPIRED"], ["canMoveTo(next): boolean"], "enum")
put("pay", 650, 330, 250, "PayResult", ["CONFIRMED, DECLINED, UNKNOWN,", "REFUNDED, REFUSED"], [], "enum")
put("line", 650, 420, 250, "Line", ["sku, qty, unitPaise"], ["paise(): long"])
put("product", 650, 520, 250, "Product", ["sku, name, pricePaise"], [])
put("quote", 650, 595, 250, "Quote", ["subtotalPaise, totalPaise", "discounts: List&lt;String&gt;"], ["less(label, off): Quote"])
put("coupon", 650, 710, 250, "Coupon", ["code, perUserLimit, totalLimit", "discount: rule -&gt; rule"], [])
# the rules handed in: right
put("rule", 940, 20, 270, "PricingRule", [], ["price(lines): Quote"], "interface")
put("list", 940, 100, 270, "ListPrice", [], ["price: sum of qty x unit"])
put("pct", 940, 180, 270, "PercentOff", ["inner: PricingRule", "percent, capPaise"], ["price: inner less % (capped)"])
put("flat", 940, 295, 270, "FlatOff", ["inner: PricingRule", "offPaise, minCartPaise"], ["price: flat off, subtotal &gt;= min"])
put("gw", 940, 420, 270, "PaymentGateway", [], ["charge(orderId, paise): boolean", "refund(orderId)"], "interface")
put("fake", 940, 520, 270, "FakeGateway", ["held: Map&lt;orderId, paise&gt;"], ["charge: once per order id", "refund: gives back what it holds"])
put("clock", 940, 640, 270, "Clock", [], ["nowMs(): long"], "interface")

edges = [
 ln(B["main"]["r"], (290, B["main"]["r"][1]), "assoc", "calls"),
 ln((290, 165), B["cart"]["r"], "compose", "per user"),
 ln((290, 293), B["book"]["r"], "compose", ""),
 ln((290, 407), B["obs"]["r"], "notify", "notifies"),
 ln(B["sms"]["t"], B["obs"]["b"], "inherit"),
 ln(B["refused"]["t"], B["reason"]["b"], "assoc"),
 ln(B["store"]["b"], B["inv"]["t"], "compose", "owns"),
 ln(B["inv"]["b"], B["stock"]["t"], "compose", "one per SKU"),
 ln(B["stock"]["b"], B["view"]["t"], "assoc", "view()"),
 ln(B["inv"]["r"], B["product"]["l"], "compose", "", [(630, B["inv"]["r"][1]), (630, B["product"]["l"][1])]),
 ln((610, 105), B["order"]["l"], "compose", ""),
 ln(B["order"]["b"], B["ostatus"]["t"], "assoc"),
 ln((610, 363), B["pay"]["l"], "assoc", ""),
 ln(B["line"]["b"], B["product"]["t"], "assoc", "sku of"),
 ln((610, 202), B["rule"]["l"], "inject", "", [(925, 202), (925, B["rule"]["l"][1])]),
 ln((610, 318), B["gw"]["l"], "inject", "", [(930, 318), (930, B["gw"]["l"][1])]),
 ln((610, 408), B["clock"]["l"], "inject", "", [(920, 408), (920, B["clock"]["l"][1])]),
 ln(B["list"]["t"], B["rule"]["b"], "inherit"),
 ln((B["pct"]["t"][0] - 60, B["pct"]["t"][1]), (B["rule"]["b"][0] - 60, B["rule"]["b"][1]), "inherit"),
 ln((B["flat"]["t"][0] - 100, B["flat"]["t"][1]), (B["rule"]["b"][0] - 100, B["rule"]["b"][1]), "inherit"),
 ln(B["pct"]["r"], (1210, 62), "assoc", "", [(1221, B["pct"]["r"][1]), (1221, 62)]),
 ln(B["flat"]["r"], (1210, 62), "assoc", "", [(1221, B["flat"]["r"][1]), (1221, 62)]),
 ln(B["fake"]["t"], B["gw"]["b"], "inherit"),
]
UMLSVG = uml_svg(1230, 890, edges, legend_y=862)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the store owns the carts, the coupon book, the inventory and the orders, and the '
 'inventory owns the catalogue and one Stock per SKU. Plain arrow = references or returns: an order points at its '
 'status, a line names a product, the store returns a PayResult. Dashed green = handed in through '
 '<code>configure()</code> and <code>setClock()</code>: the pricing rule, the bank and the clock. Dotted blue = '
 'notifies: the one call the store makes after it has released the lock. The arrows on the far right, from PercentOff '
 'and FlatOff back to PricingRule, are one rule wrapping another (Decorator). The boxes with no arrow are small values '
 'passed around: every listener gets a StoreEvent, a pricing rule returns a Quote, a Coupon lives in the coupon book, '
 'and a refusal carries a Reason. <b>Where state lives:</b> a Stock has its three counts; a cart its items; the coupon '
 'book its use counts; an order its status and the bank a charge was sent to. The store has all of them plus the '
 'idempotency keys, the order history, the queue of running holds, the event counter and the one lock. It is the '
 'only class that writes to more than one of them. On the next page this diagram is worth keeping in a second tab.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it does and what it guarantees; read only those first for the shape, then the '
 'bodies. Start with <code>Store.place</code> and <code>Store.confirmOrder</code>, the two critical steps. Each copy '
 'button copies that whole file. Below Main.java: Extensions.java (every follow-up\'s reference code, with an '
 '<code>ExtDemo</code> main that runs all of it) and FailureTests.java (fifteen groups, 92 checks, one group per claim; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT +
 '</div>Before typing, write your six to eight clarifying questions; then type in the order of Main.java: the records '
 '(Product, Line, Quote), Stock with its three counts, Inventory with the all-or-nothing methods, Cart, the pricing rules '
 '(ListPrice and one wrapper), Coupon and CouponBook, OrderStatus with its table, Order, the gateway interface with a '
 'fake, and the store with its lock: <code>place</code> (check all, then write all), <code>confirmOrder</code> (lock, '
 'charge with no lock, lock and re-check), the sweep, <code>cancelOrder</code>; then a main with the race. If the clock '
 'runs out, the one thing that must exist is <code>createOrder</code> and <code>confirmOrder</code> under one lock, with '
 'every line checked before any is blocked and the payment before the commit.</div></div>')

FU = [
("Swiggy wants discounts: 10% off up to Rs 100, Rs 100 off above Rs 999, buy 2 get 1 free. Where does each go, and in what order?", "functional", 10,
 "Pricing is already an interface, so each discount is one small class that wraps the rule before it, and the store "
 "never opens. <code>BuyXGetY</code> takes the free units off one SKU. <code>PercentOff</code> takes a percentage of "
 "what is left, up to a cap. <code>FlatOff</code> takes a flat amount when the cart's subtotal reaches the minimum. The "
 "wrapping order is the applying order: item offers first, then the percentage, then flat amounts, and the total never "
 "goes below zero. A coupon's two limits are counted in the same locked step that blocks the stock, so fifty buyers "
 "racing for a ten-use code get exactly ten (test 8). If only the best of several codes may count (Flipkart's billing "
 "task), <code>BestOf</code> keeps the cheapest, so a code applied twice never stacks.",
 sect(src, "final class PercentOff", "record Coupon(") + "\n" + X("buy X get Y", "a lock per SKU")
 + "\n// the store's offers, wrapped in the order they apply (innermost first):\n"
 "store.configure(new FlatOff(new PercentOff(new BuyXGetY(new ListPrice(), \"PEN\", 2, 1),\n"
 "        \"FESTIVE10\", 10, 100_00), \"BIG100\", 100_00, 999_00), bank, Store.HOLD_MS);\n"),

("A hundred buyers press Buy for the last ten pens at the same instant. Prove it cannot oversell, with a test.", "non-functional", 10,
 "The race lives between reading \"PEN has 1 left\" and writing \"PEN has 0\". <code>createOrder</code> does the check, "
 "the block and the new order inside one lock, so no other buyer can run in that gap. The proof is a test: a hundred "
 "threads wait on one latch, the latch opens, and every thread orders one pen. The test counts ten orders and ninety "
 "OUT_OF_STOCK refusals. PEN must end at available 0 and reserved 10: no unit lost, none sold twice. Then all ten "
 "winners pay at the same instant, and the bank must hold exactly ten pens' money.",
 T("        // 1. the race", "        // 2. all or nothing")),

("Meesho: 5 million products, 10 million users, a million orders a day. One lock for all of it?", "non-functional", 5,
 "In one process, one lock is fine: an order holds it for about twelve microseconds, so even 1,200 orders a second "
 "keep it 1.4% busy. The real limit is elsewhere: ten million users need many machines, which is follow-up 13. Still, "
 "Meesho's interviewers expect the first rung: a lock per SKU, so buyers of different products never wait for each "
 "other. An order of several lines takes its SKUs' locks in SKU order, always the same order. Then {PEN, MUG} and "
 "{MUG, PEN} can never each hold one lock and wait for the other (a deadlock); the test runs both twenty thousand "
 "times. The price: orders, idempotency keys and coupon counts now need their own thread safety. Splitting by store "
 "(Harness's many shops) is free, because stores never share stock.",
 X("a lock per SKU", "sold-out gate")),

("The buyer never pays. The five-minute block must end on its own. Who ends it, and exactly when?", "functional", 10,
 "Every order goes into a priority queue ordered by the moment its hold ends. Every store method that reads stock, "
 "orders or coupons first runs <code>sweep</code>, which ends holds from the top of the queue until it meets one "
 "still running. Ending a hold gives the units and the coupon use back and marks the order EXPIRED. It also refunds "
 "by order id if a charge was sent, and tells the listeners after the unlock. A hold ends AT its end time: at "
 "10:04:59.999 the kurtis are still held, at 10:05:00.000 they are for sale (test 3). No thread is needed for correct "
 "counts, because every read sweeps first. For a quiet store, <code>HoldSweeper</code> runs the same sweep every "
 "second and catches every exception, because a scheduled task that throws is never run again.",
 sect(src, "    private int sweep(List<Runnable> after)", "    private void refundLater(") + "\n" + X("background sweeper", "back in stock")),

("The bank says yes after the hold has ended, or never answers. What happens to the stock and the money? Show me the code.", "functional", 10,
 "<code>confirmOrder</code> sells nothing before the money moved, and re-checks after it moved. It charges with no "
 "lock held and the order id as the key, then takes the lock again. If the order is still pending and in time, "
 "reserved becomes sold; if the hold ran out or the buyer cancelled meanwhile, the money goes back (REFUNDED). A "
 "decline changes nothing, and the hold keeps running for another card. A timeout means nobody knows whether money "
 "moved, so the answer is UNKNOWN, and a retry is safe: the bank charges an order id at most once. If nobody retries, "
 "the expired order asks the bank it charged for a refund by order id, which does nothing if no money moved. A refund "
 "call that fails waits on a retry list; anything still unclear is settled by reconciliation (comparing the bank's "
 "daily settlement file with the orders).",
 sect(src, "    PayResult confirmOrder(String orderId)", "    OrderStatus cancelOrder(String orderId)")),

("The app times out and sends createOrder again, or he taps twice. Show the stock is blocked once. How should it retry?", "functional", 10,
 "The app makes an idempotency key when the buyer taps Place Order, and sends the same key with every retry. "
 "<code>createOrder</code> first looks up that buyer's key under the lock; if an order exists, it is returned as it "
 "is, and nothing is blocked again. Twenty copies of one request at the same instant make one order (test 7). Keys are "
 "kept per buyer, so two buyers can never collide on one. The client retries only what can succeed later: a timeout, "
 "never OUT_OF_STOCK. It waits a random time up to a ceiling that doubles each attempt (exponential backoff with full "
 "jitter), so a thousand phones do not retry in step. A real service keeps keys for a day or so, and Stripe rejects a "
 "key reused with a different request; this code returns the first order.",
 sect(src, "    Order createOrder(String userId", "    PayResult confirmOrder(String orderId)") + "\n"
 + sect(src, "    private Order replay(String userId", "    private Order place(") + "\n" + X("client retry", "coupons from config")),

("Cancel an order before payment and after it. And only a confirmed order may be marked delivered.", "functional", 5,
 "The life cycle is a table in <code>OrderStatus</code>, so every rule in the question is a row, not an if. Cancelling "
 "a pending order releases its block and gives the coupon use back. Cancelling a confirmed order puts the sold units "
 "back on sale, gives the coupon use back, and refunds after the unlock. Cancelling twice changes nothing the second "
 "time, because a cancelled order has nothing left to undo. A delivered order cannot be cancelled: it comes back as a "
 "return, a different flow with a warehouse check. <code>fulfilOrder</code> on an unpaid order throws, because "
 "PENDING_PAYMENT to FULFILLED is not in the table (PhonePe's \"only confirmed orders can be fulfilled\").",
 sect(src, "enum OrderStatus", "final class Order {") + "\n" + sect(src, "    OrderStatus cancelOrder(String orderId)", "    int sweepExpired()")),

("getInventory is called 10,000 times a second, and the app shows order history. Are both O(1), and do they slow orders?", "non-functional", 5,
 "Both are lookups. <code>getInventory</code> sweeps (usually one look at the top of the queue) and reads one count "
 "from a map: well under a microsecond of lock. Ten thousand reads a second therefore add about a millisecond of lock "
 "per second. It reads under the lock on purpose, so the three counts are never seen halfway through an order's "
 "writes. <code>orderHistory</code> is one map lookup plus a copy of that buyer's list. If reads ever crowded the lock, "
 "keep the available count where it can be read without the lock (a volatile field or an atomic), as the Meesho "
 "candidate did. A product page may then be a millisecond stale, but the order still decides under the lock, so it "
 "can never oversell.",
 sect(src, "    int getInventory(String sku)", "    // ---------------- the buyer's cart") + "\n"
 + sect(src, "    List<Order> orderHistory(String userId)", "    int couponUses(String code)")),

("Should adding to the cart block the stock? And what if the price changes while it sits in the cart?", "design", 5,
 "No: the cart is a wish list, and only placing the order blocks. If carts blocked stock, abandoned carts would hold "
 "units for hours, and the shop would look sold out. <code>addToCart</code> still checks that the product exists and "
 "is available right now, but that check is only advice. Two carts can hold the same last kurti, and checkout decides "
 "who gets it (test 14). The price is copied into each order line when the order is placed, so a later price change "
 "never alters an order. <code>cartTotal</code> runs the same pricing code as checkout, so the total he saw is the "
 "total he pays. A flash sale that blocks at add-to-cart for a few minutes is simply a shorter hold, the same code.",
 sect(src, "    void addToCart(String userId", "    void removeFromCart(") + "\n" + sect(src, "record Line(", "record StockView(")),

("Text the buyer on every order event, and tell buyers who are waiting for a sold-out kurti when it is back.", "twist", 10,
 "The store announces every order event and every restock after the unlock, with a try/catch per listener, so a broken "
 "SMS provider cannot break an order (test 10). An SMS is one listener, <code>BuyerSms</code>. The back-in-stock alert "
 "is another: buyers watch a SKU, and an event that gives units back makes it ask the store whether that SKU is "
 "available now. That call is safe because listeners run after the unlock, and the watch list is removed in one atomic "
 "step, so nobody is told twice. One catch: two threads can deliver one order's events in the wrong order. Every event "
 "carries a number taken under the lock, and <code>LatestOnly</code> drops an event older than the last one it passed "
 "for that order. So she is never told \"confirmed\" after \"cancelled\", and the store did not change for any of it.",
 sect(src, "    private void publish(StoreEvent e)", "\n}\n\n/** Runs a demo") + "\n" + X("back in stock", "warehouses")),

("The product sits in several warehouses, each delivering to some pincodes. Ship from one, or split the order.", "twist", 10,
 "Which site ships which units is a rule that will change, so it goes behind <code>AllocationRule</code>. "
 "<code>OneSiteElseSplit</code> first looks, nearest first, for one site that delivers to the pincode and has every "
 "line: one parcel. Only when no site has it all does it split the order across the sites that deliver there. "
 "<code>SiteStock</code> keeps the counts per site under one lock and plans and reserves in the same locked step, so "
 "two buyers are never promised the same last unit. An unserved pincode, and an order no set of sites can fill, are "
 "refused by name: \"pincode unserviceable\" and \"insufficient product inventory\". In the store this replaces "
 "<code>inventory.reserveAll</code>, and each order line remembers its site.",
 X("warehouses", "external seller")),

("PhonePe: some items belong to an external seller, and his stock can be reached only through his API.", "twist", 10,
 "Where an order's stock comes from becomes an interface, <code>StockSource</code>: our warehouse behind one "
 "implementation, the seller's API behind another. PhonePe's prompt puts every item of an order with one seller, so no "
 "order needs all or nothing across two sources. The seller's reserve is a network call, so it gets the bank's "
 "treatment. It runs outside the store's lock, before the order is written, and carries our order id, so a retry is "
 "applied once. A timeout means we do not know whether he blocked the units, so the adapter releases by order id (safe "
 "either way) and refuses the order (test 15). Paid means confirm; expired or cancelled means release, and a failed "
 "release waits on a retry list.",
 X("external seller", "persistence")),

("Many machines now. PhonePe asked: how do you lock ten pens in a distributed environment? And a flash sale on one product?", "twist", 10,
 "The lock moves into the database, and each line becomes one conditional UPDATE: <code>UPDATE stock SET available = "
 "available - 2, reserved = reserved + 2 WHERE sku = 'PEN' AND available &gt;= 2</code>. One row updated means you got "
 "the pens; zero means somebody else did. A multi-line order runs its updates in one transaction, in SKU order, and "
 "rolls back on the first zero. The hold becomes the order row's status and <code>hold_until</code>. The idempotency key "
 "becomes a UNIQUE index, so a retried INSERT fails and the retry reads the order it made. Redis answers the same "
 "question with a script that checks and takes in one step, plus a key that expires after five minutes. A flash sale "
 "puts a million requests on one row, so a sold-out gate in memory turns away everyone after the last unit, and only "
 "that many buyers ever reach the database.",
 X("persistence", "client retry") + "\n" + X("sold-out gate", "background sweeper")),

("Where does time come from, and how do you test a five-minute hold without waiting five minutes?", "design", 5,
 "The store is handed a <code>Clock</code>, a one-method interface, and reads the time nowhere else: the hold's end, "
 "the sweep and the late-payment check all ask that clock. A test keeps the time in a variable and moves it. It places "
 "the order at 10:00, sets 10:04:59.999 and sees the kurtis still held, then sets 10:05:00.000 and sees them for "
 "sale. The late-payment test goes further: its fake bank moves the clock to 10:06 inside the charge. So \"the bank "
 "answered after the hold ended\" happens on every run. Nothing sleeps, so nothing is flaky; only the background "
 "sweeper, which is about real time, waits for real.",
 T("        // 3. the hold ends", "        // 5. a declined card")),

("Which pattern is where, and why did each one earn its place?", "design", 5,
 "Each one is what a move produced, so name the move, then the line. Strategy is move 3: pricing and the bank will "
 "change, so each sits behind an interface the store is handed. Decorator is how discounts combine: each wraps the rule "
 "before it, so a new offer needs no new interface. Observer is move 4's rule that nothing slow runs inside the lock: "
 "the store publishes its events after the unlock. State is move 6: the order's life as a table. The idempotency key "
 "is not a Gang of Four pattern, but it is the one an order-system interviewer is listening for. Say the absences too: "
 "no Singleton, no Factory until coupons come from config, no Builder.",
 "// Strategy: a rule behind an interface, handed in\ninterface PricingRule { Quote price(List<Line> lines); }\n"
 "store.configure(pricing, bank, Store.HOLD_MS);\n\n"
 "// Decorator: a rule that wraps the rule before it\n"
 "new FlatOff(new PercentOff(new ListPrice(), \"SAVE10\", 10, 100_00), \"FLAT100\", 100_00, 999_00)\n\n"
 "// Observer: the store announces after the unlock; it never learns who listens\n"
 "interface StoreObserver { void onEvent(StoreEvent e); }\n"
 "} finally { lock.unlock(); runAfter(after); }      // runAfter calls publish(e)\n\n"
 "// State: the life cycle as a table; a move not in it throws\n"
 "NEXT.put(PENDING_PAYMENT, EnumSet.of(CONFIRMED, CANCELLED, EXPIRED));\n\n"
 "// Idempotency key: the same request is the same order; the same payment is the same charge\n"
 "byKey.computeIfAbsent(userId, u -> new HashMap<>()).put(key, o.id);      bank.charge(o.id, o.totalPaise());\n"),

("Which SOLID letter is where in this code?", "design", 5,
 "S: each class has one reason to change. Stock changes only with the rules for its counts, Cart with the cart, "
 "CouponBook with the coupon limits, Order with the life cycle, and the store with the flow. O: buy-two-get-one, the "
 "best-of rule and the per-SKU locks were new classes, and the store was never opened. L: any PricingRule drops in, "
 "and the store never asks which one it got. I: the interfaces are small, one job each, so a test's fake is a lambda or "
 "a few lines. PaymentGateway's one job, moving money, has two methods, because a refund exists only for a charge. D: "
 "the store depends on the interfaces it is handed, which is why a test can hand it a bank that answers six minutes "
 "late.",
 "// S: one reason to change each\nfinal class Stock { /* its three counts */ }   final class Cart { /* its items */ }   "
 "final class Store { /* the flow + the lock */ }\n"
 "// O: a new offer is a new class and one changed line; Store is never opened\n"
 "store.configure(new BuyXGetY(new ListPrice(), \"PEN\", 2, 1), bank, Store.HOLD_MS);\n"
 "// L: any rule drops in; the store never asks which one it got\nQuote plain = pricing.price(lines);\n"
 "// I: small interfaces, one job each\ninterface Clock { long nowMs(); }   interface StoreObserver { void onEvent(StoreEvent e); }\n"
 "// D: depend on interfaces; a test hands in a late bank and a clock it moves\n"
 "store.configure(new ListPrice(), lateBank, Store.HOLD_MS);   store.setClock(() -> now[0]);\n"),

("An enum of order states, or a class per state? And where would a Factory pay?", "design", 3,
 "An enum plus a table, until a state grows behaviour of its own. Five states whose whole job is \"which move is legal "
 "next\" are data: one row each, and a new state (SHIPPED) is one more row with nothing edited. A state earns a class "
 "the day it must do something of its own. Cash on delivery is the example: the order is confirmed with no payment, "
 "and the money is collected at the door. That state would be a class with its own confirm step. A Factory pays when "
 "coupons arrive as lines from an admin screen instead of being typed in code. Then one parser maps a kind to a rule, "
 "instead of a switch that grows in every caller.",
 X("coupons from config", "Runs every extension")),
]

build(dict(
    slug="inventory-orders", title="Inventory, Cart and Orders",
    subtitle="LLD &middot; Java &middot; OpenJDK 21 &middot; stock holds, checkout, coupons &middot; demo, 92 checks and a 100-buyer race pass",
    problem_body=PROBLEM_BODY,
    derivation_lead=("Run these on any LLD (parking lot, BookMyShow, Splitwise) and the class diagram, the lock, the "
                     "tests, the patterns, SOLID and the answer to every twist fall out in that order; nothing is "
                     "chosen up front, and nothing is named before the move that produced it."),
    moves=[(t, MV[k], txt) for (t, txt, k) in MOVES],
    uml_svg=UMLSVG, how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", src), ("Extensions.java", ext), ("FailureTests.java", tests)],
    test_class="FailureTests",
    implement_card_html=IMPLEMENT,
    followups=FU,
))
