# Elevator: what interviewers actually ask (research for the 2026-09-26 review)

Scope: Indian product companies, FAANG / US companies hiring in India (GCCs), UK / Singapore teams hiring from India.
Sources: web search (LeetCode Discuss pages block direct fetches, so some rows rely on search-result snippets; marked),
plus `research/landscape-bigtech.md` and `research/landscape-india-sea.md`. No AI-lab-only evidence was used.

| question | company | year | URL | where the page answers it |
|---|---|---|---|---|
| 50 floors, a lift of 20 people; every rider must reach their floor within 5 stops; take a new request only if the rule still holds for everyone on board and the newcomer | Microsoft (SWE, LLD round 2) | 2024 | https://leetcode.com/discuss/post/6154075/ | Follow-up 13 (StopBudget, new) + FailureTests 13 |
| "Request feasibility (single lift)": can the lift accept this request | Microsoft (codezym tag) | 2026 list | https://codezym.com/blog/19-top-lld-interview-questions-2026 | Follow-up 13 |
| Single-shaft lift 0-10; display floor and UP / DOWN / STOPPED; no DOWN on the ground floor, no UP on the top floor; never move past 0 or 10 | Microsoft (SDE2) | 2025 | https://leetcode.com/discuss/post/7357425/ (search snippet) | DisplayPanel (move 3); requirements + FailureTests 3; floor-range checks |
| Emergency stop at any point; a sensor fault goes to a safe halted state | Microsoft (SDE2) | 2025 | same | Follow-up 6 (goOutOfService / takeOutOfService) |
| Maintenance mode: reject new requests, finish the current trip | Microsoft (SDE2) | 2025 | same | Follow-up 6 fold (DrainForService, new) + FailureTests 12 |
| Resume a consistent, safe state after a restart (power failure) | Microsoft (SDE2) | 2025 | same | Follow-up 14 fold (new sentence) |
| Diagnostics: report faults, emergency stops, overloads, delays | Microsoft (SDE2) | 2025 | same | Move 12 "someone new wants to know" = one more observer (MaintenanceMonitor) |
| Strategy for movement, Command for requests | Microsoft | 2024-25 | https://leetcode.com/discuss/post/6350503/ (via landscape-bigtech) | Move 10 + follow-up 16 (Command earned on rung 3 only) |
| Lift called from outside by choosing the destination floor (destination dispatch) | Adobe | 2025 | https://leetcode.com/discuss/post/6474852/ , https://leetcode.com/discuss/post/6819770/ (via landscape-bigtech) | Follow-up 12 (fixed: destination pressed at boarding) + FailureTests 13 |
| Time- AND energy-efficient scheduling | Adobe | 2025 | same | Nearest-car cost (move 3) + follow-up 1 fold (EnergySavingDispatch, new) + FailureTests 11 |
| Draw the state diagram | Tekion | 2025 | https://leetcode.com/discuss/post/6583509/ (via landscape-india-sea) | Move 6 (state machine, redrawn to match the code) |
| Order of presses from many floors; a press on an intermediate floor; which of several lifts moves | Tekion (GfG, undated) | older | https://www.geeksforgeeks.org/tekion-interview-experience-for-associate-software-engineer-intern-fte/ | Follow-up 3 (LOOK), follow-up 4, moves 3 and 5 |
| Elevator LLD in the hiring-manager round | Agoda | 2024 | https://leetcode.com/discuss/post/5978891/ (via landscape-india-sea) | Whole page |
| Elevator LLD round (feedback: LLD not positive) | Amazon (SDE-2, India) | 2025 | https://leetcode.com/discuss/post/7202678/ (search snippet; landscape rates Amazon evidence weak) | Whole page |
| Elevator LLD | Oracle | 2023 | https://leetcode.com/discuss/post/4439820/ (via landscape-bigtech) | Whole page |
| Time-ordered dispatch / nearest eligible car as a simulation | Pinterest, Salesforce | 2026 | https://www.fastprep.io/pinterest-interview , https://www.fastprep.io/salesforce-interview (weak, aggregator) | Tick simulation + NearestCarStrategy; FailureTests 11 |
| Express lift / priority floors | Hello Interview (prep site, ex-FAANG interviewers) | 2025-26 | https://www.hellointerview.com/learn/low-level-design/problem-breakdowns/elevator | Follow-up 11 (zones) + ElevatorCar floor range |
| Undo / cancel a floor request | Hello Interview | 2025-26 | same | Follow-up 9 fold (count per floor, new sentence) |
| Many hall calls at the same instant | Hello Interview | 2025-26 | same | Follow-up 2 + FailureTests 1 |
| Car calls, capacity / weight, express, swappable dispatch, same-instant requests, no request waits forever | vinitshahdeo (prep write-up) | 2026 | https://vinitshahdeo.substack.com/p/elevator-system-design-lld-interview | Follow-ups 2, 9, 11; move 3 |

Company list with elevator tagged (codezym 2026): Microsoft, Adobe, Oracle, Amazon, Salesforce, MakeMyTrip, Alteryx,
Tekion, PayPal, Remitly, Quince, Indihood, Coupa.

Not added: LeetCode "Elevator Requests I-IV" (algorithm puzzles, not LLD); lobby first-come boarding fairness
(Microsoft, Glassdoor, about 2012, out of window); 40-floor capacity planning (Google, Glassdoor, old, an estimation
question); VIP / priority requests and odd/even zoning (prep sites only, no first-hand report; zoning already covers odd/even).
