# bookmyshow review (2026-09-26)

**Gates:** `guard: compiles; FailureTests ALL PASS` (53 checks, was 41). `_verify.py`: guard OK, js ok, 5 steps, 19 copy buttons, 18 cards, 12 moves, no thin steps, 0 fragment bullets. `java Main`, `java ExtDemo` exit 0. Five pages screenshotted.

**Bugs** (the new checks on the old code: all 9 FAIL; now PASS)
- S1: `charge` took no idempotency key. A timeout then Pay again charged twice; so did two taps at once. Fix: `charge(bookingId, paise)`. Test #12.
- S1: `release` sent EXPIRED for a CONFIRMED booking (a false SMS). Fix: it returns boolean. Test #14.
- S1: an empty hold or 0 seats made a free booking; a coupon over 100% gave -12,500 paise. Both refused. Test #15.
- S1: `SeatCap` never returned quota when a hold lapsed. Fix: count live seats only. Test #9b.
- S1: CAS group holds in opposite orders could both fail (18 in 20,000 old rounds). Fix: seat-id order. Test #16.
- S2: the webhook extension charged the card; `settle` asked about a key the gateway never saw; the SQL could re-sell a SOLD row; search walked every day. All fixed; test #13.
- S4: a `double` surge factor; rule fields not `volatile` (untestable).

**English:** about 45 fixes; sentences over 34 words went from 44 to 26, mostly lists now.
- "the load-bearing rule" -> "the rule that must always hold (the invariant)"
- "the three rules through configure()" -> "pricing and seat choice through configure()"
- "The pre-check before charging is advisory" -> "The status check before charging only refuses a booking that is already over"

**Added** (evidence: `research/bookmyshow.md`), still 16 cards:
- FU 13: tables, optimistic vs pessimistic locking, ACID, TTL (Flipkart 2024 and GRiD 2025, Rippling, Paytm).
- FU 5/6: idempotent checkout (Flipkart 2024, Tekion).
- FU 8: "list cinemas showing a movie" (codezym: Uber, Amazon, Microsoft).

**Not changed:** "about 2 us inside the lock" stays as a cautious figure (a laptop measures 0.1 us). A second confirm after success still throws. Not added: train segment re-sale (needs its own page), spot-the-bug (one report), single-seat gap (no evidence).
