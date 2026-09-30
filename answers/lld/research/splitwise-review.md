# Splitwise review (2026-09-26)

**Build:** `guard: compiles; FailureTests ALL PASS` (15 scenarios, 59 checks). `_verify.py`: guard OK, js ok, 5 steps, 21 copy buttons, 20 cards, 12 moves, no thin steps, 0 fragments. `java Main` and `java ExtDemo` ran with no exception.

**Bugs** (each new check fails on the old code):
- S1 `Friends.between` looked the group up, then created it, and lost an expense in 186 of 300 races. Fix: `groupOrCreate`. Test 13 "two friends creating their pair".
- S1 `newGroup` used `put`, replacing a group and its balances. Fix: `putIfAbsent`. Test 13 "second group with the same id is refused".
- S1 `removeMember` checked only the net. Main's demo let carol leave while bob owed her 150.00 and she owed alice 150.00. Fix: `Ledger.passThrough`. Test 11 "no pair names her".
- S1 Editing or deleting a leaver's expense reopened her balance. Now refused. Test 11 "cannot be deleted", "nor edited".
- S1 `members()` returned a live view of a lock-guarded set. Now a copy. Test 11 "members() handed out a copy".
- S4 `Recurring` with period 0 looped forever (test 13).
- S2 false page claims: "fewest payments" (greedy makes 4 where 3 do), "fifty threads" (the pool had 8), "~20 hash ops" (really ~40), "lock-free", the persistence SQL, "five fields", a diagram overlap.

**English:** ~40 fixes. Examples:
- "serialised for about two microseconds" -> "take turns, each holding the lock..."
- "apply the deltas" -> "apply the changes to the balances"
- a 98-word sentence -> "First... Second... Third..."

**Added (16 -> 18 cards):**
- FU 10, the true minimum (LeetCode 465): `FewestPayments` and test 14. Asked by Amazon AWS 2025, Locus 2026, Winzo 2025, Rippling 2024 and Goldman 2025.
- FU 13, a balance across groups and joining one: `addMember`, `Directory` and test 15. Asked by Acko 2026, Groww 2022/2024 and Flipkart.
- Folded in: the passbook (Razorpay, Slice), the tables (PhonePe, Amazon), double's percent bug.

**Not changed:** a reused id with a different bill returns the first expense; multiple payers (only codezym asks); a 30-day month. Reddit and Blind were not searched.
