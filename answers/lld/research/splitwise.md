# Splitwise: what interviewers actually ask (review pass 2026-09-26)

Sources: about 95 LeetCode Discuss posts that mention Splitwise, simplify debts or Optimal Account Balancing (read through
LeetCode's own search), plus `landscape-india-sea.md`. Every LeetCode row is a candidate's own post. Glassdoor, code360
and Medium were bot-walled. Reddit, Blind, 1point3acres and YouTube were not searched because the session's search
budget ran out. "FU n" means follow-up card n on page 05; "move n" means page 02.

## Reports

| question / variant | company | year | URL | where the page answers it |
|---|---|---|---|---|
| Machine coding (MC), workat.tech statement: EQUAL/EXACT/PERCENT, SHOW all / SHOW user; the interviewer runs sample tests | Swiggy SDE2 | 2024 | https://leetcode.com/discuss/post/4540407/ | Main.java core (the three rules + CheckedSplit); moves 3, 5; FU 4, FU 5 |
| MC: balances and the simplify feature | Swiggy SDE2 | 2022 | https://leetcode.com/discuss/post/2269420/ | FU 9 |
| MC, workat.tech reworded, EQUAL/EXACT only, 2.5 h | Swiggy SDE-1 | 2021 | https://leetcode.com/discuss/post/1532880/ | core |
| MC: equal split only but extensible; simplified balance with each user; expenses a user is part of | Razorpay SSE | 2024 | https://leetcode.com/discuss/post/6180241/ | move 3, FU 1; FU 9; FU 7 (passbook) |
| MC: simplified balances for everyone and per user; round to 2 decimals; validate splits | ClearTax SDE-2 | 2026 | https://leetcode.com/discuss/post/7518434/ | FU 5 (rounding), FU 4 (validation), FU 9 |
| MC: percent and exact splits; record a payment settlement | ClearTax SDE-2 | 2023 | https://leetcode.com/discuss/post/3378979/ | FU 8 |
| MC with hidden tests: addUser / splitExpense / showExpenses / showExpensesForUser | Meesho SDE-2, SDE-1 | 2024 | https://leetcode.com/discuss/post/5650118/ , https://leetcode.com/discuss/post/5811189/ | core; FU 7 (passbook) |
| MC: ADD_EXPENSE, SHOW_BALANCE, SHOW_NET_BALANCE, SETTLE_DEBT_OPTIMIZED ("minimum number of transactions"); categories | Locus.sh SDE3 | 2026 | https://leetcode.com/discuss/post/8122004/ | FU 9, **FU 10 (added)**, FU 11; categories not covered |
| LLD with a fixed input line; O(1) "how much does A owe B" | Salesforce MTS | 2026 | https://leetcode.com/discuss/post/8461169/ | move 5, FU 11 |
| MC with groups: add members; owed within one group AND across all groups | Acko SDE-1 | 2026 | https://leetcode.com/discuss/post/7617272/ | **FU 13 (added)** |
| MC: 100-person group, expenses on subsets; settling clears person-to-person and shared groups; no partial settlement | Groww SDE2 | 2024 | https://leetcode.com/discuss/post/5422097/ | FU 13, FU 8 |
| MC: add/remove users, create/remove groups, settle user-to-user and user-to-group | Groww SDE2 | 2022 | https://leetcode.com/discuss/post/2013143/ | FU 12 (leave), FU 13 (join, across groups) |
| MC, 90 min: users in many groups, bill per group, owed per group and overall | Flipkart | unknown | https://www.glassdoor.com/Interview/Machine-coding-90-min-Design-Splitwise-Group-contains-Users-User-can-be-in-multiple-Groups-Bill-is-assigned-to-a-Gr-QTN_2799023.htm | FU 13 |
| Problem-solving round: code the simplify-debt algorithm | Flipkart SDE1 | 2019 | https://www.geeksforgeeks.org/flipkart-interview-experience1-10-years-experience-sde-1/ | FU 9, FU 10 |
| HLD: min-transactions "graph edge optimization", DB schema, concurrent entries, large groups | Uber SDE2 | 2025 | https://leetcode.com/discuss/post/7672800/ | FU 2, FU 3, FU 10, FU 16 |
| DSA round: LeetCode 465 Optimal Account Balancing | Uber SDE2 | 2022 | https://leetcode.com/discuss/post/2463807/ | FU 10 |
| Settlement for a bank clearing house (same netting) | Uber SSE | 2023 | https://leetcode.com/discuss/post/4137694/ | FU 9 (the same netting); not a separate card |
| LLD with a focus on currency conversion ("bar not reached" without it) | Amazon SDE2 | 2025 | https://leetcode.com/discuss/post/6735161/ , https://leetcode.com/discuss/post/6725210/ | FU 14 |
| LLD: schema and APIs, plus spend per day/month/user/group | Amazon India SDE2 | 2025 | https://leetcode.com/discuss/post/6418112/ | FU 16 (tables); the spend report is an observer (move 12), not a card |
| LeetCode 465 in the maintainable-code round; interviewer said the two-heap greedy fails some cases | Amazon AWS SDE2 | 2025 | https://leetcode.com/discuss/post/6891316/ | **FU 10 (added)**; FU 9 now states the caveat with a 4-vs-3 example |
| MC, workat.tech plus createdBy, Show_User_Expense; justify the DB | Slice SDE-2 | 2025 | https://leetcode.com/discuss/post/6827412/ | FU 7 (passbook), FU 16 (tables) |
| "Settle group in minimum transactions (Dynamic programming)" | Winzo SSE | 2025 | https://leetcode.com/discuss/post/6616321/ | FU 10 (bitmask DP) |
| LeetCode 465 in disguise (assets), then DB, API, scaling | Goldman Sachs Associate | 2025 | https://leetcode.com/discuss/post/6649948/ | FU 10, FU 16 |
| Peer-to-peer expenses, no groups | UiPath | 2025 | https://leetcode.com/discuss/post/6737470/ | FU 15 (a pair is a group of two) |
| HLD+LLD: create/read/update/delete expenses, debts view, API and DB, scale | PhonePe SE | 2024 | https://leetcode.com/discuss/post/6145158/ | FU 7, FU 16 |
| Phone screen: settle a list of (from, to, amount); follow-up: the optimal settlement | Rippling SDE2 | 2024 | https://leetcode.com/discuss/post/5590877/ | FU 9, FU 10 |
| Design: groups, edit expense, ratio split, settle by cash or online, per-user history, concurrency and faults | Cars24 SSE | 2024 | https://leetcode.com/discuss/post/4824010/ | FU 1, FU 7, FU 8, FU 2 |
| OA: simplify a group of debt transactions (count) | ShareChat SDE-1 | 2024 | https://leetcode.com/discuss/post/4832436/ | FU 10 |
| CSV ledger: total owed, most in debt, most owed, with and without simplification | Dunzo SDE2 | 2022 | https://leetcode.com/discuss/post/1761319/ , https://leetcode.com/discuss/post/2340278/ | FU 11 ("who owes the most"), FU 9 |
| Phone screen: simplify debts, minimize transactions | Google | 2020 | https://leetcode.com/discuss/post/609750/ | FU 9, FU 10 |
| MC in 2 h / ~40 min in an IDE | Groww, ShareChat (per landscape-india-sea.md) | 2025 | https://leetcode.com/discuss/post/7046387/ , https://leetcode.com/discuss/post/6489146/ | implement card (must-write core named) |
| Classes + DB schema + APIs | Licious (per landscape-india-sea.md) | 2023 | https://leetcode.com/discuss/post/3746403/ | FU 16 |
| Splitwise LLD (details in the landscape file) | Groww 2024, MakeMyTrip 2024, ThoughtSpot 2024 (per landscape-india-sea.md) | 2024 | https://leetcode.com/discuss/post/5032433/ , https://leetcode.com/discuss/post/5777593/ , https://leetcode.com/discuss/post/4700672/ , https://leetcode.com/discuss/post/5510451/ | core |

## Published statements (not reports, but what the reports copy)

| item | source | where the page answers it |
|---|---|---|
| workat.tech: `EXPENSE u1 1000 4 u1 u2 u3 u4 EQUAL`, `SHOW`, `SHOW u1`; "33.34 to first person and 33.33 to others"; percent must total 100, exact must total the bill; optional: SHARE split, passbook, simplify toggle | https://workat.tech/machine-coding/practice/splitwise-problem-0kp2yneec2q2 | core; FU 5 (remainder rule, one line in Remainder); FU 1 (shares); FU 7 (passbook); FU 9 (toggle) |
| workat.tech editorial keeps money in double; its percent check refuses 47.72 + 38.54 + 13.74 (99.99999999999999, verified in Java) | https://workat.tech/machine-coding/editorial/how-to-design-splitwise-machine-coding-ayvnfo1tfst6/ | FU 6 (added the example) |
| codezym SplitBook: several payers per expense, reused id ignored, "round half up" | https://codezym.com/question/12 | not added: no first-hand report asks for several payers |

## Splitwise's own rules (used to decide the leave and simplify behaviour)

| rule | source | where the page answers it |
|---|---|---|
| Simplify debts "never changes anyone's total balance", re-runs after every expense or payment, per currency | https://kb.splitwise.com/balances-and-expenses/what-is-simplify-debts | FU 9 (a view recomputed from the nets), FU 14 (per currency) |
| A member with an outstanding balance cannot be removed until it is cleared | https://kb.splitwise.com/groups/how-do-i-remove-a-person-from-a-group | FU 12: the net must be zero; a zero net with a loop is passed through the leaver |
| 2012 blog rule "no one owes a person they didn't owe before" (applies to the cross-friend feature; the group feature breaks it) | https://blog.splitwise.com/2012/09/14/debts-made-simple/ | not added |

## Ranking across reports (how often each follow-up appears)
1. Simplify / minimum transactions: about 24 reports (10 inside the design, 14 as LeetCode 465). Page: FU 9 + FU 10.
2. DB schema / API design: about 20. Page: FU 16 (now names the tables).
3. EQUAL/EXACT/PERCENT and "extensible": about 21. Page: core, move 3, FU 1.
4. Groups (add/remove members, per-group vs overall): about 10. Page: FU 12, FU 13.
5. Settle up: 8. Page: FU 8.  6. Scale/HLD: 8. Page: FU 3, FU 16.
7. Passbook/history: 4. Page: FU 7.  8. Concurrency: 3. Page: FU 2, move 4.
9. Currency: 1 (Amazon). Page: FU 14.
Not seen in any first-hand report: multiple payers, notifications, recurring expenses (kept, since Splitwise has them).
