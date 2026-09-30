"""What the builder compiles and runs for the rate limiter. The page content is in problem.py."""

SLUG = 'rate-limiter'
NAME = 'Rate limiter'
TITLE = 'Rate limiter · LLD workbench'
SUBTITLE = 'LLD workbench · Java 17 · every class on this page compiles and runs'

# Snapshots of the one source tree (see ../snap.py): the core, then one per follow-up, in the
# order the follow-ups build on each other. Named after their step, never numbered.
SNAPS = ['core', 'more', 'credits', 'live', 'idle', 'waiting', 'redis', 'lockfree', 'cousins']

# The core, typed in this order. Each step compiles on its own with the steps before it.
BUILD = [
    dict(id='answer', files=['RequestContext.java', 'Limit.java', 'Decision.java',
                             'RateLimitResult.java', 'RateLimiter.java'], demo='AnswerDemo'),
    dict(id='time', files=['Clock.java', 'SystemClock.java', 'ManualClock.java'], demo='TimeDemo'),
    dict(id='bucket', files=['Bucket.java', 'TokenBucket.java'], demo='BucketDemo'),
    dict(id='count', files=['SlidingWindowLog.java', 'FixedWindowCounter.java',
                            'BucketFactory.java', 'Algorithm.java'], demo='CountDemo'),
    dict(id='budget', files=['KeyScope.java', 'LimitPolicy.java', 'Plan.java', 'Plans.java',
                             'PlanLimits.java'], demo='BudgetDemo'),
    dict(id='book', files=['RateLimitRule.java', 'RuleBook.java', 'ScoreApiRules.java'],
         demo='RuleBookDemo'),
    dict(id='store', files=['BucketStore.java', 'InMemoryBucketStore.java'], demo='StoreDemo'),
    dict(id='limiter', files=['RuleBasedRateLimiter.java', 'RateLimitListener.java',
                              'RefusalMetrics.java'], demo='LimiterDemo'),
    dict(id='door', files=['RateLimitFilter.java'], demo='DoorDemo'),
    dict(id='run', files=['Main.java'], demo='Main'),
    dict(id='tests', files=['RateLimiterTest.java'], demo='RateLimiterTest'),
]

# The demo each follow-up runs (it checks its own numbers; see demos/Check.java).
DEMOS = {'more': 'MoreDemo', 'credits': 'CreditsDemo', 'live': 'LiveDemo', 'idle': 'IdleDemo',
         'waiting': 'WaitingDemo', 'redis': 'RedisDemo', 'lockfree': 'LockFreeDemo',
         'cousins': 'CousinsDemo'}

# Extra programs run against a snapshot: their output answers questions elsewhere on the page.
EXTRA = [('FirstCut', 'core'), ('QuizDemo', 'core'), ('CostDemo', 'core')]

CORE_TYPES = ['RequestContext', 'Limit', 'Decision', 'RateLimitResult', 'RateLimiter', 'Clock',
              'SystemClock', 'ManualClock', 'Bucket', 'TokenBucket', 'SlidingWindowLog',
              'FixedWindowCounter', 'BucketFactory', 'Algorithm', 'KeyScope', 'LimitPolicy',
              'Plan', 'Plans', 'PlanLimits', 'RateLimitRule', 'RuleBook', 'ScoreApiRules',
              'BucketStore', 'InMemoryBucketStore', 'RuleBasedRateLimiter', 'RateLimitListener',
              'RefusalMetrics', 'RateLimitFilter', 'Main', 'RateLimiterTest']
FILE_ORDER = [t + '.java' for t in CORE_TYPES] + [t + '.java' for t in [
    'SlidingWindowCounter', 'LeakyBucket', 'CreditBucket', 'ShadowRateLimiter', 'Waiting',
    'RedisBucketStore', 'RedisTokenBucket', 'FakeRedis', 'AtomicTokenBucket', 'HitCounter',
    'LoggerRateLimiter']]

STRIP = [
    ('answer', ['RequestContext', 'Limit', 'Decision', 'RateLimitResult', 'RateLimiter']),
    ('time', ['Clock', 'SystemClock', 'ManualClock']),
    ('count', ['Bucket', 'TokenBucket', 'SlidingWindowLog', 'FixedWindowCounter',
               'BucketFactory', 'Algorithm']),
    ('budget', ['KeyScope', 'LimitPolicy', 'Plan', 'Plans', 'PlanLimits']),
    ('rules', ['RateLimitRule', 'RuleBook', 'ScoreApiRules']),
    ('store', ['BucketStore', 'InMemoryBucketStore']),
    ('limiter', ['RuleBasedRateLimiter', 'RateLimitListener', 'RefusalMetrics']),
    ('door', ['RateLimitFilter']),
    ('proof', ['Main', 'RateLimiterTest']),
]

# Broken copies of the core. The build makes each change, runs the tests, and stops unless the
# named test fails on every run (other tests may fail too).
REFUND = """                for (Bucket spent : charged) {
                    spent.refund(request.cost(), now);
                }
"""
GUARD = """        if (elapsed <= 0) {
            return;
        }
"""
ISOLATED = """            try {
                listener.onDecision(request, result);
            } catch (RuntimeException broken) {
                // In production: log it. The request goes on either way.
            }"""
REFILL = 'tokens = Math.min(capacity, tokens + elapsed / millisPerToken);'

MUTANTS = [
    dict(label='no lock',
         edits=[('TokenBucket.java', 'public synchronized Decision tryConsume',
                 'public Decision tryConsume')],
         test='many threads on one client get exactly its limit', runs=10,
         html='Remove <code>synchronized</code> from <code>TokenBucket.tryConsume</code>'),
    dict(label='get, then put',
         edits=[('InMemoryBucketStore.java',
                 'bucket = buckets.computeIfAbsent(key, k -> factory.create(limit, nowMillis));',
                 'bucket = factory.create(limit, nowMillis);\n            buckets.put(key, bucket);')],
         test='threads that meet a new client share one bucket', runs=10,
         html='Replace <code>computeIfAbsent</code> with <code>put</code> after the '
              '<code>get</code> finds nothing'),
    dict(label='whole tokens',
         edits=[('TokenBucket.java', 'private double tokens;', 'private long tokens;'),
                ('TokenBucket.java', REFILL,
                 'tokens = Math.min(capacity, tokens + (long) (elapsed / millisPerToken));')],
         test='a refusal says exactly when to retry', runs=1,
         html='Keep tokens in a <code>long</code>, so 120 ms earns 0 instead of 0.6'),
    dict(label='no refund',
         edits=[('RuleBasedRateLimiter.java', REFUND, '')],
         test='a refused request spends nothing, in any rule', runs=1,
         html='Drop the refund loop: a later rule refuses, the earlier buckets keep the tokens'),
    dict(label='refusals spend',
         edits=[('TokenBucket.java', '        long waitMillis = (long) Math.ceil',
                 '        tokens -= cost;\n        long waitMillis = (long) Math.ceil')],
         test='a refused request spends nothing, in any rule', runs=1,
         html='Let a refusal take tokens too'),
    dict(label='no cap',
         edits=[('TokenBucket.java', REFILL, 'tokens = tokens + elapsed / millisPerToken;')],
         test='quiet time never fills a bucket past its capacity', runs=1,
         html='Drop <code>Math.min(capacity, ...)</code> from the refill'),
    dict(label='no time guard',
         edits=[('TokenBucket.java', GUARD, '')],
         test='a clock that jumps back neither earns nor takes tokens', runs=1,
         html='Drop <code>if (elapsed &lt;= 0) return;</code> from the refill'),
    dict(label='limit not in the key',
         edits=[('RuleBasedRateLimiter.java',
                 'String key = rule.name() + "|" + rule.scope().keyOf(request) + "|" + limit;',
                 'String key = rule.name() + "|" + rule.scope().keyOf(request);')],
         test="each client gets its plan's budget; an upgrade applies at once", runs=1,
         html='Leave the limit out of the bucket key'),
    dict(label='loosest remaining',
         edits=[('RuleBasedRateLimiter.java', 'remaining = Math.min(remaining, d.remaining());',
                 'remaining = Math.max(remaining, d.remaining());')],
         test="the tightest rule's remaining is reported", runs=1,
         html='Report the <em>largest</em> remaining across the rules, not the smallest'),
    dict(label='listener not isolated',
         edits=[('RuleBasedRateLimiter.java', ISOLATED,
                 '            listener.onDecision(request, result);')],
         test='a listener that throws does not break a request', runs=1,
         html='Call listeners without the <code>try</code>/<code>catch</code>'),
]

# Written next to the page as rate-limiter-code/README.md, with the runnable projects.
EXPORT_README = """# Rate limiter: the code, ready to run

The code from `rate-limiter-workbench.html`, generated by `workbench/build.py` from the same
sources, so it always matches the page.

| folder | what is in it |
|---|---|
| `core/` | the design from the page's build steps: the rule-based limiter, `Main` and `RateLimiterTest` |
| `complete/` | the core plus every follow-up, with each follow-up's demo ({demos}) |
| `practice/` | only `RateLimiterTest.java`: write your own classes next to it, then run the tests |
| `steps/<step>/` | the code exactly as it is after each follow-up step: start drill 3 from these |

Each folder is a plain Maven project (Java 17, no dependencies). In IntelliJ: File > Open, pick
the folder, then run `Main` or `RateLimiterTest` from the green arrow.

From a terminal, without Maven:

```
cd core
javac -d out src/main/java/*.java
java -cp out Main
java -cp out RateLimiterTest
```
"""

CONFIG = dict(SLUG=SLUG, NAME=NAME, TITLE=TITLE, SUBTITLE=SUBTITLE, SNAPS=SNAPS, BUILD=BUILD,
              DEMOS=DEMOS, FILE_ORDER=FILE_ORDER, STRIP=STRIP, MUTANTS=MUTANTS,
              CORE_TYPES=CORE_TYPES, EXTRA=EXTRA, EXPORT_README=EXPORT_README)
