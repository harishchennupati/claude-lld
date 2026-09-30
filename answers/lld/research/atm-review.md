# ATM review

**Build:** `guard: compiles; FailureTests ALL PASS` (53 checks). `_verify.py`: guard OK, js ok, 5 steps, 18 copy buttons, 17 cards, 12 moves, no thin steps, 0 fragment bullets. `java Main` and `java ExtDemo` exit 0. Every new check fails on the pre-review code.

**Bugs**
- S1: the Reconciler "asked" by debiting again, taking money that had never been debited. Fix: `BankService.reverse(key)` marks the key dead and gives back once. Test 5.
- S1: the PIN count lived on the visit, so taking the card out gave fresh tries. Fix: the bank counts per card (`PinCheck`). Test 13.
- S1: a bank call that throws leaked the reserved notes and hid the row from reconciliation. Fix: UNKNOWN. Test 14.
- S1: a jam plus a failed credit-back left the row DEBITED, never reversed. Test 15.
- S1: `deposit(-500)` debited the account, and deposits credited a typed amount. Fix: `deposit(counted notes)`. Test 16.
- S1: DailyCap used UTC days and counted jammed withdrawals. Test 17.
- S1: the state-object sketch got stuck after a retained card. Test 18.
- S2: the note push runs inside the lock (about 3 s, not 85 ms); arithmetic redone. Six smaller false statements fixed.

**English:** about 35 fixes, for example:
- "a counter on the visit ... cannot inherit the previous customer's failures" -> "a thief could take the card out after two wrong tries and put it back for three fresh ones"
- "reads-then-writes a balance" -> "reads a balance and then writes it"
- a 75-word sentence -> three

**Added:** LeetCode 2241 (2022): pure greed must refuse 600; now in FU 7, with `GreedyOnly`. Uber 2025 (L5A): "interfaces given, implement the driver"; now in the implement card. RBI 2019 rule (T+5 days, then Rs 100 a day); now in FU 5.

**Not changed / unsure:**
- Part B is thin: WebSearch was exhausted; the landscape files hold one ATM report. `atm.md` lists five candidates.
- The lock still spans the bank call and the push: deliberate (one customer), now stated honestly.
- "Fewest notes" stands: brute force found no counterexample.
