"""The words of RAG v4, written fresh in v3's plain English: a derivation that grows the design,
then how each hard part works. Markup reuses v3's classes; CSS adds the push cards."""
import re


def p(s):
    """Collapse the line breaks of a triple-quoted paragraph."""
    return re.sub(r'\s*\n\s*', ' ', s.strip())


def tx(s):
    return f'<p class="tx">{p(s)}</p>'


def how(*items):
    return '<ol class="how">' + ''.join(f'<li>{p(i)}</li>' for i in items) + '</ol>'


def wl(s):
    return f'<p class="wl"><b>The one hole:</b> {p(s)}</p>'


def rem(s):
    return f'<p class="rem"><b>Remember:</b> {p(s)}</p>'


def fu(*pairs):
    return ('<div class="fu"><p class="lab3">If the interviewer pushes</p><ul>'
            + ''.join(f'<li><b>{p(q)}</b> {p(a)}</li>' for q, a in pairs) + '</ul></div>')


def fold(title, note, h):
    return f'<details class="fold"><summary>{title}<span>{note}</span></summary>{h}</details>'


def table(head, rows, cls=''):
    c = f' class="{cls}"' if cls else ''
    return (f'<table{c}><tr>' + ''.join(f'<th>{x}</th>' for x in head) + '</tr>'
            + ''.join('<tr>' + ''.join(f'<td>{p(x)}</td>' for x in r) + '</tr>' for r in rows)
            + '</table>')


def vs(s):
    return f'<div class="vs">{p(s)}</div>'


def band(k, d):
    return f'<div class="partband"><p class="k">{k}</p><p class="d">{d}</p></div>'


def h2(i, t):
    return f'<h2 id="{i}">{t}</h2>'


def pre(s, cls='sql'):
    return f'<pre class="{cls}">{s.strip(chr(10))}</pre>'


def qa(q, a):
    return f'<div class="qa"><b>{p(q)}</b><p>{p(a)}</p></div>'


# The design grows push by push. Each part: (push that adds it, band, name, gate or outside).
BANDS = ['the question\'s path', 'stores and our models', 'the ingest path']
PARTS = [
    (1, 0, 'Employee\'s browser', ''), (1, 0, 'Orchestrator', ''), (1, 0, 'Model provider', 'out'),
    (1, 1, 'Search index', ''),
    (2, 2, 'Ingest workers', ''), (2, 2, 'Object storage', ''),
    (3, 1, 'Embedding model', ''),
    (4, 1, 'Reranker', ''),
    (5, 1, 'Metadata database: the final check', 'gate'), (5, 1, 'Redis', ''),
    (5, 2, 'Identity sync', ''), (5, 2, 'Identity provider', 'out'),
    (6, 2, 'Connectors', ''), (6, 2, 'Ingest queue', ''), (6, 2, 'Source systems', 'out'),
    (7, 0, 'Rewrite model', 'out'), (7, 1, 'Question classifier', ''),
    (7, 1, 'Conversation store', ''),
    (8, 0, 'The citation rule', 'gate'), (8, 1, 'Citation checker', ''),
    (9, 0, 'Output filter', ''),
    (10, 0, 'Model router', ''), (10, 0, 'Fallback provider', 'out'),
    (11, 0, 'Trace log', ''), (11, 0, 'Eval runner', ''),
]


def strip(k):
    rows = ''
    for b, name in enumerate(BANDS):
        chips = ''.join(
            f'<span class="c{" new" if n == k else ""}{" " + kind if kind else ""}">{label}</span>'
            for n, band_, label, kind in PARTS if n <= k and band_ == b)
        rows += f'<div class="r"><span class="bl">{name}</span>{chips or "<i>nothing yet</i>"}</div>'
    total = sum(1 for n, *_ in PARTS if n <= k)
    head = 'the design so far' if k < 12 else 'one cell: every part, copied for each large company'
    return f'<div class="grow"><p class="gl">{head} · {total} parts</p>{rows}</div>'


def push(k, title, first, wrong, fix, *trade):
    return (f'<div class="push"><h3><span class="k">{k}</span>{title}</h3><div class="fwd">'
            f'<p class="h">first idea</p><p>{p(first)}</p>'
            f'<p class="h bad">what goes wrong</p><p>{p(wrong)}</p>'
            f'<p class="h ok">what we do instead</p><p>{p(fix)}</p></div>'
            + ''.join(vs(t) for t in trade) + strip(k) + '</div>')


CSS = '''<style>
.push{margin:30px 0 8px}
.push h3{font-family:"Space Grotesk",sans-serif;font-size:18px;color:var(--txt);margin:0 0 10px;max-width:92ch}
.push h3 .k{display:inline-block;min-width:1.6em;color:var(--acc)}
.fwd{display:grid;grid-template-columns:10em 1fr;gap:6px 16px;max-width:92ch}
.fwd p{margin:0;line-height:1.7}
.fwd p.h{color:var(--acc);font-size:11px;letter-spacing:.1em;text-transform:uppercase;padding-top:4px}
.fwd p.h.bad{color:#f38ba8} .fwd p.h.ok{color:#a6e3a1}
.push .vs{margin:10px 0 0;padding:8px 14px;border-left:3px solid #f9e2af;background:#181825;border-radius:0 8px 8px 0;max-width:88ch;line-height:1.65}
.push .vs b{color:#f9e2af}
.grow{margin:12px 0 0;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:#181825;max-width:92ch}
.grow .gl{margin:0 0 4px;color:var(--mut);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase}
.grow .r{display:flex;flex-wrap:wrap;align-items:center;gap:3px 4px;padding:2px 0;border-top:1px dashed var(--line)}
.grow .bl{width:12.5em;color:var(--mut);font-size:11px}
.grow i{color:var(--mut);font-size:12px}
.grow .c{display:inline-block;padding:0 6px;border:1px solid var(--line);border-radius:5px;color:var(--mut);font-size:11.5px;line-height:1.6}
.grow .c.out{border-style:dashed;color:#f9e2af}
.grow .c.gate{border-color:var(--acc);color:var(--acc)}
.grow .c.new{background:#a6e3a1;border-color:#a6e3a1;color:#1e1e2e;font-weight:600}
p.rem{margin:14px 0 12px;padding:8px 14px;border:1px solid #a6e3a1;border-radius:8px;background:#181825;max-width:90ch;line-height:1.65}
p.rem b{color:#a6e3a1}
.plan{margin:8px 0 14px;padding-left:0;list-style:none;max-width:92ch}
.plan li{display:grid;grid-template-columns:6.5em 1fr;gap:12px;padding:6px 0;border-top:1px dashed var(--line);line-height:1.6}
.plan li b{color:var(--acc);font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:500}
.card{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px 18px;margin:8px 0 14px;padding:10px 16px;border:1px solid var(--line);border-radius:8px;background:#181825;max-width:92ch}
.card p{margin:0;font-size:13.5px;line-height:1.6}
.card p b{color:#f9e2af;font-family:"IBM Plex Mono",monospace;font-weight:500}
p code,li code,td code{background:var(--sur);padding:0 4px;border-radius:4px;color:#f5c2e7;font-size:.92em}
@media (max-width:760px){.fwd{grid-template-columns:1fr}.fwd p.h{padding-top:8px}
.grow .bl{width:100%}.card{grid-template-columns:1fr}.plan li{grid-template-columns:1fr;gap:2px}}
@media print{.grow,.push .vs,p.rem,.card{background:#fff}.grow .c.new{background:#ddd;color:#111}}
</style>'''

PROBLEM = '''<p class="plab">The problem, as the interviewer puts it</p><p class="pq">“Design an assistant that
answers employees' questions from their company's own documents, like the assistants Glean sells. A large
company has about 10 million documents across its wiki, shared drives, ticket tracker and chat, and about
100,000 employees who each ask a few questions a day. An employee types a question in plain English, asks
follow-ups in the same conversation, and within a few seconds gets an answer with links to the exact
documents it came from. Every document has its own permissions in its source system, and the assistant
must never show anyone something they could not open there. An edited document should be searchable
within about five minutes, and a deleted one should disappear. You rent the language model from a
provider.”</p><p class="pi"><b>What this really is.</b> This is retrieval-augmented generation (RAG): a
search engine whose results are read by a model instead of a person. When a question arrives, we find the
few pieces of the company's documents that answer it and that this employee is allowed to read, put them in
front of a rented model, and stream its answer back with a link to the piece behind each sentence. The
model is rented, slow and sometimes wrong, and every word in or out costs money; the design is
everything around it.
<b>In scope:</b> finding and permission-checking the pieces, keeping our copy of the documents fresh, the
streamed answer with checked citations, keeping quality up as things change, and where it all runs.
<b>Out of scope:</b> training models or how they work inside, an assistant that takes actions such as
filing tickets, searching images and audio, and billing the companies we serve.</p>'''

TOC = [
    ('Start', [('s-who', 'Who is who, and the one idea to hold on to'),
               ('s-req', 'What it must do, and the two numbers that shape it')]),
    ('Part 1 · The design', [('s-derive', 'Building it, one push at a time'),
                             ('s-design', 'The whole design, and one question through it'),
                             ('s-api', 'The API: one POST, answered as a stream'),
                             ('s-data', 'The data: what we copy, what we derive, what we keep')]),
    ('Part 2 · The seven hard parts', [
        ('s-perm', 'Only what she may read'),
        ('s-fresh', 'An edit in minutes, a delete in seconds'),
        ('s-rank', 'From 100 million chunks to 8'),
        ('s-turn', 'Turn four: follow-ups and the prompt'),
        ('s-cite', 'Citations that are true, and "not found"'),
        ('s-inject', 'A document that gives orders'),
        ('s-change', 'Every change is checked first')]),
    ('Part 3 · Running it', [('s-run', 'Where it runs, and what refuses in a split'),
                             ('s-break', 'When something breaks'),
                             ('s-ledger', 'Where the second goes, where the cents go'),
                             ('s-grow', 'How it grows, and how it is watched')]),
    ('End', [('s-recap', 'Remember it: the map, the numbers, the 45 minutes'),
             ('s-round', 'The technical round')]),
]


def body(fig):
    import rag_v4_a
    import rag_v4_b
    import rag_v4_c
    return ''.join(rag_v4_a.body(fig) + rag_v4_b.body(fig) + rag_v4_c.body(fig))
