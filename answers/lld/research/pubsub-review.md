# Pub/Sub review (2026-09-27)

**Build:** `guard: compiles; FailureTests ALL PASS` (75 checks, was 54). `_verify.py`: guard OK, js ok, 5 steps, 18 copy buttons, 17 cards, 12 moves, no thin steps, 0 fragments. Main and ExtDemo: clean. The new checks fail 12 times on the old code.

**Bugs** (test number):
- S1 `seek(0)` mid-delivery replayed from 1, skipping 0. Now applied before the next read (13).
- S1 A filter that threw (a keyless message) killed the subscription. Now retried, then parked (14).
- S1 A stray interrupt left the dispatcher spinning at 100% CPU; a late stop() could hit a pooled thread serving another subscription. An interrupt now means stop, sent under a lock (15).
- S1 The back-pressure gate was check-then-act: 8 publishers overwrote 26 unread messages. Now exact (17).
- S1 Persistence dropped payloads with a tab or newline, restored in file order with new times, and re-stored everything (19).
- S1 A shared IdempotentHandler corrupted its map in 12 of 20 stress runs. Locked (20; a race, so not every old run fails).
- S2 Publish was O(retention): `ArrayList.remove(0)` on every full publish (7.6 us at 100k). Now a ring; moves 7-8 measured (0.3 us at 20 subscribers).
- S2 pause() let one more message through; STOPPED could be revived (10); time went backwards (16); a throwing retry policy killed the reader (9).

**English:** about 50 fixes. "a fourth subscriber costs eight bytes" -> "adds one cursor and one thread, never a copy". Follow-up 6's interrupt path rewritten to match the code. Defined at first use: fan-out, at-least-once, idempotent, ring, dispatcher, back-pressure, partitions.

**Added:** follow-up 10, pull (`consume()`/`ack()`, filter, long poll): Razorpay 2025 and 2026, codezym (tagged Flipkart, Microsoft, Uber, Salesforce), Uber 2026. Follow-up 7, guaranteed delivery for a consumer that is down: Razorpay; Uber 2025. A push/pull Ask row; the implement card names the must-write core (Amazon 2026's 30-minute version). Old follow-up 11 folded into 1 and 7; still 15 cards.

**Not changed:** codezym's explicit partition API; Razorpay's "copies for faster serving"; no timing test for O(1) publish (it would flake); the gate holds its lock while listeners run.
