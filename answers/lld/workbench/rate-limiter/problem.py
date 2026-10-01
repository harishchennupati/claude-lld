"""The rate limiter workbench: every step's words, in page order. The code comes from java/, the
output from real runs (see config.py), the pictures from figures.py.

Two variants of the same page are built (see VARIANTS at the end): in one, the design is thought
through and the code typed in a single walk; in the other, the walk comes first and the build
steps follow it in the same order."""
import re

from config import CONFIG
import figures

U, D, B, F, R = 'Understand', 'Design', 'Build the core', 'Follow-ups', 'Remember and practise'


def step(id_, group, nav, title, body, minutes=None, opt=False, stage=None):
    d = dict(id=id_, group=group, nav=nav, title=title, body=body, min=minutes, opt=opt)
    if stage:
        d['stage'] = stage
    return d


def hour(w, text):
    """What of this step to type in a 60-minute round."""
    return w.md('*In the hour:* ' + text)


CONFIG_YAML = '''
plans:                                # a plan belongs to the customer and carries its limits
  FREE: { rate: 5 per second,  daily: 10000 per day }
  PRO:  { rate: 50 per second, daily: 1000000 per day }

rules:                                # checked in this order; a request must pass every rule
                                      # that matches it
  - name: rate                        # each customer's speed
    match:     { caller: customer, endpoint: "*" }
    count_per: customer
    limit:     { from_plan: rate }
    algorithm: token_bucket           # a burst, then a steady rate

  - name: daily                       # each customer's allowance for the calendar day
    match:     { caller: customer, endpoint: "*" }
    count_per: customer
    limit:     { from_plan: daily }
    algorithm: fixed_window

  - name: search                      # search is expensive: its own budget
    match:     { caller: customer, endpoint: /search }
    count_per: customer_and_endpoint
    limit:     { fixed: 2 per second }
    algorithm: token_bucket

  - name: login                       # stops password guessing
    match:     { caller: any, endpoint: /login }   # no API key yet when signing in
    count_per: ip
    limit:     { fixed: 5 per minute }
    algorithm: sliding_window_log     # exact: never 6 in any 60 seconds

  - name: global                      # protects the servers
    match:     { caller: any, endpoint: "*" }
    count_per: everyone
    limit:     { fixed: 1000 per second }
    algorithm: token_bucket
'''


# ================================================================================ understand
def problem(w):
    return step('problem', U, 'The problem', 'A rate limiter for a cricket-score API', minutes=6, body=
        w.ask('We run a public API that serves live cricket scores to other apps: a score widget '
              'that news sites embed, a fantasy-cricket app, a few cricket blogs. Each app calls us '
              'with its API key, and each is on a plan, free or paid. Last week the widget shipped a '
              'retry bug and sent us 2,000 requests a second, and the API slowed down for everyone, '
              'including the customers who pay us.'
              '</p><p class="aq">'
              'Design and code the rate limiter that sits in front of this API. For every request it '
              'decides: may this go ahead now? If not, the caller gets a 429 and should know when to '
              'try again. Paid plans get more than free ones, and some endpoints need limits of their '
              'own: search is expensive, and sign-in has to stop password guessing.'
              '</p><p class="aq">'
              'Start with one server and keep the counts in memory, but it serves many requests at '
              'once. Write working Java. We will add requirements as we go, so a new limit should not '
              'mean a rewrite.')
        + w.md('''
        The brief gives the shape, not the numbers: those come from your questions. The limiter
        answers one question before the API does any work: *may this request go ahead now?*
        ''')
        + w.fig(figures.flow(), caption='The limiter sits at the front door, before the real work.')
        + w.md('''
        ## Ask these first

        Each answer changes the code:
        ''')
        + w.table(['You ask', 'Assume they say', 'What it changes'], [
            ['What are the plan limits?', 'FREE: 5 a second and 10,000 a day. PRO: 50 a second '
             'and 1,000,000 a day', 'Limits come from the customer\'s plan, not from constants; '
             'one plan has two limits.'],
            ['Search and sign-in: how much, and per what?', 'Search: 2 a second per customer. '
             'Sign-in: 5 a minute per IP, since the caller has no key yet', 'Each limit says whose '
             'budget it spends: a customer, a customer on one endpoint, an IP.'],
            ['Anything that protects the servers themselves?', 'Yes: never more than 1,000 a second '
             'in total', 'One more limit, spent by everyone together.'],
            ['Can a customer burst?', 'Yes, up to its limit; sign-ins must be exact',
             'Each limit names how it counts.'],
            ['Several limits apply: which wins?', 'All must allow; a refused request counts '
             'nowhere', 'All or nothing, with a refund.'],
            ['What goes in the 429?', 'Retry-After in whole seconds, and which limit said no',
             'The answer is a small record, not a boolean.'],
            ['A customer upgrades mid-day?', 'The new limit applies at once', 'Look the plan up '
             'on every request; the counter\'s key carries the limit, so a new limit gets a fresh '
             'counter.'],
        ], cls='qs')
        + w.md('''
        ## The limits, as the product's config

        The answers above, written down the way the product team would keep them:
        ''')
        + w.snippet(CONFIG_YAML, label='rate-limits.yaml', kind='yaml')
        + w.md('''
        Each rule answers four things:

        - **which requests** it matches: the kind of caller, and an endpoint (`"*"` for all)
        - **whose budget** they spend
        - **how much:** fixed, or from the customer's plan
        - **how** they are counted

        And two rules hold across all of them:

        - A request passes only if **every** rule that matches it allows it; a refused request
          spends nothing anywhere.
        - A new limit is a new entry here, with **no code changed**.

        ## What the hour holds

        - **Type (about 200 lines):**
            - the records
            - the limiter's loop, with its refund
            - one rule, with its key
            - the limit policy
            - the counter interface and the token bucket
            - the store
            - a `Main` with a burst and a race
        - **Type if there is time, or just say:** the filter, plans, the fixed window and the
          log, the five config lines.
        - **The 60 minutes:** 5 to ask, 10 to think the design through on the board, 35 to type,
          10 for follow-ups.
        ''')
        + w.box('note', 'How to use this page',
                '← and → move between steps. Reading takes about 2 hours; steps marked *later* are '
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
        **Why use it:** two counts and the window's start per customer, instead of one timestamp
        per request, and almost exact.

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
        up to 10 within that first second. So it is not "at most 5 in any second"; for an API
        that is fine.

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

        **What our rules use:**

        - **Token bucket:** the per-second limits. A burst, then a steady rate; it is what Stripe
          and AWS API Gateway use.
        - **Fixed window:** the daily quota, a calendar day.
        - **Sliding log:** sign-ins. Small, and must be exact.
        - **Later:** the sliding counter and the leaky bucket are a follow-up
          ([More ways to count](#windows)), whose demo runs both tests above on the real classes.
        '''))


# ==================================================================================== design
# Each branch reads the way an engineer works it: the need; the diagram so far;
# then the code: the traps, the files (each top comment says what the type is for, why it is a
# record, interface, enum or class, and the logic is explained line by line), and the hour.
NEED = {
    'door': '''
        **Need:** fantasy-app's `GET /search?q=kohli` arrives. Before any work, something must
        decide: go ahead, or 429 now. Where does that check sit, what does it take in, and what
        does it give back?
        ''',
    'limiter': '''
        **Need:** one request usually matches several rules. fantasy-app's search matches `rate`,
        `daily`, `search` and `global`, and it goes ahead only if every one of them allows it.

        - **All or nothing:** if `rate` and `daily` each take a token and then `search` refuses,
          the request never ran, so it must have spent nothing.
            - take as you go, and remember which counters were charged
            - on a refusal, give those tokens back
            - not "check all, then take": between the two, another thread can take the same
              token
        - **No global lock:** each counter has its own, so one customer never waits on another.

        **What the limiter needs**, listed breadth first before going deep:

        1. **the rules:** what one is, and which ones match a request → branch 1
        2. for each rule, **how much** it allows → branch 1a, under the rules
        3. for each rule, **what has been counted**, and how → branch 2
        4. **where** those counts live, shared by every thread → branch 3
        5. **the time**, one instant for every rule → handed in, as a `Clock`
        6. **the order** of the rules: `global` goes last. Its one counter is the busiest lock in
           the system, so only requests every other rule allowed should reach it.

        Then write the loop with names that do not exist yet. Each one is a branch to take next:
        ''',
    'rules': '''
        **Need:** what is one rule? Read one config entry: `name`, `match`, `count_per`, `limit`,
        `algorithm`. Each field becomes one piece.
        ''',
    'limits': '''
        **Need:** how much does a rule allow? Two kinds: **fixed** (`search: 2 per second`), or
        **from the customer's plan** (`rate: from_plan rate`). The rule must not care which.
        ''',
    'counters': '''
        **Need:** how is one budget counted? Each rule names its way
        ([How to count](#counting) chose them):

        - token bucket: `rate`, `search`, `global` (a burst, then a steady rate)
        - fixed window: `daily` (a calendar day)
        - sliding log: `login` (small, and exact)

        The limiter must call all three the same way.
        ''',
    'store': '''
        **Need:** where do the counts live? One counter per rule and budget, such as
        `rate:fantasy-app`, kept between requests and shared by every thread.
        ''',
}

DRAFT_LOOP = '''
for (RateLimitRule rule : rules) {                       // branch 1: the rules
    if (!rule.matches(request)) continue;
    Limit limit = rule.limits().limitFor(request);        // branch 1a: how much
    Counter counter = counters.counterFor(rule.keyFor(request), limit,   // branch 3: where
                                          rule.algorithm(), now);
    Decision d = counter.tryAcquire(now);                 // branch 2: counting
    if (!d.allowed()) { refund the earlier counters; return refused; }   // all or nothing
    charged.add(counter);
}'''

# Before the code: the traps it handles. Each type's kind, and why, is in its file's top comment.
TRAPS = {
    'door': '''
        **The traps:**

        - No API key before sign-in, so the customer id can be `null`.
        - Retry-After is whole seconds, rounded up: a 200 ms wait must say 1, not 0, or the
          client retries at once and is refused again.
        ''',
    'limiter': '''
        **The traps:**

        - Read the time once per request, so every rule judges the same instant.
        - Refund every counter already charged before returning a refusal.
        - Typed before its parts exist, as in the room: it compiles once the store is written.
        ''',
    'rules': '''
        **The traps:**

        - Keys from different rules must never collide, so the rule's name comes first:
          `rate:fantasy-app`, `search:fantasy-app:/search`, `login:203.0.113.7`, `global:*`.
        - Sign-in has no customer yet, so `login` matches caller `ANY` and counts per IP.
        ''',
    'limits': '''
        **The traps:**

        - A request with no key has no plan: `planOf(null)` answers FREE, not a crash.
        - The plan is looked up on every request, so an upgrade applies at once.
        ''',
    'counters': '''
        **The traps:**

        - A bucket changes two values together, its tokens and its last refill time, so refill,
          check and take must be one step: the methods are `synchronized` (the picture below
          the bucket).
        - The lock is per counter, so different customers never wait on each other.
        - A refund never fills a bucket past its capacity.
        ''',
    'store': '''
        **The traps:**

        - "`get`, then `put` if missing" lets two threads meeting a new customer both create a
          counter: two budgets. `computeIfAbsent` finds, creates and stores as one step per key.
        - The limit is part of the map's key, so after an upgrade the next request gets a fresh
          50-a-second counter, not the old 5-a-second one.
        ''',
}


def think(w, st):
    """The need, plus the first-draft loop for the limiter."""
    out = w.md(NEED[st])
    if st == 'limiter':
        out += w.snippet(DRAFT_LOOP, label='RuleBasedRateLimiter.check, first draft')
    return out


def think_back(w):
    return w.md('''
        ### ↑ Back to the limiter, then to the door

        Every name in the first-draft loop now exists, so the whole core compiles. Threads, end
        to end:

        - **Rules and plans:** set once, only read.
        - **`Customers` and the store:** `ConcurrentHashMap`s.
        - **Each counter:** its own lock.
        - **The limiter:** holds nothing that changes, so it needs no lock.
        - **Deadlock:** impossible. No thread ever holds two locks.
        ''')


BRANCHES = [  # (step id = diagram stage, nav, title)
    ('door', 'The front door', '1 · A request arrives: what must happen first?'),
    ('limiter', 'The limiter', '2 · ↓ What does the limiter do with many rules?'),
    ('rules', 'The rules', '3 · ↓ Branch 1: what is one rule?'),
    ('limits', 'How much', '4 · ↓↓ Branch 1a: how much does a rule allow?'),
    ('counters', 'Counting', '5 · ↑↓ Branch 2: how is one budget counted?'),
    ('store', 'Where counts live', '6 · ↑↓ Branch 3: where do the counts live?'),
]


def grown(w, st):
    return w.fig(figures.classes(st), caption='The design so far: green boxes are new in this '
                 'branch. Dashed boxes are interfaces; shaded ones records and enums.')


def whole_design(w):
    return (w.md('''
        ## The whole design
        ''')
        + w.fig(figures.classes(), title='The core')
        + w.md('''
        **The patterns, where they are:**

        - **Strategy, twice:** `Counter` for how to count, `LimitPolicy` for how much.
        - **Simple Factory:** `CounterFactory`.
        - **Interfaces the limiter is handed:** `CounterStore` and `Clock`. That is what lets
          Redis, or a clock moved by hand, drop in.

        ## One request through it

        fantasy-app, on PRO, sends its third search in the same second:

        1. `rate` and `daily` allow it, each taking a token.
        2. `search`, at 2 a second, refuses.
        3. The limiter gives back the two tokens already taken and never asks `global`.
        4. The door answers 429.
        ''')
        + w.fig(figures.journey(), title="fantasy-app's third search in one second")
        + w.md('## Where each new requirement will land')
        + w.table(['They add', 'It lands in', 'See'], [
            ['a new limit, such as exports', 'one entry in the config', '[A new rule](#newrule)'],
            ['another way of counting', 'a new `Counter` class and one `case` in the factory',
             '[More ways to count](#windows)'],
            ['a new plan', 'one line in `Plan`', '[Quick ones](#quick)'],
            ['a new way of setting limits', 'a new `LimitPolicy` class', '[Quick ones](#quick)'],
            ['many servers, one budget', 'a `CounterStore` on Redis', '[Many servers](#servers)'],
            ['a million quiet customers', 'a sweep in the store', '[Memory](#idle)'],
        ]))


# ===================================================================================== build
# Each branch's code, right after its thinking: whole files, explained in their comments, plus
# what to type in a 60-minute round.
def code_door(w):
    return (w.code(['Request.java', 'RateLimitResult.java', 'RateLimiter.java',
                    'RateLimitFilter.java'])
            + hour(w, 'the three records and the interface; the filter only if there is time.'))


def code_limiter(w):
    return (w.code(['RuleBasedRateLimiter.java', 'Clock.java'])
            + hour(w, 'all of it: this loop is the heart of the answer.'))


def code_rules(w):
    return (w.code(['RateLimitRule.java', 'Match.java', 'Caller.java', 'CountPer.java',
                    'ScoreApiRules.java'])
            + hour(w, 'the rule, `Match`, `Caller` and `CountPer`; two config entries, and say the '
                      'rest.'))


def code_limits(w):
    return (w.code(['Limit.java', 'LimitPolicy.java', 'FixedLimit.java', 'PlanLimit.java',
                    'Plan.java', 'Customers.java'])
            + hour(w, '`Limit`, `LimitPolicy` and `FixedLimit`; plans if there is time.'))


def code_counting(w):
    return (w.code(['Decision.java', 'Counter.java', 'TokenBucket.java'])
            + w.md('The bucket on its own, told the time by hand: the walk-through from '
                   '[How to count](#counting).')
            + w.run('BucketDemo')
            + w.md('Why the bucket\'s methods are `synchronized`, with one token left:')
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
            + w.md('The other two ways our rules count, the enum that names all three, and the '
                   'factory that makes them:')
            + w.code(['FixedWindowCounter.java', 'SlidingWindowLog.java', 'Algorithm.java',
                      'CounterFactory.java'])
            + w.run('CountingDemo')
            + hour(w, '`Counter`, `TokenBucket`, `Algorithm` and the factory; the window and the '
                      'log only if asked.'))


def code_store(w):
    return (w.code(['CounterStore.java', 'InMemoryCounterStore.java'])
            + w.md('16 threads meet a new customer at the same instant:')
            + w.run('StoreDemo')
            + hour(w, 'all of it.'))


def code_run(w):
    return (w.md('''
        `Main` wires everything as the server would at startup. The clock is moved by hand, so
        every run prints the same. It plays:

        - score-widget's burst
        - fantasy-app's third search in one second
        - sign-ins by IP
        - a refill
        - 100 threads racing for fantasy-app's 50 a second, with the clock frozen
        ''')
            + w.code(['Main.java'])
            + w.run('Main')
            + w.md('''
        Read it against the config:

        - The third search is refused by `search`. The next `/scores` still passes, because the
          refused search spent nothing.
        - The sixth sign-in hears "retry in 60 seconds" from the exact log.
        - The race lets exactly 50 through.
        '''))


CODE = {'door': code_door, 'limiter': code_limiter, 'rules': code_rules, 'limits': code_limits,
        'counters': code_counting, 'store': code_store}
STRIP_NOW = {b['id']: [f[:-5] for f in b['files']] for b in CONFIG['BUILD']}


def design_steps(w):
    out = []
    n = len(BRANCHES) + 1
    for k, (st, nav, title) in enumerate(BRANCHES):
        out.append(step(st, D, nav, title.split(' · ', 1)[1], minutes=8,
                        stage=f'Design and build · {k + 1} of {n}', body=
            w.strip(now=STRIP_NOW[st], groups=CONFIG['STRIP'][:k + 1])
            + think(w, st) + grown(w, st)
            + w.md('## The code')
            + (w.md('Each file\'s top comment says what it is for, and why it is a record, an '
                    'interface, an enum or a class.') if st == 'door' else '')
            + w.md(TRAPS[st]) + CODE[st](w)
            + (think_back(w) if st == 'store' else '')))
    out.append(step('run', D, 'Run it, and the whole design', 'Run it, and the whole design',
                    minutes=10, stage=f'Design and build · {n} of {n}', body=
        w.strip(now=['Main']) + code_run(w) + whole_design(w)))
    return out


# ================================================================================ follow-ups
def followup(w, s, nav, title, ask, lands, minutes, opt=False, src=None, after_run='', hole=None,
             first=()):
    snaps = CONFIG['SNAPS']
    body = (w.ask(ask, src=src, label='Follow-up' if not opt else 'Follow-up · when you have time')
            + w.strip(snap_=s)
            + w.md(lands)
            + w.diff(s, first=first)
            + w.run(CONFIG['DEMOS'][s])
            + (w.md(after_run) if after_run else '')
            + (w.box('hole', 'The catch', hole) if hole else '')
            + w.md(f'*Drill:* start from `rate-limiter-code/steps/{snaps[snaps.index(s) - 1]}/`.'))
    return step(s, F, nav, title, body, minutes=minutes, opt=opt,
                stage='Follow-up · later' if opt else 'Follow-up')


def windows(w):
    return followup(w, 'windows', 'More ways to count', 'More ways to count', minutes=5,
        ask='Implement a sliding window counter too. Which would you pick, and why?',
        lands='''
        - **What changes:** a new `Counter` class and a new `case`. No rule, limiter or store
          logic changes.
        - **The demo:** runs the two tests from [How to count](#counting) on the real classes.
        - **The leaky bucket needs no code:** as a yes-or-no meter, it is the token bucket
          mirrored.
        ''',
        first=['SlidingWindowCounter'],
        after_run='''
        **Which to pick:**

        - **Token bucket:** API rates (a burst, then a steady rate).
        - **Sliding log:** a small limit that must be exact.
        - **Fixed window:** calendar quotas.
        - **Sliding counter:** when a log would cost too much memory and an estimate is fine.
        ''')


def newrule(w):
    return followup(w, 'newrule', 'A new rule', 'A new limit arrives: exports', minutes=3,
        ask='Exports are heavy. Limit /export to 10 a minute per customer.',
        src='The most common follow-up: a new limit, to see whether the design takes it.',
        lands='''
        One entry in the config, and nothing else: every part of a rule already exists (a match,
        a count-per, a fixed limit, an algorithm). This is what modelling the rules as data buys.
        ''')


def credits(w):
    return followup(w, 'credits', 'Credits', 'Unused requests carry over: credits', minutes=5,
        opt=True,
        ask='A customer that uses less than its limit in one second should keep the unused '
            'requests as credits, up to a maximum, and spend them later.',
        lands='''
        Another way of counting, so another `Counter` and one `case`: a fixed window that saves
        what a window did not use, up to one window's worth here.
        ''',
        first=['CreditWindow'],
        hole='Credits ride on fixed windows, so the edge comes back bigger: a quiet second, then '
             '10 at 1,999 ms (5 + 5 credits) and 5 more at 2,000 ms. A token bucket with capacity '
             '10 at 5 a second saves unused requests the same way, without the edge.')


def servers(w):
    return step('servers', F, 'Many servers', 'Many servers, one budget', minutes=6,
                stage='Follow-up', body=
        w.ask("We now run 10 API servers behind a load balancer. A customer's limit must hold "
              'across all of them.', label='Follow-up')
        + w.md('''
        - **The problem:** each server counts on its own today, so 10 servers grant 10 times the
          limit. The counts must be shared.
        - **The seam is already there:** `CounterStore`. A `RedisCounterStore` hands out counters
          whose `tryAcquire` runs **one atomic step inside Redis**:
            - read the tokens and the last refill time
            - refill, check, take, write back
            - let the key expire once a full refill would have happened
        - **What does not change:** the limiter, the rules and the door.
        ''')
        + w.snippet('''
class RedisCounterStore implements CounterStore {
    public Counter counterFor(String key, Limit limit, Algorithm algorithm, long nowMillis) {
        return new RedisTokenBucket(redis, "rl:" + key, limit);   // its tryAcquire: one script
    }
}''', label='the seam (a sketch)')
        + w.md('''
        **Why one atomic step:**

        - Two servers that read "1 token", decide, and write back both allow: the same race
          `synchronized` stopped, now between machines.
        - Redis runs one script at a time, so one script that does all of it is the fleet's
          `synchronized`.
        - Say that; nobody types the script in the room.

        **The trade-offs to say:**

        - **A round trip per request,** under a millisecond in one data centre, against
          nanoseconds in memory. Better: one script for all of a request's rules, not one call each,
          which also makes all-or-nothing atomic, with no refunds.
        - **Redis down or slow:** fail open (serve everyone) for the API, fail closed for sign-ins,
          and a call timeout of a few milliseconds, or a slow Redis stalls every request thread.
        - **Clocks:** servers disagree by milliseconds, so take the time from Redis, or ignore time
          that goes backwards, as the bucket already does.
        - **When near enough is fine:** route each customer to one server, or give each server the
          limit ÷ 10.
        '''))


def idle(w):
    return followup(w, 'idle', 'Memory', 'A million customers: forget the quiet ones',
        minutes=5, opt=True,
        ask='We have a million customers, and most call once a day. Your store keeps their '
            'counters forever.',
        src='Asked of any design that keeps a map per customer.',
        lands='''
        A full token bucket is exactly what a new one would be, so it can go. Each counter says
        when it is idle (default: never), and the store gets a sweep, run by a timer, never by a
        request.
        ''',
        first=['Counter', 'TokenBucket', 'InMemoryCounterStore'],
        after_run='''
        **Keys made by strangers** are the same problem, bigger:

        - A scan from a million IPs makes a million login counters.
        - So bound the map as well as sweeping it.
        - In production a cache library does both (Caffeine's `maximumSize` and
          `expireAfterAccess`). On Redis, the key expires.
        ''')


def quick(w):
    return step('quick', F, 'Quick ones', 'Answered in a sentence', minutes=3,
                stage='Follow-up', body=
        w.md('These come up often, and the design answers each in a sentence.')
        + w.asks([
            ('Add an ENTERPRISE plan.', 'One line in `Plan` with its rate and daily limits; no rule '
             'changes.'),
            ('Search limits should differ by plan too.', 'A new `LimitPolicy` class that looks up '
             '(plan, endpoint), used by the `search` rule. Nothing else changes.'),
            ('Some requests cost more: a full match history costs 5.', '`tryAcquire(cost, now)`: '
             'take `cost` tokens instead of 1, and refund the same. A few lines in `Counter`, the '
             'counters and the limiter.'),
        ], title='Asked often'))


# ================================================================================ remember
def recall(w):
    cards = [
        ('The design, top-down', [
            'door: `RateLimitFilter` asks `RateLimiter.check(Request)`',
            'limiter: every rule that matches it, or none (refund)',
            'one rule: `Match`, `CountPer` key, `LimitPolicy`, `Algorithm`',
            'how much: `FixedLimit` or `PlanLimit` (`Plan`, `Customers`)',
            'counting: `Counter` → token bucket, fixed window, log; `CounterFactory`',
            'where: `CounterStore` → `InMemoryCounterStore`']),
        ('The token bucket, in numbers', [
            '5 a second = capacity 5, a token every 200 ms',
            '120 ms earns 0.6; the wait for 1 is 0.4 × 200 = 80 ms',
            'quiet time fills it to 5, never more',
            'not exact per second: up to 10 in one (5 saved + 5 earned)']),
        ('Threads', [
            'refill, check, take → `synchronized` on the counter',
            'find or create → `computeIfAbsent`',
            'read-only rules → no lock; `Customers` → `ConcurrentHashMap`',
            'the limiter holds no state → no lock, no deadlock']),
        ('Where each follow-up lands', [
            'a new limit → one config line',
            'another algorithm → a `Counter` + one `case`',
            'a new plan → one `Plan` line',
            'many servers → a `CounterStore` on Redis, one atomic step',
            'memory → `isIdle` + a sweep']),
    ]
    grid = '<div class="recall">' + ''.join(
        f'<div class="rc"><h4>{t}</h4><ul>' + ''.join(f'<li>{w.inline(i)}</li>' for i in items)
        + '</ul></div>' for t, items in cards) + '</div>'
    return step('recall', R, 'One-screen recall', 'The whole design on one screen', minutes=4, body=
        w.md('Come back to this a week from now. If every line brings back the code behind it, you '
             'are ready.')
        + w.fig(figures.classes(), title='The core')
        + grid
        + w.md('The lines to remember exactly:')
        + w.snippet('''
if (!rule.matches(request)) continue;                                      // which rules
Counter c = counters.counterFor(rule.keyFor(request), limit, rule.algorithm(), now);
if (!d.allowed()) { for (Counter s : charged) s.refund(now); return refused; }   // all or nothing
tokens = Math.min(capacity, tokens + elapsed / millisPerToken);           // refill, capped
long wait = (long) Math.ceil((1 - tokens) * millisPerToken);              // or say when
return counters.computeIfAbsent(id, k -> CounterFactory.create(algorithm, limit, nowMillis));''',
                    label='six lines'))


def practise(w):
    return step('practise', R, 'Practise', 'Practise: write it yourself', body=
        w.md('''
        Switch this page to **Practise** mode (top right): code and answers stay hidden until you
        ask. Write in your own editor, without the comments.
        ''')
        + w.drill('Drill 1 · The design on the board', 10, '''
        From the YAML alone: walk the branches out loud and draw the diagram, layer by layer. Then
        trace fantasy-app's third search through it.
        ''')
        + w.drill('Drill 2 · The hour', 35, '''
        Type what "In the hour" marks in each build step, top-down, and run `Main`. The first time,
        expect 50 minutes.
        ''', w.checks('core', [
            '`Request`, `RateLimitResult`, `RateLimiter`',
            '`RuleBasedRateLimiter`: the loop and the refund', '`RateLimitRule`, `CountPer`',
            '`Limit`, `LimitPolicy`, `FixedLimit`', '`Counter`, `TokenBucket`',
            '`CounterStore`, `InMemoryCounterStore` with `computeIfAbsent`',
            '`Main`: a burst, a refused search, the race']))
        + w.drill('Drill 3 · The whole core', 60, '''
        Everything, plus the filter, plans, the window and the log, and the five config lines.
        ''')
        + w.copybox(w.onefile('core'), 'The whole core in one file',
                    'to check yours against, or to run in an online editor')
        + w.md('''
        ### Drill 4 · Follow-ups

        Start from the code before the step (`rate-limiter-code/steps/<step>/`), write the change,
        then compare.
        ''')
        + w.timed([
            ('A new rule: exports', 3, '#newrule'),
            ('More ways to count: the sliding window counter', 10, '#windows'),
            ('Credits', 10, '#credits'),
            ('Memory: isIdle and the sweep', 10, '#idle'),
        ])
        + w.md('''
        ## When

        Today: read, then drills 1 and 2. In three days: drill 3, plus two follow-ups. In a week:
        the recall screen, then **Check yourself** without looking.

        ## Your miss log

        After each drill, write down what you missed. Next time, read this first. It is kept in this
        browser.
        ''')
        + w.misslog('misses', 'e.g. forgot the refund; get/put instead of computeIfAbsent'))


def check(w):
    q = w.runs.out['QuizDemo'].strip().split('\n')
    return step('check', R, 'Check yourself', 'Check yourself', minutes=12, body=
        w.md('''
        Answer each one before you open it. Some rounds start from code like the bugs below: find
        what is wrong, then fix it.

        ## Predict the output
        ''')
        + w.reveal('score-widget (FREE, 5 a second) sends 5 requests at 0 ms, then 3 more at 450 ms. '
                   'What are the three answers at 450 ms?',
                   '450 ms earns 2.25 tokens: the first takes one (1.25 left), the second takes one '
                   '(0.25), the third is refused: the missing 0.75 of a token takes 150 ms.\n\n'
                   '<pre class="asc">' + q[0] + '</pre>')
        + w.reveal('fantasy-app (PRO, 50 a second) makes one request, is quiet for 10 seconds, then '
                   'sends 60 at once. How many pass?',
                   '50: ten seconds earn 500 tokens, but the bucket keeps 50.\n\n<pre class="asc">'
                   + q[1] + '</pre>')
        + w.reveal("fantasy-app's third search in a second is refused. Does its next /scores pass?",
                   'Yes: the refused search gave back the `rate` and `daily` tokens it took. Without '
                   'the refund, every refused search would cost a rate token too.')
        + w.md('## Spot the bug')
        + bug(w, 1, '''
Counter counter = counters.get(id);
if (counter == null) {
    counter = CounterFactory.create(algorithm, limit, nowMillis);
    counters.put(id, counter);
}
return counter;''', 'Check, then act: two threads meeting a new customer both see `null` and both '
            'make a counter, so the customer gets two budgets.', '''
return counters.computeIfAbsent(id, k -> CounterFactory.create(algorithm, limit, nowMillis));''')
        + bug(w, 2, '''
@Override
public synchronized RateLimitResult check(Request request) {   // on the limiter
    ...                                                       // counters not synchronized
}''', 'Correct, and slow: one lock for the whole API, so every customer waits behind the busiest '
            'one. The lock belongs where the shared numbers are: one per counter.', '''
public RateLimitResult check(Request request) { ... }              // no lock here
public synchronized Decision tryAcquire(long nowMillis) { ... }    // one lock per counter''')
        + bug(w, 3, '''
if (!d.allowed()) {
    return RateLimitResult.refused(rule.name(), d.retryAfterMillis());   // charged keep tokens
}''', 'No refund: a search refused by `search` still cost a `rate` and a `daily` token.', '''
for (Counter spent : charged) {
    spent.refund(now);
}
return RateLimitResult.refused(rule.name(), d.retryAfterMillis());''')
        + bug(w, 4, '''
private long tokens;
...
tokens = Math.min(capacity, tokens + (long) (elapsed / millisPerToken));
lastRefillMillis = nowMillis;''', 'Whole tokens: 120 ms earns 0, and `lastRefillMillis` moves on '
            'anyway, so the 0.6 is lost for good. A customer sending every 150 ms gets its burst, '
            'then nothing ever again.', '''
private double tokens;                                        // keeps 0.6''')
        + bug(w, 5, '''
private volatile double tokens;            // "volatile makes it thread-safe"
public Decision tryAcquire(long nowMillis) {   // not synchronized
    ...''', '`volatile` makes each write visible, but `tokens -= 1` is still read, then write: two '
            'threads can both take the last token.', '''
public synchronized Decision tryAcquire(long nowMillis) { ... }''')
        + bug(w, 6, '''
String id = key;                         // the limit left out of the key
return counters.computeIfAbsent(id, k -> CounterFactory.create(algorithm, limit, nowMillis));''',
            'An upgrade from FREE to PRO is ignored: the map keeps returning the 5-a-second bucket '
            'made before the upgrade.', '''
String id = key + "|" + limit.requests() + "/" + limit.periodMillis();''')
        + w.md('## What would you change if...')
        + w.reveal('...each customer also gets 1,000 an hour?',
                   'One config line: a rule `hourly` with `CountPer.CUSTOMER`, a `FixedLimit` of '
                   '`new Limit(1_000, 3_600_000)` and the token bucket.')
        + w.reveal('...a list of partners must never be limited?',
                   'Let them past the door before `check`; no limiter code changes.')
        + w.reveal('...one limit per endpoint for everyone together?',
                   'One more `CountPer` value, `ENDPOINT`, and its `case` in `keyFor`; then a rule '
                   'that uses it.'))


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


def allcode(w, pages_by_id):
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
        title = pages_by_id[b['id']]['nav']
        groups += (f'<details class="more"><summary>{title}</summary>' + w.code(b['files'])
                   + '</details>')
    later = ''
    for prev, s in zip(snaps, snaps[1:]):
        new = [f for f in CONFIG['FILE_ORDER'] if t.exists(f, s) and not t.exists(f, prev)]
        if new:
            later += (f'<details class="more"><summary>{pages_by_id[s]["nav"]}: '
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
        + w.md('## What the follow-ups add')
        + later)


def _assemble(w, middle):
    out = ([problem(w), counting(w)] + middle(w)
           + [windows(w), newrule(w), servers(w), credits(w), idle(w), quick(w),
              recall(w), practise(w), check(w)])
    by_id = {p['id']: p for p in out}
    return out + [allcode(w, by_id)]


# One layout: the design is thought through and typed branch by branch.
def pages(w):
    return _assemble(w, design_steps)
