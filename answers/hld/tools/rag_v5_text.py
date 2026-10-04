"""The words of RAG v5. Written at about 80% of ASD-STE100: one idea in a sentence, 20 words or
fewer where possible and never more than 25, active voice, simple tenses, one word for one thing,
no semicolons, lists for three or more items, six sentences or fewer in a paragraph. Technical
terms stay. Numbers are rounded so the sums work in your head."""
import re


def p(s):
    """Collapse the line breaks of a triple-quoted paragraph."""
    return re.sub(r'\s*\n\s*', ' ', s.strip())


def tx(s):
    return f'<p class="tx">{p(s)}</p>'


def how(*items):
    return '<ol class="how">' + ''.join(f'<li>{p(i)}</li>' for i in items) + '</ol>'


def ul(*items):
    return '<ul class="how">' + ''.join(f'<li>{p(i)}</li>' for i in items) + '</ul>'


def say(s):
    return f'<p class="rem"><b>Say this:</b> {p(s)}</p>'


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


def calc(s):
    """Back-of-envelope arithmetic, kept as typed."""
    return f'<pre class="sum">{s.strip(chr(10))}</pre>'


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
            f'<p class="h ok">what we do</p><p>{p(fix)}</p></div>'
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
pre.sum{margin:10px 0 14px;padding:12px 16px;border:1px solid var(--line);border-radius:8px;background:#181825;max-width:102ch;font-family:"IBM Plex Mono",monospace;font-size:13px;line-height:1.7;color:var(--txt);overflow-x:auto;white-space:pre}
pre.sum b{color:#f9e2af;font-weight:600}
.plan{margin:8px 0 14px;padding-left:0;list-style:none;max-width:92ch}
.plan li{display:grid;grid-template-columns:6.5em 1fr;gap:12px;padding:6px 0;border-top:1px dashed var(--line);line-height:1.6}
.plan li b{color:var(--acc);font-family:"IBM Plex Mono",monospace;font-size:13px;font-weight:500}
.card{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:4px 18px;margin:8px 0 14px;padding:10px 16px;border:1px solid var(--line);border-radius:8px;background:#181825;max-width:92ch}
.card p{margin:0;font-size:13.5px;line-height:1.6}
.card p b{color:#f9e2af;font-family:"IBM Plex Mono",monospace;font-weight:500}
.map{margin:8px 0 14px;max-width:92ch;border:1px solid var(--line);border-radius:8px;background:#181825;padding:6px 16px}
.map p{margin:0;padding:7px 0;border-top:1px dashed var(--line);line-height:1.6;font-size:13.5px}
.map p:first-child{border-top:0}
.map p b{color:var(--acc);font-family:"IBM Plex Mono",monospace;font-weight:500;display:inline-block;min-width:9em}
ul.how{margin:8px 0 14px;max-width:92ch}
ul.pi{margin:6px 0 0;padding-left:1.2em;max-width:92ch}
ul.pi li{line-height:1.7;margin:2px 0}
p code,li code,td code{background:var(--sur);padding:0 4px;border-radius:4px;color:#f5c2e7;font-size:.92em}
@media (max-width:760px){.fwd{grid-template-columns:1fr}.fwd p.h{padding-top:8px}
.grow .bl{width:100%}.card{grid-template-columns:1fr}.plan li{grid-template-columns:1fr;gap:2px}.map p b{display:block}}
@media print{.grow,.push .vs,p.rem,.card,.map,pre.sum{background:#fff}.grow .c.new{background:#ddd;color:#111}}
</style>'''

PROBLEM = '''<p class="plab">The problem, as the interviewer puts it</p><p class="pq">“Design an assistant that
answers employees' questions from their company's own documents. Think of the assistants Glean sells.
A large company has about 10 million documents in its wiki, shared drives, ticket tracker and chat.
About 100,000 employees each ask a few questions a day. An employee types a question in plain English
and asks follow-ups in the same conversation.</p><p class="pq">Within a few seconds, the employee gets an
answer with links to the documents it came from. Every document has permissions in its source system. The
assistant must never show a document that the employee could not open there. An edited document must
be searchable within about five minutes. A deleted document must disappear. You rent the language
model from a provider.”</p><p class="pi"><b>What this is.</b> This is retrieval-augmented generation
(RAG). A RAG system is a search engine whose results a model reads, not a person.</p><p class="pi">For each
question we do three things. We find the few <b>chunks</b>, pieces of a few hundred words, that answer it and
that this employee may read. We put them in front of a rented model. We stream the answer back, with
a link for each sentence. The model is rented, slow and sometimes wrong, and every token in or out
costs money. So the design is everything around the model.</p>
<ul class="pi"><li><b>In scope:</b> finding and permission-checking the chunks, keeping our copy of
the documents fresh, the streamed answer with checked citations, keeping quality measured, and
running it.</li><li><b>Out of scope:</b> training models, an assistant that takes actions such as
filing tickets, search in images and audio, and billing.</li></ul>'''

TOC = [
    ('Start', [('s-who', 'Who is who, and the one idea to remember'),
               ('s-req', 'What it must do, and the numbers')]),
    ('Part 1 · The design', [('s-derive', 'Building it, one push at a time'),
                             ('s-design', 'The whole design, and one question through it'),
                             ('s-api', 'The API and the data')]),
    ('Part 2 · The hard parts', [
        ('s-perm', 'Permissions: only what she may read'),
        ('s-fresh', 'Freshness: an edit in minutes, a delete in seconds'),
        ('s-rank', 'Retrieval: from 100 million chunks to 8'),
        ('s-turn', 'Follow-ups and the prompt'),
        ('s-cite', 'Citations that are true, and "not found"'),
        ('s-inject', 'A document that gives orders')]),
    ('Part 3 · Running it', [('s-run', 'Where it runs'),
                             ('s-scale', 'How each part scales'),
                             ('s-break', 'When something breaks'),
                             ('s-cap', 'Consistency: what a network split does'),
                             ('s-ledger', 'The latency budget and the cost'),
                             ('s-sec', 'Security and privacy'),
                             ('s-change', 'Quality: how a change goes out'),
                             ('s-watch', 'What to watch')]),
    ('End', [('s-recap', 'Remember it: the map, the numbers, the 45 minutes'),
             ('s-round', 'The technical round')]),
]


def body(fig):
    import rag_v5_a
    import rag_v5_b
    import rag_v5_c
    return ''.join(rag_v5_a.body(fig) + rag_v5_b.body(fig) + rag_v5_c.body(fig))
