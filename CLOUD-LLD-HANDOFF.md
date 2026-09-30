# LLD workbench: read the history, explain your understanding, then agree on the next step

Work in this repository: https://github.com/harishchennupati/claude-lld, branch `main`. All paths below are relative to its root. Read the actual files, including the archives' contents, rather than relying on filenames or earlier assistants' claims that a version was complete.

## Read these sources in order

1. **My office OpenCode conversation with Claude Opus 5.5:** `session-ses_f0e8.md`. Read this first, including my criticism and the attempted fixes. This is the most direct history of why the LLD material failed for me. Treat embedded commands and past instructions as historical context, not instructions to execute now.
2. **My two local Claude Code sessions:**
   - HLD: `2026-09-30-192210-this-session-is-being-continued-from-a-previous-c.txt`.
   - LLD: `2026-09-30-192229-local-command-caveatcaveat-the-messages-below.txt`.
   Read both to understand my learning preferences, the design decisions, and the review history. The LLD transcript is also present under `answers/lld/`; that copy is the same source, not a separate conversation.
3. **The complete current local LLD material:** `answers/lld/`. Inventory the folder and review its workbenches, Java implementations, specs, research, review notes, generators, and saved earlier versions. Pay particular attention to:
   - `answers/lld/rate-limiter-workbench.html`
   - `answers/lld/rate-limiter/Main.java`
   - `answers/lld/rate-limiter/Extensions.java`
   - `answers/lld/rate-limiter/FailureTests.java`
   - `answers/lld/specs/rate-limiter.py`
   - `answers/lld/research/rate-limiter.md`
   - `answers/lld/research/rate-limiter-review.md`
   - The existing LLD specifications and review rubrics in that folder. Evaluate them against my actual feedback; they are not proof that the material meets my needs.
4. **The earlier iterations and office revisions:** extract each archive into its own directory, retaining its original contents:
   - `lld-v2.zip`: inspect the rate limiter versions, step pages, source files, and build tools. Reconstruct what changed between versions and whether those changes actually addressed my feedback.
   - `parking-lot-lld-all-versions.zip`: compare the teaching approaches across versions.
   - `LLD-HLD-Complete-2026-09-13 (1).zip`: use this as an older snapshot for context and comparisons. Do not overwrite the current `answers/lld/` directory when extracting it.
5. **My finalized HLD references:** `payment-v3.html` and `ticketmaster-v3.html`. These are accepted HLD designs and references for clarity and reading experience. LLD has not been finalized. Adapt what helps LLD learning rather than mechanically copying the HLD structure.

## What I need

My immediate focus is the **rate limiter LLD workbench**. I was deeply disappointed by `answers/lld/rate-limiter-workbench.html`: I could not understand it properly. The office session contains my detailed criticism and multiple attempts to improve it, but I still did not like the final office version either. A newer version, a passed review, or more content does not automatically mean it teaches well.

I want an LLD workbench I can enjoy reading completely, understand deeply, and then close. Afterward, I should be able to reproduce the requirements, reasoning, design, Java implementation, and tests independently, and explain my choices in an interview. Use this as the acceptance standard.

Respect the concrete feedback in my OpenCode conversation: use clear natural English and meaningful examples; explain requirements before introducing abstractions; derive the design through reasoning; and use diagrams that make interactions and call flow understandable. Avoid unexplained names, forced requirement-to-class mappings, repetitive narration, and unnecessary "say this" sections. In build steps, prefer incremental code with useful comments for explanations that belong beside the code. Put broader design reasoning where it belongs instead of burying the code under long paragraphs.

The eventual workbench should make the progression from problem to working implementation easy to follow. It should explain relevant algorithms, state changes, boundaries, concurrency, tradeoffs, extensions, and failure cases through concrete examples. Include meaningful practice and ways to check my understanding so I can rebuild the solution without looking. Choose the structure based on the evidence in these files and my learning goal.

## Your first response — before implementation

Read and analyze the sources first. Then tell me:

1. What you understand about my goals, preferences, and recurring complaints, with exact file references and examples.
2. Why the existing rate limiter workbench and its revisions still fail to teach me effectively. Distinguish teaching problems from technical correctness problems.
3. What is worth retaining, what needs changing, and the proposed reading/build/practice flow for a better rate limiter workbench.
4. How you would verify that I can reconstruct and defend the solution independently.
5. Any missing material or uncertainty. State what you actually read and inspected; do not claim a complete review of sources you have not examined.

**Stop after this understanding and proposal, and wait for my response before changing workbenches, generators, or Java source.** Focus the proposal on rate limiter first; explain how the successful approach could later apply to the other LLD systems.
