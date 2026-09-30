# Food Delivery (slug `food-delivery`): what interviewers actually ask

Research done 2026-09-26/27. The session's WebSearch budget was used up by other agents, so the evidence comes from
(a) pages fetched directly: problem statements that candidates published on GitHub, and the FoodKart statement itself
(a public Google Doc), and (b) the coordinator's landscape files (`landscape-india-sea.md/.json`,
`landscape-bigtech.json`), which cite first-hand LeetCode Discuss posts. LeetCode returns HTTP 403 to direct fetches,
so those rows rely on the landscape agent's reading of the posts (marked "via landscape").

Target lens (his scope): Indian product companies and startups, FAANG and GCCs in India, and some UK / Singapore
companies hiring from India. Grab, Shopee and TikTok in Singapore showed no machine-coding evidence for this system
(landscape: their loops are DSA + HLD).

| question / variant | company | year | URL | where the page answers it |
|---|---|---|---|---|
| Restaurants deliver to a list of pincodes; show the serviceable ones (deliver here AND have stock) sorted by rating or by price | Flipkart (FoodKart machine coding, 90 min) | 2022 | [statement](https://docs.google.com/document/d/1Bmkz9omByHqVvwU45cvkBRSwJAPKw9yaDsRlEnCg_lg), linked from [stym06/food-kart](https://github.com/stym06/food-kart) | card 17 (`Catalog.find`, Comparator per sort order); test 18 |
| Rate a restaurant 1 to 5 with or without a comment; its rating is the average of all ratings | Flipkart (FoodKart) | 2022 | same | card 17 (`Catalog.rate`: running sum + count in tenths; delivered orders only, once each); test 18 |
| `update_quantity` and `update_location` for a restaurant (onboarding and menu upkeep) | Flipkart (FoodKart) | 2022 | same | card 17 text (`setStock`, `onboard` again); `Restaurant.put / setStock / setOpen` in Main.java |
| One restaurant per order, quantity can be more than one | Flipkart (FoodKart) | 2022 | same | page 01 ask table row 1; `Cart` bound to one restaurant (move 1) |
| The customer names dishes, not a restaurant: the system picks one by a strategy (lowest cost, or highest rating) | Intuit; Flipkart (x3) | 2024; 2025 | [Intuit statement](https://github.com/saurabhswaraj/intuit-food-ordering-system), [Zwigato (com.intuit)](https://github.com/Gauravm017/Zwigato); LC [6614846](https://leetcode.com/discuss/post/6614846/) [6667785](https://leetcode.com/discuss/post/6667785/) [6874431](https://leetcode.com/discuss/post/6874431/) via landscape | card 18 (`KitchenPicker.cheapest / bestRated`); tests 18-19 |
| Each restaurant has a maximum processing capacity, released when the item is dispatched; "concurrency must be demoed" | Intuit; Flipkart | 2024; 2025 | same | card 18 (a Semaphore of item permits per kitchen, released at PICKED_UP or when the order dies); test 19: 12 threads |
| Commands arrive out of order and must be processed in timestamp order | Flipkart (FoodKart 2025) | 2025 | LC 6614846 / 6667785 / 6874431 via landscape | card 18 (`CommandReplay`: PriorityQueue by time, ties in arrival order, clock moved per command); test 19 |
| An accepted order cannot be cancelled | Flipkart | 2025 | same | card 9 (a stricter `CancellationPolicy` that throws past PLACED); test 5b |
| Auto-assign each order to an available delivery partner; queue orders when none is free; thread safety | Flipkart (P2P delivery, "Flipkart Minutes"); Zepto | 2025, 2026; 2024 | LC [6363567](https://leetcode.com/discuss/post/6363567/) [7588244](https://leetcode.com/discuss/post/7588244/) [5710176](https://leetcode.com/discuss/post/5710176/) via landscape | moves 4-7, card 10; tests 7, 11, 12, 13, 14 |
| Cancel allowed only before pick-up | Flipkart | 2025, 2026 | same | transition table (move 6), card 9; test 6 |
| Notify through a mocked email/SMS vendor | Flipkart | 2025, 2026 | same | Observer (move 3), `publish` after the unlock in try/catch; test 8 |
| Rate the driver; top-drivers dashboard | Flipkart | 2025, 2026 | same | **not added**: the same running average keyed by rider id; note that `handBack` clears the order's rider id, so the order would have to keep it for a rating |
| Three closest dashers to a restaurant, ties broken by rating | DoorDash | 2024 (compiled from LeetCode Discuss) | [AnudeepBalla10/DoorDash](https://github.com/AnudeepBalla10/DoorDash/blob/main/CodingChallenges/Closest%20Drivers%20to%20Restaurant.md) | `NearestFree` behind `AssignmentRule` (move 3, card 10); the tie-break is one more comparator (not coded) |
| Discounts / offers at checkout | Swiggy | 2025 | LC [7069404](https://leetcode.com/discuss/post/7069404/) via landscape | card 1 (percent coupon capped by a Decorator, flat coupon); test 3 |
| Subscription vs non-subscription customers | Walmart (grocery) | 2024, 2025 | LC [5066843](https://leetcode.com/discuss/post/5066843/) [6782621](https://leetcode.com/discuss/post/6782621/) via landscape | `MembershipWaiver` (move 11 row O, move 12 picture, ExtDemo); no card of its own |
| Add partial refunds to an existing refund codebase | DoorDash (AI Code Craft) | 2025 | LC [7401147](https://leetcode.com/discuss/post/7401147/) via landscape | card 9 (fee kept, rest refunded), card 5 (a refund is written down as owed and swept); test 15 |
| Search restaurants by name or city, menu by cuisine; cart; cancel; coupons; bill; payment modes; status | Uber Eats-style practice statement | 2022 | [arpitkhurana22/UberEats-LLD](https://github.com/arpitkhurana22/UberEats-LLD) | search by dish within a pincode (card 17); name/cuisine search not coded (the same index, keyed by another field) |
| Browse restaurants, manage menus, prices and availability, agents accept orders, tracking, payment methods, concurrency, notifications ("like Swiggy") | aggregator list | n/a | [awesome-low-level-design](https://github.com/ashishps1/awesome-low-level-design/blob/main/problems/food-delivery-service.md) | pages 01-02, cards 7, 10, 13 |
| Route optimisation using third-party real-time data | Zepto | 2024 | LC 5710176 via landscape | **not added**: needs a maps service; an HLD topic |
| Judged on classes + DB schema + API design rather than runnable code | Zepto (via InterviewVector) | 2024 | LC [5885026](https://leetcode.com/discuss/post/5885026/) via landscape | card 15 gives the schema-level SQL (conditional UPDATE, idempotency key, outbox) |
| Format: machine coding about 3 h with explanation, interviewer runs sample tests (2024); separate 60-min LLD round (2025-26) | Swiggy | 2024-2026 | LC [4540407](https://leetcode.com/discuss/post/4540407/) [7069404](https://leetcode.com/discuss/post/7069404/) via landscape | implement card now names the must-write core |

Existing cards with no food-specific interview report found (kept because the spec requires them or they are the
standard payments answers): card 5 (gateway timeout, UNKNOWN), card 8 (idempotent retry), card 12 (multi-restaurant
basket), card 13 (rider refuses; pooling), card 14 (scheduled orders).
