"""The rate limiter's figures, drawn with ../svg.py. Each function returns an <svg> string."""
from svg import Svg, sequence


def flow():
    """Where the limiter sits: the front door of the API, before any work."""
    s = Svg(940, 250)
    clients = [('score-widget', '5 a second', 14), ('fantasy-app', '50 a second', 94),
               ('cricket-blog', '5 a second', 174)]
    for name, sub, y in clients:
        s.box(8, y, 184, 56, name, sub)
        s.path(f'M192 {y + 28} C 240 {y + 28}, 240 96, 290 96', 'sv-ln', end='m')
    s.rect(262, 8, 350, 234, 'sv-box lane', 12)
    s.text(437, 30, 'our score API', 'sv-m', 12, 'middle')
    s.rect(290, 46, 294, 100, 'sv-box now', 7)
    s.text(437, 76, 'rate limiter', 'sv-t', 13.5, 'middle', 600)
    s.text(437, 102, 'may this customer go ahead now?', 'sv-m', 11, 'middle')
    s.text(437, 122, 'X requests every Y seconds, each', 'sv-m', 11, 'middle')
    s.box(290, 170, 294, 56, 'fetch the scores', 'the real work: cache, database')
    s.path('M437 146 L437 168', 'sv-ln g', end='g')
    s.text(447, 162, 'allowed', 'sv-g', 12)
    s.box(686, 22, 246, 64, '429 Too Many Requests', 'Retry-After: 1 · nothing else runs',
          'sv-box bad')
    s.path('M584 80 L684 58', 'sv-ln r', end='r')
    s.text(606, 58, 'refused', 'sv-r', 12)
    s.box(686, 166, 246, 64, '200 OK + the scores', 'the work ran', 'sv-box good')
    s.path('M584 198 L684 198', 'sv-ln g', end='g')
    return s.render('Customers call the score API. The rate limiter answers first: refused requests '
                    'get 429 at once, allowed ones go on to the work.')
