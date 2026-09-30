# Review pass on one LLD workbench (2026-09-26): technical truth + plain English + what companies really ask

He has studied `parking-lot-workbench.html` and says it is good. That page is the bar for depth and for English.
The other pages were built by agents on 2026-09-13/14 and edited on 2026-09-15; he has not read them. This pass makes
each page trustworthy BEFORE he studies it: nothing false, nothing he has to read twice, nothing an interviewer asks
that the page leaves out.

The reader: an SDE-2/3 backend engineer (Java), preparing for LLD / machine-coding / practical-coding rounds at FAANG,
AI labs (Anthropic, OpenAI...), Indian product companies (Flipkart, Swiggy, PhonePe, Razorpay...) and Singapore tech
(Grab, Shopee, ByteDance...). Anxious, diagram-first, NOT an academic: plain words, concrete numbers, pictures.

## 0. Rules
- Do not change the frame: five steps; moves 10-12 in the fixed order of LLD-SPEC.md; 8-18 follow-ups. Never edit
  `lld_engine.py`, `_build_pl_wb.py` (unless your slug is parking-lot), or any other slug's files.
- Back up before the first edit (only if the backup does not exist yet):
  `cp specs/<slug>.py specs/<slug>.py.pre-review` and `cp <slug>/X.java <slug>/X.java.pre-review` for each Java file.
- Rebuild with `python3 specs/<slug>.py` (the guard must print `guard: compiles; FailureTests ALL PASS`), then
  `python3 _verify.py <slug> shots` and LOOK at the screenshots with the Read tool. Also run `java Main` and
  `java ExtDemo` (JDK at `/opt/homebrew/opt/openjdk@21/bin`) in a temp dir: both must finish without an exception.
- Read the page as text first (pictures and code stripped) with:
  ```
  python3 - <<'EOF'
  import re,json,html
  t=open('/Users/harishchennupati/answers/lld/<slug>-workbench.html').read()
  S=json.loads(re.search(r"const STEPS=(\[.*?\]);\nconst RAW",t,re.S).group(1))
  for i,s in enumerate(S):
      x=re.sub(r'<svg[\s\S]*?</svg>',' [PIC] ',s['body']); x=re.sub(r'<pre[\s\S]*?</pre>',' [CODE] ',x)
      print('=== STEP',i+1,s['title']); print(re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',x))))
  EOF
  ```
  Run the same on `parking-lot-workbench.html` (steps 1-2 at least) to calibrate the English before editing.
- Changes must be justified. If a part is right and clear, leave it alone and say so. Do not grow the page: fix in
  place; the reading time stays 60-85 minutes. Severity: S1 wrong result or race in the code; S2 the page says
  something false or contradicts the code; S3 unclear, jargon, or needs a second read; S4 nit.

## A. Technical review (the most important part)
Read Main.java, Extensions.java and FailureTests.java line by line, as a senior interviewer at Google / Uber / Stripe
would, then the page against the code.
1. Concurrency: check-then-act outside the lock; shared fields read without the lock or `volatile`; a collection
   iterated while another thread changes it; two locks taken in different orders (deadlock); a lock held while
   calling out (listener, payment, I/O, sleep); `if` instead of `while` around `await`; signal before the state
   change (lost wakeup); an interrupt or exception path that leaks a permit, a slot, a hold or a reservation.
2. The critical step: nothing is committed before the irreversible action succeeds; a failure leaves state exactly
   as it was; a retry is safe (idempotency key where money moves); UNKNOWN outcomes are handled where they exist.
3. Edges: empty, zero, negative, duplicate ids, exactly-at-the-boundary times, overflow, rounding (money in long
   paise/cents or BigDecimal, never double), time going backwards, capacity 0 or 1.
4. Complexity: every O(1) / O(log n) claim on the page is true in the code (no hidden scan, no `list.remove(obj)` or
   `PriorityQueue.remove(obj)` sold as cheap, no copy per call).
5. Domain rules complete and correct (chess rules, snake-and-ladder rules, price-time priority and partial fills,
   LFU tie-break, the elevator sweep, token-bucket refill math, Splitwise simplify, interest and rounding, ...).
6. Java facts stated in prose are correct (ConcurrentHashMap guarantees, ReentrantLock fairness, spurious wakeups,
   volatile vs atomic, synchronized re-entry, executor shutdown, ...).
7. Page vs code: class and method names, the order at the critical step, the numbers in moves 7-8 (recompute the
   arithmetic), the class diagram shows every class of Main.java, the "what the code must do" picture matches the
   root class's public methods, each follow-up's text matches the snippet it shows.
8. As an interviewer: is this the answer a strong SDE-2/3 candidate is expected to give? Flag over-engineering that
   nobody writes in 60 minutes (then make the implement card say which part is the must-write core) and missing
   standard answers (for example LFU without O(1) frequency buckets).
For every real bug: fix the code, add a check to FailureTests that fails on the old code and passes on the new
(confirm it failed on the old code), and fix every sentence and picture on the page that described the old behaviour.

## B. What interviewers actually ask about THIS system (web research, about 20 minutes)
- TARGET COMPANIES (his instruction, 2026-09-27): Indian product companies and startups (Flipkart, Swiggy, Zomato, PhonePe,
  Razorpay, CRED, Meesho, Zepto, Groww...), FAANG offices in India, GCCs and US companies in India (Walmart, Goldman Sachs,
  Uber, Atlassian, Salesforce, Adobe, Microsoft IDC, Intuit, Rippling...), and some UK / Singapore companies that hire from
  India. Rank follow-ups by how often THESE companies ask them. Do not add AI-lab-only (OpenAI, Anthropic, xAI...) variants.
- FIRST read the three landscape files already researched on 2026-09-26 (grep them for this system and its variants):
  research/landscape-bigtech.md, research/landscape-ailabs.md, research/landscape-india-sea.md (+ .json). They hold
  first-hand reports with company, year and URL. The session's web-search budget may be exhausted; if so, these files
  are the evidence, and LeetCode Discuss posts can still be read with curl through its public GraphQL API.
- Then search for real interview reports on this system from 2023-2026: LeetCode Discuss interview experiences,
  GeeksforGeeks interview experiences, Glassdoor, Blind, Reddit, Medium candidate write-ups, 1point3acres,
  codezym, workat.tech, algomaster, hellointerview, igotanoffer, YouTube titles. Prefer first-hand reports.
- Collect the follow-ups, twists and VARIANTS of the prompt that companies actually used (company, year, URL).
  Variants matter: e.g. Amazon's parking lot vs Flipkart's; Snake and Ladder with several dice or crocodiles;
  CodeSignal-style 4-level progressive versions (bank: scheduled payments, merge accounts, balance at time t;
  in-memory DB: TTL, backup/restore; file storage: users with capacity, top-N by size) used by Anthropic,
  Coinbase and others; LeetCode-style API versions (LRU 146, LFU 460, Design Twitter 355, Hit Counter 362 ...).
- For each real follow-up or variant the page does not answer: add it. Small ones fold into an existing card;
  real ones become a follow-up card with code in Extensions.java (or Main.java if it is core) and a test if it
  makes a claim. Stay within 18 follow-ups: to add past that, merge or cut the weakest card (one that only
  restates a move). Do not add a question with no evidence that anyone asks it.
- Write `research/<slug>.md`: a table `question | company | year | URL | where the page answers it`.

## C. Plain English (the bar is the parking lot)
- Every technical term is defined where it first appears on the page, in a short plain clause, e.g.
  "an idempotency key (a unique id for this request, so a retry that arrives twice is applied once)".
  Check at least: invariant, aggregate / aggregate root, idempotent, atomic, compare-and-set, contention,
  throughput, latency, amortized, monotonic, linearizable, happens-before, visibility, volatile, re-entrant,
  critical section, starvation, livelock, fairness, back-pressure, fan-out, tombstone, copy-on-write, snapshot,
  journal / write-ahead log, ledger, double entry, reconcile, compensating action, saga, sharding, striping,
  eviction, TTL, heap, deque, trie, DAG, topological order, sentinel, memoize, orchestrator, projection,
  debounce, coalesce, jitter, exponential backoff, and any term the page coins itself.
- Keep the words an interviewer uses (he must be able to say them), explain them; cut words that are there only
  to sound clever.
- No sentence he has to read twice: one idea per sentence; split sentences over ~30 words; no stacked nouns
  ("per-key striped lock-free ring buffer"); prefer this system's own example with numbers.
- Picture labels short, plain, and inside their boxes.

## D. Report
Rebuild and verify (section 0). Then write `research/<slug>-review.md` and return the same text (under 350 words):
- the guard line and the `_verify.py` summary lines;
- bugs found, each with severity, what was wrong, the fix, and the new test name;
- English: how many fixes, and three before -> after examples;
- follow-ups / variants added, each with its company evidence;
- anything you were unsure about or chose not to change, and why.
