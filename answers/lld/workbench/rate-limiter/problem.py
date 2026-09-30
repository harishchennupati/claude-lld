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
        **In short:** a list of rules, one counter per client per rule, and one method that lets a
        request through only if every rule agrees.

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
            ['Threads', 'thread safety you can explain', 'the three ways threads break shared data (lost update, check-then-act, stale read), and '
             'the lock versus lock-free trade-off, measured'],
            ['Tests', 'a burst, a refill, a race', 'broken copies that prove each test works'],
            ['Operations', '', 'metrics, a dry run before a change, fail open or closed'],
        ])
        + w.md('''
        ## The hour

        **A 60-minute LLD round:** 10 minutes on questions and the design on paper, then type the
        round subset: the values, `Clock` and `ManualClock`, `Bucket` and `TokenBucket`,
        `Algorithm` with one constant, `KeyScope`, `LimitPolicy`, `Plans`, the rule and the rule
        book, the store, the limiter, and a `Main` with a burst and the race. Mention the rest;
        do not type it. **A 90-minute machine-coding round:** all of it, plus the tests. Either
        way, get the first version running early.
        ''')
        + w.box('note', 'How to use this page',
                '← and → move between steps. The list on the left shows minutes per step; steps '
                'marked *later* are optional. The must-do path is about 2 h 30 of reading, then '
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
        Every row becomes a `Bucket` class: the fixed window, the sliding window log and the token
        bucket are in the core; the counter and the leaky bucket come in
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
# How to get there: one class, then one interviewer push at a time. Each push breaks something in
# the code we have; the fix adds a few named types. `adds` lists them as (name, kind).
MOVES = [
    dict(push='"When should the client retry? And which limit did it hit?"',
         wrong='''
        The first version answers `true` or `false`. `false` cannot say "retry in 80 ms" or "your
        search limit". And the request is only a client id: there is no endpoint, no IP and no
        cost, so we could never limit searches or sign-ins.
        ''',
         fix='''
        So the request and the answers become **records**: plain values, built once, never
        changed. The limiter becomes an **interface** with one question.
        ''',
         adds=[('RequestContext', 'record'), ('Decision', 'record'), ('RateLimitResult', 'record'),
               ('RateLimiter', 'interface')],
         code='''
record RequestContext(String clientId, String ip, String endpoint, int cost) { }
record Decision(boolean allowed, long remaining, long retryAfterMillis) { }        // one bucket
record RateLimitResult(boolean allowed, long remaining, long retryAfterMillis,
                       String refusedBy) { }                                      // the request

interface RateLimiter {
    RateLimitResult check(RequestContext request);
}''',
         xy='Records in and out, not a boolean. The interviewer\'s `rateLimit(customerId)` stays, '
            'as a one-line default method on top of `check`.'),
    dict(push='"Write a test: a refused client must wait exactly 80 ms."',
         wrong='''
        The first version calls `System.currentTimeMillis()` inside. The test would have to sleep
        for 80 ms, and it would fail whenever the machine is slow.
        ''',
         fix='''
        So time becomes something the limiter is **handed**: an interface with one method, the
        real clock in production, and a clock the test moves by hand.
        ''',
         adds=[('Clock', 'interface'), ('SystemClock', 'class'), ('ManualClock', 'class')],
         code='''
interface Clock {
    long nowMillis();
}

class ManualClock implements Clock {            // tests: advance(120) is "120 ms later", instantly
    private volatile long now;
    public long nowMillis() { return now; }
    void advance(long millis) { now += millis; }
}''',
         xy='Time handed in, not read inside.'),
    dict(push='"A hundred threads call this at once. fantasy-app must not wait for score-widget."',
         wrong='''
        The first version's `synchronized allow()` is one lock for the whole API: during
        score-widget's retry storm, every fantasy-app request queues behind it. Yet the only data
        that needs guarding is one client's two numbers.
        ''',
         fix='''
        So those two numbers, and the arithmetic on them, move into an object of their own, and
        the lock moves with them. One **class** per client's budget; a **record** for the limit.
        ''',
         adds=[('TokenBucket', 'class'), ('Limit', 'record')],
         code='''
record Limit(int capacity, long periodMillis) { }          // 5 per 1,000 ms

class TokenBucket {
    private double tokens;                                  // one client's numbers...
    private long lastRefillMillis;

    synchronized Decision tryConsume(int cost, long nowMillis) { ... }   // ...and their lock
}''',
         xy='A lock per bucket, not one lock for everyone.'),
    dict(push='"Sign-ins must be exact: never 6 in a minute. And the daily quota starts again at '
              'midnight."',
         wrong='''
        A token bucket can do neither: after a quiet spell it lets a burst through, and it knows
        nothing about midnight. We need two more ways of counting. The tempting fix is a switch in
        the limiter, `if (type == LOG) ... else if (type == WINDOW) ...`, and every new way of
        counting would edit that method again.
        ''',
         fix='''
        So the limiter asks a question, and each way of counting is a class that answers it: an
        **interface** and three classes. An **enum** names them, so a rule can say which one it
        wants, and each constant holds its class's constructor.
        ''',
         adds=[('Bucket', 'interface'), ('SlidingWindowLog', 'class'),
               ('FixedWindowCounter', 'class'), ('BucketFactory', 'interface'),
               ('Algorithm', 'enum')],
         code='''
interface Bucket {                                         // TokenBucket implements it too
    Decision tryConsume(int cost, long nowMillis);
}

interface BucketFactory {
    Bucket create(Limit limit, long nowMillis);
}

enum Algorithm implements BucketFactory {                 // no switch anywhere
    TOKEN_BUCKET(TokenBucket::new),
    SLIDING_WINDOW_LOG(SlidingWindowLog::new),
    FIXED_WINDOW(FixedWindowCounter::new);
    ...
}''',
         xy='An interface, not a switch. This is the Strategy pattern.'),
    dict(push='"PRO clients get 50 a second, FREE 5. Searches: 2 a second each. Sign-ins: 5 a minute '
              'per IP. And 1,000 a second for the whole API."',
         wrong='''
        The tempting fix is more ifs: `if (plan == PRO) ...`, `if (endpoint.equals("/search"))
        ...`. Each one is a product decision welded into the limiter.
        ''',
         fix='''
        Look at what the five limits have in common instead. Each says which requests it covers,
        whose budget they spend, how much, and how to count. That is a **rule**, and a rule is
        data: a record made of small parts. `withKey()` and `endpoint("/search")` are small
        true-or-false functions on the request; a `LimitPolicy` answers "how much?", either fixed
        or by the client's plan.
        ''',
         adds=[('RateLimitRule', 'record'), ('KeyScope', 'enum'), ('LimitPolicy', 'interface'),
               ('PlanLimits', 'class'), ('Plans', 'class'), ('Plan', 'enum'),
               ('RuleBook', 'class'), ('ScoreApiRules', 'class')],
         code='''
record RateLimitRule(String name,
                     Predicate<RequestContext> appliesTo,   // which requests: "/search" only
                     KeyScope scope,                        // whose budget: CLIENT, IP, EVERYONE
                     LimitPolicy limits,                    // how much: fixed, or by Plan
                     Algorithm algorithm) { }               // how to count

// ScoreApiRules, one of the five:
new RateLimitRule("search", withKey().and(endpoint("/search")), KeyScope.CLIENT_AND_ENDPOINT,
        LimitPolicy.fixed(Limit.perSecond(2)), Algorithm.TOKEN_BUCKET)''',
         xy='Rules as data, not if-statements. A new limit is one new line in `ScoreApiRules`; '
            '`RuleBook` holds the list and answers "which rules cover this request?"'),
    dict(push='"We have a million clients. Where do their buckets live, and who creates them?"',
         wrong='''
        Every rule needs a bucket per key, such as `plan|fantasy-app|50/1000` (rule, whose budget,
        the limit; the limiter step says why the limit is in it). The first idea is a
        `HashMap` inside the limiter: `get`, and `put` a new bucket if there is none. Two threads
        meeting a new client both see nothing, both create a bucket, and the client gets two
        budgets. It also makes the limiter decide where buckets live, which is exactly what
        changes when we add servers.
        ''',
         fix='''
        So buckets get a home of their own behind an **interface**. The in-memory **class** finds
        or creates a bucket in one atomic step.
        ''',
         adds=[('BucketStore', 'interface'), ('InMemoryBucketStore', 'class')],
         code='''
interface BucketStore {
    Bucket bucketFor(String key, BucketFactory factory, Limit limit, long nowMillis);
}

// InMemoryBucketStore: a ConcurrentHashMap, and look-create-store as one step
return buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));''',
         xy='A store behind an interface, not a map inside the limiter. Redis replaces it later.'),
    dict(push='"A search refused by the search rule must not cost the client a plan token."',
         wrong='''
        A request now passes several rules. If each rule simply takes its token when asked, then
        plan takes one, quota takes one, search refuses, and two tokens are gone for a request
        that never ran.
        ''',
         fix='''
        So one **class** implements `RateLimiter`: it charges the rules in order, remembers what it
        took, and gives it all back when a rule refuses. `Bucket` learns to give tokens back.
        ''',
         adds=[('RuleBasedRateLimiter', 'class')],
         code='''
for (RateLimitRule rule : rules.matching(request)) {
    Bucket bucket = bucketFor(rule, request, now);          // key -> store -> bucket
    Decision d = bucket.tryConsume(request.cost(), now);
    if (!d.allowed()) {
        for (Bucket spent : charged) {
            spent.refund(request.cost(), now);              // all or nothing
        }
        return RateLimitResult.refused(d, rule.name());
    }
    charged.add(bucket);
}''',
         xy='A loop with a refund, not a Chain of Responsibility: a chain passes a request along '
            'until one handler takes it, and here every rule must agree.'),
    dict(push='"Answer with HTTP 429 and a Retry-After header. And ops want to see who is being '
              'throttled."',
         wrong='''
        Status codes and log lines inside the limiter would tie it to one web framework and one
        logger, and every new report would edit it.
        ''',
         fix='''
        So HTTP stays at the front door, in a **class** that asks the limiter first. Reports listen
        from the side: an **interface** told about every decision after it is made, and a
        **class** that counts refusals.
        ''',
         adds=[('RateLimitFilter', 'class'), ('RateLimitListener', 'interface'),
               ('RefusalMetrics', 'class')],
         code='''
// RateLimitFilter: HTTP in, HTTP out; the limiter never sees a status code
Response handle(RequestContext request, Function<RequestContext, Response> endpoint)

interface RateLimitListener {                               // RefusalMetrics is one
    void onDecision(RequestContext request, RateLimitResult result);
}''',
         xy='HTTP at the door and listeners on the side, not inside the limiter. The listeners '
            'are the Observer pattern.'),
]

KIND_SHORT = {'record': 'record', 'interface': 'interface', 'class': 'class', 'enum': 'enum'}


def grown(upto, everything=False):
    """This push's new types as chips; with everything=True, the whole design at the end."""
    moves = MOVES if everything else [MOVES[upto]]
    chips = ''.join(f'<span class="chip {"done" if everything else "now"}">{name} '
                    f'<small>{KIND_SHORT[kind]}</small></span>'
                    for m in moves for name, kind in m['adds'])
    total = sum(len(m['adds']) for m in MOVES[:upto + 1])
    label = f'all {total} types' if everything else f'new · {total} so far'
    return (f'<div class="strip grow"><div class="sg"><span class="sl">{label}</span>'
            + chips + '</div></div>')


def derive(w):
    first = w.runs.demo('FirstCut')
    cls = first[first.index('class FirstCutLimiter'):first.index('public class FirstCut ')].strip()
    moves = ''
    for i, m in enumerate(MOVES):
        moves += (w.md(f'### {i + 1} · {m["push"]}')
                  + w.md(m['wrong']) + w.md(m['fix'])
                  + w.snippet(m['code'])
                  + w.md(f'**{m["xy"]}**')
                  + grown(i))
    return step('derive', D, 'How to get there', 'How the design grows, one push at a time',
                minutes=10, body=
        w.md('''
        Nobody designs twenty classes up front. You start with one class that works, and the
        interviewer pushes, one requirement at a time. Each push breaks something in the code you
        have; the fix adds a few small types, each with one job, and you know why each one is
        there.

        This is the class everyone writes first. It is compiled and run here:
        ''')
        + w.snippet(cls, label='FirstCut.java', note='the 15-minute version')
        + w.run('FirstCut')
        + w.md('''
        It is right for one limit, one kind of client, one server. Now the pushes.
        ''')
        + moves
        + w.md('''
        That is the whole design, grown from one class by eight pushes:
        ''')
        + grown(len(MOVES) - 1, everything=True)
        + w.md('''
        The next step draws it on one page.

        Patterns you might expect and do not see (Singleton, Builder, an abstract base bucket) are
        explained in [Principles and patterns](#principles).

        ## The order to type it

        The order of the pushes, so the code compiles at every point: the records and
        `RateLimiter`; the clocks; `TokenBucket`; the other buckets and `Algorithm`; scopes, limits
        and plans; the rule and the rule book; the store; the limiter and listeners; the filter;
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
            ['`RateLimitFilter`', 'turn a result into HTTP: 429, Retry-After, headers', 'the web '
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


# ===================================================================================== build
def answer(w):
    return step('answer', B, 'The answer', 'What goes in, what comes out', minutes=4, stage='Build · the values', body=
        w.strip(now=['RequestContext', 'Limit', 'Decision', 'RateLimitResult', 'RateLimiter'])
        + w.md('''
        Start where the API starts: a request goes in, an answer comes out. Four records and the
        interface the API calls, and no logic yet.
        ''')
        + w.code(['RequestContext.java', 'Limit.java', 'Decision.java', 'RateLimitResult.java',
                  'RateLimiter.java'])
        + w.run('AnswerDemo')
        + w.javas(
            w.java('record', '`record Limit(int capacity, long periodMillis)` is a class whose '
                   'fields are set once and never change. Java writes the constructor, the '
                   'accessors (`limit.capacity()`), `equals`, `hashCode` and `toString`. An object '
                   'that never changes can be shared by any number of threads without a lock.'),
            w.java('static factory and default method', '`RequestContext.of(...)` and '
                   '`Decision.allow(4)` are named ways to build a record: shorter than the '
                   'constructor, and they say what they build. `default boolean rateLimit(...)` is '
                   'an interface method with a body: every implementation gets it for free.'))
        + w.asks([
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
        + w.md('''
        ## A thread break: the stale read

        The test thread moves the clock; request threads read it. Without `volatile`, Java does
        not promise a request thread ever sees the new time: it may keep reading 0 forever, and
        the bucket never refills. (The other two ways threads break shared data come in
        [the token bucket](#bucket) and [the store](#store).)
        ''')
        + w.java('volatile', 'Every write to a `volatile` field is seen by every later read of '
                 'it. It does not make `now += millis` one step (that is still a read, then a '
                 'write), which is fine here because only the test thread writes.')
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
        + w.md('''
        ## A thread break: the lost update

        Refill, check and take is a read, then a write. If two threads read the same number
        before either writes, both decide on it, and one update is lost:
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
        + w.md('''
        The lock is the bucket itself, so each key has its own lock and keys never wait for each
        other.
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
        + w.java('a final field, and ConcurrentHashMap', "`PlanLimits`' map is set in the "
                 'constructor and never written again: a `final` field is seen by every thread '
                 'once the constructor ends, so it needs no lock. `Plans`\' map changes while '
                 'requests run, so it is a `ConcurrentHashMap`.')
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
        other's searches.
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
        + w.md('## A thread break: check, then act')
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
             'No. At most one bin (a small slice of the table), and only while it creates a new '
             'bucket. Other keys are never blocked, and a key that already has a bucket is '
             'usually returned without any lock.'),
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
        + w.box('hole', 'The catch',
                'For a few microseconds, between taking a token and giving it back, the token is '
                'missing, so another request from the same client may be refused when it would '
                'have fit. Rarely, a refund can leave one token more than the cap would have '
                'allowed. Both are tiny, and we accept them. The strict fix is to ask every rule '
                'first and take afterwards, holding all their locks in a fixed order: more locks, '
                'more waiting.')
        + w.java('CopyOnWriteArrayList and LongAdder', 'Listeners are read on every request and '
                 'added almost never: a copy-on-write list needs no lock to read. `LongAdder` is a '
                 'counter for many writers: each thread adds to its own cell, and `sum()` adds '
                 'the cells up.')
        + w.asks([
            ('Which "remaining" goes in the header?',
             'The smallest across the rules: the tightest one decides when the client is next '
             'refused.'),
            ('Why read the clock once, at the top?',
             'So every rule judges the request at the same instant, and the clock is read outside '
             'every lock. That is also why a bucket may get a slightly older time than the last '
             'thread gave it, and why `refill` ignores time that goes backwards.'),
        ]))


def door(w):
    return step('door', B, 'The front door', 'The front door: HTTP', minutes=4, stage='Build · the front door', body=
        w.strip(now=['RateLimitFilter'])
        + w.md('''
        The limiter knows nothing about HTTP, and the filter knows nothing about buckets. The
        filter turns a result into a response: 429 with Retry-After in whole seconds, rounded up,
        and the rule's name; otherwise the real work, plus the remaining count. One case the code
        leaves out on purpose: a request that costs more than a whole bucket can never pass, so
        the API should refuse it before asking (below).
        ''')
        + w.code(['RateLimitFilter.java'])
        + w.run('DoorDemo')
        + w.asks([
            ('Why round Retry-After up?',
             'It is in whole seconds. A wait of 200 ms rounded down would say 0, and the client '
             'would come straight back and be refused again. Rounded up, it says 1.'),
            ('What about a request that costs more than the whole bucket?',
             'It could never pass, and the bucket would still answer "retry in ...": a lie. Refuse '
             'it before the limiter with 400, or split it (fetch the history in pages).'),
        ]))


def run_(w):
    return step('run', B, 'Run it', 'Run it', minutes=4, stage='Build · run', body=
        w.strip(now=['Main'])
        + w.md('''
        `Main` wires the objects as the server would at startup (the design step's snippet),
        with only the clock manual, so every run prints the same. Then it sends requests from
        three clients through the front door.
        ''')
        + '<details class="more"><summary>Main.java: the wiring and the requests</summary>'
        + w.part('Main.java', r'^import', r'System\.out\.printf\("%4d', plus=4, label='Main.java',
                 note='wiring, and requests from three clients')
        + '</details>'
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
        + w.part(t, r'^import', r'System\.exit\(1\);', plus=2, note='imports and the runner')
        + w.md('Behaviour, on the real rules, driven by the manual clock:')
        + w.part(t, r'^    // ---- behaviour', r'"the 6th: refused by plan"', plus=1, note='the first test')
        + '<details class="more"><summary>The other eleven behaviour tests</summary>'
        + w.part(t, r'^    static void retryTime', r'"and nothing was earned meanwhile"', plus=1,
                 note='behaviour', sol=False)
        + '</details>'
        + w.md('''
        Threads. For the lost update: a frozen clock and far more requests than tokens, so a
        request that sneaks through shows up as a count above the limit. For check-then-act: a
        factory that takes 50 ms to build a bucket holds the race window open, so the bad
        interleaving happens on every run, not once in a thousand. Through the limiter the race is
        too short to catch reliably, so this test calls the store directly.
        ''')
        + w.part(t, r'^    // ---- threads', r'"one bucket for one key, got "', plus=1, note='races')
        + '<details class="more"><summary>The helpers: limiters, requests, spend, together, check</summary>'
        + w.part(t, r'^    // ---- helpers', None, note='helpers', sol=False)
        + '</details>'
        + w.run('RateLimiterTest')
        + w.md('''
        ## Break it on purpose

        A test you have never seen fail proves little. Each row is a real broken copy of the core,
        and the named test fails against it every time (the race tests were run ten times).
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
    return step('holds', B, 'Why it holds up', 'Why it holds up: threads and cost', minutes=5,
                stage='Build · done', body=
        w.md('''
        ## The three ways two threads break shared data

        Every thread problem in this design is one of three, and each was met where it happens:
        the lost update in [the token bucket](#bucket), check-then-act in [the store](#store),
        the stale read in [time](#time).
        ''')
        + w.table(['The break', 'What happens', 'The fix here', "The fix's limit"], [
            ['lost update', 'two threads read 1 token, both write 0: two requests, one token',
             '`synchronized` on the bucket', 'every method that touches the fields must take the '
             'same lock'],
            ['check, then act', 'two threads find no bucket and both create one',
             '`computeIfAbsent`: look, create and store as one step',
             'the one step must cover both the check and the act'],
            ['stale read', 'a thread keeps seeing an old value another thread replaced',
             '`volatile` on `ManualClock`; a lock also gives it',
             '`volatile` does not make `now += 200` one step'],
        ])
        + w.md('''
        `synchronized` gives both halves: one thread at a time, and the next thread sees what the
        last one wrote. `volatile` gives only the second.

        ## What threads share, and what guards it
        ''')
        + w.table(['State', 'Who touches it', 'Guarded by', 'Against'], [
            ["the store's map", 'every request thread', '`ConcurrentHashMap`, `computeIfAbsent`',
             'check, then act'],
            ["a bucket's numbers", "requests for that key", '`synchronized` on the bucket',
             'lost update, stale read'],
            ['`Plans`\' map', 'requests read, sign-ups write', '`ConcurrentHashMap`',
             'stale read, or a resize seen half-done'],
            ['rules, `PlanLimits`, `RuleBook`', 'read only', '`final` fields, records',
             'nothing to guard: set once in the constructor'],
            ['the listener list', 'read per request', '`CopyOnWriteArrayList`',
             'a change during a walk'],
            ['refusal counts', 'every refused request', '`LongAdder` in a `ConcurrentHashMap`',
             'lost update'],
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
        A check on `/scores` builds three key strings and does three store lookups (one per rule
        that covers it). That memory is why a later follow-up, [Idle clients](#idle), removes
        buckets that have filled up again.
        ''')
        + w.asks([
            ('What happens under a flood of made-up client ids?',
             'Each creates buckets, so memory grows until the idle sweep clears them. Better: the '
             'API rejects unknown keys before the limiter is asked.'),
        ]))


def principles(w):
    return step('principles', B, 'Principles and patterns', 'SOLID and patterns, in this code',
                minutes=6, stage='Build · done', body=
        w.md('''
        After the code runs, most interviewers ask some version of "which patterns did you use?"
        and "how does this follow SOLID?". The strong answer points at a class and says what would
        go wrong without it. Here is that answer for every principle and pattern in the design.

        ## SOLID
        ''')
        + w.table(['Principle', 'In one line', 'Here', 'Without it'], [
            ['**S**ingle responsibility', 'one reason to change', 'counting in buckets, storing in '
             'the store, HTTP in the filter, the rules in `ScoreApiRules`', 'a new HTTP header '
             'would edit the class that counts tokens'],
            ['**O**pen/closed', 'add, do not edit', 'a new way of counting is a new `Bucket` and one '
             '`Algorithm` line; a new limit is a new rule', 'a switch on the algorithm, edited for '
             'every new one'],
            ['**L**iskov substitution', 'any implementation works where the interface is expected',
             'the limiter never asks which `Bucket` or `BucketStore` it has',
             '`if (bucket instanceof SlidingWindowLog)` in the limiter'],
            ['**I**nterface segregation', 'small interfaces, one question each', '`Clock`, '
             '`LimitPolicy`, `RateLimitListener`, `BucketFactory`: one method each',
             'a listener forced to implement methods it does not care about'],
            ['**D**ependency inversion', 'depend on interfaces, handed in', 'the API depends on '
             '`RateLimiter`; the limiter gets `BucketStore`, `Clock` and the rules in its '
             'constructor', 'no `ManualClock` in tests, no Redis store later'],
        ])
        + w.md('## Patterns used')
        + w.table(['Pattern', 'Where', 'The problem it solves here'], [
            ['Strategy', '`Bucket` with three classes', 'each rule counts its own way; the limiter '
             'does not care which'],
            ['Factory', '`BucketFactory`, `Algorithm`', 'a rule names its algorithm; the store '
             'creates the bucket only when a new key arrives'],
            ['Repository', '`BucketStore`', 'where buckets live is hidden: memory today, Redis '
             'tomorrow'],
            ['Observer', '`RateLimitListener`, `RefusalMetrics`', 'reports are added without '
             'touching the limiter'],
            ['Facade', '`RateLimiter` over rules, store and buckets', 'the API asks one question'],
            ['Decorator', '`ShadowRateLimiter` ([Live limits](#live))', 'wraps a limiter to add a '
             'dry run, and is itself a `RateLimiter`'],
        ])
        + w.md('''
        Strategy and Factory work together here: `Algorithm` is the factory that picks a
        strategy, and `Bucket` is the strategy it produces.

        ## Patterns you might reach for, and why not

        - **Singleton** for the limiter: the server creates one and passes it on anyway. A
          Singleton would stop each test from making its own, with its own clock.
        - **Chain of Responsibility** for the rules: a chain passes a request along until one
          handler takes it. Here every rule must agree, and a refusal undoes the others: a loop
          with a refund.
        - **Template Method** (an abstract base bucket): the three buckets share a question, not
          steps; there is no common code to pull up.
        - **Builder** for the records: five fields, all required; a constructor is clearer.
        - **State**: a bucket's behaviour does not change by state; its numbers do.

        ## What else they probe

        - **Program to an interface.** Every field that holds a collaborator has an interface
          type: `BucketStore store`, `Clock clock`, `RateLimiter limiter`.
        - **Composition over inheritance.** A rule is made of parts (a scope, a policy, an
          algorithm), not a subclass per kind of rule. Five rules, zero subclasses.
        - **Immutability.** Records and final fields for everything shared and never changed:
          `Limit`, `RateLimitRule`, `RequestContext`, the rule book. Nothing to lock.
        - **Testability.** Constructor injection is why every test runs in microseconds with a
          `ManualClock` and never sleeps.
        ''')
        + w.asks([
            ('`Bucket`: interface or abstract class?',
             'Interface. The buckets share no fields and no code, only the question; an abstract '
             'class would force a hierarchy for nothing and block a bucket from extending anything '
             'else.'),
            ('How would you add a new algorithm?',
             'One class that implements `Bucket`, and one line in `Algorithm`. Nothing else '
             'changes: that is open/closed, and it is exactly what [More ways to count](#more) '
             'does.'),
        ]))


# ================================================================================ follow-ups
# What each follow-up needs to make sense, and the step whose code it starts from (drill 3 starts
# from that step's folder in rate-limiter-code/steps/).
NEEDS = {'more': 'the core', 'credits': 'the core', 'live': 'the core',
         'idle': 'the core; it also gives the buckets from More ways to count their `isIdle` '
                 '(the credit bucket keeps the default: never idle)',
         'waiting': 'the core', 'redis': 'the core',
         'lockfree': 'the core (its `isIdle` comes from Idle clients)',
         'cousins': 'nothing: two small classes of their own'}
PREV = {'more': ('the core', 'tests'), 'credits': ('More ways to count', 'more'),
        'live': ('Credits', 'credits'), 'idle': ('Live limits', 'live'),
        'waiting': ('Idle clients', 'idle'), 'redis': ('Waiting', 'waiting'),
        'lockfree': ('Many servers', 'redis'), 'cousins': ('Lock-free', 'lockfree')}


def followup(w, s, id_, nav, title, ask, src, lands, minutes, opt=False, extra='',
             after_run='', hole=None, javas=(), asks=(), figure=None, before_diff='',
             first=(), fold=(), fold_note=None):
    pname, pid = PREV[s]
    body = (w.ask(ask, src=src, label='Follow-up' if not opt else 'Follow-up · when you have time')
            + w.md(f'*Needs:* {NEEDS[s]}. For drill 3, start from the folder '
                   f'`steps/{CONFIG["SNAPS"][CONFIG["SNAPS"].index(s) - 1]}/`: that is simply '
                   f'where the code stands after [{pname}](#{pid}).')
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
        The dry run finds two of score-widget's requests that the new rules would refuse. After the switch the next second allows 3, and the
        4th waits 334 ms (1,000 / 3, rounded up). The daily quota did not reset: that rule did not
        change, so its keys and buckets are the same.
        ''',
        hole='A replaced bucket starts full, so a client whose limit changes can burst once more. '
             'The old buckets stay in the store until a later sweep ([Idle clients](#idle)) '
             'removes them.',
        javas=[('a volatile reference to an immutable object', 'The `RuleBook` never changes after '
                'it is built, and the field that points to it is `volatile`: a request reads the '
                'field once and sees a whole book, old or new, never half of each. No lock.')],
        asks=[('Why not change the existing buckets in place?',
               "A bucket's capacity and rate are final, and its arithmetic assumes one rate. New keys for new "
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
        A token bucket left alone long enough to fill up again (a second, at 5 a second) is exactly
        what a new one would be, so it goes. score-widget called again at 900 ms, so its plan
        bucket is not full yet and stays. A quota bucket holds today's count, so it stays until the
        day is over.
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
        `EXPIRE` it. It has the window-edge hole, and it is two commands: a crash between them
        leaves a counter with no expiry. The token bucket needs read, refill and write as one step,
        which no two commands give:
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
               'Calling `TIME` in a script that writes needs Redis 5 or later; on older Redis, '
               'pass `now` in as an argument, and `if now > last` ignores small skews.'),
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
               'since JDK 24 (JEP 491).')])


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
        ('The eight pushes', [
            'retry time and rule name → records in and out',
            'test "wait 80 ms" → `Clock` handed in',
            '100 threads → a lock per bucket',
            'exact sign-ins, midnight quota → `Bucket` interface + `Algorithm`',
            'five limits → rules as data',
            'a million clients → `BucketStore`, `computeIfAbsent`',
            'refused search → refund: all or nothing',
            '429 and ops → filter at the door, listeners on the side']),
        ('The token bucket, in numbers', [
            '5 a second = capacity 5, a token every 200 ms',
            '120 ms earns 0.6; the wait for 1 is 0.4 × 200 = 80 ms',
            'quiet time fills it to 5, never more',
            'not exact per second: up to 10 in one (5 saved + 5 earned)',
            'exact → log (sign-ins); calendar → fixed window (quota)']),
        ('Threads', [
            'lost update → `synchronized` on the bucket',
            'check, then act → `computeIfAbsent`',
            'stale read → `volatile` (or any lock)',
            'set once → `final` fields and records: no lock',
            'one lock at a time → no deadlock']),
        ('Follow-ups: where each lands', [
            'more ways to count → a `Bucket` + one `Algorithm` line',
            'credits → a `Bucket`',
            'live limits → `volatile RuleBook`; shadow = Decorator',
            'idle clients → `isIdle` + a sweep in the store',
            'waiting → a loop around `check` + `Semaphore`',
            'many servers → a `BucketStore` on Redis + Lua',
            'lock-free → a `Bucket` with compare-and-set']),
        ('The 14 tests', [
            'burst 5, then refused; retry 200 ms, then 80 ms',
            'a refused request spends nothing; never above capacity',
            "each plan's budget; an upgrade at once; each rule's own key",
            'sign-ins exact; quota resets at midnight',
            'tightest remaining; listeners hear refusals; a broken listener is harmless',
            'clock back earns nothing',
            'races: one client exact; a new key gets one bucket (slow factory)']),
    ]
    grid = '<div class="recall">' + ''.join(
        f'<div class="rc"><h4>{t}</h4><ul>' + ''.join(f'<li>{w.inline(i)}</li>' for i in items)
        + '</ul></div>' for t, items in cards) + '</div>'
    return step('recall', R, 'One-screen recall', 'The whole design on one screen', minutes=4, body=
        w.md('''
        Come back to this a week from now and read it top to bottom. If every line brings back the
        code behind it, you are ready; if one does not, go back to that step. First, the whole
        design as signatures, in the order you type it:
        ''')
        + w.snippet('''
// in and out
record RequestContext(String clientId, String ip, String endpoint, int cost)
record Decision(boolean allowed, long remaining, long retryAfterMillis)           // one bucket
record RateLimitResult(boolean allowed, long remaining, long retryAfterMillis, String refusedBy)
interface RateLimiter { RateLimitResult check(RequestContext request); }

// time
interface Clock { long nowMillis(); }                  // SystemClock; ManualClock.advance(ms)

// counting
record Limit(int capacity, long periodMillis)          // perSecond(5): a token per 200 ms
interface Bucket { Decision tryConsume(int cost, long now); void refund(int cost, long now); }
class TokenBucket, SlidingWindowLog, FixedWindowCounter implements Bucket   // synchronized
interface BucketFactory { Bucket create(Limit limit, long now); }
enum Algorithm implements BucketFactory { TOKEN_BUCKET(TokenBucket::new), ... }

// rules
record RateLimitRule(String name, Predicate<RequestContext> appliesTo, KeyScope scope,
                     LimitPolicy limits, Algorithm algorithm)
enum KeyScope { CLIENT, IP, CLIENT_AND_ENDPOINT, EVERYONE }       // request -> key
interface LimitPolicy { Limit limitFor(RequestContext r); }       // fixed(limit), PlanLimits
class Plans { assign(clientId, plan); planOf(clientId); }         // ConcurrentHashMap
class RuleBook { List<RateLimitRule> matching(RequestContext r); } // ScoreApiRules.build(plans)

// storing, deciding, the edges
interface BucketStore { Bucket bucketFor(String key, BucketFactory f, Limit l, long now); }
class InMemoryBucketStore implements BucketStore               // computeIfAbsent
class RuleBasedRateLimiter(RuleBook, BucketStore, Clock)       // loop, refund, listeners
interface RateLimitListener { void onDecision(RequestContext r, RateLimitResult result); }
class RateLimitFilter(RateLimiter)                             // 429 + Retry-After''',
                    label='the design, as signatures')
        + grid
        + w.md('The lines to remember exactly:')
        + w.snippet('''
long elapsed = nowMillis - lastRefillMillis;
if (elapsed <= 0) { return; }                                       // an older time earns nothing
tokens = Math.min(capacity, tokens + elapsed / millisPerToken);     // refill, capped
if (tokens >= cost) { tokens -= cost; return Decision.allow((long) tokens); }   // take
long wait = (long) Math.ceil((cost - tokens) * millisPerToken);     // or say when
return buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));     // one bucket
for (Bucket spent : charged) { spent.refund(request.cost(), now); } // all or nothing''',
                    label='seven lines'))


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
            ('Idle clients: isIdle and the sweep', 10, '#idle'),
            ('Waiting instead of refusing', 10, '#waiting'),
            ('Many servers: the script and the Redis store', 15, '#redis'),
            ('Lock-free: the compare-and-set bucket', 10, '#lockfree'),
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
return buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));   // one atomic step''')
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
// in TokenBucket.tryConsume, where it refuses:
tokens = Math.max(-capacity, tokens - cost);         // each refusal digs deeper, to -capacity
long waitMillis = (long) Math.ceil((cost - tokens) * millisPerToken);
return Decision.deny(0, waitMillis);                 // below zero: report 0 left'''))
        + w.reveal('...no bursts at all, just one request every 200 ms?',
                   'A bucket that holds one token is a steady pace: `new Limit(1, 200)`.')
        + w.reveal('...a list of partners who must never be limited?',
                   'A predicate on the rules, no new class: ' + w.snippet('''
new RateLimitRule("plan", r -> r.hasKey() && !partners.contains(r.clientId()), ...)'''))
        + w.md('## The questions they ask')
        + w.reveal('Why a token bucket?', 'Bursts up to a set size, then a steady rate, with two '
                   'numbers per key. A fixed window lets twice the limit through at an edge; a log is '
                   'exact but costs an entry per request. It is not exact per second: up to 10 can pass '
                   'in one.')
        + w.reveal('What exactly does `synchronized` protect, and why per bucket?', "Refill, check and "
                   "take on one key's numbers as one step (the lost update), plus visibility. Per "
                   'bucket, because that is where the shared state is: keys never wait for each other, '
                   'and a thread never holds two locks.')
        + w.reveal('`computeIfAbsent`, `putIfAbsent`, or get-then-put?', 'Get-then-put is the '
                   'check-then-act break. `putIfAbsent` is atomic but builds a bucket before every '
                   'call and you must use the value it returns. `computeIfAbsent` builds only on a '
                   'miss, atomically.')
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
        + w.reveal('Which SOLID principles? Point at the code.', 'Say each in one line with a '
                   'class, as in [Principles and patterns](#principles): S the buckets count, the '
                   'store stores; O a new `Bucket`; L any bucket drops in; I one-method interfaces; '
                   'D everything handed in through constructors.'))


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

    # the core, in typing order, grouped like the build steps
    groups = ''
    for b in CONFIG['BUILD']:
        title = next(p['nav'] for p in PAGES_BY_ID.values() if p['id'] == b['id'])
        groups += w.md(f'### {title}') + w.code(b['files'])
    # every file a follow-up adds, in its final form, one fold per follow-up
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
        Everything on this page, in one place. Download a project, unzip it, and open the folder in
        IntelliJ (File > Open): it is a plain Maven project, Java 17, no dependencies. Run `Main`
        or `RateLimiterTest` from the green arrow. The same projects are in the repository under
        `answers/lld/rate-limiter-code/`.
        ''')
        + '<div class="dls">'
        + link(core, 'rate-limiter-core', 'Download the core (.zip)')
        + link(complete, 'rate-limiter-complete', 'Download the core + every follow-up (.zip)')
        + '</div>'
        + w.md('''
        ## The core, in the order you type it
        ''')
        + groups
        + w.md('''
        ## What the follow-ups add

        New files only, as they end up. Follow-ups also change a few core files (for example
        `isIdle` in the buckets, the `volatile` rule book in the limiter): the complete download
        has every change.
        ''')
        + later)


PAGES_BY_ID = {}


def pages(w):
    out = [p(w) for p in (problem, counting, derive, design, answer, time_, bucket, count,
                          budget, book, store, limiter, door, run_, tests, holds, principles,
                          more, credits, live, idle, waiting, redis, lockfree, cousins, recall,
                          practise, check)]
    PAGES_BY_ID.update({p['id']: p for p in out})
    return out + [allcode(w)]
