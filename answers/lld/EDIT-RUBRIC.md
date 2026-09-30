# Editorial pass on one LLD workbench (his brief, 2026-09-14: "when I read, think a lot: is it enough, do we need more, do we even need this, should we keep it, should we remove it; think holistically")

You are the editor of one page. You may add, cut, split, merge and rewrite. You may not change the frame (five steps; moves in the fixed order, 10-12 of them; 8-18 follow-ups) or lld_engine.py. Work in specs/<slug>.py and <slug>/*.java; rebuild with `python3 specs/<slug>.py` (the guard must print), then `python3 _verify.py <slug> shots` and LOOK at the screenshots.

The reader: an SDE-2/3 backend engineer preparing for LLD rounds at product companies (India and abroad), anxious, diagram-first, plain English, who will read this page in one sitting and then write the system from a blank file. He wants to know everything an interviewer could ask about THIS system, and nothing that is there only because a template asked for it.

## 1. Read the page as he would
Screenshot all five pages (the sed trick in LLD-SPEC.md) and read them top to bottom before touching anything. Note every place you had to read twice, every paragraph that says nothing this system needs, every picture whose labels do not match the code.

## 2. Interviewer coverage (add what is missing)
Write down the 10-12 questions a real interviewer asks on THIS system in a 60-minute LLD round (the follow-ups they actually use, not generic ones): the core design question, the race, the failure at the critical step, the rule that changes, the scale question, and the system's own famous twists (e.g. elevator: SCAN vs nearest, what happens to calls when a car breaks, capacity; BookMyShow: seat locking and expiry, payment failure, many screens; Splitwise: rounding, simplify, multi-currency; order book: price-time priority, partial fills, cancel O(1); rate limiter: window boundary, distributed; MT: lost wakeup, spurious wakeup, fairness, timeouts, interrupts). For each, find where the page answers it (derivation, code, test, follow-up). Anything not answered: ADD it, in the right place, with code in Extensions.java (or Main.java if it is core) and a test if it makes a claim.

## 3. Cut what does not earn its place
- A move that is mechanical for this system (nothing to derive) shrinks to two or three sentences and a small picture, or drops its picture; do not pad it.
- A follow-up card that only restates a move with no new angle: merge it into the move or cut it. Keep only questions an interviewer asks about this system.
- A test that proves nothing interesting: cut it (and its row in move 9).
- Any sentence that exists to sound thorough: cut. Target reading time for the whole page: 60 to 75 minutes. If it is longer, cut, do not compress.

## 4. Plain English on everything that stays
Every term defined where it first appears. One idea per sentence. Numbers concrete. A follow-up answer says what the code does, in 3 to 6 sentences, then shows the exact code (sliced with `sect` so it stays in sync). No phrase he would have to read twice.

## 5. Consistency across the five pages
Class and method names, numbers, and the order at the critical step must agree between the problem page, the moves, the class diagram, the code and the follow-ups. The "what the code must do" picture must match the public methods of the root class. The class diagram must show every class in Main.java, and mark Extensions classes distinctly if any are drawn.

## 6. Depth by kind of system
Money systems: idempotency, ledger/double entry, UNKNOWN outcomes and reconciliation, retries. Games: complete rules, illegal moves, undo, a bot hook. Infra/data structures: O(1) claims proven, lock scope, back-pressure, metrics. Multithreading: the wait protocol (check under the lock, wait in a loop, signal after the change), lost and spurious wakeups, fairness and starvation, timeouts and interrupts, and what java.util.concurrent already gives you.

## 7. Report (under 300 words)
Added (what and why), cut (what and why), rewritten (where), the interviewer questions you listed and where each is answered, the estimated reading time, and anything you were unsure about. The guard line and the _verify.py output must be in the report.
