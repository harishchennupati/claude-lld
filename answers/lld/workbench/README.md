# LLD workbench: the format, and how to build one

One page per LLD problem, generated from compiled Java. The rate limiter
(`../rate-limiter-workbench.html`) is the pilot; every other problem follows it.

```
python3 build.py rate-limiter            # writes ../rate-limiter-workbench.html and ../rate-limiter-code/
python3 build.py rate-limiter --fresh    # recompile and rerun everything, ignoring the cache
```

A problem can define `VARIANTS` in `problem.py` (suffix → pages function) to build the same
content in more than one layout. The rate limiter now builds one: design and build in one walk,
each branch as the question, the options weighed, the decision, the diagram so far, then the code.

## What the reader gets

The reader is preparing for SDE-2/3 interviews. They read a page once, then close it and must
reproduce the reasoning, the classes, the code and the follow-ups, and answer the
interviewer's questions. So the page teaches a small design well, with every line compiled.

One step is on screen at a time (the left list and ← → move between steps). **Read** mode shows
everything; **Practise** mode hides the code and the answers until the reader asks.

| group | steps | what each step holds |
|---|---|---|
| Understand | The problem | the interviewer's line (a real reported wording); the situation, with realistic names; one flow picture; the questions to ask, each with what its answer changes in the code; what the hour holds (typed vs said) and the 60-minute plan; how to use the page |
| | The core idea (e.g. how to count) | every option explained from scratch with ASCII pictures and worked numbers, its catch, and where it is still the right choice; all options on the same tests; one line each; which one the core uses and why |
| Design | The design, top-down | start at the front door and keep asking "what does this need?", going deeper (↓) until a question is settled, then back (↑); each answer is a type, with the first-draft code where it helps; the whole design as one tree; one case walked before typing; where each new requirement will land |
| Build | one step per group of 1-3 types, in the order they are typed in the room (top-down, the caller before its parts) | the where-we-are strip; whole files, explained in their comments; a tiny program's output where it helps; a ✗/✓ panel where a race is the point; "The thinking": why the code is written this way, including the threads, patterns and SOLID point it makes |
| | Run it | `Main` and its output: the walked case and a race |
| Follow-ups | one step each, phrased as an interviewer adds scope; optional ones marked *later* | the ask; the strip with new and changed types; where it lands in *our* design; the diff; the demo's output; the catch. A follow-up nobody types in the room (many servers) is explained in prose with the seam as a sketch. A last step answers the quick ones in a sentence each |
| Remember and practise | Recall | the design as signatures in typing order; cards; the lines to remember exactly |
| | Practise | the design on paper; the core with a tick list (plus the whole core in one file); each follow-up from `<slug>-code/steps/<step>/`; out loud; when to repeat; a miss log kept in the browser |
| | Check yourself | predict the output (answers printed by real code); spot the bug; what would you change if...; everything folded |
| | All the code | download buttons for the core and complete Maven projects; every core file in typing order; each follow-up's new files, folded |

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
- Design top-down, as people think in the room: from the request at the front door to where the
  state lives, going deep on one question before coming back. Type in that same order.
- Simple, everyday patterns: plain interfaces, constructor injection, a plain enum with a switch.
  No enums holding lambdas, no factories implemented by enums, no predicate-built rules.
- Model the domain, not the example: a tier is a property of the customer that carries a limit;
  other limits are the same limiter with another key.
- No tests step, no separate principles or patterns section: say what a pattern or a thread
  choice is for where the code makes it.
- Follow-ups as interviewers ask them: new requirements and more scope, not operational stories.
  Do not type what nobody types in the room (a Redis script): explain it and show the seam.
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
