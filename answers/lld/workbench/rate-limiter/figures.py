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
    s.text(437, 102, 'plan · quota · search · login · global', 'sv-m', 11, 'middle')
    s.text(437, 122, 'every rule that covers the request', 'sv-m', 11, 'middle')
    s.box(290, 170, 294, 56, 'fetch the scores', 'the real work: cache, database')
    s.path('M437 146 L437 168', 'sv-ln g', end='g')
    s.text(447, 162, 'allowed', 'sv-g', 12)
    s.box(686, 22, 246, 64, '429 Too Many Requests', 'Retry-After: 1 · nothing else runs',
          'sv-box bad')
    s.path('M584 80 L684 58', 'sv-ln r', end='r')
    s.text(606, 58, 'refused', 'sv-r', 12)
    s.box(686, 166, 246, 64, '200 OK + the scores', 'X-RateLimit-Remaining: 3', 'sv-box good')
    s.path('M584 198 L684 198', 'sv-ln g', end='g')
    return s.render('Clients call the score API. The rate limiter checks every rule that covers the '
                    'request first: refused requests get 429 at once, allowed ones go on to the work.')


def classes():
    """The core, in layers: the front door, the limiter, what it is handed, rules, counting."""
    s = Svg(960, 1010)

    def lane(y, h, label):
        s.rect(4, y, 952, h, 'sv-box lane', 10)
        s.text(16, y + 18, label, 'sv-acc', 11, 'start', 600)

    # --- the front door
    lane(6, 118, 'the front door')
    _, filt = s.uml(24, 34, 250, 'RateLimitFilter', None, ('limiter: RateLimiter',),
                    ('handle(request, endpoint)',), size=12)
    _, rl = s.uml(350, 30, 280, 'RateLimiter', 'interface', (),
                  ('check(RequestContext): RateLimitResult',), size=12)
    _, http = s.uml(706, 34, 234, 'HttpResponse', 'record', ('status, headers, body',), (), size=12)
    s.path(f'M{filt["x"] + filt["w"]} {filt["y"] + 30} L{rl["x"] - 2} {filt["y"] + 30}', 'sv-ln',
           end='m')

    # --- the limiter
    lane(134, 150, 'the limiter')
    _, lim = s.uml(300, 158, 380, 'RuleBasedRateLimiter', None,
                   ('rules: RuleBook   store: BucketStore', 'clock: Clock   listeners: List<…>'),
                   ('check(request): all rules, all or nothing', 'addListener(listener)'),
                   cls='now', size=12)
    s.path(f'M490 {lim["y"]} L490 {rl["y"] + rl["h"] + 2}', 'sv-ln dash', end='tri')
    _, res = s.uml(706, 158, 234, 'RateLimitResult', 'record',
                   ('allowed, remaining,', 'retryAfterMillis, refusedBy'), (), size=12)
    _, req = s.uml(24, 158, 250, 'RequestContext', 'record',
                   ('clientId, ip, endpoint, cost',), (), size=12)

    # --- handed in
    lane(294, 206, 'handed in')
    y3 = 322
    _, book = s.uml(24, y3, 210, 'RuleBook', None, ('rules: List<RateLimitRule>',),
                    ('matching(request)',), size=12)
    _, store = s.uml(254, y3, 230, 'BucketStore', 'interface', (),
                     ('bucketFor(key, algorithm,', '  limit, now): Bucket'), size=12)
    _, lis = s.uml(504, y3, 220, 'RateLimitListener', 'interface', (),
                   ('onDecision(request, result)',), size=12)
    _, clk = s.uml(744, y3, 196, 'Clock', 'interface', (), ('nowMillis()',), size=12)
    for box, x in ((book, 150), (store, 380), (lis, 600), (clk, 800)):
        s.path(f'M{min(max(x, lim["x"] + 20), lim["x"] + lim["w"] - 20)} {lim["y"] + lim["h"]} '
               f'L{box["x"] + box["w"] / 2} {box["y"] - 2}', 'sv-ln', end='m')
    y4 = 432
    _, mem = s.uml(254, y4, 230, 'InMemoryBucketStore', None,
                   ('ConcurrentHashMap<key, Bucket>',), (), size=12)
    _, met = s.uml(504, y4, 220, 'RefusalMetrics', None, ('LongAdder per rule, client',), (),
                   size=12)
    _, sc = s.uml(744, y4, 94, 'SystemClock', None, (), (), size=11)
    _, mc = s.uml(846, y4, 94, 'ManualClock', None, (), (), size=11)
    for sub, sup in ((mem, store), (met, lis), (sc, clk), (mc, clk)):
        s.path(f'M{sub["x"] + sub["w"] / 2} {sub["y"]} L{sub["x"] + sub["w"] / 2} '
               f'{sup["y"] + sup["h"] + 2}', 'sv-ln dash', end='tri')
    _, cfg = s.uml(24, y4, 210, 'ScoreApiRules', None, (), ('build(plans): RuleBook',), size=12)
    s.path(f'M{cfg["x"] + cfg["w"] / 2} {cfg["y"]} L{book["x"] + book["w"] / 2} '
           f'{book["y"] + book["h"] + 2}', 'sv-ln dash', end='m')

    # --- one rule
    lane(510, 250, 'one rule')
    y5 = 538
    _, rule = s.uml(24, y5, 250, 'RateLimitRule', 'record',
                    ('name, appliesTo', 'scope: KeyScope', 'limits: LimitPolicy',
                     'algorithm: Algorithm'), (), size=12)
    s.path(f'M{book["x"]} {book["y"] + 30} L14 {book["y"] + 30} L14 {rule["y"] + 30} '
           f'L{rule["x"] - 2} {rule["y"] + 30}', 'sv-ln', end='m', start='dia')
    _, ks = s.uml(300, y5, 196, 'KeyScope', 'enum',
                  ('CLIENT, IP,', 'CLIENT_AND_ENDPOINT, EVERYONE'), (), size=11.5)
    _, lp = s.uml(516, y5, 200, 'LimitPolicy', 'interface', (), ('limitFor(request): Limit',),
                  size=12)
    _, alg = s.uml(736, y5, 204, 'Algorithm', 'enum',
                   ('TOKEN_BUCKET, SLIDING_WINDOW_LOG,', 'FIXED_WINDOW'),
                   ('newBucket(limit, now)',), size=11)
    y6 = 668
    _, pl = s.uml(516, y6, 200, 'PlanLimits', None, ('Plans + EnumMap<Plan, Limit>',), (),
                  size=11.5)
    s.path(f'M616 {pl["y"]} L616 {lp["y"] + lp["h"] + 2}', 'sv-ln dash', end='tri')
    _, plans = s.uml(300, y6, 196, 'Plans', None, ('client -> Plan (FREE, PRO)',), (), size=11.5)
    s.path(f'M{pl["x"]} {pl["y"] + 28} L{plans["x"] + plans["w"] + 2} {plans["y"] + 28}',
           'sv-ln', end='m')
    _, bf = s.uml(736, y6, 204, 'BucketFactory', 'interface', (), ('create(limit, now)',),
                  size=12)
    s.path(f'M838 {alg["y"] + alg["h"]} L838 {bf["y"] - 2}', 'sv-ln', end='m')

    # --- counting
    lane(770, 234, 'counting')
    y7 = 798
    _, bk = s.uml(320, y7, 320, 'Bucket', 'interface', (),
                  ('tryConsume(cost, now): Decision', 'refund(cost, now)'), size=12)
    s.path(f'M{bf["x"] + bf["w"] / 2} {bf["y"] + bf["h"]} C 840 800, 700 820, '
           f'{bk["x"] + bk["w"] + 2} {bk["y"] + 34}', 'sv-ln dash', end='m')
    s.text(760, 790, 'creates', 'sv-m', 10.5)
    y8 = 912
    subs = [('TokenBucket', 'bursts, then a steady rate', 40),
            ('SlidingWindowLog', 'exact: sign-ins', 350),
            ('FixedWindowCounter', 'one counter: daily quota', 660)]
    for name, note, x in subs:
        _, b = s.uml(x, y8, 260, name, None, (note,), (), cls='acc' if x == 40 else '', size=12)
        s.path(f'M{x + 130} {y8} L{bk["x"] + bk["w"] / 2} {bk["y"] + bk["h"] + 2}', 'sv-ln dash',
               end='tri')
    s.text(24, 812, 'values:', 'sv-m', 11)
    s.text(24, 830, 'Limit, Decision', 'sv-t', 11.5)
    s.text(24, 848, '(records)', 'sv-m', 11)
    return s.render('Class diagram of the core in five layers: the filter, the rule-based '
                    'limiter, what it is handed (rule book, bucket store, listeners, clock), the '
                    'parts of one rule, and the buckets that count.')


def journey():
    """fantasy-app's third search in one second: three rules, the refund, the listeners."""
    parts = [('RateLimitFilter', 'the front door'), ('RuleBasedRateLimiter', None),
             ('RuleBook', None), ('BucketStore', 'in memory'), ('bucket', '"plan"'),
             ('bucket', '"search"'), ('RefusalMetrics', 'a listener')]
    ev = [
        ('sep', "fantasy-app's 3rd search in the same second"),
        ('call', 0, 1, 'check(request)'),
        ('self', 1, 'now = clock.nowMillis(): one instant for every rule'),
        ('call', 1, 2, 'matching(request)'),
        ('ret', 2, 1, 'plan, quota, search, global'),
        ('call', 1, 3, 'bucketFor("plan|fantasy-app|50/1000ms", …)'),
        ('call', 1, 4, 'tryConsume(1, now)'),
        ('ret', 4, 1, 'allowed, 47 left', 'g'),
        ('self', 1, '"quota": allowed, likewise'),
        ('call', 1, 5, 'tryConsume(1, now)'),
        ('ret', 5, 1, 'refused, retry in 500 ms', 'r'),
        ('call', 1, 4, 'refund(1, now): all or nothing', 'y'),
        ('self', 1, 'quota refunded too; "global" is never asked'),
        ('call', 1, 6, 'onDecision(request, result)'),
        ('ret', 1, 0, 'refused by search, retry in 500 ms', 'r'),
        ('self', 0, '429 · Retry-After: 1'),
    ]
    return sequence(parts, ev, w=1060, pad=66, name_size=12,
                    label='Sequence diagram of one refused search: the plan and '
                                            'quota buckets allow it, the search bucket refuses, '
                                            'and the earlier tokens are given back.')


def redis():
    """Many servers: every server spends from one bucket in Redis."""
    s = Svg(940, 250)
    for i, y in enumerate((20, 96, 172)):
        s.box(8, y, 196, 56, f'API server {i + 1}', 'RedisBucketStore')
        s.path(f'M204 {y + 28} C 280 {y + 28}, 290 124, 372 124', 'sv-ln acc', end='acc')
    s.text(288, 108, 'EVALSHA script', 'sv-acc', 11.5, 'middle')
    s.text(288, 146, 'one key per bucket', 'sv-m', 11, 'middle')
    s.rect(376, 16, 556, 216, 'sv-box now', 12)
    s.text(398, 44, 'Redis: runs one script at a time, so the script is one step', 'sv-t', 13,
           'start', 600)
    s.rect(398, 62, 512, 64, 'sv-box rec', 8)
    s.text(414, 86, 'rl:plan|fantasy-app|50/1000ms  →  { tokens: 12.4, last: … }', 'sv-mono sv-t',
           12)
    s.text(414, 108, 'one hash per bucket: the two numbers a TokenBucket keeps', 'sv-m', 11)
    rows = ["1  TIME: now from Redis's clock, not each server's",
            '2  refill, check, take: the same three lines as TokenBucket',
            '3  HSET the numbers; PEXPIRE: an idle bucket deletes itself']
    for i, r in enumerate(rows):
        s.text(414, 150 + i * 22, r, 'sv-t', 12)
    return s.render('Three API servers send the same Lua script to one Redis server, which holds one '
                    'hash per bucket and runs one script at a time.')
