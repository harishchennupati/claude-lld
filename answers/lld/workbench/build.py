"""Build one LLD workbench page.

    python3 build.py rate-limiter            # writes ../<slug>-workbench.html

A problem folder holds:
    java/*.java       the code, one type per file, snapshots marked with //@ (see snap.py)
    demos/*.java      small programs whose real output the page shows
    problem.py        CONFIG (snapshots, build steps, demos, broken copies) and pages(W)
    figures.py        the SVG figures (optional)

Everything the page shows is compiled and run here first. A demo that fails, a snapshot that
does not compile, or a broken copy that the tests do not catch stops the build.
"""
import html
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hl    # noqa: E402
import snap  # noqa: E402
import svg   # noqa: E402

esc = html.escape


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------ run
class Runs:
    """Compiles every build step and snapshot, runs the demos, and the broken copies."""

    def __init__(self, pdir, cfg):
        self.pdir, self.cfg = pdir, cfg
        self.tree = snap.Tree(os.path.join(pdir, 'java'), cfg['SNAPS'])
        self.out = {}          # program name -> output text
        self.mutants = []      # (label, test name, failed runs, runs)

    def demo(self, name):
        with open(os.path.join(self.pdir, 'demos', name + '.java'), encoding='utf-8') as fh:
            return fh.read()

    def fingerprint(self):
        """A hash of everything the runs depend on: the sources, the demos and the config."""
        import hashlib
        h = hashlib.sha256()
        for sub in ('java', 'demos'):
            d = os.path.join(self.pdir, sub)
            for f in sorted(os.listdir(d)):
                if f.endswith('.java'):
                    h.update(f.encode())
                    with open(os.path.join(d, f), 'rb') as fh:
                        h.update(fh.read())
        for k in ('SNAPS', 'BUILD', 'DEMOS', 'MUTANTS', 'EXTRA'):
            h.update(repr(self.cfg.get(k)).encode())
        with open(snap.__file__, 'rb') as fh:
            h.update(fh.read())
        return h.hexdigest()

    def run_all(self, use_cache=True):
        cache = os.path.join(HERE, '.cache', os.path.basename(self.pdir) + '.json')
        fp = self.fingerprint()
        if use_cache and os.path.exists(cache):
            with open(cache, encoding='utf-8') as fh:
                c = json.load(fh)
            if c.get('fp') == fp:
                self.out = c['out']
                by_label = {m['label']: m for m in self.cfg['MUTANTS']}
                self.mutants = [(by_label[label], failed) for label, failed in c['mutants']]
                print('  nothing changed in the code since the last build: reusing its runs')
                return
        self._run_all()
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as fh:
            json.dump({'fp': fp, 'out': self.out,
                       'mutants': [(m['label'], f) for m, f in self.mutants]}, fh)

    def _run_all(self):
        t = self.tree
        have = []
        for step in self.cfg['BUILD']:
            have += step['files']
            src = {f: t.text(f, 'core') for f in have}
            mains = []
            if step.get('demo'):
                d = step['demo']
                if d.endswith('Demo'):
                    src[d + '.java'] = self.demo(d)
                mains = [d]
            ok, comp, res = snap.compile_run(src, mains=mains)
            if not ok:
                raise SystemExit(f"build step {step['id']} does not compile:\n{comp}")
            for m, r in res.items():
                code, output = r[0]
                if code != 0:
                    raise SystemExit(f'{m} failed in step {step["id"]}:\n{output}')
                self.out[m] = output
            print(f"  step {step['id']:6} compiles ({len(have)} files)" + (f", ran {mains[0]}" if mains else ''))
        for s in self.cfg['SNAPS'][1:]:
            src = {f: t.text(f, s) for f in t.names(s)}
            demo = self.cfg['DEMOS'].get(s)
            mains = ['RateLimiterTest', 'Main'] if 'RateLimiterTest.java' in src else []
            if demo:
                src['Check.java'] = self.demo('Check')
                src[demo + '.java'] = self.demo(demo)
                mains = [demo] + mains
            ok, comp, res = snap.compile_run(src, mains=mains)
            if not ok:
                raise SystemExit(f'snapshot {s} does not compile:\n{comp}')
            for m, r in res.items():
                code, output = r[0]
                if code != 0:
                    raise SystemExit(f'{m} failed in snapshot {s}:\n{output}')
                if m == demo:
                    self.out[m] = output
            print(f'  snapshot {s:5} compiles; ran {", ".join(mains)}')
        for demo, s in self.cfg.get('EXTRA', []):
            src = {f: t.text(f, s) for f in t.names(s)}
            src['Check.java'] = self.demo('Check')
            src[demo + '.java'] = self.demo(demo)
            ok, comp, res = snap.compile_run(src, mains=[demo])
            if not ok:
                raise SystemExit(f'{demo} does not compile against {s}:\n{comp}')
            code, output = res[demo][0]
            if code != 0:
                raise SystemExit(f'{demo} failed:\n{output}')
            self.out[demo] = output
            print(f'  extra {demo} on {s}: ran')
        base = {f: t.text(f, 'core') for f in t.names('core')}
        for m in self.cfg['MUTANTS']:
            src = dict(base)
            for f, a, b in m['edits']:
                if a not in src[f]:
                    raise SystemExit(f"mutant {m['label']}: text not found in {f}: {a}")
                src[f] = src[f].replace(a, b, 1)
            ok, comp, res = snap.compile_run(src, mains=['RateLimiterTest'], runs=m['runs'], strict=False)
            if not ok:
                raise SystemExit(f"mutant {m['label']} does not compile:\n{comp}")
            failed = sum(1 for code, o in res['RateLimiterTest'] if code != 0 and ('FAIL  ' + m['test']) in o)
            if failed < m['runs']:
                raise SystemExit(f"mutant {m['label']}: the test '{m['test']}' failed only "
                                 f"{failed} of {m['runs']} runs")
            self.mutants.append((m, failed))
            print(f"  broken copy '{m['label']}': caught {failed} of {m['runs']} runs")


# ------------------------------------------------------------------------------- page helpers
def inline(s):
    """`code`, **bold** and *italic* inside a line. Everything else passes through as HTML."""
    s = str(s)
    parts = re.split(r'(`[^`]+`)', s)
    out = []
    for p in parts:
        if p.startswith('`') and p.endswith('`') and len(p) > 1:
            out.append('<code>' + esc(p[1:-1], quote=False) + '</code>')
        else:
            p = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', p)
            p = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', p)
            out.append(p)
    return ''.join(out)


def md(text):
    """A small, predictable subset of Markdown: paragraphs, ## and ### headings, - and 1. lists.
    A block that starts with "<" is HTML and passes through untouched."""
    text = str(text).strip('\n')
    lines = [l.rstrip() for l in text.split('\n')]
    # dedent
    ind = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    lines = [l[ind:] for l in lines]
    blocks, cur = [], []
    for l in lines:
        if l.strip() == '':
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        first = b[0]
        if first.startswith('<'):
            out.append('\n'.join(b))
        elif first.startswith('### '):
            out.append(f'<h3>{inline(first[4:])}</h3>' + (md('\n'.join(b[1:])) if b[1:] else ''))
        elif first.startswith('## '):
            out.append(f'<h2>{inline(first[3:])}</h2>' + (md('\n'.join(b[1:])) if b[1:] else ''))
        elif first.startswith('- ') or re.match(r'\d+\. ', first):
            ordered = not first.startswith('- ')
            items = []
            for l in b:
                if l.startswith('- ') or re.match(r'\d+\. ', l):
                    items.append(re.sub(r'^(- |\d+\. )', '', l))
                else:
                    items[-1] += ' ' + l.strip()
            tag = 'ol' if ordered else 'ul'
            out.append(f'<{tag}>' + ''.join(f'<li>{inline(i)}</li>' for i in items) + f'</{tag}>')
        else:
            out.append('<p>' + inline(' '.join(x.strip() for x in b)) + '</p>')
    return '\n'.join(out)


ASC_TAGS = {'r': 'ar', 'g': 'ag', 'y': 'ay', 'd': 'ad', 'a': 'aa', 'b': 'ab', 'm': 'am'}


class W:
    """Blocks that page content is written with. Every method returns an HTML string."""

    def __init__(self, runs, cfg):
        self.runs, self.cfg, self.t = runs, cfg, runs.tree
        self.raw_id = 0

    # ---- code
    def _raw(self, text):
        self.raw_id += 1
        safe = text.replace('</', '<\\/')        # a "</script>" inside the code must not end the tag
        return f'<script type="text/plain" class="raw">{safe}</script>'

    def code(self, files, snap_='core', tag=None, sol=True, open_=True, label=None):
        """Whole files, highlighted, each with a copy button."""
        blocks = []
        for f in files:
            text = self.t.text(f, snap_)
            rows = hl.lines_html(text)
            body = ''.join(f'<span class="l">{r or " "}</span>' for r in rows)
            badge = f'<span class="badge {tag}">{tag}</span>' if tag else ''
            blocks.append(
                f'<div class="code{" sol" if sol else ""}"><div class="ch"><span class="fn">{esc(label or f)}</span>'
                f'{badge}<button class="copy" type="button">copy</button></div>'
                f'<pre class="java num"><code>{body}</code></pre>{self._raw(text)}</div>')
        return self._solwrap(''.join(blocks), sol)

    def snippet(self, text, label=None, kind='java', note=None, cls=''):
        """A short piece of code that is not a file (a first idea, the caller)."""
        rows = hl.lines_html(text.strip('\n') + '\n') if kind == 'java' else [esc(x) for x in text.strip('\n').split('\n')]
        body = ''.join(f'<span class="l">{r or " "}</span>' for r in rows)
        head = f'<div class="ch"><span class="fn">{esc(label)}</span>{f"<span class=note>{note}</span>" if note else ""}</div>' if label else ''
        return f'<div class="code snip {cls}">{head}<pre class="java"><code>{body}</code></pre></div>'

    def diff(self, s, files=None, sol=True, first=(), fold=(), fold_note=None):
        """What snapshot `s` changes: new files whole, changed files as a line diff. `first` puts
        some files at the top; `fold` puts some in a closed fold at the bottom (the same change,
        repeated in another class)."""
        snaps = self.cfg['SNAPS']
        prev = snaps[snaps.index(s) - 1]
        names = files or [n for n in self.t.names(s)
                          if self.t.text(n, prev) != self.t.text(n, s)]
        order = self.cfg.get('FILE_ORDER', [])
        first = [f + '.java' if not f.endswith('.java') else f for f in first]
        fold = [f + '.java' if not f.endswith('.java') else f for f in fold]
        names = sorted(names, key=lambda n: (first.index(n) if n in first else len(first),
                                             order.index(n) if n in order else 999, n))
        main = [n for n in names if n not in fold]
        folded = [n for n in names if n in fold]
        inner = self._diff_blocks(s, prev, main)
        if folded:
            label = fold_note or ('The same change in ' + ' and '.join(
                '<code>' + n[:-5] + '</code>' for n in folded))
            inner += (f'<details class="more"><summary>{label}</summary>'
                      f'{self._diff_blocks(s, prev, folded)}</details>')
        return self._solwrap(inner, sol)

    def _diff_blocks(self, s, prev, names):
        blocks = []
        for f in names:
            old, new = self.t.text(f, prev), self.t.text(f, s)
            if old is None:
                blocks.append(self.code([f], s, tag='new', sol=False))
                continue
            a, b = hl.lines_html(old), hl.lines_html(new)
            rows = hl.diff_rows(old, new, context=2)
            out = []
            k = 0
            while k < len(rows):
                kind, i, j = rows[k]
                if kind == 'gap':
                    out.append('<span class="l gap">⋯</span>')
                elif kind == 'ctx':
                    out.append(f'<span class="l" data-n="{j + 1}">{b[j] or " "}</span>')
                elif kind == 'del':
                    # a run of removed lines: one marker, the lines themselves shown on a click
                    run = []
                    while k < len(rows) and rows[k][0] == 'del':
                        run.append(rows[k][1])
                        k += 1
                    n = len(run)
                    out.append(f'<span class="l delmark" role="button" tabindex="0">'
                               f'{n} line{"s" if n > 1 else ""} removed ▸</span>')
                    out.extend(f'<span class="l del">{a[r] or " "}</span>' for r in run)
                    continue
                else:
                    out.append(f'<span class="l add" data-n="{j + 1}">{b[j] or " "}</span>')
                k += 1
            nadd = sum(1 for r in rows if r[0] == 'add')
            ndel = sum(1 for r in rows if r[0] == 'del')
            blocks.append(
                f'<div class="code diff"><div class="ch"><span class="fn">{esc(f)}</span>'
                f'<span class="badge changed">changed</span><span class="cnt"><b class="plus">+{nadd}</b> '
                f'<b class="minus">−{ndel}</b></span><button class="copy" type="button">copy the new file</button></div>'
                f'<pre class="java"><code>{"".join(out)}</code></pre>{self._raw(new)}</div>')
        return ''.join(blocks)

    def _solwrap(self, inner, sol):
        if not sol:
            return inner
        return (f'<div class="solbox"><div class="hidden-note">The code is hidden in Practise mode. '
                f'Write yours first, then <button type="button" class="reveal">show the code</button></div>'
                f'<div class="solbody">{inner}</div></div>')

    def run(self, program, cmd=None, note=None):
        text = self.runs.out[program]
        c = cmd or f'java {program}'
        n = f'<span class="rn">{note}</span>' if note else ''
        return (f'<div class="run"><div class="rh"><span class="prompt">$</span> {esc(c)}{n}</div>'
                f'<pre>{esc(text.rstrip())}</pre></div>')

    def mutant_table(self):
        rows = []
        for m, failed in self.runs.mutants:
            rows.append(f'<tr><td>{m["html"]}</td><td>{esc(m["test"])}</td>'
                        f'<td class="num">{failed} of {m["runs"]}</td></tr>')
        return ('<table class="mut"><thead><tr><th>the break</th><th>the test that fails</th>'
                '<th>runs that failed</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>')

    def onefile(self, s='core', files=None):
        """All of a snapshot's types in one runnable Main.java (for copying into an online editor)."""
        names = files or [n for n in self.cfg['FILE_ORDER'] if self.t.exists(n, s) and n != 'RateLimiterTest.java']
        imports, bodies = [], []
        for n in names:
            text = self.t.text(n, s)
            for line in text.split('\n'):
                if line.startswith('import '):
                    if line not in imports:
                        imports.append(line)
            bodies.append('\n'.join(l for l in text.split('\n') if not l.startswith('import ')).strip('\n'))
        return '\n'.join(sorted(imports)) + '\n\n' + '\n\n'.join(bodies) + '\n'

    def inline(self, text):
        return inline(text)

    def copybox(self, text, label, note=''):
        return (f'<div class="copybox"><div><b>{esc(label)}</b> <span>{inline(note)}</span></div>'
                f'<button class="copy" type="button">copy</button>{self._raw(text)}</div>')

    # ---- words and pictures
    def asc(self, text, cls=''):
        s = esc(text.strip('\n'))
        s = re.sub(r'\{([rgydabm])\}', lambda m: f'<span class="{ASC_TAGS[m.group(1)]}">', s)
        s = s.replace('{/}', '</span>')
        s = s.replace('✗', '<span class="ar">✗</span>').replace('✓', '<span class="ag">✓</span>')
        return f'<pre class="asc {cls}">{s}</pre>'

    def fig(self, svg_html, title=None, caption=None, cls=''):
        t = f'<div class="ft">{title}</div>' if title else ''
        c = f'<figcaption>{inline(caption)}</figcaption>' if caption else ''
        return f'<figure class="{cls}">{t}{svg_html}{c}</figure>'

    def asks(self, pairs, title='If the interviewer asks'):
        items = ''.join(f'<div class="qa"><b>{inline(q)}</b><p>{inline(a)}</p></div>' for q, a in pairs)
        return f'<div class="asks"><div class="asks-h">{title}</div>{items}</div>'

    def box(self, kind, title, body):
        """kind: java | why | mistake | hole | fix | note"""
        return (f'<div class="box {kind}"><div class="bh">{inline(title)}</div>'
                f'<div class="bb">{md(body)}</div></div>')

    def java(self, title, body):
        """A Java idea, explained where it is first used."""
        return self.box('java', 'Java · ' + title, body)

    def javas(self, *boxes):
        return '<div class="javas">' + ''.join(boxes) + '</div>'

    def md(self, text):
        return md(text)

    def ask(self, quote, src=None, label='The interviewer'):
        s = f'<p class="src">{inline(src)}</p>' if src else ''
        return f'<div class="ask"><div class="al">{label}</div><p class="aq">{inline(quote)}</p>{s}</div>'

    def xy(self, items):
        """"X, not Y" lines: each item is (chosen, rejected, because)."""
        li = ''.join(f'<li><b>{inline(a)}</b>, not <i>{inline(b)}</i>: {inline(c)}</li>' for a, b, c in items)
        return f'<ul class="xy">{li}</ul>'

    def pair(self, left, right):
        return f'<div class="pair"><div>{left}</div><div>{right}</div></div>'

    def part(self, f, first, last=None, snap_='core', label=None, note=None, sol=True, plus=0):
        """Lines of one file, from the line matching regex `first` to the line matching `last`
        (inclusive, then `plus` more lines; to the end of the file if None), numbered as in the file."""
        text = self.t.text(f, snap_)
        lines = text.rstrip('\n').split('\n')
        i = next(k for k, l in enumerate(lines) if re.search(first, l))
        j = len(lines) - 1 if last is None else next(k for k in range(i, len(lines))
                                                     if re.search(last, lines[k]))
        j = min(len(lines) - 1, j + plus)
        rows = hl.lines_html(text)[i:j + 1]
        body = ''.join(f'<span class="l">{r or " "}</span>' for r in rows)
        n = f'<span class="note">{inline(note)}</span>' if note else ''
        html_ = (f'<div class="code"><div class="ch"><span class="fn">{esc(label or f)}</span>'
                 f'<span class="badge part">lines {i + 1}–{j + 1}</span>{n}'
                 f'<button class="copy" type="button">copy the whole file</button></div>'
                 f'<pre class="java num" style="--start:{i}"><code>{body}</code></pre>{self._raw(text)}</div>')
        return self._solwrap(html_, sol)

    def strip(self, now=(), snap_=None, groups=None):
        """Where-we-are chips. Build steps pass `now` (types typed in this step); follow-ups pass
        `snap_`, and the new and changed types are worked out from the snapshots."""
        groups = groups or self.cfg['STRIP']
        order = [n for _, names in groups for n in names]
        out = []
        if snap_ is None:
            done_upto = min((order.index(n) for n in now), default=len(order))
            for label, names in groups:
                chips = []
                for n in names:
                    k = order.index(n)
                    cls = 'now' if n in now else ('done' if k < done_upto else 'later')
                    chips.append(f'<span class="chip {cls}">{n}</span>')
                out.append(f'<div class="sg"><span class="sl">{label}</span>{"".join(chips)}</div>')
            key = 'this step: highlighted'
        else:
            snaps = self.cfg['SNAPS']
            prev = snaps[snaps.index(snap_) - 1]
            def state(n):
                f = n + '.java'
                if not self.t.exists(f, snap_):
                    return None
                if not self.t.exists(f, prev):
                    return 'new'
                return 'chg' if self.t.text(f, prev) != self.t.text(f, snap_) else 'done'
            for label, names in groups:
                chips = ''.join(f'<span class="chip {state(n)}">{n}</span>' for n in names if state(n))
                out.append(f'<div class="sg"><span class="sl">{label}</span>{chips}</div>')
            extra = [f[:-5] for f in self.cfg['FILE_ORDER'] if f[:-5] not in order
                     and self.t.exists(f, snap_)]
            if extra:
                chips = ''.join(f'<span class="chip {state(n)}">{n}</span>' for n in extra)
                out.append(f'<div class="sg"><span class="sl">added in follow-ups</span>{chips}</div>')
            key = '<span class="ok">green</span> new · <span class="warn">yellow</span> changed'
        return f'<div class="strip">{"".join(out)}<span class="key">{key}</span></div>'

    def drill(self, title, minutes, body, extra=''):
        t = self.timer(minutes) if minutes else ''
        return (f'<div class="drill"><div class="dh"><b>{inline(title)}</b>{t}</div>{md(body)}'
                f'{extra}</div>')

    def checks(self, key, items):
        li = ''.join(f'<li><label><input type="checkbox" data-key="{key}-{k}">{inline(x)}</label></li>'
                     for k, x in enumerate(items))
        return f'<ol class="checks">{li}</ol>'

    def misslog(self, key, placeholder=''):
        return f'<textarea class="misslog" data-key="{key}" placeholder="{esc(placeholder)}"></textarea>'

    def table(self, head, rows, cls=''):
        th = ''.join(f'<th>{inline(h)}</th>' for h in head)
        tr = ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in rows)
        return (f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead>'
                f'<tbody>{tr}</tbody></table></div>')

    def reveal(self, q, a, cls=''):
        return (f'<details class="rv {cls}"><summary>{inline(q)}</summary>'
                f'<div class="rva">{md(a)}</div></details>')

    def timer(self, minutes):
        return (f'<button type="button" class="timer" data-min="{minutes}">'
                f'<span class="tv">{minutes}:00</span> <span class="tl">start</span></button>')


# ------------------------------------------------------------------------------------ the page
def render(cfg, pages, figs, out_path):
    shell = os.path.join(HERE, 'shell')
    css = open(os.path.join(shell, 'style.css'), encoding='utf-8').read()
    js = open(os.path.join(shell, 'app.js'), encoding='utf-8').read()
    nav, sections = [], []
    group = None
    for n, p in enumerate(pages):
        if p['group'] != group:
            group = p['group']
            nav.append(f'<div class="grp">{esc(group)}</div>')
        num = f'{n + 1:02d}'
        nav.append(f'<a href="#{p["id"]}" data-step="{p["id"]}"><span class="n">{num}</span>'
                   f'<span class="t">{p["nav"]}</span></a>')
        panel = ''
        if p.get('panel'):
            panel = f'<aside class="panel">{p["panel"]}</aside>'
        layout = 'withpanel' if panel else 'wide'
        sections.append(
            f'<section class="step {layout}" id="{p["id"]}" data-nav="{esc(p["nav"])}">'
            f'<div class="scol"><div class="shead"><span class="stage">{esc(p.get("stage", p["group"]))}</span>'
            f'<span class="num">{num}</span></div><h1>{p["title"]}</h1>'
            f'<div class="body">{p["body"]}</div>'
            f'<div class="pnav"></div></div>{panel}</section>')
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(cfg["TITLE"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<style>{css}</style></head>
<body data-name="{esc(cfg["NAME"])}">{svg.DEFS}
<header class="top"><button class="navtoggle" type="button" aria-label="Contents">☰</button>
<div class="brand"><b>{esc(cfg["NAME"])}</b><span>{cfg["SUBTITLE"]}</span></div>
<div class="modes" role="group" aria-label="Mode"><button type="button" data-mode="read" class="on">Read</button><button type="button" data-mode="practise">Practise</button></div>
<div class="pn"><button type="button" id="prev" aria-label="Previous step">←</button><span id="pos"></span><button type="button" id="next" aria-label="Next step">→</button></div>
</header>
<div class="wrap"><nav class="side">{"".join(nav)}</nav>
<main id="main">{"".join(sections)}</main></div>
<script>const SLUG={json.dumps(cfg["SLUG"])};
{js}</script></body></html>'''
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(page)
    return page


POM = """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>lld</groupId>
  <artifactId>{artifact}</artifactId>
  <version>1</version>
  <properties>
    <maven.compiler.release>17</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
</project>
"""


def export_projects(runs, cfg, out_dir):
    """Runnable copies of the code next to the page: core, complete (every follow-up and its
    demo) and practice (only the tests). Each is checked here before it is written."""
    import shutil
    t = runs.tree
    last = cfg['SNAPS'][-1]
    demos = [d for d in cfg['DEMOS'].values()]
    projects = {
        'core': {f: t.text(f, 'core') for f in t.names('core')},
        'complete': dict({f: t.text(f, last) for f in t.names(last)},
                         **{d + '.java': runs.demo(d) for d in demos + ['Check']}),
        'practice': {'RateLimiterTest.java': t.text('RateLimiterTest.java', 'core')}
                    if 'RateLimiterTest.java' in t.files else {},
    }
    ok, comp, res = snap.compile_run(projects['complete'], mains=demos)
    if not ok:
        raise SystemExit('the complete project does not compile:\n' + comp)
    for d, r in res.items():
        if r[0][0] != 0:
            raise SystemExit(f'{d} fails in the complete project:\n{r[0][1]}')
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    for name, files in projects.items():
        src = os.path.join(out_dir, name, 'src', 'main', 'java')
        os.makedirs(src)
        for f, text in files.items():
            with open(os.path.join(src, f), 'w', encoding='utf-8') as fh:
                fh.write(text)
        with open(os.path.join(out_dir, name, 'pom.xml'), 'w', encoding='utf-8') as fh:
            fh.write(POM.format(artifact=cfg['SLUG'] + '-' + name))
    readme = cfg['EXPORT_README'].format(demos=', '.join(demos))
    with open(os.path.join(out_dir, 'README.md'), 'w', encoding='utf-8') as fh:
        fh.write(readme)
    print(f'  exported core, complete and practice projects to {os.path.relpath(out_dir, HERE)}')


def main(slug):
    pdir = os.path.join(HERE, slug)
    problem = load(os.path.join(pdir, 'problem.py'), 'problem_' + slug.replace('-', '_'))
    cfg = problem.CONFIG
    runs = Runs(pdir, cfg)
    runs.run_all(use_cache='--fresh' not in sys.argv)
    w = W(runs, cfg)
    pages = problem.pages(w)
    out = os.path.join(os.path.dirname(HERE), f'{slug}-workbench.html')
    page = render(cfg, pages, None, out)
    if cfg.get('EXPORT_README'):
        export_projects(runs, cfg, os.path.join(os.path.dirname(HERE), f'{slug}-code'))
    words = len(re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style|svg|pre)[\s\S]*?</\1>', ' ', page)).split())
    print(f'wrote {out}: {len(page):,} bytes, {len(pages)} steps, about {words:,} words outside code')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    main(args[0] if args else 'rate-limiter')
