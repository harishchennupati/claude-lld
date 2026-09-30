# Building a NEW LLD workbench page (2026-09-26 expansion; systems chosen from research/landscape-*.md)
TARGET (his instruction 2026-09-27): companies that hire from India = Indian product companies and startups, FAANG India,
GCCs / US companies in India, some UK / Singapore companies. Rank follow-ups by how often THEY ask; no AI-lab-only variants.
Run the page's research from the landscape files first (the session web-search budget is small).

Prompt template (fill SLUG, TITLE, KIND, EVIDENCE_IDS, GUIDANCE):

"Build the LLD workbench page for TITLE (slug SLUG) in /Users/harishchennupati/answers/lld, to the locked format, in one pass that is
already reviewed. Read first, fully: LLD-SPEC.md (the contract: five pages, twelve moves, Java rules), EDIT-RUBRIC.md (what an
editor would add or cut), REVIEW-RUBRIC.md (parts A and C: the technical and plain-English bar; part B is replaced by the evidence
below), then _build_pl_wb.py (the gold page's content; he studied the parking lot and approved its depth and English),
lld_engine.py (the helpers you call), and specs/vending.py (a recently reviewed spec, as an example of engine use). Look at
parking-lot-workbench.html pages 1, 2 and 5 in headless Chrome with the sed trick from LLD-SPEC.md.

Evidence of what companies actually ask (use it; the page must match the REAL task: its prompt, its levels, its method names and
its follow-ups): research/landscape-bigtech.md, research/landscape-ailabs.md, research/landscape-india-sea.md (and the .json
files) entries EVIDENCE_IDS. Write research/SLUG.md: a table `question or level | company | year | URL | where the page answers it`.
If web search is available, spend at most 10 searches filling gaps; if it is exhausted, the landscape files are enough.

Kind: KIND.
- lld: the usual page.
- practical (a progressive task, e.g. a CodeSignal 4-level test or an AI-lab practical round): page 01 quotes the task and lists
  its levels (what each level adds, with the real method names and signatures); Main.java implements ALL levels behind the real
  API; the moves derive the design that survives all levels (say at which level each class or map first appears); page 05
  starts with one timed card per level (level 1 is the implement card; levels 2-4 are follow-up cards, 15-25 minutes each),
  then the real follow-ups.
- concurrency: the wait/notify protocol, lost and spurious wakeups, shutdown, interrupts, back-pressure and what
  java.util.concurrent already gives you are the core; the race test runs many threads and checks the invariant.

Design guidance: GUIDANCE

Deliverables: specs/SLUG.py and SLUG/Main.java, SLUG/Extensions.java, SLUG/FailureTests.java; run `python3 specs/SLUG.py` until
the guard prints; `python3 _verify.py SLUG shots` and LOOK at the screenshots (no label outside its box, no overlap, no empty
bands); run `java Main` and `java ExtDemo` (JDK /opt/homebrew/opt/openjdk@21/bin) in a temp dir without exceptions. Work only on
this slug's files. Report under 300 words: the five page titles, the move titles, the follow-up questions with the company that
asks each, the test names, and anything you were unsure about."
