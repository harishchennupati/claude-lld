# Review pass tracker (2026-09-26, REVIEW-RUBRIC.md) — technical truth + plain English + company follow-ups
OLD QUEUE LINE (see status block below): chess logger notification-lld stackoverflow order-book pubsub ride-sharing text-editor spreadsheet digital-wallet payment-gateway cache-eviction mt-blocking-queue mt-producer-consumer mt-rwlock mt-ttl-cache mt-striped-map mt-dining mt-h2o mt-print-series parking-lot(tech+coverage only; English approved)
Research (running): research/landscape-{bigtech,ailabs,india-sea}.{md,json}

| slug | status | S1 bugs | notes |
|---|---|---|---|
| vending | DONE | 4 (walk-up coins spent by phone purchase; escrow timeout from first coin; 15% discount -> Rs 21.25 unsellable; double hold leaked unit) | follow-ups: none added (search budget) |
| tic-tac-toe | DONE | 1 (move clock checked outside lock) + 5 S2 | LC348 counter, Databricks K-in-a-row, Connect-4 folded in |
| banking | DONE | 6 S1 (fee asked after money moved -> double pay on retry; midnight deposit interest day; clock step-back reordered ledger; joint approvals outside lock; Loan.pay twice; DB refused id stayed claimed) | CodeSignal levels: L1 yes, L2 no, L3/L4 partial -> separate cs-bank page |
| splitwise | DONE | 5 S1 (between() lost expenses in races; newGroup put replaced group; removeMember checked only net; edit/delete reopened leaver; live members view) | +LC465 true minimum, cross-group balances |
| bookmyshow | DONE | 5 S1 (charge had no idempotency key -> double charge; release sent EXPIRED for CONFIRMED; empty hold/0 seats/over-100% coupon; SeatCap quota leak; CAS group holds opposite order) | +tables/locking/ACID FU, idempotent checkout, cinemas-for-movie |
| atm | DONE | 7 S1 (reconciler re-debited; PIN count per visit; throwing bank leaked notes; jam+failed credit-back never reversed; deposit(-500); DailyCap UTC; state sketch stuck) | +LC2241 greedy, Uber driver-only, RBI reversal rule |
| rate-limiter | DONE | 3 S1 (oversize call's Retry-After never succeeds; CasBucket clock moved back minting permits; GCRA burst rounding) + S2s | +Atlassian credits, LC362 hit counter, composed rules/byte budgets |
| inmem-db | DONE | 4 S1 (multi-row UPDATE refused mid-way kept partial change; WAL logged commits out of order after unlock; between(35,30) threw; AuditTrigger lost lines) | +ORDER BY card (OpenAI, Glean); CodeSignal L2/L4 not covered -> cs-record-db page |

## PAUSED by him 2026-09-26 ("stop this for some time we will do it") — status at pause
- DONE (8, safe to study): vending, tic-tac-toe, banking, splitwise, bookmyshow, atm, rate-limiter, inmem-db (+ parking-lot, approved earlier)
- STOPPED NEAR THE END (edits in place, guard passes, final check + report not done): elevator, lru, snake-ladder, food-delivery, file-system.
  Resume: a reviewer diffs each file against its .pre-review backup, re-checks the changes against REVIEW-RUBRIC.md, runs _verify.py shots, writes research/<slug>-review.md.
- STOPPED BEFORE ANY EDIT (files identical to .pre-review): chess, logger, pubsub, notification-lld, ride-sharing -> run the full review again.
- NOT STARTED: stackoverflow, order-book, text-editor, spreadsheet, digital-wallet, payment-gateway, cache-eviction, mt-blocking-queue, mt-producer-consumer, mt-rwlock, mt-ttl-cache, mt-striped-map, mt-dining, mt-h2o, mt-print-series, parking-lot (tech + coverage only).
- Web-search budget per session is ~200 calls and was spent by the 3 research agents: reviewers now use research/landscape-*.md (+ LeetCode GraphQL via curl).
- Usage: 16 parallel Opus agents used his whole 5-hour claude.ai window in ~35 min; run fewer at once.
| food-delivery | DONE 2026-09-27 | 4 S1 (cancel mid-dispatch stranded rider; waiting order beside idle rider; throwing refund lost money; accepted offer never attached rider) + S2s | +Flipkart FoodKart card, Flipkart 2025 kitchen capacity + timestamp order |
| snake-ladder | DONE 2026-09-27 | 6 S1 (clock read after first write; leave() reset roller streak; TurnTimer forfeit race; roll inside computeIfAbsent; host() replaced game; TurnToken ref compare) + S2 (jumps did not chain) | +chained jumps, play to the last, PhonePe config + random winnable board, crocodile/mine/capture |
| file-system | DONE 2026-09-27 | 3 S1 (journal before apply; failed restore lost trash record; per-dir lock locked root) + 5 S2 | +LC588 create-or-append, cd/pwd/~/Uber *, du O(1) |
| elevator | DONE 2026-09-27 | 3 S1 (cost() overcharged -> slower car sent; snapshots out of order after unlock; destination dispatch pressed floor before boarding) + S2s | +five-stop feasibility (Microsoft), fire recall card, maintenance/power-cut, energy rule |
| lru | DONE 2026-09-27 | 4 S1 (slow load overwrote newer put -> lease tickets; TTL sweeper deleted rewritten values; write-back stored old value; per-server versions) + LFU hidden scan now O(1) | +pluggable eviction (Flipkart, Bloomberg, Microsoft), fixed lifetime O(1) (Confluent), multi-level cache (PhonePe, Flipkart, Cleartrip) |

## 2026-09-27 HIS DECISION: finish only what is running (reviews: pubsub, ride-sharing, notification-lld), then STOP. "We will review other things later."
LATER (17 reviews, not started): chess, logger, stackoverflow, order-book, text-editor, spreadsheet, digital-wallet, payment-gateway, cache-eviction, mt-blocking-queue, mt-producer-consumer, mt-rwlock, mt-ttl-cache, mt-striped-map, mt-dining, mt-h2o, mt-print-series (+ optional parking-lot tech check).
| pubsub | DONE 2026-09-27 | 6 S1 (seek(0) skipped a message; throwing filter killed subscription; interrupt spun CPU / stop hit wrong thread; back-pressure check-then-act overwrote 26 unread; persistence dropped payloads; IdempotentHandler map corrupted) + O(retention) publish -> ring | +pull consume/ack/filter (Razorpay, Uber), guaranteed delivery for a down consumer |
| notification-lld | DONE 2026-09-27 | 3 S1 (quiet-hours parked message skipped later guards -> duplicate at 8am, mute ignored; cancelled push became EXPIRED and SMS sent; two digests same ms lost one) + S2 (UTC+5 int offset -> 08:40 send) | +Cleartrip order events, Microsoft two-a-day, Ajio in-order; Amazon 5,000/min |
| ride-sharing | DONE 2026-09-27 | 5 S1 (throwing rule/clock locked rider out + car stuck RESERVED; retryPayment on running trip billed 0; endTrip took -10 km/NaN; duplicate Driver matchable offline; racing pings left driver in 1,595 cells) + S2 extensions | +car-pool (Swiggy/MakeMyTrip), Nykaa five nearest + route history, offers accept/decline (Zepto, Salesforce, Uber) |
| parking-lot | FIXED 2026-09-28 (his ask, interview-scoped) | money in paise; pay outside the lock (PAYING/PENDING/settle); idempotency key = ticket id + attempt; PENDING retries on the same gateway; 50-thread race | +Gojek command-line card (13); 84 checks |
