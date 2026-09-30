"""The rate limiter workbench: every step's words, in page order. The code comes from java/, the
output from real runs (see config.py), the pictures from figures.py."""
from config import CONFIG
import figures

U, D, B, F, R = 'Understand', 'Design', 'Build the core', 'Follow-ups', 'Remember and practise'


# ================================================================================ understand
def problem(w):
    return dict(id='problem', group=U, nav='The problem', title='A rate limiter for a cricket-score API', body=
        w.ask('Each customer may make X requests every Y seconds. Implement '
              '`rateLimit(customerId)`. Keep the code simple, but extensible: we will add to it.',
              src="Atlassian's wording (2024). Freshworks and Postman (2024) and Swiggy (2025) ask "
                  'it as a machine-coding round; in 2026 OpenAI, Anthropic, Cursor, xAI and '
                  'Databricks asked versions of it, usually with one of the follow-ups at the end '
                  'of this page.', label='The interviewer')
        + w.md('''
        ## The situation

        We run a public API that serves live cricket scores to other apps: a **score widget** that
        news sites embed, a **fantasy-cricket app**, and a few **cricket blogs**. Last week the
        widget shipped a bug, a retry loop that sent 2,000 requests a second, and the API slowed
        down for everyone, including the fantasy app, which pays for a bigger plan.

        So before the API does any work for a request, it asks one question: *may this client make
        a request right now?* If yes, the API serves it. If no, it answers at once with **429 Too
        Many Requests** and a **Retry-After** header, and spends nothing else on it.
        ''')
        + w.fig(figures.flow(), caption='The limiter runs inside the API server, before the real '
                'work. A refused request costs the server almost nothing, which is the whole point.')
        + w.md('''
        **What this really is:** a map from each client to a small counter that refills over time,
        and one method that checks the counter and spends from it, so that two threads can never
        spend the same request. The rest of the design keeps those parts apart, so each can change
        without touching the others.

        ## Ask these first

        Each answer changes something in the code. That is how to tell a useful question from a
        polite one.
        ''')
        + w.table(['You ask', 'Say they answer', 'What it changes'], [
            ['Limit by what: user, API key, IP address?', 'API key: the client id',
             "The map's key. Any string works, so only the caller changes."],
            ['Can a client burst, or must requests be spread out?', 'Short bursts are fine',
             'The counting method: a token bucket (next step).'],
            ['What does a refused client get back?', '429, and when to retry',
             'The answer carries more than yes or no.'],
            ['Same limit for everyone?', 'FREE 5 a second, PRO 50',
             'Limits come from configuration, not from if-statements.'],
            ['One server, or many?', 'One, for now',
             'Buckets live in memory. Many servers is follow-up 8.'],
            ['Many requests at the same time?', 'Yes: the server has a thread pool',
             'Checking and spending must be thread-safe.'],
            ['Does a refused request count against the limit?', 'No',
             'Refusing spends nothing. (Cursor asked exactly this.)'],
        ], cls='qs')
        + w.md('''
        ## What we build

        - `tryAcquire(clientId)` says allowed or refused, how many requests are left, and when a
          refused client can retry.
        - Every client has its own budget. FREE clients get 5 requests a second, PRO clients 50. A
          client nobody has set up is FREE.
        - A client may use its whole budget at once (a burst), then gets requests back at a steady
          rate: at 5 a second, one every 200 ms.
        - A refused request spends nothing.
        - Correct with many threads: never more than the limit, even when 100 requests for one
          client arrive in the same millisecond.
        - Fast: a check is a map lookup and a little arithmetic, and different clients never wait
          for each other.
        - Testable without sleeping: time is handed in.

        **Left out, and said out loud:** many servers sharing one budget, limits per endpoint,
        changing limits while running, saving anything to disk. Each is a follow-up at the end,
        built on this same design.

        ## The hour

        About 5 minutes on these questions, 5 on the design, 25 writing the code, 10 on tests and
        threads, and the rest on follow-ups. They grade the code: small classes with one job each, a
        correct bucket, and thread safety you can explain.
        ''')
        + w.box('note', 'How to use this page',
                '← and → move between steps (or use the list on the left). Read it all once in '
                '**Read** mode. When you come back to practise, switch to **Practise** (top right): '
                'the code and the answers stay hidden until you ask, so you write them first.'))


def counting(w):
    return dict(id='counting', group=U, nav='How to count', title='Four ways to count, and why the token bucket', body=
        w.md('''
        Before any classes, decide how to count. The first idea everyone has is a counter per
        client that resets at every whole second. It is simple, and it has a hole.
        ''')
        + w.asc('''
{a}fixed window{/}, 5 a second: one counter per client, reset at every whole second

            second 0                               second 1
  |-------------------------------------|-------------------------------------|
                                 ▲▲▲▲▲  ▲▲▲▲▲
                                995 ms  1001 ms

  second 0's counter: 5 of 5 ✓          second 1's counter: 5 of 5 ✓
  {r}✗ 10 requests in 6 ms: twice the limit, and each counter says all is well{/}
''', 'bad')
        + w.table(['Way to count', 'What it keeps per client', 'Good at', 'The catch'], [
            ['**Fixed window**', 'a counter, and when its window began', 'the simplest code',
             'twice the limit across a window edge'],
            ['**Sliding window log**', 'the time of every request in the last period',
             'exact: never more than the limit in any period',
             'memory grows with the limit: 1,000 a minute is 1,000 timestamps'],
            ['**Sliding window counter**', "this window's count and the last window's",
             'nearly exact, with two numbers',
             "an estimate: it assumes the last window's requests were spread evenly"],
            ['**Token bucket**', 'tokens, and when they were last topped up',
             'bursts up to a set size, then a steady rate; two numbers',
             'not "at most 5 in any second" (see below)'],
            ['**Leaky bucket**', 'a queue that drains at a fixed rate', 'perfectly even output',
             'requests wait in a queue; we need yes or no now'],
        ])
        + w.xy([
            ('Token bucket', 'fixed window', 'the most that can pass at once is 5, not 10 across a '
             'window edge.'),
            ('Token bucket', 'a sliding window log', 'two numbers per client instead of one '
             'timestamp per request. The log is follow-up 1, for small limits that must be exact.'),
            ('Token bucket', 'a leaky bucket', 'the API needs an answer now, not a place in a queue.'),
        ])
        + w.md('''
        ## How the token bucket works

        score-widget is on FREE, 5 a second:

        - The bucket holds at most **5 tokens**. That is its capacity: the biggest burst.
        - One token comes back every **200 ms** (1,000 ms / 5).
        - A request takes a token. If none is there, the request is refused, and we know exactly
          when the next token arrives.

        No timer adds the tokens. When a request comes in, the bucket works out what it earned
        since it last looked. This is called a *lazy refill*: the same numbers a timer would
        produce, worked out only when someone asks.
        ''')
        + w.asc('''
  earned  =  elapsed / millisPerToken                  120 ms / 200 ms  =  {a}0.6 of a token{/}
  tokens  =  min(capacity, tokens + earned)            never more than {a}5{/}
  wait    =  ceil((1 - tokens) × millisPerToken)       (1 - 0.6) × 200  =  {a}80 ms{/}
''')
        + w.md('''
        Here is score-widget's bucket through one busy second. Build step 3 prints exactly these
        lines from the real class.
        ''')
        + w.table(['Time', 'Tokens before', 'Request', 'Answer', 'Tokens after'], [
            ['0 ms', '5', '1 to 5', 'allowed: 4, 3, 2, 1, 0 left', '0'],
            ['0 ms', '0', '6', '<span class="no">refused, retry in 200 ms</span>', '0'],
            ['120 ms', '0.6', '7', '<span class="no">refused, retry in 80 ms</span>', '0.6'],
            ['200 ms', '1.0', '8', 'allowed, 0 left', '0'],
            ['2,200 ms', '5 (10 earned, capped at 5)', '7 at once', '5 allowed, 2 refused', '0'],
        ], cls='trace')
        + w.box('why', 'Is it exact?',
                'No, and it is worth saying so before they ask. In any 200 ms at most 6 requests '
                'pass (5 saved, 1 earned), where a fixed window lets 10 through across an edge. But '
                'over a whole second a client can get **10**: a full bucket, then the 5 it earns '
                'during that second. A token bucket limits the burst and the average rate, not "at '
                'most 5 in any second". If the rule must be exact, count with a log (follow-up 1).')
        + w.asks([
            ('Why not the fixed window? It is simpler.',
             'It lets twice the limit through across a window edge (the ✗ above). The token '
             'bucket costs almost nothing extra: two numbers and a `min`.'),
            ('How does the sliding window counter estimate?',
             "Current window's count, plus the previous window's count times the share of the "
             'previous window still inside the last second. 300 ms into a second: '
             '`current + previous × 0.7`. It is wrong only when the previous window\'s requests '
             'were bunched up.'),
            ('Where would you use a leaky bucket?',
             'Where we send rather than receive: calls to a partner API that accepts 10 a second '
             'go into a queue, and a worker sends one every 100 ms. Requests wait instead of '
             'being refused.'),
        ]))


# ==================================================================================== design
def design(w):
    return dict(id='design', group=D, nav='The design', title='The design in one picture', body=
        w.md('''
        Start from the caller. The API needs one call before it does any work, and an answer rich
        enough to fill the response headers:
        ''')
        + w.snippet('''
// In the API, before any real work for a request (the API's code, not ours):
Decision d = limiter.tryAcquire(clientId);
if (!d.allowed()) {
    long seconds = (d.retryAfterMillis() + 999) / 1000;       // 200 ms -> 1 second
    return tooManyRequests().header("Retry-After", seconds);  // 429
}
response.header("X-RateLimit-Remaining", d.remaining());
''', label='the caller')
        + w.fig(figures.classes(), title='The classes',
                caption='Read it from the top. The API sees only <b>RateLimiter</b>. '
                '<b>ClientRateLimiter</b> implements it and holds one <b>Bucket</b> per client in a '
                'map. It is handed three things it needs but does not own: <b>Plans</b> (which '
                "limit a client gets), a <b>BucketFactory</b> (how to make a new client's bucket) "
                'and a <b>Clock</b> (what time it is). <b>TokenBucket</b> does the counting: the '
                'only class with arithmetic and a lock.')
        + w.fig(figures.journey(), title='Two requests, end to end',
                caption="fantasy-app's first request creates its bucket inside "
                '<code>computeIfAbsent</code>. score-widget\'s 6th request in the same millisecond '
                'finds its bucket already there, finds it empty, and is refused with a retry time. '
                'Notice what the limiter never does: count, decide limits, or read the system '
                'clock itself.')
        + w.md('## Who does what')
        + w.table(['Class', 'Its one job', 'It changes when'], [
            ['`RateLimiter`', 'the one method the API calls', 'never: it is the contract'],
            ['`Decision`', 'the answer: allowed, remaining, retry time', 'the API needs a new header'],
            ['`ClientRateLimiter`', 'one bucket per client, made on first use',
             'where buckets live (many servers: follow-up 8)'],
            ['`Bucket`, `TokenBucket`', "count one client's requests",
             'the counting method (follow-ups 1 and 2)'],
            ['`Plans`, `Plan`, `Limit`', 'which limit a client gets', 'plans or limits change'],
            ['`BucketFactory`', "make a new client's bucket", 'the counting method: one line of wiring'],
            ['`Clock`', 'tell the time', 'never: tests hand in a manual one'],
        ], cls='who')
        + w.md('''
        The last column is the single responsibility principle made concrete: every reason to
        change the system lands in exactly one class.
        '''))


def derive(w):
    return dict(id='derive', group=D, nav='How to get there', title='How you get to this design', body=
        w.md('''
        Nobody draws that diagram on the first try. Here is the path: for each thing the limiter
        must do, the idea that comes first, what goes wrong with it, and what we do instead.
        ''')
        + w.table(['It must', 'First idea', 'What goes wrong', 'What we do instead'], [
            ['tell the API yes or no', 'return a `boolean`',
             'the API cannot fill in Retry-After or X-RateLimit-Remaining',
             'return a `Decision`: allowed, remaining, retryAfterMillis'],
            ['count each client', 'one class: a map of counters plus the refill arithmetic',
             'every change to counting edits the class the API calls; the arithmetic cannot be '
             'tested on its own',
             'a `Bucket` per client; `TokenBucket` holds the arithmetic'],
            ['know the time', 'call `System.currentTimeMillis()` inside the bucket',
             '"retry in 80 ms" can only be tested by sleeping; the wall clock can jump backwards',
             'pass the time in; the limiter is handed a `Clock`'],
            ['give clients different limits', '`if (plan == PRO) 50 else 5` in the limiter',
             'every new plan is a code change in the limiter',
             '`Plans` maps client to plan to `Limit`, set up at startup'],
            ["make a new client's bucket", '`new TokenBucket(...)` inside the limiter',
             'the limiter is welded to one way of counting',
             'a `BucketFactory` handed in: `TokenBucket::new`'],
            ['handle many threads', 'make `tryAcquire` `synchronized`',
             'every client waits for every other client, all on one lock',
             'a `ConcurrentHashMap` of buckets, and a lock per bucket'],
            ["handle a new client's first request", '`if (!map.containsKey(id)) map.put(id, ...)`',
             'two threads each create a bucket, and the client gets double',
             '`computeIfAbsent`: find-or-create as one atomic step'],
        ], cls='derive')
        + w.xy([
            ('A `Bucket` interface', 'an enum and a switch', 'a new way of counting is a new class, '
             'and no existing code is edited (open/closed).'),
            ('A lock per bucket', 'one lock for the limiter', "score-widget's burst never slows "
             'fantasy-app down.'),
            ('Time handed in', 'time read inside', 'every test runs in microseconds and gives the '
             'same answer on every run.'),
            ('Records for `Limit` and `Decision`', 'classes with setters', 'they cannot change '
             'after they are made, so any thread can share them without a lock.'),
            ('Constructor injection', 'a Singleton', 'each test builds its own limiter, and nothing '
             'global leaks from one test into the next.'),
        ])
        + w.md('''
        ## Left out on purpose

        - **No Singleton.** The server makes one limiter at startup and hands it to the API: one
          instance, without a global that tests would share.
        - **No abstract base class for buckets.** The ways of counting share a question, not code.
        - **No events or listeners.** Nobody needs to hear about refusals yet. If they ask for
          metrics, a counter is enough (the check step shows where it goes).

        ## The order to type it

        So that it compiles at every point, each class uses only classes typed before it:

        1. `Decision`, `Limit`, `RateLimiter`: the answer, the limit, the question
        2. `Clock`, `SystemClock`, `ManualClock`: time
        3. `Bucket`, `TokenBucket`: counting one client
        4. `Plan`, `Plans`, `BucketFactory`: which limit, and making buckets
        5. `ClientRateLimiter`: it all meets here
        6. `Main`: run it, including a 100-thread race
        7. `RateLimiterTest`: prove every promise

        The next seven steps follow this order.
        '''))


# ===================================================================================== build
def b1(w):
    return dict(id='answer', group=B, stage='Build · 1 of 7', nav='The answer, the limit', title='What the API gets back', body=
        w.strip(now=['Decision', 'Limit', 'RateLimiter'])
        + w.md('''
        Start where the API starts: the question and the answer. Two records and an interface, and
        no logic yet. Everything later returns a `Decision` and reads a `Limit`, so these come first.
        ''')
        + w.code(['Decision.java', 'Limit.java', 'RateLimiter.java'])
        + w.run('B1Demo', note='a tiny program that uses only these three types')
        + w.javas(
            w.java('record', '`record Limit(int capacity, long periodMillis)` is a class whose '
                   'fields are set once and never change. Java writes the constructor, the '
                   'accessors (`limit.capacity()`, no `get`), `equals`, `hashCode` and `toString` '
                   '(the first line of the output). An object that never changes can be shared by '
                   'any number of threads without a lock.'),
            w.java('compact constructor', '`Limit { ... }`, with no parameter list, runs inside '
                   'the constructor Java writes, before the fields are set: the place to reject '
                   'bad values. `new Limit(0, 1_000)` fails right there, at startup, instead of '
                   'dividing by zero inside a bucket later.'))
        + w.asks([
            ('Why `retryAfterMillis`, when the header is in seconds?',
             'The core keeps the exact number. The API rounds up when it writes the header: 200 ms '
             'becomes `Retry-After: 1`.'),
            ('Why an interface with only one class behind it?',
             'The API is written against `RateLimiter`, so follow-ups swap in a Redis limiter (8) '
             'or a shadow limiter (5) without touching the API. That is dependency inversion: the '
             'caller depends on the question, not on who answers it.'),
            ('Why not return a boolean and throw when refused?',
             'A refusal is a normal answer, not an error: during a retry storm most answers are '
             'refusals. Exceptions are slow to build, and a boolean cannot carry the retry time.'),
        ]))


def b2(w):
    return dict(id='time', group=B, stage='Build · 2 of 7', nav='Time', title='Where time comes from', body=
        w.strip(now=['Clock', 'SystemClock', 'ManualClock'])
        + w.md('''
        A token bucket is arithmetic on time. If the bucket read the system clock itself, the only
        way to test "retry in 80 ms" would be to sleep 80 ms, and the test would fail whenever the
        machine is slow. So time becomes something the limiter is handed, like any other
        dependency: the real clock in production, a manual one in tests.
        ''')
        + w.code(['Clock.java', 'SystemClock.java', 'ManualClock.java'])
        + w.run('B2Demo')
        + w.java('volatile', 'A thread may keep a field in a CPU cache and not see another '
                 "thread's write for a long time. `volatile` makes every write visible to every "
                 'later read, on any thread. It does not make `now += millis` one step: that is a '
                 'read and then a write, and two writing threads could interleave them. Here only '
                 "the test's own thread writes, so `volatile` is enough.")
        + w.asks([
            ('Why `nanoTime` and not `currentTimeMillis`?',
             '`currentTimeMillis` is the wall clock. When the machine corrects its time it can jump '
             'back, and a bucket would see time running backwards. `nanoTime` only moves forward. '
             'Its zero point means nothing, which is fine: we only ever subtract two readings.'),
            ('Is a `Clock` interface over-engineering?',
             'It is the difference between tests that sleep and tests that do not. With it, the '
             'whole test file runs in well under a second, and gives the same answer every time.'),
        ]))


def b3(w):
    return dict(id='bucket', group=B, stage='Build · 3 of 7', nav='The bucket', title='Counting one client: the token bucket', body=
        w.strip(now=['Bucket', 'TokenBucket'])
        + w.md('''
        The heart of it. A bucket is told the time, adds what that time earned, then either takes
        a token or says how long to wait. `Bucket` is the question every way of counting answers;
        `TokenBucket` is our answer. Read the comments: they carry the explanation.
        ''')
        + w.code(['Bucket.java', 'TokenBucket.java'])
        + w.md('''
        The trace from the counting step, run against the real class. The bucket needs no clock
        and no limiter to be tested: it is simply told the time.
        ''')
        + w.run('B3Demo')
        + w.md('''
        ## Why `synchronized`

        Refill, check and take must happen as one step. Here is what happens when they don't:
        ''')
        + w.pair(w.asc('''
{r}✗ without synchronized{/}
  one token left, two requests at once

  thread A           thread B
  refill: 1.0
  1.0 >= 1? yes      refill: 1.0
  tokens = 0.0       1.0 >= 1? yes
  allowed            tokens = 0.0
                     allowed

  {y}B read 1.0 before A wrote 0.0{/}
  {r}✗ one token, two requests{/}
''', 'bad'), w.asc('''
{g}✓ with synchronized{/}
  B waits until A leaves the method

  thread A           thread B
  refill: 1.0        {d}waiting for the{/}
  1.0 >= 1? yes      {d}bucket's lock{/}
  tokens = 0.0
  allowed
                     refill: 0.0
                     0.0 >= 1? no
                     retry in 200 ms
  {g}✓ one token, one request{/}
''', 'good'))
        + w.java('synchronized', 'Only one thread at a time can be inside a `synchronized` method '
                 "of the same object. The lock here is the bucket itself, so each client has its "
                 'own lock, and clients never wait for each other. The lock is released when the '
                 'method returns or throws. It also makes the writes visible: the next thread to '
                 'take the lock sees `tokens` exactly as the last one left it.')
        + w.asks([
            ('Why is `tokens` a double?',
             '120 ms earns 0.6 of a token. A `long` would make that 0, and because '
             '`lastRefillMillis` moves on anyway, the 0.6 would be lost for good: a client '
             'sending every 150 ms would get its first 5 requests and then nothing, ever. Build '
             'step 7 shows the test that catches this.'),
            ('Why not a background thread that adds tokens?',
             'One timer per client is a million timers for a million clients. Working the tokens '
             'out when a request arrives gives the same number, in O(1), with no threads.'),
            ('Why `synchronized` and not an `AtomicLong`?',
             'Two fields change together: `tokens` and `lastRefillMillis`. An atomic variable '
             'guards one value. The lock-free way puts both in one immutable object and swaps it '
             'with `AtomicReference.compareAndSet` in a retry loop: possible, harder to read, and '
             'faster only when many threads hit the same client. The lock is held for a few '
             'arithmetic steps: a whole call takes about 35 ns (measured on one thread).'),
            ('Why cap the refill at the capacity?',
             'A client quiet for an hour would otherwise save 18,000 tokens and could send them '
             'all at once. The cap is what makes 5 the biggest burst.'),
        ]))


def b4(w):
    return dict(id='limits', group=B, stage='Build · 4 of 7', nav='Limits and the factory', title='Which limit, and who makes the bucket', body=
        w.strip(now=['Plan', 'Plans', 'BucketFactory'])
        + w.md('''
        Two small jobs the limiter should not do itself. `Plans` answers "which limit does this
        client get?". `BucketFactory` answers "make a bucket for this limit". The limiter only asks.
        ''')
        + w.code(['Plan.java', 'Plans.java', 'BucketFactory.java'])
        + w.run('B4Demo')
        + w.javas(
            w.java('method reference', '`TokenBucket::new` is TokenBucket\'s constructor, used as '
                   'a value. It fits `BucketFactory` because the constructor takes a `Limit` and a '
                   '`long` and gives back a `TokenBucket`, which is a `Bucket`. The same thing as a '
                   'lambda: `(limit, now) -> new TokenBucket(limit, now)`. `@FunctionalInterface` '
                   'makes the compiler check there is exactly one abstract method, which is what a '
                   'lambda needs.'),
            w.java('EnumMap and ConcurrentHashMap', '`EnumMap` is a map for enum keys, backed by '
                   'an array: small and fast. `limitOf` is filled in the constructor and only read '
                   'after that, so it needs no lock (the field is `final`, and `Plans` is handed to '
                   'nobody before it is built). `planOf` changes while requests run, so it is a '
                   '`ConcurrentHashMap`: many threads can read and write it at once, safely.'))
        + w.asks([
            ('Why is `Plans` a class and not an interface?',
             'There is one source of limits so far. Follow-up 4 adds a second (limits per '
             'endpoint) and then pulls out the one method the limiter needs, `limitFor`, as an '
             'interface. An interface earns its place when a second answer to the question exists, '
             'or surely will, as with counting and time.'),
            ('Why a factory at all? The limiter could call `new TokenBucket`.',
             'Then the limiter would decide how to count. With the factory handed in, switching to '
             'a sliding window is one changed line where the objects are wired (follow-up 1), and '
             "the limiter's code does not change."),
        ]))


def b5(w):
    return dict(id='limiter', group=B, stage='Build · 5 of 7', nav='The limiter', title='The class the API calls', body=
        w.strip(now=['ClientRateLimiter'])
        + w.md('''
        Now the pieces meet. The limiter reads the time once, finds or creates the client's bucket,
        and asks it. It holds no counting logic and no limits: those belong to the objects it was
        handed.
        ''')
        + w.code(['ClientRateLimiter.java'])
        + w.md('''
        ## Why `computeIfAbsent`

        The first idea for "find it, or create it" is to look, then put. Two threads can both
        look before either puts:
        ''')
        + w.asc('''
{r}✗ first idea: look, then put{/}

  Bucket b = buckets.get(id);
  if (b == null) {
      b = factory.create(plans.limitFor(id), now);
      buckets.put(id, b);
  }

  thread A: news-app's 1st request       thread B: news-app's 2nd, same instant
  get → null                             get → null
  create bucket A: 5 tokens              create bucket B: 5 tokens
  put A, take 1 from A                   put B {y}(replaces A){/}, take 1 from B
  {r}✗ A's token came from a bucket the map no longer holds: news-app can get 6 where the
    limit is 5, and with 16 threads, up to 16{/}

{g}✓ computeIfAbsent: look, create and put are one step for that key. B waits, then gets A.{/}
''')
        + w.javas(
            w.java('computeIfAbsent', '`map.computeIfAbsent(key, fn)` returns the value for `key`. '
                   'If there is none, it calls `fn` to make one and stores it, all as one atomic '
                   'step. Other threads asking for the same key wait, then get the same value. Keep '
                   '`fn` short and never touch the map from inside it: it runs while the map holds a '
                   "lock on that key's part of the table."),
            w.java('lambdas and captured variables', '`id -> factory.create(plans.limitFor(id), '
                   'now)` uses `now`, a local variable from outside the lambda. That is allowed '
                   'because `now` is never reassigned (it is "effectively final"). The lambda runs '
                   "only on a client's first request."))
        + w.asks([
            ('Does `computeIfAbsent` lock the whole map?',
             "No. It locks one bin of the table (the key's slot), and only while creating. For a "
             'client that already has a bucket, it is a plain read with no lock at all.'),
            ("Why read the clock outside the bucket's lock?",
             'Reading the time is not part of check-and-take, so it stays out of the lock. A '
             'thread that read the clock earlier but gets the lock later passes an older time; the '
             'refill ignores time that goes backwards (`elapsed <= 0`), so that is harmless.'),
            ('What if `clientId` is null?',
             '`ConcurrentHashMap` throws `NullPointerException` for a null key. The API should '
             'reject a request with no client id (401) before it gets here.'),
        ]))


def b6(w):
    return dict(id='run', group=B, stage='Build · 6 of 7', nav='Run it', title='Run it', body=
        w.strip(now=['Main'])
        + w.md('''
        `Main` wires the objects the way a server would at startup. Only the clock is manual, so
        every run prints the same numbers. First the wiring and some requests from three clients:
        ''')
        + w.part('Main.java', r'^// Wires', r'System\.out\.printf\("%4d', plus=2, label='Main.java',
                 note='wiring, and a few bursts')
        + w.md('''
        Then the race: 100 threads send one request each for fantasy-app, all at the same instant.
        Its limit is 50, and the clock is frozen, so no token comes back during the race: exactly 50
        must pass.
        ''')
        + w.part('Main.java', r'^    // 100 threads', None, label='Main.java', note='the race')
        + w.run('Main')
        + w.md('''
        - **score-widget**: 5 allowed, then refused with "retry in 200 ms".
        - **fantasy-app** has its own bucket of 50: score-widget's refusals don't touch it.
        - **cricket-blog** was never set up, so it is on FREE.
        - **300 ms later**, score-widget has earned 1.5 tokens: one request passes, and the next
          must wait 100 ms for the missing half.
        - **The race**: 100 threads at once, exactly 50 pass. Run it again: still 50.
        ''')
        + w.javas(
            w.java('CountDownLatch', 'A starting gun. Every thread calls `start.await()` and '
                   'blocks; `start.countDown()` releases them all at once. Without it, the first '
                   'threads would finish before the last ones started, and nothing would actually '
                   'race.'),
            w.java('ExecutorService and AtomicInteger', 'The pool runs submitted tasks on its '
                   'threads; `shutdown()` takes no new tasks and `awaitTermination` waits for the '
                   'running ones. `AtomicInteger.incrementAndGet()` adds 1 as one indivisible step, '
                   'so 100 threads can count together. A plain `int` with `++` would lose counts.'))
        + w.asks([
            ('Why does the task `return null`?',
             'A lambda that returns a value is a `Callable`, and a `Callable` may throw checked '
             'exceptions such as the `InterruptedException` from `await()`. A `Runnable` may not, '
             'so it would need a try/catch.'),
        ]))


def b7(w):
    t = 'RateLimiterTest.java'
    return dict(id='tests', group=B, stage='Build · 7 of 7', nav='Tests', title='Prove it: tests, and breaking the code on purpose', body=
        w.strip(now=['RateLimiterTest'])
        + w.md('''
        One test for each promise in the requirements. Plain Java with a small `check` helper, so
        it runs anywhere, including an interview editor with no JUnit. Every test builds a fresh
        limiter on a manual clock. The test names are the promises:
        ''')
        + w.part(t, r'^// One test per promise', r'System\.exit\(1\);', plus=2, note='the runner')
        + w.md('Four tests of behaviour, driven by the manual clock:')
        + w.part(t, r'^    // FREE: 5 a second', r'a client nobody set up gets FREE', plus=1,
                 note='behaviour')
        + w.md('''
        Two tests of threads. Each uses far more requests than tokens and a frozen clock, so any
        request that sneaks through shows up as a count above the limit.
        ''')
        + w.part(t, r'^    // A frozen clock and far more', r'exactly 10,000 allowed, got', plus=1,
                 note='races')
        + w.part(t, r'^    // ---- helpers', None, note='helpers')
        + w.run('RateLimiterTest')
        + w.md('''
        ## Break it on purpose

        A test you have never seen fail proves little. The build that made this page takes the
        core, makes each change below to a copy of it, runs the tests, and checks that the right
        test fails. Each race test ran ten times.
        ''')
        + w.mutant_table()
        + w.java('from plain Java to JUnit', 'With JUnit 5, each test method gets `@Test`, '
                 '`check(ok, what)` becomes `assertTrue(ok, what)`, and the IDE is the runner. The '
                 'tests themselves stay the same.')
        + w.asks([
            ('How do you test code that uses threads?',
             'Many threads, a latch so they start together, a frozen clock so no token comes back, '
             'and far more requests than tokens. Then assert the exact count. A race that lets '
             'extra requests through shows up as a count above the limit.'),
            ('Why 16 threads and 2,000 requests each, not 2 threads?',
             'The race window is a few nanoseconds wide. Many threads and many attempts make the '
             'bad interleaving happen on every run, not once in a thousand.'),
            ('Why is the clock frozen in the race tests?',
             'If time moved, some extra requests could pass legitimately, and "exactly 10,000" '
             'would no longer be a fixed number.'),
        ]))


def holds(w):
    return dict(id='holds', group=B, stage='Build · done', nav='Why it holds up', title='Why it holds up: threads, principles, cost', body=
        w.md('''
        Everything an interviewer can probe about the core, in one place: what threads share and
        what guards it, which principles the code follows and where, and what it costs.

        ## What threads share, and what guards it
        ''')
        + w.table(['State', 'Who touches it', 'Guarded by'], [
            ['the `buckets` map', 'every request thread',
             '`ConcurrentHashMap`: `computeIfAbsent` on a first request; reads take no lock'],
            ["one bucket's `tokens` and `lastRefillMillis`", "requests for that client",
             '`synchronized` on that bucket'],
            ['`planOf` in Plans', 'requests read it; sign-ups write it', '`ConcurrentHashMap`'],
            ['`limitOf` in Plans', 'read only, after the constructor',
             '`final`, and filled before anyone else sees Plans'],
            ['`Limit`, `Decision`', 'anyone', 'nothing needed: records never change'],
            ["ManualClock's `now`", 'the test writes; request threads read', '`volatile`'],
        ], cls='kv')
        + w.md('''
        ## Why it cannot deadlock

        A deadlock needs a thread that holds one lock while waiting for another. Here a thread
        holds at most one lock, one bucket's, for a few arithmetic steps, and calls nothing
        outside the bucket while it holds it. (`computeIfAbsent`'s own lock is held only while a
        bucket is created, and creating takes no other lock.)

        ## What it costs

        - **Time:** O(1) a request: one map lookup and a little arithmetic. Measured on one thread:
          about 35 ns a call. Eight threads on eight different clients run in parallel.
        - **Memory:** two numbers and a map entry per client, about 80 bytes plus the client id
          (measured). A million clients is roughly 100 MB, which is why follow-up 6 forgets idle
          ones.
        - **Waiting:** only requests for the same client wait for each other, and they must: they
          share one budget.

        ## Design principles, and where they are in the code
        ''')
        + w.table(['Principle', 'Where', 'What it buys'], [
            ['Single responsibility', '`TokenBucket` counts; `Plans` knows limits; `Clock` tells '
             'time; `ClientRateLimiter` connects them', 'a change touches one class'],
            ['Open/closed', 'a new way of counting is a new `Bucket` class and one changed line '
             'of wiring', 'follow-ups 1 and 2 edit no existing class'],
            ['Liskov substitution', 'the limiter never asks which `Bucket` it has; every bucket '
             'keeps the contract: allowed, or refused with a retry time', 'any bucket drops in'],
            ['Interface segregation', 'the API sees one method; the limiter needs one method of '
             'Plans (made explicit in follow-up 4)', "callers don't depend on what they don't use"],
            ['Dependency inversion', 'the API depends on `RateLimiter`; the limiter on `Bucket`, '
             '`BucketFactory` and `Clock`', 'tests hand in fakes, production the real ones'],
            ['Encapsulation', '`tokens` is private; only `tryConsume` changes it, under the lock',
             'nothing outside can break the count'],
            ['Immutability', '`Limit`, `Decision`', 'shared between threads with no lock'],
            ['Composition over inheritance', 'no class extends another; the limiter has buckets',
             'pieces combine without a class tree'],
        ])
        + w.md('''
        ## Patterns: used, and not used

        - **Strategy:** `Bucket`. How to count is chosen by what you hand in.
        - **Factory:** `BucketFactory`. How to make a bucket is decided where objects are wired.
        - **Dependency injection:** every dependency comes in through a constructor.
        - **Decorator:** follow-up 5's `ShadowLimiter` wraps a `RateLimiter` and is one.
        - **Not Singleton:** one limiter is made at startup and handed to the API; tests make
          their own.
        - **Not Observer, State or Builder:** nobody listens for refusals, a bucket has no modes,
          and no constructor takes more than three arguments.
        ''')
        + w.asks([
            ('Your limiter lets 10 through in one second at 5 a second. Is that a bug?',
             'No. A full bucket (5), plus a second of refill (5). The token bucket limits the burst '
             'and the average rate. If they need "at most 5 in any second", count with a log '
             '(follow-up 1).'),
            ("What if the machine's clock jumps backwards?",
             '`SystemClock` uses `nanoTime`, which never goes back. And the refill ignores negative '
             'elapsed time anyway.'),
            ('What happens under a flood of made-up client ids?',
             'Each creates a bucket, so memory grows until the idle sweep (follow-up 6) clears '
             'them. Better, stop them earlier: the API rejects unknown API keys before the limiter '
             'is asked.'),
        ]))


# ================================================================================ follow-ups
def followup(w, s, n, id_, nav, title, ask, src, lands, extra='', after_run='', hole=None,
             javas=(), asks=(), figure=None, before_diff='', first=(), fold=(), fold_note=None):
    body = (w.ask(ask, src=src, label=f'Follow-up {n}' if isinstance(n, int) else 'Also asked')
            + w.strip(snap_=s)
            + w.md(lands)
            + (figure or '')
            + before_diff
            + w.diff(s, first=first, fold=fold, fold_note=fold_note)
            + w.run(CONFIG['DEMOS'][s])
            + (w.md(after_run) if after_run else '')
            + extra
            + (w.box('hole', 'The catch', hole) if hole else '')
            + (w.javas(*[w.java(a, b) for a, b in javas]) if len(javas) > 1 else
               ''.join(w.java(a, b) for a, b in javas))
            + (w.asks(list(asks)) if asks else ''))
    return dict(id=id_, group=F, stage=f'Follow-up · {n} of 8' if isinstance(n, int) else 'Follow-up · extra',
                nav=nav, title=title, body=body)


def f1(w):
    return followup(w, 'f1', 1, 'exact', 'Exact counts', 'Exact counts: a sliding window log',
        'Logins get 5 attempts a minute, and it must be exact: never 6 in any 60 seconds.',
        'Swiggy (2025) asked for a sliding window and a leaky bucket in the same round; Atlassian '
        '(2023) accepts "a token bucket or a sliding window".',
        '''
        How to count is a `Bucket`, so this is one new class, `SlidingWindowLog`, and one changed
        line where the objects are wired: `SlidingWindowLog::new` instead of `TokenBucket::new`.
        Nothing else changes. The log keeps the time of each allowed request, oldest first; a
        request passes if fewer than 5 are inside the last 60 seconds.
        ''',
        after_run='''
        5 tries at 0 s, then one every 12 s. The token bucket earns a token back every 12 s, so it
        lets 9 through in the first minute. The log lets exactly 5, and tells the 6th to come back
        when the first attempt is 60 s old.
        ''',
        hole='Memory. The log keeps one timestamp per allowed request in the window: nothing at 5 a '
             'minute, but 10,000 longs per client at 10,000 an hour. That is why the token bucket '
             'is the default, and the log is for small limits that must be exact, like logins.',
        javas=[('ArrayDeque', 'A double-ended queue on a growable array: add at the back, look at '
                'and remove from the front, all O(1). Better than `LinkedList` (no node object per '
                'entry) and than `Stack` (locks on every call).')],
        asks=[('Can it be exact with less memory?',
               'Not exactly. The sliding window counter keeps two numbers and estimates; the log is '
               'the price of "never more than 5 in any 60 seconds".'),
              ('Why `synchronized` again?',
               '`times` must be checked and added to as one step, for the same reason as the token '
               'bucket.')])


def f2(w):
    return followup(w, 'f2', 2, 'credits', 'Credits', 'Unused requests carry over: credits',
        'A client that uses less than its limit in one second should keep the unused requests as '
        'credits, up to a maximum, and spend them later. It must work with many threads.',
        'Atlassian (2023 and 2025), as the follow-up in its rate limiter round.',
        '''
        Another way of counting, so another `Bucket`: `CreditBucket`. It needs one number more than
        a `Limit` holds, the most credits a client may save, so the factory becomes a lambda that
        supplies it: `(limit, now) -> new CreditBucket(limit, 5, now)`. The limiter still just calls
        `create`. And "many threads" needs nothing new: the limiter already gives each client one
        bucket, and the bucket's methods are `synchronized`.
        ''',
        after_run='''
        The wiring line in the demo is the whole change for the caller:
        `BucketFactory withCredits = (limit, now) -> new CreditBucket(limit, 5, now);`
        ''',
        hole="Savings are real state. In follow-up 6, a quiet client's bucket is dropped once it is "
             'as good as new; a `CreditBucket` never is, because a quiet client has saved credits '
             'that a new bucket would not have. Expiring old credits is a product decision: ask.',
        javas=[('a lambda as a factory', '`BucketFactory` has one method that takes `(Limit, '
                'long)`, so any lambda with those two parameters is one. This lambda also captures '
                'the constant 5: different plans could get different maximums the same way.')],
        asks=[('Is this different from a bigger token bucket?',
               'Barely. A token bucket with capacity 10 that refills 5 a second behaves much the '
               'same: saved tokens are credits. Say so; it shows you see the general idea. '
               "Credits over fixed windows is simply how Atlassian's question is phrased."),
              ('What if a new window starts while a request is being counted?',
               'It cannot: `roll` and the spending happen inside one `synchronized` call.')])


def f3(w):
    return followup(w, 'f3', 3, 'costs', 'Costs', 'Some requests cost more',
        "A request for a whole match's ball-by-ball history costs us five times a live score. "
        'Charge it 5 tokens.',
        'xAI (2026) asked for a per-key limiter where each call has a cost; Cursor (2026) added a '
        'budget in bytes per minute.',
        '''
        The question changes shape: "take one" becomes "take `cost`". So the interfaces change,
        without breaking a single caller: `tryAcquire(clientId, cost)` is new, and the old
        `tryAcquire(clientId)` becomes a `default` method that calls it with 1. Every bucket learns
        to take `cost` tokens and to say how long until `cost` tokens are there. A request that
        costs more than the whole bucket gets a new answer: refused for good.
        ''',
        after_run='''
        At 600 ms there are 3 tokens: the history (5) is refused and told to wait 400 ms for the 2
        missing tokens, while the answer shows the 3 that are there. An export costing 6 can never
        fit in a bucket of 5, and says so instead of sending the client into endless retries.
        ''',
        hole='Cheap requests can starve an expensive one. With 3 tokens and steady live-score '
             'traffic, the history may wait a long time, because every token is gone before 5 add '
             'up. If that matters, let the big request through and let the tokens go negative, so '
             'the requests after it pay the wait. That is how Guava\'s `RateLimiter` works.',
        javas=[('default methods', 'An interface method with a body. Every class that implements '
                'the interface gets it for free, so adding one breaks nobody. It is how Java 8 '
                'added `forEach` to `Iterable` without breaking every collection class.')],
        first=['RateLimiter', 'Bucket', 'TokenBucket', 'Decision', 'ClientRateLimiter'],
        fold=['SlidingWindowLog', 'CreditBucket'],
        fold_note='The same change in the other two buckets, <code>SlidingWindowLog</code> and '
                  '<code>CreditBucket</code>',
        asks=[('Why a default method, and not an overload in each class?',
               'Then every class would write the same one line. The default says it once, in the '
               'interface, which is where "an ordinary request costs 1" belongs.'),
              ('Why a special "never" instead of a very long retry time?',
               'A client told to retry would wait and retry forever. `NEVER` says: this request '
               'will not fit, change it (fetch the history in pages).')])


def f4(w):
    return followup(w, 'f4', 4, 'rules', 'Several rules', 'Several limits at once, all or nothing',
        "The client's plan limit still applies. On top: at most 2 searches a second per client, "
        'and at most 100 requests a second for the whole API. A request passes only if every limit '
        'allows it, and a refused request must not count against any of them.',
        'Cursor (2026): several rules, and "a denied request is counted by no rule". Cloudflare '
        '(2025): global, per path, per user and path. Microsoft (2026): combined limits.',
        '''
        Each limit is a `ClientRateLimiter` we already have, counting by a different key: the client
        id, "client /search", or "*" for everyone. A `Rule` says which requests a limiter covers and
        what key it counts by. `AllRulesLimiter` asks each rule in turn. If one refuses, it gives
        back what the earlier rules took, so a refused request spends nothing anywhere; for that,
        buckets gain `refund`. And the limiter stops depending on `Plans`: it only ever asked
        `limitFor`, so that one method becomes an interface, `LimitLookup`. `Plans` implements it,
        and so can a lambda.
        ''',
        figure=w.fig(figures.rules(), title="The third search, step by step",
                     caption='Every rule sees the same instant. The search rule refuses, so the '
                     "plan rule's token is given back and the global rule is never asked."),
        after_run='''
        The third search is refused by the search rule, and its plan token is given back: the next
        request sees 47 left, not 46. Later, 100 requests from 20 news sites use up the global
        budget, and cricket-blog's first request is refused by the global rule, although its own
        plan has all 5 tokens.
        ''',
        hole='Between taking a token and giving it back, the token is missing for a few '
             'microseconds. Another request from the same client in that moment can be refused '
             'though it would have fit. The error only ever refuses too much, never lets too much '
             'through, so we accept it. The strict fix is two phases: ask every rule whether it '
             'would allow, holding all their locks in a fixed order, then take. More locks, more '
             'waiting.',
        javas=[('Predicate and Function', '`Predicate<Request>` is a function from a request to '
                'true or false; `Function<Request, String>` turns a request into a key. So a rule '
                'is data made of two small functions: `r -> r.endpoint().equals("/search")`.'),
               ('List.copyOf', 'Makes an unmodifiable copy. Whoever built the list of rules cannot '
                'change them afterwards, and many threads can read it with no lock.')],
        first=['Request', 'Rule', 'AllRulesLimiter', 'Bucket', 'TokenBucket', 'LimitLookup', 'Plans',
               'ClientRateLimiter'],
        fold=['SlidingWindowLog', 'CreditBucket'],
        fold_note='<code>refund</code> in the other two buckets',
        asks=[('Why is the global rule last?',
               'Its one bucket is shared by every client, so it is the busiest lock in the system. '
               'Last, it is reached only by requests every other rule allowed.'),
              ('Why is `LimitLookup` a separate interface?',
               'The search rule has one limit for every key: `key -> Limit.perSecond(2)`. A whole '
               '`Plans` object would be noise. The limiter depends only on the question it asks: '
               'interface segregation.'),
              ('Which "remaining" goes in the header?',
               'The smallest across the rules: the tightest one decides when the client is next '
               'refused.')])


def f5(w):
    return followup(w, 'f5', 5, 'live', 'Live limits', 'Change limits while it runs, safely',
        'Ops want to cut FREE from 5 to 3 a second, without a restart. And before it goes live, '
        'they want to know whom it would hurt.',
        "Stripe's engineering blog (2017) describes launching every new limiter this way: in a "
        'dark mode that only counts, before it refuses anyone.',
        '''
        Two parts. **Live changes:** `Plans.setLimit` changes a plan's limit, and the limiter
        notices on each client's next request, because every bucket now remembers the limit it was
        built for. A stale bucket is replaced with `compute`, atomically. **The dry run:**
        `ShadowLimiter` is itself a `RateLimiter` that wraps two: a live one that decides, and a
        candidate that is only asked. It counts what the candidate would have refused. The API is
        handed the shadow and cannot tell the difference.
        ''',
        after_run='''
        The shadow run allows all 5 of score-widget's requests, and reports that the new limit
        would have refused 2. After `setLimit`, the next request builds a bucket for 3 a second: 3
        pass, and the 4th must wait 334 ms (1,000 / 3, rounded up).
        ''',
        hole="A replaced bucket starts full, so every client whose limit changes can burst once "
             'more. To avoid it, carry the tokens over when swapping: `min(old tokens, new '
             'capacity)`. And for a moment, two threads can disagree: one that read the old limit '
             'just before the change can swap the old bucket back, and the next request swaps it '
             'forward again. It settles within microseconds; a version number on each change '
             'rules it out.',
        javas=[('compute', '`map.compute(key, (k, old) -> ...)` stores whatever the function '
                'returns, as one atomic step for that key. Like `computeIfAbsent`, but it also sees '
                'the value that is there, so it can keep it or replace it.'),
               ('LongAdder', 'A counter built for many writers: each thread adds to its own cell, '
                'and `sum()` adds up the cells. Faster than `AtomicLong` when many threads '
                'increment and few read.')],
        first=['Plans', 'ClientRateLimiter', 'ShadowLimiter'],
        asks=[("Why not change the existing bucket's capacity in place?",
               "The bucket's fields are final, and its arithmetic assumes one rate. Replacing it "
               'keeps `TokenBucket` simple and makes the change a single atomic swap.'),
              ('Why did `limitOf` become a `ConcurrentHashMap`?',
               'It used to be written once and then only read. Now ops write it while requests read '
               'it, and an `EnumMap` gives no guarantee that readers ever see the new value.'),
              ('Which pattern is `ShadowLimiter`?',
               'Decorator: it implements `RateLimiter`, holds `RateLimiter`s, and adds behaviour '
               '(counting) without changing the class it wraps.')])


def f6(w):
    return followup(w, 'f6', 6, 'idle', 'Idle clients', 'A million clients: forget the idle ones',
        'We have a million clients, and most call once a day. Your map keeps a bucket for every '
        'client, forever.',
        'Asked of any design that keeps a map per client.',
        '''
        A token bucket left alone for one full refill period is full again, exactly like a new one.
        Forgetting it loses nothing: the next request creates the same bucket. So buckets learn
        `isIdle`, a `default` method that answers "never" for buckets that cannot tell, and the
        limiter gets `evictIdle`, which a timer runs every minute. A request never pays for the
        sweep.
        ''',
        after_run='''
        10,000 clients called once; 1,000 ms later every one of their buckets is full again, so the
        sweep removes all 10,000 and keeps score-widget's, which was used 100 ms ago.
        ''',
        hole='The sweep and a request can meet. A request fetches an idle, full bucket; before it '
             'takes a token, the sweep removes that bucket from the map. The request spends from '
             'the removed bucket, and the next request creates a new full one: for that instant '
             'the client had two buckets\' worth. It needs a returning client and a sweep in the '
             'same microsecond, and costs one extra burst at most. The strict fix: the sweep marks '
             "the bucket retired under the bucket's lock, and a request that meets a retired bucket "
             'looks it up again.',
        javas=[('remove(key, value)', 'Removes the entry only if the key still maps to that exact '
                'value. If a request replaced the bucket in between (follow-up 5), the new one '
                'stays.'),
               ('walking a ConcurrentHashMap', 'Safe while other threads change it: the walk never '
                'throws `ConcurrentModificationException`. It may or may not see changes made '
                'during the walk, which is fine for a sweep. `ScheduledExecutorService` runs it '
                'every minute on its own thread (`startSweeper` in the demo).')],
        first=['Bucket', 'TokenBucket', 'ClientRateLimiter'],
        fold=['SlidingWindowLog'],
        fold_note='<code>isIdle</code> for the sliding window log',
        asks=[('Why not remove idle buckets during requests?',
               'A request would pay for walking the map. A sweep on its own thread keeps every '
               'request O(1).'),
              ('In production, would you write this sweep?',
               "Probably not: a cache library such as Caffeine does it with "
               '`expireAfterAccess(period)`. In the interview, writing the sweep shows you know why '
               'it is safe.')])


def f7(w):
    return followup(w, 'f7', 7, 'waiting', 'Waiting', 'Wait instead of refusing',
        'Our nightly batch job would rather wait its turn than get a 429. Give it a call that '
        'blocks until the request is allowed.',
        'Plaid (2026): queue requests instead of rejecting them, with a bound on the queue.',
        '''
        The limiter already says exactly how long to wait: `retryAfterMillis`. So waiting is a loop
        around `tryAcquire`: ask, sleep that long, ask again, until allowed or past a deadline. It is
        a wrapper, not a change: `Waiting` uses a `RateLimiter` and changes nothing in it. A
        `Semaphore` caps how many callers may wait at once, because every waiting caller holds a
        thread. And sleeping is handed in, like time, so the demo "sleeps" by moving the manual
        clock.
        ''',
        after_run='''
        The first 5 pass at once, then one every 200 ms, exactly when the tokens arrive. A caller
        that will wait only 100 ms for a token 200 ms away is refused at once, without sleeping.
        So is a request that can never fit.
        ''',
        hole='Waiters are not served in order. When a token arrives, whichever waiter asks first '
             'gets it, and one waiter can lose several times in a row. For order, put waiters in a '
             'queue and hand tokens out from the front.',
        javas=[('Semaphore', 'A counter of permits. `tryAcquire()` takes one if there is one, and '
                'returns false at once if not; `release()` gives it back. Here the permits are '
                'seats in a waiting room, released in `finally` so a seat always comes back.'),
               ('InterruptedException', 'If another thread interrupts the sleep, for example at '
                'shutdown, `acquire` stops waiting and passes the exception up instead of '
                'swallowing it.')],
        asks=[('Why never for a web request?',
               'Each waiting request holds a server thread. During a retry storm the threads run '
               'out and the whole API stops. A web request should get its 429 and retry later.'),
              ('Why not sleep a fixed 100 ms and try again?',
               'Too short wastes checks, too long wastes time. The limiter knows the exact wait.')])


def f8(w):
    return followup(w, 'f8', 8, 'redis', 'Many servers', 'Many servers, one budget: Redis',
        "We now run 10 API servers behind a load balancer. fantasy-app's 50 a second must hold "
        'across all of them, not per server.',
        'OpenAI (2026): implement a distributed rate limiter. Anthropic (2026): design one. The '
        "technique, a Lua script in Redis, is in Stripe's engineering blog (2017).",
        '''
        With a map in each server, each server grants the full 50: ten servers, 500 a second. The
        budget has to live in one place every server can reach, Redis, and refill-check-take must
        still be one step. A Lua script gives exactly that, because Redis runs one script at a
        time. `RedisRateLimiter` implements `RateLimiter`, so the API does not change. The script
        uses Redis's own clock, because ten servers have ten clocks, and idle buckets delete
        themselves with `PEXPIRE`.
        ''',
        figure=w.fig(figures.redis(), caption='The same three lines as `TokenBucket`, run inside '
                     'Redis. <code>FakeRedis</code> below plays Redis so the demo runs anywhere.'),
        before_diff=w.asc('''
{r}✗ first idea: each server reads, decides, and writes back{/}   (one token left)

  server 1                        server 2
  HGET tokens → 1                 HGET tokens → 1
  1 >= 1: allow                   1 >= 1: allow
  HSET tokens 0                   HSET tokens 0
  {r}✗ both allowed: build step 3's race, now between machines{/}

{g}✓ one script does all three on the Redis server, which runs one script at a time:
  server 2's script starts after server 1's has finished, sees 0, and refuses{/}
''', 'bad'),
        after_run='''
        Two servers with their own maps grant 60 of fantasy-app's 60 requests; with the bucket in
        Redis, 50. When Redis is unreachable, the scores API fails open (allows) and the login
        limiter fails closed (refuses).
        ''',
        hole='Every request is now a network round trip (well under a millisecond inside one data '
             'centre), and Redis is one place that can fail. So decide, per limiter, what happens '
             'when it is unreachable. Fail open for scores: the limiter going down should not take '
             'the API down with it. Fail closed for logins: a flood of password guesses is worse '
             'than a short outage.',
        javas=[('text blocks', 'A string between `"""` markers can span lines, keeping the Lua '
                'script readable inside the Java file (Java 15 and later).')],
        first=['RedisRateLimiter', 'FakeRedis'],
        asks=[('Is a Redis call per request too slow?',
               'Usually not. For a very busy client, each server can take tokens in batches (a '
               'lease of 10 at a time) and count those locally: fewer calls, slightly less exact.'),
              ('What about Redis Cluster?',
               "A client's bucket is one key, so each script touches one key and runs on one node. "
               'A script that must touch several keys needs them on the same node: put a hash tag '
               'in the key, as in `rl:{fantasy-app}:search`.'),
              ("Why Redis's clock?",
               'Ten servers disagree by a few milliseconds. If each passed its own time, a bucket '
               "could see time go backwards. One clock, Redis's, keeps every refill consistent.")])


def x(w):
    return followup(w, 'x', 'extra', 'cousins', 'Hit counter, logger', 'Two cousins: the hit counter and the logger',
        'Design a hit counter: `hit(timestamp)`, and `getHits(timestamp)` for the last 5 '
        'minutes. / Print a message only if the same message was not printed in the last 10 '
        'seconds.',
        'Hit counter (LeetCode 362): Intuit (2024), Cloudflare (2025), Uber and Apple (2026). '
        'Logger (LeetCode 359): Google (2025).',
        '''
        Both are rate limiters in disguise. The hit counter is a sliding window that only counts:
        300 slots, one per second, so its memory stays the same however heavy the traffic (a log
        would grow with it). The logger is a limiter where every message is a client with a limit
        of 1 per 10 seconds: remember when each message may next be printed.
        ''',
        asks=[('Millions of hits a second, from many threads?',
               'The `synchronized` methods become the bottleneck. Count with a `LongAdder` per slot, '
               'and guard only the rare reset (a new second landing on an old slot) with that '
               "slot's lock."),
              ('And the logger with many threads?',
               'Make the map a `ConcurrentHashMap` and do the check-and-set in one '
               '`compute(message, ...)` call, so two threads cannot both print.'),
              ("The logger's map grows forever.",
               "Same fix as follow-up 6: a sweep removes messages whose next-allowed time has passed.")])


# ================================================================================ remember
def recall(w):
    cards = [
        ('The ask', ['429 with Retry-After, before any work', 'per client; bursts are fine',
                     'FREE 5 a second, PRO 50', '`Decision(allowed, remaining, retryAfterMillis)`',
                     'a refused request spends nothing']),
        ('Counting', ['token bucket: capacity is the burst', '5 a second: a token per 200 ms',
                      'refill: `min(capacity, tokens + elapsed / msPerToken)`',
                      'wait: `ceil((1 - tokens) × msPerToken)`',
                      'not exact per second: up to 10 in one']),
        ('Classes', ['`RateLimiter` ← `ClientRateLimiter`', 'map: client id → `Bucket`',
                     'handed `Plans`, `BucketFactory`, `Clock`', '`TokenBucket` implements `Bucket`',
                     '`Limit`, `Decision`: records']),
        ('Threads', ['`computeIfAbsent`: one bucket per client',
                     '`synchronized` per bucket: clients never wait on each other',
                     'one lock at a time: no deadlock', 'records: share freely',
                     'ManualClock `now`: `volatile`']),
        ('Tests', ['ManualClock: no sleeping', 'one test per promise, six in all',
                   'races: latch, frozen clock, exact count',
                   'break it: no lock, get-then-put, whole tokens, no cap']),
        ('Follow-ups', ['1 log: exact, costs memory', '2 credits: a lambda factory',
                        '3 costs: default methods', '4 rules: refund, `LimitLookup`',
                        '5 live limits: `compute`, shadow decorator',
                        '6 idle: `isIdle`, `remove(key, value)`', '7 waiting: loop, `Semaphore`',
                        '8 Redis: a Lua script is one step']),
    ]
    grid = '<div class="recall">' + ''.join(
        f'<div class="rc"><h4>{t}</h4><ul>' + ''.join(f'<li>{w.inline(i)}</li>' for i in items)
        + '</ul></div>' for t, items in cards) + '</div>'
    return dict(id='recall', group=R, nav='One-screen recall', title='The whole thing on one screen', body=
        w.md('''
        Come back to this a week from now. If every line brings back the code behind it, you are
        ready. If one does not, go back to that step.
        ''')
        + grid
        + w.md('The lines to remember, exactly:')
        + w.snippet('''
tokens = Math.min(capacity, tokens + elapsed / millisPerToken);           // refill
if (tokens >= cost) { tokens -= cost; return Decision.allow((long) tokens); }  // take
long wait = (long) Math.ceil((cost - tokens) * millisPerToken);           // or say when
Bucket b = buckets.computeIfAbsent(id, k -> factory.create(limits.limitFor(k), now));
public synchronized Decision tryConsume(int cost, long nowMillis)         // a lock per bucket
''', label='five lines'))


def practise(w):
    t = w.t.text('RateLimiterTest.java', 'core')
    return dict(id='practise', group=R, nav='Practise', title='Practise: write it yourself', body=
        w.md('''
        Close everything else, and switch this page to **Practise** mode (top right): code and
        answers stay hidden until you ask. Write in your own editor, not on this page.
        ''')
        + w.drill('Drill 1 · The core, from a blank file', 35, '''
        Type it in this order. Tick each part as it compiles.
        ''')
        + w.checks('core', [
            '`Decision`, `Limit` with its check, `RateLimiter`',
            '`Clock`, `SystemClock`, `ManualClock`',
            '`Bucket`, `TokenBucket`: refill, take, and the wait',
            '`Plan`, `Plans`, `BucketFactory`',
            '`ClientRateLimiter` with `computeIfAbsent`',
            '`Main`: the wiring, a burst, and the 100-thread race'])
        + w.md('''
        Then run the tests against your code. A failing test's name tells you which promise you
        broke. (In a single file, only one class may be `public`: remove `public` from
        `RateLimiterTest`, or keep it in its own file.)
        ''')
        + w.copybox(t, 'RateLimiterTest.java', 'the test file from build step 7')
        + w.copybox(w.onefile('core'), 'The whole core in one file',
                    'for an online editor: every type, only `Main` public')
        + w.drill('Drill 2 · Follow-ups, 10 minutes each', 10, '''
        Pick one, write the change against your core, then compare with its step:

        1. Exact counts for logins (sliding window log): the **Exact counts** step
        2. Credits for unused requests: **Credits**
        3. Requests that cost more: **Costs**
        4. Three rules, all or nothing: **Several rules**
        5. Change a limit while running: **Live limits**
        6. Forget idle clients: **Idle clients**
        7. Wait instead of refusing: **Waiting**
        8. Ten servers, one budget: **Many servers**
        ''')
        + w.drill('Drill 3 · Out loud, one minute each', 5, '''
        Why a lock per bucket and not one for the limiter? What goes wrong without
        `computeIfAbsent`? Why is the clock handed in? Is the token bucket exact?
        ''')
        + w.md('''
        ## When

        Today: read, then drill 1. In three days: drill 1 again in 25 minutes, plus three
        follow-ups. In a week: the recall screen, then **Check yourself** without looking.

        ## Your miss log

        After each drill, write down what you missed or got wrong. Next time, read this list first.
        It is kept in this browser.
        ''')
        + w.misslog('misses', 'e.g. forgot the cap in refill; used get/put instead of computeIfAbsent'))


def check(w):
    q = w.runs.out['QuizDemo']
    qc = w.runs.out['QuizCostDemo']
    lines = q.strip().split('\n')
    return dict(id='check', group=R, nav='Check yourself', title='Check yourself', body=
        w.md('''
        Answer each one before you open it. OpenAI's rate limiter round (2026) starts from code
        like the bugs below: find what is wrong, then make it fast.

        ## Predict the output
        ''')
        + w.reveal('score-widget (5 a second) sends 5 requests at 0 ms, then 3 more at 450 ms. What '
                   'are the three answers at 450 ms?',
                   '450 ms earns 2.25 tokens. The first takes one (1.25 left, shown as 1), the '
                   'second takes one (0.25 left), and the third is refused: the missing 0.75 of a '
                   'token takes 150 ms.\n\n<pre class="asc">' + '\n'.join(lines[:3]) + '</pre>')
        + w.reveal('fantasy-app (50 a second) makes one request, is quiet for 10 seconds, then sends '
                   '60 at once. How many pass?',
                   '50. Ten seconds earn 500 tokens, but the bucket keeps at most 50.\n\n'
                   '<pre class="asc">' + lines[3] + '</pre>')
        + w.reveal('With costs (follow-up 3): score-widget spends all 5 tokens at 0 ms, then asks '
                   'for a history (cost 5) at 700 ms. What is the answer?',
                   '700 ms earns 3.5 tokens, so 1.5 are missing: 1.5 × 200 ms = 300 ms. The answer '
                   'shows the 3 whole tokens that are there.\n\n<pre class="asc">'
                   + qc.strip() + '</pre>')
        + w.md('## Spot the bug')
        + w.reveal('Bug 1',
                   w.snippet('''
public Decision tryAcquire(String clientId) {
    long now = clock.nowMillis();
    Bucket bucket = buckets.get(clientId);
    if (bucket == null) {
        bucket = factory.create(plans.limitFor(clientId), now);
        buckets.put(clientId, bucket);
    }
    return bucket.tryConsume(now);
}''') + '\n\nTwo threads that meet a new client both see `null`, both create a bucket, and the '
                   'client gets more than its limit. Fix: `computeIfAbsent`. Build step 7\'s '
                   '"get, then put" row is exactly this change, caught on 10 runs of 10.')
        + w.reveal('Bug 2',
                   w.snippet('''
class ClientRateLimiter implements RateLimiter {
    // ... fields as before
    @Override
    public synchronized Decision tryAcquire(String clientId) {
        long now = clock.nowMillis();
        Bucket bucket = buckets.computeIfAbsent(clientId,
                id -> factory.create(plans.limitFor(id), now));
        return bucket.tryConsume(now);       // and tryConsume is no longer synchronized
    }
}''') + '\n\nIt is correct, and slow: one lock for the whole API, so fantasy-app\'s requests '
                   "queue behind score-widget's. Fix: the lock belongs on each bucket, where the "
                   'shared state is.')
        + w.reveal('Bug 3',
                   w.snippet('''
private void refill(long nowMillis) {
    long earned = (nowMillis - lastRefillMillis) / (long) millisPerToken;   // whole tokens
    tokens = Math.min(capacity, tokens + earned);
    lastRefillMillis = nowMillis;
}''') + '\n\nThe division drops the fraction, and `lastRefillMillis` moves on anyway, so partial '
                   'tokens are thrown away. A client sending every 150 ms gets its first 5 requests, '
                   'then nothing at all (checked: 0 of the next 62 in 10 seconds), when it should '
                   'get 5 a second. Fix: divide as doubles, or move `lastRefillMillis` forward only '
                   'by the time actually turned into tokens.')
        + w.reveal('Bug 4',
                   w.snippet('''
class Plans {
    private final Map<String, Plan> planOf = new HashMap<>();
    void assign(String clientId, Plan plan) { planOf.put(clientId, plan); }
    // ... called by request threads while sign-ups call assign()
}''') + '\n\nA `HashMap` written by one thread while others read it can lose entries or, during '
                   'a resize, return garbage. Fix: `ConcurrentHashMap`.')
        + w.md('## What would you change if...')
        + w.reveal('...the limit must be per IP address, not per API key?',
                   'Only the key: the API passes the IP instead of the client id. The limiter does '
                   'not change, because a key is just a string.')
        + w.reveal('...a customer wants 1,000 an hour and also 20 a second?',
                   'Two rules over the same client, all or nothing: follow-up 4.')
        + w.reveal('...refused requests should count too, to punish retry storms?',
                   'Let a refusal still take a token, so the count can go below zero (down to minus '
                   'the capacity, say). A client that keeps hammering digs itself a deeper hole and '
                   'must go quiet to recover. One change inside `TokenBucket`.')
        + w.reveal('...no bursts at all, just one request every 200 ms?',
                   'Capacity 1, refilling 5 a second: a bucket that holds one token is a steady '
                   'pace. `new Limit(1, 200)` says it directly.')
        + w.reveal('...ops want to see how often each client is refused?',
                   'Wrap the limiter in a decorator that counts refusals in a '
                   '`ConcurrentHashMap<String, LongAdder>`, like `ShadowLimiter` wraps one. The '
                   'limiter itself does not change.')
        + w.md('## The questions they ask')
        + w.reveal('Why a token bucket?',
                   'Bursts up to a set size, then a steady rate, with two numbers per client. A '
                   'fixed window lets twice the limit through at a window edge; a log is exact but '
                   'costs a timestamp per request. It is not exact per second: say so.')
        + w.reveal('What exactly does `synchronized` protect, and why per bucket?',
                   "Refill, check and take on one client's two numbers, as one step. Per bucket, "
                   'because that is where the shared state is: clients never wait for each other, '
                   'and a thread never holds two locks, so there is no deadlock.')
        + w.reveal('What goes wrong without `computeIfAbsent`?',
                   'Two threads meeting a new client each create a bucket; the client gets more '
                   'than its limit. `computeIfAbsent` makes find-or-create one atomic step for that '
                   'key.')
        + w.reveal('How do you test it without sleeping? And the race?',
                   'A `ManualClock` handed in: `advance(120)` is 120 ms, instantly. For the race: 16 '
                   'threads, a latch, a frozen clock and far more requests than tokens, then assert '
                   'the exact count. And break the code on purpose to see each test fail.')
        + w.reveal('What does it cost?',
                   'O(1) time a request, about 35 ns on one thread. About 80 bytes per client plus '
                   'its id, so idle buckets are swept (follow-up 6).')
        + w.reveal('How would it work across 10 servers?',
                   "The bucket moves to Redis, and a Lua script does refill-check-take as one step, "
                   "using Redis's clock. `RedisRateLimiter` implements `RateLimiter`, so the API "
                   'does not change. Decide fail open or fail closed per limiter.')
        + w.reveal('Which SOLID principles does this follow? Point at the code.',
                   'S: `TokenBucket` counts, `Plans` knows limits, `Clock` tells time. O: a new way '
                   'of counting is a new `Bucket` class. L: the limiter never asks which bucket it '
                   'has. I: `LimitLookup` has the one method the limiter needs. D: the limiter is '
                   'handed interfaces through its constructor.')
        + w.reveal('Why no Singleton?',
                   'Tests need fresh limiters, and a global makes them share state. One limiter is '
                   'made at startup and handed to the API: one instance, no global.'))


def pages(w):
    return [p(w) for p in (problem, counting, design, derive, b1, b2, b3, b4, b5, b6, b7, holds,
                           f1, f2, f3, f4, f5, f6, f7, f8, x, recall, practise, check)]
