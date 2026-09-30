# In-memory Database: what interviewers actually ask (research for the 2026-09-26 review)

Sources: my own fetches (hellointerview, workat.tech, prachub, sundeepteki, linkjob.ai; LeetCode Discuss and
Medium returned 403, so LeetCode rows marked "snippet" come from search-result text), plus the shared landscape
files `landscape-ailabs.md`, `landscape-india-sea.md` and `landscape-bigtech.json` (first-hand LeetCode posts read
through GraphQL by that pass). The session's web-search budget ran out part way through the pass.

Card numbers below are the page's follow-up cards after this review (1 foreign key ... 16 patterns/SOLID).

| question / variant | company | year | URL | where the page answers it |
|---|---|---|---|---|
| SQL-like tables: create **and delete** tables, typed columns (string <= 20 chars, int -1024..1024), required columns, insert, print all, filter by a column | Razorpay (machine coding) | 2020-21, 2024 | https://leetcode.com/discuss/interview-question/949850/in-memory-sql-like-database-ood-machine-coding/ (snippet), https://leetcode.com/discuss/post/4750617/ | Main: `createTable` / `dropTable` (added), `TypeRule`, `NotNullRule`, `CheckRule`; card 6 names the three constraints (added); card 7 filters by column; card 16: a new column type is one enum constant (added) |
| "Design an in-memory RDBMS" | not named | 2021 | https://leetcode.com/discuss/interview-question/1051013/Design-an-in-memory-RDBMS/ (title only) | the whole page |
| API mini-SQL: `create_table / insert / select(columns, where, order_by)`, compound WHERE, **ORDER BY multi-column asc/desc**, delete via **tombstones** + LSM talk | OpenAI | 2024 | https://leetcode.com/discuss/post/5984554/ (via landscape-ailabs) | card 7 (where + index), **card 8 ORDER BY + column list (new, `OrderBy`, test 14)**, card 4 tombstone + LSM compaction (added) |
| 5-part table module in 2 hours; joins as parts 4-5 | Glean | 2025 | landscape-ailabs `api-sql-table-db` | card 13 (nested loop vs hash join), card 8 |
| KV store with typed attributes, `search(attrKey, attrValue)` sorted, thread-safe (SDE II/III machine coding) | workat.tech list (used by Indian product cos.) | 2024-26 | https://workat.tech/machine-coding/practice/design-key-value-store-6gz6cq124k65/ | TypeRule, card 7 (index probe = search), card 2 (threads). Not built: type learned from the first value (the page fixes the schema up front) |
| BitDB: file persistence + BEGIN/COMMIT/ROLLBACK + locks | Gojek | 2024 | https://leetcode.com/discuss/post/5129060/ (landscape-india-sea) | card 12 (commit log, fixed), card 10, moves 4/7 |
| KV get/set/delete -> begin/commit/rollback -> nested; "multi-threaded operations needed to pass senior" | Rippling | 2023-25 | https://leetcode.com/discuss/post/5375106/, https://leetcode.com/discuss/post/5071351/ (landscape-bigtech) | card 2 (race), card 10 (savepoint marks = nested rollback). Nested BEGIN/COMMIT API: separate page |
| Transactional KV, nested BEGIN/ROLLBACK/COMMIT, "NO TRANSACTION" | Applied Intuition (tech screen) | 2025-26 | https://prachub.com/coding-questions/design-a-transactional-in-memory-keyvalue-store | card 10 (partial); separate page |
| Transactional KV parts 1-3; part 3 = per-thread private layers, visible only after outermost commit | Snowflake (tech screen) | 2025-26 | https://prachub.com/coding-questions/design-transactional-in-memory-key-value-store | card 10, card 5 (partial: locking model, not private layers); separate page |
| In-memory DB with nested transactions, abort restores | Lyft (Staff/Senior), Anchorage Digital, Coinbase, Uber | 2026 | https://www.hellointerview.com/community/questions/memory-database-transactions/cm6uaoy1y00003b6la4jojd7s | card 10; value counts (Lyft) only as committed `CityCount`; separate page |
| CodeSignal 4 levels: set/get/delete field -> scan / scan_by_prefix -> timestamped ops + TTL -> backup/restore | Anthropic OA; xAI onsite; Coinbase | 2023-26 | https://www.linkjob.ai/interview-questions/anthropic-software-engineer-interview/ , https://www.sundeepteki.org/advice/anthropic-codesignal-assessment-guide , https://leetcode.com/discuss/post/5911625/ | card 15 (TTL sweeper, injected clock) only; separate page |
| Versioned in-memory DB: TTL-aware writes, tombstones, prefix scans, historical reads | Anthropic (onsite) | 2026 | https://prachub.com/companies/anthropic/categories/coding-and-algorithms | card 4 (versions, tombstones, snapshot reads) partial; separate page |
| Durable KV: serialize/restore, WAL, fsync, checksums, torn writes | OpenAI; Baseten | 2025-26 | landscape-ailabs `durable-kv-store` | card 12: log written before the unlock, failed append fails COMMIT (fixed); length + checksum framing and snapshots (added) |
| Read pickleDB, split its god-class, add TTL | Postman | 2024 | https://leetcode.com/discuss/post/5502573/ | moves 1-3 (classes by state), card 15 |

No evidence found for (so not added): OR in where-clauses, unique secondary columns, LIMIT/pagination.
