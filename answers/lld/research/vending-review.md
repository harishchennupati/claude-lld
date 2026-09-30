# Vending Machine review (2026-09-26)

**Build:** `guard: compiles; FailureTests ALL PASS`. `_verify.py`: guard OK, js ok, 5 steps, 18 copy buttons, 17 cards, 12 moves, no thin steps, 0 fragment bullets. `java Main` and `java ExtDemo` exit 0. Every new check fails on the old code.

**Bugs**
- S1: `purchase()` spent a walk-up customer's coins, so a phone pocketed his Rs 20. Fix: `PURCHASE` legal only in IDLE. Test 11 "a phone purchase is refused while his coins are in".
- S1: the escrow timeout ran from the first coin, so an active customer's press threw. Fix: each coin or press restarts it. Test 9 "coins at 0 s and 20 s, a press at 31 s: it sells".
- S1: a 15% happy hour gave Rs 21.25, so nothing could sell. Fix: round down to whole rupees. Test 12.
- S1: a second hold by the same customer leaked a unit. Test 14.
- S2: on the `purchase()` path, observers ran inside the lock. Fix: private `sell()`, publish after the outer unlock. Test 6.
- S2: a card timeout left the customer charged, and failed refunds were lost. Fix: sale-id idempotency key, a refund when the outcome is unknown, a retry list. Test 14.
- S3: observer lists not thread-safe (test 6); negative restocks accepted (test 13).

**Page truth fixed:** "a second panel changes no design"; reads "never scan" (they also wait 2 s behind the motor); the DP "for arbitrary denominations" (back-off already finds any change).

**English:** about 30 fixes, for example:
- "they sit inside the machine but are still yours" -> "...in escrow (held, but still yours)"
- the 85-word ladder sentence -> "Rung one / two / three", with compare-and-set defined
- "What the table cannot show is the bottom three rows" -> "The bottom three rows are the absences"

**Follow-ups added:** none. Part B was blocked: parallel runs used up the search budget (200/200), and direct fetches returned 403, 404 or a paywall. `research/vending.md` lists 5 candidates to check.

**Not changed:** the motor stays inside the lock (stated honestly); `purchase()` still returns COLLECTED.
