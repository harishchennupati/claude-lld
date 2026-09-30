# ATM: what interviewers ask (review pass 2026-09-26)

## How this was gathered

The session's WebSearch budget (200 of 200 calls) was used up by the parallel reviews before this slug's part B
began. I did not route searches through other tools (a search engine or a site search fetched directly), because
that would get around the limit. Evidence comes from:
- the coordinator's landscape research (`research/landscape-bigtech.json`, `landscape-india-sea.md`,
  `landscape-ailabs.md`, grepped for ATM);
- direct fetches of pages I already knew. The LeetCode 2241 statement (via the doocs mirror), the
  awesome-low-level-design ATM page, the Grokking chapter index and the RBI circular all loaded. The Uber post
  (403), GFG (404), DigitalOcean (shell only) and codezym (shell only) did not.

**What the landscape files say:** there is one first-hand ATM report in the window (Uber, 2025). India/SEA has none:
"No in-window first-hand report found for: chess, ATM (codezym tags only)" (`landscape-india-sea.md`). The AI-lab
file has none.

## Evidence, mapped to the page

| question | company | year | URL | where the page answers it |
|---|---|---|---|---|
| ATM: card, PIN, balance, withdraw with denominations, states. The interfaces and classes were GIVEN; the candidate implements the driver (L5A) | Uber | 2025 | https://leetcode.com/discuss/post/6840488/ (via landscape-bigtech.json; direct fetch 403) | Implement card: new sentence saying the driver is the ATM class plus its main, and the order inside `doWithdraw` is what gets graded. The rest of the page is the full answer. |
| "Design an ATM Machine": notes of 20/50/100/200/500. Withdraw prefers larger notes and must REFUSE when greed fails (600 from 500x1 + 200x3 is rejected). `deposit(int[] banknotesCount)` counts per note | LeetCode 2241 (Biweekly Contest 76) | 2022 | https://leetcode.com/problems/design-an-atm-machine/ (statement read at https://github.com/doocs/leetcode/blob/main/solution/2200-2299/2241.Design%20an%20ATM%20Machine/README_EN.md) | FU 7 now names this variant. `GreedyOnly` (Extensions.java) implements it, with a check in test 6. `ATM.deposit` now takes counted notes, the same shape as 2241's deposit. |
| Balance inquiry, cash withdrawal, cash deposit; card + PIN; the bank's backend validates and moves money; a cash dispenser; concurrent access with consistent data | none named (second-hand problem list) | n/a | https://github.com/ashishps1/awesome-low-level-design/blob/main/problems/atm.md | Functional requirements; FU 2 (the 40-machine race); deposit |
| "Designing ATM" as a standard OOD interview chapter (requirements, use cases, class, sequence and activity diagrams, code) | Educative, Grokking the OOD Interview | n/a | https://www.educative.io/courses/grokking-the-object-oriented-design-interview/design-an-atm (lesson content paywalled) | The whole page |
| "Is the wrong-PIN lockout per session or on the account?" plus the extension "card lockout that persists across sessions" | his own source material, built from Grokking and Alex Xu (second-hand) | n/a | ~/answers/system-design/_pipeline/sd_src/lld-atm.json | Bug fix: the bank now counts per card. FU 6 is rewritten (and retitled with the take-it-out-and-put-it-back twist); test 13 |
| Domain rule, not a question: "account debited but cash not dispensed" must be auto-reversed within T+5 days, then Rs 100 per day of delay to the customer | RBI circular RBI/2019-20/67 (DPSS.CO.PD No.629/02.01.014/2019-20) | 2019 | https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=11693&Mode=0 | FU 5: one sentence |

## Candidates with no evidence yet (NOT added)

1. Partial dispense: some notes came out, the rest jammed. The page treats a jam as nothing handed over.
2. Cash retraction when the customer does not take the notes (RBI's stance on retraction was not verified this session).
3. "Card before cash" ordering (eject the card first, then present the notes).
4. Transfers, PIN change and multi-currency are named out of scope on page 01; there is no report asking for them.
5. Offline or stand-in limits when the switch is down (listed as a twist in LLD-SYSTEMS.md, but not found in any report).

Re-run part B with a search budget to confirm or kill these, and to find more first-hand reports (GFG, Glassdoor,
Blind, Medium, codezym, YouTube).
