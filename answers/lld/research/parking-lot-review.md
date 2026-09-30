# Parking lot review (2026-09-28)

`guard: compiles; failure tests ALL PASS` (80 checks, was 70).
`_verify`: guard OK, js ok, 5 steps, 19 cards, 12 moves.
Main, ExtDemo and CommandShell run clean.
Every new test fails on .pre-review (24 does not compile).

1. **Money.** Every fee is `long` paise, including the Extensions twists. Surge is `(p*3+1)/2`: a half paisa rounds up. Paise are defined in "Say before typing". Test 21: a Rs 7.10/kWh bill is exactly 13940 paise.
2. **Retry.** `pay(key, paise)` returns OK, DECLINED or UNKNOWN. The key is the ticket id. A timeout moves the ticket to PENDING, and the retry re-sends the same key and amount. Test 22: a timeout, then a retry, charges once.
3. **Lock.** Exit is a locked step to PAYING, then the payment with no lock, then `settle()`. Moves 4 and 6-9, the UML, FU 3-5 and the implement card updated. The ladder starts at a lock per floor. Test 23 uses latches: a park finishes during a hung card, and a second checkout is refused.
4. **Gojek card.** `SlotLot` (TreeSet, two maps) plus `CommandShell` (word to handler). Cites 6371415 and 6491846. Test 24 matches the sample output exactly.
5. **Race.** The pool is now 50 threads.

**Unsure:**
- PENDING is my reading of "PAYING/pending".
- A cash retry after a card timeout is not guarded.
- CAS and DB tests keep 8 threads (text still true).
- `_verify` only shoots step 1 here (`pl.step`), so I checked the other steps myself.

## Orchestrator follow-up (2026-09-28)
Two gaps in the idempotency fix, closed by hand: (1) the key was the ticket id alone, and a real gateway keeps its FIRST answer per key, so after one declined card every later card would also be "declined"; the key is now ticket id + attempt number, bumped only after a decline (a timeout reuses it). (2) After a timeout the driver could pay cash while the card charge might have gone through; a PENDING ticket now retries on the gateway that holds the key (`pendingOn`), never in cash on top. Tests 25 and 26 fail on the code without these two changes and pass now. FU 5 text, the Ticket box (attempt, pendingOn) and the check counts (84) updated; enum boxes moved down so the taller Ticket box does not touch them.
