# LRU / LFU review (2026-09-27)

**Build:** `guard: compiles; FailureTests ALL PASS`. `_verify.py`: guard OK, js ok, 5 steps, 20 copy buttons, 19 cards, 12 moves, no thin steps. Its Chrome hung, so I screenshotted steps 1, 2, 3 and 5 myself: labels fit. `java Main` and `java ExtDemo` run clean. Checks: 39 to 60; all eight new bug checks fail on the old code.

**Bugs** (test):
- S1: a slow read-through load overwrote a newer put or revived a removed key. Fix: per-load tickets, memcache's "lease" (11, 12).
- S1: the TTL sweeper deleted rewritten values and reported REMOVED (13).
- S1: write-back stored the overwritten, out-of-date value (14).
- S1: per-server version counters let a later write lose; a server served a value the store refused (15).
- S1, untested: admission sketch updated outside the lock.
- S2: hidden scan in LFU eviction; now O(1) throughout (9, brute-force check).
- S2: seven false claims fixed (Redis default, Caffeine sizes, LinkedHashMap, pointer count...).
- S4: config fields volatile; negative weights refused.

**English:** about 70 fixes, e.g.
- "a synchronised wrapper, correct and five lines though it is, drags..." -> "A wrapper whose methods are all synchronized is correct and five lines long. But it drags..."
- "a sketch refuses one-hit wonders" -> "a sketch keeps one-off keys out"
- "a hot segment thrashes" -> "a hot segment keeps evicting keys it still needs"

**Added:** Q2 store plus pluggable policy (Flipkart 2024 x3, Bloomberg 2023, Microsoft 2024); Q9 fixed lifetime with O(1) average (Confluent 2024 x3); Q15 multi-level cache (PhonePe 2024, Flipkart 2025, Cleartrip 2025); Q13 memo key plus write-ahead log (Anthropic, kept short). Folded in: expire-after-access (TikTok, PhonePe), segmented LRU (Nutanix), write policies (PhonePe), rank eviction (LinkedIn). Cut: Redis-sampling card (no evidence).

**Unsure / not changed:** listener notices may arrive out of order across threads (documented). Page grew: prose +14%, Java 1,447 to 1,955 lines, about 80 minutes. WebSearch was exhausted; I ran about 13 keyword queries on LeetCode's own discuss listing before learning sibling reviews avoid that.
