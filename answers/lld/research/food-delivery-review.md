# Food Delivery review (2026-09-27)

**Build:** `guard: compiles; FailureTests ALL PASS` (60 checks, was 38). `_verify.py`: guard OK, js ok, 5 steps, 21 copy buttons, 20 cards, 12 moves, no thin steps. `java Main` and `java ExtDemo` exit 0. Screenshots of pages 1, 2, 3, 5: every label fits.

**Bugs** (each new check failed on the old code):
- S1: a cancel landing mid-dispatch stranded the rider on a cancelled order. `takePartner` now runs under the order lock, only while READY. Test 12.
- S1: two riders freed at once left a waiting order beside an idle rider. The drain now runs until riders or orders run out. Test 13.
- S1: a failing refund skipped the rider hand-back and lost the money. The hand-back now comes first; the refund is written as REFUND_OWED and swept. Test 15.
- S1 (ext): an accepted offer never attached the rider. Test 16.
- S2: a rider logging in never served the queue; pickup needed no rider (test 14). Idempotency keys were shared across customers (test 8).
- S2 (ext): the scheduler ignored the ride, wiped her open cart, and one failed booking blocked the rest. Test 17.
- S2 text: "one ten-thousandth" busy (really one ten-millionth), "seven fields" (eight), "before ACCEPTED" (PREPARING), Observer's move, the diagram's ownership list.

**English:** about 60 fixes; sentences over 30 words 68 to 32 (parking lot 42).
- "Three apps are driving the same order — ... — and none..., so..." -> two short sentences.
- "genuinely contended" -> "contended (wanted by two callers at the same instant)".
- "a lock busy one ten-thousandth" -> "about one ten-millionth".

**Added:** card 17, Flipkart FoodKart (2022 statement): pincodes, ratings, sorted list. Card 18, Flipkart 2025 (three posts, landscape file) and Intuit 2024: system-picked kitchen, capacity, timestamp-ordered commands. Card 9: "accepted orders cannot be cancelled" (Flipkart 2025).

**Unsure:** web search was exhausted; evidence is GitHub statements plus the landscape file. An UNKNOWN payment still frees the key, so a retry may charge twice until the sweep refunds (the page says so). Rider ratings not added.
