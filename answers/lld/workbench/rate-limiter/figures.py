"""The rate limiter's figures, drawn with ../svg.py. Each function returns an <svg> string."""
from svg import Svg, sequence


def flow():
    """Where the limiter sits: the front door of the API, before any work."""
    s = Svg(940, 250)
    clients = [('score-widget', 'FREE · 5 a second', 14), ('fantasy-app', 'PRO · 50 a second', 94),
               ('someone signing in', 'no key yet · by IP', 174)]
    for name, sub, y in clients:
        s.box(8, y, 184, 56, name, sub)
        s.path(f'M192 {y + 28} C 240 {y + 28}, 240 96, 290 96', 'sv-ln', end='m')
    s.rect(262, 8, 350, 234, 'sv-box lane', 12)
    s.text(437, 30, 'our score API', 'sv-m', 12, 'middle')
    s.rect(290, 46, 294, 100, 'sv-box now', 7)
    s.text(437, 76, 'rate limiter', 'sv-t', 13.5, 'middle', 600)
    s.text(437, 102, 'rate · daily · search · login · global', 'sv-m', 11, 'middle')
    s.text(437, 122, 'every rule that covers the request', 'sv-m', 11, 'middle')
    s.box(290, 170, 294, 56, 'fetch the scores', 'the real work: cache, database')
    s.path('M437 146 L437 168', 'sv-ln g', end='g')
    s.text(447, 162, 'allowed', 'sv-g', 12)
    s.box(686, 22, 246, 64, '429 Too Many Requests', 'Retry-After: 1 · nothing else runs',
          'sv-box bad')
    s.path('M584 80 L684 58', 'sv-ln r', end='r')
    s.text(606, 58, 'refused', 'sv-r', 12)
    s.box(686, 166, 246, 64, '200 OK + the scores', 'the work ran', 'sv-box good')
    s.path('M584 198 L684 198', 'sv-ln g', end='g')
    return s.render('Clients call the score API. The rate limiter checks every rule that covers the '
                    'request first: refused requests get 429 at once, allowed ones go on to the work.')


# The class diagram, grown stage by stage in the order the design is thought through. Every box
# has a fixed place; a stage draws the boxes of that stage and the ones before it, the new ones
# highlighted, so the reader watches the same picture grow.
STAGES = ['door', 'limiter', 'rules', 'limits', 'counters', 'store']
LANES = [  # (label, top, height, stage that first shows it)
    ('1 · the front door: who asks?', 6, 190, 'door'),
    ('2 · the limiter, and what it is handed', 206, 180, 'limiter'),
    ('3 · one rule: which requests, whose budget, how much, how it counts', 396, 330, 'rules'),
    ('4 · counting: how one budget is counted', 736, 270, 'counters'),
]


def classes(upto=None):
    """The core's class diagram. upto: the last stage to draw (None: all, nothing highlighted)."""
    last = STAGES.index(upto) if upto else len(STAGES) - 1
    seen = lambda st: STAGES.index(st) <= last
    hot = lambda st: upto is not None and st == upto
    lanes = [l for l in LANES if seen(l[3])]
    height = lanes[-1][1] + lanes[-1][2] + 8
    s = Svg(980, height)
    for label, top, h, _ in lanes:
        s.rect(4, top, 972, h, 'sv-box lane', 10)
        s.text(16, top + 18, label, 'sv-acc', 11, 'start', 600)
    box = {}

    def b(st, key, *a, **k):
        if seen(st):
            if hot(st):
                k['cls'] = 'new'
            _, box[key] = s.uml(*a, **k)

    # 1 · the door
    b('door', 'filter', 20, 34, 260, 'RateLimitFilter', None, ('limiter: RateLimiter',),
      ('handle(request, work): Response',), size=12)
    b('door', 'rl', 320, 34, 330, 'RateLimiter', 'interface', (),
      ('check(Request): RateLimitResult', 'rateLimit(customerId): boolean'), size=12)
    b('door', 'req', 690, 30, 270, 'Request', 'record', ('customerId, ip, endpoint',), (), size=12)
    b('door', 'res', 690, 110, 270, 'RateLimitResult', 'record',
      ('allowed, retryAfterMillis, refusedBy',), (), size=11.5)
    # 2 · the limiter
    b('limiter', 'lim', 20, 234, 380, 'RuleBasedRateLimiter', None,
      ('rules: List<RateLimitRule>', 'counters: CounterStore   clock: Clock'),
      ('check(request): every rule, or none',), size=12)
    b('limiter', 'clock', 430, 234, 180, 'Clock', 'interface', (), ('nowMillis()',), size=12)
    b('store', 'cs', 640, 234, 320, 'CounterStore', 'interface', (),
      ('counterFor(key, limit, algorithm, now)',), size=11.5)
    b('store', 'mem', 640, 318, 320, 'InMemoryCounterStore', None,
      ('ConcurrentHashMap<key, Counter>',), (), size=11.5)
    # 3 · one rule
    b('rules', 'rule', 20, 424, 300, 'RateLimitRule', 'record',
      ('name', 'match: Match', 'countPer: CountPer → keyFor()', 'limits: LimitPolicy',
       'algorithm: Algorithm'), (), size=11.5)
    b('rules', 'cfg', 20, 600, 300, 'ScoreApiRules', None, (),
      ('build(customers): the rules, in order',), size=11.5)
    b('rules', 'match', 350, 424, 250, 'Match', 'record', ('caller, endpoint',),
      ('matches(request)',), size=11.5)
    b('rules', 'caller', 350, 536, 250, 'Caller', 'enum', ('CUSTOMER, ANY',), (), size=11.5)
    b('rules', 'cp', 350, 620, 250, 'CountPer', 'enum',
      ('CUSTOMER, IP,', 'CUSTOMER_AND_ENDPOINT, EVERYONE'), (), size=11)
    b('limits', 'lp', 630, 424, 330, 'LimitPolicy', 'interface', (),
      ('limitFor(request): Limit',), size=12)
    b('limits', 'fixed', 630, 516, 150, 'FixedLimit', 'record', ('limit',), (), size=11.5)
    b('limits', 'plim', 800, 516, 160, 'PlanLimit', None, ('customers, field',), (), size=11.5)
    b('limits', 'plan', 630, 602, 150, 'Plan', 'enum', ('FREE, PRO',), (), size=11.5)
    b('limits', 'cust', 800, 602, 160, 'Customers', None, ('id → Plan',), (), size=11.5)
    # 4 · counting
    b('counters', 'dec', 20, 764, 280, 'Decision', 'record', ('allowed, retryAfterMillis',), (),
      size=11.5)
    b('counters', 'ctr', 330, 764, 320, 'Counter', 'interface', (),
      ('tryAcquire(now): Decision', 'refund(now)'), size=12)
    b('counters', 'fac', 680, 764, 280, 'CounterFactory', None, (),
      ('create(algorithm, limit, now)',), size=11.5)
    b('counters', 'alg', 680, 838, 280, 'Algorithm', 'enum',
      ('TOKEN_BUCKET, FIXED_WINDOW,', 'SLIDING_WINDOW_LOG'), (), size=11)
    for key, name, note, x in (('tb', 'TokenBucket', 'rate, search, global', 20),
                               ('fw', 'FixedWindowCounter', 'daily', 335),
                               ('sl', 'SlidingWindowLog', 'login: exact', 650)):
        b('counters', key, x, 936, 290, name, None, (note,), (), size=11.5)

    def arrow(a, b_, d, cls='sv-ln', end='m', start=None, label=None, at=None):
        if a in box and b_ in box:
            s.path(d, cls, end=end, start=start)
            if label:
                s.text(at[0], at[1], label, 'sv-m', 10.5)

    arrow('filter', 'rl', 'M280 70 L318 70')                                    # asks
    arrow('lim', 'rl', 'M300 234 L420 122', 'sv-ln dash', end='tri')         # implements
    arrow('lim', 'clock', 'M400 268 L428 268')
    arrow('lim', 'cs', 'M400 318 L620 318 L620 268 L638 268')
    arrow('mem', 'cs', 'M800 318 L800 303', 'sv-ln dash', end='tri')
    arrow('lim', 'rule', 'M170 335 L170 422', start='dia')                    # holds the list
    arrow('cfg', 'rule', 'M170 600 L170 557', 'sv-ln dash', label='builds', at=(178, 588))
    arrow('rule', 'match', 'M320 466 L348 466')
    arrow('match', 'caller', 'M475 518 L475 534')
    arrow('rule', 'cp', 'M320 540 L335 540 L335 662 L348 662')
    arrow('rule', 'lp', 'M320 526 L615 526 L615 456 L628 456')
    arrow('fixed', 'lp', 'M705 516 L705 493', 'sv-ln dash', end='tri')
    arrow('plim', 'lp', 'M880 516 L880 493', 'sv-ln dash', end='tri')
    arrow('plim', 'cust', 'M880 573 L880 600')
    arrow('cust', 'plan', 'M800 630 L782 630')
    arrow('ctr', 'dec', 'M330 804 L302 804')
    arrow('fac', 'ctr', 'M680 792 L652 792', label='creates', at=(654, 784))
    arrow('fac', 'alg', 'M820 821 L820 836')
    for k, x in (('tb', 165), ('fw', 480), ('sl', 690)):
        arrow(k, 'ctr', f'M{x} 936 L490 850', 'sv-ln dash', end='tri')
    arrow('mem', 'fac', 'M960 350 L970 350 L970 790 L962 790', label='uses', at=(930, 760))
    stage = f'after "{upto}"' if upto else 'the whole core'
    return s.render(f'Class diagram of the rate limiter core, {stage}: the front door, the '
                    'limiter and what it is handed, one rule (its match, whose budget, how much) '
                    'and the counters.')


def journey():
    """fantasy-app's third search in one second: rules in order, a refusal, the refund."""
    parts = [('RateLimitFilter', 'the front door'), ('RuleBasedRateLimiter', None),
             ('CounterStore', 'in memory'), ('counter', '"rate:fantasy-app"'),
             ('counter', '"daily:fantasy-app"'), ('counter', '"search:fantasy-app:…"')]
    ev = [
        ('sep', "fantasy-app (PRO) sends its 3rd search in the same second"),
        ('call', 0, 1, 'check(request)'),
        ('self', 1, 'now = clock.nowMillis(): one instant for every rule'),
        ('self', 1, 'rule "rate" covers it: key "rate:fantasy-app", limit from PRO: 50/s'),
        ('call', 1, 2, 'counterFor("rate:fantasy-app", 50/s, TOKEN_BUCKET)'),
        ('call', 1, 3, 'tryAcquire(now)'),
        ('ret', 3, 1, 'allowed', 'g'),
        ('call', 1, 4, 'tryAcquire(now)  (rule "daily", found the same way)'),
        ('ret', 4, 1, 'allowed', 'g'),
        ('call', 1, 5, 'tryAcquire(now)  (rule "search": 2 a second)'),
        ('ret', 5, 1, 'refused: retry in 500 ms', 'r'),
        ('call', 1, 3, 'refund(now)', 'y'),
        ('call', 1, 4, 'refund(now)', 'y'),
        ('self', 1, 'rule "global" is never asked: the answer is already no'),
        ('ret', 1, 0, 'refused by search, retry in 500 ms', 'r'),
        ('self', 0, '429 · Retry-After: 1 · X-RateLimit-Rule: search'),
    ]
    return sequence(parts, ev, w=1180, pad=120, name_size=12,
                    label='Sequence diagram of fantasy-app\'s third search in a second: the rate '
                          'and daily counters allow it, the search counter refuses, the first two '
                          'are refunded, and the door answers 429.')
