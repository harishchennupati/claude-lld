# Train and flight seat booking (IRCTC, Cleartrip): what interviewers actually ask (research, 2026-09-27)

How this was gathered: the landscape entry `ticket-booking-train-flight` in `research/landscape-india-sea.md` / `.json`
(8 reports), then LeetCode Discuss read in full through its public GraphQL API (searches: IRCTC, train booking, railway
reservation, train ticket, flight booking, airline booking, bus booking, ticket booking system; every post below was
opened and read). No web searches were used. Every row is a first-hand report unless it says otherwise.
FU n = follow-up card n on page 05 of `train-booking-workbench.html`; "core" = Main.java and pages 01-03.

| question or level | company | year | URL | where the page answers it |
|---|---|---|---|---|
| IRCTC LLD: search by train number and by source, destination and date; seats available for train + source + destination + date; book, handling concurrent requests "in a fair manner"; a seat reused per segment (S1 booked station 1 to 2, sold again from station 3); cancel. Interviewer focused on the DB design; the candidate added a Segment entity | Zepto (SDE-2) | 2024 | https://leetcode.com/discuss/post/5724806/ | core (Berth bitmap, TrainRun.book); FU 1 (fair lock); FU 2 (search, route by number); FU 3 (tables); FU 4 (segments); FU 7 (cancel); FU 8 (availability) |
| Train ticket booking: entities (Train, Coach, Seat, Booking, User, Search), seat allocation, concurrency control, waitlist logic, basic HLD | Swiggy (SDE-2) | 2025 | https://leetcode.com/discuss/post/7383296/ | pages 01-03; FU 1; FU 6 (RAC and waitlist); FU 9 (seat allocation rule) |
| Railway reservation: trains between stations, seat availability, via details (the route); the ticket with seat allocation is generated after a successful payment; store train details, fares, PNR number | Walmart | 2024 | https://leetcode.com/discuss/post/5780635/ | FU 2 (search; `train(number)` gives the route); FU 8; FU 11 (the ticket exists only once BOOKED); FU 12 (fares); FU 3 (pnr table) |
| Railway reservation (IRCTC): entities User, Train, Station, Route, Seat, Booking; class diagram and relationships; pessimistic vs optimistic locking; implement the core booking logic | InMobi (SDE 2) | 2025 | https://leetcode.com/discuss/post/7422653/ | page 03; core `TrainRun.book`; FU 1 (pessimistic); FU 3 (both, in SQL) |
| IRCTC ticket booking: HLD, LLD and "algorithms for figuring out ticket booking" | Navi (SDE-2) | 2023 | https://leetcode.com/discuss/post/4572315/ | moves 1, 5, 6 (the per-segment bitmap and the booking order) |
| Design IRCTC: the database schema, the query behind each API, concurrency | MakeMyTrip (SSE2) | 2024 | https://leetcode.com/discuss/post/4700672/ | FU 3; FU 2 (the search query); FU 1 |
| Design IRCTC (director's round) | MakeMyTrip (SSE-2) | 2024 | https://leetcode.com/discuss/post/6203468/ | whole page |
| Flight inventory machine coding (2 h): `AddUser(userId, name, funds)`, `SearchFlight(from, to, departDate, paxCount)`, `Book(userId, flightNumber, departDate, fareType, seats)` all seats in one fare type and enough funds or a proper error, `Cancel(userId, bookingId)` restores seats and funds, `GetUserBooking(userId)` booked and cancelled; bonus `UpdateFlight(...)` charging the difference, `SearchFlightByPreferedAirline(..., sortBy, sortType)`, race conditions in booking | Cleartrip (SDE-1) | 2024 | https://leetcode.com/discuss/post/4973782/ , https://leetcode.com/discuss/post/5046642/ | FU 5 (`FlightDesk`: search, book, cancel, bookings, preferred airline); FU 10 (`change`, two locks in key order) |
| The same flight-inventory problem as a machine-coding round | Cleartrip | 2025 | https://leetcode.com/discuss/post/7052339/ | FU 5, FU 10 |
| Airline booking like Cleartrip: requirements, all the tables (the candidate forgot the payments table), concurrent seat bookings with locks | Flipkart (SDE 2) | 2025 | https://leetcode.com/discuss/post/7560534/ | FU 3 (payment table with a unique idempotency key); FU 1; FU 5 |
| Train booking: book between stations, find trains, assign seats, routes, sell a seat that is vacant after a passenger's station; DB schema and SQL for each use case | Adobe (CS-1) | 2025 | https://leetcode.com/discuss/post/6924065/ | FU 4; FU 2; FU 3 |
| Thousands of stations, trains passing through several: how to query which trains pass a station | Adobe (CS-1) | 2024 | https://leetcode.com/discuss/post/6136507/ | FU 2 (the station index: station to train to stop number) |
| IRCTC LLD focused on searching trains between two stations on a date | Salesforce | 2024 | https://leetcode.com/discuss/post/5523721/ | FU 2 |
| Design IRCTC, search and booking only | Tekion (SSE) | 2024 | https://leetcode.com/discuss/post/5636708/ | FU 2; core |
| Where would you use Kafka in IRCTC? Then `searchTrains(startLocation, endLocation, Date)`: DB design and the search query | Goldman Sachs (Analyst) | 2024 | https://leetcode.com/discuss/post/4841391/ (also in the compiled post 5073339) | FU 13 (a queue per run, one partition per run); FU 2 (the SQL self-join) |
| Data model and algorithm for trains between two stations from a start date, and seat availability by class (3A, 2A) | Google (team match, Hyderabad, L3) | 2024 | https://leetcode.com/discuss/post/5565396/ | FU 2; FU 8 |
| Train booking like IRCTC: search journeys, book seats with the emphasis on concurrency, cancel | Tesco (SDE3) | 2024 | https://leetcode.com/discuss/post/5306198/ | FU 2; FU 1; FU 7 |
| IRCTC seat booking, strongly consistent; the catch: a seat booked 1 to 3 and 5 to 10 must show in a search for 3 to 4; APIs and schema | Kotak (SDE 2) | 2024 | https://leetcode.com/discuss/post/5016353/ | FU 4 (this exact question); FU 3 |
| DB schema for IRCTC and the queries to find seats and book | Zepto (SDE 2, in a multi-company post) | 2024 | https://leetcode.com/discuss/post/5761804/ | FU 3; FU 2 |
| Flight management machine coding: flights with economy, business and first seats; search, book, cancel; a passenger's bookings; readability and concurrency | PhonePe (SDE-2) | 2024 | https://leetcode.com/discuss/post/6093920/ (also 5761804) | FU 5 |
| Flight booking system: functional requirements, classes, DB schema, API contracts | Flipkart (SDE-2) | 2024 | https://leetcode.com/discuss/post/5471724/ | FU 5; FU 3 |
| Airline management system, LLD and HLD, API contracts and tables | Flipkart (SDE3) | 2024 | https://leetcode.com/discuss/post/6145422/ | FU 5; FU 3 |
| Flight booking: the first 120 users book one seat free; guarantee exactly 120 under concurrent requests | Intuit (SSE) | 2024 | https://leetcode.com/discuss/post/4838618/ | FU 1, one sentence: claim the counter inside the same lock, or `UPDATE promo SET used = used + 1 WHERE used < 120` (no code) |
| Railway reservation console app (3 h): berth preference; 63 confirmed berths, 18 RAC on side lowers, 10 waitlist; lower berths for passengers over 60 and ladies with children; no berth for children under 5; a cancel confirms the first RAC and moves the first waitlisted to RAC; print booked and available tickets | Zoho (MTS, Chennai) | 2024 | https://leetcode.com/discuss/post/4531089/ | FU 6 (the cascade, test 4); FU 9 (seniors on lower berths). Not answered: children under five without a berth, the ladies-with-children rule (each is one more line in the berth chooser) |
| Design the database schema of IRCTC | Junglee Games | 2024 | https://leetcode.com/discuss/post/4716465/ | FU 3 |
| Bus booking app: a SearchBus(source, destination, date) API and the DB schema | MakeMyTrip (SSE-1) | 2024 | https://leetcode.com/discuss/post/6171093/ | FU 2 (the same search); FU 3 |
| Design a flight booking system (system design) | DE Shaw (Lead) | 2024 | https://leetcode.com/discuss/post/5578112/ | FU 5 (the LLD side only) |
| Scenario questions on a given flight booking HLD | Agoda (SSE, Bangkok) | 2024 | https://leetcode.com/discuss/post/5290917/ | not specific enough to map; FU 5 and FU 10 are the LLD side |
| Landscape summary: fair handling of concurrent bookings (pessimistic vs optimistic); segment-wise seat reuse; waitlist and promotion on cancel; PNR / ticket generation after payment; DB schema incl. payments | 8 companies (aggregated) | 2023-25 | research/landscape-india-sea.md, id `ticket-booking-train-flight` | FU 1, FU 4, FU 6, FU 11, FU 3 |

## Follow-ups ranked by how often these companies ask them (the page's order)
1. The race for the last berth, and pessimistic vs optimistic locking (Zepto, Swiggy, InMobi, MakeMyTrip, Flipkart, Tesco, PhonePe, Kotak, Cleartrip, Intuit).
2. Search between two stations on a date (Zepto, Walmart, Salesforce, Tekion, Goldman Sachs, Google, Tesco, Adobe x2, MakeMyTrip bus).
3. Tables, queries and locking in the database (Zepto x2, MakeMyTrip x2, Flipkart x3, Adobe, Goldman Sachs, Junglee, Kotak, InMobi).
4. A berth sold again per segment (Zepto, Kotak, Adobe, Navi).
5. The flight version (Cleartrip x3, PhonePe, Flipkart x3, DE Shaw, Agoda).
6. RAC and the waitlist moving up on a cancel (Swiggy, Zoho, landscape).
7-13. Cancel and refunds; availability at scale; a family together; changing a flight (Cleartrip bonus); the ticket after payment (Walmart); fares (Walmart, Cleartrip fare types); the Tatkal rush and Kafka (Goldman Sachs).

## Checked and left out
- Overbooking (airlines selling more seats than exist): named in the build guidance, but no report asks it; not added.
- Tatkal quota mechanics (a pool that opens at 10:00): no report asks it directly; Tatkal appears as a fare rule (FU 12) and as the load spike (FU 13), and a quota is named in move 12.
- Chart preparation (waitlisted e-tickets cancelled and refunded): no report asks it; named once in move 12.
- Amounts in the refund rule and the Tatkal floor and cap are illustrative; only their shape is claimed (the page says so).
- Uber's "assign trains to platforms" (research/landscape-india-sea.md, `train-platform`) is a different problem; not covered here.
