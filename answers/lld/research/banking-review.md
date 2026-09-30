# Banking review (2026-09-26)

**Build:** `guard: compiles; FailureTests ALL PASS`. `_verify.py`: guard OK, js ok, 5 steps, 16 copy buttons, 15 cards, 12 moves, no thin steps. `java Main`, `java ExtDemo`: clean. Checks: 41 to 58. The new ones fail 21 times on the old code; the joint race fails 10/10 old runs, passes 25/25 new.

**Bugs** (test number):
- S1: the fee was asked after the money moved. A failing policy left no receipt, so a retry paid twice; a fee could pass the overdraft limit. Now asked first (16).
- S1: a midnight deposit counted for the day before: INR 76.71 (4 days) where the page says 3; now INR 65.75 (4).
- S1: a clock stepping back reordered the ledger, so statements missed rows (17).
- S1: the joint account changed its approval maps outside the lock (19).
- S1: `Loan.pay` run twice cut the amount owed twice (20).
- S1: the database version kept a refused id claimed, so a retry "succeeded" without moving money (21).
- S2: one frozen account stopped the batch (18); a reused id returned another transfer's receipt (10); frozen accounts could close (9); the penalty could make savings negative, which RBI forbids (5). Page text fixed to match.
- S3: two fields not volatile (23); negative opening balances allowed (22).

**English:** about 50 fixes, e.g. "makes the wait graph acyclic" became "every thread takes the lower account id first". "A fold over the ledger" became "re-added from the ledger on every read". "Reentrant" gained "(the thread that holds it may take it again)".

**Added** (inside existing cards): tryLock, FOR UPDATE and a version column (Revolut, 2026); double entry (Coinbase); a 24-hour spend limit (Ramp, 2026, weak); LeetCode 2043 (Capital One).

**CodeSignal levels:** 1 covered; 2 no; 3 partly (repeating payments, no cancel); 4 partly (balance at a past time, no merge).

**Not changed:** kept the minimum-balance, joint, KYC, loan and freeze cards without interview evidence. Two different transfers under one id at the same instant can both move money. The prose grew by 800 words.
