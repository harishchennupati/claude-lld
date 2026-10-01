"""Builds llm-chatbot-rag-v4.html: v3's look, figures and sentences, edited to about two hours of
reading. The words are in rag_v4_text.py."""
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rag_v4_text as T  # noqa: E402

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
    return str(f)


n = 0
toc = '<nav class="toc"><p class="t">Contents</p>'
for group, items in T.TOC:
    toc += f'<p class="g">{group}</p><ol>'
    for sid, title in items:
        n += 1
        toc += f'<li><a href="#{sid}"><span class="n">{n:02d}</span><span>{title}</span></a></li>'
    toc += '</ol>'
toc += '</nav>'

main = v3.find('main')
main.clear()
main.append(BeautifulSoup('<header class="hero"><h1>Enterprise RAG assistant</h1></header>' + toc
                          + f'<section class="problem">{T.PROBLEM}</section>'
                          + f'<div class="body">{T.body(fig)}</div>', 'html.parser'))
out = str(v3)
open(ROOT + 'llm-chatbot-rag-v4.html', 'w').write(out)


def words(h):
    h = re.sub(r'<(script|style|svg)[\s\S]*?</\1>', ' ', h)
    return len(re.sub(r'<[^>]+>', ' ', h).split())


soup = BeautifulSoup(out, 'html.parser')
folds = sum(words(str(d)) for d in soup.find_all('details'))
print(f'v4: {words(out):,} words in all (outside diagrams), {folds:,} of them in folds')
