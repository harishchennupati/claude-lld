# Inventory, Cart and Orders: what companies actually ask (research, 2026-09-27)

Sources: the landscape entries `inventory-order-management` and `ecommerce-cart` in `research/landscape-india-sea.json`
and `inventory-order-management` in `research/landscape-bigtech.json`. Every LeetCode Discuss post below was then read in
full through LeetCode's public GraphQL endpoint (**V** = read in full this session). codezym statements were read through
its question API (**AGG** = aggregator: company tags are the site owner's, undated, not first-hand). No web search was
used (the session budget was spent). FU n = follow-up card n on page 05; M n = move n on page 02.

## The real task, and where the page matches it

| question or level | company | year | URL | where the page answers it |
|---|---|---|---|---|
| `addProduct(productId, name, count)`, `getInventory(productId)`, `updateInventory(productId, count)` (restock), `blockInventory(productId, count, orderId)` "holds for 5 min", `confirmOrder(orderId)`: deduct on payment success, else release automatically. In memory, thread-safe for 10M users / 5M products / ~1M orders a day, race conditions explicit. The candidate used per-product locks and a cleanup thread | Meesho (SDE-3, machine coding) | 2026 | https://leetcode.com/discuss/post/7854949/ (V) | the whole page: `addProduct`, `getInventory`, `updateInventory`, `createOrder` (blocks, 5-minute hold), `confirmOrder`; M4 and FU 2 (race); FU 3 (per-product locks, SKU order, the arithmetic with Meesho's numbers); FU 4 (lazy sweep + background sweeper) |
| `addProduct(productId, quantity)`, `createOrder(orderId, products and quantities)`, `confirmOrder(orderId)`, `getStock(productId)`; "block the inventory when createOrder is called, reduce the stock when confirmOrder is called"; the interviewer wanted two counts: available and blocked-by-an-unconfirmed-order | Meesho (SDE-1, machine coding, 90 min) | 2024 | https://leetcode.com/discuss/post/5925685/ (V) | `Stock` = available / reserved / sold (M1, M2); `createOrder` blocks all lines, `confirmOrder` sells them (M6); FU 9 (block at order, not at cart) |
| Machine coding: "design an inventory/order management service"; focus on handling concurrent users and thread safety | Meesho (SDE-3, 2 h HackerRank) | 2024 | https://leetcode.com/discuss/post/5863391/ (V) | M4, M7, M8; FU 2, FU 3 |
| Flipkart-like Order Management System in 1 hour: `addItemToInventory(itemId, quantity)`, `getAvailableInventory(itemId, seller)`, `createOrder(customerId, itemsInfo, address)` (several items, one seller, provisionally reserves, returns the amount to pay, validations and error codes), `updateOrder(orderId, state)`: confirm after payment, cancel frees the stock, FULFILLED only after confirmed; INTERNAL vs EXTERNAL (seller API) inventory; optional auto-cancel after a time; "take care of race conditions" | PhonePe (SDE-2, machine coding) | 2023 | https://leetcode.com/discuss/post/3918884/ (V) | `updateInventory`, `getInventory`, `createOrder` (multi-line, total with coupon, `OrderRefused` + `Reason` as the error code), `confirmOrder`, `cancelOrder`, `fulfilOrder`; FU 7 (the state table: fulfil only from CONFIRMED); FU 12 (external seller behind `StockSource`); FU 4 (auto-expiry) |
| Review round after an e-commerce machine-coding task: "how will you lock a quantity of 10 Pen in inventory in a distributed environment?" | PhonePe (backend, 1.7 YOE) | 2023 | https://leetcode.com/discuss/post/4472947/ (V) | FU 13 (conditional UPDATE per line in one transaction, hold as an order row with `hold_until`, the Redis script with a 5-minute key) |
| Online marketplace (like Flipkart/Amazon): user login, add products, add to cart, check out the cart into an order, order history | PhonePe (machine coding, 2 h) | 2023 | https://leetcode.com/discuss/post/3605761/ (V) | `addToCart`, `viewCart`, `cartTotal`, `checkout`, `orderHistory`; FU 8 (history is one lookup) |
| Design the Swiggy cart: add / remove / delete a product, calculate the total, validate with inventory, discount, payment, notification | Swiggy (SDE-2, LLD round) | 2025 | https://leetcode.com/discuss/post/7069404/ (V) | `addToCart` (checked against available, as advice), `removeFromCart`, `cartTotal`; FU 1 (discount rules); `PaymentGateway` (M3); FU 10 (notification) |
| "LLD code of Cart Service", production-ready with design patterns and concurrency; the one question asked afterwards: "API retry strategy" | Cars24 (SDE-2) | 2024 | https://leetcode.com/discuss/post/5050216/ (V) | FU 6 (idempotency key + retry only timeouts, exponential backoff with full jitter, `RetryingClient`) |
| "Design Shopify": many stores (tenants), a catalogue per store, correct inventory counts that never go negative, a cart, an order of one or more products from one store, a pluggable payment interface; concurrency "not required upfront" | Harness (Senior SDE, LLD) | 2026 | https://leetcode.com/discuss/post/7560806/ (V) | the core (never negative: `Stock` refuses; test 13 checks every unit); `PaymentGateway` (M3); FU 3 (`Platform`: a store per tenant, one lock each) |
| Inventory management system: "only one unit left and two users order at the same time: how do you stop both succeeding?"; race conditions, concurrent updates, locking / transaction approaches (asked as HLD by mistake in an LLD slot) | Amazon (SDE-2, Bangalore) | 2026 | https://leetcode.com/discuss/post/8512004/ (V) | M4; FU 2 (the race test); FU 13 (the same race decided by the database row) |
| "Design an order processing engine to handle multiple orders where one order can come multiple times due to network issues and retries" | Amazon (SDE-2, LLD round) | 2026 | https://leetcode.com/discuss/post/7622801/ (V) | FU 6 (idempotency key per buyer; twenty copies at once make one order, test 7); the order id as the bank's key (FU 5, test 6) |
| Inventory management system (data storage, stock updates, consistency); promotion round: the same design for high concurrency, multithreading and scale | Google (L5) | 2025 | https://leetcode.com/discuss/post/6552739/ (V) | M7, M8 (the arithmetic and the ladder); FU 3; FU 13 |
| LLD for an inventory management system (60-min round with a coding question) | Licious (SDE-2) | 2023 | https://leetcode.com/discuss/post/3846272/ (V; the post names the topic only) | the whole page |
| Design of an order management system: key components, API contracts and DB design (hiring-manager round) | Walmart (IN3, Bangalore) | 2023 | https://leetcode.com/discuss/post/4374203/ (V) | pages 01-03; FU 13 (`Sql.SCHEMA`: stock, orders with a UNIQUE (user, key), order_lines) |
| Order and inventory management, multi-threaded: sellers with serviceable pincodes and payment modes, `addInventory(productId, sellerId, delta)`, `getInventory(productId, sellerId)`, `createOrder(orderId, pincode, sellerId, productId, count, paymentMode)` -> "order placed" / "pincode unserviceable" / "payment mode not supported" / "insufficient product inventory" | tags: Intuit, Amazon, Flipkart, Meesho, Licious, Wayfair, TikTok, DE Shaw, apna (AGG) | undated | https://codezym.com/question/4 (AGG) | FU 11 (sites that serve pincodes; `OneSiteElseSplit`; the two refusal strings). Payment modes per seller: not coded (a set check on the seller) |
| Shopping cart: `addItem` -> UNAVAILABLE / OUT OF STOCK / SUCCESS, `viewCart()` sorted by item id, `checkout()` returns the total, -1 on an empty cart | tags: PayPal, Amazon, Walmart, Microsoft, Salesforce, Meesho, Myntra (AGG) | undated | https://codezym.com/question/41 (AGG) | `addToCart` (UNKNOWN_PRODUCT / OUT_OF_STOCK), `Cart` kept in SKU order, `cartTotal`, `EMPTY_ORDER` |
| Billing and discounts: P10 / P20 (only the best percentage counts), FLAT100 only if subtotal >= 500, points capped at 20%; a fixed order of application; integer maths rounded down; the same code twice must not stack; payable never below zero | tags: Flipkart, Cleartrip (AGG) | undated | https://codezym.com/question/73 (AGG) | FU 1: the wrapping order, `FlatOff` checks the subtotal, `PercentOff` rounds down, `Quote.less` never below zero, `BestOf` (never stacks, test 15). Points redemption: not coded |
| Checkout and payment states: CREATED, PAYMENT_IN_PROGRESS, PAID, PAYMENT_FAILED, CANCELLED, CANCELLED_REFUND_DUE (a paid order cancelled needs a refund) | tags: Goldman Sachs (AGG) | undated | https://codezym.com/question/134 (AGG) | FU 7 (cancel after payment refunds); FU 5 (declined stays payable; late money refunded) |

## Follow-ups on page 05, ranked by how often these companies ask them

| FU | question | evidence |
|---|---|---|
| 1 | discounts: percent with a cap, flat above a minimum, buy 2 get 1, codes must not stack | Swiggy 2025 (V); Flipkart / Cleartrip billing (AGG) |
| 2 | 100 buyers, 10 pens: prove no oversell | Amazon 2026 (V); Meesho 2024, 2026 (V); PhonePe 2023 (V); Harness 2026 (V) |
| 3 | one lock for 5M products and 10M users? per-SKU locks; many stores | Meesho 2026 (V); Google 2025 (V); Harness 2026 (V); landscape "lock granularity" (Amazon, Google, Intuit) |
| 4 | the unpaid block ends by itself: who, when | Meesho 2024, 2026 (V); PhonePe 2023 optional (V) |
| 5 | late or unknown payment: stock and money | Goldman checkout states (AGG); Amazon 2026 retries (V); the design brief |
| 6 | the same request twice; the client's retry | Amazon 2026 (V); Cars24 2024 (V) |
| 7 | cancel before / after payment; fulfil only confirmed | PhonePe 2023 (V); Goldman (AGG) |
| 8 | getInventory at 10,000/s; order history | Meesho 2026 (reads kept off the product lock) (V); PhonePe 2023 marketplace (V) |
| 9 | block at add-to-cart or at checkout? price changes | Meesho 2024 SDE-1 (V); Swiggy 2025 (V); codezym cart (AGG) |
| 10 | notifications; back in stock | Swiggy 2025 (V); the design brief (back in stock: no first-hand report) |
| 11 | several warehouses / sellers by pincode; split | codezym q4 (AGG); landscape bigtech prompt "across warehouses" |
| 12 | external seller stock via API | PhonePe 2023 (V) |
| 13 | many machines: lock 10 pens; a flash sale | PhonePe 2023 review (V); Walmart 2023 DB design (V); Google 2025 (V). Flash sale as its own LLD: no first-hand report (landscape: Agoda HLD only), so it is folded into this card |
| 14-17 | time, patterns, SOLID, enum vs class + Factory | the page format (every page has them) |

## Asked for in the design brief but with no first-hand report, so kept small or left out
- Cart merge on login (guest cart into the user's cart): no report found; not on the page.
- Back-in-stock alerts: folded into FU 10 next to Swiggy's notifications (listener code + test), not a card of its own.
- Flash sale on one hot SKU: folded into FU 13 (the sold-out gate), not a card of its own.
- Per-user coupon limits: no interview report names them; kept inside FU 1 and test 8 because the race on a limited coupon is the same race as the stock.
