# Ride sharing: review report (2026-09-27)

**Guard:** `guard: compiles; FailureTests ALL PASS` (18 blocks, 90 checks, 8 runs in a row).
**_verify:** guard OK, js ok, 5 steps, 20 copy buttons, 19 cards, 12 moves, no thin steps, 0 fragment bullets. Main and ExtDemo exit 0. Screenshots checked.

**Bugs.** Every new check failed on the `.pre-review` code.
- S1: when a matching rule or the clock threw, `requestRide` locked the rider out and left a claimed car RESERVED forever. Fix: `finally` hands both back. Test 10.
- S1: `retryPayment` on a running trip spent the trip's key on 0 paise, so the real end was billed 0.00. Fix: refused unless COMPLETED_UNPAID. Test 11.
- S1: `endTrip` took −10 km, NaN or ∞ (it charged −65.00). Fix: an input check plus exact arithmetic. Test 12.
- S1: a duplicate Driver object under a known id stayed matchable after the driver went offline. Fix: refused. Test 13.
- S1: racing pings left one driver in 1,595 grid cells. Fix: a per-driver `compute()`. Test 14.
- S2, extensions: widening stopped at a busy car; surge compared 1 cell of demand with 9 of supply; a 120% coupon gave −34.40; an unknown quote was billed at 1.0x. Test 15.
- S2, page: "159 lost races" (actually 36 to 219); 60 µs per request (measured ~20).
- S3: `startTrip` ignored `board()`.

**English:** about 65 fixes.
- "mutual exclusion" → "places two riders can collide"
- "serialised" → "settled one at a time"
- "a named seam" → "plugs in later behind an interface"

**Follow-ups added** (17 cards, ranked by evidence):
- New card: car-pool offer/select (Swiggy/MMT 2026).
- New card: Nykaa's five nearest cars, first come first served, and route history (2025).
- Offers with accept/decline history (Zepto, Salesforce, Uber).
- Schema (Zepto, Arcesium), ETA by vehicle (Paytm), nearest-then-rating.

**Unsure:**
- No first-hand report of "nearest, then rating".
- A declined cancellation fee is only logged.
- The strict first-come queue points to the food-delivery page instead of being built.
- The prose grew about 12%.
