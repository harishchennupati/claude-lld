# Elevator review (2026-09-26)

`guard: compiles; FailureTests ALL PASS`. Verify: `guard: OK`, `js: ok`, `steps: 5`, `copy buttons: 20 | cards: 19 | moves: 12`, `thin steps: none`, `fragment bullets: 0`. Main and ExtDemo run clean; 63 checks; every bug check fails on old code.

**Bugs**
- S1 `cost()` over-charged two of six cases (36 floors, not 20), sending a slower car. Test "8 DOWN goes to car 0".
- S1 Snapshots published after unlock arrive out of order, so `MaintenanceMonitor` over-counted. Added `version` and an odometer. Test "maintenance count equals the floors really moved" (old: 30/30 fail).
- S1 Destination dispatch pressed the rider's floor before boarding, stranding them; now pressed at boarding. Test "opened at 10 ... then at 17".
- S2 Fire recall obeyed car buttons; recall is now a bank mode. Test "during recall the buttons inside a car do nothing".
- S2 Lobby estimate counted cars that cannot reach the floor (3 vs 7). Test "the board says 7 floors".
- S2 Page vs code: replay wait 2000 → 1500 ms; a phantom queue tie-break; lock hold 2.5 → ~0.6 µs measured (moves 7-8 redone); "unbounded" wait despite its 38-floor bound; IDLE now entered from DOORS_OPEN.
- S4 Door buttons "worked" out of service; out-of-order car ids picked the wrong car (both tested); rule swaps now take the lock.

**English**: about 45 fixes (15 terms defined, 30 splits). "like a disk head" → "like the arm of an old hard disk"; "so the bank is deterministic" → "so the same presses always send the same car"; "Sticky assignment was an assumption" → "Assignment is sticky (a call stays with the car that took it)".

**Added** (17 cards now): five-stop request feasibility (Microsoft 2024, LC 6154075); fire recall as its own card. Folds: maintenance mode and restart after a power cut (Microsoft 2025, LC 7357425), an energy rule (Adobe 2025, LC 6474852), cancel a floor (Hello Interview).

**Not changed**: an idle car clears both lamps at its floor; same-floor keypad riders share one car (needs a trip-keyed index; stated); recall doesn't hold doors open. Prose +12.5%.
