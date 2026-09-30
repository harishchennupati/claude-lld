# Rate Limiter review (2026-09-26)

**Verify:** `guard: compiles; FailureTests ALL PASS`. `_verify.py`: guard OK, js ok, steps 5, copy buttons 20, cards 19, moves 12, no thin steps, 0 fragment bullets. Main and ExtDemo run clean; FailureTests passed 15 of 15 runs. New bug checks fail on the old code; block 13 on a mutant.

**Bugs** (test block)
- S1: a call bigger than the bucket got a Retry-After that never succeeds. Fix: `capacity()`, `Decision.never` (10).
- S1: CasBucket moved its clock back on a stale read, minting 5 permits. Fix: `max(now, atMs)` (14).
- S1: GCRA rounded up (burst 2, not 3, at 3/s). Fix: exact integer units (9).
- S2: wrong Retry-After in the sliding counter and log (12). An unknown key's `remaining()` gave the burst under window algorithms (11). Refusals reported 0 left (10).
- S2: Redis stand-in used pod clocks; Lua moved `ts` back. Fix: Redis `TIME` (15).
- S2: sweeper race claimed tested, was not; new re-entrant-lock test (13).
- S2: cut BucketRepository (read-then-write; its SQL never refilled).
- S2 page: a State pattern the code lacks; "LayeredLimiter takes any Limiter"; moves 7-8 numbers now measured (11 ns per allow; slowest of 100 threads ~15 µs; 340 B per key).

**English:** ~24 terms defined; sentences over 33 words: 70 → 2.
- 93-word "interviewer watches" list → five short sentences.
- "ConcurrentHashMap, which needs no lock of its own" → "safe to share without a lock around it: reads take no lock; a write locks only its slot".
- Move 2 contradicted its own rule → now says why the algorithm gets the method.

**Added:** Atlassian credits card (LC 4133665, 2023; 6344788, 2025); LeetCode 362 hit-counter card (Intuit 2024, Cloudflare 2025, Uber 2026, Databricks 2023/25). Folded in: composed rules and byte budgets (Cursor 2026, Cloudflare 2025), debug-and-optimize (OpenAI 2026), bounded wait queue (Plaid 2026).

**Not changed:** KeyState keeps every algorithm's fields (documented); the token bucket stays on double; a late refund can over-credit (documented); the layered refund is exact in the final count, not strictly atomic. Prose: 6,265 → 6,766 words (the two new cards).
