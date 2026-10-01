"""Part 3 and the end: where it runs, failures, the two ledgers, growth, recall, the technical round."""
from rag_v4_text import band, fu, h2, how, qa, rem, table, tx


def body(fig):
    B = []
    B.append(band('Part 3', 'Running it'))

    # ---------------------------------------------------------------- where it runs
    B.append(h2('s-run', 'Where it runs: a cell in each company\'s area, and what refuses in a network split'))
    B.append(tx('''A <b>region</b> is one place where a cloud platform has data centres, such as Frankfurt;
        its zones sit about a millisecond apart. A company's cell runs across three zones of one region
        inside the area it chose, keeps its backups in a second region there, and sends prompts only to
        model endpoints inside the area, so its text never leaves, not even for the fallback. One region
        is enough at 99.9%: a second live cell would double the cost to save a few hours in a rare
        regional outage.'''))
    B.append(fig(12, '''Top: dashed boxes are cells. Bottom: one question arriving in zone A, which holds
        every primary; a question arriving in B or C reads them from there.'''))
    B.append(tx('''A commit to the metadata database waits until a copy in another zone has it, because of
        the identity provider: we answer its changes only after the commit, and it never sends a change
        twice, so a removal lost with a dead primary would let a removed employee read on.'''))
    B.append(tx('''<b>In a network split, only the final check refuses.</b> In a <b>network partition</b>,
        two groups of machines cannot reach each other, and the <b>CAP theorem</b> says each part of a
        system must then choose <b>consistency</b> (every read sees the latest truth) or
        <b>availability</b> (every request is answered, perhaps from stale data). Ask of each part: if it
        is cut off, what does she see?'''))
    B.append(how(
        '''<b>The final check</b> chooses consistency: a zone that cannot reach the database primary
        refuses, and the load balancer moves its questions to a zone that can.''',
        '''<b>The search index</b> chooses availability: a cut-off copy answers from what it holds, which
        is safe because the final check comes after it.''',
        '''<b>Ingest and the identity sync</b> queue their changes until the split heals.''',
        '''<b>The conversation store</b>: the question is answered as a first turn and not saved.'''))
    B.append(rem('''one cell per large company, in its own area, across three zones; in a split, the gate
        chooses consistency and everything before it chooses availability.'''))
    B.append(fu(
        ('Why does every final check read the primary, even from another zone?',
         '''A copy in its own zone can lag a removal, and the final check is the one step that must be
         exact; the primary is only a millisecond away. The cost: a failover of the primary refuses
         questions in every zone for about 30 seconds.''')))

    # ---------------------------------------------------------------- when it breaks
    B.append(h2('s-break', 'When something breaks: the model provider first'))
    B.append(tx('''<b>RPO</b>, the data a failure loses, is zero for a lost machine or zone, because the
        database and the ingest queue confirm a write only once another zone has it. The provider fails
        most often, so here is the router's <b>circuit breaker</b> through an outage; its states are named
        after an electric circuit: <b>closed</b>, calls pass; <b>open</b>, calls go to the fallback;
        <b>half open</b>, trial calls test the provider.'''))
    B.append(fig(13, 'A 529 is the provider\'s "overloaded" error.'))
    B.append(table(['what fails', 'what employees see meanwhile', 'back in'], [
        ['the GPU pool', '''No embeddings: keyword search only. No reranker: fusion order, no abstaining.
         No checker: citations marked "not checked".''', 'minutes'],
        ['one index node', 'Nothing; two other copies answer while a peer copies the shard back.',
         'about 35 min'],
        ['the database primary', '''"I can't check permissions right now" while a copy is
         promoted.''', 'about 30 s'],
        ['Redis', '''Principal lists come from the database; no answer cache; each orchestrator counts a
         sixth of each provider limit itself.''', 'seconds'],
        ['a source, or the identity provider', '''That source's edits wait, and an alarm fires. Signed-in
         employees keep asking; no one new can sign in.''', 'when it recovers'],
    ]))
    B.append(tx('''A corrupted index or a lost region means no answers until a restore: 1 to 1.5 hours from
        the 6-hourly snapshot and the stored vectors, or hours in the area's second region. Three index
        copies protect against a lost machine, not a bad change, which reaches all three at once; that is
        why every change builds a new index beside the old one. The database can be restored to any
        second from its nightly backup and write-ahead log; then the connectors re-read every change
        since, and the daily sweep runs at once for the deletes no one will resend.'''))
    B.append(rem('''no first word in 3 seconds moves a question to the fallback; half of 20 calls failing in
        10 seconds opens the breaker; both providers down means search-only answers, never an error.'''))
    B.append(fu(
        ('One index node is slow, not down. What happens to every question?',
         '''Each question asks all 4 shards, so one slow copy would slow them all. A shard still searching
         after 80 ms is asked again on its copy in another zone, and the first answer wins; a shard silent
         at 150 ms is left out.''')))

    # ---------------------------------------------------------------- ledgers
    B.append(h2('s-ledger', 'Where the second goes, and where the cents go'))
    B.append(tx('''Interviewers ask for these two ledgers, usually as "where would you cut?". First, the
        time to Asha's first word, from the picture in Part 1:'''))
    B.append(table(['step', 'takes', 'clock'], [
        ['her turn saved; principals read; question embedded and classified', '20 ms', '20 ms'],
        ['vector and keyword searches on all 4 shards, side by side; fusion', '41 ms', '61 ms'],
        ['the reranker scores the 91 candidates fusion produced', '91 ms', '152 ms'],
        ['the final check on 20 ids; the best 8 packed into the prompt', '5 ms', '157 ms'],
        ['the provider reads 5,187 tokens and writes its first word', 'about 700 ms', '0.86 s'],
        ['a follow-up adds the rewrite before the searches', '+ 400 ms', '1.26 s'],
    ], 'led'))
    B.append(tx('''Most of the second is the provider's. To reach 0.5 seconds, the lever is a smaller,
        faster model for ordinary questions; reranking 50 instead of 100 saves only about 50 ms.'''))
    B.append(tx('''Second, the cost of an answer: 6,000 input tokens × $3 a million = 1.8 cents, plus 400
        output × $15 a million = 0.6 cents. Three quarters is input, so every lever is about fewer input
        tokens, or cheaper ones:'''))
    B.append(table(['lever', 'what it saves'], [
        ['the provider caches the 1,100 tokens of instructions that open every prompt', '''about $1,500
         a day, so 2.1 cents an answer; cached tokens also do not count against the rate limit'''],
        ['8 chunks after the reranker, not 20 (push 4)', 'about $9,000 a day'],
        ['the answer cache serves about 1 first turn in 10', 'about $500 a day; those start in 0.2 s'],
        ['no model call when the best score is below 0.30', 'a whole call per unanswerable question'],
        ['a small rewrite model, not the large one', 'about $900 a day: $450 against $1,350'],
    ], 'led'))
    B.append(tx('''<b>The answer cache</b>, in Redis, serves a first turn only when its prompt would repeat an
        earlier one exactly: same prompt version and model, same question as searched, same 8 chunks after
        the final check. That is safe without knowing who asked, because whoever reaches those 8 chunks
        has just passed the final check on all of them. A cache keyed by permissions would rarely hit, and
        one that matches by meaning could answer a different question. Follow-ups carry the
        conversation, so they are never cached.'''))
    B.append(rem('''the first word is mostly the provider's 0.7 seconds; the cost is three quarters input,
        so the levers are fewer input tokens and cached ones.'''))

    # ---------------------------------------------------------------- growth
    B.append(h2('s-grow', 'How it grows, and how it is watched'))
    B.append(tx('''At ten times today the index runs out of RAM first: one bit a number in RAM, rescored
        from SSD. The provider's limit goes next: ordinary questions to a smaller model, and across
        providers. Then the GPU pool: more GPUs, or rerank 50. The sources' API quotas cap how fast a new
        company loads. Above the planned peak, each employee may ask 60 questions an hour, and a
        question whose provider bucket is short waits up to 2 seconds, then goes to the fallback. A model
        is pinned by its exact version id, never "latest", which the provider could move.'''))
    B.append(table(['watch', 'page someone when'], [
        ['the first word, 95th percentile', 'above 2 seconds for 10 minutes'],
        ['the model router\'s breakers', 'a breaker opens'],
        ['questions refused by the final check', 'more than 1 in 1,000: the primary is slow or unreachable'],
        ['chunks dropped by the final check', 'more than 2%: the search side lags'],
        ['ingest lag, edit to searchable', 'above 5 minutes for 15 minutes'],
        ['citations failing the check; cost per answer', 'half again above usual; above 3 cents'],
    ]))
    B.append(fu(
        ('A new company connects 10 million documents on Monday. When can its employees ask?',
         '''After about a day: the most recently edited documents load first. The sources' quotas leave
         about 32 documents a second, so all 10 million take about 3.5 days, while embedding them takes
         only about 2 hours. They come through a separate backfill topic, so the load never delays anyone's
         edits.''')))

    # ================================================================ End
    B.append(band('End', 'Remember it'))
    B.append(h2('s-recap', 'Remember it: the map, the numbers, and the 45 minutes'))
    B.append(tx('''If you can redraw this map from memory, you can rebuild the page. Read only the coloured
        word that starts each line, say the rest aloud, then check. Do it on day 1, 3, 7 and 10.'''))
    B.append(fig(14, ''))
    B.append(tx('<b>The numbers to carry into the room:</b>'))
    card = [
        ('chunk', '480 tokens, 50 overlap'), ('vector', '1,024 numbers'),
        ('index', '100 M chunks, 127 GB at 1 byte'), ('nodes', '4 shards × 3 copies = 12'),
        ('peak', '50 questions a second'), ('prompt', '6,000 in, 400 out'),
        ('tokens', '18 M a minute'), ('bill', '$12,000 a day, 2.4 ¢'),
        ('first word', '0.9 s; done 6.6 s'), ('funnel', '50 + 50 → 100 → 20 → 8'),
        ('fusion', '1 / (60 + rank)'), ('abstain', 'best score below 0.30'),
        ('cite', 'checker score 0.5 or more'), ('cache', 'principals 60 s'),
        ('fresh', 'edit 5 min, delete 1 min'), ('refresh', 'every 10 s'),
        ('breaker', '3 s · 10 s · probe 30 s'), ('checks', '1,000 golden; 5% canary a day'),
        ('available', '99.9% = 43 min a month'), ('GPUs', '12, 4 a zone'),
        ('servers', '6 orchestrators, 150 ingest'),
    ]
    B.append('<div class="card">' + ''.join(f'<p><b>{k}</b> {v}</p>' for k, v in card) + '</div>')
    B.append(tx('''<b>How to run the 45 minutes.</b> Interviews on this problem follow the same arc; have
        the opening of each step ready:'''))
    plan = [
        ('0–5 min', '''<b>Requirements.</b> Read back the five jobs, ask about scale, and open with "This
         is a search engine whose results a model reads; the design is everything around the model, and
         two things in it must be exact."'''),
        ('5–10 min', '<b>The two sums</b>, vector memory and tokens a minute, and what each decides.'),
        ('10–18 min', '''<b>Draw the picture</b> in three bands, parts in the order of the pushes, the two
         gates marked.'''),
        ('18–25 min', '''<b>One question through it</b>, with timings: approximate up to the reranker,
         exact at the final check, streamed and checked after the model.'''),
        ('25–40 min', '''<b>The deep dives they pick.</b> Permissions and freshness come up most; have
         retrieval, follow-ups and citations ready. If they leave it to you, ask: "I can go deeper on
         permissions, freshness or answer quality. Which matters most to you?"'''),
        ('40–45 min', '<b>What it survives</b>: the provider failing, quality checks, cells, the cost.'),
    ]
    B.append('<ol class="plan">' + ''.join(f'<li><b>{t}</b><span>{" ".join(s.split())}</span></li>'
                                           for t, s in plan) + '</ol>')

    # ---------------------------------------------------------------- technical round
    B.append(h2('s-round', 'The technical round: eight questions interviewers push on'))
    B.append(qa('A manager says yesterday\'s answer was wrong. How do you find which step failed?',
        '''Open the turn in the trace log, which keeps every step's inputs and outputs. Was the rewritten
        question right? Someone who knows the subject names the chunk that answers: was it among the 100
        candidates (recall), the reranker's 20 (ranking), the 8 packed (packing)? Was it cited, and what
        did the checker say? Each step points to its own fix, and the question joins the golden set so
        the fix is checked.'''))
    B.append(qa('''A connector maps a restricted page as readable by all staff. The search filter and the
        final check both trust that row. What catches it?''',
        '''Neither can, so it is caught where permissions are written. Each connector ships with a
        permission test suite, documents whose readers are known, run on every release; each run counts
        documents whose readers got wider, and a jump pages someone. The conversation store's chunk ids
        then say who received the page.'''))
    B.append(qa('A folder of salaries was shared with all staff by mistake years ago. Who can find it now?',
        '''Everyone, since the source allows it; the assistant would turn a forgotten mistake into a
        one-line answer. So admins can exclude folders or sensitivity labels from indexing, and a weekly
        report lists widely shared documents matching sensitive terms for their owners to fix at the
        source. A file shared only by link never becomes a principal: a link is not permission to be
        found.'''))
    B.append(qa('Why not give the model a search tool and let it search until it is satisfied?',
        '''A loop handles two-hop questions better, but each round adds a model call, about 0.7 seconds,
        input tokens grow two to three times, and a poisoned chunk could steer the next search. So our
        code decides the searches; if two-hop questions become common in the golden set, that changes.'''))
    B.append(qa('''"How many P1 tickets are open for payments?" or "Summarise this 40-page design
        doc." What happens?''',
        '''The classifier marks it as a count or a summary. A count becomes a query on the filter fields
        every chunk record carries, under the same permission filter and final check, counted once per
        document by our code, never guessed by the model. A summary gets a budget of its own: the whole
        document, up to about 30,000 tokens; a longer one is summarised section by section.'''))
    B.append(qa('An employee asks in German, and most documents are in English. What still works?',
        '''Vector search, if the embedding model was trained on many languages, because meanings land near
        each other whatever the language. Keyword search does not, so the rewrite model also writes an
        English version for it, and the model answers in German from English chunks.'''))
    B.append(qa('''In a shared cell, one company uses the whole token limit all morning. What protects the
        others?''',
        '''Each company has its own token bucket inside the cell's, sized by its seats; it may borrow
        unused share up to a cap, and over its share it goes to the fallback provider first. The
        reranker's queue takes each company's work in turn, and a company that keeps hitting its share
        moves to a cell of its own.'''))
    B.append(qa('''She loses access to a document an old answer cited. What does she see when she reopens
        the conversation?''',
        '''The text stays, but each citation is checked again when the conversation is shown: one she may
        no longer read loses its link and says "source no longer available to you", and a turn that
        drew on it is never carried into a new prompt. A legal delete goes further and redacts the text.'''))
    return B
