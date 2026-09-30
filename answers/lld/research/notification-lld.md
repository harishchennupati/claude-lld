# Notification Service: what interviewers actually ask (research for notification-lld-workbench.html, 2026-09-27)

Sources: the three landscape files (2026-09-26), then every LeetCode Discuss post they cite for this system, plus a
fresh keyword search, all read in full through LeetCode's public GraphQL endpoint (`ugcArticleDiscussionArticle`).
Marks: **1st** = the candidate wrote about their own round; **agg** = a prep/aggregator write-up; **(v)** = read in
full by the reviewer. Target companies only (India product companies, FAANG/GCCs in India); no AI-lab variants.

## Follow-ups, twists and variants

| question / variant | company | year | URL | where the page answers it |
|---|---|---|---|---|
| Order notification system: PLACED / SHIPPED / DELIVERED; customer hears all, seller only PLACED, logistics only SHIPPED; only people on that order; channels configurable per person; subscribe, unsubscribe, add/remove channels; bonus: replay on today's channels, concurrent subscription edits, non-blocking | Cleartrip (SDE-2 machine coding) | 2025 | https://leetcode.com/discuss/post/7266352/ (1st, v) | FU2, new: `OrderNotifier`, test 15 |
| Same order-notification problem in 1.5 h; a Kafka-style design was rejected: "demoable, not scalable" | Cleartrip | 2026 | https://leetcode.com/discuss/post/7533924/ (1st, v) | FU2 (a table and a loop, no broker) |
| Notification service (SMS + email) for parcel updates; the providers allow 5,000/min; resend if sending failed; log of communications sent to the user | Amazon (SDE-2) | 2026 | https://leetcode.com/discuss/post/7573423/ (1st, v) | FU7 (provider-wide bucket, `r -> "all"`), FU6 (retry), FU8 (`historyOf`, new in Main) |
| N jobs, each tied to a user; notify on completion by email or SMS; at most 2 a day per user (configurable); over the limit, deliver next day | Microsoft (SDE-2, Hyderabad) | 2024 | https://leetcode.com/discuss/post/5299198/ (1st, v) | FU5, new: `HoldForTomorrowGuard` over `DailyCapGuard`, test 14 |
| Email / WhatsApp / SMS; register a template per channel; two APIs: template registration and template invoke | Kotak Mahindra Bank (SDE-1) | 2026 | https://leetcode.com/discuss/post/8312895/ (1st, v) | FU1, implement card ("know which version you were asked") |
| LLD with "focus on building message content for different channels" | Amazon (SDE-2) | 2025 | https://leetcode.com/discuss/post/6408439/ (1st, v) | FU1 (templates keyed by id AND channel) |
| SMS, WhatsApp, push; which design patterns; follow-up: tracking the user's activity on the notification | Adobe (MTS-2) | 2025 | https://leetcode.com/discuss/post/6789642/ (1st, v) | FU1 (WhatsApp), FU4 (patterns), FU9 (opened/clicked kept as events, not states) |
| "You own the notification service (SMS, email, in-app); your customers are Amazon teams"; groom the requirements | Amazon (SDE-2 bar raiser) | 2024 | https://leetcode.com/discuss/post/4999447/ (1st, v) | page 01 prompt and ask table |
| Ola's internal notification system: HLD + LLD components + skeleton code + APIs + DB schemas in 90 min, many scenarios | Ola (SDE-2) | 2024 | https://leetcode.com/discuss/post/5616645/ (1st, v) | FU3 (tables, SQL), implement card |
| Design discussion on draw.io: flow, APIs, DB design, indexing, Kafka vs APIs, scalability, trade-offs | Blinkit (SDE-1) | 2026 | https://leetcode.com/discuss/post/8514070/ (1st, v) | FU3, move 8 ladder |
| After an async queue design: "Order Placed" must go out before "Item Dispatched" | Ajio | 2023 | https://leetcode.com/discuss/post/3264320/ (1st, v) | FU10, new: `InOrderDispatcher`, test 16 |
| "Design a Notification System", asked to write code | Swiggy (SDE-1) | 2025 | https://leetcode.com/discuss/post/7389374/ (1st, v; no detail) | whole page |
| One LLD problem on a notification service (HM round); the MC review asked about patterns and extensibility | PhonePe | 2026 | https://leetcode.com/discuss/post/8382058/ (1st, v; little detail) | whole page, FU4 |
| "Design notification service" in the HM round | Meesho (SDE-1) | 2025 | https://leetcode.com/discuss/post/6834461/ (1st, v; no detail) | whole page |
| Notification system for Windows: many apps raise and show notifications (AI-assisted LLD) | Microsoft (SDE-2) | 2026 | https://leetcode.com/discuss/post/8462091/ (1st, v) | partly: a client-side notification centre is out of scope; priority (core), grouping (FU15), do-not-disturb (FU13) |
| Notification centre: priority, grouping, do-not-disturb | Microsoft | 2026 | https://www.fastprep.io/microsoft-interview (agg, via landscape-bigtech) | core priority heap, FU15, FU13 |
| Subscribe/unsubscribe to notification types; preferences for frequency and channels; personalisation; opt-out | "Microsoft, PayPal, Walmart" | 2025 | https://leetcode.com/discuss/post/7238197/ (agg, v) | `PreferenceGuard` (core), FU2 subscriptions, FU15 |
| Priority classes with delivery deadlines (1 h / 30 min / 30 s); never deliver twice | company not named | 2023 | https://leetcode.com/discuss/post/3948309/ (v) | core priority heap and deadline, FU11 |
| Notify via a mocked email/SMS vendor (bonus inside delivery assignment) | Flipkart | 2025-26 | https://leetcode.com/discuss/post/7588244/ (via landscape-india-sea) | `Sender` interface (core) |

Out of scope, noted: Uber's stock-price alert is asked as HLD, not coded (landscape-bigtech); Meta's mobile
notification SDK (https://leetcode.com/discuss/post/3928998/, 2023) is client-side Android work.

## How page 05 is ranked now
By how many target-company reports ask it: 1 new channel + templates (Kotak, Amazon, Adobe); 2 order events
(Cleartrip x2); 3 persistence (Ola, Blinkit); 4 patterns (Adobe, PhonePe); 5 daily limit held for tomorrow
(Microsoft); 6 timeout / resend (Amazon x2); 7 provider limit, breaker, jitter (Amazon); 8 status and per-user log
(Amazon); 9 receipts and opened/clicked (Adobe); 10 in order per key (Ajio); then the cards with no first-hand
target-company report: 11 the race test and 12 one gate per user (both spec-required), 13 quiet hours and
15 digest (aggregator only), 14 starvation (aggregator only), 16 fallback ladder (none found), 17 time and testing.

## Looked for, not found
No first-hand report from a target company asked for scheduled sends ("send at 10:00"), a channel fallback ladder,
or CodeSignal-style levels for this system. A scheduled send would be the same DEFER that quiet hours uses.
