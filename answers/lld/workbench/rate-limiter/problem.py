"""The rate limiter workbench: every step's words, in page order. The code comes from java/, the
output from real runs (see config.py), the pictures from figures.py."""
import re

from config import CONFIG
import figures

U, D, B, F, R = 'Understand', 'Design', 'Build the core', 'Follow-ups', 'Remember and practise'


def step(id_, group, nav, title, body, minutes=None, opt=False, stage=None):
    d = dict(id=id_, group=group, nav=nav, title=title, body=body, min=minutes, opt=opt)
    if stage:
        d['stage'] = stage
    return d


def say(w, text):
    """Why this step's code is written the way it is: the thinking, in a short paragraph."""
    return w.md('**The thinking.** ' + text)


# ================================================================================ understand
def problem(w):
    return step('problem', U, 'The problem', 'A rate limiter for a cricket-score API', minutes=5, body=
        w.ask('Each customer may make X requests every Y seconds. Implement '
              '`rateLimit(customerId)`. Keep the code simple, but extensible: we will add to it.',
              src="Atlassian's version, as candidates report it; Freshworks, Postman, Swiggy, "
                  'OpenAI and Anthropic ask versions of it, with follow-ups like the ones at the '
                  'end of this page.', label='The interviewer')
        + w.md('''
        ## The situation

        We run a public API that serves live cricket scores to other apps, our **customers**: a
        score widget that news sites embed, a fantasy-cricket app, a few cricket blogs. Each calls
        with its API key. Last week the widget shipped a retry loop that sent 2,000 requests a
        second, and the API slowed down for everyone.

        So before the API does any work, it asks one question: *may this customer go ahead now?*
        If not, it answers at once with **429 Too Many Requests** and a **Retry-After** header,
        and spends nothing else on the request.
        ''')
        + w.fig(figures.flow())
        + w.md('''
        ## Ask these first

        Each answer changes the code:
        ''')
        + w.table(['You ask', 'Assume they say', 'What it changes'], [
            ['Who is limited?', 'Each customer, by its API key', 'The limiter counts per customer.'],
            ['Same limit for everyone?', 'A default, and some customers get more',
             'Limits come from a lookup, not from constants in the code.'],
            ['Can a customer burst?', 'Yes, up to its limit at once', 'The token bucket, below.'],
            ['What does a refused customer get?', '429, and when to retry',
             'The answer says how long to wait, not just no.'],
            ['One server or many?', 'One, for now', 'Counts in memory, behind an interface that a '
             'shared store can replace later.'],
            ['Many requests at once?', 'Yes: a thread pool', 'Thread-safe, and customers never wait '
             'on each other.'],
        ], cls='qs')
        + w.md('''
        ## What the hour holds

        **Typed in the room:** one limiter, a limit per customer with a default, the token bucket,
        counts kept in memory, thread-safe, and a `Main` that shows a burst, a refill and a race:
        about 150 lines. **Said, not typed:** the other ways of counting, tiers, limits per
        endpoint, many servers. Each lands on a seam the core already has, which is what "simple,
        but extensible" is grading.

        **The 60 minutes:** 5 to ask, 10 to walk the design top-down on the board, 35 to type the
        core, 10 for follow-ups. Get it running early.
        ''')
        + w.box('note', 'How to use this page',
                '← and → move between steps. Reading takes about 1 h 45; steps marked *later* are '
                'optional. Then practise in **Practise** mode (top right), where code and answers '
                'stay hidden.'))


def counting(w):
    return step('counting', U, 'How to count', 'Five ways to count', minutes=15, body=
        w.md('''
        Before any classes: how do we count "X requests every Y seconds"? Five ways are known, and
        an interviewer expects you to name them and say why you picked one. All examples use 5 a
        second.

        ## 1. Fixed window

        **Idea:** cut time into 1-second boxes by the clock, count requests in the current box, and
        reset the count to 0 when a new box starts. **Keeps per customer:** when the current window
        started, and a count.
        ''')
        + w.asc('''
   window A (0 – 999 ms)              window B (1000 – 1999 ms)
 |==================================|==================================|
   ✓ ✓ ✓ ✓ ✓   ✗   ✗                  ✓ ✓ ✓ ...
   count: 1 2 3 4 5  (full)           count resets to 0 at 1000 ms
               ✗ "retry at 1000 ms"
''')
        + w.md('**Retry after:** the end of the current window. **The catch:** the edge between '
               'two windows.')
        + w.asc('''
   window A                          window B
 |==================================|==================================|
                          ✓✓✓✓✓     |  ✓✓✓✓✓
                         at 995 ms  |  at 1001 ms

   window A's count: 5 → fine        window B's count: 5 → fine
   {r}but 10 requests passed in 6 ms  ✗  twice the limit{/}
''', 'bad')
        + w.md('''
        **Still useful for:** a daily quota ("10,000 a day, resets at midnight"). There the
        calendar day is the rule, and a per-second limit already stops bursts.

        ## 2. Sliding window log

        **Idea:** remember the time of every allowed request. "The last second" moves with now,
        and you count only the timestamps inside it. **Keeps per customer:** a list of timestamps,
        oldest first.
        ''')
        + w.asc('''
                  ┌───────── the last 1000 ms ─────────┐
 ─────────────────┼────────────────────────────────────┼────▶ time
              now − 1000                              now
   older timestamps          count the ones in here;
   are thrown away           fewer than 5 → allow

 t = 0..400   allowed at 0, 100, 200, 300, 400       → log [0, 100, 200, 300, 400]
 t = 995      last 1000 ms = (−5 .. 995]: all 5 inside → ✗ refused
              retry when the oldest (0) leaves: 0 + 1000 − 995 = 5 ms
 t = 1001     last 1000 ms = (1 .. 1001]: 0 drops out  → 4 inside
              ✓ allowed                                → log [100, 200, 300, 400, 1001]
''')
        + w.md('**Retry after:** when the oldest timestamp leaves the window. The fixed window\'s '
               'edge problem cannot happen:')
        + w.asc('''
 5 at 995 ms  → log [995, 995, 995, 995, 995]
 at 1001 ms   → all 5 still inside the last second → ✗ until 1995 ms
 {g}never more than 5 in ANY 1000 ms: exact{/}
''')
        + w.md('**The catch:** one timestamp per request.')
        + w.asc('''
 limit 600 a minute  → up to 600 timestamps per customer
 1 million customers → up to 600 million timestamps   {r}✗ memory{/}
''')
        + w.md('''
        **Use for:** small limits that must be exact, like sign-in attempts (5 a minute per IP).

        ## 3. Sliding window counter: the log's answer, guessed

        The log asks "how many requests in the last second?" and answers exactly, because it keeps
        every timestamp. The counter asks the same question but keeps only two numbers, like a
        fixed window: how many requests came in the **previous** second, and how many have come in
        **this** second so far.

        To keep the arithmetic easy, take a limit of 10 a second. The previous second had 10
        requests, this one has 2 so far, and the time is 1300 ms.

        **Step 1: draw "the last 1 second".**
        ''')
        + w.asc('''
        previous second (10 requests)        current second (2 so far)
 |────────────────────────────────────|────────────────────────────────────|
 0                                  1000                                 2000
             |◄─────────── last 1 second ───────────►|
            300                                    1300 = now
''')
        + w.md('''
        The last second covers 700 ms of the previous second and the first 300 ms of this one.

        **Step 2:** we do not know where the previous 10 requests fell, so assume they were spread
        evenly, one per 100 ms.
        ''')
        + w.asc('''
 |  ●  |  ●  |  ●  |  ●  |  ●  |  ●  |  ●  |  ●  |  ●  |  ●  |
 0    100   200   300   400   500   600   700   800   900   1000
 └──── 3 outside ──┘└────────── 7 inside the last second ──────────┘
''')
        + w.md('''
        So 70% of 10 = 7 of them count.

        **Step 3:** add this second's real count. 7 + 2 = 9. The limit is 10, so one more fits ✓.
        ''')
        + w.asc('''
 guess = previous × (share still inside) + current
       =   10     ×        70%           +    2     = 9
''')
        + w.md('''
        **The catch:** "assumes evenly spread". If all 10 previous requests came at 950 ms, all 10
        are inside the last second, but the guess still counts 7, so a few extra requests slip
        through. A small error, and that is the whole catch.
        ''')
        + w.asc('''
 what it guesses:  | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |   → counts 7
 what happened:    |   |   |   |   |   |   |   |   |   |●●●●●●●●●●| → really 10
''')
        + w.md('''
        **Why use it:** three numbers per customer instead of one timestamp per request, and
        almost exact.

        ## 4. Token bucket: a fixed window that refills one ticket at a time

        Think of the fixed window as a jar of 5 tickets. At every clock tick (0 ms, 1000 ms,
        2000 ms) someone refills it to 5 all at once, and each request takes a ticket. That
        all-at-once refill is exactly why 10 requests can pass around 1000 ms.

        The token bucket changes one thing: the jar gets **one ticket every 200 ms** (5 a second),
        and never holds more than 5.
        ''')
        + w.asc('''
     FIXED WINDOW                         TOKEN BUCKET
     refilled to 5 at each tick           +1 ticket every 200 ms
     (at 0, 1000, 2000 ms)
           │                                    │
           ▼                                    ▼
       ┌───────┐                            ┌───────┐
       │ ●●●●● │  max 5                     │ ●●●●● │  max 5
       └───┬───┘                            └───┬───┘
           ▼ each request takes 1               ▼ each request takes 1
       empty → ✗                            empty → ✗
''')
        + w.md('Walk through it:')
        + w.asc('''
 time      what happens                                    jar after
 0 ms      jar starts full                                 ●●●●●
 0 ms      5 requests, each takes one        ✓✓✓✓✓         (empty)
 0 ms      6th request, no ticket            ✗             (empty)
 200 ms    +1 ticket drops in                              ●
 200 ms    a request takes it                ✓             (empty)
 300 ms    a request; next ticket at 400 ms  ✗ "retry in 100 ms"
 400 ms    +1 ticket drops in                              ●
 ... quiet until 3400 ms: 15 tickets would drop, the jar holds 5
 3400 ms                                                   ●●●●●
''')
        + w.md('The fixed window\'s edge problem does not happen, because nothing refills all at '
               'once:')
        + w.asc('''
 995 ms    jar full → 5 requests            ✓✓✓✓✓     jar empty
 1001 ms   only 6 ms later, no new ticket   ✗✗✗✗✗     (next ticket at 1195 ms)
''')
        + w.md('''
        There is no machine dropping tickets. When a request arrives, the code works out how many
        tickets would have dropped since it last looked:
        ''')
        + w.asc('''
 tickets earned = (now − last time) ÷ 200 ms
 e.g. last looked at 0 ms with 0 tickets, now 600 ms → 600 ÷ 200 = 3 tickets
''')
        + w.md('''
        It keeps parts of a ticket too: 120 ms earns 0.6 of one. That is why a refused request at
        120 ms hears "retry in 80 ms": the missing 0.4 of a ticket takes 80 ms.

        **What it promises:** at most 5 at once (a full jar), and 5 a second on average (the
        drip). After a quiet spell a customer can use the full jar and then 1 more every 200 ms:
        up to 10 within that first second. That is what "not at most 5 in any second" means, and
        for an API it is fine.

        ## 5. Leaky bucket: the token bucket, counted the other way

        Picture a bucket with a small hole: each request pours in 1 cup, the hole drains 1 cup
        every 200 ms, the bucket holds 5 cups, and a request whose cup would overflow it is
        refused ✗.
        ''')
        + w.asc('''
 moment              token bucket          leaky bucket
 start (quiet)       ●●●●●  5 tickets      empty    0 cups
 after 3 requests    ●●     2 tickets      ~~~      3 cups
 after 5 requests    empty  → next ✗       ~~~~~    5 cups, full → next ✗
 200 ms later        ●      1 ticket → ✓   ~~~~     4 cups, room → ✓
''')
        + w.md('''
        Same answer every time, because water = 5 − tickets. In the room: "a leaky bucket that
        answers yes or no is just the token bucket, mirrored."

        Its other use is as a **queue**: a clerk serves one person every 200 ms; a burst stands in
        line instead of hearing no, and arrivals are turned away only when 5 already wait. Good for
        calls *we* send (staying under a partner's 5 a second); bad for incoming requests, which
        want a yes or a no now.

        ## All of them on the same two tests

        **Test 1, the window edge:** 5 requests at 995 ms, then 5 more at 1001 ms.
        ''')
        + w.asc('''
                  at 995 ms   at 1001 ms   passed
 fixed window     ✓✓✓✓✓       ✓✓✓✓✓        10   ✗ refilled all at once at 1000
 sliding log      ✓✓✓✓✓       ✗✗✗✗✗         5   all 5 still in the last second
 sliding counter  ✓✓✓✓✓       ✗✗✗✗✗         5   guess 5 × 99.9% ≈ 5, no room
 token bucket     ✓✓✓✓✓       ✗✗✗✗✗         5   jar empty, next ticket at 1195
 leaky bucket     ✓✓✓✓✓       ✗✗✗✗✗         5   bucket full, room at 1195
''')
        + w.md('**Test 2, a steady trickle:** 5 at 0 ms, then one every 200 ms. It shows how the '
               'log and the token bucket differ.')
        + w.asc('''
                  0 ms     200   400   600   800   1000
 sliding log      ✓✓✓✓✓    ✗     ✗     ✗     ✗     ✓    strict: 5 in ANY second
 token bucket     ✓✓✓✓✓    ✓     ✓     ✓     ✓     ✓    burst of 5, then 1 per 200 ms
''')
        + w.md('''
        In one line each:

        - **Fixed window:** 5 per clock second.
        - **Log:** never more than 5 in any second, exactly.
        - **Counter:** the log's answer, guessed from two numbers.
        - **Token bucket:** a burst of 5, then a steady 5 a second.
        - **Leaky bucket:** the token bucket mirrored, or a queue served at a steady pace.

        **The core types the token bucket:** two numbers per customer, bursts allowed, a precise
        Retry-After, and it is what Stripe and AWS API Gateway use. The others are one class
        each, a follow-up ([More ways to count](#windows)) proves it, and its demo runs both tests
        above on the real classes.
        '''))


# ==================================================================================== design
def design(w):
    return step('design', D, 'The design', 'The design, top-down', minutes=12, body=
        w.md('''
        Start where a request starts, at the API's front door, and keep asking "what does this
        need?". When a question opens a deeper one, follow it down until it is settled, then come
        back up and carry on. ↓ marks going deeper, ↑ coming back. Each answer is a type.

        ### 1 · A request arrives. What must happen before any work?

        Authentication has already turned the API key into a customer id. Then one question,
        asked by the request handler: *may this customer go ahead now?* The handler
        should not know how the answer is worked out, so the question is an **interface** with
        one method. The answer is more than yes or no, because a refused customer must hear when
        to retry: a small **record**.
        ''')
        + w.snippet('''
// the front door, in the request handler
Decision d = limiter.check(customerId);
if (!d.allowed()) {
    return tooManyRequests(d.retryAfterMillis());   // 429; Retry-After in seconds, rounded up
}
return serveScores(request);''', label='the handler')
        + w.md('''
        → `RateLimiter` (`check`, plus the interviewer's `boolean rateLimit(customerId)` as a
        one-line default), `Decision`.

        ### 2 · ↓ What does the limiter need to answer?

        Three things: **how much** this customer may do, **what it has done** so far, and **what
        time it is**. Write the method first, with names that do not exist yet; each name is a
        question to settle next:
        ''')
        + w.snippet('''
long now = clock.nowMillis();
Limit limit = limits.limitFor(customerId);                 // how much?
Counter counter = counters.counterFor(customerId, limit, now);   // what has it done?
return counter.tryAcquire(now);''', label='PerKeyRateLimiter.check, first draft')
        + w.md('''
        All three are **handed in** through the constructor, so each can be swapped without
        touching this class. Time is handed in too: then a demo can say "200 ms later" without
        sleeping. → `PerKeyRateLimiter`, `Clock`.

        ### 3 · ↓ How much?

        "X requests every Y seconds" is a value: `Limit(requests, periodMillis)`. Who decides the
        limit for a customer? Today: a few customers have their own, everyone else a default.
        Tomorrow ("we will add to it"): perhaps by plan. So that choice sits behind a one-method
        **interface**, and today's answer is a map with a default. → `Limit`, `LimitPolicy`,
        `CustomerLimits`. ↑ Tiers later are just another `LimitPolicy`; nothing above changes.

        ### 4 · ↓ What has the customer done?

        Some state per customer, and a rule for updating it: that is the algorithm. One method,
        "may one more pass now?", so each way of counting is a class behind an **interface** and
        the limiter never knows which one it holds (the **Strategy** pattern). → `Counter`.

        ↓ **Which one?** The token bucket (see [How to count](#counting)). → `TokenBucket`.

        ↓ **Two threads for the same customer at once?** Refill, check and take must be one step,
        or both can take the last token. `synchronized` on the bucket: the lock is per customer,
        so customers never wait on each other. ↑

        ### 5 · ↓ Where does each customer's counter live?

        In a map from customer to counter, shared by every request thread. Two threads meeting a
        new customer must get the same counter, so finding and creating are one step:
        `ConcurrentHashMap.computeIfAbsent`. The limit goes into the map's key too, so a customer
        whose limit changes simply starts a new counter. And this is the one thing that changes when many
        servers must share one budget, so the map sits behind an **interface** too. Which
        algorithm to create is a plain **enum** and a `switch` in the store. → `CounterStore`,
        `InMemoryCounterStore`, `Algorithm`. ↑

        ### 6 · ↑ Back to the limiter, then to the door

        Every name in the first draft now exists. The limiter keeps no state of its own, so it
        needs no lock, and no thread ever holds two locks, so nothing can deadlock. At startup,
        `Main` builds the three parts and hands them in.

        ## The whole design
        ''')
        + w.asc('''
 the front door      limiter.check(customer) → 429 + Retry-After, or do the work
 └─ {a}RateLimiter{/}        the question                       → {a}Decision{/}
    └─ {a}PerKeyRateLimiter{/}   asks three things, holds no state
       ├─ how much?          {a}LimitPolicy{/} → {a}Limit{/}         {d}CustomerLimits: own limit, or a default{/}
       ├─ what has it done?  {a}CounterStore{/} → {a}Counter{/}      {d}one counter per customer{/}
       │  ├─ counted how?    {a}TokenBucket{/}                 {d}synchronized: one lock per customer{/}
       │  └─ kept where?     {a}InMemoryCounterStore{/}        {d}computeIfAbsent; Algorithm + switch{/}
       └─ what time?         {a}Clock{/}                       {d}handed in: System::currentTimeMillis{/}
''')
        + w.md('''
        ## Walk one case before typing

        score-widget, 5 a second, sends 7 requests at 0 ms. Its bucket starts full: 5 pass, the
        6th and 7th hear "retry in 200 ms". At 120 ms one more: 0.6 of a token earned, refused,
        "retry in 80 ms". At 200 ms: one whole token, allowed. cricket-blog at 200 ms has its own
        bucket, full: allowed. [Run it](#run) prints exactly this.

        ## Where each new requirement will land
        ''')
        + w.table(['They add', 'It lands in', 'Above it, nothing changes'], [
            ['another way of counting', 'a new `Counter` class and one `case`',
             '[More ways to count](#windows)'],
            ['tiers: FREE 5 a second, PRO 50', 'a new `LimitPolicy`', '[Tiers](#tiers)'],
            ['search, a daily quota, sign-ins by IP, a global cap', 'more limiters with other '
             'keys, checked in order at the door', '[Every limit at the door](#door)'],
            ['many servers, one budget', 'a `CounterStore` on Redis', '[Many servers](#servers)'],
            ['a million quiet customers', 'a sweep in the store', '[Memory](#idle)'],
        ])
        + w.md('''
        That table is the "extensible" the interviewer asked for, and the SOLID story without the
        acronym: each class has one reason to change, new behaviour arrives as a new class rather
        than an edit, and the limiter depends on interfaces it is handed.
        '''))


# ===================================================================================== build
def question(w):
    return step('question', B, 'The question', 'The question the API asks', minutes=3,
                stage='Build · 1 of 6', body=
        w.strip(now=['RateLimiter', 'Decision'])
        + w.md('Type in the order of the design: the question first.')
        + w.code(['RateLimiter.java', 'Decision.java'])
        + say(w, 'The API depends only on this interface. `check` returns a `Decision` so the '
                 'API can send Retry-After; the interviewer\'s `boolean rateLimit` is a one-line '
                 'default on top.'))


def limiter(w):
    return step('limiter', B, 'The limiter', 'The limiter, written first', minutes=4,
                stage='Build · 2 of 6', body=
        w.strip(now=['PerKeyRateLimiter', 'Clock'])
        + w.md('''
        The limiter goes in next, before its parts: write the caller, then make its names exist.
        It does not compile until the store exists, and that is normal in the room.
        ''')
        + w.code(['PerKeyRateLimiter.java', 'Clock.java'])
        + say(w, 'Three questions: how much, what has been done, what time. Each is handed in, '
                 'so the policy can become tiers, the store Redis, and the clock a hand-moved one, '
                 'and this class never changes. It holds no state, so it needs no lock.')
        + w.xy([('Our own one-method `Clock`', '`java.time.Clock`', 'either works; ours is a '
                 'lambda away from a hand-moved clock (`now::get`). With `java.time.Clock` use '
                 '`Clock.fixed` in tests.')])
        + w.md('''
        **Wall clock or `nanoTime`?** `System.currentTimeMillis()` can jump back when the machine
        syncs its clock; the bucket's `elapsed <= 0` guard makes that earn nothing. Within one JVM,
        `System.nanoTime()` never jumps and is the better source for elapsed time; the wall clock
        matters only when servers must agree on a time (Redis).
        '''))


def limits(w):
    return step('limits', B, 'How much', 'How much: the limit, and who decides it', minutes=3,
                stage='Build · 3 of 6', body=
        w.strip(now=['Limit', 'LimitPolicy', 'CustomerLimits'])
        + w.code(['Limit.java', 'LimitPolicy.java', 'CustomerLimits.java'])
        + w.md('''
        `CustomerLimits` is built once and never changes (`Map.copyOf` makes it read-only), so
        every thread can read it without a lock.
        ''')
        + say(w, 'A limit is just X per Y. Who gets which limit is a policy: today a map with a '
                 'default, later tiers, and the limiter never knows the difference.'))


def counting_(w):
    return step('bucket', B, 'Counting', 'Counting: the token bucket', minutes=8,
                stage='Build · 4 of 6', body=
        w.strip(now=['Counter', 'TokenBucket'])
        + w.code(['Counter.java', 'TokenBucket.java'])
        + w.md('The bucket on its own, told the time by hand: the walk-through from '
               '[How to count](#counting).')
        + w.run('BucketDemo')
        + w.md('''
        ## Why `synchronized`

        Refill, check and take read the numbers, then write them. Two threads with one token left:
        ''')
        + w.pair(w.asc('''
{r}✗ without synchronized{/}

  thread A           thread B
  tokens = 1.0
  1.0 >= 1? yes      tokens = 1.0
  tokens = 0.0       1.0 >= 1? yes
  allowed            tokens = 0.0
                     allowed
  {r}✗ one token, two requests{/}
''', 'bad'), w.asc('''
{g}✓ with synchronized{/}

  thread A           thread B
  tokens = 1.0       {d}waits for the{/}
  1.0 >= 1? yes      {d}bucket's lock{/}
  tokens = 0.0
  allowed
                     tokens = 0.0
                     refused
  {g}✓ one token, one request{/}
''', 'good'))
        + w.md('''
        The lock is the bucket itself, so each customer has its own lock. A lock rather than an
        `AtomicLong`: two numbers change together (`tokens` and `lastRefillMillis`), and an atomic
        variable guards only one.
        ''')
        + say(w, 'The limiter only knows `Counter` (Strategy). The bucket earns its tokens when a '
                 'request arrives, not from a timer; `tokens` is a double so 120 ms keeps its 0.6; '
                 'and `synchronized` makes refill, check and take one step per customer.'))


def store(w):
    return step('store', B, 'Where counts live', 'Where the counters live', minutes=5,
                stage='Build · 5 of 6', body=
        w.strip(now=['Algorithm', 'CounterStore', 'InMemoryCounterStore'])
        + w.code(['Algorithm.java', 'CounterStore.java', 'InMemoryCounterStore.java'])
        + w.md('''
        ## Why `computeIfAbsent`

        The first idea is `get`, and `put` a new counter if there is none. Two threads meeting a
        new customer at the same instant both see nothing, both create a counter, and the customer
        gets two budgets. `computeIfAbsent` finds, creates and stores as one step for that key; it
        locks only that key's slot, and only while a counter is created. The limit is part of the
        map's key, so a customer whose limit changes starts a new counter.
        ''')
        + w.run('StoreDemo')
        + say(w, 'Counters live behind an interface: this map today, Redis when there are many '
                 'servers. The key is a plain string on purpose: a customer today, an IP or a '
                 'customer and endpoint later. Which algorithm is a plain enum and a switch: a new '
                 'one is one class and one line.'))


def run_(w):
    return step('run', B, 'Run it', 'Run it', minutes=4, stage='Build · 6 of 6', body=
        w.strip(now=['Main'])
        + w.md('''
        `Main` wires the parts as the server would at startup, with a clock moved by hand so every
        run prints the same: the case from [the design](#design), then 100 threads racing for
        fantasy-app's 50 a second with the clock frozen, so exactly 50 may pass.
        ''')
        + w.code(['Main.java'])
        + w.run('Main')
        + w.md('''
        That is the core: twelve small types and `Main`, about 150 lines. In a 60-minute round,
        this running is the goal; everything after it is talk, unless they ask you to type it.
        '''))


# ================================================================================ follow-ups
def followup(w, s, nav, title, ask, src, lands, minutes, opt=False, after_run='', hole=None,
             first=(), extra=''):
    snaps = CONFIG['SNAPS']
    body = (w.ask(ask, src=src, label='Follow-up' if not opt else 'Follow-up · when you have time')
            + w.strip(snap_=s)
            + w.md(lands)
            + w.diff(s, first=first)
            + w.run(CONFIG['DEMOS'][s])
            + (w.md(after_run) if after_run else '')
            + extra
            + (w.box('hole', 'The catch', hole) if hole else '')
            + w.md(f'*Drill:* start from `rate-limiter-code/steps/{snaps[snaps.index(s) - 1]}/`.'))
    return step(s, F, nav, title, body, minutes=minutes, opt=opt,
                stage='Follow-up · later' if opt else 'Follow-up')


def windows(w):
    return followup(w, 'windows', 'More ways to count', 'More ways to count', minutes=6,
        ask='Implement a sliding window instead. Which would you pick, and why?',
        src='Swiggy (2025) asked for a sliding window and a leaky bucket in the same round.',
        lands='''
        Three new `Counter` classes and three new `case` lines; the limiter does not change. The
        demo runs the two tests from [How to count](#counting) on the real classes.
        ''',
        first=['Algorithm', 'InMemoryCounterStore'],
        after_run='''
        **Which to pick:** the token bucket for an API (a burst, then a steady rate, two numbers);
        the log when it must be exact and the limit is small (sign-ins); the fixed window for
        calendar quotas; the counter when the log would cost too much memory.
        ''')


def credits(w):
    return followup(w, 'credits', 'Credits', 'Unused requests carry over: credits', minutes=5,
        opt=True,
        ask='A customer that uses less than its limit in one second should keep the unused '
            'requests as credits, up to a maximum, and spend them later.',
        src="Atlassian's rate limiter round, as the follow-up to this exact problem.",
        lands='''
        Another way of counting, so another `Counter` and one `case`: a fixed window that saves
        what a window did not use, up to one window's worth here.
        ''',
        hole='Credits ride on fixed windows, so the edge comes back bigger: a quiet second, then '
             '10 at 1,999 ms (5 + 5 credits) and 5 more at 2,000 ms. Say it: a token bucket with '
             'capacity 10 and 5 a second saves unused requests the same way, without the edge.')


def tiers(w):
    return followup(w, 'tiers', 'Tiers', 'Tiers: FREE and PRO', minutes=5,
        ask='FREE customers get 5 a second, PRO 50. Customers can upgrade at any time.',
        src='The most common extension of this problem.',
        lands='''
        A tier is a property of the customer that carries a limit, so it is an `enum` with a
        `Limit`, and choosing by tier is a new `LimitPolicy`. Two new classes and nothing else:
        the store already puts the limit in the counter's key, so an upgrade gets a new counter at
        once. The old 5-a-second counter stays until the idle sweep ([Memory](#idle)).
        ''',
        first=['Tier', 'TierLimits'],
        after_run='''
        `TierLimits` is written by sign-ups and upgrades while requests read it, so it is a
        `ConcurrentHashMap`; `CustomerLimits` never changed, so a plain read-only map was enough.
        ''')


def limits_followup(w):
    return followup(w, 'door', 'Every limit at the door', 'Search, a daily quota, sign-ins, '
                    'and a global cap', minutes=8,
        ask='Searches are expensive: 2 a second per customer. Add a daily quota of 10,000. '
            'Sign-ins come before any API key: 5 a minute per IP, exactly. And never more than '
            '1,000 a second for the whole API.',
        src='Scope grows like this in most rounds: each sentence is one more limit.',
        lands='''
        Each new limit is the **same limiter** with a different key, a different limit and the
        right way of counting: per customer, per IP, or one key for everyone. The core gains only
        a `Limit.perDay` helper. One new class at the door holds them and checks them in order, and the first
        refusal is the answer; a `Request` record carries what the door knows. The old per-customer
        limiter is now one of five. The daily quota uses the fixed window: a token bucket of
        10,000 would let all 10,000 through in one burst, and "per day" is a calendar rule (UTC
        days here).
        ''',
        first=['Request', 'ApiLimits'],
        after_run='''
        The third search in a second is refused by the search limit, and the sign-ins are counted
        by IP with the exact log. The wiring, in `LimitsDemo`:
        ''',
        extra=w.snippet('''
new ApiLimits(
    limiter(tiers,                           Algorithm.TOKEN_BUCKET,       clock),  // by plan
    limiter(key -> Limit.perDay(10_000),     Algorithm.FIXED_WINDOW,       clock),  // quota
    limiter(key -> Limit.perSecond(2),       Algorithm.TOKEN_BUCKET,       clock),  // search
    limiter(key -> Limit.perMinute(5),       Algorithm.SLIDING_WINDOW_LOG, clock),  // by IP
    limiter(key -> Limit.perSecond(1_000),   Algorithm.TOKEN_BUCKET,       clock)); // global''',
            label='LimitsDemo.java'),
        hole='The refused third search already spent a per-second and a daily token. If that '
             'matters, give `Counter` a `refund(now)` and hand back what the earlier limits took '
             'when a later one refuses. In the room, say it; type it only if asked. And the global '
             'cap is first come, first served: under load, FREE traffic can crowd out PRO; give each '
             'tier its own share of the cap if that matters.')


def servers(w):
    return step('servers', F, 'Many servers', 'Many servers, one budget', minutes=6,
                stage='Follow-up', body=
        w.ask("We now run 10 API servers behind a load balancer. A customer's limit must hold "
              'across all of them.', src='OpenAI and Anthropic (2026) asked for a distributed '
              'rate limiter.', label='Follow-up')
        + w.md('''
        Each server counts on its own today, so 10 servers grant 10 times the limit. The counts
        must be shared, and the core already has the seam: `CounterStore`. A `RedisCounterStore`
        hands out counters whose `tryAcquire` runs **one atomic step inside Redis**: read the
        tokens and the last refill time, refill, check, take, write back, and set the key to expire
        once a full refill would have happened. The limiter, the policies and the door do not
        change.
        ''')
        + w.snippet('''
class RedisCounterStore implements CounterStore {
    public Counter counterFor(String key, Limit limit, long nowMillis) {
        // Counter has one abstract method, so a lambda is a Counter
        return now -> redis.runTokenBucket("rl:" + key, limit, now);   // one atomic step
    }
}''', label='the seam (a sketch)')
        + w.md('''
        **Why one atomic step:** two servers that read "1 token", decide, and write back both
        allow: the same race `synchronized` stopped, now between machines. Redis runs one script
        at a time, so a short Lua script is the fleet's `synchronized`. Say that; nobody types the
        script in the room.

        **What to say about the trade-offs:**

        - **A round trip per request,** under a millisecond in one data centre, against
          nanoseconds in memory. Use one script for all of a request's keys, not one call each.
        - **Redis down or slow:** decide fail open (serve everyone, the API is not protected for a
          minute) or fail closed (refuse everyone). For an API, open; for sign-ins, closed. Give
          the call a timeout of a few milliseconds, or a slow Redis stalls every request thread.
        - **Clocks:** servers disagree by milliseconds, so take the time from Redis, or pass `now`
          and ignore time that goes backwards, as the bucket already does.
        - **Cheaper alternatives** when near enough is fine: route each customer to one server, or
          give each server limit ÷ servers and accept the error.
        '''))


def idle(w):
    return followup(w, 'idle', 'Memory', 'A million customers: forget the quiet ones',
        minutes=5, opt=True,
        ask='We have a million customers, and most call once a day. Your store keeps their '
            'counters forever.',
        src='Asked of any design that keeps a map per customer.',
        lands='''
        A full token bucket is exactly what a new one would be, so it can go. Each counter says
        when it is idle (default: never), and the store gets a sweep, run by a timer every minute,
        never by a request.
        ''',
        first=['Counter', 'TokenBucket', 'InMemoryCounterStore'],
        after_run='''
        Keys made by strangers are the same problem, bigger: a scan from a million IPs makes a
        million sign-in counters. Bound the map (a cache with a maximum size) as well as sweeping
        it. In production, a cache library does both (Caffeine's `maximumSize` and
        `expireAfterAccess`); on Redis, the key's expiry.
        ''')


def quick(w):
    return step('quick', F, 'Quick ones', 'Questions answered in a sentence', minutes=3,
                stage='Follow-up', body=
        w.md('''
        Not everything needs code. These come up often, and the core answers each in a sentence.
        ''')
        + w.asks([
            ('Some requests cost more: a full match history costs 5.',
             '`tryAcquire(int cost, long now)`: take `cost` tokens instead of 1. Three lines '
             'across `Counter`, `TokenBucket` and the limiter.'),
            ('Change a customer\'s limit while it runs.',
             'Make the policy writable, as `TierLimits.setTier` is, or swap in a new one. The store '
             'starts a fresh counter on the next request, because the limit is in its key.'),
            ('How would you test it?',
             'A hand-moved clock, as in `Main`: a burst, a refusal with its wait, a refill. Then '
             '100 threads with a frozen clock: never more than the limit allowed.'),
            ('Can it be lock-free?',
             'Yes: keep the tokens and the last refill time in one immutable object and swap it '
             'with `compareAndSet`, retrying on a clash. Same answers; not worth it while one '
             'customer\'s lock is held for nanoseconds.'),
            ('Tell clients how many requests they have left.',
             'Add `remaining` to `Decision`; the bucket knows its tokens. The API sends it as '
             '`X-RateLimit-Remaining`.'),
            ('What should a client do with a 429?',
             'Wait Retry-After; without one, back off exponentially with jitter so retries do not '
             'arrive in a wave.'),
            ('Why not Guava\'s `RateLimiter` or Bucket4j?',
             'In production, use a library: Bucket4j gives token buckets per key with Redis. Guava '
             'is one limiter per JVM and only says yes or no. In the room, the hand-written bucket '
             'shows the thinking.'),
        ], title='Asked often'))


# ================================================================================ remember
def recall(w):
    cards = [
        ('The design, top-down', [
            'the door asks one question → `RateLimiter.check` → `Decision`',
            'the limiter asks three: how much, what done, what time',
            'how much → `LimitPolicy` → `Limit` (`CustomerLimits`)',
            'what done → `CounterStore` → `Counter` (`TokenBucket`)',
            'what time → `Clock`, handed in']),
        ('The token bucket, in numbers', [
            '5 a second = capacity 5, a token every 200 ms',
            '120 ms earns 0.6; the wait for 1 is 0.4 × 200 = 80 ms',
            'quiet time fills it to 5, never more',
            'not exact per second: up to 10 in one (5 saved + 5 earned)',
            'exact → log (sign-ins); calendar → fixed window (quota)']),
        ('Threads', [
            'refill, check, take → `synchronized` on the bucket',
            'find or create → `computeIfAbsent`',
            'read-only maps → no lock; written maps → `ConcurrentHashMap`',
            'the limiter holds no state → no lock, no deadlock']),
        ('Where each follow-up lands', [
            'another algorithm → a `Counter` + one `case`',
            'credits → a `Counter`',
            'tiers → a `LimitPolicy` (the limit is already in the key)',
            'search, quota, sign-in, global → more limiters, other keys',
            'many servers → a `CounterStore` on Redis, one atomic step',
            'memory → `isIdle` + a sweep']),
    ]
    grid = '<div class="recall">' + ''.join(
        f'<div class="rc"><h4>{t}</h4><ul>' + ''.join(f'<li>{w.inline(i)}</li>' for i in items)
        + '</ul></div>' for t, items in cards) + '</div>'
    return step('recall', R, 'One-screen recall', 'The whole design on one screen', minutes=4, body=
        w.md('''
        Come back to this a week from now. If every line brings back the code behind it, you are
        ready; if one does not, go back to that step. The design as signatures, in typing order:
        ''')
        + w.snippet('''
interface RateLimiter { Decision check(String key); default boolean rateLimit(String id) }
record Decision(boolean allowed, long retryAfterMillis)
class PerKeyRateLimiter(LimitPolicy limits, CounterStore counters, Clock clock)
interface Clock { long nowMillis(); }                  // System::currentTimeMillis
record Limit(int requests, long periodMillis)          // perSecond(5)
interface LimitPolicy { Limit limitFor(String key); }
class CustomerLimits(Map<String, Limit> byCustomer, Limit defaultLimit)
interface Counter { Decision tryAcquire(long nowMillis); }
class TokenBucket implements Counter                    // synchronized
enum Algorithm { TOKEN_BUCKET }
interface CounterStore { Counter counterFor(String key, Limit limit, long nowMillis); }
class InMemoryCounterStore(Algorithm algorithm)         // computeIfAbsent; key + limit''',
                    label='the design, as signatures')
        + grid
        + w.md('The lines to remember exactly:')
        + w.snippet('''
long elapsed = nowMillis - lastRefillMillis;
if (elapsed <= 0) { return; }                                   // an older time earns nothing
tokens = Math.min(capacity, tokens + elapsed / millisPerToken); // refill, capped
if (tokens >= 1) { tokens -= 1; return Decision.allow(); }      // take
long wait = (long) Math.ceil((1 - tokens) * millisPerToken);    // or say when
return counters.computeIfAbsent(id, k -> newCounter(limit, nowMillis));    // one per key''',
                    label='six lines'))


def practise(w):
    return step('practise', R, 'Practise', 'Practise: write it yourself', body=
        w.md('''
        Switch this page to **Practise** mode (top right): code and answers stay hidden until you
        ask. Write in your own editor, without the comments.
        ''')
        + w.drill('Drill 1 · The design on paper', 5, '''
        Draw the top-down tree from [the design](#design) from memory, and say the case: 7 at
        0 ms, one at 120 ms, one at 200 ms.
        ''')
        + w.drill('Drill 2 · The core', 35, '''
        Type the core in the build order, top-down, and run `Main`. The first time, expect 50
        minutes; the second, 35.
        ''', w.checks('core', [
            '`RateLimiter`, `Decision`', '`PerKeyRateLimiter`, `Clock`',
            '`Limit`, `LimitPolicy`, `CustomerLimits`', '`Counter`, `TokenBucket`: refill, take, '
            'wait', '`Algorithm`, `CounterStore`, `InMemoryCounterStore` with `computeIfAbsent`',
            '`Main`: the case and the 100-thread race']))
        + w.copybox(w.onefile('core'), 'The whole core in one file',
                    'to check yours against, or to run in an online editor')
        + w.md('''
        ### Drill 3 · Follow-ups

        Start from the code before the step (`rate-limiter-code/steps/<step>/`), write the change,
        then compare.
        ''')
        + w.timed([
            ('More ways to count: fixed window, log, counter', 15, '#windows'),
            ('Tiers, and an upgrade that applies at once', 10, '#tiers'),
            ('Every limit at the door', 15, '#door'),
            ('Credits', 10, '#credits'),
            ('Memory: isIdle and the sweep', 10, '#idle'),
        ])
        + w.drill('Drill 4 · Out loud, one minute each', 5, '''
        The design top-down. Why `synchronized` per bucket. Why `computeIfAbsent`. Why the clock
        is handed in. Is the token bucket exact? Where would Redis go?
        ''')
        + w.md('''
        ## When

        Today: read, then drills 1 and 2. In three days: drill 2 again, plus two follow-ups. In a
        week: the recall screen, then **Check yourself** without looking.

        ## Your miss log

        After each drill, write down what you missed. Next time, read this first. It is kept in this
        browser.
        ''')
        + w.misslog('misses', 'e.g. forgot computeIfAbsent; refilled before checking elapsed'))


def check(w):
    q = w.runs.out['QuizDemo'].strip().split('\n')
    return step('check', R, 'Check yourself', 'Check yourself', minutes=12, body=
        w.md('''
        Answer each one before you open it. Some rounds start from code like the bugs below: find
        what is wrong, then fix it.

        ## Predict the output
        ''')
        + w.reveal('score-widget (5 a second) sends 5 requests at 0 ms, then 3 more at 450 ms. What '
                   'are the three answers at 450 ms?',
                   '450 ms earns 2.25 tokens: the first takes one (1.25 left), the second takes one '
                   '(0.25), the third is refused: the missing 0.75 of a token takes 150 ms.\n\n'
                   '<pre class="asc">' + q[0] + '</pre>')
        + w.reveal('fantasy-app (50 a second) makes one request, is quiet for 10 seconds, then sends '
                   '60 at once. How many pass?',
                   '50: ten seconds earn 500 tokens, but the bucket keeps 50.\n\n<pre class="asc">'
                   + q[1] + '</pre>')
        + w.md('## Spot the bug')
        + bug(w, 1, '''
Counter counter = counters.get(key);
if (counter == null) {
    counter = newCounter(limit, nowMillis);
    counters.put(key, counter);
}
return counter;''', 'Check, then act: two threads meeting a new customer both see `null` and both '
            'make a counter, so the customer gets two budgets.', '''
return counters.computeIfAbsent(key, k -> newCounter(limit, nowMillis));   // one step''')
        + bug(w, 2, '''
@Override
public synchronized Decision check(String key) {    // on the limiter
    ...                                            // and TokenBucket is not synchronized
}''', 'Correct, and slow: one lock for the whole API, so every customer waits behind the busiest '
            'one. The lock belongs where the shared numbers are: one per bucket.', '''
public Decision check(String key) { ... }                          // no lock here
public synchronized Decision tryAcquire(long nowMillis) { ... }    // one lock per bucket''')
        + bug(w, 3, '''
private long tokens;
...
tokens = Math.min(capacity, tokens + (long) (elapsed / millisPerToken));
lastRefillMillis = nowMillis;''', 'Whole tokens: 120 ms earns 0, and `lastRefillMillis` moves on '
            'anyway, so the 0.6 is lost for good. A customer sending every 150 ms gets its burst, '
            'then nothing ever again.', '''
private double tokens;                                        // keeps 0.6
tokens = Math.min(capacity, tokens + elapsed / millisPerToken);''')
        + bug(w, 4, '''
private volatile double tokens;            // "volatile makes it thread-safe"

public Decision tryAcquire(long nowMillis) {   // not synchronized
    refill(nowMillis);
    if (tokens >= 1) { tokens -= 1; return Decision.allow(); }
    ...''', '`volatile` makes each write visible, but `tokens -= 1` is still read, then write: two '
            'threads can both pass the check and both take the last token.', '''
public synchronized Decision tryAcquire(long nowMillis) { ... }''')
        + bug(w, 5, '''
// in InMemoryCounterStore
return counters.computeIfAbsent(key, k -> newCounter(limit, nowMillis));''', 'An upgrade from '
            'FREE to PRO is ignored: the map already has a counter for the customer, built with 5 '
            'a second, and returns it forever.', '''
String id = key + "|" + limit.requests() + "/" + limit.periodMillis();   // new limit, new counter
return counters.computeIfAbsent(id, k -> newCounter(limit, nowMillis));''')
        + w.md('## What would you change if...')
        + w.reveal('...each customer also gets 1,000 an hour, on top of the rest?',
                   'One more limiter, with `key -> new Limit(1_000, 3_600_000)` and the token bucket: '
                   'a field and one line in `ApiLimits`, the one place the API\'s limits are listed. '
                   'Nothing in the core changes.')
        + w.reveal('...a list of partners must never be limited?',
                   'Skip the limiter for them at the door, before `check`; no limiter code changes.')
        + w.reveal('...no bursts at all, just one request every 200 ms?',
                   'A bucket that holds one token is a steady pace: `new Limit(1, 200)`.')
        + w.reveal('...one limit per endpoint for everyone together?',
                   'One more limiter whose key is the endpoint: `check(request.endpoint())`.'))


def bug(w, n, code, answer, fix):
    return (w.md(f'### Bug {n}') + w.snippet(code)
            + w.reveal('What is wrong, and the fix', answer + '\n\n' + w.snippet(fix, label='the fix')))


def _zip(files, folder, pom):
    """A Maven project as a zip, base64, for a download link that works from a local file."""
    import base64
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{folder}/pom.xml', pom.format(artifact=folder))
        for name, text in sorted(files.items()):
            z.writestr(f'{folder}/src/main/java/{name}', text)
    return base64.b64encode(buf.getvalue()).decode()


def allcode(w):
    import sys
    pom = sys.modules[type(w).__module__].POM
    t = w.t
    snaps = CONFIG['SNAPS']
    last = snaps[-1]
    core = {f: t.text(f, 'core') for f in t.names('core')}
    demos = list(CONFIG['DEMOS'].values()) + ['Check']
    complete = dict({f: t.text(f, last) for f in t.names(last)},
                    **{d + '.java': w.runs.demo(d) for d in demos})

    def link(files, folder, label):
        return (f'<a class="dl" download="{folder}.zip" '
                f'href="data:application/zip;base64,{_zip(files, folder, pom)}">{label}</a>')

    groups = ''
    for b in CONFIG['BUILD']:
        title = PAGES_BY_ID[b['id']]['nav']
        groups += (f'<details class="more"><summary>{title}</summary>' + w.code(b['files'])
                   + '</details>')
    later = ''
    for prev, s in zip(snaps, snaps[1:]):
        new = [f for f in CONFIG['FILE_ORDER'] if t.exists(f, s) and not t.exists(f, prev)]
        if new:
            nav = PAGES_BY_ID[s]['nav']
            later += (f'<details class="more"><summary>{nav}: '
                      + ', '.join(n[:-5] for n in new) + '</summary>'
                      + w.code(new, snap_=last) + '</details>')
    return step('code', R, 'All the code', 'All the code, to read or open in your IDE', body=
        w.md('''
        Download a project, unzip it, and open the folder in IntelliJ (File > Open): a plain Maven
        project, Java 17, no dependencies. Run `Main`. The same projects are in the repository
        under `answers/lld/rate-limiter-code/`.
        ''')
        + '<div class="dls">'
        + link(core, 'rate-limiter-core', 'Download the core (.zip)')
        + link(complete, 'rate-limiter-complete', 'Download the core + every follow-up (.zip)')
        + '</div>'
        + w.md('## The core, in the order you type it')
        + groups
        + w.md('''
        ## What the follow-ups add

        New files only, as they end up. Follow-ups also change a few core files; the complete
        download has every change.
        ''')
        + later)


PAGES_BY_ID = {}


def pages(w):
    out = [p(w) for p in (problem, counting, design, question, limiter, limits, counting_, store,
                          run_, windows, tiers, limits_followup, servers, idle, credits, quick,
                          recall, practise, check)]
    PAGES_BY_ID.update({p['id']: p for p in out})
    return out + [allcode(w)]
