# LLD workbench: the format, and how to build one

One page per LLD problem, generated from compiled Java. The rate limiter
(`../rate-limiter-workbench.html`) is the pilot; every other problem follows it.

```
python3 build.py rate-limiter            # writes ../rate-limiter-workbench.html and ../rate-limiter-code/
python3 build.py rate-limiter --fresh    # recompile and rerun everything, ignoring the cache
```

## What the reader gets

The reader is preparing for SDE-2/3 interviews. They read a page once, then close it and must
reproduce the reasoning, the classes, the code, the tests and the follow-ups, and answer the
interviewer's questions. So the page teaches a small design well, with every line compiled.

One step is on screen at a time (the left list and ← → move between steps). **Read** mode shows
everything; **Practise** mode hides the code and the answers until the reader asks.

| group | steps | what each step holds |
|---|---|---|
| Understand | The problem | the interviewer's line (a real reported wording, with company and year); the situation, with realistic names and numbers; one flow picture; "what this really is" in one sentence; the questions to ask, each with what its answer changes in the code; what we build (the product's rules as a table); what SDE-2 and SDE-3 are graded on; the hour (what to type in a 60-minute round, what in a 90-minute machine-coding round); how to use the page |
| | The core idea (e.g. how to count) | the first idea, drawn failing (a ✗ text panel); the options as a table; "X, not Y" lines; the chosen mechanism with its formula and a worked trace whose numbers the code prints later |
| Design | How to get there | the first version everyone writes, compiled and run (the 15-minute version); then one question per move, written as an engineer thinking aloud: what they notice in the problem or the code, the tempting fix and why it fails, the new types (each named as record, interface, class or enum), a short code sketch, a bold "X, not Y" line, and a chip row of the design so far. By the last question every type exists. It comes *before* the finished diagram, so the diagram is the summary |
| | The design | the caller's code first; the class diagram; one sequence diagram of a real request; who does what, and when each class changes |
| Build | one step per group of 1-5 types, in typing order | the where-we-are strip; 2-4 sentences of why; the code, whole files, explained in its comments; the output of a tiny program that uses only what exists so far; a ✗/✓ panel where a race or a wrong first idea is the point; a "Java ·" note where a language or library idea is first used; at most two "If the interviewer asks" answers |
| | Run it | `Main` in parts, its output, and what the output shows |
| | Tests | the test file in parts (the first test open, the rest folded); its output; the break-it table (real broken copies, each with the test that must fail) |
| | Why it holds up | the thread breaks met in the build (each is taught in the step where it happens, never in a separate primer) as one table; what threads share and what guards it; why it cannot deadlock; measured cost |
| | Principles and patterns | SOLID as a table (in one line / here / without it); patterns used, with the problem each solves here; patterns you might reach for and why not; what else they probe (program to an interface, composition, immutability, testability) |
| Follow-ups | one step each, ordered so each builds on the last; optional ones marked *later* | the ask (a reported wording, company, year); "Builds on:" the step before; the strip with only new and changed types; where it lands in *our* design (which interface absorbs it); the diff (new code with changes highlighted; repeated changes folded); the demo's output; the catch (the one hole left); Java notes; interview answers |
| Remember and practise | Recall | the whole design as signatures in typing order; cards (the eight questions, the core mechanism in numbers, threads, where each follow-up lands, the tests); the lines to remember exactly |
| | Practise | drill 0: the 15-minute version; drill 1: the 60-minute round subset with a tick list; drill 2: machine coding, then the page's tests against your code (plus the whole core in one file for an online editor); drill 3: each follow-up with its own time, started from `<slug>-code/steps/<step>/`; drill 4: out loud; when to repeat; a miss log kept in the browser |
| | Check yourself | predict the output (answers printed by real code); spot the bug (real bugs, each with its fix as code); what would you change if... (answers as code); the questions they ask; everything folded |
| | All the code | download buttons for the core and complete Maven projects (zips embedded in the page); every core file in typing order; each follow-up's new files, folded |

The left list shows minutes per step; the must-do path is the steps without *later*.

## Writing rules

These come from the reader's feedback on earlier versions. Break none of them.

- Plain, natural English. Short sentences. Explain the problem before any solution.
- Realistic names and numbers (score-widget, fantasy-app, 5 a second), used the same way on every
  step. Never acme, foo, Client A.
- Show the thinking as: the first idea, what goes wrong, what we do instead; then "X, not Y: because".
  Never "underline the nouns", never a requirement-to-class mapping, never R1/R2 labels.
- No "say this" boxes, no scripts of what to tell the interviewer, no "a strong answer contains",
  no walkthrough lists of the same content in other words.
- Code first. The explanation lives in the code's comments; prose around code is 2-4 sentences.
- Only code you would type in the room: no validation, no custom `toString`, no edge-case paths
  or helpers that exist only for demos. Mention the edge case in a Q&A instead.
- Code in digestible pieces: whole files of 10-50 lines; a longer file is shown in labelled parts
  (`W.part`), with a copy button for the whole file.
- Explain a concept where it is first needed (a "Java ·" note), never in a glossary dump.
- Every number on the page comes from a program the build ran. Measure before quoting a cost.
- Follow-ups build on the design and on each other, with code, and each says which existing
  interface absorbed the change.
- Say what is not exact, what is left out, and the one hole each follow-up leaves.
- Main text is read in full; folds are skimmed. Put only repeated or optional material in folds.
- LLD is about code, abstractions and principles: no capacity estimates, no HLD boxes.
- At most two interview Q&As per step; the rest go to Check yourself.
- Never claim which of two measured things wins: print both, and let generated words describe
  the numbers of this build (the lock-free step does this).
- A race test must fail on every run when the code is broken. When many threads are not enough,
  widen the race window on purpose (a factory that takes 50 ms), rather than hoping.

## Files of a problem

```
<slug>/java/*.java     the code, one type per file, written once for every snapshot (see snap.py)
<slug>/demos/*.java    the tiny programs whose output the page shows; follow-up demos call
                       Check.that(...) so a wrong number stops the build
<slug>/config.py       snapshots, build steps, demos, broken copies (MUTANTS), strip groups
<slug>/problem.py      the words: one function per step, in page order, returning
                       dict(id, group, nav, title, body, min, opt[, stage]); `min` is the
                       step's reading minutes, `opt` marks a step as *later*
<slug>/figures.py      the diagrams, drawn with svg.py (sequence() draws sequence diagrams)
```

Snapshot markers in the Java files (flat, never nested):

```
//@ from f3            the lines below exist from snapshot f3 on
//@ until f3           ...only before f3
//@ from f1 until f4
//@ end
//@ file from f2       first line: the whole file exists from f2 on
```

`problem.py` writes steps with the helpers in `build.py`'s class `W`: `md`, `code`, `snippet`,
`part`, `diff`, `run`, `asc` (text panels; `{r}`, `{g}`, `{y}`... colour spans; ✗ and ✓ colour
themselves), `pair`, `fig`, `table`, `xy`, `ask`, `strip`, `java`, `javas`, `box`, `asks`,
`reveal`, `drill`, `checks`, `timed`, `copybox`, `onefile`, `misslog`, `mutant_table`.
`w.runs.out[name]` is a program's output, for quoting a measured number in the words.

## What the build checks

- Every build step compiles on its own with the steps before it, with `-Xlint:all -Werror`.
- Every snapshot compiles; its demo runs and checks its own numbers; the tests pass in every
  snapshot (a follow-up never breaks the core).
- Every broken copy in `MUTANTS` makes its named test fail on every run (race tests run 10 times);
  other tests may fail too.
- The exported `complete` project compiles with every demo, and every demo runs.

## Before shipping a page

1. `python3 build.py <slug> --fresh` passes.
2. Screenshots of every step at 1440 px and 390 px: no clipped figure, no overflow, code readable.
   On a phone, tables turn into one card per row and figures scroll sideways at full size.
3. A technical review (every claim, every line of code) and a cold read by someone playing the
   learner; fix what they find, rebuild, look again.
