# LRU / LFU Cache: what interviewers actually ask (research for lru-workbench.html, 2026-09-26/27)

Method. The session's WebSearch budget (200 of 200) was used up before part B began. Evidence comes from:
**1st** = a candidate's own post, fetched and read by the reviewer (LeetCode Discuss posts through leetcode.com's
GraphQL endpoint by post id; GeeksforGeeks pages directly). **tag** = LeetCode company tags from
https://github.com/liquidslr/leetcode-company-wise-problems (data "as of June 2025", repo pushed 2026-08).
**land** = the shared landscape notes in this folder (`landscape-bigtech.json`, `landscape-india-sea.md`,
`landscape-ailabs.md`), not re-fetched. Disclosure: to *find* the LeetCode posts I ran about 13 keyword queries
against LeetCode's own discuss listing (GraphQL `categoryTopicList`) before I saw that sibling reviews treated a
site's own search as off-limits once the cap was hit; I stopped when pointed to the landscape files.
Scope: his targets are Indian product companies, FAANG / GCC offices in India, and UK / Singapore firms hiring
from India. AI-lab rows are kept for completeness and marked.

"FU n" = follow-up n on page 05 after this review. "core" = pages 01-04 (the LeetCode 146 answer plus the lock).

## Follow-ups, twists and variants

| question / variant | company | year | URL | where the page answers it |
|---|---|---|---|---|
| LRU Cache (LeetCode 146) in a coding round | Meta (E4 onsite) | 2024 | https://leetcode.com/discuss/interview-experience/5987903/ (1st) | core |
| LRU Cache in the phone screen | Meta (E5; and another phone screen) | 2024 | https://leetcode.com/discuss/interview-experience/4861970/ ; https://leetcode.com/discuss/interview-question/5092015/ (1st) | core |
| "Variation of LRU Cache", onsite coding | Google (L4, Bangalore) | 2024 | https://leetcode.com/discuss/interview-experience/5133247/ (1st) | core |
| LRU Cache, onsite | Amazon (L6; SDE-2) | 2024; 2023 | https://leetcode.com/discuss/interview-experience/5514550/ ; https://leetcode.com/discuss/interview-experience/4166624/ (1st) | core |
| LRU cache with TTL | Amazon (SDE-2 VO) | 2024 | https://leetcode.com/discuss/interview-question/4979681/ (1st) | FU8 |
| LRU in a coding round; "Design LRU Cache" as the LLD round | Microsoft (10+ YOE; SDE-2) | 2024 | https://leetcode.com/discuss/interview-experience/6110952/ ; https://leetcode.com/discuss/interview-experience/4745798/ (1st) | core |
| LLD "Design LRU", every step questioned by a 25-year veteran | Microsoft (L64, Hyderabad) | 2024 | https://leetcode.com/discuss/interview-experience/5618345/ (1st) | core, FU6 (why O(1)) |
| Working LRU, then LFU "with minimal changes" | Microsoft (L61, Noida) | 2024 | https://leetcode.com/discuss/interview-experience/5317286/ (1st) | FU1 |
| Distributed cache LLD, extend to LRU and LFU; running LFU with generic key/value | Microsoft (SDE-2, Hyderabad) | 2024 | https://leetcode.com/discuss/interview-experience/5299198/ (1st) | FU1 |
| "Mem cache with LFU, LRU and custom policy"; policy as an interface | Microsoft (L61) | 2024 | https://leetcode.com/discuss/interview-experience/5259713/ (1st) | FU2, FU1 |
| LFU (LeetCode 460) as the LLD round; LRU+LFU cache LLD; running LFU code | Microsoft (SDE-2; L62; SDE-2 Hyderabad) | 2024 | https://leetcode.com/discuss/interview-experience/5250071/ ; .../5155438/ ; .../5020134/ (1st) | FU1 |
| Generic cache class, then extend it into LRU | Microsoft (L62, Hyderabad) | 2024 | https://leetcode.com/discuss/interview-experience/5102651/ (1st) | move 3, FU2 |
| LRU and LFU in one DSA round | ThoughtSpot (MTS4) | 2024 | https://leetcode.com/discuss/interview-experience/5253431/ (1st) | core, FU1 |
| LFU exactly as LeetCode 460, about 20 minutes to code it | Coupang (L6 Staff) | 2024 | https://leetcode.com/discuss/interview-experience/5540593/ (1st) | FU1 |
| LFU Cache (DSA round); LRU "extensible to different policies" | Salesforce (SMTS) | 2024 | https://leetcode.com/discuss/interview-question/5817444/ ; https://leetcode.com/discuss/interview-experience/5444975/ (1st) | FU1, FU2 |
| "LFU cache like thing, try making it thread safe" | Confluent (onsite) | 2024 | https://leetcode.com/discuss/interview-question/6155819/ (1st) | FU1, FU3 |
| Phone screen: "store key-value entries within a time-based interval. Slight variation to LRU Cache"; "Modified LRU Cache" | Confluent (SSE; London) | 2024 | https://leetcode.com/discuss/interview-experience/5047273/ ; https://leetcode.com/discuss/interview-experience/5559597/ (1st) | FU9, FU8 |
| Screening: cache with time-based eviction; get(), put(), getAverage() | Confluent (SSE) | 2024 | https://leetcode.com/discuss/interview-experience/5746976/ ; https://leetcode.com/discuss/interview-experience/6125401/ (1st) | FU9 (added) |
| "Windowed Key-Value Map": average over unexpired entries | Confluent | 2023-25 | https://leetcode.com/discuss/post/4188001/ + fastprep (land) | FU9 |
| LLD: LFU cache with several eviction policies and a cache manager | Amazon (SDE-1) | 2024 | https://leetcode.com/discuss/interview-experience/6139812/ (1st) | FU1, FU2 |
| LFU caching logic with classes and interfaces | Walmart (SDE-3) | 2024 | https://leetcode.com/discuss/interview-question/6146111/ (1st) | FU1 |
| Pseudo-code for LRU, LFU and FIFO; "how would you implement TTL"; distributed cache across pods | Walmart (SE-3, Bengaluru) | 2025 | https://leetcode.com/discuss/interview-experience/6492160/ (1st) | FU2, FU8, FU14 |
| HLD distributed cache, then LRU implementation code | Walmart (SSE AdTech) | 2024 | https://leetcode.com/discuss/interview-experience/4553107/ (1st) | core, FU14 |
| In-memory cache: get, put, put with TTL; LRU and LFU strategies | Dream11 (SDE-3) | 2024 | https://leetcode.com/discuss/interview-question/5708308/ (1st) | FU2, FU8 |
| Cache whose eviction policy is selected at run time (LRU, time-based) | Flipkart (SDE-2 machine coding) | 2024 | https://leetcode.com/discuss/interview-experience/5426325/ (1st) | FU2 (added) |
| Cache management with time-based and data-based eviction policies | Flipkart (SDE-2 machine coding) | 2024 | https://leetcode.com/discuss/interview-experience/5656345/ (1st) | FU2, FU8 |
| "flip-cache" library: store and eviction policy chosen at initialization; concurrent requests; hit-ratio metric | Flipkart (SDE-3 machine coding) | 2024 | https://leetcode.com/discuss/interview-question/5572225/ (1st) | FU2, FU3, FU12 |
| Three-level cache L1/L2/L3: capacity, read time, write time, evictions; average read/write time over last N | Flipkart (SDE-2) | 2025 | https://www.geeksforgeeks.org/interview-experiences/flipkart-interview-experience-for-sde-2-3-5-years-experienced/ (1st) | FU15 (added) |
| N-level cache L1..Ln: read copies up, write stops at a level with the same value; STAT = usage + averages of last 5 | PhonePe (SE, Pune; 24-hour take-home + review of concurrency) | 2024 | https://leetcode.com/discuss/interview-experience/6029482/ (1st) | FU15 (added) |
| In-memory cache: LRU, read-through backing store, TTL after last access, write policy; bonus refresh / async load | PhonePe (SDE-3 machine coding) | 2024 | https://leetcode.com/discuss/interview-question/5996786/ (1st) | FU5, FU8, FU14 |
| L1 per-user LRU (5) + L2 global LFU (20) + primary store; hits per level | Cleartrip / Flipkart (SDE-1 machine coding) | 2025 | https://leetcode.com/discuss/interview-question/6289757/ (1st) | FU15, FU12 |
| LRU where an object dies S seconds after its last get or set; then "make it thread-safe" | TikTok (phone screen) | 2024 | https://leetcode.com/discuss/interview-question/5237638/ (1st) | FU8 (expire-after-access, tail sweep), FU3 |
| Two-part LRU: untouched keys vs keys touched at least once (n/3 and 2n/3) | Nutanix (MTS-2) | 2024 | https://leetcode.com/discuss/interview-experience/6144324/ (1st) | FU11 (segmented LRU) |
| Thread-safe cache over two HashMaps with a TTL | EPAM (Senior) | 2024 | https://leetcode.com/discuss/interview-experience/6203677/ (1st) | FU8, FU3 |
| LRU as the LLD / DSA round | Tata 1mg (SDE-2); PolicyBazaar (SDE-2); Freecharge (Senior SDE); TrueFoundry (SSE); Freshworks (Lead) | 2023-25 | https://leetcode.com/discuss/interview-experience/4186755/ ; .../6325111/ ; .../5669624/ ; .../5872739/ ; .../5256522/ (1st) | core |
| LRU with tests (VP Super Day); LLD of LRU | Goldman Sachs | 2024 | https://leetcode.com/discuss/interview-question/5309405/ ; https://leetcode.com/discuss/interview-experience/6131599/ (1st) | core, FailureTests |
| Evict by a rank from a mocked API, LRU among equal rank; hit and miss counters | LinkedIn | 2026 | https://leetcode.com/discuss/post/7479450/ (land) | FU2 (one sentence), FU12 |
| Refactor a working LRU into pluggable eviction policies | Bloomberg (LLD) | 2023 | https://leetcode.com/discuss/post/3606527/ (land) | FU2 |
| Thread-safe LRU/LFU | Oracle; MakeMyTrip | 2025; 2024 | https://leetcode.com/discuss/post/7327102/ ; https://leetcode.com/discuss/post/4700672/ (land) | FU3 |
| Blocking keyed cache: readers wait for an in-flight load | Databricks | 2026 | fastprep (land) | FU7, FU5 (tickets) |
| Expiring counter put_element / get_element_count / get_total_elements; timestamps increase, so a queue, not a heap | Uber (L5A) | 2025 | https://leetcode.com/discuss/post/7043175/ (land) | FU9 (one sentence) |
| LRU memo: fix a buggy key, then durability with a write-ahead log, restoring recency order | Anthropic (AI lab, outside his target list) | 2025-26 | inbyte / prachub / darkinterview (land, aggregators) | FU13 (kept short) |
| LRU Cache company tag (no first-hand report found) | OpenAI (AI lab) | 2025 data | liquidslr repo (tag) | core |

## How often (LeetCode company tags, 2025 data)

LRU Cache (146), rank within the company's list: Amazon 2 of 2011 (8 in the last three months), Apple 1, Oracle 1,
TikTok 1 (also 1 in the last three months), ByteDance 1, Snap 1, ServiceNow 1, Nvidia 2, Walmart Labs 2, Shopee 2 of 7,
PayPal 4, Microsoft 6, Goldman Sachs 8, Uber 13, Bloomberg 25, Meta 27, Google 40 (42 in three months), PhonePe 24 of 95,
Swiggy 32 of 36, Flipkart 95 of 108, OpenAI 17 of 17. LFU Cache (460): Salesforce 4 of 193, Oracle 14, Zomato 14 of 30,
Citadel 19, Walmart Labs 43, Amazon 104, Microsoft 180.

## Asked, but not added
- Browser-history cache (Bloomberg 2023) and the token-TTL "authentication manager" (LeetCode 1797; Microsoft, Apple,
  Oracle): different problems.
- LFU where an access changes a score field (Google): FU2's rank sentence covers the shape.
- A key-value store with transactions (Rippling 2024): the inmem-db page.

## No evidence found (the page keeps these, but does not claim they are commonly asked)
Bounding by bytes (FU10), the admission door / W-TinyLFU (FU11, apart from Nutanix's two-part LRU), the LinkedHashMap
question (FU17; one 2025 post asks whether an ordered dict is allowed: https://leetcode.com/discuss/interview-question/6273201/).
Redis-style sampled eviction had no evidence and three false statements; its card was cut.

## Technical sources checked
Redis eviction docs (default policy `noeviction`; `maxmemory-samples 5`; 10 is close to true LRU):
https://redis.io/docs/latest/develop/reference/eviction/ . Caffeine `FrequencySketch.ensureCapacity`: one `long` (16
four-bit counters) per entry of capacity, so about 1 MB for 100,000 entries:
https://github.com/ben-manes/caffeine/blob/master/caffeine/src/main/java/com/github/benmanes/caffeine/cache/FrequencySketch.java .
Caffeine design (read buffers striped by a thread hash, lossy; write-order queue for expireAfterWrite; timer wheel for
variable expiry): https://github.com/ben-manes/caffeine/wiki/Design . Guava `CacheBuilder.maximumSize` (each segment
limits itself to about maximumSize / concurrencyLevel; "Prefer Caffeine"):
https://guava.dev/releases/snapshot-jre/api/docs/com/google/common/cache/CacheBuilder.html . `LinkedHashMap`
(`removeEldestEntry` receives the eldest entry; in access order `get` is a structural modification):
https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/LinkedHashMap.html . Facebook, "Scaling
Memcache at Facebook", NSDI 2013, section 3.2.1 (leases prevent stale sets; a delete invalidates the lease):
https://www.usenix.org/system/files/conference/nsdi13/nsdi13-final170_update.pdf .
