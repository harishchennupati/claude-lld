# Vending Machine: what interviewers ask (review pass 2026-09-26)

## Status: part B could not be done properly

The session's WebSearch budget (200 of 200 calls) was used up by the parallel reviews before this slug's
part B began. I did not send searches through other tools (a search engine or a site's own search fetched
directly), because that would get around the limit. Instead I fetched the specific pages I knew of:

| page | result |
|---|---|
| https://github.com/ashishps1/awesome-low-level-design/blob/main/problems/vending-machine.md | fetched: a problem statement, second-hand, no company or year |
| https://github.com/ashishps1/awesome-low-level-design (README) | fetched: lists the problem under "Easy Problems"; no company tags |
| https://algomaster.io/learn/lld/design-vending-machine | paywalled |
| https://www.hellointerview.com/learn/low-level-design/problem-breakdowns/vending-machine | 404 |
| https://www.geeksforgeeks.org/design-vending-machine/ and /system-design/design-vending-machine/ | 404 |
| https://igotanoffer.com/blogs/tech/object-oriented-design-interview | 403 |
| https://leetcode.com/discuss/interview-question/object-oriented-design/ | 403 |

So there is **no first-hand evidence (company, year, report) in this file**. Following the rubric ("do not add a
question with no evidence that anyone asks it"), **no follow-up was added and none was cut**. Re-run part B
when a search budget is available.

## What the one source I could read lists, mapped to the page

| question | company | year | URL | where the page answers it |
|---|---|---|---|---|
| Many products, each with its own price and quantity | none named (second-hand problem list) | n/a | awesome-low-level-design, vending-machine.md | moves 1 and 5: Slot, Inventory as Map<code, Slot> |
| Accept coins AND notes of different denominations | none named | n/a | same | partly: the Coin enum holds coins up to Rs 20; a note would be one more constant. Not said on the page |
| Dispense the item and return change | none named | n/a | same | move 6 and FU 5: `sell()`, and change is proven before the motor turns |
| Track what is left | none named | n/a | same | `qty(code)`, `stockCounts()`, FU 11 |
| Several transactions at once, data stays consistent | none named | n/a | same | move 4, FU 2 (the 40-thread race), test 11 (a phone never spends a walk-up customer's coins) |
| An operator interface to restock and to COLLECT the money | none named | n/a | same | restock: yes (`restock`, FU 11). Collecting the takings: **not answered** (only `loadFloat` adds coins) |
| Insufficient funds, sold out | none named | n/a | same | NEED_MORE and SOLD_OUT outcomes; move 6 |

## To check first when part B is re-run (candidates, no evidence yet, NOT added)

1. The operator empties the takings but keeps a float for change (the one gap in the list above).
2. Notes as well as coins, and refusing a note that the float cannot change.
3. "Return the fewest coins" as an explicit requirement (neither change rule here minimises the coin count).
4. Select first, then pay (the page assumes money first; the Ask table names it as a question).
5. A class per state (the State pattern with classes) as a hard requirement at Amazon-style rounds (FU 15 covers the trade-off).
