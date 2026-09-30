"""The rate limiter's figures, drawn with ../svg.py. Each function returns an <svg> string."""
from svg import Svg, sequence


def flow():
    """Where the limiter sits: before any work, inside the API server."""
    s = Svg(940, 236)
    clients = [('score-widget', 'FREE · 5 a second', 16), ('fantasy-app', 'PRO · 50 a second', 92),
               ('cricket-blog', 'FREE · 5 a second', 168)]
    for name, sub, y in clients:
        s.box(8, y, 184, 52, name, sub)
        s.path(f'M192 {y + 26} C 240 {y + 26}, 240 84, 290 84', 'sv-ln', end='m')
    s.rect(262, 8, 350, 220, 'sv-box lane', 12)
    s.text(437, 30, 'our score API', 'sv-m', 12, 'middle')
    s.box(290, 50, 294, 68, 'rate limiter', 'tryAcquire(clientId)', 'sv-box now')
    s.box(290, 150, 294, 60, 'fetch the scores', 'the real work: cache, database')
    s.path('M437 118 L437 148', 'sv-ln g', end='g')
    s.text(447, 138, 'allowed', 'sv-g', 12)
    s.box(686, 22, 246, 64, '429 Too Many Requests', 'Retry-After: 1 · nothing else runs',
          'sv-box bad')
    s.path('M584 76 L684 58', 'sv-ln r', end='r')
    s.text(606, 56, 'refused', 'sv-r', 12)
    s.box(686, 148, 246, 64, '200 OK + the scores', 'X-RateLimit-Remaining: 3', 'sv-box good')
    s.path('M584 180 L684 180', 'sv-ln g', end='g')
    return s.render('Three client apps call the score API. The rate limiter answers first: refused '
                    'requests get 429 at once, allowed ones go on to fetch the scores.')


def classes():
    """The core: 12 types, who holds whom, who implements what."""
    s = Svg(960, 800)
    # row A: the caller, the interface it sees, and the answer
    s.rect(10, 26, 170, 56, 'sv-box dash', 8)
    s.text(95, 50, 'the API', 'sv-t', 13.5, 'middle', 600)
    s.text(95, 68, 'calls one method', 'sv-m', 11, 'middle')
    hA, rl = s.uml(300, 16, 360, 'RateLimiter', 'interface', (), ['tryAcquire(clientId): Decision'])
    hD, dec = s.uml(716, 8, 234, 'Decision', 'record',
                    ['allowed: boolean', 'remaining: long', 'retryAfterMillis: long'],
                    ['allow(remaining)', 'deny(retryAfterMillis)'])
    s.path(f'M180 54 L{rl["x"] - 2} 54', 'sv-ln', end='m')
    s.path(f'M{rl["x"] + rl["w"]} {rl["y"] + 34} L{dec["x"] - 2} {rl["y"] + 34}', 'sv-ln dash', end='m')
    s.text(688, rl['y'] + 27, 'returns', 'sv-m', 11, 'middle')
    # row B: the limiter, with time on its left and limits on its right
    yB = 196
    hC, crl = s.uml(290, yB, 380, 'ClientRateLimiter', None,
                    ['buckets: ConcurrentHashMap<String, Bucket>', 'plans: Plans',
                     'factory: BucketFactory', 'clock: Clock'],
                    ['tryAcquire(clientId): Decision'], cls='now')
    s.path(f'M480 {yB} L480 {rl["y"] + rl["h"] + 2}', 'sv-ln dash', end='tri')
    s.text(488, yB - 30, 'implements', 'sv-m', 11)
    hK, clk = s.uml(10, yB + 30, 200, 'Clock', 'interface', (), ['nowMillis(): long'])
    s.path(f'M{crl["x"]} {yB + 68} L{clk["x"] + clk["w"] + 2} {yB + 68}', 'sv-ln', end='m')
    hP, pl = s.uml(740, yB + 10, 210, 'Plans', None, ['limitOf: Plan → Limit', 'planOf: id → Plan'],
                   ['assign(clientId, plan)', 'limitFor(clientId)'])
    s.path(f'M{crl["x"] + crl["w"]} {yB + 68} L{pl["x"] - 2} {yB + 68}', 'sv-ln', end='m')
    # row C: the clocks, and the plan types
    yC = yB + hC + 44
    hS, sc = s.uml(10, yC, 118, 'SystemClock', None, (), ['nanoTime'], size=12)
    hM, mc = s.uml(138, yC, 142, 'ManualClock', None, (), ['advance(millis)'], size=12)
    for c in (sc, mc):
        s.path(f'M{c["x"] + c["w"] / 2} {c["y"]} L{c["x"] + c["w"] / 2} {clk["y"] + clk["h"] + 2}',
               'sv-ln dash', end='tri')
    hL, lim = s.uml(740, yC, 210, 'Limit', 'record', ['capacity: int', 'periodMillis: long'],
                    ['perSecond(n)', 'millisPerToken()'])
    hN, pn = s.uml(636, yC, 94, 'Plan', 'enum', ['FREE, PRO'], ())
    s.path(f'M845 {pl["y"] + pl["h"]} L845 {lim["y"] - 2}', 'sv-ln', end='m')
    s.path(f'M760 {pl["y"] + pl["h"]} L700 {pn["y"] - 2}', 'sv-ln', end='m')
    # row D: making and holding buckets
    yD = yC + hL + 36
    hF, fac = s.uml(236, yD, 250, 'BucketFactory', 'interface', (), ['create(limit, now): Bucket'])
    hB, bk = s.uml(560, yD, 230, 'Bucket', 'interface', (), ['tryConsume(now): Decision'])
    s.path(f'M{crl["x"] + 70} {crl["y"] + crl["h"]} L{crl["x"] + 70} {fac["y"] - 2}', 'sv-ln', end='m')
    s.text(crl['x'] + 78, crl['y'] + crl['h'] + 20, 'makes new buckets', 'sv-m', 11)
    s.path(f'M{crl["x"] + 310} {crl["y"] + crl["h"] + 1} L{crl["x"] + 310} {bk["y"] - 2}', 'sv-ln',
           end='m', start='dia')
    s.text(crl['x'] + 318, crl['y'] + crl['h'] + 20, 'one per client', 'sv-m', 11)
    s.path(f'M{fac["x"] + fac["w"]} {fac["y"] + 40} L{bk["x"] - 2} {bk["y"] + 40}', 'sv-ln dash', end='m')
    s.text((fac['x'] + fac['w'] + bk['x']) / 2, fac['y'] + 33, 'creates', 'sv-m', 11, 'middle')
    # row E: the one class with the arithmetic and the lock
    yE = yD + max(hF, hB) + 40
    hT, tb = s.uml(500, yE, 350, 'TokenBucket', None,
                   ['capacity: int', 'millisPerToken: double', 'tokens: double',
                    'lastRefillMillis: long'],
                   ['synchronized tryConsume(now)', 'refill(now)'], cls='acc')
    s.path(f'M675 {yE} L675 {bk["y"] + bk["h"] + 2}', 'sv-ln dash', end='tri')
    s.text(683, yE - 14, 'implements', 'sv-m', 11)
    # legend
    ly = yE + 30
    s.text(10, ly, 'how to read it', 'sv-acc', 11.5, 'start', 600)
    rows = [('──▷', 'implements (dashed)'), ('◆──▶', 'holds, one per client'),
            ('──▶', 'uses: handed in through the constructor'), ('- - ▶', 'returns / creates')]
    for i, (sym, txt) in enumerate(rows):
        s.text(10, ly + 22 + i * 19, sym, 'sv-m', 11.5)
        s.text(56, ly + 22 + i * 19, txt, 'sv-m', 11.5)
    s.text(10, ly + 22 + 4 * 19 + 6, 'dashed box = interface', 'sv-m', 11.5)
    s.h = max(s.h, yE + hT + 12)
    return s.render('Class diagram of the core. The API calls RateLimiter. ClientRateLimiter implements '
                    'it, holds one Bucket per client, and is handed Plans, a BucketFactory and a Clock. '
                    'TokenBucket implements Bucket.')


def journey():
    """One request end to end, then a refusal."""
    parts = [('API', 'the caller'), ('ClientRateLimiter', None), ('buckets', 'ConcurrentHashMap'),
             ('Plans', None), ('BucketFactory', 'TokenBucket::new'), ('TokenBucket', None)]
    ev = [
        ('sep', "fantasy-app's first request: PRO, 50 a second"),
        ('call', 0, 1, 'tryAcquire("fantasy-app")'),
        ('self', 1, 'now = clock.nowMillis() → 0'),
        ('call', 1, 2, 'computeIfAbsent("fantasy-app", …)'),
        ('self', 2, 'no bucket yet, so run the function'),
        ('call', 2, 3, 'limitFor("fantasy-app")'),
        ('ret', 3, 2, '50 a second'),
        ('call', 2, 4, 'create(limit, 0)'),
        ('call', 4, 5, 'new TokenBucket: 50 tokens', 'acc'),
        ('ret', 2, 1, "the new bucket, now stored under the key"),
        ('call', 1, 5, 'tryConsume(0)'),
        ('self', 5, 'refill, 50 ≥ 1, take one'),
        ('ret', 5, 1, 'allowed, 49 left', 'g'),
        ('ret', 1, 0, '200 OK · X-RateLimit-Remaining: 49', 'g'),
        ('gap', 6),
        ('sep', "score-widget's 6th request in the same millisecond: FREE, 5 a second"),
        ('call', 0, 1, 'tryAcquire("score-widget")'),
        ('call', 1, 2, 'computeIfAbsent("score-widget", …)'),
        ('ret', 2, 1, 'its bucket, already there: nothing is created'),
        ('call', 1, 5, "tryConsume(0) on score-widget's bucket"),
        ('self', 5, 'refill earns 0, 0 < 1'),
        ('ret', 5, 1, 'refused, retry in 200 ms', 'r'),
        ('ret', 1, 0, '429 · Retry-After: 1', 'r'),
    ]
    return sequence(parts, ev, w=960, label='Sequence diagram of two requests through the limiter.')


def rules():
    """Follow-up 4: the third search is refused by the search rule; the plan's token comes back."""
    parts = [('API', 'the caller'), ('AllRulesLimiter', None), ('rule "plan"', '50 a second'),
             ('rule "search"', '2 a second'), ('rule "global"', '100 a second')]
    ev = [
        ('sep', "fantasy-app's 3rd search in the same second"),
        ('call', 0, 1, 'check(fantasy-app, /search)'),
        ('self', 1, 'now = clock.nowMillis(): one instant for every rule'),
        ('call', 1, 2, 'tryAcquire("fantasy-app", 1, now)'),
        ('ret', 2, 1, 'allowed, 47 left', 'g'),
        ('call', 1, 3, 'tryAcquire("fantasy-app /search", 1, now)'),
        ('ret', 3, 1, 'refused, retry in 500 ms', 'r'),
        ('call', 1, 2, 'refund("fantasy-app", 1, now)', 'y'),
        ('self', 2, '47 → 48: the token is back'),
        ('ret', 1, 0, '429 · refused by "search"', 'r'),
        ('self', 4, 'never asked'),
    ]
    return sequence(parts, ev, w=960, label='Sequence diagram: three rules checked in order; the '
                                            'search rule refuses and the plan rule is refunded.')


def redis():
    """Follow-up 8: every server spends from one bucket in Redis."""
    s = Svg(940, 250)
    for i, y in enumerate((20, 96, 172)):
        s.box(8, y, 196, 56, f'API server {i + 1}', 'RedisRateLimiter')
        s.path(f'M204 {y + 28} C 280 {y + 28}, 290 124, 372 124', 'sv-ln acc', end='acc')
    s.text(288, 108, 'EVALSHA script', 'sv-acc', 11.5, 'middle')
    s.text(288, 146, 'key rl:fantasy-app', 'sv-m', 11, 'middle')
    s.rect(376, 16, 556, 216, 'sv-box now', 12)
    s.text(398, 44, 'Redis: runs one script at a time, so the script is one step', 'sv-t', 13, 'start', 600)
    s.rect(398, 62, 512, 64, 'sv-box rec', 8)
    s.text(414, 86, 'rl:fantasy-app  →  { tokens: 12.4, last: 1727712000123 }', 'sv-mono sv-t', 12)
    s.text(414, 108, 'one hash per client: the numbers a TokenBucket keeps', 'sv-m', 11)
    rows = ['1  TIME: now from Redis\'s clock, not ten servers\' clocks',
            '2  refill, check, take: the same three lines as TokenBucket',
            '3  HSET the new numbers; PEXPIRE: an idle bucket deletes itself']
    for i, r in enumerate(rows):
        s.text(414, 150 + i * 22, r, 'sv-t', 12)
    return s.render('Three API servers send the same Lua script to one Redis server, which holds one '
                    'bucket per client and runs one script at a time.')
