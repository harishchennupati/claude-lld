# snake-ladder review (2026-09-26)

**Verify.** `guard: compiles; FailureTests ALL PASS`. `_verify.py`: guard OK, js ok, 5 steps, 19 copy buttons, 18 cards, 12 moves, 0 thin steps, 0 fragment bullets. `java Main` and `java ExtDemo` exit 0. Checks: 62 → 88.

**Bugs.** Every new check failed on the pre-review code.
- S1: clock read after the first write (a moved token, no log row). Now read first. Test "a clock that throws".
- S1: any `leave()` reset the roller's streak (bypassing three sixes). Now only the leaver's own. Test "another player leaving".
- S1: TurnTimer's two volatile fields could forfeit a just-begun turn. Now one record. Test "a sweeper ... re-armed".
- S1: IdempotentRolls rolled inside `computeIfAbsent` (a slow screen stalled other tables). Now a `putIfAbsent` claim. Test "a slow screen on one table".
- S1: `host()` replaced a same-id game. Now refused. Test "a taken id is refused".
- S1: TurnToken compared ids by reference. Removed; rung 2 is now routing by game id.
- S2: board mutable after build. Now frozen. Test "the board is frozen".
- S2: jumps did not chain (no loop check); three sixes only capped; "play on for 2nd place" was claimed but impossible. Blocks 3, 6, 12.

**English.** ~55 fixes (18 terms defined, 9 jargon phrases replaced, ~30 long sentences split).
- "would be cargo cult" → "would protect nothing"
- "busy two hundred-thousandths of one per cent" → "busy about 0.00002% of the time, one second in ten weeks"
- "a game id as the shard key" → "the game id decides which server holds a game"

**Follow-ups: 13 → 16.**
- New: chained jumps plus the loop check (workat.tech; Flipkart 2022).
- New: play to the last (workat.tech; Flipkart 2022).
- New: input lines, PhonePe config, and a random winnable board (PhonePe 2024).
- Reworked: three sixes cancel (workat.tech).
- Reworked: crocodile, mine, capture to start (PhonePe SDE2 2024).
- Reworked: dice override and several dice (PhonePe; workat.tech).
- Cut (no evidence): bot dice, teleport cells, lock-free gate.
- Swiggy 2025 and Tekion 2024 report only the base question.

**Unsure / left.**
- Max/min dice: no first-hand source; one class in card 1.
- Captures inside a later-cancelled streak are not restored.
- Reading time ~80 min (prose +16%).
