# Snake and Ladder: what interviewers actually ask (research for snake-ladder-workbench.html, 2026-09-26)

Sources: LeetCode Discuss posts read in full through the public GraphQL endpoint (first-hand), the workat.tech
problem page and editorial (the statement Flipkart-style machine-coding candidates practise on), GitHub copies of
candidates' prompts, and `research/landscape-india-sea.md`. Web search ran out before a first-hand source for
"several dice combined by max/min" was found; that variant is folded into one card and marked below.
FU = follow-up card number on page 05.

## Target companies first (PhonePe, Swiggy, Flipkart, Tekion)

| question / variant | company | year | URL | where the page answers it |
|---|---|---|---|---|
| Machine coding: Snake and Ladder with full working code, modular, "add further rules without much change" | PhonePe SDE2 (first-hand, verbatim prompt) | 2024 | https://leetcode.com/discuss/post/4615686/ | the whole page; implement card |
| Read a config file: N players, a BS x BS board, S snakes, L ladders, D dice | PhonePe | 2024 | https://leetcode.com/discuss/post/4615686/ | FU12 (`GameConfig.from`) |
| A player who lands on an occupied cell sends that player back to start ("start again from 1") | PhonePe (a mandatory rule) | 2024 | https://leetcode.com/discuss/post/4615686/ | FU11, move 12 (`capture()`, `startAt`, `tokenOn`); test block 12 |
| Generate a random VALID board and "devise proper rules for placing objects" | PhonePe | 2024 | https://leetcode.com/discuss/post/4615686/ | FU12 (`RandomBoard.generate` + `winnable`) |
| Special objects: a crocodile (exactly 5 back) and a mine (holds you for 2 turns) | PhonePe (optional) | 2024 | https://leetcode.com/discuss/post/4615686/ | FU11, move 12 (`crocodile`, `mine`, `TurnKind.HELD`); test block 12 |
| A manual override for the interviewer: each player's starting cell and the dice values per turn | PhonePe | 2024 | https://leetcode.com/discuss/post/4615686/ | FU1 (`ScriptedDice`), FU12 (`startAt`) |
| Round-robin driver; log every event (roll, move, snake, ladder); unit tests for edge cases | PhonePe | 2024 | https://leetcode.com/discuss/post/4615686/ | `Turn.describe` + observers (move 4); move 9 and FailureTests |
| "A game like snake and ladder with other features"; extra features implemented live in the evaluation round | PhonePe SDE2 | 2024 | https://leetcode.com/discuss/post/5241117/ | move 12 (every twist is one of five moves); page 05 |
| 90 minutes, demoable; must handle a new obstacle and any number of players | PhonePe (GfG write-up, undated) | n/a | https://www.geeksforgeeks.org/phonepe-interview-experience-1-10-years-experience/ | FU11; move 12 |
| LLD of Snake and Ladder in the interview LLD round | Swiggy Instamart SDE-1 | 2025 | https://leetcode.com/discuss/post/6260445/ | the whole page (no follow-ups reported) |
| Snake Ladder in the LLD round ("interviewer was in a hurry") | Tekion | 2024 | https://leetcode.com/discuss/post/5224482/ | the whole page (no follow-ups reported) |
| Machine coding SDE1: candidate's code follows chained jumps in a loop and keeps a winning order until one player is left | Flipkart | 2022 | https://leetcode.com/discuss/interview-experience/1721362/ | FU6 (chain, loop check), FU7 (`playToLast`, `finishOrder`) |
| Design and code it, then "how would you extend it" | Flipkart SDE-2 (search snippets only, weak) | 2024 | GfG Flipkart SDE-2 experiences (snippet) | move 12; page 05 |
| Given an interface, modify existing snake-ladder code | Meesho (search snippet only, weak) | n/a | research/landscape-india-sea.md | move 12 |

## The statement candidates practise on (workat.tech, used for Flipkart / Swiggy / Uber prep)

| question / variant | source | year | URL | where the page answers it |
|---|---|---|---|---|
| Jumps chain: "another snake/ladder at the tail of the snake or the end of the ladder, and the piece should go up/down accordingly"; assume no infinite loop | workat.tech problem (aggregator) | current | https://workat.tech/machine-coding/practice/snake-and-ladder-problem-zgtac9lxwntg/ | Ask row 2, FU6, `Board.addJump` loop check, test 3 |
| "Snakes and Ladders can form an infinite loop (show validation)" | candidate's copy of a machine-coding prompt | 2024 | https://github.com/pawan-jindal/snake-ladder-machineCoding | FU6 |
| Input: counts, then pairs, then player names; print "X rolled a n and moved from a to b" | workat.tech | current | same as above | FU12 (`BoardInput.read`), `Turn.describe` |
| A roll past 100 does not move; win only by landing exactly | workat.tech | current | same as above | FU5 (`OvershootStays`) |
| Two dice, totals 2 to 12 | workat.tech (optional) | current | same as above | FU1 (`CombinedDice` SUM, or `dice(2, 6)`) |
| Board size as input | workat.tech (optional) | current | same as above | `GameBuilder.boardSize`, `GameConfig` |
| Play on until only one player is left | workat.tech (optional); kshitijmishra23 README | current | same; https://github.com/kshitijmishra23/Snake-and-Ladder | FU7 |
| A six gives another turn; three consecutive sixes cancel all three | workat.tech (optional); algomaster ("returns to the position they started") | current | same; https://algomaster.io/learn/lld/design-snake-and-ladder | FU4 (`Next.CANCEL_STREAK`, `CappedExtraTurn`), test 6 |
| Create snakes and ladders programmatically (random) | workat.tech (optional) | current | same as above | FU12 |
| The editorial's own design follows chains with a do-while loop | workat.tech editorial | current | https://workat.tech/machine-coding/editorial/how-to-design-snake-and-ladder-machine-coding-ehskk9c40x2w/ | FU6 |

## Other evidence and what was not added

| question / variant | source | year | URL | where the page answers it |
|---|---|---|---|---|
| Extensible to any kind of mover (a jetpack); a player plays several games at once | LeetCode LLD post | 2022 | https://leetcode.com/discuss/interview-question/object-oriented-design/1779179/ | move 1 (a crocodile is a Jump), move 2 (position lives on the game, so one player can sit at two tables) |
| One jump per move, never chained | LeetCode 909 (the DSA version) | n/a | https://leetcode.com/problems/snakes-and-ladders/ | FU6, last sentence (the `for` becomes an `if`) |
| Asked at Goldman Sachs, Amazon, Microsoft, Flipkart, Tekion, Oracle, Salesforce | codezym tags (aggregator) | 2026 | https://codezym.com/blog/19-top-lld-interview-questions-2026 | the whole page |
| Several dice combined by MAX or MIN | no first-hand report found | n/a | n/a | folded into FU1 (`CombinedDice`) because the brief named it; no card of its own |
| Two dice showing a double earn another turn | algomaster only (prep site, not an interview report) | n/a | https://algomaster.io/learn/lld/design-snake-and-ladder | not added |
| Concurrency (many phones), persistence, turn timers | no snake-ladder report; required by LLD-SPEC's frame | n/a | n/a | FU2, FU3, FU13-FU15 |
