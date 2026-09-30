"""Java syntax highlighting to HTML, one list of line strings per file, and line diffs."""
import difflib
import html
import re

KEYWORDS = set('''abstract assert boolean break byte case catch char class const continue default do
double else enum extends final finally float for goto if implements import instanceof int interface
long native new package private protected public return short static strictfp super switch
synchronized this throw throws transient try void volatile while record var yield true false null
sealed permits non-sealed'''.split())

TOKEN = re.compile(r'''
  (?P<tblock>"""[\s\S]*?""")
 |(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)
 |(?P<string>"(?:\\.|[^"\\\n])*")
 |(?P<char>'(?:\\.|[^'\\\n])')
 |(?P<annot>@[A-Za-z_]\w*)
 |(?P<number>\b\d[\d_]*(?:\.\d+)?[LlFfDd]?\b)
 |(?P<word>[A-Za-z_]\w*)
 |(?P<nl>\n)
 |(?P<other>.)
''', re.X)


def tokens(src):
    for m in TOKEN.finditer(src):
        kind = m.lastgroup
        text = m.group(kind)
        if kind == 'word':
            if text in KEYWORDS:
                kind = 'kw'
            elif text[0].isupper():
                kind = 'type'
            else:
                kind = 'plain'
        elif kind == 'tblock':
            kind = 'string'
        elif kind == 'char':
            kind = 'string'
        elif kind == 'other':
            kind = 'plain'
        yield kind, text


CLASS = {'kw': 'k', 'type': 't', 'string': 's', 'comment': 'c', 'number': 'n', 'annot': 'a'}


def lines_html(src):
    """Highlight `src`; return one HTML string per source line (spans never cross lines)."""
    out, cur = [], []
    for kind, text in tokens(src):
        if kind == 'nl':
            out.append(''.join(cur))
            cur = []
            continue
        parts = text.split('\n')
        for i, part in enumerate(parts):
            if i > 0:
                out.append(''.join(cur))
                cur = []
            if part == '':
                continue
            esc = html.escape(part, quote=False)
            cls = CLASS.get(kind)
            cur.append(f'<span class="{cls}">{esc}</span>' if cls else esc)
    out.append(''.join(cur))
    if src.endswith('\n') and out and out[-1] == '':
        out.pop()
    return out


def diff_ops(old, new):
    """Line opcodes between two texts: list of (tag, i1, i2, j1, j2)."""
    a, b = old.rstrip('\n').split('\n'), new.rstrip('\n').split('\n')
    return a, b, difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()


def diff_rows(old, new, context=3):
    """Rows for a unified view: ('ctx'|'del'|'add'|'gap', old_line_no|None, new_line_no|None).
    Line numbers are 0-based indexes into old/new."""
    a, b, ops = diff_ops(old, new)
    rows = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            rows.extend(('ctx', i1 + k, j1 + k) for k in range(i2 - i1))
        else:
            rows.extend(('del', i, None) for i in range(i1, i2))
            rows.extend(('add', None, j) for j in range(j1, j2))
    keep = [False] * len(rows)
    for n, r in enumerate(rows):
        if r[0] != 'ctx':
            for k in range(max(0, n - context), min(len(rows), n + context + 1)):
                keep[k] = True
    out, skipping = [], False
    for n, r in enumerate(rows):
        if keep[n]:
            out.append(r)
            skipping = False
        elif not skipping:
            out.append(('gap', None, None))
            skipping = True
    return out
