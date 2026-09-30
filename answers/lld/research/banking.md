# Banking System: what interviewers actually ask (research for banking-workbench.html, 2026-09-26)

Sources: web research by a sub-agent, then spot-checked by the reviewer (curl). Marks: **1st** = the candidate or
interviewer wrote about their own round; **agg** = prep/aggregator site (paraphrase, lower confidence);
**(v)** = fetched and confirmed by the reviewer; **(s)** = search snippet only (site blocked the fetcher).
LeetCode Discuss, Glassdoor, Medium and 1point3acres blocked fetching, so items there rest on titles/snippets.

## Follow-ups, twists and variants

| question / variant | company | year | URL | where the page answers it |
|---|---|---|---|---|
| CodeSignal 4-level "banking app" is one of two known problems (the other: in-memory DB) | Anthropic | Feb 2024 | https://www.teamblind.com/post/anthropic-codesignal-interview-gdclgwkl (1st, v) | Level 1 only (see coverage below); the rest is out of scope by instruction (separate page planned) |
| Banking OA; lost time on "Level 3 on the scheduled payments" | Anthropic | Apr 2024 | https://www.teamblind.com/post/anthropic-oa-retake-1jlayxy5 (1st, v) | Partly: FU10 standing instruction (scheduled transfers, idempotent ids); no one-off delay or cancel |
| "One question is about the banking app" | Anthropic | Jul 2024 | https://www.teamblind.com/post/anthropic-codesignal-problem-p5acxgvk (1st) | as above |
| Banking ending in "interest calculations with time-dependent logic"; "transaction history with filtering" | Anthropic | Apr 2026 | https://www.sundeepteki.org/advice/anthropic-codesignal-assessment-guide (agg) | FU2 (daily-closing-balance interest), FU12 (injected clock); statement window FU7 |
| Full 4 levels: create/deposit/transfer; top spenders; schedule_payment + cancel_payment; merge + get_balance(time_at) | Coinbase | Sep 2025 | https://www.linkjob.ai/interview-questions/coinbase-codesignal-assessment-insider-guide/ (agg) | Level 1 covered; levels 2-4 not added (instruction) |
| "Codesignal Banking System Questions" (phone screen) | Coinbase | ? | https://www.1point3acres.com/interview/thread/1121233 (s) | as above |
| Counter-evidence: got a TTL key-value store instead | Coinbase | Jul 2024 | https://www.teamblind.com/post/whats-a-passing-score-for-coinbase-oa-on-codesignal-syluyder (1st) | n/a (problems rotate) |
| "Simulate a bank with deposits, withdrawals, fees, and queries" | Coinbase | 2026 | https://www.lodely.com/blog/coinbase-online-assessment-2025 (agg) | FeePolicy in the transfer (move 6, FU3), month-end charges (FU3) |
| Java signatures: createAccount, deposit/transfer -> Optional, topSpenders, schedulePayment with cashback %, mergeAccounts | eBay | Oct 2025 | https://leetcode.com/discuss/post/7302772/ ; mirror https://interviewexperiences.in/experience/ebay/ebay-codesignal-oa-industry-coding-assessment (1st, v) | Level 1 covered |
| 4 levels; due payments processed before later API calls (min-heap of execute time) | Airbnb | Aug 2026 | https://prachub.com/interview-experiences/airbnb-software-engineer-interview-experience-a-four-level-banking-system-online-assessment (agg) | Level 1 covered |
| 4 levels; withdraw counts toward spend; cancel only before execution; merged source can no longer be operated | The Trade Desk | Nov 2025 | https://www.linkjob.ai/interview-questions/the-trade-desk-codesignal-questions/ (agg) | Level 1 covered |
| Transfer "atomic: if either side fails, the entire operation fails" | Ramp | May 2026 | https://oavoservice.com/en/articles/ramp-oa-2026-codesignal-bank-system-guide (agg, low confidence, v) | Move 6 order, FU6 |
| SET_PAYMENT_LIMIT: spend over a trailing window_ms may not exceed a limit | Ramp | May 2026 | same URL (agg, low confidence, v) | FU8: one sentence added (queue of (time, amount), drop old entries before each check) |
| "Codesignal Banking System" | Circle | ? | https://www.1point3acres.com/bbs/thread-1143606-1-1.html (s) | Level 1 covered |
| Interviewer's post: "design banking application ... deposit, transfer, accounts with top activity" | Capital One | Sep 2023 | https://www.teamblind.com/post/What-does-Capital-One-ask-on-OA-UaxsP1K3 (1st, v) | deposit/transfer covered; top activity not added (CodeSignal-style ranking, separate page) |
| Top activity = sum of deposits and both sides of each transfer | Capital One | ? | https://www.fastprep.io/problems/capital-one-banking-top-activity (agg) | not covered (as above) |
| LeetCode 2043 Simple Bank System (1-indexed balances; transfer/deposit/withdraw return bool) | Capital One, PayPal, Okta, OpenAI | 2025-2026 | https://www.hellointerview.com/community/questions/bank-system/cm5eguhag03l5838orse1253f (agg, v) | Implement card: one sentence added (the smallest version: long[] by account number, return false instead of throwing) |
| Bank ledger: lock ordering / deadlocks / write skew; idempotent writes; as-of balances; statements; immutable double-entry ledger; velocity checks | Coinbase | 2025-2026 | https://prachub.com/interview-questions/design-a-bank-account-ledger (agg, system-design flavour, v) | Lock order: move 6, FU4. Idempotency: move 5-6, test 10, FU10-11. Statements: FU7. Velocity: FU8. Double entry: FU11 (sentence added). As-of balance: partly (see coverage) |
| "Building a Bank Ledger: Concurrency, Locks, and Race Conditions" | Coinbase | Aug 2026 | https://medium.com/@emilyhustlenyc/coinbase-interview-question-building-a-bank-ledger-concurrency-locks-and-race-conditions-75eeb1a80e45 (s, title only) | Moves 4, 6, 7; FU4 |
| Transfer that deadlocks with naive locking; fix by ascending account id; tryLock with a timeout as the alternative | Revolut | 2026 | https://prachub.com/interview-guide/revolut-software-engineer-interview-questions-guide-2026 (agg, v) | Move 6, FU4 (tryLock sentence added) |
| SELECT ... FOR UPDATE and a version column; idempotent charge under duplicate retries | Revolut | 2026 | same URL (agg, v) | FU11 (sentence added: the three database answers), test 10 |
| "Ledger company" (loan EMIs) listed as a machine-coding problem | Navi | ? | https://github.com/hardihood/LLD (listing only) | FU10 loan (equal-principal EMIs, idempotent instalments) |
| Machine coding: design a wallet | Flipkart | ? | https://www.glassdoor.co.in/Interview/Machine-coding-design-round-design-a-wallet-QTN_4415509.htm (s) | the digital wallet page, not this one |
| Machine coding: payment gateway | PhonePe | 2022 | https://leetcode.com/discuss/interview-question/object-oriented-design/2771368/PhonePe-or-Machine-Coding-Round-or-Design-Payment-Gateway-or-5-years-exp (s) | the payment gateway page, not this one |

The 4-level task's exact spec (practice copy, not tied to a company): https://github.com/EricZheng0404/LibreSignal
(Questions/bank_system/level1-4.md): L1 create_account / deposit / transfer (None on missing account, same account,
short funds); L2 top_spenders(timestamp, n) as "id(total_outgoing)", ties by id; L3 pay() with 2% cashback after
24 h + get_payment_status (other versions: schedule_payment(delay) + cancel_payment); L4 merge_accounts +
get_balance(timestamp, account_id, time_at).

## Which CodeSignal levels this page's code already covers (not added here, by instruction)
- **Level 1 (create account, deposit, transfer): covered.** openSavings/openCurrent (duplicate id refused), deposit,
  Bank.transfer (same account, missing account and short funds refused). It throws where CodeSignal returns None.
- **Level 2 (top spenders / Capital One top activity): not covered.** No per-account outgoing total or ranking.
- **Level 3 (scheduled payment with delay + cancel, or cashback after 24 h): partly.** StandingInstruction runs
  due periods as idempotent transfers; there is no one-off delayed payment, payment id, cancel or status.
- **Level 4 (merge accounts; balance at a past time): balance-at-time partly, merge not covered.** Every ledger row
  carries balanceAfter, and statement(0, t).closing() is the balance at t by binary search (DailyBalances does the
  same for interest). There is no get_balance(time_at) method and no "did not exist yet -> None" case.

## Domain facts used on the page (official RBI pages, fetched and confirmed)
- Savings interest on a **daily product basis from 1 April 2010**: RBI/2009-10/322, 19 Feb 2010,
  https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=5508&Mode=0 -> FU2 (code: DailyBalanceInterest).
- Minimum-balance penalty **"directly proportionate to the extent of shortfall"** and the balance must **not "turn into
  negative balance solely on account of levy of charges"**: Master Circular on Customer Service, para 5.4.1 (iv), (vi),
  https://www.rbi.org.in/Scripts/BS_ViewMasCirculardetails.aspx?id=9862 -> FU3 (code: MinBalancePenalty).
- **Inoperative = no customer-induced transaction for over two years**; bank charges and savings interest are
  "bank induced" (they do not count as activity): RBI/2023-24/105, 1 Jan 2024,
  https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12589&Mode=0 -> move 6 (code: post() does not let
  INTEREST or FEE rows wake a DORMANT account; the code's 180 days is its own configurable number).

## No evidence found (kept on the page, but not claimed as commonly asked)
Minimum balance / penalty, joint accounts, KYC, multi-currency, freeze/close, daily ATM cap (only Ramp's trailing
window, low confidence), loans (only the Navi listing), fees (one aggregator). No first-hand 2023-26 report of an
interviewer asking lock ordering or idempotent retries in a "design a bank" LLD round was reachable (aggregators
only; the blocked sites may hold some). No first-hand banking-LLD report found for Razorpay, Paytm, Amazon, Uber,
Goldman Sachs, JPMorgan or Stripe.
