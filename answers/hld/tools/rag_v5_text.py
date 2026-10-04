"""The words of RAG v5: v3's structure, written at about 80% of ASD-STE100. One idea in a sentence,
25 words or fewer, active voice, simple tenses, one word for one thing, no semicolons, a list for
three or more items, six sentences or fewer in a paragraph. Technical terms stay and are explained
once. Numbers are rounded so the sums work in your head."""
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


def wl(s):
    return f'<p class="wl"><b>The one hole:</b> {p(s)}</p>'


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


def band(k, d):
    return f'<div class="partband"><p class="k">{k}</p><p class="d">{d}</p></div>'


def h2(i, t):
    return f'<h2 id="{i}">{t}</h2>'


def h3(t):
    return f'<h3 class="sub">{t}</h3>'


def pre(s, cls='sql'):
    return f'<pre class="{cls}">{s.strip(chr(10))}</pre>'


def qa(q, a):
    return f'<p><b>{p(q)}</b></p><p>{p(a)}</p>'


CSS = '''<style>
ul.how{margin:8px 0 14px;max-width:92ch}
ul.pi{margin:6px 0 0;padding-left:1.2em;max-width:92ch}
ul.pi li{line-height:1.7;margin:2px 0}
p code,li code,td code{background:var(--sur);padding:0 4px;border-radius:4px;color:#f5c2e7;font-size:.92em}
.fold p b{color:var(--acc)}
</style>'''

PROBLEM = '''<p class="plab">The problem, as the interviewer puts it</p><p class="pq">“Design an assistant that
answers employees' questions from their company's own documents. Think of the assistants Glean sells.
A large company has about 10 million documents in its wiki, shared drives, ticket tracker and chat.
About 100,000 employees each ask a few questions a day. An employee types a question in plain English
and asks follow-ups in the same conversation.</p><p class="pq">Within a few seconds, the employee gets
an answer with links to the documents it came from. Every document has permissions in its source
system. The assistant must never show a document that the employee could not open there. An edited
document must be searchable within about five minutes. A deleted document must disappear. You rent the
language model from a provider.”</p><p class="pi"><b>What this really is.</b> This is retrieval-augmented
generation (RAG). A RAG system is a search engine whose results a model reads, not a person.</p>
<p class="pi">Before the model sees anything, we find the few <b>chunks</b>, pieces of a few hundred
words, that answer the question and that this employee may read. After the model writes, a citation
reaches her only if it points at a chunk we gave the model. A small checker scores whether the chunk
supports its sentence. The model is rented, slow and sometimes wrong. The design is everything around
it.</p>
<ul class="pi"><li><b>In scope:</b> finding and permission-checking the chunks, keeping our copy of
the documents fresh, the streamed answer with checked citations, keeping quality as things change,
and where it runs.</li><li><b>Out of scope:</b> training or fine-tuning models, how a model works
inside, an assistant that takes actions, search in images and audio, and billing.</li></ul>'''

TOC = [
    ('Start · Who is in the room, and what is asked', [
        ('s-who', 'Who is who, and one question from Enter to the last citation'),
        ('s-req', 'What the interviewer expects: five jobs, vector memory and tokens a second')]),
    ('Part 1 · The design', [
        ('s-api', 'The chat stream: one POST, answered as server-sent events'),
        ('s-design', 'The whole design in one picture'),
        ('s-data', 'The data: what we copy, what we derive, and what we keep')]),
    ('Part 2 · The seven hard parts', [
        ('s-perm', 'Only what each employee may read: a filter inside both searches, and one exact check'),
        ('s-fresh', 'An edit in minutes, a delete in seconds: the latest fetch wins'),
        ('s-rank', 'From 100 million chunks to 8: two searches, rank fusion and a reranker'),
        ('s-turn', 'Turn four: understanding the question, packing the prompt, and what runs beside what'),
        ('s-cite', 'A citation must point at a chunk we gave the model, and "not found" is an answer'),
        ('s-inject', 'A document that gives orders: prompt injection'),
        ('s-change', 'Every change is checked before everyone sees it')]),
    ('Part 3 · Running it', [
        ('s-run', 'Where it runs: a cell in each company\'s area'),
        ('s-cap', 'In a network split: only the final check refuses'),
        ('s-break', 'When something breaks: the model provider first'),
        ('s-grow', 'How it grows: ten times the questions, or ten times the documents'),
        ('s-ledger', 'Where the second goes, and where the cents go'),
        ('s-sec', 'Security, privacy, and what we keep for how long'),
        ('s-watch', 'Rollout, and what to watch')]),
    ('End', [('s-recap', 'Remember it: the whole page on one map, and the technical round')]),
]


def body(fig):
    import rag_v5_a
    import rag_v5_b
    import rag_v5_c
    return ''.join(rag_v5_a.body(fig) + rag_v5_b.body(fig) + rag_v5_c.body(fig))
