# inmem-db review (2026-09-26)

**Verify:** `guard: compiles; FailureTests ALL PASS`. `_verify.py`: guard OK, js ok, 5 steps, 19 copy buttons, 18 cards, 12 moves, no thin steps, 0 fragment bullets. `java Main` and `java ExtDemo` exit 0. 61 checks (was 49); each new check failed on the old code.

**Bugs**
- S1: a multi-row UPDATE/DELETE refused on row 2 kept row 1's change; COMMIT saved it. Fix: undo to the statement's start. Test 11.
- S1: the WAL, an after-unlock trigger, logged commits out of order (replay rebuilt the wrong row) and swallowed failed appends. Fix: a `CommitLog` appended before the unlock, not wrapped. Test 12.
- S1: `between(35, 30)` on an index threw. Fix: return empty. Test 5.
- S1: `AuditTrigger` lost lines under concurrent commits. Fix: a synchronized list. Test 8.
- S2: `CostPlanner.select` never used the cheapest path. Fix: `cheapest()`. Test 13.
- S2 prose: isolation-level definitions, interface count, MVCC's "no lock", memory math (page: 8M rows = 1 GB; measured 2.4 GB). Timings re-measured: 0.3 us/statement, about 300k transactions/s.

**English:** ~70 fixes: 33 terms defined, 27 splits, 10 jargon words.
- "where the two invariants live" -> adds "(rules that must be true at every instant)"
- "a waits-for graph with victim selection" -> "who waits for whom; a cycle is a deadlock; one transaction in it (the victim) is aborted"
- "the transaction orchestrates" -> "the transaction runs the steps"

**Added**
- Card 8: ORDER BY plus a column list, with test 14. Evidence: OpenAI 2024, Glean 2025.
- Folded in: `dropTable` and column constraints (Razorpay 2020-24); tombstones and LSM (OpenAI 2024, Rippling); log checksums and snapshots (OpenAI, Baseten 2025-26); the must-write core (implement card).

**Separate variants, already covered**
- CodeSignal: L1 and L3 partly (rows by key; clock, TTL sweeper, MVCC snapshot reads); L2 and L4 not covered.
- Nested-transaction KV: L1 and L2 yes. L3 only through `savepoint()`/`rollbackTo()`.

**Not changed:** ReentrantLock stays (the spec asks for it); a transaction must commit on its own thread, now documented. Int savepoints accept stale marks. No group commit. Page prose grew 13% (card 8, definitions).
