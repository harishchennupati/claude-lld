# file-system review (2026-09-27)

**Verify.** `guard: compiles; FailureTests ALL PASS` (58 checks, was 34). `_verify.py`: guard OK, js ok, 5 steps, 21 copy buttons, 20 cards, 12 moves, no thin steps, 0 fragment bullets; shots of steps 1, 2, 5 clean. `java Main`, `java ExtDemo` exit 0.

**Bugs** (every new check fails on the old code):
- S1 `JournaledFs` journaled refused calls, so replay crashed or revived them. Now apply, then journal (test 13).
- S1 A failed `Trash.restore` lost its record, stranding the file. Now claim, move, put back (test 14).
- S1 `StripedNamespace` locked the root exclusively, so nothing overlapped. Now shared ancestors, exclusive target (test 15).
- S2 Read-only `/etc` let rm, mv and mkdir through; every change now asks the guard (test 5b).
- S2 Watchers missed moves out and ancestor deletes (test 12).
- S2 Paging copied every name: 7,303 ms, now 17 ms (test 16).
- S2 Symlink `..` was resolved as text (test 17).
- S4 `mkdir -p` on a file, `move(x, x)` (tests 1, 3); volatile mtime, single `close`, 2 GB cap.
- Page facts fixed: lock order, "no downcast", Iterator row, 64 KB write (5 us, not 14), loss 1,700-2,900.

**English.** About 80 fixes: 27 terms defined, about 40 sentences split.
- "Shape changes take no file lock at all" -> "A shape change may take a file's lock, but always second."
- "harmless because each one is idempotent" -> "a refused call throws before its line exists."
- "two invariants here and not one" -> "(an invariant is a rule that must hold at every moment)".

**Added (15 -> 18 cards).**
- LeetCode 588 create-or-append and strict mkdir: Airbnb, Coupang, Adobe, Coinbase, TikTok (test 18).
- cd, pwd, `~` and `*`: Uber Bangalore, Microsoft Hyderabad, Meta, eBay, Tekion (test 19).
- O(1) du: Atlassian, Google, Datadog (test 20).

**Unsure / not changed.**
- 7,500 words (was 6,576): about 80-85 minutes, the top of the band.
- Permissions and trash kept on weak evidence; a quota set below current usage blocks shrinking writes.
- Cloud storage: levels 1-2 partly covered, 3-4 not. Amazon find: covered except symlinks and streaming.
