# LLD rollout tracker (started 2026-09-13; target: all done by morning)

How to run one system: launch a general-purpose agent (model opus) with the prompt template in this file, slug from the list. It writes specs/<slug>.py + <slug>/{Main,Extensions,FailureTests}.java, runs the engine (guard), screenshots, reports. After each report: re-run `python3 specs/<slug>.py` to confirm the guard line; `node` syntax check of the page's last <script>; count STEPS == 5; open one page screenshot if it is one of the spot checks. Then mark it here and launch the next slug. Keep ~6 agents running.

Prompt template (fill SLUG, TITLE, and paste the system's paragraph from LLD-SYSTEMS.md):
"Build the LLD workbench page for TITLE, to the locked format. Read first, fully: /Users/harishchennupati/answers/lld/LLD-SPEC.md (the contract), then /Users/harishchennupati/answers/lld/_build_pl_wb.py (the gold example's content) and /Users/harishchennupati/answers/lld/lld_engine.py (the helpers you call). Open /Users/harishchennupati/answers/lld/parking-lot-workbench.html in headless Chrome with the sed trick from the spec and look at all five pages. Source material: /Users/harishchennupati/answers/system-design/_pipeline/sd_src/lld-SLUG.json; use it for coverage, do not copy its code. Deliverables: /Users/harishchennupati/answers/lld/specs/SLUG.py and the Java in /Users/harishchennupati/answers/lld/SLUG/: Main.java, Extensions.java, FailureTests.java. slug "SLUG", title "TITLE". Design guidance for this system: <paragraph>. Run the spec until the engine prints the guard line, run `java Main` and `java ExtDemo` in a temp dir, screenshot the five pages and inspect them, fix overflows. Report under 300 words: the five page titles, the move titles, the test names, and anything you were unsure about."

| slug | title | status |
|---|---|---|
| parking-lot | Parking Lot | DONE (gold) |
| elevator | Elevator System | DONE (verified) |
| bookmyshow | Movie Ticket Booking | DONE (verified) |
| splitwise | Splitwise | DONE (verified, screenshots ok) |
| vending | Vending Machine | DONE (verified) |
| atm | ATM | DONE (verified) |
| rate-limiter | Rate Limiter | DONE (verified) |
| lru | LRU / LFU Cache | DONE (verified) |
| logger | Logger | DONE (verified) |
| tic-tac-toe | Tic-Tac-Toe | DONE (verified) |
| chess | Chess | DONE (verified) |
| snake-ladder | Snake and Ladder | DONE (verified) |
| notification-lld | Notification Service (LLD) | DONE (verified) |
| file-system | In-memory File System | DONE (verified) |
| stackoverflow | Stack Overflow | DONE (verified) |
| order-book | Order Book / Matching Engine | DONE (verified) |
| pubsub | Pub/Sub System | DONE (verified) |
| ride-sharing | Ride Sharing | DONE (verified) |
| food-delivery | Food Delivery | DONE (verified) |
| text-editor | Text Editor | DONE (verified) |
| spreadsheet | Spreadsheet | DONE (verified) |
| digital-wallet | Digital Wallet | DONE (verified) |
| banking | Banking System | DONE (verified) |
| inmem-db | In-memory Database | DONE (verified) |
| cache-eviction | Cache with Eviction Policies | DONE (verified) |
| payment-gateway | Payment Gateway | DONE (verified) |
| mt-blocking-queue | Bounded Blocking Queue | DONE (verified) |
| mt-producer-consumer | Producer-Consumer | DONE (verified) |
| mt-rwlock | Read-Write Lock | DONE (verified) |
| mt-ttl-cache | TTL Cache | DONE (verified) |
| mt-striped-map | Striped Concurrent Map | DONE (verified) |
| mt-dining | Dining Philosophers | DONE (verified) |
| mt-h2o | H2O Barrier | DONE (verified) |
| mt-print-series | Print in Order | DONE (verified) |

## Editorial pass (2026-09-14, EDIT-RUBRIC.md): add what the interviewer asks about THIS system, cut filler, plain English, consistency; 60-75 min read target
| slug | edit status |
|---|---|
| elevator | EDITED (verified) |
| bookmyshow | EDITED (verified) |
| order-book | EDITED (verified) |
| splitwise | EDITED (verified) |
| vending | EDITED (verified) |
| atm | EDITED (verified) |
| rate-limiter | EDITED (verified) |
| lru | EDITED (verified) |
| logger | EDITED (verified) |
| tic-tac-toe | EDITED (verified) |
| chess | EDITED (verified) |
| snake-ladder | EDITED (verified) |
| notification-lld | EDITED (verified) |
| file-system | EDITED (verified) |
| stackoverflow | EDITED (verified) |
| pubsub | EDITED (verified) |
| ride-sharing | EDITED (verified) |
| food-delivery | EDITED (verified) |
| text-editor | EDITED (verified) |
| spreadsheet | EDITED (verified) |
| digital-wallet | EDITED (verified) |
| banking | EDITED (verified) |
| inmem-db | EDITED (verified) |
| cache-eviction | EDITED (verified) |
| payment-gateway | EDITED (verified) |
| mt-blocking-queue | EDITED (verified) |
| mt-producer-consumer | EDITED (verified) |
| mt-rwlock | EDITED (verified) |
| mt-ttl-cache | EDITED (verified) |
| mt-striped-map | EDITED (verified) |
| mt-dining | EDITED (verified) |
| mt-h2o | EDITED (verified) |
| mt-print-series | EDITED (verified) |
| parking-lot | EDITED (verified) |
