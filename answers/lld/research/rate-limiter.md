# Rate limiter: what interviewers actually ask (2023-2026)

Sources: my web searches and fetches (2026-09-26), plus the shared landscape files in this folder
(landscape-bigtech.json `x-rate-limiter` and `hit-counter`, landscape-ailabs.json `rate-limiter-lab-variants` and
`kv-load-metrics`, landscape-india-sea.json `x-rate-limiter`). Card numbers are page 05 after this review.
LeetCode and Glassdoor block fetching, so for those URLs the detail comes from search snippets or the landscape files.

| question | company | year | URL | where the page answers it |
|---|---|---|---|---|
| Per-customer "X requests per Y seconds": implement `boolean rateLimit(int customerId)`; "simple but extensible code" | Atlassian | 2024 | https://www.teamblind.com/post/atlassian-coding-design-and-system-design-bank-gvuoncyd | Core: page 01 prompt, Main.java |
| Standard rate-limiter LLD in round 1: token bucket, code plus tests, run in an IDE | Atlassian | 2023, 2024 | https://leetcode.com/discuss/post/4377722/ , https://leetcode.com/discuss/post/6587244/ | Core; moves 1-9; FailureTests |
| "Implement token bucket or sliding window", working code, not diagrams | Atlassian (Blind) | 2023 | https://www.teamblind.com/post/atlassian-lld-round-ruqatzsf | Core; card 7 |
| Leaking bucket, then per user with a ConcurrentHashMap, then a credit system for unused rate | Atlassian (P6 Sydney) | 2023 | https://leetcode.com/discuss/interview-experience/4133665/ | Card 6 (leaky bucket = Gcra); card 8 (credits, NEW) |
| Credits: unused requests carry over, up to a max; handle it with many threads | Atlassian | 2025 | https://leetcode.com/discuss/post/6344788/ | Card 8 (NEW, CreditWindow) + FailureTests block 16 |
| Code both a sliding window and a leaky bucket (bar raiser) | Swiggy | 2025 | https://leetcode.com/discuss/post/7069404/ | Main.java SlidingWindowCounter / SlidingWindowLog; card 6 (Gcra) |
| Rate limiter in the LLD / machine-coding round | Freshworks; Postman | 2024 | https://leetcode.com/discuss/post/4832058/ , https://leetcode.com/discuss/post/5170690/ | Core |
| Combined limits across several APIs | Microsoft (compiled post) | 2026 | https://leetcode.com/discuss/post/7644877/ | Card 4 (LayeredLimiter); card 11 |
| `isRateLimited` with several rules: global, per path, user+path, user+path+tenant | Cloudflare | 2025 | https://leetcode.com/discuss/post/6396271/ | Card 11 (folded: one layer per rule) |
| Composite rules (req/s on one endpoint, req/min on another, bytes/min budget, req/hour across all); a denied request is counted by no rule | Cursor (Anysphere) | 2026 | https://leetcode.com/discuss/post/7511117/ | Card 11 (folded: byte budget = cost), card 4 (refund makes it all-or-nothing); ask-table row "does a refused call count?" |
| Per-key fixed-window COST limiter with ALLOW and RESET | xAI | 2026 | https://prachub.com/interview-questions/per-key-fixed-window-cost-limiter-with-allow-and-reset-commands | Main.java FixedWindow with cost; card 11 |
| "Rate Limiter Debug and Optimize" (fix and speed up given code); "Implement a Distributed Rate Limiter" | OpenAI | 2026 | https://darkinterview.com/collections/openai/questions/a8c0d262-8ca5-4364-a6dd-fbab94010bac | Card 3 (folded: UnsafeLimiter bug, lock fix, CAS speed-up); card 10 |
| Design a distributed rate limiter (onsite) | Anthropic | 2026 | https://prachub.com/companies/anthropic | Card 10 (Redis script, Redis's clock, TTL, fail open / closed) |
| Rate limiter that handles concurrent requests correctly (concurrency round) | Databricks | 2026 (prep article) | https://spacecomplexity.ai/blog/databricks-onsite-interview | Card 2 (race), move 4, FailureTests block 3 |
| KV store with put/get load over the last 5 minutes; then many calls within one second (interviewer wanted a circular array) | Databricks | 2023, 2025 | https://leetcode.com/discuss/post/4285067/ , https://leetcode.com/discuss/post/6525129/ | Card 9 (NEW, folded) |
| Hit counter: hits in the last N seconds, millions of hits a second, many threads calling hit() | Intuit; Cloudflare; Uber; Apple | 2024; 2025; 2026; 2026 | https://leetcode.com/discuss/post/5250764/ , https://leetcode.com/discuss/post/6796944/ , https://leetcode.com/discuss/post/8509983/ , https://www.fastprep.io/apple-interview | Card 9 (NEW, HitCounter) + FailureTests block 17 |
| Design a Hit Counter (LeetCode 362) with a concurrency section | Microsoft, Amazon, Dropbox (GfG "asked in") | page updated 2026 | https://www.geeksforgeeks.org/system-design/design-a-hit-counter/ | Card 9 |
| Logger rate limiter: drop duplicates within 10 s (LeetCode 359) | Google | 2025 | https://leetcode.com/discuss/post/6476739/ | Card 9 (one line); the logger page |
| Queue requests instead of rejecting: a bounded token-bucket request queue | Plaid | 2026 | https://www.fastprep.io/plaid-interview | Card 13 (WaitingLimiter; folded: a Semaphore of N bounds the waiters) |
| VIP-priority fixed-window limiter | Intuit | 2026 | https://www.fastprep.io/intuit-interview | Partly: card 1 (a rule per tier). Priority ordering of waiting callers is not covered |
| Count dropped requests from a request log | Oracle | 2026 | https://www.fastprep.io/oracle-interview | Partly: MetricsCounter counts refusals |
| Rate limiter coding round (general) | Uber; Walmart; Amazon; Google; Adobe; Apple | 2024; 2025; 2026; 2026; 2026; 2024 | https://leetcode.com/discuss/post/4861889/ , https://leetcode.com/discuss/post/7261128/ , https://leetcode.com/discuss/post/7728145/ , https://leetcode.com/discuss/post/7858030/ , https://leetcode.com/discuss/post/8317368/ , https://leetcode.com/discuss/post/4669922/ | Core (several of the Amazon/Microsoft/Walmart ones are HLD rounds) |
| "Implement a rate limiter" | Stripe | 2023 (weak: 2 reports) | https://www.fastprep.io/stripe-interview , https://www.glassdoor.com/Interview/Implement-a-rate-limiter-QTN_2490237.htm | Core |
| Token bucket in Redis, Lua for atomicity, fail open vs closed, 429 with Retry-After and X-RateLimit headers | Hello Interview breakdown; Stripe engineering blog | n.d.; 2017 | https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter , https://stripe.com/blog/rate-limiters | Card 10; Decision + ApiFilter |
| Dark launch a limiter before it blocks anyone | Stripe engineering blog | 2017 | https://stripe.com/blog/rate-limiters | Card 12 (shadow mode) |

Not added, and why:
- Rubrik's bad-password lockout limiter (LeetCode 1672751): one report, 2022, outside the 2023-2026 window.
- Stripe's concurrent-requests limiter (cap on in-flight calls): only in Stripe's 2017 blog; no interview report found.
- Multi-threaded blocking `get(amount)` token bucket (Dropbox): 2021 evidence only; WaitingLimiter covers the idea.
