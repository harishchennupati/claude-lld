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


# ================================================================================ understand
def problem(w):
    return step('problem', U, 'The problem', 'A rate limiter for a cricket-score API', minutes=4, body=
        w.ask('Each customer may make X requests every Y seconds. Implement '
              '`rateLimit(customerId)`. Keep the code simple, but extensible: we will add to it.',
              src="Atlassian's version, as a candidate reported it (2024). Freshworks and Postman "
                  '(2024) ask it as a machine-coding round, Swiggy (2025) in a bar-raiser round; in '
                  '2026 OpenAI, Anthropic, Cursor, xAI and Databricks asked versions of it, with '
                  'the follow-ups at the end of this page.', label='The interviewer')
        + w.md('''
        ## The situation

        We run a public API that serves live cricket scores to other apps: a **score widget** that
        news sites embed, a **fantasy-cricket app** on a paid plan, a few **cricket blogs**, and a
        developer portal where people **sign in** to get their keys. Last week the widget shipped
        a bug, a retry loop that sent 2,000 requests a second, and the API slowed down for
        everyone, including the paying fantasy app.

        So before the API does any work for a request, it asks: *may this request go ahead right
        now?* If yes, the API serves it. If no, it answers at once with **429 Too Many Requests**,
        a **Retry-After** header and the rule that said no, and spends nothing else on it.
        ''')
        + w.fig(figures.flow(), caption='The limiter sits at the front door, before the real work.')
        + w.md('''
        **What this really is:** a rule book, a bucket per key, and one method that charges every
        rule covering a request, or none of them, without two threads ever spending the same
        token.

        ## Ask these first

        Each answer changes something in the code. That is how to tell a useful question from a
        polite one.
        ''')
        + w.table(['You ask', 'Assume they say', 'What it changes'], [
            ['Limit by what: client, IP, endpoint?', 'By client; searches per client too; sign-ins '
             'by IP; and one cap for the whole API', 'Whose budget a request spends is part of '
             'each rule: a key scope.'],
            ['Same limit for everyone?', 'FREE 5 a second, PRO 50, plus a daily quota',
             'Limits come from the plan, not from if-statements.'],
            ['Can a client burst?', 'Yes, up to its limit; sign-ins must be exact',
             'Each rule names its way of counting.'],
            ['Several limits apply: which wins?', 'All must allow; a refused request counts '
             'nowhere', 'All or nothing, with a refund.'],
            ['What does a refused client get?', '429, when to retry, and which rule',
             'The answer is a record, not a boolean.'],
            ['Do some requests cost more?', 'A whole match history costs 5',
             'The cost travels with the request.'],
            ['One server or many?', 'One, for now', 'Buckets in memory, behind a store that '
             'Redis can replace later.'],
            ['What do ops need to see?', 'Who is throttled, and by which rule',
             'Listeners hear every decision.'],
            ['Many requests at once?', 'Yes: a thread pool', 'Thread-safe, and clients never '
             'wait on each other.'],
        ], cls='qs')
        + w.md('''
        ## What we build: the product's limits, as rules
        ''')
        + w.table(['Rule', 'Covers', 'Counts by', 'Limit', 'Counted with'], [
            ['plan', 'requests with a key', 'the client', 'FREE 5/s · PRO 50/s', 'token bucket'],
            ['quota', 'requests with a key', 'the client', 'FREE 10,000/day · PRO 1,000,000/day',
             'fixed window'],
            ['search', '`/search`, with a key', 'client + endpoint', '2/s', 'token bucket'],
            ['login', '`/login` (no key yet)', 'the IP', '5/min, exact', 'sliding window log'],
            ['global', 'every request', 'everyone', '1,000/s', 'token bucket'],
        ])
        + w.md('''
        A request passes only if every rule that covers it allows it, and a refused request spends
        nothing anywhere. The answer says how many requests are left (by the tightest rule), when
        to retry, and which rule refused. It must be correct with many threads, a check must cost
        a few map lookups, and time is handed in so tests never sleep. Left out on purpose: many
        servers sharing one budget, and changing rules while running. Both are follow-ups.

        ## What they grade
        ''')
        + w.table(['', 'SDE-2', 'SDE-3, on top'], [
            ['Design', 'small classes, one job each; Strategy for counting; limits from config',
             'the seams: rules as data, a store Redis can replace, all or nothing'],
            ['Code', 'a correct token bucket; it compiles and runs', 'every algorithm behind one '
             'interface; clean records; no switch on types'],
            ['Threads', 'thread safety you can explain', 'the three named ways it breaks, and '
             'the lock versus lock-free trade-off, measured'],
            ['Tests', 'a burst, a refill, a race', 'broken copies that prove each test works'],
            ['Operations', '', 'metrics, a dry run before a change, fail open or closed'],
        ])
        + w.md('''
        ## The hour

        **A 60-minute LLD round:** 10 minutes on questions and the design on paper, then type the
        round subset: the values, `Clock` and `ManualClock`, `Bucket` and `TokenBucket`,
        `Algorithm` with one constant, `KeyScope`, `LimitPolicy`, `Plans`, the rule and the rule
        book, the store, the limiter, and a `Main` with a burst and the race. Name the rest out
        loud. **A 90-minute machine-coding round:** all of it, plus the tests. Either way, have
        something running by minute 10.
        ''')
        + w.box('note', 'How to use this page',
                '← and → move between steps. The list on the left shows minutes per step; steps '
                'marked *later* are optional. The must-do path is about 2 h 20 of reading, then '
                'the drills. Read it once in **Read** mode; come back in **Practise** mode (top '
                'right), where code and answers stay hidden until you ask.'))


def counting(w):
    return step('counting', U, 'How to count', 'Five ways to count, and why the token bucket', minutes=6, body=
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
        + w.table(['Way to count', 'What it keeps per key', 'Good at', 'The catch'], [
            ['**Fixed window**', 'a counter, and when its window began', 'the simplest; right '
             'for calendar quotas', 'twice the limit across a window edge'],
            ['**Sliding window log**', 'the time of every request in the last period',
             'exact: never more than the limit in any period', 'one entry per request'],
            ['**Sliding window counter**', "this window's count and the last window's",
             'nearly exact, with two numbers', "an estimate: assumes the last window's requests "
             'were spread evenly'],
            ['**Token bucket**', 'tokens, and when they were last topped up',
             'bursts up to a set size, then a steady rate; two numbers', 'not "at most 5 in any '
             'second" (see below)'],
            ['**Leaky bucket**', 'a level that drains at a fixed rate', 'as a meter: the token '
             'bucket in a mirror', 'as a queue it makes callers wait'],
        ])
        + w.xy([
            ('Token bucket', 'fixed window', 'the most that can pass at once is 5, not 10 across a '
             'window edge.'),
            ('Token bucket', 'a sliding window log', 'two numbers per key instead of one timestamp '
             'per request. The log is for small limits that must be exact: sign-ins.'),
            ('Fixed window for the daily quota', 'a token bucket', 'a quota per calendar day IS a '
             'fixed window, and the per-second rules already stop bursts.'),
        ])
        + w.md('''
        Every row becomes a `Bucket` class: the first three we use in the core, the other two in
        [More ways to count](#more).

        ## How the token bucket works

        score-widget is on FREE, 5 a second. The bucket holds at most **5 tokens** (its capacity:
        the biggest burst), and one token comes back every **200 ms**. A request takes a token; if
        none is there, it is refused, and we know exactly when the next token arrives. No timer
        adds the tokens: when a request comes in, the bucket works out what it earned since it
        last looked (a *lazy refill*).
        ''')
        + w.asc('''
  earned  =  elapsed / millisPerToken                  120 ms / 200 ms  =  {a}0.6 of a token{/}
  tokens  =  min(capacity, tokens + earned)            never more than {a}5{/}
  wait    =  ceil((cost - tokens) × millisPerToken)    (1 - 0.6) × 200  =  {a}80 ms{/}
''')
        + w.md("score-widget's bucket through one busy second. The [bucket](#bucket) step prints "
               'these lines from the real class.')
        + w.table(['Time', 'Tokens on arrival (refilled)', 'Request', 'Answer', 'Tokens after'], [
            ['0 ms', '5', '1 to 5', 'allowed: 4, 3, 2, 1, 0 left', '0'],
            ['0 ms', '0', '6', '<span class="no">refused, retry in 200 ms</span>', '0'],
            ['120 ms', '0.6', '7', '<span class="no">refused, retry in 80 ms</span>', '0.6'],
            ['200 ms', '1.0', '8', 'allowed, 0 left', '0'],
            ['2,200 ms', '5 (10 earned, capped at 5)', '7 at once', '5 allowed, 2 refused', '0'],
        ], cls='trace')
        + w.box('why', 'Is it exact?',
                'No. In any 200 ms at most 6 requests pass (5 saved, 1 earned), where a fixed '
                'window lets 10 through across an edge. But over a whole second a client can get '
                '**10**: a full bucket, then the 5 it earns during that second. A token bucket '
                'limits the burst and the average rate, not "at most 5 in any second". When the '
                'rule must be exact, count with a log.')
        + w.asks([
            ('Why not the fixed window everywhere? It is simpler.',
             'It lets twice the limit through across a window edge (the ✗ above). For a daily '
             'quota that edge does not matter; for a per-second rate it is the whole problem.'),
            ('How does the sliding window counter estimate?',
             "Current window's count, plus the previous window's count times the share of it "
             'still inside the last second: at 300 ms, `current + previous × 0.7`. It is wrong '
             "only when the previous window's requests were bunched up. Code in "
             '[More ways to count](#more).'),
        ]))


# ==================================================================================== design
# The derivation: each interviewer push, what it breaks, and the code it leads to.
MOVES = [
    ('"Test that a refused client waits exactly 80 ms"',
     'The clock is read inside, so the test must sleep 80 ms, and fails whenever the machine is '
     'slow. Time becomes a dependency: a `Clock` handed in, the real one in production, a manual '
     'one in tests. **Time handed in, not read inside.**', """
interface Clock { long nowMillis(); }
long now = clock.nowMillis();                     // was: System.currentTimeMillis()"""),
    ('"Tell the client when to retry, and which rule said no"',
     '`false` carries neither. Each bucket answers with a `Decision`, and the limiter with a '
     '`RateLimitResult` that adds which rule refused. **A result record, not a boolean.**', """
record Decision(boolean allowed, long remaining, long retryAfterMillis) { }
RateLimitResult check(RequestContext request);   // was: boolean allow(String clientId)"""),
    ('"PRO gets 50. Searches: 2 a second each. Sign-ins by IP. A daily quota. One cap for '
     'everyone."',
     '`if (plan == PRO) ... else if (endpoint.equals("/search"))` grows with every product '
     'decision. So a rule becomes data: which requests it covers, whose budget it spends (a '
     '`KeyScope`), how much (a `LimitPolicy`, per plan through `PlanLimits`) and how it counts '
     '(an `Algorithm`). The rules sit in a `RuleBook`. **Rules as data, not if-statements.**', """
new RateLimitRule("search", withKey().and(endpoint("/search")), KeyScope.CLIENT_AND_ENDPOINT,
        LimitPolicy.fixed(Limit.perSecond(2)), Algorithm.TOKEN_BUCKET)"""),
    ('"Sign-ins must be exact, and the quota starts again at midnight"',
     "The token bucket's arithmetic is welded into the class. `Bucket` becomes an interface with "
     'three classes, and `Algorithm` names them so a rule can pick one by name, each constant '
     'holding a constructor. **A `Bucket` interface, not a switch.**', """
interface Bucket {
    Decision tryConsume(int cost, long nowMillis);
    void refund(int cost, long nowMillis);
}"""),
    ('"A hundred threads at once"',
     '`synchronized allow` is one lock for the whole API: during the widget\'s retry storm every '
     'fantasy-app request queues behind it. The lock moves into each bucket, and the buckets move '
     'into a `BucketStore` over a `ConcurrentHashMap`, created with `computeIfAbsent`. **A lock '
     'per bucket, not one lock; a store, not a map inside the limiter.**', """
public synchronized Decision tryConsume(int cost, long nowMillis)   // in each bucket
buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis)) // in the store"""),
    ('"A request refused by one rule must not count in the others"',
     'If each rule takes its token on its own, a refused search still costs a plan token. The '
     'limiter charges the rules in order and, when one refuses, gives back what the earlier ones '
     'took. **All or nothing with a refund, not a chain that passes the request along.**', """
for (Bucket spent : charged) {
    spent.refund(request.cost(), now);           // a later rule said no
}"""),
    ('"Send 429 with Retry-After. And ops want to see who is throttled"',
     'HTTP and log lines inside the limiter would tie it to one web framework and one logger. A '
     '`RateLimitFilter` at the front door speaks HTTP; listeners hear every decision, and '
     '`RefusalMetrics` counts refusals. **A filter and listeners, not HTTP and logging in the '
     'limiter.**', """
Response handle(RequestContext request, Function<RequestContext, Response> endpoint)
interface RateLimitListener { void onDecision(RequestContext request, RateLimitResult result); }"""),
]


def derive(w):
    first = w.runs.demo('FirstCut')
    cls = first[first.index('class FirstCutLimiter'):first.index('public class FirstCut ')].strip()
    return step('derive', D, 'How to get there', 'How you get to this design', minutes=8, body=
        w.md('''
        Everyone's first version is one class. Here it is, compiled and run:
        ''')
        + w.snippet(cls, label='FirstCutLimiter.java', note='the 15-minute version')
        + w.run('FirstCut')
        + w.md('''
        It is correct for one rule on one server, and it is what you should have running by
        minute 10. Every step below is one push from the interviewer, what it breaks, and what the
        design becomes.
        ''')
        + ''.join(w.md(f'### {i} · {push}\n\n{why}') + w.snippet(code)
                  for i, (push, why, code) in enumerate(MOVES, 1))
        + w.md('That is the whole design. The next step draws it.')
        + '<details class="more"><summary>The same path as a table</summary>'
        + w.table(['It must', 'First idea', 'What goes wrong', 'What we do instead'], [
            ['know the time', '`System.currentTimeMillis()` inside',
             '"retry in 80 ms" can only be tested by sleeping', 'a `Clock` handed in'],
            ['answer the API', 'return a `boolean`', 'no Retry-After, no rule name',
             '`Decision` per bucket, `RateLimitResult` per request'],
            ['give different limits', 'if-statements on plan and endpoint',
             'every product change edits the limiter', 'rules as data: scope, policy, algorithm'],
            ['count in more than one way', 'the token bucket welded in',
             'exact sign-ins and quotas need other arithmetic', 'a `Bucket` interface; '
             '`Algorithm` names the classes'],
            ['serve many threads', '`synchronized` on the limiter', 'every client waits for '
             'every other', 'a lock per bucket; a `ConcurrentHashMap` store'],
            ["meet a new key's first request", '`get`, then `put` if missing',
             'two threads build two buckets', '`computeIfAbsent`'],
            ['refuse fairly', 'each rule charges on its own', 'a refused request still costs '
             'tokens elsewhere', 'charge in order, refund on a refusal'],
            ['speak HTTP and report', 'inside the limiter', 'tied to one framework and logger',
             'a filter at the door; listeners'],
        ], cls='derive')
        + '</details>'
        + w.md('''
        ## Left out on purpose

        - **Singleton.** The server makes one limiter and hands it on; tests make their own.
        - **A Builder** for a five-field record: a constructor and two static helpers are enough.
        - **Chain of Responsibility** for rules: every rule must allow, and a refusal refunds; that
          is a loop with a rollback list, not a chain that passes the request along.
        - **An abstract base bucket:** the buckets share a question, not code.

        ## The order to type it

        Each step uses only what came before, so it compiles at every point: the values and the
        question; time; the token bucket; two more buckets and the algorithm names; key scopes
        and limits; the rule book; the store; the limiter and its listeners; the front door;
        `Main`; the tests.
        '''))


def design(w):
    return step('design', D, 'The design', 'The design in one picture', minutes=5, body=
        w.md('Here is where the last step ends up. The server wires it once, at startup:')
        + w.snippet('''
// At startup:
RateLimiter limiter = new RuleBasedRateLimiter(ScoreApiRules.build(plans),
        new InMemoryBucketStore(), new SystemClock());
RateLimitFilter api = new RateLimitFilter(limiter);

// For every request:
RateLimitFilter.Response response = api.handle(request, scores::serve);
''', label='the server')
        + w.fig(figures.classes(), title='The classes',
                caption='Five layers: the front door, the limiter, what it is handed, one rule, '
                        'and the buckets that count. Dashed boxes are interfaces.')
        + w.fig(figures.journey(), title="fantasy-app's third search in one second",
                caption='Plan and quota allow it, search refuses, the earlier tokens come back, '
                        'the listener hears it, and the client gets 429.')
        + w.md('## Who does what')
        + w.table(['Class', 'Its one job', 'It changes when'], [
            ['`RateLimitFilter`', 'turn a result into HTTP: 429, 413, headers', 'the web '
             'framework changes'],
            ['`RateLimiter`', 'the question the API asks', 'rarely: it is the contract'],
            ['`RuleBasedRateLimiter`', 'charge every matching rule, or none', 'the way rules '
             'combine changes'],
            ['`RuleBook`, `RateLimitRule`', 'which rules exist, and what each covers',
             'the product adds a limit: data, not code'],
            ['`KeyScope`', 'whose budget a request spends', 'a new kind of key appears'],
            ['`LimitPolicy`, `PlanLimits`, `Plans`', 'how much, from the plan', 'plans or '
             'prices change'],
            ['`Algorithm`, `BucketFactory`', 'how to count, by name', 'a new way of counting'],
            ['`Bucket` and its classes', "count one key's requests", 'the arithmetic changes'],
            ['`BucketStore`', 'where buckets live', 'many servers ([Redis](#redis))'],
            ['`RateLimitListener`', 'hear every decision', 'ops want a new report'],
            ['`Clock`', 'tell the time', 'never: tests hand in a manual one'],
            ['the records', 'carry values between the others', 'a new field is needed'],
        ], cls='who')
        + w.md('''
        The last column is the single responsibility principle made concrete: each reason to
        change lands in one class. And the API depends only on `RateLimiter`, the question, never
        on who answers it: that is dependency inversion.
        '''))


def threads(w):
    return step('threads', D, 'Threads: three breaks', 'Two threads, three ways to break shared data', minutes=4, body=
        w.md('''
        Every thread bug on this page is one of these three. Name it, and the fix is obvious.
        ''')
        + w.pair(w.asc('''
{r}1 · lost update{/}  (read, modify, write)
  one token left, two requests

  thread A            thread B
  reads tokens 1.0
                      reads tokens 1.0
  writes 0.0: allow
                      writes 0.0: allow
  {r}✗ one token, two requests{/}
''', 'bad'), w.asc('''
{r}2 · check, then act{/}
  a new client's first two requests

  thread A            thread B
  get → null
                      get → null
  put bucket A
                      put bucket B
  {r}✗ two buckets: 6 pass, limit 5{/}
''', 'bad'))
        + w.asc('''
{r}3 · stale read{/}  (visibility)          the test moves the clock; a request thread reads it

  test thread                     request thread
  now = 200
                                  reads now → still 0: nothing promises it ever sees 200
  {r}✗ the bucket never refills{/}
''', 'bad')
        + w.table(['The break', 'The fix here', "The fix's limit"], [
            ['lost update', '`synchronized` on the bucket: one thread at a time, and the next '
             'thread sees what the last one wrote', 'every method that touches the fields must '
             'take the same lock'],
            ['check, then act', '`computeIfAbsent`: look, create and store as one step per key',
             'the one step must cover the check and the act; a lock around the put alone does '
             'nothing'],
            ['stale read', '`volatile`: every write is seen by every later read', 'it does not '
             'make `now += 200` one step: that is still read, then write'],
            ['(no break) written once, read forever', '`final` fields and records: once the '
             'constructor ends, every thread sees them', 'only if nothing changes them later'],
        ])
        + w.md('''
        `synchronized` gives both halves: one thread at a time, and visibility. `volatile` gives
        only visibility. An atomic variable gives both for one value; a compare-and-set loop gives
        both for one immutable object ([Lock-free](#lockfree)). This page uses the smallest tool
        that fits and says which break it is fixing.
        '''))


# ===================================================================================== build
def answer(w):
    return step('answer', B, 'The answer', 'What goes in, what comes out', minutes=4, stage='Build · the values', body=
        w.strip(now=['RequestContext', 'Limit', 'Decision', 'RateLimitResult', 'RateLimiter'])
        + w.md('''
        Start where the API starts: a request goes in, an answer comes out. Four records and the
        interface the API calls, and no logic yet. A bad value fails here, at the door, and never
        deep inside a bucket.
        ''')
        + w.code(['RequestContext.java', 'Limit.java', 'Decision.java', 'RateLimitResult.java',
                  'RateLimiter.java'])
        + w.run('AnswerDemo')
        + w.javas(
            w.java('record', '`record Limit(int capacity, long periodMillis)` is a class whose '
                   'fields are set once and never change. Java writes the constructor, the '
                   'accessors (`limit.capacity()`), `equals`, `hashCode` and `toString`. An object '
                   'that never changes can be shared by any number of threads without a lock.'),
            w.java('compact constructor and default method', '`RequestContext { ... }`, with no '
                   'parameter list, runs before the fields are set: the place to reject a bad '
                   'value. `default boolean rateLimit(...)` is an interface method with a body: '
                   'every implementation gets it for free.'))
        + w.asks([
            ('Why validate the cost here?',
             'A cost of 0 or less is a programming error, and a negative cost would add tokens '
             'past the capacity. Rejected at the door, like a bad `Limit`.'),
            ('They asked for `boolean rateLimit(customerId)`. Why a record?',
             'Give them both: `rateLimit` is the default method, one line on top of `check`. The '
             'record is what lets the API send Retry-After and name the rule; a boolean cannot.'),
        ]))


def time_(w):
    return step('time', B, 'Time', 'Where time comes from', minutes=3, stage='Build · time', body=
        w.strip(now=['Clock', 'SystemClock', 'ManualClock'])
        + w.md('''
        Counting requests is arithmetic on time, so time becomes something the limiter is handed.
        In production it is the wall clock; in tests, a clock that moves only when the test says,
        so the whole test file runs in a fraction of a second and never sleeps.
        ''')
        + w.code(['Clock.java', 'SystemClock.java', 'ManualClock.java'])
        + w.run('TimeDemo')
        + w.java('volatile', 'The stale read from the [threads](#threads) step: without it, a '
                 'request thread might never see the test move the clock. It does not make '
                 '`now += millis` one step, so only the test thread writes.')
        + w.asks([
            ('Why not `nanoTime`?',
             '`nanoTime` never jumps, but it knows nothing about midnight, and the daily quota '
             'starts again at midnight. So the wall clock, and buckets that tolerate its jumps: '
             'a jump back freezes refills until the clock catches up; a jump forward refills '
             'early, at most one burst per key. The purist answer is two clocks, a monotonic one '
             'for rates and the wall clock for quotas; one clock is simpler, and the harm is '
             'bounded.'),
        ]))


def bucket(w):
    return step('bucket', B, 'The token bucket', 'Counting one key: the token bucket', minutes=8, stage='Build · counting', body=
        w.strip(now=['Bucket', 'TokenBucket'])
        + w.md('''
        The heart of it. A bucket is told the time and the cost, adds what the time earned, then
        takes the tokens or says how long to wait. `Bucket` is the question every way of counting
        answers; `TokenBucket` is the first answer. The comments carry the explanation.
        ''')
        + w.code(['Bucket.java', 'TokenBucket.java'])
        + w.md('The trace from [How to count](#counting), run against the real class, which is '
               'simply told the time:')
        + w.run('BucketDemo')
        + w.md('## The lost update, and the lock')
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
        + w.md('''
        The lock is the bucket itself, so each key has its own lock and keys never wait for each
        other. The limiter reads the clock *before* it takes this lock, so a slower thread can
        arrive holding an older time; `refill` treats that as no time passing, which is why the
        `elapsed <= 0` guard is there.
        ''')
        + w.xy([('A lock', 'an `AtomicLong`', 'two fields change together, `tokens` and '
                 '`lastRefillMillis`, and an atomic variable guards one. The lock-free way keeps '
                 'both in one immutable object swapped by compare-and-set; [Lock-free](#lockfree) '
                 'builds it and measures both.')])
        + w.java('synchronized', 'Only one thread at a time can be inside a `synchronized` method '
                 'of the same object; the lock is released when the method returns or throws. '
                 'The next thread to take the lock sees the fields as the last one left them.')
        + w.asks([
            ('Why is `tokens` a double?',
             '120 ms earns 0.6 of a token. A `long` would make that 0, and since '
             '`lastRefillMillis` moves on anyway, the 0.6 would be lost for good: a client sending '
             'every 150 ms would get 5 requests and then nothing, ever. The tests catch it.'),
            ('Why not a background thread that adds tokens?',
             'A million clients would need a million timers. Working the tokens out when a '
             'request arrives gives the same number, in O(1), with no threads.'),
        ]))


def count(w):
    return step('count', B, 'Two more buckets', 'Two more ways to count, chosen by name', minutes=5, stage='Build · counting', body=
        w.strip(now=['SlidingWindowLog', 'FixedWindowCounter', 'BucketFactory', 'Algorithm'])
        + w.md('''
        Each rule counts the way its job needs. Sign-ins must be exact, so they get a log of every
        attempt; the daily quota is a calendar day, so it gets a fixed window. `Algorithm` names
        the three for configuration, and each constant holds its bucket's constructor.
        ''')
        + w.code(['SlidingWindowLog.java', 'FixedWindowCounter.java', 'BucketFactory.java',
                  'Algorithm.java'])
        + w.run('CountDemo')
        + w.md('''
        The token bucket would let a sixth sign-in through at 12 s; the log holds the line until
        the first attempt is a minute old. Its price is memory: one entry per allowed request, which
        is nothing at 5 a minute and a lot at 10,000 an hour. That is why the token bucket stays the
        default.
        ''')
        + w.java('method reference', '`TokenBucket::new` is a constructor used as a value. It fits '
                 '`BucketFactory` because it takes `(Limit, long)` and gives back a `Bucket`. And '
                 '`Algorithm` implements `BucketFactory` itself, so `Algorithm.FIXED_WINDOW.create'
                 '(limit, now)` is a factory call with no switch in sight.')
        + w.asks([
            ('The derivation said "not a switch". Why an enum?',
             'The enum is a registry of names for configuration: it holds constructors and never '
             'switches on anything. A new way of counting is a new class and one new line here.'),
            ('Where does the fixed window go wrong?',
             'Across a window edge it lets twice the limit through. For a quota per day that edge '
             'is harmless: the per-second rules still stop any burst.'),
        ]))


def budget(w):
    return step('budget', B, 'Whose budget, how much', 'Whose budget, and how much', minutes=5, stage='Build · rules', body=
        w.strip(now=['KeyScope', 'LimitPolicy', 'Plan', 'Plans', 'PlanLimits'])
        + w.md('''
        Two questions every rule answers. *Whose budget does this request spend?* The client's,
        the IP's, the client's for this endpoint, or everyone's: a `KeyScope`. *How much?* A fixed
        limit, or one that depends on the client's plan: a `LimitPolicy`.
        ''')
        + w.code(['KeyScope.java', 'LimitPolicy.java', 'Plan.java', 'Plans.java', 'PlanLimits.java'])
        + w.run('BudgetDemo')
        + w.md('''
        An interface earns its place when a second answer to its question exists: `LimitPolicy`
        has two on day one (a fixed limit, and limits by plan), as do `Bucket` and `Clock`.
        ''')
        + w.java('EnumMap, a final field, and ConcurrentHashMap', "`PlanLimits`' map is filled in "
                 'the constructor and never written again: a `final` field is seen by every thread '
                 'once the constructor ends (the fourth row on the [threads](#threads) step). '
                 "`Plans`' map changes while requests run, so it is a `ConcurrentHashMap`.")
        + w.asks([
            ('A third plan?',
             'One enum constant, and one entry in each rule\'s `PlanLimits`. No code that reads '
             'limits changes.'),
        ]))


def book(w):
    return step('book', B, 'The rule book', 'One rule, and the rule book', minutes=4, stage='Build · rules', body=
        w.strip(now=['RateLimitRule', 'RuleBook', 'ScoreApiRules'])
        + w.md('''
        A rule puts the parts together: which requests, whose budget, how much, how to count.
        `ScoreApiRules` is the product's limits, written once at startup; reading it top to bottom
        is reading the table on the first step.
        ''')
        + w.code(['RateLimitRule.java', 'RuleBook.java', 'ScoreApiRules.java'])
        + w.run('RuleBookDemo')
        + w.md('''
        Search covers only requests with a key: `withKey().and(endpoint("/search"))`, which is
        why the keyless search above meets only the global rule. Without the `withKey()`, every
        keyless search would share one `anonymous` bucket, and three strangers would use up each
        other's searches. In production a keyless request to an endpoint that needs a key gets
        401 from authentication, before the limiter is asked.
        ''')
        + w.java('Predicate and Function', '`Predicate<RequestContext>` is a function from a '
                 'request to true or false (`request -> request.endpoint().equals("/search")`); '
                 '`KeyScope` holds a `Function<RequestContext, String>`. Rules are data made of '
                 'small functions.')
        + w.asks([
            ('Why is the global rule last?',
             'Its one bucket is shared by every client: the busiest lock in the system. Last, it '
             'is reached only by requests every other rule allowed. The order never changes an '
             'answer, only how often that lock is taken.'),
            ('Why must rule names be unique?',
             'They are part of every bucket key. Two rules named "plan" would share buckets.'),
        ]))


def store(w):
    return step('store', B, 'The store', 'Where buckets live', minutes=6, stage='Build · the store', body=
        w.strip(now=['BucketStore', 'InMemoryBucketStore'])
        + w.md('''
        One bucket per key, made on the key's first request. The limiter only asks the store for
        "the bucket for this key"; the store decides where buckets live, which is what lets
        [Redis](#redis) replace it later without the limiter noticing.
        ''')
        + w.code(['BucketStore.java', 'InMemoryBucketStore.java'])
        + w.md('## Check, then act')
        + w.asc('''
{r}✗ first idea: look, then put{/}

  Bucket b = buckets.get(key);
  if (b == null) {
      b = factory.create(limit, now);
      buckets.put(key, b);
  }

  thread A: news-app's 1st request       thread B: news-app's 2nd, same instant
  get → null                             get → null
  create bucket A: 5 tokens              create bucket B: 5 tokens
  put A, take 1 from A                   put B {y}(replaces A){/}, take 1 from B
  {r}✗ A's token came from a bucket the map no longer holds. Two threads: 6 pass where the
    limit is 5. Sixteen threads racing on the first request: all 16 can pass.{/}

{g}✓ computeIfAbsent: look, create and put are one step for that key. B waits, then gets A.{/}
''')
        + w.run('StoreDemo')
        + w.javas(
            w.java('computeIfAbsent', '`map.computeIfAbsent(key, fn)` returns the value for `key`; '
                   'if there is none, it calls `fn` and stores the result, all as one atomic step '
                   'for that key. Keep `fn` short and never touch the same map inside it.'),
            w.java('putIfAbsent', '`putIfAbsent(key, value)` is atomic too, but the value is built '
                   'before the call, so a bucket is created and thrown away on every hit, and you '
                   'must use the value it returns, not yours: forgetting that is the classic bug.'))
        + w.asks([
            ('Does `computeIfAbsent` lock the whole map?',
             'No: at most one bin of the table, while creating. Since Java 9 it returns an '
             'existing value without the lock only if the key is first in its bin; Java 8 always '
             'locked the bin. `get` never locks, hence the idiom here: `get` first, '
             '`computeIfAbsent` only on a miss.'),
        ]))


def limiter(w):
    return step('limiter', B, 'The limiter', 'The limiter: every rule, or none', minutes=8, stage='Build · the limiter', body=
        w.strip(now=['RuleBasedRateLimiter', 'RateLimitListener', 'RefusalMetrics'])
        + w.md('''
        Now the pieces meet. For each request the limiter reads the clock once, asks the rule book
        which rules cover it, gets each rule's bucket for this request's key, and charges them in
        order. When one refuses, it gives back what the earlier ones took, so a refused request
        spends nothing anywhere. Listeners hear the decision afterwards, holding no lock.
        ''')
        + w.code(['RuleBasedRateLimiter.java', 'RateLimitListener.java', 'RefusalMetrics.java'])
        + w.run('LimiterDemo')
        + w.md('''
        The bucket key has three parts: the rule, whose budget, and the limit. With the limit in
        the key, a client that upgrades from FREE to PRO gets a PRO bucket on its very next
        request, and the old one is never used again.
        ''')
        + w.box('hole', 'The catch',
                'Between taking a token and giving it back, the token is missing for a few '
                'microseconds, so another request from the same client can be refused though it '
                'would have fit, or be told one fewer is left. At most one request\'s worth, for '
                'microseconds, and only ever stricter. We accept it. The strict fix is to ask every '
                'rule first and take afterwards, holding all their locks in a fixed order: more '
                'locks, more waiting.')
        + w.java('CopyOnWriteArrayList and LongAdder', 'Listeners are read on every request and '
                 'added almost never: a copy-on-write list needs no lock to read. `LongAdder` is a '
                 'counter for many writers: each thread adds to its own cell, and `sum()` adds '
                 'the cells up.')
        + w.asks([
            ('Which "remaining" goes in the header?',
             'The smallest across the rules: the tightest one decides when the client is next '
             'refused.'),
            ("Isn't this a Chain of Responsibility?",
             'No. A chain passes a request along until one handler deals with it; here every rule '
             'must allow it, and a refusal undoes the others. That is a loop with a rollback list.'),
        ]))


def door(w):
    return step('door', B, 'The front door', 'The front door: HTTP', minutes=4, stage='Build · the front door', body=
        w.strip(now=['RateLimitFilter'])
        + w.md('''
        The limiter knows nothing about HTTP, and the filter knows nothing about buckets. The
        filter turns a result into a response: 429 with Retry-After in whole seconds, rounded up,
        and the rule's name; 413 when no wait could ever help; otherwise the real work, plus the
        remaining count.
        ''')
        + w.code(['RateLimitFilter.java'])
        + w.run('DoorDemo')
        + w.asks([
            ('Why 413, not 429, for a request that costs too much?',
             'A 429 means "wait and try again", and waiting will never help here: the request '
             'costs more than the whole bucket. 413 says "make it smaller", for example fetch the '
             'history in pages.'),
        ]))


def run_(w):
    return step('run', B, 'Run it', 'Run it', minutes=4, stage='Build · run', body=
        w.strip(now=['Main'])
        + w.md('''
        `Main` wires the objects as the server would at startup, with only the clock manual, so
        every run prints the same. First some requests through the front door:
        ''')
        + w.part('Main.java', r'^import', r'System\.out\.printf\("%4d', plus=2, label='Main.java',
                 note='wiring, and requests from three clients')
        + w.md('Then the race: 100 threads send one request each for fantasy-app at the same '
               'instant, with a frozen clock, so exactly 50 may pass.')
        + w.part('Main.java', r'^    // 100 threads', None, label='Main.java', note='the race')
        + w.run('Main')
        + w.md('Read the output against the rules table: each refusal names its rule, the refused '
               'search spent nothing (47, not 46), and the race lets exactly 50 through, run '
               'after run.')
        + w.java('the race harness', 'A `CountDownLatch` is a starting gun: every thread waits at '
                 '`await()` until `countDown()`. `AtomicInteger.incrementAndGet()` adds one as a '
                 'single step, so 100 threads can count together. The task returns `null` so it '
                 'is a `Callable`, which may throw the `InterruptedException` from `await()`.'))


def tests(w):
    t = 'RateLimiterTest.java'
    return step('tests', B, 'Tests', 'Prove it: tests, and breaking the code on purpose', minutes=8, stage='Build · prove it', body=
        w.strip(now=['RateLimiterTest'])
        + w.md('''
        One test per promise. Plain Java with a small `check` helper, so it runs anywhere,
        including an interview editor with no JUnit. The names are the promises:
        ''')
        + w.part(t, r'^// One test per promise', r'System\.exit\(1\);', plus=2, note='the runner')
        + w.md('Behaviour, on the real rules, driven by the manual clock:')
        + w.part(t, r'^    // ---- behaviour', r'"the 6th: refused by plan"', plus=1, note='the first test')
        + '<details class="more"><summary>The other twelve behaviour tests</summary>'
        + w.part(t, r'^    static void retryTime', r'"and nothing was earned meanwhile"', plus=1,
                 note='behaviour', sol=False)
        + '</details>'
        + w.md('''
        Threads. For the lost update: a frozen clock and far more requests than tokens, so a
        request that sneaks through shows up as a count above the limit. For check-then-act: a
        factory that takes 50 ms to build a bucket holds the race window open, so the bad
        interleaving happens on every run, not once in a thousand.
        ''')
        + w.part(t, r'^    // ---- threads', r'"one bucket for one key, got "', plus=1, note='races')
        + '<details class="more"><summary>The helpers: limiters, requests, spend, together, check</summary>'
        + w.part(t, r'^    // ---- helpers', None, note='helpers', sol=False)
        + '</details>'
        + w.run('RateLimiterTest')
        + w.md('''
        ## Break it on purpose

        A test you have never seen fail proves little. Each row is a real broken copy of the core,
        run against these tests; the build stops unless the named test fails on every run (the
        race tests ran ten times each). Other tests may fail too; the table names the one that
        must.
        ''')
        + w.mutant_table()
        + w.asks([
            ('How do you test code that uses threads?',
             'Many threads, a latch so they start together, a frozen clock so no token comes back, '
             'and far more requests than tokens; then assert the exact count. When the race window '
             'is tiny, widen it on purpose, like the slow factory here. Then break the code on '
             'purpose and watch the test fail.'),
        ]))


def holds(w):
    cost = w.runs.out['CostDemo'].strip().split('\n')
    return step('holds', B, 'Why it holds up', 'Why it holds up: threads, cost, principles', minutes=5, stage='Build · done', body=
        w.md('## What threads share, and what guards it')
        + w.table(['State', 'Who touches it', 'Guarded by', 'Against'], [
            ["the store's map", 'every request thread', '`ConcurrentHashMap`, `computeIfAbsent`',
             'check, then act'],
            ["a bucket's numbers", "requests for that key", '`synchronized` on the bucket',
             'lost update, stale read'],
            ['`Plans`\' map', 'requests read, sign-ups write', '`ConcurrentHashMap`',
             'stale read, a corrupted map'],
            ['`PlanLimits`, `RuleBook`, rules', 'read only', '`final` fields, records',
             '(safe publication)'],
            ['the listener list', 'read per request', '`CopyOnWriteArrayList`',
             'a change during a walk'],
            ['refusal counts', 'every refused request', '`LongAdder` in a `ConcurrentHashMap`',
             'lost update'],
            ["`ManualClock`'s time", 'the test writes, requests read', '`volatile`', 'stale read'],
        ], cls='kv')
        + w.md('''
        ## Why it cannot deadlock

        A deadlock needs a thread that holds one lock while waiting for another. Here a thread
        holds at most one lock at a time: one bucket's, for a few arithmetic steps, calling
        nothing outside the bucket. Listeners run after the decision, holding none.

        ## What it costs

        Measured on the machine that built this page:
        ''')
        + w.asc('\n'.join('  ' + c for c in cost))
        + w.md('''
        A check on `/scores` builds three short key strings and does three map lookups, one per
        rule that covers it. The memory is why [Idle clients](#idle) sweeps buckets that a new one
        would replace exactly.

        ## Design principles, where they are in the code
        ''')
        + w.table(['Principle', 'Where', 'What it buys'], [
            ['Single responsibility', 'each class has one reason to change (the design step\'s '
             'last column)', 'a change touches one class'],
            ['Open/closed', 'a new way of counting is a new `Bucket` and one enum line; a new limit '
             'is a new rule', 'follow-ups add classes, rarely edit'],
            ['Liskov substitution', 'the limiter never asks which `Bucket` it has', 'any bucket '
             'drops in'],
            ['Interface segregation', '`LimitPolicy`, `Clock`, `RateLimitListener`: one method each',
             "callers depend on the question, not on a big class"],
            ['Dependency inversion', 'the API depends on `RateLimiter`; the limiter on `BucketStore`, '
             '`Clock`, listeners', 'tests hand in fakes'],
        ])
        + w.md('''
        ## Patterns: used, and not used

        - **Strategy:** `Bucket`. **Factory:** `Algorithm` / `BucketFactory`. **Repository:**
          `BucketStore`. **Facade:** `RuleBasedRateLimiter`, one call over many rules.
          **Observer:** `RateLimitListener`. **Decorator** (in the follow-ups): `ShadowRateLimiter`.
        - **Not** Singleton, Builder, Chain of Responsibility, or an abstract base bucket: the
          derivation says why.
        ''')
        + w.asks([
            ('What happens under a flood of made-up client ids?',
             'Each creates buckets, so memory grows until the idle sweep clears them. Better: the '
             'API rejects unknown keys before the limiter is asked.'),
        ]))


# ================================================================================ follow-ups
PREV = {'more': ('the core', 'tests'), 'credits': ('More ways to count', 'more'),
        'live': ('Credits', 'credits'), 'idle': ('Live limits', 'live'),
        'waiting': ('Idle clients', 'idle'), 'redis': ('Waiting', 'waiting'),
        'lockfree': ('Many servers', 'redis'), 'cousins': ('Lock-free', 'lockfree')}


def followup(w, s, id_, nav, title, ask, src, lands, minutes, opt=False, extra='',
             after_run='', hole=None, javas=(), asks=(), figure=None, before_diff='',
             first=(), fold=(), fold_note=None):
    pname, pid = PREV[s]
    body = (w.ask(ask, src=src, label='Follow-up' if not opt else 'Follow-up · when you have time')
            + w.md(f'*Builds on:* [{pname}](#{pid}).')
            + w.strip(snap_=s)
            + w.md(lands)
            + (figure or '')
            + before_diff
            + w.diff(s, first=first, fold=fold, fold_note=fold_note)
            + w.run(CONFIG['DEMOS'][s])
            + (w.md(after_run) if after_run else '')
            + extra
            + (w.box('hole', 'The catch', hole) if hole else '')
            + ''.join(w.java(a, b) for a, b in javas)
            + (w.asks(list(asks)) if asks else ''))
    return step(id_, F, nav, title, body, minutes=minutes, opt=opt,
                stage='Follow-up · later' if opt else 'Follow-up')


def more(w):
    return followup(w, 'more', 'more', 'More ways to count', 'More ways to count', minutes=6,
        ask='Code the sliding window counter and the leaky bucket too, and show me how they behave '
            'at a window edge.',
        src='Swiggy (2025) asked for a sliding window and a leaky bucket in the same round.',
        lands='''
        Two more `Bucket` classes and two more `Algorithm` constants: nothing else changes. The demo
        sends the same traffic through all five ways of counting, the counting step's table made
        real.
        ''',
        after_run='''
        Only the fixed window lets 10 through in 6 ms. The counter estimates: 5 hits at 999 ms, and
        at 1,300 ms 70% of that second still counts, so 3.5 are "in the window" and one more fits.
        ''',
        hole='The counter is an estimate. If the previous window\'s requests were bunched at its '
             'end, it lets a few too many through soon after. The leaky bucket here is a meter; as '
             'a queue (requests wait and leave at a fixed rate) it is a different thing, for '
             'smoothing calls you send, not for answering yes or no.',
        asks=[('Which would you pick for a per-second API limit?',
               'The token bucket: bursts up to a set size, then a steady rate, two numbers. The '
               'log where it must be exact, the fixed window for calendar quotas.')])


def credits(w):
    return followup(w, 'credits', 'credits', 'Credits', 'Unused requests carry over: credits',
        minutes=5,
        ask='A client that uses less than its limit in one second should keep the unused requests '
            'as credits, up to a maximum, and spend them later. It must work with many threads.',
        src='Atlassian (2023 and 2025), as the follow-up in its rate limiter round.',
        lands='''
        Another way of counting, so another `Bucket`: `CreditBucket`. It needs one more number than
        a `Limit` holds, the most a client may save, so its `Algorithm` constant is a lambda that
        supplies it. "Many threads" needs nothing new: one bucket per key, and its methods are
        `synchronized`.
        ''',
        hole='Credits ride on fixed windows, the counting step\'s hole: a quiet second, then 10 '
             '(5 + 5 credits) at 1,999 ms and 5 more at 2,000 ms is 15 in a millisecond at "5 a '
             'second". And credits are savings, so this bucket is never idle: forgetting it would '
             'take them away.',
        asks=[('Is this different from a bigger token bucket?',
               'Barely: a token bucket with capacity 10 that refills 5 a second saves unused tokens '
               'the same way, without the edge. Credits over fixed windows is how Atlassian '
               'phrases it; the token bucket is the general idea.')])


def live(w):
    return followup(w, 'live', 'live', 'Live limits', 'Change the rules while it runs, safely',
        minutes=7,
        ask='Ops want to cut FREE from 5 to 3 a second, without a restart. First they want to know '
            'whom it would hurt.',
        src="Stripe's engineering blog (2017) describes launching every new limiter this way: a "
            'dark run that only counts, then the switch.',
        lands='''
        Two parts. **The dry run:** `ShadowRateLimiter` is a `RateLimiter` wrapping two, the live
        one that decides and a candidate that is only asked; it counts, per client, what the
        candidate would have refused. That is the Decorator pattern. **The switch:** the limiter's
        rule book becomes a `volatile` field that `replaceRules` swaps in one write. Because every
        bucket key carries its limit, a changed limit simply gets new buckets.
        ''',
        after_run='''
        The dry run names score-widget, twice. After the switch the next second allows 3, and the
        4th waits 334 ms (1,000 / 3, rounded up). The daily quota did not reset: that rule did not
        change, so its keys and buckets are the same.
        ''',
        hole='A replaced bucket starts full, so a client whose limit changes can burst once more. '
             'The old buckets stay in the store until the [idle sweep](#idle) removes them.',
        javas=[('a volatile reference to an immutable object', 'The `RuleBook` never changes after '
                'it is built, and the field that points to it is `volatile`: a request reads the '
                'field once and sees a whole book, old or new, never half of each. No lock.')],
        asks=[('Why not change the existing buckets in place?',
               "A bucket's fields are final and its arithmetic assumes one rate. New keys for new "
               'limits keep `TokenBucket` simple and the switch a single write.')])


def idle(w):
    return followup(w, 'idle', 'idle', 'Idle clients', 'A million clients: forget the idle ones',
        minutes=5, opt=True,
        ask='We have a million clients, and most call once a day. Your store keeps their buckets '
            'forever.',
        src='Asked of any design that keeps a map per client.',
        lands='''
        A bucket that a new one would replace exactly can go. Each bucket says when that is
        (`isIdle`, a default of "never"), and the store gets `evictIdle`, run by a timer every minute,
        never by a request.
        ''',
        first=['Bucket', 'TokenBucket', 'FixedWindowCounter', 'InMemoryBucketStore'],
        fold=['SlidingWindowLog', 'SlidingWindowCounter', 'LeakyBucket'],
        fold_note='`isIdle` in the other buckets',
        after_run='''
        A token bucket left alone for one refill period is full again, so it goes. A quota bucket
        holds today's count, so it stays until the day is over.
        ''',
        hole='A sweep and a request can meet: the request fetches an idle, full bucket, the sweep '
             'removes it from the map, the request spends from the removed bucket, and the next '
             'request creates a new full one. One extra burst, for a client returning at exactly '
             'that microsecond. The strict fix: the sweep marks the bucket retired under its lock, '
             'and a request that meets a retired bucket looks it up again.',
        javas=[('remove(key, value), and walking a ConcurrentHashMap', '`remove(key, value)` removes '
                'the entry only if the key still maps to that same bucket. Walking the map while '
                'other threads change it is safe: it never throws, and may or may not see changes '
                'made during the walk.')],
        asks=[('In production, would you write this sweep?',
               'Probably not: a cache library such as Caffeine does it with '
               '`expireAfterAccess(period)`. In the interview, writing it shows why it is safe.')])


def waiting(w):
    return followup(w, 'waiting', 'waiting', 'Waiting', 'Wait instead of refusing', minutes=4,
        opt=True,
        ask='Our nightly batch job would rather wait its turn than get a 429. Give it a call that '
            'blocks until the request is allowed.',
        src='Plaid (2026): queue requests instead of rejecting them, with a bound on the queue.',
        lands='''
        The limiter already says how long to wait. So waiting is a loop around `check`: ask, sleep
        exactly that long, ask again, until allowed or the sleeps would pass the caller's limit. A
        `Semaphore` caps how many callers may wait at once, because each one holds a thread.
        ''',
        hole='Waiters are not served in order: when a token arrives, whichever waiter asks first '
             'gets it. For order, queue the waiters and hand tokens out from the front.',
        javas=[('Semaphore', 'A counter of permits: `tryAcquire()` takes one or returns false at '
                'once, `release()` gives it back. Here the permits are seats in a waiting room, '
                'released in `finally` so a seat always comes back.')],
        asks=[('Why never for a web request?',
               'Each waiting request holds a server thread. During a retry storm the threads run '
               'out and the whole API stops. A web request should get its 429.')])


def redis(w):
    return followup(w, 'redis', 'redis', 'Many servers', 'Many servers, one budget: Redis', minutes=8,
        ask="We now run 10 API servers behind a load balancer. fantasy-app's 50 a second must hold "
            'across all of them.',
        src='OpenAI (2026): implement a distributed rate limiter. Anthropic (2026): design one.',
        lands='''
        With a store in each server, each server grants the full 50. The buckets move to Redis
        behind the same `BucketStore` interface, so the limiter does not change. Refill, check and
        take must still be one step, and a Lua script gives exactly that: Redis runs one script at
        a time.
        ''',
        figure=w.fig(figures.redis(), caption='`FakeRedis` below plays Redis, so the demo runs '
                     'anywhere.'),
        before_diff=w.md('''
        The first answer everyone gives is a fixed window: `INCR` a key per client per second and
        `EXPIRE` it. That is two commands (a crash between them leaves a counter that never resets;
        use `SET key 0 EX 1 NX` first, or a script), and it has the window-edge hole. The token
        bucket needs read, refill and write as one step, which no two commands give:
        ''') + w.asc('''
{r}✗ each server reads, decides, and writes back{/}   (one token left)

  server 1                        server 2
  HGET tokens → 1                 HGET tokens → 1
  1 >= 1: allow                   1 >= 1: allow
  HSET tokens 0                   HSET tokens 0
  {r}✗ both allowed: the lost update, now between machines{/}

{g}✓ one script does all three on the Redis server, which runs one script at a time{/}
''', 'bad'),
        first=['RedisBucketStore', 'RedisTokenBucket'],
        fold=['FakeRedis'], fold_note='`FakeRedis`: the stand-in that plays Redis in the demo',
        after_run='''
        Two servers with their own stores grant 60 of 60; with Redis, 50. When Redis is down, the
        scores API fails open and says the whole budget is left, so polite clients do not slow down;
        a sign-in limiter fails closed.
        ''',
        hole='Every check is now a network round trip, and one request with three rules makes three '
             '(one script over all of a request\'s keys would make one, and make all-or-nothing '
             'atomic too). A slow Redis is worse than a dead one: without a call timeout of a few ms, '
             'every request thread waits on the socket and fail-open never triggers, so add a circuit '
             'breaker. And after a restart the script cache is empty: `EVALSHA` answers `NOSCRIPT`, '
             'and the client sends the script again.',
        asks=[("Why Redis's clock?",
               'Ten servers disagree by milliseconds, so a bucket could see time go backwards. '
               '`TIME` before writing inside a script needs Redis 5 or later; on older versions, '
               'pass `now` from the client as an argument: `if now > last` ignores small skews.'),
              ('And Redis Cluster?',
               'Each bucket is one key, so each script runs on one node. A script over several keys '
               'needs them on one node: a hash tag, as in `rl:{fantasy-app}:plan`.')])


def lockfree(w):
    verdict = timing_verdict(w.runs.out['LockFreeDemo'])
    return followup(w, 'lockfree', 'lockfree', 'Lock-free', 'Make it faster: a lock-free bucket',
        minutes=6,
        ask='Profiling shows threads waiting on the bucket lock for our hottest client. Can you '
            'remove the lock?',
        src="OpenAI's rate limiter round (2026) hands you slow code to fix and speed up.",
        lands='''
        Both numbers go into one immutable `State`, held in an `AtomicReference`. A request reads the
        state, computes the next one, and swaps it in with `compareAndSet` only if nobody changed it
        meanwhile; otherwise it reads again and redoes the sums. One more `Algorithm` constant, and
        any rule can use it.
        ''',
        after_run='''
        Same answers, same exact count under the race. Then the timing on the machine that built
        this page. {verdict} Neither result is a rule: every attempt allocates a new `State`,
        failed attempts redo their sums, and an uncontended `synchronized` costs a few
        nanoseconds.
        '''.replace('{verdict}', verdict),
        hole='Measure on your own machine and load. With many more runnable threads than cores, '
             'failed compare-and-sets pile up and the retries can lose. The lock stays the '
             'default until a profile says otherwise; keep the version you can explain.',
        asks=[('What about ABA?',
               'Not here: every state is a new object, so a reference can never come back to an old '
               'value that compares equal.'),
              ('Does `synchronized` hurt with virtual threads?',
               'Not here: the lock is held for nanoseconds and nothing blocks inside it. Pinning '
               'only mattered when a virtual thread blocked while holding a monitor, and it is gone '
               'since JDK 24.')])


def timing_verdict(out):
    """One sentence about the demo's own numbers, so the words always match what was printed."""
    rows = [(int(n), int(lock), int(cas)) for n, lock, cas in re.findall(
        r'(\d+) threads?\s+on one bucket:\s+synchronized\s+(\d+) ns\s+CAS\s+(\d+) ns', out)]
    faster = ['the lock' if lock < cas else 'CAS' if cas < lock else None for _, lock, cas in rows]
    if len(rows) == 2 and faster[0] and faster[0] == faster[1]:
        return f'Here {faster[0]} was faster both times, with one thread and with {rows[1][0]}.'
    said = [f'with {"one thread" if n == 1 else f"{n} threads"}, '
            + (f'{who} was faster' if who else 'a tie') for (n, _, _), who in zip(rows, faster)]
    return ('Here, ' + '; '.join(said) + '.') if said else ''


def cousins(w):
    return followup(w, 'cousins', 'cousins', 'Hit counter, logger', 'Two cousins: the hit counter and the logger',
        minutes=5, opt=True,
        ask='Design a hit counter: `hit(timestamp)`, and `getHits(timestamp)` for the last 5 '
            'minutes. / Print a message only if it was not printed in the last 10 seconds.',
        src='Hit counter (LeetCode 362): Intuit (2024), Cloudflare (2025), Uber and Apple (2026). '
            'Logger (LeetCode 359): Google (2025).',
        lands='''
        Both are rate limiters in disguise. The hit counter is a sliding window that only counts:
        300 slots, one per second, so memory stays the same however heavy the traffic. The logger
        is a limiter where every message is a key with a limit of 1 per 10 seconds.
        ''',
        asks=[('Millions of hits a second, from many threads?',
               'The `synchronized` methods become the bottleneck: count with a `LongAdder` per '
               "slot, and guard only the rare reset (a new second landing on an old slot) with that "
               "slot's lock."),
              ('The logger with many threads?',
               'A `ConcurrentHashMap` and one `compute(message, ...)` call for the check and the set, '
               'so two threads cannot both print.')])


# ================================================================================ remember
def recall(w):
    cards = [
        ('The ask', ['429 + Retry-After + the rule, before any work',
                     'five rules: plan, quota, search, login, global',
                     'all must allow; a refusal counts nowhere', 'the cost travels with the request']),
        ('Counting', ['token bucket: capacity = burst, a token per 200 ms',
                      'refill: `min(capacity, tokens + elapsed / msPerToken)`',
                      'wait: `ceil((cost - tokens) × msPerToken)`',
                      'log: exact, one entry per request; fixed window: quotas',
                      'not exact per second: up to 10 in one']),
        ('The shape', ['filter → limiter → rule book → store → buckets',
                       'a rule = appliesTo + KeyScope + LimitPolicy + Algorithm',
                       'bucket key = rule | scope key | limit',
                       'listeners after the decision']),
        ('Threads', ['lost update → `synchronized` per bucket', 'check, then act → '
                     '`computeIfAbsent`', 'stale read → `volatile`; written once → `final`',
                     'one lock at a time: no deadlock']),
        ('X, not Y', ['time handed in, not read', 'a result record, not a boolean',
                      'rules as data, not ifs', 'a Bucket interface, not a switch',
                      'a lock per bucket, not one', 'refund, not a chain']),
        ('Tests', ['one per promise, 15 in all', 'races: latch, frozen clock, exact count',
                   'ten broken copies, each caught']),
        ('Follow-ups', ['more: counter, leaky bucket', 'credits: a lambda constant',
                        'live: volatile rule book, limit in the key, shadow decorator',
                        'idle: isIdle, remove(key, value)', 'waiting: loop + Semaphore',
                        'redis: one Lua script = one step', 'lock-free: CAS, measured']),
        ('What the tests need', ['`RequestContext.of(client, ip, endpoint)`',
                                 '`new RuleBasedRateLimiter(rules, store, clock)`',
                                 '`ScoreApiRules.build(plans)`, `plans.assign(id, Plan.PRO)`',
                                 '`new ManualClock(0)`, `advance(ms)`',
                                 '`new RuleBook(List.of(new RateLimitRule(...)))`']),
    ]
    grid = '<div class="recall">' + ''.join(
        f'<div class="rc"><h4>{t}</h4><ul>' + ''.join(f'<li>{w.inline(i)}</li>' for i in items)
        + '</ul></div>' for t, items in cards) + '</div>'
    return step('recall', R, 'One-screen recall', 'The whole thing on one screen', minutes=3, body=
        w.md('Come back to this a week from now. If every line brings back the code behind it, you '
             'are ready; if one does not, go back to that step.')
        + grid
        + w.md('The lines to remember, exactly:')
        + w.snippet('''
long elapsed = nowMillis - lastRefillMillis;
if (elapsed <= 0) { return; }                                       // an older time earns nothing
tokens = Math.min(capacity, tokens + elapsed / millisPerToken);     // refill
if (tokens >= cost) { tokens -= cost; return Decision.allow((long) tokens); }   // take
long wait = (long) Math.ceil((cost - tokens) * millisPerToken);     // or say when
bucket = buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));
for (Bucket spent : charged) { spent.refund(request.cost(), now); } // all or nothing
''', label='seven lines'))


def practise(w):
    t = w.t.text('RateLimiterTest.java', 'core')
    return step('practise', R, 'Practise', 'Practise: write it yourself', body=
        w.md('''
        Close everything else and switch this page to **Practise** mode (top right): code and
        answers stay hidden until you ask. Write in your own editor, and skip the comments: they are
        for learning, not for the room.
        ''')
        + w.drill('Drill 0 · The 15-minute version', 15, '''
        `FirstCutLimiter` from the derivation, from memory, running by minute 10.
        ''')
        + w.drill('Drill 1 · The round', 45, '''
        The round subset from the first step. First time, expect 60 minutes; the second time, 45.
        ''', w.checks('round', [
            'the records: `RequestContext`, `Limit`, `Decision`, `RateLimitResult`, and `RateLimiter`',
            '`Clock`, `ManualClock`', '`Bucket`, `TokenBucket`: refill, take, wait',
            '`Algorithm` (one constant), `KeyScope`, `LimitPolicy`, `Plans`',
            '`RateLimitRule`, `RuleBook`', '`BucketStore`, `InMemoryBucketStore` with '
            '`computeIfAbsent`', '`RuleBasedRateLimiter`: the loop and the refund',
            '`Main`: a burst and the 100-thread race']))
        + w.drill('Drill 2 · Machine coding', 90, '''
        Everything, plus the tests. Then run the page's tests against your code: a failing test's
        name tells you which promise you broke. (In one file only one class may be `public`.)
        ''')
        + w.copybox(t, 'RateLimiterTest.java', 'the test file from the [Tests](#tests) step')
        + w.copybox(w.onefile('core'), 'The whole core in one file',
                    'for an online editor: every type, only `Main` public')
        + w.md('''
        ### Drill 3 · Follow-ups

        Start from the code as it was at the step before (`rate-limiter-code/steps/<step>/`), write
        the change, then compare with the step.
        ''')
        + w.timed([
            ('More ways to count: the counter and the leaky bucket', 10, '#more'),
            ('Credits for unused requests', 10, '#credits'),
            ('Live limits: the shadow run and the switch', 15, '#live'),
            ('Many servers: the script and the Redis store', 15, '#redis'),
            ('Lock-free: the compare-and-set bucket', 10, '#lockfree'),
            ('Idle clients: isIdle and the sweep', 10, '#idle'),
            ('Waiting instead of refusing', 10, '#waiting'),
        ])
        + w.drill('Drill 4 · Out loud, one minute each', 5, '''
        The three thread breaks and their fixes. Why a lock per bucket. Why `computeIfAbsent`. Why
        the clock is handed in. Is the token bucket exact? Why all or nothing?
        ''')
        + w.md('''
        ## When

        Today: read, then drills 0 and 1. In three days: drill 1 again, plus two follow-ups. In a
        week: the recall screen, then **Check yourself** without looking.

        ## Your miss log

        After each drill, write down what you missed. Next time, read this first. It is kept in this
        browser.
        ''')
        + w.misslog('misses', 'e.g. forgot the refund loop; used get/put instead of computeIfAbsent'))


def check(w):
    q = w.runs.out['QuizDemo'].strip().split('\n')
    return step('check', R, 'Check yourself', 'Check yourself', minutes=15, body=
        w.md('''
        Answer each one before you open it. OpenAI's rate limiter round (2026) starts from code like
        the bugs below: find what is wrong, then fix it.

        ## Predict the output
        ''')
        + w.reveal('score-widget (FREE, 5 a second) sends 5 requests at 0 ms, then 3 more at 450 ms. '
                   'What are the three answers at 450 ms?',
                   '450 ms earns 2.25 tokens: the first takes one (1.25 left, shown as 1), the second '
                   'takes one (0.25), and the third is refused: the missing 0.75 of a token takes '
                   '150 ms.\n\n<pre class="asc">' + '\n'.join(q[:3]) + '</pre>')
        + w.reveal('fantasy-app (PRO, 50 a second) makes one request, is quiet for 10 seconds, then '
                   'sends 60 at once. How many pass?',
                   '50: ten seconds earn 500 tokens, but the bucket keeps 50.\n\n<pre class="asc">'
                   + q[3] + '</pre>')
        + w.reveal('cricket-blog (FREE) asks for a match history that costs 5, twice: at 0 ms and at '
                   '700 ms. What is the second answer?',
                   '700 ms earns 3.5 tokens, so 1.5 are missing: 1.5 × 200 ms = 300 ms.\n\n'
                   '<pre class="asc">' + q[4] + '</pre>')
        + w.md('## Spot the bug')
        + bug(w, 1, '''
Bucket bucket = buckets.get(key);
if (bucket == null) {
    bucket = factory.create(limit, nowMillis);
    buckets.put(key, bucket);
}
return bucket;''', 'Check, then act: two threads meeting a new key both see `null` and both build a '
            'bucket; the client gets more than its limit. The [Tests](#tests) step\'s "get, then '
            'put" row is exactly this change.', '''
Bucket bucket = buckets.get(key);
if (bucket == null) {
    bucket = buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));
}
return bucket;''')
        + bug(w, 2, '''
@Override
public synchronized RateLimitResult check(RequestContext request) {   // on the limiter
    // ... the same loop, and TokenBucket.tryConsume is no longer synchronized
}''', 'Correct, and slow: one lock for the whole API, so fantasy-app waits behind score-widget. '
            'The lock belongs where the shared numbers are: one per bucket.', '''
public RateLimitResult check(RequestContext request) { ... }          // no lock here
public synchronized Decision tryConsume(int cost, long nowMillis)     // one lock per bucket''')
        + bug(w, 3, '''
private void refill(long nowMillis) {
    long earned = (nowMillis - lastRefillMillis) / (long) millisPerToken;   // whole tokens
    tokens = Math.min(capacity, tokens + earned);
    lastRefillMillis = nowMillis;
}''', 'The division drops the fraction and `lastRefillMillis` moves on anyway, so partial tokens '
            'are thrown away: a client sending every 150 ms gets 5 requests, then none at all '
            '(checked: 0 of the next 62 in 10 seconds).', '''
long elapsed = nowMillis - lastRefillMillis;
if (elapsed <= 0) { return; }
tokens = Math.min(capacity, tokens + elapsed / millisPerToken);     // a double: keeps 0.6
lastRefillMillis = nowMillis;''')
        + bug(w, 4, '''
class Plans {
    private final Map<String, Plan> planOf = new HashMap<>();   // sign-ups write, requests read
}''', 'A `HashMap` written by one thread while others read it can miss entries, show stale values, '
            'or, before Java 8, loop forever during a resize.', '''
private final Map<String, Plan> planOf = new ConcurrentHashMap<>();''')
        + bug(w, 5, '''
private volatile double tokens;          // "volatile fixes threads"

public Decision tryConsume(int cost, long nowMillis) {   // not synchronized
    refill(nowMillis);
    if (tokens >= cost) { tokens -= cost; return Decision.allow((long) tokens); }
    ...''', '`volatile` fixes the stale read, not the lost update: `tokens -= cost` is still read, '
            'then write, and two threads can both pass the check.', '''
public synchronized Decision tryConsume(int cost, long nowMillis) { ... }   // the lock''')
        + bug(w, 6, '''
if (!d.allowed()) {
    result = RateLimitResult.refused(d, rule.name());
    break;                               // the charged buckets keep their tokens
}''', 'No refund: a search refused by the search rule still costs a plan token and a quota token. '
            'The next /scores shows 46 left, not 47; the tests catch it.', '''
for (Bucket spent : charged) {
    spent.refund(request.cost(), now);
}''')
        + bug(w, 7, '''
public synchronized Decision tryConsume(int cost, long nowMillis) {
    ...
    listener.onDecision(request, result);  // told inside the bucket's lock
}''', 'A slow listener now stalls every request for that key, and a listener that calls back into '
            'the limiter could hold two locks: a deadlock becomes possible. Tell listeners after the '
            'decision, holding no lock.', '''
RateLimitResult result = ...;             // decided
tell(request, result);                    // then told, no lock held''')
        + w.md('## What would you change if...')
        + w.reveal('...a new limit: 1,000 an hour per client, on top of the rest?',
                   'One more rule, no code: ' + w.snippet('''
new RateLimitRule("hourly", RateLimitRule.withKey(), KeyScope.CLIENT,
        LimitPolicy.fixed(new Limit(1_000, 3_600_000)), Algorithm.TOKEN_BUCKET)'''))
        + w.reveal('...one limit per endpoint for everyone together?',
                   'One new key scope, one line: ' + w.snippet('''
ENDPOINT(RequestContext::endpoint),                  // "/search" for all clients together'''))
        + w.reveal('...refused requests should count too, to punish retry storms?',
                   'In `TokenBucket`, let a refusal take tokens as well, down to minus the capacity, so '
                   'a client that keeps hammering digs a deeper hole: ' + w.snippet('''
tokens = Math.max(-capacity, tokens - cost);         // before computing the wait'''))
        + w.reveal('...no bursts at all, just one request every 200 ms?',
                   'A bucket that holds one token is a steady pace: `new Limit(1, 200)`.')
        + w.reveal('...a list of partners who must never be limited?',
                   'A predicate on the rules, no new class: ' + w.snippet('''
new RateLimitRule("plan", r -> r.hasKey() && !partners.contains(r.clientId()), ...)'''))
        + w.md('## The questions they ask')
        + w.reveal('Why a token bucket?', 'Bursts up to a set size, then a steady rate, with two '
                   'numbers per key. A fixed window lets twice the limit through at an edge; a log is '
                   'exact but costs an entry per request. It is not exact per second: say so.')
        + w.reveal('What exactly does `synchronized` protect, and why per bucket?', "Refill, check and "
                   "take on one key's numbers as one step (the lost update), plus visibility. Per "
                   'bucket, because that is where the shared state is: keys never wait for each other, '
                   'and a thread never holds two locks.')
        + w.reveal('`computeIfAbsent`, `putIfAbsent`, or get-then-put?', 'Get-then-put is the '
                   'check-then-act break. `putIfAbsent` is atomic but builds a bucket before every '
                   'call and you must use the value it returns. `computeIfAbsent` builds only on a '
                   'miss, atomically; `get` first keeps the common path lock-free.')
        + w.reveal('`ReentrantLock` or `synchronized`?', 'The same guarantees. `ReentrantLock` adds '
                   '`tryLock` with a timeout, fairness and conditions; none is needed here, so '
                   '`synchronized`: nothing to allocate, nothing to forget to unlock.')
        + w.reveal('Why your own `Clock`, not `java.time.Clock`?', 'Either works: '
                   '`Clock.systemUTC()` in production and `Clock.fixed` in tests. Ours is one method, '
                   'easy to fake by hand; in a Spring codebase use `java.time.Clock`, and keep the '
                   '`elapsed <= 0` guard.')
        + w.reveal('How would it work across 10 servers?', 'The store moves to Redis and a Lua script '
                   'does refill, check and take as one step. The limiter does not change. Decide fail '
                   'open or closed per rule; set a short timeout.')
        + w.reveal('Why not Guava, Bucket4j or Resilience4j?', "Guava's `RateLimiter` is one limiter "
                   'per JVM, keys are yours to map, and `tryAcquire` says only yes or no: no '
                   'Retry-After. Bucket4j is token buckets per key with Redis backends, the closest to '
                   'this page. In the room, the hand-written bucket shows the thinking; in production, '
                   'a library.')
        + w.reveal('What should a client do with a 429?', 'Honour Retry-After; otherwise back off '
                   'exponentially with jitter so retries do not arrive in a wave; cap the retries.')
        + w.reveal('Which SOLID principles? Point at the code.', 'S: every class has one reason to '
                   'change. O: a new way of counting is a new `Bucket`; a new limit is a new rule. '
                   'L: the limiter never asks which bucket it has. I: one-method interfaces. D: the '
                   'API depends on `RateLimiter`, the limiter on `BucketStore` and `Clock`.'))


def bug(w, n, code, answer, fix):
    return (w.md(f'### Bug {n}') + w.snippet(code)
            + w.reveal('What is wrong, and the fix', answer + '\n\n' + w.snippet(fix, label='the fix')))


def pages(w):
    return [p(w) for p in (problem, counting, derive, design, threads, answer, time_, bucket, count,
                           budget, book, store, limiter, door, run_, tests, holds, more, credits,
                           live, idle, waiting, redis, lockfree, cousins, recall, practise, check)]
