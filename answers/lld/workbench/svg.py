"""Tiny SVG builder. Colours come from CSS classes (see shell/style.css), so figures follow the
page theme. Markers are defined once per page in DEFS (a hidden <svg> at the top of <body>)."""
import html

DEFS = '''<svg class="sv-defs" width="0" height="0" aria-hidden="true" focusable="false"><defs>
<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="mk"/></marker>
<marker id="ar-acc" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="mk-acc"/></marker>
<marker id="ar-g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="mk-g"/></marker>
<marker id="ar-r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="mk-r"/></marker>
<marker id="ar-y" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="mk-y"/></marker>
<marker id="tri" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="11" markerHeight="11" orient="auto"><path d="M0 0L12 6L0 12z" class="mk-tri"/></marker>
<marker id="dia" viewBox="0 0 12 12" refX="1" refY="6" markerWidth="11" markerHeight="11" orient="auto"><path d="M0 6L6 0L12 6L6 12z" class="mk"/></marker>
</defs></svg>'''

ARROW = {'m': 'ar', 'acc': 'ar-acc', 'g': 'ar-g', 'r': 'ar-r', 'y': 'ar-y', 'tri': 'tri'}


def esc(s):
    return html.escape(str(s), quote=False)


class Svg:
    def __init__(self, w, h, cls=''):
        self.w, self.h, self.cls, self.parts = w, h, cls, []

    def add(self, s):
        self.parts.append(s)
        return self

    def rect(self, x, y, w, h, cls='sv-box', rx=7):
        return self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" class="{cls}"/>')

    def text(self, x, y, s, cls='sv-t', size=13, anchor='start', weight=None, raw=False):
        wt = f' font-weight="{weight}"' if weight else ''
        body = s if raw else esc(s)
        return self.add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
                        f'class="{cls}"{wt}>{body}</text>')

    def lines(self, x, y, rows, size=12.5, lh=None, cls='sv-t', anchor='start'):
        lh = lh or size * 1.45
        for i, r in enumerate(rows):
            if isinstance(r, tuple):
                txt, c = r
            else:
                txt, c = r, cls
            self.text(x, y + i * lh, txt, c, size, anchor)
        return self

    def path(self, d, cls='sv-ln', end=None, start=None, sw=None):
        me = f' marker-end="url(#{ARROW[end]})"' if end else ''
        ms = f' marker-start="url(#{ARROW[start] if start != "dia" else "dia"})"' if start else ''
        w = f' stroke-width="{sw}"' if sw else ''
        return self.add(f'<path d="{d}" class="{cls}" fill="none"{me}{ms}{w}/>')

    def line(self, pts, cls='sv-ln', end=None, start=None):
        d = 'M' + ' L'.join(f'{x} {y}' for x, y in pts)
        return self.path(d, cls, end, start)

    def circle(self, x, y, r, cls='sv-dot'):
        return self.add(f'<circle cx="{x}" cy="{y}" r="{r}" class="{cls}"/>')

    def box(self, x, y, w, h, title, sub=None, cls='sv-box', tcls='sv-t', scls='sv-m', size=13.5,
            ssize=11.5):
        self.rect(x, y, w, h, cls)
        if sub:
            self.text(x + w / 2, y + h / 2 - 4, title, tcls, size, 'middle', 600)
            self.text(x + w / 2, y + h / 2 + 13, sub, scls, ssize, 'middle')
        else:
            self.text(x + w / 2, y + h / 2 + size * 0.36, title, tcls, size, 'middle', 600)
        return self

    def uml(self, x, y, w, name, stereo=None, fields=(), methods=(), cls='', size=12.5):
        """A class box. Returns (height, anchors dict)."""
        lh = size * 1.42
        head = 30 if not stereo else 40
        h = head + (len(fields) * lh + 10 if fields else 0) + (len(methods) * lh + 10 if methods else 0)
        kind = 'sv-box'
        if stereo == 'interface':
            kind += ' dash'
        if stereo in ('record', 'enum'):
            kind += ' rec'
        self.rect(x, y, w, h, (kind + ' ' + cls).strip(), rx=6)
        ty = y + 20
        if stereo:
            self.text(x + w / 2, y + 15, '«' + stereo + '»', 'sv-m', 10.5, 'middle')
            ty = y + 31
        self.text(x + w / 2, ty, name, 'sv-t', 14, 'middle', 650)
        cy = y + head
        for rows, c in ((fields, 'sv-m sv-mono'), (methods, 'sv-t sv-mono')):
            if rows:
                self.add(f'<line x1="{x}" y1="{cy}" x2="{x + w}" y2="{cy}" class="sv-sep"/>')
                for i, r in enumerate(rows):
                    self.text(x + 10, cy + 16 + i * lh, r, c, size - 1)
                cy += len(rows) * lh + 10
        a = dict(l=(x, y + h / 2), r=(x + w, y + h / 2), t=(x + w / 2, y), b=(x + w / 2, y + h),
                 x=x, y=y, w=w, h=h)
        return h, a

    def render(self, label):
        return (f'<svg viewBox="0 0 {self.w} {self.h}" class="fig {self.cls}" role="img" '
                f'aria-label="{html.escape(label)}" xmlns="http://www.w3.org/2000/svg">'
                + ''.join(self.parts) + '</svg>')


def text_w(s, size, mono=True):
    """Rough width of a line of text in px: good enough to size boxes."""
    return len(str(s)) * size * (0.6 if mono else 0.56)


def sequence(parts, events, w=940, label='Sequence diagram', top=8, gap=34, pad=76, name_size=13):
    """A UML-style sequence diagram.

    parts:  [(name, sub or None), ...]            one lifeline each, left to right
    events: ('call', a, b, text[, cls])           solid arrow a -> b (indexes into parts)
            ('ret', a, b, text[, cls])            dashed arrow back; cls 'g' or 'r' colours it
            ('self', a, text[, cls])              a note beside lifeline a (work done inside it)
            ('sep', text)                         a section heading across the whole width
            ('gap', px)                           extra space
    """
    n = len(parts)
    xs = [pad + i * (w - 2 * pad) / (n - 1) for i in range(n)] if n > 1 else [w / 2]
    spacing = (w - 2 * pad) / (n - 1) if n > 1 else w
    head_h = 46
    # measure the height first
    y = top + head_h + 24
    heights = []
    for e in events:
        k = e[0]
        step = {'call': gap, 'ret': gap, 'self': gap - 4, 'sep': 40, 'gap': e[1] if k == 'gap' else 0}[k]
        heights.append(step)
        y += step
    h = y + 10
    s = Svg(w, h, 'seq')
    for i, (name, sub) in enumerate(parts):
        bw = min(spacing - 8, max(text_w(name, name_size) + 16, (text_w(sub, 11) + 16) if sub else 0,
                                  96))
        s.rect(xs[i] - bw / 2, top, bw, head_h, 'sv-box acc' if i == 0 else 'sv-box', 8)
        if sub:
            s.text(xs[i], top + 19, name, 'sv-t', name_size, 'middle', 600)
            s.text(xs[i], top + 36, sub, 'sv-m', 11, 'middle')
        else:
            s.text(xs[i], top + 28, name, 'sv-t', name_size, 'middle', 600)
        s.add(f'<line x1="{xs[i]}" y1="{top + head_h}" x2="{xs[i]}" y2="{h - 6}" class="sv-ln life"/>')
    y = top + head_h + 24
    for e, step in zip(events, heights):
        k = e[0]
        if k in ('call', 'ret'):
            a, b, txt = e[1], e[2], e[3]
            cls = e[4] if len(e) > 4 else ''
            x1, x2 = xs[a], xs[b]
            d = 1 if x2 > x1 else -1
            line_cls = 'sv-ln' + (' dash' if k == 'ret' else '') + (f' {cls}' if cls else '')
            s.path(f'M{x1 + d * 3} {y} L{x2 - d * 4} {y}', line_cls,
                   end={'g': 'g', 'r': 'r', 'acc': 'acc', 'y': 'y'}.get(cls, 'm'))
            tcls = {'g': 'sv-g', 'r': 'sv-r', 'acc': 'sv-acc', 'y': 'sv-y'}.get(cls, 'sv-t' if k == 'call' else 'sv-m')
            mid = (x1 + x2) / 2
            tw = text_w(txt, 12)
            if abs(x2 - x1) < tw + 10:          # a long label on a short arrow: start it at the caller
                anchor, tx = ('start', x1 + 8) if d > 0 else ('end', x1 - 8)
            else:
                anchor, tx = 'middle', mid
            if anchor == 'middle':
                tx = max(tw / 2 + 4, min(w - tw / 2 - 4, tx))
            elif anchor == 'end' and tx - tw < 4:      # would run off the left edge
                tx = tw + 4
            elif anchor == 'start' and tx + tw > w - 4:
                tx = w - 4 - tw
            s.text(tx, y - 7, txt, tcls, 12, anchor)
        elif k == 'self':
            a, txt = e[1], e[2]
            cls = e[3] if len(e) > 3 else ''
            tcls = {'g': 'sv-g', 'r': 'sv-r', 'acc': 'sv-acc', 'y': 'sv-y'}.get(cls, 'sv-m')
            x = xs[a]
            tw = text_w(txt, 11.5)
            right = x + 14 + tw < w - 4
            if right:
                s.path(f'M{x} {y - 12} h12 v14 h-9', 'sv-ln thin', end='m')
                s.text(x + 17, y, txt, tcls, 11.5, 'start')
            else:
                s.path(f'M{x} {y - 12} h-12 v14 h9', 'sv-ln thin', end='m')
                s.text(x - 17, y, txt, tcls, 11.5, 'end')
        elif k == 'sep':
            s.add(f'<line x1="8" y1="{y - 2}" x2="{w - 8}" y2="{y - 2}" class="sv-sep" stroke-dasharray="2 5"/>')
            tw = text_w(e[1], 12)
            s.rect(14, y - 13, tw + 20, 22, 'sv-box dim', 5)
            s.text(24, y + 3, e[1], 'sv-acc', 12, 'start', 600)
        y += step
    return s.render(label)
