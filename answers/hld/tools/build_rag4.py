"""Builds llm-chatbot-rag-v4.html: the same look and the best figures as v3, a shorter text
with the derivation as its spine."""
import re
import sys

SRC = '/home/user/claude-lld/llm-chatbot-rag-v3.html'
OUT = '/home/user/claude-lld/llm-chatbot-rag-v4.html'
v3 = open(SRC).read()
STYLE = re.search(r'<style>[\s\S]*?</style>', v3).group(0)
SCRIPT = re.findall(r'<script[\s\S]*?</script>', v3)[0]
FIGS = re.findall(r'<figure[\s\S]*?</figure>', v3)


def fig(i, caption=None, title=None):
    f = FIGS[i]
    if title is not None:
        f = re.sub(r'<h3 class="ft">[\s\S]*?</h3>', f'<h3 class="ft">{title}</h3>', f, count=1)
    if caption is not None:
        cap = f'<figcaption><p class="cap">{caption}</p></figcaption>'
        if '<figcaption' in f:
            f = re.sub(r'<figcaption[\s\S]*?</figcaption>', cap, f, count=1)
        else:
            f = f.replace('</figure>', cap + '</figure>')
    return f


EXTRA_CSS = """<style>
.grow{margin:12px 0 18px;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:#181825;font-size:12px;line-height:2}
.grow .l{color:var(--mut);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;margin-right:8px}
.grow span.p{display:inline-block;padding:0 8px;margin:0 4px 0 0;border:1px solid var(--line);border-radius:6px;color:var(--mut);line-height:1.7}
.grow span.p.new{border-color:var(--acc);background:var(--acc);color:#1e1e2e;font-weight:600}
.xy{margin:10px 0;padding:8px 14px;border-left:3px solid #f9e2af;background:var(--sur);border-radius:0 8px 8px 0}
.xy b{color:#f9e2af}
.step h3{font-family:"Space Grotesk",-apple-system,"Segoe UI",system-ui,sans-serif;font-size:18px;color:var(--txt);margin:34px 0 8px}
.step h3 .k{color:var(--acc);margin-right:8px}
.fwd{display:grid;grid-template-columns:9.5em 1fr;gap:4px 14px;margin:8px 0}
.fwd .h{color:var(--acc);font-size:12px;letter-spacing:.06em;text-transform:uppercase;padding-top:2px}
.fwd .h.bad{color:#f38ba8} .fwd .h.ok{color:#a6e3a1}
.fwd p{margin:0}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:12px 0}
.cards>div{background:var(--sur);border-radius:8px;padding:10px 14px}
.cards h4{margin:0 0 6px;color:var(--acc);font-family:"Space Grotesk",sans-serif;font-size:15px}
.cards ul{margin:0;padding-left:18px} .cards li{font-size:13px;margin:3px 0}
p code,li code,td code,.qa code{background:var(--sur);padding:0 4px;border-radius:4px;color:#f5c2e7;font-size:.95em}
pre.code{background:#181825;border:1px solid var(--line);border-radius:8px;padding:12px 14px;overflow-x:auto;font-size:12.5px;line-height:1.55}
@media (max-width:760px){.fwd{grid-template-columns:1fr}.cards{grid-template-columns:1fr}.req{grid-template-columns:1fr}}
</style>"""


def section(sid, num, title, body):
    return f'<section id="{sid}"><h2 id="h-{sid}"><span class="num">{num}</span>{title}</h2>{body}</section>'


def xy(text):
    return f'<div class="xy">{text}</div>'


def qa(q, a):
    return f'<div class="qa"><b>{q}</b><p>{a}</p></div>'


def table(head, rows, cls=''):
    th = ''.join(f'<th>{h}</th>' for h in head)
    tr = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def fold(summary, body):
    return f'<details><summary>{summary}</summary>{body}</details>'


PARTS = [
    ['Orchestrator', 'Search index', 'Model provider'],
    ['Ingest workers', 'GPU pool: embedding model, reranker', 'Object storage'],
    ['Metadata database', 'Identity sync', 'Redis'],
    ['Connectors', 'Ingest queue'],
    ['Conversation store', 'rewrite model', 'question classifier'],
    ['citation checker', 'output filter'],
    ['Model router', 'Fallback provider', 'Trace log', 'Eval runner'],
]


def grown(k):
    chips = ''
    for i, ps in enumerate(PARTS[:k + 1]):
        for p in ps:
            chips += f'<span class="p{" new" if i == k else ""}">{p}</span>'
    total = sum(len(ps) for ps in PARTS[:k + 1])
    return f'<div class="grow"><span class="l">the design so far · {total} parts</span>{chips}</div>'


def step(k, title, first, wrong, fix, x):
    return (f'<div class="step"><h3><span class="k">{k + 1}</span>{title}</h3>'
            f'<div class="fwd"><div class="h">first idea</div><p>{first}</p>'
            f'<div class="h bad">what goes wrong</div><p>{wrong}</p>'
            f'<div class="h ok">what we do</div><p>{fix}</p></div>'
            + ''.join(xy(t) for t in x) + grown(k) + '</div>')


import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from content import build  # noqa: E402

body, toc = build(globals())
html = (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Enterprise RAG assistant</title>'
        f'<link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family='
        f'IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Space+Grotesk:wght@500;600;700'
        f'&display=swap" rel="stylesheet">{STYLE}{EXTRA_CSS}</head><body><main>'
        f'<header class="hero"><h1>Enterprise RAG assistant</h1>'
        f'<p class="dek">A search engine whose results a model reads. About 75 minutes.</p></header>'
        f'{toc}{body}</main>{SCRIPT}</body></html>')
open(OUT, 'w').write(html)
text = re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style|svg|pre)[\s\S]*?</\1>', ' ', html))
print('wrote', OUT, len(html), 'bytes;', len(text.split()), 'words outside figures and code')
