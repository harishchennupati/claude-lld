"""Builds llm-chatbot-rag-v5.html: v3's look and figures, with a text written at about 80% of
ASD-STE100, rounded numbers, hard parts at interview depth, and a fuller Part 3 on running it.
The words are in rag_v5_text.py and rag_v5_a/b/c.py."""
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rag_v5_text as T  # noqa: E402

ROOT = '/home/user/claude-lld/'
v3 = BeautifulSoup(open(ROOT + 'llm-chatbot-rag-v3.html').read(), 'html.parser')
FIGS = v3.find_all('figure')


def fig(i, caption=None):
    f = BeautifulSoup(str(FIGS[i]), 'html.parser').figure
    if caption is not None:
        cap = f.find('figcaption')
        new = BeautifulSoup(f'<figcaption><p class="cap">{caption}</p></figcaption>', 'html.parser')
        if cap:
            cap.replace_with(new)
        else:
            f.append(new)
    # the reused drawings carry a few exact numbers; round them like the text
    out = str(f)
    for a, b in [('5,187', '5,200'), ('0.86 s', '0.9 s'), ('0.86', '0.9'), ('6.6 s', '7 s')]:
        out = out.replace(a, b)
    return out


n = 0
toc = '<nav class="toc"><p class="t">Contents</p>'
for group, items in T.TOC:
    toc += f'<p class="g">{group}</p><ol>'
    for sid, title in items:
        n += 1
        toc += f'<li><a href="#{sid}"><span class="n">{n:02d}</span><span>{title}</span></a></li>'
    toc += '</ol>'
toc += '</nav>'

v3.head.append(BeautifulSoup(T.CSS, 'html.parser'))
if v3.title:
    v3.title.string = 'Enterprise RAG assistant · HLD v5'
main = v3.find('main')
main.clear()
main.append(BeautifulSoup('<header class="hero"><h1>Enterprise RAG assistant</h1></header>' + toc
                          + f'<section class="problem">{T.PROBLEM}</section>'
                          + f'<div class="body">{T.body(fig)}</div>', 'html.parser'))
out = str(v3)
open(ROOT + 'llm-chatbot-rag-v5.html', 'w').write(out)


def words(h):
    h = re.sub(r'<(script|style|svg)[\s\S]*?</\1>', ' ', h)
    return len(re.sub(r'<[^>]+>', ' ', h).split())


soup = BeautifulSoup(out, 'html.parser')
folds = sum(words(str(d)) for d in soup.find_all('details'))
print(f'v5: {words(out):,} words in all (outside diagrams), {folds:,} of them in folds')
