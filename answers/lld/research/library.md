# Library management: what interviewers actually ask (research for the new page, 2026-09-27)

Sources: the `library-management` entries of `research/landscape-india-sea.{md,json}` and `research/landscape-bigtech.{md,json}`.
Every LeetCode post below was re-read in full on 2026-09-27 through LeetCode's public GraphQL endpoint (`topic` and
`ugcArticleDiscussionArticle` queries, by post id); the workat.tech problem page was fetched with curl (its text is
server-rendered). No web searches were used. FU n = follow-up card n on page 05 of `library-workbench.html`.

| question or level | company | year | URL | where the page answers it |
|---|---|---|---|---|
| Machine coding, 90 min, in memory, demo-able: add books by name and author with a generated id (first three letters of the author's last name + a number, e.g. ROW1234); several copies of a book; register and unregister users; borrow by book id; if every copy is out, join a FIFO waitlist; "When the book is returned to the library, it will not be marked as available and will be available only to the first user under the FIFO queue"; 14-day loans, fine Rs 20 per day late. Bonus: a user may reserve only one copy of a book; audit "given a bookId, the users having it" and "given a userId, the books issued to him" | Flipkart (SDE-2) | 2025 | https://leetcode.com/discuss/post/6729792/ | The core: `checkout`, `placeHold`, `returnCopy` and `placeCopy` (moves 4-6, FU 5); `Desk.borrow` = borrow, else join the queue; `StandardTerms` (14 days) and `PerDayFine(2_000)`; `ALREADY_HAS_TITLE`; `unregister`; `borrowersOf` / `loansOf`. The id rule: FU 6 (`BookIdGenerator`, ROW1001) |
| Backend LLD: add a book, get it by id, list books with filters (available books, books by author), register and fetch users, borrow if available, return and update availability, list a user's borrowed books. A book is borrowed by one user at a time; at most 3 books per user | Slice (SDE-3) | 2025 | https://leetcode.com/discuss/post/6704196/ | `StandardTerms` = 3 books (test 3: LIMIT_REACHED); `searchAuthor` and `Found.onShelf` (FU 7); `loansOf`; one copy lent once (FU 2) |
| Core Java + LLD round: "LLD - Design library management system", with threads, multithreading, HashMap internals and SOLID in the same round | Walmart (IN3 / SDE-2, Bangalore) | 2023 | https://leetcode.com/discuss/post/4343398/ | The whole page; the races (FU 2); SOLID (move 11, FU 15) |
| Core Java + LLD round: "LLD of a library management system (Class diagram and DB schema only)"; the same round asked about Singleton, Factory, Observer, Command, SOLID, ExecutorService and dependency injection | Walmart (IN3, Bangalore) | 2023 | https://leetcode.com/discuss/post/4374203/ | Page 03 (the class diagram); FU 8 (`LibrarySql.SCHEMA`); FU 14 names which of Singleton, Factory, Observer and Command earned a place and why (move 10) |
| LLD round: "Design a online book store (borrow, return books)"; the candidate discussed the DB schema, the API and design patterns (singleton, abstract factory, strategy) and implemented it | Zepto (SDE-1, via Interview Vector) | 2024 | https://leetcode.com/discuss/post/5760479/ | The core; FU 8 (schema); Strategy (move 3); FU 14 (why no Singleton, when a Factory pays) |
| Online assessment, LLD question: "Book store management" | Licious (SDE-2) | 2024 | https://leetcode.com/discuss/post/5996910/ | The whole page (the post gives no further detail) |
| Design round: "design a library system", HLD first and then LLD; "a run through of how we will go about in the design if a student wants to come and do x thing"; "then he asked me how you will scale it" | Microsoft (SDE-2, L61) | 2024 | https://leetcode.com/discuss/post/4937133/ | Page 01 (what the code must do; three weeks replayed); FU 3 (does one lock scale, the ladder); FU 12 (twenty branches) |
| "Design a Library Circulation System" (circulation = checkout, return, holds) | Microsoft (aggregator list, from landscape-bigtech.json) | undated | https://www.fastprep.io/microsoft-interview | The whole page |
| Onsite coding round: "LLD for library checkout + with SQL query" | Bloomberg (Senior SWE, NYC) | 2025 | https://leetcode.com/discuss/post/7363661/ | FU 8 (`LibrarySql.OVERDUE`, the claim `UPDATE copy ... WHERE status='AVAILABLE'`); checkout in the core |
| OOD: "Design Library Book Management System: borrow book, return book, reservation" (older than the 2023-26 window; kept because it is first-hand) | Amazon (onsite) | 2020 | https://leetcode.com/discuss/post/485566/ | The core; FU 5 (the queue and the pickup date) |
| Machine-coding practice problem (SDE II): racks 1..n, a rack holds at most one copy of any book; add to the first available rack ("Rack not available" if too few); borrow by book id gives the copy on the lowest rack, or borrow a named copy; return to the first available rack; at most 5 books per user ("Overlimit"); print a user's borrowed copies; search by book id, author or publisher; remove a copy | workat.tech (aggregator practice list) | read 2026-09-27 | https://workat.tech/machine-coding/practice/design-library-management-system-jgjrv8q8b136 | FU 9 (`RackedShelf`; this build also counts copies that are out, so a returned copy always finds a rack: test 13); the limit is one number in `LoanRules`; search in FU 7. Not added: the exact command-line format, and "remove a copy" (a refusal unless the copy is on the shelf) |
| Twists with no company report in the landscape files, from the design guidance (LLD-SYSTEMS-2.md): member tiers, e-books with licence counts, several branches, renewals refused while others wait, a lost-book charge, due-soon reminders | none found | n/a | n/a | FU 1 (`TieredTerms`), FU 16 (`EbookLending`), FU 12 (`BranchNetwork`), FU 10 (renew and lost), FU 11 (`DueSoonReminder`, `SmsOutbox`). Ranked after the evidenced cards |

## How the follow-ups were ranked
- Evidenced by first-hand reports from India-hiring companies, most often first: the waitlist and what a return does
  (Flipkart 2025, Amazon 2020), fines (Flipkart), the limit (Slice, workat.tech), the schema and the SQL (Walmart x2,
  Zepto, Bloomberg), Flipkart's bonus items (one copy per member, audit queries, unregister, generated ids), search and
  filters (Slice, workat.tech), scaling (Microsoft), patterns by name (Walmart, Zepto), racks (workat.tech).
- The concurrency cards (FU 2, FU 3) are the standard LLD follow-up; Walmart's round paired this LLD with Java threads.
- Guidance-only twists (tiers, e-books, branches, reminders) come after the evidenced cards.

## Not covered
- Intuit craft demo "Book exchange system" (2023, https://leetcode.com/discuss/post/3319368/): a question with no
  details, and a peer-to-peer exchange is a different system.
- Licious's first interview round was a pharmacy database schema, not a library; only its online assessment listed
  "Book store management".
