# Job Scheduler: what interviewers ask (research for job-scheduler-workbench.html, 2026-09-27)

Sources: the landscape files (B job-scheduler, I job-scheduler, A job-scheduler-durable), then every LeetCode post they
cite was read in full through LeetCode's public GraphQL API (curl; old posts via `topic(id)`, new ones via
`ugcArticleDiscussionArticle(topicId)`). Marks: **1st** = the candidate wrote about their own round; **(v)** = read in
full by me; **agg** = aggregator (prachub / fastprep), lower confidence. The web-search budget was exhausted (0 searches
made). Ranked for companies that hire from India (his instruction, 2026-09-27); AI-lab-only variants are listed at the
end and were NOT added.

## What was asked, and where the page answers it

| question or level | company | year | URL | where the page answers it |
|---|---|---|---|---|
| "Design a Delayed Scheduler": logic plus code, like a DSA round; "a standard LinkedIn Concurrency round question however followups were hard" | LinkedIn (Bangalore) | 2024 | https://leetcode.com/discuss/post/5911896/ (1st, v) | The whole page; the wake-early protocol is move 4 and FU1; cancel FU7; recurring FU2 |
| Concurrency round is its own hour at LinkedIn India (blocking queue, H2O, delayed scheduler); "he would run my code offline" | LinkedIn | 2024 | https://leetcode.com/discuss/post/5039865/ , https://leetcode.com/discuss/post/4742052/ (1st, v) | Page 04: the code compiles and runs; FailureTests prove the claims |
| "Implement a thread-safe task scheduler" (LLD + coding round, then Observer, then Kafka producer/consumer) | Salesforce (SMTS, India) | 2026 | https://leetcode.com/discuss/post/7619394/ (1st, v) | Move 4, FU3 (16 threads x 500 jobs race), listeners = Observer (move 3, FU15) |
| "Design a job scheduler that runs all available jobs in an optimized manner, considering job dependencies"; get_next_jobs(finished_jobs) | Rubrik (L4) | 2025 | https://leetcode.com/discuss/post/6730864/ (1st, v) | Prerequisites: moves 4-6 second halves, FU4 (parallel workers, count-down under the lock) |
| Task scheduler: dependencies, priority (1,2,3), retry "if task failed 5 times", cancel, parallelize, history, circular dependency protection; "not able to run the code" | Media.net (SDE-2, India) | 2025 | https://leetcode.com/discuss/post/7346375/ (1st, v) | FU4 (dependencies), FU8 (priority), FU6 (retry x5), FU7 + move 6b (cancel and its dependents), FU3 (parallel), FU15 (history), FU5 (cycle) |
| "Design your own Cron System": a unix command plus the epoch time to run it | Swiggy Instamart (SDE-1) | 2025 | https://leetcode.com/discuss/post/6260445/ (1st, v) | JobSpec.at(epochMs) in Main; FU9 (CommandTask, Cron, time zone) |
| "Design an Asynchronous Task Processor", extended to: scheduling at a particular time, at recurring intervals, execution management | Harness (SSE1, India) | 2026 | https://leetcode.com/discuss/post/8524180/ (1st, v) | Main (schedule, scheduleAtFixedRate / WithFixedDelay); FU2 |
| "Provide LLD for Task scheduler" | Oracle OCI (Bangalore) | 2023 | https://leetcode.com/discuss/post/4160037/ (1st, v) | The whole page |
| "Task Scheduler", LLD + HLD in one round, after Java concurrency questions | MPL (SDE-2, Bangalore) | 2023 | https://leetcode.com/discuss/post/3954383/ (1st, v) | Moves 7-8 (lock arithmetic, ladder), FU10 (jobs table, many machines), FU14 |
| "A problem similar to job scheduler"; the staff interviewer wanted LLD + HLD and asked push vs pull | Uber (L4) | 2025 | https://leetcode.com/discuss/post/7196883/ (1st, v) | FU10 (machines pull due rows and claim them with a lease); move 12 |
| HM round: "Design the job scheduler" | Amazon (SDE-2) | 2024 | https://leetcode.com/discuss/post/4999447/ (1st, v) | The whole page; FU10 for the persistence discussion |
| Scheduler with machines that each have capabilities; a job runs only on a machine with all it needs | Microsoft (hiring drive) | 2025 | https://leetcode.com/discuss/post/7135013/ (1st, v) | FU11 (Placement: best fit, backfilling, refused if no machine fits) |
| Jobs scheduled on clusters by infra needs (e.g. 100 GB RAM, CPU); job priority | Arcesium | 2023 | https://leetcode.com/discuss/post/3351948/ (1st, v) | FU11 (CPU/RAM needs), FU8 (priority) |
| TaskScheduler in milestones: add / complete / get next; prerequisites; completion plan for a task | Brex (SWE II, US) | 2025 | https://leetcode.com/discuss/post/6475958/ (1st, v) | FU5 (CompletionPlan gives yoga, coffee, toast, brainstorm, as in the post), FU4 |
| Tasks with dependencies printed in a format; follow-up on DAGs | Rippling (SDE2, Bangalore) | 2026 | https://leetcode.com/discuss/post/7908132/ (1st, v) | FU5, moves 5b-6b |
| "Laptop interview: somewhat on the lines of design a scheduler" | Lyft (US) | 2024 | https://leetcode.com/discuss/post/4549316/ (1st, v) | The whole page |
| ScheduledThreadPoolExecutor from scratch: DelayQueue, schedule / fixed-rate / fixed-delay, next = last + period vs now + delay, shutdown interrupts workers | Uber / Goldman Sachs / Rubrik (compiled post, a tutorial, secondary) | 2026 | https://leetcode.com/discuss/post/7646238/ (v) | FU12 (DelayQueueScheduler, what the JDK gives, its traps), FU2, FU13 |
| Follow-ups listed across the B entry: N worker threads; sleep until the next due time and wake early for an earlier task; fixed-rate vs fixed-delay; cancel; priorities and fairness; retry and timeout; a throwing task must not kill the worker | 13 companies (landscape B job-scheduler) | 2023-2026 | research/landscape-bigtech.md, entry job-scheduler | FU1, FU2, FU7, FU8 (aging), FU6, FU13 (TimeoutTask), FU6 + test 9 |
| Follow-ups listed in the I entry: cancel a task and its dependents; execution history; parallel execution with a pool; recurring and run at time T | Swiggy, MPL, Oracle, Media.net, Uber, Harness, Arcesium (landscape I job-scheduler) | 2023-2026 | research/landscape-india-sea.md, entry job-scheduler | Move 6b + test 3, FU15, FU3, FU2 + FU9 |

## Asked, but deliberately not given a card

| question | company | year | URL | why not |
|---|---|---|---|---|
| TaskProcessor: runTask(task), flushTasks(), flush when 10 accumulate | Netflix (US onsite) | 2023 | https://leetcode.com/discuss/post/3953494/ (1st, v) | A batching buffer, not a time scheduler; US-only; at the 18-card limit |
| Durable cron: occurrences, time zones, missed runs, worker leases; durable delayed task scheduler; debug a concurrent job scheduler (rate limit of R starts per second) | Cursor, Decagon, Scale AI, OpenAI (agg) | 2026 | https://prachub.com/interview-questions/design-a-durable-cron-job-scheduler and siblings in landscape A job-scheduler-durable | AI-lab-only: excluded by the 2026-09-27 instruction. The general parts (leases, misfire after downtime, time zones) are covered anyway for Uber / MPL / Swiggy in FU9 and FU10 |

## Coverage summary
Every follow-up card cites at least one India-hiring company. Cards in order of how often those companies ask:
1 wake early (LinkedIn), 2 fixed rate / delay (Harness), 3 thread-safety race (Salesforce, LinkedIn, Rubrik),
4 prerequisites race + failure (Media.net, Rubrik), 5 cycle + completion plan (Media.net, Brex, Rippling),
6 retries (Media.net), 7 cancel (Media.net), 8 priority + aging (Media.net, Arcesium), 9 cron (Swiggy, Harness),
10 persistence + many machines (Uber, MPL, Amazon), 11 capabilities + limits (Microsoft, Arcesium),
12 the JDK (LinkedIn, Uber/GS/Rubrik), 13 shutdown + timeouts, 14 scale + back-pressure (MPL, Uber),
15 status + history (Media.net), 16-18 patterns, SOLID, enum vs interface.
