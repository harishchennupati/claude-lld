# Tic-Tac-Toe review (2026-09-26)

**Build:** `guard: compiles; FailureTests ALL PASS`. `_verify`: guard OK, js ok, 5 steps, 17 copy buttons, 16 cards, 12 moves, no thin steps, 0 fragment bullets. `java Main` and `java ExtDemo` exit 0. Tests: 9 blocks and 37 checks (was 8 and 32). Every new check failed on the pre-review code.

**Bugs**
1. S1: the move clock checked outside the lock and could time out a seat that moved in time. Fix: `Game.abandonIfIdle` checks and abandons in one locked step. Test: "a seat that moved at 29 s is not timed out by a tick at 31 s".
2. S2: `undo()` revived an ABANDONED game and deleted a legal move. Fix: refused. Test: "undo cannot revive an abandoned game…".
3. S2: a mid-game undo sent no event, so spectators kept a removed mark. Fix: `onUndo`. Test: "a mid-game undo is announced…".
4. S2: MoveLog keyed seats by name, so two seats called Sam broke the restore. Fix: key by symbol index. Test: "…both called Sam is restored…".
5. S2: the page contradicted the code. The evening story was impossible, and a duplicate tap gets NOT_YOUR_TURN, not CELL_TAKEN. Also false: "same counters" (Connect-4), "rendering never under the lock", "append-only".
6. S2: wrong lock timings. Measured: 35-75 ns a move (page: 0.4 us), and about 10 us per hand-off.

**English:** about 35 fixes and ten definitions, e.g.:
- "owns nothing: pure" -> "owns no game state"
- "daemon thread… adding latency" -> "background thread… slowing the game"
- "the only method… that changes anything" -> "the only class"

**Added** (folded in; still 14 cards)
- LeetCode 348's single +1/-1 counter (FU5; tagged Amazon, Google, Microsoft, Uber).
- Databricks 2026 "Rectangular K-in-a-Row" (FU1).
- Connect-4's 7 x 6 board and only-door rule (FU7; Salesforce 2026, Hello Interview).
- The implement card names the must-write core.

**Not changed / unsure**
- First-hand reports came from the parallel landscape files (search budget spent).
- `abandon(why)` ignores `why`.
- ScoreBoard could lose a point if an undo races a second win.
- MatchHistory is single-threaded.
- Board stays square.
