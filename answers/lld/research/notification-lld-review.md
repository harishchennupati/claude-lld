# Notification review, 2026-09-27

**Build:** `guard: compiles; FailureTests ALL PASS`. `_verify.py`: guard OK, js ok, 5 steps, 20 copy buttons, 19 cards, 12 moves, no thin steps, 0 fragment bullets. `java Main` (was 12 s, now 0.2 s) and `java ExtDemo` exit 0. 79 checks in 16 blocks, 40/40 runs pass; the new checks fail 10 times on old code.

**Bugs** (test):
- S1: a message parked for quiet hours skipped the later guards: a client retry at 3am became two messages at 8, a 7am mute was ignored, the cap never counted it. Every guard now runs again at wake-up (11).
- S1: a cancelled push later became EXPIRED, and the ladder texted the user. Finished states now share one rank; only DELIVERED is higher (12).
- S1: two digests in one millisecond shared a clock-made key; the second was lost (13).
- S2: "India, UTC+5" as an int offset; a 03:40 promo went out at 08:40. Now a ZoneId and 08:00 sharp (6).
- S3: pacer chunks were views of the caller's list; a clock stepped back an hour blocked sends for an hour (13).
- S2 page: "a fake is a lambda" (Sender has two methods); move-8 arithmetic; de-dup claim keyed on our own id; a fake "outbox"; move-6 arrows through labels. The diagram now shows every class.

**English:** about 45 fixes:
- "an idempotency key with a de-dup window" -> "...(a unique id for this request)... (say one minute)"
- one 70-word sentence -> "They may have unsubscribed. They may have had twenty already today..."
- "resets itself without a sweeper" -> "resets the count on first use, with no clean-up job"

**Added:** Cleartrip order events (2025, 2026); Microsoft's two a day, the rest tomorrow (2024); Ajio's in-order sending (2023). Folded in: Amazon's 5,000/min limit and per-user log (2026), Kotak's template APIs (2026), Adobe's opened/clicked (2025). Page 05 re-ranked by this evidence; the implement card names the 300-line core.

**Not changed:** four cards (quiet hours, starvation, digest, ladder) lack first-hand evidence, kept. A message parked twice keeps its first reason. Prose grew about 950 words.
