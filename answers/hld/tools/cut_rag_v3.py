"""Builds llm-chatbot-rag-v4.html from v3 without rewriting a word: the heaviest mechanics move into
"Deeper, if they push" folds (styled like v3's own folds). Every sentence, figure and interviewer
question of v3 stays; only where it sits changes."""
import re
from bs4 import BeautifulSoup

SRC = '/home/user/claude-lld/llm-chatbot-rag-v3.html'
OUT = '/home/user/claude-lld/llm-chatbot-rag-v4.html'
soup = BeautifulSoup(open(SRC).read(), 'html.parser')
body = soup.find('div', class_='body')
blocks = [c for c in body.children if getattr(c, 'name', None)]


def text(el):
    return re.sub(r'\s+', ' ', el.get_text(' ')).strip()


def find(start, kind=None):
    """The top-level block whose text starts with `start` (a figure: whose title starts with it)."""
    hits = []
    for b in blocks:
        t = text(b.find(class_='ft')) if b.name == 'figure' and b.find(class_='ft') else text(b)
        if t.startswith(start) and (kind is None or b.name == kind):
            hits.append(b)
    assert len(hits) == 1, (start, len(hits))
    return hits[0]


def fold(title, first, last=None, note='if they push deeper'):
    """Wrap the blocks from `first` to `last` (inclusive, consecutive) in a v3-style fold."""
    a = find(first)
    b = find(last) if last else a
    group, cur = [], a
    while True:
        group.append(cur)
        if cur is b:
            break
        cur = cur.find_next_sibling()
    d = soup.new_tag('details', attrs={'class': 'fold deep'})
    s = soup.new_tag('summary')
    s.append(BeautifulSoup(f'Deeper: {title}<span>{note}</span>', 'html.parser'))
    d.append(s)
    a.insert_before(d)
    for el in group:
        d.append(el.extract())
    return d


# ---- the moves: mechanics an interviewer rarely asks for, kept word for word in a fold
fold('one chunk record, byte by byte, on its shard', 'One chunk record, and where its bytes live')
fold('the final check as SQL, line by line', 'WITH RECURSIVE his(principal)', 'WITH RECURSIVE builds lists')
fold('the fetch ticket as SQL, and how a worker uses it', '-- before fetching doc_91', 'For a new document the INSERT')
fold('how each change event is handled, and the one late-write hole',
     'When only a document\'s sharing or filter fields change', 'The one hole: a worker that commits')
fold('the question classifier, and how the conversation itself is kept safe',
     'The question classifier reads every new turn as it arrives')
fold('the signals the canary watches, and their limits', 'signal what it counts limit')
fold('the switch row, before and after', 'retrieval_target, one row in the metadata database',
     'Each orchestrator reads this row every 10 seconds')
fold('restoring the metadata database, and the three repairs after it',
     'The metadata database keeps a nightly backup', 'Every fetch_next is raised by a million')

css = soup.new_tag('style')
css.string = 'details.fold.deep{border-style:dashed}'
soup.head.append(css)
open(OUT, 'w').write(str(soup))


def words(html):
    h = re.sub(r'<(script|style|svg)[\s\S]*?</\1>', ' ', html)
    return len(re.sub(r'<[^>]+>', ' ', h).split())


out = str(soup)
folds = sum(words(str(d)) for d in soup.find_all('details'))
print(f'wrote {OUT}: {words(out):,} words; in folds {folds:,}; main text {words(out) - folds:,}')
v3 = open(SRC).read()
v3s = BeautifulSoup(v3, 'html.parser')
v3f = sum(words(str(d)) for d in v3s.find_all('details'))
print(f'v3: {words(v3):,} words; in folds {v3f:,}; main text {words(v3) - v3f:,}')
