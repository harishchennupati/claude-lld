# Ride sharing: what interviewers ask (review pass 2026-09-27)

## How this was gathered

The web-search budget was spent, so no WebSearch was used. The evidence is the three landscape files
(`research/landscape-{india-sea,bigtech,ailabs}.{md,json}`, grepped for ride / cab / taxi / driver / pool / surge).
All ten LeetCode posts they cite were then read in full through LeetCode's public GraphQL API
(`ugcArticleDiscussionArticle(topicId)`). Target companies only; the AI-lab file has no ride-sharing variant.

## Evidence, mapped to the page

| question | company | year | URL | where the page answers it |
|---|---|---|---|---|
| "Design a Premium Cab Hailing Service for Uber": cab allocation logic, clean code, running solution with multithreading scenarios (L4 LLD round, in person, Bengaluru) | Uber | 2026 | https://leetcode.com/discuss/post/8476675/ | Core: move 4 and FU 1 (race), FU 12 (runs in parallel), FU 2 (a driver never holds two offers), FU 11 (premium floor in `RatedNearest`) |
| Passengers request rides, drivers accept and fulfil them, passengers cancel, pickup and destination, fare by distance, ride type and time (SMTS LLD round) | Salesforce | 2025 | https://leetcode.com/discuss/post/7398700/ | `requestRide`; FU 2 (driver accepts or declines: `OfferDesk`); FU 5 (cancellation fee); `NormalPricing` (base + km + minutes per tier); FU 6 (surge) |
| DB schema for Uber; "driver should see which requests he accepted and declined"; then components and caching; last follow-up: concurrency at the driver's end | Zepto | 2024 | https://leetcode.com/discuss/post/5703566/ | FU 7 (tables, with an `offer` table for the accepted and declined screen); FU 2 (`historyOf`, accept against expiry decided by one CAS, a late tap cannot take a newer offer); test 16 |
| Ride sharing: show the nearest five drivers; allocate rides first come first served; keep ride location history with the exact route | Nykaa | 2025 | https://leetcode.com/discuss/post/7406725/ | NEW FU 9: `RideService.nearestFree(pickup, type, k)` (Main), FCFS explained plus a pointer to the food-delivery waiting line, `RouteLog` (Extensions); test 18 |
| Car-pool: `offer_ride(vehicle, seats, origin, destination, start, duration)`, `select_ride(origin, destination, seats, preference)` with earliest ending, lowest duration, most vacant or preferred vehicle; rides offered and taken per user | Swiggy / MakeMyTrip (compiled post) | 2026 | https://leetcode.com/discuss/post/7484820/ | NEW FU 8: `CarPool` (one open ride per vehicle via putIfAbsent, seats by CAS, preference enum); test 17 |
| Implement `calculateETA` by vehicle type; which design patterns | Paytm | 2025 | https://leetcode.com/discuss/post/7113665/ | FU 10: `EtaByVehicle` (one RouteProvider per tier in an EnumMap) |
| Uber-like system: User, Driver, Ride, Payment, Location, Vehicle; DB normalisation and scalability; HM round: Factory (why and when), Open/Closed | Arcesium | 2025 | https://leetcode.com/discuss/post/7178192/ | Move 1 (nouns); FU 7 (normalised tables); FU 17 (Factory "not yet"); move 11 (O) |
| "Design Cab booking service application like Ola, Uber" (LLD round) | Razorpay | 2024 | https://leetcode.com/discuss/post/6095033/ | The whole page |
| "Design a Ride matching Service" (LLD round) | Amazon | 2026 | https://leetcode.com/discuss/post/7599995/ | Moves 3 to 5, FU 1, FU 11 |
| "Design a service to find a rider for a quick commerce app" (bar raiser, LLD) | Amazon | 2026 | https://leetcode.com/discuss/post/7576550/ | Same matching core; the order waiting line is on the food-delivery page |

## The coordinator's topics

| topic | evidence | where |
|---|---|---|
| driver matching: nearest, then rating | indirect (Uber 2026 premium allocation); no first-hand post says "then rating" | `NearestDriver`; `RatedNearest` in FU 11 |
| a driver offered to two riders at once | Uber 2026, Zepto 2024 | FU 1 (CAS), FU 2 (offer = reserve; 30 riders, 3 cars, 3 offers) |
| ride states and cancellation fees | Salesforce 2025 | move 6, FU 5 |
| fare rules and surge | Salesforce 2025 | `NormalPricing`, FU 6, FU 14 |
| shared rides / pooling | Swiggy/MMT 2026 (car-pool) | FU 8; FU 15 (UberPool fare split, no first-hand post) |
| ratings | adjacent only: Flipkart P2P delivery "rate the driver" (landscape-india-sea) | FU 11 |

Not added (no evidence): batched dispatch, two-way ratings, driver-side cancellation.
